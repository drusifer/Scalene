# E10 (Sprint 4) Story Staleness — Flagged for Cypher

Found during Sprint 4 close doc-groom (2026-07-15). Not edited directly — Cypher owns story content; these are observations for her to act on.

## STORY-1001's premise no longer matches what was built (significant)
STORY-1001 as written: "As a developer writing policy rules, I want `pattern` to support named regex capture groups, so a rule can hand a scanner just the relevant sub-value..." — this describes a **user-facing** feature (a config `pattern` field with named groups).

What actually shipped (§13.1, a full-replacement architecture decision made *during* this sprint): there is no more user-authored `pattern`/`jsonpath` at all. Named regex captures are an **internal implementation detail** of each built-in scanner's own detection regex (`FileScanner`'s/`URLScanner`'s fallback patterns), never exposed to a developer. `docs/ARCHITECTURE.md` §13.2 says this explicitly: "not a user-facing config concept."

All 3 of STORY-1001's AC boxes are still unchecked and describe a mechanism (`pattern` with capture groups as something a developer writes) that will never literally exist as worded — the underlying *capability* (host extraction from a URL, etc.) was delivered, but not the interface the story describes. Worth rewriting the story to match what was actually decided, or explicitly marking it superseded by §13.1's decision — your call, not mine to silently rewrite.

## STORY-1003's AC has a minor precision mismatch
AC: "Cache entries are keyed by resource identity: files by `(path, mtime)`..." — implies `mtime` is part of the cache *key*. What shipped: the key is the path alone (`f"{scanner_name}:{identity}"`); `mtime` is stored as a *value* field used to check freshness, not part of the key (confirmed in `src/scalene/scan_cache.py`). The AC's *intent* (a changed file should be re-verified) is fully satisfied — `is_fresh()` checks `mtime` — but the literal wording overstates what's in the key itself. Minor, not blocking, but noting for accuracy.

## All 5 E10 story checkboxes are still unchecked
STORY-1001 through STORY-1005 all show `[ ]` throughout, even though all 5 Sprint 4 phases are implemented, UAT'd, reviewed, and gated. Worth updating at sprint close for an accurate historical record — not something I'll do myself since checking off ACs is a product/story-ownership call (are they *satisfied as worded*, given STORY-1001's divergence above, or do some need rewording first).
