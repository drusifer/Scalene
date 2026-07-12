# Project Lessons Learned

This file contains critical lessons and rules derived from past errors, technical discoveries, and architectural decisions. All agents MUST review this file before starting new implementation or architectural tasks.

---

## [2026-05-06] Transition to Artifact-Based Verification

> **Tags:** #Process #Oracle #Neo

### Context
Agents were previously instructed to consult the Oracle persona via chat for historical context and decisions. This often resulted in chat messages that were never picked up or processed by the intended persona.

### The Issue
Chat-based consultation is asynchronous and unreliable for immediate blocking needs. Agents would wait for a response that might not come, stalling progress.

### The Solution
Replaced "Oracle First" chat-based consultation with "Artifacts First" document-based verification. Agents now read consolidated logs and sprint plans directly.

### The Rule (The "Lesson")
DO NOT consult the Oracle via chat (`@Oracle *ora ask ...`) for routine historical or context checks. Instead, read the following artifacts in order: 1) Mouse's sprint plan (`agents/mouse.docs/`), 2) Oracle's `lessons.md` and `memory.md`, and 3) the recent `CHAT.md` history.

### References
- **Files:** `agents/*/SKILL.md`, `agents/oracle.docs/lessons.md`

---

## [2026-07-10] Sprint 2: Real Execution Catches What Code Review Misses

> **Tags:** #Process #Trin #Morpheus #Smith #Testing

### Context
Sprint 2 built `scalene monitor`, a Textual TUI (STORY-701/702). Three separate times across one phase, a gate that actually *ran* the software (not just read the diff) found a real, concrete bug that had already passed an earlier code-only check.

### The Issue
1. Morpheus's Phase 2 review flagged a *theoretical* concern (full table redraw every poll tick "might" cause UI flicker) — Smith's `*user test` (driving the real app via Textual's headless `Pilot`) found it was worse than flicker: the visual cursor silently diverged from the actual data filter.
2. Morpheus's Phase 3 review round 1 ran `apply_onboard_command()` with adversarial inputs (missing binary, malformed quoting) rather than trusting the happy-path tests — found 2 real uncaught crash paths that would have taken down the whole TUI.
3. Smith's Phase 3 `*user test` drove the full select→dismiss→apply flow and found the app lost all keyboard focus after any terminal action (Textual's `Widget.watch_disabled()` blurs a focused widget on disable, documented behavior, but nothing refocused anything after) — invisible from a code read, obvious within seconds of actually using it.

### The Rule (The "Lesson")
For interactive/UI-facing work, code review and unit tests are necessary but not sufficient. Reviewers (Morpheus) should probe with adversarial inputs, not just confirm the happy path compiles and passes. Smith's UX gate must actually drive the software (Textual's `App.run_test()`/`Pilot` is the correct headless mechanism for TUIs — not a mock, a real supported execution path) rather than reviewing a description of the feature. Do not skip or lighten these gates for "it's probably fine" phases — this sprint, every one of them found something real.

### References
- **Files:** `src/scalene/monitor_app.py`, `tests/test_monitor_app.py`, `agents/smith.docs/context.md`, `agents/morpheus.docs/context.md`

---

## [2026-07-10] detect-secrets: `scan_line()` Is a Debug API, Not a Filtered Scanner

> **Tags:** #Neo #Testing #ThirdPartyLibraries

### Context
Sprint 2 Phase 1 (STORY-801) swapped `secrets_scan.py` from 3 hand-rolled regexes to the `detect-secrets` library.

### The Issue
The obvious-looking API, `detect_secrets.core.scan.scan_line()` (meant for adhoc string scanning), deliberately skips its own entropy-limit filtering for non-quoted matches — by design, so `detect-secrets scan --string` can show raw entropy scores for debugging. Used naively, it flagged plain English words ("just", "docs", "markdown") in ordinary text as high-entropy secrets.

### The Rule (The "Lesson")
Before integrating a third-party scanning/detection library, test it against a known-clean input first. A false positive on trivial input is a strong signal you've picked the wrong entry point in the library's API, not that the library is bad. The correct path here was `scan_file()` (via a temp file) — the same fully-filtered path the library's own CLI uses.

### References
- **Files:** `src/scalene/secrets_scan.py`, `tests/test_secrets_scan.py`

---

## [2026-07-10] A Written Rule Nobody Checks Is Not an Enforced Rule

> **Tags:** #Process #Trin #Smith #Bob #Neo #Tooling

### Context
`*qa judge session` was run twice today. The first pass reconstructed a trace from `agents/CHAT.md` prose and scored TES=100 with zero bugs. The user rejected that approach and pointed at `agents/tools/trace_annotate.py` — a tool that already existed, parses real Claude Code JSONL session transcripts, and programmatically flags anti-patterns. It was orphaned: missing `jinja2` dependency, no `make` target, and never referenced by `judge/SKILL.md` or Trin's own `SKILL.md`. Once wired up (`make judge-trace`) and run against the same day's real sessions, it found 190 flags across 566 real tool calls — including `make test 2>&1 | tail -N` used ~39 times, directly contradicting a rule already written verbatim in `agents/neo.docs/SKILL.md`.

### The Issue
Two separate failure modes stacked on top of each other:
1. **Judging from a self-report, not a measurement.** CHAT.md is what personas chose to say about their own work — it cannot show tool-call-level behavior, and reconstructing a "trace" from it will always look better than reality, because anything not worth mentioning in a handoff message is invisible to it.
2. **A correct, specific, already-written rule was violated at scale anyway.** This wasn't a documentation gap (contrast with S1-003's missing chain step) — the exact right rule text (`NEVER: make test 2>&1 | tail -30 → use make test-q`) was sitting right there and simply wasn't consulted at the moment of running a test, 39 times over.

### The Rule (The "Lesson")
1. When judging tool/skill usage, use `make judge-trace` (real session-transcript parsing) as the primary evidence source. CHAT.md/state files remain the right source for *process* adherence (chain sequencing, gate compliance) — the two check different things and neither substitutes for the other.
2. When a violation is of an already-correct, already-specific rule (not a documentation gap), adding more prose to the same file is unlikely to fix it — the fix needs an actual checkpoint (Trin's UAT gate now runs `make judge-trace` before sign-off) rather than relying on recall alone. Save the distinction (documentation gap vs. enforcement gap) explicitly when filing similar findings — they need different fixes.

### References
- **Files:** `agents/tools/trace_annotate.py`, `agents/tools/trace_rules.json`, `agents/skills/judge/SKILL.md`, `agents/neo.docs/SKILL.md`, `agents/trin.docs/SKILL.md`, `agents/trin.docs/judge_20260710_trace.md`, `agents/smith.docs/trace_eval_20260710.md`
