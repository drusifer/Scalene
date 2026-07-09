"""docs/SETUP.md must document hook registration (Task 4.1)."""

import unittest
from pathlib import Path

SETUP_DOC = Path(__file__).resolve().parent.parent / "docs" / "SETUP.md"


class TestSetupDocs(unittest.TestCase):
    def test_setup_doc_exists(self):
        self.assertTrue(SETUP_DOC.exists())

    def test_documents_hook_registration(self):
        text = SETUP_DOC.read_text()
        for term in ("PreToolUse", "PostToolUse", "scalene-guard", ".claude/settings.json"):
            self.assertIn(term, text)


if __name__ == "__main__":
    unittest.main()
