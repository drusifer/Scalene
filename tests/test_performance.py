"""Formal NFR-Performance verification (STORY-301, STORY-1003).

2026-07-14 (Sprint 4 Phase 3, docs/ARCHITECTURE.md sec13.3): the single
<15ms NFR is split into two, since resource identification + cache lookup
are now in the hot path:

- NFR-Perf-Steady-State (<15ms, unchanged): every identified resource has a
  fresh cache entry -- pure JSON-cache reads under a FileLock, no
  subprocess spawn, genuinely the same cost as pre-Sprint-4 code.
- NFR-Perf-FirstSighting (<25ms provisional, per newly-identified
  resource): a call that identifies a never-before-seen resource pays the
  real, measured cost of the fire-and-forget background-scan spawn
  (Morpheus's Phase 2 review measured ~6.6ms avg / ~16ms max in this
  environment; 25ms budget is deliberate headroom, not the raw number).
  This test must verify the provisional number for real, not assume it
  holds -- same "verify, don't assume" standard as the hook-contract
  exit-code work.
"""

import statistics
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scalene.hook_adapter import pre_tool_use
from scalene.policy_config import PolicyConfig
from scalene.scan_cache import ScanCache
from scalene.scanner import Resource, ScanResult

STEADY_STATE_BUDGET_MS = 15.0
FIRST_SIGHTING_BUDGET_MS_PER_RESOURCE = 25.0
WARMUP_ITERATIONS = 5
MEASURED_ITERATIONS = 100
FIRST_SIGHTING_MEASURED_ITERATIONS = 20


class TestPreToolUseSteadyStatePerformance(unittest.TestCase):
    def test_evaluation_with_fresh_cache_entries_stays_under_15ms_budget(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            cache_path = state_dir / "scan_cache.json"
            target_file = state_dir / "README.md"
            target_file.write_text("docs")

            # Representative call: identifies both a file and a URL resource
            # (not an empty config trivially short-circuiting) -- both
            # pre-cached as fresh, so every iteration takes the real
            # steady-state path (cache reads only, no subprocess spawn).
            cache = ScanCache(cache_path)
            cache.put(
                Resource(kind="file", identity=str(target_file), scanner_name="secrets"),
                ScanResult(label="public"),
            )
            cache.put(
                Resource(kind="url", identity="internal.example.com", scanner_name="reputation"),
                ScanResult(label="trusted"),
            )

            config = PolicyConfig()
            hook_input = {
                "session_id": "perf-session",
                "tool_name": "Bash",
                "tool_input": {"command": f"cat {target_file} && curl https://internal.example.com/api"},
            }

            for _ in range(WARMUP_ITERATIONS):
                pre_tool_use(hook_input, config, state_dir=state_dir, cache_path=cache_path)

            samples_ms = []
            for _ in range(MEASURED_ITERATIONS):
                start = time.perf_counter()
                pre_tool_use(hook_input, config, state_dir=state_dir, cache_path=cache_path)
                samples_ms.append((time.perf_counter() - start) * 1000)

            avg_ms = statistics.mean(samples_ms)
            median_ms = statistics.median(samples_ms)
            self.assertLess(
                avg_ms,
                STEADY_STATE_BUDGET_MS,
                f"avg={avg_ms:.3f}ms median={median_ms:.3f}ms exceeds {STEADY_STATE_BUDGET_MS}ms steady-state budget",
            )


class TestPreToolUseFirstSightingPerformance(unittest.TestCase):
    def test_first_sighting_stays_under_provisional_per_resource_budget(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            cache_path = state_dir / "scan_cache.json"
            config = PolicyConfig()

            samples_ms = []
            for i in range(FIRST_SIGHTING_MEASURED_ITERATIONS):
                # A distinct, never-cached path every iteration -- each call
                # identifies exactly 1 new file resource, so this measures
                # per-resource first-sighting cost directly.
                hook_input = {
                    "session_id": "perf-session",
                    "tool_name": "Bash",
                    "tool_input": {"command": f"cat /tmp/scalene-perf-test-{i}.md"},
                }
                start = time.perf_counter()
                pre_tool_use(hook_input, config, state_dir=state_dir, cache_path=cache_path)
                samples_ms.append((time.perf_counter() - start) * 1000)

            avg_ms = statistics.mean(samples_ms)
            max_ms = max(samples_ms)
            self.assertLess(
                avg_ms,
                FIRST_SIGHTING_BUDGET_MS_PER_RESOURCE,
                f"avg={avg_ms:.3f}ms max={max_ms:.3f}ms exceeds the "
                f"{FIRST_SIGHTING_BUDGET_MS_PER_RESOURCE}ms provisional NFR-Perf-FirstSighting budget",
            )


if __name__ == "__main__":
    unittest.main()
