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
from dataclasses import dataclass
from pathlib import Path

import yaml


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


@dataclass(frozen=True)
class PolicyRule:
    """docs/ARCHITECTURE.md sec14.1/14.5 (STORY-1102, STORY-1103): decides
    candidacy/classification of an already-identified Resource, never trust
    directly -- `identify()` (scanner.py) still finds resources; a rule's
    `tool` (regex against tool_name) + `pattern` (regex against
    resource.identity) decide which sensitivity/mode apply. `scanner` is an
    optional disambiguating filter (inferred from Resource.scanner_name when
    omitted). `jsonpath` is retained for forward-compatibility (a future
    case where a tool has multiple candidate argument fields) -- not
    required for the common case."""

    tool: str
    pattern: str
    sensitivity: str
    mode: str
    jsonpath: str = ""
    scanner: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        if self.sensitivity not in VALID_SENSITIVITIES:
            raise PolicyConfigError(
                f"'sensitivity' must be one of {VALID_SENSITIVITIES}, got {self.sensitivity!r}"
            )
        if self.mode not in VALID_RULE_MODES:
            raise PolicyConfigError(f"'mode' must be one of {VALID_RULE_MODES}, got {self.mode!r}")
        # Trin's adversarial UAT finding (Sprint 5 Phase 2): an invalid regex
        # must fail loud here, at rule-construction time -- not raise
        # re.error deep in resource_verifier.evaluate() on every subsequent
        # call that happens to identify a resource.
        for field_name in ("tool", "pattern"):
            try:
                re.compile(getattr(self, field_name))
            except re.error as exc:
                raise PolicyConfigError(f"'{field_name}' is not a valid regex: {getattr(self, field_name)!r} ({exc})") from exc


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

        raw_rules = data.get("rules", []) or []
        if not isinstance(raw_rules, list):
            raise PolicyConfigError(f"'rules' section in {path} must be a list")

        rules = []
        for i, raw_rule in enumerate(raw_rules):
            if not isinstance(raw_rule, dict):
                raise PolicyConfigError(f"'rules[{i}]' in {path} must be a mapping")
            try:
                rules.append(
                    PolicyRule(
                        tool=raw_rule["tool"],
                        pattern=raw_rule["pattern"],
                        sensitivity=raw_rule["sensitivity"],
                        mode=raw_rule["mode"],
                        jsonpath=raw_rule.get("jsonpath", ""),
                        scanner=raw_rule.get("scanner", ""),
                        description=raw_rule.get("description", ""),
                    )
                )
            except KeyError as exc:
                raise PolicyConfigError(f"'rules[{i}]' in {path} is missing required field {exc}") from exc

        return cls(
            sensitive_by_default=bool(defaults.get("sensitive_by_default", True)),
            untrusted_by_default=bool(defaults.get("untrusted_by_default", True)),
            mode=defaults.get("mode", "mask"),
            rules=tuple(rules),
        )
