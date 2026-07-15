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


VALID_MODES = ("mask", "block")


@dataclass
class PolicyConfig:
    sensitive_by_default: bool = True
    untrusted_by_default: bool = True
    # Action taken when a payload is provenance-risky AND actually scans as a
    # real secret (masking.MaskingEngine.decide, 2026-07-14): "mask" replaces
    # the value and allows the call; "block" denies the call outright.
    mode: str = "mask"

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

        return cls(
            sensitive_by_default=bool(defaults.get("sensitive_by_default", True)),
            untrusted_by_default=bool(defaults.get("untrusted_by_default", True)),
            mode=defaults.get("mode", "mask"),
        )
