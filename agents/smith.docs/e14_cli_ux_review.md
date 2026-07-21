# Smith CLI UX Review — `scg onboard` (Sprint 8/E14, retroactive)

**Prompted by:** user feedback (2026-07-21) that Smith's reviews should critique CLI ergonomics directly — arg naming, defaults, ease of use — not just verify a feature works and is discoverable. My Gate 1/2/mandatory-gate reviews focused on the confirmation flow's discoverability and non-interactive escapes; this pass looks at the interface design itself.

## Findings

### 1. `--scanner` means two different things depending on `--list` (HEURISTIC #4, Consistency and Standards)
```
SURFACE: --scanner
EXPECTED: a flag name means the same thing everywhere it's accepted
ACTUAL: in the onboarding flow, --scanner disambiguates which scanner a rule belongs to (rare — "usually inferred"); with --list, --scanner is a filter selecting which scanner's inventory to show (the common case for --list). Same name, unrelated role, distinguished only by which other flag is present.
IMPACT: a user who's used --scanner one way has to re-learn it the other way; --help shows both meanings crammed into one line ("Optional disambiguating scanner name (usually inferred); also filters --list"), which is a tell that one flag is doing two jobs.
FIX: rename one. --list's filter is the more commonly-used of the two — consider a positional argument (`scg onboard --list reputation`) or a distinctly-named flag (`--filter-scanner`), leaving `--scanner` for its original, rarer rule-authoring role.
VERDICT: Concern (non-blocking, already shipped) — real, worth a follow-up.
```

### 2. Interactive "select" asks what to exclude, not what to include (HEURISTIC #7, Flexibility and Efficiency)
```
SURFACE: the [Y/n/s(elect)] confirmation prompt's 's' path
EXPECTED: the common case (a call identifies several candidates, the user wants only one or two of them) should require the least typing
ACTUAL: 's' asks "Enter numbers to exclude" — if a Bash command identifies 5 targets and the user only wants 1, they must type 4 numbers to exclude, not 1 to include
IMPACT: the interaction model is optimized for the "drop a couple of stragglers from a mostly-wanted list" case, but the more likely real case (per this project's own examples — a multi-path Bash command with one actual intended target) is "pick 1-2 out of several."
FIX: ask which numbers to *include* instead (or offer both, defaulting to whichever is empirically more common). This doesn't affect --only, which already lets a script name an inclusion list directly — only the interactive sub-prompt has this asymmetry.
VERDICT: Concern (non-blocking, already shipped) — real, worth a follow-up.
```

### 3. Omitting one of `--sensitivity`/`--mode` defaults toward the *permissive* choice (HEURISTIC #5, Error Prevention)
```
SURFACE: --sensitivity/--mode defaulting
EXPECTED: given this project's own established posture elsewhere (sensitive_by_default: true, untrusted_by_default: true — restrictive unless proven otherwise), an omitted onboarding axis defaulting the *other* direction would be more consistent
ACTUAL: omitting --mode defaults it to 'allow' (the more permissive of the two); omitting --sensitivity defaults it to 'public' (the least restrictive of three). Both defaults lean permissive, not restrictive.
IMPACT: a user who only thinks to specify one axis (e.g. "--mode allow" because they're clearing a block) gets sensitivity: public without having considered it — the least-restrictive value, silently.
VERDICT: Concern, not a clear defect — this default direction was a conscious sec16 decision (carried into sec17 unchanged), not new to this sprint, and there's a real counter-argument (onboarding a resource you're actively clearing is usually for something ordinary, so 'public' is often correct). Flagging explicitly rather than letting it pass as an unexamined carry-forward — worth a deliberate yes/no from the team, not silent inheritance.
```

## Not filed as bugs
These are UX refinement opportunities on an already-shipped, working, gated feature — not correctness defects, not violations of any hard requirement from this sprint's gates. Routing to Cypher's backlog (not Trin's fix-loop) since nothing is broken; a future tech-debt sprint can pick up whichever of these the team wants to act on.
