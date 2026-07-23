# User Stories — Project Scalene

**Owner:** Cypher (PM)
**Status:** Sprint 1 (E1-E6) shipped and closed 2026-07-09. Sprint 2 (E7-E8) shipped and closed 2026-07-10. Sprint 3 (E9) shipped and closed 2026-07-16. Sprint 4 (E10) shipped and closed 2026-07-15. Sprint 5 (E11 → sec15) shipped and closed 2026-07-18. Sprint 6 (E12, tech debt) shipped and closed 2026-07-18. Sprint 7 (E13 / sec16 correction) shipped and closed 2026-07-20. Sprint 8 (E14, Tool-Call-Driven Onboarding) shipped and closed 2026-07-21, full formal cycle, 3 phases, 1 fix round; STORY-1406 remains flagged, not committed. **Sprint 9 (E15, Configurable Scanner Registry & Extended Scanner Coverage) shipped and closed 2026-07-21** — full formal cycle, 4 phases, Phase 4 gated twice after a direct mid-sprint user design correction (implicit in-memory rule replaced with a real on-disk one), 1 real infra finding from Tank (URLhaus's "no API key" premise was false, resolved with a real Auth-Key + env var). 389/389 tests. **Sprint 10 (E16, Interactive Onboarding Dashboard & Non-Blocking Review Loop) shipped 2026-07-23** — full formal cycle, 6 phases, 2 mandatory Smith gates (accessibility, core interactive flow) both passed. Origin: direct user `*user consult` with Smith. One mid-planning correction (STORY-1603 restored to full-call-log scope after a cost-conflation error, direct user catch) and one mid-implementation correction (STORY-1606's OS-mount verification shelved and its replacement design backlogged, direct user decision) — both recorded, not silently absorbed. 439/439 tests.

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
- [x] Onboarding command accepts a narrow rule pattern (tool + jsonpath + pattern) and writes it to `scalene_policy.yaml` on success.
- [x] Allowlist onboarding runs a rapid credentials/secrets scan on the destination asset first; if secrets are found, onboarding fails with a clear reason.
- [x] Trust-list onboarding runs an automated reputation/threat-intel lookup on the target resource/domain first; failure blocks onboarding.
- [ ] Successful onboarding is attributable (git-committed change) for compliance audit trail (BRD 1.2 Zero Overhead Compliance). Resolved differently than literally written: `scg onboard` never auto-commits on the developer's behalf (no git-write authority needed); attributability is satisfied by writing a clear, reviewable diff to `scalene_policy.yaml` for the developer to commit themselves. Left unchecked since the AC as written (git-committed) isn't literally what ships.

**Tank flag:** Trust-list onboarding depends on an external reputation/threat-intel lookup service — needs a Tank review for what service/API this calls, auth/env vars required, and network egress implications.

**Reconciled 2026-07-20 (Oracle, groom pass, sec16 close):** this story's premise went through 3 mechanism changes since it was written — Sprint 4/§13.4 re-scoped onboarding to cache-pre-seeding only (dropped rule-authoring entirely), then a direct user design session (`docs/ARCHITECTURE.md` §16, post-Sprint-6) restored rule-authoring in a more specific form than originally described here: CLI flags matching `PolicyRule`'s exact field names (`--tool`/`--pattern`/`--sensitivity`/`--mode`/`--scanner`/`--description`), not a single freeform "rule pattern." The first 3 ACs above are genuinely satisfied by what ships today — checked off against real, current behavior, not the original literal wording. Kept as historical record per this doc's append-only-correction convention, not rewritten.

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

## E12 — Tech Debt: Config Validation, Test Feedback Loop, Doc-Drift Guard

**Origin:** `*sprint tech debt` — a dedicated sprint pulling from the retro backlog accumulated across Sprints 3-5, not a new user-facing feature request. Before writing stories, each carried-forward item was checked against the current codebase rather than assumed still open: `_suggest_onboard_command`'s adapter-layer-placement debt is moot (the function was deleted entirely in the sec15 rework); `cache_refresh_worker.py`'s cache-write exception-handling gap was already closed in Sprint 4 Phase 4; the scan-cache `os.stat()` TOCTOU gap and `resource_verifier.evaluate()`'s hardcoded 2-scanner aggregation are both still technically present but low-value (the TOCTOU gap was already judged "not worth a fix round" by Morpheus, and `evaluate()` is dormant code since sec15 — not part of the live decision path). Three items are real, open, and worth fixing:

1. A rule's `scanner` field has no validation against the real scanner registry — a typo (Trin's Sprint 5 UAT finding, `agents/trin.docs/current_task.md`) silently makes the rule permanently ineffective with zero warning, the same shape of gap the regex-validation fix (Sprint 5 Phase 2) already closed for `tool`/`pattern`.
2. `make test-q` (a concise/quick test target, distinct from `make test`'s full lint+secret-scan+verbose run) has been flagged twice across sprints (Trin's Sprint 4 and Sprint 5 retros) and never built.
3. Architecture doc drift goes undetected — Morpheus's Sprint 5 architecture review found 3 stale references in §4/§5 (a class's fields, a method's signature, a whole sequence diagram) that no automated check would have caught, since Mermaid diagrams and prose aren't executable.

Explicitly out of scope for this sprint (process/Bob-protocol items from the retro backlog, not code): "3rd status bucket for gated-then-superseded," "codify hostile-input testing as standing protocol," "cold-start should check for unresolved handoffs." These belong to Bob's (prompt-engineering persona) domain, not a software delivery sprint.

### STORY-1201
As a developer authoring a `scalene_policy.yaml` rule, I want an invalid `scanner` value to be rejected at config-load time with a clear error, so a typo doesn't silently produce a rule that never matches anything.

**Acceptance Criteria**
- [x] `PolicyRule.__post_init__` validates a non-empty `scanner` field against the real scanner registry (`SCANNERS` in `scanner.py`), raising `PolicyConfigError` with a clear message (naming the invalid value and, ideally, the valid options) if it doesn't match a registered scanner name.
- [x] An empty/omitted `scanner` (the common case — inferred from the matched resource) is unaffected — validation only applies when a value is actually provided.
- [x] Consistent with the existing `tool`/`pattern` regex-validation precedent: fails loud at rule-construction time, not silently or deep in `decide_access()`'s hot path.
- [x] A real test constructs a rule with a plausible typo (e.g. `"reputatoin"`) and confirms it's rejected, not silently accepted — verified both via unit test and end-to-end through `PolicyConfig.from_yaml` against a real YAML file (Trin's UAT).

### STORY-1202
As a developer running the test suite frequently during iteration, I want a `make test-q` target that gives fast, concise feedback, so I don't have to wait for or scroll past incidental logging/asyncio noise on every quick check.

**Revised 2026-07-18 (Neo, during implementation):** the story's original premise ("make test's full lint+secret-scan+verbose output") was carried over from the generic `make` skill's doc, which turned out to be wrong for this project — `make test`'s real recipe is plain `unittest discover`, no lint or secret-scan step (the project's secret-scanning is a separate pre-commit gitleaks hook, not part of `make test`). Corrected here and in the `make` skill rather than leaving a wrong premise in a "locked" doc.

**Acceptance Criteria**
- [x] `make test-q` runs the same test suite as `make test` but with quieter output (`unittest discover -s tests -b`) — routed through `mkf`/`build/build.out` the same way every other target is. **Measured, not assumed**: reduces incidental logging/asyncio noise from 5 occurrences to 1 on a real run — genuinely quieter, not perfectly silent (one asyncio slow-callback warning survives from a test class whose event loop pre-dates `-b`'s per-test redirection). Documented honestly rather than overclaiming full suppression.
- [x] Appears in `make help`'s target list with a clear one-line description distinguishing it from `make test`.
- [x] Documented in the `make` skill guidance so it isn't lost again after this sprint (this is the second time it's been flagged and not built) — also corrected the skill's own pre-existing wrong claim about `make test`'s contents in the same pass.

### STORY-1203
As a maintainer reviewing an architecture change, I want a real check that `docs/ARCHITECTURE.md`'s class diagrams reference symbols that actually exist in the codebase, so stale diagrams get caught automatically instead of only when someone happens to read closely during a review.

**Acceptance Criteria**
- [x] A test parses `docs/ARCHITECTURE.md`'s Mermaid `classDiagram` block and confirms every referenced class name corresponds to a real class (or documented module-level stereotype, e.g. `<<module: resource_verifier.py>>`) somewhere in `src/scalene/`.
- [x] Deliberately scoped to class *existence*, not full method-signature fidelity — explicitly noted as a scope boundary, not silently underdelivered.
- [x] The test fails loudly with a clear message naming the stale reference if the diagram and code diverge, not a vague assertion failure — verified live: Trin temporarily renamed a real class in the actual doc, confirmed the exact failure message, then reverted.
- [x] Run as part of the normal `make test` suite (`tests/test_architecture_docs.py`), not a separate opt-in check that's easy to forget.

---

## E14 — Tool-Call-Driven Onboarding via the Scanner Framework

**Origin:** Direct user request (2026-07-20, post-Sprint-7): `--target` (a manually-typed `file://`/`https://` URI, unchanged since Sprint 4's §13.4 and still the sole input `scg onboard` accepts even after sec16's rule-authoring rework) should be retired in favor of re-using the scanner framework already doing this same identification work, live, on every hook call. Each `Scanner.identify(tool, args)` (`scanner.py`, unchanged since Sprint 4) already knows how to recognize the resources *its own* scanner type cares about in a real tool call — onboarding should call that directly instead of asking a human to hand-resolve and type a URI. User's own framing: run onboarding against the tool call itself, let each scanner claim what it recognizes, confirm the resulting target list with the developer, then scan and onboard only what's confirmed.

This is additive to sec16 (`docs/ARCHITECTURE.md` §16) — sec16's per-target rule-authoring (`--sensitivity`/`--mode`/etc.) is not being removed, only how a target gets *identified* changes. Genuinely new concepts this epic introduces (a per-scanner "inventory" of onboarded targets, a reputation score alongside the existing sensitivity label, an interactive confirmation step) don't have prior architecture decisions to build on — several mechanism questions are carried to Morpheus explicitly below rather than pre-decided here.

### STORY-1401
As a developer onboarding a resource, I want `scg onboard` to identify targets automatically from a real tool call instead of me typing a `--target` URI by hand, so that onboarding uses the exact same recognition logic already trusted to make live pre-call decisions, instead of a second, hand-maintained resolution path that can drift from it.

**Acceptance Criteria**
- [x] `--target` is removed from `scg onboard`'s CLI surface.
- [x] Onboard accepts a description of a real tool call (tool name + args) as its new input.
- [x] Onboard traverses the full `SCANNERS` registry — not one hardcoded scanner — calling each registered scanner's own `identify(tool_name, args)` and collecting every distinct `Resource` found across *all* scanner types in one pass. A call touching both a file and a URL (e.g. a `Bash` command with both) is fully covered by one invocation, not one per resource.
- [ ] No separate/duplicated target-resolution logic in `onboard.py` — identification is exactly `Scanner.identify()`, unchanged, the same call `pre_tool_use` already makes live. **Partially true, reconciled 2026-07-21 (Oracle):** the CLI's own resolution is exactly `identify_targets()`/`Scanner.identify()`, as written. But `_resolve_resource()` (the old single-URI resolver) was deliberately *kept*, not deleted — Neo's Phase 3 implementation found its dedicated test (`test_unknown_scheme_blocks_with_no_cache_write`) exercises real URI-scheme-validation behavior with no equivalent in the new flow. It now serves a distinct, still-tested library entry point (`onboard()`), not a competing/duplicated path the real CLI could drift against — but the AC as literally written implied full removal, which didn't happen.

### STORY-1402
As a developer onboarding a resource, I want to see and confirm exactly which targets `scg onboard` identified before anything is scanned or written, so an incidental path- or URL-shaped string the tool call happened to also contain doesn't get onboarded as a side effect of a target I actually meant to trust.

**Acceptance Criteria**
- [x] Before any scan runs, onboard shows every identified `Resource` (kind, identity, which scanner claimed it) as a reviewable list.
- [x] The developer can confirm the full list or exclude individual targets before proceeding — no scan and no write happens for an excluded target.
- [x] Declining every identified target exits cleanly with no scan, no cache write, no rule write — a deliberate no-op, not an error.
- [x] Non-interactive/scripted invocation (tests, CI, automation) stays possible — resolved as `--yes` (accept all) and `--only <identity,...>` (accept a named subset, fails loud on a name that wasn't identified); fails fast (no hang) if neither is given and stdin isn't a TTY.

### STORY-1403
As a developer onboarding a resource, I want each confirmed target scanned for real before it's onboarded, so onboarding keeps Scalene's existing "never claim safety without a real check" guarantee even though target discovery is now automatic instead of manually typed.

**Acceptance Criteria**
- [x] Each confirmed target is scanned via its owning scanner's `scan()` — unchanged mechanism from today, only how the target was found is new.
- [x] A clean scan result onboards that target (added to its scanner's inventory, per STORY-1404); a bad result blocks that specific target with a clear, plain-language reason. Other confirmed targets in the same batch are unaffected — partial success across a batch is real, not all-or-nothing. Verified live by Trin (1 clean + 1 real fake-secret target in one batch: exactly 1 onboarded, 1 blocked, exit 0).
- [x] sec16's existing `mode: allow`/`mode: block` semantics still apply per target — a bad finding can still be explicitly declared blocked, same as today.

### STORY-1404
As a developer, I want each scanner to track which resources it has actually onboarded (its "dependencies"), so I can see, per scanner type, exactly what's been explicitly vetted and trusted — not have to infer it indirectly from the scan cache or the policy file.

**Acceptance Criteria**
- [ ] Each scanner exposes a queryable inventory of the targets it has onboarded (identity, when, scan result). **Resolved differently than literally written, reconciled 2026-07-21 (Oracle):** §17.5 deliberately chose *not* to add a per-scanner inventory API or a new store — `scg onboard --list` is a read-only CLI view grouping the existing `ScanCache.all_entries()` by scanner name. The developer-facing value (see what's been vetted, per scanner type) is delivered; "each scanner exposes" as an object-level API is not. Left unchecked since the AC's literal mechanism wasn't built, by a considered architecture decision, not an oversight.
- [x] The inventory is visible somewhere a developer can actually check it — `scg onboard --list [--scanner NAME]`, reading `ScanCache` directly (no new store, so nothing here can drift from what `decide_access()` actually consults).
- [x] Onboarding a target updates only its own scanner's inventory, never another scanner's (cache keys are `scanner_name:identity`-prefixed by construction).

### STORY-1405
As a developer relying on a scan result to make a trust decision, I want the result to carry both a sensitivity classification and a reputation score, so onboarding (and any future evaluation of a tool call's actual results, per STORY-1406) has more signal than today's single pass/fail label.

**Acceptance Criteria**
- [x] A scan result carries a sensitivity classification and a reputation score, not just today's single `label`. **Reconciled 2026-07-21 (Oracle):** "sensitivity classification" turned out to already be solved — `PolicyRule.sensitivity` (developer-chosen at onboarding, per sec16) is this project's sensitivity axis; `ScanResult` itself only needed the genuinely new piece, `reputation: float | None`, additive alongside the unchanged `label`/`reason`.
- [x] The reputation score is computed for real from the scan — not a placeholder/stub value. `LocalHeuristicChecker.check()` was changed from first-match-wins to evaluate-all-3-heuristics specifically so the score reflects real evaluated signal; `FileScanner` deliberately stays `None` (no fixed-heuristic-count basis to build a fraction from), not silently defaulted to something that would look precise but isn't.
- [ ] Onboarding's allow/block decision can weigh both signals, not only a single pass/fail label. **Not done, honestly unchecked:** the shipped decision (`_onboard_resource()`) still gates purely on `result.label` — the reputation score is displayed (`-> trusted (score 1.00)`) but does not itself influence whether a target is blocked. Real, open follow-on work if a graded threshold is ever wanted, not silently claimed as done.

### STORY-1406 — Flagged, not committed this epic
"Scans... [may be] used to evaluate the results from the tool call if applicable" (user's own framing) — genuinely new scope, not a refinement of an existing decision: `post_tool_use` (`hook_adapter.py`) is currently an intentional no-op under §15, on the explicit rationale that every resource a call touches is knowable from `tool_input` alone before the call ever runs, so there's no tool-*response*-derived signal left to add. Scanning a tool's actual output would directly revisit that rationale. Not writing this as a committed story until Morpheus has weighed in on whether/how it coexists with §15 — flagged here so it isn't silently dropped, not pre-scoped by Cypher.

## Open Questions for Architecture (Morpheus) — E14

1. Does removing `--target` retire sec16's other flags (`--tool`/`--pattern`/`--sensitivity`/`--mode`/`--scanner`/`--description`) too, or do they still apply per-confirmed-target as an overlay on top of scanner-identified targets? The user only asked to remove `--target`.
2. What exactly is "a tool call" as onboard's new input — the same JSON shape `scalene-guard` already reads from stdin? A path to a saved audit-log entry? Something typed inline on the CLI? This is the shape of `scg onboard`'s entire new invocation contract.
3. Interactive confirmation mechanism (STORY-1402) — a blocking TTY prompt vs. a `--yes`/`-y` flag for scripts vs. piped input. This is a real UX design decision, not just a mechanism detail — needs Smith's input directly during Gate 1/2, not assumed here.
4. Is the "inventory of onboarded targets" (STORY-1404) a genuinely new on-disk store, or a reframing of the existing `ScanCache` + `PolicyConfig.rules` combination sec16 already writes? Both already durably record every scanned/onboarded resource — worth confirming a 3rd store adds real value rather than duplicating state that could drift from it.
5. Reputation score's scale/units (STORY-1405), and which scanners currently have enough real signal to compute one meaningfully — `reputation.py`'s `LocalHeuristicChecker` has exactly 3 heuristics (IP-literal, punycode, suspicious-length label) today; worth confirming a numeric score is meaningful now vs. starting coarse (e.g. a 0-2 count of heuristics triggered) and refining later.
6. STORY-1406 above — whether scan results ever apply to a tool call's *response*, and if so how that coexists with §15's post_tool_use no-op rationale.

---

## E15 — Configurable Scanner Registry & Extended Scanner Coverage

**Origin:** Direct user request (voice, 2026-07-21), per the user's own prior direction that the next sprint would focus on scanner work. Read `src/scalene/scanner.py`, `reputation.py`, and `scan_cache.py` before writing these stories. Most of what the user described is already shipped and working exactly as asked — not re-storied here: the two-entry-point `Scanner` protocol (`identify()`/`scan()`, since E10/STORY-1001), `FileScanner.scan()` already reusing the existing secrets-detection logic for sensitivity, and the 24h scan-cache expiration/rescan cycle (`scan_cache.py`, since E10/STORY-1003). Three things the user asked for are genuinely new:

1. `SCANNERS` (`scanner.py:178`) is today a fixed `{"secrets": FileScanner(), "reputation": URLScanner()}` dict literal — no config-driven way to add a scanner.
2. `FileScanner` has no hardcoded sensitive-path handling today — a clean secrets scan of e.g. `~/.ssh/id_rsa` currently returns `public`, same as any other clean file.
3. `reputation.py`'s `LocalHeuristicChecker` is 3 local, offline heuristics only (IP-literal, punycode, suspicious label) — no real external reputation source.

The user named enterprise integrations (asset inventory/CMDB, data-labeling systems, vulnerability databases) as the motivating *reason* for a configurable registry, and was explicit that "for now we'll start with the file system scanner and the url scanner" — so those enterprise scanners are this epic's rationale, not its scope. Not storied as build work this sprint; STORY-1501 delivers only the extension point they'd eventually plug into.

A follow-up user note added a 4th item: a new project's own folder should default to trusted + Internal Only rather than today's global untrusted/sensitive-by-default posture — added as STORY-1504.

### STORY-1501
As an operator, I want Scalene to load its built-in scanners (FileScanner, URLScanner) by default but allow registering additional scanners via config, so that enterprise-specific scanners (asset inventory/CMDB, data-labeling systems, vulnerability databases) can plug in later without editing `scanner.py`.

**Acceptance Criteria**
- [x] `SCANNERS` is populated from config at startup (built-ins on by default) instead of being a fixed dict literal in `scanner.py`. `scanner.load_scanners()` + `PolicyConfig.scanners`.
- [x] A config-declared scanner can be registered without modifying `scanner.py`. `scalene_policy.yaml`'s `scanners: extra:` section, `importlib`-loaded.
- [x] Omitting scanner config from `scalene_policy.yaml` preserves today's exact default behavior (`FileScanner` + `URLScanner` only, same names/order) — no silent behavior change for existing projects/configs. Verified: `PolicyConfig.scanners` defaults to `dict(SCANNERS)`.
- [x] Enterprise integrations themselves (asset inventory, data-labeling, vulnerability-database scanners) are explicitly NOT built this sprint. Confirmed — not built.

### STORY-1502
As a user, I want well-known sensitive system paths (e.g. `/etc`, the user's `~/.ssh`) to always be classified Restricted sensitivity and Untrusted, regardless of what the secrets scan finds, so a clean secrets-scan result on a path like `~/.ssh/id_rsa` can't be mistaken for safe-to-treat-as-public.

**Acceptance Criteria**
- [x] `FileScanner` forces `sensitivity=restricted` + untrusted for a defined set of sensitive path prefixes, independent of the underlying secrets-scan outcome for that path. **Reconciled 2026-07-21 (Oracle):** the real mechanism is `ScanResult(label="sensitive")`, which `decide_access()` treats as `confirmed_bad` — an unconditional block, regardless of any rule. Neo traced `decide_access()`'s actual control flow during implementation and found the originally-designed "implicit restricted `PolicyRule`" addition to `resource_verifier.py` would have been unreachable dead code (`is_bad` is checked before any rule match) — the tri-level `sensitivity=restricted` label and a distinct "untrusted" trust state, as literally worded, aren't what gets produced; an unconditional block is, which is the AC's real intent (this path can never be treated as safe).
- [x] `/etc` and the invoking user's `~/.ssh` are in the default set. `_HARDCODED_RESTRICTED_PREFIXES`.
- [x] Verified for real: a path under one of these prefixes with a clean (no-secrets-found) scan is still labeled restricted/untrusted, not public/trusted. Verified via `tests/test_resource_verifier.py::TestHardcodedRestrictedPaths` and `tests/test_scanner.py`, using the real `FileScanner`, not a fabricated result.

### STORY-1503
As a user relying on URL reputation results, I want `URLScanner`'s validation to draw on real open-source or free-tier external reputation/threat-intel sources, not just today's 3 local offline heuristics, so a genuinely malicious or newly-registered domain has a realistic chance of being caught.

**Acceptance Criteria**
- [x] `URLScanner.scan()` consults at least one real external open-source/free-tier reputation data source, in addition to (not replacing) the existing local heuristics. `URLHausChecker` (abuse.ch) + `composite_check()`.
- [x] A source-unreachable or rate-limited condition degrades to today's local-heuristic-only result rather than blocking every call (`ScannerMachineryError` semantics unaffected). `ReputationCheckUnavailable`, verified via `tests/test_reputation.py`.
- [x] **Flagged for Tank**: introduces outbound network calls to a third-party service and likely new config (API keys/rate limits) — needs Tank's review on env vars/service dependency, per the standard Cypher-Tank protocol for stories touching external services. **Tank's review found the endpoint's "no API key" premise was false in practice** (verified live, not from docs) — user decided to obtain a free Auth-Key via `SCALENE_URLHAUS_AUTH_KEY` (`.env.example`), never hardcoded. Tank re-reviewed and approved the fix.

### STORY-1504
As a developer setting up Scalene on a new project, I want the project's own folder to default to trusted + Internal Only, so that onboarding doesn't start by treating my own codebase — the thing Scalene exists to protect, not attack — as an unrecognized, untrusted resource requiring the same scrutiny as arbitrary external files/URLs.

**Acceptance Criteria**
- [x] A newly onboarded project's own root folder defaults to `trust=trusted`, `sensitivity=internal` — not today's global `untrusted_by_default`/`sensitive_by_default` posture, and not `public` (the project's source is not meant to be world-shareable either). **Reconciled 2026-07-21 (Oracle):** "trust=trusted" as literally worded doesn't correspond to a real state this system has (`taint.trust` is `low`/`med`/`high`; Smith's Phase 4 gate found and corrected an early implementation that invented a `trust=trusted` display value that never actually occurred). What actually ships: a clean project file becomes `validated_allow` — `sensitivity` escalates to `internal`, and `trust` is simply never contaminated by it (stays whatever it already was). The AC's real intent — project files aren't treated as scrutinized/untrusted resources — is satisfied; the literal wording predates the vocabulary this epic's own implementation clarified.
- [x] This default applies to the project folder specifically (however scoped — see open question below), not a blanket change to `scalene_policy.yaml`'s global `defaults:` block, which still governs everything outside it. Resolved: a single, ordinary `rules:` entry, not a `defaults:` change.
- [x] Coexists with STORY-1502's hardcoded restricted paths — a sensitive subpath inside the project folder (e.g. a `.ssh`-like directory someone actually committed) is not blanket-trusted just because it's under the project root. Verified via `tests/test_resource_verifier.py::TestProjectFolderDefault::test_coexists_with_hardcoded_restricted_paths_under_the_project_root`.

**Mechanism note (corrected mid-sprint, direct user request, 2026-07-21):** originally implemented as an implicit `PolicyRule` constructed in memory by `PolicyConfig.__post_init__`, surfaced via a synthetic `scg onboard --list` line — already fully gated and approved. The user then asked for a simpler design explicitly to avoid an implicit special case: `policy_config.write_default_project_policy()` now writes one real, ordinary rule to a real `scalene_policy.yaml` the first time a project has none, with no `ScanCache` entry pre-seeded ("timestamp uninitialized," the user's own phrase — first tool-use still triggers a genuine scan). Found and fixed a real bug while implementing this version: the rule's broad pattern, written first, would otherwise permanently shadow any more specific rule a developer onboards later (append-only + first-match-wins) — `onboard.py::_write_rule()` now inserts new rules ahead of this one specifically. Both the original and corrected mechanisms were fully gated (Smith Gate 1 hard requirement, satisfied differently by each); the corrected one shipped.

## Open Questions for Architecture (Morpheus) — E15 — all resolved during Sprint 9

1. **Resolved**: `scalene_policy.yaml` gains a `scanners: extra:` section (`name`/`import: "module.path:ClassName"`), `importlib`-loaded and validated against the `Scanner` protocol at load time.
2. **Resolved**: kept to exactly the two paths the user named (`/etc`, `~/.ssh`) — not expanded to a guessed broader list. A developer can add their own via `rules:` today.
3. **Resolved**: URLhaus (abuse.ch) — though its "no API key" premise turned out false in practice (Tank's finding); resolved with a real, free Auth-Key via `SCALENE_URLHAUS_AUTH_KEY`.
4. **Not resolved, deliberately carried** — still an open, separate backlog item (see Cypher's `next_steps.md`), not folded into E15.
5. **Resolved, and changed mid-sprint**: originally an implicit rule keyed off `PolicyConfig.project_root`; corrected per direct user request to a real `rules:` entry written to a real `scalene_policy.yaml` on first run (`policy_config.write_default_project_policy()`), wherever `--policy-path` resolves to. No `scg init` command needed or added — `scalene-guard`'s own hot path creates the file on first use.

---

# Sprint 10

## E16 — Interactive Onboarding Dashboard & Non-Blocking Review Loop

**Origin:** Direct user `*user consult` (2026-07-22), fully worked through with Smith before being storied — see `agents/smith.docs/e16_onboarding_tui_consult.md` for the full exchange. The user wants onboarding to be "super easy" while allow-list decisions stay "plainly obvious," via an elaborate extension of the existing `scg monitor` TUI (E7/E10 Phase 5: `monitor_app.py`, `monitor_data.py`) run in a separate shell/process from the agent session. Two design questions Smith raised were resolved in the same consult, not left open here: (1) the hook stays fully synchronous — a block returns immediately with retry guidance in its existing `reason` field, instead of the hook process pausing to await a decision (this is why there is no STORY here changing `pre_tool_use`'s timing/contract); (2) "dirty" means validation-expired, which already exists as `ScanCache.is_fresh()` — no new cache concept needed, only a display gap to close.

Deliberately NOT storied this epic, per the consult: enforcement inside third-party agent harnesses Scalene doesn't control (STORY-1606 covers only what Scalene's own setup can enforce); any change to `pre_tool_use`'s hook contract itself (none is needed).

### STORY-1601
As an agent operator, when a tool call is blocked, I want the block reason to tell me whether to wait-and-retry or not-retry-without-a-rule-change, so an agent doesn't spin-retry a call that was explicitly denied, and does know to retry once review completes.

**Acceptance Criteria**
- [x] A block on the `uncleared` path (`resource_verifier.py`'s `decide_access`: no matching rule yet, nothing confirmed wrong) produces a `reason` ending in explicit wait/retry guidance (e.g. "wait for review, then retry"). `AccessDecision.block_kind="uncleared"`, verified via `tests/test_resource_verifier.py::test_contaminated_context_unmatched_resource_is_uncleared_with_retry_guidance`.
- [x] A block on the `confirmed_bad` path (a real scanner finding, or a rule explicitly setting a non-allow mode) produces a `reason` explicitly stating not to retry without a rule/config change. `block_kind="confirmed_bad"`, verified via `test_scanner_confirmed_bad_is_block_kind_confirmed_bad_with_no_retry_guidance`.
- [x] No change to `pre_tool_use`'s contract, timing, or exit-code semantics — still fully synchronous, still resolved in one hook invocation, same as today. Confirmed by Phase 1's Morpheus review and the unchanged `SCALENE_BYPASS` short-circuit path.
- [x] Verified for real: an agent reading only the `reason` text (not source code) can tell the two cases apart. Both test cases above assert on the literal `reason` string, not internal state.

### STORY-1602
As a developer watching `scg monitor`, I want to see each configured scanner and whether it currently has a resource pending verification, so I know a review is expected to resolve rather than wondering if anything is happening.

**Acceptance Criteria**
- [x] A new panel/row exists per configured scanner (from `PolicyConfig.scanners`, so it reflects config-driven registration from E15/STORY-1501, not a hardcoded list). Verified against a real config-declared scanner (E15's `DummyScanner` fixture), no monitor code change needed.
- [x] Each row shows at least: scanner name, and idle/busy — busy meaning at least one real `ScanCache.pending_since` reservation for that scanner, not a simulated indicator. Trin independently verified the full reserve→complete lifecycle (busy on `try_reserve`, idle again after `put()`), not just the trigger direction.
- [x] Updates on the existing 0.5s poll cycle (`POLL_INTERVAL_SECONDS`) — no new polling mechanism introduced. `refresh_scanner_activity()` is called from the same `poll_data()` as every other panel.

### STORY-1603
As a developer watching `scg monitor`, I want a log of every tool call (not just blocked ones), showing which rule/tag matched (if any) using both a color and a text/symbol marker, so I can scan for sensitive-call activity even without color (SSH sessions, monochrome terminals, colorblind users).

**Acceptance Criteria**
- [x] The log shows every tool call the hook evaluates, allowed or blocked — not only blocks (today's `#events` panel is block-only; this story generalizes it to the full stream, per direct user correction 2026-07-22 of an earlier, incorrectly-scoped-down draft — see `docs/ARCHITECTURE.md` §20.3). `pre_tool_use` writes an `"allow"` audit entry too now.
- [x] Every log row shows a short text tag identifying its sensitivity/mode/outcome — not color alone. `[ALLOW]`/`[WAIT]`/`[DENY]`/`[BLOCK]` (old-format fallback).
- [x] Color is layered on top of the text tag as a secondary cue, never the only signal. Trin independently verified 3 distinct real Rich styles via direct `.style` inspection.
- [x] Verified for real in a color-stripped render (no ANSI color codes) that every row's information is still fully legible. Smith drove the real `MonitorApp` herself (real `export_screenshot()`), confirmed all 3 tags present in the color-stripped `<text>`-node extraction with 11 distinct fill colors existing separately in the same SVG.
- [x] A real, measured benchmark confirms logging every call (not just blocks) doesn't regress the existing `<15ms` hot-path NFR (`docs/ARCHITECTURE.md` §13.3) — the added cost is a single buffered file append, not a scan/subprocess spawn, but this project measures rather than assumes the size of a hot-path change. `tests/test_performance.py::TestPreToolUseEveryCallAuditLogPerformance`.

### STORY-1604
As a developer, when a call is blocked and I have `scg monitor` open, I want a dashboard showing the tool being called, which scanner(s)/rule(s) matched, and each identified target's onboarded/validated status and freshness, so I have everything needed to decide without leaving the TUI.

**Acceptance Criteria**
- [x] A new block event (via the existing `AuditTail`/AuditLog mechanism) surfaces a dashboard view for that event: tool name, the real tool-call JSON, matched scanner(s), identified target(s). `MonitorApp._pending_reviews` + `ReviewScreen`, populated via `build_review_entry()`/`onboard.identify_targets()`.
- [x] Each listed target shows its onboarded/validated status and a fresh/expired indicator — real `ScanCache.is_fresh()`, not simulated. `monitor_data.target_status()` — the `Resource`-reconstruction Smith flagged is a natural side effect of reusing `identify_targets()`, not a separate helper.
- [x] Three actions are available: **Verify**, **Allow**, **Deny**. Default selection is **Deny**. Deny is pre-selected/always-valid; Allow requires Verify first (below).
- [x] **Allow is disabled/unreachable until Verify has completed** for every listed target. Textual's real `disabled=True` state, confirmed by Trin, not just a visual hint.
- [x] Verify triggers a real scan via the existing scan machinery, confirmed via `ScanCache` gaining a real entry (not simulated). **Reconciled 2026-07-23 (Oracle)**: "visible in-progress indicator per target" as literally worded would mean a per-row spinner inside the dashboard table; what shipped instead reuses STORY-1602's Scanners panel (busy/idle) as the in-progress signal during Verify — `action_verify()` wraps each scan in `try_reserve()`/`put()`, the same real reservation state the Scanners panel already reads. Satisfies the AC's real intent (the operator can see a scan is in flight) via the existing signal rather than a second, duplicate one, matching the architecture's own "reuses STORY-1602's activity signal" framing — not a silently-skipped requirement.

### STORY-1605
As a developer allowing a blocked call from the dashboard, I want a form showing the real tool-call JSON with the match-expression fields (tool, pattern, sensitivity, mode) pre-filled with tight, narrow defaults derived from the actual call, so I don't have to hand-author a `PolicyRule` from scratch.

**Acceptance Criteria**
- [x] Choosing Allow (post-Verify) opens a form populated from the real blocked `tool_input` for that event, not a blank form. Sensitivity/mode inputs pre-filled `public`/`allow`; the underlying `tool_input` JSON is shown above the form.
- [x] The default `pattern` is derived as narrowly as E13/sec16's existing `scg onboard` flow already produces for the same target — not a wildcard, and not a new/separate default-derivation mechanism. `re.escape(resource.identity)`, reused verbatim from `onboard.py`.
- [x] Submitting writes a real `PolicyRule` via the existing rule-authoring path (`onboard.py`'s writer) to the real on-disk policy file — no separate/parallel write mechanism. `onboard.write_rule` (renamed public from `_write_rule`, a second real caller now exists).
- [x] Verified end-to-end: after submitting, retrying the exact same original call (per STORY-1601's retry guidance) is now allowed. `tests/test_monitor_app.py::test_allow_writes_a_real_rule_and_a_retry_of_the_same_call_is_then_allowed` — real Textual `Pilot` clicks, real `pre_tool_use` calls before/after, real `PolicyConfig.from_yaml` reload, nothing mocked. Smith's mandatory Phase 5 gate verified this directly.

### STORY-1606 — shipped scope reduced 2026-07-23; hash-snapshot detection backlogged
As an operator, I want Scalene to detect and revert any change to `scalene_policy.yaml` that didn't happen through its own legitimate write path, and record that it happened, so an agent that edits the policy file directly can't grant itself a rule it wasn't given.

**Mechanism note (corrected 2026-07-23, direct user request, before Tank's originally-planned OS/mount verification task started)**: the original AC (read-only mount of the policy file inside the agent's own execution environment, verified by Tank across local/Docker/cloud targets) is shelved — Tank's own live-verification standard doesn't extend to infrastructure this project doesn't control or deploy, and as the user put it, an unenforced convention doesn't stop an agent from just editing whatever wrote the hook registration in the first place. Replacement design (hash-snapshot detect-and-restore, fully inside Scalene's own application code, no external infra dependency) recorded in `docs/ARCHITECTURE.md` §20.6 — **backlogged, not built this sprint**, per direct user decision, not silently dropped.

**Shipped this sprint** (the still-true parts of the original write-up): `onboard.write_rule`'s existing `OSError`/`PermissionError` handling degrades cleanly against a real read-only policy file (Trin's tests, Phase 6.1), and `docs/USER_GUIDE.md` documents the read-only-mount deployment recommendation for operators who control their own deployment target (Phase 6.2). Both are real defense-in-depth, just not this story's full original AC.

**Acceptance Criteria (backlogged — not this sprint)**
- [ ] A policy file edited outside `write_rule`/`write_default_project_policy` is detected on the next load (hash mismatch against `.scalene/policy_snapshot.json`).
- [ ] On detection: the on-disk file is restored to the last legitimately-written content, and the current call's access decision uses the trusted content even if the disk restore itself fails (e.g. a genuinely read-only mount).
- [ ] A `policy_tamper` event is appended to `.scalene/audit.log` with enough detail to identify when it happened.
- [ ] `scg monitor` surfaces a tamper event via the same attention signal as a queued review (bell + title) — operator-visible, not agent-visible.
- [ ] A brand-new project (no snapshot yet, a real pre-existing policy file) bootstraps trusting current content as the baseline, not a false-positive tamper alarm on first load.
- [ ] Explicitly out of scope, unchanged from the original AC: enforcing anything inside third-party agent harnesses Scalene doesn't control (an agent could still find and edit the hook registration itself, outside Scalene's own file-integrity boundary — this story protects the policy file specifically, not the whole trust chain).

## Open Questions for Architecture (Morpheus) — E16

1. **STORY-1606's concrete mechanism** — read-only bind mount? OS file permissions (chmod)? A separate writable staging file the TUI reconciles into the real policy file? The AC states the goal, not the design.
2. **STORY-1604's dashboard state** — is a review keyed off the audit-log block event alone (stateless, TUI-side only, matching this project's "poll real files, don't invent a parallel store" precedent — sec15's `BlockEvent` docstring), or does it need new on-disk state so a second monitor instance or a restart mid-review doesn't lose track? Recommend stateless first; confirm or override.
3. **STORY-1602's "busy" definition** — a simple boolean (≥1 `pending_since` reservation for that scanner) is recommended over any duration/progress tracking, unless Morpheus finds a concrete need.
4. **STORY-1605's default-pattern reuse** — confirm reusing E13/sec16's existing onboard default-derivation mechanism exactly, rather than the form needing its own (e.g. broader-by-one-directory-level) default logic.
5. Whether STORY-1602 and STORY-1604's freshness/activity displays share one `Resource`-reconstruction helper in `monitor_data.py`, or need separate ones — an implementation-shape call, not a product one.

---
