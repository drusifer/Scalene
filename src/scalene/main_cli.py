"""`scalene` — developer-facing CLI. Currently one subcommand: `scalene onboard`."""

from __future__ import annotations

import sys

from .onboard import main as onboard_main

_SUBCOMMANDS = {"onboard": onboard_main}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in _SUBCOMMANDS:
        print(f"usage: scalene <{'|'.join(_SUBCOMMANDS)}> ...", file=sys.stderr)
        return 2
    subcommand, rest = argv[0], argv[1:]
    return _SUBCOMMANDS[subcommand](rest)


if __name__ == "__main__":
    sys.exit(main())
