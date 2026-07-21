# Smith Mandatory Gate — E14 Phase 2 (Sprint 8)

**Reviewed:** the real interactive `scg onboard` confirmation flow, `--yes`/`--only`, `--list`, reputation-score display.
**Verdict: APPROVE**

## Real interactive session, via a genuine pty

Trin's Phase 2 UAT thoroughly covered the two non-interactive escapes (`--yes`, `--only`) for real, but the actual TTY prompt — the surface my Gate 1/2 hard requirement was most focused on protecting *around*, not the prompt's own UX — had only been exercised through mocked `input()` in unit tests. Since this is the mandatory gate specifically for real user-facing surface, I drove it through an actual pseudo-terminal (`pty.openpty()`), not a mock:

```
Identified 2 target(s):
  1. [file] /tmp/e14-smith/clean.md (via secrets)
  2. [url] https://partner.example.com/api (via reputation)
Onboard all 2 targets? [Y/n/s(elect)]
s
Enter numbers to exclude, comma-separated (or blank for none):
1
Verified: reputation:https://partner.example.com/api -> trusted (score 1.00)
Rule written to policy.yaml: tool='.*' pattern='https://partner\.example\.com/api' sensitivity='public' mode='allow'
1 onboarded, 0 blocked
```

**Heuristic evaluation of the real output:**
- **#1 Visibility of system status**: every target is listed with kind/identity/*which scanner claimed it* before any decision is asked for — a user isn't confirming a black box. The final summary line (`1 onboarded, 0 blocked`) closes the loop even in the excluded-target case.
- **#2 Match between system and the real world**: `s(elect)` reads clearly as a third option without needing documentation; the follow-up prompt ("Enter numbers to exclude...") uses the same 1-indexed numbering just shown, no translation required.
- **#4 Consistency**: the reputation score format (`score 1.00`) and rule-written line match exactly what `--yes`/`--only` already print (confirmed against Trin's UAT output) — the interactive path isn't a second, differently-formatted code path.
- **#3 User control and freedom**: excluding target 1 correctly dropped it from the batch — verified via the real written `policy.yaml` (only the reputation rule landed, not a secrets rule for the excluded file).

## Cross-checked against my own Gate 1/2 notes
- Non-interactive escapes: Trin's UAT already confirmed these for real; not re-litigated here.
- Mixed-sensitivity `--only`-twice workaround (my Gate 2 note): Trin verified this for real already — confirmed in her UAT notes, not re-run by me since it doesn't touch the interactive surface this gate is specifically about.
- Reputation score visibility (my Gate 1 ask): confirmed live above — `(score 1.00)`, not buried.

## Verdict
**APPROVE.** The real interactive flow — the one part of this phase no one had driven through an actual terminal yet — reads clearly and behaves exactly as designed. No UX issues found. Handing to Neo for Phase 3.
