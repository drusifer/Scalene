"""Tests for PolicyConfig YAML loading + JSONPath evaluation (STORY-201, STORY-202).

2026-07-14: schema simplified to one unified `allowlist`, keyed by each
rule's `target` URI scheme (`file://` -> sensitivity, `http(s)://` -> trust)
instead of two separate YAML sections.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scalene.policy_config import MatchResult, PolicyConfig, PolicyConfigError, PolicyRule


def write_yaml(tmp: Path, text: str) -> Path:
    path = tmp / "scalene_policy.yaml"
    path.write_text(text)
    return path


class TestPolicyConfigLoading(unittest.TestCase):
    def test_from_yaml_parses_full_schema(self):
        with TemporaryDirectory() as tmp:
            path = write_yaml(
                Path(tmp),
                """
                defaults:
                  sensitive_by_default: true
                  untrusted_by_default: true
                allowlist:
                  - tool: Read
                    jsonpath: "$.file_path"
                    pattern: "\\\\.md$"
                    target: "file:///workspace/docs"
                    description: "Markdown files are non-sensitive"
                  - tool: Bash
                    jsonpath: "$.command"
                    pattern: "^git "
                    target: "https://github.com"
                    description: "git commands are trusted"
                """,
            )
            config = PolicyConfig.from_yaml(path)
            self.assertTrue(config.sensitive_by_default)
            self.assertTrue(config.untrusted_by_default)
            self.assertEqual(len(config.allowlist), 2)
            self.assertIsInstance(config.allowlist[0], PolicyRule)

    def test_from_yaml_applies_defaults_when_sections_missing(self):
        with TemporaryDirectory() as tmp:
            path = write_yaml(Path(tmp), "defaults: {}\n")
            config = PolicyConfig.from_yaml(path)
            self.assertTrue(config.sensitive_by_default)
            self.assertTrue(config.untrusted_by_default)
            self.assertEqual(config.allowlist, [])

    def test_invalid_yaml_raises_clear_error_not_silent_noop(self):
        with TemporaryDirectory() as tmp:
            path = write_yaml(Path(tmp), "defaults: [this is not: valid: yaml")
            with self.assertRaises(PolicyConfigError):
                PolicyConfig.from_yaml(path)

    def test_rule_missing_required_field_raises(self):
        with TemporaryDirectory() as tmp:
            path = write_yaml(
                Path(tmp),
                """
                allowlist:
                  - tool: Read
                    jsonpath: "$.file_path"
                """,
            )
            with self.assertRaises(PolicyConfigError):
                PolicyConfig.from_yaml(path)

    def test_rule_missing_target_raises(self):
        with TemporaryDirectory() as tmp:
            path = write_yaml(
                Path(tmp),
                """
                allowlist:
                  - tool: Read
                    jsonpath: "$.file_path"
                    pattern: "\\\\.md$"
                """,
            )
            with self.assertRaises(PolicyConfigError):
                PolicyConfig.from_yaml(path)


class TestPolicyRuleScheme(unittest.TestCase):
    def test_file_scheme(self):
        rule = PolicyRule(tool="Read", jsonpath="$.x", pattern=".*", target="file:///a/b")
        self.assertEqual(rule.scheme, "file")

    def test_https_scheme(self):
        rule = PolicyRule(tool="Read", jsonpath="$.x", pattern=".*", target="https://example.com")
        self.assertEqual(rule.scheme, "https")

    def test_no_scheme_for_malformed_target(self):
        rule = PolicyRule(tool="Read", jsonpath="$.x", pattern=".*", target="not-a-uri")
        self.assertEqual(rule.scheme, "")


class TestPolicyConfigEvaluate(unittest.TestCase):
    def test_file_scheme_rule_matches_nested_json_parameters(self):
        config = PolicyConfig(
            allowlist=[
                PolicyRule(tool="Read", jsonpath="$.file_path", pattern=r"\.md$", target="file:///workspace/docs")
            ],
        )
        result = config.evaluate("Read", {"file_path": "docs/PRD.md"})
        self.assertIsInstance(result, MatchResult)
        self.assertFalse(result.is_sensitive)

    def test_https_scheme_rule_matches_shell_command_string(self):
        config = PolicyConfig(
            allowlist=[
                PolicyRule(tool="Bash", jsonpath="$.command", pattern=r"^git ", target="https://github.com")
            ],
        )
        result = config.evaluate("Bash", {"command": "git status"})
        self.assertTrue(result.is_trusted)

    def test_https_scheme_rule_matches_url_path(self):
        config = PolicyConfig(
            allowlist=[
                PolicyRule(
                    tool="WebFetch",
                    jsonpath="$.url",
                    pattern=r"^https://internal\.example\.com/",
                    target="https://internal.example.com",
                )
            ],
        )
        result = config.evaluate("WebFetch", {"url": "https://internal.example.com/api"})
        self.assertTrue(result.is_trusted)

    def test_file_scheme_rule_matches_db_table_column_target(self):
        config = PolicyConfig(
            allowlist=[
                PolicyRule(tool="DBQuery", jsonpath="$.table", pattern=r"^public\.", target="file:///workspace/db")
            ],
        )
        result = config.evaluate("DBQuery", {"table": "public.orders", "column": "id"})
        self.assertFalse(result.is_sensitive)

    def test_a_rule_only_affects_its_own_scheme(self):
        """A file:// rule must not also count toward trust, and vice versa —
        the two computations stay independent even in one unified list."""
        config = PolicyConfig(
            allowlist=[
                PolicyRule(tool="Bash", jsonpath="$.command", pattern=r"^git ", target="file:///workspace/docs"),
            ],
        )
        result = config.evaluate("Bash", {"command": "git status"})
        self.assertFalse(result.is_trusted)  # file:// rule doesn't grant trust

    def test_no_match_falls_back_to_defaults(self):
        config = PolicyConfig(sensitive_by_default=True, untrusted_by_default=True)
        result = config.evaluate("Read", {"file_path": "secrets/prod.env"})
        self.assertTrue(result.is_sensitive)
        self.assertFalse(result.is_trusted)
        self.assertFalse(result.fail_safe_triggered)

    def test_both_flags_can_be_true_simultaneously(self):
        # Triangle-of-Doom trigger condition (STORY-102)
        config = PolicyConfig(sensitive_by_default=True, untrusted_by_default=True)
        result = config.evaluate("Read", {"file_path": "secrets/prod.env"})
        self.assertTrue(result.is_sensitive)
        self.assertFalse(result.is_trusted)

    def test_malformed_jsonpath_fails_safe(self):
        config = PolicyConfig(
            allowlist=[
                PolicyRule(tool="Read", jsonpath="$[invalid(((", pattern=".*", target="file:///workspace/docs")
            ],
        )
        result = config.evaluate("Read", {"file_path": "docs/PRD.md"})
        self.assertTrue(result.is_sensitive)
        self.assertFalse(result.is_trusted)
        self.assertTrue(result.fail_safe_triggered)

    def test_fail_safe_path_is_logged_not_silent(self):
        # STORY-202 AC: "Fail-safe path is logged (not silent) for developer visibility."
        config = PolicyConfig(
            allowlist=[
                PolicyRule(tool="Read", jsonpath="$[invalid(((", pattern=".*", target="file:///workspace/docs")
            ],
        )
        with self.assertLogs("scalene.policy", level="WARNING") as captured:
            config.evaluate("Read", {"file_path": "docs/PRD.md"})
        self.assertTrue(any("Fail-safe" in msg for msg in captured.output))


if __name__ == "__main__":
    unittest.main()
