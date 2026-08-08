"""Full end-to-end sprint-close journey tests, split out of test_monitor_app.py
(direct user request, 2026-08-08) -- these are genuinely slow (each drives
several real screens/hook calls in one continuous scenario) and belong only
to UAT/sprint-close sign-off (Smith's `*user test E17`/`E18`), not routine
dev iteration. Named `uat_test_*.py` (not `test_*.py`) so `unittest
discover`'s default pattern skips this file entirely -- `make test`/
`test-q` never touch it. `make test-uat` runs it explicitly via `-p
'uat_test*.py'`, in addition to the normal suite."""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from textual.widgets import DataTable, Input, Static

from scalene.monitor_app import MonitorApp

from _fast_async import FastIsolatedAsyncioTestCase
from test_monitor_app import _write_state


class TestE17EndToEndUserJourney(FastIsolatedAsyncioTestCase):
    """Smith's sprint-close end-to-end test (`*user test E17`) — the full
    queue-first redesign exercised as one continuous real scenario through
    the actual scg monitor TUI + the real pre_tool_use hook, not per-phase
    in isolation. Supersedes `TestE16EndToEndUserJourney` (STORY-1602's
    standalone Scanners panel and STORY-1603's tagged event log are both
    permanently retired by this epic, not gapped -- there is no successor
    journey through them). Same standard as TestE14/E15/E16
    EndToEndUserJourney: real binaries/functions throughout, nothing
    mocked, touches every screen this epic shipped (queue, review, rules)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name) / "state"
        self.state_dir.mkdir()
        self.audit_log = Path(self._tmp.name) / "audit.log"
        self.cache_path = Path(self._tmp.name) / "scan_cache.json"
        self.policy_path = Path(self._tmp.name) / "scalene_policy.yaml"

    def tearDown(self):
        self._tmp.cleanup()

    async def test_full_journey_block_to_queue_to_review_to_allow_to_retry_to_rules(self):
        from scalene.hook_adapter import pre_tool_use
        from scalene.policy_config import PolicyConfig, VALID_RULE_MODES, VALID_SENSITIVITIES

        # A clean session's first unrecognized resource is allowed
        # (fail-safe, taints trust to low) -- a real block needs an
        # already-tainted session, same setup every other real-hook test
        # in this file uses.
        _write_state(self.state_dir, "s1", trust="low")
        target_path = Path(self._tmp.name) / "clean.md"
        target_path.write_text("nothing sensitive here")
        hook_input = {"session_id": "s1", "tool_name": "Read", "tool_input": {"file_path": str(target_path)}}

        # STORY-1601: a real blocked call carries differentiated retry
        # guidance in its systemMessage/reason, not just a bare denial.
        first = pre_tool_use(
            hook_input,
            PolicyConfig(),
            state_dir=self.state_dir,
            cache_path=self.cache_path,
            audit_log_path=self.audit_log,
        )
        self.assertEqual(first["hookSpecificOutput"]["permissionDecision"], "deny")
        reason = first["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("wait", reason.lower())
        self.assertIn("retry", reason.lower())

        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test(size=(120, 50)) as pilot:
            app.poll_data()
            await pilot.pause()

            # STORY-1702: session line tracks the real session, live.
            self.assertIn("s1", str(app.query_one("#session-line", Static).content))
            # STORY-1703: status strip shows real scanner state (the
            # background first-sighting scan E10 spawns for this
            # never-before-seen resource may already be idle again by now).
            self.assertIn("Scanners:", str(app.query_one("#status-strip", Static).content))
            # STORY-1701: the queue itself, and the attention signal.
            self.assertIn("1 pending review", app.title)
            queue = app.query_one("#queue", DataTable)
            self.assertEqual(queue.row_count, 1)
            self.assertEqual(queue.get_row_at(0)[1], "Read")

            # STORY-1701: Enter on the queue row opens the real blocked call.
            queue.move_cursor(row=0)
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(app.screen.query_one("#tool-input", Static).content, json.dumps({"file_path": str(target_path)}, indent=2))
            targets_table = app.screen.query_one("#targets", DataTable)
            self.assertEqual(targets_table.get_row_at(0)[0], str(target_path))
            # "not yet scanned", or already "public (fresh)" if the
            # background refresh worker E10's fail-safe path spawned for
            # this never-before-seen resource (during the pre_tool_use()
            # call above) won its own real race against this assertion --
            # both are correct, real cache-derived states.
            self.assertIn(targets_table.get_row_at(0)[2], ("not yet scanned", "public (fresh)"))

            # STORY-1704: match-expr fields (and their live Matches?
            # preview) are visible immediately, before Verify -- the
            # default per-target pattern already matches. (Allow's
            # disabled-until-Verify state isn't asserted here: E10's
            # background first-sighting scan for this never-before-seen
            # resource may have already completed by now, same legitimate
            # race as the target-status assertion above -- STORY-1604's own
            # dedicated tests already cover the controlled disabled/enabled
            # transition without that race.)
            self.assertEqual(targets_table.get_row_at(0)[4], "yes")

            # Verify -> real scan -> Allow unlocked.
            await pilot.click(app.screen.query_one("#verify-btn"))
            await pilot.pause()
            self.assertFalse(app.screen.query_one("#allow-btn").disabled)

            self.assertEqual(
                app.screen._selected_radio_value("sensitivity-radio", VALID_SENSITIVITIES, "public"), "public"
            )
            self.assertEqual(app.screen._selected_radio_value("mode-radio", VALID_RULE_MODES, "allow"), "allow")

            # STORY-1704: Allow writes directly now -- one click, not
            # reveal-then-submit.
            await pilot.click(app.screen.query_one("#allow-btn"))
            await pilot.pause()
            await pilot.pause()

            self.assertEqual(app._pending_reviews, [])
            self.assertIn("scg monitor", app.title)
            self.assertNotIn("pending review", app.title)

        self.assertTrue(self.policy_path.exists())
        written = self.policy_path.read_text()
        self.assertIn("mode: allow", written)

        # The retry: identical original call, real fresh config reload
        # from the just-written policy file, now genuinely allowed.
        second = pre_tool_use(
            hook_input,
            PolicyConfig.from_yaml(self.policy_path),
            state_dir=self.state_dir,
            cache_path=self.cache_path,
            audit_log_path=self.audit_log,
        )
        self.assertEqual(second["hookSpecificOutput"]["permissionDecision"], "allow")

        # STORY-1705: the Rules screen shows the rule that just-allowed
        # call wrote, through the real UI (a fresh monitor instance, same
        # as actually restarting `scg monitor`).
        app2 = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app2.run_test() as pilot:
            await pilot.press("r")
            await pilot.pause()
            rules_table = app2.screen.query_one("#rules", DataTable)
            self.assertEqual(rules_table.row_count, 1)
            self.assertEqual(rules_table.get_row_at(0)[2], str(target_path))
            self.assertEqual(rules_table.get_row_at(0)[4], "allow")

        self.assertTrue(self.policy_path.exists())
        written = self.policy_path.read_text()
        self.assertIn("mode: allow", written)

        # The retry: identical original call, real fresh config reload
        # from the just-written policy file, now genuinely allowed.
        second = pre_tool_use(
            hook_input,
            PolicyConfig.from_yaml(self.policy_path),
            state_dir=self.state_dir,
            cache_path=self.cache_path,
            audit_log_path=self.audit_log,
        )
        self.assertEqual(second["hookSpecificOutput"]["permissionDecision"], "allow")

        # STORY-1603's tagged event log (asserted here previously) is
        # retired by E17 -- nothing in this app shows the allow event
        # directly anymore, only the (now-empty) review queue.
        app2 = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app2.run_test() as pilot:
            app2.poll_data()
            await pilot.pause()
            self.assertEqual(app2.query_one("#queue", DataTable).row_count, 0)


class TestE18EndToEndUserJourney(FastIsolatedAsyncioTestCase):
    """Smith's sprint-close end-to-end test (`*user test E18`) — the
    review-queue overhaul exercised as one continuous real scenario, real
    binaries/functions throughout. Per-feature behavior is already covered
    by focused unit/integration tests per phase (test pyramid); this test
    covers only what a single continuous session proves that isolated
    tests can't: aggregation + skip + multi-target rows all coexisting in
    one real queue, and a Rules-screen edit/delete each verified against a
    real retried `pre_tool_use` call, not just the written YAML."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name) / "state"
        self.state_dir.mkdir()
        self.audit_log = Path(self._tmp.name) / "audit.log"
        self.cache_path = Path(self._tmp.name) / "scan_cache.json"
        self.policy_path = Path(self._tmp.name) / "scalene_policy.yaml"

    def tearDown(self):
        self._tmp.cleanup()

    async def test_aggregation_skip_multi_target_and_rules_edit_delete_in_one_session(self):
        from scalene.hook_adapter import pre_tool_use
        from scalene.policy_config import PolicyConfig

        _write_state(self.state_dir, "s1", trust="low")

        noisy_target = str(Path(self._tmp.name) / "noisy.env")
        Path(noisy_target).write_text("x")
        first_url = "https://first.example.com/x"
        second_url = "https://second.example.com/x"

        # Same exact call, blocked twice -- must aggregate to one entry.
        for _ in range(2):
            pre_tool_use(
                {"session_id": "s1", "tool_name": "Read", "tool_input": {"file_path": noisy_target}},
                PolicyConfig(),
                state_dir=self.state_dir,
                cache_path=self.cache_path,
                audit_log_path=self.audit_log,
            )
        # A distinct multi-target call.
        pre_tool_use(
            {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": f"curl {first_url} {second_url}"}},
            PolicyConfig(),
            state_dir=self.state_dir,
            cache_path=self.cache_path,
            audit_log_path=self.audit_log,
        )

        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test(size=(120, 50)) as pilot:
            app.poll_data()
            await pilot.pause()

            # STORY-1801: 2 identical Reads collapsed into 1 entry, count 2.
            self.assertEqual(len(app._pending_reviews), 2)
            noisy_entry = next(e for e in app._pending_reviews if e.event.tool_name == "Read")
            self.assertEqual(noisy_entry.count, 2)

            # STORY-1803: the Bash call's 2 targets render as 2 rows.
            table = app.query_one("#queue", DataTable)
            self.assertEqual(table.row_count, 3)  # 1 (Read, aggregated) + 2 (Bash targets)

            # STORY-1804: skip the noisy aggregated entry -- gone, no rule.
            noisy_row = next(i for i in range(table.row_count) if table.get_row_at(i)[1] == "Read")
            table.move_cursor(row=noisy_row)
            await pilot.press("s")
            await pilot.pause()
            self.assertEqual(len(app._pending_reviews), 1)
            self.assertFalse(self.policy_path.exists())

            # Allow the Bash/URL call so there's a real rule to edit next.
            table = app.query_one("#queue", DataTable)
            table.move_cursor(row=0)
            await pilot.press("enter")
            await pilot.pause()
            await pilot.click(app.screen.query_one("#verify-btn"))
            await pilot.pause()
            pattern_input = app.screen.query_one("#rule-pattern-input", Input)
            pattern_input.focus()
            pattern_input.value = re.escape(first_url)  # one shared rule for both targets
            await pilot.click(app.screen.query_one("#allow-btn"))
            await pilot.pause()
            await pilot.pause()

        self.assertTrue(self.policy_path.exists())

        # Real retry: now allowed.
        retry_allowed = pre_tool_use(
            {"session_id": "s2", "tool_name": "Bash", "tool_input": {"command": f"curl {first_url}"}},
            PolicyConfig.from_yaml(self.policy_path),
            state_dir=self.state_dir,
            cache_path=self.cache_path,
            audit_log_path=self.audit_log,
        )
        self.assertEqual(retry_allowed["hookSpecificOutput"]["permissionDecision"], "allow")

        # STORY-1807: edit the just-written rule's pattern away from
        # first_url -- a real retry of the same call must go back to
        # blocked, proving the edit took effect through the real hook, not
        # just in the written YAML.
        app2 = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app2.run_test() as pilot:
            await pilot.press("r")
            await pilot.pause()
            app2.screen.query_one("#rules", DataTable).move_cursor(row=0)
            await pilot.press("e")
            await pilot.pause()
            edit_pattern = app2.screen.query_one("#edit-pattern-input", Input)
            edit_pattern.focus()
            edit_pattern.value = re.escape("https://totally-different.example.com/x")
            await pilot.press("enter")
            await pilot.pause()
            self.assertIn("Saved rule #1", str(app2.screen.query_one("#rule-confirm", Static).content))

        # Trin's UAT lesson from the update_rule/delete_rule unit tests
        # (sec23.7): a *clean* session's first touch of an unmatched
        # resource gets decide_access's own fail-safe free pass regardless
        # of rule state, so proving the edit actually took effect needs an
        # already-tainted session, same as this file's own established
        # precedent for a real deterministic block.
        _write_state(self.state_dir, "s3", trust="low")
        retry_after_edit = pre_tool_use(
            {"session_id": "s3", "tool_name": "Bash", "tool_input": {"command": f"curl {first_url}"}},
            PolicyConfig.from_yaml(self.policy_path),
            state_dir=self.state_dir,
            cache_path=self.cache_path,
            audit_log_path=self.audit_log,
        )
        self.assertEqual(retry_after_edit["hookSpecificOutput"]["permissionDecision"], "deny")

        # STORY-1808: delete the rule outright -- confirmed via the Rules
        # screen showing 0 rules afterward (the edited pattern no longer
        # matches anything in this test anyway; the real point already
        # proven is the edit's real hook effect above).
        app3 = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app3.run_test() as pilot:
            await pilot.press("r")
            await pilot.pause()
            app3.screen.query_one("#rules", DataTable).move_cursor(row=0)
            await pilot.press("d")
            await pilot.press("d")
            await pilot.pause()
            self.assertIn("visible", app3.screen.query_one("#no-rules").classes)

        data = PolicyConfig.from_yaml(self.policy_path)
        self.assertEqual(data.rules, ())
