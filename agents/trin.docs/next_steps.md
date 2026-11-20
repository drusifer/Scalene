## 2026-11-20
- Nothing pending. Process note: map ACs to tests at phase UAT.

# Next Steps

## Immediate Next Action — READ THIS FIRST ON COLD START
`*qa uat decide_access-correction` is DONE — PASS (2026-08-08). Both `decide_access()`'s corrected gate logic and the `RulesScreen` UX change (including the silent-downgrade bug I found and Neo fixed) verified, 602/602 at `make test`. Morpheus and Smith both subsequently approved; committed + pushed as `6d350fe`. Nothing in-flight for Trin.

Also worth knowing on cold start (not mine, Neo's direct-user-session work, same commit): `make test` dropped from ~600-625s to ~74s, and the 2 genuine full-journey E2E tests moved to `tests/uat_test_monitor_app_journeys.py` (`make test-uat`-only) — no formal Trin UAT pass has run against that change specifically.

## Waiting On
Nothing.

## Minor finding, not blocking (E15 Phase 1)
`make test-q ARGS="-k pattern"` doesn't actually filter — the `test-q` Makefile target runs `unittest discover`, which ignores `-k`. Neo's own `SKILL.md` documents `ARGS="-k pattern"` as valid usage for `test-q`; it isn't, for this target. Not an E15 bug, pre-existing infra/doc mismatch — flagging for Bob to correct the doc, not fixing the Makefile myself mid-sprint.

## Carried forward (still real)
- Driving a real pseudo-terminal (`pty.openpty()`) for any new interactive CLI prompt — apply again at Phase 4's mandatory Smith gate (the project-folder default's `--list` output).
- `make judge-trace` cumulative flags — still not re-measured since Sprint 6's `test-q` fix.

---
*Last updated: 2026-07-21*
