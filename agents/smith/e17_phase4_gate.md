# `*user test` Phase 4 — E17 Rules Screen & Reordering (mandatory gate)

Per task.md: Phase 4 carries a required Smith gate — new screen with real,
write-on-use access-control consequences, the concern I raised back in the
original consult (`e17_monitor_queue_first_consult.md`: "reordering has
live access-control consequences the instant it's written... wants a
visible confirmation/toast on write, not a silent same-tick rewrite").

## My original concern, checked against the real shipped code

Traced `RulesScreen._move()`: `swap_rule_order()` (the write) and
`self.query_one("#rule-confirm", Static).update(...)` (the confirmation)
happen in the same synchronous method call, in that order, with
`refresh_rules()` re-reading the real file in between. There is no `await`
or scheduled callback between the write and the confirmation — Textual's
single-threaded event loop means no other key event can be processed
between them. This is genuinely synchronous, not "fires quickly after."
STORY-1705's hard AC ("before the next input is accepted") is satisfied by
construction, not by timing luck.

## Discoverability, checked for real

`k`/`j`/`escape` are declared via `BINDINGS` with human-readable
descriptions ("Move rule up"/"Move rule down"/"Back to queue") — Textual's
`Footer` widget renders these automatically, same mechanism every other
screen in this app already relies on for key discoverability (Nielsen #6,
recognition rather than recall). Not a hidden shortcut only found by
reading source.

## Real end-to-end AC, re-run myself

`test_reordering_via_the_real_screen_changes_which_rule_a_real_hook_call_
resolves_with`: a genuine 2-rule conflict (broad allow before specific
block), a real `pre_tool_use` call before reordering resolves `allow`,
reorder through the actual `RulesScreen` (key presses, not a direct
`swap_rule_order()` call), the identical call after resolves `deny`. This
is the story's own hard AC, and it's exercised through the real UI
surface, not just the underlying function in isolation.

## Nielsen #1 gap Trin found and closed

An empty rules table had no explanation — checked the fix
(`#no-rules`, same `display:none`/`.visible` pattern `#no-queue` already
established in Phase 1) and its test. Consistent with this app's own
established convention, not a one-off.

## Verdict

**APPROVED.** My one real concern from the original consult is closed with
verified evidence (synchronous ordering, not assumed), not just a claim
that it's fixed. 512/512 tests. This closes Phase 4 — all 4 implementation
phases of E17 are now complete. Handing to Oracle for docs groom, then my
own end-to-end sprint-close pass.
