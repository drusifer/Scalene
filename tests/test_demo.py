"""demo/run_demo.py must actually demonstrate real rule-driven access
control, and must not silently rot (STORY-903) — run as a subprocess, same
as a user would.

2026-07-17 (docs/ARCHITECTURE.md sec15, direct user design session):
rewritten entirely for the access-control model (allow/block), replacing
the old masking-centric demo and its tests."""

import subprocess
import sys
import unittest
from pathlib import Path

from _env_guards import disable_remote_reputation, restore_remote_reputation

DEMO_SCRIPT = Path(__file__).resolve().parent.parent / "demo" / "run_demo.py"

# docs/ARCHITECTURE.md sec18.3 (STORY-1503): the demo's WebFetch scenarios
# use real URLs -- subprocess.run() below inherits this process's
# environment by default (no explicit env= override), so setting this here
# propagates through run_demo.py's own subprocess calls too. See
# _env_guards.py.
setUpModule = disable_remote_reputation
tearDownModule = restore_remote_reputation


class TestDemo(unittest.TestCase):
    def test_demo_runs_clean_end_to_end(self):
        result = subprocess.run(
            [sys.executable, str(DEMO_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_demo_shows_clean_session_call_allowed(self):
        result = subprocess.run([sys.executable, str(DEMO_SCRIPT)], capture_output=True, text=True, timeout=30)
        self.assertIn("Allowed. Session was clean", result.stdout)

    def test_demo_shows_unrecognized_destination_blocked(self):
        result = subprocess.run([sys.executable, str(DEMO_SCRIPT)], capture_output=True, text=True, timeout=30)
        self.assertIn("has no validated, explicitly-allowed rule", result.stdout)

    def test_demo_shows_onboard_and_rule_clearing_a_destination(self):
        # docs/ARCHITECTURE.md sec17 (Sprint 8/E14): --target is gone --
        # onboard now takes --call/--yes, identifying targets from the tool
        # call itself.
        result = subprocess.run([sys.executable, str(DEMO_SCRIPT)], capture_output=True, text=True, timeout=30)
        self.assertIn("scg onboard --call", result.stdout)
        self.assertIn("--yes", result.stdout)
        self.assertIn("Rule written to", result.stdout)
        self.assertIn("mode='allow'", result.stdout)
        self.assertIn("1 onboarded, 0 blocked", result.stdout)
        self.assertIn("Allowed. Validated (real scan passed)", result.stdout)

    def test_demo_shows_rule_does_not_leak_to_other_destinations(self):
        result = subprocess.run([sys.executable, str(DEMO_SCRIPT)], capture_output=True, text=True, timeout=30)
        self.assertIn("didn't", result.stdout)
        self.assertIn("silently clear anything else", result.stdout)

    def test_demo_shows_known_bad_resource_overrides_an_allow_rule(self):
        result = subprocess.run([sys.executable, str(DEMO_SCRIPT)], capture_output=True, text=True, timeout=30)
        self.assertIn("the scanner found a real issue with it", result.stdout)
        self.assertIn("never overrides a real, validated", result.stdout)

    def test_demo_never_double_prefixes_the_blocked_reason(self):
        # Regression for a real bug caught while writing this demo: the
        # narration text and the real permissionDecisionReason both started
        # with "Blocked:", producing "Blocked: Blocked: ..." in the output.
        result = subprocess.run([sys.executable, str(DEMO_SCRIPT)], capture_output=True, text=True, timeout=30)
        self.assertNotIn("Blocked: Blocked:", result.stdout)


if __name__ == "__main__":
    unittest.main()
