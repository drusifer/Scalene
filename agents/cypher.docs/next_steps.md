# Next Steps

## Immediate Next Action
Sprint 12 (E18, Review Queue Overhaul & Rules Editing) closed and launched (2026-08-07). Nothing in-flight for Cypher. Not yet committed/pushed — ask the user before doing so (this session did not commit; a prior session's precedent has the user explicitly requesting commit+push after `*pm launch`, but that instruction doesn't carry forward automatically).

Sprint 11 (E17, Queue-First Monitor Redesign) closed and launched (2026-08-04), committed and pushed (`7ccc4d2`, `origin/main`).

## Waiting On
Nothing. Next sprint direction not yet given by the user.

## Backlog (from E18 retro, agents/cypher.docs/e18_retro_backlog.md)
- [ ] Decision-undo/redo (Verify/Allow/Deny) — explicitly deferred by direct user choice this epic. Needs its own design pass on safe unwind semantics (Allow/Verify write to shared files something else may already rely on) before it's storied.
- [ ] The armed/confirm idiom (skip-all, rule-delete) is now used twice, independently implemented per screen — `docs/ARCHITECTURE.md` §23.8 flags extracting a shared helper if a 3rd destructive action appears. Not urgent yet.
- [ ] `decide_access`'s clean-session free-pass is a recurring test-design trap (hit twice independently this sprint) — durable lesson recorded (`agents/oracle.docs/lessons.md`, 2026-08-07 entry), worth checking new tests against going forward.

## Planned Work — still-open backlog, deliberately not folded into E17
- [ ] **New (E17)**: resource-cache freshness/Last-Scanned display (STORY-1005, the `is_fresh()` display gap Smith originally flagged in the E16 consult) is now fully retired with no successor — real capability loss, worth a real product decision (bring it back in some form vs. genuinely not needed) rather than leaving it silently gone.
- [ ] **New (E17)**: a session-history/scrollback browser for a non-latest session — capability the Sessions-table removal cost (`docs/ARCHITECTURE.md` §22.6). Only worth building if it becomes a real complaint, not preemptively.
- [ ] **Note (E17)**: `PolicyRule.trust` now at least has read visibility (the Rules screen's Trust column) but still no CLI (`scg onboard --trust`) or TUI *editing* exposure — the item below is only partially addressed, not resolved.
- [ ] **Carried (2026-07-30, §21.10)**: `PolicyRule.trust` has no CLI (`scg onboard --trust`) or TUI (Allow form field) *edit* exposure yet — hand-authored in YAML only. Real product surface gap once someone other than the person who built it needs to use it.
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
- [ ] **Process note (E17, Smith)**: a destructive `git checkout -- <file>` mid-session reverted more than intended (a 4-line temp test patch turned into wiping an entire uncommitted phase). Fully recovered, no data lost, but worth reinforcing: targeted `Edit`, never a destructive git command, for a change that specific.

---
*Last updated: 2026-08-05*
