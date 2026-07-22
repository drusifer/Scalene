"""Tests for resource verification (STORY-1002, STORY-1003) -- replaces
PolicyConfig.evaluate()'s PolicyRule/allowlist matching (docs/ARCHITECTURE.md
sec13.1, full replacement). Returns the same MatchResult shape
pre_tool_use/post_tool_use already consume (sec13.1.1), so this module is
the only thing that changes -- MaskingEngine.decide() is untouched.
"""

import os
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scalene.policy_config import MatchResult, PolicyConfig, PolicyRule, write_default_project_policy
from scalene.resource_verifier import decide_access, evaluate
from scalene.scan_cache import ScanCache
from scalene.scanner import FileScanner, Resource, ScanResult
from scalene.taint_state import TaintState

from _env_guards import disable_remote_reputation, restore_remote_reputation

# sec18.3 (STORY-1503): several tests below use never-seen URLs to exercise
# the first-sighting/fail-safe path -- a real cache miss spawns a real
# (fire-and-forget) background subprocess that would now attempt a live
# URLhaus call. See _env_guards.py.
setUpModule = disable_remote_reputation
tearDownModule = restore_remote_reputation


class TestNoResourcesIdentified(unittest.TestCase):
    """A call with nothing file- or URL-shaped in its args -- must fall back
    to the config defaults exactly like today's PolicyConfig.evaluate() did
    when no allowlist rule matched."""

    def test_falls_back_to_defaults_when_nothing_identified(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            config = PolicyConfig(sensitive_by_default=True, untrusted_by_default=True)
            result = evaluate("Bash", {"command": "echo hello"}, config, cache)
            self.assertIsInstance(result, MatchResult)
            self.assertTrue(result.is_sensitive)
            self.assertFalse(result.is_trusted)
            self.assertFalse(result.fail_safe_triggered)

    def test_respects_non_default_config_when_nothing_identified(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            config = PolicyConfig(sensitive_by_default=False, untrusted_by_default=False)
            result = evaluate("Bash", {"command": "echo hello"}, config, cache)
            self.assertFalse(result.is_sensitive)
            self.assertTrue(result.is_trusted)


class TestCachedResourceResolution(unittest.TestCase):
    def test_known_public_file_is_not_sensitive(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "clean.md"
            target.write_text("ordinary text")
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            cache.put(Resource(kind="file", identity=str(target), scanner_name="secrets"), ScanResult(label="public"))

            config = PolicyConfig(sensitive_by_default=True, untrusted_by_default=True)
            result = evaluate("Read", {"file_path": str(target)}, config, cache)
            self.assertFalse(result.is_sensitive)
            self.assertFalse(result.fail_safe_triggered)

    def test_known_sensitive_file_is_sensitive(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "secret.env"
            target.write_text("AWS_KEY=fake")
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            cache.put(
                Resource(kind="file", identity=str(target), scanner_name="secrets"),
                ScanResult(label="sensitive", reason="Possible AWS Access Key"),
            )

            config = PolicyConfig(sensitive_by_default=False)
            result = evaluate("Read", {"file_path": str(target)}, config, cache)
            self.assertTrue(result.is_sensitive)

    def test_known_trusted_url_is_trusted(self):
        # STORY-1101 (sec14.2): cache key is the full URL, not the bare
        # host -- must match exactly what URLScanner.identify() extracts
        # from this WebFetch call.
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            cache.put(
                Resource(kind="url", identity="https://internal.example.com/api", scanner_name="reputation"),
                ScanResult(label="trusted"),
            )

            config = PolicyConfig(untrusted_by_default=True)
            result = evaluate("WebFetch", {"url": "https://internal.example.com/api"}, config, cache)
            self.assertTrue(result.is_trusted)
            self.assertFalse(result.fail_safe_triggered)

    def test_known_untrusted_url_is_not_trusted(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            cache.put(
                Resource(kind="url", identity="https://203.0.113.42/api", scanner_name="reputation"),
                ScanResult(label="untrusted", reason="IP-literal targets are untrusted by default"),
            )

            config = PolicyConfig(untrusted_by_default=False)
            result = evaluate("WebFetch", {"url": "https://203.0.113.42/api"}, config, cache)
            self.assertFalse(result.is_trusted)

    def test_verified_path_does_not_vouch_for_sibling_path_under_same_host(self):
        # The actual STORY-1101 defect fix, at the evaluate() level: onboard/
        # verify one path under a host, confirm a different, unverified path
        # under that same host is NOT treated as trusted (pre-sec14.2, host-
        # level identity would have silently trusted it).
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            cache.put(
                Resource(kind="url", identity="https://internal.example.com/known-good", scanner_name="reputation"),
                ScanResult(label="trusted"),
            )

            config = PolicyConfig(untrusted_by_default=True)
            result = evaluate("WebFetch", {"url": "https://internal.example.com/never-verified"}, config, cache)
            self.assertFalse(result.is_trusted)
            self.assertTrue(result.fail_safe_triggered)


class TestFailSafeTriggered(unittest.TestCase):
    """sec13.1.1: fail_safe_triggered now means "at least one identified
    resource had no cache entry and fell back to defaults" -- not the old
    JSONPath-evaluation-failure meaning."""

    def test_never_before_seen_file_triggers_fail_safe_and_uses_default(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "never_seen.md"
            target.write_text("text")
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            config = PolicyConfig(sensitive_by_default=True)

            result = evaluate("Read", {"file_path": str(target)}, config, cache)
            self.assertTrue(result.is_sensitive)  # sensitive_by_default applied
            self.assertTrue(result.fail_safe_triggered)

    def test_never_before_seen_url_triggers_fail_safe_and_uses_default(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            config = PolicyConfig(untrusted_by_default=True)

            result = evaluate("WebFetch", {"url": "https://never-seen.example.com/x"}, config, cache)
            self.assertFalse(result.is_trusted)  # not untrusted_by_default applied
            self.assertTrue(result.fail_safe_triggered)

    def test_fail_safe_not_triggered_when_everything_identified_is_cached(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "clean.md"
            target.write_text("text")
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            cache.put(Resource(kind="file", identity=str(target), scanner_name="secrets"), ScanResult(label="public"))
            cache.put(
                Resource(kind="url", identity="https://internal.example.com/x", scanner_name="reputation"),
                ScanResult(label="trusted"),
            )
            config = PolicyConfig()

            result = evaluate(
                "Bash",
                {"command": f"cat {target} && curl https://internal.example.com/x"},
                config,
                cache,
            )
            self.assertFalse(result.fail_safe_triggered)

    def test_first_sighting_spawns_exactly_one_background_scan_per_resource(self):
        # Confirms this module actually calls refresh_if_needed (side effect:
        # a background scan gets triggered), not just is_fresh-style checks.
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "never_seen.md"
            target.write_text("text")
            cache_path = Path(tmp) / "scan_cache.json"
            cache = ScanCache(cache_path)
            config = PolicyConfig()

            from unittest.mock import patch

            with patch("scalene.scan_cache.subprocess.Popen") as mock_popen:
                evaluate("Read", {"file_path": str(target)}, config, cache)

            mock_popen.assert_called_once()


class TestMultipleResourcesAnySemantics(unittest.TestCase):
    """Mirrors the old PolicyRule model's ANY-match semantics for parity
    (sec13.1.1: same MatchResult shape, same downstream handling) -- a call
    touching multiple resources of one kind is sensitive/untrusted unless
    ALL of them individually resolve to a clean/trusted label."""

    def test_one_sensitive_file_among_several_makes_the_call_sensitive(self):
        with TemporaryDirectory() as tmp:
            clean = Path(tmp) / "clean.md"
            clean.write_text("text")
            secret = Path(tmp) / "secret.env"
            secret.write_text("AWS_KEY=fake")
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            cache.put(Resource(kind="file", identity=str(clean), scanner_name="secrets"), ScanResult(label="public"))
            cache.put(
                Resource(kind="file", identity=str(secret), scanner_name="secrets"),
                ScanResult(label="sensitive", reason="AWS key"),
            )
            config = PolicyConfig(sensitive_by_default=False)

            result = evaluate("Bash", {"command": f"cat {clean} {secret}"}, config, cache)
            self.assertTrue(result.is_sensitive)

    def test_all_public_files_makes_the_call_not_sensitive(self):
        with TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.md"
            a.write_text("text")
            b = Path(tmp) / "b.md"
            b.write_text("text")
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            cache.put(Resource(kind="file", identity=str(a), scanner_name="secrets"), ScanResult(label="public"))
            cache.put(Resource(kind="file", identity=str(b), scanner_name="secrets"), ScanResult(label="public"))
            config = PolicyConfig(sensitive_by_default=True)

            result = evaluate("Bash", {"command": f"cat {a} {b}"}, config, cache)
            self.assertFalse(result.is_sensitive)


class TestRuleResolvedSensitivityAndMode(unittest.TestCase):
    """docs/ARCHITECTURE.md sec14.1/14.4 (STORY-1102, STORY-1103): a rule
    decides sensitivity/mode for an already-identified Resource; the
    implicit default rule (sensitivity=public, mode=config.mode) applies
    when nothing more specific matches."""

    def test_no_rules_and_no_resources_uses_implicit_default(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            config = PolicyConfig(mode="block")
            result = evaluate("Bash", {"command": "echo hello"}, config, cache)
            self.assertEqual(result.sensitivity, "public")
            self.assertEqual(result.mode, "block")

    def test_no_rules_but_resources_identified_uses_implicit_default(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            config = PolicyConfig(mode="mask")
            result = evaluate("WebFetch", {"url": "https://never-seen.example.com/x"}, config, cache)
            self.assertEqual(result.sensitivity, "public")
            self.assertEqual(result.mode, "mask")

    def test_matching_rule_overrides_sensitivity_and_mode(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            config = PolicyConfig(
                mode="mask",
                rules=(
                    PolicyRule(
                        tool=".*",
                        pattern=r"https://internal\.example\.com/.*",
                        sensitivity="internal",
                        mode="block",
                    ),
                ),
            )
            result = evaluate("WebFetch", {"url": "https://internal.example.com/wiki"}, config, cache)
            self.assertEqual(result.sensitivity, "internal")
            self.assertEqual(result.mode, "block")

    def test_non_matching_rule_falls_back_to_default(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            config = PolicyConfig(
                mode="mask",
                rules=(
                    PolicyRule(
                        tool=".*",
                        pattern=r"https://internal\.example\.com/.*",
                        sensitivity="internal",
                        mode="block",
                    ),
                ),
            )
            result = evaluate("WebFetch", {"url": "https://unrelated.example.org/x"}, config, cache)
            self.assertEqual(result.sensitivity, "public")
            self.assertEqual(result.mode, "mask")

    def test_rule_tool_filter_is_respected(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            config = PolicyConfig(
                mode="mask",
                rules=(
                    PolicyRule(tool="Read", pattern=r".*/tests/.*", sensitivity="public", mode="allow"),
                ),
            )
            # Same path pattern, different tool -- rule must not apply to Write.
            target = Path(tmp) / "tests" / "fixture.md"
            result = evaluate("Write", {"file_path": str(target)}, config, cache)
            self.assertEqual(result.mode, "mask")

    def test_rule_scanner_filter_disambiguates(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            config = PolicyConfig(
                mode="mask",
                rules=(
                    PolicyRule(tool=".*", pattern=".*", sensitivity="public", mode="allow", scanner="reputation"),
                ),
            )
            # A file resource matches the pattern too, but scanner="reputation"
            # restricts the rule to URL resources only.
            target = Path(tmp) / "anything.md"
            target.write_text("x")
            result = evaluate("Read", {"file_path": str(target)}, config, cache)
            self.assertEqual(result.mode, "mask")

    def test_most_restrictive_mode_wins_across_multiple_resources(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            config = PolicyConfig(
                mode="mask",
                rules=(
                    PolicyRule(tool=".*", pattern=r"https://safe\.example\.com/.*", sensitivity="public", mode="allow"),
                    PolicyRule(tool=".*", pattern=r"https://risky\.example\.com/.*", sensitivity="restricted", mode="block"),
                ),
            )
            result = evaluate(
                "Bash",
                {"command": "curl https://safe.example.com/a https://risky.example.com/b"},
                config,
                cache,
            )
            self.assertEqual(result.mode, "block")
            self.assertEqual(result.sensitivity, "restricted")

    def test_old_format_host_keyed_cache_entry_does_not_leak_trust(self):
        # STORY-1105 (docs/ARCHITECTURE.md sec14.6): a pre-sec14.2 cache
        # entry keyed by bare host (e.g. from before this epic's fix) must
        # never be silently read as valid trust for a URL under that host
        # now that the key scheme is per-URL. No auto-migration by design
        # -- the old-format entry should simply be inert/unmatched.
        import json

        with TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "scan_cache.json"
            cache_path.write_text(
                json.dumps(
                    {
                        "reputation:internal.example.com": {
                            "label": "trusted",
                            "reason": "",
                            "scanned_at": 0.0,
                        }
                    }
                )
            )
            cache = ScanCache(cache_path)
            config = PolicyConfig(untrusted_by_default=True)

            result = evaluate("WebFetch", {"url": "https://internal.example.com/some/path"}, config, cache)
            self.assertFalse(result.is_trusted)
            self.assertTrue(result.fail_safe_triggered)

    def test_first_matching_rule_wins_by_declaration_order(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            config = PolicyConfig(
                mode="mask",
                rules=(
                    PolicyRule(tool=".*", pattern=r"https://internal\.example\.com/.*", sensitivity="internal", mode="mask"),
                    PolicyRule(tool=".*", pattern=".*", sensitivity="restricted", mode="block"),
                ),
            )
            result = evaluate("WebFetch", {"url": "https://internal.example.com/x"}, config, cache)
            # First rule matches -- must win, not the broader second rule.
            self.assertEqual(result.sensitivity, "internal")
            self.assertEqual(result.mode, "mask")


class TestDecideAccess(unittest.TestCase):
    """docs/ARCHITECTURE.md sec15 (direct user design session, 2026-07-17):
    rule-driven access control -- the core call-permission decision,
    replacing sec14.4's content-scanning model for this correction. Masking
    is explicitly out of scope."""

    def test_no_resources_identified_proceeds_and_tags_unchanged(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            config = PolicyConfig()
            taint = TaintState(session_id="s1")
            decision = decide_access("Bash", {"command": "echo hello"}, config, cache, taint)
            self.assertTrue(decision.allowed)
            self.assertTrue(taint.is_clean)

    def test_clean_context_unmatched_resource_proceeds_then_taints_trust_low(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            config = PolicyConfig()
            taint = TaintState(session_id="s1")
            decision = decide_access(
                "WebFetch", {"url": "https://never-seen.example.com/x"}, config, cache, taint
            )
            self.assertTrue(decision.allowed)
            self.assertEqual(taint.trust, "low")
            self.assertEqual(taint.sensitivity, "public")

    def test_contaminated_context_unmatched_resource_is_blocked(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            config = PolicyConfig()
            taint = TaintState(session_id="s1", trust="low")
            decision = decide_access(
                "WebFetch", {"url": "https://never-seen.example.com/x"}, config, cache, taint
            )
            self.assertFalse(decision.allowed)
            self.assertTrue(decision.reason)

    def test_validated_allow_rule_proceeds_and_escalates_sensitivity(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            cache.put(
                Resource(kind="url", identity="https://internal.example.com/wiki", scanner_name="reputation"),
                ScanResult(label="trusted"),
            )
            config = PolicyConfig(
                rules=(
                    PolicyRule(
                        tool=".*",
                        pattern=r"https://internal\.example\.com/.*",
                        sensitivity="internal",
                        mode="allow",
                    ),
                )
            )
            taint = TaintState(session_id="s1")
            decision = decide_access(
                "WebFetch", {"url": "https://internal.example.com/wiki"}, config, cache, taint
            )
            self.assertTrue(decision.allowed)
            self.assertEqual(taint.trust, "high")  # unaffected -- validated, not uncleared
            self.assertEqual(taint.sensitivity, "internal")

    def test_validated_allow_proceeds_even_from_contaminated_context(self):
        # An explicitly validated+allowed resource bypasses the
        # block-when-contaminated gate -- that's the whole point of
        # declaring trust for it.
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            cache.put(
                Resource(kind="url", identity="https://internal.example.com/wiki", scanner_name="reputation"),
                ScanResult(label="trusted"),
            )
            config = PolicyConfig(
                rules=(
                    PolicyRule(
                        tool=".*", pattern=r"https://internal\.example\.com/.*", sensitivity="public", mode="allow"
                    ),
                )
            )
            taint = TaintState(session_id="s1", trust="low", sensitivity="restricted")
            decision = decide_access(
                "WebFetch", {"url": "https://internal.example.com/wiki"}, config, cache, taint
            )
            self.assertTrue(decision.allowed)

    def test_scanner_confirmed_bad_blocks_unconditionally_even_from_clean_context(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            cache.put(
                Resource(kind="url", identity="https://evil.example.com/x", scanner_name="reputation"),
                ScanResult(label="untrusted", reason="bad reputation"),
            )
            config = PolicyConfig()
            taint = TaintState(session_id="s1")
            decision = decide_access("WebFetch", {"url": "https://evil.example.com/x"}, config, cache, taint)
            self.assertFalse(decision.allowed)
            self.assertTrue(taint.is_clean)  # blocked call, no tag mutation

    def test_scanner_confirmed_bad_overrides_a_matching_allow_rule(self):
        # "Known bad resources are always blocked" -- a rule can declare
        # intent but never overrides a real, validated bad finding.
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            cache.put(
                Resource(kind="url", identity="https://evil.example.com/x", scanner_name="reputation"),
                ScanResult(label="untrusted"),
            )
            config = PolicyConfig(
                rules=(PolicyRule(tool=".*", pattern=r"https://evil\.example\.com/.*", sensitivity="public", mode="allow"),)
            )
            taint = TaintState(session_id="s1")
            decision = decide_access("WebFetch", {"url": "https://evil.example.com/x"}, config, cache, taint)
            self.assertFalse(decision.allowed)

    def test_explicit_non_allow_rule_blocks_unconditionally_even_from_clean_context(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            cache.put(
                Resource(kind="url", identity="https://banned.example.com/x", scanner_name="reputation"),
                ScanResult(label="trusted"),
            )
            config = PolicyConfig(
                rules=(
                    PolicyRule(
                        tool=".*",
                        pattern=r"https://banned\.example\.com/.*",
                        sensitivity="restricted",
                        mode="block",
                    ),
                )
            )
            taint = TaintState(session_id="s1")
            decision = decide_access("WebFetch", {"url": "https://banned.example.com/x"}, config, cache, taint)
            self.assertFalse(decision.allowed)
            self.assertTrue(taint.is_clean)

    def test_allow_rule_matched_but_not_yet_validated_is_treated_as_uncleared(self):
        # Rule declares intent; the cache hasn't confirmed it clean yet
        # (never scanned) -- sec15.2: a match only counts once validated.
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            config = PolicyConfig(
                rules=(
                    PolicyRule(
                        tool=".*", pattern=r"https://pending\.example\.com/.*", sensitivity="public", mode="allow"
                    ),
                )
            )
            taint = TaintState(session_id="s1")
            decision = decide_access("WebFetch", {"url": "https://pending.example.com/x"}, config, cache, taint)
            self.assertTrue(decision.allowed)  # clean context -- proceeds, same as unmatched
            self.assertEqual(taint.trust, "low")

    def test_confirmed_bad_wins_over_validated_allow_in_the_same_call(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            cache.put(
                Resource(kind="url", identity="https://good.example.com/a", scanner_name="reputation"),
                ScanResult(label="trusted"),
            )
            cache.put(
                Resource(kind="url", identity="https://evil.example.com/b", scanner_name="reputation"),
                ScanResult(label="untrusted"),
            )
            config = PolicyConfig(
                rules=(
                    PolicyRule(tool=".*", pattern=r"https://good\.example\.com/.*", sensitivity="public", mode="allow"),
                )
            )
            taint = TaintState(session_id="s1")
            decision = decide_access(
                "Bash",
                {"command": "curl https://good.example.com/a https://evil.example.com/b"},
                config,
                cache,
                taint,
            )
            self.assertFalse(decision.allowed)

    def test_mixed_validated_allow_and_uncleared_in_one_call_from_clean_context(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            cache.put(
                Resource(kind="url", identity="https://internal.example.com/a", scanner_name="reputation"),
                ScanResult(label="trusted"),
            )
            config = PolicyConfig(
                rules=(
                    PolicyRule(
                        tool=".*", pattern=r"https://internal\.example\.com/.*", sensitivity="internal", mode="allow"
                    ),
                )
            )
            taint = TaintState(session_id="s1")
            decision = decide_access(
                "Bash",
                {"command": "curl https://internal.example.com/a https://unknown.example.net/b"},
                config,
                cache,
                taint,
            )
            self.assertTrue(decision.allowed)
            self.assertEqual(taint.trust, "low")  # uncleared resource present
            self.assertEqual(taint.sensitivity, "internal")  # from the validated-allow match

    def test_sensitivity_escalation_is_most_restrictive_across_matched_rules(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            cache.put(
                Resource(kind="url", identity="https://a.example.com/x", scanner_name="reputation"),
                ScanResult(label="trusted"),
            )
            cache.put(
                Resource(kind="url", identity="https://b.example.com/y", scanner_name="reputation"),
                ScanResult(label="trusted"),
            )
            config = PolicyConfig(
                rules=(
                    PolicyRule(tool=".*", pattern=r"https://a\.example\.com/.*", sensitivity="internal", mode="allow"),
                    PolicyRule(tool=".*", pattern=r"https://b\.example\.com/.*", sensitivity="restricted", mode="allow"),
                )
            )
            taint = TaintState(session_id="s1")
            decision = decide_access(
                "Bash", {"command": "curl https://a.example.com/x https://b.example.com/y"}, config, cache, taint
            )
            self.assertTrue(decision.allowed)
            self.assertEqual(taint.sensitivity, "restricted")

    def test_rule_scanner_filter_still_respected(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            target = Path(tmp) / "anything.md"
            target.write_text("x")
            cache.put(Resource(kind="file", identity=str(target), scanner_name="secrets"), ScanResult(label="public"))
            config = PolicyConfig(
                rules=(
                    PolicyRule(tool=".*", pattern=".*", sensitivity="public", mode="allow", scanner="reputation"),
                )
            )
            taint = TaintState(session_id="s1")
            # File resource matches pattern but not scanner="reputation" -- rule shouldn't apply.
            decision = decide_access("Read", {"file_path": str(target)}, config, cache, taint)
            self.assertTrue(decision.allowed)  # clean context, unmatched -> proceeds
            self.assertEqual(taint.trust, "low")  # NOT validated_allow -- fell through to uncleared


class TestHardcodedRestrictedPaths(unittest.TestCase):
    """docs/ARCHITECTURE.md sec18.2 (STORY-1502). Uses the real FileScanner
    (not a fabricated ScanResult) against a real path under one of the
    hardcoded prefixes -- /etc/hostname exists on essentially every Linux
    system and is safe to stat/read (no real secret content). Pre-populates
    the cache with the *real* FileScanner().scan() result directly, same
    precedent as this file's other cache-hit tests (e.g.
    test_validated_allow_rule_proceeds_and_escalates_sensitivity) --
    decide_access()'s first-sighting path is fire-and-forget async (no
    synchronous scan on a cache miss), so testing the post-scan state this
    way is what the rest of this file already does, not a shortcut unique
    to this test."""

    def _seed_real_scan(self, cache: ScanCache, identity: str) -> Resource:
        resource = Resource(kind="file", identity=identity, scanner_name="secrets")
        cache.put(resource, FileScanner().scan(resource))
        return resource

    def test_hardcoded_restricted_path_blocks_unconditionally(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            self._seed_real_scan(cache, "/etc/hostname")
            config = PolicyConfig()
            taint = TaintState(session_id="s1")
            decision = decide_access("Read", {"file_path": "/etc/hostname"}, config, cache, taint)
            self.assertFalse(decision.allowed)

    def test_hardcoded_restricted_path_blocks_even_with_a_matching_allow_rule(self):
        # The actual STORY-1502 "regardless" AC: a hand-authored rule that
        # would normally validated_allow a clean-scanning resource must not
        # be able to override the hardcoded floor.
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            self._seed_real_scan(cache, "/etc/hostname")
            config = PolicyConfig(
                rules=(
                    PolicyRule(tool=".*", pattern=r"/etc/hostname", sensitivity="public", mode="allow"),
                )
            )
            taint = TaintState(session_id="s1")
            decision = decide_access("Read", {"file_path": "/etc/hostname"}, config, cache, taint)
            self.assertFalse(decision.allowed)

    def test_ordinary_path_outside_the_hardcoded_set_is_unaffected(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "clean.md"
            target.write_text("ordinary docs, not under any restricted prefix")
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            self._seed_real_scan(cache, str(target))
            config = PolicyConfig()
            taint = TaintState(session_id="s1")
            decision = decide_access("Read", {"file_path": str(target)}, config, cache, taint)
            self.assertTrue(decision.allowed)


class TestProjectFolderDefault(unittest.TestCase):
    """docs/ARCHITECTURE.md sec18.4 (STORY-1504, corrected 2026-07-21 per
    direct user request): a brand-new project's own folder gets a real
    rule written to a real scalene_policy.yaml (write_default_project_policy,
    policy_config.py) -- not an implicit in-memory special case. These
    tests load that real, on-disk rule via PolicyConfig.from_yaml(), the
    same way `scalene-guard` actually does, then exercise decide_access()
    against it. Uses the real FileScanner result pre-seeded into the cache
    -- same precedent as TestHardcodedRestrictedPaths -- since
    decide_access()'s first-sighting path is fire-and-forget async, not
    synchronous."""

    def _seed_real_scan(self, cache: ScanCache, identity: str) -> Resource:
        resource = Resource(kind="file", identity=identity, scanner_name="secrets")
        cache.put(resource, FileScanner().scan(resource))
        return resource

    def test_clean_project_file_is_validated_allow_and_escalates_internal_sensitivity(self):
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            target = project_root / "src" / "main.py"
            target.parent.mkdir()
            target.write_text("print('hello')")
            cache = ScanCache(project_root / "scan_cache.json")
            self._seed_real_scan(cache, str(target))
            policy_path = project_root / "scalene_policy.yaml"
            write_default_project_policy(policy_path, project_root)
            config = PolicyConfig.from_yaml(policy_path)
            taint = TaintState(session_id="s1")
            decision = decide_access("Read", {"file_path": str(target)}, config, cache, taint)
            self.assertTrue(decision.allowed)
            self.assertEqual(taint.sensitivity, "internal")
            self.assertEqual(taint.trust, "high")  # validated, not merely uncleared

    def test_second_project_file_in_the_same_session_does_not_hit_the_uncleared_wall(self):
        # The actual friction STORY-1504 fixes: without this rule, a 2nd
        # uncleared resource in an already-"low"-trust session would block.
        # With it, a 2nd *clean, in-project* file still proceeds.
        with TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            first = project_root / "a.py"
            second = project_root / "b.py"
            first.write_text("a")
            second.write_text("b")
            cache = ScanCache(project_root / "scan_cache.json")
            self._seed_real_scan(cache, str(first))
            self._seed_real_scan(cache, str(second))
            policy_path = project_root / "scalene_policy.yaml"
            write_default_project_policy(policy_path, project_root)
            config = PolicyConfig.from_yaml(policy_path)
            taint = TaintState(session_id="s1", trust="low")  # already contaminated
            decision = decide_access("Read", {"file_path": str(second)}, config, cache, taint)
            self.assertTrue(decision.allowed)

    def test_coexists_with_hardcoded_restricted_paths_under_the_project_root(self):
        # sec18.2's coexistence AC: a restricted subpath under the project
        # root is not blanket-trusted just because it's under project_root.
        # _HARDCODED_RESTRICTED_PREFIXES is fixed to /etc and the real
        # ~/.ssh -- an arbitrary tmp dir can't literally *be* one of those,
        # so this uses the real home directory as project_root (a realistic
        # "project root happens to be your home dir" case) with a target
        # under ~/.ssh. FileScanner's short-circuit fires before any real
        # file read, so the target path doesn't need to actually exist, and
        # the policy file is written to a scratch dir (never touches the
        # real ~/scalene_policy.yaml).
        home = Path(os.path.expanduser("~"))
        target = Path(os.path.expanduser("~/.ssh")) / "id_rsa"
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            self._seed_real_scan(cache, str(target))
            policy_path = Path(tmp) / "scalene_policy.yaml"
            write_default_project_policy(policy_path, home)
            config = PolicyConfig.from_yaml(policy_path)
            taint = TaintState(session_id="s1")
            decision = decide_access("Read", {"file_path": str(target)}, config, cache, taint)
            self.assertFalse(decision.allowed)  # is_bad wins, the allow rule never fires

    def test_file_outside_the_project_root_is_unaffected(self):
        with TemporaryDirectory() as project_tmp, TemporaryDirectory() as outside_tmp:
            project_root = Path(project_tmp)
            outside_target = Path(outside_tmp) / "other.py"
            outside_target.write_text("not part of this project")
            cache = ScanCache(project_root / "scan_cache.json")
            self._seed_real_scan(cache, str(outside_target))
            policy_path = project_root / "scalene_policy.yaml"
            write_default_project_policy(policy_path, project_root)
            config = PolicyConfig.from_yaml(policy_path)
            taint = TaintState(session_id="s1")
            decision = decide_access("Read", {"file_path": str(outside_target)}, config, cache, taint)
            self.assertTrue(decision.allowed)  # clean, unmatched -> uncleared, was_clean -> proceeds
            self.assertEqual(taint.trust, "low")  # NOT validated_allow


if __name__ == "__main__":
    unittest.main()
