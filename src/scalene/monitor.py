"""`scalene monitor` (STORY-701): live TUI over `.scalene/audit.log` and
taint state. Requires the optional `monitor` extra
(`pip install scalene-guard[monitor]`) — kept out of the base package so the
hot-path hook adapter never imports a TUI framework it doesn't use
(docs/ARCHITECTURE.md sec 11.1).
"""

from __future__ import annotations

import sys


def main(argv: list[str]) -> int:
    del argv  # no flags yet — Phase 2 scope is the console itself, not options
    try:
        from .monitor_app import MonitorApp
    except ImportError:
        print(
            "scalene monitor requires the optional 'monitor' extra: pip install scalene-guard[monitor]",
            file=sys.stderr,
        )
        return 1

    MonitorApp().run()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
