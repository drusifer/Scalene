# Agent Local Context: Smith

## Recent Decisions
- Gate 1 review of `docs/USER_STORIES.md`: **Approved with notes** (masking visibility, onboarding confirmation gaps).
- Gate 2 review of `docs/ARCHITECTURE.md`: **Approved**, no notes. Both Gate 1 gaps were addressed at the architecture level (audit log + `systemMessage` for masks; confirm+diff for onboarding) rather than punted — treating that as resolution even though the story AC text itself hasn't been edited yet (tracked as a Cypher follow-up, non-blocking).
- `*qa judge session` (2026-07-09): scored today's full-session tool/skill usage trace at TES 98/100. Filed 3 findings (S1-001 double `Skill(make)` call, S1-002 `git stash -u` care lapse, S1-003 my own planned post-Phase-2 UX gate never ran). None are code bugs — all routed to Bob for prompt/process guidance.

## Key Findings
- STORY-501's offline-developer open question (from Cypher's original open-questions list) is also resolved as a side effect of Morpheus's `LocalHeuristicChecker` decision — v1 onboarding does zero network calls, so it always works offline. Good UX outcome that wasn't explicitly the goal (Morpheus was solving a Tank/infra concern) — worth noting so it doesn't get lost.
- No new UX-impacting concerns from the architecture itself: no daemon means no "is the service running?" status question for the developer; fail-safe defaults are consistent with what was reviewed at Gate 1; sentinel masking string behavior is unchanged from Gate 1 (already accepted).
- **Important process finding (S1-003):** the `/bloop *impl <phase>` chain (`agents/skills/bloop/SKILL.md`) is `Neo → Trin → Morpheus → [Tank if deploy] → [context check]` — it has no Smith step, ever. Any future sprint plan that writes "Smith re-engages post-Phase-N" (as this one did, in `task.md`) will silently not happen unless the chain itself is changed or someone manually invokes `*chat @smith` mid-sprint. This is a standing gap, not a one-off mistake.

## Important Notes
- Both sprint planning gates (Gate 1, Gate 2) are clear; Sprint 1 fully implemented and closed (2026-07-09) — but see S1-003: the planned post-Phase-2 UX test against real hook behavior never happened. Recommend a retroactive lightweight `*user test` pass against the real `scalene-guard` binary before Sprint 2 starts.

## `*user consult` — onboarding UX for allowlisting tool calls (2026-07-09)

**Question posed by user (broadcast, no assigned persona):** how does a developer know what JSONPath/pattern to write to allowlist a tool call, having never seen an example of that tool's actual call shape? What's a user-friendly onboarding flow?

**Ran the software to confirm the gap (heuristic #6, recognition over recall):** `scalene onboard` (`src/scalene/onboard.py`) requires `--tool`, `--jsonpath`, `--pattern`, `--target` all supplied up front, with zero discovery mechanism — the developer must already know Claude Code's internal tool-call JSON schema (field names per tool) and hand-write both a JSONPath expression and a regex, with no example to copy from. This is a real defect against Nielsen #6 and #10 (recognition rather than recall; help and documentation) — today's flow assumes expert prior knowledge of an undocumented internal schema.

**Key existing asset that's currently wasted:** `pre_tool_use` (`hook_adapter.py`) already has the full real `tool_input` in hand at the exact moment it decides to mask — that's the ideal onboarding example, generated for free, and today it's thrown away (audit log only stores `tool_name` + `payload_field`, not the field shape).

**Options surfaced (ranked, presented to user):**
1. **Actionable mask `systemMessage`** (lowest effort, highest leverage): extend the existing mask `systemMessage`/audit entry to include a ready-to-run `scalene onboard` command, pre-filled with the real tool name, a JSONPath into the field that actually matched, and a literal-escaped regex derived from the real value — the user only loosens the pattern if they want it broader. Turns every block into its own worked example.
2. **Persist last-blocked call for later onboarding** (`--from-last-block`): store the real pre-mask `tool_input` per session (e.g. `.scalene/pending/<session_id>.json`, capped) so the suggested command survives past transcript scrollback.
3. **Static `docs/RECIPES.md`**: table of common built-in tool → jsonpath → pattern examples (Read/Write/Edit/Bash/WebFetch), for users who want to write a rule pre-emptively before ever hitting a block. Complement, not replacement — doesn't reflect the user's actual project.
4. (Discussed, not detailed) an interactive/wizard onboarding mode.

**Recommendation given:** (1) first — free, uses data already computed, closes the "never seen an example" gap directly by making the blocking event the example. (2) as a durable follow-up. (3) as cheap complementary docs.

**Status:** Discussion only, not yet a story/task. No code changed. Not blocking anything.

---
*Last updated: 2026-07-09*
