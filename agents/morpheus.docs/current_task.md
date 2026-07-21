# Current Task

**Status:** `*lead review phase-2` (Sprint 8/E14) — **APPROVED after 1 fix round.** Handed to Smith for the mandatory gate.
**Assigned to:** N/A (Smith next)
**Started:** 2026-07-21
**Completed:** 2026-07-21

## Task Description (most recent): `*lead review phase-2` re-review after Neo's ordering fix
Independently re-verified the fix myself (not just trusting Neo's report): mocked the exact same real run (`isatty=True`, `input` mocked) with the axis flags missing — confirmed `input()` is called **0** times now (was 1 before the fix) and the error surfaces immediately. **APPROVED.** No other issues found this round. `make test`: same 5 known Phase-3-scoped failures, no new ones.

## Task Description (most recent): `*lead review phase-2` (Sprint 8/E14)
Verified `_confirm_targets()`/`onboard_targets()`/`_list_inventory()` against §17.3/17.4/17.5. Reviewed Neo's self-caught bug fix (the `_onboard_resource()` tool/pattern override) — correct, and confirmed by re-reading the diff that `onboard()`'s custom `tool`/`pattern` now flow into the *one* real write, not a cosmetic post-hoc patch on the returned dict.

**Found a real UX/ordering bug myself, verified live (my own standing habit, not just reading code)**: `main()` calls `_confirm_targets()` — which runs the interactive prompt — *before* `onboard_targets()` validates `--sensitivity`/`--mode`. Mocked a real interactive run (`isatty=True`, `input` returns `'y'`) with neither flag set: the user answers the confirmation prompt (`input()` called once), and only *after* that gets "At least one of 'sensitivity' or 'mode' must be provided." A batch-level precondition that's checked *after* asking the user to do something is backwards — it should fail before wasting their input, the same way `--yes`'s non-interactive path already fails immediately (confirmed via Trin's UAT). **Sending back to Neo**: move `_validate_axis()`'s call to the top of `main()`, right after `argparse`, before `load_tool_call`/`identify_targets`/`_confirm_targets` — a one-line reordering, not a design change.

Not blocking on anything else: `--list`'s grouping/filtering matches §17.5 exactly, batch semantics (Trin's real partial-failure test) match §17.4. `make test`: 324/329, same 5 known Phase-3-scoped failures Neo/Trin already confirmed — no new failures from this review.

## Task Description (prior): `*lead review phase-1` (Sprint 8/E14) — **APPROVED.**

## Task Description (most recent): `*lead review phase-1` (Sprint 8/E14)
Verified against §17.1/17.2/17.6 exactly. `identify_targets()` is a literal match for §17.2's pseudocode — traverses `SCANNERS`, dedupes by `(kind, identity)`. Confirmed the reputation score plumbing is genuinely additive end-to-end: `subprocess_isolation.py` needed zero changes (it JSON-round-trips the whole worker response transparently, so a new `"reputation"` key just flows through), `ScanResult.reputation` defaults to `None`, and `FileScanner.scan()` was correctly left untouched rather than wired to a `.get("reputation")` that would always be `None` anyway — no dead code added for a key that's never present in that path.

**Endorsing Neo's scope deviation** (task.md literally said "delete `_resolve_resource()` entirely" as a Phase 1 line item — Neo deferred it): correct call, not a shortcut. `_resolve_resource()`'s only caller is `onboard()`, which Phase 2 is what actually replaces; deleting it in Phase 1 would have either broken `onboard()`/`main()` immediately (before their replacement exists) or left it as orphaned dead code with nothing calling it, neither of which serves "every phase stays green." Corrected `task.md`'s Phase 1 task wording to match reality (`--` a phase plan describing something that didn't literally happen would itself become exactly the kind of doc drift this project treats as a real defect, not cosmetic).

No class-diagram changes needed — `identify_targets()`/`load_tool_call()` are module-level functions, same treatment as every other CLI-entrypoint helper in `onboard.py`, consistent with precedent. `make test`: 310/310 (unaffected by my one doc correction). **APPROVED.**

## Task Description (prior): `*lead review sprint plan` (Sprint 8/E14) — **APPROVED, LOCKED.**

## Task Description (most recent): `*lead review sprint plan` (Sprint 8/E14)
Verified Mouse's 3-phase breakdown against §17 exactly: Phase 1 = §17.1/17.2 (invocation contract + traversal) + §17.6 (reputation, sequenced first since Phase 2's output formatting depends on `ScanResult.reputation` existing) — correctly no Smith gate, no usable CLI change yet. Phase 2 = §17.3/17.4/17.5 (confirmation, per-target scan/write, `--list`) — correctly the one gated phase, this is where my hard-requirement design (non-interactive escapes) becomes real code Smith can actually run. Phase 3 = §17.8's named breaking-change files, correctly not re-gated (reconciling already-approved Phase 2 behavior into docs, not new behavior) but held to Trin's verbatim-doc-reread standard instead. Confirmed `_resolve_resource()` has zero direct test references (grepped myself before approving Phase 1's "delete entirely" task) — safe to remove outright, not deprecate-in-place. §17.7's deferral (STORY-1406) correctly produced zero tasks, not silently absorbed into Phase 2 or 3. No Tank confirmed correct — no infra/daemon change. **APPROVED. Sprint 8 plan LOCKED.**

## Task Description (prior): `*lead arch sprint` (E14) — architecture written as ARCHITECTURE.md §17.

## Task Description (most recent): `*lead arch sprint` (E14) — Tool-Call-Driven Onboarding
Resolved all 6 of Cypher's open questions plus Smith's Gate 1 hard requirement into `docs/ARCHITECTURE.md` §17:
- **Invocation contract**: `scg onboard` reads `{"tool_name", "tool_input"}` from stdin (or `--call PATH`) — deliberately reuses `scalene-guard`'s own hook-JSON field names rather than inventing a second vocabulary.
- **Confirmation (Smith's hard requirement)**: interactive TTY prompt by default, `--yes` and `--only IDENTITY,...` as two explicit non-interactive escapes, fail-fast (not hang) if stdin isn't a TTY and neither escape is given.
- **`--tool`/`--pattern` dropped**, `--sensitivity`/`--mode`/`--scanner`/`--description` kept as batch-level flags — the former don't compose across N auto-identified targets, the latter still express one coherent trust decision about the confirmed batch.
- **Inventory (STORY-1404)**: no new store — `scg onboard --list [--scanner NAME]` is a read-only view over `ScanCache.all_entries()`, which already durably records exactly this. Deliberately avoided introducing state that could drift from what already exists.
- **Reputation score (STORY-1405)**: `ScanResult` gains `reputation: float | None`, additive (no `label`/`reason` change, zero blast radius on existing `decide_access()` callers). `LocalHeuristicChecker.check()` changes from first-match-wins to evaluate-all-3-heuristics so the score reflects real evaluated signal, not a relabeled boolean; `is_trusted` semantics unchanged (still any-trip-fails). `FileScanner` stays `reputation: None` deliberately — `detect-secrets`' open-ended finding list has no natural fixed-heuristic-count basis for a fraction the way `reputation.py`'s 3 checks do; inventing one would be false precision.
- **STORY-1406 explicitly deferred** — not designed here, would need its own full story→architecture pass given it reverses §15's post_tool_use rationale.
- Updated §4's class diagram for `ScanResult.reputation` in the same pass (own standing discipline against the exact kind of drift I've flagged 3x before in other reviews). `tests/test_architecture_docs.py`: 6/6, confirms the new stereotype doesn't break the drift guard.
- Flagged the real breaking-change surface (Smith's Gate 1 grep) as an explicit §17.8 subsection so Mouse's phasing has to account for it, not discover it mid-implementation.

## Task Description (prior): `*lead review sec16` — **APPROVED, no fix round.** Handed to Oracle for grooming.

## Task Description (most recent): `*lead review sec16` — architecture review of `scg onboard` authoring a `PolicyRule` in one call
Read `onboard.py` in full against §16 (which Neo added when picking this up via bob-protocol — I confirmed it accurately describes the shipped code, not just aspirationally). Checked:
- Ordering is correct and safe: `mode` validity is checked before the scan runs (no wasted scan on an invalid request); the `PolicyRule` itself is constructed and validated (regex/sensitivity/mode/scanner membership, reusing `PolicyRule.__post_init__` — no duplicated validation logic) *before* the cache is touched, so an invalid rule request never pollutes the scan cache.
- Confirmed §4's class diagram needs no changes — `onboard()`/`_write_rule()` are CLI-entrypoint functions, not classes, same treatment as the pre-existing (untouched) `PolicyRule`/`ScanCache` boxes; §13.4's original re-scope never added diagram nodes for onboard.py either, consistent precedent.
- Confirmed `DEFAULT_POLICY_PATH`/`--policy-path` in `onboard.py` matches `cli.py`'s own default (`Path("scalene_policy.yaml")`, cwd-relative) — no drift between the two consumers of the same file.
- Ran `tests/test_architecture_docs.py` directly after Neo's new §16 heading landed — still 6/6, the doc-drift guard tolerates a new section correctly.
- **One real, non-blocking observation**: `onboard()` writes the scan-cache entry (`ScanCache.put`) *before* writing the policy rule (`_write_rule`) — if the rule-write step fails (e.g. a permissions error on `scalene_policy.yaml`) after the cache write already succeeded, the user sees "Onboarding blocked: could not write..." even though the real scan genuinely happened and is durably cached. Harmless under sec15's `decide_access` (a cache entry with no matching rule is inert — matching requires both), but the error framing slightly undersells that the scan itself succeeded. Not worth a fix round for this low-probability ordering nit; flagging for whoever next touches `onboard()`.
- `make test`: 289/289 (unaffected, confirmed).

**APPROVED.**

## Task Description (prior): `*lead review sec15` — architecture review of the rule-driven access control rework
This never got a formal review when it shipped (direct engineering with the user, mid-conversation). Found and fixed one real issue: `_resolve_rule_for_resource()` (feeds the dormant `evaluate()`/`MaskingEngine` path) and `_find_matching_rule()` (feeds the live `decide_access()` path) had **identical** rule-matching logic (scanner/tool/pattern checks) duplicated verbatim — consolidated so `_resolve_rule_for_resource` now calls `_find_matching_rule` and derives its return from the result. Behavior-preserving (`make test` 266/266 unchanged before/after).

Also found and fixed real documentation drift in §4's class diagram, not caught by any test since diagrams aren't executable: `TaintState`'s fields still showed `has_sensitive_data`/`has_untrusted_data` (removed in this same rework), `MaskingEngine.decide()`'s signature still showed the old `(taint, match, value, mode)` args (it's `(match, value)` now, `taint` was dropped in Phase 3), and `MaskingEngine --> TaintState` was a stale relation. Fixed all three, added `AccessDecision`/updated `ResourceVerifier`'s relations. Replaced §5's sequence diagram (which only showed the old masking flow) with the real `decide_access()` flow, keeping the old one as marked historical record rather than deleting it — same convention as every other correction in this document.

**APPROVED.**

## Task Description (prior): `*lead review phase-3` (Sprint 5, last phase)

## Task Description (most recent): `*lead review phase-3` (Sprint 5, last phase)
Verified `MaskingEngine.decide()` matches §14.4 exactly — unconditional scan, `mode == "allow"` short-circuit before scanning ever runs. Confirmed Trin's aggregation-safety check directly in code: `_MODE_RANK`'s max-wins means an `allow`-matched resource can never override a stricter `mask`/`block` resolved for a different resource in the same call. Agreed with Trin's flagged discussion point (pattern=".*"+mode=allow can blanket-disable scanning at the rule level) — genuinely deliberate/hand-authored, not automatic, so correctly not blocking, but a legitimate question for Smith's gate on whether that deserves a warning. One cosmetic note, not worth the blast radius to fix now: `MaskingEngine.MASK_LITERAL`'s name ("PROVENANCE_GUARD") is stale now that provenance doesn't gate masking — it's real, user-visible output text (appears in actual masked tool calls), so renaming it is a behavior-visible change for a naming nicety, not worth doing without a real reason. **APPROVED.** All 3 Sprint 5 phases complete — handed to Smith for the mandatory gate.

## Task Description (prior): `*lead review phase-2` (Sprint 5)
Verified `_resolve_rule_for_resource`/`_resolve_sensitivity_and_mode` match §14.1/§14.4 exactly: first-match-by-declaration-order per resource, most-restrictive-wins aggregation across resources (mirrors the existing ANY-match convention), `config.mode` correctly can never resolve to `allow` when no rule matches (consistent with "allow is rule-only" — confirmed `PolicyConfig.mode`'s own validator still rejects it). Noted Trin's adversarial regex-validation finding (real, correctly fixed at `PolicyRule.__post_init__`, the right layer — config-load time, not the hot path) — good example of exactly the kind of adversarial testing I've pushed for in past phase reviews (Sprint 4 Phase 1/2 precedent), glad to see Trin doing it proactively now rather than needing me to demonstrate it every time. **APPROVED.**

## Task Description (most recent): `*lead review phase-1` (Sprint 5) + a real architecture amendment
Verified Neo's Phase 1 work matches §14.1/14.2/14.5/14.6 exactly: `URLScanner` identity is genuinely per-URL now (confirmed via the new `test_distinct_paths_under_same_host_are_separate_resources` + evaluate()-level test), `scan()` correctly still runs the host-level reputation heuristic (extracts host via `urlparse`, sensible fallback for bare-host callers), `PolicyRule`/`rules:` parsing matches the documented schema and validates cleanly, the repo's own dead `allowlist:` block is migrated with a real regression test guarding against recurrence. **APPROVED.**

**While reviewing, caught a real gap in my own §14.4 design** (not Neo's fault — an architecture miss): STORY-1104's unconditional scanning silently removes the only mechanism a user had (onboarding a destination as trusted) to permanently stop a real-looking-secret false positive from being masked forever, with nothing designed to replace it. This is a genuine safety/UX tradeoff, not a mechanical detail — raised directly with the user rather than deciding it myself. **User's call: add a scoped suppression mechanism.** Added `PolicyRule.mode = "allow"` (rule-only, `scg onboard` never sets it) to §14.4 as an amendment, updated STORY-1103's ACs, updated `task.md` Phase 3 (task 3.1 now handles the skip-scan branch, new task 3.4 reworks the onboard-suggestion messaging and rewrites its e2e test's premise). Flagged to Smith now since Phase 3's Smith gate will need to evaluate the reworded messaging — bigger UX surface than originally scoped for that phase.

## Task Description (most recent): `*lead review sprint plan` (Sprint 5)
Verified Mouse's 3-phase `task.md` breakdown against my own §14 architecture. Phase boundaries match exactly (schema → matching → wiring, correctly hard-dependency-ordered — matching can't resolve without rules existing, masking can't consume `mode` without matching producing it). Smith gate placement correct: only Phase 3, since Phases 1-2 have zero user-facing surface (`scg onboard` explicitly untouched per §14.3, nothing consumes `sensitivity`/`mode` until Phase 3). Confirmed my own real-migration-test-case finding (dead `allowlist:` block) and the `NFR-Perf-UnconditionalScan` verification requirement both landed as named tasks (1.3, 3.3), not loose prose. No Tank phase confirmed correct (§14.7). **APPROVED. Sprint 5 plan LOCKED.**

## Task Description (most recent): `*lead arch sprint` — formal E11 architecture (§14)
Cypher's E11 stories (STORY-1101-1105) passed Smith Gate 1 with one carried-forward hard requirement: `scg onboard` must not regress from single-`--target` simplicity. Wrote §14 resolving:
- **Rules layer on top of scanner identification, not a replacement of it** (resolves open Q#1 on JSONPath) — `identify()` stays as-is; a `PolicyRule`'s job is purely classification (sensitivity/mode) of an already-identified `Resource`, matched by `tool` regex + `pattern` regex against `resource.identity`. The implicit default rule is constructed in code, never written to YAML.
- **`scanner` field is optional/inferred** (resolves Q#2) — every `Resource` already carries `scanner_name`; `scanner` on a rule is only a disambiguating filter.
- **`URLScanner` identity fixed to per-URL, not per-host** (STORY-1101) — `_URL_FALLBACK_RE` captures the full URL span, not just `host`. This is the actual defect fix. Broadening trust to a whole host now requires an explicit, auditable `rules:` entry.
- **`scg onboard --target` unchanged** — satisfies Smith's hard requirement directly. Rule-authoring is the separate power-user path (hand-edit `scalene_policy.yaml`), not CLI-automated in this epic (no evidence yet it's the common case).
- **`MatchResult` gains `sensitivity`/`mode`**, resolved per-call from rule matching; `is_sensitive`/`is_trusted` keep their exact current meaning (still feed `TaintState`, still displayed in `scg monitor` — confirmed via grep this is their only consumer).
- **`MaskingEngine.decide()` becomes unconditional** (STORY-1104) — `taint`/`provenance_risk` gate removed from `decide()`'s signature entirely; every payload value gets scanned every time, action driven by `match.mode`. Named the resulting NFR consequence explicitly (`NFR-Perf-UnconditionalScan`, <10ms provisional) rather than leaving it a footnote — per Sprint 4's own retro lesson about unverified runtime claims.
- **On-disk schema** (resolves Q#3): new `rules:` list, sibling to `defaults:` in `scalene_policy.yaml`. Optional — absent means implicit-default-rule-only behavior.
- **STORY-1105 migration**: no automatic cache re-keying (mechanically converting a host-keyed entry to a URL-keyed one would just relocate the same over-broad-trust bug). Old-scheme entries go inert/unmatched — fail-safe by construction, not by added migration code. Real test required: seed an old-format entry, confirm a different path on the same host is NOT trusted.
- **Found a real, live bug while designing this**: the repo's own root `scalene_policy.yaml` still has a pre-Sprint-4 `allowlist:` block that's been silently dead since E10 shipped (`PolicyConfig.from_yaml` never parses `allowlist:`, only `defaults:`) — nobody caught this through all of Sprint 4's close/retro. Not caused by E11, but this file becomes Neo's real (not synthetic) migration test case — Phase 1 must rewrite it to the new `rules:` schema.
- Carried forward (not re-litigated a 4th time): §4's class diagram needs `PolicyRule` back — flagged for whoever implements Phase 1.

## Task Description (most recent): correct §13.1, document the trust/sensitivity model (§13.8)
The per-resource mask|block proposal (previous task below) evolved through direct conversation with the user into something much larger and more fundamental: **§13.1's "URL resource identity = host, not full URL" decision is wrong** — it structurally reproduces the exact "one scan vouches for an unbounded future set" defect E10 was built to close, just relocated from a user-authored regex into the resource-identity model. `FileScanner` already does this correctly (full path); `URLScanner` doesn't.

The user reframed Scalene's actual priority: mitigating prompt-injection/tool-poisoning is the **primary** goal (trust = could this source make the agent do something malicious), secret-masking is the **emergent/secondary** protection (sensitivity = blast radius if something goes wrong). These are independent axes, not parallel provenance signals as previously treated.

**What's now written into `docs/ARCHITECTURE.md`** (committed):
- §13.1: revision note in place (kept the original wrong reasoning visible, not deleted) pointing to §13.8.
- §13.8 (new): the corrected model in full —
  - Trust (read-side, could this source inject malicious instructions) vs. Sensitivity (blast radius, independent axis) as two separate concepts.
  - Exactly 3 sensitivity levels: Public / Internal Only / Restricted.
  - Masking becomes **unconditional** via an implicit default top-level rule (`tool: ".*"`, `jsonpath: "$.*"`, `pattern: ".*"`, `sensitivity: public`, `mode: mask`) — content-scanning is a universal baseline, not gated by taint/classification. This is what makes `sensitivity: public` a safe default rather than a weakening.
  - `PolicyRule` returns (jsonpath + pattern, tool-shape-agnostic) but in a **narrower role than pre-Sprint-4**: it decides *candidacy and resource identity* (named capture groups become the cache key, generalizing STORY-1001's original intent instead of Phase 1's internal-only downgrade of it) — it does NOT decide trust directly. The scan cache still verifies and freshness-tracks *per distinct matched identity*, so a wildcard `pattern` widens what's considered, never what's vouched for without checking. This is the piece that makes bringing patterns back safe this time.
  - `PolicyRule`'s new shape: `tool`, `jsonpath`, `pattern`, `sensitivity`, `mode` (mask|block — not a boolean, confirmed with the user), `scanner` (optional), `description`.
  - Explicit "not yet decided" list: exact JSONPath for "any argument," whether `scanner` must be explicit or inferred, the real on-disk schema, how `scg onboard --target` maps onto a generated rule.
- §4's class diagram: `PolicyRule` added back, connected to `ResourceVerifier`, explanatory note rewritten.

**Not implemented.** This is a documented, corrected *design*, not code. The user then said `*sprint go` — meaning: run this through the real sprint process (Cypher writes stories, Smith gates, Mouse phases, implementation Bloop) rather than just coding it ad hoc, given it touches a shipped, closed sprint's on-disk format and CLI surface.

## Task Description (prior): direct user proposal — per-resource mode at onboard time
User (via `*chat TO=all`): "add a property to the allowlist rules for: mask | block. So when I onboard I can make that decision." Assessed against the current architecture (post Sprint 4/E10): flagged that `MaskingEngine.decide()`'s `not match.is_trusted` gate means content-scanning is *skipped entirely* for trusted resources today, not scanned-then-treated-leniently — so a per-resource mode property attached to `trusted` would never actually fire. Presented 2 structural paths (always-scan-and-weight vs. a new scan-but-respond-differently category) with a lean toward the latter (additive, doesn't weaken what `trusted` currently guarantees or E10's latency reasoning). Full writeup: `agents/morpheus.docs/proposal_per_resource_mode.md`. Explicitly did not decide unilaterally — asked the user for direction, flagged this probably wants Cypher's requirements framing too before a schema change (touches `.scalene/scan_cache.json`'s on-disk format and `scg onboard`'s CLI, both just stabilized in Sprint 4).

## Task Description (prior): `*lead review phase-3` (Sprint 3, STORY-903) — completing Sprint 3's close
Reviewed `demo/run_demo.py` adversarially (my own standing habit). One narrow, non-blocking observation: `_call_guard()`'s `subprocess.run(..., check=True)` would raise an uncaught `CalledProcessError` if `scalene-guard` ever exited non-zero (Sprint 4's new fatal-exit path, STORY-1004) — the demo only handles the "decision != allow" case gracefully, not a machinery-failure exit. In practice this can't trigger: the demo always uses a fresh tmp dir, so the scan cache is never corrupted (missing ≠ corrupted — `ScanCache._read()` returns `{}` for a missing file, no error). Pre-existing shape, orthogonal to Sprint 3's actual scope, not worth a fix round for a local dev demo script. **APPROVED.**

## Task Description (prior): `*lead review phase-5-fix` (Last Scanned truncation fix)
Reviewed Neo's structural fix (full-width row instead of a 3rd squeezed column) against Trin's independent re-verification (different, longer dataset than either Neo's or Smith's own checks). Clean, correctly-scoped change — CSS height percentages (60%/40%) could theoretically clash with the other auto-sized siblings (Header/Input/Footer) in Textual's layout model, but both my own and Trin's real rendered screenshots confirm everything displays without clipping, which is the authoritative check here, not CSS-semantics reasoning in the abstract. 230/230 passing. **APPROVED.** Back to Smith to re-run her gate.

## Task Description (most recent): `*lead review phase-5` (Sprint 4, STORY-1005)

## Progress
- [x] Read `monitor_data.discover_scan_results()`/`monitor_app.py`'s new panel against §13.6 — matches exactly, reads the real cache store via `ScanCache.all_entries()`, no parallel bookkeeping
- [x] Reviewed my own §4 class-diagram rewrite (Neo closed my 3x-carried-forward note this phase) for accuracy before considering it done: caught that I'd represented `resource_verifier.evaluate()` — a free function, not a class — as a plain pseudo-class box, which could mislead a reader into thinking a literal `class ResourceVerifier` exists. Fixed with a `<<module: resource_verifier.py>>` stereotype, consistent with the diagram's existing `<<interface>>`/`<<exception>>` stereotype usage.
- [x] `make test`: 223/223 passing (unaffected by the doc fix, confirmed).
- [x] **APPROVED.** Handing to Smith for the mandatory gate.

## Task Description (prior): `*lead review phase-4`

## Task Description (most recent): `*lead review phase-4` (Sprint 4, STORY-1004)

## Progress
- [x] Read `onboard.py`, `scan_cache.py`, `cli.py`, `cache_refresh_worker.py` against §13.4/§13.5 — matches exactly, including the file-identity normalization that keeps onboarding and live evaluation using the same cache key
- [x] Personally re-verified the exit-code fix myself (not just trusting Trin's PreToolUse-only test): confirmed live that `PostToolUse` also correctly returns exit 2 on cache corruption — consistent with the real contract's "exit 2 is non-blocking for PostToolUse but still surfaces stderr" semantics
- [x] Traced `refresh_if_needed()` → `cache.get()`/`try_reserve()` call ordering: confirmed no partial-state issue if `ScanCacheError` fires on the first call (never reaches the second)
- [x] **Non-blocking observation**: `is_fresh()`/`put()`'s direct `os.stat()` calls on a *resource's own file* (not the cache store) aren't wrapped in error handling — a theoretical TOCTOU gap (file vanishes between `os.path.exists()` and `os.stat()`) could raise uncaught. Extremely low likelihood/impact, and out of STORY-1004's specific scope (that's about the cache *store*, not a scanned resource's own filesystem entry) — not worth a fix round.
- [x] Confirmed `scg onboard`'s own CLI exit codes are correctly NOT conflated with `scalene-guard`'s hook-specific exit-2 semantics — `onboard.py` is a normal dev CLI, no Claude Code hook contract governs it, plain `return 1` on any `OnboardError` is the right, boring Unix convention there.
- [x] `make test`: 210/210 passing, 0 skipped.
- [x] **APPROVED.** Handing to Smith for the mandatory gate.

## Carry-forward (not new, flagged again)
`ARCHITECTURE.md` §4's class diagram is still stale (still shows `PolicyRule`/`allowlist`) — flagged at Phase 3 review, flagged again at Phase 4 handoff by Neo, still not done. Third flag. Should happen at Phase 5 or as its own small cleanup — I'll personally check this doesn't slip a fourth time.

## Task Description (prior): `*lead review phase-3`

## Task Description (most recent): `*lead review phase-3` (Sprint 4, STORY-1002/1003)

## Progress
- [x] Read `resource_verifier.py` + both `hook_adapter.py` call sites against §13.1/§13.1.1 — confirmed `MatchResult` shape and `MaskingEngine.decide()`'s content-gating logic are genuinely untouched, exactly as the architecture specified this swap should work
- [x] Confirmed `ScanCache(cache_path)` construction is fresh-per-hook-invocation (no daemon, matches §2's stateless-process-per-hook-call principle)
- [x] **Structural observation (non-blocking, documentation-worthy)**: `resource_verifier.evaluate()` hardcodes exactly two scanner names (`_FILE_SCANNER_NAME`/`_URL_SCANNER_NAME`) mapping to the two fixed `MatchResult` dimensions (sensitivity/trust) — STORY-1002's "adding a scanner is adding an entry, no dispatch code changes" AC holds for the detection/registry layer (`SCANNERS` dict, `identify()`/`scan()`) but NOT for this aggregation layer. A 3rd scanner type would need someone to explicitly decide which `MatchResult` dimension(s) it affects — inherently a human design call given `MatchResult`'s shape is fixed at 2 dimensions, not something "just add a registry entry" can resolve automatically. Not a regression (implicit since Phase 1's registry design), but worth a one-line `ARCHITECTURE.md` §13.2 clarification so a future contributor doesn't assume full dispatch-free extensibility exists at this layer.
- [x] Reviewed Trin's independently-confirmed onboard-suggestion regression myself — agree it's real and significant, not overstated. This is the exact "copy the command, run it, it works" promise that's been gated and re-verified twice already (Sprint 1 UX consult, Sprint 3 Gate 1/2) — from a real user's perspective this is one atomic feature now partially broken, even though internally it's cleanly split across two sequenced phases. **My recommendation for Smith to weigh, not a decision I'm making unilaterally**: this needs her explicit call on whether Phase 3 is shippable with this window open, or whether it should block until Phase 4 closes it.
- [x] `make test`: 200/200 passing, 1 documented skip.
- [x] **APPROVED.** Handing to Smith for the mandatory gate (task.md: "this is the phase where a real behavior/copy change becomes user-visible").

## Resolution (2026-07-14)
User chose "accept the cost, revise the NFR" over the other two options (batch spawns, decouple from sync hot path). Updated both docs to be honest about the real cost rather than let Phase 3's perf test discover it as a surprise:
- `docs/ARCHITECTURE.md` §13.3: split the NFR into `NFR-Perf-Steady-State` (<15ms, unchanged, cached/fresh path) and `NFR-Perf-FirstSighting` (new, provisional **<25ms added latency per newly-identified resource**, headroom over the measured ~16ms worst case) — explicitly flagged for Phase 3 task 3.4 to verify with a real test, not assume.
- `docs/PRD.md`: Sprint 4 Goal 13 and the top-level <15ms success metric both annotated with the 2026-07-14 exception and a pointer to §13.3.
- Deliberately did **not** redesign `refresh_if_needed()`'s spawn mechanism (batching/decoupling) — the added cost is one-time-per-resource and self-amortizing (every subsequent call on that resource falls back to the free steady-state path), judged not worth the added design complexity given the user's choice.

## Task Description (most recent): `*lead review phase-2` (Sprint 4, STORY-1003)

## Progress
- [x] Read `scan_cache.py`/`cache_refresh_worker.py` against §13.3 — key format matches the literal `f"{scanner_name}:{resource.identity}"` formula (correctly resolved, not the illustrative-but-inconsistent JSON example I flagged after Phase 1)
- [x] Found a real (if bounded) robustness gap myself: `cache_refresh_worker.py`'s `try/except` wraps `scanner.scan()` but not the subsequent `ScanCache.put()` call — confirmed live with a mocked `OSError` on `put()`, the exception propagates uncaught out of `main()`. Bounded impact: this is a detached background worker, so its crash never reaches the parent's already-returned response; practical effect is just that one resource sits in its 5-minute pending-reservation window before self-healing on the next lookup. **Non-blocking** — flagged for Phase 3/4 hardening, not a Phase 2 rejection.
- [x] **Major finding — personally verified the "zero-added-latency" claim from my own §13.3 design and found it does NOT hold**: measured `refresh_if_needed()` on brand-new (never-cached) resources at ~6.6ms avg / ~16ms max per call. Isolated the cause: it's `subprocess.Popen()`'s own spawn-call cost in a fire-and-forget pattern (not waiting between spawns) — reproduced the same ~3.6ms avg / ~19ms max with a trivial no-op command, ruling out the worker script's own complexity as the cause. This is real process-creation cost in this environment, not a measurement artifact.
  - **Why this matters**: §13.3's entire non-regression argument for the "new resource" path rests on it being "identical to today's fail-safe-default behavior... zero-latency." It isn't — it's up to ~16ms of *added* latency on top of whatever `pre_tool_use` already costs (~6ms per Trin's Sprint 1 informal check), which alone could exceed the existing <15ms hot-path NFR on a single first-sighting call, before even accounting for multiple never-seen resources in one call (e.g. a `Bash` command with 2 paths + 1 URL = 3 separate spawns, compounding).
  - **Not a fresh surprise** — this is precisely the risk Smith's Gate 2 watch-item and task.md's Phase 3 task 3.4 ("re-verify <15ms NFR... not assumed compatible") already anticipated. My measurement turns that from a flagged-but-unverified risk into a confirmed, quantified one, which changes Phase 3 from "verify it's probably fine" to "this needs an actual design decision before wiring into the hot path."
- [x] `make test`: 195/195 passing
- [x] **APPROVED** (Phase 2 delivered exactly its own scope correctly) **with the latency finding escalated to the user before Phase 3 begins** — this isn't a formal Smith gate, but building Phase 3 on a performance premise I've now personally disproven risks a lot of wasted downstream work.

## Task Description (prior): `*lead review phase-1` (Sprint 4, STORY-1001/1002)

## Progress
- [x] Read `src/scalene/scanner.py` in full against §13.2's spec — `Scanner` Protocol, `Resource`/`ScanResult` dataclasses, `SCANNERS` registry all match the architecture literally (field names, registry shape)
- [x] Confirmed extensibility AC (STORY-1002): adding a 3rd scanner is only a `SCANNERS` dict entry, no dispatch code elsewhere references `FileScanner`/`URLScanner` by name
- [x] Independently adversarially probed `identify()`/`scan()` myself before approving (my own standing habit, not just trusting Trin's UAT): mixed non-string arg values (int/None/bool alongside strings), empty args dicts, empty-string known-field values — all degrade cleanly, no crash, no spurious resource
- [x] Reviewed Trin's finding + Neo's fix (URL/path collision — every `WebFetch` call was producing a bogus file resource) — the fix (span-exclusion against a full-URL regex) is structurally sound, not a patch that just moves the bug; confirmed it handles the general case (arbitrarily many `/segments` in a URL path), not just the one repro string
- [x] **Confirmed a design note Neo already self-flagged holds up under review, not a fresh finding**: `FileScanner.scan()`/`URLScanner.scan()` never raise — any `run_scanner` failure (real finding *or* scanner-machinery breakage) collapses into a `ScanResult` label. §13.2's docstring implies scan() raising is *one* of STORY-1004's two fatal triggers (the other being cache-store corruption, unrelated to scan()). Since `run_scanner`'s existing `{"ok": bool, "reason": str}` contract (Sprint 1, unchanged) doesn't distinguish "finding" from "infra failure" either, this isn't a Phase 1 regression — it's a pre-existing ambiguity Neo faithfully preserved and correctly deferred to Phase 4, not silently swallowed. Confirmed it's captured in Neo's `next_steps.md` so Phase 4 doesn't rediscover it from scratch.
- [x] Confirmed no `hook_adapter.py`/`policy_config.py` changes leaked into this phase — `scanner.py` is genuinely standalone, matches Phase 1's scope exactly
- [x] `make test`: 176/176 passing
- [x] **APPROVED.** No Tank/Smith gate needed (internal component, correct per task.md).

## Task Description (prior): `*lead arch sprint` (Sprint 4), following Smith's Gate 1 approval on Cypher's E10 stories (STORY-1001 through 1005).

## Progress
- [x] Resolved Cypher's explicit open question: **full replacement** of `PolicyConfig.allowlist`/`PolicyRule` (the tool/jsonpath/pattern/target model shipped one commit before this epic), not coexistence — the defect this epic fixes is structural to pattern-matching itself, keeping it around anywhere would leave the hole open on that path.
- [x] Designed `Scanner` protocol + registry (`identify()`/`scan()`), `Resource`/`ScanResult` types — extensible per STORY-1002, reused existing `FileScanner`≈`secrets_scan.py`/`URLScanner`≈`LocalHeuristicChecker` logic rather than rewriting it
- [x] Decided Bash gets no dedicated scanner type — its command string is fed into FileScanner's and URLScanner's existing generic-fallback detection instead of duplicating shape-detection regexes in a third scanner
- [x] Designed the scan cache (`.scalene/scan_cache.json`, `filelock`-protected like `taint_state.py`) and its 3-state lookup table (none/fresh/expired) per STORY-1003 — confirmed the "new resource" path adds zero latency (identical to today's fail-safe-default behavior) since it never blocks on a scan, only seeds the cache in the background
- [x] Designed "background" as a detached `Popen` (no `.wait()`) subprocess, consistent with the existing SCALENE_BYPASS isolation pattern — no daemon introduced
- [x] Confirmed `mtime`-only staleness for files (no hashing) per explicit user direction
- [x] Re-scoped `scg onboard` to pre-seed the cache (drops `--tool`/`--jsonpath`/`--pattern`/`--description` entirely) rather than writing a policy rule
- [x] Specified the fail-safe-exit-0 vs fatal-exit-nonzero boundary precisely (STORY-1004): ordinary scan findings stay exit 0; only scanning-*machinery* failure (cache store broken, scanner crash) is fatal. Provisional exit code 1, explicitly flagged for Neo to verify against the real Claude Code hook contract before shipping — not assumed, same lesson as the earlier schema fix
- [x] Documented exactly how this integrates with the unchanged `MaskingEngine.decide()` content-gating path (§13.1.1) — two different checks, only one is being replaced
- [x] `scg monitor` gets a new resource-cache panel (STORY-1005), same poll-based pattern as existing panels
- [x] Flagged §4's class diagram as stale-until-implementation (predates §13, will need a real update once Neo's classes exist)

## Progress (plan review, 2026-07-14)
- [x] Verified Mouse's 5-phase breakdown matches §13 exactly: scanners → cache → hook integration → onboard/monitor consumers, correctly hard-dependency-ordered (not foundational-but-parallel like Sprint 3)
- [x] Verified Smith gate placement (Phases 3-5 gated, Phases 1-2 not) matches expectation — Phases 1-2 are internal, no user-facing surface yet
- [x] Verified both Smith Gate 2 watch-items (dedup, perf re-verification) and my own devops note (orphaned processes) are folded into named tasks (2.3, 3.4, folded into Phase 2 exit criteria), not left as loose prose
- [x] Confirmed no Tank phase needed
- [x] **APPROVED. Sprint 4 plan LOCKED.**

## Blockers
None — handed Phase 1 to Neo.

## Oracle Consultations
None yet

---
*Last updated: 2026-07-14*
