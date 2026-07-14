"""docs/USER_GUIDE.md must exist and its CLI reference must match real --help
output, not memory/source transcription (STORY-902)."""

import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from scalene.cli import main as guard_main
from scalene.install_hooks import main as install_hooks_main
from scalene.onboard import main as onboard_main

USER_GUIDE_DOC = Path(__file__).resolve().parent.parent / "docs" / "USER_GUIDE.md"
README_DOC = Path(__file__).resolve().parent.parent / "README.md"


def _help_output(main_func) -> str:
    out = io.StringIO()
    with redirect_stdout(out):
        with unittest.TestCase().assertRaises(SystemExit):
            main_func(["--help"])
    return out.getvalue()


class TestUserGuideDocs(unittest.TestCase):
    def setUp(self):
        self.text = USER_GUIDE_DOC.read_text()

    def test_doc_exists(self):
        self.assertTrue(USER_GUIDE_DOC.exists())

    def test_documents_all_four_commands(self):
        for term in ("scalene-guard", "scg onboard", "scg install-hooks", "scg monitor"):
            self.assertIn(term, self.text)

    def test_documents_troubleshooting_and_fail_safe(self):
        for term in ("fail safe", "Troubleshooting", "malformed", "never crashes"):
            self.assertIn(term, self.text)

    def test_documents_onboard_suggestion_workflow(self):
        self.assertIn("systemMessage", self.text)
        self.assertIn("suggested", self.text.lower())

    def test_readme_links_to_guide(self):
        self.assertIn("docs/USER_GUIDE.md", README_DOC.read_text())

    def test_guard_flags_match_real_help_output(self):
        real_help = _help_output(guard_main)
        for flag in ("--policy-path", "--state-dir"):
            self.assertIn(flag, real_help)
            self.assertIn(flag, self.text)

    def test_onboard_flags_match_real_help_output(self):
        real_help = _help_output(onboard_main)
        for flag in ("--target", "--tool", "--jsonpath", "--pattern", "--description", "--policy-path"):
            self.assertIn(flag, real_help)
            self.assertIn(flag, self.text)

    def test_install_hooks_flags_match_real_help_output(self):
        real_help = _help_output(install_hooks_main)
        self.assertIn("--settings-path", real_help)
        self.assertIn("--settings-path", self.text)


if __name__ == "__main__":
    unittest.main()
