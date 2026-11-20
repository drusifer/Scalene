"""Claude Code PreToolUse/PostToolUse hook adapter (STORY-301, STORY-302).

Nothing in the policy engine (`policy_config`, `taint_state`, `resource_verifier`)
imports this module or knows about Claude Code's hook JSON shape — this module is
the only place that translates between the two (architecture §2, adapter isolation).

2026-07-14: the response shape below was corrected to Claude Code's real
PreToolUse/PostToolUse hook contract (confirmed against
https://code.claude.com/docs/en/hooks.md) — the previous flat
`{"allow": ..., "updatedInput": ..., "sanitizedOutput": ...}` shape was never
part of that contract, which explains why masked `updatedInput` never
actually took effect against a real session despite `scalene-guard`
computing and logging a mask decision on every call.

2026-07-17 (docs/ARCHITECTURE.md sec15, direct user design session): the
core mechanism is now rule-driven access control (`resource_verifier.
decide_access`), replacing content-scanning/masking as what gates whether
a call proceeds. A call either has a validated, explicit rule permitting
it, or it's blocked outright — see sec15 for the full model. Masking
(`masking.py`, `MaskingEngine`) is untouched and still tested, but no
longer wired into `pre_tool_use`'s default flow; its future role is
explicitly undecided (sec15.5), not removed.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from .masking import MaskingEngine
from .policy_config import PolicyConfig, oloy_setting
from .resource_verifier import decide_access
from .scan_cache import DEFAULT_CACHE_PATH, ScanCache
from .taint_state import DEFAULT_STATE_DIR, TaintState

logger = logging.getLogger("scalene.adapter")

DEFAULT_AUDIT_LOG = Path(".scalene") / "audit.log"


def _pre_tool_use_response(
    permission_decision: str,
    reason: str | None = None,
    updated_input: dict[str, Any] | None = None,
    warning: str | None = None,
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
    if warning is not None:
        # sec24.1 (Smith Gate 2): a config warning is appended to the
        # user-visible systemMessage, never to permissionDecisionReason --
        # the decision and its reason are unaffected by it.
        response["systemMessage"] = f"{reason}\n{warning}" if reason is not None else warning
    return response


def append_audit_log(entry: dict[str, Any], audit_log_path: Path) -> None:
    """Renamed from `_append_audit_log` (2026-07-30) -- monitor_app.py's
    review-resolution persistence (a `review_resolved` marker written when
    a review is Denied/Allowed, direct user report: "review status is not
    persisted") is now a second real caller outside this module, same
    precedent as onboard.py's `write_rule` (see its own docstring)."""
    audit_log_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_log_path.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def pre_tool_use(
    hook_input: dict[str, Any],
    config: PolicyConfig,
    state_dir: Path = DEFAULT_STATE_DIR,
    audit_log_path: Path = DEFAULT_AUDIT_LOG,
    cache_path: Path = DEFAULT_CACHE_PATH,
) -> dict[str, Any]:
    """STORY-301 (docs/ARCHITECTURE.md sec15): rule-driven access control.
    A call proceeds only if every resource it touches is either validated
    + explicitly allow-ruled, or the session is still clean (nothing
    sensitive/untrusted touched yet) — otherwise it's blocked outright."""
    tool_input = hook_input.get("tool_input", {})

    if os.environ.get("SCALENE_BYPASS") == "1":
        # STORY-601 AC2: scanner-subprocess actions never recurse back through
        # policy evaluation.
        return _pre_tool_use_response("allow")

    tool_name = hook_input["tool_name"]
    session_id = hook_input["session_id"]

    oloy, oloy_warning = oloy_setting(config)
    taint = TaintState.load(session_id, state_dir=state_dir)
    decision = decide_access(tool_name, tool_input, config, ScanCache(cache_path), taint, oloy=oloy)
    taint.save()

    # docs/ARCHITECTURE.md sec24 (OLOY auto-mask): once a session is tainted,
    # an allowed call's outgoing payload is scanned for real secrets and any
    # field containing one is masked via `updatedInput`, instead of asking a
    # human. A clean session's payloads pass through untouched -- nothing
    # untrusted has been seen yet, so there's nothing to exfiltrate *to*.
    masked_input: dict[str, Any] | None = None
    masked_fields: dict[str, tuple[str, ...]] = {}
    if oloy and decision.allowed and not taint.is_clean:
        candidate, masked_fields = MaskingEngine().mask_secrets(tool_input, tool_name=tool_name)
        if masked_fields:
            masked_input = candidate

    # docs/ARCHITECTURE.md sec20.3 (STORY-1603, corrected 2026-07-22): every
    # call is logged, allow or block -- not just blocks -- so scg monitor's
    # event panel is a genuine tool-call stream, not a block-only feed. The
    # append is a single buffered write, not a scan/subprocess spawn, so
    # this doesn't share the measured first-sighting latency cost (sec13.3).
    entry: dict[str, Any] = {
        "event": "allow" if decision.allowed else "block",
        "session_id": session_id,
        "tool_name": tool_name,
        # sec24: a masked call logs what actually ran -- never write the
        # secret that was just masked out of the call into the audit log.
        "tool_input": masked_input if masked_input is not None else tool_input,
        "reason": decision.reason,
        "block_kind": decision.block_kind,
        # docs/ARCHITECTURE.md sec22.2 (STORY-1701): the queue screen's
        # "Age" column needs a real occurrence time -- nothing before
        # this recorded one at all (ScanCache.scanned_at is a different
        # timestamp, when a *scan* completed, not when the call itself
        # happened). Defaults to 0.0 on read for any pre-existing
        # audit-log line written before this field existed (monitor_
        # data.ToolCallEvent), same "don't crash on an old-format line"
        # convention as block_kind/tool_input already use.
        "ts": time.time(),
    }
    if oloy:
        # sec24: marks this event as decided automatically -- `scg monitor`
        # never queues an OLOY block for human review (monitor_app.py).
        entry["oloy"] = True
        if decision.auto_cleared:
            entry["auto_cleared"] = list(decision.auto_cleared)
        if masked_fields:
            entry["masked_fields"] = {key: list(found) for key, found in masked_fields.items()}
    append_audit_log(entry, audit_log_path)

    if masked_input is not None:
        fields = ", ".join(sorted(masked_fields))
        return _pre_tool_use_response(
            "allow",
            reason=f"Scalene OLOY: masked possible secret(s) in {fields} before this call ran.",
            updated_input=masked_input,
            warning=oloy_warning,
        )
    if decision.allowed:
        return _pre_tool_use_response("allow", warning=oloy_warning)
    return _pre_tool_use_response("deny", reason=decision.reason, warning=oloy_warning)


def post_tool_use(
    hook_input: dict[str, Any],
    config: PolicyConfig,
    state_dir: Path = DEFAULT_STATE_DIR,
    cache_path: Path = DEFAULT_CACHE_PATH,
) -> dict[str, Any]:
    """STORY-302: intentionally a no-op under sec15's model. Every resource
    a call touches is identifiable from `tool_input` alone (file paths,
    URLs), so `pre_tool_use` already makes the full access decision and
    updates trust/sensitivity tags before the call ever runs — there is no
    tool-response-derived signal this hook needs to add. `config`/
    `cache_path` are accepted for signature compatibility with existing
    call sites and Claude Code's PostToolUse registration, not used."""
    if os.environ.get("SCALENE_BYPASS") == "1":
        # STORY-601 AC2: scanner-subprocess actions never write state.
        return {}
    return {}
