"""Tests for `scalene install-hooks` (.claude/settings.json PreToolUse/PostToolUse wiring)."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scalene.install_hooks import HOOK_COMMAND, install_hooks


class TestInstallHooksFreshFile(unittest.TestCase):
    def test_creates_settings_file_with_both_hooks(self):
        with TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / ".claude" / "settings.json"
            result = install_hooks(settings_path)
            data = json.loads(settings_path.read_text())

            self.assertTrue(result["changed"])
            pre = data["hooks"]["PreToolUse"]
            post = data["hooks"]["PostToolUse"]
            self.assertEqual(pre[0]["matcher"], "*")
            self.assertIn({"type": "command", "command": HOOK_COMMAND}, pre[0]["hooks"])
            self.assertIn({"type": "command", "command": HOOK_COMMAND}, post[0]["hooks"])


class TestInstallHooksPreservesExisting(unittest.TestCase):
    def test_preserves_unrelated_top_level_settings(self):
        with TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / ".claude" / "settings.json"
            settings_path.parent.mkdir(parents=True)
            settings_path.write_text(json.dumps({"permissions": {"allow": ["Bash(ls:*)"]}}))

            install_hooks(settings_path)
            data = json.loads(settings_path.read_text())

            self.assertEqual(data["permissions"], {"permissions": {"allow": ["Bash(ls:*)"]}}["permissions"])
            self.assertIn("hooks", data)

    def test_preserves_other_matcher_entries(self):
        with TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / ".claude" / "settings.json"
            settings_path.parent.mkdir(parents=True)
            settings_path.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "PreToolUse": [
                                {"matcher": "Bash", "hooks": [{"type": "command", "command": "other-tool"}]}
                            ]
                        }
                    }
                )
            )

            install_hooks(settings_path)
            data = json.loads(settings_path.read_text())
            matchers = {entry["matcher"] for entry in data["hooks"]["PreToolUse"]}

            self.assertIn("Bash", matchers)
            self.assertIn("*", matchers)
            bash_entry = next(e for e in data["hooks"]["PreToolUse"] if e["matcher"] == "Bash")
            self.assertEqual(bash_entry["hooks"], [{"type": "command", "command": "other-tool"}])

    def test_appends_to_existing_star_matcher_without_removing_other_commands(self):
        with TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / ".claude" / "settings.json"
            settings_path.parent.mkdir(parents=True)
            settings_path.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "PreToolUse": [
                                {"matcher": "*", "hooks": [{"type": "command", "command": "some-other-guard"}]}
                            ]
                        }
                    }
                )
            )

            install_hooks(settings_path)
            data = json.loads(settings_path.read_text())
            star_entries = [e for e in data["hooks"]["PreToolUse"] if e["matcher"] == "*"]

            self.assertEqual(len(star_entries), 1)
            commands = [h["command"] for h in star_entries[0]["hooks"]]
            self.assertIn("some-other-guard", commands)
            self.assertIn(HOOK_COMMAND, commands)


class TestInstallHooksIdempotent(unittest.TestCase):
    def test_running_twice_does_not_duplicate(self):
        with TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / ".claude" / "settings.json"

            first = install_hooks(settings_path)
            second = install_hooks(settings_path)

            data = json.loads(settings_path.read_text())
            pre_commands = [h["command"] for e in data["hooks"]["PreToolUse"] for h in e["hooks"]]

            self.assertTrue(first["changed"])
            self.assertFalse(second["changed"])
            self.assertEqual(pre_commands.count(HOOK_COMMAND), 1)


class TestInstallHooksInvalidJson(unittest.TestCase):
    def test_malformed_existing_settings_raises_clear_error(self):
        with TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / ".claude" / "settings.json"
            settings_path.parent.mkdir(parents=True)
            settings_path.write_text("{not valid json")

            with self.assertRaises(ValueError):
                install_hooks(settings_path)


if __name__ == "__main__":
    unittest.main()
