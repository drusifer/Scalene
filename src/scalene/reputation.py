"""Local, offline reputation/threat-intel heuristics (STORY-501 decision #4).

No paid external API in v1 (architecture §7.4) — a `ReputationChecker` interface
means a real API can be added later without touching callers.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Protocol

SUSPICIOUS_LABEL_LENGTH = 30


@dataclass(frozen=True)
class ReputationResult:
    is_trusted: bool
    reason: str = ""


class ReputationChecker(Protocol):
    def check(self, target: str) -> ReputationResult: ...


class LocalHeuristicChecker:
    """Domain heuristics: IP-literal targets, punycode homographs, suspicious
    (unusually long) domain labels. No network calls."""

    def check(self, target: str) -> ReputationResult:
        if not target:
            return ReputationResult(is_trusted=False, reason="Empty target")

        if self._is_ip_literal(target):
            return ReputationResult(is_trusted=False, reason="IP-literal targets are untrusted by default")

        if self._is_punycode(target):
            return ReputationResult(
                is_trusted=False, reason="Punycode-encoded domain (possible homograph attack)"
            )

        if self._has_suspicious_label(target):
            return ReputationResult(
                is_trusted=False,
                reason=f"Suspicious domain label longer than {SUSPICIOUS_LABEL_LENGTH} characters",
            )

        return ReputationResult(is_trusted=True)

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
