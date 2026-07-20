"""docs/GETTING_STARTED.md must exist and document the real access-control
walkthrough (STORY-901; rewritten 2026-07-17 per docs/ARCHITECTURE.md
sec15 -- rule-driven access control replaces the masking walkthrough)."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scalene.hook_adapter import pre_tool_use
from scalene.onboard import onboard
from scalene.policy_config import PolicyConfig

GETTING_STARTED_DOC = Path(__file__).resolve().parent.parent / "docs" / "GETTING_STARTED.md"
README_DOC = Path(__file__).resolve().parent.parent / "README.md"


class TestGettingStartedDocs(unittest.TestCase):
    def test_doc_exists(self):
        self.assertTrue(GETTING_STARTED_DOC.exists())

    def test_documents_the_access_control_walkthrough(self):
        text = GETTING_STARTED_DOC.read_text()
        for term in (
            "scalene-guard",
            "pip install scalene-guard",
            "PreToolUse",
            ".scalene/audit.log",
            "hookSpecificOutput",
            "permissionDecision",
            "scg onboard",
            "mode: allow",
        ):
            self.assertIn(term, text)

    def test_readme_links_instead_of_duplicating(self):
        text = README_DOC.read_text()
        self.assertIn("docs/GETTING_STARTED.md", text)

    def test_walkthrough_scenario_actually_blocks_then_allows(self):
        """Replays the doc's exact scenario (Read -> WebFetch blocked ->
        onboard + rule -> WebFetch allowed) against the real hook adapter,
        so this test breaks (not the doc, silently) if the access-control
        decision or its messaging ever changes."""
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            audit_log = state_dir / "audit.log"
            cache_path = state_dir / "scan_cache.json"
            config = PolicyConfig()

            first = pre_tool_use(
                {"session_id": "demo", "tool_name": "Read", "tool_input": {"file_path": "secret.txt"}},
                config,
                state_dir=state_dir,
                audit_log_path=audit_log,
                cache_path=cache_path,
            )
            self.assertEqual(first["hookSpecificOutput"]["permissionDecision"], "allow")

            second = pre_tool_use(
                {
                    "session_id": "demo",
                    "tool_name": "WebFetch",
                    "tool_input": {"url": "https://example.com", "prompt": "summarize this"},
                },
                config,
                state_dir=state_dir,
                audit_log_path=audit_log,
                cache_path=cache_path,
            )
            self.assertEqual(second["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn("systemMessage", second)

            policy_path = Path(tmp) / "scalene_policy.yaml"
            onboard("https://example.com", mode="allow", sensitivity="public", cache_path=cache_path, policy_path=policy_path)
            allow_config = PolicyConfig.from_yaml(policy_path)

            third = pre_tool_use(
                {
                    "session_id": "demo",
                    "tool_name": "WebFetch",
                    "tool_input": {"url": "https://example.com", "prompt": "summarize this"},
                },
                allow_config,
                state_dir=state_dir,
                audit_log_path=audit_log,
                cache_path=cache_path,
            )
            self.assertEqual(third["hookSpecificOutput"]["permissionDecision"], "allow")


if __name__ == "__main__":
    unittest.main()
