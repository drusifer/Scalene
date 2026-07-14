# User Stories — Project Scalene

**Owner:** Cypher (PM)
**Status:** Sprint 1 (E1-E6) shipped and closed 2026-07-09. Sprint 2 (E7-E8) shipped and closed 2026-07-10. Sprint 3 (E9) — Draft v1, pending Smith gate 1.

Format: `STORY-ID: As a <role>, I want <capability>, so that <value>.`

---

## E1 — Taint State Machine

### STORY-101
As an AI-enabled engineer, I want the system to track `has_sensitive_data` and `has_untrusted_data` as sticky booleans for the lifetime of my agent session, so that once tainted data enters context it stays flagged even across many tool calls.

**Acceptance Criteria**
- [ ] Both flags default to `false` at session start.
- [ ] A flag flipped to `true` never reverts to `false` except on explicit session/context reset.
- [ ] Flag state is queryable by the hook layer on every tool call without re-scanning prior calls.

### STORY-102
As an engineer, I want a tool read that matches the sensitive inventory to set `has_sensitive_data = true`, and a tool read that doesn't match the trusted inventory to set `has_untrusted_data = true`, so that provenance reflects actual data flow through the session.

**Acceptance Criteria**
- [ ] Rule matching runs on every tool result via `post_tool_call`.
- [ ] Matching against sensitive inventory sets only `has_sensitive_data`.
- [ ] Non-match against trusted inventory sets only `has_untrusted_data`.
- [ ] Both flags can be true simultaneously (this is the Triangle-of-Doom trigger condition).

---

## E2 — Policy Config Engine

### STORY-201
As an engineer, I want project-level policy defined in `scalene_policy.yaml` using JSONPath expressions, so that rules are declarative, git-versioned, and reviewable like code.

**Acceptance Criteria**
- [ ] Schema supports `non_sensitive_allowlist` and `trusted_sources_list` sections, each with `tool`, `jsonpath`, `pattern`, `description`.
- [ ] Schema supports project-level `defaults` (`sensitive_by_default`, `untrusted_by_default`).
- [ ] JSONPath expressions match nested JSON parameters, shell command strings (`$.command`), full URL paths, file system paths, and DB table/column targets.
- [ ] Invalid YAML fails config load with a clear error, not a silent no-op.

### STORY-202
As an engineer, I want malformed or non-matching JSONPath evaluation to fail safe, so that ambiguous cases never silently permit an unsafe call.

**Acceptance Criteria**
- [ ] A JSONPath expression that fails to parse or match results in `sensitive=true, trusted=false` for that argument.
- [ ] Fail-safe path is logged (not silent) for developer visibility.

---

## E3 — Tool Call Hooks

### STORY-301
As an engineer, I want every tool call intercepted by a `pre_tool_call` hook that evaluates arguments against policy before execution, so that masking can happen before a leak occurs, not after.

**Acceptance Criteria**
- [ ] Hook receives full tool name + argument payload before the tool executes.
- [ ] Hook evaluation (rule match + decision) completes in <15ms (NFR-Performance).
- [ ] Hook decision is one of: execute directly, execute with masked payload.
- [ ] Hooks are cross-platform: run identically on local dev, Docker, and cloud dev environments (NFR-Portability).

### STORY-302
As an engineer, I want a `post_tool_call` hook that updates taint labels from the tool's result via JSONPath provenance matching, so that state stays accurate for subsequent calls in the session.

**Acceptance Criteria**
- [ ] Hook runs after every tool call, success or failure.
- [ ] Hook updates `has_sensitive_data` / `has_untrusted_data` per STORY-102 rules.
- [ ] Sanitized output (post-masking, if applicable) is what's returned to the context window.

---

## E4 — Structural Masking

### STORY-401
As an engineer, I want the system to automatically mask outbound payload data (not block the call) when a tainted-sensitive context targets an untrusted destination, so my agent's workflow isn't interrupted by a hard failure.

**Acceptance Criteria**
- [ ] Trigger condition: `has_sensitive_data == true AND has_untrusted_data == true AND target is untrusted`.
- [ ] Masking replaces the payload field (e.g. HTTP body, file writer `text` param) with the literal string `[MASKED_BY_POLICY_PROVENANCE_GUARD]`.
- [ ] Masking is structural/blind — it does not attempt to parse or redact partial content; it fully replaces the identified payload field.
- [ ] Call syntax and non-payload arguments (e.g. destination path, method) are preserved so execution doesn't error out.
- [ ] Masking never throws a runtime error back to the agent.

---

## E5 — Onboarding Workflow

### STORY-501
As an engineer, I want an interactive command to onboard a new allowlist or trust-list pattern when I hit a false-positive block, so I can unblock my own workflow without editing YAML by hand or waiting on a security team.

**Acceptance Criteria**
- [ ] Onboarding command accepts a narrow rule pattern (tool + jsonpath + pattern) and writes it to `scalene_policy.yaml` on success.
- [ ] Allowlist onboarding runs a rapid credentials/secrets scan on the destination asset first; if secrets are found, onboarding fails with a clear reason.
- [ ] Trust-list onboarding runs an automated reputation/threat-intel lookup on the target resource/domain first; failure blocks onboarding.
- [ ] Successful onboarding is attributable (git-committed change) for compliance audit trail (BRD 1.2 Zero Overhead Compliance).

**Tank flag:** Trust-list onboarding depends on an external reputation/threat-intel lookup service — needs a Tank review for what service/API this calls, auth/env vars required, and network egress implications.

---

## E6 — Fail-Safe & Isolation

### STORY-601
As an engineer, I want the scanning infrastructure (credential scans, threat-intel lookups) to run in an isolated memory space, so that a compromised or misbehaving scanner can't itself become a new leak vector.

**Acceptance Criteria**
- [ ] Scanner processes are isolated from the main hook execution context (separate process/sandbox).
- [ ] Scanner actions use a context bypass token (`SCALENE_BYPASS=1`) to avoid re-triggering the interception hooks recursively (scanner loop prevention).

**Tank flag:** Introduces a new env var (`SCALENE_BYPASS`) and a sandboxing/process-isolation requirement — needs Tank input on isolation mechanism (subprocess, container, etc.) across local/Docker/cloud targets.

---

## Open Questions for Architecture (Morpheus) — Sprint 1

1. What runtime/language implements the hook layer — is this a Claude Code / Cursor plugin, a language-agnostic sidecar process, or both?
2. Where does taint state live for the session — in-memory per process, or persisted to disk for crash recovery mid-session?
3. What's the actual mechanism for `pre_tool_call`/`post_tool_call` hook registration — does this target a specific agent harness's hook API, or is it meant to be harness-agnostic?
4. What threat-intel/reputation service does trust-list onboarding call (STORY-501)? Is this a paid third-party API, and what happens if the developer runs offline?

All 4 resolved during Sprint 1 architecture/implementation — see `docs/ARCHITECTURE.md` and `docs/STORY_TRACEABILITY.md`.

---

# Sprint 2

**Scope per user direction (2026-07-10):** usability focus, promote backlogged items, and a new live list-management console.

## E7 — Live Taint & List Management Console

**Motivation:** Onboarding a false-positive already produces a ready-to-run `scalene onboard` command (`hook_adapter.py:_suggest_onboard_command`, shipped as the "copyable system messages" feature) and a JSON-lines audit trail (`.scalene/audit.log`) plus per-session taint state (`.scalene/state/<session_id>.json`). Today a developer only sees this if they're reading raw terminal `systemMessage` output or hand-parsing the log files. E7 turns those existing data sources into a live view a developer keeps open alongside their agent session.

### STORY-701
As an engineer running an agent session, I want a live view of my session's taint status and recent mask events, so I understand in real time why a call was masked without hand-parsing `.scalene/audit.log` or `.scalene/state/*.json`.

**Acceptance Criteria**
- [ ] Displays current `has_sensitive_data` / `has_untrusted_data` flags per active session, updating automatically as `.scalene/state/<session_id>.json` changes — no manual refresh action required.
- [ ] Displays a running feed of `.scalene/audit.log` mask events (tool name, payload field), newest first (by append order — the audit log has no timestamp field, and a separate AC below forbids adding one; ordering satisfies the "real time" intent), as they're appended.
- [ ] **Only surfaces an entry/indicator for calls where masking actually occurred** — mirrors the existing `hook_adapter.py` guarantee that no audit entry or `systemMessage` is emitted when nothing was actually masked (e.g. tools like `Read`/`WebSearch` with no mapped payload field). The console must consume that guarantee, not re-derive or weaken it — every tool call is not a mask event, and the UI must not imply otherwise. (User directive, 2026-07-10.)
- [ ] Requires zero changes to the audit log / state file formats to become visible — reads the existing files as-is.
- [ ] If no session/audit data exists yet (fresh project, no calls made), the view says so clearly rather than showing a blank screen or an error.

### STORY-702
As an engineer, I want the console to show me the suggested `scalene onboard` command for each masked call and let me run it without a terminal context-switch, so onboarding a false positive is a one-click action.

**Acceptance Criteria**
- [ ] Each mask event surfaces its existing `suggested_onboard_command` audit field, with the `<domain-this-call-reaches>` placeholder editable inline before running.
- [ ] Triggering "apply" runs the exact `scalene onboard` command and reports success/failure back in the console — not fire-and-forget.
- [ ] The console is a UI shell over the existing onboarding CLI only — it never bypasses onboarding's existing safety gates (secrets scan / reputation lookup).
- [ ] Dismissing a suggestion has no side effect (no partial YAML write, no state change).

**Open question for Morpheus (architecture step):** TUI (e.g. Textual, reads local files directly, no new process/port) vs. local web frontend (needs a localhost server — evaluate whether that counts as a "new service" requiring a lightweight Tank note, even though it's dev-local-only with no deploy/CI footprint). Also: filesystem-watch vs. poll for "realtime" — `audit.log`/state files are plain files, not a socket or event stream.

---

## E8 — Category-Aware Secrets Scan (from backlog)

**Origin:** `agents/morpheus.docs/BACKLOG.md` (2026-07-09 research, promoted into Sprint 2 per user direction to include backlogged items).

### STORY-801
As a security-conscious engineer, I want the onboarding secrets scan to detect a broader category of credential types instead of 3 hand-rolled regexes, so trust-list onboarding doesn't approve a resource that still contains an undetected credential.

**Acceptance Criteria**
- [ ] `secrets_scan.py`'s detection is upgraded to use `detect-secrets` (per backlog recommendation) in place of the current 3 hand-rolled regexes, with no change to the onboarding CLI's external interface/behavior for callers.
- [ ] All existing secrets-scan test fixtures continue to pass, adjusted for the new detector's actual match set — fixtures are fixed to reflect real detection, not weakened with scanner allowlist exceptions (project policy).
- [ ] No network egress introduced — `detect-secrets` is pure Python, preserves the offline-scan requirement (`ARCHITECTURE.md` §9).
- [ ] Category-aware masking of the mask *literal itself* (`MaskingEngine.apply_mask`, `scrubadub`/`presidio` per backlog) is explicitly **out of scope** for this story — backlog defers that until category-aware masking becomes an actual requirement, not just a nice-to-have.

---

---

## E9 — Documentation & Onboarding (Sprint 3)

**Origin:** Direct user request 2026-07-13 — no existing user-facing guide exists; `docs/SETUP.md` is install/reference-oriented, `README.md`'s "Getting started" is a 3-line stub, and there is no runnable demonstration of Scalene actually stopping an exfiltration attempt.

### STORY-901
As a new user evaluating Scalene, I want a `docs/GETTING_STARTED.md` that takes me from a clean clone to seeing Scalene mask a real tool call in under 5 minutes, so that I can validate the tool works before investing time in full configuration.

**Acceptance Criteria**
- [ ] Every command in the doc is copy-pasteable and runs successfully on a clean clone (no undocumented prerequisites).
- [ ] The walkthrough ends with the reader observing one concrete masked/blocked event (e.g. an entry in `.scalene/audit.log`), not just "install succeeded."
- [ ] A person with no prior Scalene knowledge can complete it start-to-finish in under 5 minutes (Smith to verify by timing a cold run).
- [ ] `README.md`'s "Getting started" section is updated to link to this doc instead of duplicating/stubbing the content.

### STORY-902
As a developer operating Scalene day-to-day, I want a `docs/USER_GUIDE.md` covering all CLI commands, policy config options, and common workflows (onboarding a rule, reading the audit log, running the monitor console) in one place, so that I don't have to piece together usage from `SETUP.md`, `ARCHITECTURE.md`, and source code.

**Acceptance Criteria**
- [ ] Documents every `scalene` and `scalene-guard` CLI command/flag that exists in the current codebase (verified against actual `--help` output, not assumed).
- [ ] Documents `scalene_policy.yaml`'s schema by example, cross-referencing `ARCHITECTURE.md` §4 rather than duplicating the full schema definition.
- [ ] Includes a troubleshooting section covering fail-safe behavior (what happens on malformed config, missing policy file, scan failure).
- [ ] `README.md`'s documentation table is updated to include this doc.
- [ ] No content forked/duplicated from `SETUP.md` without a clear reason — link instead where the content already lives there.

### STORY-903
As a prospective user or reviewer, I want a runnable demo that shows Scalene actually stopping a realistic data-exfiltration attempt end-to-end, so that I can see the value in minutes without reading code or setting up my own project.

**Acceptance Criteria**
- [ ] Demo is a scripted, repeatable flow (e.g. `make demo` or a `demo/` script) — not a one-off manual walkthrough that can drift out of date silently.
- [ ] Demo scenario matches a real BRD/PRD scenario (tainted-sensitive read followed by an untrusted-destination call) and shows the actual masked output, not a mocked/fake result.
- [ ] Demo runs offline with no real external network egress (consistent with `ARCHITECTURE.md` §9's offline requirement) — any "untrusted destination" in the demo is simulated locally.
- [ ] Demo's expected output is checked by `make test` or a dedicated smoke test so it can't silently break/rot as the codebase changes.

---

## Sprint 2 — Deferred / Not Promoted to a Story

- **Placeholder wording fix** (Smith's non-blocking note, 2026-07-10: onboard-command placeholder says "domain-or-file" but every current suggestion is trust-list/domain-only): too small for a full story per Bloop's fast-track/consolidation rule — flagged to Mouse as a one-line task to fold into whichever Sprint 2 phase touches `hook_adapter.py`.
- **Relocate `_suggest_onboard_command()` out of `hook_adapter.py`** (Morpheus's review note, 2026-07-09): explicitly deferred until a second harness adapter is built — not actionable now, no second adapter exists.
