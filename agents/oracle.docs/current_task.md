# Current Task

**Status:** `*ora groom` (Sprint 8 / E14 close) complete. Handed to Smith.
**Assigned to:** Oracle
**Started:** 2026-07-21
**Completed:** 2026-07-21

## Task Description (most recent): `*ora groom` (Sprint 8 / E14 close)
- `CHAT.md` at 50 messages — within threshold, no archive needed.
- Reconciled `docs/USER_STORIES.md`'s E14 stories carefully, not just checking everything off: STORY-1401's "no separate resolution logic" AC honestly left partially-unchecked with a note (kept `_resolve_resource()`, a deliberate revision, not full removal); STORY-1404's "each scanner exposes an inventory" AC left unchecked (shipped as a CLI `--list` view over `ScanCache` instead — the developer-facing value landed, the literal per-scanner-object mechanism didn't); STORY-1405's "decision can weigh both signals" AC left unchecked and honestly flagged as real, open follow-on work — the reputation score displays but doesn't yet drive the allow/block gate. Everything else checked off against real, verified behavior.
- `task.md`: Sprint 8 marked implementation-complete, each phase's exit criteria updated with real PASSED outcomes (not just "done"), Phase 3's scope revision and the carried-forward stale-diagram flag both recorded in Notes.
- Recorded 1 durable lesson (`agents/oracle.docs/lessons.md`): "A 'Delete This' Line in a Phase Plan Is Also a Hypothesis" — Neo's `onboard()`-keeping decision, generalized.
- `make test`: 331/331 (docs-only changes this pass, confirmed unaffected).

## Task Description (prior): `*ora groom` (Sprint 7 / sec16 close) complete.

## Task Description (most recent): `*ora groom` (Sprint 7 / sec16 close)
- `CHAT.md` was at 80 messages (approaching the range past archives triggered at) — archived through Sprint 6's launch to `agents/chat_archive/CHAT-ARCHIVE-20260720.md` (extracted via `sed`, not retyped), kept the live sec16 sequence (build failure → now) plus a new summary paragraph, same convention as every prior archive.
- Added a `# Sprint 7` section to `task.md` (retroactive single-phase entry, same treatment sec15 got in Sprint 5's table) and updated the top status line.
- Reconciled `docs/USER_STORIES.md` STORY-501: checked off 3 of 4 ACs as genuinely satisfied by the shipped §16 design (the 4th — git-committed attributability — resolved differently than literally written, left unchecked with an explanation rather than force-checked). Added a dated Reconciled note explaining the 3-mechanism history (original design → Sprint 4 cache-only re-scope → sec16 restores rule-authoring), original text kept per this doc's append-only convention.
- Recorded 1 durable lesson (`agents/oracle.docs/lessons.md`): layered validation (CLI `argparse.choices=` plus a library function's own deeper check) can leave a well-reasoned inner message unreachable from the real entry point — Trin's finding, generalized so it doesn't only apply to `scg onboard`.
- `make test`: 289/289 (docs-only changes, confirmed unaffected).

## Task Description (prior): Sprint 3 close groom
CHAT.md at 47 messages — well under the archive threshold, no action needed. Checked STORY-901/902/903's ACs in `docs/USER_STORIES.md` for staleness (unlike E10's STORY-1001, none of these literally describe a mechanism that got replaced) — checked all off as genuinely satisfied, with 2 small in-place notes (STORY-902/903) pointing at where Sprint 4 kept the underlying doc/demo current rather than letting it drift. No new durable lessons this pass — this was process catch-up (a skipped UAT step run late), not a new discovery.

## Task Description (prior)
Stage 3 sprint close (Sprint 4 / E10), step 7: groom docs, archive CHAT.md if oversized, record durable lessons.

## Progress
- [x] `CHAT.md` was at 157 messages (well over the 50-100 threshold) — archived messages through the Phase 3 gate approval to `agents/chat_archive/CHAT-ARCHIVE-20260715.md`, replaced with a summary + link, kept Phase 4/5 + close activity live (~40 messages)
- [x] Recorded 2 durable lessons in `agents/oracle.docs/lessons.md`: (1) an architecture claim about latency/exit-codes is a hypothesis until measured — both Phase 2's latency finding and Phase 4's exit-code finding were the same failure shape; (2) a row-content/data-model UI test is not a rendering test — Phase 5's real-screenshot-caught truncation bug, and the first fix attempt passing every data-level test while still being visibly broken
- [x] Flagged 3 AC-text staleness items to Cypher, not edited myself: **STORY-1001's entire premise no longer matches what shipped** (describes a user-facing `pattern`-with-capture-groups feature; the actual §13.1 architecture decision made named captures purely an internal scanner detail, never user-facing) — significant, not cosmetic; STORY-1003's cache-key wording overstates what's literally in the key vs. value; all 5 E10 story checkboxes still unchecked despite all 5 phases being done. Full: `agents/oracle.docs/e10_story_staleness_flag.md`
- [x] Handed off to Smith for Stage 3 step 8 (end-to-end sprint testing)

## Task Description (prior): Sprint 2 close groom

## Progress (most recent): `*ora groom` — Sprint 5 (E11 → sec15) close
- [x] `CHAT.md` was at 98 messages (over the 50-100 threshold) — archived messages through 2026-07-17 15:13 to `agents/chat_archive/CHAT-ARCHIVE-20260718.md` (extracted via `sed`, not retyped, to avoid transcription errors on real historical data), replaced with a summary + link, kept the live tail (36 messages).
- [x] Reconciled `docs/USER_STORIES.md`'s E11 epic, `task.md`'s Sprint 5 section (both the phase table and the top-level status line), and `docs/PRD.md`'s Sprint 5 goals + epic table row — all still described the original masking-centric design. Added dated "Superseded" notes pointing to `docs/ARCHITECTURE.md` §15, same append-only-correction convention as every other revision in these docs — did not rewrite or delete the original text.
- [x] Recorded 1 durable lesson in `agents/oracle.docs/lessons.md`: "A Gate That Actually Exercises the Feature Can Overturn the Feature" — Smith's mandatory Phase 3 gate tried a maximally broad, laziest-possible rule and found the feature reproduced the project's own core defect; the fix was reopening the design mid-gate, not patching around it.
- [x] Handed off to Smith for the real end-to-end sprint test (the one that got interrupted by the mode=allow discovery and never completed the first time).

## Blockers
None

## Oracle Consultations
None yet

---
*Last updated: 2026-07-18*
