# Next Steps

## Immediate Next Action
Phase 2 approved (2026-07-21, after 1 fix round — an axis-validation ordering bug I caught by mocking a real interactive run). Handed to Smith for the mandatory gate.

## Waiting On
Smith's gate verdict. If approved: Phase 3 (demo/docs/existing-test reconciliation, no separate gate) closes out the 5 known Phase-3-scoped test failures, then Oracle groom → Smith end-to-end test → retro → Cypher launch.

## Watch-items for my own Phase reviews (once implementation starts)
- Confirm `main()` genuinely fails fast (no hang) when stdin isn't a TTY and neither `--yes`/`--only` is given — this is the piece protecting the test suite, don't just trust it works, verify it.
- Confirm `LocalHeuristicChecker.check()`'s evaluate-all-3 change doesn't silently change `is_trusted`'s truth table — only the score should be new, the boolean's meaning must be provably unchanged (a good spot for Trin to diff old-vs-new behavior across a matrix of trigger combinations).
- Confirm §17.8's real breaking-change surface (demo, tests, GETTING_STARTED.md, SETUP.md) is actually a named task in Mouse's phase breakdown, not assumed to happen incidentally.

## Planned Work
- [x] Resolved all 4 of §13.8's open questions into concrete decisions (§14.1, §14.5).
- [x] Named the rule-matching/unconditional-scan NFR consequence explicitly rather than leaving it a footnote (§14.4's `NFR-Perf-UnconditionalScan`).
- [x] Surfaced the migration story explicitly (§14.6).
- [x] Verified Mouse's phase breakdown matches §14 exactly, plan LOCKED.
- [ ] At Phase 1 review: confirm the repo's own `scalene_policy.yaml` migration (task 1.3) and §4's class diagram restoration both actually landed, not just claimed.
- [ ] At Phase 3 review: this is the first phase where I should personally re-verify the `NFR-Perf-UnconditionalScan` measurement myself (same pattern as my own Sprint 4 Phase 2 finding), not just trust Neo's/Trin's reported number.

---
*Last updated: 2026-07-17*
