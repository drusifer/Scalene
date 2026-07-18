# Product Requirements Document — Project Scalene

**Owner:** Cypher (PM)
**Source:** `docs/BRD.md`
**Status:** Sprint 1 (E1-E6) shipped 2026-07-09. Sprint 2 (E7-E8) shipped 2026-07-10. Sprint 3 (E9) implemented 2026-07-14 (retro/launch pending). Sprint 4 (E10) — Draft v1, pending Smith (UX) gate 1.

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

- Pre-tool-call rule evaluation completes in <15ms (NFR). **Sprint 4 exception (2026-07-14):** a resource's first sighting under E10's scan cache pays a separate, larger one-time budget — see Sprint 4 Goal 13 and `docs/ARCHITECTURE.md` §13.3's `NFR-Perf-FirstSighting`. Steady-state (cached) calls remain under the original <15ms.
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
| E10 | Extensible Scanner Registry & Resource Verification | Replace one-time onboard-verification with autonomous per-scanner resource identification + a 24h-cached, continuously-refreshed scan-result store |
| E11 | Trust/Sensitivity Model & Rule-Driven Resource Identity | Correct E10's host-level trust granularity defect; split trust (source legitimacy) and sensitivity (blast radius, 3 levels) into independent axes. **Superseded mid-sprint (2026-07-18, ARCHITECTURE.md §15):** originally planned unconditional content-scanning with per-rule `mode: mask\|block`; shipped as rule-driven access control instead (block/allow the call, not scan its content) after a real gap was found. |

E7-E8 are Sprint 2. E9 is Sprint 3. E10 is Sprint 4. E11 is Sprint 5. See `docs/USER_STORIES.md` for the full story breakdown and acceptance criteria.

## Sprint 2 Goals (added 2026-07-10)

6. Give developers a realtime, human-friendly view of taint status and mask events instead of raw log files — usability is the primary driver for Sprint 2 (user directive).
7. Let developers act on a suggested onboarding rule with one click/action instead of copy-pasting a terminal command.

## Sprint 3 Goals (added 2026-07-13)

8. Give a brand-new user a copy-pasteable path from clean clone to seeing Scalene actually mask a call, in under 5 minutes — no prior source-reading required.
9. Consolidate day-to-day CLI/config usage into one reference doc instead of requiring readers to piece it together from `SETUP.md` + `ARCHITECTURE.md` + source.
10. Give prospective users/reviewers a runnable, repeatable demo of the core value proposition (masking a real exfiltration attempt) that can't silently rot, rather than a one-off manual walkthrough.

## Sprint 4 Goals (added 2026-07-14)

11. Close a real verification gap: an onboarded allow/trust rule should not be able to vouch, forever and unrefreshed, for a broader class of future values than what was actually checked at onboarding time.
12. Make resource identification (file paths, URLs) automatic per scanner type instead of requiring a human to hand-author jsonpath+pattern extraction for every resource shape.
13. Keep continuous re-verification affordable via a per-resource, time-bounded cache with background refresh — not a scan on every call. **Revised 2026-07-14** (Morpheus's Phase 2 review measured the real cost of the background-refresh spawn): the existing <15ms NFR holds unchanged for the steady-state (cached/fresh) path, since that's pure JSON-cache reads with no subprocess spawn. It does **not** hold for a resource's first sighting — spawning the background scan costs real, measured latency (~6.6ms avg / ~16ms max in testing) that a from-scratch <15ms budget can't absorb on top of the existing hook cost. Accepted as a one-time, per-newly-seen-resource cost rather than redesigning the spawn mechanism — see `docs/ARCHITECTURE.md` §13.3's `NFR-Perf-FirstSighting`.

## Sprint 5 Goals (added 2026-07-17)

14. Close a real defect found in shipped E10 code: `URLScanner`'s host-level resource identity reproduces the exact "one verification vouches for an unbounded future set" problem E10 exists to fix. A resource's trust identity must be scoped narrowly enough to distinguish the specific verified resource from every other resource sharing its host.
15. Separate trust (could this source cause the agent to act maliciously) from sensitivity (blast radius if it does) as two independent axes, rather than treating them as parallel provenance signals. Sensitivity is exactly three levels: Public, Internal Only, Restricted.
16. Make real-secret content-scanning an unconditional baseline for every call, not conditioned on a session already being classified tainted-sensitive-and-untrusted — so scanning coverage doesn't silently depend on classification being correct. **Superseded 2026-07-18** — replaced by the goal below (blocking the call outright, not scanning its content) once a real gap was found mid-sprint. See `docs/ARCHITECTURE.md` §15.
17. Resolve the user's per-resource `mask`/`block` request as a `mode` field on the generalized `PolicyRule`, fired via the always-on default rule, rather than requiring trust itself to become "always scan." **Superseded 2026-07-18** — see goal 18.
18. **(Added 2026-07-18, replaces 16-17)** Gate whether a call is *permitted at all* on validated, explicit trust decisions, not on scanning its content. Two independent session tags (`trust`: low/med/high, `sensitivity`: public/internal/restricted) escalate as a session touches unrecognized resources; a call proceeds only if every resource it touches is validated + explicitly allow-ruled, or the session is still clean. Content-scanning (`masking.py`) is kept but dormant, not required by this goal — see `docs/ARCHITECTURE.md` §15.
