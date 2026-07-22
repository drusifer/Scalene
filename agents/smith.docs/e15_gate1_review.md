# Smith — `*user review` Gate 1 — E15 (2026-07-21)

Reviewed STORY-1501 through 1504 (`docs/USER_STORIES.md`) against Nielsen's heuristics. Checked `agents/oracle.docs/lessons.md` first — the 2026-07-20 sec16 lesson ("a well-reasoned validation message can be unreachable from the real CLI") and the general project pattern (E11/sec15, E13/sec16, E14's own CLI UX pass) both converge on the same risk: this project has been burned repeatedly by *correct* behavior that's silent or undiscoverable to the actual user. That lens is what shapes the notes below.

## STORY-1501 — Configurable scanner registry
No end-user-facing surface described yet (config schema is an open question for Morpheus). Nothing to gate on from a UX standpoint at the story level. **One forward-looking note**: whatever config schema Morpheus picks should follow `scalene_policy.yaml`'s existing `rules:` vocabulary/conventions rather than inventing a second config idiom — flagging now so it's on Morpheus's plate at Gate 2, not discovered as an inconsistency later.

## STORY-1502 — Hardcoded restricted paths (`/etc`, `~/.ssh`)
Testable, correctly scoped. **Non-blocking note**: the AC as written doesn't say what *reason string* the developer sees. This project's existing pattern (`FileScanner.scan()`'s `reason` field) already distinguishes "secrets found" from "clean" — a hardcoded path override needs its own distinct reason (e.g. "path is a hardcoded restricted system location," not the generic secrets-found message) so a developer debugging a restricted classification on a *clean* file isn't misled into thinking a secret was actually detected. Violates Nielsen #9 (help users diagnose) if conflated. Add as an explicit AC before Gate 2.

## STORY-1503 — Real external reputation source
Correctly scoped, and the degrade-on-unreachable AC is the right fail-open behavior. **Non-blocking note**: "degrades to local-heuristic-only result" must not look identical, to the developer, as a full external check having run and passed clean — otherwise a developer could reasonably believe a URL was checked against real threat-intel when it was only checked against the 3 local heuristics. Needs a visibility signal (Nielsen #1) distinguishing "checked externally: clean" from "external check unavailable, local heuristics only" — at minimum in the `reason`/audit trail, not necessarily the terminal happy path. Add as an explicit AC before Gate 2.

## STORY-1504 — Project folder defaults trusted + Internal Only
This is the one I'm giving the most scrutiny, for the same reason Cypher flagged it: it's a deliberate exception to this project's established fail-safe-by-default posture. Cypher's AC already handles the *scope* concern well (project-root-only, still overridable by STORY-1502). What's missing is **discoverability of the exception itself**.

This project has a real, repeated history of shipping a correct-but-silent behavior change and paying for it at a later gate (sec16's `--help` gap, found post-hoc at real-CLI-use; the 2026-07-20 lesson above, same shape). A developer whose project folder gets silently classified trusted+internal — differently from every other resource Scalene touches — has no way to discover that fact except by reading source or `scalene_policy.yaml` directly. If that default is ever wrong for a given project (e.g. a monorepo where the "project folder" isn't actually low-risk), the developer has no signal that a special-case default is even in effect.

**Hard requirement, carried to Gate 2** (same weight as my §14.3/sec16 precedent): STORY-1504 needs an explicit AC that this default is visible to the developer — e.g. surfaced at `scg init`/first onboarding of a project, or queryable via `scg onboard --list`/an equivalent — not just a silent runtime behavior. I will not approve a Gate 2 architecture where this classification is undiscoverable outside of reading config/source.

## Verdict

**Approved with notes.** Nothing here blocks Gate 1 — all 4 stories are testable, user-facing (or correctly scoped as non-user-facing for 1501), and don't overreach into architecture Morpheus should own. 3 non-blocking notes (1502's reason-string distinction, 1503's degraded-state visibility, 1501's config-schema consistency) plus 1 hard requirement (1504's default-visibility AC) carried to Gate 2 with the same weight as prior hard requirements in this project's history.
