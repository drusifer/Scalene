# Product Requirements Document — Project Scalene

**Owner:** Cypher (PM)
**Source:** `docs/BRD.md`
**Status:** Sprint 1 (E1-E6) shipped 2026-07-09. Sprint 2 (E7-E8) shipped 2026-07-10. Sprint 3 (E9) — Draft v1, pending Smith (UX) gate 1.

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
| E7 | Live Taint & List Management Console | Realtime dashboard (TUI or web) over `.scalene/audit.log` + taint state, with one-click onboarding of suggested rules |
| E8 | Category-Aware Secrets Scan | Upgrade onboarding secrets scan from 3 hand-rolled regexes to `detect-secrets` |
| E9 | Documentation & Onboarding | `USER_GUIDE.md`, `GETTING_STARTED.md`, and a runnable demo of Scalene stopping a real exfiltration attempt |

E7-E8 are Sprint 2. E9 is Sprint 3. See `docs/USER_STORIES.md` for the full story breakdown and acceptance criteria.

## Sprint 2 Goals (added 2026-07-10)

6. Give developers a realtime, human-friendly view of taint status and mask events instead of raw log files — usability is the primary driver for Sprint 2 (user directive).
7. Let developers act on a suggested onboarding rule with one click/action instead of copy-pasting a terminal command.

## Sprint 3 Goals (added 2026-07-13)

8. Give a brand-new user a copy-pasteable path from clean clone to seeing Scalene actually mask a call, in under 5 minutes — no prior source-reading required.
9. Consolidate day-to-day CLI/config usage into one reference doc instead of requiring readers to piece it together from `SETUP.md` + `ARCHITECTURE.md` + source.
10. Give prospective users/reviewers a runnable, repeatable demo of the core value proposition (masking a real exfiltration attempt) that can't silently rot, rather than a one-off manual walkthrough.
