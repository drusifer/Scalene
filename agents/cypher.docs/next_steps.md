# Next Steps

## Immediate Next Action
Sprint 8 (E14) closed and launched (2026-07-21). Nothing in-flight for Cypher.

## Waiting On
Nothing. **User direction (2026-07-21): the next sprint will do more scanner work** — the items below are explicitly earmarked for that sprint, not a generic future backlog. When that sprint starts, verify each against current code first (same discipline as every prior backlog pull), don't assume staleness.

## Planned Work — earmarked for the next (scanner-focused) sprint
- [ ] STORY-1405's reputation-score-drives-the-decision gap — should a scan's reputation score influence the allow/block decision (a real threshold), not just display alongside the label? Natural fit for a scanner-focused sprint.
- [ ] STORY-1406 (flagged, never committed, E14) — scanning a tool call's *response*, not just its arguments. Directly revisits §15's post_tool_use no-op rationale; needs its own architecture pass. Also natural scanner-sprint scope.
- [ ] Smith's post-close CLI UX findings on `scg onboard` (`agents/smith.docs/e14_cli_ux_review.md`): `--scanner` means two different things depending on `--list`; the interactive "select" sub-prompt asks what to exclude rather than include; `--sensitivity`/`--mode` both default permissive when omitted. Not scanner-specific, but `--scanner`'s naming overlaps directly with whatever new scanner work lands, so worth doing in the same pass.
- [ ] `docs/ARCHITECTURE.md` §5's stale Onboarding sequence diagram — 4th instance of diagram drift; if scanner work touches the onboarding flow again, fix it in passing rather than as a separate task.
- [ ] STORY-501's git-committed-attributability AC — still unchecked by design, lower priority, only pull in if compliance requirements sharpen.

---
*Last updated: 2026-07-21*
