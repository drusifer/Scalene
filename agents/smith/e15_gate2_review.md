# Smith — `*user feedback` Gate 2 — E15 (2026-07-21)

Reviewed `docs/ARCHITECTURE.md` §18 against my Gate 1 hard requirement and 3 non-blocking notes, plus new UX impact from the architecture itself (breaking changes, confusing new surfaces).

## My Gate 1 hard requirement — STORY-1504 discoverability
**Satisfied.** §18.4 gives `scg onboard --list` a new synthetic line (`implicit default: <project_root> -> sensitivity=internal, trust=trusted (project-folder default, sec18.4)`), reusing the exact surface STORY-1404 already trained developers to check for "what's been vetted," rather than inventing a new one or leaving the default silent. This is the right shape — I'll verify the actual rendered output doesn't visually blur with real `ScanCache` entries once implemented (design intent is clear separation; real terminal output is the thing that actually matters, same standard I hold everywhere else).

## My 3 non-blocking Gate 1 notes
- STORY-1502 reason-string clarity: addressed — `"path matches a hardcoded restricted system location"` is textually distinct from a secrets-scan finding.
- STORY-1503 degraded-check visibility: addressed — a dedicated `ReputationCheckUnavailable` exception plus a distinguishing marker appended to `reason`, never conflated with "checked, came back clean."
- STORY-1501 config-schema consistency: reasonably addressed — `scanners: extra: [{name, import}]` follows the same "list of flat string-field mappings" shape as the existing `rules:` list. Not identical vocabulary (necessarily — a scanner registration isn't a rule) but not a second idiom either.

## New from this gate
- STORY-1501's `PolicyConfigError` for a bad `import:` path — confirmed (§18.1) it fails loud at load time, same precedent as existing regex/scanner-name errors. Light non-blocking ask for whoever implements: name the exact offending string and the expected `"module.path:ClassName"` shape in the message, matching this project's existing error-message quality bar (e.g. §14.1's regex errors). Not blocking — just don't let this one error path be the exception to an otherwise-good pattern.
- Confirmed the `PolicyRule` construction-time-validation move (§18.1) is invisible to an actual YAML-authoring user — the real fail-loud-at-load-time behavior is unchanged; only direct-Python-construction unit tests lose the check. Correctly scoped as Trin's test-audit item, not a UX regression.
- No new CLI flags introduced by any of the 4 stories — good, nothing new for a user to learn or discover via `--help` this epic.

## Verdict

**Approved.** Hard requirement satisfied at the design level (will re-verify against real rendered output at the mandatory phase gate, per standard practice — design intent isn't the same as confirmed behavior). No breaking changes to existing CLI surface. Proceeding to Mouse for phase planning.
