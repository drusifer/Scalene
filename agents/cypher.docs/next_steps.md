# Next Steps

## Immediate Next Action
Sprint 10 (E16) closed and launched (2026-07-23). A large, direct-with-the-user fast-track session on 2026-07-30 (no formal story cycle — see `docs/ARCHITECTURE.md` §21, `agents/neo.docs/current_task.md`) fixed real bugs found dogfooding `scg monitor` and added `PolicyRule.trust` + rule-change auto-resolution. Pushed (`origin/main` at `f167df6`). Nothing in-flight for Cypher; the §21 work never went through a formal Gate 1/2 review chain — real, legitimate carried review debt, same shape §16 once flagged for itself.

## Waiting On
Nothing. Next sprint direction not yet given by the user — when it is, verify each backlog item below against current code first, don't assume staleness.

## Planned Work — still-open backlog, deliberately not folded into E16
- [ ] **New (2026-07-30, §21.10)**: `PolicyRule.trust` has no CLI (`scg onboard --trust`) or TUI (Allow form field) exposure yet — hand-authored in YAML only. Real product surface gap once someone other than the person who built it needs to use it.
- [ ] **New (2026-07-30, §21.10)**: pending-review auto-resolution (§21.9) only runs right after a review is explicitly resolved, not on every poll tick — a hand-edited policy file won't retroactively clear now-covered reviews until the next resolution happens.
- [ ] **New (2026-07-30)**: the whole §21 session (directory-scan fix, `Scanner.match()`/gitignore matching, `Scanner.from_config()`, monitor persistence fixes, `PolicyRule.trust`, rule-change auto-resolution) shipped without a formal Trin UAT / Morpheus review / Smith gate — real review debt, worth a retroactive pass through the normal chain even though it's already live and tested.
- [ ] STORY-1606's hash-snapshot detect-and-restore mechanism — fully designed (`docs/ARCHITECTURE.md` §20.6), not built. Backlogged per direct user decision.
- [ ] **New (E16)**: pre-existing shared-`.scalene/audit.log` test-hygiene gap (several tests don't override `audit_log_path`) now confirmed to cause a real, if rare, test flake — worth a real audit pass, not just a theoretical concern.
- [ ] STORY-1405's reputation-score-drives-the-decision gap — should a scan's reputation score influence the allow/block decision (a real threshold), not just display alongside the label? Now doubly relevant since E15/STORY-1503 shipped a real external reputation source (URLhaus) — the score is no longer purely local-heuristic-derived either.
- [ ] STORY-1406 (flagged, never committed, E14) — scanning a tool call's *response*, not just its arguments. Directly revisits §15's post_tool_use no-op rationale; needs its own architecture pass.
- [ ] Smith's post-close CLI UX findings on `scg onboard` (`agents/smith.docs/e14_cli_ux_review.md`): `--scanner` means two different things depending on `--list`; the interactive "select" sub-prompt asks what to exclude rather than include; `--sensitivity`/`--mode` both default permissive when omitted.
- [ ] `docs/ARCHITECTURE.md` §5's stale Onboarding sequence diagram — 4th+ instance of diagram drift, still not fixed across 3 more sprints now.
- [ ] STORY-501's git-committed-attributability AC — still unchecked by design, lower priority.
- [ ] Whether the "auto-created default rule can be shadowed" bug-shape has any other instances elsewhere in the rule-writing system worth auditing for, not just the one instance fixed in Sprint 9.
- [ ] Someone with a real URLhaus Auth-Key should confirm one successful authenticated call before relying on STORY-1503 in production (Tank flagged this — he can't obtain a key himself).

---
*Last updated: 2026-07-23*
