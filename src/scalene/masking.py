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
from .scanner import locator_fields
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

    def mask_secrets(self, args: Any, tool_name: str = "") -> tuple[Any, dict[str, tuple[str, ...]]]:
        """docs/ARCHITECTURE.md sec24 (OLOY auto-mask): scans every top-level
        string value in `args` for real secret content and replaces each one
        that has findings with MASK_LITERAL. Returns `(masked_args,
        findings_by_field)`; `findings_by_field` is empty (and `args` returned
        unchanged) when nothing was found. Never raises on a non-dict `args`.

        `tool_name`'s locator fields (`scanner.locator_fields()` -- e.g.
        `Write.file_path`, `WebFetch.url`) are never scanned or masked
        (sec24.3): masking one would break the call outright."""
        if not isinstance(args, dict):
            return args, {}
        skip = locator_fields(tool_name)
        findings_by_field: dict[str, tuple[str, ...]] = {}
        for key, value in args.items():
            if key in skip:
                continue
            if isinstance(value, str) and value:
                findings = tuple(scan_text_for_secrets(value))
                if findings:
                    findings_by_field[key] = findings
        if not findings_by_field:
            return args, {}
        masked = dict(args)
        for key in findings_by_field:
            masked[key] = self.MASK_LITERAL
        return masked, findings_by_field
