"""Tests for the `scg onboard` CLI/library function (STORY-501).

2026-07-18 (direct user design session, post-Sprint-6): re-scoped again --
`scg onboard` is now the frontend for authoring a `PolicyRule`, not just a
cache-seeding utility. The user's own framing: "scg onboard is effectively
saying: when a tool call matches these conditions, apply these context
labels." A single call now both validates (real scan, unchanged since
Sprint 4) *and* declares (writes a `rules:` entry to scalene_policy.yaml)
in one action -- previously these were two disconnected steps, one via
CLI, one via hand-editing YAML, which the user found confusing while
reading the docs. CLI flag names deliberately match `PolicyRule`'s field
names exactly (tool/pattern/sensitivity/mode/scanner/description) --
no separate vocabulary to learn between the CLI and the YAML schema.
"""

import io
import os
import re
import unittest
import yaml
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from scalene.onboard import OnboardError, main, onboard
from scalene.policy_config import PolicyConfig
from scalene.scan_cache import ScanCache


class TestOnboardHelpDisclosesRealConstraints(unittest.TestCase):
    """Smith's sec16 gate finding: --help showed --sensitivity/--mode as
    independently optional (standard argparse brackets), so the naive
    pre-sec16-muscle-memory command (`--target` alone) always failed on the
    first try with no way to know why beforehand. The runtime error message
    was already good; this guards that the *reachable-before-you-fail*
    disclosure stays in --help, not just in the error path."""

    def _help_text(self) -> str:
        out = io.StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit):
                main(["--help"])
        return out.getvalue()

    def test_help_discloses_the_sensitivity_mode_requirement(self):
        text = self._help_text()
        self.assertIn("At least one of --sensitivity/--mode is required", text)

    def test_help_discloses_why_mask_is_rejected(self):
        # Trin's related finding: argparse's choices= rejects --mode mask
        # before onboard()'s own detailed rationale can ever fire for a real
        # CLI user -- that rationale needs to be reachable via --help instead.
        text = self._help_text()
        self.assertIn("--mode does not accept 'mask'", text)


class TestOnboardRequiresAtLeastOneAxis(unittest.TestCase):
    def test_neither_sensitivity_nor_mode_raises(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")
            with self.assertRaises(OnboardError) as ctx:
                onboard(f"file://{target}", cache_path=tmp_path / "cache.json", policy_path=tmp_path / "policy.yaml")
            self.assertIn("sensitivity", str(ctx.exception).lower())
            self.assertIn("mode", str(ctx.exception).lower())

    def test_mode_only_defaults_sensitivity_to_public(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")
            result = onboard(
                f"file://{target}", mode="allow", cache_path=tmp_path / "cache.json", policy_path=tmp_path / "policy.yaml"
            )
            self.assertEqual(result["rule"].sensitivity, "public")
            self.assertEqual(result["rule"].mode, "allow")

    def test_sensitivity_only_defaults_mode_to_allow(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")
            result = onboard(
                f"file://{target}",
                sensitivity="restricted",
                cache_path=tmp_path / "cache.json",
                policy_path=tmp_path / "policy.yaml",
            )
            self.assertEqual(result["rule"].sensitivity, "restricted")
            self.assertEqual(result["rule"].mode, "allow")

    def test_mode_mask_is_rejected_even_though_policyrule_allows_it_in_general(self):
        # Real gap caught by checking --help output directly: 'mask' is a
        # valid PolicyRule.mode in general (the dormant evaluate()/
        # MaskingEngine path distinguishes it from 'block'), but
        # decide_access() -- what an onboard-authored rule actually feeds --
        # treats anything that isn't 'allow' identically. Offering 'mask'
        # here would silently produce a rule that behaves like 'block'.
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")
            with self.assertRaises(OnboardError) as ctx:
                onboard(
                    f"file://{target}",
                    mode="mask",
                    cache_path=tmp_path / "cache.json",
                    policy_path=tmp_path / "policy.yaml",
                )
            self.assertIn("mask", str(ctx.exception).lower())

    def test_both_provided_together_is_the_common_case(self):
        # Trust and sensitivity are independent -- a resource can be both
        # "trusted" (mode: allow) and "restricted" (sensitivity) at once.
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")
            result = onboard(
                f"file://{target}",
                sensitivity="restricted",
                mode="allow",
                cache_path=tmp_path / "cache.json",
                policy_path=tmp_path / "policy.yaml",
            )
            self.assertEqual(result["rule"].sensitivity, "restricted")
            self.assertEqual(result["rule"].mode, "allow")


class TestOnboardRuleDefaults(unittest.TestCase):
    def test_pattern_defaults_to_exact_resolved_resource(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")
            result = onboard(
                f"file://{target}", mode="allow", cache_path=tmp_path / "cache.json", policy_path=tmp_path / "policy.yaml"
            )
            self.assertEqual(result["rule"].pattern, re.escape(os.path.abspath(target)))

    def test_tool_defaults_to_any(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")
            result = onboard(
                f"file://{target}", mode="allow", cache_path=tmp_path / "cache.json", policy_path=tmp_path / "policy.yaml"
            )
            self.assertEqual(result["rule"].tool, ".*")

    def test_explicit_pattern_and_tool_are_respected(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result = onboard(
                "https://internal.example.com",
                tool="WebFetch",
                pattern=r"https://internal\.example\.com/.*",
                mode="allow",
                cache_path=tmp_path / "cache.json",
                policy_path=tmp_path / "policy.yaml",
            )
            self.assertEqual(result["rule"].tool, "WebFetch")
            self.assertEqual(result["rule"].pattern, r"https://internal\.example\.com/.*")

    def test_invalid_rule_fields_reuse_policyrule_validation(self):
        # No duplicated validation logic -- constructs a real PolicyRule
        # internally, so an invalid sensitivity/mode/regex/scanner is
        # rejected the exact same way a hand-authored rule would be.
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")
            with self.assertRaises(OnboardError):
                onboard(
                    f"file://{target}",
                    mode="allow",
                    scanner="typo-scanner",
                    cache_path=tmp_path / "cache.json",
                    policy_path=tmp_path / "policy.yaml",
                )


class TestOnboardWritesPolicyFile(unittest.TestCase):
    def test_creates_a_fresh_policy_file_with_the_rule(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")
            policy_path = tmp_path / "scalene_policy.yaml"
            self.assertFalse(policy_path.exists())

            onboard(f"file://{target}", mode="allow", cache_path=tmp_path / "cache.json", policy_path=policy_path)

            self.assertTrue(policy_path.exists())
            config = PolicyConfig.from_yaml(policy_path)
            self.assertEqual(len(config.rules), 1)
            self.assertEqual(config.rules[0].mode, "allow")

    def test_appends_to_an_existing_rules_list_without_clobbering(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            policy_path = tmp_path / "scalene_policy.yaml"
            policy_path.write_text(
                "defaults:\n  mode: mask\nrules:\n"
                "  - tool: \".*\"\n    pattern: \"https://existing.example.com\"\n"
                "    sensitivity: public\n    mode: allow\n"
            )
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")

            onboard(f"file://{target}", mode="allow", cache_path=tmp_path / "cache.json", policy_path=policy_path)

            config = PolicyConfig.from_yaml(policy_path)
            self.assertEqual(len(config.rules), 2)
            self.assertEqual(config.rules[0].pattern, "https://existing.example.com")
            # defaults: section (unrelated to rules) must survive the rewrite.
            self.assertEqual(config.mode, "mask")

    def test_malformed_existing_policy_file_raises_clear_error(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            policy_path = tmp_path / "scalene_policy.yaml"
            policy_path.write_text(": not: valid: yaml: [")
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")

            with self.assertRaises(OnboardError):
                onboard(f"file://{target}", mode="allow", cache_path=tmp_path / "cache.json", policy_path=policy_path)

    def test_description_is_written_when_provided(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")
            policy_path = tmp_path / "scalene_policy.yaml"

            onboard(
                f"file://{target}",
                mode="allow",
                description="Reviewed test fixture",
                cache_path=tmp_path / "cache.json",
                policy_path=policy_path,
            )
            raw = yaml.safe_load(policy_path.read_text())
            self.assertEqual(raw["rules"][0]["description"], "Reviewed test fixture")


class TestOnboardModeBlockOverridesBadScan(unittest.TestCase):
    def test_mode_allow_with_a_bad_scan_still_blocks_onboarding(self):
        # Unchanged behavior: can't claim "allow" for something the
        # scanner actively flagged as bad.
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "leaky.env"
            fake_key = "AKIA" + "ABCDEFGHIJKLMNOP"
            target.write_text(f"AWS_KEY={fake_key}")
            cache_path = tmp_path / "cache.json"
            policy_path = tmp_path / "policy.yaml"

            with self.assertRaises(OnboardError) as ctx:
                onboard(f"file://{target}", mode="allow", cache_path=cache_path, policy_path=policy_path)
            self.assertIn("secrets", str(ctx.exception).lower())
            self.assertFalse(cache_path.exists())
            self.assertFalse(policy_path.exists())

    def test_mode_block_with_a_bad_scan_proceeds_and_writes_both(self):
        # The actual point of mode=block: explicitly declaring a known-bad
        # resource blocked, backed by (not despite) a real scan finding.
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "leaky.env"
            fake_key = "AKIA" + "ABCDEFGHIJKLMNOP"
            target.write_text(f"AWS_KEY={fake_key}")
            cache_path = tmp_path / "cache.json"
            policy_path = tmp_path / "policy.yaml"

            result = onboard(f"file://{target}", mode="block", cache_path=cache_path, policy_path=policy_path)
            self.assertEqual(result["label"], "sensitive")
            self.assertEqual(result["rule"].mode, "block")

            entry = ScanCache(cache_path).get(result["resource"])
            self.assertEqual(entry.label, "sensitive")  # cache reflects the real, honest finding
            config = PolicyConfig.from_yaml(policy_path)
            self.assertEqual(config.rules[0].mode, "block")


class TestOnboardFileTarget(unittest.TestCase):
    def test_clean_target_seeds_the_cache_as_public(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")
            cache_path = tmp_path / "cache.json"

            result = onboard(f"file://{target}", mode="allow", cache_path=cache_path, policy_path=tmp_path / "policy.yaml")
            self.assertEqual(result["label"], "public")

            entry = ScanCache(cache_path).get(result["resource"])
            self.assertIsNotNone(entry)
            self.assertEqual(entry.label, "public")

    def test_seeded_identity_matches_live_evaluation_normalization(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")
            cache_path = tmp_path / "cache.json"

            from scalene.scanner import FileScanner

            result = onboard(f"file://{target}", mode="allow", cache_path=cache_path, policy_path=tmp_path / "policy.yaml")
            live_resources = FileScanner().identify("Read", {"file_path": str(target)})
            self.assertEqual(len(live_resources), 1)
            self.assertEqual(result["resource"].identity, live_resources[0].identity)


class TestOnboardUrlTarget(unittest.TestCase):
    def test_trusted_domain_seeds_the_cache_as_trusted(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cache_path = tmp_path / "cache.json"
            result = onboard(
                "https://internal.example.com", mode="allow", cache_path=cache_path, policy_path=tmp_path / "policy.yaml"
            )
            self.assertEqual(result["label"], "trusted")

            entry = ScanCache(cache_path).get(result["resource"])
            self.assertEqual(entry.label, "trusted")

    def test_untrusted_ip_target_with_mode_allow_blocks_onboarding(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cache_path = tmp_path / "cache.json"
            with self.assertRaises(OnboardError) as ctx:
                onboard("https://203.0.113.42", mode="allow", cache_path=cache_path, policy_path=tmp_path / "policy.yaml")
            self.assertTrue(str(ctx.exception))
            self.assertFalse(cache_path.exists())

    def test_unknown_scheme_blocks_with_no_cache_write(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cache_path = tmp_path / "cache.json"
            with self.assertRaises(OnboardError):
                onboard("ftp://x.md", mode="allow", cache_path=cache_path, policy_path=tmp_path / "policy.yaml")
            self.assertFalse(cache_path.exists())

    def test_seeded_url_identity_matches_live_evaluation_normalization(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cache_path = tmp_path / "cache.json"

            from scalene.scanner import URLScanner

            result = onboard(
                "https://internal.example.com/docs/page?x=1",
                mode="allow",
                cache_path=cache_path,
                policy_path=tmp_path / "policy.yaml",
            )
            live_resources = URLScanner().identify("WebFetch", {"url": "https://internal.example.com/docs/page?x=1"})
            self.assertEqual(len(live_resources), 1)
            self.assertEqual(result["resource"].identity, live_resources[0].identity)
            self.assertEqual(result["resource"].identity, "https://internal.example.com/docs/page")


if __name__ == "__main__":
    unittest.main()
