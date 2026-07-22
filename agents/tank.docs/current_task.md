# Current Task

**Status:** `*devops review phase-3` (Sprint 9/E15) — APPROVED after recheck. Handed to Neo for Phase 4.
**Assigned to:** Tank
**Started:** 2026-07-21
**Completed:** 2026-07-21

## Task Description (most recent): `*devops review phase-3` recheck — Auth-Key fix
Full report: `agents/tank.docs/e15_phase3_recheck.md`. User chose "get a free key, env var" from my 3 options. Verified Neo's fix directly: `SCALENE_URLHAUS_AUTH_KEY` read from env only (grepped, no hardcoded secret anywhere), `.env.example` correctly documents it without a real value, `.env` stays gitignored. The fix avoids the exact failure I found — no request sent at all when the key is absent. **APPROVED**, with one honest, non-blocking limitation flagged: I can't obtain a real key myself (requires human signup), so someone with a live key should confirm one real authenticated call succeeds before relying on this in production. Phase 3 closes on the engineering side. Handed to Neo for Phase 4.

## Task Description: `*devops review phase-3` — external reputation source (STORY-1503)
Full report: `agents/tank.docs/e15_phase3_review.md`. Asked to confirm URLhaus's host-lookup endpoint needs no API key (the stated reason it was chosen) and assess rate-limit/volume safety. Verified directly against the live endpoint (curl), not the docs it was designed against: it now requires an `Auth-Key` header, returning `{"error": "Unauthorized"}` without one. Traced the real consequence through `reputation.py`: `URLHausChecker.check()` gets a response with no `query_status` key, raises `ReputationCheckUnavailable`, and `composite_check()` degrades to local-heuristics-only — meaning in production this would degrade on **every** call, permanently, not just on real network hiccups. STORY-1503's actual AC (a real external source catching what local heuristics can't) is not met as currently merged.

Found a genuinely keyless alternative (URLhaus's recent-URLs CSV feed, confirmed reachable, HTTP 200) but it's feed-based, not per-host-query — would need a real redesign of `URLHausChecker`, not a quick endpoint swap.

Gave 3 options (get a free Auth-Key + env var; redesign against the CSV feed; ship explicitly-labeled degrade-only for now) without deciding unilaterally — this is a real product/architecture trade-off (setup friction vs. coverage vs. scope), not an infra call I should make alone.

Also resolved a smaller question from my own operational guidelines (item 9, "requests over urllib"): confirmed `requests` isn't already a project dependency, so stdlib `urllib` (Neo's choice) is the right call here, not a violation.

## Progress
- [x] Verified the "no API key" premise against the real endpoint — false.
- [x] Traced the real production consequence (permanent silent degrade) through the actual code, not assumed.
- [x] Found and verified a genuinely keyless alternative data source.
- [x] Resolved the urllib-vs-requests question against actual project dependencies.
- [x] Posted `*devops blocked` — did not approve, did not silently work around it.

## Blockers
Awaiting a real decision from Morpheus/Cypher (and likely the user) on which of the 3 options to take before Phase 3 can close.

## Oracle Consultations
None yet — this is a fresh finding, not a repeat of a known issue.

---
*Last updated: 2026-07-21*
