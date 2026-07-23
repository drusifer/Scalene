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
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

from .policy_config import (
    PROJECT_FOLDER_DEFAULT_DESCRIPTION,
    PolicyConfig,
    PolicyConfigError,
    PolicyRule,
    VALID_SENSITIVITIES,
)
from .scan_cache import DEFAULT_CACHE_PATH, ScanCache, ScanCacheError
from .scanner import SCANNERS, Resource, Scanner, ScannerMachineryError

DEFAULT_POLICY_PATH = Path("scalene_policy.yaml")

BLOCKED_LABELS = ("sensitive", "untrusted")
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


def identify_targets(
    tool_name: str, tool_input: dict, scanners: dict[str, Scanner] | None = None
) -> list[Resource]:
    """docs/ARCHITECTURE.md sec17.1/17.2 (STORY-1401): traverses the full
    scanner registry, calling each scanner's own identify() -- the exact
    mechanism pre_tool_use already runs live -- instead of a hand-typed
    --target URI resolved by a second, onboard-only resolver. Deduplicated
    by (kind, identity): the same value can surface via a known field AND
    the generic-fallback scan of the same string (e.g. WebFetch's --url
    field vs. that same URL appearing in --prompt too).

    sec18.1 (STORY-1501): `scanners` defaults to the module-level SCANNERS
    constant (the 2 builtins) when not given, so every existing caller
    (tests, direct library use) is unaffected -- `main()` passes the
    project's own loaded PolicyConfig.scanners so a config-declared scanner
    is identified here too, not just at live hook-decision time."""
    registry = scanners if scanners is not None else SCANNERS
    seen: set[tuple[str, str]] = set()
    targets: list[Resource] = []
    for scanner in registry.values():
        for resource in scanner.identify(tool_name, tool_input):
            key = (resource.kind, resource.identity)
            if key in seen:
                continue
            seen.add(key)
            targets.append(resource)
    return targets


def load_tool_call(call_path: str | None = None) -> tuple[str, dict]:
    """docs/ARCHITECTURE.md sec17.1: reads {"tool_name": ..., "tool_input":
    ...} from `call_path` if given, else stdin -- deliberately the same
    field names scalene-guard's own hook contract already uses (docs/
    USER_GUIDE.md), so onboarding is one mental model, not two. Raises
    OnboardError (never a raw exception) on a missing file, malformed JSON,
    or a missing 'tool_name' key."""
    try:
        text = Path(call_path).read_text() if call_path else sys.stdin.read()
    except OSError as exc:
        raise OnboardError(f"Onboarding blocked: could not read tool call — {exc}") from exc

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OnboardError(f"Onboarding blocked: tool call is not valid JSON — {exc}") from exc

    if not isinstance(payload, dict) or "tool_name" not in payload:
        raise OnboardError("Onboarding blocked: tool call JSON must be an object with a 'tool_name' key")

    return payload["tool_name"], payload.get("tool_input", {})


def write_rule(policy_path: Path, rule: PolicyRule) -> None:
    """docs/ARCHITECTURE.md sec20.5 (STORY-1605): renamed from `_write_rule`
    (2026-07-23) -- `monitor_app.ReviewScreen`'s Allow action is now a
    second real caller outside this module, so the underscore-private
    convention no longer described its actual usage."""
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

    # sec18.4 (STORY-1504): the auto-created project-folder default's
    # pattern is broad by design -- if a real onboarded rule for the same
    # (or a more specific) path were simply appended after it, the default
    # would always match first and the new, more specific decision would
    # be silently unreachable forever. Insert ahead of it instead of after,
    # same declaration-order-wins mechanism, just placed correctly.
    default_index = next(
        (i for i, r in enumerate(rules) if isinstance(r, dict) and r.get("description") == PROJECT_FOLDER_DEFAULT_DESCRIPTION),
        None,
    )
    if default_index is None:
        rules.append(rule_dict)
    else:
        rules.insert(default_index, rule_dict)
    data["rules"] = rules

    try:
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text(yaml.safe_dump(data, sort_keys=False, default_flow_style=False))
    except OSError as exc:
        raise OnboardError(f"Onboarding blocked: could not write {policy_path} — {exc}") from exc


def _validate_axis(sensitivity: str | None, mode: str | None) -> tuple[str, str]:
    """Batch-level precondition (sec17.4): checked once, before any target
    is touched -- a bad flag combo blocks the whole invocation, not one
    target at a time, since --sensitivity/--mode describe one trust
    decision shared across everything in this batch."""
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
    return sensitivity, mode


def _onboard_resource(
    resource: Resource,
    sensitivity: str,
    mode: str,
    scanner: str,
    description: str,
    cache_path: Path,
    policy_path: Path,
    tool: str = ".*",
    pattern: str | None = None,
    scanners: dict[str, Scanner] | None = None,
) -> dict:
    """One target's worth of scan + rule-write (sec17.4). `onboard_targets()`
    never overrides tool/pattern (the flags are gone from that flow entirely
    -- ".*" and an exact match on the resource's own identity, same default
    sec16 already had). `onboard()` (pre-sec17, kept for its existing
    callers) still can, via these two params.

    sec18.1 (STORY-1501): `scanners` defaults to the module-level SCANNERS
    constant when not given, same precedent as identify_targets(). The
    `scanner` param (the rule's disambiguating filter, distinct from
    `resource.scanner_name`) is validated here against this same registry --
    `PolicyRule.__post_init__` no longer validates it (sec18.1's move), and
    this function constructs a `PolicyRule` directly, never through
    `PolicyConfig.from_yaml`'s own validation loop -- so without this check
    a typo'd --scanner would silently write an ineffective rule (E12/
    STORY-1201's original defect, reintroduced by the sec18.1 move if left
    unchecked here)."""
    registry = scanners if scanners is not None else SCANNERS
    scanner_obj = registry[resource.scanner_name]

    if scanner and scanner not in registry:
        raise OnboardError(
            f"Onboarding blocked: invalid rule — 'scanner' must be one of {tuple(registry)} or empty "
            f"(inferred), got {scanner!r}"
        )

    try:
        result = scanner_obj.scan(resource)
    except ScannerMachineryError as exc:
        raise OnboardError(f"Onboarding blocked: scan machinery failed — {exc}") from exc

    if result.label in BLOCKED_LABELS and mode != "block":
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

    write_rule(policy_path, rule)

    return {"resource": resource, "label": result.label, "reputation": result.reputation, "rule": rule}


def onboard_targets(
    targets: list[Resource],
    sensitivity: str | None = None,
    mode: str | None = None,
    scanner: str = "",
    description: str = "",
    cache_path: Path = DEFAULT_CACHE_PATH,
    policy_path: Path = DEFAULT_POLICY_PATH,
    scanners: dict[str, Scanner] | None = None,
) -> list[dict]:
    """docs/ARCHITECTURE.md sec17.4 (STORY-1403): scans + writes a rule for
    each confirmed target. Batch semantics, not all-or-nothing -- one
    target's scan/rule failure is caught and recorded per-target (ok=False,
    error=...), the rest of the batch still proceeds. Returns one result
    dict per target, in the same order as `targets`.

    sec18.1 (STORY-1501): `scanners` (defaults to the module-level SCANNERS
    constant) is threaded through to `_onboard_resource()` unchanged."""
    sensitivity, mode = _validate_axis(sensitivity, mode)

    results = []
    for resource in targets:
        try:
            outcome = _onboard_resource(
                resource, sensitivity, mode, scanner, description, cache_path, policy_path, scanners=scanners
            )
            results.append({**outcome, "ok": True})
        except OnboardError as exc:
            results.append({"resource": resource, "ok": False, "error": str(exc)})
    return results


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
    success. Raises OnboardError (no cache/policy write) on failure.

    Superseded by onboard_targets() as of sec17 (Sprint 8/E14) -- kept as-is
    (still `--target`-driven, single-resource) since its only caller,
    _resolve_resource(), is deliberately not deleted yet (Phase 1's scope
    note). Phase 3 migrates the remaining direct callers and removes both."""
    sensitivity, mode = _validate_axis(sensitivity, mode)

    resource = _resolve_resource(target)
    return _onboard_resource(
        resource, sensitivity, mode, scanner, description, cache_path, policy_path, tool=tool, pattern=pattern
    )


def _confirm_targets(targets: list[Resource], yes: bool, only: str | None) -> list[Resource]:
    """docs/ARCHITECTURE.md sec17.3 (STORY-1402, Smith's Gate 1 hard
    requirement): interactive by default, two explicit non-interactive
    escapes. Fails fast (never hangs) when stdin isn't a TTY and neither
    escape was given -- the failure mode that would otherwise silently wedge
    a script/CI run on a read() that never resolves."""
    if only is not None:
        wanted = [identity.strip() for identity in only.split(",") if identity.strip()]
        by_identity = {t.identity: t for t in targets}
        missing = [identity for identity in wanted if identity not in by_identity]
        if missing:
            raise OnboardError(
                f"Onboarding blocked: --only named identities not found among identified targets: "
                f"{', '.join(missing)}"
            )
        return [by_identity[identity] for identity in wanted]

    if yes:
        return list(targets)

    if not sys.stdin.isatty():
        raise OnboardError(
            "Onboarding blocked: no TTY for interactive confirmation, and neither --yes nor --only "
            "was given. Pass --yes to confirm every identified target, or --only <identity,...> to "
            "confirm a specific subset non-interactively."
        )

    print(f"Identified {len(targets)} target(s):")
    for i, target in enumerate(targets, start=1):
        print(f"  {i}. [{target.kind}] {target.identity} (via {target.scanner_name})")
    answer = input(f"Onboard all {len(targets)} targets? [Y/n/s(elect)] ").strip().lower()
    if answer in ("", "y", "yes"):
        return list(targets)
    if answer in ("s", "select"):
        exclude_raw = input("Enter numbers to exclude, comma-separated (or blank for none): ").strip()
        excluded = {int(tok) for tok in exclude_raw.split(",") if tok.strip().isdigit()}
        return [target for i, target in enumerate(targets, start=1) if i not in excluded]
    # 'n'/'no'/anything unrecognized: decline everything rather than guess.
    return []


def _list_inventory(cache_path: Path, scanner_filter: str | None) -> int:
    """docs/ARCHITECTURE.md sec17.5 (STORY-1404): a read-only view over
    ScanCache.all_entries() grouped by scanner -- no new store, so there's
    nothing here that could drift from what decide_access() actually reads."""
    try:
        entries = ScanCache(cache_path).all_entries()
    except ScanCacheError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    grouped: dict[str, list[tuple[str, dict]]] = {}
    for key, entry in entries.items():
        scanner_name, _, identity = key.partition(":")
        if scanner_filter and scanner_name != scanner_filter:
            continue
        grouped.setdefault(scanner_name, []).append((identity, entry))

    if not grouped:
        print("No onboarded targets in the scan cache.")
        return 0

    for scanner_name in sorted(grouped):
        print(f"{scanner_name}:")
        for identity, entry in sorted(grouped[scanner_name]):
            print(f"  {identity} -> {entry.get('label', '?')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scg onboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Reads a tool call ({\"tool_name\": ..., \"tool_input\": ...}) from stdin by default,\n"
            "or --call PATH -- the same field names scalene-guard's own hook contract already\n"
            "uses. Every scanner's identify() runs against it; identified targets are confirmed\n"
            "(interactively, or via --yes/--only) before anything is scanned or written.\n\n"
            "At least one of --sensitivity/--mode is required -- onboarding is the moment you\n"
            "declare a trust decision, so it's never silently inferred. Whichever you omit\n"
            "defaults sensibly (mode: allow, sensitivity: public).\n\n"
            "--mode does not accept 'mask': under the live access-control decision\n"
            "(docs/ARCHITECTURE.md sec15), a rule's mode only ever distinguishes 'allow' from\n"
            "'not allow' -- mask would silently behave exactly like block."
        ),
    )
    parser.add_argument("--call", default=None, help="Path to a JSON {tool_name, tool_input} file (default: read from stdin)")
    parser.add_argument(
        "--yes", "-y", action="store_true", help="Onboard every identified target without an interactive prompt"
    )
    parser.add_argument(
        "--only",
        default=None,
        help="Comma-separated identities to onboard, skipping the prompt (fails if a named identity wasn't identified)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List onboarded targets from the scan cache (optionally filtered by --scanner) instead of onboarding",
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
    parser.add_argument(
        "--scanner", default="", help="Optional disambiguating scanner name (usually inferred); also filters --list"
    )
    parser.add_argument("--description", default="", help="Why this rule exists (recommended)")
    parser.add_argument("--policy-path", default=str(DEFAULT_POLICY_PATH))
    parser.add_argument("--cache-path", default=str(DEFAULT_CACHE_PATH))
    args = parser.parse_args(argv)

    if args.list:
        return _list_inventory(Path(args.cache_path), args.scanner or None)

    # Morpheus's Phase 2 review (Sprint 8/E14): validate the batch-level
    # --sensitivity/--mode precondition BEFORE the interactive confirmation
    # prompt, not after -- a user who answers the prompt shouldn't then be
    # told they forgot a required flag; the failure has to come before
    # their input is asked for, same as --yes's non-interactive path
    # already did.
    try:
        sensitivity, mode = _validate_axis(args.sensitivity, args.mode)
    except OnboardError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        tool_name, tool_input = load_tool_call(call_path=args.call)
    except OnboardError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    # sec18.1 (STORY-1501): load the project's own registry (builtins +
    # any config-declared scanners) once -- so a config-declared scanner is
    # identified/onboarded here the same way it participates in live
    # pre_tool_use decisions, not just the 2 builtins. A missing/absent
    # policy file (a brand-new project) falls back to the builtins only,
    # same as PolicyConfig()'s own default.
    policy_path = Path(args.policy_path)
    try:
        scanners = PolicyConfig.from_yaml(policy_path).scanners if policy_path.exists() else dict(SCANNERS)
    except PolicyConfigError as exc:
        print(f"scg onboard: could not load {policy_path}: {exc}", file=sys.stderr)
        return 1

    targets = identify_targets(tool_name, tool_input, scanners=scanners)
    if not targets:
        print("No targets identified in this tool call.")
        return 0

    try:
        confirmed = _confirm_targets(targets, yes=args.yes, only=args.only)
    except OnboardError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not confirmed:
        print("No targets selected. Nothing onboarded.")
        return 0

    results = onboard_targets(
        confirmed,
        sensitivity=sensitivity,
        mode=mode,
        scanner=args.scanner,
        description=args.description,
        cache_path=Path(args.cache_path),
        policy_path=policy_path,
        scanners=scanners,
    )

    ok_count = 0
    for r in results:
        resource = r["resource"]
        if r["ok"]:
            ok_count += 1
            score = f" (score {r['reputation']:.2f})" if r["reputation"] is not None else ""
            rule = r["rule"]
            print(f"Verified: {resource.scanner_name}:{resource.identity} -> {r['label']}{score}")
            print(
                f"Rule written to {args.policy_path}: tool={rule.tool!r} pattern={rule.pattern!r} "
                f"sensitivity={rule.sensitivity!r} mode={rule.mode!r}"
            )
        else:
            print(f"Blocked: {resource.scanner_name}:{resource.identity} -> {r['error']}", file=sys.stderr)

    print(f"{ok_count} onboarded, {len(results) - ok_count} blocked")
    return 0 if ok_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
