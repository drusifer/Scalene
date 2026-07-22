# Next Steps

## Immediate Next Action
Phase 3 (E15) fully closed on the engineering side (2026-07-21) — my Auth-Key finding was resolved by a real code fix (env-var-gated, no hardcoded secret), re-verified. Nothing in-flight for Tank right now — no Tank task in Phase 4 (project-folder default, no new infra/network/env-var surface there).

## Waiting On
Nothing immediate. If a future phase/sprint touches deploy config, CI, or new services, that's when I re-engage.

## Follow-up, not blocking, for whoever eventually deploys this for real
Confirm one real, successful authenticated URLhaus call with an actual `SCALENE_URLHAUS_AUTH_KEY` (obtained via human signup at `https://auth.abuse.ch/`) — I couldn't do this myself. Until then, production behavior with the key unset is honest (clean degrade to local heuristics), just not the "real" external check STORY-1503 intended.

## Standing notes for future Tank invocations
- This project has no CI/CD pipeline or deploy config yet — first real infra surface was E15's external network dependency.
- Verify vendor API claims (auth requirements, rate limits, endpoint shape) directly against the live service, not just documentation, before approving — this is exactly what caught the Auth-Key gap here.

---
*Last updated: 2026-07-21*
