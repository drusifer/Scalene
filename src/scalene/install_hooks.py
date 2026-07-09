"""`scalene install-hooks`: wire scalene-guard into a project's
`.claude/settings.json` PreToolUse/PostToolUse hooks (docs/SETUP.md).

Merges non-destructively: existing settings, other tool matchers, and other
commands already registered on the `*` matcher are all preserved. Idempotent —
running it again does not duplicate the scalene-guard entry.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HOOK_COMMAND = "scalene-guard"
DEFAULT_SETTINGS_PATH = Path(".claude") / "settings.json"
_HOOK_EVENTS = ("PreToolUse", "PostToolUse")


def _merge_event(entries: list, changed: list[bool]) -> list:
    star_entry = next((e for e in entries if e.get("matcher") == "*"), None)
    if star_entry is None:
        entries.append({"matcher": "*", "hooks": [{"type": "command", "command": HOOK_COMMAND}]})
        changed.append(True)
        return entries

    commands = [h.get("command") for h in star_entry.setdefault("hooks", [])]
    if HOOK_COMMAND not in commands:
        star_entry["hooks"].append({"type": "command", "command": HOOK_COMMAND})
        changed.append(True)
    return entries


def install_hooks(settings_path: Path = DEFAULT_SETTINGS_PATH) -> dict:
    """Returns {"changed": bool, "settings_path": str}. Raises ValueError on
    malformed existing JSON rather than silently overwriting it."""
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text())
        except json.JSONDecodeError as exc:
            raise ValueError(f"Existing {settings_path} is invalid JSON: {exc}") from exc
    else:
        data = {}

    hooks = data.setdefault("hooks", {})
    changed: list[bool] = []
    for event in _HOOK_EVENTS:
        hooks[event] = _merge_event(hooks.setdefault(event, []), changed)

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(data, indent=2) + "\n")

    return {"changed": any(changed), "settings_path": str(settings_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scalene install-hooks")
    parser.add_argument("--settings-path", default=str(DEFAULT_SETTINGS_PATH))
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    result = install_hooks(Path(args.settings_path))
    if result["changed"]:
        print(f"Installed scalene-guard PreToolUse/PostToolUse hooks in {result['settings_path']}")
    else:
        print(f"scalene-guard hooks already present in {result['settings_path']} — nothing to do")
    return 0


if __name__ == "__main__":
    sys.exit(main())
