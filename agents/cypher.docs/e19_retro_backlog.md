# E19 (OLOY Mode) Retro Backlog, 2026-11-20

- [ ] `scg install-hooks` registers an explicit hook `timeout` (all modes). A timed-out hook is a non-blocking error, so the call proceeds unchecked. This is why OLOY needed a scan budget. (Morpheus)
- [ ] "OLOY on" indicator in `scg monitor` before the first OLOY decision. (Smith, Gate 1 + e2e)
- [ ] Give the OLOY summary its own line on narrow terminals; at 80 cols the wrap splits `(trust=…, sensitivity=…)`. (Smith, Phase 3 gate)
- [ ] `scg` subcommand to toggle OLOY. (Cypher, §24.5)
- [ ] Mask nested (non-top-level) payload values. (Cypher, §24.5)
- [ ] Extract a per-mode strategy from `decide_access` if a 3rd mode appears. (Neo/Morpheus)
- Process: map every AC to a test at phase UAT, not at sprint close (Trin). Archive CHAT.md at every sprint close (Oracle). Config ACs must state invalid-value behavior (Cypher).
