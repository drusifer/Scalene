"""Local, offline reputation/threat-intel heuristics (STORY-501 decision #4).

No paid external API in v1 (architecture §7.4) — a `ReputationChecker` interface
means a real API can be added later without touching callers.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Protocol

SUSPICIOUS_LABEL_LENGTH = 30


_NUM_HEURISTICS = 3


@dataclass(frozen=True)
class ReputationResult:
    is_trusted: bool
    reason: str = ""
    score: float = 1.0  # docs/ARCHITECTURE.md sec17.6: 1.0 - (triggered heuristics / 3)


class ReputationChecker(Protocol):
    def check(self, target: str) -> ReputationResult: ...


class LocalHeuristicChecker:
    """Domain heuristics: IP-literal targets, punycode homographs, suspicious
    (unusually long) domain labels. No network calls.

    docs/ARCHITECTURE.md sec17.6: all 3 heuristics are evaluated unconditionally
    (not first-match-wins) so `score` reflects real evaluated signal, not a
    relabeled boolean -- `is_trusted` keeps its original any-trip-fails
    meaning, unchanged."""

    def check(self, target: str) -> ReputationResult:
        if not target:
            return ReputationResult(is_trusted=False, reason="Empty target", score=0.0)

        reasons = []
        if self._is_ip_literal(target):
            reasons.append("IP-literal targets are untrusted by default")
        if self._is_punycode(target):
            reasons.append("Punycode-encoded domain (possible homograph attack)")
        if self._has_suspicious_label(target):
            reasons.append(f"Suspicious domain label longer than {SUSPICIOUS_LABEL_LENGTH} characters")

        if not reasons:
            return ReputationResult(is_trusted=True, score=1.0)

        score = 1.0 - (len(reasons) / _NUM_HEURISTICS)
        return ReputationResult(is_trusted=False, reason="; ".join(reasons), score=score)

    @staticmethod
    def _is_ip_literal(target: str) -> bool:
        try:
            ipaddress.ip_address(target)
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_punycode(target: str) -> bool:
        return any(label.startswith("xn--") for label in target.split("."))

    @staticmethod
    def _has_suspicious_label(target: str) -> bool:
        return any(len(label) > SUSPICIOUS_LABEL_LENGTH for label in target.split("."))
