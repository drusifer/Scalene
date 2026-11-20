# E19 Gate 2 — Architecture Review (OLOY Mode, ARCHITECTURE.md §24), 2026-11-20

**Verdict: REJECT (1 required fix), then re-review.**

## Required fix
**§24.1 — the "visible warning" goes to a channel nobody sees (H1 visibility, H9 error recovery).** Real check: no logging is configured anywhere in `src/scalene`, so `logger.warning` falls to Python's last-resort stderr handler; Claude Code only surfaces a successful (exit 0) hook's stderr in verbose mode. Ran `SCALENE_OLOY=enable scalene-guard` live: the JSON response is byte-identical to a normal allow. The Gate 1 fix would be satisfied on paper and invisible in practice.
FIX: put the warning in the hook response's `systemMessage` (the user-visible field `_pre_tool_use_response` already uses), on every call until the value is fixed. Repeating it is right here: it's a security tool misconfiguration, and the fix is one env var. The permission decision itself must still not change.

## Approved as designed
- §24.2 scan budget: overflow message tells the agent to retry shortly. Correct guidance, because the retry will actually succeed once the background scan lands (H9).
- §24.3: excluding `file_path`/`url` from masking prevents a confusing broken call (H5).
- §24.4: summary on the existing session line, empty for non-OLOY users. No new navigation, no noise for anyone else (H8). Counts use the same words as the stories (cleared/masked/blocked) (H4).

## Re-review (same day)
§24.1 now delivers the warning via `systemMessage` and keeps it from replacing a block/mask reason. Required fix resolved. **APPROVED.**
