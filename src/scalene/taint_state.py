"""Session-scoped sticky taint flags (STORY-101, STORY-102)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from filelock import FileLock

DEFAULT_STATE_DIR = Path(".scalene") / "state"


@dataclass
class TaintState:
    session_id: str
    has_sensitive_data: bool = False
    has_untrusted_data: bool = False
    state_dir: Path = field(default=DEFAULT_STATE_DIR, repr=False, compare=False)

    def mark_sensitive(self) -> None:
        """Sticky: only ever flips False -> True."""
        self.has_sensitive_data = True

    def mark_untrusted(self) -> None:
        """Sticky: only ever flips False -> True."""
        self.has_untrusted_data = True

    def reset(self) -> None:
        """Explicit session/context reset — the only path back to False."""
        self.has_sensitive_data = False
        self.has_untrusted_data = False
        path = self._path()
        if path.exists():
            path.unlink()

    @classmethod
    def load(cls, session_id: str, state_dir: Path = DEFAULT_STATE_DIR) -> "TaintState":
        path = Path(state_dir) / f"{session_id}.json"
        if not path.exists():
            return cls(session_id=session_id, state_dir=Path(state_dir))
        with FileLock(str(path) + ".lock"):
            data = json.loads(path.read_text())
        return cls(
            session_id=session_id,
            has_sensitive_data=data.get("has_sensitive_data", False),
            has_untrusted_data=data.get("has_untrusted_data", False),
            state_dir=Path(state_dir),
        )

    def save(self) -> None:
        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(path) + ".lock"):
            path.write_text(
                json.dumps(
                    {
                        "session_id": self.session_id,
                        "has_sensitive_data": self.has_sensitive_data,
                        "has_untrusted_data": self.has_untrusted_data,
                    }
                )
            )

    def _path(self) -> Path:
        return Path(self.state_dir) / f"{self.session_id}.json"
