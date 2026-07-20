# Next Steps

## Immediate Next Action
`*qa retest sec16 bug` complete (2026-07-20) — Neo's `--help` discoverability fix verified for real. Handed back to Smith for her re-gate.

## Waiting On
Smith's re-approval, then retro → Cypher launch (Sprint 7).

## Resolved
My earlier carried note (`--mode mask` rejection message unreachable from the real CLI) is now closed — Neo's epilog fix covers both my finding and Smith's, verified together.

## Planned Work (Sprint 5 close)
- [ ] If Smith files a `*user bug`, triage per protocol (correctness → Neo, UX → Neo+Smith re-test).
- [ ] My own retro input when `*sprint retro` happens: (1) this sprint's phase-boundary discipline (Neo correctly deferred `sensitivity`/`mode` test-writing to Phase 2 rather than jumping ahead) — positive pattern, contrasting with Sprint 4's premature-parameter gaps. (2) adversarial regex-validation testing caught a real hot-path crash before it shipped — worth keeping "construct a hostile config value, not just a hostile call" as standard UAT practice for any new user-authored-config feature. (3) a mid-implementation architecture amendment (mode=allow) happened cleanly this sprint because it was raised immediately rather than discovered at close — worth naming as the right instinct to keep.
- [ ] Carried, not blocking: flagged to Smith that a rule with `pattern: ".*"` + `mode: allow` can blanket-disable scanning at the rule level even though `PolicyConfig.mode` can't — deliberate/reviewable, not automatic, but worth her opinion on whether a warning is worth adding later.

## Loose ends (not blocking, carried from Sprint 4)
- [x] Sprint 3 is closed (2026-07-16) — resolved, no longer open.
- [ ] `make judge-trace` cumulative flags were climbing last sprint. `make test-q` (the documented fix) still doesn't exist as a target — still a real tooling gap to raise with Bob/Mouse eventually.

---
*Last updated: 2026-07-17*
