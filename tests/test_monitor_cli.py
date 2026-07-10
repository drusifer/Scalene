"""Tests for `scalene monitor`'s CLI entrypoint (STORY-701) — specifically
the plain-language fallback when the optional `monitor` extra isn't
installed, since `textual` must never be a hard dependency of the base
package (docs/ARCHITECTURE.md sec 11.1)."""

import sys
import unittest
from unittest.mock import patch

from scalene import monitor


class TestMonitorMain(unittest.TestCase):
    def test_missing_textual_extra_prints_plain_language_install_hint(self):
        # Setting a sys.modules entry to None deterministically forces the
        # next `import`/`from ... import` of it to raise ImportError,
        # regardless of whether it's already cached from another test.
        with patch.dict(sys.modules, {"scalene.monitor_app": None}):
            with patch("sys.stderr") as mock_stderr:
                exit_code = monitor.main([])

        self.assertEqual(exit_code, 1)
        printed = "".join(call.args[0] for call in mock_stderr.write.call_args_list)
        self.assertIn("pip install scalene-guard[monitor]", printed)


if __name__ == "__main__":
    unittest.main()
