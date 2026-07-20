"""`scg onboard` CLI (STORY-501).

2026-07-18 (direct user design session, post-Sprint-6): re-scoped again --
`scg onboard` is now the frontend for authoring a `PolicyRule`, not just a
cache-seeding utility. Previously (Sprint 4, sec13.4) onboarding only ran a
real scan and pre-seeded `.scalene/scan_cache.json`; declaring what to
actually *do* with a verified resource (the `rules:` entry) was left as a
separate, undiscoverable, hand-edit-the-YAML step. The user found this
confusing while reading the docs: `--target` reads like it should express
a whole rule, but it only ever meant "verify this one thing." Their own
framing: "scg onboard is effectively saying: when a tool call matches
these conditions, apply these context labels."

A single `scg onboard` call now both validates (real scan, unchanged) and
declares (writes a `rules:` entry) in one action. CLI flag names match
`PolicyRule`'s field names exactly (tool/pattern/sensitivity/mode/scanner/
description) -- no separate vocabulary between the CLI and the YAML
schema. `--pattern` defaults to an exact match on the resolved resource
(narrow, safe -- same scope as pre-2026-07-18 onboarding); `--tool`
defaults to ".*" (any tool). At least one of `--sensitivity`/`--mode`
must be provided -- onboarding is the moment a human declares a trust
decision, so silently defaulting both away would quietly recreate an
implicit-default-rule pattern this project has deliberately avoided
elsewhere (docs/ARCHITECTURE.md sec14.4's amendment). Whichever one is
omitted gets a sensible default (mode: allow, sensitivity: public).

`mode: block` is a real, distinct use case, not just "allow"'s opposite:
declaring a known-bad resource blocked, backed by a real scan finding
rather than relying purely on fail-safe machinery. A bad scan result
blocks onboarding when requesting `mode: allow` (unchanged from before --
can't claim something is safe when the scanner says otherwise), but does
NOT block a `mode: block` request -- that is exactly the case it exists
to cover. The scan cache always reflects the real, honest finding
regardless of which mode was requested.

Rule construction reuses `PolicyRule`'s own validation (regex compile
checks, sensitivity/mode/scanner membership) rather than duplicating it --
an invalid `--scanner` typo, say, fails exactly the same way a
hand-authored rule would.

Known limitation: writing the rule re-parses and re-serializes the whole
policy YAML file (`yaml.safe_load` + `yaml.safe_dump`) -- any hand-added
comments in an existing `scalene_policy.yaml` will not survive an
onboard-triggered rewrite. Traded deliberately for correctness (a fragile
text-append approach risks corrupting the file if `rules:` isn't its last
section) over cosmetic preservation.

STORY-1004: a scanner-machinery failure (ScannerMachineryError) or a
broken cache store (ScanCacheError) both surface as a real OnboardError
here too -- pre-seeding must fail loudly, not silently succeed with a
wrong/missing cache entry.

2026-07-20 (Smith's sec16 gate, `*user bug`): `main()`'s --help gave no
signal that --sensitivity/--mode have an OR-requirement -- argparse shows
both as independently optional, so the naive pre-2026-07-18 muscle-memory
command (`--target` alone) always failed on first try with no way to know
why beforehand. Added an epilog disclosing both this and why --mode
rejects 'mask' (the latter bundling Trin's related finding: argparse's
choices= rejected 'mask' before onboard()'s own detailed rationale could
ever fire for a real CLI invocation). The runtime error messages were
already correct; this only makes the constraints reachable via --help
before a user has to trigger the error to learn them.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

from .policy_config import PolicyConfigError, PolicyRule, VALID_SENSITIVITIES
from .scan_cache import DEFAULT_CACHE_PATH, ScanCache, ScanCacheError
from .scanner import SCANNERS, Resource, ScannerMachineryError

DEFAULT_POLICY_PATH = Path("scalene_policy.yaml")

_BLOCKED_LABELS = ("sensitive", "untrusted")
# 'mask' is deliberately excluded -- see onboard()'s docstring/comment for why.
_ONBOARD_VALID_MODES = ("allow", "block")


class OnboardError(Exception):
    """Raised when onboarding is blocked. The message is the clear, user-facing reason."""


def _resolve_resource(target: str) -> Resource:
    """URI-scheme dispatch: returns the Resource to scan for `target`.
    Raises OnboardError for any scheme other than file/http/https.

    File identities are normalized via os.path.abspath -- the same
    normalization FileScanner.identify() applies during live evaluation --
    so a resource pre-seeded here uses the exact same cache key a real
    hook call would look up. URL identities (docs/ARCHITECTURE.md
    sec14.2 -- STORY-1101) are normalized the same way URLScanner.identify()
    extracts them from live call text: scheme+host+path, query/fragment
    dropped -- onboarding a specific path pre-seeds only that path, not the
    whole host."""
    parsed = urlparse(target)
    if parsed.scheme == "file":
        path = target[len("file://") :]
        return Resource(kind="file", identity=os.path.abspath(path), scanner_name="secrets")
    if parsed.scheme in ("http", "https"):
        identity = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return Resource(kind="url", identity=identity, scanner_name="reputation")
    raise OnboardError(f"--target must be a file://, http://, or https:// URI (got {target!r})")


def _write_rule(policy_path: Path, rule: PolicyRule) -> None:
    if policy_path.exists():
        try:
            data = yaml.safe_load(policy_path.read_text())
        except yaml.YAMLError as exc:
            raise OnboardError(f"Onboarding blocked: {policy_path} has invalid YAML — {exc}") from exc
        except OSError as exc:
            raise OnboardError(f"Onboarding blocked: could not read {policy_path} — {exc}") from exc
        data = data or {}
        if not isinstance(data, dict):
            raise OnboardError(f"Onboarding blocked: {policy_path} must be a YAML mapping")
    else:
        data = {}

    rules = data.get("rules") or []
    if not isinstance(rules, list):
        raise OnboardError(f"Onboarding blocked: 'rules' in {policy_path} must be a list")

    rule_dict = {"tool": rule.tool, "pattern": rule.pattern, "sensitivity": rule.sensitivity, "mode": rule.mode}
    if rule.scanner:
        rule_dict["scanner"] = rule.scanner
    if rule.description:
        rule_dict["description"] = rule.description

    rules.append(rule_dict)
    data["rules"] = rules

    try:
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text(yaml.safe_dump(data, sort_keys=False, default_flow_style=False))
    except OSError as exc:
        raise OnboardError(f"Onboarding blocked: could not write {policy_path} — {exc}") from exc


def onboard(
    target: str,
    tool: str = ".*",
    pattern: str | None = None,
    sensitivity: str | None = None,
    mode: str | None = None,
    scanner: str = "",
    description: str = "",
    cache_path: Path = DEFAULT_CACHE_PATH,
    policy_path: Path = DEFAULT_POLICY_PATH,
) -> dict:
    """Returns {"resource": Resource, "label": str, "rule": PolicyRule} on
    success. Raises OnboardError (no cache/policy write) on failure."""
    if sensitivity is None and mode is None:
        raise OnboardError(
            "At least one of 'sensitivity' or 'mode' must be provided — onboarding is the moment "
            "you declare a trust decision, it can't be inferred silently."
        )
    sensitivity = sensitivity or "public"
    mode = mode or "allow"
    if mode not in _ONBOARD_VALID_MODES:
        # 'mask' is a valid PolicyRule.mode in general (the dormant
        # evaluate()/MaskingEngine path still distinguishes it from
        # 'block'), but decide_access() -- what a scg-onboard-authored rule
        # actually feeds -- treats anything that isn't 'allow' identically
        # (confirmed_bad, blocked unconditionally). Offering 'mask' here
        # would silently produce a rule that behaves like 'block' while
        # looking like it should behave like the old masking model.
        raise OnboardError(
            f"'mode' must be one of {_ONBOARD_VALID_MODES} — 'mask' is a valid rule value in general "
            f"but has no distinct effect under the live access-control decision (docs/ARCHITECTURE.md "
            f"sec15); it would silently behave exactly like 'block'."
        )

    resource = _resolve_resource(target)
    scanner_obj = SCANNERS[resource.scanner_name]

    try:
        result = scanner_obj.scan(resource)
    except ScannerMachineryError as exc:
        raise OnboardError(f"Onboarding blocked: scan machinery failed — {exc}") from exc

    if result.label in _BLOCKED_LABELS and mode != "block":
        raise OnboardError(
            f"Onboarding blocked: {resource.scanner_name} check failed — {result.reason}. "
            f"(Use --mode block to explicitly declare this resource blocked based on this finding.)"
        )

    try:
        rule = PolicyRule(
            tool=tool,
            pattern=pattern or re.escape(resource.identity),
            sensitivity=sensitivity,
            mode=mode,
            scanner=scanner,
            description=description,
        )
    except PolicyConfigError as exc:
        raise OnboardError(f"Onboarding blocked: invalid rule — {exc}") from exc

    try:
        ScanCache(cache_path).put(resource, result)
    except ScanCacheError as exc:
        raise OnboardError(f"Onboarding blocked: could not write to the scan cache — {exc}") from exc

    _write_rule(policy_path, rule)

    return {"resource": resource, "label": result.label, "rule": rule}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scg onboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "At least one of --sensitivity/--mode is required -- onboarding is the moment you\n"
            "declare a trust decision, so it's never silently inferred. Whichever you omit\n"
            "defaults sensibly (mode: allow, sensitivity: public).\n\n"
            "--mode does not accept 'mask': under the live access-control decision\n"
            "(docs/ARCHITECTURE.md sec15), a rule's mode only ever distinguishes 'allow' from\n"
            "'not allow' -- mask would silently behave exactly like block."
        ),
    )
    parser.add_argument(
        "--target",
        required=True,
        help="file://<path> (runs a secrets scan) or http(s)://<host> (runs a reputation check)",
    )
    parser.add_argument("--tool", default=".*", help="Regex against the tool name (default: any tool)")
    parser.add_argument(
        "--pattern", default=None, help="Regex against the resource identity (default: exact match on --target)"
    )
    parser.add_argument(
        "--sensitivity",
        choices=VALID_SENSITIVITIES,
        default=None,
        help="public|internal|restricted (default 'public' if --mode is given)",
    )
    parser.add_argument(
        "--mode", choices=_ONBOARD_VALID_MODES, default=None, help="allow|block (default 'allow' if --sensitivity is given)"
    )
    parser.add_argument("--scanner", default="", help="Optional disambiguating scanner name (usually inferred)")
    parser.add_argument("--description", default="", help="Why this rule exists (recommended)")
    parser.add_argument("--policy-path", default=str(DEFAULT_POLICY_PATH))
    parser.add_argument("--cache-path", default=str(DEFAULT_CACHE_PATH))
    args = parser.parse_args(argv)

    try:
        result = onboard(
            args.target,
            tool=args.tool,
            pattern=args.pattern,
            sensitivity=args.sensitivity,
            mode=args.mode,
            scanner=args.scanner,
            description=args.description,
            cache_path=Path(args.cache_path),
            policy_path=Path(args.policy_path),
        )
    except OnboardError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    resource = result["resource"]
    rule = result["rule"]
    print(f"Verified: {resource.scanner_name}:{resource.identity} -> {result['label']}")
    print(
        f"Rule written to {args.policy_path}: tool={rule.tool!r} pattern={rule.pattern!r} "
        f"sensitivity={rule.sensitivity!r} mode={rule.mode!r}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
