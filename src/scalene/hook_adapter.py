"""Claude Code PreToolUse/PostToolUse hook adapter (STORY-301, STORY-302).

Nothing in the policy engine (`policy_config`, `taint_state`, `masking`) imports
this module or knows about Claude Code's hook JSON shape — this module is the
only place that translates between the two (architecture §2, adapter isolation).
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
from pathlib import Path
from typing import Any

from .masking import MaskingEngine
from .policy_config import PolicyConfig
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


def _append_audit_log(entry: dict[str, Any], audit_log_path: Path) -> None:
    audit_log_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_log_path.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def _suggest_onboard_command(tool_name: str, payload_field: str, value: Any) -> str:
    """Build a ready-to-run `scalene onboard` command for the exact call that
    was just masked (Smith UX consult, 2026-07-09) — a trust-list rule, since
    that's what actually exempts a future identical call from masking
    (PolicyConfig.evaluate's trusted_sources_list feeds MatchResult.is_trusted,
    which MaskingEngine.decide checks). Pattern defaults to an anchored escaped
    literal of the real value — the narrowest possible rule; the developer
    loosens it themselves if they want broader coverage."""
    jsonpath = f"$.{payload_field}"
    pattern = f"^{re.escape(str(value))}$"
    return (
        "scalene onboard --list-type trust "
        f"--tool {shlex.quote(tool_name)} "
        f"--jsonpath {shlex.quote(jsonpath)} "
        f"--pattern {shlex.quote(pattern)} "
        f"--target {shlex.quote('<domain-or-file-this-call-reaches>')}"
    )


def pre_tool_use(
    hook_input: dict[str, Any],
    config: PolicyConfig,
    state_dir: Path = DEFAULT_STATE_DIR,
    payload_fields: dict[str, str] | None = None,
    audit_log_path: Path = DEFAULT_AUDIT_LOG,
) -> dict[str, Any]:
    """STORY-301: evaluate a tool call before execution; mask if tainted-sensitive
    session data would flow to an untrusted destination (STORY-401)."""
    tool_input = hook_input.get("tool_input", {})

    if os.environ.get("SCALENE_BYPASS") == "1":
        # STORY-601 AC2: scanner-subprocess actions never recurse back through
        # policy evaluation/masking.
        return {"allow": True, "updatedInput": tool_input}

    session_id = hook_input["session_id"]
    tool_name = hook_input["tool_name"]
    payload_fields = DEFAULT_PAYLOAD_FIELDS if payload_fields is None else payload_fields

    taint = TaintState.load(session_id, state_dir=state_dir)
    match = config.evaluate(tool_name, tool_input)

    engine = MaskingEngine()
    decision = engine.decide(taint, match)

    if not decision.should_mask:
        return {"allow": True, "updatedInput": tool_input}

    payload_field = payload_fields.get(tool_name)
    updated_input = engine.apply_mask(tool_input, payload_field)

    if updated_input is tool_input:
        # Nothing was actually masked (tool_name has no entry in
        # payload_fields, or payload_field wasn't present in this call's
        # args) — don't announce a mask that didn't happen.
        return {"allow": True, "updatedInput": tool_input}

    suggestion = _suggest_onboard_command(tool_name, payload_field, tool_input[payload_field])

    _append_audit_log(
        {
            "event": "mask",
            "session_id": session_id,
            "tool_name": tool_name,
            "payload_field": payload_field,
            "suggested_onboard_command": suggestion,
        },
        audit_log_path,
    )

    return {
        "allow": True,
        "updatedInput": updated_input,
        "systemMessage": (
            f"Scalene masked the '{payload_field}' argument to {tool_name} "
            "(tainted-sensitive session data targeting an untrusted destination). "
            f"To allow this exact call going forward, run:\n{suggestion}"
        ),
    }


def post_tool_use(
    hook_input: dict[str, Any],
    config: PolicyConfig,
    state_dir: Path = DEFAULT_STATE_DIR,
) -> dict[str, Any]:
    """STORY-302: update sticky taint flags from the tool's result. Runs on every
    call, success or failure. Output masking (if any) already happened in
    pre_tool_use, so the response is passed through unchanged here."""
    tool_response = hook_input.get("tool_response", {})

    if os.environ.get("SCALENE_BYPASS") == "1":
        # STORY-601 AC2: scanner-subprocess actions never write taint state.
        return {"sanitizedOutput": tool_response}

    session_id = hook_input["session_id"]
    tool_name = hook_input["tool_name"]

    taint = TaintState.load(session_id, state_dir=state_dir)
    match = config.evaluate(tool_name, tool_response)

    if match.is_sensitive:
        taint.mark_sensitive()
    if not match.is_trusted:
        taint.mark_untrusted()
    taint.save()

    return {"sanitizedOutput": tool_response}
