"""Scanner subprocess entrypoint (STORY-601): runs in an isolated process,
invoked by subprocess_isolation.run_scanner with SCALENE_BYPASS=1 set.

Usage: python -m scalene.scan_worker <secrets|reputation> <target>
Prints a single JSON line to stdout: {"ok": bool, "reason": str}
"""

from __future__ import annotations

import json
import os
import sys

from .reputation import composite_check
from .secrets_scan import scan_text_for_secrets


def _scan_file(path: str) -> list[str]:
    text = open(path, encoding="utf-8", errors="replace").read()
    return scan_text_for_secrets(text)


def _scan_secrets(target: str) -> dict:
    if os.path.isdir(target):
        # A directory target (e.g. Verify pressed on a folder in `scg
        # monitor`) scans every file underneath it, not just the target
        # path itself -- previously open(target) raised IsADirectoryError,
        # surfacing as a ScannerMachineryError that silently left the
        # dashboard row unverified (monitor_app.py's action_verify()
        # catches that error and continues). A single unreadable file
        # (permission denied, broken symlink) is skipped rather than
        # failing the whole directory, so one bad entry can't block
        # verifying the rest of the tree.
        findings: list[str] = []
        for root, _dirs, files in os.walk(target):
            for name in files:
                path = os.path.join(root, name)
                try:
                    file_findings = _scan_file(path)
                except OSError:
                    continue
                if file_findings:
                    findings.append(f"{path}: {'; '.join(file_findings)}")
        if findings:
            return {"ok": False, "reason": "; ".join(findings)}
        return {"ok": True, "reason": ""}

    findings = _scan_file(target)
    if findings:
        return {"ok": False, "reason": "; ".join(findings)}
    return {"ok": True, "reason": ""}


def _scan_reputation(target: str) -> dict:
    # sec18.3 (STORY-1503): composite_check() always runs the free, offline
    # heuristics and additionally attempts a real external reputation source
    # (URLhaus), degrading visibly to local-only if that source is
    # unreachable -- this runs inside this same isolated subprocess
    # boundary (STORY-601), the right place for a new outbound network call.
    result = composite_check(target)
    return {"ok": result.is_trusted, "reason": result.reason, "reputation": result.score}


_SCANNERS = {"secrets": _scan_secrets, "reputation": _scan_reputation}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(json.dumps({"ok": False, "reason": f"usage: scan_worker <{'|'.join(_SCANNERS)}> <target>", "machinery_error": True}))
        return 2

    scan_type, target = argv
    scanner = _SCANNERS.get(scan_type)
    if scanner is None:
        print(json.dumps({"ok": False, "reason": f"unknown scan type: {scan_type}", "machinery_error": True}))
        return 2

    try:
        result = scanner(target)
    except Exception as exc:
        # The scan itself couldn't run (e.g. target unreadable) -- distinct
        # from a real finding (STORY-1004: this is what makes Scanner.scan()
        # raise ScannerMachineryError at the caller, not return a ScanResult).
        print(json.dumps({"ok": False, "reason": f"scan_worker error: {exc}", "machinery_error": True}))
        return 1

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
