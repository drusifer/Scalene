"""`scalene-guard` — the hook command invoked by Claude Code's PreToolUse/PostToolUse
hook system (architecture §6, Distribution). Reads one hook JSON payload from
stdin, dispatches on `hook_event_name`, writes one JSON response to stdout.

Never blocks the agent on an adapter-internal problem: malformed stdin or an
unrecognized hook event both fail safe to `{"allow": True}` rather than raising.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .hook_adapter import post_tool_use, pre_tool_use
from .policy_config import PolicyConfig
from .taint_state import DEFAULT_STATE_DIR

DEFAULT_POLICY_PATH = Path("scalene_policy.yaml")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scalene-guard")
    parser.add_argument("--policy-path", default=str(DEFAULT_POLICY_PATH))
    parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps({"allow": True}))
        return 0

    policy_path = Path(args.policy_path)
    config = PolicyConfig.from_yaml(policy_path) if policy_path.exists() else PolicyConfig()
    state_dir = Path(args.state_dir)

    event = payload.get("hook_event_name")
    if event == "PreToolUse":
        result = pre_tool_use(payload, config, state_dir=state_dir)
    elif event == "PostToolUse":
        result = post_tool_use(payload, config, state_dir=state_dir)
    else:
        result = {"allow": True}

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
