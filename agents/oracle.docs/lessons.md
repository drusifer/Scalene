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

---

## [2026-07-15] Sprint 4: An Architecture Claim Is a Hypothesis, Not a Fact, Until Measured

> **Tags:** #Process #Morpheus #Neo #Architecture #Testing

### Context
Sprint 4 (E10) contained two separate, unrelated instances of the same failure shape: a written architectural claim about runtime behavior turned out to be empirically false when someone actually measured or tested it, rather than trusted it.

### The Issue
1. **Phase 2:** `docs/ARCHITECTURE.md` §13.3 asserted the new-resource cache-lookup path was "zero-added-latency." Morpheus measured it directly instead of trusting his own design doc and found ~6.6ms avg / ~16ms max per call, isolated to the background-scan spawn cost — a real risk against the <15ms hot-path NFR, not a rounding error.
2. **Phase 4:** the same architecture doc left the fatal-exit code "provisionally 1... pending verification." Neo actually corrupted this repo's own live, dogfooded `scalene-guard` hook (`.claude/settings.json` wires the real editable install as the session's own hook) and confirmed exit 1 has **zero blocking effect** on a real tool call — only exit code 2 blocks `PreToolUse`, per Claude Code's real hook contract, fetched fresh rather than recalled.

### The Rule (The "Lesson")
Any architecture-doc claim about latency, exit codes, or other externally-governed runtime behavior is a hypothesis until someone measures or tests it against the real system it depends on — not a fact because it was reasoned through carefully at design time. This is a stricter, more specific case of the 2026-07-10 "real execution catches what code review misses" lesson: here, the thing being checked wasn't even the codebase's own logic, it was an *external contract* (the hook harness, the OS process-spawn cost) that no amount of internal code review could ever validate. When architecture explicitly flags something as "provisional, needs verification," treat that as a hard requirement to actually verify empirically before implementation is considered done — not a formality to note and move past.

### References
- **Files:** `docs/ARCHITECTURE.md` §13.3/§13.5, `agents/morpheus.docs/phase2_latency_finding.md`, `src/scalene/cli.py`, `tests/test_performance.py`, `tests/test_cli.py`

---

## [2026-07-15] Sprint 4: A Row-Content Check Is Not a Rendering Check

> **Tags:** #Process #Smith #Trin #Neo #Testing #UI

### Context
Sprint 4 Phase 5 added a resource-cache panel to the `scg monitor` TUI. Trin's UAT added a real test asserting the panel's `DataTable` held the correct identity/label/timestamp values (closing a known gap-class from Sprint 2). Smith's UX gate still found a real bug: at a common 120-column terminal width, the "Last Scanned" column rendered as unreadable truncated text.

### The Issue
Textual's `DataTable` stores full, correct cell values regardless of the terminal's actual rendered width — a test that queries `table.get_row()` or asserts on stored cell content will pass even when the *visible, rendered* text is cut off to a few characters. Only Smith's `app.export_screenshot()` check, which inspects the actual rendered SVG/text output at a real terminal size, caught the truncation. The first fix attempt (shortening the timestamp string) still passed every existing data-level test while remaining visibly broken in a re-rendered screenshot — proving the string-shortening fix wrong required re-running the *same* screenshot check that found the bug, not writing a new unit test.

### The Rule (The "Lesson")
For any TUI/UI change, "the data model has the right values" and "the rendered output is legible" are two different claims requiring two different kinds of check. Row-count and row-content assertions (`table.get_row()`, `row_count`) verify the former; only a rendered screenshot (`app.export_screenshot()` at a realistic terminal size, or the real terminal itself) verifies the latter. Do not treat a passing data-level Pilot test as sufficient sign-off for a layout/width-sensitive UI change — and when re-verifying a fix for a rendering bug specifically, re-run the same screenshot-based check that found it, since a new data-level test can pass while the original rendering problem is still present.

### References
- **Files:** `src/scalene/monitor_app.py`, `tests/test_monitor_app.py` (`test_last_scanned_column_is_not_truncated_at_a_common_terminal_width`), `agents/smith.docs/phase5_bug_last_scanned_truncation.md`

---

## [2026-07-18] Sprint 5: A Gate That Actually Exercises the Feature Can Overturn the Feature

> **Tags:** #Process #Smith #Trin #Morpheus #Architecture #Security

### Context
Sprint 5 (E11) built `mode: allow` as a scoped, hand-authored exception to unconditional content-scanning (STORY-1104), specifically to give a user a way to silence a known false positive. Smith's mandatory Phase 3 gate — required to actually run the software, not review it on paper — tried a deliberately broad rule (`pattern: ".*"`, `mode: allow`) as an adversarial check. It worked exactly as coded: a single rule silently disabled all content-scanning project-wide, with zero warning. That's the identical failure shape the entire project exists to prevent (the "lethal trifecta"/Triangle-of-Doom), just reintroduced through the newest feature meant to add flexibility.

### The Issue
The gap wasn't a coding bug — `mode: allow` did precisely what STORY-1103's acceptance criteria asked for. The gap was that the feature's *design* let a single declaration self-certify trust with no independent validation behind it, which nothing in code review or the unit-test suite (all of which tested narrow, well-scoped rules) was positioned to catch. Only running the software with a hostile, plausible input — not a contrived edge case, a single wildcard character — surfaced it. Talking through the fix with the user in real time didn't produce a patch to `mode: allow`; it produced a wholesale replacement of the sprint's core mechanism (`docs/ARCHITECTURE.md` §15: rule-driven access control, validated-trust-gates-permission instead of scan-then-maybe-mask), because the same self-certification gap existed one level up in how trust was granted at all.

### The Rule (The "Lesson")
A mandatory pre-ship gate that only reviews code or runs example-shaped tests will pass a feature that is fully correct against its own stated acceptance criteria and still reintroduces the exact defect the project exists to prevent — the ACs themselves can be too narrow to expose it. The gate has to include someone deliberately trying to break the *safety property*, not just confirm the *feature* works: for a permission/trust system specifically, always test the maximally broad, laziest-possible-to-write version of any new escape hatch (the blanket wildcard, the empty pattern, the config a rushed developer would actually paste) before approving it, not just the narrow example in the docs. When that test reveals the gap is structural, don't patch around it — the right response can be to reopen the design, even mid-gate, rather than ship a narrower version of the same hole.

### References
- **Files:** `docs/ARCHITECTURE.md` §15 (full corrected design), `src/scalene/resource_verifier.py` (`decide_access`), `agents/smith.docs/e11_gate1_review.md`/`e11_gate2_review.md` (the gates that approved the superseded design), `agents/neo.docs/current_task.md` (full implementation change list)

---

## [2026-07-20] Sprint 7: A Well-Reasoned Validation Message Can Be Unreachable From the Real CLI

> **Tags:** #Trin #UX #DX #Validation

### Context
`scg onboard`'s `--mode` flag rejects `mask` at two layers: `argparse`'s `choices=("allow", "block")` (generic "invalid choice" error) and `onboard()`'s own explicit check, which carries a carefully-written explanation of *why* — `mask` has no distinct effect under sec15's `decide_access`, and would silently behave like `block` while looking like it should do something else. Trin's UAT (real CLI invocation, not a direct library call) found that a real terminal user hitting `--mode mask` only ever sees argparse's generic message; the reasoned explanation is real, tested code, but structurally unreachable from the command line because the outer validation layer always fires first.

### The Issue
Layered validation (CLI-level `choices=` plus a library function's own deeper check) is a reasonable defense-in-depth pattern — the library function still protects direct/programmatic callers (tests, other code) that bypass argparse. But nobody had asked, for this specific case, *which* layer's message a real end user actually sees. The two messages weren't in tension or wrong — one was just silently unreachable in the one context (the real CLI) where a human is most likely to hit it. This wasn't caught by unit tests, since `test_onboard.py`'s own coverage calls `onboard()` directly, the same shortcut that made the gap invisible.

### The Rule (The "Lesson")
When a constraint is checked at more than one layer (CLI parsing vs. the underlying function, a form vs. its API, a decorator vs. the method it wraps), don't assume the "best" message wins — check which layer actually fires first for the audience that matters most, by running the real entry point, not just calling the function directly. If the inner layer's message carries real, non-obvious reasoning (not just "this value is invalid"), either surface a shortened version at the outer layer too, or confirm the outer layer's generic message is good enough that the inner one is genuinely just a safety net for callers who don't need the explanation.

### References
- **Files:** `src/scalene/onboard.py` (`_ONBOARD_VALID_MODES` check vs. `main()`'s `argparse` `choices=`), `agents/trin.docs/current_task.md` (`*qa uat sec16`, the real-CLI check that found this)
