# Sprint Task Board — Project Scalene

**Owner:** Mouse
**Status:** Sprint 1 closed 2026-07-09. Sprint 2 closed 2026-07-10. **Sprint 3 closed 2026-07-16** (implemented 2026-07-14; Phase 3's UAT/review/gate never ran before the session moved to unrelated work — closed retroactively once noticed). **Sprint 4 (E10) closed 2026-07-15** — all 5 phases complete, every required gate passed (Trin UAT + Morpheus review every phase; Smith UX gate on Phases 3-5, found and closed a real regression-window decision plus a real UI rendering bug). Full end-to-end test passed. 230/230 tests passing. Retro complete, launched by Cypher. **Sprint 5 (E11) closed 2026-07-18** — planned as a 3-phase masking refinement, but Phase 3's Smith gate found a real gap that led to replacing the sprint's entire mechanism mid-gate (`docs/ARCHITECTURE.md` §15, rule-driven access control, superseding §14.4). Re-reviewed after the fact (Trin UAT + Morpheus review against the shipped sec15 code). 266/266 tests passing. **Sprint 6 (E12, tech debt) closed 2026-07-18** — 1 phase, 3 small independent stories pulled from the Sprint 3-5 retro backlog, verified against current code before scoping. 275/275 tests passing. **Sprint 7 (E13, `scg onboard` sec16 correction) closed 2026-07-20** — direct user design session, post-Sprint-6, same shape as sec15: `scg onboard` re-scoped to author a full `PolicyRule` in one call instead of only pre-seeding the cache (`docs/ARCHITECTURE.md` §16, reversing §14.3's "CLI surface never changes" requirement). Re-gated after the fact (Trin UAT + Morpheus review + Smith end-to-end test against the shipped sec16 code; Smith's gate found a real `--help` discoverability gap, fixed and re-verified within the same close). 291/291 tests passing.

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
**Status:** ✅ **SPRINT CLOSED 2026-07-16** — all 3 phases complete, every required gate passed (Trin UAT + Morpheus review every phase; Smith UX gate on Phases 1 & 3). Phase 3's UAT/review/gate were handed off but never actually run when this session moved to unrelated direct-request work back on 2026-07-14 — completed retroactively on 2026-07-16, once flagged, rather than left open indefinitely. Full end-to-end demo re-verified live against Sprint 4's current behavior. 230/230 tests passing. Retro complete, launched by Cypher.
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

✅ **DONE 2026-07-14** — `docs/GETTING_STARTED.md` (real 3-command walkthrough, verified against the real installed binary, not fabricated), `README.md` trimmed to link. Trin UAT passed (cloned fresh, ran `make setup`, ran all 3 commands against that clone's own binary). Smith's timed gate passed — 24s machine time end-to-end, well under 5 minutes.

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

✅ **DONE 2026-07-14** — `docs/USER_GUIDE.md` (all commands verified against real `--help` output), found+fixed a real pre-existing bug while writing the troubleshooting section (`cli.py` had no exception handling around malformed policy YAML). Trin UAT passed (confirmed Smith's onboard-suggestion note landed). Morpheus approved. Kept current through Sprint 4's CLI/schema changes.

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

✅ **DONE — implemented 2026-07-14, UAT/review/gate completed 2026-07-16** (handed off to Trin on 2026-07-14 but never actually run before that session moved to unrelated direct-request work; closed retroactively once flagged, not silently left open). `demo/run_demo.py` + `tests/test_demo.py` + `make demo`. Trin's UAT (run 2026-07-16 against the demo's current, Sprint-4-updated behavior): clean run, 3/3 tests, no network-capable imports. Morpheus approved (1 non-blocking, pre-existing observation about an uncaught exit-code path that can't realistically trigger given the demo's always-fresh tmp dir). Smith's gate passed — ran the demo herself fresh, narration reads cleanly for a BRD-naive audience, no jargon in the actual printed output. **Sprint 3's last phase — all 3 phases now closed.**

## Notes
- No Tank phase this sprint — per Morpheus's architecture (§12.2), `demo/run_demo.py` is a local dev-only script, no new port/service/env var/CI impact.
- Phase ordering (Getting Started → User Guide → Demo) is foundational-first, not a hard dependency: Getting Started is the smallest and most time-boxed (Smith's <5min AC), User Guide is the largest pure-writing effort, Demo is saved for last since it's the only phase introducing new code (the demo script + its test).

---

# Sprint 4

**Owner:** Mouse
**Status:** ✅ **SPRINT CLOSED 2026-07-15** — all 5 phases complete, every required gate passed (Trin UAT + Morpheus review every phase; Smith UX gate on Phases 3-5). Full end-to-end test passed with no new bugs. 230/230 tests passing. Retro complete, launched by Cypher.
**Source:** `docs/USER_STORIES.md` (E10) + `docs/ARCHITECTURE.md` (§13)
**Scope:** Direct user design session (2026-07-14) — replace the just-shipped `PolicyConfig.allowlist`/`PolicyRule` matching model (a rule's one-time scan can vouch for an unbounded future pattern-match) with an extensible per-scanner resource-identification system backed by a 24h `mtime`-keyed scan cache with background refresh.

Larger than Sprint 3 — 5 phases, since this replaces a subsystem shipped one commit ago and adds a new cache store + background-process model, not just docs/a demo. Phases are dependency-ordered (each builds on the previous): scanners can't be cached without existing; the hook can't be integrated without both; onboarding/monitor are consumers of the finished system.

## Phase 1 — Scanner Protocol & Built-in Scanners
*Chain: Neo → Trin → Morpheus*
*Depends on: nothing new.*

| Task | Description | Story Refs |
|------|-------------|-----------|
| 1.1 | `Scanner` protocol (`identify()`/`scan()`), `Resource`/`ScanResult` dataclasses (§13.2) | STORY-1002 |
| 1.2 | `FileScanner`: built-in per-tool path detection (`Read`/`Write`/`Edit`) + generic path-shaped fallback regex w/ named capture; `scan()` wraps existing `secrets_scan.py` unchanged | STORY-1001, STORY-1002 |
| 1.3 | `URLScanner`: built-in `WebFetch` URL detection + generic URL-shaped fallback regex w/ named `host` capture (resource identity = host, not full URL); `scan()` wraps existing `LocalHeuristicChecker` unchanged. Wire `Bash`'s `command` string into both scanners' generic fallback (no dedicated Bash scanner type, per §13.2) | STORY-1001, STORY-1002 |

**Exit criteria:** Trin UAT passes (both scanners correctly identify resources across all built-in tool shapes + the generic fallback, at parity with today's secrets-scan/reputation-check behavior — no regression). Morpheus reviews. No Tank, no Smith gate — internal components, nothing user-facing changes yet.

---

## Phase 2 — Scan Cache Store
*Chain: Neo → Trin → Morpheus*
*Depends on: Phase 1 (caches `ScanResult`/`Resource` values).*

| Task | Description | Story Refs |
|------|-------------|-----------|
| 2.1 | `.scalene/scan_cache.json` read/write, `filelock`-protected (same pattern as `taint_state.py`) | STORY-1003 |
| 2.2 | 3-state lookup (none/fresh/expired) per §13.3's table; file staleness by `mtime` (not content hash) | STORY-1003 |
| 2.3 | Background rescan via detached `subprocess.Popen` (no `.wait()`, no daemon); in-flight-scan dedup so concurrent calls to the same never-cached resource don't spawn N redundant background scans (Smith's Gate 2 watch-item) | STORY-1003 |

**Exit criteria:** Trin UAT passes, including a real repeated-invocation test proving no zombie/orphaned background processes accumulate (Morpheus's Gate 2 devops note, §13.7) and that concurrent first-sighting calls don't spawn duplicate scans. Morpheus reviews. No Tank, no Smith gate — still no user-facing surface.

---

## Phase 3 — Hook Integration & First-Sighting Messaging
*Chain: Neo → Trin → Morpheus → Smith (required)*
*Depends on: Phase 1 + Phase 2.*

| Task | Description | Story Refs |
|------|-------------|-----------|
| 3.1 | Replace `PolicyConfig.evaluate()` call site in `hook_adapter.py` with the new resource-verification path; `MatchResult` shape and `MaskingEngine.decide()`'s content-gating logic stay unchanged (§13.1.1) | STORY-1002, STORY-1003 |
| 3.2 | Remove `PolicyRule`/`allowlist` from `policy_config.py` entirely (§13.1 full-replacement decision); update `ARCHITECTURE.md` §4's class diagram for real (flagged stale in §13 header) | STORY-1002 |
| 3.3 | First-sighting mask/block message reads as "not yet verified" distinctly from a known-bad decision (Smith's Gate 1/2 note) | STORY-1003 |
| 3.4 | Re-verify `tests/test_performance.py`'s <15ms NFR actually still passes with resource identification + cache lookup in the hot path — not assumed compatible (Smith's Gate 2 watch-item) | STORY-1003 |

**Exit criteria:** Trin UAT passes (incl. re-running the perf test for real, confirming the "no cache entry" path is genuinely zero-added-latency vs. today's baseline). Morpheus reviews. **Smith `*user test` required** — this is the phase where a real behavior/copy change becomes user-visible; Smith personally verifies the first-sighting message reads as intended (her Gate 1/2 commitment), not just that it exists.

---

## Phase 4 — `scg onboard` Re-scope & Fatal Exit
*Chain: Neo → Trin → Morpheus → Smith (required)*
*Depends on: Phase 2 (writes directly to the scan cache) + Phase 3 (fatal path sits alongside the integrated decision flow).*

| Task | Description | Story Refs |
|------|-------------|-----------|
| 4.1 | Rewrite `scg onboard`: drops `--tool`/`--jsonpath`/`--pattern`/`--description`, resolves scanner from `--target`'s URI scheme (unchanged), runs `scan()` synchronously, writes directly into `.scalene/scan_cache.json` (§13.4) | STORY-1004 (re-scope), replaces prior onboarding behavior |
| 4.2 | Fatal-exit handling in `cli.py`: scanning-machinery failure (cache store broken, scanner crash) exits non-zero with a plain-language stderr message; ordinary scan findings stay exit 0 | STORY-1004 |
| 4.3 | Verify the actual effect of a non-zero `scalene-guard` exit against Claude Code's real hook contract (same method as the earlier hookSpecificOutput research — don't assume) before finalizing the exit code; adjust from the provisional `1` if the real contract calls for something else | STORY-1004 |

**Exit criteria:** Trin UAT passes (a real cache-store-corruption scenario and a real scanner-crash scenario both produce the documented non-zero exit + plain-language message; a real scan-finding scenario stays exit 0). Morpheus reviews. **Smith `*user test` required** — Smith confirms the fatal-exit message is genuinely plain-language (no raw traceback, her Gate 1 note) and that the verified exit code's real effect matches what's documented.

---

## Phase 5 — `scg monitor` Resource Panel
*Chain: Neo → Trin → Morpheus → Smith (required)*
*Depends on: Phase 2 (reads the scan cache).*

| Task | Description | Story Refs |
|------|-------------|-----------|
| 5.1 | New panel in `monitor_app.py`/`monitor_data.py` showing recent scan results (resource, label, last-scanned) — reads `.scalene/scan_cache.json` directly, poll-based like existing panels (§11.2 precedent) | STORY-1005 |

**Exit criteria:** Trin UAT passes (panel reflects real cache content, no separate/duplicated bookkeeping — STORY-1005 AC). Morpheus reviews. **Smith `*user test` required** — new UI surface, same precedent as Sprint 2's Console Foundations gate.

## Notes
- No Tank phase this sprint — no daemon, no new port/service; background scans are one-shot detached subprocesses, not a persistent process (§13.7). Devops-adjacent note (not a gate): confirm background `Popen` spawning doesn't leave orphaned processes in constrained container environments — folded into Phase 2's exit criteria rather than a separate Tank phase.
- Phases are hard-dependency-ordered, unlike Sprint 3's foundational-but-parallel-capable phases — Phase 3 cannot be built without Phases 1-2 existing, and Phases 4-5 are consumers of the finished cache/scanner system.
- `.scalene/scan_cache.json` needs the same `.gitignore` treatment as `.scalene/audit.log`/`state/` (Morpheus's Gate 2 follow-up) — folded into Phase 2, not a separate task.

---

# Sprint 5

**Owner:** Mouse
**Status:** ✅ **SPRINT CLOSED 2026-07-18** — Phases 1-2 shipped as planned below. Phase 3's Smith gate found a real gap (a blanket `pattern:".*"` + `mode:allow` rule could silently disable all scanning) that led to replacing the sprint's entire core mechanism mid-gate: `docs/ARCHITECTURE.md` §15 (rule-driven access control) superseded §14.4 (masking) for the call-permission decision, implemented directly with the user rather than as a re-scoped Phase 3. See §15 for the real shipped design; the phase table below is the original plan, kept as historical record. Full re-review (Trin UAT + Morpheus architecture review) ran against the sec15 code on 2026-07-18, closing the gate gap the pivot left open. 266/266 tests passing.
**Source:** `docs/USER_STORIES.md` (E11) + `docs/ARCHITECTURE.md` (§14, superseded by §15 mid-Phase-3)
**Scope:** Direct user design session (2026-07-17) found the just-shipped E10's `URLScanner` resource identity (host-level) reproduces E10's own core defect — this sprint fixes that (shipped, §14.2/STORY-1101) and originally planned to split trust/sensitivity via unconditional content-scanning (§14.4) — **superseded by §15's access-control model before Phase 3 completed**.

3 phases, hard-dependency-ordered like Sprint 4 (not Sprint 3's parallel-capable shape): rule schema must exist before rule matching can consume it; rule matching must exist before the masking engine can be wired to use its output.

## Phase 1 — Resource Identity Fix & Rule Schema
*Chain: Neo → Trin → Morpheus*
*Depends on: nothing new.*

| Task | Description | Story Refs |
|------|-------------|-----------|
| 1.1 | `URLScanner._URL_FALLBACK_RE`: capture the full URL span (scheme+host+path, query dropped), not just `host` — the actual STORY-1101 defect fix (§14.2) | STORY-1101 |
| 1.2 | `PolicyRule` dataclass (`tool`/`jsonpath`/`pattern`/`sensitivity`/`mode`/`scanner`/`description`) in `policy_config.py`; `PolicyConfig.from_yaml` parses an optional top-level `rules:` list, validating `sensitivity`/`mode` against fixed value sets via the existing `PolicyConfigError` path (§14.5) | STORY-1102, STORY-1103 |
| 1.3 | Rewrite this repo's own root `scalene_policy.yaml`: its pre-Sprint-4 `allowlist:` block has been silently dead since E10 shipped (found during architecture, §14.6) — replace with an equivalent `rules:` entry. Restore `docs/ARCHITECTURE.md` §4's class diagram `PolicyRule` box (carried forward a 4th time, close it for real this time) | STORY-1105 (real migration case) |

**Exit criteria:** Trin UAT passes (URL identity is now per-path; two different paths under the same host get independent labels; `rules:` parses and validates correctly, rejects an invalid `sensitivity`/`mode` value with a clear error). Morpheus reviews. No Tank, no Smith gate — internal/config-schema only, no user-facing behavior change yet (`scg onboard`'s CLI surface is untouched, §14.3).

---

## Phase 2 — Rule Matching & `MatchResult` Extension
*Chain: Neo → Trin → Morpheus*
*Depends on: Phase 1 (rules must exist to be matched).*

| Task | Description | Story Refs |
|------|-------------|-----------|
| 2.1 | Rule-matching in `resource_verifier.py`: for each identified `Resource`, first rule (declaration order) where `tool` regex matches `tool_name` and `pattern` regex matches `resource.identity` (optionally filtered by `scanner` if present) wins; implicit default rule (any/any, `sensitivity: public`, `mode: <defaults.mode>`) always matches last, constructed in code not YAML (§14.1) | STORY-1102, STORY-1103 |
| 2.2 | Extend `MatchResult` with `sensitivity`/`mode` fields; `evaluate()` resolves them per call using the existing most-restrictive-wins convention (`block` > `mask`, `restricted` > `internal` > `public`) when multiple resources' rule matches disagree (§14.4). `is_sensitive`/`is_trusted` keep their exact current meaning — do not touch their taint-tracking role | STORY-1102, STORY-1103 |
| 2.3 | Real tests: (a) STORY-1101's defect fix — onboard/verify one path under a host, confirm a second unverified path under the same host is not trusted; (b) STORY-1105's migration fail-safe — seed an old-format `reputation:<host>` cache entry, confirm it does not leak trust to a new-format lookup on a different path under that host | STORY-1101, STORY-1105 |

**Exit criteria:** Trin UAT passes on both real tests in 2.3 plus rule-precedence edge cases (no rule matches → default applies; multiple rules could match → declaration order + most-restrictive-wins is correct). Morpheus reviews. No Tank, no Smith gate — still no user-facing behavior change (nothing consumes `sensitivity`/`mode` yet).

---

## Phase 3 — Unconditional Masking & Docs
*Chain: Neo → Trin → Morpheus → Smith (required)*
*Depends on: Phase 2 (`MatchResult.mode` must exist to wire in).*

| Task | Description | Story Refs |
|------|-------------|-----------|
| 3.1 | `MaskingEngine.decide()`: drop the `taint`/`provenance_risk` gate entirely; scan every non-null payload value unconditionally *unless* `match.mode == "allow"` (skip scanning entirely — the scoped suppression exception, §14.4 amendment); action driven by `match.mode` instead of a caller-supplied global `mode` argument | STORY-1104, STORY-1103 |
| 3.2 | `hook_adapter.py`: update `pre_tool_use`'s `engine.decide(...)` call site for the new signature; `TaintState` load/save in `pre_tool_use`/`post_tool_use` stays exactly as-is (still feeds `scg monitor`'s Sessions panel, confirmed sole consumer) | STORY-1104 |
| 3.3 | `NFR-Perf-UnconditionalScan` real verification test (provisional <10ms/call budget, §14.4) — measure, don't assume, same standard as Sprint 4 Phase 2/3's precedent | STORY-1104 |
| 3.4 | Rework the suggested-onboard-command message (`hook_adapter._suggest_onboard_command`): drop the now-false "run this to stop future masking" framing; state plainly that scanning happens regardless of trust, and separately point to the `rules:`/`mode: allow` path (with an explicit warning it disables scanning for the matched pattern) as the real way to silence a known false positive. Rewrite `tests/test_onboard_suggestion_e2e.py`'s premise to match (an explicit `mode: allow` rule closes the loop now, not `scg onboard` alone) | STORY-1103 (§14.4 amendment) |
| 3.5 | Update `docs/USER_GUIDE.md`'s policy-config reference section for the new `rules:`/`sensitivity`/`mode` (incl. `allow`) schema (currently documents the pre-E11 model) | STORY-1102, STORY-1103 |

**Exit criteria:** Trin UAT passes (a call that previously would have been silently skipped now genuinely gets scanned and masked/blocked when it contains a real secret; a `mode: allow` rule genuinely suppresses scanning for its matched pattern and nothing else; the perf test in 3.3 passes for real). Morpheus reviews. **Smith `*user test` required** — this is the phase where a real behavior change becomes user-visible (masking now fires in cases it didn't before, and the false-positive-suppression story has fundamentally changed); Smith personally verifies the reworded messaging reads correctly and doesn't overstate what `scg onboard --target` alone still does (her Gate 1/2 condition — the flag stays single-purpose, it just means less than it used to).

## Notes
- No Tank phase — no daemon, no new port/service/env var (§14.7).
- Phases are hard-dependency-ordered: Phase 2 cannot resolve rule matches without Phase 1's schema existing; Phase 3 cannot wire `match.mode` into masking without Phase 2 producing it.
- STORY-1105's migration concern (§14.6) is fully addressed by Phase 1 (rewriting this repo's live config) + Phase 2's real fail-safe test — no separate migration-script task, per Morpheus's "no automatic re-keying" architecture decision.

---

# Sprint 6

**Owner:** Mouse
**Status:** ✅ **SPRINT CLOSED 2026-07-18** — Phase 1 (only phase) complete, every gate passed (Trin UAT with real end-to-end verification for all 3 tasks, Morpheus review). No Smith gate (no user-facing surface, correctly predicted). 275/275 tests passing.
**Source:** `docs/USER_STORIES.md` (E12) + Morpheus's `*lead arch sprint` handoff (2026-07-18)
**Scope:** Tech debt pulled from the Sprint 3-5 retro backlog, verified against current code before scoping — `PolicyRule.scanner` typo validation, a `make test-q` fast-feedback target, and an architecture-diagram drift guard.

1 phase — all 3 stories are small and fully independent (no shared files, no ordering dependency), unlike every prior sprint's hard-dependency or foundational-parallel shape.

## Phase 1 — Config Validation, Test Feedback Loop, Doc-Drift Guard
*Chain: Neo → Trin → Morpheus*
*Depends on: nothing new.*

| Task | Description | Story Refs |
|------|-------------|-----------|
| 1.1 | `PolicyRule.__post_init__` validates a non-empty `scanner` field against the real `SCANNERS` registry, raising `PolicyConfigError` on a typo — consistent with the existing `tool`/`pattern` regex-validation pattern | STORY-1201 |
| 1.2 | `make test-q`: real recipe is `unittest discover -s tests -b`. Verified empirically (not assumed): reduces logging/asyncio noise from 5 occurrences to 1 on a real run — genuinely quieter, not perfectly silent (one asyncio slow-callback warning survives from a test class whose event loop pre-dates `-b`'s per-test redirection). Stub routes through `mkf` like every other target; appears in `make help` | STORY-1202 |
| 1.3 | New `tests/test_architecture_docs.py`: parses `docs/ARCHITECTURE.md`'s `classDiagram` block, confirms every referenced class exists in `src/scalene/` (or its `<<module: file.py>>` stereotype's file exists) | STORY-1203 |

**Exit criteria:** Trin UAT passes (a real typo'd `scanner` value is rejected with a clear message; `make test-q` produces genuinely quieter output than `make test` on a real run; the doc-drift test both passes against the current, accurate diagram and fails with a clear message when a class is deliberately renamed to prove it's not a no-op). Morpheus reviews. No Tank, no Smith gate — no user-facing product surface (dev-tooling + internal docs only).

## Notes
- No Tank phase — no CI/infra changes, `make test-q` is a local dev convenience target using the same `mkf` wrapper every other target already uses.
- All 3 tasks touch different files with no shared state — genuinely parallelizable if ever split across implementers, kept as one phase here since the whole sprint is small.

---

# Sprint 7

**Owner:** N/A (direct user design session, same shape as Sprint 5's sec15 correction — implemented outside the sprint framework, closing formally through the same after-the-fact gate chain)
**Status:** ✅ **SPRINT CLOSED 2026-07-20** — implemented (picked up via bob-protocol), Trin UAT + Morpheus review both passed with no fix round. Smith's end-to-end test found 1 real bug (`--help` didn't disclose the `--sensitivity`/`--mode` requirement) — fixed by Neo, re-verified by Trin, re-approved by Smith, all within this close. Retro compiled, launched by Cypher. 291/291 tests passing.
**Source:** `docs/ARCHITECTURE.md` §16 (2026-07-18 direct user design session)
**Scope:** `scg onboard` becomes the single frontend for authoring a `PolicyRule` — one call now both runs the real scan (unchanged since §13.4) and writes a `rules:` entry to `scalene_policy.yaml` (`--tool`/`--pattern`/`--sensitivity`/`--mode`/`--scanner`/`--description`, one flag per `PolicyRule` field). This explicitly reverses §14.3's Smith-Gate-locked "CLI surface never changes" requirement — the reversal and its rationale are recorded in §16, not silently applied.

## Phase 1 — `scg onboard` Rule Authoring (retroactive)
*Chain: (implemented directly) → Trin → Morpheus*

| Task | Description | Ref |
|------|-------------|-----|
| 1.1 | `onboard()`/`main()` gain `--tool`/`--pattern`/`--sensitivity`/`--mode`/`--scanner`/`--description`/`--policy-path`; construct and validate a real `PolicyRule` (reusing its own `__post_init__` checks) before touching the cache; write it to `scalene_policy.yaml`'s `rules:` list without clobbering existing entries (comments excepted — documented known limitation) | §16 |
| 1.2 | At least one of `--sensitivity`/`--mode` required; `--mode` restricted to `allow`/`block` (`mask` rejected — has no distinct effect under sec15's `decide_access`) | §16 |
| 1.3 | Docs (`docs/USER_GUIDE.md`, `docs/GETTING_STARTED.md`) and tests (`test_onboard.py`, `test_user_guide_docs.py`, `test_getting_started_docs.py`, `test_cli.py`, `demo/run_demo.py`, `test_demo.py`) updated for the single-call workflow | §16 |

**Exit criteria:** Trin UAT (real end-to-end via installed binaries: full `GETTING_STARTED.md` walkthrough, `mode: allow`/`mode: block` against a real secret finding, comment-stripping known limitation) — **PASSED**. Morpheus review (rule validation ordering, class-diagram drift, policy-path consistency) — **APPROVED**. Smith end-to-end test — pending (elevated priority: this phase reverses her own §14.3 Gate 1/2 hard requirement).

## Notes
- No Tank phase — no infra/CI change, same category as Sprint 6.
- `docs/USER_STORIES.md` STORY-501's ACs predate this (and predate Sprint 4's original re-scope) — reconciled with a dated note, not rewritten (see USER_STORIES.md).
