# Product Requirements Document — Project Scalene

**Owner:** Cypher (PM)
**Source:** `Scalene BRD.md`
**Status:** Draft v1 — pending Smith (UX) gate

## Vision

Project Scalene prevents AI coding agents from exfiltrating sensitive data to untrusted tool destinations, without breaking developer flow. It does this via deterministic, provenance-based taint tracking and structural payload masking — not content inspection — so it stays fast (<15ms) and doesn't need to understand what the data *means*, only where it came from and where it's going.

## Target User

AI-enabled software engineer / DevOps engineer who runs autonomous coding agents (Claude Code, Cursor, etc.) against real codebases and wants guardrails that don't force manual restarts or break agent context loops.

## Goals

1. Track data provenance (sensitive / untrusted) per agent session, not per payload content.
2. Intercept every tool call pre- and post-execution and enforce policy via JSONPath rule matching against project YAML config.
3. When a tainted-sensitive context targets an untrusted destination, mask the payload rather than blocking the call outright.
4. Let developers safely onboard new allow/trust rules through a guarded, auto-verified workflow.
5. Fail safe: any ambiguity (malformed JSONPath, missing rule) defaults to sensitive=true / trusted=false.

## Non-Goals (Out of Scope)

- Semantic/NLP analysis of LLM output content.
- OS/kernel-level enforcement (eBPF, Landlock).
- Remediation of historical logs or past breaches.
- IAM / role provisioning.

## Success Metrics

- Pre-tool-call rule evaluation completes in <15ms (NFR).
- Zero unhandled exceptions from malformed agent arguments (fail-safe path always triggers instead).
- Onboarding a new trust/allow rule requires no manual YAML hand-editing outside the guarded flow.

## Epics

| ID | Epic | Summary |
|----|------|---------|
| E1 | Taint State Machine | Session-scoped `has_sensitive_data` / `has_untrusted_data` sticky flags |
| E2 | Policy Config Engine | `scalene_policy.yaml` schema + JSONPath rule matching |
| E3 | Tool Call Hooks | `pre_tool_call` / `post_tool_call` interception |
| E4 | Structural Masking | Blind payload substitution at the Triangle-of-Doom boundary |
| E5 | Onboarding Workflow | Developer-guided allow/trust rule additions with pre-write scans |
| E6 | Fail-Safe & Isolation | Error handling, scanner-loop prevention, sandboxed scanning |

See `docs/USER_STORIES.md` for the full story breakdown and acceptance criteria.
