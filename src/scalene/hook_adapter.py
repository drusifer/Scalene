"""Claude Code PreToolUse/PostToolUse hook adapter (STORY-301, STORY-302).

Nothing in the policy engine (`policy_config`, `taint_state`, `masking`) imports
this module or knows about Claude Code's hook JSON shape — this module is the
only place that translates between the two (architecture §2, adapter isolation).

2026-07-14: the response shape below was corrected to Claude Code's real
PreToolUse/PostToolUse hook contract (confirmed against
https://code.claude.com/docs/en/hooks.md) — the previous flat
`{"allow": ..., "updatedInput": ..., "sanitizedOutput": ...}` shape was never
part of that contract, which explains why masked `updatedInput` never
actually took effect against a real session despite `scalene-guard`
computing and logging a mask decision on every call.
"""

from __future__ import annotations

import json
import logging
import os
import shlex
from pathlib import Path
from typing import Any

from .masking import MaskingEngine
from .policy_config import PolicyConfig
from .resource_verifier import evaluate as verify_resources
from .scan_cache import DEFAULT_CACHE_PATH, ScanCache
from .taint_state import DEFAULT_STATE_DIR, TaintState

logger = logging.getLogger("scalene.adapter")

DEFAULT_AUDIT_LOG = Path(".scalene") / "audit.log"

# Standard Claude Code tool schemas: the argument that carries outbound payload
# content, as opposed to destination/syntax arguments (STORY-401 AC: preserve
# non-payload arguments). Callers may override per-deployment via payload_fields.
DEFAULT_PAYLOAD_FIELDS = {
    "Write": "content",
    "Edit": "new_string",
    "Bash": "command",
    "WebFetch": "prompt",
}


def _pre_tool_use_response(
    permission_decision: str,
    reason: str | None = None,
    updated_input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hook_specific: dict[str, Any] = {"hookEventName": "PreToolUse", "permissionDecision": permission_decision}
    if reason is not None:
        hook_specific["permissionDecisionReason"] = reason
    if updated_input is not None:
        hook_specific["updatedInput"] = updated_input
    response: dict[str, Any] = {"hookSpecificOutput": hook_specific}
    if reason is not None:
        # systemMessage is documented as a "universal" top-level field
        # (confirmed for PostToolUse, not explicitly confirmed for
        # PreToolUse) — included defensively so the reason surfaces
        # regardless of which field Claude Code actually reads for this event.
        response["systemMessage"] = reason
    return response


def _append_audit_log(entry: dict[str, Any], audit_log_path: Path) -> None:
    audit_log_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_log_path.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def _suggest_onboard_command(tool_name: str, payload_field: str, value: Any) -> str:
    """Build a ready-to-run `scg onboard` command for the exact call that
    was just masked (Smith UX consult, 2026-07-09) — an https:// target,
    since that's what actually exempts a future identical call from masking
    (resource_verifier.evaluate resolves http(s):// resources into
    MatchResult.is_trusted, which MaskingEngine.decide checks).

    2026-07-15 (Sprint 4 Phase 4, sec13.4): `scg onboard` re-scoped to
    pre-seed the resource cache from `--target` alone — no more
    `--tool`/`--jsonpath`/`--pattern`/`--description`, since there's no YAML
    rule to author anymore. `tool_name`/`payload_field`/`value` are no
    longer used to build the command itself, but the signature is kept as-is
    (call sites already pass them) since they're still useful context for
    whoever might extend this later.
    """
    return f"scg onboard --target {shlex.quote('https://<domain-this-call-reaches>')}"


def pre_tool_use(
    hook_input: dict[str, Any],
    config: PolicyConfig,
    state_dir: Path = DEFAULT_STATE_DIR,
    payload_fields: dict[str, str] | None = None,
    audit_log_path: Path = DEFAULT_AUDIT_LOG,
    cache_path: Path = DEFAULT_CACHE_PATH,
) -> dict[str, Any]:
    """STORY-301: evaluate a tool call before execution; mask or block if a
    tainted-sensitive session actually sends a real secret to an untrusted
    destination (STORY-401, content-gated 2026-07-14)."""
    tool_input = hook_input.get("tool_input", {})

    if os.environ.get("SCALENE_BYPASS") == "1":
        # STORY-601 AC2: scanner-subprocess actions never recurse back through
        # policy evaluation/masking.
        return _pre_tool_use_response("allow")

    session_id = hook_input["session_id"]
    tool_name = hook_input["tool_name"]
    payload_fields = DEFAULT_PAYLOAD_FIELDS if payload_fields is None else payload_fields

    taint = TaintState.load(session_id, state_dir=state_dir)
    match = verify_resources(tool_name, tool_input, config, ScanCache(cache_path))

    payload_field = payload_fields.get(tool_name)
    value = tool_input.get(payload_field) if payload_field is not None else None

    engine = MaskingEngine()
    decision = engine.decide(taint, match, value, mode=config.mode)

    if decision.action == "allow":
        return _pre_tool_use_response("allow")

    findings_text = "; ".join(decision.findings)
    suggestion = _suggest_onboard_command(tool_name, payload_field, value)
    # STORY-1003 (Smith Gate 1/2 note): a destination that simply hasn't been
    # scanned yet reads very differently from one a scan actively flagged as
    # bad -- conflating the two ("untrusted") overstates first-sighting risk
    # and erodes trust in later, real findings.
    verification_note = (
        "This destination has not yet been verified — Scalene defaults to caution until a background scan completes."
        if match.fail_safe_triggered
        else "This destination is known to be untrusted."
    )

    if decision.action == "block":
        _append_audit_log(
            {
                "event": "block",
                "session_id": session_id,
                "tool_name": tool_name,
                "payload_field": payload_field,
                "findings": list(decision.findings),
                "suggested_onboard_command": suggestion,
            },
            audit_log_path,
        )
        return _pre_tool_use_response(
            "deny",
            reason=(
                f"Scalene blocked the '{payload_field}' argument to {tool_name}: {findings_text}. "
                f"{verification_note} "
                f"To allow this exact call going forward, run:\n{suggestion}"
            ),
        )

    # decision.action == "mask"
    updated_input = engine.apply_mask(tool_input, payload_field)

    # Every mask is recorded here, every time — this is the durable record
    # `scg monitor` and onboarding read from, distinct from the
    # transcript notification below.
    _append_audit_log(
        {
            "event": "mask",
            "session_id": session_id,
            "tool_name": tool_name,
            "payload_field": payload_field,
            "findings": list(decision.findings),
            "suggested_onboard_command": suggestion,
        },
        audit_log_path,
    )

    return _pre_tool_use_response(
        "allow",
        reason=(
            f"Scalene masked the '{payload_field}' argument to {tool_name}: {findings_text}. "
            f"{verification_note} "
            f"To allow this exact call going forward, run:\n{suggestion}"
        ),
        updated_input=updated_input,
    )


def post_tool_use(
    hook_input: dict[str, Any],
    config: PolicyConfig,
    state_dir: Path = DEFAULT_STATE_DIR,
    cache_path: Path = DEFAULT_CACHE_PATH,
) -> dict[str, Any]:
    """STORY-302: update sticky taint flags from the tool's result. Runs on every
    call, success or failure. Output masking (if any) already happened in
    pre_tool_use — this hook is pure bookkeeping and has nothing to report."""
    tool_response = hook_input.get("tool_response", {})

    if os.environ.get("SCALENE_BYPASS") == "1":
        # STORY-601 AC2: scanner-subprocess actions never write taint state.
        return {}

    session_id = hook_input["session_id"]
    tool_name = hook_input["tool_name"]

    taint = TaintState.load(session_id, state_dir=state_dir)
    match = verify_resources(tool_name, tool_response, config, ScanCache(cache_path))

    if match.is_sensitive:
        taint.mark_sensitive()
    if not match.is_trusted:
        taint.mark_untrusted()
    taint.save()

    return {}
