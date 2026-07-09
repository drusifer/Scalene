"""Scanner subprocess isolation (STORY-601).

Spawns the scanner as a separate process (not a container — architecture §6)
with SCALENE_BYPASS=1 set, so a compromised/misbehaving scanner can't itself
become a new leak vector, and so its actions don't recursively re-trigger the
interception hooks.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

_KNOWN_SCAN_TYPES = {"secrets", "reputation"}


def run_scanner(scan_type: str, target: str) -> dict:
    """Never raises — any failure (unknown scan type, subprocess error, bad
    output) fails safe with ok=False and a clear reason."""
    if scan_type not in _KNOWN_SCAN_TYPES:
        return {"ok": False, "reason": f"unknown scan type: {scan_type}"}

    env = os.environ.copy()
    env["SCALENE_BYPASS"] = "1"

    try:
        completed = subprocess.run(
            [sys.executable, "-m", "scalene.scan_worker", scan_type, target],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
    except Exception as exc:
        return {"ok": False, "reason": f"scanner subprocess failed to run: {exc}"}

    try:
        return json.loads(completed.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        return {"ok": False, "reason": f"scanner subprocess returned malformed output: {exc}"}
