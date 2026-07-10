# Next Steps

## Immediate Next Action
Approved "copyable system messages" (post-sprint-1 ad hoc feature, not a formal story). Handed to Smith for the `*impl` chain's required UX gate (this changes developer-facing `systemMessage`/audit-log behavior). No active Morpheus task after that until Sprint 2 planning starts.

## Waiting On
Nothing from me — Smith's UX test, then done.

## Planned Work
- [ ] If/when a second harness adapter is built: relocate `_suggest_onboard_command()` out of `hook_adapter.py` into the policy-engine layer (see context.md finding) — cheap now, real duplication cost later if forgotten
- [ ] If a retrospective happens: worth carrying forward — (1) strict TDD test-first (user correction early in Sprint 1, applied consistently after), (2) `make <target>` as the only way to run build/env tasks, (3) don't trust a persona's own stated numbers/status without independently recounting/re-checking (Trin's traceability-doc catch, and again this session with the shell-quoting bug)
- [ ] Sprint 2 scope: not yet defined

---
*Last updated: 2026-07-09*
