# Cypher — E15 requirements capture (2026-07-21)

## User request (source)
Two messages, both verbatim-intent captured here (first was voice-dictated, cleaned up against actual code):

1. "Time to focus on the scanners. At runtime Scalene Guard should identify its set of scanners by default — built-in scanners will be loaded but there will be an option to add scanners via config for enterprise integration (asset inventory/data-labeling systems, vulnerability databases). For now we'll start with the file system scanner and the url scanner. Scanner interface has two main entry points: identify (recognize assets in a tool call's args) and scan (accepts a target asset, returns context tags). Our default FileSystemScanner will use the secret-detection logic we've already built to determine sensitivity. It'll have hardcoded defaults too — sensitive areas like /etc or the user's .ssh are always labeled restricted and untrusted. The URL scanner will detect web URLs and validate them using open source/free-tier tools. Once onboarded, an asset gets an expiration; a cache hit checks expiration and returns the cached result or forces a rescan."
2. "The default posture for a new project should be: project folder is trusted and Internal Only."

## What was already true before this sprint (verified against code, not assumed)
- `Scanner` protocol already has exactly `identify()`/`scan()` (scanner.py, since E10/STORY-1001).
- `FileScanner.scan()` already reuses the existing secrets-detection logic for sensitivity.
- 24h scan-cache expiration + rescan-on-expiry already exists (`scan_cache.py`, since E10/STORY-1003).
- These three were **not** re-storied — they're confirmations of existing shipped scope, not new asks.

## Genuinely new, written as E15 (docs/USER_STORIES.md)
- STORY-1501: config-driven `SCANNERS` registry (built-ins default-on, extra scanners registrable via config). Enterprise scanners themselves explicitly out of scope this sprint.
- STORY-1502: hardcoded restricted+untrusted defaults for `/etc`, `~/.ssh` in `FileScanner`, independent of scan outcome.
- STORY-1503: real external open-source/free-tier reputation source(s) for `URLScanner`, beyond today's 3 local heuristics. Flagged for Tank (external service call, likely API keys/rate limits).
- STORY-1504: newly onboarded project's own folder defaults to trusted + Internal Only, not the global untrusted/sensitive-by-default posture. Flagged as a deliberate, narrow carve-out against PRD Goal 5 (fail-safe defaults) — bounded to the project root, still subject to STORY-1502's override.

## Open questions carried to Morpheus (5, in USER_STORIES.md E15 section)
Registry config schema/mechanism; canonical sensitive-path list beyond the 2 named; concrete reputation source pick (+ what Tank needs to review); interaction with the still-open STORY-1405 backlog item; how "project's own folder" gets scoped/detected for STORY-1504.

## Not touched this pass
STORY-1405/1406 backlog, Smith's e14 CLI UX findings, sec5 diagram drift (all still open in next_steps.md, earmarked for "scanner sprint" generally but not part of this specific dictation — left as separate backlog items, not silently folded in).
