# Current Task

**Status:** `*ora groom docs` complete
**Assigned to:** Oracle
**Started:** 2026-07-09
**Completed:** 2026-07-09

## Task Description
`*ora groom docs` — audit and organize the documentation tree, fix broken links, ensure no orphan files in root, update README.md ToC.

## Progress
- [x] Surveyed root, `docs/`, and `agents/` for misplaced/orphan files
- [x] Moved `Scalene BRD.md` → `docs/BRD.md` (`git mv`, preserves history)
- [x] Updated live references to the moved file (`docs/PRD.md`, `agents/cypher.docs/current_task.md`)
- [x] Rewrote root `README.md` with a doc table + quickstart + Bob Protocol pointer
- [x] Fixed 5 broken links in `agents/DOCUMENTATION_INDEX.md` (4 nonexistent framework docs, 1 nonexistent archive file)
- [x] Added a "Project Documentation (Scalene)" section to `agents/DOCUMENTATION_INDEX.md`
- [x] Verified every touched/added link resolves (file-existence check, not assumed)
- [x] Ran `make test` post-move — 77/77 still passing

## Blockers
None

## Oracle Consultations
None yet

---
*Last updated: 2026-07-09*
