"""Shared test-suite env-var guards. Not a test module itself (no `test_`
prefix -- not collected by `unittest discover`), imported explicitly by
files that need it.

docs/ARCHITECTURE.md sec18.3 (STORY-1503): reputation.composite_check() now
attempts a real external URLhaus call by default. That call happens inside
scan_worker.py's isolated subprocess (STORY-601) -- a real, separate process
no in-process mock can reach -- so the only way to keep this test suite's
standing no-live-network convention across that boundary is an env var the
child subprocess inherits (subprocess_isolation.run_scanner already copies
the parent's os.environ). Scoped via setUpModule/tearDownModule (restores
the previous value, never leaves it stuck on for other test modules).
"""

from __future__ import annotations

import os

_ENV_VAR = "SCALENE_SKIP_REMOTE_REPUTATION"
_saved: dict[str, str | None] = {}


def disable_remote_reputation() -> None:
    """Call from a test module's setUpModule()."""
    _saved["value"] = os.environ.get(_ENV_VAR)
    os.environ[_ENV_VAR] = "1"


def restore_remote_reputation() -> None:
    """Call from the same test module's tearDownModule()."""
    previous = _saved.pop("value", None)
    if previous is None:
        os.environ.pop(_ENV_VAR, None)
    else:
        os.environ[_ENV_VAR] = previous
