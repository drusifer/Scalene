# State Save — 2026-07-22, before context clear

## Sprint 9 (E15) — fully closed
Full formal cycle: Cypher → Smith Gate 1 → Morpheus arch (§18) → Smith Gate 2 → Mouse phasing → Morpheus plan review → 4-phase Bloop → Oracle groom → Smith sprint-close e2e → all-persona retro → Cypher launch.

**Shipped:**
1. **STORY-1501** — `SCANNERS` is config-driven (`scalene_policy.yaml`'s `scanners: extra:` section, `importlib`-loaded, validated against the `Scanner` protocol).
2. **STORY-1502** — `FileScanner` hardcodes `/etc` and `~/.ssh` as always-restricted, independent of scan outcome.
3. **STORY-1503** — `URLScanner` adds a real external reputation source (URLhaus, abuse.ch). **Real Tank finding**: the endpoint's "no API key needed" premise was false in practice (verified live) — fixed with a real, free `SCALENE_URLHAUS_AUTH_KEY` env var (`.env.example`), never hardcoded.
4. **STORY-1504** — a brand-new project's own folder gets a real `rules:` entry (`mode: allow`, `sensitivity: internal`) auto-written to a real `scalene_policy.yaml` on first use. **Reworked mid-sprint** per direct user request, after the original implicit-in-memory-rule design was already fully gated — the user wanted no special case. Found+fixed a real bug during the rework: the broad default, written first, would otherwise silently shadow a later, more specific onboarded rule (`onboard.py::_write_rule()` now inserts new rules ahead of the auto-created default).

**Post-close correction (2026-07-22, direct user session, not part of the formal sprint):** `URLScanner` now recognizes any URL protocol (not just `http(s)`); `file://` is the one exception, routed to `FileScanner` instead. Found and fixed a real regex bug along the way (a `(?!file://)` lookahead only blocks a match at its exact starting position; `finditer` retried one character later and matched `"ile://..."`). Also dropped STORY-1504's now-redundant `scanner: secrets` filter — the anchored path pattern was already sufficient; general principle stated by the user: a rule author shouldn't need to remember scanner registry names by default. Recorded in `docs/ARCHITECTURE.md` §19.

**Tests:** 396/396, `make test` passing clean.

**2 durable lessons recorded** in `agents/oracle.docs/lessons.md`: (1) architecture claims about *existing* code need the same verify-before-build standard as claims about new code; (2) a broad auto-created default written first can silently shadow a more specific rule written later, under an unrelated append-only convention — a new-feature-interacts-with-old-mechanism bug shape.

**Standing feedback memory reinforced a 3rd time** (`feedback_no_adhoc_bash_verification.md`): ad-hoc bash verification recurred twice more this session (Phase 4 gate cycle) despite 2 prior corrections — escalated weight in the memory, plus a role-attribution point ("trin will do the automation" — e2e/verification tests belong to the persona whose job it actually is, not whoever's implementing).

## Repo state — everything below is uncommitted, not asked to commit
`git status` shows the full Sprint 9 diff uncommitted: `src/scalene/{cache_refresh_worker,cli,onboard,policy_config,reputation,resource_verifier,scan_worker,scanner}.py`, all `tests/*.py` touched this sprint plus 2 new fixture files (`tests/_env_guards.py`, `tests/fixtures_custom_scanner.py`), `docs/{ARCHITECTURE,PRD,USER_STORIES}.md`, `task.md`, `.env.example` (new), all `agents/*.docs/{context,current_task,next_steps}.md`, `agents/CHAT.md` (archived), plus ~25 new `agents/*.docs/e15_*.md` review/notes files. `.claude/settings.json` shows as deleted — **pre-existing from before this session started, not something this session did**, don't investigate it as new.

## No open handoffs
Every persona's state files (`context.md`/`current_task.md`/`next_steps.md`) are current as of sprint close + the post-close correction. Next sprint direction has not yet been given by the user — on resume, either wait for direction or check `agents/cypher.docs/next_steps.md` for the carried backlog (STORY-1405, STORY-1406, Smith's CLI UX findings, the still-stale §5 diagram, and 2 new Sprint-9-retro items).

## To resume cold
1. Read the bottom of `agents/CHAT.md` for the last real handoff.
2. Check `git status` — a lot of real, tested, working code is sitting uncommitted; confirm with the user before committing/pushing.
3. `make test` to reconfirm 396/396 before doing anything else.
