"""Session-scoped sticky trust/sensitivity tags (STORY-101, STORY-102).

2026-07-17 (docs/ARCHITECTURE.md sec15, direct user design session): the
old binary has_sensitive_data/has_untrusted_data flags are replaced by two
independent, sticky, ratcheting tags -- trust (low/med/high) and
sensitivity (public/internal/restricted) -- driving a per-call access
decision (sec15.3), not a masking decision. Both tags only ever move
toward more restrictive; the only way back to clean is starting a new
session or an explicit reset(). trust is kept 3-valued (not binary) even
though only "high" and "low" are produced by any transition today, so a
future scanner/rule can resolve an intermediate trust level without a
breaking change later.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from filelock import FileLock

DEFAULT_STATE_DIR = Path(".scalene") / "state"

TRUST_LEVELS = ("low", "med", "high")
SENSITIVITY_LEVELS = ("public", "internal", "restricted")

# Higher score = more restrictive; escalation always moves toward the
# higher score on either axis, never back down except via reset().
_TRUST_RESTRICTIVENESS = {"high": 0, "med": 1, "low": 2}
_SENSITIVITY_RESTRICTIVENESS = {"public": 0, "internal": 1, "restricted": 2}


@dataclass
class TaintState:
    session_id: str
    trust: str = "high"
    sensitivity: str = "public"
    state_dir: Path = field(default=DEFAULT_STATE_DIR, repr=False, compare=False)
    # 2026-08-07 (docs/ARCHITECTURE.md sec15.2's own flagged future work,
    # direct user request): resources this session was optimistically
    # granted access to on a matching `mode: allow` rule *before* their
    # background scan finished -- "trust but verify," not "verify before
    # trust." Raw `scan_cache.cache_key()` strings (scanner_name:identity),
    # not full `Resource` objects: `resource_verifier._reconcile_pending_
    # trust()` only ever needs to look up the label, never re-scan. Scalene
    # has no daemon -- one process per hook invocation -- so this list is
    # what makes reconciliation possible at all: without it, there'd be
    # nothing recorded to check on the *next* call in this session.
    pending_trust: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.trust not in TRUST_LEVELS:
            raise ValueError(f"trust must be one of {TRUST_LEVELS}, got {self.trust!r}")
        if self.sensitivity not in SENSITIVITY_LEVELS:
            raise ValueError(f"sensitivity must be one of {SENSITIVITY_LEVELS}, got {self.sensitivity!r}")

    @property
    def is_clean(self) -> bool:
        """True only when neither tag has ever escalated (sec15.1)."""
        return self.trust == "high" and self.sensitivity == "public"

    def escalate_trust(self, level: str) -> None:
        """Sticky ratchet: only ever moves toward more restrictive (sec15.1/15.4)."""
        if _TRUST_RESTRICTIVENESS[level] > _TRUST_RESTRICTIVENESS[self.trust]:
            self.trust = level

    def escalate_sensitivity(self, level: str) -> None:
        """Sticky ratchet: only ever moves toward more restrictive (sec15.1/15.4)."""
        if _SENSITIVITY_RESTRICTIVENESS[level] > _SENSITIVITY_RESTRICTIVENESS[self.sensitivity]:
            self.sensitivity = level

    def add_pending_trust(self, key: str) -> None:
        """Start tracking `key` (`scan_cache.cache_key()`'s format) as
        optimistically trusted, pending its background scan's real verdict.
        A no-op if already tracked -- a resource touched more than once
        before its scan finishes shouldn't accumulate duplicate entries."""
        if key not in self.pending_trust:
            self.pending_trust.append(key)

    def resolve_pending_trust(self, key: str) -> None:
        """Stop tracking `key` -- its scan has finished (clean or bad;
        callers decide what a bad finding means for `trust`/`sensitivity`
        themselves, this method only ever removes the tracking entry)."""
        if key in self.pending_trust:
            self.pending_trust.remove(key)

    def reset(self) -> None:
        """Explicit session/context reset — the only path back to clean (sec15.4)."""
        self.trust = "high"
        self.sensitivity = "public"
        self.pending_trust = []
        path = self._path()
        if path.exists():
            path.unlink()

    @classmethod
    def load(cls, session_id: str, state_dir: Path = DEFAULT_STATE_DIR) -> "TaintState":
        path = Path(state_dir) / f"{session_id}.json"
        if not path.exists():
            return cls(session_id=session_id, state_dir=Path(state_dir))
        # `FileLock`'s own default (timeout=-1) blocks forever on
        # contention -- a stuck/stale lock would hang the hook indefinitely.
        # `filelock.Timeout` (a `TimeoutError`/`OSError` subclass) propagates
        # to the caller instead, same fail-fast contract as scan_cache.py's.
        with FileLock(str(path) + ".lock", timeout=5):
            data = json.loads(path.read_text())
        return cls(
            session_id=session_id,
            trust=data.get("trust", "high"),
            sensitivity=data.get("sensitivity", "public"),
            state_dir=Path(state_dir),
            pending_trust=list(data.get("pending_trust", [])),
        )

    def save(self) -> None:
        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(path) + ".lock", timeout=5):
            path.write_text(
                json.dumps(
                    {
                        "session_id": self.session_id,
                        "trust": self.trust,
                        "sensitivity": self.sensitivity,
                        "pending_trust": self.pending_trust,
                    }
                )
            )

    def _path(self) -> Path:
        return Path(self.state_dir) / f"{self.session_id}.json"
