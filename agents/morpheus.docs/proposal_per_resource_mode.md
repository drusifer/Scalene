# Proposal: per-resource `mask`/`block` at onboard time (2026-07-17)

## The user's proposal
Add a property to onboarded resources (currently: just a `label` — `trusted`/`public`/etc. in the scan cache) for `mode: mask | block`, settable via `scg onboard`, so the mask-vs-block decision can be made per-resource instead of via the single global `defaults.mode` in `scalene_policy.yaml`.

## Why this isn't a trivial bolt-on
`MaskingEngine.decide()` (`src/scalene/masking.py`):

```python
provenance_risk = taint.has_sensitive_data and taint.has_untrusted_data and not match.is_trusted
if not provenance_risk or value is None:
    return Decision(action="allow")
findings = tuple(scan_text_for_secrets(str(value)))
...
```

Today, `is_trusted=True` (i.e. `scg onboard`-ed) makes `provenance_risk` False, which means **the content scan never runs at all** for that destination — not "runs and is treated leniently," genuinely skipped. This is deliberate (§13.1, and the demo we just extended specifically to show it): trust is an *exemption from scanning*, not a softer verdict on a scan that still happens.

Given that, a per-resource `mode` property attached to a *trusted* resource would never actually fire — there's no detection event left for it to act on. For the proposal to mean something, one of two structural changes is needed:

**Option A — trust becomes classification-only, always scan.** Remove the `not match.is_trusted` short-circuit; `is_trusted` still feeds provenance risk, but content-scanning always runs regardless. The per-resource `mode` then governs what happens on a real finding, even for "trusted" destinations. This is a real architecture change — it removes the performance/friction optimization Sprint 4 (E10) was specifically built around (§13.3's "no added latency for the cached path" reasoning partly rests on skipping the scan, not just skipping a mask). Trust becomes a weaker guarantee (always checked) but a more granular one (fine-tunable response).

**Option B — a new, distinct onboarding category.** Keep `trusted` meaning exactly what it means today (skip-scan fast path). Add a separate category — something like "acknowledged, still scan" — that does *not* skip content-scanning, and carries its own `mode` preference for when a finding occurs there. `trusted` stays the fast/exempt path; the new category is for "I know this destination is a bit risky, I still want the agent to be able to use it, but let me control what happens if something real shows up." Additive, doesn't touch existing semantics or the cached-path performance story.

## My read
Option B fits the existing design intent more cleanly — it doesn't quietly weaken the guarantee `trusted` currently makes, and it's the more honest match for what I think the user's actual use case is (differentiated *response*, not identical trust). Option A is the more powerful/general version but is a real regression on the latency/friction reasoning this whole epic was built on, and changes what "trusted" has meant since Sprint 4.

Not deciding this alone — this is exactly the kind of thing that should get Cypher's requirements framing (is this a new story, and what's the actual scenario driving it?) before I lock in a schema change, especially since it touches the scan cache's on-disk format (`.scalene/scan_cache.json`) and `scg onboard`'s CLI surface, both of which just stabilized in Sprint 4.
