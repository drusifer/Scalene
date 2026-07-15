"""Tests for PolicyConfig YAML loading (STORY-201, STORY-202).

2026-07-14 (Sprint 4 Phase 3, docs/ARCHITECTURE.md sec13.1): PolicyRule and
`allowlist`-based JSONPath rule matching removed entirely -- full
replacement, not coexistence (see tests/test_resource_verifier.py and
tests/test_scanner.py for the new resource-identification/verification
model). This module now only loads sensitivity/trust defaults + mode.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scalene.policy_config import MatchResult, PolicyConfig, PolicyConfigError


def write_yaml(tmp: Path, text: str) -> Path:
    path = tmp / "scalene_policy.yaml"
    path.write_text(text)
    return path


class TestPolicyConfigLoading(unittest.TestCase):
    def test_from_yaml_parses_defaults(self):
        with TemporaryDirectory() as tmp:
            path = write_yaml(
                Path(tmp),
                """
                defaults:
                  sensitive_by_default: true
                  untrusted_by_default: true
                  mode: mask
                """,
            )
            config = PolicyConfig.from_yaml(path)
            self.assertTrue(config.sensitive_by_default)
            self.assertTrue(config.untrusted_by_default)
            self.assertEqual(config.mode, "mask")

    def test_from_yaml_applies_defaults_when_section_missing(self):
        with TemporaryDirectory() as tmp:
            path = write_yaml(Path(tmp), "defaults: {}\n")
            config = PolicyConfig.from_yaml(path)
            self.assertTrue(config.sensitive_by_default)
            self.assertTrue(config.untrusted_by_default)

    def test_from_yaml_with_no_file_content_uses_all_defaults(self):
        with TemporaryDirectory() as tmp:
            path = write_yaml(Path(tmp), "")
            config = PolicyConfig.from_yaml(path)
            self.assertTrue(config.sensitive_by_default)
            self.assertTrue(config.untrusted_by_default)
            self.assertEqual(config.mode, "mask")

    def test_invalid_yaml_raises_clear_error_not_silent_noop(self):
        with TemporaryDirectory() as tmp:
            path = write_yaml(Path(tmp), "defaults: [this is not: valid: yaml")
            with self.assertRaises(PolicyConfigError):
                PolicyConfig.from_yaml(path)

    def test_non_mapping_yaml_raises(self):
        with TemporaryDirectory() as tmp:
            path = write_yaml(Path(tmp), "- just\n- a\n- list\n")
            with self.assertRaises(PolicyConfigError):
                PolicyConfig.from_yaml(path)

    def test_missing_file_raises(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(PolicyConfigError):
                PolicyConfig.from_yaml(Path(tmp) / "does_not_exist.yaml")


class TestPolicyConfigMode(unittest.TestCase):
    def test_invalid_mode_raises(self):
        with self.assertRaises(PolicyConfigError):
            PolicyConfig(mode="delete_everything")

    def test_default_mode_is_mask(self):
        self.assertEqual(PolicyConfig().mode, "mask")


class TestMatchResult(unittest.TestCase):
    def test_fail_safe_triggered_defaults_to_false(self):
        result = MatchResult(is_sensitive=True, is_trusted=False)
        self.assertFalse(result.fail_safe_triggered)


if __name__ == "__main__":
    unittest.main()
