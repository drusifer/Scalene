"""Tests for the Scanner protocol + built-in scanners (STORY-1001, STORY-1002).

Sprint 4 (E10) Phase 1: docs/ARCHITECTURE.md sec13.2. FileScanner/URLScanner
wrap today's secrets_scan.py/LocalHeuristicChecker unchanged (via the existing
subprocess_isolation.run_scanner boundary, STORY-601) so scan() results stay
at parity with pre-Sprint-4 behavior -- only identify()'s resource-detection
logic is new.
"""

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scalene.scanner import (
    SCANNERS,
    FileScanner,
    Resource,
    ScannerRegistryError,
    ScanResult,
    ScannerMachineryError,
    URLScanner,
    load_scanners,
)

from _env_guards import disable_remote_reputation, restore_remote_reputation

# sec18.3 (STORY-1503): URLScanner.scan() now runs inside an isolated
# subprocess that would otherwise attempt a real URLhaus call. See
# _env_guards.py.
setUpModule = disable_remote_reputation
tearDownModule = restore_remote_reputation


class TestResourceAndScanResult(unittest.TestCase):
    def test_resource_is_frozen(self):
        resource = Resource(kind="file", identity="/tmp/x", scanner_name="secrets")
        with self.assertRaises(Exception):
            resource.kind = "url"

    def test_scan_result_reason_defaults_to_empty(self):
        result = ScanResult(label="public")
        self.assertEqual(result.reason, "")

    def test_scan_result_reputation_defaults_to_none(self):
        # docs/ARCHITECTURE.md sec17.6: additive field, None where a scanner
        # has no graded signal to offer.
        result = ScanResult(label="public")
        self.assertIsNone(result.reputation)


class TestFileScannerIdentify(unittest.TestCase):
    def setUp(self):
        self.scanner = FileScanner()

    def test_name_is_secrets(self):
        self.assertEqual(self.scanner.name, "secrets")

    def test_read_known_field(self):
        resources = self.scanner.identify("Read", {"file_path": "/abs/path/notes.md"})
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].kind, "file")
        self.assertEqual(resources[0].identity, "/abs/path/notes.md")
        self.assertEqual(resources[0].scanner_name, "secrets")

    def test_write_known_field_ignores_content(self):
        resources = self.scanner.identify("Write", {"file_path": "/abs/out.txt", "content": "hello world"})
        self.assertEqual([r.identity for r in resources], ["/abs/out.txt"])

    def test_edit_known_field(self):
        resources = self.scanner.identify(
            "Edit", {"file_path": "/abs/edit.py", "old_string": "a", "new_string": "b"}
        )
        self.assertEqual([r.identity for r in resources], ["/abs/edit.py"])

    def test_relative_known_field_normalized_to_absolute(self):
        resources = self.scanner.identify("Read", {"file_path": "relative/notes.md"})
        self.assertTrue(os.path.isabs(resources[0].identity))

    def test_generic_fallback_finds_path_in_bash_command(self):
        resources = self.scanner.identify("Bash", {"command": "cat /etc/passwd"})
        self.assertTrue(any(r.identity == "/etc/passwd" for r in resources))
        self.assertTrue(all(r.scanner_name == "secrets" and r.kind == "file" for r in resources))

    def test_no_false_positive_on_unrelated_bash_command(self):
        resources = self.scanner.identify("Bash", {"command": "echo hello world"})
        self.assertEqual(resources, [])

    def test_unknown_tool_with_no_path_shaped_args_finds_nothing(self):
        resources = self.scanner.identify("SomeOtherTool", {"foo": "bar"})
        self.assertEqual(resources, [])

    def test_no_duplicate_resources_for_repeated_path(self):
        resources = self.scanner.identify("Bash", {"command": "diff /etc/passwd /etc/passwd"})
        self.assertEqual(len(resources), 1)

    def test_url_in_bash_command_is_not_mistaken_for_a_file_path(self):
        resources = self.scanner.identify("Bash", {"command": "curl https://evil.example.net/x/y?token=abc"})
        self.assertEqual(resources, [])

    def test_webfetch_url_field_is_not_mistaken_for_a_file_path(self):
        resources = self.scanner.identify(
            "WebFetch", {"url": "https://internal.example.com/reports", "prompt": "summarize"}
        )
        self.assertEqual(resources, [])

    def test_file_uri_in_any_tool_args_is_identified_as_a_file(self):
        # 2026-07-22 (direct user request): file:// is a filesystem
        # reference wearing a URI shape -- FileScanner's job, regardless of
        # which tool/field it shows up in.
        resources = self.scanner.identify("Bash", {"command": "cat file:///etc/passwd"})
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].identity, "/etc/passwd")
        self.assertEqual(resources[0].kind, "file")

    def test_file_uri_does_not_also_produce_a_stray_path_fragment(self):
        # The file:// span must be excluded from the generic path fallback,
        # so this doesn't ALSO produce a bogus "//abs/path"-shaped resource
        # on top of the correct file:// extraction.
        resources = self.scanner.identify("Bash", {"command": "cat file:///tmp/secret.txt"})
        self.assertEqual([r.identity for r in resources], ["/tmp/secret.txt"])

    def test_other_protocol_url_is_not_mistaken_for_a_file_path(self):
        # A non-file, non-http(s) scheme (e.g. ftp://, s3://) is still a URL,
        # not a file -- must be excluded from FileScanner the same way
        # https:// already was.
        resources = self.scanner.identify("Bash", {"command": "aws s3 cp s3://my-bucket/data.csv ."})
        self.assertEqual(resources, [])


class TestFileScannerScan(unittest.TestCase):
    def setUp(self):
        self.scanner = FileScanner()

    def test_clean_file_is_public(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "clean.md"
            target.write_text("just some ordinary docs")
            result = self.scanner.scan(Resource(kind="file", identity=str(target), scanner_name="secrets"))
            self.assertIsInstance(result, ScanResult)
            self.assertEqual(result.label, "public")

    def test_file_with_secret_is_sensitive(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "leaky.env"
            # Fake key built via concatenation, not a contiguous literal a
            # secret scanner would flag in this source file.
            fake_key = "AKIA" + "ABCDEFGHIJKLMNOP"
            target.write_text(f"AWS_KEY={fake_key}")
            result = self.scanner.scan(Resource(kind="file", identity=str(target), scanner_name="secrets"))
            self.assertEqual(result.label, "sensitive")
            self.assertTrue(result.reason)

    def test_target_that_cannot_be_read_raises_machinery_error_not_a_finding(self):
        # STORY-1004: a scan that couldn't run (target unreadable) is a
        # machinery failure, distinct from an ordinary "sensitive" finding --
        # this is what makes the fatal-exit path fire (cli.py), not a
        # ScanResult a caller would otherwise treat as a normal decision.
        with self.assertRaises(ScannerMachineryError):
            self.scanner.scan(Resource(kind="file", identity="/no/such/path/here.md", scanner_name="secrets"))

    def test_etc_path_is_sensitive_even_when_clean(self):
        # docs/ARCHITECTURE.md sec18.2 (STORY-1502): /etc/hostname has no
        # real secret content -- the hardcoded floor must still fire.
        result = self.scanner.scan(Resource(kind="file", identity="/etc/hostname", scanner_name="secrets"))
        self.assertEqual(result.label, "sensitive")

    def test_etc_path_reason_is_distinct_from_a_real_secrets_finding(self):
        # Smith's Gate 1 non-blocking note: a developer must be able to
        # tell "hardcoded system path" apart from "an actual secret matched".
        result = self.scanner.scan(Resource(kind="file", identity="/etc/hostname", scanner_name="secrets"))
        self.assertIn("hardcoded restricted", result.reason)

    def test_ssh_dir_path_is_sensitive_even_when_clean(self):
        home_ssh = os.path.expanduser("~/.ssh")
        result = self.scanner.scan(Resource(kind="file", identity=f"{home_ssh}/id_rsa", scanner_name="secrets"))
        self.assertEqual(result.label, "sensitive")

    def test_similarly_named_path_is_not_a_false_positive(self):
        # "/etcetera/..." must not match the "/etc" prefix via a naive
        # str.startswith("/etc").
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "etcetera" / "clean.md"
            target.parent.mkdir()
            target.write_text("just some ordinary docs, not under /etc")
            result = self.scanner.scan(Resource(kind="file", identity=str(target), scanner_name="secrets"))
            self.assertEqual(result.label, "public")

    def test_exact_prefix_itself_is_restricted_not_just_subpaths(self):
        # Trin's UAT (Phase 2): "/etc" itself (no trailing component) must
        # match too, not only paths strictly under it.
        result = self.scanner.scan(Resource(kind="file", identity="/etc", scanner_name="secrets"))
        self.assertEqual(result.label, "sensitive")

    def test_hardcoded_restricted_short_circuit_never_touches_the_secrets_scan_subprocess(self):
        # A path under /etc doesn't need to exist -- the short-circuit
        # fires before run_scanner() would ever try to read it.
        result = self.scanner.scan(
            Resource(kind="file", identity="/etc/this-file-does-not-actually-exist", scanner_name="secrets")
        )
        self.assertEqual(result.label, "sensitive")

    def test_directory_target_scans_every_file_inside_and_is_public_when_all_clean(self):
        # Bug fix: Verify on a directory target in scg monitor previously
        # raised ScannerMachineryError (open() on a dir), silently leaving
        # the row unverified. A directory now scans every file underneath.
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "a.md").write_text("just some ordinary docs")
            nested = Path(tmp) / "nested"
            nested.mkdir()
            (nested / "b.md").write_text("more ordinary docs")
            result = self.scanner.scan(Resource(kind="file", identity=tmp, scanner_name="secrets"))
            self.assertEqual(result.label, "public")

    def test_directory_target_with_a_secret_in_a_nested_file_is_sensitive(self):
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "clean.md").write_text("just some ordinary docs")
            nested = Path(tmp) / "nested"
            nested.mkdir()
            fake_key = "AKIA" + "ABCDEFGHIJKLMNOP"
            (nested / "leaky.env").write_text(f"AWS_KEY={fake_key}")
            result = self.scanner.scan(Resource(kind="file", identity=tmp, scanner_name="secrets"))
            self.assertEqual(result.label, "sensitive")
            self.assertIn("leaky.env", result.reason)

    def test_empty_directory_target_is_public(self):
        with TemporaryDirectory() as tmp:
            result = self.scanner.scan(Resource(kind="file", identity=tmp, scanner_name="secrets"))
            self.assertEqual(result.label, "public")

    def test_reputation_stays_none_deliberately(self):
        # sec17.6: detect-secrets' open-ended finding list has no fixed-
        # heuristic-count basis for a fraction the way reputation.py's 3
        # checks do -- inventing one would be false precision.
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "clean.md"
            target.write_text("just some ordinary docs")
            result = self.scanner.scan(Resource(kind="file", identity=str(target), scanner_name="secrets"))
            self.assertIsNone(result.reputation)


class TestURLScannerIdentify(unittest.TestCase):
    def setUp(self):
        self.scanner = URLScanner()

    def test_name_is_reputation(self):
        self.assertEqual(self.scanner.name, "reputation")

    def test_webfetch_known_field_identity_is_full_url_query_stripped(self):
        # STORY-1101 (docs/ARCHITECTURE.md sec14.2): identity is the full
        # URL (scheme+host+path), not the bare host -- scanning one path
        # must not vouch for every other path under the same host. Query
        # string is dropped to keep cache keys bounded.
        resources = self.scanner.identify(
            "WebFetch", {"url": "https://internal.example.com/path?x=1", "prompt": "summarize this"}
        )
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].kind, "url")
        self.assertEqual(resources[0].identity, "https://internal.example.com/path")
        self.assertEqual(resources[0].scanner_name, "reputation")

    def test_generic_fallback_finds_full_url_in_bash_command(self):
        resources = self.scanner.identify("Bash", {"command": "curl https://evil.example.net/x"})
        self.assertTrue(any(r.identity == "https://evil.example.net/x" for r in resources))

    def test_no_false_positive_on_unrelated_bash_command(self):
        resources = self.scanner.identify("Bash", {"command": "echo hello world"})
        self.assertEqual(resources, [])

    def test_no_duplicate_resources_for_repeated_identical_url(self):
        resources = self.scanner.identify("Bash", {"command": "curl https://x.example.com/a https://x.example.com/a"})
        self.assertEqual(len(resources), 1)

    def test_distinct_paths_under_same_host_are_separate_resources(self):
        # The actual STORY-1101 defect fix, at the identify() level: two
        # different paths under one host must not collapse into a single
        # resource identity the way host-only identity used to.
        resources = self.scanner.identify("Bash", {"command": "curl https://x.example.com/a https://x.example.com/b"})
        identities = {r.identity for r in resources}
        self.assertEqual(identities, {"https://x.example.com/a", "https://x.example.com/b"})

    def test_non_http_protocol_is_still_recognized_as_a_url(self):
        # 2026-07-22 (direct user request): "any URL with a protocol", not
        # just http(s) -- ftp/ws/s3/etc. are all real destinations a call
        # could exfiltrate to.
        resources = self.scanner.identify("Bash", {"command": "curl ftp://files.example.com/upload"})
        self.assertEqual([r.identity for r in resources], ["ftp://files.example.com/upload"])

    def test_file_uri_is_excluded_from_url_scanning(self):
        # The one explicit exception -- file:// belongs to FileScanner
        # (see TestFileScannerIdentify.test_file_uri_in_any_tool_args...).
        resources = self.scanner.identify("Bash", {"command": "cat file:///etc/passwd"})
        self.assertEqual(resources, [])

    def test_file_uri_alongside_a_real_url_only_identifies_the_real_url(self):
        resources = self.scanner.identify(
            "Bash", {"command": "cat file:///tmp/local.txt https://example.com/remote.txt"}
        )
        self.assertEqual([r.identity for r in resources], ["https://example.com/remote.txt"])


class TestURLScannerScan(unittest.TestCase):
    def setUp(self):
        self.scanner = URLScanner()

    def test_ordinary_domain_is_trusted(self):
        result = self.scanner.scan(Resource(kind="url", identity="internal.example.com", scanner_name="reputation"))
        self.assertIsInstance(result, ScanResult)
        self.assertEqual(result.label, "trusted")

    def test_ordinary_domain_has_a_perfect_reputation_score(self):
        # sec17.6: the score travels the real isolated-subprocess boundary
        # (scan_worker.py), not just the in-process LocalHeuristicChecker.
        result = self.scanner.scan(Resource(kind="url", identity="internal.example.com", scanner_name="reputation"))
        self.assertEqual(result.reputation, 1.0)

    def test_ip_literal_is_untrusted(self):
        result = self.scanner.scan(Resource(kind="url", identity="203.0.113.42", scanner_name="reputation"))
        self.assertEqual(result.label, "untrusted")
        self.assertTrue(result.reason)

    def test_ip_literal_reputation_score_reflects_the_single_triggered_heuristic(self):
        result = self.scanner.scan(Resource(kind="url", identity="203.0.113.42", scanner_name="reputation"))
        self.assertAlmostEqual(result.reputation, 2 / 3)

    def test_scan_extracts_host_from_full_url_identity(self):
        # STORY-1101: identity is now a full URL (for cache-key granularity),
        # but the underlying reputation heuristic still examines the host --
        # a URL's path doesn't change whether its host is reputable.
        result = self.scanner.scan(
            Resource(kind="url", identity="https://internal.example.com/some/path", scanner_name="reputation")
        )
        self.assertEqual(result.label, "trusted")

    def test_scan_ip_literal_full_url_is_untrusted(self):
        result = self.scanner.scan(
            Resource(kind="url", identity="https://203.0.113.42/path", scanner_name="reputation")
        )
        self.assertEqual(result.label, "untrusted")


class TestScannerBaseMatch(unittest.TestCase):
    """Scanner.match() (2026-07-30): pattern matching moved from one
    generic regex check in resource_verifier.py to a scanner-owned method,
    so each scanner's own identity shape stays in sync with how its
    patterns are interpreted. The base class default is plain regex --
    unchanged behavior from before this method existed."""

    def test_default_match_is_plain_regex(self):
        from scalene.policy_config import PolicyRule
        from scalene.scanner import Scanner

        rule = PolicyRule(tool=".*", pattern=r"https://internal\.example\.com/.*", sensitivity="public", mode="mask")
        resource = Resource(kind="url", identity="https://internal.example.com/x", scanner_name="reputation")
        self.assertTrue(Scanner().match(rule, resource))

    def test_default_match_fails_safe_on_invalid_regex_not_a_crash(self):
        # PolicyRule no longer validates `pattern` as regex at construction
        # time (its syntax is scanner-owned) -- a pattern meant for a
        # different scanner's syntax (e.g. a gitignore "**/" prefix) must
        # not crash the hot-path hook call when handed to the plain-regex
        # default matcher.
        from scalene.policy_config import PolicyRule
        from scalene.scanner import Scanner

        rule = PolicyRule(tool=".*", pattern="**/*.env", sensitivity="public", mode="mask")
        resource = Resource(kind="url", identity="https://example.com/x", scanner_name="reputation")
        self.assertFalse(Scanner().match(rule, resource))

    def test_url_scanner_has_no_match_override_still_plain_regex(self):
        from scalene.policy_config import PolicyRule

        rule = PolicyRule(tool=".*", pattern=r"https://internal\.example\.com/.*", sensitivity="public", mode="mask")
        resource = Resource(kind="url", identity="https://internal.example.com/x", scanner_name="reputation")
        self.assertTrue(URLScanner().match(rule, resource))


class TestFileScannerMatch(unittest.TestCase):
    """FileScanner.match() (user request: familiar, gitignore-style wildcard
    matching so a rule can cover "the whole project folder recursively")."""

    def setUp(self):
        self.scanner = FileScanner()

    def _rule(self, pattern: str):
        from scalene.policy_config import PolicyRule

        return PolicyRule(tool=".*", pattern=pattern, sensitivity="public", mode="allow")

    def test_exact_literal_pattern_matches_only_that_path(self):
        rule = self._rule("/tmp/project/clean.md")
        self.assertTrue(self.scanner.match(rule, Resource(kind="file", identity="/tmp/project/clean.md", scanner_name="secrets")))
        self.assertFalse(self.scanner.match(rule, Resource(kind="file", identity="/tmp/project/other.md", scanner_name="secrets")))

    def test_single_star_matches_recursively_across_directories(self):
        # Unlike shell globbing, gitignore's "*" has no special-cased
        # directory boundary either at this depth -- "/project/*" matches
        # arbitrarily nested files under it, which is the actual behavior
        # the user asked for ("match the whole project folder recursively").
        rule = self._rule("/project/*")
        nested = Resource(kind="file", identity="/project/a/b/c.py", scanner_name="secrets")
        self.assertTrue(self.scanner.match(rule, nested))

    def test_double_star_suffix_matches_root_and_everything_nested(self):
        rule = self._rule("/project\n/project/**")
        self.assertTrue(self.scanner.match(rule, Resource(kind="file", identity="/project", scanner_name="secrets")))
        self.assertTrue(
            self.scanner.match(rule, Resource(kind="file", identity="/project/a/b/c.py", scanner_name="secrets"))
        )

    def test_double_star_suffix_does_not_match_a_similarly_named_sibling(self):
        # Same boundary-safety class as scanner.py's own "/etc" vs.
        # false-positive "/etcetera" handling.
        rule = self._rule("/project\n/project/**")
        sibling = Resource(kind="file", identity="/project-evil/x.py", scanner_name="secrets")
        self.assertFalse(self.scanner.match(rule, sibling))

    def test_negation_pattern_excludes_a_previously_matched_subpath(self):
        # Real gitignore semantics: a later "!" line un-ignores something an
        # earlier line matched -- free, since this is genuine gitignore
        # syntax (pathspec.GitIgnoreSpec), not a bespoke reimplementation.
        rule = self._rule("/project/**\n!/project/public/**")
        self.assertTrue(
            self.scanner.match(rule, Resource(kind="file", identity="/project/secret.env", scanner_name="secrets"))
        )
        self.assertFalse(
            self.scanner.match(rule, Resource(kind="file", identity="/project/public/readme.md", scanner_name="secrets"))
        )


class TestScannerFromConfig(unittest.TestCase):
    """Scanner.from_config() (user request: config-declared scanners should
    be able to receive their own settings from scalene_policy.yaml's
    `scanners.extra[].config`, not just an import path)."""

    def test_default_from_config_ignores_config_and_returns_a_plain_instance(self):
        from scalene.scanner import Scanner

        instance = Scanner.from_config({"anything": "ignored"})
        self.assertIsInstance(instance, Scanner)

    def test_builtin_scanners_construct_via_from_config_unchanged(self):
        self.assertIsInstance(FileScanner.from_config({}), FileScanner)
        self.assertIsInstance(URLScanner.from_config({}), URLScanner)

    def test_load_scanners_passes_the_config_subblock_to_a_scanner_that_overrides_from_config(self):
        scanners = load_scanners(
            {
                "extra": [
                    {
                        "name": "configurable",
                        "import": "fixtures_configurable_scanner:ConfigurableScanner",
                        "config": {"endpoint": "https://cmdb.example.internal"},
                    }
                ]
            }
        )
        self.assertEqual(scanners["configurable"].endpoint, "https://cmdb.example.internal")

    def test_load_scanners_still_works_for_a_scanner_with_no_from_config_override(self):
        # DummyScanner doesn't inherit Scanner at all (no from_config) --
        # load_scanners() must fall back to bare cls(), same as before this
        # feature existed, not raise.
        scanners = load_scanners({"extra": [{"name": "dummy", "import": "fixtures_custom_scanner:DummyScanner"}]})
        self.assertEqual(scanners["dummy"].name, "dummy")


class TestScannerRegistry(unittest.TestCase):
    def test_registry_has_both_built_in_scanners(self):
        self.assertIn("secrets", SCANNERS)
        self.assertIn("reputation", SCANNERS)
        self.assertIsInstance(SCANNERS["secrets"], FileScanner)
        self.assertIsInstance(SCANNERS["reputation"], URLScanner)


class TestLoadScanners(unittest.TestCase):
    """docs/ARCHITECTURE.md sec18.1 (STORY-1501): the config-driven registry."""

    def test_empty_config_yields_exactly_the_builtins(self):
        scanners = load_scanners({})
        self.assertEqual(set(scanners), {"secrets", "reputation"})
        self.assertIsInstance(scanners["secrets"], FileScanner)
        self.assertIsInstance(scanners["reputation"], URLScanner)

    def test_extra_scanner_is_imported_and_registered(self):
        scanners = load_scanners(
            {"extra": [{"name": "dummy", "import": "fixtures_custom_scanner:DummyScanner"}]}
        )
        self.assertIn("dummy", scanners)
        self.assertEqual(scanners["dummy"].name, "dummy")
        # Builtins are untouched by adding an extra scanner.
        self.assertIn("secrets", scanners)
        self.assertIn("reputation", scanners)

    def test_extra_scanner_actually_dispatches_through_identify_and_scan(self):
        # Not just "it imports" -- it has to behave like a real registry
        # entry for identify()/scan() dispatch, the actual STORY-1501 AC.
        scanners = load_scanners(
            {"extra": [{"name": "dummy", "import": "fixtures_custom_scanner:DummyScanner"}]}
        )
        resources = scanners["dummy"].identify("SomeTool", {"dummy_field": "widget-1"})
        self.assertEqual(len(resources), 1)
        result = scanners["dummy"].scan(resources[0])
        self.assertEqual(result.label, "public")

    def test_name_colliding_with_a_builtin_raises(self):
        with self.assertRaises(ScannerRegistryError):
            load_scanners({"extra": [{"name": "secrets", "import": "fixtures_custom_scanner:DummyScanner"}]})

    def test_unimportable_module_raises_naming_the_offending_path(self):
        with self.assertRaises(ScannerRegistryError) as ctx:
            load_scanners({"extra": [{"name": "dummy", "import": "no.such.module:Whatever"}]})
        self.assertIn("no.such.module:Whatever", str(ctx.exception))

    def test_missing_class_in_a_real_module_raises(self):
        with self.assertRaises(ScannerRegistryError):
            load_scanners({"extra": [{"name": "dummy", "import": "fixtures_custom_scanner:NoSuchClass"}]})

    def test_class_not_satisfying_scanner_protocol_raises(self):
        with self.assertRaises(ScannerRegistryError):
            load_scanners({"extra": [{"name": "dummy", "import": "fixtures_custom_scanner:NotAScanner"}]})

    def test_import_missing_colon_raises_clear_error(self):
        with self.assertRaises(ScannerRegistryError):
            load_scanners({"extra": [{"name": "dummy", "import": "fixtures_custom_scanner.DummyScanner"}]})

    def test_extra_entry_missing_required_field_raises(self):
        with self.assertRaises(ScannerRegistryError):
            load_scanners({"extra": [{"name": "dummy"}]})

    def test_extra_not_a_list_raises(self):
        with self.assertRaises(ScannerRegistryError):
            load_scanners({"extra": "not-a-list"})


if __name__ == "__main__":
    unittest.main()
