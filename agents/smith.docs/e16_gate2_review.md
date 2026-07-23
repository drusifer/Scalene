# `*user feedback` Gate 2 — E16 (2026-07-22)

Reviewing `docs/ARCHITECTURE.md` §20 against my Gate 1 hard-requirement
watch-items and general UX impact.

## Gate 1 watch-items — both landed

1. **STORY-1606's concrete mechanism** — resolved better than I expected:
   §20.6 traced `onboard.write_rule`'s existing `OSError` handling and found
   it already catches `PermissionError` with a clear message, no new
   production code needed. Real remaining work (docs + a Tank verification
   task) is honestly scoped, not hand-waved as "done."
2. **Attention signal on the dashboard** — §20.4 specifies `self.bell()` +
   a pending-count in the title bar, explicitly flagged for Neo to verify
   against the real installed Textual API rather than assumed from this
   doc. Good — matches this project's own live-verification standard
   rather than repeating an assumed-API mistake.

## New item — real scope correction needs the user's own sign-off, not just ours

§20.3 correctly caught that "the tool-call log" I storied doesn't match
what's actually built (block-events only) — good catch, and the NFR
reasoning for not silently expanding to every call is sound. **But this is
a deviation from the user's own original framing** ("a scrolly log of the
tool calls," not "a scrolly log of blocked tool calls") — Morpheus flagged
it to Cypher/me, which is right, but a scope narrowing on a direct user
request should go back to the user explicitly, the same way STORY-1504's
Goal-5 tension was surfaced rather than quietly decided by the team alone.
**Not blocking Gate 2** — the architecture itself is sound either way — but
I'm carrying this forward as an explicit flag rather than treating
Morpheus's note as sufficient sign-off on its own.

## Update (2026-07-22, same session): scope-correction item resolved directly by the user

The user answered my flagged item directly rather than needing a separate round-trip: my (and Morpheus's) reasoning conflated the measured scan-spawn cost with a plain log-append cost. Corrected — STORY-1603 is back to full scope (every call, not just blocks), with a measured-benchmark AC replacing the deferral. No longer an open item.

## Verdict: Approved

Architecture is sound, both hard-requirement watch-items resolved for
real, and the one new item (STORY-1603 scope) is a flag-forward, not a
blocker. No breaking changes to existing surfaces, `AccessDecision.
block_kind` is additive, `write_rule` rename has exactly one real caller
change to audit (Trin should grep for the old `_write_rule` name to confirm
nothing else references it directly).

@Mouse for phase planning.
