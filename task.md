# Sprint Task Board — Project Scalene

**Owner:** Mouse
**Status:** Sprint 1 closed 2026-07-09. Sprint 2 closed 2026-07-10. **Sprint 3 planned** — 3 phases, awaiting Morpheus's plan review before `*impl phase-1`.

---

# Sprint 1 (closed)

**Status:** ✅ **SPRINT CLOSED 2026-07-09** — all 4 phases complete, Trin UAT + Morpheus review passed every phase. All 9 user stories' acceptance criteria verified (`docs/STORY_TRACEABILITY.md`). 77/77 tests passing.
**Source:** `docs/USER_STORIES.md` (E1-E6) + `docs/ARCHITECTURE.md` (§1-10)

Both sprint-planning gates (Smith Gate 1 & 2) are clear. No Tank phase included — no deploy/CI/system-level env var work in this sprint (`SCALENE_BYPASS` is a subprocess-local var per architecture, not infra-scoped); revisit if that changes.

## Phase 1 — Policy Engine Foundations
*Chain: Neo → Trin → Morpheus*

| Task | Description | Story Refs |
|------|-------------|-----------|
| 1.1 | `TaintState`: session-scoped sticky flags, load/save to `.scalene/state/<session_id>.json` | STORY-101 |
| 1.2 | `PolicyConfig`: YAML loader + schema validation for `scalene_policy.yaml` | STORY-201 |
| 1.3 | JSONPath rule evaluator (`PolicyConfig.evaluate`) + fail-safe path on malformed/no-match | STORY-102, STORY-202 |

**Exit criteria:** Trin UAT passes on all 3 tasks; Morpheus reviews for architecture fit before Phase 2 starts. ✅ **DONE 2026-07-08** — `src/scalene/taint_state.py`, `src/scalene/policy_config.py`, 20/20 tests passing.

---

## Phase 2 — Hook Adapter & Masking
*Chain: Neo → Trin → Morpheus*
*Depends on: Phase 1*

| Task | Description | Story Refs |
|------|-------------|-----------|
| 2.1 | `PreToolUse` hook adapter: parse Claude Code hook JSON, call policy engine, return allow/updatedInput | STORY-301 |
| 2.2 | `MaskingEngine`: mask decision + payload substitution + audit log entry + `systemMessage` on mask (Smith Gate 1 follow-up) | STORY-401 |
| 2.3 | `PostToolUse` hook adapter: provenance updater, taint state write-back | STORY-302 |

**Exit criteria:** Trin UAT passes (incl. verifying masking never raises); Morpheus reviews. ✅ **DONE 2026-07-09** — `src/scalene/masking.py`, `src/scalene/hook_adapter.py`, 40/40 tests passing.

---

## Phase 3 — Onboarding & Scanner Isolation
*Chain: Neo → Trin → Morpheus*
*Depends on: Phase 1 (config engine)*

| Task | Description | Story Refs |
|------|-------------|-----------|
| 3.1 | `scalene onboard` CLI + `LocalHeuristicChecker` (domain heuristics, no network) + secrets scan on allowlist target | STORY-501 |
| 3.2 | Scanner subprocess isolation: spawn with `SCALENE_BYPASS=1`, confirm no hook re-trigger | STORY-601 |
| 3.3 | Onboarding success confirmation output (rule + YAML diff) + audit log entry (Smith Gate 1 follow-up) | STORY-501 |

**Exit criteria:** Trin UAT passes (incl. verifying onboarding works fully offline); Morpheus reviews. ✅ **DONE 2026-07-09** — `src/scalene/reputation.py`, `secrets_scan.py`, `scan_worker.py`, `subprocess_isolation.py`, `onboard.py`, 67/67 tests passing.

---

## Phase 4 — Packaging, Perf Verification & Full UAT
*Chain: Neo → Trin → Morpheus → [context check]*
*Depends on: Phases 1-3*

| Task | Description | Story Refs |
|------|-------------|-----------|
| 4.1 | Pip packaging (`scalene-guard`) + `.claude/settings.json` hook registration setup docs + confirm `.scalene/` is `.gitignore`d and excluded from CI artifact capture | — |
| 4.2 | Perf test: verify pre-tool-call evaluation stays under 15ms (NFR, flagged by Smith at Gate 2) | NFR-Performance |
| 4.3 | Full UAT across all 9 stories' acceptance criteria | All |

**Exit criteria:** All AC pass; Morpheus final review; sprint closes. ✅ **DONE 2026-07-09** — `src/scalene/cli.py`, `main_cli.py`, `docs/SETUP.md`, `docs/STORY_TRACEABILITY.md`, `tests/test_performance.py`, 77/77 tests passing. **SPRINT 1 CLOSED.**

---

## Notes
- No Tank phase this sprint (see header). Reassess at Phase 3 if onboarding scope grows to include a real external threat-intel API.
- Smith re-engages post-Phase 2 for `*user test` against real hook behavior (not just spec review).

---

# Sprint 2

**Owner:** Mouse
**Status:** ✅ **SPRINT CLOSED 2026-07-10** — all 3 phases complete, every required gate passed (Trin UAT + Morpheus review every phase; Smith UX gate on Phases 2 & 3, both found and closed real bugs). Full end-to-end test passed with no bugs. 124/124 tests passing. Retro complete, launched by Cypher.
**Source:** `docs/USER_STORIES.md` (E7-E8) + `docs/ARCHITECTURE.md` (§11)
**Scope:** User-directed (2026-07-10) — usability focus, promote backlogged items, add a live console for taint status + guided list maintenance.

Every phase below carries a **required** Smith UX gate (`*user test`) after Trin/Morpheus, per bloop's `*impl` conditional Smith step — called out explicitly per phase so this doesn't repeat Sprint 1's S1-003 gap (a "Smith re-engages" note with no actual chain step behind it).

## Phase 1 — Secrets Scan Upgrade
*Chain: Neo → Trin → Morpheus*
*Independent of Phases 2-3 — no shared code, can run first or in parallel if ever parallelized.*

| Task | Description | Story Refs |
|------|-------------|-----------|
| 1.1 | Integrate `detect-secrets` into `secrets_scan.py`, routed through the existing plain-language result-translation layer (never raw library exception text) | STORY-801 |
| 1.2 | Update/fix existing secrets-scan test fixtures for the new detector's real match set — fix fixtures, do not add scanner allowlist exceptions (project policy) | STORY-801 |

**Exit criteria:** Trin UAT passes (incl. confirming onboarding-blocked message stays plain-language); Morpheus reviews. No Tank, no Smith gate required this phase (no new user-facing surface — same CLI behavior, better detection under the hood). *If a secrets-scan failure message actually changes wording, Smith spot-checks it — optional, not blocking.*

✅ **DONE 2026-07-10** — `src/scalene/secrets_scan.py` rewritten on `detect-secrets` (via `scan_file()`, not the unfiltered `scan_line()` adhoc API — caught a real false-positive trap there before implementing), `detect-secrets>=1.5.0` added to `pyproject.toml`. No network egress (verified against docs + a regression test). 90/90 tests passing. Trin UAT + Morpheus review both passed.

---

## Phase 2 — Console Foundations
*Chain: Neo → Trin → Morpheus → Smith (required)*
*Depends on: nothing new — reads existing `.scalene/audit.log` / `.scalene/state/*.json` formats as-is.*

| Task | Description | Story Refs |
|------|-------------|-----------|
| 2.1 | `scalene monitor` console-script entrypoint, `textual` as an optional `[monitor]` pip extra (never a hard dependency of the base package) | STORY-701 |
| 2.2 | Polling data layer (~500ms) over audit log (mask events only — never announce a non-mask call, per hook_adapter.py's existing guarantee) + session state files | STORY-701 |
| 2.3 | Multi-session list view (default) + per-session filter + "all sessions" aggregate toggle | STORY-701 |

**Exit criteria:** Trin UAT passes, including a concrete realtime check (new mask event visible within ~1s of the audit-log write, per Smith's Gate 2 note); Morpheus reviews. **Smith `*user test` required** (STORY-701 is directly developer-observable UI) — run against a real session's real audit.log, not a mocked feed.

✅ **DONE 2026-07-10** — `src/scalene/monitor_data.py` (pure data layer), `monitor_app.py` (Textual App), `monitor.py` (CLI entrypoint, graceful missing-extra fallback). `textual>=8.0` as the `[monitor]` optional extra. Trin UAT passed; Morpheus approved; **Smith's UX gate found a real bug** (session-selection cursor silently diverged from the actual filter on every poll refresh) — triaged by Trin, fixed by Neo (test-first), independently re-verified by both Trin and Smith across repeated poll ticks before final approval. 109/109 tests passing. One non-blocking spec-conflict flagged to Cypher (STORY-701's "timestamp" AC bullet vs. the audit log's actual schema — needs a wording fix, not a code fix).

---

## Phase 3 — Guided Onboarding Action
*Chain: Neo → Trin → Morpheus → Smith (required)*
*Depends on: Phase 2 (console must exist to act within).*

| Task | Description | Story Refs |
|------|-------------|-----------|
| 3.1 | Render each mask event's `suggested_onboard_command` with the `<domain-or-file-this-call-reaches>` placeholder editable inline — also fix the placeholder wording itself (Smith's non-blocking Sprint-1 nit: it's always trust-list/domain-only, never "-or-file") since this is the first time it's directly user-facing in a UI, not just a copyable terminal string | STORY-702 |
| 3.2 | "Apply" action: subprocess call to the real `scalene onboard` CLI (never a reimplementation) using the edited command; report success/failure back in the console | STORY-702 |
| 3.3 | "Dismiss" action with no side effect (no partial YAML write, no state change) | STORY-702 |

**Exit criteria:** Trin UAT passes (incl. confirming apply/dismiss never bypass onboarding's existing secrets-scan/reputation-check gates); Morpheus reviews. **Smith `*user test` required** (STORY-702 is the sprint's highest-stakes UX surface — a one-click action that writes to `scalene_policy.yaml`).

✅ **DONE 2026-07-10** — placeholder wording fixed; `apply_onboard_command()` (real subprocess to the actual `scalene` CLI, never a reimplementation) wired into `monitor_app.py`'s command-input/apply-status UI. Trin UAT passed (verified independently through the real UI that a real secret genuinely blocks the write). Morpheus's review round 1 found and rejected 2 uncaught crash paths (missing binary, malformed quoting) — Neo fixed both plus a 3rd found while re-checking (empty input), round 2 approved. Smith's UX gate found a real bug (focus lost entirely after dismiss/apply, stranding the user) — triaged by Trin, fixed by Neo, re-verified by both Trin and Smith across a full realistic multi-step sequence. 124/124 tests passing. **Sprint 2's last planned phase — all 3 phases now closed.**

## Notes
- No Tank phase this sprint — see header; Morpheus's architecture decision (§11.1) explicitly avoided introducing anything that would need one.
- Phase 1 is independent of Phases 2-3; sequenced first here only because it's the smallest/lowest-risk phase, not because of a hard dependency.
- Two items intentionally **not** phased as their own tasks (`docs/USER_STORIES.md`'s "Deferred / Not Promoted" section): the placeholder-wording fix is folded into task 3.1 instead of a standalone task (too small); relocating `_suggest_onboard_command()` out of `hook_adapter.py` stays deferred until a second harness adapter exists.

---

# Sprint 3

**Owner:** Mouse
**Status:** Planned, pending Morpheus's plan review.
**Source:** `docs/USER_STORIES.md` (E9) + `docs/ARCHITECTURE.md` (§12)
**Scope:** User-directed (2026-07-13) — a `GETTING_STARTED.md`, a `USER_GUIDE.md`, and a runnable/tested demo of Scalene stopping a real exfiltration attempt.

None of these 3 phases share code — sequenced by risk/foundational order, not hard dependency. Only Phase 3 introduces a new user-facing *surface* (a demo people actually run); Phases 1-2 are pure documentation.

## Phase 1 — Getting Started Guide
*Chain: Neo → Trin → Morpheus → Smith (required)*
*Depends on: nothing new — describes the existing install/config/onboard flow.*

| Task | Description | Story Refs |
|------|-------------|-----------|
| 1.1 | Write `docs/GETTING_STARTED.md`: clean-clone → install → minimal policy → first observed mask/block, every command copy-pasteable and verified to actually run | STORY-901 |
| 1.2 | Trim `README.md`'s "Getting started" section to a link into the new doc (no duplicated content) | STORY-901 |

**Exit criteria:** Trin UAT passes (every command in the doc actually run on a clean checkout, ends in one concrete observed masked/blocked event). Morpheus reviews. **Smith `*user test` required** — Smith personally times a cold run to verify the sub-5-minute AC (Gate 1 commitment), not just Neo's/Trin's say-so.

---

## Phase 2 — User Guide
*Chain: Neo → Trin → Morpheus*
*Depends on: nothing new — reference doc over existing CLI/config surface.*

| Task | Description | Story Refs |
|------|-------------|-----------|
| 2.1 | Write `docs/USER_GUIDE.md` covering every `scalene`/`scalene-guard` command and flag, verified against real `--help` output (not memory/source transcription) | STORY-902 |
| 2.2 | Document `scalene_policy.yaml` schema by example, cross-referencing `ARCHITECTURE.md` §4 rather than duplicating it; add a troubleshooting section (fail-safe behavior on malformed config/missing policy/scan failure) | STORY-902 |
| 2.3 | Surface the onboard-suggestion workflow (`_suggest_onboard_command()`) as the guide's primary onboarding path, per Smith's Gate 1 note — manual `scalene onboard` flags presented as the fallback; add `USER_GUIDE.md` to `README.md`'s doc table | STORY-902 |

**Exit criteria:** Trin UAT passes, including diffing documented commands/flags against real `--help` output and confirming Smith's Gate 1 note (onboard-suggestion prominence) actually landed. Morpheus reviews. No dedicated Smith gate — no new interactive surface, this is an accuracy/completeness check, not a usability-flow one.

---

## Phase 3 — Demo
*Chain: Neo → Trin → Morpheus → Smith (required)*
*Depends on: nothing new — exercises the existing `scalene-guard` CLI as a real subprocess.*

| Task | Description | Story Refs |
|------|-------------|-----------|
| 3.1 | `demo/run_demo.py`: temp project + minimal policy, real `scalene-guard` subprocess fed real `PreToolUse`/`PostToolUse` JSON on stdin, scenario = `Read`(fake sensitive file) → `WebFetch`(untrusted domain) → masked response shown, plain-language narration written for a BRD-naive reader (Smith's Gate 2 note) | STORY-903 |
| 3.2 | `tests/test_demo.py`: run the demo as a subprocess, assert the masking marker appears and the fake secret never appears unmasked in output | STORY-903 |
| 3.3 | `make demo` Makefile target wired to `demo/run_demo.py` | STORY-903 |

**Exit criteria:** Trin UAT passes (demo runs clean on a checkout, `tests/test_demo.py` passes, confirms no real network egress occurs). Morpheus reviews. **Smith `*user test` required** — Smith runs the demo herself to confirm it reads as genuinely non-mocked and that the narration is understandable without prior BRD/PRD context (Gate 2 commitment).

## Notes
- No Tank phase this sprint — per Morpheus's architecture (§12.2), `demo/run_demo.py` is a local dev-only script, no new port/service/env var/CI impact.
- Phase ordering (Getting Started → User Guide → Demo) is foundational-first, not a hard dependency: Getting Started is the smallest and most time-boxed (Smith's <5min AC), User Guide is the largest pure-writing effort, Demo is saved for last since it's the only phase introducing new code (the demo script + its test).
