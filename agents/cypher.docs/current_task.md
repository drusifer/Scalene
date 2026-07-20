# Current Task

**Status:** Sprint 7 (E13, sec16 correction) closed. `*pm launch` posted.
**Assigned to:** Cypher
**Started:** 2026-07-20

## Task Description (most recent): Sprint 7 (E13/sec16) close — retro compile, `*pm launch`
Compiled retro backlog from all 6 persona inputs. Central theme: this is the 2nd sprint in a row (after sec15) where real engineering shipped directly with the user ahead of formal review — and the 2nd time in a row the after-the-fact gate chain caught something genuinely real rather than rubber-stamping already-working code (sec15: a structural safety gap; sec16: a first-use CLI discoverability regression against Smith's own prior hard requirement). Updated `docs/PRD.md` (new E13 epic row, Sprint 7 goals 22-23) and `task.md` (Sprint 7 section + top status line marked closed).

## Retro Backlog (Sprint 7)
1. **"Implement fast with the user, gate formally after" is validated as a working pattern here — but only because the gate chain actually runs every time** (Smith, Neo) — 2 sprints running now where this shape produced real findings, not theater. Worth naming explicitly rather than treating it as an exception each time it happens.
2. **"Run the real `--help`/CLI output cold, like a first-time user" is a distinct UAT/gate technique from "CLI output matches the docs"** (Trin, Smith) — worth naming alongside the existing mutate-verify-revert and real-binary techniques already recorded from Sprint 6.
3. **Stories can drift through multiple undocumented mechanism changes before anyone walks them back to source** (Oracle) — STORY-501 went through 3 changes across Sprints 1/4/7 before this groom reconciled it. Recommend a periodic full-story-sweep against current `ARCHITECTURE.md`, not only triggered by the sprint that happens to touch a given story.
4. **Small, single-surface corrections correctly skip Mouse's phase-planning role** (Mouse) — confirms the pattern from sec15/Sprint 6, not a new finding, but worth reconfirming since Mouse sitting out 2 sprints in a row could otherwise look like an oversight rather than a deliberate scope fit.
5. **A "hard requirement, carried forward" tag on an architecture decision reads as more permanent than intended** (Morpheus) — §14.3 was written as Smith-Gate-locked; reversing it needed a full new numbered section to feel legitimate. Worth a lighter tag for decisions genuinely expected to be revisited.

## Progress
- [x] Read all 6 persona retro posts in `agents/CHAT.md`.
- [x] Compiled backlog above, no items invented — every line traces to a specific persona's post.
- [x] `docs/PRD.md`: added E13 epic row, Sprint 7 Goals section (22-23), updated the Sprint-to-epic mapping line.
- [x] `task.md`: Sprint 7 section marked closed, top status line updated, test count corrected to 291/291.
- [x] `*pm launch` posted to CHAT.md.

## Task Description (next, unstarted): write E11 stories from Morpheus's §13.8 design
A direct user design conversation (2026-07-16/17, after Sprint 4's close) found a real defect in shipped E10 code and worked through a full replacement design with Morpheus. **Read `docs/ARCHITECTURE.md` §13.1's revision note and §13.8 in full before starting** — the design is already written, this task is to formalize it as proper user stories so it goes through Smith's Gate 1 like every other sprint, not to invent it from scratch.

**Core of what §13.8 designed** (condensed for story-writing):
1. §13.1 was wrong: `URLScanner`'s host-only resource identity reproduces the exact "one scan vouches for an unbounded future set" defect E10 existed to fix (trusting `github.com` trusts every repo on it, not just the one that was scanned).
2. Trust and Sensitivity are independent axes, not parallel signals: Trust = could this source inject malicious instructions (prompt-injection/tool-poisoning risk); Sensitivity = blast radius if something goes wrong, exactly 3 levels (Public / Internal Only / Restricted).
3. Masking becomes unconditional via an implicit default top-level rule (any tool, any args, `sensitivity: public`, `mode: mask`) — content-scanning is a universal baseline, not gated by classification.
4. `PolicyRule` returns (jsonpath + pattern, generic across any tool's arg shape) but only decides *candidacy/identity* — the scan cache still verifies and freshness-tracks per distinct matched identity, so a wildcard pattern can't vouch for anything unchecked. New fields: `tool`, `jsonpath`, `pattern`, `sensitivity`, `mode` (mask|block), `scanner` (optional), `description`.
5. Explicitly NOT yet decided (§13.8's own list): exact JSONPath for "any argument," whether `scanner` must be explicit or inferred, real on-disk schema, how `scg onboard --target` maps onto a generated rule.
6. **Not in §13.8, flagged by Morpheus's own next_steps.md as a gap**: this changes a shipped, closed-sprint on-disk format (`scan_cache.json` key scheme) and `scalene_policy.yaml`'s schema — needs a real migration/compatibility story for existing projects, not just "re-onboard everything." Surface this explicitly as a story or an open question, don't let it get silently skipped.

## Progress
- [x] Wrote 5 stories (STORY-1101 through 1105) into `docs/USER_STORIES.md`, condensing §13.8's full design into testable ACs.
- [x] STORY-1101 covers the core defect fix (host-level trust granularity).
- [x] STORY-1102/1103 split trust vs. sensitivity and add per-rule `mode`, resolving the original mask/block proposal that opened this thread.
- [x] STORY-1104 makes content-scanning an unconditional baseline (removes `MaskingEngine`'s current provenance-risk gate).
- [x] STORY-1105 explicitly covers the scan-cache migration gap Morpheus flagged (not in §13.8 itself) — did not let it get silently skipped.
- [x] Carried §13.8's own 4 explicit open questions forward as an "open questions for Morpheus" list in the epic header, not pre-decided.
- [x] Updated `docs/PRD.md` epic table (added E11 row) + added Sprint 5 Goals section (14-17).
- [x] Corrected `docs/USER_STORIES.md`'s header status line (was stale: said Sprint 3 unclosed / Sprint 4 draft-pending-gate1, both wrong by this point).
- [x] Handed off to Smith for Gate 1 review.

## Blockers
None — awaiting Smith's Gate 1 verdict.

## Oracle Consultations
None yet.

---
*Last updated: 2026-07-17*

## Task Description (most recent): Sprint 3 close — retro, `*pm launch`
Compiled retro backlog from all 6 persona inputs (Neo, Trin, Morpheus, Oracle, Mouse, Smith). Central theme across nearly every input: this sprint's real lesson isn't about code, it's about how a completed-but-ungated phase silently sat open for 2 days of unrelated work with no mechanism catching it.

## Retro Backlog (Sprint 3)
1. **A handoff is not a completed step** (Neo, Trin): `*swe handoff` to Trin sat unactioned across an unrelated multi-day work stretch; Trin's own `next_steps.md` correctly recorded the pending UAT the entire time, but nothing forced consulting it before the next session moved on. Recommend: cold-start protocol should explicitly check for any unresolved handoff addressed to the persona being activated before starting new work, not just read state files passively.
2. **`task.md`'s own DONE markers lagged reality** (Oracle) — Sprint 3's header still read "Planned, pending review" 2 days after 2 of 3 phases had actually passed every gate; Sprint 1/2/4 all got markers immediately at each phase's approval, Sprint 3 didn't. This is likely the direct, mechanical reason the gap wasn't noticed sooner. Recommend: DONE markers land in the same commit as each phase's own approval, not deferred.
3. **A 3rd status bucket may be warranted** (Mouse): "implemented but gate unconfirmed" is a real, distinct state from both "in progress" and "done" that nothing currently tracks explicitly.
4. **Real-subprocess architecture decisions pay off at exactly moments like this** (Morpheus): the demo's "real subprocess, never mocked" design meant re-verifying it against Sprint 4's changed behavior was "run it again," not "update a stale mock."
5. Sprint 4's retro backlog (recurring test-hygiene gap-shape, architecture claims needing a named verification step, screenshot-check UI, cross-check ACs against architecture as decisions happen) remains open and unaffected by this close — not re-litigated here.

## Task Description (prior): Sprint 4 close — retro, story accuracy pass, `*pm launch`
- [x] Acted on Oracle's groom-pass flag (`agents/oracle.docs/e10_story_staleness_flag.md`) rather than letting it sit until "someday": rewrote STORY-1001 in `docs/USER_STORIES.md` — its premise (user-facing `pattern` capture groups) was superseded by Morpheus's §13.1 full-replacement decision partway through the sprint, and the story as originally worded would never literally be satisfied. Kept the original text visible with a dated revision note rather than silently rewriting history.
- [x] Fixed STORY-1003's cache-key wording (said `(path, mtime)` as the key; the real key is path alone, `mtime` is a value field) — same principle, correct rather than mark-satisfied-as-literally-wrong.
- [x] Checked off all 5 stories' ACs (all verified true via real testing across the phase Bloop, not assumed).
- [x] Compiled retro backlog from all 6 persona inputs (Neo, Trin, Morpheus, Oracle, Mouse, Smith) — see Progress below.
- [x] `*pm launch` posted.

## Retro Backlog (compiled from all persona inputs)
1. **Recurring gap-shape, worth a standing checklist item**: test-hygiene mechanics (a new state-carrying parameter not threaded through every test call site) recurred 3x this sprint alone (Neo); row-count-only UI tests missing content checks recurred across 2 sprints (Trin). Both are the same underlying failure mode — a new parameter/dimension added to an interface, with the update to its *consumers* (here: tests) incomplete. Worth a written checklist item for future phases: "when adding a new constructor/function parameter, grep for every existing call site, don't rely on remembering them."
2. **Architecture claims about runtime behavior need empirical verification built into the plan, not left as a "verify later" footnote** (Morpheus, Oracle): the latency claim and the exit-code assumption were both flagged as "needs verification" in the architecture doc and both turned out wrong. Recommend: future architecture docs should name a *specific verification step* with an owner and phase, not just a caveat sentence.
3. **Screenshot-check UI changes before approving, not just Pilot data-model tests** (Smith, Oracle) — now recorded as a durable lesson in `agents/oracle.docs/lessons.md`.
4. **Cross-check story ACs against architecture decisions as they're made, not just at sprint close** (Oracle) — STORY-1001's divergence sat unnoticed for 3 phases. Recommend: Morpheus's phase reviews should flag AC/architecture mismatches to Cypher inline, not wait for the groom pass to surface them.
5. **Sprint 3 is still not formally closed** — carried forward again, not resolved this session. Flagging explicitly rather than letting a 3rd sprint stack on top of it unaddressed.

## Task Description (prior): Sprint 4 (E10) stories drafted, approved at both Gate 1 and Gate 2, architected (Morpheus §13), phased (Mouse), and plan LOCKED (Morpheus).

## Task Description (most recent): `*pm plan sprint` — Sprint 6 (E12, tech debt)
Wrote 3 stories (STORY-1201-1203) from the Sprint 3-5 retro backlog. Deliberately verified each carried-forward item against current code *before* writing a story for it — 2 items were already resolved (`_suggest_onboard_command` deleted in the sec15 rework, `cache_refresh_worker.py`'s exception-handling gap closed in Sprint 4 Phase 4) and 2 were judged low-value/dormant (scan-cache TOCTOU, `evaluate()`'s hardcoded 2-scanner aggregation — the latter is dead code since sec15, not part of the live path). Explicitly scoped out the retro backlog's process/Bob-protocol items (3rd status bucket, standing hostile-input-testing protocol, cold-start handoff checks) as not this sprint's domain. Updated `docs/PRD.md` epic table + added Sprint 6 goals (19-21). Handed to Smith for Gate 1.

## Task Description (prior): Sprint 5 (E11 → sec15) close — retro compile, `*pm launch`
Compiled retro backlog from all 6 persona inputs (Neo, Trin, Morpheus, Oracle, Mouse, Smith). Central theme: this sprint's real defect was caught by a gate specifically designed to *run the software adversarially*, not review it on paper — every persona's retro independently converges on the same point from a different angle.

## Retro Backlog (Sprint 5)
1. **A mandatory "actually run it" gate is what caught this sprint's real defect** (Smith, Trin, Morpheus) — `mode: allow` passed code review, 2 Smith gates, and every unit test written against its own acceptance criteria; only Smith's adversarial live-test (a blanket `pattern:".*"` rule) found it reproduces the project's own core defect. Recommend: codify "try the laziest/broadest possible input, not just a contrived edge case" as a standing step in Smith's/Trin's testing protocol specifically for any trust/permission feature, not left to instinct each time (already started: `agents/oracle.docs/lessons.md`).
2. **Docs/diagrams drift silently — nothing tests them** (Morpheus) — found 3 real stale references (`TaintState` fields, `MaskingEngine.decide()`'s signature, a whole sequence diagram) during architecture review that no automated check would have caught, since Mermaid diagrams and prose aren't executable.
3. **No status bucket exists for "phase implemented+gated, then superseded by a finding in that same gate"** (Mouse) — a real, recurring gap-shape (echoes Sprint 3's retro flag about missing status buckets); still not built.
4. **Reflexive backwards-compatibility instinct needs a check-first habit** (Neo) — defaulted to writing migration/fallback handling for an internal format change unprompted; user explicitly didn't want it. Saved as a durable feedback memory this session; worth reinforcing as a team habit, not just a one-off correction.
5. **The append-only-correction convention scales to a mid-sprint pivot this large** (Oracle) — confirmed, not just a small-fix pattern.
6. **CHAT.md hit the archive threshold mid-sprint** (Oracle) — archiving may need to become routine during a sprint, not just at close.

## Task Description (prior): Direct user design session (2026-07-14) identified a real gap in the just-shipped URI-scheme onboarding model (commit `df8eb08`): a rule's one-time scan of a representative `target` can vouch for an unbounded, never-rescanned future set matched by `pattern`. User specified a replacement in detail through conversation: named regex captures, per-scanner-type autonomous resource identification, a 24h mtime-keyed scan cache with background refresh, fail-safe-until-first-scan for never-seen resources, and fatal-non-zero-exit reserved for scanner-machinery failures (not scan findings). Wrote as E10 — Extensible Scanner Registry & Resource Verification — 5 stories (STORY-1001 through 1005) in `docs/USER_STORIES.md`, updated `docs/PRD.md` epic table + Sprint 4 goals, updated `task.md` header (Sprint 3 status was stale — implemented but never formally closed; noted honestly rather than silently marking it done).

## Progress
- [x] Captured the full design (already hashed out in conversation with the user, not something Cypher had to invent) as 5 testable stories.
- [x] Left one explicit open question for Morpheus in the epic's origin note: does E10's autonomous scanning *replace* the `scg onboard`/single-`allowlist` model, or coexist with it? Deliberately did not pre-decide this myself — it's an architecture call, not a product-scope call.
- [x] STORY-1004 explicitly flags that Morpheus must enumerate exactly which failure classes stay fail-safe-exit-0 vs. become fatal-non-zero, so the new "fatal" exception doesn't quietly widen past what the user specified (scanner-machinery failures only, never scan findings).
- [x] Handed off to Smith for Gate 1 review — **approved**.
- [x] Morpheus architected (§13, full-replacement decision), Smith Gate 2 — **approved**.
- [x] Mouse phased (5 phases, `task.md`), Morpheus plan review — **LOCKED**, handed to Neo.

## Blockers
None.

## Oracle Consultations
None yet.

---
*Last updated: 2026-07-14*
