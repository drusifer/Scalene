# Agent Local Context: Tank

## Recent Decisions
- **Sprint 9 (E15) Phase 3 review (2026-07-21)**: `*devops review phase-3` — first real Tank invocation in this project. Blocked the phase rather than approving: URLhaus's host-lookup API (chosen by Morpheus's §18.3 specifically because it was documented as keyless) now requires an `Auth-Key` in practice, verified via direct `curl`, not assumed from docs. Traced the real production consequence through `reputation.py`'s actual code (not just the failure mode in the abstract): every real call degrades to local-heuristics-only, permanently, since the response never carries a `query_status` field the code checks for. Found a genuinely keyless alternative (URLhaus's recent-URLs CSV feed) but flagged it needs a real redesign, not decided to implement it myself. Gave 3 options to Morpheus/Cypher without picking one — this is a product/architecture trade-off (setup friction vs. real coverage vs. reduced scope), not purely an infra call.

## Key Findings
- **`requests` is not a project dependency** (`pyproject.toml`: pyyaml, jsonpath-ng, filelock, detect-secrets only) — my own operational guideline's "requests over urllib" resolution order only applies when requests is already present; for a single simple POST+JSON call with no existing HTTP library in the project, stdlib `urllib` is the right, minimal-footprint call, not a violation to flag.
- This project's `scan_worker.py`/`subprocess_isolation.py` boundary (STORY-601) is the existing isolation mechanism for anything scanner-related, including outbound network calls (per Morpheus's §18.3 design) — no new isolation mechanism needed for external reputation checks, they run inside the existing spawned-subprocess boundary.

## Important Notes
- This project has no CI/CD pipeline, render.yaml, or deploy config yet (confirmed by absence in prior sprint history) — my role so far has been infra/external-dependency review at the sprint-gate level (Cypher's stories tag Tank-relevant items explicitly), not pipeline/deploy ownership. No pipeline work exists to keep in sync yet.
- Prior sprints (E10/E11) explicitly avoided any external network dependency for v1 (§7.4/STORY-501: "no paid external API in v1... LocalHeuristicChecker... no network call"). E15/STORY-1503 is the first time this project introduces a real outbound network dependency — treat any future scanner/reputation work with the same scrutiny (verify the real endpoint behavior directly, don't trust vendor docs at face value) given this is a newly-established pattern, not a mature one.

---
*Last updated: 2026-07-21*
