"""`scg` — developer-facing CLI. Subcommands: `onboard`, `install-hooks`, `monitor`."""

from __future__ import annotations

import sys

from .onboard import main as onboard_main
from .install_hooks import main as install_hooks_main
from .monitor import main as monitor_main

_SUBCOMMANDS = {"onboard": onboard_main, "install-hooks": install_hooks_main, "monitor": monitor_main}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in _SUBCOMMANDS:
        print(f"usage: scg <{'|'.join(_SUBCOMMANDS)}> ...", file=sys.stderr)
        return 2
    subcommand, rest = argv[0], argv[1:]
    return _SUBCOMMANDS[subcommand](rest)


if __name__ == "__main__":
    sys.exit(main())
