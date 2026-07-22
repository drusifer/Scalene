# Next Steps

## Immediate Next Action
Sprint 9 (E15) closed and launched (2026-07-21). Nothing in-flight for Cypher.

## Waiting On
Nothing. Next sprint direction not yet given by the user — when it is, verify each backlog item below against current code first (same discipline as every prior pull), don't assume staleness.

## Planned Work — still-open backlog, deliberately not folded into E15
- [ ] STORY-1405's reputation-score-drives-the-decision gap — should a scan's reputation score influence the allow/block decision (a real threshold), not just display alongside the label? Now doubly relevant since E15/STORY-1503 shipped a real external reputation source (URLhaus) — the score is no longer purely local-heuristic-derived either.
- [ ] STORY-1406 (flagged, never committed, E14) — scanning a tool call's *response*, not just its arguments. Directly revisits §15's post_tool_use no-op rationale; needs its own architecture pass.
- [ ] Smith's post-close CLI UX findings on `scg onboard` (`agents/smith.docs/e14_cli_ux_review.md`): `--scanner` means two different things depending on `--list`; the interactive "select" sub-prompt asks what to exclude rather than include; `--sensitivity`/`--mode` both default permissive when omitted.
- [ ] `docs/ARCHITECTURE.md` §5's stale Onboarding sequence diagram — 4th+ instance of diagram drift, still not fixed across 2 more sprints now.
- [ ] STORY-501's git-committed-attributability AC — still unchecked by design, lower priority.
- [ ] New from Sprint 9's retro: whether the "auto-created default rule can be shadowed" bug-shape (backlog item 2) has any other instances elsewhere in the rule-writing system worth auditing for, not just the one instance fixed this sprint.
- [ ] New from Sprint 9: someone with a real URLhaus Auth-Key should confirm one successful authenticated call before relying on STORY-1503 in production (Tank flagged this — he can't obtain a key himself).

---
*Last updated: 2026-07-21*
