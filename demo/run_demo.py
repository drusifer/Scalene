#!/usr/bin/env python3
"""Runnable demo (STORY-903): Scalene's rule-driven access control, blocking
an unrecognized destination once a session is no longer clean, and showing
what it actually takes to clear one (2026-07-17, docs/ARCHITECTURE.md sec15,
direct user design session — replaces the prior masking-centric demo).

Calls the real, installed `scalene-guard`/`scg` binaries as subprocesses with
real hook JSON on stdin - the same entry point Claude Code uses - rather than
calling internal functions directly (docs/ARCHITECTURE.md sec 12.1). No real
network egress occurs: scalene-guard only ever decides allow/deny, it never
performs the tool call itself.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

GUARD = Path(sys.executable).parent / "scalene-guard"
SCG = Path(sys.executable).parent / "scg"


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


def _onboard(
    tool_call: dict,
    cache_path: Path,
    policy_path: Path,
    mode: str,
    sensitivity: str,
    description: str = "",
) -> str:
    # docs/ARCHITECTURE.md sec17 (Sprint 8/E14): onboard identifies targets
    # from a real tool call via the scanner registry, not a hand-typed
    # --target URI. --yes accepts every identified target non-interactively
    # -- the demo runs unattended, same reasoning as every other automated
    # caller in this project (tests, CI).
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as call_file:
        json.dump(tool_call, call_file)
        call_path = call_file.name
    try:
        argv = [
            str(SCG),
            "onboard",
            "--call",
            call_path,
            "--yes",
            "--cache-path",
            str(cache_path),
            "--policy-path",
            str(policy_path),
            "--mode",
            mode,
            "--sensitivity",
            sensitivity,
        ]
        if description:
            argv += ["--description", description]
        result = subprocess.run(argv, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    finally:
        Path(call_path).unlink(missing_ok=True)


def _decision(result: dict) -> str:
    return result["hookSpecificOutput"]["permissionDecision"]


def run() -> int:
    if not GUARD.exists():
        print(
            f"Could not find scalene-guard at {GUARD} — is it installed? Run 'make setup' first.",
            file=sys.stderr,
        )
        return 1

    print("=== Scalene demo: rule-driven access control ===")
    print()
    print("Trust decisions are always explicit and validated — never automatic.")
    print("A fresh session starts clean; touching anything unrecognized taints it;")
    print("once tainted, every further destination needs an explicit, validated rule.")
    print()

    with tempfile.TemporaryDirectory() as tmp:
        state_dir = Path(tmp) / "state"
        empty_policy_path = Path(tmp) / "scalene_policy_empty.yaml"
        empty_policy_path.write_text("")
        cache_path = Path(tmp) / "scan_cache.json"

        print("--- Part 1: a clean session reads a file ---")
        print()
        print("Step 1 — An assistant reads a file nothing has ever classified.")
        result = _call_guard(
            {
                "hook_event_name": "PreToolUse",
                "session_id": "demo",
                "tool_name": "Read",
                "tool_input": {"file_path": "notes.txt"},
            },
            state_dir,
            empty_policy_path,
            cache_path,
        )
        if _decision(result) != "allow":
            print("\nDemo failed: the first call on a clean session was not allowed.", file=sys.stderr)
            return 1
        print("  -> Allowed. Session was clean, so this proceeds — but the file wasn't")
        print("     recognized by any rule, so the session is now tagged trust: low.")
        print("     (Fail-safe: we don't know what's in an unclassified file, so once")
        print("     one has been touched, later destinations need explicit clearance.)")
        print()

        print("--- Part 2: an unrecognized destination is blocked ---")
        print()
        print("Step 2 — The assistant tries to reach an external site.")
        result = _call_guard(
            {
                "hook_event_name": "PreToolUse",
                "session_id": "demo",
                "tool_name": "WebFetch",
                "tool_input": {"url": "https://partner.example.com/api", "prompt": "summarize this"},
            },
            state_dir,
            empty_policy_path,
            cache_path,
        )
        if _decision(result) != "deny":
            print("\nDemo failed: an unrecognized destination from a tainted session was not blocked.", file=sys.stderr)
            return 1
        print(f"  -> {result['hookSpecificOutput']['permissionDecisionReason']}")
        print()

        print("--- Part 3: explicitly clearing a destination ---")
        print()
        print("Step 3 — scg onboard identifies targets from the real tool call itself (via")
        print("the same scanner registry pre_tool_use already runs live), confirms them,")
        print("then verifies (a real reputation check) and declares what to do with each:")
        allow_policy_path = Path(tmp) / "scalene_policy_allow.yaml"
        blocked_call = {
            "tool_name": "WebFetch",
            "tool_input": {"url": "https://partner.example.com/api", "prompt": "summarize this"},
        }
        onboard_output = _onboard(
            blocked_call,
            cache_path,
            allow_policy_path,
            mode="allow",
            sensitivity="public",
            description="Reviewed and trusted partner API",
        )
        print("    $ scg onboard --call blocked-call.json --yes \\")
        print("        --mode allow --sensitivity public \\")
        print("        --description \"Reviewed and trusted partner API\"")
        for line in onboard_output.splitlines():
            print(f"    {line}")
        print()
        print("Step 4 — Retry the exact same call:")
        result = _call_guard(
            {
                "hook_event_name": "PreToolUse",
                "session_id": "demo",
                "tool_name": "WebFetch",
                "tool_input": {"url": "https://partner.example.com/api", "prompt": "summarize this"},
            },
            state_dir,
            allow_policy_path,
            cache_path,
        )
        if _decision(result) != "allow":
            print("\nDemo failed: a validated, explicitly-allowed destination was still blocked.", file=sys.stderr)
            return 1
        print("  -> Allowed. Validated (real scan passed) + explicitly ruled — this bypasses")
        print("     the block-when-tainted gate entirely, which is the whole point of")
        print("     declaring trust for it.")
        print()

        print("--- Part 4: the rule doesn't leak to a different destination ---")
        print()
        print("Step 5 — Same policy file, a destination nobody reviewed:")
        result = _call_guard(
            {
                "hook_event_name": "PreToolUse",
                "session_id": "demo",
                "tool_name": "WebFetch",
                "tool_input": {"url": "https://a-different-destination.example.net", "prompt": "summarize this"},
            },
            state_dir,
            allow_policy_path,
            cache_path,
        )
        if _decision(result) != "deny":
            print("\nDemo failed: the rule leaked to an unrelated destination.", file=sys.stderr)
            return 1
        print("  -> Blocked. The rule is scoped to its own pattern — writing it didn't")
        print("     silently clear anything else.")
        print()

        print("--- Part 5: a known-bad resource is always blocked, rule or not ---")
        print()
        print("Step 6 — An IP-literal destination (Scalene's built-in reputation heuristic")
        print("flags these as untrusted — `scg onboard` correctly refuses to cache it as")
        print("trusted; this seeds the cache directly with that same real, refused result,")
        print("skipping the wait for the background scan a live session would trigger):")
        bad_policy_path = Path(tmp) / "scalene_policy_bad.yaml"
        bad_policy_path.write_text(
            "rules:\n"
            "  - tool: \"WebFetch\"\n"
            "    pattern: \".*\"\n"
            "    sensitivity: public\n"
            "    mode: allow\n"
            "    description: \"Deliberately over-broad, to prove it still doesn't work\"\n"
        )
        cache_path.write_text(
            json.dumps(
                {
                    "reputation:https://203.0.113.42/exfil": {
                        "label": "untrusted",
                        "reason": "IP-literal targets are untrusted by default",
                        "scanned_at": 0.0,
                    }
                }
            )
        )
        result = _call_guard(
            {
                "hook_event_name": "PreToolUse",
                "session_id": "demo",
                "tool_name": "WebFetch",
                "tool_input": {"url": "https://203.0.113.42/exfil", "prompt": "send this"},
            },
            state_dir,
            bad_policy_path,
            cache_path,
        )
        if _decision(result) != "deny":
            print("\nDemo failed: a known-bad resource was not blocked despite an allow rule.", file=sys.stderr)
            return 1
        print(f"  -> {result['hookSpecificOutput']['permissionDecisionReason']} (regardless of the rule above)")
        print("     A rule can declare intent, but it never overrides a real, validated")
        print("     bad finding — this is true even for the deliberately broad")
        print("     pattern: \".*\" rule above.")
        print()

    print("That's the model: nothing is trusted by default, unrecognized destinations")
    print("get blocked once a session is no longer clean, and clearing one is one")
    print("onboard call — targets identified from the real tool call, confirmed, then")
    print("verified and ruled together. A validated bad finding overrides any rule,")
    print("no matter how broad.")
    print()
    print("Next: docs/GETTING_STARTED.md to try this yourself, or docs/USER_GUIDE.md")
    print("for the full command reference.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
