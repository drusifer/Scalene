# E19 Gate 1 — User Story Review (OLOY Mode), 2026-11-20

**Verdict: REJECT (1 required fix), then re-review.**

Evaluated STORY-1901..1904 against Nielsen's heuristics, and probed the real `oloy_enabled()` rather than reasoning about it.

## Required fix
**STORY-1901 AC3 — silent failure on an unrecognized `SCALENE_OLOY` value (H9 error recovery, H5 error prevention).**
Real probe: `SCALENE_OLOY=enable` → OLOY stays off, no message anywhere. `1/true/TRUE/yes/ on ` → on. The AC as written ("any other value defers to the file") makes that silent fallback the *specified* behavior. A user who types a plausible-but-unlisted value believes OLOY is on and has no way to find out it isn't.
FIX: AC must (a) list the exact accepted values (on: `1/true/on/yes`, off: `0/false/off/no`, case/whitespace-insensitive) — matching what the docs say — and (b) require an unrecognized non-empty value to fall back to the file setting *and* emit a visible warning naming the bad value and the accepted ones.

## Non-blocking notes
- STORY-1904: counts only appear once OLOY has decided something; before the first decision a user can't tell OLOY is on. Acceptable for this sprint (the decisions are what matter), noted for retro.
- STORY-1902: good that the restricted-session message must drop "wait for review" — wrong guidance there would cause pointless retries (H2).
- STORY-1903: masking a path-like field would break the call in a confusing way — rightly left to Morpheus (open question 2), but the answer must be explicit in the arch.

## Re-review (same day)
STORY-1901 now lists the exact accepted values and requires a warning on anything else. Required fix resolved. **APPROVED.** Non-blocking notes stand, carried to arch/retro.
