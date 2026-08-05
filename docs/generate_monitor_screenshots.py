#!/usr/bin/env python3
"""Generates real screenshots of `scg monitor` for docs/MONITOR_GUIDE.md.

Boots the real `MonitorApp` via Textual's headless test harness (the same
mechanism `tests/test_monitor_app.py` uses) against seeded, realistic data,
and exports real SVG screenshots via `App.export_screenshot()` -- not
mockups or hand-drawn diagrams. Re-run whenever the TUI's appearance
changes materially; the doc's screenshots are only trustworthy if they
match what the app actually renders.

Usage: python docs/generate_monitor_screenshots.py
Output: docs/images/monitor-*.svg
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Same convention as tests/_env_guards.py -- keep this script's screenshot
# generation off the live network, no different a standard than the test suite's.
os.environ["SCALENE_SKIP_REMOTE_REPUTATION"] = "1"

OUT_DIR = Path(__file__).resolve().parent / "images"


async def _generate() -> None:
    import yaml

    from scalene.monitor_app import MonitorApp
    from scalene.scan_cache import ScanCache
    from scalene.scanner import Resource, ScanResult
    from textual.widgets import DataTable

    with TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        state_dir = tmp / "state"
        state_dir.mkdir()
        audit_log = tmp / "audit.log"
        cache_path = tmp / "scan_cache.json"
        policy_path = tmp / "scalene_policy.yaml"

        (state_dir / "a1b2c3d4.json").write_text(
            json.dumps({"session_id": "a1b2c3d4", "trust": "low", "sensitivity": "internal"})
        )

        now = time.time()
        events = [
            {
                "event": "block",
                "session_id": "a1b2c3d4",
                "tool_name": "WebFetch",
                "tool_input": {"url": "https://unknown-saas.example.com/api"},
                "reason": (
                    "Blocked: https://unknown-saas.example.com/api has no validated, "
                    "explicitly-allowed rule, and this session has already touched "
                    "sensitive/untrusted data (trust=low, sensitivity=internal). "
                    "Wait for review, then retry."
                ),
                "block_kind": "uncleared",
                "ts": now - 125,
            },
            {
                "event": "block",
                "session_id": "a1b2c3d4",
                "tool_name": "Read",
                "tool_input": {"file_path": "/workspace/src/secrets.env"},
                "reason": (
                    "Blocked: /workspace/src/secrets.env (the scanner found a real "
                    "issue with it). Do not retry without a rule/config change."
                ),
                "block_kind": "confirmed_bad",
                "ts": now - 12,
            },
        ]
        with audit_log.open("a") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

        # One completed scan (secrets idle) and one in-flight reservation
        # (reputation busy) -- the status strip shows a real mixed state,
        # not both idle.
        cache = ScanCache(cache_path)
        cache.put(
            Resource(kind="file", identity="/workspace/src/app.py", scanner_name="secrets"),
            ScanResult(label="public"),
        )
        cache.try_reserve(Resource(kind="url", identity="internal-wiki.example.com", scanner_name="reputation"))

        # A real 2-rule policy file for the Rules screen screenshot -- order
        # matters (first-match-wins), shown as-is.
        policy_path.write_text(
            yaml.safe_dump(
                {
                    "rules": [
                        {
                            "tool": ".*",
                            "pattern": "/workspace/**",
                            "sensitivity": "internal",
                            "mode": "allow",
                            "description": "project folder default (auto-created)",
                        },
                        {
                            "tool": "Bash",
                            "pattern": "/etc/**",
                            "sensitivity": "restricted",
                            "mode": "block",
                        },
                    ]
                },
                sort_keys=False,
                default_flow_style=False,
            )
        )

        OUT_DIR.mkdir(exist_ok=True)

        app = MonitorApp(
            state_dir=state_dir, audit_log_path=audit_log, cache_path=cache_path, policy_path=policy_path
        )
        async with app.run_test(size=(130, 42)) as pilot:
            app.poll_data()
            await pilot.pause()
            (OUT_DIR / "monitor-main.svg").write_text(app.export_screenshot(title="scg monitor"))
            print("wrote monitor-main.svg")

            # Open the oldest queued review (row 0 -- the queue is FIFO).
            table = app.query_one("#queue", DataTable)
            table.move_cursor(row=0)
            await pilot.press("enter")
            await pilot.pause()
            (OUT_DIR / "monitor-review-dashboard.svg").write_text(
                app.export_screenshot(title="scg monitor — review")
            )
            print("wrote monitor-review-dashboard.svg")

            await pilot.click(app.screen.query_one("#verify-btn"))
            await pilot.pause()
            (OUT_DIR / "monitor-review-verified.svg").write_text(
                app.export_screenshot(title="scg monitor — review (verified)")
            )
            print("wrote monitor-review-verified.svg")

            await pilot.press("escape")
            await pilot.pause()
            await pilot.press("r")
            await pilot.pause()
            (OUT_DIR / "monitor-rules.svg").write_text(app.export_screenshot(title="scg monitor — rules"))
            print("wrote monitor-rules.svg")

    print(f"Screenshots written to {OUT_DIR}")


if __name__ == "__main__":
    asyncio.run(_generate())
