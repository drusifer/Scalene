"""Structural payload masking engine (STORY-401)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .policy_config import MatchResult
from .taint_state import TaintState

logger = logging.getLogger("scalene.masking")


@dataclass(frozen=True)
class Decision:
    should_mask: bool


class MaskingEngine:
    MASK_LITERAL = "[MASKED_BY_POLICY_PROVENANCE_GUARD]"

    def decide(self, taint: TaintState, match: MatchResult) -> Decision:
        """Trigger: has_sensitive_data AND has_untrusted_data AND target is untrusted."""
        should_mask = taint.has_sensitive_data and taint.has_untrusted_data and not match.is_trusted
        return Decision(should_mask=should_mask)

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
