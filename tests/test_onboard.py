"""Tests for the `scalene onboard` CLI/library function (STORY-501)."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scalene.onboard import OnboardError, onboard
from scalene.policy_config import PolicyConfig


class TestOnboardAllowlist(unittest.TestCase):
    def test_clean_target_writes_rule_and_returns_diff(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")
            policy_path = tmp_path / "scalene_policy.yaml"
            audit_log = tmp_path / "audit.log"

            result = onboard(
                "allowlist",
                "Read",
                "$.file_path",
                r"\.md$",
                str(target),
                description="markdown is fine",
                policy_path=policy_path,
                audit_log_path=audit_log,
            )
            self.assertIn("rule", result)
            self.assertIn("diff", result)
            self.assertTrue(policy_path.exists())
            self.assertIn("non_sensitive_allowlist", policy_path.read_text())
            self.assertTrue(audit_log.exists())
            self.assertIn("onboard", audit_log.read_text())

    def test_secrets_found_blocks_onboarding_with_clear_reason_and_no_write(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "leaky.env"
            # Fake key built via concatenation, not a contiguous literal a
            # secret scanner would flag in this source file.
            fake_key = "AKIA" + "ABCDEFGHIJKLMNOP"
            target.write_text(f"AWS_KEY={fake_key}")
            policy_path = tmp_path / "scalene_policy.yaml"

            with self.assertRaises(OnboardError) as ctx:
                onboard("allowlist", "Read", "$.file_path", r"\.env$", str(target), policy_path=policy_path)
            self.assertIn("secrets", str(ctx.exception).lower())
            self.assertFalse(policy_path.exists())


class TestOnboardTrustList(unittest.TestCase):
    def test_trusted_domain_writes_rule(self):
        with TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "scalene_policy.yaml"
            result = onboard(
                "trust",
                "WebFetch",
                "$.url",
                r"^https://internal\.example\.com/",
                "internal.example.com",
                policy_path=policy_path,
            )
            self.assertTrue(policy_path.exists())
            self.assertIn("trusted_sources_list", policy_path.read_text())
            self.assertIn("rule", result)

    def test_untrusted_ip_target_blocks_onboarding_with_no_write(self):
        with TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "scalene_policy.yaml"
            with self.assertRaises(OnboardError) as ctx:
                onboard("trust", "WebFetch", "$.url", r".*", "203.0.113.42", policy_path=policy_path)
            self.assertTrue(str(ctx.exception))
            self.assertFalse(policy_path.exists())


class TestOnboardAppendsToExistingConfig(unittest.TestCase):
    def test_preserves_existing_rules(self):
        with TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "scalene_policy.yaml"
            policy_path.write_text(
                "non_sensitive_allowlist:\n"
                "  - tool: Read\n"
                '    jsonpath: "$.file_path"\n'
                '    pattern: "\\\\.txt$"\n'
                "    description: existing rule\n"
            )
            target = Path(tmp) / "clean.md"
            target.write_text("ordinary docs")

            onboard("allowlist", "Read", "$.file_path", r"\.md$", str(target), policy_path=policy_path)

            config = PolicyConfig.from_yaml(policy_path)
            self.assertEqual(len(config.non_sensitive_allowlist), 2)

    def test_unknown_list_type_blocks_with_no_write(self):
        with TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "scalene_policy.yaml"
            with self.assertRaises(OnboardError):
                onboard("bogus", "Read", "$.file_path", r".*", "x.md", policy_path=policy_path)
            self.assertFalse(policy_path.exists())


if __name__ == "__main__":
    unittest.main()
