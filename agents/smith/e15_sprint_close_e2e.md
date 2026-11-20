# Smith — `*user test E15` — Sprint 9 close, full end-to-end — 2026-07-21

Not a phase gate — confirming all 4 E15 stories cohere as one continuous real session, same standard as Sprint 8's `TestE14EndToEndUserJourney`. Written as a real, permanent test (`tests/test_cli.py::TestE15EndToEndUserJourney`), not a narrated transcript — same discipline reinforced twice already this session.

## What the test covers, in one session via the real `scalene-guard` hook adapter
1. A brand-new project (no `scalene_policy.yaml`) — first real call creates it with the project-folder default rule (STORY-1504), call allowed.
2. The same file, now with a real clean scan cached — resolves `validated_allow`.
3. A **second**, different clean project file in the same session — also allowed, the actual friction STORY-1504 exists to remove (doesn't hit the "second uncleared resource in a low-trust session blocks" wall).
4. `/etc/hostname` in the same session — **still blocked**, unconditionally (STORY-1502), proving the project-folder default can't paper over a hardcoded-restricted path even mid-session.

STORY-1501 (config-driven registry) and STORY-1503 (composite reputation) are exercised indirectly — every one of these calls goes through the default scanner registry and (for the reputation half) the composite-check code path, degraded to local-only via `SCALENE_SKIP_REMOTE_REPUTATION` per this sprint's own test-hermeticity fix.

## Verdict

**PASSED.** `make test`: 390/390 (full suite, this new test included). No new bugs — every phase's own gate already did its job; this confirms they compose correctly as one real user journey, not just individually.

@all `*sprint retro`.
