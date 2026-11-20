# Neo — Sprint 9 (E15) Phase 3 implementation notes (2026-07-21)

## What shipped
- `reputation.py`: `URLHausChecker` (implements `ReputationChecker`, queries URLhaus's keyless host-lookup endpoint via `urllib.request`, stdlib only — no new dependency). `ReputationCheckUnavailable` distinguishes "couldn't check" from "checked, found bad." `composite_check(target)` — always runs `LocalHeuristicChecker`, attempts `URLHausChecker`, combines any-bad-wins + min-score, degrades to local-only with a visible marker in `reason` on `ReputationCheckUnavailable`.
- `scan_worker.py::_scan_reputation` now calls `composite_check()` instead of `LocalHeuristicChecker().check()` directly — runs inside the existing isolated subprocess (STORY-601), no new isolation mechanism.
- `docs/ARCHITECTURE.md` §4 diagram: added `ReputationChecker`/`LocalHeuristicChecker`/`URLHausChecker`/`ReputationResult`/`ReputationCheckUnavailable` — this time for real, since they now exist (Phase 1 had to revert a premature addition; this is the "add it as part of this phase" I flagged for myself back then).

## A real, serious implementation-time finding — not a minor detail
Running `make test` after wiring `composite_check()` into `scan_worker.py` **made every existing `URLScanner.scan()` test hit a real, live network call** — `scan_worker.py` runs in a genuinely separate subprocess (STORY-601's isolation boundary), so no in-process `unittest.mock.patch` in the test suite can reach it; `composite_check()`'s default (production-correct) behavior of attempting URLHaus fired for real, for every test that exercises a URL resource through `URLScanner.scan()`, `decide_access()`'s first-sighting background spawn, or onboarding a URL target. Confirmed this was real (not assumed) by timing `make test`: 57s vs. the ~43s baseline, and by directly curling the URLhaus endpoint from this environment to confirm it's reachable here.

This is a genuine regression risk this codebase has never had before (no other test anywhere depends on live network) — not just slow, but flaky in offline/CI/rate-limited environments, and a real (if small) load against a third-party service on every test run.

**Fix**: `composite_check()` gained an env-var gate (`SCALENE_SKIP_REMOTE_REPUTATION`, checked before ever calling `URLHausChecker`) — unset in production (real behavior), set by the test suite. Since `subprocess_isolation.run_scanner()` already copies the *parent* process's `os.environ` into the child's when spawning `scan_worker.py`, setting this in the test process before a scan happens reaches the subprocess correctly. Added a small shared helper (`tests/_env_guards.py`, not a test module itself) with `disable_remote_reputation()`/`restore_remote_reputation()`, wired via `setUpModule`/`tearDownModule` in every test file that touches a URL resource through a real scan path: `test_scanner.py`, `test_resource_verifier.py`, `test_onboard.py`, `test_hook_adapter.py`, `test_performance.py`, `test_cli.py`, `test_getting_started_docs.py`, `test_demo.py` (the last one via env inheritance into `subprocess.run()`'s default, since it runs `demo/run_demo.py` as its own subprocess). `test_reputation.py` itself is deliberately NOT gated — its `TestURLHausChecker`/`TestCompositeCheck` tests call the real functions in-process and mock `_query_urlhaus` directly, so they need the real (non-skipped) code path to exercise the mock.

Confirmed the fix: `make test` back to 44.7s (371 tests, includes the reputation tests I added), no live network involved.

## Test coverage added
`tests/test_reputation.py`: `TestURLHausChecker` (5 tests: no-results-trusted, listed-with-online-url-untrusted, listed-but-offline-trusted, network-error raises `ReputationCheckUnavailable`, unexpected query_status raises unavailable too) and `TestCompositeCheck` (6 tests: clean+clean, local-clean-but-remote-bad wins, local-bad-stays-bad-even-if-remote-clean, unreachable-degrades-with-visible-marker, degraded-result-still-shows-a-real-local-finding). All mock `_query_urlhaus` directly (in-process, no live network, no `SCALENE_SKIP_REMOTE_REPUTATION` involved since these bypass the subprocess boundary entirely).

## Verification
`make test`: 371/371.

## Handoff note for Tank
This phase requires Tank's review before it can be considered closed (task.md's own exit criteria) — outbound network call to a third-party service, no API key needed (confirm this holds in practice), timeout/rate-limit behavior under real call volume.
