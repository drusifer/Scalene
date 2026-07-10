# Agent Local Context: Oracle

## Recent Decisions
- `*ora groom docs` (2026-07-10): found one new orphan created *after* the 07-09 pass — `url-malware-checking.md` at root, landed in the `8d77f9e` "copyable messages" commit alongside unrelated code changes (so the prior groom pass, done earlier the same day, never saw it). Zero references anywhere (grepped `.md`/`.py`/`CHAT.md` — none). `git mv`'d to `docs/URL_MALWARE_CHECKING.md` to match the project's `ALL_CAPS.md` docs-folder convention, and added it to `README.md`'s doc table. Skipped `make test` — pure doc move, no code/test referenced the old path (verified via grep before moving, not after).
- `*ora groom docs` (2026-07-09): moved the one orphan root file, `Scalene BRD.md` (space in filename, no docs/ home) → `docs/BRD.md` via `git mv` to preserve history. Updated the two live references to it (`docs/PRD.md`'s Source line, `agents/cypher.docs/current_task.md`) — deliberately left `agents/CHAT.md`'s reference untouched since it's an append-only historical log, not a live doc.
- Rewrote root `README.md`: was 2 lines with no links. Added a doc table (BRD/PRD/USER_STORIES/ARCHITECTURE/SETUP/STORY_TRACEABILITY/task.md), a `make setup && make test` quickstart, and a pointer to `agents/DOCUMENTATION_INDEX.md` for the Bob Protocol coordination layer.
- Fixed `agents/DOCUMENTATION_INDEX.md`: it referenced 4 files that don't exist in this project (`STARTUP.md`, `SHORTHAND_GUIDE.md`, `BOB_SYSTEM_PROTOCOL.md`, `START_HERE.md`) and one nonexistent archive file (`.archive_state_management_fix.md`) — these read like generic bob-protocol template boilerplate that was never actually created here. Removed the dead links rather than leaving them dangling. Also added a new "Project Documentation (Scalene)" section since the index previously only covered framework meta-docs, not the actual project docs in `docs/`.
- Verified every link I touched or added actually resolves (checked file existence for each relative path from its source file's directory) before finishing — did not assume paths were correct.

## Key Findings
- `agents/cypher.docs/current_task.md` is significantly stale (still says "Awaiting Smith gate 1 approval" as of 2026-07-02, but Sprint 1 fully closed 2026-07-09 per `agents/CHAT.md` and `task.md`). Did **not** rewrite Cypher's narrative/status content myself — that's outside Oracle's remit per the "don't overwrite persona content without permission" rule; only fixed the one mechanical broken-link reference inside it. Flagging here so Cypher's next activation (or the user) knows to reconcile it.
- `task.md` and the symlinked root files (`AGENTS.md`, `CHATGPT.md`, `GEMINI.md`, `.cursorrules` → `agents/AGENTS.md`) are intentional per bob-protocol convention, not orphans — left alone.

## Important Notes
- Grooming pass scope: root-level orphan files + broken links in `agents/DOCUMENTATION_INDEX.md` + `README.md` ToC. Did not touch `docs/ARCHITECTURE.md`/`PRD.md`/`USER_STORIES.md` content itself (those are Morpheus's/Cypher's owned documents, structurally fine, not orphaned).
- Ran `make test` after the file move (77/77 still passing) to confirm no code referenced the old `Scalene BRD.md` path.

---
*Last updated: 2026-07-09*
