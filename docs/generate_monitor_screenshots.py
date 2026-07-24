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
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Same convention as tests/_env_guards.py -- keep this script's screenshot
# generation off the live network, no different a standard than the test suite's.
os.environ["SCALENE_SKIP_REMOTE_REPUTATION"] = "1"

OUT_DIR = Path(__file__).resolve().parent / "images"


async def _generate() -> None:
    from scalene.monitor_app import MonitorApp
    from scalene.scan_cache import ScanCache
    from scalene.scanner import Resource, ScanResult

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
        (state_dir / "f7e8d9c0.json").write_text(
            json.dumps({"session_id": "f7e8d9c0", "trust": "high", "sensitivity": "public"})
        )

        events = [
            {
                "event": "allow",
                "session_id": "a1b2c3d4",
                "tool_name": "Read",
                "tool_input": {"file_path": "/workspace/src/app.py"},
                "reason": "",
                "block_kind": None,
            },
            {
                "event": "allow",
                "session_id": "a1b2c3d4",
                "tool_name": "Bash",
                "tool_input": {"command": "pytest tests/"},
                "reason": "",
                "block_kind": None,
            },
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
            },
            {
                "event": "block",
                "session_id": "a1b2c3d4",
                "tool_name": "WebFetch",
                "tool_input": {"url": "https://known-bad.example.com/x"},
                "reason": (
                    "Blocked: https://known-bad.example.com/x (the scanner found a real "
                    "issue with it). Do not retry without a rule/config change."
                ),
                "block_kind": "confirmed_bad",
            },
        ]
        with audit_log.open("a") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

        cache = ScanCache(cache_path)
        cache.put(
            Resource(kind="file", identity="/workspace/src/app.py", scanner_name="secrets"),
            ScanResult(label="public"),
        )
        cache.put(
            Resource(kind="url", identity="https://internal-wiki.example.com", scanner_name="reputation"),
            ScanResult(label="trusted"),
        )

        OUT_DIR.mkdir(exist_ok=True)

        app = MonitorApp(
            state_dir=state_dir, audit_log_path=audit_log, cache_path=cache_path, policy_path=policy_path
        )
        async with app.run_test(size=(130, 42)) as pilot:
            app.poll_data()
            await pilot.pause()
            app.selected_session_id = "a1b2c3d4"
            app.refresh_events()
            await pilot.pause()
            (OUT_DIR / "monitor-main.svg").write_text(app.export_screenshot(title="scg monitor"))
            print("wrote monitor-main.svg")

            # Oldest queued review is the "uncleared" WebFetch block (FIFO).
            await pilot.press("r")
            await pilot.pause()
            (OUT_DIR / "monitor-review-dashboard.svg").write_text(
                app.export_screenshot(title="scg monitor — review")
            )
            print("wrote monitor-review-dashboard.svg")

            await pilot.click(app.screen.query_one("#verify-btn"))
            await pilot.pause()
            await pilot.click(app.screen.query_one("#allow-btn"))
            await pilot.pause()
            await pilot.pause()
            (OUT_DIR / "monitor-allow-form.svg").write_text(
                app.export_screenshot(title="scg monitor — allow")
            )
            print("wrote monitor-allow-form.svg")

    print(f"Screenshots written to {OUT_DIR}")


if __name__ == "__main__":
    asyncio.run(_generate())
