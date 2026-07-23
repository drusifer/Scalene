# Sprint 10 (E16) Retro Backlog

Compiled from all 6 persona retro posts (Neo, Trin, Morpheus, Oracle, Mouse,
Smith). No Tank retro this sprint — task 6.3 was shelved before Tank's
task started, not an oversight.

## Central theme

This sprint's story origin (a fully-worked-through `*user consult` between
Smith and the user, resolving both hard design questions before a single
story existed) produced unusually low churn at Gate 1/2 — worth repeating
as a pattern for future feature-shaped requests, not just bug-shaped ones.
Against that, two real mid-sprint corrections (STORY-1603's cost-conflation
mis-scoping, STORY-1606's mechanism pivot) both landed at the architecture/
implementation layer, not the story-writing layer — both handled by
re-running the relevant gate/phase rather than assuming prior approval
carried over, same discipline as every prior sprint's corrections.

## Backlog items (new this sprint)

1. **STORY-1606's hash-snapshot detect-and-restore mechanism is fully
   designed, not built** (`docs/ARCHITECTURE.md` §20.6) — policy-file
   tamper detection via snapshot+hash comparison on every load, restore on
   mismatch, operator-only notification via `scg monitor`'s attention
   signal. Backlogged per direct user decision, ready to pick up as its own
   phase/sprint whenever prioritized.
2. **The no-ad-hoc-verification rule applies to debugging, not just
   feature-confirmation** (Trin) — reinforced a 4th time this session
   (`feedback_no_adhoc_bash_verification.md`) after reaching for scratch
   debug scripts mid-diagnosis of 2 real test failures. Sharper framing
   recorded: when a test fails and the fix isn't obvious, narrow with a
   real test (or a temporary assertion inside the real failing test), never
   a throwaway interactive script.
3. **Cost-class conflation is a real, repeatable mistake shape** (Morpheus,
   recorded as a durable lesson) — treating "new hot-path I/O" as one
   undifferentiated risk bucket, instead of naming the specific operation
   and confirming it's the same cost class as whatever was previously
   measured. Worth a standing checklist item for future NFR-adjacent scope
   decisions: name the operation, don't borrow another operation's weight.
4. **Off-screen/clipped widget clicks are silent no-ops in Textual tests**
   (Trin/Neo, recorded as a durable lesson) — a distinct failure shape from
   the existing "row-content check is not a rendering check" lesson;
   worth checking terminal/viewport size before assuming an interaction
   test's failure is application logic.
5. **The pre-existing shared-`.scalene/audit.log` test-hygiene gap
   (flagged Phase 1) caused a real, if rare, flake this sprint** — several
   perf/other tests don't override `audit_log_path`, writing into this
   repo's own real (very large, dogfooded) audit log. Not fixed this
   sprint (out of scope, pre-existing), but now confirmed to cause
   observable flakiness, not just theoretical disk growth — worth a real
   pass auditing test files for missing `audit_log_path=`/`cache_path=`
   overrides.

## Carried, not part of this sprint, unaffected

- STORY-1405 (reputation-score-drives-decision), STORY-1406 (post-call
  scanning), Smith's `scg onboard` CLI UX findings (`e14_cli_ux_review.md`),
  `docs/ARCHITECTURE.md` §5's stale diagram, STORY-501's git-attributability
  AC, the shadowed-default-rule audit, and the URLhaus Auth-Key production
  confirmation — all still open, none touched by E16.
