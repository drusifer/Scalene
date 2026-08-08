"""Shared fast-async test base. Not a test module itself (no `test_`
prefix -- not collected by `unittest discover`), imported explicitly by
files that need it.

Direct user request (2026-08-08, measured not assumed): `unittest.
IsolatedAsyncioTestCase` unconditionally constructs its runner with
`asyncio.Runner(debug=True)` (stdlib default since 3.11, no override hook)
-- `debug=True` calls `loop.set_debug(True)`, which enables asyncio's
slow-callback detector and adds real per-callback overhead. Measured ~2.4x
slower than the same Textual `run_test()` scenario with debug off, and is
the source of every `Executing <Task ...> took N seconds` line in this
project's build logs. `FastIsolatedAsyncioTestCase` overrides
`_setupAsyncioRunner` (private stdlib method, not a public override point --
if a future Python version renames/removes it, this falls back to stock
`debug=True` behavior harmlessly, just slower again) to leave `debug`
unset, matching `asyncio.Runner`'s own real default.
"""

from __future__ import annotations

import asyncio
import unittest


class FastIsolatedAsyncioTestCase(unittest.IsolatedAsyncioTestCase):
    def _setupAsyncioRunner(self):
        assert self._asyncioRunner is None, "asyncio runner is already initialized"
        self._asyncioRunner = asyncio.Runner(loop_factory=self.loop_factory)
