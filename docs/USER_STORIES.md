# User Stories — Project Scalene

**Owner:** Cypher (PM)
**Status:** Sprint 1 (E1-E6) shipped and closed 2026-07-09. Sprint 2 (E7-E8) shipped and closed 2026-07-10. Sprint 3 (E9) shipped and closed 2026-07-16. Sprint 4 (E10) shipped and closed 2026-07-15. Sprint 5 (E11) — Draft v1, pending Smith Gate 1.

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
- [x] Every command in the doc is copy-pasteable and runs successfully on a clean clone (no undocumented prerequisites).
- [x] The walkthrough ends with the reader observing one concrete masked/blocked event (e.g. an entry in `.scalene/audit.log`), not just "install succeeded."
- [x] A person with no prior Scalene knowledge can complete it start-to-finish in under 5 minutes (Smith verified by timing a cold run: 24s machine time end-to-end).
- [x] `README.md`'s "Getting started" section is updated to link to this doc instead of duplicating/stubbing the content.

### STORY-902
As a developer operating Scalene day-to-day, I want a `docs/USER_GUIDE.md` covering all CLI commands, policy config options, and common workflows (onboarding a rule, reading the audit log, running the monitor console) in one place, so that I don't have to piece together usage from `SETUP.md`, `ARCHITECTURE.md`, and source code.

**Acceptance Criteria**
- [x] Documents every `scalene` and `scalene-guard` CLI command/flag that exists in the current codebase (verified against actual `--help` output, not assumed — and kept current through Sprint 4's flag changes, `--cache-path`/re-scoped `scg onboard`).
- [x] Documents `scalene_policy.yaml`'s schema by example, cross-referencing `ARCHITECTURE.md` (§13 as of Sprint 4's replacement of the §4-era allowlist schema) rather than duplicating the full schema definition.
- [x] Includes a troubleshooting section covering fail-safe behavior (what happens on malformed config, missing policy file, scan failure, and — added Sprint 4 — a genuinely fatal scanning-machinery failure).
- [x] `README.md`'s documentation table is updated to include this doc.
- [x] No content forked/duplicated from `SETUP.md` without a clear reason — link instead where the content already lives there.

### STORY-903
As a prospective user or reviewer, I want a runnable demo that shows Scalene actually stopping a realistic data-exfiltration attempt end-to-end, so that I can see the value in minutes without reading code or setting up my own project.

**Acceptance Criteria**
- [x] Demo is a scripted, repeatable flow (`make demo` / `demo/run_demo.py`) — not a one-off manual walkthrough that can drift out of date silently.
- [x] Demo scenario matches a real scenario (a session that's touched sensitive data, followed by an untrusted-destination call) and shows the actual masked output, not a mocked/fake result — messaging/onboard-suggestion format kept current through Sprint 4's changes (verified live at Sprint 3 close, 2026-07-16, not just re-reading old output).
- [x] Demo runs offline with no real external network egress — confirmed no network-capable imports exist in `demo/run_demo.py`; `scalene-guard` is decision-only by architecture and never performs the tool call itself.
- [x] Demo's expected output is checked by a dedicated smoke test (`tests/test_demo.py`) so it can't silently break/rot as the codebase changes.

---

## E10 — Extensible Scanner Registry & Resource Verification

**Origin:** Direct user design session, 2026-07-14, following the CLI-simplification work in E-unnumbered (the `--list-type` → single `--target` URI-scheme unification, shipped as commit `df8eb08`). That session surfaced a real gap: an onboarded allow/trust rule is verified once (one file, one domain) at onboard time, but the `pattern` it's paired with can match an unbounded, never-rescanned future set — nothing ties what was checked to what gets exempted going forward. E10 replaces one-time onboarding verification with autonomous, cached, continuously-refreshed resource verification.

**Full design context (from conversation, condensed for implementers):**
- Regex pattern matching (from the URI-scheme epic) stays — it's the right tool for expressing broad, reusable rules (e.g. "any file under `/workspace/public/`", "any `git` command"). The gap wasn't regex itself; it was that the *scan* only ever validated one instance while the *pattern* could apply to a whole class, with the two independently authored and never cross-checked.
- Named regex capture groups let a rule narrow *which part* of a matched value gets handed to a scanner (e.g. just a URL's host), instead of always scanning the whole matched string. No named groups → whole matched value is scanned (unchanged default, stays simple for the common case).
- Each scanner type owns its own resource-identification logic — given `(tool_name, tool_call_args)`, it finds the resources *it* cares about (a file scanner looks for path-shaped strings, a URL scanner looks for URL-shaped strings, a Bash-command scanner may look for both embedded in a shell string). This replaces requiring a human to hand-author jsonpath+pattern extraction for every resource shape. The scanner registry is extensible — new scanner types register without touching core dispatch logic.
- Scan results are cached per identified resource: files keyed by `(path, mtime)` (not a content hash — too slow to compute on every call), URLs/domains keyed by host with a scan timestamp. A cached result is fresh for 24h.
- **The fail-safe boundary this all hangs on:** a resource with *no* cache entry is not implicitly trusted — it falls back to today's existing fail-safe defaults (sensitive/untrusted) until an actual scan produces a real label for it. A resource with a *fresh* cache entry uses that label directly (fast path). A resource with an *expired* (>24h) cache entry uses the last-known label immediately, **without blocking**, while a background rescan refreshes the cache for next time. Only the true first-sighting case is synchronous/blocking; every renewal is background-only. This is what makes continuous re-verification affordable inside the existing <15ms NFR instead of a one-time approval that ages indefinitely.
- "Fatal" is about the scanning *machinery*, not scan findings: a scan that finds a real secret or bad reputation is an ordinary decision (mask/block), same as today, exit 0. A failure in the scanning subsystem itself (cache store unwritable/corrupted, a registered scanner crashing) is fatal — `scalene-guard` exits non-zero. This is a deliberate, narrow exception to the project's existing "adapter-internal problems always fail safe to exit 0" rule (`cli.py`'s docstring) — Morpheus must reconcile exactly which failure classes stay fail-safe-exit-0 versus which are newly fatal-non-zero, so this doesn't quietly widen into "any scan error blocks the agent."
- Whatever labels *did* resolve for a call (e.g. `trusted`, `public`, `sensitive`, `untrusted`) should always be surfaced in the response, independent of whether the overall call was fatal.
- A summary of recent scan results (resource, label, when last scanned) should be queryable — `scg monitor` is the natural home given it already surfaces live session/mask-event state, but Morpheus should confirm rather than assume.

**Explicit open question for Morpheus (architecture step):** does this *replace* the `scg onboard`/single-`allowlist`-with-`target`-URI model shipped just before this epic, or *coexist* with it (e.g. autonomous scanning handles the common cases, manual onboarding remains for pre-emptive approval of something never yet encountered live)? This needs a firm answer before phase breakdown — Mouse cannot size phases against an ambiguous foundation.

### STORY-1001
As a developer writing policy rules, I want `pattern` to support named regex capture groups, so a rule can hand a scanner just the relevant sub-value (e.g. a URL's host) instead of the whole matched field — while rules with no named groups keep scanning the whole matched value, unchanged.

**Revised 2026-07-15 (Cypher, at sprint close, per Oracle's groom-pass flag):** this story's premise was written before Morpheus's §13.1 architecture decision (full replacement of `PolicyRule`/`allowlist` — no user-authored `pattern`/`jsonpath` at all, not just this story's rules). The underlying capability (extract a specific sub-value rather than the whole match) was still delivered, but as an internal detail of each *built-in scanner's own* detection regex (e.g. `URLScanner`'s fallback pattern's `(?P<host>...)` group), never exposed to a developer as config. Rewriting the story below to describe what actually shipped, rather than leave a materially wrong premise in a "locked" doc through launch.

**As shipped:** As a scanner author (not a developer authoring config), I want each built-in scanner's own detection regex to support named capture groups, so a scanner can extract just the relevant sub-value (e.g. a URL's host) from its generic fallback match instead of the whole matched string.

**Acceptance Criteria**
- [x] ~~A rule's `pattern` may contain named capture groups~~ — superseded; no user-authored `pattern` exists post-§13.1. Satisfied instead by: each built-in scanner's own fallback regex uses named capture groups internally (`src/scalene/scanner.py`'s `_URL_FALLBACK_RE`'s `(?P<host>...)`).
- [x] ~~A rule with no named groups behaves exactly as before~~ — N/A, no user-authored rules exist to have or lack named groups.
- [x] At least one worked example per existing scanner type (file path capture, URL host capture) is covered by a real test, not just documented — `tests/test_scanner.py`'s `FileScanner`/`URLScanner` identify() tests.

### STORY-1002
As a developer, I want each scanner type to identify its own candidate resources within any tool call's arguments, so common resource shapes (file paths, URLs) are found automatically without a human hand-authoring an extraction rule for every case.

**Acceptance Criteria**
- [x] A scanner interface/protocol exists exposing resource identification over `(tool_name, tool_call_args)`, independent of any specific `jsonpath` — `Scanner` Protocol, `identify()`, `src/scalene/scanner.py`.
- [x] The scanner registry is extensible: adding a new scanner type requires implementing the interface and registering it, not modifying core dispatch logic — `SCANNERS` dict. (Note carried from Morpheus's Phase 3 review: this holds at the registry/detection layer; the aggregation layer, `resource_verifier.py`, still hardcodes which 2 scanner names feed which `MatchResult` dimension — a 3rd scanner needs a human decision there, `MatchResult`'s shape can't auto-extend.)
- [x] Ships with at minimum a file/secrets scanner and a URL/reputation scanner, at parity with today's existing secrets-scan and reputation-check capabilities (no regression) — `FileScanner`/`URLScanner`, both wrap the pre-existing `secrets_scan.py`/`LocalHeuristicChecker` unchanged.
- [x] A Bash-command scanner is either implemented or explicitly deferred with a written reason — deferred: `Bash`'s `command` string is wired into both existing scanners' generic fallback instead of a 3rd scanner type (§13.2).

### STORY-1003
As a developer, I want scan results cached per identified resource with a 24h freshness window, so the same resource isn't re-scanned on every matching call and continuous verification stays inside the existing <15ms NFR.

**Note (Cypher, at sprint close):** the NFR itself was revised mid-sprint (Morpheus measured the real first-sighting cost and found it real; see `docs/ARCHITECTURE.md` §13.3's `NFR-Perf-FirstSighting`) — the *cached* path still meets the original <15ms, which is what this story's "stays inside the existing NFR" actually depended on.

**Acceptance Criteria**
- [x] Cache entries are keyed by resource identity — corrected from the original wording ("files by `(path, mtime)`"): the cache *key* is the path alone (`f"{scanner_name}:{identity}"`); `mtime` is stored as a *value* field checked for freshness, not part of the key. The AC's intent (a changed file must be re-verified) is fully satisfied by `ScanCache.is_fresh()`.
- [x] A resource with no cache entry is not treated as trusted/non-sensitive — today's fail-safe defaults apply until a real scan result exists for it.
- [x] A fresh (<24h) cache entry is used directly — no scan runs.
- [x] An expired (>24h) cache entry's last-known label is used immediately (no blocking) while a rescan is kicked off in the background to refresh it.
- [x] A resource with no cache entry at all triggers a background scan; the fail-safe default (not a blanket allow) determines the current call's outcome while it's pending.

### STORY-1004
As an operator, I want `scalene-guard` to exit non-zero only when the scanning machinery itself fails, so real infrastructure problems are distinguishable from ordinary scan/mask decisions.

**Acceptance Criteria**
- [x] A scan that finds a real secret or bad reputation is an ordinary decision (mask or block per `mode`) — exit 0, same as today.
- [x] A scanning-machinery failure (cache store unreadable/corrupted/unwritable, a registered scanner raising unexpectedly) causes `scalene-guard` to exit non-zero — exit code **2**, empirically verified (not assumed) against Claude Code's real hook contract, both by fetching the current docs and by live-testing against this repo's own dogfooded `scalene-guard` installation.
- [x] Whatever labels did resolve for the call are still included in the response even when the exit is fatal, wherever determinable.
- [x] Malformed hook JSON / an unrecognized hook event still exit 0 (unchanged) — only scanning-machinery failures are newly fatal, per `docs/ARCHITECTURE.md` §13.5.

### STORY-1005
As a developer, I want a summary of recently-scanned resources and their labels, so I can audit what Scalene has actually verified without reading raw cache files.

**Acceptance Criteria**
- [x] Recent scan results (resource identity, label, last-scanned time) are viewable through `scg monitor`'s new resource-cache panel.
- [x] The summary reflects the real cache store — no separate/duplicated bookkeeping that can drift from it (`ScanCache.all_entries()`, confirmed via grep that no parallel reader exists).

---

## Sprint 2 — Deferred / Not Promoted to a Story

- **Placeholder wording fix** (Smith's non-blocking note, 2026-07-10: onboard-command placeholder says "domain-or-file" but every current suggestion is trust-list/domain-only): too small for a full story per Bloop's fast-track/consolidation rule — flagged to Mouse as a one-line task to fold into whichever Sprint 2 phase touches `hook_adapter.py`.
- **Relocate `_suggest_onboard_command()` out of `hook_adapter.py`** (Morpheus's review note, 2026-07-09): explicitly deferred until a second harness adapter is built — not actionable now, no second adapter exists.

---

## E11 — Trust/Sensitivity Model & Rule-Driven Resource Identity

**Origin:** Direct user design session, 2026-07-17, after Sprint 4 (E10) was formally closed. Two threads fed into this epic: (1) the user proposed adding a per-resource `mask`/`block` property at onboard time (`agents/morpheus.docs/proposal_per_resource_mode.md`); pursuing that surfaced a structural tension — `is_trusted` today means "content-scanning is skipped entirely," so a per-resource response mode would never fire on a trusted resource, since there's no detection event left to act on; (2) working through that tension in conversation with the user surfaced a second, more serious problem: `URLScanner`'s host-only resource identity (shipped in E10) **reproduces the exact defect E10 exists to fix** — one verification (scanning a single path under a host) vouches for an unbounded future set (every other path under that host), the same shape of bug as a `pattern` matching unboundedly from one scanned `target`, just relocated from user-authored regex into the resource-identity model itself. `docs/ARCHITECTURE.md` §13.8 documents the corrected design; this epic turns it into testable stories. **Not a new epic replacing E10 — an in-place correction of a defect in what E10 shipped**, following the same Bloop review process (Smith Gate 1/2, Morpheus architecture, Mouse phasing) as everything else in this document, not applied retroactively without review.

**Full design context (from §13.8, condensed for implementers — see the architecture doc for complete reasoning):**
- **Two independent axes, not parallel signals.** *Trust* answers "could this source cause the agent to do something malicious" (prompt-injection/tool-poisoning risk) — a source-legitimacy question, answered by scanning at whatever granularity actually distinguishes the safe case from the unsafe one (per-repo, not per-host, for anything multi-tenant like a public git host). *Sensitivity* answers "what's the blast radius if a malicious call involving this resource succeeds" — a data-classification question, independent of trust, with exactly three levels: **Public**, **Internal Only**, **Restricted**. The dangerous combination this whole project exists to prevent is low-trust *and* high-sensitivity together, not either alone.
- **Masking becomes an unconditional baseline, not sensitivity-gated.** An implicit, always-present default rule (any tool, any argument, `sensitivity: public`, `mode: mask`) matches every call unless a more specific rule overrides it — real-secret content-scanning no longer depends on a session already being tainted-sensitive-and-untrusted (`MaskingEngine.decide()`'s current `provenance_risk` gate). This is what makes `sensitivity: public` a safe default rather than a weakening.
- **`PolicyRule` returns, generalized — not the pre-Sprint-4 shape.** Fields: `tool` (regex), `jsonpath`, `pattern` (regex, named capture groups become resource identity), `sensitivity` (public/internal/restricted), `mode` (mask/block), `scanner` (optional), `description`. Critically, a rule only decides *candidacy and identity* — the scan cache (§13.3, unchanged) still verifies and freshness-tracks per distinct identity a rule's pattern actually matches. A wildcard rule widens what's *considered*, never what's *vouched for without checking* — this is the structural fix for the host-level-trust defect, generalized beyond just `URLScanner`.
- **Zero-config baseline is preserved.** `FileScanner`/`URLScanner`'s built-in generic-fallback detection (shipped in E10, unaffected) remains why a brand-new project gets real protection immediately; rules are an additive precision layer on top of the implicit default, not a prerequisite for any scanning to happen.
- The original per-resource `mask`/`block` proposal that started this thread is resolved as a side effect of the generalized model, not as its own separate Option-A/Option-B bolt-on: `mode` is a field on `PolicyRule`, which fires on every call via the always-on default rule, so a mask/block choice is available per rule (and therefore effectively per onboarded resource, via a rule scoped to it) without needing trust itself to become "always scan."

**Explicit open questions for Morpheus (architecture step — §13.8's own deferred list, not pre-decided here):**
1. The exact JSONPath expression for "any argument" in the default rule.
2. Whether `scanner` must always be explicit on a user-authored rule, or can be inferred the way URI-scheme inference works today for `scg onboard`.
3. The real on-disk schema for `PolicyRule` in `scalene_policy.yaml` — replaces the removed `allowlist`; does not resurrect the pre-Sprint-4 shape (`sensitivity`/`mode` are new, `target` does not return).
4. How `scg onboard --target` maps onto a generated rule with a sensible default pattern.

**Superseded 2026-07-17 (Cypher, groom pass, after the fact — during Phase 3's Smith gate, not before implementation):** the paragraphs above describe E11 exactly as planned and as Phases 1-2 shipped it — kept as the historical record, not rewritten. Phase 3's Smith gate found a real gap in the "masking becomes an unconditional baseline" design: a rule with `pattern: ".*"` + `mode: allow` could silently disable all content-scanning project-wide with zero validation behind it. Working through the fix with the user in real time replaced this epic's *entire core mechanism* — not a tweak to STORY-1104, a different model. `docs/ARCHITECTURE.md` §15 (rule-driven access control) is the real, shipped design: two sticky session tags (`trust`: low/med/high, `sensitivity`: public/internal/restricted, not a single masking mode), a call proceeds only if every resource it touches is validated + explicitly allow-ruled or the session is still clean, otherwise it's blocked outright. Masking/content-scanning (STORY-1104's mechanism) is **not deleted** but is dormant — `MaskingEngine` still exists and is tested, just not wired into the default decision path; whether it has a future role is explicitly undecided (§15.5), not ruled out.

This was implemented directly with the user, mid-conversation, not through a second `*pm plan sprint` cycle — these stories were never rewritten to match, by direct instruction (get the design right first). STORY-1101 (the host-level trust identity fix) and STORY-1105 (cache migration) shipped materially as written below — §15 didn't change resource identity or cache mechanics, only what happens with the resolved trust/sensitivity classification. STORY-1102/1103/1104 describe a mechanism (unconditional masking, per-rule mask/block/allow) that §15 replaced with access-control (allow/block a call, not mask its content) — read them as "what was originally planned," not "what runs today."

### STORY-1101
As a security-conscious developer, I want a resource's trust identity to be scoped narrowly enough to distinguish a specific verified resource from every other resource sharing its host/domain, so that onboarding one path doesn't silently vouch for everything else nearby.

**Acceptance Criteria**
- [ ] `URLScanner` (or its replacement matching logic) no longer treats an entire host as trusted on the strength of one scanned path under it by default.
- [ ] Two different resources under the same host can carry independent trust labels and independent scan-cache entries.
- [ ] Broadening trust to an entire host remains possible, but only via an explicit, visible rule (auditable in `scalene_policy.yaml`), not as an implicit consequence of resource-identity granularity.
- [ ] A real test demonstrates the fixed defect directly: onboard/verify one path under a host, then confirm a second, unverified path under the same host is *not* treated as trusted.

### STORY-1102
As a developer, I want `PolicyRule` to carry `sensitivity` (public/internal/restricted) as an axis independent of trust, so the response to a risky call can scale with blast radius rather than being conflated with source legitimacy.

**Acceptance Criteria**
- [ ] `PolicyRule` supports exactly three sensitivity levels: Public, Internal Only, Restricted — no open-ended/free-text classification.
- [ ] Trust and sensitivity are computed independently for a given call; neither is derived from the other.
- [ ] A worked example (via a real test) shows a low-trust + low-sensitivity resource handled differently from a low-trust + high-sensitivity one, demonstrating the axes actually combine rather than collapse into one signal.

### STORY-1103
As a developer, I want to set `mode: mask | block | allow` per rule, so I can choose the response to a real finding independently for each classified resource instead of relying on one global `defaults.mode`.

**Revised 2026-07-17 (found during Phase 1 review, resolved directly with the user):** a third `mode` value, `allow`, was added after implementation began. Making STORY-1104's scanning unconditional removes the exemption path E10's onboarding used to provide (onboarding a destination as "trusted" used to stop scanning entirely) — with nothing to replace it, a known false positive (e.g. a test fixture shaped like a real secret) would have no way to be permanently silenced. `allow` is the narrow, explicit replacement: reachable only by hand-authoring a `rules:` entry, never automatically via `scg onboard`. See `docs/ARCHITECTURE.md` §14.4's amendment for the full reasoning.

**Acceptance Criteria**
- [ ] `PolicyRule` carries a `mode` field (`mask` | `block` | `allow`), honored by `MaskingEngine`'s decision path for calls matched by that rule.
- [ ] `mode: allow` skips content-scanning entirely for a matched call (`MaskingEngine.decide()` returns `allow` without calling `scan_text_for_secrets`) — the deliberate, scoped exception to STORY-1104's "unconditional" rule.
- [ ] `mode: allow` is reachable only via a hand-authored `rules:` entry in `scalene_policy.yaml` — `scg onboard --target` never sets it, directly or indirectly.
- [ ] The global `defaults.mode` in `scalene_policy.yaml` remains the fallback for calls matched only by the implicit default rule (STORY-1104), not removed. `defaults.mode` itself is not extended to accept `allow` (blanket-allow-by-default would defeat the point of a scoped, deliberate exception) — only `PolicyConfig.mode`'s existing `mask`/`block` pair stays valid there.
- [ ] Resolves the original proposal that opened this epic (`agents/morpheus.docs/proposal_per_resource_mode.md`): a developer can express "let the agent use this resource, but block rather than mask if something real turns up here" without trust itself having to become "always scan."

### STORY-1104
As a developer, I want content-scanning to run as an unconditional baseline on every call by default, so real-secret detection doesn't silently depend on a resource's trust/sensitivity classification being correct.

**Acceptance Criteria**
- [ ] An implicit, always-present default rule (any tool, any argument, `sensitivity: public`, `mode: mask`) is active with zero user configuration.
- [ ] `MaskingEngine.decide()`'s current gate (scanning only when a session is already tainted-sensitive *and* tainted-untrusted) is removed/replaced so a call can be scanned even when neither prior taint flag is set.
- [ ] A user-authored rule can override the default for a more specific match (e.g. `mode: block` for a rule matched by a `restricted`-sensitivity resource) — the default is a floor, not a ceiling.
- [ ] A real test confirms a brand-new project with zero authored rules still gets real content-scanning coverage on an arbitrary call, not just previously-tainted ones.

### STORY-1105
As an operator upgrading from Sprint 4, I want a defined, explicit migration path for the scan cache's resource-identity scheme, so an existing project's `.scalene/scan_cache.json` doesn't silently misbehave when resource identity granularity changes underneath it.

**Note (Cypher):** flagged as a gap by Morpheus's own next_steps.md, not covered by §13.8 itself — surfacing explicitly as a story rather than letting it be silently skipped during implementation, per this epic's own design principle.

**Acceptance Criteria**
- [ ] Existing `scan_cache.json` entries keyed under the old host-level `URLScanner` identity scheme are explicitly accounted for on upgrade — either re-keyed by a migration step, or explicitly left to expire/re-verify under the new identity scheme with a clearly documented reason for that choice.
- [ ] The chosen path is fail-safe by construction: an old-scheme cache entry that no longer matches the new identity scheme must never be silently read as still-valid trust for a narrower, unverified resource.
- [ ] `scalene_policy.yaml` configs written before this epic (no `allowlist`/`PolicyRule` entries exist post-E10 by construction) continue to load without error — this story only needs to cover the *cache's* schema change, not a policy-config migration, since there is no pre-existing rule data to migrate on that side.
- [ ] The chosen migration behavior (re-key vs. re-verify-on-expiry) is covered by a real test simulating an upgrade from an E10-era cache file, not just documented.

---
