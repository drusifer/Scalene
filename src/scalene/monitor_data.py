"""Data layer for `scg monitor` (STORY-701/702).

Reads `.scalene/audit.log` and `.scalene/state/*.json` as plain files via
polling, not a filesystem-watch dependency (docs/ARCHITECTURE.md sec 11.1-
11.2). Pure functions/classes with no `textual` import, so this stays
testable without a terminal — the TUI layer (`monitor_app.py`) is a thin
composition over this module.
"""

from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .hook_adapter import DEFAULT_AUDIT_LOG
from .taint_state import DEFAULT_STATE_DIR


@dataclass(frozen=True)
class SessionInfo:
    session_id: str
    has_sensitive_data: bool
    has_untrusted_data: bool
    updated_at: float


@dataclass(frozen=True)
class MaskEvent:
    session_id: str
    tool_name: str
    payload_field: str
    suggested_onboard_command: str
    event_type: str = "mask"  # "mask" | "block" (2026-07-14: block was previously silently dropped here)


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
                has_sensitive_data=bool(data.get("has_sensitive_data", False)),
                has_untrusted_data=bool(data.get("has_untrusted_data", False)),
                updated_at=path.stat().st_mtime,
            )
        )
    sessions.sort(key=lambda s: s.updated_at, reverse=True)
    return sessions


class AuditTail:
    """Incremental reader over `.scalene/audit.log`. Tracks a byte offset so
    repeated `poll()` calls only return newly-appended entries. `onboard.py`
    writes `{"event": "onboard", ...}` to this same file, so mask/block events
    are filtered explicitly rather than assuming every line is one (STORY-701
    AC: only surface events where masking or blocking actually occurred)."""

    def __init__(self, audit_log_path: Path = DEFAULT_AUDIT_LOG) -> None:
        self._path = audit_log_path
        self._offset = 0

    def poll(self) -> list[MaskEvent]:
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
                event_type = entry.get("event")
                if event_type not in ("mask", "block"):
                    continue
                events.append(
                    MaskEvent(
                        session_id=entry.get("session_id", ""),
                        tool_name=entry.get("tool_name", ""),
                        payload_field=entry.get("payload_field", ""),
                        suggested_onboard_command=entry.get("suggested_onboard_command", ""),
                        event_type=event_type,
                    )
                )
            self._offset = f.tell()
        return events


def apply_onboard_command(command: str) -> tuple[bool, str]:
    """Runs an edited `suggested_onboard_command` (STORY-702) as a real
    subprocess against the actual `scg` CLI — never a reimplementation of
    `onboard.py`'s logic, so the console can't accidentally bypass its real
    secrets-scan/reputation-check safety gates.

    Never raises: a user is expected to hand-edit this string (Morpheus's
    Phase 3 review finding), so malformed quoting (`shlex.split`'s
    `ValueError`) and a missing/unreachable binary (`OSError`, e.g. `scg`
    not on PATH) are both real, easy-to-hit cases — every other error
    boundary in this codebase returns a plain-language result instead of
    propagating an exception, and this one must too."""
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        return False, f"Could not parse command: {exc}"

    if not argv:
        return False, "No command to run — the input was empty."

    try:
        result = subprocess.run(argv, capture_output=True, text=True)
    except OSError as exc:
        return False, f"Could not run command: {exc}"

    output = (result.stdout + result.stderr).strip()
    return result.returncode == 0, output
