"""`scg onboard` CLI (STORY-501): unblock a false-positive without hand-editing YAML.

One unified allowlist, keyed by the URI scheme of `--target` (2026-07-14
simplification — previously a separate `--list-type {allowlist,trust}` flag
plus two different `--target` meanings depending on it):

- `file://<path>` — runs a secrets scan on that local path first (STORY-601,
  isolated subprocess). On success, the rule counts as "not sensitive".
- `http://<host>` / `https://<host>` — runs a reputation check on that host
  first. On success, the rule counts as "trusted destination".

On success the rule is appended to scalene_policy.yaml's single `allowlist`
and a confirmation + diff + audit log entry are produced (Smith Gate 1
follow-up).
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

from .subprocess_isolation import run_scanner

DEFAULT_POLICY_PATH = Path("scalene_policy.yaml")
DEFAULT_AUDIT_LOG = Path(".scalene") / "audit.log"


class OnboardError(Exception):
    """Raised when onboarding is blocked. The message is the clear, user-facing reason."""


# PolicyRule/allowlist (validation via PolicyRule.from_dict) was removed
# from policy_config.py in Sprint 4 Phase 3 (docs/ARCHITECTURE.md sec13.1 --
# full replacement, not coexistence). This CLI's own re-scope (drop
# --tool/--jsonpath/--pattern/--description, write directly into the scan
# cache instead of scalene_policy.yaml's allowlist, sec13.4) is explicitly
# Phase 4 scope, not this phase's -- this is a minimal inline stand-in for
# the validation PolicyRule.from_dict used to do, only so `scg onboard`
# keeps working (and its tests keep passing) in the gap between the two
# phases, not a preview of Phase 4's real design.
_REQUIRED_RULE_FIELDS = ("tool", "jsonpath", "pattern", "target")


def _validate_rule_shim(rule: dict) -> None:
    missing = [k for k in _REQUIRED_RULE_FIELDS if not rule.get(k)]
    if missing:
        raise OnboardError(f"Onboarding blocked: invalid rule — missing required field(s) {missing}: {rule!r}")


def _resolve_scan(target: str) -> tuple[str, str]:
    """URI-scheme dispatch: returns (scan_type, value_to_scan) for `target`.
    Raises OnboardError for any scheme other than file/http/https."""
    parsed = urlparse(target)
    if parsed.scheme == "file":
        return "secrets", target[len("file://") :]
    if parsed.scheme in ("http", "https"):
        return "reputation", parsed.hostname or ""
    raise OnboardError(
        f"--target must be a file://, http://, or https:// URI (got {target!r})"
    )


def onboard(
    target: str,
    tool: str,
    jsonpath: str,
    pattern: str,
    description: str = "",
    policy_path: Path = DEFAULT_POLICY_PATH,
    audit_log_path: Path = DEFAULT_AUDIT_LOG,
) -> dict:
    """Returns {"rule": dict, "diff": str} on success. Raises OnboardError (no
    write) on failure."""
    scan_type, scan_value = _resolve_scan(target)
    scan = run_scanner(scan_type, scan_value)
    if not scan["ok"]:
        raise OnboardError(f"Onboarding blocked: {scan_type} check failed — {scan['reason']}")

    rule = {"tool": tool, "jsonpath": jsonpath, "pattern": pattern, "target": target, "description": description}
    _validate_rule_shim(rule)

    before_text = policy_path.read_text() if policy_path.exists() else ""
    try:
        config_data = yaml.safe_load(before_text) if before_text else {}
    except yaml.YAMLError as exc:
        raise OnboardError(f"Onboarding blocked: existing {policy_path} is invalid YAML: {exc}") from exc
    config_data = config_data or {}
    config_data.setdefault("allowlist", [])
    config_data["allowlist"].append(rule)

    after_text = yaml.safe_dump(config_data, sort_keys=False)
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(after_text)

    diff = "\n".join(
        difflib.unified_diff(
            before_text.splitlines(),
            after_text.splitlines(),
            fromfile=str(policy_path),
            tofile=str(policy_path),
            lineterm="",
        )
    )

    audit_log_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_log_path.open("a") as f:
        f.write(json.dumps({"event": "onboard", "rule": rule}) + "\n")

    return {"rule": rule, "diff": diff}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scg onboard")
    parser.add_argument(
        "--target",
        required=True,
        help="file://<path> (runs a secrets scan) or http(s)://<host> (runs a reputation check)",
    )
    parser.add_argument("--tool", required=True)
    parser.add_argument("--jsonpath", required=True)
    parser.add_argument("--pattern", required=True)
    parser.add_argument("--description", default="")
    parser.add_argument("--policy-path", default=str(DEFAULT_POLICY_PATH))
    args = parser.parse_args(argv)

    try:
        result = onboard(
            args.target,
            args.tool,
            args.jsonpath,
            args.pattern,
            description=args.description,
            policy_path=Path(args.policy_path),
        )
    except OnboardError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Rule added: {result['rule']}")
    if result["diff"]:
        print(result["diff"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
