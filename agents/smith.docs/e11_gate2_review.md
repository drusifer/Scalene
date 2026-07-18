# Smith Gate 2 Review — E11 Architecture (`docs/ARCHITECTURE.md` §14)

**Verdict: APPROVE**

## My Gate 1 hard requirement — checked directly

§14.3: "`scg onboard`'s CLI surface does not change. It still takes exactly `--target <uri>`." Confirmed by reading the actual decision text, not just trusting the summary. Rule-authoring (broader trust, explicit sensitivity/mode) is a separate, hand-edited-YAML path — exactly the E10 precedent (`scalene_policy.yaml` editing was always the power-user path; the CLI onboarding flow was always the common-case shortcut). **Satisfied.**

## Other UX-relevant checks

**#1 Visibility of System Status — STORY-1104's behavior change.** My Gate 1 note asked whether a user gets any signal the first time scanning newly fires on a call that used to be silently skipped. Checked `hook_adapter.py`'s existing mask path: every mask/block already writes an audit log entry *and* a `systemMessage` into the transcript, unconditionally, regardless of why the decision fired. Since §14.4 doesn't touch that response-construction code — only what feeds `decide()` — this signal continues to fire exactly the same way for a newly-triggered mask as an old one. No new messaging code needed. Will re-verify this holds for real at end-to-end test, not just from reading the architecture.

**#4 Consistency — new `rules:` YAML key.** Reasonable choice not to reuse `allowlist:` as the key name for a materially different schema (§14.5's stated reasoning). `rules:` reads correctly next to the existing `defaults:` block — same visual weight, no naming collision.

**#9 Help users recover from errors — rule validation.** `sensitivity`/`mode` validated against fixed value sets via the same `PolicyConfigError` path `PolicyConfig.mode` already uses (§14.5) — consistent error-reporting mechanism, not a new one to learn.

**Latency risk flagged, not blocking.** §14.4's `NFR-Perf-UnconditionalScan` is a real UX risk (added latency on every tool call is directly felt by the user, more than a first-sighting-only cost was) — but Morpheus named it explicitly with a verification requirement rather than leaving it a caveat, per the sprint's own retro lesson. I'll test this for real (not just read the provisional number) at end-to-end.

## Verdict
**APPROVE.** My Gate 1 condition is met, no new sharp edges introduced, and the one real UX risk (latency) has a named, owned verification step rather than an assumption. Proceed to Mouse for phasing.
