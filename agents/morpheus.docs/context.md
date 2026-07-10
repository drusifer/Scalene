# Agent Local Context: Morpheus

## Recent Decisions
- **Two-layer architecture**: Hook Adapter (Claude Code-specific) + Policy Engine (harness-agnostic). Reason: BRD calls for cross-platform portability and the BRD's own YAML example uses generic tool names (`view_file`, `read_file`) rather than Claude-Code-specific ones — treating harness coupling as an adapter concern keeps a future Cursor/other-harness port from being a rewrite.
- **No daemon** — state externalized to per-session JSON files (`.scalene/state/<session_id>.json`), loaded/saved per hook subprocess invocation. Reason: NFR-Portability (must run in Docker/cloud dev envs without assuming a long-lived process is allowed) and simplicity — avoids crash-recovery/IPC design entirely.
- **Threat-intel for trust-list onboarding (STORY-501): rejected external paid API for v1.** Shipping a `LocalHeuristicChecker` (domain heuristics, no network call) behind a `ReputationChecker` interface instead. This directly resolves the Tank-flag concern Cypher raised (no new external dependency/egress in v1) — pluggable interface means a real API can be added later without touching callers.
- **Python 3.11+ / pip-installable CLI** as the stack. Reason: matches existing tooling conventions already in this repo (`via` is pip-installed).
- **Approved Mouse's task.md as-is**, with one addendum: folded a `.gitignore`/CI-artifact check for `.scalene/` into task 4.1 rather than spinning up a full Tank phase for it — Mouse's no-Tank-phase call was right (no deploy/CI/infra work this sprint), this is just a one-line hygiene check, not worth a phase.

## Key Findings (2026-07-09, `*lead review copyable system messages`)
- `_suggest_onboard_command()` (`hook_adapter.py`) is harness-agnostic (takes primitives, never touches Claude Code's hook JSON shape) but lives in the adapter layer, which §2's "adapter isolation" principle reserves for harness-specific translation. Not blocking — private helper, cheap to relocate — but flagged so it isn't forgotten if/when a second harness adapter is actually built: move it to the policy-engine layer (`masking.py` or a new small module) at that point so both adapters can share it instead of duplicating.
- This is the first concrete instance of the §10 technical-debt watch item ("the adapter/policy-engine seam is the one most likely to be tested by a second-harness port") actually surfacing — worth remembering as a precedent, not just a one-off.


- The BRD's hook naming (`pre_tool_call_hook`, `post_tool_call_hook`) maps directly onto Claude Code's actual `PreToolUse`/`PostToolUse` hook mechanism — the same one active in this very session. Chose to target it explicitly rather than inventing a generic hook protocol nobody would consume yet.
- Addressed both of Smith's Gate 1 notes architecturally rather than leaving them purely as story AC: masking events get an audit log entry AND a `systemMessage` surfaced into the transcript (visibility); onboarding CLI prints a confirmation + diff (STORY-501 success feedback).
- task.md's phase sequencing matches the architecture's dependency graph correctly: Foundations (config+state) before both Hook Adapter (needs both) and Onboarding (needs config only) — Onboarding could theoretically run parallel to Phase 2 but Mouse kept it sequential for a single-implementer sprint, which is the right call here.

## Important Notes
- Sprint plan is now **locked**. `docs/PRD.md`, `docs/USER_STORIES.md`, `docs/ARCHITECTURE.md`, and `task.md` are all in place. The `*plan sprint` Bloop chain (Cypher → Smith Gate1 → Morpheus → Smith Gate2 → Mouse → Morpheus review) is complete.
- Next actual work is `*impl phase-1` (Neo) whenever the user is ready — not part of this planning chain.

---
*Last updated: 2026-07-02*
