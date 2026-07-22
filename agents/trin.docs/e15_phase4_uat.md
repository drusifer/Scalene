# Trin — `*qa uat phase-4` — Sprint 9 (E15) — 2026-07-21

## Checked against artifacts first
`task.md` Sprint 9 Phase 4 exit criteria: first-sighting still requires one real clean scan; a long session touching only project files never hits the "second uncleared resource blocks" wall; a restricted subpath under the project root still blocks. Mandatory Smith gate on `--list`'s real rendered output.

## Verified the actual ACs
`tests/test_resource_verifier.py::TestProjectFolderDefault` (Neo's 5 tests, reviewed and re-run, not just trusted): clean project file → `validated_allow` + `sensitivity=internal`; a *second* clean project file in an already-"low"-trust session still proceeds (the real friction this story fixes — confirmed this is genuinely different from the pre-E15 behavior by tracing `decide_access()`'s `uncleared` branch myself); explicit user rule beats the implicit default; hardcoded-restricted coexistence (using the real home directory + real `~/.ssh`, not a fabricated tmp-dir stand-in — Neo's first version of this test used a fake `.ssh` folder in a tmp dir and correctly failed, since the hardcoded prefixes are real absolute paths, not name-pattern matches; the corrected version is right).

## Went beyond the unit tests — ran the real CLI myself
Per this project's own precedent (real-binary verification, not just mocked units) and because this phase carries Smith's discoverability requirement: ran `python -m scalene.onboard --list` for real in a scratch directory, both before and after onboarding a real target.

```
$ python -m scalene.onboard --list --cache-path ./cache.json --policy-path ./scalene_policy.yaml
implicit default: /tmp/e15_manual_check -> sensitivity=internal, trust=trusted (project-folder default, docs/ARCHITECTURE.md sec18.4)
No onboarded targets in the scan cache.

[... onboarded a real clean file ...]

$ python -m scalene.onboard --list --cache-path ./cache.json --policy-path ./scalene_policy.yaml
implicit default: /tmp/e15_manual_check -> sensitivity=internal, trust=trusted (project-folder default, docs/ARCHITECTURE.md sec18.4)
secrets:
  /tmp/e15_manual_check/clean.md -> public
```

Confirms Smith's Gate 1 hard requirement is met in real rendered output, not just design intent: the synthetic line is visually distinct from a real cache entry (different prefix, different shape) and appears whether or not any real entries exist yet.

## Regression check
Full suite: `make test` — **381/381**.

## Verdict

**PASSED.** Handing to Smith for her mandatory gate — my real-CLI run above is a data point for her, not a substitute for her own `*user test`.
