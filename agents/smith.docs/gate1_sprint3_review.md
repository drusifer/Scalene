# Smith — Sprint 3 Gate 1 Review (E9: Documentation & Onboarding)

**Date:** 2026-07-13
**Stories reviewed:** STORY-901 (GETTING_STARTED.md), STORY-902 (USER_GUIDE.md), STORY-903 (demo)
**Verdict:** APPROVED, one non-blocking note.

## Review

All three stories have testable, user-facing acceptance criteria (not vague adjectives):
- STORY-901: copy-pasteable on a clean clone, ends in an observed concrete masked event, timed under 5 minutes (I'll verify by timing a cold run at UAT).
- STORY-902: every CLI command/flag verified against actual `--help` output (not assumed), troubleshooting section required.
- STORY-903: scripted/repeatable, offline, and checked by `make test`/a smoke test so it can't silently rot — this addresses a real risk (demos going stale) rather than a hypothetical one.

All three explicitly require linking to existing docs (README, SETUP.md, ARCHITECTURE.md) instead of duplicating content. This matters here specifically: Sprint 2's retro flagged 2 AC-text-vs-implementation drift items found only at UAT time, so avoiding a second copy of the same facts is the right call for this project, not boilerplate caution.

## Non-blocking note for implementation (STORY-902)

My 2026-07-09 `*user consult` (see `agents/smith.docs/context.md`) found a real Nielsen #6 (recognition over recall) gap: `scalene onboard` requires `--tool`/`--jsonpath`/`--pattern`/`--target` up front with no example of a tool's actual call shape to copy from. E7's monitor console already solved half of this (suggested onboard commands from real blocked calls). USER_GUIDE.md should surface that suggested-command workflow prominently as the primary onboarding path, not the raw manual-flag flow — that's the single highest-leverage discoverability fix available today, and burying it in the guide would waste it.

## Gate Decision

Approved. Proceeding to Morpheus for architecture (Gate 2 next).
