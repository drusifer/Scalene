"""demo/run_demo.py must actually demonstrate real masking, and must not
silently rot (STORY-903) — run as a subprocess, same as a user would."""

import subprocess
import sys
import unittest
from pathlib import Path

DEMO_SCRIPT = Path(__file__).resolve().parent.parent / "demo" / "run_demo.py"
FAKE_SECRET = "AKIAIOSFODNN7EXAMPLE"  # AWS access-key-ID shape (detect-secrets recognizes this)


class TestDemo(unittest.TestCase):
    def test_demo_shows_a_real_masked_event(self):
        result = subprocess.run(
            [sys.executable, str(DEMO_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("MASKED_BY_POLICY_PROVENANCE_GUARD", result.stdout)

    def test_demo_never_prints_the_secret_as_the_outbound_value(self):
        """The masked-value line (what would actually have gone out over the
        wire) must not contain the real secret. The suggested onboard
        command legitimately quotes the real value as a matching pattern —
        that's shown to the developer deciding whether to allow it, not
        leaked externally — so it's intentionally excluded from this check."""
        result = subprocess.run(
            [sys.executable, str(DEMO_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        outbound_line = next(line for line in result.stdout.splitlines() if "Scalene stepped in" in line)
        self.assertNotIn(FAKE_SECRET, outbound_line)

    def test_demo_prints_a_suggested_onboard_command(self):
        result = subprocess.run(
            [sys.executable, str(DEMO_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertIn("scg onboard", result.stdout)


if __name__ == "__main__":
    unittest.main()
