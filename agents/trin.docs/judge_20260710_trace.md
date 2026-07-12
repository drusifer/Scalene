# Judge Trace — Today's Tool/Skill Use (2026-07-10) — REVISED

**Compiled by:** Trin
**Supersedes:** the first version of this file, which reconstructed a trace from `agents/CHAT.md` prose. The user correctly rejected that approach — this project has a purpose-built tool (`agents/tools/trace_annotate.py`) that parses **real Claude Code JSONL session transcripts** (actual `tool_use` events) and programmatically flags anti-patterns via `agents/tools/trace_rules.json`. It existed but was orphaned: missing `jinja2` dependency, no `make` target, not referenced by `judge/SKILL.md` or Trin's own `SKILL.md`. Fixed as part of this run: `jinja2` added as a `dev` extra in `pyproject.toml`, `make judge-trace` target added to `Makefile`.

**Source:** `make judge-trace DATE=2026-07-10 FORMAT=md` → `agents/trin.docs/judge_tool_trace.md` (raw tool output, machine-generated, do not hand-edit).

## Ground-Truth Numbers

566 real tool calls across 2 sessions (521-call session = Sprint 2 plan-through-launch; 45-call session = this judge run itself, including the tool's own bootstrapping). 190 flags (33.6% flag rate).

| Flag | Count | Verdict after manual review |
|---|---|---|
| `AP-MAKE-PIPE` | 104 | **Mixed** — see breakdown below |
| `AP-RAW-VENV` | 62 | **Mixed** — see breakdown below |
| `AP-DUP-READ` | 12 | Mostly false-positive (see below) |
| `AP-VIA-READ` | 7 | Real violation |
| `AP-VIA-GREP` | 6 | Real violation |
| `AP-MAKE-BYPASS` | 1 | Real violation |

### AP-MAKE-PIPE (104) — breakdown
- **51 instances**: `make chat MSG=... | tail -N`. **False positive.** `make chat` is explicitly excluded from `mkf.py` capture in the `Makefile` itself (see the `chat:` target comment: "All targets except help, chat, install_bob... route through mkf"). There is no `build/build.out` equivalent for chat output, so the rule's stated fix ("tail build/build.out instead") doesn't apply. `MAKE_PIPE_RE` in `trace_annotate.py` matches any `make ... |` regardless of whether that target routes through mkf — this is a tool bug, not an agent behavior problem.
- **39 instances**: `make test 2>&1 | tail -N`. **Real, repeated violation.** Neo's own `SKILL.md` line 145 states verbatim: `NEVER: make test 2>&1 | tail -30 → use make test-q (built-in concise output)`. This rule was already written and was violated on the large majority of test runs during Sprint 2 implementation — not a documentation gap, a compliance gap.
- **2 instances**: `make judge-trace ... | tail` (this session, mine) and 1 other minor. Same category as the `make test` violations — documented alternative existed (`tail -n N build/build.out` per the project's own verbosity convention), piped anyway.

### AP-RAW-VENV (62) — breakdown
- **1 clear rule violation**: `.venv/bin/python -m pytest tests/test_secrets_scan.py -v` — directly contradicts Neo's `SKILL.md` line 142 (`NEVER: .venv/bin/pytest ... → use make test`), and `make test FILE=tests/test_secrets_scan.py` was the documented equivalent the whole time.
- **~55 instances**: one-off `.venv/bin/python -c "..."` adversarial/exploratory snippets (testing `detect-secrets` library entry points, checking `RowDoesNotExist` import paths, informal perf timing, manually driving the installed `scalene`/`scalene-guard` binaries for real end-to-end UAT). These match the pattern `lessons.md`'s 2026-07-10 entry explicitly praises ("real execution catches what code review misses") and Trin's own `SKILL.md` explicitly sanctions ("if you're having trouble with an issue try making a bespoke tool to help"). Not filing these as violations — they're the mechanism behind real bugs found this sprint (secrets-scan false-positive trap, textual graceful-degradation check), not a `make`-target bypass in the pytest/ruff/mypy sense the rule targets.
- **~6 instances**: `.venv/bin/pip install ...` — legitimate, this *is* what `make setup` does internally; these ran during active dependency work (adding `detect-secrets`, `textual`) where confirming an install inline before wiring it into `pyproject.toml`/`make setup` is reasonable, not a target bypass.

### AP-VIA-GREP / AP-VIA-READ (13 combined) — real violations
`agents/PROJECT.md` states `via: enabled`. Neo's and Trin's own `SKILL.md`s both state this is mandatory ("Raw File-Reads and Grep Fallbacks are Forbidden... MUST NEVER perform fallback file-reading or grep searches to locate symbols"), and `mcp__via__via_query` was available as a tool this session. `grep -n "class TaintState\|def..."`-style symbol lookups and un-edited source-file `Read`s occurred instead. Real, if lower-volume, violations of an existing rule.

### AP-DUP-READ (12) — mostly false-positive
Nearly all instances are `Read` calls on the *same file at different offsets* while actively editing a large file (`monitor_app.py`, `test_monitor_app.py`, `task.md`) — navigating sections of a large file during development, not re-reading unchanged content. The rule (`Read on same path 3+ times`) doesn't check offset or whether the file changed between reads, so it over-flags this legitimate pattern.

### AP-MAKE-BYPASS (1) — real
Same event as the `.venv/bin/python -m pytest` line above — one Bash call double-flagged (raw venv path *and* pytest-bypass).

## Bugs / Anti-Patterns Found (filed)

1. **Tool bug** — `AP-MAKE-PIPE` in `trace_annotate.py`/`trace_rules.json` doesn't exclude `make chat` (a target the `Makefile` itself documents as not routed through `mkf`), producing 51 false positives out of 104 total flags for this rule. Routes to **Neo** (script fix).
2. **Behavior gap** — `make test 2>&1 | tail -N` was used in ~39 of ~45 test-run invocations this sprint despite Neo's own `SKILL.md` explicitly forbidding it and naming the correct alternative (`make test-q`). The rule exists and is precise; it just isn't being followed at the point of use. Routes to **Bob** (needs stronger reinforcement, not new documentation — the doc is already correct).
3. **Behavior gap** — `via`-mandatory rule (real, tool-available, written in 2 personas' `SKILL.md`s) bypassed 13 times via raw `grep`/`Read` for symbol lookups. Routes to **Bob**.
4. **Rule quality** — `AP-DUP-READ` doesn't distinguish "re-reading unchanged content" (wasteful) from "reading a different offset of a large file mid-edit" (normal). Routes to **Neo** (script fix) as a lower-priority cleanup.

## Judge-Loop Gap (separate from the above)

The judge `SKILL.md` and Trin's own `SKILL.md` never referenced `trace_annotate.py`/`session_trace.py` as the tool Trin should use for `*qa judge`. The 2026-07-08/09 judge loop and my own first pass at this one both hand-reconstructed a trace from memory/CHAT.md instead. Fixed as part of this run (see Bob's handoff) — needs the reference added so this doesn't recur.

---
*Handoff: @Smith *user feedback judge session (revised)*
