# Neo — Sprint 9 (E15) Phase 2 implementation notes (2026-07-21)

## What shipped
- `scanner.py`: `_HARDCODED_RESTRICTED_PREFIXES = ("/etc", os.path.expanduser("~/.ssh"))` + `_is_hardcoded_restricted(identity)` (prefix-boundary-safe, not a naive `str.startswith` — rejects a false positive like `/etcetera/file`). `FileScanner.scan()` short-circuits to `ScanResult(label="sensitive", reason="path matches a hardcoded restricted system location")` before ever calling `run_scanner("secrets", ...)` — the path doesn't even need to exist for this to fire.

## A real design correction found while implementing, not assumed away
§18.2 (as architected) proposed an implicit `PolicyRule(sensitivity="restricted", mode="block")` in `resource_verifier.py` to make the tri-level `sensitivity` axis reflect "restricted". Tracing `decide_access()`'s actual control flow (§15.3) before writing that code: `is_bad` (true whenever a cached `label` is in `_BAD_LABELS`, which includes `"sensitive"`) is checked **before** any rule is matched, and immediately returns `AccessDecision(allowed=False, ...)` — no rule can ever move a `label="sensitive"` resource into `validated_allow`. That makes the proposed `resource_verifier.py` addition unreachable dead code: `FileScanner`'s short-circuit alone already makes a hardcoded-restricted path unconditionally, un-overridably blocked via the live path, with zero changes outside `scanner.py`. Corrected `docs/ARCHITECTURE.md` §18.2 to explain this rather than implementing code that would never execute — same "verify by attempting, don't implement an unverified plan" discipline as Sprint 8's onboard() revision and Phase 1's diagram-drift catch.

Also removed the public `scanner.is_hardcoded_restricted(resource)` cross-module helper §18.2 originally proposed — with no `resource_verifier.py` consumer, a private, single-file helper (`_is_hardcoded_restricted`) is the right scope (YAGNI).

## Test coverage added
`tests/test_scanner.py` (5 new `TestFileScannerScan` cases): `/etc/hostname` sensitive-even-clean, distinct reason text, `~/.ssh` path sensitive-even-clean, `/etcetera/...` false-positive rejection, and confirming the short-circuit fires even for a nonexistent path (never touches the scan subprocess). `tests/test_resource_verifier.py` (3 new `TestHardcodedRestrictedPaths` cases, using the *real* `FileScanner().scan()` result pre-seeded into the cache, same precedent as this file's other cache-hit tests — `decide_access()`'s first-sighting path is fire-and-forget async, so there's no synchronous scan to test against on a cache miss): unconditional block, block-even-with-a-matching-allow-rule (the actual "regardless" AC), and confirming an ordinary path outside the hardcoded set is unaffected.

## Verification
`make test`: 360/360 (352 baseline + 8 new).
