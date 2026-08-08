"""Data layer for `scg monitor` (STORY-701/702).

Reads `.scalene/audit.log` and `.scalene/state/*.json` as plain files via
polling, not a filesystem-watch dependency (docs/ARCHITECTURE.md sec 11.1-
11.2). Pure functions/classes with no `textual` import, so this stays
testable without a terminal — the TUI layer (`monitor_app.py`) is a thin
composition over this module.

2026-07-17 (docs/ARCHITECTURE.md sec15): STORY-702's editable-and-applyable
suggested-onboard-command workflow is removed -- clearing a destination now
always takes two explicit steps (a real scan, then a hand-authored rule),
not one runnable command, so there's no longer a single string to suggest
and apply from this panel.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from .hook_adapter import DEFAULT_AUDIT_LOG
from .onboard import identify_targets
from .scan_cache import DEFAULT_CACHE_PATH, PENDING_TIMEOUT_SECONDS, ScanCache, ScanCacheError
from .scanner import Resource
from .taint_state import DEFAULT_STATE_DIR


@dataclass(frozen=True)
class SessionInfo:
    session_id: str
    trust: str
    sensitivity: str
    updated_at: float


@dataclass(frozen=True)
class ToolCallEvent:
    """docs/ARCHITECTURE.md sec20.3 (STORY-1603, renamed from BlockEvent,
    2026-07-22): every call `pre_tool_use` evaluates is now logged, allow
    or block -- not only blocks -- so this is a genuine tool-call stream,
    not a block-only feed. `event` is `"allow"` or `"block"`; `block_kind`
    (sec20.1) is `"confirmed_bad"` / `"uncleared"` / `None` (always `None`
    for an allow). Both new fields default so an old, pre-sec20 audit-log
    line (block-only, no `block_kind`/`tool_input`) still parses instead of
    crashing the reader.

    `log_offset` (2026-07-30, direct user report: "review status is not
    persisted -- always resets to N pending reviews on restart"): the byte
    offset where this event's own line starts in audit.log -- a stable,
    real identity for this exact event, used to record ("review_resolved",
    below) that a specific block event was actually dealt with, so a
    restart's full re-read of the log doesn't re-queue it. Defaults to -1
    (never a real file offset) for events constructed directly, not via
    AuditTail.poll() -- most existing tests build ToolCallEvent by hand and
    don't need this."""

    session_id: str
    tool_name: str
    reason: str
    event: str = "block"
    block_kind: str | None = None
    tool_input: dict = field(default_factory=dict)
    log_offset: int = -1
    # docs/ARCHITECTURE.md sec22.2 (STORY-1701): when the call actually
    # happened, for the queue screen's "Age" column. Defaults to 0.0 for an
    # audit-log line written before this field existed (`hook_adapter.py`'s
    # `pre_tool_use`) -- same graceful-degrade convention as `block_kind`/
    # `tool_input` above, not a crash on old data.
    timestamp: float = 0.0


@dataclass(frozen=True)
class ReviewResolution:
    """A `{"event": "review_resolved", "resolved_offset": ...}` audit-log
    line (written by monitor_app._on_review_resolved) -- not a tool call
    itself, just a marker that the block event at `resolved_offset` was
    actually Denied or Allowed, so AuditTail.poll()'s caller can drop it
    from the pending queue on a restart's full re-read instead of silently
    re-surfacing something already dealt with."""

    resolved_offset: int


@dataclass
class ReviewEntry:
    """docs/ARCHITECTURE.md sec20.4 (STORY-1604): one queued review per
    *aggregate group* of block events (sec23.1, STORY-1801, 2026-08-07) --
    not a live gate: `pre_tool_use` already resolved (denied) this call
    synchronously before the TUI ever saw it (sec20.1), so an entry that
    never gets reviewed just stays queued; no timeout logic.

    2026-08-07 (docs/ARCHITECTURE.md sec23.1, STORY-1801, direct user
    request): repeated, byte-for-byte identical block events (same
    `tool_name`/`tool_input`, `review_aggregation_key()` below) collapse
    into one `ReviewEntry` instead of one per occurrence -- `event` (a
    single `ToolCallEvent`) becomes `events` (every occurrence, oldest
    first) plus a stable `id` for the life of the running monitor process.
    `event`/`count`/`last_seen` are read-only properties derived from
    `events`, not separately-tracked fields, so there is exactly one source
    of truth for "how many times, and when most recently."

    2026-07-30 (direct user report: "restarted scg monitor and it lost the
    verified status"): Verify completion used to be tracked in a separate
    `verified: dict[str, bool]` field on this object, set by
    monitor_app.action_verify() -- but `build_review_entry()` constructs a
    brand-new `ReviewEntry` (empty dict) every time the audit log is
    rescanned, including on every monitor restart, so that flag was never
    actually persisted anywhere and always reset to "not verified" even
    when the real `ScanCache` already had a perfectly fresh, valid entry
    from before the restart. Gating Allow on `is_verified()`/`all_verified()`
    below instead -- computed live from the one real, persisted source of
    truth (`ScanCache`, same as `target_status()` already reads) rather
    than a second, parallel, unpersisted flag that could (and did) drift
    from it -- matches this project's own repeated "poll real files, don't
    invent a parallel store" precedent."""

    id: int
    events: list[ToolCallEvent]
    targets: list[Resource]

    @property
    def event(self) -> ToolCallEvent:
        # The most recent occurrence -- every event in a group shares the
        # same tool_name/tool_input by construction (that's the
        # aggregation identity), so any field a caller reads off this
        # (reason, session_id, tool_input) is real data from an actual
        # occurrence; recency is just the natural representative to pick.
        return self.events[-1]

    @property
    def count(self) -> int:
        return len(self.events)

    @property
    def last_seen(self) -> float:
        return max((e.timestamp for e in self.events), default=0.0)

    def is_verified(self, target: Resource, cache: ScanCache) -> bool:
        entry = cache.get(target)
        return entry is not None and cache.is_fresh(target, entry)

    def all_verified(self, cache: ScanCache) -> bool:
        return bool(self.targets) and all(self.is_verified(t, cache) for t in self.targets)


def review_aggregation_key(event: ToolCallEvent) -> tuple[str, str]:
    """docs/ARCHITECTURE.md sec23.1 (STORY-1801): two block events are "the
    same tool call" iff `tool_name` and `tool_input` are identical -- a real
    repeated retry of the exact same call, not merely one touching the same
    resource (a `cat secret.txt` and a `rm secret.txt` are not "the same
    call" even though they identify the same target; conflating them would
    hide a real, distinct action from the operator). `json.dumps(...,
    sort_keys=True)` gives a stable, hashable identity regardless of dict
    insertion order, without requiring `tool_input` itself to be hashable;
    `default=str` so a non-JSON-native value (should never happen for a
    real hook payload, but this reads an on-disk log) still keys instead of
    raising."""
    return (event.tool_name, json.dumps(event.tool_input, sort_keys=True, default=str))


def build_review_entry(event: ToolCallEvent, scanners: dict, entry_id: int) -> ReviewEntry:
    """docs/ARCHITECTURE.md sec20.4: reconstructs matched scanner(s)/
    target(s) via `onboard.identify_targets()` -- the exact function `scg
    onboard` already uses on the real tool call -- no second identification
    mechanism. `entry_id` (sec23.1, STORY-1801): the caller assigns this --
    a monotonically increasing counter scoped to one running monitor
    process, not derived from anything in `event` itself."""
    targets = identify_targets(event.tool_name, event.tool_input, scanners)
    return ReviewEntry(id=entry_id, events=[event], targets=targets)


def target_status(resource: Resource, cache: ScanCache) -> str:
    """docs/ARCHITECTURE.md sec20.4: a target's onboarded/validated status
    for the dashboard -- real `ScanCache` state, not simulated. Freshness
    (Smith's consult flag, 2026-07-22: `ScanCache.is_fresh()` already
    exists, only a display gap) is folded directly into the status string
    here since this function already has the `Resource` needed to call it."""
    entry = cache.get(resource)
    if entry is None:
        return "not yet scanned"
    freshness = "fresh" if cache.is_fresh(resource, entry) else "expired"
    return f"{entry.label} ({freshness})"


def discover_sessions(state_dir: Path = DEFAULT_STATE_DIR) -> list[SessionInfo]:
    """Recent-first list of sessions with a discoverable state file."""
    if not state_dir.exists():
        return []

    sessions = []
    for path in state_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        sessions.append(
            SessionInfo(
                session_id=data.get("session_id", path.stem),
                trust=data.get("trust", "high"),
                sensitivity=data.get("sensitivity", "public"),
                updated_at=path.stat().st_mtime,
            )
        )
    sessions.sort(key=lambda s: s.updated_at, reverse=True)
    return sessions


@dataclass(frozen=True)
class ScanResultInfo:
    identity: str
    scanner_name: str
    label: str
    reason: str
    scanned_at: float


def discover_scan_results(cache_path: Path = DEFAULT_CACHE_PATH) -> list[ScanResultInfo]:
    """Recent-first list of completed scan results (STORY-1005). Reads
    `.scalene/scan_cache.json` directly via `ScanCache.all_entries()` -- the
    same store the live hook consults, not a parallel summary that could
    drift from it. A resource with only an in-flight `pending_since`
    reservation (no scan finished yet) isn't a real result and is excluded.
    A corrupted cache store fails safe to an empty list rather than raising
    -- this is a read-only monitoring view, not the fatal-exit hook path."""
    try:
        raw_entries = ScanCache(cache_path).all_entries()
    except ScanCacheError:
        return []

    results = []
    for key, entry in raw_entries.items():
        if "label" not in entry:
            continue
        scanner_name, _, identity = key.partition(":")
        results.append(
            ScanResultInfo(
                identity=identity,
                scanner_name=scanner_name,
                label=entry["label"],
                reason=entry.get("reason", ""),
                scanned_at=entry.get("scanned_at", 0.0),
            )
        )
    results.sort(key=lambda r: r.scanned_at, reverse=True)
    return results


@dataclass(frozen=True)
class ScannerActivity:
    name: str
    busy: bool


def format_scanner_status(activities: list[ScannerActivity]) -> str:
    """docs/ARCHITECTURE.md sec22.3 (STORY-1703): the queue screen's status
    strip. Reuses the exact "busy"/"idle" words STORY-1602's Scanners panel
    already printed -- no new vocabulary for the same real state. Each
    scanner is its own independent clause joined by " · ", so a future
    second indicator can be appended the same way without restructuring
    this one (STORY-1703's own extensibility AC)."""
    if not activities:
        return "Scanners: none configured"
    clauses = [f"{a.name} {'busy' if a.busy else 'idle'}" for a in activities]
    return "Scanners: " + " · ".join(clauses)


def discover_scanner_activity(cache_path: Path, scanners: dict) -> list[ScannerActivity]:
    """docs/ARCHITECTURE.md sec20.2 (STORY-1602): one row per *configured*
    scanner (from `PolicyConfig.scanners`, so a config-declared scanner
    shows up with zero code changes here), not per cache entry -- an idle
    scanner with no cache entries at all must still appear as idle, not be
    silently missing. `busy` reuses `ScanCache`'s own `PENDING_TIMEOUT_
    SECONDS` staleness constant (the same one `try_reserve` uses) rather
    than a second, driftable timeout. A corrupted cache store fails safe to
    all-idle, same standard as `discover_scan_results`."""
    try:
        raw_entries = ScanCache(cache_path).all_entries()
    except ScanCacheError:
        raw_entries = {}

    now = time.time()
    busy_scanner_names = set()
    for key, entry in raw_entries.items():
        pending_since = entry.get("pending_since")
        if pending_since is not None and now - pending_since < PENDING_TIMEOUT_SECONDS:
            scanner_name, _, _ = key.partition(":")
            busy_scanner_names.add(scanner_name)

    return [ScannerActivity(name=name, busy=name in busy_scanner_names) for name in scanners]


class AuditTail:
    """Incremental reader over `.scalene/audit.log`. Tracks a byte offset so
    repeated `poll()` calls only return newly-appended entries. `onboard.py`
    writes `{"event": "onboard", ...}` to this same file, so tool-call
    events are filtered explicitly rather than assuming every line is one.

    2026-07-22 (docs/ARCHITECTURE.md sec20.3, STORY-1603): reads both
    "allow" and "block" events now, not block-only -- a genuine tool-call
    stream. "mask" events still never exist (sec15: rule-driven access
    control has no partial/masked outcome)."""

    def __init__(self, audit_log_path: Path = DEFAULT_AUDIT_LOG) -> None:
        self._path = audit_log_path
        self._offset = 0

    def poll(self) -> list[ToolCallEvent | ReviewResolution]:
        if not self._path.exists():
            return []

        size = self._path.stat().st_size
        if size < self._offset:
            # File was truncated/rotated — start over rather than seeking
            # past EOF forever.
            self._offset = 0

        items: list[ToolCallEvent | ReviewResolution] = []
        with self._path.open("r", encoding="utf-8") as f:
            f.seek(self._offset)
            while True:
                # 2026-07-30: `readline()` in a loop (not `for line in f`)
                # so `f.tell()` reliably gives each line's own starting
                # byte offset -- ToolCallEvent.log_offset's stable identity,
                # used to record/recognize that a specific block event was
                # actually resolved (see ReviewResolution above).
                line_start = f.tell()
                raw_line = f.readline()
                if not raw_line:
                    break
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event = entry.get("event")
                if event == "review_resolved":
                    resolved_offset = entry.get("resolved_offset")
                    if isinstance(resolved_offset, int):
                        items.append(ReviewResolution(resolved_offset=resolved_offset))
                    continue
                if event not in ("allow", "block"):
                    continue
                items.append(
                    ToolCallEvent(
                        session_id=entry.get("session_id", ""),
                        tool_name=entry.get("tool_name", ""),
                        reason=entry.get("reason", ""),
                        event=event,
                        block_kind=entry.get("block_kind"),
                        tool_input=entry.get("tool_input") or {},
                        log_offset=line_start,
                        timestamp=entry.get("ts", 0.0),
                    )
                )
            self._offset = f.tell()
        return items
