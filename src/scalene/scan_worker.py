"""Scanner subprocess entrypoint (STORY-601): runs in an isolated process,
invoked by subprocess_isolation.run_scanner with SCALENE_BYPASS=1 set.

Usage: python -m scalene.scan_worker <secrets|reputation> <target>
Prints a single JSON line to stdout: {"ok": bool, "reason": str}
"""

from __future__ import annotations

import json
import sys

from .reputation import LocalHeuristicChecker
from .secrets_scan import scan_text_for_secrets


def _scan_secrets(target: str) -> dict:
    text = open(target, encoding="utf-8", errors="replace").read()
    findings = scan_text_for_secrets(text)
    if findings:
        return {"ok": False, "reason": "; ".join(findings)}
    return {"ok": True, "reason": ""}


def _scan_reputation(target: str) -> dict:
    result = LocalHeuristicChecker().check(target)
    return {"ok": result.is_trusted, "reason": result.reason}


_SCANNERS = {"secrets": _scan_secrets, "reputation": _scan_reputation}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(json.dumps({"ok": False, "reason": f"usage: scan_worker <{'|'.join(_SCANNERS)}> <target>"}))
        return 2

    scan_type, target = argv
    scanner = _SCANNERS.get(scan_type)
    if scanner is None:
        print(json.dumps({"ok": False, "reason": f"unknown scan type: {scan_type}"}))
        return 2

    try:
        result = scanner(target)
    except Exception as exc:
        print(json.dumps({"ok": False, "reason": f"scan_worker error: {exc}"}))
        return 1

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
