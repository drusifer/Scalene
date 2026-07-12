# Bug 2026-07-10-004: `via`-mandatory rule bypassed 13× despite being enabled and available

**Severity**: P3
**Filed by**: Smith
**Route to**: Bob (prompt reinforcement)

---

## Reproduction

`agents/trin.docs/judge_20260710_trace.md`, `AP-VIA-GREP` (6) + `AP-VIA-READ` (7) instances — raw `grep`/`Read` used for symbol/relationship lookups (e.g. `grep -n "class TaintState\|def \|@\|self\." src/scalene/taint_state.py`) instead of `mcp__via__via_query`.

## Expected

`agents/PROJECT.md` states `via: enabled`. Both Neo's and Trin's `SKILL.md`s state this is mandatory: "Raw File-Reads and Grep Fallbacks are Forbidden... MUST NEVER perform fallback file-reading or grep searches to locate symbols." `mcp__via__via_query` was present in the toolset during these sessions.

## Actual

13 real bypasses across the session — lower volume than bug 003 but the same underlying pattern: a specific, already-written rule not applied at the point of use.

## Root Cause

Same class of gap as bug 003 — not a documentation problem, a recall/enforcement problem.

## Recommended Fix

Route together with bug 003 — likely the same mechanism fix applies to both (e.g. a lightweight self-check Trin runs before signing off UAT, rather than more SKILL.md prose).
