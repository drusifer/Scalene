# Tank — `*devops review phase-3` — Sprint 9 (E15) — 2026-07-21

## What I was asked to verify
Per Cypher's original story flag and Morpheus's §18.3 design: confirm URLhaus's host-lookup endpoint genuinely needs no API key (stated as the specific reason this source was chosen), and assess timeout/rate-limit/volume safety.

## Finding: the "no API key required" premise is false in practice — confirmed against the real endpoint, not assumed from docs

```
$ curl -s -X POST https://urlhaus-api.abuse.ch/v1/host/ -d "host=example.com"
{"error": "Unauthorized"}

$ curl -s -X POST https://urlhaus-api.abuse.ch/v1/host/ -H "Auth-Key: test" -d "host=example.com"
{"query_status": "unknown_auth_key"}
```

The host-lookup endpoint (`_URLHAUS_HOST_ENDPOINT` in `reputation.py`) now requires an `Auth-Key` header — abuse.ch added mandatory authentication to this API at some point after §18.3 was designed against its (evidently outdated) public documentation. This is not a network flakiness/rate-limit case `composite_check()`'s degrade-path was built for — it's a permanent, structural failure.

**Real consequence, traced through the code, not hypothetical**: `URLHausChecker.check()` calls `_query_urlhaus()`, gets back `{"error": "Unauthorized"}` (no `query_status` key at all), so `payload.get("query_status")` is `None`, which falls through to `raise ReputationCheckUnavailable(...)`. `composite_check()` catches that and degrades to local-heuristics-only. **In production, today, as merged, this means STORY-1503 never actually checks anything against a real external source — every single call silently and permanently degrades**, which defeats the story's own stated purpose ("so a genuinely malicious or newly-registered domain has a realistic chance of being caught"). The degrade path itself works correctly (that's real, tested code) — but it would be the *only* path that ever executes, forever, which is not what got approved at Cypher's Gate 1 or Morpheus's architecture review.

## A genuinely keyless alternative exists, but needs a different design
```
$ curl -s -o /dev/null -w "%{http_code}\n" https://urlhaus.abuse.ch/downloads/csv_recent/
200
```
URLhaus's recent-URLs CSV feed is real, public, and keyless — but it's feed-based (download + check membership), not a per-host query, so `URLHausChecker` as currently written can't just swap the endpoint; it needs a real redesign (fetch/cache the feed, check host/URL membership against it, handle feed staleness). That's implementation work for Neo, gated on an architecture decision, not something I should silently rewrite myself.

## Recommendation (not deciding unilaterally — flagging for Morpheus/Cypher)
1. **Get a real URLHaus Auth-Key** (free, requires signup) and store it as an env var (e.g. `SCALENE_URLHAUS_AUTH_KEY`), documented in `.env.example`, never hardcoded/committed. Preserves the "free tier" framing from Cypher's story but changes it from zero-config to a documented one-time setup step — a real scope/UX change Smith should weigh in on.
2. **Switch to the keyless CSV feed** instead — no credential needed, but real design work (feed fetch/cache/membership-check), and "recent URLs only" is a narrower coverage window than a live host query.
3. **Ship Phase 3 as pure degrade-to-local for now**, explicitly labeled as such (not silently), if the team wants to defer the credential/redesign decision — but then STORY-1503's actual AC ("consults at least one real external...source") isn't met, and that should be said out loud, not quietly accepted.

## On the `urllib` vs `requests` question (my own operational guideline, item 9)
Checked: `requests` is not currently a project dependency (`pyproject.toml`: pyyaml, jsonpath-ng, filelock, detect-secrets only). My own guideline's example ("`requests` was already present") doesn't apply here — there's nothing already in this project to reuse. Given this project's repeatedly-stated minimal-dependency posture (§7.4/STORY-501's same reasoning), stdlib `urllib` for one POST+JSON call is the right call, not a violation worth flagging. Noting this override explicitly rather than silently deviating from my own stated resolution order.

## Verdict

**BLOCKED — not approved as-is.** This is a real, structural problem with the chosen data source, not an infra nitpick. Escalating per the standing Anti-Loop Protocol shape: root cause identified, two concrete options given, awaiting a decision rather than picking one myself or silently shipping degraded-forever code labeled as "real external verification."
