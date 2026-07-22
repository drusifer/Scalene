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
from .policy_config import PolicyConfig, PolicyConfigError, write_default_project_policy
from .scan_cache import DEFAULT_CACHE_PATH, ScanCacheError
from .scanner import ScannerMachineryError
from .taint_state import DEFAULT_STATE_DIR

logger = logging.getLogger("scalene.guard")

DEFAULT_POLICY_PATH = Path("scalene_policy.yaml")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scalene-guard")
    parser.add_argument("--policy-path", default=str(DEFAULT_POLICY_PATH))
    parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    parser.add_argument("--cache-path", default=str(DEFAULT_CACHE_PATH))
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps({}))
        return 0

    policy_path = Path(args.policy_path)
    # sec18.4 (STORY-1504): a brand-new project (no policy file yet) gets
    # one real, ordinary rule for its own folder written to a real file --
    # not an implicit in-memory special case. Same shape as any
    # onboard-authored rule, visible by just opening scalene_policy.yaml.
    # If the write itself fails (e.g. unwritable directory), fail safe the
    # same way an unreadable/malformed policy file already does below.
    if not policy_path.exists():
        try:
            write_default_project_policy(policy_path, project_root=policy_path.resolve().parent)
        except OSError as exc:
            logger.warning("Could not create default %s (%s) — using fail-safe defaults", policy_path, exc)

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
    cache_path = Path(args.cache_path)

    event = payload.get("hook_event_name")
    try:
        if event == "PreToolUse":
            result = pre_tool_use(payload, config, state_dir=state_dir, cache_path=cache_path)
        elif event == "PostToolUse":
            result = post_tool_use(payload, config, state_dir=state_dir, cache_path=cache_path)
        else:
            result = {}
    except (ScanCacheError, ScannerMachineryError) as exc:
        # STORY-1004: the ONLY fatal-nonzero-exit case -- the scanning
        # machinery itself is broken (cache store corrupt/unwritable, or a
        # scanner's own scan()/identify() couldn't run), not an ordinary
        # scan finding (secret found, bad reputation), which always stays
        # exit 0 via the normal mask/block/allow decision path above.
        # Plain-language reason only, never a raw traceback.
        #
        # Exit code 2, verified (not assumed) 2026-07-15 against Claude
        # Code's real hook contract -- confirmed both by fetching the
        # current docs and by live-testing against this very repo's own
        # dogfooded scalene-guard hook: exit 1 (the initial, Unix-
        # conventional choice) is explicitly documented as a NON-blocking
        # error for PreToolUse ("Claude Code treats exit code 1 as a
        # non-blocking error and proceeds with the action"); only exit
        # code 2 actually blocks a PreToolUse call. Confirmed live: with
        # exit 1, a real tool call proceeded normally through this exact
        # fatal path with zero visible effect -- the fail-closed behavior
        # STORY-1004 wants (block the call when the scanning machinery
        # can't be trusted) requires exit 2, not 1. For PostToolUse, exit
        # 2 is explicitly non-blocking too (the tool already ran) --
        # using 2 uniformly is correct and simplest; it's the only code
        # that changes behavior anywhere, and it changes it correctly.
        print(f"scalene-guard: fatal scanning-machinery failure — {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
