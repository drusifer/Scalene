"""docs/GETTING_STARTED.md must exist and document the real mask-event walkthrough (STORY-901)."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scalene.hook_adapter import post_tool_use, pre_tool_use
from scalene.masking import MaskingEngine
from scalene.policy_config import PolicyConfig

GETTING_STARTED_DOC = Path(__file__).resolve().parent.parent / "docs" / "GETTING_STARTED.md"
README_DOC = Path(__file__).resolve().parent.parent / "README.md"
FAKE_SECRET = "AKIAIOSFODNN7EXAMPLE"  # AWS access-key-ID shape (detect-secrets recognizes this)


class TestGettingStartedDocs(unittest.TestCase):
    def test_doc_exists(self):
        self.assertTrue(GETTING_STARTED_DOC.exists())

    def test_documents_the_masking_walkthrough(self):
        text = GETTING_STARTED_DOC.read_text()
        for term in (
            "scalene-guard",
            "PreToolUse",
            "PostToolUse",
            "MASKED_BY_POLICY_PROVENANCE_GUARD",
            ".scalene/audit.log",
            "hookSpecificOutput",
            "permissionDecision",
        ):
            self.assertIn(term, text)

    def test_readme_links_instead_of_duplicating(self):
        text = README_DOC.read_text()
        self.assertIn("docs/GETTING_STARTED.md", text)
        self.assertNotIn("MASKED_BY_POLICY_PROVENANCE_GUARD", text)

    def test_walkthrough_scenario_actually_masks(self):
        """Replays the doc's exact 3-call scenario (Read -> PostToolUse -> WebFetch)
        against the real hook adapter, so this test breaks (not the doc, silently)
        if MaskingEngine.MASK_LITERAL or the masking trigger ever changes."""
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            audit_log = state_dir / "audit.log"
            config = PolicyConfig()

            first = pre_tool_use(
                {"session_id": "demo", "tool_name": "Read", "tool_input": {"file_path": "secret.txt"}},
                config,
                state_dir=state_dir,
                audit_log_path=audit_log,
            )
            self.assertEqual(first["hookSpecificOutput"]["permissionDecision"], "allow")
            self.assertNotIn("systemMessage", first)

            post_tool_use(
                {
                    "session_id": "demo",
                    "tool_name": "Read",
                    "tool_response": {"content": FAKE_SECRET},
                },
                config,
                state_dir=state_dir,
            )

            second = pre_tool_use(
                {
                    "session_id": "demo",
                    "tool_name": "WebFetch",
                    "tool_input": {"url": "https://example.com", "prompt": FAKE_SECRET},
                },
                config,
                state_dir=state_dir,
                audit_log_path=audit_log,
            )
            self.assertEqual(
                second["hookSpecificOutput"]["updatedInput"]["prompt"], MaskingEngine.MASK_LITERAL
            )
            self.assertIn("systemMessage", second)


if __name__ == "__main__":
    unittest.main()
