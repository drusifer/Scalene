"""`scg monitor` (STORY-701): live TUI over `.scalene/audit.log` and
taint state. Requires the optional `monitor` extra
(`pip install scalene-guard[monitor]`) — kept out of the base package so the
hot-path hook adapter never imports a TUI framework it doesn't use
(docs/ARCHITECTURE.md sec 11.1).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hook_adapter import DEFAULT_AUDIT_LOG
from .onboard import DEFAULT_POLICY_PATH
from .scan_cache import DEFAULT_CACHE_PATH
from .taint_state import DEFAULT_STATE_DIR


def main(argv: list[str]) -> int:
    # 2026-07-30 (direct user report: "monitor decisions not persisting
    # across sessions"): all 4 defaults below are relative to the current
    # working directory at launch, same as scalene-guard's own hook-adapter
    # defaults (cli.py) -- correct for a hook Claude Code invokes from a
    # fixed project root, but `scg monitor` is launched by hand in a
    # separate terminal, where a different cwd between runs (or between the
    # monitor and whatever cwd scalene-guard is actually running from)
    # silently points it at a different .scalene/ and scalene_policy.yaml
    # entirely -- indistinguishable from "it forgot." These flags (matching
    # `scg onboard`'s existing --policy-path/--cache-path names) let an
    # operator pin it explicitly; MonitorApp also now shows the resolved
    # absolute paths in its own sub_title so a cwd mismatch is visible
    # rather than silent.
    parser = argparse.ArgumentParser(prog="scg monitor")
    parser.add_argument("--policy-path", default=str(DEFAULT_POLICY_PATH))
    parser.add_argument("--cache-path", default=str(DEFAULT_CACHE_PATH))
    parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    parser.add_argument("--audit-log-path", default=str(DEFAULT_AUDIT_LOG))
    args = parser.parse_args(argv)

    try:
        from .monitor_app import MonitorApp
    except ImportError:
        print(
            'scg monitor requires the optional \'monitor\' extra: pip install "scalene-guard[monitor]"',
            file=sys.stderr,
        )
        return 1

    MonitorApp(
        state_dir=Path(args.state_dir),
        audit_log_path=Path(args.audit_log_path),
        cache_path=Path(args.cache_path),
        policy_path=Path(args.policy_path),
    ).run()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
