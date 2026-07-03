# Sprint Task Board — Project Scalene, Sprint 1

**Owner:** Mouse
**Status:** Planned — pending Morpheus plan review
**Source:** `docs/USER_STORIES.md` + `docs/ARCHITECTURE.md`

Both sprint-planning gates (Smith Gate 1 & 2) are clear. No Tank phase included — no deploy/CI/system-level env var work in this sprint (`SCALENE_BYPASS` is a subprocess-local var per architecture, not infra-scoped); revisit if that changes.

## Phase 1 — Policy Engine Foundations
*Chain: Neo → Trin → Morpheus*

| Task | Description | Story Refs |
|------|-------------|-----------|
| 1.1 | `TaintState`: session-scoped sticky flags, load/save to `.scalene/state/<session_id>.json` | STORY-101 |
| 1.2 | `PolicyConfig`: YAML loader + schema validation for `scalene_policy.yaml` | STORY-201 |
| 1.3 | JSONPath rule evaluator (`PolicyConfig.evaluate`) + fail-safe path on malformed/no-match | STORY-102, STORY-202 |

**Exit criteria:** Trin UAT passes on all 3 tasks; Morpheus reviews for architecture fit before Phase 2 starts.

---

## Phase 2 — Hook Adapter & Masking
*Chain: Neo → Trin → Morpheus*
*Depends on: Phase 1*

| Task | Description | Story Refs |
|------|-------------|-----------|
| 2.1 | `PreToolUse` hook adapter: parse Claude Code hook JSON, call policy engine, return allow/updatedInput | STORY-301 |
| 2.2 | `MaskingEngine`: mask decision + payload substitution + audit log entry + `systemMessage` on mask (Smith Gate 1 follow-up) | STORY-401 |
| 2.3 | `PostToolUse` hook adapter: provenance updater, taint state write-back | STORY-302 |

**Exit criteria:** Trin UAT passes (incl. verifying masking never raises); Morpheus reviews.

---

## Phase 3 — Onboarding & Scanner Isolation
*Chain: Neo → Trin → Morpheus*
*Depends on: Phase 1 (config engine)*

| Task | Description | Story Refs |
|------|-------------|-----------|
| 3.1 | `scalene onboard` CLI + `LocalHeuristicChecker` (domain heuristics, no network) + secrets scan on allowlist target | STORY-501 |
| 3.2 | Scanner subprocess isolation: spawn with `SCALENE_BYPASS=1`, confirm no hook re-trigger | STORY-601 |
| 3.3 | Onboarding success confirmation output (rule + YAML diff) + audit log entry (Smith Gate 1 follow-up) | STORY-501 |

**Exit criteria:** Trin UAT passes (incl. verifying onboarding works fully offline); Morpheus reviews.

---

## Phase 4 — Packaging, Perf Verification & Full UAT
*Chain: Neo → Trin → Morpheus → [context check]*
*Depends on: Phases 1-3*

| Task | Description | Story Refs |
|------|-------------|-----------|
| 4.1 | Pip packaging (`scalene-guard`) + `.claude/settings.json` hook registration setup docs + confirm `.scalene/` is `.gitignore`d and excluded from CI artifact capture | — |
| 4.2 | Perf test: verify pre-tool-call evaluation stays under 15ms (NFR, flagged by Smith at Gate 2) | NFR-Performance |
| 4.3 | Full UAT across all 9 stories' acceptance criteria | All |

**Exit criteria:** All AC pass; Morpheus final review; sprint closes.

---

## Notes
- No Tank phase this sprint (see header). Reassess at Phase 3 if onboarding scope grows to include a real external threat-intel API.
- Smith re-engages post-Phase 2 for `*user test` against real hook behavior (not just spec review).
