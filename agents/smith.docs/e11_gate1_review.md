# Smith Gate 1 Review — E11 (Trust/Sensitivity Model & Rule-Driven Resource Identity)

**Reviewed:** `docs/USER_STORIES.md` STORY-1101 through 1105
**Verdict: APPROVE**

## Per-story notes

**STORY-1101 (host-level trust defect fix)** — AC is concrete and testable: "onboard/verify one path under a host, then confirm a second, unverified path under the same host is not treated as trusted" is a real, runnable test a user could sanity-check themselves. #5 Error Prevention: fixes a case where the system silently over-trusted without the user ever making that choice.

**STORY-1102 (trust/sensitivity split)** — #2 Match Between System and Real World: "Public / Internal Only / Restricted" reads the way a real data classifier thinks (a user already has this mental model from other tools — S3 bucket policies, IAM, etc.), not internal jargon. Good choice to cap it at exactly 3, not an open enum (#6 Recognition over Recall — nothing to memorize).

**STORY-1103 (per-rule mask|block)** — #4 Consistency: reuses the *existing* `mask`/`block` vocabulary already shipped in `PolicyConfig.mode`/`Decision.action` rather than inventing new terms for the same concept. This directly resolves the user's original request. Correctly keeps `defaults.mode` as a fallback rather than forcing every project to author a rule just to get today's global behavior back.

**STORY-1104 (unconditional baseline scanning)** — This is a behavior change a user could genuinely be surprised by (scanning now happens on calls that used to be silently skipped). AC requires a real test proving zero-config coverage, which is right, but I want the *messaging* covered too — if scanning newly fires on a call that never triggered it before, does the user get any signal (System Status, heuristic #1), or does it just silently start working? Not blocking — this is exactly the kind of thing Morpheus's architecture step should answer, and I'll test it directly at Gate 2/end-to-end regardless.

**STORY-1105 (cache migration)** — Correctly scoped to fail-safe-by-construction (#5 Error Prevention: an old-scheme entry must never be silently read as valid trust for a narrower resource). Good that this didn't get silently dropped.

## One flag for Gate 2 (not blocking Gate 1)

E10 was a real UX win: `scg onboard` dropped from `--tool`/`--jsonpath`/`--pattern`/`--description` down to a single `--target` (#7 Flexibility and Efficiency, #8 Minimalist Design — the common case got simpler). E11 reintroduces `PolicyRule`'s `jsonpath`+`pattern` at the config layer. §13.8's own open question #4 ("how does `scg onboard --target` map onto a generated rule with a sensible default pattern") is exactly the seam that decides whether E10's simplicity survives this change or regresses.

**This does not belong to the stories — it's an architecture decision** — but I'm flagging it now so it's not a surprise at Gate 2: I will not approve an architecture where the common onboarding path requires a user to hand-author `jsonpath`/`pattern` themselves. `scg onboard --target` must keep working as a single flag; rule-authoring should be for the power-user/precision case E10 already established as optional, not the default path.

## Verdict
**APPROVE.** Stories are testable, user-facing, and correctly resolve the original per-resource mask/block request without overreaching into architecture decisions that belong to Morpheus.
