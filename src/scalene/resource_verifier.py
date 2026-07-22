"""Resource verification (STORY-1002, STORY-1003).

docs/ARCHITECTURE.md sec13.1: full replacement of PolicyConfig.evaluate()'s
PolicyRule/allowlist JSONPath matching -- the defect that model has (a
rule's one-time scan vouching for an unbounded future pattern match) is
structural to pattern-matching itself, not a bug in one implementation.

Runs every registered scanner's identify() across a call's args, looks each
identified Resource up in the scan cache (refreshing in the background on a
miss/staleness -- STORY-1003's 3-state lookup), and aggregates into the same
MatchResult shape pre_tool_use/post_tool_use already consume (sec13.1.1) --
so MaskingEngine.decide()'s content-gating logic is completely unaffected
by this swap.

Aggregation mirrors the old model's ANY-match semantics for behavioral
parity: a call touching multiple resources of one kind is sensitive/
untrusted unless *every* one of them individually resolves clean/trusted.
`fail_safe_triggered` now means "at least one identified resource had no
cache entry and fell back to defaults" (sec13.1.1), replacing its old
"a rule's JSONPath failed to evaluate" meaning.

2026-07-17 (sec14.1, STORY-1102/1103): PolicyRule returns as a *classifier*
of already-identified resources, never as the identification mechanism
itself -- identify() above is unchanged. For each identified resource, the
first rule (declaration order) whose `tool` regex matches tool_name and
`pattern` regex matches resource.identity (optionally filtered by
`scanner`) supplies that resource's sensitivity/mode; the implicit default
(sensitivity=public, mode=config.mode) applies when nothing matches --
constructed here in code, never written to a user's YAML (sec14.1). When a
call touches multiple resources, the most restrictive sensitivity
(restricted > internal > public) and mode (block > mask > allow) across
all of them wins, mirroring the existing ANY-match-wins-conservative
convention this module already uses for is_sensitive/is_trusted.

`evaluate()`/`MatchResult` above (STORY-1002/1003/1102/1103) feed
`MaskingEngine`'s content-scanning decision (sec14.4) -- kept intact and
still tested, but no longer wired into `hook_adapter.pre_tool_use`'s
default flow as of sec15 (see `decide_access()` below). Masking's role
going forward is explicitly undecided (sec15.5), not removed.

2026-07-17 (sec15, direct user design session): `decide_access()` is the
new core mechanism -- rule-driven access control, replacing content-
scanning as what actually gates whether a call proceeds. A rule's `tool`/
`pattern` still only decide *candidacy* (unchanged); a match additionally
requires the scan cache to independently confirm the resource clean
(sec15.2) before it counts as validated. Three per-resource outcomes:
`confirmed_bad` (scanner found it bad, OR a matched rule's `mode` isn't
`allow` -- both block unconditionally, regardless of session state, since
a rule can declare intent but never overrides a real bad finding);
`validated_allow` (rule matched, `mode: allow`, cache confirms clean --
proceeds unconditionally, escalates the session's `sensitivity` tag);
`uncleared` (no rule matched, or a rule matched but isn't yet validated --
proceeds only if the session is currently clean, escalating `trust` to
`low`; blocked outright once the session is already contaminated). See
`docs/ARCHITECTURE.md` sec15 for the full state machine and rationale.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .policy_config import MatchResult, PolicyConfig, PolicyRule
from .scan_cache import ScanCache, refresh_if_needed
from .scanner import Resource
from .taint_state import TaintState

_FILE_SCANNER_NAME = "secrets"
_URL_SCANNER_NAME = "reputation"

_BAD_LABELS = ("sensitive", "untrusted")
_CLEAN_LABELS = ("public", "trusted")

_SENSITIVITY_RANK = {"public": 0, "internal": 1, "restricted": 2}
_MODE_RANK = {"allow": 0, "mask": 1, "block": 2}


def _find_matching_rule(tool_name: str, resource: Resource, rules: tuple[PolicyRule, ...]) -> PolicyRule | None:
    for rule in rules:
        if rule.scanner and rule.scanner != resource.scanner_name:
            continue
        if not re.search(rule.tool, tool_name):
            continue
        if not re.search(rule.pattern, resource.identity):
            continue
        return rule
    return None


def _resolve_rule_for_resource(
    tool_name: str, resource: Resource, rules: tuple[PolicyRule, ...], default_mode: str
) -> tuple[str, str]:
    rule = _find_matching_rule(tool_name, resource, rules)
    if rule is None:
        return "public", default_mode
    return rule.sensitivity, rule.mode


def _resolve_sensitivity_and_mode(
    tool_name: str, resources: list[Resource], rules: tuple[PolicyRule, ...], default_mode: str
) -> tuple[str, str]:
    if not resources:
        return "public", default_mode
    resolved = [_resolve_rule_for_resource(tool_name, r, rules, default_mode) for r in resources]
    sensitivity = max((s for s, _ in resolved), key=_SENSITIVITY_RANK.get)
    mode = max((m for _, m in resolved), key=_MODE_RANK.get)
    return sensitivity, mode


def evaluate(tool_name: str, args: dict, config: PolicyConfig, cache: ScanCache) -> MatchResult:
    # sec18.1 (STORY-1501): config.scanners, not the module-level SCANNERS
    # constant -- so a config-declared scanner participates in identification
    # the same way a builtin does.
    resources_by_scanner: dict[str, list[Resource]] = {
        name: scanner.identify(tool_name, args) for name, scanner in config.scanners.items()
    }
    file_resources = resources_by_scanner.get(_FILE_SCANNER_NAME, [])
    url_resources = resources_by_scanner.get(_URL_SCANNER_NAME, [])

    fail_safe_triggered = False

    sensitive_flags = []
    for resource in file_resources:
        entry = refresh_if_needed(resource, cache)
        if entry is None:
            fail_safe_triggered = True
            sensitive_flags.append(config.sensitive_by_default)
        else:
            sensitive_flags.append(entry.label == "sensitive")
    is_sensitive = any(sensitive_flags) if sensitive_flags else config.sensitive_by_default

    trusted_flags = []
    untrusted_url = ""
    for resource in url_resources:
        entry = refresh_if_needed(resource, cache)
        resource_trusted = entry is not None and entry.label == "trusted"
        if entry is None:
            fail_safe_triggered = True
            trusted_flags.append(not config.untrusted_by_default)
        else:
            trusted_flags.append(resource_trusted)
        # STORY-1101 fallout (sec14.2): the first identified URL resource
        # that isn't trusted, so onboard-suggestion messaging can name the
        # exact resource to verify -- a generic host placeholder no longer
        # suffices now that trust is per-URL, not per-host.
        if not resource_trusted and not untrusted_url:
            untrusted_url = resource.identity
    is_trusted = any(trusted_flags) if trusted_flags else not config.untrusted_by_default

    sensitivity, mode = _resolve_sensitivity_and_mode(
        tool_name, file_resources + url_resources, config.rules, config.mode
    )

    return MatchResult(
        is_sensitive=is_sensitive,
        is_trusted=is_trusted,
        fail_safe_triggered=fail_safe_triggered,
        untrusted_url=untrusted_url,
        sensitivity=sensitivity,
        mode=mode,
    )


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    reason: str = ""


def decide_access(
    tool_name: str, args: dict, config: PolicyConfig, cache: ScanCache, taint: TaintState
) -> AccessDecision:
    """docs/ARCHITECTURE.md sec15.3: the core call-permission decision.
    Mutates `taint` in place (escalate_trust/escalate_sensitivity) when the
    call is allowed -- callers persist it (taint.save()) themselves."""
    resources = [r for scanner in config.scanners.values() for r in scanner.identify(tool_name, args)]
    if not resources:
        return AccessDecision(allowed=True)

    was_clean = taint.is_clean

    confirmed_bad: list[tuple[Resource, str]] = []
    validated_allow: list[tuple[Resource, PolicyRule]] = []
    uncleared: list[Resource] = []

    for resource in resources:
        entry = refresh_if_needed(resource, cache)
        is_bad = entry is not None and entry.label in _BAD_LABELS
        is_clean_entry = entry is not None and entry.label in _CLEAN_LABELS
        rule = _find_matching_rule(tool_name, resource, config.rules)

        if is_bad:
            confirmed_bad.append((resource, "the scanner found a real issue with it"))
        elif rule is not None and rule.mode != "allow":
            confirmed_bad.append((resource, f"a matching rule sets mode={rule.mode!r}, not 'allow'"))
        elif rule is not None and is_clean_entry:
            validated_allow.append((resource, rule))
        else:
            uncleared.append(resource)

    if confirmed_bad:
        details = "; ".join(f"{resource.identity} ({why})" for resource, why in confirmed_bad)
        return AccessDecision(allowed=False, reason=f"Blocked: {details}.")

    for resource, rule in validated_allow:
        taint.escalate_sensitivity(rule.sensitivity)

    if not uncleared:
        return AccessDecision(allowed=True)

    if was_clean:
        taint.escalate_trust("low")
        return AccessDecision(allowed=True)

    names = ", ".join(resource.identity for resource in uncleared)
    return AccessDecision(
        allowed=False,
        reason=(
            f"Blocked: {names} has no validated, explicitly-allowed rule, and this session "
            f"has already touched sensitive/untrusted data (trust={taint.trust}, "
            f"sensitivity={taint.sensitivity})."
        ),
    )
