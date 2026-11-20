# E19 Sprint-Close End-to-End Test (OLOY Mode), 2026-11-20

**Verdict: PASS.** Followed `docs/USER_GUIDE.md`'s OLOY section literally in a fresh project, using real `scalene-guard` calls.

1. OLOY off (default): after a taint, a read of an outside file is denied ("no explicitly-allowed rule"). Unchanged default behavior.
2. Added `defaults: oloy: true` as the guide shows, in a new session: the same read is allowed (auto-cleared).
3. `SCALENE_OLOY=0` overrides the file: denied again.
4. `SCALENE_OLOY=enabled` (a typo): decision unchanged, and the `systemMessage` names the bad value and the accepted ones.
5. `scg monitor --help` unchanged. The session-line summary was already verified with real screenshots at the Phase 3 gate.

Carried to retro (non-blocking): the 80-col wrap splits the trust/sensitivity parens; there's no "OLOY on" indicator before the first OLOY decision.
