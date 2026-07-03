# User Stories — Project Scalene

**Owner:** Cypher (PM)
**Status:** Draft v1 — pending Smith (UX) gate 1

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

## Open Questions for Architecture (Morpheus)

1. What runtime/language implements the hook layer — is this a Claude Code / Cursor plugin, a language-agnostic sidecar process, or both?
2. Where does taint state live for the session — in-memory per process, or persisted to disk for crash recovery mid-session?
3. What's the actual mechanism for `pre_tool_call`/`post_tool_call` hook registration — does this target a specific agent harness's hook API, or is it meant to be harness-agnostic?
4. What threat-intel/reputation service does trust-list onboarding call (STORY-501)? Is this a paid third-party API, and what happens if the developer runs offline?
