"""Tests for OLOY mode (docs/ARCHITECTURE.md sec24, direct user request
2026-11-20): vetting during a session is automatic -- an unknown/stale
resource is scanned synchronously and the scanner's verdict decides the
call (auto-review), secrets in a tainted session's outgoing payload are
masked rather than blocked (auto-mask), and nothing is parked for a human.
"""

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scalene.hook_adapter import pre_tool_use
from scalene.masking import MaskingEngine
from scalene.monitor_app import MonitorApp
from scalene.monitor_data import AuditTail, OloyCounts, format_oloy_summary
from textual.widgets import Static

from _fast_async import FastIsolatedAsyncioTestCase
from scalene.policy_config import OLOY_ENV_VAR, PolicyConfig, PolicyRule, oloy_enabled, oloy_setting
from scalene import resource_verifier
from scalene.resource_verifier import OLOY_SCAN_BUDGET_SECONDS, decide_access
from scalene.scan_cache import ScanCache
from scalene.scanner import Resource, ScanResult, Scanner
from scalene.taint_state import TaintState

REAL_SECRET = "AKIAIOSFODNN7EXAMPLE"  # AWS access-key-ID shape; detect-secrets flags it


class FakeScanner(Scanner):
    """Deterministic, in-process scanner: identifies `args["target"]` and
    returns whatever label `verdicts` maps it to. Counts scans so tests can
    assert the synchronous path actually ran (or didn't)."""

    name = "fake"

    def __init__(self, verdicts: dict[str, str]):
        self.verdicts = verdicts
        self.scanned: list[str] = []

    def identify(self, tool_name, args):
        target = args.get("target")
        return [Resource(kind="fake", identity=target, scanner_name=self.name)] if target else []

    def scan(self, resource):
        self.scanned.append(resource.identity)
        return ScanResult(label=self.verdicts[resource.identity])


def _config(scanner: FakeScanner, rules=()) -> PolicyConfig:
    return PolicyConfig(scanners={scanner.name: scanner}, rules=tuple(rules))


class TestOloyAutoReview(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.cache = ScanCache(Path(self._tmp.name) / "scan_cache.json")
        # OLOY must never fall back to a background worker.
        spawn = patch("scalene.scan_cache._spawn_background_refresh")
        self.spawn = spawn.start()
        self.addCleanup(spawn.stop)

    def tearDown(self):
        self._tmp.cleanup()

    def test_contaminated_session_unruled_clean_resource_is_auto_cleared(self):
        scanner = FakeScanner({"thing-a": "public"})
        taint = TaintState(session_id="s1", trust="low")
        decision = decide_access("Tool", {"target": "thing-a"}, _config(scanner), self.cache, taint, oloy=True)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.auto_cleared, ("thing-a",))
        self.assertEqual(scanner.scanned, ["thing-a"])
        self.assertEqual(self.cache.get_by_key("fake:thing-a").label, "public")
        self.spawn.assert_not_called()

    def test_same_call_without_oloy_still_waits_for_review(self):
        scanner = FakeScanner({"thing-a": "public"})
        taint = TaintState(session_id="s1", trust="low")
        decision = decide_access("Tool", {"target": "thing-a"}, _config(scanner), self.cache, taint)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.block_kind, "uncleared")
        self.assertEqual(scanner.scanned, [])

    def test_unruled_bad_resource_is_blocked_as_confirmed_bad(self):
        scanner = FakeScanner({"thing-b": "untrusted"})
        taint = TaintState(session_id="s1")
        decision = decide_access("Tool", {"target": "thing-b"}, _config(scanner), self.cache, taint, oloy=True)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.block_kind, "confirmed_bad")

    def test_clean_session_auto_cleared_resource_still_lowers_trust(self):
        scanner = FakeScanner({"thing-a": "trusted"})
        taint = TaintState(session_id="s1")
        decision = decide_access("Tool", {"target": "thing-a"}, _config(scanner), self.cache, taint, oloy=True)
        self.assertTrue(decision.allowed)
        self.assertEqual(taint.trust, "low")
        self.assertEqual(taint.sensitivity, "public")

    def test_restricted_untrusted_session_still_blocks_auto_cleared_egress(self):
        scanner = FakeScanner({"thing-a": "public"})
        taint = TaintState(session_id="s1", trust="low", sensitivity="restricted")
        decision = decide_access("Tool", {"target": "thing-a"}, _config(scanner), self.cache, taint, oloy=True)
        self.assertFalse(decision.allowed)
        self.assertIn("OLOY mode", decision.reason)
        self.assertNotIn("Wait for review", decision.reason)

    def test_explicit_block_rule_still_wins(self):
        scanner = FakeScanner({"thing-a": "public"})
        rules = [PolicyRule(tool=".*", pattern="thing-a", sensitivity="public", mode="block")]
        taint = TaintState(session_id="s1")
        decision = decide_access("Tool", {"target": "thing-a"}, _config(scanner, rules), self.cache, taint, oloy=True)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.block_kind, "confirmed_bad")

    def test_allow_rule_is_validated_synchronously_not_trust_but_verify(self):
        scanner = FakeScanner({"thing-a": "public"})
        rules = [PolicyRule(tool=".*", pattern="thing-a", sensitivity="internal", mode="allow")]
        taint = TaintState(session_id="s1")
        decision = decide_access("Tool", {"target": "thing-a"}, _config(scanner, rules), self.cache, taint, oloy=True)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.auto_cleared, ())
        self.assertEqual(taint.pending_trust, [])
        self.assertEqual(taint.sensitivity, "internal")

    def test_fresh_cache_entry_is_not_rescanned(self):
        scanner = FakeScanner({"thing-a": "public"})
        self.cache.put(Resource(kind="fake", identity="thing-a", scanner_name="fake"), ScanResult(label="public"))
        taint = TaintState(session_id="s1", trust="low")
        decision = decide_access("Tool", {"target": "thing-a"}, _config(scanner), self.cache, taint, oloy=True)
        self.assertTrue(decision.allowed)
        self.assertEqual(scanner.scanned, [])


class TestOloyFailsClosed(unittest.TestCase):
    """STORY-1902 AC: a scanner-machinery failure during OLOY's synchronous
    scan blocks the call (scalene-guard exit 2), never fails open."""

    def test_machinery_failure_during_sync_scan_exits_2(self):
        import io
        from scalene.cli import main
        from scalene.scanner import ScannerMachineryError

        payload = {"hook_event_name": "PreToolUse", "session_id": "f", "tool_name": "WebFetch",
                   "tool_input": {"url": "https://never-seen.example.com/x"}}
        with TemporaryDirectory() as tmp, patch.dict(os.environ, {OLOY_ENV_VAR: "1"}), \
                patch("scalene.scanner.URLScanner.scan", side_effect=ScannerMachineryError("boom")), \
                patch("sys.stdin", io.StringIO(json.dumps(payload))), patch("sys.stdout", io.StringIO()), \
                patch("sys.stderr", io.StringIO()) as err:
            os.environ.pop("SCALENE_BYPASS", None)
            code = main([
                "--policy-path", str(Path(tmp) / "p.yaml"),
                "--state-dir", str(Path(tmp) / "state"),
                "--cache-path", str(Path(tmp) / "cache.json"),
            ])
        self.assertEqual(code, 2)
        self.assertIn("boom", err.getvalue())


class TestOloyConfig(unittest.TestCase):
    def test_defaults_off(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(OLOY_ENV_VAR, None)
            self.assertFalse(oloy_enabled(PolicyConfig()))

    def test_yaml_defaults_oloy_turns_it_on(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "scalene_policy.yaml"
            path.write_text("defaults:\n  oloy: true\n")
            config = PolicyConfig.from_yaml(path)
            self.assertTrue(config.oloy)

    def test_env_var_overrides_file_both_ways(self):
        with patch.dict(os.environ, {OLOY_ENV_VAR: "1"}):
            self.assertTrue(oloy_enabled(PolicyConfig(oloy=False)))
        with patch.dict(os.environ, {OLOY_ENV_VAR: "0"}):
            self.assertFalse(oloy_enabled(PolicyConfig(oloy=True)))
        with patch.dict(os.environ, {OLOY_ENV_VAR: ""}):
            self.assertTrue(oloy_enabled(PolicyConfig(oloy=True)))


class TestOloyEnvWarning(unittest.TestCase):
    """STORY-1901 / sec24.1 (Smith Gates 1+2): an unrecognized SCALENE_OLOY
    value falls back to the file AND is surfaced -- never silently."""

    def test_accepted_values_are_case_and_whitespace_insensitive(self):
        for raw in ("1", "TRUE", " on ", "Yes"):
            with patch.dict(os.environ, {OLOY_ENV_VAR: raw}):
                self.assertEqual(oloy_setting(PolicyConfig()), (True, None), raw)
        for raw in ("0", "False", " OFF", "no"):
            with patch.dict(os.environ, {OLOY_ENV_VAR: raw}):
                self.assertEqual(oloy_setting(PolicyConfig(oloy=True)), (False, None), raw)

    def test_unrecognized_value_falls_back_to_file_with_a_warning(self):
        with patch.dict(os.environ, {OLOY_ENV_VAR: "enable"}):
            enabled, warning = oloy_setting(PolicyConfig(oloy=False))
        self.assertFalse(enabled)
        self.assertIn("'enable'", warning)
        self.assertIn("1/true/on/yes", warning)

    def test_hook_surfaces_the_warning_in_system_message_without_changing_the_decision(self):
        with TemporaryDirectory() as tmp, patch.dict(os.environ, {OLOY_ENV_VAR: "enable"}):
            result = pre_tool_use(
                {"session_id": "w", "tool_name": "Bash", "tool_input": {"command": "echo hi"}},
                PolicyConfig(),
                state_dir=Path(tmp),
                audit_log_path=Path(tmp) / "audit.log",
                cache_path=Path(tmp) / "cache.json",
            )
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "allow")
        self.assertNotIn("permissionDecisionReason", result["hookSpecificOutput"])
        self.assertIn("SCALENE_OLOY", result["systemMessage"])

    def test_warning_is_appended_to_a_block_reason_not_replacing_it(self):
        with TemporaryDirectory() as tmp, patch.dict(os.environ, {OLOY_ENV_VAR: "enable"}):
            TaintState(session_id="w2", trust="low", state_dir=Path(tmp)).save()
            result = pre_tool_use(
                {"session_id": "w2", "tool_name": "WebFetch", "tool_input": {"url": "https://never-seen.example.com/x"}},
                PolicyConfig(),
                state_dir=Path(tmp),
                audit_log_path=Path(tmp) / "audit.log",
                cache_path=Path(tmp) / "cache.json",
            )
        out = result["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "deny")
        self.assertNotIn("SCALENE_OLOY", out["permissionDecisionReason"])
        self.assertIn(out["permissionDecisionReason"], result["systemMessage"])
        self.assertIn("SCALENE_OLOY", result["systemMessage"])


class TestOloyScanBudget(unittest.TestCase):
    """STORY-1902 / sec24.2: synchronous scanning is bounded per call so a
    many-resource call can't run past the hook timeout (non-blocking = fail
    open). Fake clock: each scan advances it, no real sleeping."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.cache = ScanCache(Path(self._tmp.name) / "scan_cache.json")
        spawn = patch("scalene.scan_cache._spawn_background_refresh")
        self.spawn = spawn.start()
        self.addCleanup(spawn.stop)
        self.now = [0.0]
        clock = patch.object(resource_verifier, "_clock", lambda: self.now[0])
        clock.start()
        self.addCleanup(clock.stop)

    def tearDown(self):
        self._tmp.cleanup()

    def _slow_scanner(self, cost: dict[str, float]) -> FakeScanner:
        test = self

        class SlowScanner(FakeScanner):
            def identify(self, tool_name, args):
                return [Resource(kind="fake", identity=t, scanner_name=self.name) for t in args["targets"]]

            def scan(self, resource):
                test.now[0] += cost[resource.identity]
                return super().scan(resource)

        return SlowScanner({k: "public" for k in cost})

    def test_resources_past_the_budget_are_not_scanned_synchronously_and_the_call_blocks(self):
        scanner = self._slow_scanner({"a": 15.0, "b": 10.0, "c": 1.0})
        taint = TaintState(session_id="s1", trust="low")
        decision = decide_access("Tool", {"targets": ["a", "b", "c"]}, _config(scanner), self.cache, taint, oloy=True)
        self.assertEqual(scanner.scanned, ["a", "b"])  # c reached after 25s > budget
        self.assertGreater(25.0, OLOY_SCAN_BUDGET_SECONDS)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.block_kind, "uncleared")
        self.assertIn("Blocked: c is still being scanned", decision.reason)
        self.assertIn("retry", decision.reason.lower())
        self.spawn.assert_called_once()  # c handed to the normal background path

    def test_within_budget_everything_is_scanned_and_cleared(self):
        scanner = self._slow_scanner({"a": 5.0, "b": 5.0})
        taint = TaintState(session_id="s1", trust="low")
        decision = decide_access("Tool", {"targets": ["a", "b"]}, _config(scanner), self.cache, taint, oloy=True)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.auto_cleared, ("a", "b"))


class TestMaskSecrets(unittest.TestCase):
    def test_masks_only_fields_with_secrets(self):
        args = {"command": f"export KEY={REAL_SECRET}", "description": "set a key"}
        masked, found = MaskingEngine().mask_secrets(args)
        self.assertEqual(masked["command"], MaskingEngine.MASK_LITERAL)
        self.assertEqual(masked["description"], "set a key")
        self.assertIn("command", found)
        self.assertEqual(args["command"], f"export KEY={REAL_SECRET}")  # input not mutated

    def test_clean_payload_is_returned_unchanged(self):
        args = {"command": "ls -la"}
        masked, found = MaskingEngine().mask_secrets(args)
        self.assertIs(masked, args)
        self.assertEqual(found, {})


class TestMaskScopeLocatorFields(unittest.TestCase):
    """STORY-1903 / sec24.3: a tool's locator field (file_path, url) is never
    masked -- replacing it breaks the call, and the resource it names was
    already vetted by auto-review."""

    def test_write_content_is_masked_but_file_path_is_kept(self):
        args = {"file_path": "/tmp/notes.txt", "content": f"aws_key = '{REAL_SECRET}'"}
        masked, found = MaskingEngine().mask_secrets(args, tool_name="Write")
        self.assertEqual(masked["file_path"], "/tmp/notes.txt")
        self.assertEqual(masked["content"], MaskingEngine.MASK_LITERAL)
        self.assertEqual(set(found), {"content"})

    def test_locator_field_is_excluded_even_if_it_looks_like_a_secret(self):
        args = {"url": f"https://example.com/?k={REAL_SECRET}"}
        masked, found = MaskingEngine().mask_secrets(args, tool_name="WebFetch")
        self.assertIs(masked, args)
        self.assertEqual(found, {})

    def test_same_field_name_on_a_tool_without_that_locator_is_still_masked(self):
        # `url` is only a locator for WebFetch; on Bash it's just a string.
        masked, found = MaskingEngine().mask_secrets({"url": f"k={REAL_SECRET}"}, tool_name="Bash")
        self.assertEqual(masked["url"], MaskingEngine.MASK_LITERAL)

    def test_hook_masks_write_content_and_keeps_the_secret_out_of_the_audit_log(self):
        with TemporaryDirectory() as tmp, patch.dict(os.environ, {OLOY_ENV_VAR: "1"}):
            tmp = Path(tmp)
            os.environ.pop("SCALENE_BYPASS", None)
            TaintState(session_id="m", trust="low", state_dir=tmp).save()
            target = tmp / "out.txt"
            config = PolicyConfig(
                rules=(PolicyRule(tool=".*", pattern=str(target), sensitivity="public", mode="allow"),)
            )
            result = pre_tool_use(
                {"session_id": "m", "tool_name": "Write",
                 "tool_input": {"file_path": str(target), "content": f"aws_key = '{REAL_SECRET}'"}},
                config,
                state_dir=tmp,
                audit_log_path=tmp / "audit.log",
                cache_path=tmp / "cache.json",
            )
            out = result["hookSpecificOutput"]
            self.assertEqual(out["permissionDecision"], "allow")
            self.assertEqual(out["updatedInput"]["file_path"], str(target))
            self.assertEqual(out["updatedInput"]["content"], MaskingEngine.MASK_LITERAL)
            self.assertNotIn(REAL_SECRET, (tmp / "audit.log").read_text())


class TestOloyHookAutoMask(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.audit = self.tmp / "audit.log"
        env = patch.dict(os.environ, {OLOY_ENV_VAR: "1"})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("SCALENE_BYPASS", None)

    def tearDown(self):
        self._tmp.cleanup()

    def _call(self, session_id: str, command: str) -> dict:
        return pre_tool_use(
            {"session_id": session_id, "tool_name": "Bash", "tool_input": {"command": command}},
            PolicyConfig(),
            state_dir=self.tmp,
            audit_log_path=self.audit,
            cache_path=self.tmp / "cache.json",
        )

    def test_tainted_session_secret_is_masked_not_blocked(self):
        TaintState(session_id="s1", trust="low", state_dir=self.tmp).save()
        result = self._call("s1", f"echo {REAL_SECRET}")
        out = result["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "allow")
        self.assertEqual(out["updatedInput"]["command"], MaskingEngine.MASK_LITERAL)
        self.assertIn("masked", result["systemMessage"])
        entry = json.loads(self.audit.read_text().splitlines()[-1])
        self.assertTrue(entry["oloy"])
        self.assertIn("command", entry["masked_fields"])
        self.assertNotIn(REAL_SECRET, self.audit.read_text())

    def test_clean_session_payload_is_not_masked(self):
        result = self._call("s2", f"echo {REAL_SECRET}")
        self.assertNotIn("updatedInput", result["hookSpecificOutput"])

    def test_oloy_off_never_masks(self):
        TaintState(session_id="s3", trust="low", state_dir=self.tmp).save()
        with patch.dict(os.environ, {OLOY_ENV_VAR: "0"}):
            result = self._call("s3", f"echo {REAL_SECRET}")
        self.assertNotIn("updatedInput", result["hookSpecificOutput"])
        entry = json.loads(self.audit.read_text().splitlines()[-1])
        self.assertNotIn("oloy", entry)


class TestOloyAuditEvents(unittest.TestCase):
    def test_oloy_flag_round_trips_through_audit_tail(self):
        with TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.log"
            log.write_text(
                json.dumps({"event": "block", "session_id": "s", "tool_name": "T", "reason": "r", "oloy": True}) + "\n"
                + json.dumps({"event": "block", "session_id": "s", "tool_name": "T", "reason": "r"}) + "\n"
            )
            events = AuditTail(log).poll()
            self.assertEqual([e.oloy for e in events], [True, False])



def _oloy_line(event: str, session_id: str, **extra) -> str:
    entry = {"event": event, "session_id": session_id, "tool_name": "Bash", "tool_input": {"command": "x"},
             "reason": "r" if event == "block" else "", "block_kind": "confirmed_bad" if event == "block" else None,
             "ts": 1.0, "oloy": True}
    entry.update(extra)
    return json.dumps(entry) + "\n"


class TestOloySummaryData(unittest.TestCase):
    """STORY-1904 / sec24.4: data layer for the monitor's OLOY summary."""

    def test_audit_tail_parses_auto_cleared_and_masked(self):
        with TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.log"
            log.write_text(_oloy_line("allow", "s", auto_cleared=["/a"], masked_fields={"command": ["x"]}))
            (event,) = AuditTail(log).poll()
            self.assertEqual(event.auto_cleared, ("/a",))
            self.assertTrue(event.masked)

    def test_counts_classify_calls_and_format(self):
        counts = OloyCounts()
        with TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.log"
            log.write_text(
                _oloy_line("allow", "s", auto_cleared=["/a"])
                + _oloy_line("allow", "s", auto_cleared=["/b"], masked_fields={"command": ["x"]})
                + _oloy_line("block", "s")
                + json.dumps({"event": "block", "session_id": "s", "tool_name": "T", "reason": "r"}) + "\n"
            )
            for event in AuditTail(log).poll():
                counts.add(event)
        self.assertEqual((counts.cleared, counts.masked, counts.blocked), (2, 1, 1))
        self.assertEqual(format_oloy_summary(counts), "OLOY: 2 cleared · 1 masked · 1 blocked")

    def test_no_oloy_events_formats_as_empty(self):
        self.assertEqual(format_oloy_summary(OloyCounts()), "")
        self.assertEqual(format_oloy_summary(None), "")


class TestOloyMonitorApp(FastIsolatedAsyncioTestCase):
    """STORY-1904: the summary is on the session line for the latest session;
    an OLOY block never enters the queue; nothing changes for non-OLOY users."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        root = Path(self._tmp.name)
        self.state_dir = root / "state"
        self.audit_log = root / "audit.log"
        self.cache_path = root / "scan_cache.json"
        TaintState(session_id="s1", trust="low", state_dir=self.state_dir).save()

    def tearDown(self):
        self._tmp.cleanup()

    def _app(self) -> MonitorApp:
        return MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path,
                          policy_path=Path(self._tmp.name) / "none.yaml")

    async def test_session_line_shows_latest_sessions_oloy_summary_and_queue_stays_empty(self):
        self.audit_log.write_text(
            _oloy_line("allow", "s1", auto_cleared=["/a"])
            + _oloy_line("allow", "s1", masked_fields={"command": ["x"]})
            + _oloy_line("block", "s1")
            + _oloy_line("block", "other-session")
        )
        app = self._app()
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            line = str(app.query_one("#session-line", Static).content)
            self.assertIn("Session: s1", line)
            self.assertIn("OLOY: 1 cleared · 1 masked · 1 blocked", line)
            self.assertEqual(app._pending_reviews, [])

    async def test_session_line_is_unchanged_without_oloy_events(self):
        self.audit_log.write_text(json.dumps(
            {"event": "block", "session_id": "s1", "tool_name": "T", "tool_input": {}, "reason": "r"}) + "\n")
        app = self._app()
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            line = str(app.query_one("#session-line", Static).content)
            self.assertNotIn("OLOY", line)
            self.assertEqual(len(app._pending_reviews), 1)  # default-mode block still queues

if __name__ == "__main__":
    unittest.main()
