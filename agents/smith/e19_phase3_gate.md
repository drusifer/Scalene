# E19 Phase 3 Gate — OLOY monitor visibility (mandatory), 2026-11-20

**Verdict: APPROVED. 1 non-blocking finding.**

Method: a real scratch project. Six real `scalene-guard` calls with `SCALENE_OLOY=1` (an untrusted fetch; a hardcoded-restricted read; a new-file read; a project-folder read; a secret in a Bash payload; a secret-bearing file). Then the real `MonitorApp` rendered against that real audit log via `export_screenshot()`, converted to PNG and inspected: `e19_phase3_monitor_130.png`, `e19_phase3_monitor_80.png`.

- **H1 visibility:** the session line reads `OLOY: 2 cleared · 1 masked · 2 blocked`, which matches the six calls exactly. The project-folder read is correctly a rule allow, not an auto-clear. It's visible without navigation.
- **Queue:** "No pending reviews." Both OLOY blocks stayed out of the queue, as STORY-1904 requires. Read with the summary, it's not misleading: the 2 blocks are counted right above.
- **H4 consistency:** same ` · ` separator and lowercase status words as the scanner strip.
- **80x24:** with a real-length UUID session id, the line wraps to 2 rows. Nothing is clipped, and the queue, status strip, and footer are intact.
- **Agent-facing messages** (live): block reasons say "Do not retry"; the mask reason names the field.

## Non-blocking
- At 80 cols the wrap falls inside `(trust=low, sensitivity=…)`. Cosmetic; candidate for retro (e.g. put OLOY on its own line when narrow).
