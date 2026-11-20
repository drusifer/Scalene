# Smith Gate 2 Review — E14 Architecture (`docs/ARCHITECTURE.md` §17)

**Reviewed:** §17.1-17.9
**Verdict: APPROVE**

## Hard requirement check (from Gate 1)

**Satisfied.** §17.3's design gives a real non-interactive path two ways — `--yes` (accept everything identified) and `--only IDENTITY,...` (accept exactly a named subset, fails loud if a named identity wasn't actually found). Both bypass the prompt entirely, and the fail-fast-on-no-TTY behavior is exactly the right shape: rather than a script/test silently hanging on a `read()` that will never return, it gets a clear, immediate `OnboardError` telling it to pass `--yes`/`--only`. This is #5 Error Prevention done correctly — the failure mode a CI run would otherwise hit (indefinite hang) is converted into an immediate, actionable error.

## Non-blocking Gate 1 asks, now checked

**STORY-1404 (inventory)** — `--list [--scanner NAME]` is concrete enough to test directly once built. Good call reusing `ScanCache` instead of new state — fewer places for "what's actually onboarded" to drift from "what the cache says," which is exactly the kind of question I'd otherwise have to chase down myself at end-to-end test time.

**STORY-1405 (reputation visibility)** — `Verified: reputation:https://x.com -> trusted (score 1.00)` in §17.6 satisfies my ask directly; the score isn't buried in a file only the machine reads.

**Breaking-change surface** — §17.8 names the real files I grepped at Gate 1. This is architecture correctly surfacing the list, not architecture claiming to have fixed it — I'll hold Mouse's phase plan to actually covering every one of them, not just this section acknowledging they exist.

## One new, non-blocking note

**Batch-level `--sensitivity`/`--mode` (§17.4)** applies identically to every confirmed target in one invocation. A tool call that legitimately touches both a public doc and a genuinely sensitive internal URL in the same call would need two separate `scg onboard` runs (via `--only`, once per desired axis value) to classify them differently — the architecture doesn't silently misclassify anything, it just requires the developer to notice and split the confirmation manually. Not blocking: `--only` is a real, already-designed escape hatch for exactly this, not a workaround I'm inventing. Flagging so Trin's UAT specifically tries a mixed-sensitivity tool call rather than only single-target happy-path cases.

## Verdict
**APPROVE.** My Gate 1 hard requirement is concretely satisfied, not just gestured at. Handing to Mouse for phase breakdown.
