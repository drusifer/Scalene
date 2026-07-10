# Backlog — Project Scalene

**Owner:** Morpheus
**Status:** Post-Sprint-1, pending Sprint 2 scope.

Items here are candidate work, not committed to a sprint. Promote into `task.md` when scoped.

---

## Category-aware PII / secrets masking library

**Origin:** User research request (2026-07-09), not yet scoped into an epic.

**Problem:** Two spots in the codebase currently do content-level detection with hand-rolled, narrow logic:
- `secrets_scan.py` (STORY-501 onboarding allowlist gate) — 3 regexes (AWS key, private-key header, generic `key=value` secret pattern). Explicitly documented as "not a full entropy/ML scanner."
- `MaskingEngine.apply_mask` (`masking.py`) — blind, category-blind: always substitutes the whole field with a single static literal `[MASKED_BY_POLICY_PROVENANCE_GUARD]`, regardless of what kind of data was in it.

**Candidate packages (researched 2026-07-09):**
- **`detect-secrets`** (Yelp) — pure Python, no network egress, ~20 plugin detectors (cloud provider keys, private keys, JWTs, service tokens, high-entropy strings), baseline workflow. Best fit as a drop-in upgrade to `secrets_scan.py` — matches the existing pure-Python dependency stack and the "isolated scan, no network" onboarding principle (`ARCHITECTURE.md` §9).
- **`scrubadub`** — lightweight general-PII redaction (email, phone, SSN, credit card, URLs, credentials); NER-based name/address detection is an optional add-on, not a hard dependency. Good if general-PII coverage is wanted without a heavier NLP footprint.
- **Microsoft `presidio`** (`presidio-analyzer` + `presidio-anonymizer`) — most comprehensive category coverage (SSN, credit card, IBAN, crypto wallets, medical/passport/license numbers, phone, IP, NER-based names/locations) and per-category masking operators (replace/mask/redact/hash/encrypt). Actively maintained (June 2026 release). Pulls in spaCy for NER-based recognizers — real dependency/latency cost.

**Architectural constraint:** none of these belong on the `PreToolUse` masking *trigger* path — that decision must stay deterministic/provenance-based per the BRD (NFR: <15ms, no semantic/NLP content inspection for the trigger). They'd only apply to (a) the onboarding-time secrets scan (already out-of-band), and/or (b) categorizing the mask literal itself for audit-log clarity after the trigger has already fired.

**Recommendation (not yet actioned):** `detect-secrets` for the onboarding secrets-scan upgrade; `scrubadub` or `presidio` only if/when category-aware masking (vs. blind masking) becomes an actual requirement.

---
*Last updated: 2026-07-09*
