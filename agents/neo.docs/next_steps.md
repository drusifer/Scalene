# Next Steps

## Immediate Next Action
Nothing in-flight. `*fix` closed (2026-08-07, Neo→Trin→Morpheus, approved): `FileScanner.identify()` now `expanduser()`+`expandvars()` before `abspath()` (`_normalize_path()`), and the generic-fallback regex was broadened to catch `~`/`$VAR`-shaped tokens, paired with a new `os.path.exists()` validation on those specific candidates only (not known-field/`file://` paths — `Write`'s new-file target must stay unaffected). Root cause: `~/.ssh/id_rsa`/`$HOME/.env` embedded in a Bash command either weren't regex-matched at all (old fallback required a literal `/`/`./`/`../` prefix) or normalized to the wrong absolute path (`<cwd>/~/.ssh/id_rsa`) — silently missing `docs/ARCHITECTURE.md` sec18.2's hardcoded-restricted-path check. `docs/ARCHITECTURE.md` sec18.2 has a correction note. 8 new tests (`tests/test_scanner.py::TestFileScannerIdentifyPathExpansion`), full suite 561/561, perf budgets re-verified unaffected.

Ad-hoc diagnostic (2026-08-07): user asked why `scg monitor` showed "11K pending reviews" for `../tetris`. Root cause: not a code bug — the running `scg monitor` process's cwd was `/home/drusifer/Projects/Scalene` (this repo) instead of `../tetris`, so it was reading Scalene's own dogfooding `.scalene/audit.log` (11,847 unresolved `block` events, 0 `review_resolved` ever — this repo's own hook fires on every tool call across every persona session, and nobody's pointed the monitor at Scalene's own dir to work through it). tetris's real log has only 15 blocks/6 resolved. No fix needed in code; told the user to `cd` into the target project (or pass `--audit-log-path`/`--cache-path`/`--state-dir`/`--policy-path`) before running `scg monitor`. Flagging as a real UX gap worth a product decision: `scg monitor` gives no indication which project's data it's showing (no path in the title/header), so a cwd mistake like this is silent and easy to make.

E16 follow-up session (2026-07-30) closed and pushed (`origin/main` at `f167df6`). No formal sprint review/gate chain ran against this session's work (fast-tracked directly with the user throughout) — if a future session wants to retroactively run Trin UAT / Morpheus review / Smith gate against it, that's real, legitimate review debt, same shape as the §16 rework noted below once was.

## Waiting On
Nothing. No open questions blocking Neo.

## Carried, not blocking (from `docs/ARCHITECTURE.md` §21.10)
- `ScanCache` freshness for a directory resource keys off the directory's own mtime (doesn't catch a nested file's *contents* changing deeper in the tree) — only matters if directory-target Allow rules become common.
- `Scanner.from_config()` has no `get_config()`/introspection counterpart — nothing concrete wants this yet.
- `PolicyRule.trust` has no CLI (`scg onboard --trust`) or TUI (Allow form) exposure yet — hand-authored in `scalene_policy.yaml` only.
- The pending-review auto-resolution (§21.9) only runs right after a review is explicitly resolved, not on every `poll_data()` tick — a hand-edited policy file won't retroactively clear now-covered reviews until the next resolution happens.
- `docs/ARCHITECTURE.md` §5's Onboarding sequence diagram is still stale (pre-existing, not touched this session either).
- `cache_refresh_worker.py` stays scoped to builtin scanners only (pre-existing, documented gap) — revisit only if a real config-declared scanner ever ships.

---
*Last updated: 2026-07-30*

## Immediate Next Action (prior, 2026-07-21)
Sprint 9 (E15) Phase 4 complete (last phase), handed to Trin for UAT. On re-invocation:
- If Trin/Smith find issues → fix within Phase 4's scope only.
- If they pass → nothing further for Neo this sprint. Sprint moves to close (Oracle groom → Smith end-to-end test → all-persona retro → Cypher launch) — not Neo's steps.

## Sprint 9 (E15) phase tracking — all 4 phases implemented
- [x] Phase 1 — Configurable Scanner Registry. `make test`: 349/349 (+CLI tests → 352).
- [x] Phase 2 — Hardcoded Restricted Paths. `make test`: 360/360.
- [x] Phase 3 — External Reputation Source. `make test`: 371→374/374 (Tank found+we fixed a real Auth-Key gap).
- [x] Phase 4 — Project-Folder Default. `make test`: 381/381. Smith's mandatory gate + final reviews pending.
