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
from unittest.mock import patch

from scalene.onboard import OnboardError, identify_targets, load_tool_call, main, onboard, onboard_targets
from scalene.policy_config import PolicyConfig, write_default_project_policy
from scalene.scan_cache import ScanCache
from scalene.scanner import Resource

from _env_guards import disable_remote_reputation, restore_remote_reputation

# sec18.3 (STORY-1503): onboarding a URL target calls URLScanner.scan()
# synchronously (a real finding is required before writing a rule) -- this
# would otherwise block on a real URLhaus call. See _env_guards.py.
setUpModule = disable_remote_reputation
tearDownModule = restore_remote_reputation


class TestIdentifyTargets(unittest.TestCase):
    """docs/ARCHITECTURE.md sec17.1/17.2 (Sprint 8/E14, STORY-1401): target
    discovery moves from a hand-typed --target URI to traversing SCANNERS
    and calling each scanner's own identify() -- the exact mechanism
    pre_tool_use already runs live, not a second hand-rolled resolver."""

    def test_traverses_every_registered_scanner(self):
        # A Bash command touching both a file path and a URL must be fully
        # covered by one call -- not one scanner type at a time.
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "clean.md"
            target.write_text("ordinary docs")
            resources = identify_targets("Bash", {"command": f"cat {target} && curl https://example.com/x"})
            kinds = {r.kind for r in resources}
            self.assertEqual(kinds, {"file", "url"})

    def test_known_field_target_is_identified(self):
        resources = identify_targets("Read", {"file_path": "/tmp/secret.txt"})
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].kind, "file")
        self.assertEqual(resources[0].identity, os.path.abspath("/tmp/secret.txt"))

    def test_no_targets_in_an_unrelated_call_returns_empty(self):
        resources = identify_targets("Bash", {"command": "echo hello world"})
        self.assertEqual(resources, [])

    def test_deduplicates_by_kind_and_identity(self):
        # The same URL can surface via a known field AND the generic
        # fallback scan of the same string -- must not be listed twice.
        resources = identify_targets("WebFetch", {"url": "https://example.com/x", "prompt": "fetch https://example.com/x"})
        url_resources = [r for r in resources if r.identity == "https://example.com/x"]
        self.assertEqual(len(url_resources), 1)


class TestLoadToolCall(unittest.TestCase):
    """docs/ARCHITECTURE.md sec17.1: the same {"tool_name", "tool_input"}
    field names scalene-guard's own hook contract already uses -- one
    mental model, not two."""

    def test_reads_from_a_file_via_call_path(self):
        with TemporaryDirectory() as tmp:
            call_path = Path(tmp) / "call.json"
            call_path.write_text('{"tool_name": "Read", "tool_input": {"file_path": "/tmp/x"}}')
            tool_name, tool_input = load_tool_call(call_path=str(call_path))
            self.assertEqual(tool_name, "Read")
            self.assertEqual(tool_input, {"file_path": "/tmp/x"})

    def test_malformed_json_raises_onboard_error_not_a_raw_exception(self):
        with TemporaryDirectory() as tmp:
            call_path = Path(tmp) / "call.json"
            call_path.write_text("not valid json{{{")
            with self.assertRaises(OnboardError):
                load_tool_call(call_path=str(call_path))

    def test_missing_tool_name_raises_onboard_error(self):
        with TemporaryDirectory() as tmp:
            call_path = Path(tmp) / "call.json"
            call_path.write_text('{"tool_input": {}}')
            with self.assertRaises(OnboardError):
                load_tool_call(call_path=str(call_path))

    def test_missing_file_raises_onboard_error(self):
        with self.assertRaises(OnboardError):
            load_tool_call(call_path="/no/such/file.json")

    def test_json_that_is_not_an_object_raises_onboard_error(self):
        # Trin's UAT (Sprint 8/E14 Phase 1): valid JSON, wrong shape (an
        # array, not an object) -- must fail loud, not IndexError/TypeError
        # deep inside dict-key access.
        with TemporaryDirectory() as tmp:
            call_path = Path(tmp) / "call.json"
            call_path.write_text("[1, 2, 3]")
            with self.assertRaises(OnboardError):
                load_tool_call(call_path=str(call_path))


class TestOnboardTargets(unittest.TestCase):
    """docs/ARCHITECTURE.md sec17.4 (STORY-1403): per-target scan + rule-
    write with batch semantics -- one target failing must not abort the
    others. sensitivity/mode/scanner/description apply once, batch-level,
    to every target (sec17.4) -- --tool/--pattern are gone entirely,
    replaced by the fixed default (tool=".*", pattern=exact identity)."""

    def test_requires_at_least_one_axis_before_touching_any_target(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")
            resource = Resource(kind="file", identity=str(target), scanner_name="secrets")
            with self.assertRaises(OnboardError):
                onboard_targets([resource], cache_path=tmp_path / "cache.json", policy_path=tmp_path / "policy.yaml")

    def test_all_clean_targets_onboard_successfully(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            t1 = tmp_path / "a.md"
            t1.write_text("ordinary docs")
            t2 = tmp_path / "b.md"
            t2.write_text("more ordinary docs")
            targets = [
                Resource(kind="file", identity=str(t1), scanner_name="secrets"),
                Resource(kind="file", identity=str(t2), scanner_name="secrets"),
            ]
            results = onboard_targets(
                targets, mode="allow", cache_path=tmp_path / "cache.json", policy_path=tmp_path / "policy.yaml"
            )
            self.assertEqual(len(results), 2)
            self.assertTrue(all(r["ok"] for r in results))
            config = PolicyConfig.from_yaml(tmp_path / "policy.yaml")
            self.assertEqual(len(config.rules), 2)

    def test_one_bad_target_does_not_abort_the_others(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            clean = tmp_path / "clean.md"
            clean.write_text("ordinary docs")
            leaky = tmp_path / "leaky.env"
            fake_key = "AKIA" + "ABCDEFGHIJKLMNOP"
            leaky.write_text(f"AWS_KEY={fake_key}")
            targets = [
                Resource(kind="file", identity=str(clean), scanner_name="secrets"),
                Resource(kind="file", identity=str(leaky), scanner_name="secrets"),
            ]
            results = onboard_targets(
                targets, mode="allow", cache_path=tmp_path / "cache.json", policy_path=tmp_path / "policy.yaml"
            )
            self.assertEqual(len(results), 2)
            ok_by_identity = {r["resource"].identity: r["ok"] for r in results}
            self.assertTrue(ok_by_identity[str(clean)])
            self.assertFalse(ok_by_identity[str(leaky)])
            config = PolicyConfig.from_yaml(tmp_path / "policy.yaml")
            self.assertEqual(len(config.rules), 1)

    def test_pattern_defaults_to_exact_identity_no_tool_pattern_flags(self):
        # sec17.4: --tool/--pattern are removed from this flow entirely --
        # confirms the fixed default still applies, not a regression.
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")
            resource = Resource(kind="file", identity=str(target), scanner_name="secrets")
            results = onboard_targets(
                [resource], mode="allow", cache_path=tmp_path / "cache.json", policy_path=tmp_path / "policy.yaml"
            )
            self.assertEqual(results[0]["rule"].pattern, re.escape(str(target)))
            self.assertEqual(results[0]["rule"].tool, ".*")

    def test_result_includes_reputation_when_present(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            resource = Resource(kind="url", identity="https://internal.example.com", scanner_name="reputation")
            results = onboard_targets(
                [resource], mode="allow", cache_path=tmp_path / "cache.json", policy_path=tmp_path / "policy.yaml"
            )
            self.assertEqual(results[0]["reputation"], 1.0)


class TestConfirmTargets(unittest.TestCase):
    """docs/ARCHITECTURE.md sec17.3 (STORY-1402, Smith's Gate 1 hard
    requirement): interactive by default, --yes/--only as the two required
    non-interactive escapes, fail-fast (not hang) with no TTY and neither."""

    def setUp(self):
        from scalene.onboard import _confirm_targets

        self._confirm_targets = _confirm_targets
        self.targets = [
            Resource(kind="file", identity="/tmp/a.md", scanner_name="secrets"),
            Resource(kind="url", identity="https://example.com/x", scanner_name="reputation"),
        ]

    def test_yes_confirms_every_target_without_prompting(self):
        with patch("builtins.input") as mock_input:
            confirmed = self._confirm_targets(self.targets, yes=True, only=None)
            mock_input.assert_not_called()
        self.assertEqual(confirmed, self.targets)

    def test_only_confirms_named_subset_without_prompting(self):
        with patch("builtins.input") as mock_input:
            confirmed = self._confirm_targets(self.targets, yes=False, only="/tmp/a.md")
            mock_input.assert_not_called()
        self.assertEqual(confirmed, [self.targets[0]])

    def test_only_with_an_unidentified_identity_fails_loud(self):
        with self.assertRaises(OnboardError) as ctx:
            self._confirm_targets(self.targets, yes=False, only="/tmp/never-identified.md")
        self.assertIn("/tmp/never-identified.md", str(ctx.exception))

    def test_no_tty_and_neither_escape_fails_fast_not_hang(self):
        # The exact failure mode Smith's hard requirement exists to prevent:
        # a script/test piping input must get an immediate, clear error,
        # never a blocked read() waiting on input that will never arrive.
        with patch("sys.stdin.isatty", return_value=False), patch("builtins.input") as mock_input:
            with self.assertRaises(OnboardError) as ctx:
                self._confirm_targets(self.targets, yes=False, only=None)
            mock_input.assert_not_called()
        self.assertIn("--yes", str(ctx.exception))
        self.assertIn("--only", str(ctx.exception))

    def test_interactive_yes_confirms_all(self):
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="y"):
            confirmed = self._confirm_targets(self.targets, yes=False, only=None)
        self.assertEqual(confirmed, self.targets)

    def test_interactive_enter_defaults_to_yes(self):
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value=""):
            confirmed = self._confirm_targets(self.targets, yes=False, only=None)
        self.assertEqual(confirmed, self.targets)

    def test_interactive_no_declines_everything_as_a_clean_no_op(self):
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="n"):
            confirmed = self._confirm_targets(self.targets, yes=False, only=None)
        self.assertEqual(confirmed, [])

    def test_interactive_select_excludes_named_indices(self):
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", side_effect=["s", "1"]):
            confirmed = self._confirm_targets(self.targets, yes=False, only=None)
        self.assertEqual(confirmed, [self.targets[1]])


class TestListInventory(unittest.TestCase):
    """docs/ARCHITECTURE.md sec17.5 (STORY-1404): a read-only view over
    ScanCache.all_entries(), grouped by scanner -- no new store."""

    def test_list_shows_onboarded_targets_grouped_by_scanner(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")
            resource = Resource(kind="file", identity=str(target), scanner_name="secrets")
            onboard_targets([resource], mode="allow", cache_path=tmp_path / "cache.json", policy_path=tmp_path / "policy.yaml")

            out = io.StringIO()
            with redirect_stdout(out):
                exit_code = main(["--list", "--cache-path", str(tmp_path / "cache.json")])
            self.assertEqual(exit_code, 0)
            self.assertIn(str(target), out.getvalue())
            self.assertIn("secrets", out.getvalue())

    def test_list_filters_by_scanner(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            file_target = tmp_path / "clean.md"
            file_target.write_text("ordinary docs")
            resources = [
                Resource(kind="file", identity=str(file_target), scanner_name="secrets"),
                Resource(kind="url", identity="https://internal.example.com", scanner_name="reputation"),
            ]
            onboard_targets(resources, mode="allow", cache_path=tmp_path / "cache.json", policy_path=tmp_path / "policy.yaml")

            out = io.StringIO()
            with redirect_stdout(out):
                main(["--list", "--scanner", "reputation", "--cache-path", str(tmp_path / "cache.json")])
            text = out.getvalue()
            self.assertIn("internal.example.com", text)
            self.assertNotIn(str(file_target), text)

    def test_list_on_an_empty_cache_is_a_clean_no_op(self):
        with TemporaryDirectory() as tmp:
            out = io.StringIO()
            with redirect_stdout(out):
                exit_code = main(["--list", "--cache-path", str(Path(tmp) / "cache.json")])
            self.assertEqual(exit_code, 0)


class TestMainNewCliSurface(unittest.TestCase):
    """docs/ARCHITECTURE.md sec17.1-17.4: --target/--tool/--pattern are gone;
    --call/--yes/--only plus the tool-call-JSON input contract replace them."""

    def test_target_flag_no_longer_exists(self):
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit):
            with patch("sys.stderr", out):
                main(["--target", "https://example.com", "--mode", "allow"])

    def test_full_flow_via_call_file_and_yes(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")
            call_path = tmp_path / "call.json"
            call_path.write_text(f'{{"tool_name": "Read", "tool_input": {{"file_path": "{target}"}}}}')

            exit_code = main(
                [
                    "--call",
                    str(call_path),
                    "--yes",
                    "--mode",
                    "allow",
                    "--cache-path",
                    str(tmp_path / "cache.json"),
                    "--policy-path",
                    str(tmp_path / "policy.yaml"),
                ]
            )
            self.assertEqual(exit_code, 0)
            config = PolicyConfig.from_yaml(tmp_path / "policy.yaml")
            self.assertEqual(len(config.rules), 1)

    def test_missing_axis_fails_before_the_confirmation_prompt_not_after(self):
        # Morpheus's Phase 2 review (Sprint 8/E14): caught live -- a user
        # who answers the interactive prompt must never then be told they
        # forgot --sensitivity/--mode. input() must not be called at all.
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")
            call_path = tmp_path / "call.json"
            call_path.write_text(f'{{"tool_name": "Read", "tool_input": {{"file_path": "{target}"}}}}')

            with patch("sys.stdin.isatty", return_value=True), patch("builtins.input") as mock_input:
                exit_code = main(
                    [
                        "--call",
                        str(call_path),
                        "--cache-path",
                        str(tmp_path / "cache.json"),
                        "--policy-path",
                        str(tmp_path / "policy.yaml"),
                    ]
                )
                mock_input.assert_not_called()
            self.assertEqual(exit_code, 1)

    def test_no_targets_identified_is_a_clean_no_op(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            call_path = tmp_path / "call.json"
            call_path.write_text('{"tool_name": "Bash", "tool_input": {"command": "echo hello world"}}')
            exit_code = main(["--call", str(call_path), "--yes", "--mode", "allow"])
            self.assertEqual(exit_code, 0)


class TestCustomScannerCLI(unittest.TestCase):
    """docs/ARCHITECTURE.md sec18.1 (STORY-1501), Trin's Phase 1 UAT: not
    just that load_scanners()/PolicyConfig can see a config-declared
    scanner at the library level (Neo's own tests) -- the real `scg onboard`
    CLI entry point (`main()`) has to identify and onboard through it too,
    since that's the actual STORY-1501 AC ("traverse the registry"), not an
    implementation detail."""

    def _write_policy_with_dummy_scanner(self, tmp_path: Path) -> Path:
        policy_path = tmp_path / "scalene_policy.yaml"
        policy_path.write_text(
            "scanners:\n"
            "  extra:\n"
            "    - name: dummy\n"
            '      import: "fixtures_custom_scanner:DummyScanner"\n'
        )
        return policy_path

    def test_main_identifies_and_onboards_through_a_config_declared_scanner(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            policy_path = self._write_policy_with_dummy_scanner(tmp_path)
            call_path = tmp_path / "call.json"
            call_path.write_text('{"tool_name": "SomeTool", "tool_input": {"dummy_field": "widget-1"}}')

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--call",
                        str(call_path),
                        "--yes",
                        "--mode",
                        "allow",
                        "--policy-path",
                        str(policy_path),
                        "--cache-path",
                        str(tmp_path / "cache.json"),
                    ]
                )
            self.assertEqual(exit_code, 0)
            self.assertIn("1 onboarded, 0 blocked", stdout.getvalue())
            self.assertIn("dummy:widget-1", stdout.getvalue())

    def test_main_list_shows_a_config_declared_scanner_after_onboarding(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            policy_path = self._write_policy_with_dummy_scanner(tmp_path)
            call_path = tmp_path / "call.json"
            call_path.write_text('{"tool_name": "SomeTool", "tool_input": {"dummy_field": "widget-2"}}')
            cache_path = tmp_path / "cache.json"

            with redirect_stdout(io.StringIO()):
                main(
                    [
                        "--call",
                        str(call_path),
                        "--yes",
                        "--mode",
                        "allow",
                        "--policy-path",
                        str(policy_path),
                        "--cache-path",
                        str(cache_path),
                    ]
                )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(["--list", "--cache-path", str(cache_path)])
            self.assertEqual(exit_code, 0)
            self.assertIn("dummy:", stdout.getvalue())
            self.assertIn("widget-2", stdout.getvalue())

    def test_a_typo_scanner_name_via_cli_still_fails_loud_against_the_full_registry(self):
        # Adversarial: --scanner must be validated against the *loaded*
        # registry (builtins + config-declared), not just the builtins,
        # and a genuine typo against that full set must still be rejected.
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            policy_path = self._write_policy_with_dummy_scanner(tmp_path)
            call_path = tmp_path / "call.json"
            call_path.write_text('{"tool_name": "SomeTool", "tool_input": {"dummy_field": "widget-3"}}')

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--call",
                        str(call_path),
                        "--yes",
                        "--mode",
                        "allow",
                        "--scanner",
                        "dummmy",
                        "--policy-path",
                        str(policy_path),
                        "--cache-path",
                        str(tmp_path / "cache.json"),
                    ]
                )
            self.assertEqual(exit_code, 1)
            self.assertIn("0 onboarded, 1 blocked", stdout.getvalue())


class TestE14EndToEndUserJourney(unittest.TestCase):
    """Sprint 8 (E14) full user story, encoded as a real, repeatable test
    with assertions -- not an ad-hoc bash transcript re-verified by eye each
    time. Covers the whole loop docs/GETTING_STARTED.md/USER_GUIDE.md
    describe: a session gets tainted, a mixed multi-target tool call is
    identified, --only selects one target to onboard, the retry is allowed,
    and --list shows what was onboarded -- via the real hook_adapter and
    the real onboard CLI, not narrated by hand."""

    def test_mixed_batch_only_one_confirmed_then_allowed_then_listed(self):
        from scalene.hook_adapter import pre_tool_use
        from scalene.policy_config import PolicyConfig

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_dir = tmp_path / "state"
            audit_log = tmp_path / "audit.log"
            cache_path = tmp_path / "cache.json"
            policy_path = tmp_path / "policy.yaml"
            config_file = tmp_path / "app.yaml"
            config_file.write_text("server: prod")

            # 1. A clean session reads a file -- allowed, but now tainted.
            first = pre_tool_use(
                {"session_id": "e2e", "tool_name": "Read", "tool_input": {"file_path": "notes.txt"}},
                PolicyConfig(),
                state_dir=state_dir,
                audit_log_path=audit_log,
                cache_path=cache_path,
            )
            self.assertEqual(first["hookSpecificOutput"]["permissionDecision"], "allow")

            # 2. A tainted session hits an unrecognized destination -- blocked.
            second = pre_tool_use(
                {
                    "session_id": "e2e",
                    "tool_name": "WebFetch",
                    "tool_input": {"url": "https://partner.example.com/api", "prompt": "x"},
                },
                PolicyConfig(),
                state_dir=state_dir,
                audit_log_path=audit_log,
                cache_path=cache_path,
            )
            self.assertEqual(second["hookSpecificOutput"]["permissionDecision"], "deny")

            # 3. A mixed tool call (file + URL) identifies both targets;
            # --only equivalent (explicit target list) onboards just the URL.
            call_tool_input = {
                "command": f"cat {config_file} && curl https://partner.example.com/api",
            }
            targets = identify_targets("Bash", call_tool_input)
            self.assertEqual({t.kind for t in targets}, {"file", "url"})
            url_target = next(t for t in targets if t.kind == "url")

            results = onboard_targets(
                [url_target],
                mode="allow",
                sensitivity="public",
                description="trusted partner",
                cache_path=cache_path,
                policy_path=policy_path,
            )
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0]["ok"])
            self.assertEqual(results[0]["reputation"], 1.0)

            # 4. Retrying the exact same blocked call is now allowed.
            allow_config = PolicyConfig.from_yaml(policy_path)
            third = pre_tool_use(
                {
                    "session_id": "e2e",
                    "tool_name": "WebFetch",
                    "tool_input": {"url": "https://partner.example.com/api", "prompt": "x"},
                },
                allow_config,
                state_dir=state_dir,
                audit_log_path=audit_log,
                cache_path=cache_path,
            )
            self.assertEqual(third["hookSpecificOutput"]["permissionDecision"], "allow")

            # 5. --list shows the onboarded URL, not the never-onboarded file.
            out = io.StringIO()
            with redirect_stdout(out):
                exit_code = main(["--list", "--cache-path", str(cache_path)])
            self.assertEqual(exit_code, 0)
            listing = out.getvalue()
            self.assertIn("https://partner.example.com/api", listing)
            self.assertNotIn(str(config_file), listing)


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

    def test_onboarded_rule_is_inserted_before_the_project_folder_default_not_after(self):
        # docs/ARCHITECTURE.md sec18.4: the auto-created default's pattern
        # is broad by design -- if a real onboarded rule got appended AFTER
        # it, the default would always match first and the new, more
        # specific decision would be silently unreachable forever.
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            policy_path = tmp_path / "scalene_policy.yaml"
            write_default_project_policy(policy_path, tmp_path)
            target = tmp_path / "secret_config.py"
            target.write_text("not actually secret, just an example")

            onboard(
                f"file://{target}", mode="block", sensitivity="restricted", cache_path=tmp_path / "cache.json", policy_path=policy_path
            )

            config = PolicyConfig.from_yaml(policy_path)
            self.assertEqual(len(config.rules), 2)
            # The newly onboarded (specific, block) rule must come first --
            # otherwise it would never actually take effect.
            self.assertEqual(config.rules[0].mode, "block")
            self.assertIn("project folder default", config.rules[1].description)

    def test_multiple_onboards_after_the_default_all_stay_ahead_of_it_in_order(self):
        # Trin's UAT (2026-07-21): the fix must hold for more than one
        # onboard call, not just the single-call case -- each newly
        # onboarded rule should insert immediately ahead of the (still
        # last) default, preserving onboard order among the real rules.
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            policy_path = tmp_path / "scalene_policy.yaml"
            write_default_project_policy(policy_path, tmp_path)
            first = tmp_path / "first.py"
            second = tmp_path / "second.py"
            first.write_text("a")
            second.write_text("b")

            onboard(f"file://{first}", mode="block", cache_path=tmp_path / "cache.json", policy_path=policy_path)
            onboard(f"file://{second}", mode="block", cache_path=tmp_path / "cache.json", policy_path=policy_path)

            config = PolicyConfig.from_yaml(policy_path)
            self.assertEqual(len(config.rules), 3)
            self.assertRegex(str(first), config.rules[0].pattern)
            self.assertRegex(str(second), config.rules[1].pattern)
            self.assertIn("project folder default", config.rules[2].description)

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
