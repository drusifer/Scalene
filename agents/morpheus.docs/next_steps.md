# Next Steps

## Immediate Next Action
`*lead review sec15` complete (2026-07-18) — approved, one real duplication + 3 doc-drift issues found and fixed. Handed to Oracle for grooming.

## Waiting On
Nothing. Next in the resumed close sequence: Oracle groom → Smith end-to-end test → retro → Cypher launch.

## Planned Work
- [x] Resolved all 4 of §13.8's open questions into concrete decisions (§14.1, §14.5).
- [x] Named the rule-matching/unconditional-scan NFR consequence explicitly rather than leaving it a footnote (§14.4's `NFR-Perf-UnconditionalScan`).
- [x] Surfaced the migration story explicitly (§14.6).
- [x] Verified Mouse's phase breakdown matches §14 exactly, plan LOCKED.
- [ ] At Phase 1 review: confirm the repo's own `scalene_policy.yaml` migration (task 1.3) and §4's class diagram restoration both actually landed, not just claimed.
- [ ] At Phase 3 review: this is the first phase where I should personally re-verify the `NFR-Perf-UnconditionalScan` measurement myself (same pattern as my own Sprint 4 Phase 2 finding), not just trust Neo's/Trin's reported number.

---
*Last updated: 2026-07-17*
