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
from dataclasses import dataclass
from pathlib import Path

from .hook_adapter import DEFAULT_AUDIT_LOG
from .scan_cache import DEFAULT_CACHE_PATH, ScanCache, ScanCacheError
from .taint_state import DEFAULT_STATE_DIR


@dataclass(frozen=True)
class SessionInfo:
    session_id: str
    trust: str
    sensitivity: str
    updated_at: float


@dataclass(frozen=True)
class BlockEvent:
    """docs/ARCHITECTURE.md sec15: renamed from MaskEvent -- masking no
    longer exists as a distinct event type, only "block" is ever written
    now (rule-driven access control has no partial/masked outcome).
    `payload_field`/`suggested_onboard_command` are gone with it -- a
    blocked call's `reason` is a plain-language explanation, not a single
    runnable command (clearing a destination always takes two steps: a
    real scan, then a rule)."""

    session_id: str
    tool_name: str
    reason: str


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


class AuditTail:
    """Incremental reader over `.scalene/audit.log`. Tracks a byte offset so
    repeated `poll()` calls only return newly-appended entries. `onboard.py`
    writes `{"event": "onboard", ...}` to this same file, so block events
    are filtered explicitly rather than assuming every line is one.

    2026-07-17 (docs/ARCHITECTURE.md sec15): "mask" events no longer exist
    -- rule-driven access control only ever writes "block" (or nothing, on
    allow)."""

    def __init__(self, audit_log_path: Path = DEFAULT_AUDIT_LOG) -> None:
        self._path = audit_log_path
        self._offset = 0

    def poll(self) -> list[BlockEvent]:
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
                if entry.get("event") != "block":
                    continue
                events.append(
                    BlockEvent(
                        session_id=entry.get("session_id", ""),
                        tool_name=entry.get("tool_name", ""),
                        reason=entry.get("reason", ""),
                    )
                )
            self._offset = f.tell()
        return events
