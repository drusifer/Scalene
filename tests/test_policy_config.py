"""Tests for PolicyConfig YAML loading (STORY-201, STORY-202).

2026-07-14 (Sprint 4 Phase 3, docs/ARCHITECTURE.md sec13.1): PolicyRule and
`allowlist`-based JSONPath rule matching removed entirely -- full
replacement, not coexistence (see tests/test_resource_verifier.py and
tests/test_scanner.py for the new resource-identification/verification
model). This module now only loads sensitivity/trust defaults + mode.

2026-07-17 (Sprint 5 Phase 1, docs/ARCHITECTURE.md sec14.1/14.5): PolicyRule
returns, generalized -- decides candidacy/classification (sensitivity/mode)
of an already-identified Resource, never trust directly (sec14.1). Optional
top-level `rules:` list in scalene_policy.yaml, sibling to `defaults:`.
"""

import logging
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from scalene.policy_config import (
    MatchResult,
    PolicyConfig,
    PolicyConfigError,
    PolicyRule,
    write_default_project_policy,
)


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

    def test_sensitivity_and_mode_default(self):
        result = MatchResult(is_sensitive=True, is_trusted=False)
        self.assertEqual(result.sensitivity, "public")
        self.assertEqual(result.mode, "mask")

    def test_untrusted_url_defaults_empty(self):
        result = MatchResult(is_sensitive=True, is_trusted=False)
        self.assertEqual(result.untrusted_url, "")


class TestPolicyRule(unittest.TestCase):
    def test_valid_rule_constructs(self):
        rule = PolicyRule(
            tool=".*",
            pattern="https://internal\\.example\\.com/.*",
            sensitivity="internal",
            mode="block",
        )
        self.assertEqual(rule.jsonpath, "")
        self.assertEqual(rule.scanner, "")
        self.assertEqual(rule.description, "")

    def test_invalid_sensitivity_raises(self):
        with self.assertRaises(PolicyConfigError):
            PolicyRule(tool=".*", pattern=".*", sensitivity="top_secret", mode="mask")

    def test_invalid_mode_raises(self):
        with self.assertRaises(PolicyConfigError):
            PolicyRule(tool=".*", pattern=".*", sensitivity="public", mode="delete_everything")

    def test_invalid_tool_regex_raises_clear_error(self):
        # Trin's adversarial UAT finding (Phase 2): an invalid regex must
        # fail loud at rule-construction time, not crash evaluate() deep in
        # the hot path on every subsequent call.
        with self.assertRaises(PolicyConfigError):
            PolicyRule(tool="[unclosed", pattern=".*", sensitivity="public", mode="mask")

    def test_invalid_pattern_regex_raises_clear_error(self):
        with self.assertRaises(PolicyConfigError):
            PolicyRule(tool=".*", pattern="[unclosed", sensitivity="public", mode="mask")

    def test_allow_mode_is_valid_on_a_rule(self):
        # docs/ARCHITECTURE.md sec14.4 amendment: the scoped suppression
        # exception -- a rule (never PolicyConfig.mode) may set mode=allow.
        rule = PolicyRule(tool=".*", pattern=".*", sensitivity="public", mode="allow")
        self.assertEqual(rule.mode, "allow")

    def test_valid_scanner_name_constructs(self):
        rule = PolicyRule(tool=".*", pattern=".*", sensitivity="public", mode="allow", scanner="reputation")
        self.assertEqual(rule.scanner, "reputation")

    def test_empty_scanner_is_not_validated(self):
        # The common case -- inferred from the matched resource, not required.
        rule = PolicyRule(tool=".*", pattern=".*", sensitivity="public", mode="allow", scanner="")
        self.assertEqual(rule.scanner, "")

    def test_invalid_scanner_name_no_longer_validated_at_construction(self):
        # sec18.1 (STORY-1501): moved out of PolicyRule.__post_init__ --
        # a rule can't see a dynamically-loaded registry from inside its
        # own constructor. Direct construction (this test) no longer raises;
        # see TestPolicyConfigScanners below for the real, still-fail-loud
        # check at PolicyConfig.from_yaml's YAML-loading boundary, which is
        # the only place an actual user ever hits this.
        rule = PolicyRule(tool=".*", pattern=".*", sensitivity="public", mode="allow", scanner="reputatoin")
        self.assertEqual(rule.scanner, "reputatoin")


class TestPolicyConfigModeExcludesAllow(unittest.TestCase):
    def test_global_default_mode_rejects_allow(self):
        # allow is a rule-only exception -- a project-wide default of
        # "allow" would blanket-disable scanning, defeating the point of a
        # scoped, hand-authored exception (sec14.4).
        with self.assertRaises(PolicyConfigError):
            PolicyConfig(mode="allow")


class TestPolicyConfigRulesLoading(unittest.TestCase):
    def test_rules_section_absent_yields_empty_list(self):
        with TemporaryDirectory() as tmp:
            path = write_yaml(Path(tmp), "defaults: {}\n")
            config = PolicyConfig.from_yaml(path)
            self.assertEqual(config.rules, ())

    def test_rules_section_parses_into_policy_rules(self):
        with TemporaryDirectory() as tmp:
            path = write_yaml(
                Path(tmp),
                """
                defaults:
                  mode: mask
                rules:
                  - tool: ".*"
                    pattern: "https://internal\\\\.example\\\\.com/.*"
                    sensitivity: internal
                    mode: block
                    description: "Internal wiki"
                """,
            )
            config = PolicyConfig.from_yaml(path)
            self.assertEqual(len(config.rules), 1)
            rule = config.rules[0]
            self.assertEqual(rule.tool, ".*")
            self.assertEqual(rule.sensitivity, "internal")
            self.assertEqual(rule.mode, "block")
            self.assertEqual(rule.description, "Internal wiki")

    def test_rule_missing_required_field_raises_clear_error(self):
        with TemporaryDirectory() as tmp:
            path = write_yaml(
                Path(tmp),
                """
                rules:
                  - tool: ".*"
                    sensitivity: public
                    mode: mask
                """,
            )
            with self.assertRaises(PolicyConfigError):
                PolicyConfig.from_yaml(path)

    def test_rule_invalid_sensitivity_in_yaml_raises_clear_error(self):
        with TemporaryDirectory() as tmp:
            path = write_yaml(
                Path(tmp),
                """
                rules:
                  - tool: ".*"
                    pattern: ".*"
                    sensitivity: nope
                    mode: mask
                """,
            )
            with self.assertRaises(PolicyConfigError):
                PolicyConfig.from_yaml(path)

    def test_rules_section_not_a_list_raises(self):
        with TemporaryDirectory() as tmp:
            path = write_yaml(Path(tmp), "rules: not-a-list\n")
            with self.assertRaises(PolicyConfigError):
                PolicyConfig.from_yaml(path)


class TestPolicyConfigScanners(unittest.TestCase):
    """docs/ARCHITECTURE.md sec18.1 (STORY-1501): config-driven registry."""

    def test_bare_config_defaults_to_the_two_builtins(self):
        config = PolicyConfig()
        self.assertEqual(set(config.scanners), {"secrets", "reputation"})

    def test_from_yaml_with_no_scanners_section_matches_bare_default(self):
        with TemporaryDirectory() as tmp:
            path = write_yaml(Path(tmp), "defaults: {}\n")
            config = PolicyConfig.from_yaml(path)
            self.assertEqual(set(config.scanners), {"secrets", "reputation"})

    def test_from_yaml_loads_an_extra_scanner(self):
        with TemporaryDirectory() as tmp:
            path = write_yaml(
                Path(tmp),
                """
                scanners:
                  extra:
                    - name: dummy
                      import: "fixtures_custom_scanner:DummyScanner"
                """,
            )
            config = PolicyConfig.from_yaml(path)
            self.assertIn("dummy", config.scanners)
            self.assertIn("secrets", config.scanners)

    def test_from_yaml_bad_scanner_import_raises_policy_config_error(self):
        with TemporaryDirectory() as tmp:
            path = write_yaml(
                Path(tmp),
                """
                scanners:
                  extra:
                    - name: dummy
                      import: "no.such.module:Whatever"
                """,
            )
            with self.assertRaises(PolicyConfigError):
                PolicyConfig.from_yaml(path)

    def test_scanners_section_not_a_mapping_raises(self):
        with TemporaryDirectory() as tmp:
            path = write_yaml(Path(tmp), "scanners: not-a-mapping\n")
            with self.assertRaises(PolicyConfigError):
                PolicyConfig.from_yaml(path)

    def test_rule_scanner_validated_against_the_loaded_registry_not_just_builtins(self):
        # A rule can now legitimately reference a config-declared scanner.
        with TemporaryDirectory() as tmp:
            path = write_yaml(
                Path(tmp),
                """
                scanners:
                  extra:
                    - name: dummy
                      import: "fixtures_custom_scanner:DummyScanner"
                rules:
                  - tool: ".*"
                    pattern: ".*"
                    sensitivity: public
                    mode: allow
                    scanner: dummy
                """,
            )
            config = PolicyConfig.from_yaml(path)
            self.assertEqual(config.rules[0].scanner, "dummy")

    def test_rule_with_typo_scanner_name_still_fails_loud_at_yaml_load_time(self):
        # sec18.1: the real, user-visible fail-loud behavior is unchanged --
        # only *where* it's checked moved (from_yaml, not PolicyRule.__init__).
        with TemporaryDirectory() as tmp:
            path = write_yaml(
                Path(tmp),
                """
                rules:
                  - tool: ".*"
                    pattern: ".*"
                    sensitivity: public
                    mode: allow
                    scanner: reputatoin
                """,
            )
            with self.assertRaises(PolicyConfigError):
                PolicyConfig.from_yaml(path)


class TestRepoOwnPolicyFile(unittest.TestCase):
    """STORY-1105 (docs/ARCHITECTURE.md sec14.6): this repo's own root
    scalene_policy.yaml had a pre-Sprint-4 `allowlist:` block that was
    silently dead since E10 shipped -- rewritten to the new `rules:` schema.
    A real regression test, not a one-off manual check, so a future change
    can't silently reintroduce a config this project's own scg would choke
    on or silently ignore."""

    def _repo_policy_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "scalene_policy.yaml"

    def test_repo_policy_file_parses_without_error(self):
        config = PolicyConfig.from_yaml(self._repo_policy_path())
        self.assertIsInstance(config, PolicyConfig)

    def test_repo_policy_file_has_no_dead_allowlist_key(self):
        data = yaml.safe_load(self._repo_policy_path().read_text())
        self.assertNotIn("allowlist", data)

    def test_repo_policy_file_rules_parse_into_policy_rules(self):
        config = PolicyConfig.from_yaml(self._repo_policy_path())
        self.assertGreaterEqual(len(config.rules), 1)
        for rule in config.rules:
            self.assertIsInstance(rule, PolicyRule)


class TestWriteDefaultProjectPolicy(unittest.TestCase):
    """docs/ARCHITECTURE.md sec18.4 (STORY-1504, corrected 2026-07-21 per
    direct user request): a brand-new project gets a real rule for its own
    folder written to a real scalene_policy.yaml -- not an implicit,
    in-memory special case."""

    def test_writes_a_real_yaml_file_with_one_rule(self):
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            policy_path = project_root / "scalene_policy.yaml"
            write_default_project_policy(policy_path, project_root)
            self.assertTrue(policy_path.exists())
            data = yaml.safe_load(policy_path.read_text())
            self.assertEqual(len(data["rules"]), 1)

    def test_written_rule_parses_as_an_ordinary_policy_rule(self):
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            policy_path = project_root / "scalene_policy.yaml"
            write_default_project_policy(policy_path, project_root)
            config = PolicyConfig.from_yaml(policy_path)
            self.assertEqual(len(config.rules), 1)
            rule = config.rules[0]
            self.assertEqual(rule.sensitivity, "internal")
            self.assertEqual(rule.mode, "allow")
            # 2026-07-22: no scanner filter -- the anchored absolute-path
            # pattern is already selective enough on its own.
            self.assertEqual(rule.scanner, "")

    def test_written_rule_matches_a_file_under_the_project_root(self):
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            policy_path = project_root / "scalene_policy.yaml"
            write_default_project_policy(policy_path, project_root)
            config = PolicyConfig.from_yaml(policy_path)
            rule = config.rules[0]
            target = str(project_root / "src" / "main.py")
            self.assertRegex(target, rule.pattern)

    def test_written_rule_does_not_match_a_path_outside_the_project_root(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as other_tmp:
            project_root = Path(tmp)
            policy_path = project_root / "scalene_policy.yaml"
            write_default_project_policy(policy_path, project_root)
            config = PolicyConfig.from_yaml(policy_path)
            rule = config.rules[0]
            outside_target = str(Path(other_tmp) / "other.py")
            self.assertNotRegex(outside_target, rule.pattern)

    def test_no_scan_cache_entry_is_pre_seeded(self):
        # User's own explicit direction: "timestamp uninitialized so that it
        # scans on first tool use" -- this function must only ever write the
        # rule, never a cache entry.
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            policy_path = project_root / "scalene_policy.yaml"
            write_default_project_policy(policy_path, project_root)
            self.assertFalse((project_root / "scan_cache.json").exists())
            self.assertFalse((project_root / ".scalene").exists())


if __name__ == "__main__":
    unittest.main()
