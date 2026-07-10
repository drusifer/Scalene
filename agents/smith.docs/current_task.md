# Current Task

**Status:** `*user test copyable system messages` — APPROVED with one non-blocking note
**Assigned to:** Smith (impl chain complete)
**Started:** 2026-07-09

## Task Description
User asked how a developer would know how to write a `scalene onboard` JSONPath/pattern with no example to work from. Consulted (ran `onboard.py`/`hook_adapter.py`), proposed 3 ranked options (see `context.md`), user approved option #1.

## Progress
- [x] Confirmed the gap by running the software: `onboard.py` requires `--tool/--jsonpath/--pattern` fully hand-written, no discovery mechanism (Nielsen #6/#10)
- [x] Identified that `pre_tool_use` already computes the real `tool_input` at mask time and discards it (audit log only keeps `tool_name`+`payload_field`)
- [x] Proposed: extend the mask `systemMessage` (and audit log entry) to include a ready-to-run `scalene onboard` command, JSONPath pointed at the matched/payload field, pattern defaulted to an escaped literal of the real value
- [x] User approved — handed to Neo as an implementation task (test-first per project convention)
- [x] Neo implemented; Trin's UAT round 1 found a real shell-quoting bug (`--target` placeholder not `shlex.quote()`'d, broke bash on paste) — Neo fixed, round 2 passed; Morpheus approved with a non-blocking note (adapter/policy-engine layer placement)
- [x] `*user test`: piped real hook JSON through the actual installed `scalene-guard` binary (not internal functions) — systemMessage is correct, actionable, and shell-safe
- [x] Found one non-blocking wording nit: placeholder says `<domain-or-file-this-call-reaches>` but every suggestion is `--list-type trust` (domain-only per `onboard.py`'s own help text) — "-or-file" offers a choice that doesn't exist. Suggest `<domain-this-call-reaches>`. Not filing as `*user bug`/full loop — trivial one-string fix, noted for whenever Neo next touches this function.
- [x] Verdict: **APPROVED.** `*impl` chain for "copyable system messages" complete.

## Blockers
None

## Oracle Consultations
None yet

---
*Last updated: 2026-07-09*
