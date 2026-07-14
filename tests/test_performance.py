"""Formal NFR-Performance verification (STORY-301): hook evaluation (rule match
+ decision) must complete in <15ms. Supersedes the informal sanity checks done
during Phase 2/3 review — this is Task 4.2's explicit deliverable.
"""

import statistics
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scalene.hook_adapter import pre_tool_use
from scalene.policy_config import PolicyConfig, PolicyRule

PERF_BUDGET_MS = 15.0
WARMUP_ITERATIONS = 5
MEASURED_ITERATIONS = 100


def _representative_config() -> PolicyConfig:
    # A handful of rules, not an empty config — an empty config trivially
    # short-circuits and would understate real-world evaluation cost.
    return PolicyConfig(
        allowlist=[
            PolicyRule(tool="Read", jsonpath="$.file_path", pattern=r"\.md$", target="file:///workspace/docs"),
            PolicyRule(tool="Read", jsonpath="$.file_path", pattern=r"\.txt$", target="file:///workspace/docs"),
            PolicyRule(tool="Bash", jsonpath="$.command", pattern=r"^git status", target="file:///workspace/docs"),
            PolicyRule(
                tool="WebFetch",
                jsonpath="$.url",
                pattern=r"^https://internal\.example\.com/",
                target="https://internal.example.com",
            ),
            PolicyRule(tool="Bash", jsonpath="$.command", pattern=r"^git ", target="https://github.com"),
        ],
    )


class TestPreToolUsePerformance(unittest.TestCase):
    def test_evaluation_stays_under_15ms_budget(self):
        config = _representative_config()
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            hook_input = {
                "session_id": "perf-session",
                "tool_name": "Bash",
                "tool_input": {"command": "git status"},
            }

            for _ in range(WARMUP_ITERATIONS):
                pre_tool_use(hook_input, config, state_dir=state_dir)

            samples_ms = []
            for _ in range(MEASURED_ITERATIONS):
                start = time.perf_counter()
                pre_tool_use(hook_input, config, state_dir=state_dir)
                samples_ms.append((time.perf_counter() - start) * 1000)

            avg_ms = statistics.mean(samples_ms)
            median_ms = statistics.median(samples_ms)
            self.assertLess(
                avg_ms,
                PERF_BUDGET_MS,
                f"avg={avg_ms:.3f}ms median={median_ms:.3f}ms exceeds {PERF_BUDGET_MS}ms budget",
            )


if __name__ == "__main__":
    unittest.main()
