# Smith — `*user test phase-4` re-gate — Sprint 9 (E15), mechanism corrected — 2026-07-21

## Why I'm re-gating, not reusing my earlier approval
The underlying mechanism changed completely (a real on-disk rule instead of an implicit in-memory one + my synthetic `--list` line, which no longer exists). My earlier approval was for code that Neo no longer ships — re-testing the actual current behavior, not the design I signed off on before.

## What I ran (superseded by an automated test — see correction below)
My first pass here used a manual, one-off `echo ... | python -m scalene.cli ...` shell check to see the real behavior. User correction, mid-session: that verification needed to become a real, repeatable automated test (Trin's to build, not an ad-hoc scenario), not stay a throwaway transcript. Trin added `test_cli.py::TestGuardCreatesDefaultProjectPolicy::test_real_subprocess_end_to_end_creates_and_reuses_the_default` — a genuine `subprocess.run([sys.executable, "-m", "scalene.cli", ...])` call (real binary, not the in-process `guard_main()` helper), asserting exactly what I checked by hand: first call creates `scalene_policy.yaml` with the correct single rule (`mode: allow`, `sensitivity: internal`, `project folder default` in the description); second call reuses it without duplicating the rule or rewriting the file. My gate evidence below is this test (reviewed and re-run via `make test`), not my own manual transcript.

```
$ cat scalene_policy.yaml   # (real output, captured once for illustration; the actual gate evidence is the automated test above)
rules:
- tool: .*
  pattern: ^/tmp/e15_smith_final(/|$)
  sensitivity: internal
  mode: allow
  scanner: secrets
  description: project folder default (auto-created)
```

## My Gate 1 hard requirement (discoverability), re-evaluated against the new mechanism
**Satisfied — more robustly than the mechanism I originally gated.** The rule now lives in the developer's own `scalene_policy.yaml`, in plain YAML, using the exact same field vocabulary (`tool`/`pattern`/`sensitivity`/`mode`/`scanner`/`description`) as every hand-written or onboard-authored rule — zero new mental model (Nielsen #4, Consistency). The `description: project folder default (auto-created)` tag makes it self-explanatory to anyone who opens the file, which they will, since it's now a real file that appears in their project the first time they use it (`ls`, `git status`, opening the repo in an editor all surface it naturally) — a stronger discoverability guarantee than my original synthetic CLI-only line, which only ever surfaced if someone specifically ran `--list`.

## Silent creation on the hot path — checked, not a finding
The file gets created with zero stdout announcement. Confirmed this is correct, not a gap: `scalene-guard`'s stdout contract is exactly one JSON hook-response object (Claude Code parses it directly) — any extra printed text would break that contract. This matches the existing precedent for other silent first-sighting side effects (cache writes) elsewhere in this codebase.

## Reviewed Trin's automated test itself (not just its pass/fail)
Read `test_real_subprocess_end_to_end_creates_and_reuses_the_default` in full: it spawns the real binary via `subprocess.run()`, feeds a real hook JSON payload on stdin exactly as Claude Code would, and asserts on the real parsed `hookSpecificOutput.permissionDecision` *and* the real written YAML content — not a mocked shortcut. Re-ran `make test` myself (389/389) rather than trusting the reported count.

## Verdict

**APPROVED.** The corrected mechanism satisfies my original hard requirement by construction, not by a bolted-on display feature, and it's now backed by a real, repeatable automated test instead of a one-off manual transcript. Handing to Morpheus for the corrected-design code review.
