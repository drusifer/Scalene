"""Declarative policy config: sensitivity/trust defaults + mask/block mode
(STORY-201, STORY-202).

2026-07-14 (Sprint 4 / E10, docs/ARCHITECTURE.md sec13.1): PolicyRule and
the `allowlist` (previously YAML-authored tool/jsonpath/pattern/target
rules, resolved by JSONPath matching) are removed entirely, not deprecated
alongside a replacement -- the defect this epic fixes (a rule's one-time
scan vouching for an unbounded future pattern match) is structural to
pattern-matching itself. Resource identification + verification now lives
in `scanner.py`/`resource_verifier.py`/`scan_cache.py`; this module keeps
only the sensitivity/trust defaults + mode, and `MatchResult` (the shared
return shape `resource_verifier.evaluate()` now produces).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .scanner import SCANNERS, Scanner, ScannerRegistryError, escape_gitignore_literal, load_scanners


class PolicyConfigError(ValueError):
    """Raised when scalene_policy.yaml is malformed or fails schema validation."""


@dataclass(frozen=True)
class MatchResult:
    is_sensitive: bool
    is_trusted: bool
    fail_safe_triggered: bool = False
    # 2026-07-17 (docs/ARCHITECTURE.md sec14.2, STORY-1101 fallout): the
    # generic onboard-suggestion placeholder only worked because trust used
    # to be host-level -- any URL under a suggested host would do. Now that
    # identity is per-URL, the suggestion must name the *specific* untrusted
    # URL actually identified, or onboarding it won't stop the exact call
    # that triggered the suggestion. Empty when no URL resource was identified.
    untrusted_url: str = ""
    # sec14.1/14.4 (STORY-1102, STORY-1103): resolved from whichever
    # PolicyRule matched an identified resource, or the implicit default
    # (public/config.mode) when nothing matched. Independent of
    # is_sensitive/is_trusted -- a classification axis, not a taint signal.
    sensitivity: str = "public"
    mode: str = "mask"


VALID_MODES = ("mask", "block")
# docs/ARCHITECTURE.md sec14.4 amendment (2026-07-17): a rule may carry the
# narrow, explicit exception `allow` -- skips content-scanning entirely for
# a matched call. Deliberately NOT part of VALID_MODES (PolicyConfig.mode's
# global default): a project-wide "allow" would blanket-disable scanning by
# one config line, defeating the point of a scoped, hand-authored exception.
VALID_RULE_MODES = ("mask", "block", "allow")
VALID_SENSITIVITIES = ("public", "internal", "restricted")
# Same 3 levels as TaintState.trust (taint_state.py) -- kept as a local
# constant here rather than importing TRUST_LEVELS from taint_state.py,
# matching how VALID_SENSITIVITIES/VALID_RULE_MODES are already local
# constants rather than cross-module imports.
VALID_TRUST_LEVELS = ("low", "med", "high")


@dataclass(frozen=True)
class PolicyRule:
    """docs/ARCHITECTURE.md sec14.1/14.5 (STORY-1102, STORY-1103), sec21.8
    (2026-07-30, direct user request): decides candidacy/classification of
    an already-identified Resource -- `identify()` (scanner.py) still finds
    resources; a rule's `tool` (always regex against tool_name) + `pattern`
    decide which sensitivity/mode/trust apply. `pattern`'s syntax is
    scanner-owned (Scanner.match(), scanner.py) rather than fixed here:
    FileScanner interprets it as gitignore syntax (e.g. "/project/**"),
    everything else (URLScanner, the Scanner base default) still treats it
    as plain regex -- a rule doesn't have to declare `scanner:` to be
    matched, so this class can't know which syntax applies at construction
    time. `scanner` is an optional disambiguating filter (inferred from
    Resource.scanner_name when omitted). `jsonpath` is retained for
    forward-compatibility (a future case where a tool has multiple
    candidate argument fields) -- not required for the common case.

    `trust` (sec21.8): defaults to "high" (least restrictive -- a rule with
    no opinion changes nothing, exactly today's behavior for every rule
    written before this field existed). Since TaintState.escalate_trust()
    only ever ratchets *toward* more restrictive (sec15.1), a validated
    `mode: allow` match already left trust untouched by default; this field
    only matters when a rule author explicitly wants touching a validated,
    content-clean resource to still cap the session's trust at `med` or
    `low` -- e.g. "this vendor's API payloads are fine, but I still don't
    fully trust the vendor as an origin." It does not let a rule *restore*
    trust already contaminated by something else earlier in the session --
    the ratchet-only-restrictive rule (sec15.1) applies here exactly as it
    does to sensitivity."""

    tool: str
    pattern: str
    sensitivity: str
    mode: str
    jsonpath: str = ""
    scanner: str = ""
    description: str = ""
    trust: str = "high"

    def __post_init__(self) -> None:
        if self.sensitivity not in VALID_SENSITIVITIES:
            raise PolicyConfigError(
                f"'sensitivity' must be one of {VALID_SENSITIVITIES}, got {self.sensitivity!r}"
            )
        if self.mode not in VALID_RULE_MODES:
            raise PolicyConfigError(f"'mode' must be one of {VALID_RULE_MODES}, got {self.mode!r}")
        if self.trust not in VALID_TRUST_LEVELS:
            raise PolicyConfigError(f"'trust' must be one of {VALID_TRUST_LEVELS}, got {self.trust!r}")
        # Trin's adversarial UAT finding (Sprint 5 Phase 2): an invalid regex
        # must fail loud here, at rule-construction time -- not raise
        # re.error deep in resource_verifier.evaluate() on every subsequent
        # call that happens to identify a resource. Only `tool` is validated
        # this way now -- `pattern`'s syntax depends on which scanner ends up
        # matching it (see class docstring), which this constructor can't
        # know, and a real gitignore pattern (e.g. a leading "**/") is often
        # not valid regex at all, so applying this same regex check to
        # `pattern` unconditionally would reject legitimate glob patterns
        # outright, not just genuine typos.
        try:
            re.compile(self.tool)
        except re.error as exc:
            raise PolicyConfigError(f"'tool' is not a valid regex: {self.tool!r} ({exc})") from exc
        # E12/STORY-1201 (Trin's Sprint 5 UAT finding): a typo'd scanner name
        # used to silently make a rule permanently ineffective (it would
        # never pass resource_verifier's `rule.scanner != resource.scanner_name`
        # check for any real resource) with no warning.
        #
        # sec18.1 (STORY-1501): this used to validate `self.scanner` against
        # the module-level `SCANNERS` constant right here. Once the registry
        # became config-driven, that's no longer correct -- a rule can't see
        # a dynamically-loaded registry from inside its own __post_init__,
        # since `scanners:` and `rules:` are parsed from the same YAML
        # document and the registry has to be built first. The check itself
        # still happens, fail-loud, same message shape -- just moved to
        # PolicyConfig.from_yaml, after `scanners` is built and before each
        # rule is constructed. Direct `PolicyRule(...)` construction (as
        # several tests do, bypassing from_yaml) no longer fails fast on a
        # bad scanner name -- a deliberate, documented behavior change
        # (Smith's Gate 2 review), not an oversight. Real YAML-loading
        # behavior (the only thing an actual user ever sees) is unchanged.


@dataclass
class PolicyConfig:
    sensitive_by_default: bool = True
    untrusted_by_default: bool = True
    # Action taken when a payload is provenance-risky AND actually scans as a
    # real secret (masking.MaskingEngine.decide, 2026-07-14): "mask" replaces
    # the value and allows the call; "block" denies the call outright.
    mode: str = "mask"
    # docs/ARCHITECTURE.md sec14.5: optional, sibling to `defaults:`. Absent
    # means implicit-default-rule-only behavior (sec14.1) -- identical to a
    # brand-new zero-config project.
    rules: tuple[PolicyRule, ...] = ()
    # sec18.1 (STORY-1501): the registry `resource_verifier.py`/`onboard.py`
    # traverse, in place of importing the module-level `SCANNERS` constant
    # directly. Defaults to the same 2 builtin instances `SCANNERS` already
    # holds, so a bare `PolicyConfig()` (as most existing tests construct)
    # reproduces today's exact behavior with no config file involved.
    scanners: dict[str, Scanner] = field(default_factory=lambda: dict(SCANNERS))

    def __post_init__(self) -> None:
        if self.mode not in VALID_MODES:
            raise PolicyConfigError(f"'mode' must be one of {VALID_MODES}, got {self.mode!r}")

    @classmethod
    def from_yaml(cls, path: Path | str) -> "PolicyConfig":
        path = Path(path)
        try:
            raw_text = path.read_text()
        except OSError as exc:
            raise PolicyConfigError(f"Cannot read policy file {path}: {exc}") from exc

        try:
            data = yaml.safe_load(raw_text)
        except yaml.YAMLError as exc:
            raise PolicyConfigError(f"Invalid YAML in {path}: {exc}") from exc

        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise PolicyConfigError(
                f"Policy file {path} must be a YAML mapping, got {type(data).__name__}"
            )

        defaults = data.get("defaults", {}) or {}
        if not isinstance(defaults, dict):
            raise PolicyConfigError(f"'defaults' section in {path} must be a mapping")

        # sec18.1 (STORY-1501): built before `rules:` is parsed -- a rule's
        # `scanner` field is validated against this registry, not the module-
        # level SCANNERS constant, so a config-declared scanner is a valid
        # `scanner:` value too.
        raw_scanners_config = data.get("scanners", {}) or {}
        if not isinstance(raw_scanners_config, dict):
            raise PolicyConfigError(f"'scanners' section in {path} must be a mapping")
        try:
            scanners = load_scanners(raw_scanners_config)
        except ScannerRegistryError as exc:
            raise PolicyConfigError(f"Invalid 'scanners' section in {path}: {exc}") from exc

        raw_rules = data.get("rules", []) or []
        if not isinstance(raw_rules, list):
            raise PolicyConfigError(f"'rules' section in {path} must be a list")

        rules = []
        for i, raw_rule in enumerate(raw_rules):
            if not isinstance(raw_rule, dict):
                raise PolicyConfigError(f"'rules[{i}]' in {path} must be a mapping")
            rule_scanner = raw_rule.get("scanner", "")
            if rule_scanner and rule_scanner not in scanners:
                raise PolicyConfigError(
                    f"'rules[{i}].scanner' must be one of {tuple(scanners)} or empty (inferred), "
                    f"got {rule_scanner!r}"
                )
            try:
                rules.append(
                    PolicyRule(
                        tool=raw_rule["tool"],
                        pattern=raw_rule["pattern"],
                        sensitivity=raw_rule["sensitivity"],
                        mode=raw_rule["mode"],
                        jsonpath=raw_rule.get("jsonpath", ""),
                        scanner=rule_scanner,
                        description=raw_rule.get("description", ""),
                        trust=raw_rule.get("trust", "high"),
                    )
                )
            except KeyError as exc:
                raise PolicyConfigError(f"'rules[{i}]' in {path} is missing required field {exc}") from exc

        return cls(
            sensitive_by_default=bool(defaults.get("sensitive_by_default", True)),
            untrusted_by_default=bool(defaults.get("untrusted_by_default", True)),
            mode=defaults.get("mode", "mask"),
            rules=tuple(rules),
            scanners=scanners,
        )


# sec18.4: shared with onboard.py's write_rule(), so a later, more specific
# onboarded rule can be inserted ahead of this one rather than being
# silently shadowed by it forever (see write_default_project_policy's
# docstring for why order matters here).
PROJECT_FOLDER_DEFAULT_DESCRIPTION = "project folder default (auto-created)"


def write_default_project_policy(path: Path, project_root: Path) -> None:
    """docs/ARCHITECTURE.md sec18.4 (STORY-1504). Called only when `path`
    doesn't exist yet -- writes one real `rules:` entry for the project's
    own folder to a real, new `scalene_policy.yaml`, the same shape as any
    onboard-authored or hand-written rule (user's own direction, 2026-07-21:
    avoid an implicit in-code special case; make it a real, ordinary rule
    instead). No `ScanCache` entry is pre-seeded here -- the project
    folder's first real tool-use still triggers a genuine scan and goes
    through `decide_access()`'s normal uncleared -> validated_allow
    progression, exactly like any other resource. This function only ever
    creates the rule; it never touches an existing file (callers check
    `path.exists()` first).

    Ordering matters: `_find_matching_rule()` (resource_verifier.py) returns
    the *first* declaration-order match, and this rule's pattern is broad
    (matches almost anything under the project root) -- if it's ever first
    in the file and a later, more specific `scg onboard`-authored rule for
    the same path is simply appended after it, the specific rule would be
    silently unreachable forever. `onboard.py::write_rule()` accounts for
    this by inserting new rules *before* this one, not after -- see there.

    2026-07-30 (Scanner.match(), scanner.py): FileScanner now matches
    patterns as gitignore syntax, not regex (user request: familiar
    wildcard matching for "the whole project folder recursively") -- the
    old `^...(/|$)` regex anchoring is replaced with 2 gitignore lines (the
    root path itself, and "root/**" for everything under it -- plain
    gitignore semantics don't match a bare directory via "root/**" alone,
    only its contents). pathspec's GitIgnoreSpec handles the "/etc" vs.
    false-positive "/etcetera" boundary correctly on its own.

    Still no `scanner:` filter -- sec19.3's principle holds (a rule author
    shouldn't need to remember/specify a scanner registry name when the
    pattern alone is already selective). A gitignore-shaped pattern handed
    to a different scanner's plain-regex match() (e.g. URLScanner, for an
    unrelated URL resource) could raise ("**" isn't valid regex) rather
    than just fail to match -- but Scanner.match()'s base regex path now
    catches `re.error` and fails safe (no match), so this is handled at
    the matcher level, not by re-adding a filter here for every scanner-
    specific pattern syntax that comes along."""
    escaped_root = escape_gitignore_literal(str(project_root))
    rule = {
        "tool": ".*",
        "pattern": f"{escaped_root}\n{escaped_root}/**",
        "sensitivity": "internal",
        "mode": "allow",
        "description": PROJECT_FOLDER_DEFAULT_DESCRIPTION,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"rules": [rule]}, sort_keys=False, default_flow_style=False))
