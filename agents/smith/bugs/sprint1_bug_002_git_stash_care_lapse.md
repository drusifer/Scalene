# Bug S1-002: `git stash -u` run mid-investigation without a blast-radius check

**Severity**: P1 — Near-miss data-loss incident (no data actually lost, but the working tree held a full day's uncommitted work at the time)
**Filed by**: Smith
**Route to**: Bob (prompt/skill guidance, not a code bug) + user-facing disclosure (already done in-session)

---

## Reproduction

Mid-session, while investigating whether gitleaks would flag the repo's own committed content, the agent ran:

```bash
git add -A -n 2>&1 | head -3
git stash -u 2>&1 | tail -3 || true
```

At that point the working tree held the entire Sprint 1 implementation (4 phases, ~74 files) plus a full documentation-grooming pass — none of it committed yet.

## Expected

Per the system's own "Executing actions with care" guidance: run `git status` before any command that could discard uncommitted work, and weigh reversibility/blast-radius before acting — especially for a repo-wide, no-argument `git stash -u`.

## Actual

`git stash -u` ran immediately, with no preceding `git status` check and no pause to consider that it would stash the entire day's work, not just the file(s) relevant to the gitleaks question being investigated.

## Root Cause

The action was taken as a quick way to get a "clean baseline" to test against, without first asking "what is currently at risk in the working tree if this command runs." No malicious or careless intent — just a missed blast-radius check for an action that is explicitly called out as needing one.

## Impact

None realized — the agent noticed immediately, ran `git stash pop`, and confirmed via `git status` + `make test` (77/77) that everything was restored intact. Disclosed to the user proactively in the same turn. But had the agent not caught it (e.g., context had ended, or a crash occurred between the stash and the pop), a full day's uncommitted implementation work would have been sitting in an unnamed stash entry, easy to lose track of.

## Recommended Fix

Bob to reinforce, in whatever persistent guidance applies across sessions (not just this repo's skills — this is a general safety lesson): before any `git stash`/`git reset --hard`/`git checkout --`/similar working-tree-discarding command, run `git status` first and explicitly weigh what's at risk, even when the command feels like a "quick, temporary" check. A memory entry is more durable here than a project-local skill edit, since this class of mistake isn't specific to Project Scalene.
