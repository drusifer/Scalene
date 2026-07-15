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
"""

from __future__ import annotations

from .policy_config import MatchResult, PolicyConfig
from .scan_cache import ScanCache, refresh_if_needed
from .scanner import SCANNERS, Resource

_FILE_SCANNER_NAME = "secrets"
_URL_SCANNER_NAME = "reputation"


def evaluate(tool_name: str, args: dict, config: PolicyConfig, cache: ScanCache) -> MatchResult:
    resources_by_scanner: dict[str, list[Resource]] = {
        name: scanner.identify(tool_name, args) for name, scanner in SCANNERS.items()
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
    for resource in url_resources:
        entry = refresh_if_needed(resource, cache)
        if entry is None:
            fail_safe_triggered = True
            trusted_flags.append(not config.untrusted_by_default)
        else:
            trusted_flags.append(entry.label == "trusted")
    is_trusted = any(trusted_flags) if trusted_flags else not config.untrusted_by_default

    return MatchResult(is_sensitive=is_sensitive, is_trusted=is_trusted, fail_safe_triggered=fail_safe_triggered)
