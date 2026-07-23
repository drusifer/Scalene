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
    crashing the reader."""

    session_id: str
    tool_name: str
    reason: str
    event: str = "block"
    block_kind: str | None = None
    tool_input: dict = field(default_factory=dict)


@dataclass
class ReviewEntry:
    """docs/ARCHITECTURE.md sec20.4 (STORY-1604): one queued review per
    block event. Not a live gate -- `pre_tool_use` already resolved (denied)
    this call synchronously before the TUI ever saw it (sec20.1), so an
    entry that never gets reviewed just stays queued; no timeout logic.
    `verified` tracks per-target Verify completion by `Resource.identity`,
    gating sec20.5's Allow action (disabled until every target is True)."""

    event: ToolCallEvent
    targets: list[Resource]
    verified: dict[str, bool] = field(default_factory=dict)

    @property
    def all_verified(self) -> bool:
        return bool(self.targets) and all(self.verified.get(t.identity, False) for t in self.targets)


def build_review_entry(event: ToolCallEvent, scanners: dict) -> ReviewEntry:
    """docs/ARCHITECTURE.md sec20.4: reconstructs matched scanner(s)/
    target(s) via `onboard.identify_targets()` -- the exact function `scg
    onboard` already uses on the real tool call -- no second identification
    mechanism."""
    targets = identify_targets(event.tool_name, event.tool_input, scanners)
    return ReviewEntry(event=event, targets=targets)


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

    def poll(self) -> list[ToolCallEvent]:
        if not self._path.exists():
            return []

        size = self._path.stat().st_size
        if size < self._offset:
            # File was truncated/rotated — start over rather than seeking
            # past EOF forever.
            self._offset = 0

        events = []
        with self._path.open("r", encoding="utf-8") as f:
            f.seek(self._offset)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event = entry.get("event")
                if event not in ("allow", "block"):
                    continue
                events.append(
                    ToolCallEvent(
                        session_id=entry.get("session_id", ""),
                        tool_name=entry.get("tool_name", ""),
                        reason=entry.get("reason", ""),
                        event=event,
                        block_kind=entry.get("block_kind"),
                        tool_input=entry.get("tool_input") or {},
                    )
                )
            self._offset = f.tell()
        return events
