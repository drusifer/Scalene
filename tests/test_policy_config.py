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
    delete_rule,
    swap_rule_order,
    update_rule,
    write_default_project_policy,
)
from scalene.scanner import FileScanner, Resource


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
        self.assertEqual(rule.trust, "high")

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

    def test_pattern_is_not_regex_validated_at_construction_time(self):
        # 2026-07-30: pattern's syntax is scanner-owned (Scanner.match(),
        # scanner.py) -- FileScanner reads it as gitignore syntax, other
        # scanners still as regex -- and a rule doesn't have to declare
        # `scanner:` to be matched later, so PolicyRule can't know which
        # syntax applies at construction time. A leading "**/" (ordinary,
        # valid gitignore syntax) is not valid regex at all ("nothing to
        # repeat"), so unconditionally regex-validating `pattern` here would
        # reject legitimate glob patterns, not just genuine typos -- this
        # replaces the old test_invalid_pattern_regex_raises_clear_error,
        # whose premise no longer holds.
        rule = PolicyRule(tool=".*", pattern="**/*.env", sensitivity="public", mode="mask")
        self.assertEqual(rule.pattern, "**/*.env")

    def test_allow_mode_is_valid_on_a_rule(self):
        # docs/ARCHITECTURE.md sec14.4 amendment: the scoped suppression
        # exception -- a rule (never PolicyConfig.mode) may set mode=allow.
        rule = PolicyRule(tool=".*", pattern=".*", sensitivity="public", mode="allow")
        self.assertEqual(rule.mode, "allow")

    def test_trust_defaults_to_high(self):
        # sec21.8: "high" is trust's least-restrictive value -- a rule
        # written before this field existed (or that just doesn't care)
        # must not silently change decide_access() behavior.
        rule = PolicyRule(tool=".*", pattern=".*", sensitivity="public", mode="allow")
        self.assertEqual(rule.trust, "high")

    def test_explicit_trust_level_constructs(self):
        rule = PolicyRule(tool=".*", pattern=".*", sensitivity="public", mode="allow", trust="low")
        self.assertEqual(rule.trust, "low")

    def test_invalid_trust_raises(self):
        with self.assertRaises(PolicyConfigError):
            PolicyRule(tool=".*", pattern=".*", sensitivity="public", mode="allow", trust="paranoid")

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

    def test_rule_trust_parses_from_yaml_and_defaults_to_high(self):
        with TemporaryDirectory() as tmp:
            path = write_yaml(
                Path(tmp),
                """
                rules:
                  - tool: ".*"
                    pattern: "/project/**"
                    sensitivity: public
                    mode: allow
                    trust: low
                  - tool: ".*"
                    pattern: "/other/**"
                    sensitivity: public
                    mode: allow
                """,
            )
            config = PolicyConfig.from_yaml(path)
            self.assertEqual(config.rules[0].trust, "low")
            self.assertEqual(config.rules[1].trust, "high")

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
            # 2026-07-22 (sec19.3): no scanner filter needed -- a rule
            # author shouldn't have to name a scanner when the pattern
            # alone is already selective. Still true after 2026-07-30's
            # gitignore-syntax pattern change: Scanner.match()'s base
            # regex path now catches re.error and fails safe (no match)
            # for a scanner this pattern wasn't meant for, so the filter
            # was never re-needed for correctness.
            self.assertEqual(rule.scanner, "")

    def test_written_rule_matches_a_file_under_the_project_root(self):
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            policy_path = project_root / "scalene_policy.yaml"
            write_default_project_policy(policy_path, project_root)
            config = PolicyConfig.from_yaml(policy_path)
            rule = config.rules[0]
            target = str(project_root / "src" / "main.py")
            resource = Resource(kind="file", identity=target, scanner_name="secrets")
            self.assertTrue(FileScanner().match(rule, resource))

    def test_written_rule_matches_the_project_root_itself(self):
        # STORY-1504's original regex (`^root(/|$)`) matched the root path
        # itself, not just files under it -- the gitignore replacement
        # needs both "root" and "root/**" as separate lines to preserve
        # that (a bare "root/**" alone only matches root's *contents*).
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            policy_path = project_root / "scalene_policy.yaml"
            write_default_project_policy(policy_path, project_root)
            config = PolicyConfig.from_yaml(policy_path)
            rule = config.rules[0]
            resource = Resource(kind="file", identity=str(project_root), scanner_name="secrets")
            self.assertTrue(FileScanner().match(rule, resource))

    def test_written_rule_does_not_match_a_path_outside_the_project_root(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as other_tmp:
            project_root = Path(tmp)
            policy_path = project_root / "scalene_policy.yaml"
            write_default_project_policy(policy_path, project_root)
            config = PolicyConfig.from_yaml(policy_path)
            rule = config.rules[0]
            outside_target = str(Path(other_tmp) / "other.py")
            resource = Resource(kind="file", identity=outside_target, scanner_name="secrets")
            self.assertFalse(FileScanner().match(rule, resource))

    def test_written_rule_does_not_match_a_similarly_named_sibling_directory(self):
        # Boundary-safety regression test, same class as scanner.py's
        # existing "/etc" vs. false-positive "/etcetera" case -- a sibling
        # directory whose name happens to start with the project root's
        # name must not match.
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            policy_path = project_root / "scalene_policy.yaml"
            write_default_project_policy(policy_path, project_root)
            config = PolicyConfig.from_yaml(policy_path)
            rule = config.rules[0]
            sibling_target = str(Path(tmp) / "project-evil" / "x.py")
            resource = Resource(kind="file", identity=sibling_target, scanner_name="secrets")
            self.assertFalse(FileScanner().match(rule, resource))

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


class TestSwapRuleOrder(unittest.TestCase):
    """docs/ARCHITECTURE.md sec22.5 (STORY-1705): `scg monitor`'s Rules
    screen reorder controls. Rule order is real access-control precedence,
    not display -- this is the one function that actually rewrites it."""

    def _write_rules(self, policy_path: Path, rules: list[dict]) -> None:
        policy_path.write_text(yaml.safe_dump({"rules": rules}, sort_keys=False, default_flow_style=False))

    def test_moves_a_rule_down(self):
        with TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "scalene_policy.yaml"
            self._write_rules(
                policy_path,
                [
                    {"tool": ".*", "pattern": "a", "sensitivity": "public", "mode": "allow"},
                    {"tool": ".*", "pattern": "b", "sensitivity": "public", "mode": "allow"},
                ],
            )
            swap_rule_order(policy_path, index=0, direction=1)
            data = yaml.safe_load(policy_path.read_text())
            self.assertEqual([r["pattern"] for r in data["rules"]], ["b", "a"])

    def test_moves_a_rule_up(self):
        with TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "scalene_policy.yaml"
            self._write_rules(
                policy_path,
                [
                    {"tool": ".*", "pattern": "a", "sensitivity": "public", "mode": "allow"},
                    {"tool": ".*", "pattern": "b", "sensitivity": "public", "mode": "allow"},
                ],
            )
            swap_rule_order(policy_path, index=1, direction=-1)
            data = yaml.safe_load(policy_path.read_text())
            self.assertEqual([r["pattern"] for r in data["rules"]], ["b", "a"])

    def test_every_field_round_trips_unchanged_except_position(self):
        with TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "scalene_policy.yaml"
            self._write_rules(
                policy_path,
                [
                    {"tool": "Bash", "pattern": "a", "sensitivity": "restricted", "mode": "block", "scanner": "secrets", "description": "first", "trust": "low"},
                    {"tool": ".*", "pattern": "b", "sensitivity": "public", "mode": "allow"},
                ],
            )
            swap_rule_order(policy_path, index=0, direction=1)
            data = yaml.safe_load(policy_path.read_text())
            moved = data["rules"][1]
            self.assertEqual(
                moved,
                {"tool": "Bash", "pattern": "a", "sensitivity": "restricted", "mode": "block", "scanner": "secrets", "description": "first", "trust": "low"},
            )

    def test_reordering_changes_which_rule_actually_wins(self):
        # The real point: order is access-control precedence, verified via
        # PolicyConfig.from_yaml + the real matching path, not just the
        # written YAML's row order.
        from scalene.resource_verifier import decide_access
        from scalene.scan_cache import ScanCache
        from scalene.taint_state import TaintState

        with TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "scalene_policy.yaml"
            target = str(Path(tmp) / "secret.env")
            Path(target).write_text("nothing")
            # Broad allow first, specific block second -- broad wins today
            # (first-match), even though the specific rule is "more right".
            self._write_rules(
                policy_path,
                [
                    {"tool": ".*", "pattern": f"{target}", "sensitivity": "public", "mode": "allow"},
                    {"tool": ".*", "pattern": f"{target}", "sensitivity": "restricted", "mode": "block"},
                ],
            )
            cache_path = Path(tmp) / "scan_cache.json"
            state_dir = Path(tmp) / "state"
            state_dir.mkdir()

            config_before = PolicyConfig.from_yaml(policy_path)
            taint = TaintState(session_id="s1", state_dir=state_dir)
            decision_before = decide_access("Read", {"file_path": target}, config_before, ScanCache(cache_path), taint)
            self.assertTrue(decision_before.allowed)

            swap_rule_order(policy_path, index=0, direction=1)

            config_after = PolicyConfig.from_yaml(policy_path)
            taint2 = TaintState(session_id="s2", state_dir=state_dir)
            decision_after = decide_access("Read", {"file_path": target}, config_after, ScanCache(cache_path), taint2)
            self.assertFalse(decision_after.allowed)

    def test_missing_file_raises_policy_config_error_not_a_traceback(self):
        with TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "does_not_exist.yaml"
            with self.assertRaises(PolicyConfigError):
                swap_rule_order(policy_path, index=0, direction=1)

    def test_read_only_policy_file_raises_policy_config_error(self):
        import os
        import stat

        with TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "scalene_policy.yaml"
            self._write_rules(
                policy_path,
                [
                    {"tool": ".*", "pattern": "a", "sensitivity": "public", "mode": "allow"},
                    {"tool": ".*", "pattern": "b", "sensitivity": "public", "mode": "allow"},
                ],
            )
            policy_path.chmod(stat.S_IRUSR)
            try:
                with self.assertRaises(PolicyConfigError):
                    swap_rule_order(policy_path, index=0, direction=1)
            finally:
                policy_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
                os.chmod(tmp, 0o755)


class TestUpdateRule(unittest.TestCase):
    """docs/ARCHITECTURE.md sec23.7 (STORY-1807): `scg monitor`'s Rules
    screen edit action. Pure file-level unit tests -- no Textual/UI
    dependency, matching TestSwapRuleOrder's own style."""

    def _write_rules(self, policy_path: Path, rules: list[dict]) -> None:
        policy_path.write_text(yaml.safe_dump({"rules": rules}, sort_keys=False, default_flow_style=False))

    def test_replaces_the_rule_at_the_given_index(self):
        with TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "scalene_policy.yaml"
            self._write_rules(
                policy_path,
                [{"tool": ".*", "pattern": "old", "sensitivity": "public", "mode": "allow"}],
            )
            update_rule(policy_path, 0, PolicyRule(tool="Bash", pattern="new", sensitivity="restricted", mode="block"))
            data = yaml.safe_load(policy_path.read_text())
            self.assertEqual(
                data["rules"][0],
                {"tool": "Bash", "pattern": "new", "sensitivity": "restricted", "mode": "block"},
            )

    def test_other_rules_and_order_are_unaffected(self):
        with TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "scalene_policy.yaml"
            self._write_rules(
                policy_path,
                [
                    {"tool": ".*", "pattern": "a", "sensitivity": "public", "mode": "allow"},
                    {"tool": ".*", "pattern": "b", "sensitivity": "public", "mode": "allow"},
                    {"tool": ".*", "pattern": "c", "sensitivity": "public", "mode": "allow"},
                ],
            )
            update_rule(policy_path, 1, PolicyRule(tool=".*", pattern="edited-b", sensitivity="public", mode="allow"))
            data = yaml.safe_load(policy_path.read_text())
            self.assertEqual([r["pattern"] for r in data["rules"]], ["a", "edited-b", "c"])

    def test_serializes_in_write_rule_shape_omitting_defaults(self):
        # scanner/description omitted when empty, trust omitted at its
        # default "high" -- matches onboard.write_rule's own convention so
        # an edited rule looks identical to a freshly-authored one.
        with TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "scalene_policy.yaml"
            self._write_rules(
                policy_path,
                [{"tool": "Bash", "pattern": "old", "sensitivity": "restricted", "mode": "block", "scanner": "secrets", "description": "stale", "trust": "low"}],
            )
            update_rule(policy_path, 0, PolicyRule(tool=".*", pattern="new", sensitivity="public", mode="allow"))
            data = yaml.safe_load(policy_path.read_text())
            self.assertEqual(data["rules"][0], {"tool": ".*", "pattern": "new", "sensitivity": "public", "mode": "allow"})

    def test_serializes_non_default_scanner_description_and_trust(self):
        with TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "scalene_policy.yaml"
            self._write_rules(policy_path, [{"tool": ".*", "pattern": "a", "sensitivity": "public", "mode": "allow"}])
            update_rule(
                policy_path,
                0,
                PolicyRule(tool="Bash", pattern="b", sensitivity="restricted", mode="block", scanner="secrets", description="real", trust="low"),
            )
            data = yaml.safe_load(policy_path.read_text())
            self.assertEqual(
                data["rules"][0],
                {"tool": "Bash", "pattern": "b", "sensitivity": "restricted", "mode": "block", "scanner": "secrets", "description": "real", "trust": "low"},
            )

    def test_out_of_range_index_raises_index_error(self):
        with TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "scalene_policy.yaml"
            self._write_rules(policy_path, [{"tool": ".*", "pattern": "a", "sensitivity": "public", "mode": "allow"}])
            with self.assertRaises(IndexError):
                update_rule(policy_path, 5, PolicyRule(tool=".*", pattern="b", sensitivity="public", mode="allow"))

    def test_missing_file_raises_policy_config_error_not_a_traceback(self):
        with TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "does_not_exist.yaml"
            with self.assertRaises(PolicyConfigError):
                update_rule(policy_path, 0, PolicyRule(tool=".*", pattern="a", sensitivity="public", mode="allow"))

    def test_editing_a_rules_pattern_changes_which_rule_a_real_hook_call_resolves_with(self):
        # Trin's UAT (sec23.7, mirrors TestSwapRuleOrder's own hard e2e AC):
        # the real point of "edit" is that it's a genuine access-control
        # write, not just a YAML content change -- verified via
        # PolicyConfig.from_yaml + the real matching path.
        #
        # Deliberately anchored on the `confirmed_bad`/block branch for
        # "before" (Trin's own correction after a first draft of this test
        # wrongly relied on decide_access's separate "clean session's first
        # touch gets a free pass" behavior for its *before* assertion too --
        # that path fires regardless of which rule matched, so it couldn't
        # actually prove the edit was what changed the outcome). A matching
        # `mode=block` rule blocks deterministically, independent of session
        # state, so "before" only passes because the rule really matched.
        from scalene.resource_verifier import decide_access
        from scalene.scan_cache import ScanCache
        from scalene.taint_state import TaintState

        with TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "scalene_policy.yaml"
            target = str(Path(tmp) / "secret.env")
            Path(target).write_text("nothing")
            other = str(Path(tmp) / "other.env")
            Path(other).write_text("nothing")
            self._write_rules(policy_path, [{"tool": ".*", "pattern": target, "sensitivity": "restricted", "mode": "block"}])
            cache_path = Path(tmp) / "scan_cache.json"
            state_dir = Path(tmp) / "state"
            state_dir.mkdir()

            config_before = PolicyConfig.from_yaml(policy_path)
            taint = TaintState(session_id="s1", state_dir=state_dir)
            decision_before = decide_access("Read", {"file_path": target}, config_before, ScanCache(cache_path), taint)
            self.assertFalse(decision_before.allowed)  # rule matches `target` with mode=block

            update_rule(policy_path, 0, PolicyRule(tool=".*", pattern=other, sensitivity="restricted", mode="block"))

            config_after = PolicyConfig.from_yaml(policy_path)
            taint2 = TaintState(session_id="s2", state_dir=state_dir)
            decision_after = decide_access("Read", {"file_path": target}, config_after, ScanCache(cache_path), taint2)
            self.assertTrue(decision_after.allowed)  # edited rule no longer matches `target`


class TestDeleteRule(unittest.TestCase):
    """docs/ARCHITECTURE.md sec23.7 (STORY-1808): `scg monitor`'s Rules
    screen delete action."""

    def _write_rules(self, policy_path: Path, rules: list[dict]) -> None:
        policy_path.write_text(yaml.safe_dump({"rules": rules}, sort_keys=False, default_flow_style=False))

    def test_removes_the_rule_at_the_given_index(self):
        with TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "scalene_policy.yaml"
            self._write_rules(
                policy_path,
                [
                    {"tool": ".*", "pattern": "a", "sensitivity": "public", "mode": "allow"},
                    {"tool": ".*", "pattern": "b", "sensitivity": "public", "mode": "allow"},
                ],
            )
            delete_rule(policy_path, 0)
            data = yaml.safe_load(policy_path.read_text())
            self.assertEqual([r["pattern"] for r in data["rules"]], ["b"])

    def test_other_rules_and_order_are_unaffected(self):
        with TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "scalene_policy.yaml"
            self._write_rules(
                policy_path,
                [
                    {"tool": ".*", "pattern": "a", "sensitivity": "public", "mode": "allow"},
                    {"tool": ".*", "pattern": "b", "sensitivity": "public", "mode": "allow"},
                    {"tool": ".*", "pattern": "c", "sensitivity": "public", "mode": "allow"},
                ],
            )
            delete_rule(policy_path, 1)
            data = yaml.safe_load(policy_path.read_text())
            self.assertEqual([r["pattern"] for r in data["rules"]], ["a", "c"])

    def test_out_of_range_index_raises_index_error(self):
        with TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "scalene_policy.yaml"
            self._write_rules(policy_path, [{"tool": ".*", "pattern": "a", "sensitivity": "public", "mode": "allow"}])
            with self.assertRaises(IndexError):
                delete_rule(policy_path, 5)

    def test_missing_file_raises_policy_config_error_not_a_traceback(self):
        with TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "does_not_exist.yaml"
            with self.assertRaises(PolicyConfigError):
                delete_rule(policy_path, 0)

    def test_deleting_a_rule_changes_which_rule_a_real_hook_call_resolves_with(self):
        # Trin's UAT (sec23.7): deleting the rule that was actively
        # blocking a resource must genuinely stop blocking it, verified via
        # the real matching path -- not just that the YAML shrank by one.
        #
        # Anchored on the deterministic `confirmed_bad`/block branch for
        # "before" (same correction as TestUpdateRule's e2e test above --
        # a matching mode=block rule blocks regardless of session state,
        # unlike an "allow" outcome, which can also come from decide_
        # access's separate clean-session first-touch free pass and so
        # wouldn't actually prove the *rule* was what granted it).
        from scalene.resource_verifier import decide_access
        from scalene.scan_cache import ScanCache
        from scalene.taint_state import TaintState

        with TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "scalene_policy.yaml"
            target = str(Path(tmp) / "secret.env")
            Path(target).write_text("nothing")
            self._write_rules(policy_path, [{"tool": ".*", "pattern": target, "sensitivity": "restricted", "mode": "block"}])
            cache_path = Path(tmp) / "scan_cache.json"
            state_dir = Path(tmp) / "state"
            state_dir.mkdir()

            config_before = PolicyConfig.from_yaml(policy_path)
            taint = TaintState(session_id="s1", state_dir=state_dir)
            decision_before = decide_access("Read", {"file_path": target}, config_before, ScanCache(cache_path), taint)
            self.assertFalse(decision_before.allowed)  # rule matches `target` with mode=block

            delete_rule(policy_path, 0)

            config_after = PolicyConfig.from_yaml(policy_path)
            taint2 = TaintState(session_id="s2", state_dir=state_dir)
            decision_after = decide_access("Read", {"file_path": target}, config_after, ScanCache(cache_path), taint2)
            self.assertTrue(decision_after.allowed)  # no rule left to block it


if __name__ == "__main__":
    unittest.main()
