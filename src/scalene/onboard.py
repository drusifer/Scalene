"""`scg onboard` CLI (STORY-501): unblock a false-positive without hand-editing YAML.

Allowlist onboarding runs a secrets scan on the target file first; trust-list
onboarding runs a reputation check on the target domain first. Both scans run
in an isolated subprocess (STORY-601). On success the rule is appended to
scalene_policy.yaml and a confirmation + diff + audit log entry are produced
(Smith Gate 1 follow-up).
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

import yaml

from .policy_config import PolicyConfigError, PolicyRule
from .subprocess_isolation import run_scanner

DEFAULT_POLICY_PATH = Path("scalene_policy.yaml")
DEFAULT_AUDIT_LOG = Path(".scalene") / "audit.log"

_SECTION_BY_LIST_TYPE = {
    "allowlist": "non_sensitive_allowlist",
    "trust": "trusted_sources_list",
}


class OnboardError(Exception):
    """Raised when onboarding is blocked. The message is the clear, user-facing reason."""


def onboard(
    list_type: str,
    tool: str,
    jsonpath: str,
    pattern: str,
    target: str,
    description: str = "",
    policy_path: Path = DEFAULT_POLICY_PATH,
    audit_log_path: Path = DEFAULT_AUDIT_LOG,
) -> dict:
    """Returns {"rule": dict, "diff": str} on success. Raises OnboardError (no
    write) on failure."""
    section = _SECTION_BY_LIST_TYPE.get(list_type)
    if section is None:
        raise OnboardError(
            f"Unknown list_type {list_type!r} (expected one of {list(_SECTION_BY_LIST_TYPE)})"
        )

    scan_type = "secrets" if list_type == "allowlist" else "reputation"
    scan = run_scanner(scan_type, target)
    if not scan["ok"]:
        raise OnboardError(f"Onboarding blocked: {scan_type} check failed — {scan['reason']}")

    rule = {"tool": tool, "jsonpath": jsonpath, "pattern": pattern, "description": description}
    try:
        PolicyRule.from_dict(rule)
    except PolicyConfigError as exc:
        raise OnboardError(f"Onboarding blocked: invalid rule — {exc}") from exc

    before_text = policy_path.read_text() if policy_path.exists() else ""
    try:
        config_data = yaml.safe_load(before_text) if before_text else {}
    except yaml.YAMLError as exc:
        raise OnboardError(f"Onboarding blocked: existing {policy_path} is invalid YAML: {exc}") from exc
    config_data = config_data or {}
    config_data.setdefault(section, [])
    config_data[section].append(rule)

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
        f.write(json.dumps({"event": "onboard", "list_type": list_type, "rule": rule}) + "\n")

    return {"rule": rule, "diff": diff}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scg onboard")
    parser.add_argument("--list-type", required=True, choices=list(_SECTION_BY_LIST_TYPE))
    parser.add_argument("--tool", required=True)
    parser.add_argument("--jsonpath", required=True)
    parser.add_argument("--pattern", required=True)
    parser.add_argument("--target", required=True, help="file path (allowlist) or domain (trust)")
    parser.add_argument("--description", default="")
    parser.add_argument("--policy-path", default=str(DEFAULT_POLICY_PATH))
    args = parser.parse_args(argv)

    try:
        result = onboard(
            args.list_type,
            args.tool,
            args.jsonpath,
            args.pattern,
            args.target,
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
