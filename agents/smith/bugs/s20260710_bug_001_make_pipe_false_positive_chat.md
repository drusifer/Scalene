# Bug 2026-07-10-001: `AP-MAKE-PIPE` false-positives on `make chat`

**Severity**: P3 — Signal-to-noise problem in the judge trace tool, no functional impact
**Filed by**: Smith
**Route to**: Neo (script bug in `agents/tools/trace_annotate.py`)

---

## Reproduction

Run `make judge-trace DATE=2026-07-10 FORMAT=md`, then grep the output for `AP-MAKE-PIPE`. 51 of 104 flagged calls are `make chat MSG="..." | tail -N`.

## Expected

`AP-MAKE-PIPE`'s stated fix is "mkf already captures output to `build/build.out` — tail that instead of piping." That's a real problem for targets routed through `mkf.py` (`make test`, `make judge-trace`, etc). `make chat` is explicitly *not* one of those targets — the `Makefile`'s own interception-layer comment says "All targets except help, chat, install_bob, update_bob, pull_bob, and clean_bob route through mkf." There is no `build/build.out` capture of `make chat`'s output for these calls to redirect to.

## Actual

`MAKE_PIPE_RE = re.compile(r'\bmake\b[^\n]*\|')` in `trace_annotate.py` matches any `make ... |` regardless of which target is invoked, so `make chat` calls are flagged with a fix instruction that doesn't apply to them.

## Root Cause

The regex has no target-awareness — it can't distinguish an mkf-routed target from an excluded one.

## Impact

51 of 190 total flags this run (27%) are noise. This inflates the apparent violation rate and could cause a future judge pass to either over-penalize `make chat` usage or, worse, get dismissed as unreliable because half its flags don't hold up under review.

## Recommended Fix

Exclude `make chat` (and the other mkf-excluded targets: `help`, `install_bob`, `update_bob`, `pull_bob`, `clean_bob`) from `AP-MAKE-PIPE` detection in `classify_bash()`, or restrict the regex to only fire when the piped `make` invocation's target is not in that exclusion list.
