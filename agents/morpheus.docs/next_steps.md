# Next Steps

## Immediate Next Action
Waiting on the user's direction on the per-resource `mask`/`block` proposal (Option A: always-scan-and-weight vs. Option B: new additive category vs. something else). Do not start implementation or a formal architecture doc until that's resolved — this is still at the "is this the right shape" stage, not locked.

## Waiting On
User (direction on the proposal) → possibly Cypher (requirements framing, is this a new story) → then a real architecture pass if it proceeds.

## Planned Work
- [ ] If the user picks a direction: write it up properly (likely a new `docs/ARCHITECTURE.md` §14 or an addendum to §13, since it touches the same scan cache / resource-verification system) rather than just coding it ad hoc — this changes an on-disk format and a CLI surface that only just stabilized.
- [ ] If Option A (always-scan) is chosen: need to re-verify the latency/NFR story again (same "measure, don't assume" discipline as Phase 2's finding this sprint) — removing the scan-skip for trusted resources could reintroduce the exact cost Phase 2 was built to avoid for cached/trusted paths.
- [ ] If Option B (new category) is chosen: need a clear name for it distinct from "trusted" — placeholder used in the proposal doc ("acknowledged, still scan") is not a real proposed name, just descriptive.

---
*Last updated: 2026-07-17*
