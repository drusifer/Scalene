"""`scg` — developer-facing CLI. Subcommands: `onboard`, `install-hooks`, `monitor`."""

from __future__ import annotations

import sys

from .onboard import main as onboard_main
from .install_hooks import main as install_hooks_main
from .monitor import main as monitor_main

_SUBCOMMANDS = {"onboard": onboard_main, "install-hooks": install_hooks_main, "monitor": monitor_main}

_SUBCOMMAND_HELP = (
    ("install-hooks", "Wire scalene-guard into .claude/settings.json PreToolUse/PostToolUse hooks"),
    ("onboard", "Verify targets from a tool call and write an explicit rule to scalene_policy.yaml"),
    ("monitor", "Launch the interactive approval-queue TUI (requires scalene-guard[monitor])"),
)


def _usage_text() -> str:
    lines = [
        f"usage: scg <{'|'.join(_SUBCOMMANDS)}> [options]",
        "",
        "subcommands:",
    ]
    for name, desc in _SUBCOMMAND_HELP:
        lines.append(f"  {name:<15} {desc}")
    lines.append("")
    lines.append("Run 'scg <subcommand> --help' for subcommand options.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ("-h", "--help"):
        print(_usage_text())
        return 0
    if not argv or argv[0] not in _SUBCOMMANDS:
        print(f"usage: scg <{'|'.join(_SUBCOMMANDS)}> ...", file=sys.stderr)
        return 2
    subcommand, rest = argv[0], argv[1:]
    return _SUBCOMMANDS[subcommand](rest)


if __name__ == "__main__":
    sys.exit(main())
