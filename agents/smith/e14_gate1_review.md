# Smith Gate 1 Review — E14 (Tool-Call-Driven Onboarding via the Scanner Framework)

**Reviewed:** `docs/USER_STORIES.md` STORY-1401 through 1405 (STORY-1406 flagged, not committed)
**Verdict: APPROVE**

## Per-story notes

**STORY-1401 (scanner-identified targets replace `--target`)** — #2 Match Between System and Real World: the user no longer has to translate "the file I just touched" into a `file://<abspath>` URI by hand — onboard now recognizes it the same way the live hook already does. Reusing `Scanner.identify()` verbatim (not a second hand-rolled resolver) is also the right #4 Consistency call — two resolution paths that could silently drift apart is exactly the class of bug this project has hit before (onboard's own `_resolve_resource` already duplicated normalization logic once; good that this AC explicitly forecloses a second instance of that).

**STORY-1402 (confirm before scanning)** — #1 Visibility of System Status + #3 User Control and Freedom, both done right: nothing happens irreversibly (no scan, no write) before the user sees exactly what was identified. This is the single most important story in this epic from a UX standpoint, so I'm not leaving my input as an open question for Morpheus to guess at — see the hard requirement below.

**STORY-1403 (per-target scan gating)** — #5 Error Prevention, correctly scoped: partial success across a batch (some targets onboard, others don't) is more honest than all-or-nothing, and matches how a real multi-resource tool call actually looks. Good that `mode: block` on a bad finding still works per-target — no regression against sec16.

**STORY-1404 (per-scanner inventory)** — Testable in principle, but the AC as written ("visible somewhere a developer can actually check") isn't concrete enough to gate against yet. I'm not blocking Gate 1 on this — Cypher correctly left the storage question open for architecture — but Morpheus's design needs to land on an actual visible surface (a new `scg` subcommand, a `scg monitor` panel, `--list`?) before Gate 2, not stay abstract. I will test whatever surface gets chosen directly, the same way I tested `scg monitor`'s resource panel in Sprint 4.

**STORY-1405 (sensitivity + reputation score)** — One real concern: is the reputation score ever shown to the user, or only consumed internally by the allow/block decision? If it's invisible, a user has no way to sanity-check *why* something was trusted beyond a label — worse than today's single `label`, not better, on #1 Visibility of System Status. Non-blocking for Gate 1 (this is a display-surface decision, architecture's to make), but I want it in the `Verified: ...` onboarding confirmation output at minimum, not buried in a file only the machine reads.

**STORY-1406 (flagged, not committed)** — Correct call by Cypher not to fold this in silently. If Morpheus does decide to scope this in, it needs its own Gate 1 pass, not a retroactive addition to an already-approved epic — a decision this size (reversing §15's post_tool_use rationale) deserves the same story-writing discipline as everything else, not a shortcut because "it's related."

## Hard requirement for Gate 2 (same weight as §14.3's precedent)

**The confirmation mechanism (STORY-1402) must support a genuinely non-interactive path, not just a TTY prompt with no escape hatch.** This project's own test suite calls `onboard()` directly and its CLI is exercised in CI-shaped ways (`tests/test_onboard.py`, `demo/run_demo.py`) — a design that assumes an interactive human at every invocation would make onboarding un-scriptable and break the existing automated-testing pattern this whole project has used since Sprint 1. I want to see this decided explicitly in the architecture (a flag, an explicit target list on the CLI that skips the prompt, whatever) — not left implicit or discovered as a test-suite breakage during implementation.

**Also flagging now, not as a blocker but so it isn't a surprise at Gate 2:** removing `--target` is a real breaking change with more surface area than sec16's addition-only rework — I grepped and found it touches `demo/run_demo.py`, `tests/test_demo.py`, `docs/GETTING_STARTED.md`, and `docs/SETUP.md` directly, plus the `onboard()` library function's own call sites in `tests/test_onboard.py`/`tests/test_getting_started_docs.py`. Mouse's phase breakdown needs an explicit phase (or explicit task within a phase) for updating all of these — "the docs/demo still work" isn't a side effect I want discovered late, it's exactly the kind of thing Sprint 4's onboard re-scope handled correctly (Neo's own cross-phase doc-drift fixes) and I expect the same discipline here.

## Verdict
**APPROVE.** Stories are testable and user-facing. One hard requirement carried to Gate 2 (non-interactive path for STORY-1402), two non-blocking asks for architecture to land concretely (STORY-1404's visible surface, STORY-1405's score visibility), and an explicit flag that the `--target` removal's full breaking-change surface needs its own phase coverage, not an afterthought.
