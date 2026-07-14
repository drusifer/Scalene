"""Structural payload masking + blocking decision engine (STORY-401).

2026-07-14 (user-reported): masking used to fire unconditionally once a
session was tainted-sensitive + untrusted, regardless of what a given call's
payload actually contained — every subsequent Bash command got masked and
announced even when nothing sensitive was present (e.g. `ls -la`). Masking
is now gated on real content detection (`secrets_scan.py`, `detect-secrets`)
in addition to provenance: taint + untrusted-destination still decides
*whether to bother checking content at all* (so untainted sessions pay zero
scanning cost), but the actual mask/block action only fires when the
specific value scans as a real secret.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .policy_config import MatchResult
from .secrets_scan import scan_text_for_secrets
from .taint_state import TaintState

logger = logging.getLogger("scalene.masking")


@dataclass(frozen=True)
class Decision:
    action: str  # "allow" | "mask" | "block"
    findings: tuple[str, ...] = field(default_factory=tuple)


class MaskingEngine:
    MASK_LITERAL = "[MASKED_BY_POLICY_PROVENANCE_GUARD]"

    def decide(self, taint: TaintState, match: MatchResult, value: Any, mode: str = "mask") -> Decision:
        """Provenance gate first (cheap, no scanning): session must already be
        tainted-sensitive, tainted-untrusted, and this call's destination
        must not be trust-listed. Only then is `value` actually scanned for
        real secret content — untainted/trusted calls never pay that cost.
        """
        provenance_risk = taint.has_sensitive_data and taint.has_untrusted_data and not match.is_trusted
        if not provenance_risk or value is None:
            return Decision(action="allow")

        findings = tuple(scan_text_for_secrets(str(value)))
        if not findings:
            return Decision(action="allow")

        return Decision(action="block" if mode == "block" else "mask", findings=findings)

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
