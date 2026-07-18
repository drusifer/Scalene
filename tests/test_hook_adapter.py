"""Tests for the Claude Code PreToolUse/PostToolUse hook adapter (STORY-301, STORY-302).

2026-07-14: response shape corrected to Claude Code's real hook contract
(`hookSpecificOutput.permissionDecision`/`updatedInput`), not the
previously-invented flat `{"allow": ..., "updatedInput": ...}` shape,
which the real harness never honored.

2026-07-17 (docs/ARCHITECTURE.md sec15, direct user design session):
rewritten entirely for rule-driven access control, replacing the old
content-scanning/masking model. `pre_tool_use` now makes the full
allow/block decision via `resource_verifier.decide_access` and persists
the resulting trust/sensitivity tags; `post_tool_use` is a documented
no-op (see hook_adapter.py's docstring for why).
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scalene.hook_adapter import post_tool_use, pre_tool_use
from scalene.policy_config import PolicyConfig, PolicyRule
from scalene.scan_cache import ScanCache
from scalene.scanner import Resource, ScanResult
from scalene.taint_state import TaintState

REAL_SECRET = "AKIAIOSFODNN7EXAMPLE"  # AWS access-key-ID shape (not used for scanning under sec15, kept for realistic call shapes)


def _decision(result: dict) -> str:
    return result["hookSpecificOutput"]["permissionDecision"]


def _reason(result: dict):
    return result["hookSpecificOutput"].get("permissionDecisionReason")


class TestPreToolUseCleanContext(unittest.TestCase):
    def test_no_resources_identified_allows(self):
        with TemporaryDirectory() as tmp:
            config = PolicyConfig()
            result = pre_tool_use(
                {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "echo hello"}},
                config,
                state_dir=Path(tmp),
                cache_path=Path(tmp) / "cache.json",
            )
            self.assertEqual(_decision(result), "allow")

    def test_unmatched_resource_from_clean_context_allows_and_taints_trust(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            config = PolicyConfig()
            result = pre_tool_use(
                {"session_id": "s1", "tool_name": "WebFetch", "tool_input": {"url": "https://never-seen.example.com/x"}},
                config,
                state_dir=state_dir,
                cache_path=state_dir / "cache.json",
            )
            self.assertEqual(_decision(result), "allow")
            taint = TaintState.load("s1", state_dir=state_dir)
            self.assertEqual(taint.trust, "low")
            self.assertEqual(taint.sensitivity, "public")

    def test_validated_allow_rule_allows_and_escalates_sensitivity(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            cache_path = state_dir / "cache.json"
            cache = ScanCache(cache_path)
            cache.put(
                Resource(kind="url", identity="https://internal.example.com/wiki", scanner_name="reputation"),
                ScanResult(label="trusted"),
            )
            config = PolicyConfig(
                rules=(
                    PolicyRule(
                        tool=".*", pattern=r"https://internal\.example\.com/.*", sensitivity="internal", mode="allow"
                    ),
                )
            )
            result = pre_tool_use(
                {"session_id": "s1", "tool_name": "WebFetch", "tool_input": {"url": "https://internal.example.com/wiki"}},
                config,
                state_dir=state_dir,
                cache_path=cache_path,
            )
            self.assertEqual(_decision(result), "allow")
            taint = TaintState.load("s1", state_dir=state_dir)
            self.assertEqual(taint.trust, "high")
            self.assertEqual(taint.sensitivity, "internal")


class TestPreToolUseContaminatedContext(unittest.TestCase):
    def test_unmatched_resource_from_contaminated_context_is_blocked(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            taint = TaintState(session_id="s1", trust="low", state_dir=state_dir)
            taint.save()
            config = PolicyConfig()

            result = pre_tool_use(
                {"session_id": "s1", "tool_name": "WebFetch", "tool_input": {"url": "https://also-unseen.example.com/x"}},
                config,
                state_dir=state_dir,
                cache_path=state_dir / "cache.json",
            )
            self.assertEqual(_decision(result), "deny")
            self.assertIsNotNone(_reason(result))

    def test_validated_allow_rule_still_proceeds_from_contaminated_context(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            cache_path = state_dir / "cache.json"
            cache = ScanCache(cache_path)
            cache.put(
                Resource(kind="url", identity="https://internal.example.com/wiki", scanner_name="reputation"),
                ScanResult(label="trusted"),
            )
            taint = TaintState(session_id="s1", trust="low", sensitivity="restricted", state_dir=state_dir)
            taint.save()
            config = PolicyConfig(
                rules=(
                    PolicyRule(tool=".*", pattern=r"https://internal\.example\.com/.*", sensitivity="public", mode="allow"),
                )
            )

            result = pre_tool_use(
                {"session_id": "s1", "tool_name": "WebFetch", "tool_input": {"url": "https://internal.example.com/wiki"}},
                config,
                state_dir=state_dir,
                cache_path=cache_path,
            )
            self.assertEqual(_decision(result), "allow")


class TestPreToolUseConfirmedBad(unittest.TestCase):
    def test_scanner_confirmed_bad_blocks_even_from_clean_context(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            cache_path = state_dir / "cache.json"
            cache = ScanCache(cache_path)
            cache.put(
                Resource(kind="url", identity="https://evil.example.com/x", scanner_name="reputation"),
                ScanResult(label="untrusted", reason="bad reputation"),
            )
            config = PolicyConfig()

            result = pre_tool_use(
                {"session_id": "s1", "tool_name": "WebFetch", "tool_input": {"url": "https://evil.example.com/x"}},
                config,
                state_dir=state_dir,
                cache_path=cache_path,
            )
            self.assertEqual(_decision(result), "deny")
            taint = TaintState.load("s1", state_dir=state_dir)
            self.assertTrue(taint.is_clean)  # blocked call -- no tag mutation

    def test_explicit_non_allow_rule_blocks_even_from_clean_context(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            cache_path = state_dir / "cache.json"
            cache = ScanCache(cache_path)
            cache.put(
                Resource(kind="url", identity="https://banned.example.com/x", scanner_name="reputation"),
                ScanResult(label="trusted"),
            )
            config = PolicyConfig(
                rules=(
                    PolicyRule(tool=".*", pattern=r"https://banned\.example\.com/.*", sensitivity="restricted", mode="block"),
                )
            )

            result = pre_tool_use(
                {"session_id": "s1", "tool_name": "WebFetch", "tool_input": {"url": "https://banned.example.com/x"}},
                config,
                state_dir=state_dir,
                cache_path=cache_path,
            )
            self.assertEqual(_decision(result), "deny")


class TestPreToolUseAuditLog(unittest.TestCase):
    def test_block_event_appended_to_audit_log(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            audit_log = Path(tmp) / "audit.log"
            taint = TaintState(session_id="s1", trust="low", state_dir=state_dir)
            taint.save()
            config = PolicyConfig()

            pre_tool_use(
                {"session_id": "s1", "tool_name": "WebFetch", "tool_input": {"url": "https://unseen.example.com/x"}},
                config,
                state_dir=state_dir,
                cache_path=state_dir / "cache.json",
                audit_log_path=audit_log,
            )
            entry = json.loads(audit_log.read_text().strip())
            self.assertEqual(entry["event"], "block")
            self.assertTrue(entry["reason"])

    def test_no_audit_log_entry_when_allowed(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            audit_log = Path(tmp) / "audit.log"
            config = PolicyConfig()

            pre_tool_use(
                {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "echo hello"}},
                config,
                state_dir=state_dir,
                cache_path=state_dir / "cache.json",
                audit_log_path=audit_log,
            )
            self.assertFalse(audit_log.exists())


class TestPostToolUseIsANoOp(unittest.TestCase):
    def test_returns_empty_and_writes_no_state(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            config = PolicyConfig()
            result = post_tool_use(
                {"session_id": "s1", "tool_name": "Read", "tool_input": {}, "tool_response": {"file_path": "secrets.env"}},
                config,
                state_dir=state_dir,
                cache_path=state_dir / "cache.json",
            )
            self.assertEqual(result, {})
            self.assertFalse((state_dir / "s1.json").exists())

    def test_runs_regardless_of_tool_success_or_failure(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            config = PolicyConfig()
            result = post_tool_use(
                {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "false"}, "tool_response": {}},
                config,
                state_dir=state_dir,
                cache_path=state_dir / "cache.json",
            )
            self.assertEqual(result, {})


class TestScaleneBypass(unittest.TestCase):
    """STORY-601 AC2: SCALENE_BYPASS=1 must short-circuit both hooks so a
    scanner subprocess's own actions never recursively re-trigger them."""

    def test_pre_tool_use_bypasses_and_writes_no_state(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            config = PolicyConfig()

            with patch.dict("os.environ", {"SCALENE_BYPASS": "1"}):
                result = pre_tool_use(
                    {"session_id": "s1", "tool_name": "WebFetch", "tool_input": {"url": "https://unseen.example.com/x"}},
                    config,
                    state_dir=state_dir,
                    cache_path=state_dir / "cache.json",
                )
            self.assertEqual(_decision(result), "allow")
            self.assertFalse((state_dir / "s1.json").exists())

    def test_post_tool_use_bypasses_and_returns_empty(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            config = PolicyConfig()

            with patch.dict("os.environ", {"SCALENE_BYPASS": "1"}):
                result = post_tool_use(
                    {"session_id": "s1", "tool_name": "Read", "tool_input": {}, "tool_response": {"file_path": "secrets.env"}},
                    config,
                    state_dir=state_dir,
                    cache_path=state_dir / "cache.json",
                )
            self.assertEqual(result, {})
            self.assertFalse((state_dir / "s1.json").exists())


if __name__ == "__main__":
    unittest.main()
