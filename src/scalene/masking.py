"""Structural payload masking + blocking decision engine (STORY-401).

2026-07-14 (user-reported): masking used to fire unconditionally once a
session was tainted-sensitive + untrusted, regardless of what a given call's
payload actually contained — every subsequent Bash command got masked and
announced even when nothing sensitive was present (e.g. `ls -la`). Masking
is gated on real content detection (`secrets_scan.py`, `detect-secrets`) —
the action only fires when the specific value scans as a real secret.

2026-07-17 (docs/ARCHITECTURE.md sec14.4, STORY-1104): the taint/
provenance_risk gate that used to decide *whether to bother scanning at
all* is removed entirely — every non-null payload value is scanned,
unconditionally, so real-secret detection never silently depends on a
session's taint state or a destination's trust classification being
correct. `match.mode` (resolved per-call by resource_verifier.evaluate(),
sec14.1) replaces the old caller-supplied global `mode` argument. The sole
remaining way to skip scanning is `match.mode == "allow"` — a deliberate,
narrow exception reachable only via an explicit hand-authored `PolicyRule`
(sec14.4 amendment), never automatic and never based on session state.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .policy_config import MatchResult
from .secrets_scan import scan_text_for_secrets

logger = logging.getLogger("scalene.masking")


@dataclass(frozen=True)
class Decision:
    action: str  # "allow" | "mask" | "block"
    findings: tuple[str, ...] = field(default_factory=tuple)


class MaskingEngine:
    MASK_LITERAL = "[MASKED_BY_POLICY_PROVENANCE_GUARD]"

    def decide(self, match: MatchResult, value: Any) -> Decision:
        """Unconditional content scan (sec14.4): every non-null payload value
        is checked for real secret content, regardless of taint or trust.
        `match.mode == "allow"` is the sole, deliberate exception — skips
        scanning entirely, only reachable via an explicit rule."""
        if value is None or match.mode == "allow":
            return Decision(action="allow")

        findings = tuple(scan_text_for_secrets(str(value)))
        if not findings:
            return Decision(action="allow")

        return Decision(action="block" if match.mode == "block" else "mask", findings=findings)

    def apply_mask(self, args: Any, payload_field: str | None) -> Any:
        """Structurally replace payload_field with the mask literal. Never raises."""
        if not isinstance(args, dict) or payload_field is None or payload_field not in args:
            logger.warning(
                "Masking skipped: payload_field %r not found in args (keys=%s)",
                payload_field,
                list(args) if isinstance(args, dict) else type(args).__name__,
            )
            return args
        masked = dict(args)
        masked[payload_field] = self.MASK_LITERAL
        return masked
