"""Declarative YAML policy config + JSONPath rule evaluation (STORY-201, STORY-202)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from jsonpath_ng import parse as parse_jsonpath

logger = logging.getLogger("scalene.policy")


class PolicyConfigError(ValueError):
    """Raised when scalene_policy.yaml is malformed or fails schema validation."""


#: Rules are keyed by their target URI's scheme, not by which YAML list they
#: live in (2026-07-14 simplification — one unified list instead of separate
#: non_sensitive_allowlist/trusted_sources_list sections). `file://` rules
#: were verified by scanning a local path for secrets and count toward
#: "not sensitive"; `http(s)://` rules were verified by a domain reputation
#: check and count toward "trusted destination".
SENSITIVITY_SCHEMES = ("file",)
TRUST_SCHEMES = ("http", "https")


@dataclass(frozen=True)
class PolicyRule:
    tool: str
    jsonpath: str
    pattern: str
    target: str
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "PolicyRule":
        if not isinstance(data, dict):
            raise PolicyConfigError(f"Policy rule must be a mapping, got {data!r}")
        missing = [k for k in ("tool", "jsonpath", "pattern", "target") if k not in data]
        if missing:
            raise PolicyConfigError(f"Policy rule missing required field(s) {missing}: {data!r}")
        return cls(
            tool=data["tool"],
            jsonpath=data["jsonpath"],
            pattern=data["pattern"],
            target=data["target"],
            description=data.get("description", ""),
        )

    @property
    def scheme(self) -> str:
        return self.target.split("://", 1)[0] if "://" in self.target else ""


@dataclass(frozen=True)
class MatchResult:
    is_sensitive: bool
    is_trusted: bool
    fail_safe_triggered: bool = False


VALID_MODES = ("mask", "block")


@dataclass
class PolicyConfig:
    sensitive_by_default: bool = True
    untrusted_by_default: bool = True
    # Action taken when a payload is provenance-risky AND actually scans as a
    # real secret (masking.MaskingEngine.decide, 2026-07-14): "mask" replaces
    # the value and allows the call; "block" denies the call outright.
    mode: str = "mask"
    allowlist: list[PolicyRule] = field(default_factory=list)

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

        allowlist_raw = data.get("allowlist", []) or []
        if not isinstance(allowlist_raw, list):
            raise PolicyConfigError(f"'allowlist' in {path} must be a YAML sequence")

        return cls(
            sensitive_by_default=bool(defaults.get("sensitive_by_default", True)),
            untrusted_by_default=bool(defaults.get("untrusted_by_default", True)),
            mode=defaults.get("mode", "mask"),
            allowlist=[PolicyRule.from_dict(r) for r in allowlist_raw],
        )

    def evaluate(self, tool: str, args: dict[str, Any]) -> MatchResult:
        fail_safe = False

        def rule_matches(rule: PolicyRule) -> bool:
            nonlocal fail_safe
            if rule.tool != tool:
                return False
            try:
                found = parse_jsonpath(rule.jsonpath).find(args)
                return any(re.search(rule.pattern, str(m.value)) for m in found)
            except Exception:
                logger.warning(
                    "Fail-safe triggered: JSONPath rule failed to evaluate "
                    "(tool=%s, jsonpath=%s, pattern=%s)",
                    rule.tool,
                    rule.jsonpath,
                    rule.pattern,
                )
                fail_safe = True
                return False

        non_sensitive_match = any(
            rule_matches(r) for r in self.allowlist if r.scheme in SENSITIVITY_SCHEMES
        )
        trusted_match = any(rule_matches(r) for r in self.allowlist if r.scheme in TRUST_SCHEMES)

        if fail_safe:
            return MatchResult(is_sensitive=True, is_trusted=False, fail_safe_triggered=True)

        is_sensitive = self.sensitive_by_default and not non_sensitive_match
        is_trusted = trusted_match or not self.untrusted_by_default
        return MatchResult(is_sensitive=is_sensitive, is_trusted=is_trusted)
