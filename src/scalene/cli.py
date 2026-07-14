"""`scalene-guard` — the hook command invoked by Claude Code's PreToolUse/PostToolUse
hook system (architecture §6, Distribution). Reads one hook JSON payload from
stdin, dispatches on `hook_event_name`, writes one JSON response to stdout.

Never blocks the agent on an adapter-internal problem: malformed stdin or an
unrecognized hook event both fail safe to `{}` (empty output — the real
Claude Code hook contract treats this as "allow, no decision") rather than
raising or returning an invented, non-contract shape.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .hook_adapter import post_tool_use, pre_tool_use
from .policy_config import PolicyConfig, PolicyConfigError
from .taint_state import DEFAULT_STATE_DIR

logger = logging.getLogger("scalene.guard")

DEFAULT_POLICY_PATH = Path("scalene_policy.yaml")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scalene-guard")
    parser.add_argument("--policy-path", default=str(DEFAULT_POLICY_PATH))
    parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps({}))
        return 0

    policy_path = Path(args.policy_path)
    try:
        config = PolicyConfig.from_yaml(policy_path) if policy_path.exists() else PolicyConfig()
    except PolicyConfigError as exc:
        # Same fail-safe contract as this module's docstring: an
        # adapter-internal problem (here, an unreadable/malformed policy
        # file) must never block the agent. Falls back to PolicyConfig()'s
        # fail-safe defaults (sensitive_by_default/untrusted_by_default=True),
        # same as a missing policy file (docs/SETUP.md).
        logger.warning("Fail-safe triggered: %s could not be loaded (%s) — using fail-safe defaults", policy_path, exc)
        config = PolicyConfig()
    state_dir = Path(args.state_dir)

    event = payload.get("hook_event_name")
    if event == "PreToolUse":
        result = pre_tool_use(payload, config, state_dir=state_dir)
    elif event == "PostToolUse":
        result = post_tool_use(payload, config, state_dir=state_dir)
    else:
        result = {}

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
