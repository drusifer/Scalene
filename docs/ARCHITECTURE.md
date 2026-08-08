# Project Architecture (ARCH.md) — Project Scalene

Maintained by **Morpheus**. Status: Sprint 1 (§1-10) shipped 2026-07-09. Sprint 2 (§11) shipped 2026-07-10. Sprint 3 (§12) implemented 2026-07-14 (retro/launch pending). Sprint 4 (§13) — Draft v1, pending Smith Gate 2. **§4's class diagram predates §13 and will be revised during Sprint 4 implementation** (`PolicyRule`/`PolicyConfig.allowlist` are replaced per §13.1 — not reflected below yet, Neo to update alongside the code change).

## 1. System Overview

Scalene is a provenance-based DLP layer for AI coding agents. It sits between the agent harness (Claude Code, initially) and its tools, tracking where data came from and blind-masking payloads when tainted-sensitive data would flow to an untrusted destination. It has two layers:

- **Hook Adapter** — thin, harness-specific integration (v1: Claude Code `PreToolUse`/`PostToolUse` hooks).
- **Policy Engine** — harness-agnostic core: taint state machine, JSONPath rule matching, masking decision, onboarding.

Splitting these means porting to a second harness (Cursor, etc.) later is an adapter, not a rewrite.

## 2. Architectural Principles

- **Deterministic over probabilistic**: rule matching (JSONPath), not content/NLP inspection — keeps latency and behavior predictable (NFR: <15ms).
- **Fail-safe by default**: any ambiguity resolves to `sensitive=true, trusted=false` (BRD 2.4).
- **No daemon required**: stateless-process-per-hook-call model, state externalized to disk. Simpler to reason about, trivially portable across local/Docker/cloud (NFR-Portability) — no background service to manage or crash-recover.
- **Adapter isolation**: nothing in the policy engine imports or knows about Claude Code's hook JSON schema. The adapter translates in both directions.

## 3. Component Diagram

```mermaid
graph TD
    A[Claude Code Hook Runtime] -->|PreToolUse JSON stdin| B[Hook Adapter: scalene-guard CLI]
    B --> C[Policy Engine]
    C --> D[Taint State Store<br/>.scalene/state/session_id.json]
    C --> E[Policy Config<br/>scalene_policy.yaml]
    C --> F[Masking Engine]
    B -->|PreToolUse JSON stdout<br/>allow / updatedInput| A
    A -->|PostToolUse JSON stdin| B
    B --> G[Provenance Updater]
    G --> D
    H[Onboarding CLI: scg onboard] --> I[Scanner Subprocess<br/>SCALENE_BYPASS=1]
    I -->|isolated, no hook re-trigger| E
    H --> J[Audit Log<br/>.scalene/audit.log]
    F --> J
```

## 4. Class & Data Structures

```mermaid
classDiagram
    class TaintState {
        <<sec15, 2026-07-17: trust/sensitivity tags replace has_sensitive_data/has_untrusted_data>>
        +str session_id
        +str trust
        +str sensitivity
        +bool is_clean
        +escalate_trust(level)
        +escalate_sensitivity(level)
        +load(session_id) TaintState
        +save()
    }
    class AccessDecision {
        <<sec15, 2026-07-17>>
        +bool allowed
        +str reason
    }
    class PolicyConfig {
        <<sec18, 2026-07-21: scanners added>>
        +bool sensitive_by_default
        +bool untrusted_by_default
        +str mode
        +tuple~PolicyRule~ rules
        +dict~str,Scanner~ scanners
        +from_yaml(path) PolicyConfig
    }
    class MatchResult {
        +bool is_sensitive
        +bool is_trusted
        +bool fail_safe_triggered
        +str untrusted_url
        +str sensitivity
        +str mode
    }
    class ResourceVerifier {
        <<module: resource_verifier.py>>
        +evaluate(tool, args, config, cache) MatchResult
    }
    class PolicyRule {
        <<corrected 2026-07-17, sec13.8>>
        +str tool
        +str jsonpath
        +str pattern
        +str sensitivity
        +str mode
        +str scanner
        +str description
    }
    class Scanner {
        <<interface>>
        +str name
        +identify(tool, args) list~Resource~
        +scan(resource) ScanResult
    }
    class FileScanner {
        <<sec18, 2026-07-21: hardcoded restricted-path short-circuit>>
        +str name = "secrets"
    }
    class URLScanner {
        +str name = "reputation"
    }
    class ReputationChecker {
        <<interface, reputation.py>>
        +check(target) ReputationResult
    }
    class LocalHeuristicChecker {
        +check(target) ReputationResult
    }
    class URLHausChecker {
        <<sec18.3, 2026-07-21 -- STORY-1503>>
        +check(target) ReputationResult
    }
    class ReputationResult {
        +bool is_trusted
        +str reason
        +float score
    }
    class ReputationCheckUnavailable {
        <<exception>>
    }
    class Resource {
        +str kind
        +str identity
        +str scanner_name
    }
    class ScanResult {
        <<sec17, 2026-07-20: reputation added, additive>>
        +str label
        +str reason
        +float reputation
    }
    class ScannerMachineryError {
        <<exception>>
    }
    class ScanCache {
        +get(resource) CacheEntry
        +put(resource, result)
        +try_reserve(resource) bool
        +is_fresh(resource, entry) bool
        +all_entries() dict
    }
    class CacheEntry {
        +str label
        +str reason
        +float scanned_at
        +float mtime
    }
    class ScanCacheError {
        <<exception>>
    }
    class MaskingEngine {
        <<sec14.4, dormant since sec15 -- no longer called from hook_adapter.pre_tool_use's default flow>>
        +decide(match, value) Decision
        +apply_mask(args, payload_field) dict
    }
    Scanner <|.. FileScanner
    Scanner <|.. URLScanner
    Scanner --> Resource
    Scanner --> ScanResult
    Scanner ..> ScannerMachineryError
    ResourceVerifier --> Scanner
    ResourceVerifier --> ScanCache
    ResourceVerifier --> PolicyConfig
    ResourceVerifier --> PolicyRule
    ResourceVerifier --> MatchResult
    ResourceVerifier --> TaintState
    ResourceVerifier --> AccessDecision
    PolicyRule ..> Scanner
    ScanCache --> CacheEntry
    ScanCache ..> ScanCacheError
    MaskingEngine --> MatchResult
    ReputationChecker <|.. LocalHeuristicChecker
    ReputationChecker <|.. URLHausChecker
    ReputationChecker --> ReputationResult
    URLHausChecker ..> ReputationCheckUnavailable
    URLScanner ..> ReputationChecker : isolated subprocess (scan_worker.py, STORY-601)
```

**Full replacement, not incremental simplification (2026-07-15, Sprint 4 / E10, §13.1) — corrected 2026-07-17, §13.8:** the original `PolicyConfig.allowlist`/`PolicyRule` model (tool/jsonpath/pattern/target, matching a call *and* deciding trust in one step) was removed entirely at Sprint 4, on the reasoning that pattern-matching itself was structurally unsafe (one scan vouching for an unbounded future match). That reasoning was right about the *old* `PolicyRule`, but the replacement (host-only resource identity for URLs) reintroduced the identical defect in a different shape — see §13.1's revision note. `PolicyRule` returns in §13.8's corrected model, but doing a narrower job than before: it decides *candidacy and resource identity* (jsonpath + pattern, tool-shape-agnostic), never trust directly — the scan cache (`ScanCache`) still verifies and freshness-tracks each *distinct* matched identity, which is what keeps a wildcard `pattern` from vouching for anything it hasn't actually checked. `PolicyConfig` still carries the mode/sensitivity-by-default fallbacks used when no rule matches. `docs/BRD.md` is left as the original historical requirements doc, not updated to match — same treatment as `task.md`/`USER_STORIES.md`.

## 5. Sequence & Interaction Flows

### Pre-tool-call (access-control path)

**Superseded 2026-07-17 by sec15** — the diagram below is the historical record of §14.4's content-scanning/masking flow, kept for context, not silently rewritten. See the real current flow further down.

Response shape uses Claude Code's real `PreToolUse` hook contract
(`hookSpecificOutput.permissionDecision`/`updatedInput`/`permissionDecisionReason`)
— corrected 2026-07-14; a prior flat `{"allow": ..., "updatedInput": ...}`
shape was never part of that contract and was silently ignored by the real
harness. Masking/blocking is also content-gated (2026-07-14): provenance
(taint + untrusted destination) only decides whether to scan at all —
`secrets_scan.py` must actually find something before any action is taken.

```mermaid
sequenceDiagram
    participant Agent
    participant Adapter as Hook Adapter
    participant Engine as Policy Engine
    participant Scan as secrets_scan
    participant State as Taint State
    Agent->>Adapter: PreToolUse(tool, args)
    Adapter->>Engine: evaluate(tool, args)
    Engine->>State: load(session_id)
    Engine-->>Adapter: MatchResult
    alt tainted-sensitive AND target untrusted
        Adapter->>Scan: scan_text_for_secrets(payload_field value)
        Scan-->>Adapter: findings
        alt findings non-empty, mode=mask
            Adapter->>Engine: apply_mask(args)
            Engine-->>Adapter: masked_args
            Adapter->>Adapter: log mask event (audit.log + systemMessage)
            Adapter-->>Agent: permissionDecision=allow, updatedInput=masked_args
        else findings non-empty, mode=block
            Adapter->>Adapter: log block event (audit.log + reason)
            Adapter-->>Agent: permissionDecision=deny, reason
        else no findings
            Adapter-->>Agent: permissionDecision=allow, unmodified
        end
    else safe (untainted or trusted destination)
        Adapter-->>Agent: permissionDecision=allow, unmodified
    end
```

**Current (sec15): `decide_access()` is the real flow.** No content scanning in the default path — the decision is entirely about whether identified resources are validated + explicitly allowed, or the session is still clean.

```mermaid
sequenceDiagram
    participant Agent
    participant Adapter as Hook Adapter
    participant Verifier as decide_access
    participant Cache as ScanCache
    participant State as Taint State
    Agent->>Adapter: PreToolUse(tool, args)
    Adapter->>State: load(session_id)
    Adapter->>Verifier: decide_access(tool, args, config, cache, taint)
    Verifier->>Cache: refresh_if_needed(resource) per identified resource
    alt any resource confirmed bad, or a matched rule's mode != allow
        Verifier-->>Adapter: AccessDecision(allowed=False, reason)
        Adapter->>Adapter: log block event (audit.log)
        Adapter-->>Agent: permissionDecision=deny, reason
    else all resources validated + allow-ruled (or none identified)
        Verifier->>State: escalate_sensitivity(rule.sensitivity) per match
        Verifier-->>Adapter: AccessDecision(allowed=True)
        Adapter-->>Agent: permissionDecision=allow
    else some resource unmatched/unvalidated
        alt session was clean before this call
            Verifier->>State: escalate_trust("low")
            Verifier-->>Adapter: AccessDecision(allowed=True)
            Adapter-->>Agent: permissionDecision=allow
        else session already tainted
            Verifier-->>Adapter: AccessDecision(allowed=False, reason)
            Adapter->>Adapter: log block event (audit.log)
            Adapter-->>Agent: permissionDecision=deny, reason
        end
    end
    Adapter->>State: save()
```

### Onboarding

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant CLI as scg onboard
    participant Scan as Scanner Subprocess
    participant Cfg as scalene_policy.yaml
    Dev->>CLI: onboard --target URI --tool X --jsonpath Y --pattern Z
    CLI->>CLI: resolve scan type from URI scheme
    Note right of CLI: file:// -> secrets scan<br/>http(s):// -> reputation check
    CLI->>Scan: spawn(SCALENE_BYPASS=1)
    Scan-->>CLI: scan result (secrets? reputation?)
    alt scan clean
        CLI->>Cfg: append rule (incl. target) to allowlist
        CLI-->>Dev: "Rule added: <rule>. Diff: ..." (audit.log entry)
    else scan fails
        CLI-->>Dev: "Onboarding blocked: <reason>" (no write)
    end
```

## 6. Technical Stack

- **Language**: Python 3.11+. Rationale: matches the surrounding tool ecosystem (`via` is pip-installed per this repo's own tooling), fast to iterate, `jsonpath-ng` and `pyyaml` cover the config/matching needs without custom parsing.
- **Distribution**: pip-installable CLI (`scalene-guard`), invoked as the hook `command` in `.claude/settings.json` (`hooks.PreToolUse[].hooks[].command`, `hooks.PostToolUse[].hooks[].command`).
- **State store**: flat JSON files under `.scalene/state/<session_id>.json`, file-locked (`filelock`) for the rare concurrent-call case. No database, no daemon.
- **Config**: `scalene_policy.yaml` at project root, loaded fresh per hook invocation (no caching across process boundaries — config is small, load cost is negligible against the 15ms budget).
- **Scanner isolation**: `subprocess.run` with `env={"SCALENE_BYPASS": "1", ...}`, not a container — keeps it portable to environments without container runtime access, while still preventing the scanner's own tool calls (if any) from re-entering the hook loop.

## 7. Resolved Open Questions (from Cypher's `docs/USER_STORIES.md`)

1. **Runtime/hook API target** → Claude Code's native `PreToolUse`/`PostToolUse` hook system for v1 (this is the same hook mechanism this very repo's session is running under). Policy engine kept adapter-isolated so Cursor/others can be added later without a rewrite.
2. **Taint state persistence** → Per-session JSON file keyed by Claude Code's `session_id` (present in every hook JSON payload), not in-memory/daemon. Survives individual hook subprocess exits; cleared on explicit reset or session end.
3. **Hook registration mechanism** → Standard Claude Code `settings.json` hook config (matcher + command), documented in project setup instructions (Neo to write during implementation).
4. **Threat-intel service for trust-list onboarding (STORY-501)** → **Decision: no paid external API in v1.** Ships with `LocalHeuristicChecker` (new/suspicious domain patterns, IP-literal targets, punycode homograph detection) behind a `ReputationChecker` interface. Removes the external-dependency/env-var concern Cypher flagged for Tank — reassess with Tank only if/when a real threat-intel API is added post-v1.

## 8. Response to Smith's Gate 1 Notes

- **STORY-401 masking visibility**: Adapter writes every mask event to `.scalene/audit.log` AND returns a Claude Code `systemMessage` in the PreToolUse hook response, so the event surfaces directly in the transcript the developer is watching — not just a silently swapped string. Cypher: please add this as explicit AC on STORY-401.
- **STORY-501 onboarding confirmation**: `scg onboard` prints the rule added plus a YAML diff on success, and writes the same to `audit.log`. Cypher: please add as explicit AC on STORY-501.

## 9. Devops/Infra Impact (for Tank)

- STORY-601 (`SCALENE_BYPASS` env var) — confirmed as a subprocess env var, not a system-wide/CI env var. No CI pipeline changes needed for v1.
- STORY-501's original Tank flag (external threat-intel API) is **resolved** by decision #4 above — no external network egress in v1. Tank review still useful for confirming `.scalene/` directory placement doesn't collide with `.gitignore`/CI artifact rules, but is no longer a hard gate.

## 10. Refactoring Status & Technical Debt

None yet — greenfield. First implementation phase should establish the `PolicyEngine`/`Adapter` boundary early since it's the seam most likely to be tested by a second-harness port later.

---

## 11. Sprint 2 Architecture — Live Console (E7) & Secrets Scan Upgrade (E8)

### 11.1 Decision: TUI, not a web frontend

Cypher's stories left TUI-vs-web-frontend open. **Decision: TUI, built on `textual`.**

Reasons:
- A web frontend needs a bound localhost port and (likely) a small web-server dependency (Flask/FastAPI) — this project currently has zero web-server dependencies, and binding a port is exactly the kind of thing that would trigger a Tank infra review. A TUI reads local files directly and needs neither.
- The user's own framing was "a TUI or web frontend the user runs alongside their Claude session" — a terminal-native tool sits in the same terminal workflow a developer already has open; no browser tab, no localhost URL to remember (Nielsen #7, fewer things for the user to juggle).
- Matches the existing distribution model exactly: another `scg` console-script subcommand (`scg monitor`), same pip package, no new deployment surface.
- **Consequence: no Tank gate needed for Sprint 2** — no new port, service, env var, or CI/deploy impact. Same precedent as Sprint 1 (no Tank phase; reassess if this ever grows into a hosted/team-shared dashboard instead of a local single-developer tool).

**Packaging note:** `textual` is added as an optional extra (`pip install scalene-guard[monitor]`), not a hard dependency of the base package — the hot-path hook adapter (`scalene-guard`, <15ms NFR) must never import a TUI framework it doesn't use.

### 11.2 Data access: poll, don't watch

`.scalene/audit.log` and `.scalene/state/*.json` are read via simple polling (fixed interval, e.g. every 500ms — Neo to tune during implementation) rather than an inotify-style filesystem watcher. Reason: consistent with NFR-Portability (inotify-based watching is flaky on some Docker bind-mounts and network filesystems); the files are small, so poll cost is negligible; avoids a new dependency (`watchdog`) for a dev-only convenience tool.

### 11.3 Session scope (resolves Smith's Gate 1 note)

Every audit entry and state file already carries `session_id` (`hook_adapter.py:105`, `taint_state.py`). Decision: the console's default view lists all sessions with a discoverable state file (recent-first), each showing its own taint flags; selecting one filters the mask-event feed to that session. An aggregate "all sessions" feed is also available as a toggle — real developers commonly run more than one agent session at once, and neither "always merge" nor "always force a single-session pick" serves that alone.

**Cypher: please add this as explicit AC on STORY-701** (mirrors how Sprint 1's §8 response fed back into story AC).

### 11.4 Onboarding action (STORY-702)

The console's "apply" action is a **subprocess call to the existing `scg onboard` CLI** using the exact `suggested_onboard_command` string already generated by `hook_adapter.py`, with the placeholder target substituted by the user's inline edit. This is a UI shell, not a reimplementation — it goes through the same secrets-scan/reputation-check gates as running the command by hand. No new code path in `onboard.py` itself.

### 11.5 Secrets scan upgrade (E8) — error message translation layer (resolves Smith's Gate 1 note)

`secrets_scan.py` already produces its own plain-language scan-result messages rather than surfacing regex internals. The `detect-secrets` integration must preserve that: detect-secrets' plugin/detector output is translated into the existing result format inside `secrets_scan.py`, never surfaced as raw library exception text to the onboarding CLI's user-facing output.

**Cypher: please add this as explicit AC on STORY-801.**

## 12. Sprint 3 Architecture — Documentation & Onboarding (E9)

STORY-901/902 are pure documentation — no new architecture decisions, just placement:

- `docs/GETTING_STARTED.md` and `docs/USER_GUIDE.md` are new top-level docs under `docs/`, added to `README.md`'s documentation table (per Smith Gate 1). `README.md`'s existing "Getting started" section is trimmed to a link, not a duplicate.
- STORY-902's CLI reference must be generated/verified against real `--help` output (`scg --help`, `scg onboard --help`, `scg monitor --help`, `scg install-hooks --help`, `scalene-guard --help`) at write time — Neo checks this by actually running each command, not transcribing from memory of the source.
- Per Smith's Gate 1 note: the onboard-suggestion workflow (`_suggest_onboard_command()`, §4/§11.4) must be the guide's primary onboarding path, with the raw manual-flag `scg onboard` invocation presented as the fallback for cases with no prior blocked call to suggest from.

### 12.1 Decision: demo is a real `scalene-guard` subprocess run, not a mocked walkthrough

STORY-903 requires the demo show a *real* masked call, offline, and be checked by a test so it can't rot silently. Decision: a small script (`demo/run_demo.py`) that:

1. Builds a temp project dir with a minimal `scalene_policy.yaml` (no sensitive allowlist, no trusted sources — matches the fail-safe defaults new users actually hit first).
2. Invokes the real `scalene-guard` CLI as a subprocess, feeding it real `PreToolUse`/`PostToolUse` JSON payloads on stdin exactly as Claude Code would (same entry point as production, per §1's adapter-isolation principle — this is not a call to internal functions that could drift from the real CLI contract).
3. Scenario matches the BRD's Triangle-of-Doom case directly: a `Read` of a fake "sensitive" file (sets `has_sensitive_data`), followed by a `WebFetch` to a domain that is not on the trust list (untrusted destination) — the second call's response shows the payload masked.
4. Prints each step with plain-language narration (what happened and why) so it reads as a demo, not raw JSON — but the underlying JSON is real `scalene-guard` output, not fabricated for display.

**Why this stays offline (STORY-903 AC):** `scalene-guard` never performs the tool call itself — it only returns an allow/mask decision (§1, hook adapter is decision-only). The demo never actually issues the `WebFetch` HTTP request; showing the masked `tool_input`/response *is* the entire demonstration. No mocking is needed to keep this offline — it's a structural property of the architecture, not a demo-specific shortcut.

### 12.2 Decision: demo is tested, not just runnable

`tests/test_demo.py` invokes `demo/run_demo.py` as a subprocess (same as a user would) and asserts the final output matches the demo's real, current behavior. This runs under ordinary `pytest`/`make test` collection — no separate CI wiring needed. `make demo` (new Makefile target) runs the same script directly for a human to watch, narration included.

**2026-07-16 (direct user request, post-Sprint-4):** the demo was extended beyond the single masked-call scenario to demonstrate the actual security-model contrast — mask (default) vs. a verified-trusted destination vs. `mode: block` — using the real `scg onboard` CLI and a real `mode: block` policy file, not just the original zero-config mask case. This means "the fake secret never appears unmasked" is **no longer a whole-demo invariant**: Part 3 deliberately shows the same fake secret passing through *unmasked* to a destination that's been onboarded/verified trusted, since that's the concrete, honest way to demonstrate that trust is an exemption from content-scanning, not an additional layer of detection. `tests/test_demo.py`'s assertions were updated accordingly (the "never unmasked" check is now scoped to Part 2's specific line, not the whole output).

**No Tank gate needed:** no new service, port, env var, or deploy/CI impact — `demo/run_demo.py` is a local dev-only script in the same vein as Sprint 1/2's no-Tank precedent.

## 13. Sprint 4 Architecture — Extensible Scanner Registry & Resource Verification (E10)

### 13.1 Decision: replace the allowlist/PolicyRule matching model, don't bolt scanning on top of it

**Corrected 2026-07-17 (direct user design session, post-Sprint-4-close) — see §13.8.** The paragraph below is kept as the historical record of what shipped and why it was wrong, not silently rewritten. The specific error: claiming host-only resource identity "doesn't lose" the old model's flexibility. It does, and worse — host-level identity **structurally reproduces the exact defect this epic exists to fix** (one verification vouching for an unbounded future set), just relocated from a user-authored regex into the resource-identity model itself. Trusting a host based on scanning one path under it is the same shape of bug as a `pattern` matching an unbounded set based on scanning one `target`. §13.8 corrects this: `PolicyRule` (jsonpath + pattern) returns as the *matching* mechanism — generic across any tool's argument shape, not assuming a fixed per-tool-type resource schema — while the scan cache's per-distinct-identity verification and freshness tracking (§13.3, which was and remains correct) is what actually keeps a wildcard pattern safe: the pattern controls *candidacy*, the cache still controls *trust*, checked per specific match, not once for the whole pattern.

Cypher's epic left this as an explicit open question. **Decision: full replacement**, not coexistence. `PolicyConfig.allowlist`/`PolicyRule` (tool/jsonpath/pattern/target, shipped one commit before this epic) is removed entirely, not deprecated alongside a new system.

Reasoning: the defect this epic exists to fix — a rule's `pattern` can match an unbounded future set while its `target` was only ever scanned once — is structural to the pattern-matching model itself, not a bug in one implementation of it. Any coexistence would keep the hole open for whichever rules stay on the old path. The new model's resource-identity granularity (a URL scanner's resource is a *host*, not a full URL) already gives broad, reusable coverage — "trust `internal.example.com`" naturally covers every path under it — without needing a hand-written regex to express "broad." The old model's flexibility isn't lost, it's absorbed into resource-identity choice.

`scg onboard` is **not removed** — it's re-scoped from "write a policy rule" to "pre-seed the resource cache" (§13.4): given a target, run the matching scanner against it right now and write the result into the same cache the live hook consults, so a developer can front-load the first-sighting cost for a resource they already know is fine, instead of eating it the first time an agent hits it live.

### 13.1.1 How this fits into the existing `pre_tool_use`/`post_tool_use`/`MaskingEngine` flow

Two *different* checks exist today and stay separate — this epic replaces one of them, not both:

1. **Content-gating (shipped, unrelated to this epic):** `MaskingEngine.decide()` scans the *specific payload value being sent* (e.g. an outbound `prompt`) for embedded secrets via `scan_text_for_secrets()`, gated behind provenance risk. This governs *whether to mask/block this specific call*. **Unchanged by E10.**
2. **Resource verification (this epic, replaces `PolicyConfig.evaluate()`):** governs the *provenance signals themselves* — `is_sensitive` (does a `Read`'s target count as sensitive) and `is_trusted` (does a call's destination count as trusted). Previously computed by matching `PolicyRule`s; now computed by asking the scanner registry to identify resources in the call's args and checking the resource cache.

Concretely, `hook_adapter.py` changes from `match = config.evaluate(tool, args)` to something like `match = resource_verifier.evaluate(tool, args)`, returning the same `MatchResult(is_sensitive, is_trusted, fail_safe_triggered)` shape both `pre_tool_use` and `post_tool_use` already consume — `MaskingEngine.decide()`'s signature and content-gating logic don't change at all. `fail_safe_triggered` now means "at least one identified resource had no cache entry and fell back to defaults," replacing its old meaning ("a rule's JSONPath failed to evaluate") — same field, same downstream handling (existing tests/log messages), new trigger condition.

### 13.2 Component: Scanner protocol + registry

```python
class Scanner(Protocol):
    name: str  # "secrets", "reputation", ... — the label namespace this scanner owns

    def identify(self, tool_name: str, args: dict) -> list[Resource]:
        """Find candidate resources this scanner cares about within a call's
        args. No jsonpath/pattern from user config — each scanner owns its
        own detection logic (STORY-1002)."""

    def scan(self, resource: Resource) -> ScanResult:
        """Verify one resource. Runs in an isolated subprocess (SCALENE_BYPASS=1,
        unchanged from today's subprocess_isolation.py) — never raises to the
        caller; a scanner-internal exception is what makes STORY-1004's fatal
        path fire, not what gets returned as a ScanResult."""

@dataclass(frozen=True)
class Resource:
    kind: str          # "file" | "url" — extensible, not a closed enum
    identity: str       # cache key material: absolute path, or host
    scanner_name: str

@dataclass(frozen=True)
class ScanResult:
    label: str          # "public" | "sensitive" | "trusted" | "untrusted"
    reason: str = ""
```

Registry is a plain `dict[str, Scanner]` populated at import time (`SCANNERS = {"secrets": FileScanner(), "reputation": URLScanner()}`) — adding a scanner is adding an entry, no dispatch code changes (STORY-1002 AC).

**Built-in scanners (STORY-1002):**
- `FileScanner` — `identify()` checks known per-tool fields first (`Read`/`Write`/`Edit`'s `file_path`/`new_string`/`content`-adjacent path arguments, reusing today's `DEFAULT_PAYLOAD_FIELDS`-style knowledge internally, not exposed to config) plus a generic "does this string look like an absolute/relative path" regex fallback for anything else. `scan()` is today's `secrets_scan.py` unchanged, run against the file's content.
- `URLScanner` — `identify()` checks known fields (`WebFetch`'s `url`) plus a generic `https?://` regex fallback. Resource identity is the **host**, not the full URL (§13.1). `scan()` is today's `LocalHeuristicChecker` unchanged.
- **Bash command scanner: not a third scanner type.** Decision: `Bash`'s `command` string is handed to *both* `FileScanner.identify()` and `URLScanner.identify()`'s generic fallback regexes as an additional input source, since a shell command is just a string that may embed either shape. A dedicated `BashScanner` would only duplicate the same shape-detection regexes FileScanner/URLScanner already need for their generic fallback — no new scanner type needed, just wiring `Bash` into both existing scanners' `identify()`.
- Named regex captures (STORY-1001) are an internal detail of each scanner's own detection regex (e.g. `URLScanner`'s fallback pattern has a `(?P<host>...)` group it extracts and discards the rest of) — not a user-facing config concept. There is no more user-authored `jsonpath`/`pattern` for this purpose at all (§13.1).

### 13.3 Component: Scan cache

`.scalene/scan_cache.json`, project-wide (not per-session — a file's or host's verification status isn't session-scoped), file-locked like `taint_state.py`'s per-session files (`filelock`, same pattern, not a new dependency):

```json
{
  "file:///abs/path/to/file.md": {"mtime": 1720000000.0, "label": "public", "reason": "", "scanned_at": 1720000000.0},
  "reputation:internal.example.com": {"label": "trusted", "reason": "", "scanned_at": 1720000000.0}
}
```

Key is `f"{scanner_name}:{resource.identity}"` (file resources additionally carry `mtime` inside the value, not the key, since re-verifying a changed file should overwrite its entry rather than accumulate stale ones per-mtime).

**Lookup/refresh logic (STORY-1003), run for every identified resource on every call:**

| Cache state | Label used for *this* call | Rescan? |
|---|---|---|
| No entry | Existing fail-safe default (`sensitive_by_default`/`untrusted_by_default`) — **identical to today's behavior for an unconfigured resource, no new latency** | Fire-and-forget background scan, seeds cache for next time |
| Fresh (<24h, and for files: `mtime` unchanged) | Cached label, direct | None |
| Expired (>24h, or file `mtime` changed) | Last-known cached label, immediate, no blocking | Fire-and-forget background scan, refreshes cache |

This is why the "new resource" path is *not* a regression risk for the **decision** it produces: it applies exactly the same fail-safe default today's code does, so the label a caller acts on never changes. Only the *previously-scanned* paths get faster than fail-safe defaults, and only once something has actually been verified.

**NFR revision, 2026-07-14 (Morpheus's Phase 2 review, informed by real measurement, not assumption):** the "zero added latency" framing above was wrong about *wall-clock cost*, only right about *decision behavior*. `refresh_if_needed()`'s fire-and-forget `subprocess.Popen` spawn (the "merely adds a side-effect" step) is not free — measured at ~6.6ms avg / ~16ms max per newly-identified resource in this environment, isolated to the spawn syscall itself (reproduced identically with a trivial no-op command, ruling out worker-script complexity as the cause).

Splitting the NFR to be honest about this rather than letting Phase 3's perf test discover it as a surprise:
- **`NFR-Perf-Steady-State`** (unchanged, <15ms): applies whenever every identified resource in a call has a fresh cache entry — pure JSON-cache reads under a `FileLock`, no subprocess spawn, genuinely the same cost as today's pre-Sprint-4 code.
- **`NFR-Perf-FirstSighting`** (new, provisional): a call that identifies N never-before-seen (or expired) resources pays roughly N × spawn-cost in *added* latency on top of the steady-state cost, since each triggers its own dedup-checked `Popen` spawn. Provisional budget: **<25ms added latency per newly-identified resource** (headroom over the measured ~16ms worst case). This is a one-time cost per resource — paid once, then the resource is cache-fresh for 24h and falls back under `NFR-Perf-Steady-State` for every subsequent call. Phase 3 task 3.4 must verify this NFR with a real test (analogous to `tests/test_performance.py`'s existing steady-state test), not assume the provisional number holds — same "verify, don't assume" standard as the hook-contract exit-code work.
- Accepted deliberately over redesigning the spawn mechanism (e.g., batching multiple resources into one spawn, or decoupling from the synchronous `pre_tool_use` path) — the added cost is one-time-per-resource and self-amortizing (every subsequent call on that resource is free), judged not worth the added design complexity for a per-resource cost this bounded.

**"Background" mechanism:** `subprocess.Popen` (not `subprocess.run`) with no `.wait()` — the child scanning process (running with `SCALENE_BYPASS=1`, same isolation as today) writes its result into the cache file (via the same `FileLock`) whenever it finishes, independent of the parent `scalene-guard` process having already exited and returned its response. No daemon, no persistent process — consistent with §2's "no daemon required" principle; each background scan is a one-shot detached subprocess, same lifecycle model as everything else in this codebase.

**File staleness uses `mtime`, not a content hash** (Smith/user direction) — `os.stat().st_mtime` is effectively free; hashing file content on every call would reintroduce the exact performance problem this cache exists to solve.

### 13.4 `scg onboard` re-scoped: pre-seed the cache

```
scg onboard --target file:///path/to/file.md
scg onboard --target https://internal.example.com
```

Drops `--tool`/`--jsonpath`/`--pattern`/`--description` entirely (§13.1 — there's no rule to author anymore, just a resource to check now instead of later). Resolves the scanner from the URI scheme exactly as today (`file://` → `FileScanner`, `http(s)://` → `URLScanner`), runs `scan()` synchronously (this is the one deliberately-blocking scan path left in the system, and it's fine — it's a one-off CLI invocation, not the hot hook path), and writes the result into `.scalene/scan_cache.json` directly. No more separate `scalene_policy.yaml` `allowlist` writes, no diff-printing (there's no YAML edit to diff) — prints the resolved label instead.

### 13.5 STORY-1004: fatal exit — exact boundary and mechanism

**Fail-safe-exit-0 (unchanged from today):** malformed hook JSON, unrecognized hook event, a scanner's `identify()`/`scan()` returning an ordinary bad result (secret found, bad reputation) — all ordinary decisions, `scalene-guard` exits 0 exactly as it does today.

**Fatal-exit-nonzero (new, narrow):** the scan **cache store itself** is unreadable/corrupted/unwritable, or a registered scanner's `scan()`/`identify()` raises an unhandled exception (a bug in scanner code, not a scan finding). This is a "the safety mechanism can't do its job" condition, categorically different from "the safety mechanism did its job and found something."

**Exit code: verified as 2** (2026-07-15, Neo — not assumed, not left provisional). Checked two ways: (1) fetched Claude Code's real hook docs, which are explicit — "Claude Code treats exit code 1 as a non-blocking error and proceeds with the action, even though 1 is the conventional Unix failure code... only exit code 2 blocks [PreToolUse]"; (2) live-verified against this very repo's own dogfooded `scalene-guard` installation (`.claude/settings.json` wires the real, editable-installed binary as this session's actual hook) — corrupted the real `.scalene/scan_cache.json`, confirmed a real tool call passed through completely unaffected while the fatal path returned exit 1, then confirmed exit 2 is what's actually required to block a `PreToolUse` call. The architecture's original caution above (don't assume exit 2's semantics carry over from the earlier hook-contract research) was a reasonable question to raise, but the real contract doesn't distinguish "deliberate policy block" from "machinery failure" by cause — it only cares about the exit code value. Exit 2 is used uniformly for both `PreToolUse` (where it correctly blocks — the fail-closed behavior this story wants: if the scanning machinery can't be trusted, stop the call rather than let it through unchecked) and `PostToolUse` (where exit 2 is explicitly non-blocking too, same as any other non-zero code, which is correct since the tool has already run by then).

**Message:** same plain-language standard as `secrets_scan.py`/`onboard.py` — a fatal exit still writes a real reason to stderr, never a raw traceback (Smith Gate 1 note).

**Labels always surfaced regardless of fatal/non-fatal:** whatever labels *did* resolve for other resources in the same call (e.g. one resource's scanner is fine, another's cache store lookup is what failed) are still included in the response — a fatal condition on one resource doesn't blank out information that was actually available.

### 13.6 STORY-1005: recent scans surfaced in `scg monitor`

New panel alongside the existing Sessions/Mask-events tables (`monitor_app.py`), reading `.scalene/scan_cache.json` directly (poll-based, same §11.2 precedent — no filesystem-watch dependency). Columns: resource identity, label, last-scanned time. This is a read of the real cache store, not a parallel summary that could drift from it (STORY-1005 AC).

### 13.7 Devops/Infra impact

No Tank gate: still no daemon, no new port/service/env var. The one new behavior worth Tank's awareness (not a gate) is background subprocess spawning via `Popen` without `wait()` — confirm this doesn't leave zombie/orphaned processes in constrained container environments; Neo to verify during implementation with a real, repeated-invocation test, not just a single-call check.

### 13.8 Correction (2026-07-17): rule-driven resource identity, and an explicit trust/sensitivity model

Direct user design session, after Sprint 4 was formally closed. Corrects §13.1's resource-identity decision and generalizes it — not a new epic replacing E10, an in-place fix to a defect in what E10 shipped.

**What was wrong.** §13.1 hard-codes what "a resource" means per scanner type: `FileScanner`'s identity is the full path (correct), `URLScanner`'s identity is the *host* (wrong). Host-level identity means onboarding one path under a host (e.g. `github.com/you/your-repo`) silently trusts every other path under that host (e.g. anyone else's repo on `github.com`) — one verification vouching for an unbounded set, the exact defect this epic exists to close, just relocated into the resource model instead of a user-authored regex.

**Why it matters more than "less granular than ideal."** The user framed Scalene's primary purpose precisely: mitigating prompt-injection/tool-poisoning vectors without relying on the model's own guardrails, *not* secret-leak prevention — that's the secondary, emergent protection that falls out of the taint-tracking/content-scanning machinery. Under that priority order, **trust is the primary control** (should the agent be allowed to pull content from this source at all) and **masking is the backup** (catch it if something sensitive slips out anyway). Host-level trust granularity is therefore a hole in the *primary* control, not the backup one: `github.com` hosts both a trusted repo and every untrusted, potentially-poisoned repo anyone else has ever pushed, and host-level identity cannot distinguish them.

**Two independent axes, not one.** Prior to this correction, `is_sensitive`/`is_trusted` were treated as roughly parallel provenance signals. They are not — they answer different questions:
- **Trust** — *could this source cause the agent to do something malicious* (prompt injection, tool poisoning)? A read-side/source-legitimacy question, answered by scanning/verifying/vouching for a resource, at whatever granularity actually distinguishes the safe case from the unsafe one (per-repo, not per-host, for anything multi-tenant like a public git host).
- **Sensitivity** — *what's the blast radius if a malicious tool call involving this resource succeeds?* A data-classification question, independent of trust. Exactly three levels, deliberately small:
  1. **Public** — anyone in the world can access it.
  2. **Internal Only** — anyone internal to the org can access it.
  3. **Restricted** — only specific people can see it.

  It's fine to work with low- or medium-trust sources when sensitivity is Public/non-critical — the worst case is bounded. The dangerous combination (the "Triangle-of-Doom"/lethal-trifecta case this whole project exists to prevent) is low-trust *and* high-sensitivity together, not either alone.

**Masking becomes unconditional, not sensitivity-gated.** Today, content-scanning only runs when a session is already tainted-sensitive *and* tainted-untrusted (`MaskingEngine.decide()`'s `provenance_risk` gate). Under the corrected model, an implicit, always-present top-level rule —

```yaml
- tool: ".*"        # any tool
  jsonpath: "$.*"    # any argument (conceptual; exact JSONPath TBD at implementation)
  pattern: ".*"      # any value
  sensitivity: public
  mode: mask
```

— matches every call by default, so real-secret content-scanning is a universal baseline, not conditioned on classification. This is what makes `sensitivity: public` a safe *default* rather than a weakening: the leak-detection safety net no longer depends on the classification being right. Sensitivity/trust govern *stricter* handling on top of that baseline (e.g. a rule matching something classified `restricted` can carry `mode: block` instead of `mask`), not whether any protection exists at all.

**`PolicyRule` returns, generalized — not the pre-Sprint-4 shape.** The pre-Sprint-4 `PolicyRule` matched calls directly and *was itself* the trust decision (evaluate → allow/deny), which is what let one scan vouch for an unbounded pattern. The corrected model splits that: `PolicyRule` (jsonpath + pattern, tool-shape-agnostic — Scalene does not need to know a given tool's argument structure in advance) decides *candidacy and resource identity* (a named capture group in `pattern`, generalizing STORY-1001's original — not Phase 1's internal-only downgrade of it — intent, becomes the cache key); the scan cache (§13.3, unchanged and still correct) decides *trust*, verified and freshness-tracked per distinct identity a rule's pattern actually matches, never once for the whole pattern. A wildcard rule widens what's *considered*, never what's *vouched for without checking*.

```python
@dataclass(frozen=True)
class PolicyRule:
    tool: str          # regex against tool_name (".*" = any)
    jsonpath: str       # JSONPath into tool_input/tool_response
    pattern: str        # regex against the extracted value; named capture groups
                        # (e.g. (?P<host>...)) become the resource identity
    sensitivity: str    # "public" | "internal" | "restricted"
    mode: str           # "mask" | "block"
    scanner: str = ""   # which verifier checks a match ("secrets" | "reputation" |
                        # inferred from context if omitted)
    description: str = ""
```

**Zero-config baseline is preserved, not replaced.** `FileScanner`/`URLScanner`'s built-in generic-fallback detection (Phase 1, unaffected) remains the reason a brand-new, unconfigured project gets real protection immediately — rules are an *additive precision layer* (narrower or broader than the generic heuristic, deliberately chosen) layered on top of that baseline via the implicit default rule above, not a configuration requirement before any scanning happens.

**Not yet decided / explicitly deferred to implementation:** the exact JSONPath expression for "any argument" in the default rule; whether `scanner` must always be explicit on a user-authored rule or can be inferred the way URI scheme inference works today; the real on-disk schema for `PolicyRule` in `scalene_policy.yaml` (replaces the removed `allowlist`, does not resurrect its exact pre-Sprint-4 shape — `sensitivity`/`mode` are new fields, `target` does not return); how `scg onboard` maps a `--target` onto a generated rule with a sensible default pattern. This section documents the corrected *model*; implementation is a follow-up phase, not retroactively applied to already-closed Sprint 4 code without going through the same Bloop review process everything else in this document did.

## 14. Sprint 5 Architecture — Trust/Sensitivity Model & Rule-Driven Resource Identity (E11)

Resolves §13.8's 4 deferred open questions and STORY-1101 through 1105. Grounded in the real shipped E10 code (`scanner.py`, `policy_config.py`, `resource_verifier.py`, `masking.py`, `onboard.py`, `scan_cache.py`), not a rewrite from a blank page — this section states exactly what changes and what stays.

### 14.1 Rules layer *on top of* scanner identification — they do not replace it

Resolves open question #1 (exact JSONPath for "any argument"). §13.8's `PolicyRule` describes `jsonpath` as extracting a value from `tool_input`/`tool_response` directly, which would mean rules do their own independent resource discovery — duplicating what `FileScanner`/`URLScanner`'s `identify()` already does today, and reopening the exact "zero-config baseline preserved" promise §13.8 itself makes a few paragraphs earlier.

**Decision:** rules do not re-derive resources from raw args. `identify()` (unchanged, Phase 1) still finds every candidate `Resource` for a call. A rule's job is purely classification: for each identified `Resource`, find the first rule (in declaration order) where `tool` (regex) matches `tool_name` and `pattern` (regex) matches `resource.identity` — that rule's `sensitivity`/`mode` apply to this resource for this call. The implicit default rule (§13.8, any tool/any value, `sensitivity: public`, `mode: <defaults.mode>`) always matches last, as a fallback, not a real `PolicyRule` requiring JSONPath evaluation — it is constructed in code, never written to a user's YAML (a magic always-on YAML entry could be accidentally deleted; a code-level fallback cannot). This closes open question #1 by making it moot for the default case: `jsonpath` remains a documented field on `PolicyRule` for a future case where a tool has multiple candidate argument fields that need distinguishing, but is not required for E11's scope — omit it and the rule matches any resource the `tool`+`pattern` pair identifies.

**Resolves open question #2 (`scanner` explicit vs. inferred):** inferred by default. Every identified `Resource` already carries `scanner_name` (which scanner found it). A rule's optional `scanner` field is a disambiguating filter only — if present, the rule additionally requires `resource.scanner_name == rule.scanner`; if absent, the rule applies to any resource whose `tool`+`pattern` match, regardless of which scanner identified it. This matters only for the rare case where a file-shaped and URL-shaped string could both plausibly match the same `pattern` (e.g. a Bash command).

### 14.2 Fix STORY-1101: `URLScanner` identity becomes per-URL, not per-host

The defect: `URLScanner.identify()` (§13.2) extracts a `host` capture group as the resource identity. Scanning `https://github.com/you/your-repo` once and caching `reputation:github.com -> trusted` silently trusts `https://github.com/anyone/anything-else` forever after — one verification vouching for an unbounded set.

**Fix:** `_URL_FALLBACK_RE` changes from `https?://(?P<host>[^/\s:"']+)` to capture the full URL span (scheme + host + path, query string dropped to keep cache keys bounded — `https?://(?P<url>[^\s:"']+)`, trimmed of a trailing `?...`). `Resource.identity` for a URL becomes this full (scheme, host, path) string, not the bare host. Every distinct path is now its own cache entry, independently scanned and freshness-tracked (§13.3's cache mechanics are otherwise unchanged) — the exact fix the defect calls for.

**Broadening remains possible, but only via an explicit rule, never implicitly.** A developer who genuinely wants "trust everything under `internal.example.com`" writes:
```yaml
rules:
  - tool: ".*"
    pattern: "https://internal\\.example\\.com/.*"
    sensitivity: internal
    mode: mask
```
This rule's `pattern` only decides *candidacy* — which resources it's willing to consider trusted-if-verified. The scan cache still verifies and freshness-tracks each *distinct* URL this pattern actually matches (§13.3, unchanged) — a wildcard rule widens what's considered, never what's vouched for without a real per-resource cache entry. This is the generalized version of the same fix, available to any scanner type, not just URLs.

### 14.3 `scg onboard --target` stays single-flag (Smith's Gate 1 hard requirement, carried to Gate 2)

**Decision: `scg onboard`'s CLI surface does not change.** It still takes exactly `--target <uri>`, verifies that one exact resource (now per-URL under 14.2's fix, same behavior as today for `file://` targets since those were already full-path identity), and pre-seeds the cache — no `--pattern`/`--sensitivity`/`--mode` flags added. This is the common case (§13.4, unaffected) and Smith's explicit condition for Gate 2 approval: the onboarding simplicity E10 shipped does not regress.

Authoring a `PolicyRule` (broader pattern, explicit `sensitivity`/`mode`) is the separate, opt-in power-user path for the two cases `--target` alone can't express: (a) trusting more than one exact resource at a time, (b) setting `sensitivity`/`mode` to anything other than the project-wide `defaults.mode`. A rule is hand-written into `scalene_policy.yaml` directly, same as the pre-Sprint-4 `allowlist:` editing model — this is deliberately not automated by a CLI flag in this epic (no evidence yet that it's the common case; add a `scg rule add` convenience command later if usage shows otherwise, not speculatively now).

### 14.4 `MatchResult` gains `sensitivity`/`mode`; `MaskingEngine` scanning becomes unconditional (STORY-1102, 1103, 1104)

`resource_verifier.evaluate()` (currently returns `MatchResult(is_sensitive, is_trusted, fail_safe_triggered)`) gains two fields:
```python
@dataclass(frozen=True)
class MatchResult:
    is_sensitive: bool          # unchanged: FileScanner's literal secret-content detection (taint tracking)
    is_trusted: bool            # unchanged in meaning, now computed at per-URL identity (14.2)
    fail_safe_triggered: bool = False
    sensitivity: str = "public"  # NEW: resolved from the matching PolicyRule (14.1), 3 levels
    mode: str = "mask"           # NEW: resolved from the matching PolicyRule, "mask" | "block" | "allow" (14.4 amendment)
```
`is_sensitive`/`is_trusted` keep their exact current meaning and taint-tracking role (`post_tool_use` → `taint.mark_sensitive()`/`mark_untrusted()`, still read by `scg monitor`'s Sessions panel — unaffected by this epic). `sensitivity`/`mode` are the new, independent axis (§13.8) resolved once per call by taking the *most specific single rule match* across all of a call's identified resources — if resources disagree (rare: a call touching two resources with different rule matches), the most restrictive `mode` (`block` over `mask`) and most restrictive `sensitivity` (`restricted` > `internal` > `public`) wins, matching the existing ANY-match-wins-conservative convention `evaluate()` already uses for `is_sensitive`/`is_trusted`.

**`MaskingEngine.decide()` changes** (STORY-1104 — this is the behavior change users will actually notice):
```python
def decide(self, match: MatchResult, value: Any) -> Decision:
    if value is None:
        return Decision(action="allow")
    findings = tuple(scan_text_for_secrets(str(value)))
    if not findings:
        return Decision(action="allow")
    return Decision(action="block" if match.mode == "block" else "mask", findings=findings)
```
The `taint`/`provenance_risk` gate is removed entirely — every call's payload value is scanned for real secret content, unconditionally, using `match.mode` (resolved per-call from whichever rule applied) instead of the caller-supplied global `mode` argument. `taint: TaintState` is dropped from `decide()`'s signature — `TaintState` itself is **not removed**; it keeps being loaded/updated in `pre_tool_use`/`post_tool_use` exactly as today, purely for `scg monitor`'s existing session-risk display, which has no other data source (`monitor_data.py`/`monitor_app.py` read `has_sensitive_data`/`has_untrusted_data` directly — confirmed by grep, no other consumer).

**NFR consequence, named explicitly rather than left as a footnote (per the Sprint 4 retro lesson — architecture claims about runtime behavior need a named verification step, not a caveat sentence):** today, `scan_text_for_secrets` only runs when a session is already tainted-sensitive-and-untrusted — most calls in most sessions pay zero scanning cost. Under this change, every call with a non-null payload value pays that cost, every time. **`NFR-Perf-UnconditionalScan` (new, provisional):** budget <10ms added latency per scanned payload value (in-process regex/heuristic work, no subprocess spawn — same cost class as `secrets_scan.py`'s existing per-file scan, not a new mechanism). Phase task must verify this with a real test analogous to `tests/test_performance.py`'s existing steady-state test, not assume it holds — same standard as `NFR-Perf-FirstSighting` (§13.3).

**Amendment 2026-07-17 (found during Phase 1 review, resolved with the user directly): a third `mode` value, `allow`, is required.** Unconditional scanning has a real side effect that wasn't caught when §14.4 was first written: under E10, onboarding a destination as "trusted" exempted it from secret-scanning entirely — that's how the existing suggested-onboard-command messaging works (mask once, onboard, never masked again for that exact call). Making scanning unconditional removes that exemption path *entirely*, with nothing designed to replace it — there would be no way left for a user to permanently silence a known false positive (e.g. a test fixture shaped like a real secret, a case that already exists in this very repo's own test suite). Presented to the user as a real fork, not silently decided: accept "no bypass, ever" as final, or add a scoped suppression mechanism. **Decision: add one, narrow and explicit.**

`PolicyRule.mode` gains a third valid value: `"allow"` (`VALID_MODES = ("mask", "block", "allow")`). When the rule that resolves for a call's matched resource has `mode: allow`, `MaskingEngine.decide()` skips `scan_text_for_secrets` entirely for that call and returns `Decision(action="allow")` immediately — the same full-exemption semantics onboarding used to provide under E10, but now:
- **Never automatic.** `scg onboard --target` still only pre-seeds the trust/reputation cache (§14.3, unchanged) — it does not write a rule and does not grant `mode: allow`. A destination being "trusted" no longer implies "exempt from scanning" (that conflation is exactly the bug STORY-1104 fixes).
- **Only reachable by hand-authoring a `rules:` entry** in `scalene_policy.yaml` with an explicit `mode: allow` — a deliberate, visible, reviewable action (the rule shows up in the file, with its own `description`), not an automatic side effect of a CLI convenience command.
- **Scoped by the rule's own `pattern`/`tool`**, same candidacy mechanism as `mask`/`block` rules (§14.1) — a suppression rule is exactly as narrow or broad as its author writes it, auditable the same way.

**Onboard-suggestion messaging must be reworded** (Phase 3 task, not Phase 4/5 — this sprint has no Phase 4/5): the existing message ("run this command to stop future masking") becomes false once this lands. The reworded message states plainly that scanning happens regardless of trust, and — only when a real destination was identified — separately suggests the `rules:`/`mode: allow` path with an explicit warning that it disables scanning for the matched pattern, so a user opts into the risk deliberately rather than being nudged into it by convenient phrasing. `tests/test_onboard_suggestion_e2e.py`'s assertion (onboarding alone stops future masking) no longer holds under the new model and must be rewritten to test the real new behavior — an explicit `mode: allow` rule, not `scg onboard`, is what closes the loop now.

### 14.5 On-disk schema (resolves open question #3)

`scalene_policy.yaml` gains a top-level `rules:` list, sibling to the existing `defaults:` block — `allowlist:` (pre-Sprint-4, dead since E10 shipped — see 14.6) is not reused as the key name, to avoid any reader assuming pre-Sprint-4 semantics:
```yaml
defaults:
  sensitive_by_default: true
  untrusted_by_default: true
  mode: mask

rules:
  - tool: ".*"                                    # regex against tool_name; ".*" = any
    pattern: "https://internal\\.example\\.com/.*" # regex against resource.identity
    sensitivity: internal                          # public | internal | restricted
    mode: block                                    # mask | block
    scanner: reputation                            # optional, inferred from the resource otherwise
    description: "Internal wiki — block on any real finding"
```
`rules:` is optional — a project with none gets exactly the implicit-default-rule behavior (14.1), identical to a brand-new zero-config project. `PolicyConfig.from_yaml` parses `rules:` into `list[PolicyRule]`, validating each entry's `sensitivity`/`mode` against the same fixed value sets `PolicyConfig.mode` already validates against (`PolicyConfigError` on an invalid value — consistent with existing error handling, no new error-reporting mechanism).

### 14.6 STORY-1105: migration, and a real bug found while designing it

**This repo's own checked-in `scalene_policy.yaml` (root of the repo) still has a pre-Sprint-4 `allowlist:` block** (`tool`/`jsonpath`/`pattern`/`target`/`description` entries) that has been **silently dead since E10 shipped** — `PolicyConfig.from_yaml` (current code) only ever reads `defaults:`; nothing in the shipped E10 code parses `allowlist:` at all. This sat unnoticed through Sprint 4's entire close and retro. Not caused by this epic, but found while designing it, and directly relevant: Neo's implementation phase must rewrite this file's dead `allowlist:` block into the new `rules:` schema (14.5) as part of Phase 1 — this repo's own dogfooded config becomes the real (not synthetic) test case for the migration story below.

**Scan cache key scheme (the actual STORY-1105 concern):** existing `.scalene/scan_cache.json` entries from before this epic are keyed `reputation:<host>` (14.2's fix changes this to `reputation:<full-url>`). **Decision: no automatic re-keying.** A host-keyed entry cannot be safely converted to a URL-keyed one — there is no single correct URL to assign it, and mechanically picking one (e.g. `https://<host>/`) would just relocate the exact over-broad-trust defect this epic fixes. Old-scheme entries are simply never matched by new lookups (`reputation:github.com` never equals any `reputation:https://github.com/...` key) — inert, harmless JSON, not silently read as valid trust for a narrower unverified resource (fail-safe-by-construction, satisfies the AC by construction rather than by added migration code). Every URL resource re-verifies under the new scheme exactly like any other never-before-seen resource — same fail-safe-default-then-background-scan path §13.3 already handles, no special-cased migration logic needed. `scalene_policy.yaml`'s schema change is purely additive (14.5) — no pre-existing `rules:` data exists to migrate, and old configs with only `defaults:` continue to load unchanged.

Phase task must include a real test: seed a cache file with an old-format `reputation:<host>` entry, confirm a call against a *different* path on that host is **not** treated as trusted (proves the fail-safe-by-construction claim rather than asserting it).

### 14.7 Devops/Infra impact

None — no daemon, no new port/service/env var, no change to the background-scan subprocess mechanism (§13.7 stands unchanged). No Tank gate.

### 14.8 Carried-forward, not addressed by this epic

`docs/ARCHITECTURE.md` §4's class diagram will need a `PolicyRule` box again (it was correctly removed after E10 per Neo's Phase 5 closure of the 3x-carried-forward note) — flagged for whoever implements Phase 1 to update alongside the code change, not deferred a 4th time.

## 15. Sprint 5 Correction (2026-07-17) — Rule-Driven Access Control Replaces Content-Scanning as the Core Mechanism

Direct user design session, after Phases 1-3 of §14 were already implemented, reviewed, and gated (Trin's Phase 3 UAT flagged a real gap: a rule with `pattern: ".*"` + `mode: allow` could silently disable content-scanning project-wide with zero validation behind it — see Phase 3 UAT notes in `agents/trin.docs/current_task.md`). Working through the fix exposed a deeper question — what does "trust, backed by validation" actually mean structurally — and the answer reframes the *core protection mechanism* itself. Kept as an append-only correction, same convention as §13.1's revision note and §14.4's amendment: the sections above are the historical record of what was built and reviewed, not silently rewritten.

**What changes:** the core decision of whether a tool call proceeds moves from §14.4's model (scan every outbound payload for literal secrets, `mode` chosen by whichever rule matched) to an **access-control model**: a tool call either has a validated, explicit rule permitting it, or it is blocked outright. **Masking/content-scanning is explicitly out of scope for this correction** — deferred to a later pass, not decided here. §14.4's unconditional-scanning design (STORY-1104), the `mode: allow`-skips-scanning mechanic, the reworked onboard-suggestion messaging, and the demo's Part 3/4 rework are all superseded by this model for the call-permission decision. Sprint 5's already-implemented Phase 1-3 code will need reconciling against this corrected model as a follow-up implementation step, through the same Bloop review process as everything else in this document — not retroactively rewritten in place.

### 15.1 Two independent, sticky session tags

Both start at their least-restrictive value at session start (or after an explicit context-clear — the only ways to reset them; never automatic, never time-based):

- **`trust`**: `low` | `med` | `high`. Three levels, not binary, even though only two (`high` and `low`) are actually produced by any transition in this correction's scope — kept 3-valued deliberately so a future scanner/rule can resolve an intermediate trust level without a breaking change later. Starts at `high`.
- **`sensitivity`**: `public` | `internal` | `restricted` (unchanged from §13.8/§14.1 — blast radius if something goes wrong). Starts at `public`.

A session that has only ever touched validated `sensitivity: public` resources at `trust: high` is "clean."

### 15.2 Rule matching requires validation, not just a pattern hit

A `PolicyRule`'s `tool`/`pattern` still decide *candidacy* (§14.1, unchanged) — but a match only counts if the scanner registry's own cache (§13.3, unchanged: `identify()`/`scan()`/`ScanCache`) independently confirms the matched resource is clean. A rule declares *intent* ("I trust this API endpoint," "this package is fine"); the extensible scanner architecture supplies the *validation*. **A resource the scanner has actively found bad is always blocked, regardless of any rule** — a rule can declare intent but can never override a real, validated bad finding. Periodic re-validation/alerting for a resource that goes bad *after* being trusted (the scan cache's existing 24h freshness + background refresh, §13.3, already re-checks it) is real, deliberate future work for the *alerting* half of that story — not required to get this correction's core decision right today.

### 15.3 Per-call decision

For each resource a call touches (via the existing `identify()`, unchanged):

| Resource outcome | Effect |
|---|---|
| Matches a validated rule, `mode: allow`, `sensitivity: public` | Proceeds. Tags unchanged. |
| Matches a validated rule, `mode: allow`, `sensitivity: internal`/`restricted` | Proceeds. `sensitivity` tag escalates to that level if higher than current (sticky, most-restrictive-wins). |
| Matches a rule but validation fails (scanner actively found it bad), or the rule's `mode` isn't `allow` | **Blocked**, unconditionally. |
| No matching rule at all, context currently clean (`trust: high`, `sensitivity: public`) | Proceeds — nothing sensitive is at risk yet (lethal-trifecta logic, unchanged from the project's founding framing: risk requires *both* taint *and* an unvetted channel). Afterward, `trust` tag drops to `low` (fail-safe — an unrecognized resource could be anything). |
| No matching rule at all, context already contaminated (`trust != high` or `sensitivity != public`) | **Blocked** — no explicit clearance exists for this destination while risk is already present. |
| **Matches a rule (`mode: allow`), but not yet validated** (never scanned, or scan still in flight) | **Proceeds immediately, regardless of context** — "trust but verify," §15.2a below. Superseded from an earlier revision of this table (see §15.2a's own correction note) that blocked this case the same as "no rule at all." |

**Correction (2026-08-07, direct user bug report — "my `/**` rule isn't matching the nested folders")**: traced with real evidence (the user's own `scalene_policy.yaml` + `_find_matching_rule` called directly against it) — the wildcard rule *did* match every time, including for deeply-nested, never-before-seen files (`pathspec`'s own `GitIgnoreSpec.match_file()` confirmed recursive-`/**` matching works correctly in isolation). At the time, the gap was §15.2's own validation requirement: a rule match alone was never sufficient on its own, and a brand-new nested file has no scan-cache entry yet on first touch — so it was genuinely `uncleared` until a background scan completed. The bug **at that point** was the *message*: `decide_access()`'s `uncleared` reason said "has no validated, explicitly-allowed rule" for **both** "no rule matched at all" and "a rule matched but this resource isn't verified yet," reading as "your rule isn't matching" when it was. That message-clarity fix is itself now superseded by §15.2a below — the case it was clarifying no longer blocks at all.

### 15.2a "Trust but verify" — a rule match proceeds immediately, verification catches up (2026-08-07, direct user request)

Direct follow-up to the bug report above, in the same conversation: once it was clear the rule really was matching and the friction was §15.2's own "block until independently confirmed" requirement, the user asked for that requirement itself to change — **a human authoring a `mode: allow` rule already made the trust determination; Scalene shouldn't re-litigate it synchronously on every first touch.** This is exactly the "alerting half of that story" §15.2 above named as deliberate future work, now built.

**What changes:** in `decide_access()`, a resource that matches a `mode: allow` rule but hasn't yet been independently confirmed clean (`is_clean_entry` false — never scanned, or the scan is still in flight) is now its own outcome, **`trust_but_verify`**, distinct from both `validated_allow` (already confirmed) and `uncleared` (no rule matched at all):

- Proceeds immediately, from *any* session context (clean or already tainted) — the old table row 5 above (block when contaminated) no longer applies to this case.
- Tags escalate exactly the same way `validated_allow` already does (`taint.escalate_sensitivity(rule.sensitivity)`, `taint.escalate_trust(rule.trust)`) — the rule's own declared intent applies immediately, not just once confirmed.
- `refresh_if_needed()` (unchanged, §13.3) still ensures a real background scan is in flight for the resource — this isn't "skip scanning," only "don't block the call on the scan's result."
- The resource's `cache_key()` is added to a new, session-persisted `TaintState.pending_trust: list[str]` — otherwise there would be nothing recorded to reconcile against later.

**What does *not* change**: a resource the scanner has *already* found bad (`confirmed_bad`) is still blocked unconditionally, regardless of any matching rule — §15.2's core guarantee is untouched. A rule whose `mode` isn't `allow` is still `confirmed_bad` too. Only the "matched, mode=allow, not yet independently confirmed" case moves from blocking to proceeding.

**Reconciliation — the actual "verify" half**: Scalene has no daemon (§6/§11.1 — one process per hook invocation), so there is no way to react the instant a background scan finishes. The only place left to notice is **the next call in the same session**. `resource_verifier._reconcile_pending_trust(taint, cache)` runs first thing inside `decide_access()`, before this call's own resources are even identified: for each `pending_trust` key, look up the real, current cache entry — if it's now a `_BAD_LABELS` result, ratchet `trust` to `low` and `sensitivity` to `restricted` (the same maximum-caution severity `confirmed_bad` represents, since the original call already happened and can't be un-happened); either way (bad or clean), stop tracking it. Still-unresolved scans stay tracked for the call after that. Running this *before* `was_clean` is captured means a retroactively-discovered bad finding correctly affects this same call's own unrelated resources too, not only future ones.

**Known, accepted limitation, not silently glossed over**: if a session's optimistically-trusted resource turns out bad but the session makes no further tool calls afterward, that particular finding is never reconciled or surfaced anywhere — there's no daemon and nothing else triggers reconciliation. This mirrors §15.2's own original framing exactly ("periodic re-validation/*alerting*... is real, deliberate future work") — this correction builds the *tag-escalation* half of that story, not an operator-visible alert/audit-log signal for the case above. That remains open, explicitly deferred, not decided here.

**Real, non-hypothetical residual risk, stated plainly**: the whole point of "trust but verify" is that a resource's actual content can now reach the agent *before* a scan confirms it's safe, for the window between the call and that scan completing. For a brand-new file with no content yet, that window is moot (nothing exists to leak). For a rule matching *existing* content, this is a deliberate trade of a real, if narrow, window of exposure for removing the "block, then retry" round trip on every first touch of anything a human already wrote a broad rule for — a conscious choice, not an oversight.

**Trin's Gate finding (non-blocking, flagged not fixed)**: `_reconcile_pending_trust()` does one `ScanCache.get_by_key()` (a full cache-file read+lock) per tracked entry, on *every* subsequent call in the session — not indexed, not batched. Bounded in practice since a real scan usually resolves within seconds, shrinking the list back down quickly. But a resource whose scan permanently fails (`ScannerMachineryError` inside the detached worker never writing a result — the same failure shape as the stuck `pending_since` reservations found in the "11K pending reviews" investigation, `agents/neo.docs/next_steps.md`) would stay in `pending_trust` forever, paying that cost on every future call for the rest of the session. Worth revisiting if it ever becomes a real, measured problem — not optimized preemptively here.

### 15.4 Aggregation and persistence

Most-restrictive-wins on each axis independently, both across multiple resources touched within one call and across the whole session's lifetime — tags only ratchet toward more restrictive, never relax on their own. This mirrors the existing ANY-match-wins-conservative convention already used for `is_sensitive`/`is_trusted` aggregation (§13.1.1) and for rule-resolved `sensitivity`/`mode` aggregation (§14.4) — same principle, now governing call-permission instead of (or in addition to) content response.

### 15.5 Not yet decided / explicitly deferred

Whether content-scanning (masking) still has a role on top of this access-control decision (e.g. as an additional check even on an *allowed* call) — genuinely open, not decided here, masking is out of scope for this correction by direct instruction. The real on-disk/in-memory shape for the two session tags (replacing or extending `TaintState`'s existing `has_sensitive_data`/`has_untrusted_data` booleans). Exactly how "validation" is checked at rule-match time (a fresh cache lookup vs. requiring a specific freshness bound). How this reconciles with Sprint 5's already-built Phase 1-3 code. This section documents the corrected *model*; implementation is a follow-up phase, through the same Bloop review process as everything else in this document.

## 16. Post-Sprint-6 Correction (2026-07-18) — `scg onboard` Becomes the Single Frontend for Authoring a Rule

Direct user design session, same category as §15 (identified outside the sprint framework, implemented ahead of a formal Bloop review pass — see `agents/neo.docs/next_steps.md` for the standing review-debt note this adds to). Under §15's access-control model, clearing a destination genuinely requires two distinct artifacts: a validated scan result (the cache) and a declared intent (a `PolicyRule`). §13.4/§14.3 built and then hard-locked (Smith's Gate 1, carried to Gate 2) `scg onboard` as pre-seeding the cache *only*, leaving rule-authoring as a separate, undiscoverable hand-edit of `scalene_policy.yaml`. Reading the resulting docs, the user found this split confusing: `--target` reads like it should express a whole rule, but only ever meant "verify this one thing." Their framing, kept verbatim in `onboard.py`'s docstring: *"scg onboard is effectively saying: when a tool call matches these conditions, apply these context labels."*

**What changes:** `scg onboard` now does both halves in one call — the existing real scan (§13.4, unchanged), plus writing a `PolicyRule` to `scalene_policy.yaml`'s `rules:` list. **This explicitly reverses §14.3's "CLI surface does not change" hard requirement** — `--tool`/`--pattern`/`--sensitivity`/`--mode`/`--scanner`/`--description` are added back, one flag per `PolicyRule` field, so the CLI vocabulary matches the YAML schema exactly rather than requiring a second vocabulary for the same concept. At least one of `--sensitivity`/`--mode` is required (the moment of onboarding is the moment a trust decision is declared — never silently inferred); whichever is omitted defaults sensibly (`mode: allow`, `sensitivity: public`). `--pattern` defaults to an exact match on the resolved `--target` (same narrow scope §14.3 already had), so the common case is still a single `--target` invocation with the axis flags added.

`--mode` accepts only `allow`/`block`, not `mask` — under §15's decision, `decide_access()` (what an onboard-authored rule feeds) never distinguishes `mask` from `block`, so exposing it here would produce a rule that silently behaves like `block` while reading like it should do something else. A scan finding that comes back bad blocks onboarding when `--mode allow` is requested (unchanged: can't declare something safe when the scanner disagrees), but not `--mode block` — a known-bad resource, blocked and backed by the finding, is a real, intended use case, not an error path.

**Not yet reconciled:** this section documents the corrected `scg onboard` surface; a real Trin UAT / Morpheus review / Smith gate pass against it (closing out §14.3's now-superseded hard requirement formally, the same way §15 flagged its own review debt) has not run. `docs/USER_STORIES.md`'s STORY-501/STORY-1101-1105 descriptions have not been updated to match.

**Resolved 2026-07-20 — see §17.** §16 is superseded for the *target-identification* half (`--target` is retired), not for rule-authoring (`--sensitivity`/`--mode`/`--scanner`/`--description` survive unchanged, applied per-target). §16's UAT/review/Smith-gate debt above was formally closed in Sprint 7 before §17 was designed — see `task.md`'s Sprint 7 entry.

## 17. E14 Architecture — Tool-Call-Driven Onboarding via the Scanner Framework

Direct user request (2026-07-20, post-Sprint-7): `--target` — a manually-typed `file://`/`https://` URI, unchanged in shape since §13.4 even through §16's rework — is retired in favor of reusing the scanner framework's own `identify()` logic (§13.2, unchanged), the same mechanism `pre_tool_use`/`decide_access()` already run live on every hook call. Formalized here per `docs/USER_STORIES.md` E14 (STORY-1401-1405) and Smith's Gate 1 review (`agents/smith.docs/e14_gate1_review.md`), resolving the open questions Cypher carried forward.

### 17.1 New invocation contract: a tool call, not a URI

`scg onboard` reads a tool-call payload — `{"tool_name": "...", "tool_input": {...}}` — from **stdin** by default, or from a file via `--call PATH`. This deliberately reuses the exact field names `scalene-guard`'s own hook contract already uses (`docs/USER_GUIDE.md`'s `scalene-guard` section) — a developer who already understands "one JSON payload in, one decision out" from that doc needs no second mental model here (Smith's Gate 1 #2/#4 framing). It is not the full hook envelope (no `hook_event_name`/`session_id` needed — onboarding isn't a live hook call) — just the two fields every `Scanner.identify()` call actually consumes.

Resolves OQ2 (Cypher): this *is* the contract. `--call PATH` exists specifically so the common ad-hoc case doesn't require constructing a shell pipe by hand — `scg onboard --call /tmp/call.json` reads the same shape from a file.

### 17.2 Target identification: traverse the registry, don't hand-roll resolution

```python
identified: list[Resource] = []
for scanner in SCANNERS.values():
    identified.extend(scanner.identify(tool_name, tool_input))
```

This is `onboard.py`'s entire target-discovery step (STORY-1401) — `_resolve_resource()`'s hand-rolled URI-scheme dispatch (§13.4, unchanged since Sprint 4) is deleted, not kept alongside the new path. `Resource`s are deduplicated by `(kind, identity)` before confirmation (STORY-1402) — the same generic-fallback-plus-known-field detection that can flag one string via two paths (e.g. a `Bash` command's known field and its generic-fallback scan) must not surface the same target twice in the confirmation list.

### 17.3 Confirmation: interactive by default, two explicit non-interactive escapes

Resolves OQ3 and Smith's Gate 1 hard requirement.

- **Interactive (TTY, default):** every identified `Resource` is printed as a numbered list (kind, identity, claiming scanner). Prompt: `Onboard all N targets? [Y/n/s(elect)]`. `Y`/Enter proceeds with all; `n` aborts as a clean no-op (no scan, no write — STORY-1402 AC3); `s` accepts a comma-separated exclude list before proceeding.
- **Non-interactive escape 1 — `--yes`/`-y`:** skips the prompt, proceeds with every identified target. For automation that trusts its own input shape.
- **Non-interactive escape 2 — `--only IDENTITY[,IDENTITY...]`:** skips the prompt, proceeds only with the named identities (exact match against `Resource.identity`). For automation that wants to assert *which* targets it expects, not just "however many there are" — fails loudly (`OnboardError`) if a named identity wasn't actually identified, so a stale/wrong expectation doesn't silently onboard the wrong resource.
- **Fail-fast, not hang:** if stdin is not a TTY (piped/redirected — the shape every test in this repo uses) and neither `--yes` nor `--only` is given, `main()` raises a clear `OnboardError` ("no TTY for interactive confirmation — pass --yes or --only") instead of blocking on a read that will never resolve. This is what makes the test suite's existing non-interactive call pattern (`tests/test_onboard.py` calling `onboard()` directly, never through `main()`'s prompt) safe by construction, and gives a real, scriptable path through `main()` itself for `demo/run_demo.py` and any future CI use.

### 17.4 Per-target scanning and rule-authoring (STORY-1403)

Unchanged mechanism from §16 per confirmed target: `scan()` runs, a clean result (or an explicit `--mode block` request) writes a `PolicyRule` via `_write_rule()`. **Batch semantics, not all-or-nothing** (Smith's Gate 1 note): each confirmed target is scanned and decided independently; one target failing (`--mode allow` requested, scan came back bad) does not abort the others. `main()` reports a clear per-target result line and a summary (`N onboarded, M blocked`), non-zero exit only if every target failed.

`--sensitivity`/`--mode`/`--scanner`/`--description` (§16) survive as **batch-level flags** — applied identically to every target onboarded in this invocation, since confirming a tool call is confirming one coherent trust decision about it. **`--tool`/`--pattern` are dropped** — they don't compose across N auto-identified targets each with their own natural identity, and hand-authoring a custom pattern/tool filter is still available directly via `scalene_policy.yaml` (§16's power-user path, unchanged) for anyone who needs it. `--pattern` for each written rule defaults to an exact match on that target's own resolved identity (unchanged default from §16), `--tool` defaults to `.*`.

### 17.5 Inventory (STORY-1404): a view, not a new store

Resolves OQ4. **No new on-disk store.** `ScanCache` (§13.3, unchanged) already durably records every scanned resource, keyed `scanner_name:identity`, with label/reason/scanned_at/mtime — this already *is* the per-scanner record of what's been checked. Adding a 3rd store duplicating this would risk exactly the kind of drift Morpheus has flagged against elsewhere in this document (§16's own review). `scg onboard --list [--scanner NAME]` is a new, read-only mode: groups `ScanCache.all_entries()` by `scanner_name`, printing identity/label/last-scanned per entry — mutually exclusive with the onboarding flow (providing `--list` never reads a tool call from stdin). Satisfies Smith's Gate 1 ask for a concrete visible surface without inventing new state.

### 17.6 Reputation score (STORY-1405): real signal, not manufactured precision

Resolves OQ5. `ScanResult` gains one new field:

```python
@dataclass(frozen=True)
class ScanResult:
    label: str               # unchanged: "public" | "sensitive" | "trusted" | "untrusted"
    reason: str = ""          # unchanged
    reputation: float | None = None   # NEW — 0.0 (worst) .. 1.0 (best), None where no graded signal exists
```

Additive, not a breaking change to `label`/`reason` — every existing `decide_access()`/`onboard()` code path that reads `.label` is untouched. STORY-1405's "sensitivity classification" turns out to already be solved: `PolicyRule.sensitivity` (public/internal/restricted, chosen by the developer at onboarding per §16) is the sensitivity axis this project already has — the genuinely new piece is only the reputation score.

**`reputation.py`'s `LocalHeuristicChecker.check()` changes from first-match-wins to evaluate-all-three:** today it returns on the *first* heuristic that trips (IP-literal, punycode, suspicious-length label), discarding whether the others would have too. To produce a real graded score instead of a relabeled boolean, `check()` now runs all 3 unconditionally, collects every triggered reason (joined, not just the first), and `reputation = 1.0 - (triggered_count / 3)`. `is_trusted` (hence `label`) is unchanged in meaning — still `False` if *any* heuristic trips (this project's existing ANY-match-is-unsafe convention, §13.1.1) — only the score is new granularity layered on top, computed from the same real evaluation, not fabricated.

**`FileScanner`'s secrets scan keeps `reputation: None`.** `detect-secrets`' finding set isn't drawn from a small fixed heuristic list the way `reputation.py`'s 3 checks are — inventing a fractional score from an open-ended findings list would be precision the underlying scan doesn't actually support. `None` is honest; a future scanner (or a future revision of `secrets_scan.py`) can populate it once there's a real basis to. `onboard()`'s printed confirmation (`Verified: ...`) includes the reputation score when present (`Verified: reputation:https://x.com -> trusted (score 1.00)`), satisfying Smith's Gate 1 ask that it not be display-invisible.

### 17.7 STORY-1406 — explicitly deferred, not designed here

Scanning a tool call's *response* (as opposed to its pre-call arguments) is not scoped into this architecture. It would directly revisit §15's stated rationale that `post_tool_use` is a no-op because every resource is knowable from `tool_input` before the call runs. Reversing that is a decision on the same order as §15 itself and deserves its own design pass — including its own Cypher story, Smith Gate 1, and architecture section — not a rider on E14. `hook_adapter.post_tool_use` is untouched by this section.

### 17.8 Class diagram / breaking-change surface

`ScanResult` gains `reputation` (§4's class diagram, updated in the same pass as this section — see below). `_resolve_resource()` is deleted from `onboard.py`, not deprecated-in-place. Real call sites needing updates (confirmed via `grep`, not assumed — Smith's Gate 1 flag): `demo/run_demo.py`, `tests/test_demo.py`, `docs/GETTING_STARTED.md`, `docs/SETUP.md`, and `onboard()`'s own direct callers in `tests/test_onboard.py`/`tests/test_getting_started_docs.py` (these call the library function directly, not `main()`, so they're unaffected by the CLI-flag changes but must still pass `tool_name`/`tool_input` instead of `target`).

### 17.9 Not yet decided / explicitly deferred

Whether `--only`'s identity-matching should support globs/regex instead of exact strings (kept exact for v1 — simplest thing that satisfies "assert exactly what I expect," extend only if a real scripting need shows up). Whether `scg monitor`'s TUI should also surface the `--list` inventory view as a 4th panel, or whether the CLI's own `--list` output is sufficient for now — left to whoever implements Phase 1/2, not pre-decided. Exact wording of `main()`'s per-target success/failure summary lines — implementation detail, not an architecture decision.

## 18. E15 Architecture — Configurable Scanner Registry & Extended Scanner Coverage

Direct user request (2026-07-21), per `docs/USER_STORIES.md` E15 (STORY-1501-1504) and Smith's Gate 1 review (`agents/smith.docs/e15_gate1_review.md`). Read `scanner.py`, `policy_config.py`, `resource_verifier.py`, `reputation.py`, `scan_worker.py`, and `subprocess_isolation.py` before designing this — three separate hardcoded scanner-name registries exist today (`scanner.py`'s `SCANNERS`, `scan_worker.py`'s `_SCANNERS`, `subprocess_isolation.py`'s `_KNOWN_SCAN_TYPES`), at two different layers (in-process dispatch vs. the isolated-subprocess boundary, STORY-601). That distinction is what shapes 18.1's scope below.

### 18.1 STORY-1501: `SCANNERS` becomes config-driven — the in-process registry only

`scanner.py`'s module-level `SCANNERS: dict[str, Scanner] = {"secrets": FileScanner(), "reputation": URLScanner()}` becomes the *default* seed of a registry built by a new function:

```python
def load_scanners(raw_config: dict) -> dict[str, Scanner]:
    """raw_config is scalene_policy.yaml's `scanners:` section (or {})."""
```

`scalene_policy.yaml` gains an optional `scanners:` section:

```yaml
scanners:
  extra:
    - name: "asset_inventory"                       # new registry key -- must not collide with a builtin
      import: "myco.scalene_scanners:AssetInventoryScanner"   # "module.path:ClassName"
```

Builtins (`secrets`, `reputation`) always load — omitting `scanners:` entirely reproduces today's exact behavior byte-for-byte (Smith's Gate 1 AC). `import` is split on `:`, resolved via `importlib.import_module` + `getattr`, instantiated zero-arg (`Cls()`, matching `FileScanner()`/`URLScanner()`'s own construction), and validated at load time against the `Scanner` protocol (has `.name`, `.identify`, `.scan` — `isinstance(obj, Scanner)` since `Scanner` is `@runtime_checkable`-eligible, or an explicit `hasattr` triplet if simpler) and against `.name` matching the registry key. A name collision with a builtin, an unimportable path, or a class that doesn't satisfy the protocol all raise `PolicyConfigError` at load time — same fail-loud precedent as `PolicyRule`'s regex/scanner-name validation (§14.1's Trin/E12 finding).

**Threading change, not additive-only:** `PolicyConfig` gains a `scanners: dict[str, Scanner]` field, populated by `load_scanners()` inside `from_yaml` (and defaulting to the two builtins in the bare `PolicyConfig()` constructor, so every existing call site that doesn't load from YAML is unaffected). `resource_verifier.evaluate()`/`decide_access()` iterate `config.scanners` instead of importing the module-level `SCANNERS` constant directly. `onboard.py`'s `identify_targets()`/`_onboard_resource()`/`onboard_targets()` gain an optional `scanners` parameter (defaulting to the module constant, so every existing call site is unaffected); `main()` loads the project's real registry once and threads it through, so a config-declared scanner is identified/onboarded via the CLI too, not just at live hook-decision time.

**Implementation-time correction (Neo, Phase 1, endorsed at code review):** `cache_refresh_worker.py` (STORY-1003's background-refresh worker) stays on the module-level `SCANNERS` constant this epic, not threaded to `config.scanners` as originally planned above. It's a detached subprocess with no shared memory with the parent process — making it see a config-declared scanner would require passing the project's `policy_path` across the subprocess boundary (through `_spawn_background_refresh()`/`refresh_if_needed()`, neither of which carries it today) purely so it can reload `PolicyConfig` itself. Real plumbing, zero payoff this epic (no config-declared scanner ships). Documented in-code as a bounded, non-silent gap: a background refresh for such a resource no-ops (`return 2`) until the next lookup retries via the normal fail-safe path — never a wrong/missing result, just a delayed one. Revisit if a real config-declared scanner ever ships.

**`PolicyRule.scanner`'s validation moves.** Today `PolicyRule.__post_init__` validates `self.scanner in SCANNERS` against the module constant — that can no longer be correct once the registry is config-driven (a rule and the `scanners:` section are both parsed from the same YAML document, and `PolicyRule` has no way to see a dynamically-loaded registry from inside its own `__post_init__`). Validation moves to `PolicyConfig.from_yaml`: build `scanners` from the `scanners:` section *first*, then validate each parsed rule's `scanner` field against that dict, raising the same `PolicyConfigError` as before. Direct `PolicyRule(...)` construction (as several existing unit tests do, bypassing `from_yaml`) no longer fail-fast on a bad `scanner` name at construction time — this is a deliberate, real behavior change, not an oversight; Trin should audit `tests/test_policy_config.py` for any test relying on the old construction-time check and adjust it to assert at the `from_yaml` boundary instead.

**Explicitly deferred, not designed here:** a config-registered scanner's `.scan()` method is free to implement scanning however it wants, but if it wants the existing subprocess-isolation boundary (`run_scanner()`/`scan_worker.py`, STORY-601), `scan_worker.py`'s `_SCANNERS` dispatch table and `subprocess_isolation.py`'s `_KNOWN_SCAN_TYPES` set are **not** made config-driven this epic — both stay hardcoded to `{"secrets", "reputation"}`. No real enterprise scanner ships this sprint (Cypher's story is explicit about this), so there is no concrete case yet to design that extension against; making the isolation boundary itself pluggable without a real second scan-type to validate it against would be speculative. A future epic that ships a real config-registered scanner needing subprocess isolation must revisit this — noted so it isn't silently assumed solved.

### 18.2 STORY-1502: hardcoded restricted paths for `FileScanner`

New module-level constant in `scanner.py`:

```python
_HARDCODED_RESTRICTED_PREFIXES = (
    "/etc",
    os.path.expanduser("~/.ssh"),
)
```

`FileScanner.scan()` checks `resource.identity` against this list *before* calling `run_scanner("secrets", ...)` — a match short-circuits to `ScanResult(label="sensitive", reason="path matches a hardcoded restricted system location")` without ever invoking the secrets-scan subprocess. This is deliberate, not just an optimization: Scalene should not need to read the byte contents of `~/.ssh/id_rsa` to know it's sensitive. Resolves Smith's Gate 1 non-blocking note — the `reason` string is textually distinct from a real secrets-scan finding, so a developer inspecting the audit log can tell "hardcoded system path" apart from "an actual secret pattern matched."

**Resolves Cypher's open question #2 (canonical path list):** kept to exactly the two paths the user named (`/etc`, `~/.ssh`) — not expanded to a broader guessed list (`~/.aws`, `~/.gnupg`, etc.). Those are real candidates but weren't asked for; adding them speculatively risks surprising a developer with a restriction they didn't request and can't find documented anywhere. If a broader default set is wanted later, it's a small, explicit follow-up to this same constant — not something to pre-guess now. `scalene_policy.yaml`'s `rules:` section already lets a developer add their own restricted paths today (§14.1), so nothing is blocked by keeping the hardcoded set narrow.

**Correction (2026-08-07, direct user `*fix` request) — path detection didn't expand shell shorthand or env vars, so a sensitive path could reach this exact restricted-prefix check without ever matching it.** `_HARDCODED_RESTRICTED_PREFIXES` compares against `resource.identity`, which `FileScanner.identify()` built via `os.path.abspath()` alone — a literal string operation that does *not* resolve `~`/`~user` or `$VAR`/`${VAR}`. A Bash command like `cat ~/.ssh/id_rsa` normalized to `<cwd>/~/.ssh/id_rsa`, not the real `~/.ssh/id_rsa` this section exists to catch — silently missing the exact class of path it names. Worse, the generic-fallback regex (`_PATH_FALLBACK_RE`) didn't even match a `~`- or `$`-prefixed token in the first place (only `/`, `./`, `../` prefixes), so this wasn't just a wrong identity, it was often no detection at all.

Fixed in `scanner.py`: new `_normalize_path()` (`expanduser()` → `expandvars()` → `abspath()`, in that order) replaces the bare `os.path.abspath()` call at every `FileScanner.identify()` call site. `expandvars()`/`expanduser()` resolve against *this process's own* environment — correct specifically because the hook runs in the same environment the real Bash tool call would, so `$HOME` etc. expand identically to how the shell itself would. `_PATH_FALLBACK_RE` is broadened to also match `~[\w-]*/...` and `\$\{?\w+\}?/...` shapes.

Broadening the fallback regex is only safe paired with a new existence check: the generic fallback is a heuristic regex match over arbitrary string content (a whole Bash command), not a structured field known to be a path, so each expanded fallback candidate is now validated via `os.path.exists()` before becoming a resource — this both catches an unresolved/unset env var (`expandvars()` leaves `$UNDEFINED_VAR/x` as a literal string, which then almost certainly doesn't exist) and reduces false-positive noise from the broader regex. **Deliberately not applied to the known-field or `file://`-URI paths** — those are structured references (the tool schema, or an explicit URI, already tells us the string is a path), and `Write`'s own target legitimately doesn't exist yet; gating those on existence would have broken new-file detection.

**2nd correction (2026-08-07, direct user bug report) — `FileScanner.scan()` treated "target doesn't exist yet" as a scanning-machinery failure, permanently disabling `scg monitor`'s Allow button for any new-file `Write`.** `pre_tool_use` runs *before* the tool itself executes, so a `Write`'s target is identified and Verify-able while it still doesn't exist on disk. `scan_worker.py`'s `_scan_file()` does a plain `open(path)`, which raised `FileNotFoundError`, surfacing as `machinery_error: True` → `ScannerMachineryError` — `ReviewScreen.action_verify()` already fails safe on that (catches it, leaves the target unverified rather than crashing), which meant the target simply never became verified, ever. There is genuinely nothing to scan yet, which is not a finding of "sensitive" (nothing was found), so it must not behave like one.

Fixed in two places, both required — the first alone was insufficient (caught by the test written to reproduce the bug before the fix, per this project's standing TDD discipline): `FileScanner.scan()` now checks `os.path.exists(resource.identity)` *after* the hardcoded-restricted check above (so writing a brand-new file under `~/.ssh` is still caught) and *before* calling `run_scanner()` — a nonexistent target short-circuits straight to `ScanResult(label="public")`. But `ScanCache.is_fresh()` independently re-checks `os.path.exists()` on every call regardless of what was cached, so even a correctly-cached "public" result for a still-nonexistent file was immediately judged stale — `is_fresh()` now treats `entry.mtime is None` (which `put()` already left unset for a nonexistent target, no change needed there) as "fresh iff the file still doesn't exist" — the moment real content actually appears where there was none at scan time, the cached result correctly goes stale again, forcing a real re-verification, same standard as any other changed file.

**3rd correction (2026-08-07, direct user bug report, found live in a real Rust project) — a source-code comment (`/// doc comment`, or a bare `//`) was mistaken for a reference to the filesystem root.** `_PATH_FALLBACK_RE`'s path-body character class (`[\w./+-]`) includes `/` itself — a run of pure slash characters with nothing else satisfies the regex shape (`///` → matched, `_normalize_path()` → `abspath()` collapses it to bare `/`), and the bare root always exists, so it survived the existence check (§18.2's earlier correction) too. `scanner.py`'s `_find_paths_excluding_urls()` now rejects any fallback candidate with no real content character (alnum or `_`) anywhere in the match — `/`, `//`, `///`, `..` are all pure punctuation and get dropped; any real path (which always names *something*) is unaffected. Scoped to the generic fallback only, not the known-field/`file://` paths (a structured field is still trusted as intentional, same reasoning as every other fallback-only restriction in this file).

**Implementation-time correction (Neo, Phase 2, endorsed at code review) — no `resource_verifier.py` change needed.** This section originally proposed an implicit `PolicyRule(sensitivity="restricted", mode="block")` in `resource_verifier.py` to reach the tri-level `sensitivity` axis. Tracing `decide_access()`'s actual control flow (§15.3) shows that's unreachable dead code, not a real gap: `is_bad` (true whenever the scan-cache entry's `label` is in `_BAD_LABELS`, which includes `"sensitive"`) is checked **before** any rule is even matched, and a `confirmed_bad` resource returns `AccessDecision(allowed=False, ...)` immediately — no rule, however written, can ever move a `label="sensitive"` resource into `validated_allow`. `FileScanner`'s hardcoded short-circuit alone therefore already makes a hardcoded-restricted path unconditionally, un-overridably blocked via the live `decide_access()` path — exactly the "regardless" the user asked for — with zero changes outside `scanner.py`. The tri-level `sensitivity` axis (`PolicyRule.sensitivity`/`taint.sensitivity`) is a *display/escalation* tag for calls that are actually *permitted* (`validated_allow`'s branch); a call this section blocks outright never reaches that branch, so there's nothing for a "restricted" tag to escalate — the call simply doesn't happen. Kept as a private, single-consumer helper inside `scanner.py` (no cross-module `is_hardcoded_restricted()` API, since only `FileScanner.scan()` needs it).

### 18.3 STORY-1503: real external reputation source for `URLScanner`

**Concrete pick: [URLhaus](https://urlhaus.abuse.ch/) (abuse.ch), host lookup endpoint** (`POST https://urlhaus-api.abuse.ch/v1/host/`, form field `host=<hostname>`).

**Correction (Tank's Phase 3 review, 2026-07-21):** this section originally described the endpoint as keyless, per its public documentation. Tank verified directly against the live API (not just its docs, per this section's own original instruction to "specifically verify, not assume") and found it now requires a real `Auth-Key` header — an unauthenticated request returns a bare `{"error": "Unauthorized"}`. User decision (2026-07-21, given 3 options): obtain a free Auth-Key (registration at `https://auth.abuse.ch/`, no cost) and supply it via `SCALENE_URLHAUS_AUTH_KEY` (documented in `.env.example`, never hardcoded/committed). `_query_urlhaus()` checks this env var *before* ever sending a request — if unset, it raises `ReputationCheckUnavailable` immediately with a message pointing at the signup URL, rather than making a request already known to fail. This is real setup friction this project didn't have before (§7.4/STORY-501's "no credentials to provision" v1 preference no longer holds universally — it holds for the always-on local heuristics, not for real external verification), which is why this needed a real decision rather than a silent workaround.

New class in `reputation.py`, implementing the existing `ReputationChecker` protocol (unused until now — built for exactly this extensibility in Sprint 1, per §7.4's own note):

```python
class URLHausChecker:
    def check(self, target: str) -> ReputationResult: ...  # raises ReputationCheckUnavailable on network/timeout/bad-response
```

A new exception, `ReputationCheckUnavailable`, distinguishes "checked, found bad" from "couldn't check" — the composite step below must never conflate the two. New composition function, `reputation.composite_check(target) -> ReputationResult`, called by `scan_worker.py::_scan_reputation` in place of today's direct `LocalHeuristicChecker().check(target)`:

1. Always run `LocalHeuristicChecker` (free, offline, unchanged).
2. Attempt `URLHausChecker` (short timeout, ~3s). On success, combine: `is_trusted = local.is_trusted and remote.is_trusted` (ANY-bad-wins, §13.1.1's existing convention), `score = min(local.score, remote.score)` (conservative — the worse signal wins, mirroring §14.4's most-restrictive-wins aggregation), `reason` joins both non-empty reasons.
3. On `ReputationCheckUnavailable` (network error, timeout, non-200, malformed response): fall back to the local-only result, but **append a distinguishing marker to `reason`** (e.g. `"; external reputation check unavailable: <cause>"`) — resolves Smith's Gate 1 non-blocking note. A developer reading the audit trail can tell "checked externally, came back clean" apart from "external check didn't run this time."

Runs inside `scan_worker.py`'s existing isolated subprocess (STORY-601, `SCALENE_BYPASS=1`) — the same boundary that already isolates file reads for secrets scanning is the correct place for a new outbound network call, not a new isolation mechanism. No new dependency: implemented with `urllib.request` (stdlib), matching this project's existing minimal-dependency posture.

**Flagged for Tank, not resolved here** (per Cypher's story and standing Cypher-Tank protocol): outbound network call to a third-party service, timeout/rate-limit behavior under real load, and whether URLhaus's usage policy is compatible with this project's expected call volume (a scan can happen on every first-sighting of a new URL, project-wide, across potentially many concurrent sessions). Tank must review before this ships — scheduled as an explicit phase task, not folded silently into Neo's implementation.

### 18.4 STORY-1504: new project's own folder defaults to trusted + Internal Only

Resolves Smith's Gate 1 hard requirement (discoverability) and Cypher's own flagged tension with PRD Goal 5 (fail-safe defaults).

**Correction (direct user request, 2026-07-21, after the first implementation had already been gated and approved):** the original design (below, kept for the record) made this an implicit `PolicyRule` constructed in code — real for the purposes of `decide_access()`, but invisible to a developer who didn't know to run `scg onboard --list`. The user's own framing: *"if a yaml doesn't exist then create one with a rule for the project folder but with the timestamp uninitialized so that it scans on first tool use — trying to avoid an implicit special case."* Reworked accordingly:

**Scoping "the project's own folder"** (Cypher's open question #5, unchanged): wherever `scalene_policy.yaml` lives or would live — `cli.py`'s `--policy-path`, resolved to an absolute parent directory.

**Mechanism: write a real rule to a real file, not an in-memory special case.** `policy_config.write_default_project_policy(path, project_root)` — called by `cli.py`'s `main()` only when `policy_path` doesn't exist yet — writes a brand-new `scalene_policy.yaml` containing exactly one ordinary `rules:` entry:

```yaml
rules:
  - tool: ".*"
    pattern: "^<project_root>(/|$)"
    sensitivity: internal
    mode: allow
    scanner: secrets
    description: "project folder default (auto-created)"
```

This is the *same shape* as a hand-written or `scg onboard`-authored rule — parsed by the ordinary `PolicyConfig.from_yaml()` path, with no new `PolicyConfig` field and no `__post_init__` special-casing. **"Timestamp uninitialized" (the user's own phrase):** this function never touches `ScanCache` — no cache entry is pre-seeded, so the project folder's first real tool-use still runs a genuine scan and goes through `decide_access()`'s ordinary `uncleared → validated_allow` progression, identical to any other resource under any other rule. What changes versus an ordinary file with no matching rule at all: today, a file with no rule stays `uncleared` forever, so a *second* unrelated uncleared resource in the same session blocks; under this rule, a clean project file becomes `validated_allow` after its one real scan, so a long session touching only its own project files never hits that wall. **Coexists with §18.2 by construction**: `_HARDCODED_RESTRICTED_PREFIXES` paths are forced to `label="sensitive"` by the scanner itself, so `is_clean_entry` is never true for them — this rule's `mode=allow` can never fire for a restricted subpath.

**A real ordering hazard this design introduces, found and fixed during implementation**: `_find_matching_rule()` returns the *first* declaration-order match, and this rule's pattern is deliberately broad (matches almost anything under the project root). Since the default rule is written *first* (before any onboarding has ever happened), a naive append-only rule-writer would place any later `scg onboard`-authored rule *after* it in the file — meaning the broad default would always match first, silently and permanently shadowing a developer's later, more specific trust decision (e.g. explicitly `mode: block`-ing one sensitive file inside their own project). Fixed in `onboard.py::_write_rule()`: it now inserts a newly-authored rule *before* the auto-created default (identified by its fixed `description`, shared as `PROJECT_FOLDER_DEFAULT_DESCRIPTION` between `policy_config.py` and `onboard.py`) rather than appending after it — every other rule-write keeps its existing append-at-end behavior unchanged, this insertion-point adjustment only applies when the auto-created default is present.

**Discoverability (Smith's Gate 1 hard requirement) is satisfied by construction, not a bolted-on display line**: the rule lives in the developer's own `scalene_policy.yaml`, in plain YAML, exactly where every other rule they'd hand-author or onboard lives — no separate synthetic `--list` line is needed (the prior implementation's synthetic line, and the `trust=trusted` wording bug found in it, are both removed; see git history / this section's prior revision for that finding, now moot since the underlying mechanism changed).

**Fail-safe on write failure**: if the directory isn't writable (or any other `OSError`), `cli.py` logs a warning and falls back to a bare `PolicyConfig()` (today's pre-STORY-1504 fail-safe defaults) — same fail-safe contract as an unreadable/malformed existing policy file.

**Sensitivity here is display/audit only, same as everywhere else today** — `internal` does not itself change what's gated versus what escalates `trust`; that remains the still-open, explicitly-carried STORY-1405 backlog question (does a sensitivity/reputation signal ever drive the allow/block decision itself). This section doesn't answer that question, it only participates in the existing trust-gating mechanism the same way any other `validated_allow` rule does.

### 18.5 Devops/Infra impact

STORY-1503 introduces the project's first default-on outbound network call (URLhaus) — flagged for Tank, per §18.3. STORY-1501's config-driven registry introduces `importlib`-based dynamic loading of developer-supplied module paths — Tank should confirm this doesn't complicate any sandboxing/CI assumptions (a config-declared `import:` path executes arbitrary developer-controlled code at policy-load time, same trust level as the `scalene_policy.yaml` file itself already has today, but worth stating explicitly rather than leaving implicit).

### 18.6 Not yet decided / explicitly deferred

Whether a config-registered custom scanner (STORY-1501) can use the subprocess-isolation boundary (§18.1's deferred item) — no real scanner ships this epic to validate a design against. Exact `--list` output formatting for STORY-1504's synthetic default line (implementation detail). Whether `URLHausChecker`'s short timeout (~3s) needs to be config-tunable — left at a fixed constant for v1, revisit if real-world latency becomes a complaint (same "measure before optimizing" precedent as §13.3's `NFR-Perf-FirstSighting`).

## 19. Post-Sprint-9 Correction (2026-07-22) — Generic Protocol Detection, `file://` Routed to `FileScanner`

Direct user session, after E15 closed. Two related corrections to `scanner.py`'s resource-identification layer (§13.2), prompted by a question about why STORY-1504's auto-created rule carried a `scanner: secrets` filter.

### 19.1 `URLScanner` recognizes any protocol, not just `http(s)`

**Before:** `_URL_FALLBACK_RE` matched only `https?://`. **User's framing:** URLScanner should handle "anything URL with a protocol" — `ftp://`, `ws://`, `s3://`, etc. are all real destinations a tool call could exfiltrate to or fetch from, not just web URLs. `_URI_SCHEME` (a simplified RFC 3986 scheme grammar, `[a-zA-Z][a-zA-Z0-9+.-]*://`) replaces the hardcoded `https?`, broadening both `_URL_FALLBACK_RE` and the path-exclusion span (`_ANY_URI_SPAN_RE`, replacing the old `_URL_SPAN_RE`) to any scheme.

### 19.2 `file://` is the one explicit exception — routed to `FileScanner`, not `URLScanner`

**User's framing:** `file://` is a filesystem reference wearing a URI shape, not a fetchable destination — it should be excluded from URL scanning and identified by `FileScanner` instead, using the same file:// → absolute-path normalization `onboard.py::_resolve_resource()` already does for the legacy single-target flow. New `_FILE_URI_RE` in `scanner.py`, checked inside `FileScanner.identify()`'s generic-fallback loop (works for `file://` appearing in *any* tool's args, not just a hardcoded field — same "traverse all scanners, don't require anyone to remember which one applies" principle behind the rest of this identification layer).

**A real regex bug found while implementing this, not assumed correct:** the first attempt excluded `file://` from `_URL_FALLBACK_RE` via a `(?!file://)` negative lookahead placed at the start of the pattern. A lookahead only blocks a match *starting* at that exact position — `re.finditer` still retries starting one character later, where `(?!file://)` trivially succeeds (`"ile://..."` isn't `"file://"`) and `[a-zA-Z][a-zA-Z0-9+.-]*://` happily accepts `"ile"` as a scheme name, producing a mangled `"ile:///etc/passwd"` resource. Caught by a test that actually exercised `file://` through `URLScanner.identify()`, not by inspection. Fixed by matching *any* scheme (including `file`) in the regex, then filtering `file://` matches out in `URLScanner.identify()` itself (`_is_file_uri()`) — a plain string check has no retry-at-next-position failure mode the way a regex lookahead does.

### 19.3 STORY-1504's auto-created rule drops its `scanner: secrets` filter

Per the same session: the rule's pattern is an absolute filesystem path anchored with `^`, which no URL (of any scheme) or other-scheme identity can ever match — the `scanner: secrets` filter was a redundant assumption on top of an already-sufficient pattern. Removed. General principle stated by the user, applying beyond just this one rule: a rule author shouldn't need to remember/specify a scanner registry name when the pattern alone is already selective — `scanner:` remains available (and still occasionally necessary, e.g. `test_rule_scanner_filter_still_respected`'s disambiguation case) but isn't required by default.

### References
`src/scalene/scanner.py` (`_URI_SCHEME`, `_URL_FALLBACK_RE`, `_FILE_URI_RE`, `_ANY_URI_SPAN_RE`, `_is_file_uri`, `FileScanner.identify()`, `URLScanner.identify()`), `src/scalene/policy_config.py` (`write_default_project_policy()`), `tests/test_scanner.py` (new `file://`/generic-protocol tests, including the regex-retry regression).

## 20. E16 Architecture — Interactive Onboarding Dashboard & Non-Blocking Review Loop

Traced the real control flow of `hook_adapter.pre_tool_use`, `resource_verifier.decide_access`, `monitor_app.py`/`monitor_data.py`, and `onboard.py` before designing any of this — per my own Sprint 9 retro lesson (architecture claims about *existing* code need the same verify-don't-assume discipline as claims about new code). One real correction fell out of that tracing: see §20.3.

### 20.1 STORY-1601: differentiated retry guidance

`AccessDecision` (`resource_verifier.py:165-167`) gains one field: `block_kind: str | None = None`, set to the literal values `"confirmed_bad"` or `"uncleared"` at `decide_access`'s two existing block-return sites (lines 203 and 216-223) — reusing those functions' own real local variable names verbatim rather than inventing new vocabulary (this project has shipped one bug already from a UI label naming a value that didn't correspond to real internal state — Smith's Sprint 9 Phase 4 `trust=trusted` finding — not repeating that here). The `reason` string at each site gets an explicit suffix appended in place: `confirmed_bad` → "...Do not retry without a rule/config change."; `uncleared` → "...Wait for review, then retry.". No change to `pre_tool_use`'s contract, timing, exit codes, or `permissionDecision`/`systemMessage` plumbing — the guidance rides the field that already reaches the agent today.

`_append_audit_log`'s block-event entry (`hook_adapter.py:97-105`) gains `"block_kind": decision.block_kind` alongside the existing fields, for §20.4's dashboard and §20.5's tag rendering to consume without re-running `decide_access` themselves.

### 20.2 STORY-1602: per-scanner activity panel

`MonitorApp.__init__` gains a `policy_path` parameter (default `onboard.DEFAULT_POLICY_PATH`), loading a `PolicyConfig` once at startup the same way `scg onboard`/`scalene-guard` already do (`PolicyConfig.scanners` already defaults to the 2 built-ins when no policy file exists — no new default-handling needed). New `monitor_data.discover_scanner_activity(cache_path, scanners: dict[str, Scanner]) -> list[ScannerActivity]`: reads `ScanCache.all_entries()` (already the monitor's existing read path, `STORY-1005` precedent), groups by the `scanner_name` prefix of each `f"{scanner_name}:{identity}"` key, and reports `busy = any entry for that scanner has an unexpired pending_since` (reusing `scan_cache.PENDING_TIMEOUT_SECONDS`, the same staleness constant `ScanCache.try_reserve` already uses — not a second, driftable timeout). A scanner with zero cache entries at all is simply `idle`, not an error.

### 20.3 STORY-1603: tagged log — full call stream, cost re-assessed after direct user correction

**Traced, not assumed**: today's `#events` panel (`monitor_app.py`) is a *block-events* log — `pre_tool_use` writes an audit entry only when a call is denied (`hook_adapter.py:94-106`); an allowed call writes nothing at all. STORY-1603 as storied says "the tool-call log," which reads as every call.

**First-pass decision (superseded, kept here for the record)**: scoped this down to block-events-only, treating "unconditional new hot-path I/O" as a single undifferentiated NFR risk equivalent to §13.3/13.5's measured first-sighting cost. **Wrong, per direct user correction**: those are two different operations. The measured ~6.6ms avg / ~16ms max cost in §13.3 is specifically subprocess-spawn latency, on a cache miss/staleness — already bounded by `FRESHNESS_SECONDS` (24h, `scan_cache.py:44`), so it recurs rarely once a project's resources are known, exactly the user's own point. Writing one audit-log line is a single buffered `open(path, "a").write(json.dumps(entry) + "\n")` — no subprocess, no scan, not the same cost class, and conflating the two was a category error.

**Decision**: `pre_tool_use` logs every call, not only blocks — `_append_audit_log` runs on the `allowed` branch too (`hook_adapter.py:94-95`), with an `"event": "allow"` entry carrying `tool_name`, `session_id`, and (reusing §20.4's `identify_targets` traversal, run once regardless of outcome) which resource(s)/scanner(s) were touched, so an allowed row can still carry a tag. `monitor_data.BlockEvent` is generalized to a `ToolCallEvent` (or a base class both allow/block share) so the `#events` panel becomes the genuine tool-call stream the user asked for, with `block_kind` (§20.1, `None` for an allow) driving the tag. **Verification, not skipped**: Phase implementation includes a real measured benchmark (N synthetic calls through `pre_tool_use`, before/after this change) confirming the added append doesn't regress the `<15ms` hot-path NFR — a quick check appropriate to the operation's actual cost, not a research spike; this project's "measure, don't assume" rule applies to confirming the size of the cost, not to gating on an inflated guess at what that cost is.

### 20.4 STORY-1604: dashboard + review queue

`_append_audit_log`'s block-event entry also gains `"tool_input": tool_input` (already in scope in `pre_tool_use`, just not persisted today) — the dashboard reconstructs matched scanner(s)/target(s) by calling `onboard.identify_targets(tool_name, tool_input, scanners)`, the exact function `scg onboard` already uses (no second identification mechanism). Each identified `Resource` is looked up in `ScanCache` for its cached label/rule status and `is_fresh()` (Smith's consult flag: `discover_scan_results`-style code needs a `Resource` object to call `is_fresh()`, which this reconstruction already produces as a side effect — no separate helper needed here, unlike §20.2's resource-cache panel which still reads raw keyed entries and is unaffected by this).

**Because `pre_tool_use` already resolved (denied) the call synchronously per §20.1 before the TUI ever sees it, the dashboard is not gating anything live** — it's a to-do list of blocks not yet reviewed, not a blocking prompt. This directly resolves Smith's Gate 1 note on multiple simultaneous block events: new block events append to a simple in-memory FIFO queue (`MonitorApp._pending_reviews: list[BlockEvent]`); the dashboard shows the oldest unresolved one; resolving it (Allow or an explicit Deny acknowledgment) advances to the next. No timeout/expiry logic needed — an ignored entry just stays queued.

**Attention signal (Smith's Gate 1 hard-requirement watch-item)**: on any new block event, `MonitorApp` calls `self.bell()` and updates `self.title` to include the pending-review count (e.g. `"scg monitor — 2 pending review"`). **Flagged for Neo to verify against the actually-installed Textual version's real API during implementation** (`bell()`/`title` are documented Textual `App` members as of the version already pinned in this project's `pyproject.toml`, but per this project's own standing rule, confirm against the real installed package, don't assume the API surface from memory).

Verify/Allow/Deny: **Deny** is the pre-selected default action (the call is already denied regardless — this is just closing the review). **Verify** runs the real scan for every listed target (`scanner_obj.scan(resource)` + `ScanCache(cache_path).put(resource, result)` — the same two calls `onboard._onboard_resource` already makes, invoked directly rather than through `onboard_targets()`'s scan-and-write-rule bundle, since Verify must not write a rule yet). **Allow is disabled until every listed target's Verify has completed** — tracked as simple per-target state on the queued review entry, not a new persisted store (consistent with §20.6 open question #2's stateless-first recommendation).

### 20.5 STORY-1605: pre-filled Allow form

**Default pattern**: reuses `re.escape(resource.identity)` exactly — `onboard.py:298`'s existing default, already as narrow as a single resource's identity. No new derivation logic; confirms Cypher's open question #4 as "reuse the existing mechanism," not a new one.

**Write path**: `onboard._write_rule(policy_path, rule)` (`onboard.py:172-216`) is renamed to `write_rule` (drops the underscore) — it now has a second real caller outside `onboard.py` (the dashboard's Allow action, `monitor_app.py`), so the module-private convention no longer describes its actual usage; a thin duplicate wrapper would just be indirection for no reason. The dashboard constructs a `PolicyRule` the same way `_onboard_resource` does (`onboard.py:296-303`: `tool=".*"`, `pattern=re.escape(resource.identity)` unless the form's user overrides it, `sensitivity`/`mode` from the form) and calls `write_rule` directly — Verify (§20.4) already did the scan, so Allow does not re-scan. `_onboard_resource`'s own existing guard (bad-finding-blocks-onboarding-unless-`mode=block`) is unaffected — the same `PolicyRule`/`OnboardError` construction path enforces it identically whether called from the CLI or the dashboard, no duplicated validation logic.

### 20.6 STORY-1606 — corrected 2026-07-23: hash-snapshot detect-and-restore, not OS-level enforcement

**Backlogged, not built this sprint (2026-07-23, direct user decision)**: the design below is recorded for whenever this is picked up, but E16 ships without it — Phase 6 closes with only the still-true parts of the original write-up (`write_rule`'s existing fail-safe error handling, Trin's tests for it, and the `docs/USER_GUIDE.md` deployment section). Carried to Cypher's backlog, not silently dropped.


**Superseded, kept for the record**: the original design (read-only bind mount of the policy file inside the agent's own execution environment, live-verified by Tank on a reference environment such as Docker) is shelved per direct user request, before Tank's task started. The user's own reasoning: this project doesn't control or deploy the agent's sandbox, and an unenforced documentation-only convention doesn't stop an agent from tampering with whatever *registers* the hook in the first place, not just the policy file — Tank's own live-verification standard doesn't extend to infrastructure outside this project's reach. §20.6's original write-up (the still-real, unaffected `write_rule` `OSError`/`PermissionError` handling, and the `docs/USER_GUIDE.md` deployment section) stays true and useful as a defense-in-depth layer for operators who *do* control their deployment, but is no longer this story's primary mechanism.

**New mechanism, fully inside Scalene's own application code**: a hash-snapshot detect-and-restore loop, no external infrastructure dependency, verifiable with this project's own real test suite.

- **Trusted snapshot**: `policy_config.py` gains `save_policy_snapshot(policy_path, snapshot_path)` — called by both legitimate writers (`onboard.write_rule`, `write_default_project_policy`) immediately after a successful write. Stores `{"hash": sha256(content), "content": content}` as JSON at `snapshot_path` (default: `.scalene/policy_snapshot.json`, alongside the existing `audit.log`/`scan_cache.json`/`state/` — the same gitignored runtime-state directory, not a new location convention).
- **Load-time check**: `policy_config.load_with_integrity_check(policy_path, snapshot_path, audit_log_path)` replaces `cli.py`'s current bare `PolicyConfig.from_yaml(policy_path) if policy_path.exists() else PolicyConfig()` load. Reads the real on-disk file, hashes it, compares to the stored snapshot:
  - **No snapshot yet** (first run after this feature ships, or a pre-existing project's first load): bootstrap — trust current content as the new baseline, write the snapshot, proceed normally. Not a false-positive tamper alarm on a project that predates this mechanism.
  - **Hash matches**: proceed normally, `PolicyConfig.from_yaml(policy_path)`.
  - **Hash mismatch**: the file changed outside `write_rule`/`write_default_project_policy` — restore the on-disk file to the snapshot's content, append a `policy_tamper` audit-log event, and **build the returned `PolicyConfig` from the snapshot's in-memory content, not a fresh disk read** — so even if the restore write itself fails (e.g. a genuinely read-only mount, where `write_rule`'s existing `OSError` handling already degrades safely), the current call's decision still uses trusted content, not the tampered version. Requires factoring `PolicyConfig.from_yaml`'s YAML-parsing body into a `PolicyConfig.from_yaml_text(text)` classmethod `from_yaml` now delegates to — a clean refactor, not a behavior change for existing callers.
- **Notification, operator-only** (direct user decision — a compromised/misbehaving agent should not learn its edit was caught and reverted, only the human operator should): no `systemMessage`/agent-visible signal at all. `monitor_data.AuditTail.poll()` recognizes a third event type (`policy_tamper`, alongside the existing `allow`/`block`) and returns a new `PolicyTamperEvent` (`policy_path`, `detected_at`) interleaved with `ToolCallEvent`s in file order. `MonitorApp.poll_data()` reuses Phase 5's exact attention-signal mechanism (`bell()` + a `self.title` count) for tamper events, and a dedicated, normally-hidden `#tamper-alert` panel shows the count/most-recent-timestamp once any exist.

**What stays true from the original write-up**: `write_rule`'s `OSError`/`PermissionError` handling (already tested, Trin's Phase 6.1) and the `docs/USER_GUIDE.md` deployment section (Phase 6.2) are still valid, complementary advice for operators who do control a deployment target — this new mechanism doesn't replace defense-in-depth via OS/mount permissions, it adds a layer that works even without them.

### 20.7 Devops/Infra impact

None, following the correction above — the hash-snapshot mechanism is pure application code against files this project already owns, no new external dependency, no Tank task required. STORY-601's isolation-mechanism question (scanner-subprocess boundary, local/Docker/cloud) remains the one still-open project-wide infra flag, unaffected by this correction.

### 20.8 Not yet decided / explicitly deferred

- **STORY-1603's full every-call log** (§20.3) — explicitly deferred, needs its own story + a measured hot-path NFR answer, not assumed.
- **`MonitorApp`'s attention-signal API** (§20.4) — needs Neo's real-version confirmation during implementation, not assumed from this doc.
- Whether `_pending_reviews`' per-target Verify-completion state needs to survive a monitor restart (today's design: no, it's in-memory only, consistent with the stateless-TUI-side precedent) — acceptable for v1, revisit only if operators report losing review state as a real complaint.

### References
`src/scalene/resource_verifier.py` (`AccessDecision.block_kind`, `decide_access`), `src/scalene/hook_adapter.py` (`_append_audit_log`'s new `block_kind`/`tool_input` fields), `src/scalene/monitor_app.py`/`monitor_data.py` (new scanner-activity panel, dashboard, review queue), `src/scalene/onboard.py` (`identify_targets`, `write_rule` renamed from `_write_rule`, `re.escape(resource.identity)` default pattern reused), `agents/smith.docs/e16_onboarding_tui_consult.md`, `agents/smith.docs/e16_gate1_review.md`.

## 21. Post-E16 Correction (2026-07-30) — Scanner-Owned Matching, Persisted Review State, Monitor UX

Fast-tracked directly with the user across a single session, dogfooding `scg monitor` after E16 shipped — no formal `*pm plan sprint` cycle; recorded here per this project's own convention (get real bugs/design fixed first, formalize the doc after).

### 21.1 `Scanner.match()`: pattern matching becomes scanner-owned, not one generic regex check

**Problem**: `resource_verifier._find_matching_rule()` applied a single `re.search(rule.pattern, resource.identity)` to every resource regardless of which scanner produced it — no awareness of how `FileScanner` vs. `URLScanner` shape their own identity strings, so the two could drift out of sync with no way for either to correct it.

**Fix**: `Scanner` (`scanner.py`) becomes a real base class (was a structural `Protocol` — `load_scanners()`'s conformance check is still duck-typed `hasattr`, so a third-party scanner that doesn't inherit from it at all is unaffected) with a concrete default `match(rule, resource) -> bool` (plain regex, unchanged behavior). `FileScanner` overrides it to interpret `rule.pattern` as **gitignore syntax** (`pathspec.GitIgnoreSpec`, a real, familiar library/convention rather than a bespoke glob — user's own suggestion mid-session) instead of regex; `URLScanner` doesn't override it (URL identities aren't path-shaped). Compiled specs are `functools.lru_cache`d (hot path: every `pre_tool_use` call re-checks every rule against every resource).

A directory-wide rule needs **2 gitignore lines** — the root path itself, and `root/**` for everything under it (plain gitignore semantics don't match a bare directory via `root/**` alone, only its contents) — this is what "match the whole project folder recursively" actually resolves to. `write_default_project_policy` (§18.4) is updated to this 2-line form.

**Blast radius**:
- `PolicyRule.pattern` is no longer regex-validated at construction time (`policy_config.py`) — its syntax is scanner-owned now, and a real gitignore pattern (a leading `**/`) is often not valid regex at all ("nothing to repeat"). Only `tool` (always regex, every scanner) is still validated eagerly.
- The base `Scanner.match()`'s regex path catches `re.error` and fails safe (no match, not a crash) — necessary once `pattern` isn't guaranteed valid regex for whichever scanner ends up evaluating it.
- 3 call sites that write a FileScanner-targeted default pattern (`onboard.py`, `monitor_app.py`'s Allow form, `write_default_project_policy`) switched from `re.escape(identity)` to a new `scanner.escape_gitignore_literal(identity)` — gitignore has different special characters than regex (`*?[]!#`, not `.()+`).
- New hard dependency: `pathspec>=0.12` in `pyproject.toml`'s base `dependencies` (not an extra like `textual`/monitor) — `FileScanner.match()` runs on the hot-path hook adapter unconditionally.
- **§19.3's principle re-confirmed, not reversed**: an earlier pass through this fix re-added a `scanner: secrets` filter to `write_default_project_policy`'s rule, reasoning that a gitignore-shaped pattern handed to another scanner's regex matcher could raise. Caught on review (direct user question, "did you read the docs?") — §19.3 already states a rule author shouldn't need a `scanner:` filter when the pattern alone is selective, and the `re.error` catch above already handles the raise case at the matcher level. The filter was removed again; §19.3's rule stands.

### 21.2 `Scanner.from_config()`: config-declared scanners can take settings

**Gap**: `load_scanners()` (§18.1) instantiated every scanner via a bare `cls()` — no way for a config-declared scanner (§18.1's own motivating case: enterprise CMDB/vuln-DB scanners) to receive settings (an endpoint URL, a credentials path) from `scalene_policy.yaml`.

**Fix**: `Scanner.from_config(raw_config: dict) -> Scanner` classmethod, default `return cls()` (every existing scanner needs zero changes). `load_scanners()` reads an optional `scanners.extra[].config` sub-block and calls `cls.from_config(config)` if the class defines it, else falls back to bare `cls()` (so a third-party scanner that doesn't inherit `Scanner` at all, like this project's own `DummyScanner` test fixture, keeps working unchanged).

### 21.3 Review queue and Verify status now survive a monitor restart

**Resolves §20.8's explicitly-flagged open question** ("today's design: no, [Verify state is] in-memory only... revisit only if operators report losing review state as a real complaint") — an operator did, in this session, for both Verify status *and* the pending-review queue itself.

**Verify status**: `ReviewEntry.verified` (an in-memory `dict[str, bool]`, reset empty every time `build_review_entry()` reconstructs an entry — including on every restart) is replaced with `is_verified()`/`all_verified()` methods computed live from the real `ScanCache` (`monitor_data.py`) — the same source `target_status()` already reads. A Verify from a previous session stays valid across a restart as long as the cache entry is still fresh (§13.3's existing 24h/mtime freshness, unchanged).

**Review queue**: `AuditTail`'s read offset always starts at 0 for a fresh instance, so every monitor restart re-read the *entire* audit log and re-queued every historical block event — including ones already Denied or Allowed, since neither action recorded "resolved" anywhere. Fixed by appending a `{"event": "review_resolved", "resolved_offset": N}` marker to the same `audit.log` when a review is dequeued (`monitor_app._on_review_resolved`), where `N` is the original block event's own byte offset in the log (`ToolCallEvent.log_offset`, new field — a stable identity that costs nothing extra to compute, `AuditTail.poll()` already reads the file line-by-line). A restart's first `poll()` re-reads the whole file in file order and nets a `block` back out against any later matching `review_resolved`, the same way a live in-session Deny/Allow already worked. A review nobody has acted on yet is unaffected — still reappears, per §20.4's original "no timeout, an ignored entry just stays queued" design.

`hook_adapter._append_audit_log` is renamed to `append_audit_log` (drops the underscore) — same precedent as `write_rule`'s own rename (§20.5): a second real caller (`monitor_app.py`) now exists outside its original module.

### 21.4 `scg monitor` CLI flags + visible state paths

**Problem**: all 4 of `scg monitor`'s state paths (`--policy-path`/`--cache-path`/`--state-dir`/`--audit-log-path`) default to cwd-relative — correct for `scalene-guard`, a hook Claude Code invokes from a fixed project root, but `scg monitor` is launched by hand in a separate terminal, where a different cwd between runs (or between the monitor and wherever the hook is actually running) silently points it at a different `.scalene/`/`scalene_policy.yaml` entirely — indistinguishable from "it forgot," and initially mistaken for exactly that before the real cause (§21.3) was found.

**Fix**: `monitor.py` gains the same 4 flags `scg onboard` already exposes (not new defaults, just an escape hatch to pin them explicitly). `MonitorApp.__init__` resolves all 4 to absolute paths and shows them in `sub_title` (the Header widget's second line) — a cwd mismatch is now visible in the TUI itself, not silent.

### 21.5 ReviewScreen: Next/Prev navigation, editable Allow fields, compact layout

- **Next/Prev + "Review X of Y"**: `ReviewScreen` now takes the full pending-review list + an index (was: a single `ReviewEntry`) so multiple queued reviews can be browsed without closing/reopening the screen. Exposed a latent bug: `dismiss()` used to report a bare `True`/`False`, and `MonitorApp` closed over the *original* entry the screen opened with to know what to dequeue — once Next/Prev can move to a *different* entry before Deny/Allow, that closure would dequeue the wrong one. Fixed: `dismiss()` now passes back the actual `ReviewEntry` resolved (or `None` for a plain Escape).
- **Editable Tool/Pattern in the Allow form**: `tool` defaults to the exact tool name (was hardcoded `".*"`), always editable — call-level, one value for every target in the call. `pattern` defaults to an exact-match gitignore pattern per target; for a multi-target call, a typed pattern now writes **one shared rule** covering every target (not disabled, and not the same pattern duplicated once per target — an earlier pass disabled the field for multi-target calls, corrected on direct follow-up).
- **Sensitivity/Mode become a `RadioSet` grid**, not free-text Input — can't type an invalid value. Single-select is the correct semantic (each is exactly one value), not a checkbox group.
- **Fewer clicks**: Allow auto-focuses the Pattern field; Enter in either text field submits directly.
- **Compact layout**: every `Button`/`Input`/`RadioButton` in `ReviewScreen` uses `compact=True` (a documented Textual option) so the whole Allow form fits an 80x24 terminal. Two real bugs found and fixed while building this, both the same underlying shape — an unconstrained widget silently defaulting to a `1fr` share of remaining space instead of "size to my content": an empty `Static`/`Input` defaulting to `width: 1fr` pushed a sibling off the right edge of the screen entirely (`OutOfBounds` on click); a `Vertical` (`#allow-form`) with no explicit `height` defaulted to `height: 1fr` and got compressed by exactly 1 row once a 2-target call made the targets table 1 row taller, silently overlapping `#allow-error` on top of `#submit-btn` and swallowing every click on it with no visible error. Both fixed with explicit `width: auto`/`height: auto`; both now have geometry-bounds/overlap regression tests, not just eyeballing.

### 21.6 Directory scan target: Verify no-op fixed

`FileScanner.scan()` → `scan_worker._scan_secrets()` called `open(target).read()` unconditionally; a directory target raised `IsADirectoryError`, surfaced as `ScannerMachineryError`, caught by `monitor_app.action_verify()`'s per-target `except: continue` — correct fail-safe behavior for the live TUI, but the net effect was Verify silently doing nothing for a directory target, with no error shown. Fixed: `_scan_secrets()` now walks a directory recursively (`os.walk`), scanning every file and aggregating findings; an individual unreadable file is skipped, not fatal to the whole directory.

### 21.8 `PolicyRule.trust`: a rule can directly declare a resource's trust contribution

**Question that exposed the gap**: "how to assign trust axis on a resource?" First answer was wrong — `mode: allow` + validated already means "don't taint the session's trust for this resource" (a validated resource never enters `uncleared`, the only bucket that ratchets `trust` down, §15.3), but that's an *implicit* side effect, not something a rule directly declares — unlike `sensitivity`, which is a real field. Direct user follow-up, after confirming the implicit mechanism was understood: add a real `trust` field, symmetric to `sensitivity`.

**Design**: `PolicyRule.trust: str = "high"` (`policy_config.py`) — same 3 levels as `TaintState.trust` (`low`/`med`/`high`). Defaults to `"high"`, trust's least-restrictive value, so a rule written before this field existed (every rule in every project today) is unaffected — `taint.escalate_trust("high")` is always a no-op regardless of current trust, since escalation only moves toward *more* restrictive (§15.1). `decide_access()`'s `validated_allow` loop (`resource_verifier.py`) now calls `taint.escalate_trust(rule.trust)` alongside the existing `taint.escalate_sensitivity(rule.sensitivity)` — same mechanism, same ratchet, same aggregation rules, just a second axis a rule can move.

**What this adds over the implicit mechanism**: a rule author can now say "this resource is validated and allowed content-wise, but I still don't fully trust it as an *origin*" (`trust: med` or `trust: low`) — e.g. a third-party vendor API whose payloads scan clean but whose origin isn't fully vetted. Previously there was no way to express that distinction; a validated `mode: allow` resource left trust untouched, full stop.

**What it still can't do, deliberately unchanged**: restore trust already contaminated by something else earlier in the session. The ratchet-only-restrictive rule (§15.1) applies to `trust` exactly as it already does to `sensitivity` — a rule declaring `trust: high` on a validated resource is always a no-op if the session's trust is already `low` from an unrelated prior touch.

**Persistence**: `onboard.write_rule()` omits `trust` from the written YAML when it's the `"high"` default (matching how `scanner`/`description` are already conditionally written) — a rule that doesn't use this field reads exactly like one written before it existed.

**Not yet wired**: `scg onboard --trust` and a Trust field/RadioSet in `scg monitor`'s Allow form (§20.5/§21.5) — today `trust` is hand-authored in `scalene_policy.yaml` only. Flagged as a likely follow-up, not built in this pass.

### 21.9 Adding a rule re-evaluates the rest of the pending-review queue

**Direct user scenario**: a wildcard Allow rule added via one review's Pattern field (`/home/user/project/**`) should render *other* already-queued reviews for files under that same folder moot too — the operator shouldn't have to manually Deny/dismiss every review a broader rule now covers.

**Design, reusing §15.2's own principle rather than a shortcut**: a rule declares *intent*; it only counts once the scan cache independently confirms the resource clean. So this isn't "any review whose target matches the new pattern is resolved" — it's "any review whose target is *already validated* (cache-confirmed clean) under the updated rule set." New `resource_verifier.is_validated_allow(tool_name, resource, config, cache) -> bool` mirrors `decide_access()`'s own `validated_allow` classification exactly (same `_find_matching_rule`, same `_CLEAN_LABELS` check) rather than a second, driftable reimplementation — and reads `cache.get()` directly, not `refresh_if_needed()`, so it never itself spawns a new background scan as a side effect of checking.

`MonitorApp._on_review_resolved` (`monitor_app.py`), after resolving whichever review the operator acted on, reloads `PolicyConfig` from the real policy file and re-checks every *other* still-pending review's targets against it. A review where every target is now `is_validated_allow` is auto-resolved the same way an explicit Deny/Allow is — dequeued and given a real `review_resolved` audit-log marker (§21.3), so it stays resolved across a restart too, not just for the rest of this session.

**Why targets are typically already validated in this exact scenario**: E10's `decide_access()` spawns a background refresh scan for any never-before-seen resource at first sight (§13.3), regardless of whether that call ends up blocked — so by the time a file's own block event reaches the review queue, its cache entry is often already populated. A file that was truly never scanned stays queued even after a matching rule is added, same as `decide_access()` itself would treat it (`uncleared`, not `validated_allow`) — this mechanism doesn't silently skip validation, it just surfaces the *same* validation state the core access decision already uses.

### 21.10 Not yet decided / explicitly deferred

- `ScanCache` freshness for a directory resource keys off the directory's own mtime (changes only when direct children are added/removed, not when a nested file's *contents* change deeper in the tree) — a directory-target Allow rule's cached freshness can go stale without the mtime check catching it. Not fixed here (§21.6's fix was "no effect" → "has effect," not freshness correctness); worth a follow-up if directory-target Allow rules become common.
- Whether `Scanner.from_config()` needs a `get_config()`/introspection counterpart (e.g. for `scg monitor`'s Scanners panel to display a scanner's current settings) — nothing concrete wants this yet.
- §21.8's own carried item: CLI (`scg onboard --trust`) and TUI (Allow form) exposure for `PolicyRule.trust`.
- §21.9's auto-resolution only runs right after a review is explicitly resolved, not on every `poll_data()` tick — a policy file hand-edited outside the TUI while it's running won't retroactively clear now-covered reviews until the next resolution happens. Acceptable for v1; revisit if that's a real complaint.

### References
`src/scalene/scanner.py` (`Scanner` base class, `match()`, `from_config()`, `escape_gitignore_literal`), `src/scalene/policy_config.py` (`PolicyRule.pattern` validation dropped, `PolicyRule.trust`, `write_default_project_policy`), `src/scalene/resource_verifier.py` (`_find_matching_rule` threads `scanners` through, `decide_access`'s `escalate_trust(rule.trust)`), `src/scalene/scan_worker.py` (`_scan_secrets` directory walk), `src/scalene/monitor_data.py` (`ReviewEntry.is_verified`/`all_verified`, `ToolCallEvent.log_offset`, `ReviewResolution`, `AuditTail.poll()`), `src/scalene/monitor_app.py` (`ReviewScreen` Next/Prev, Allow form fields, compact CSS, `sub_title`), `src/scalene/monitor.py` (CLI flags), `src/scalene/hook_adapter.py` (`append_audit_log`), `src/scalene/onboard.py` (`write_rule`'s conditional `trust` emission), `pyproject.toml` (`pathspec` dependency).

## 22. E17 Architecture — Queue-First Monitor Redesign

Traced `monitor_app.py`/`monitor_data.py`/`policy_config.py`/`scanner.py` before designing (Smith's own consult, `agents/smith.docs/e17_monitor_queue_first_consult.md`, already did most of this tracing — confirmed rather than re-derived from scratch).

### 22.1 Screen/navigation model

`MonitorApp` stays the app's base screen (not wrapped in a pushed `HomeScreen`) — same shape E16 already established (`ReviewScreen` pushed on top of the App directly). `MonitorApp.compose()` is rewritten in place (§22.2) rather than introducing a new base-screen class; the only new `Screen` subclass is `RulesScreen` (§22.5), pushed via a binding (`"r"` — see naming note below) and popped via `Esc`, the identical push/pop shape `ReviewScreen` already uses. Three screens total: queue (App), review (pushed from queue), rules (pushed from queue, sibling to review — never pushed from inside review).

**Naming collision, resolved**: today's `"r"` binding is `action_open_review` (open the oldest pending review). STORY-1701 replaces that action's *purpose* — Enter-on-a-queue-row now opens a review, so the standalone "open oldest" shortcut has no reason to keep the same key once Enter covers it. `"r"` is reassigned to open the Rules screen; the old `action_open_review` binding is removed outright (Enter-on-cursor supersedes it, not left as a redundant second path to the same place).

### 22.2 STORY-1701/1702: queue screen + live latest-session

`MonitorApp.compose()` drops `#sessions`, `#events`, `#scanners`, `#scan-results` `DataTable`s and their wrapping containers (`#top-row`, `#scan-results-panel`) entirely. New composition: a `#session-line` `Static`, a `#queue` `DataTable` (`cursor_type="row"`, columns `Tool`/`Resources`/`Kind`/`Reason`/`Age`), a `#status-strip` `Static` (§22.3), then `Footer`.

`selected_session_id`/`show_all_sessions` are removed from `MonitorApp` state entirely, not just unused — nothing reads them once the Sessions table and session-filtered Events log are both gone. `refresh_sessions()` is replaced by `refresh_session_line()`: computes `latest = discover_sessions(self._state_dir)[0] if sessions else None` fresh every `poll_data()` tick (no `is None`-guarded stickiness) and updates `#session-line`'s text (or `_NO_SESSIONS_MESSAGE`, reused verbatim per STORY-1702's AC).

`refresh_queue()` (new) renders `_pending_reviews` into `#queue`, oldest-first (unchanged FIFO ordering `_pending_reviews.append()` already produces — no new sort needed, just displayed instead of only consumed by `action_open_review`). Each row: `entry.event.tool_name`, `len(entry.targets)`, a joined `Kind` string (`", ".join(sorted({t.kind for t in entry.targets}))`, since a call can identify mixed kinds), `entry.event.reason`, and `Age` via the same `_format_relative_time()` helper the old resource-cache panel already used (no new time-formatting code). Empty queue: table cleared, a `"No pending reviews."` `Static` shown in its place (same `.visible`-class toggle pattern `#no-sessions` already uses, not a new mechanism).

`Enter`/`on_data_table_row_selected` on `#queue` opens `ReviewScreen(self._pending_reviews, event.cursor_row, ...)` — `action_open_review`'s old hardcoded-`0` call is gone (§22.1).

**Smith's Gate 1 non-blocking notes (Reason column / session line truncation)**: no code-level fix designed here — both are "verify against a real screenshot at implementation, don't assume it fits," per the note's own framing. Flagged for Neo's Phase 1 UAT, not a design change.

### 22.3 STORY-1703: scanner status strip

New pure function `monitor_data.format_scanner_status(activities: list[ScannerActivity]) -> str` (no `textual` import, same testability boundary every other `monitor_data.py` function already holds): `"Scanners: none configured"` if `activities` is empty, else `"Scanners: " + " · ".join(f"{a.name} {'busy' if a.busy else 'idle'}" for a in activities)` — reuses the exact `busy`/`idle` words `discover_scanner_activity()`'s callers already print today (STORY-1602 precedent), not new vocabulary.

`MonitorApp` renders this into `#status-strip`, a `Static` yielded after `#queue` and before `Footer`. Updated from the existing `poll_data()` tick, no new timer.

**Corrected 2026-08-03 (Phase 2, real-rendered-geometry check)**: the original design above (`dock: bottom` on both `#status-strip` and `Footer`, assuming Textual stacks same-edge docked widgets outward from the edge) was wrong — verified via `widget.region` on the real app, both widgets rendered at the *identical* region (full overlap), not stacked. Real fix: `#queue` gets `height: 1fr` (expands to fill remaining vertical space) and `#status-strip` is left **un-docked**, in normal document flow — since it's the last widget yielded before `Footer` (which removes itself from flow via its own internal dock), it lands exactly one row above the true bottom with no overlap, for any queue length. `tests/test_monitor_app.py::test_status_strip_shows_scanner_activity_and_renders_above_the_footer` asserts `strip.region.y + strip.region.height <= footer.region.y` directly — this is exactly the "verify the real rendered stacking order" flag from the original design paying off: the assumption was wrong, and a real test (not a screenshot eyeball) caught it before it shipped.

STORY-1703's "future indicators" requirement is satisfied by `format_scanner_status`'s signature taking a list and joining independent clauses — a second indicator is a second function returning its own clause, joined the same way, not a rewrite of this one. Not building a second indicator now (nothing else has been requested); the seam is what's being built, not speculative content.

### 22.4 STORY-1704: match-expr-on-top + live match preview

`ReviewScreen.compose()`: `#allow-form` (Tool/Pattern/Sensitivity/Mode) moves to immediately after `#nav-row`, before `#tool-input`/`#targets` — and is no longer conditionally hidden. `on_mount`'s `self.query_one("#allow-form", Vertical).display = False` is deleted; the form is simply always part of the layout, refreshed by `_refresh_allow_form_defaults()` exactly as today (per-entry reset on Next/Prev is unchanged).

**Allow becomes the direct write action, collapsing the old two-step reveal-then-submit.** With the fields always visible, "click Allow to reveal the form, then click Submit rule" has no remaining purpose — `#submit-btn` is removed; `#allow-btn`'s `on_button_pressed` branch calls `self.action_submit_allow()` directly instead of toggling `display`/focusing the pattern field. `#allow-btn`'s existing `disabled` gating (`all_verified()`) is unchanged — STORY-1704's AC that this must not loosen is satisfied by construction, not a separate check. `on_input_submitted`'s Enter-submits-the-rule behavior for the two text inputs is unaffected (still calls `action_submit_allow()`).

**Live match column**: `#targets` gains a 5th column, `Matches?`. New `ReviewScreen._preview_matches(target: Resource) -> str`: builds a transient `PolicyRule` from the *current* form field values (same construction `action_submit_allow` already does at lines 450-451 today — factored into a small shared helper both call, not duplicated) and calls `self._scanners[target.scanner_name].match(rule, target)` — the exact dispatch (`FileScanner`'s gitignore override vs. the base regex default) `action_submit_allow`'s write path already relies on, so there is no second matcher. `PolicyConfigError` (e.g. an in-progress edit to the Tool field that isn't valid regex yet) is caught and rendered as `"—"` (indeterminate), not `"no"` — an invalid-mid-edit rule isn't the same claim as "this valid rule doesn't match," and collapsing them would misinform the operator. Matches this file's own established fail-safe-not-fail-crash standard for this exact live TUI (`action_verify`'s docstring).

`on_input_changed` on `#rule-pattern-input` calls `self.refresh_targets()` (already recomputes the whole targets table on every call; the new column just means it also calls `_preview_matches` per row). Not wired on `#rule-tool-input` — `Scanner.match()` only ever reads `rule.pattern`, never `rule.tool` (confirmed: `Scanner.match`/`FileScanner.match`, `scanner.py:151-170,236-248`), so a tool-field edit can't change any row's `Matches?` value — wiring it would be a no-op call, not a correctness gap.

**Corrected 2026-08-03 (Smith's Gate 2 rejection)**: promoting the Pattern field to always-visible/focusable *before* Verify has run removes the thing that was actually enforcing "Allow requires Verify first." That guarantee lived entirely in the Allow button's `disabled` state plus the old `display=False` gate on the form — neither of which `on_input_submitted`'s Enter-key path (`monitor_app.py:361-367`, unconditionally calls `action_submit_allow()`) was ever gated by. Traced `action_submit_allow()` itself: it has no `all_verified()` check anywhere in its body, only a per-target `BLOCKED_LABELS` check that's silently skipped when a target was never scanned at all (`cache.get(t) is None`). With the field reachable pre-Verify, Enter now writes an Allow rule for an unscanned target with zero review — a real regression of this project's default-deny/Verify-gated-Allow guarantee (STORY-1604's own AC), not a cosmetic gap.

**Fix**: `action_submit_allow()` gains its own guard, first line of the method — `if not self._entry.all_verified(ScanCache(self._cache_path)): self.query_one("#allow-error", Static).update("Verify every target before allowing."); return`. Enforced at the point of consequence (the write itself), independent of which UI path reached it — the Allow button's existing `disabled` state stays as the first, visible line of defense (Nielsen #5, error prevention: don't let the operator reach a dead end), this new check is the one that actually can't be bypassed. No change to `_refresh_allow_form_defaults`, `refresh_targets`, or the `Matches?` column design above — only `action_submit_allow` gains the guard.

### 22.5 STORY-1705: rules screen + reorder

New `monitor_data.py` (no, `policy_config.py` — same module `write_default_project_policy` already lives in, not a new file) function: `swap_rule_order(policy_path: Path, index: int, direction: int) -> None`. `direction` is `+1` (move down) or `-1` (move up). Reads the real YAML exactly as `onboard.write_rule` already does (`yaml.safe_load`, `OSError`/`YAMLError` → this module's own `PolicyConfigError`, matching the module the function lives in rather than reusing `OnboardError`), swaps `data["rules"][index]` with `data["rules"][index + direction]` **as raw dicts** (not reconstructed from `PolicyRule` — every field, including ones a future rule might carry that this code doesn't know about yet, round-trips byte-for-byte except position), writes back via `yaml.safe_dump(data, sort_keys=False, default_flow_style=False)` — identical serialization call `write_rule` already uses, so formatting stays consistent across every write path this file has.

New `RulesScreen(Screen)`: one `DataTable` (`#rules`, columns `#`/`Tool`/`Pattern`/`Sensitivity`/`Mode`/`Trust`), populated from `PolicyConfig.from_yaml(policy_path).rules` (re-read fresh on mount and after every write — same "poll real files" precedent as everywhere else in this app, no separate in-memory rule list that could drift). Two bound actions, `move_up`/`move_down` (bindings, not buttons — matches this screen's simpler, single-table shape; `K`/`J` chosen to avoid colliding with the `DataTable`'s own `↑`/`↓` cursor movement), each: **disabled at the boundary** exactly like `ReviewScreen`'s `#prev-btn`/`#next-btn` disabled-at-index-0/len-1 pattern (`refresh_header`'s `self.query_one("#prev-btn", Button).disabled = self._index == 0`) — swapped here for a bound action's availability rather than a button's `disabled` state, same boundary logic; calls `swap_rule_order`, then **re-reads the file and repopulates the table before accepting the next key** (STORY-1705's hard AC: confirmation before the next input, not just eventually) — a `#rule-confirm` `Static` (same always-persists-until-replaced pattern as `ReviewScreen`'s `#allow-error`, no auto-clear timer per Cypher's Open Question #4 recommendation) shows `"Moved rule #{old} → #{new} — saved."` synchronously in the same handler that performed the write, so there is no frame where the operator could act again before seeing confirmation of what happened.

`Esc` returns to the queue screen (`pop_screen`), consistent with `ReviewScreen`'s existing `escape` binding shape.

### 22.6 Not yet decided / explicitly deferred

- A session-history/scrollback browser for a specific non-latest session (STORY-1701's Origin note flagged this as a real capability the Sessions-table removal loses) — not storied this epic, revisit only if it becomes a real complaint, per the same disposition E16's §20.6 backlog item used.
- `swap_rule_order`'s behavior on a concurrent external edit to `scalene_policy.yaml` between `RulesScreen`'s load and its write (last-write-wins, same as every other write path in this file today) — no optimistic-lock/version-check added; consistent with this project not having built one anywhere else yet.

### References
`src/scalene/monitor_app.py` (`MonitorApp.compose()`/`refresh_session_line`/`refresh_queue`, `ReviewScreen`'s promoted allow-form + `Matches?` column, new `RulesScreen`), `src/scalene/monitor_data.py` (`format_scanner_status`), `src/scalene/policy_config.py` (`swap_rule_order`), `src/scalene/scanner.py` (`Scanner.match()` dispatch, confirmed pattern-only), `agents/smith.docs/e17_monitor_queue_first_consult.md`, `agents/smith.docs/e17_gate1_review.md`, `docs/USER_STORIES.md` (E17, STORY-1701–1705).

## 23. E18 Architecture — Review Queue Overhaul & Rules Editing

Resolves Cypher's 5 open questions (`docs/USER_STORIES.md` E18) in order.

### 23.1 STORY-1801: aggregation + numeric ID

**Aggregation identity (Open Question 1): exact `(tool_name, tool_input)` match, not same-identified-target.** Two calls touching the same resource via genuinely different commands (`cat secret.txt` vs. `rm secret.txt`) are not "the same call" — collapsing them under one row would hide a real, distinct action from the operator. This is the conservative, literal reading of "identical tool calls," and it composes correctly with STORY-1803 (targets are still derived per-entry via the existing `identify_targets()`, unaffected by which calls got grouped into that entry). New `monitor_data.review_aggregation_key(event: ToolCallEvent) -> tuple[str, str]`: `(event.tool_name, json.dumps(event.tool_input, sort_keys=True, default=str))` — sorted-key JSON gives a stable identity regardless of dict insertion order without requiring `tool_input` itself to be hashable.

`ReviewEntry` (`monitor_data.py`) is restructured: the single `event: ToolCallEvent` field becomes `events: list[ToolCallEvent]` (append-ordered, oldest first within the group), plus a new required `id: int`. Three read-only properties replace what call sites used to read directly off the old `event` field:
- `event` → `self.events[-1]` (the most recent occurrence — every event in a group shares the same `tool_name`/`tool_input` by construction, so any field the UI reads off it, e.g. `reason`/`session_id`, is real data from an actual occurrence; recency is just the natural pick).
- `count` → `len(self.events)`.
- `last_seen` → `max(e.timestamp for e in self.events)` (STORY-1802).

`build_review_entry(event, scanners, entry_id) -> ReviewEntry` gains the `entry_id` parameter, constructing a fresh 1-event group.

`MonitorApp` gains `self._pending_by_key: dict[tuple[str, str], ReviewEntry]` and `self._next_review_id: int` (starts at 0, incremented per new group — not persisted; a restart's full log replay reassigns IDs from scratch, matching STORY-1801's own AC that this is a within-session reference, not a persisted identity). `poll_data()`'s `ToolCallEvent`/`event == "block"` branch: compute `key = review_aggregation_key(item)`; if `self._pending_by_key.get(key)` exists, `.events.append(item)`; else increment `_next_review_id`, build a new entry, append to both `_pending_reviews` and `_pending_by_key`.

**Cache-consistency bookkeeping (Open Question 2): one `_forget_entry(entry)` helper, used at every removal site, no exceptions.**
```python
def _forget_entry(self, entry: ReviewEntry) -> None:
    if entry in self._pending_reviews:
        self._pending_reviews.remove(entry)
    stale_keys = [k for k, v in self._pending_by_key.items() if v is entry]
    for k in stale_keys:
        del self._pending_by_key[k]
```
Scanning by identity (`v is entry`) rather than recomputing `review_aggregation_key(entry.events[0])` deliberately — the latter breaks once `entry.events` is already empty (the exact state the `ReviewResolution` branch below produces right before this call), and identity-scan is cheap at this scale (bounded by the count of distinct pending groups, not raw event volume — the whole point of aggregation). Every removal path routes through this one function: `_on_review_resolved` (Allow/Deny), the new `_resolve_as_skipped` (STORY-1804), `_auto_resolve_now_covered_reviews`, and the `ReviewResolution` full-replay branch below. A resolved key can never "resurrect" a phantom group because there is exactly one place membership in `_pending_by_key` is granted (the new-block branch above) and exactly one place it's revoked (`_forget_entry`) — no second, parallel bookkeeping path to drift out of sync.

`ReviewResolution` handling (a `review_resolved` audit-log line, live or replayed from byte 0 on restart) now operates per-occurrence, not per-entry: for each pending entry, filter `events` down by dropping the one matching `resolved_offset`; if the group is now empty, `_forget_entry` it. This is what makes STORY-1801's 4th AC true: resolving an aggregate (any path) must write a `review_resolved` line for *every* occurrence's `log_offset`, not just the representative one — `_append_review_resolved(entry)` (used by Allow/Deny/skip alike) is changed from writing one line to looping `for event in entry.events: append_audit_log(...)`. A restart's full replay then nets every occurrence back out correctly, regardless of how large the original aggregated group was.

### 23.2 STORY-1802: last-seen + recency sort

**Display-only sort (Open Question 3): a fresh sorted copy for the table on every `refresh_queue()` call; `_pending_reviews`'s own storage order is never mutated.** `MonitorApp._pending_reviews` stays FIFO-append order (unaffected by this epic) — `refresh_queue()` computes `ordered = sorted(self._pending_reviews, key=lambda e: e.last_seen, reverse=True)` locally and renders from that. `ReviewScreen` is still constructed against the real `self._pending_reviews` object (not the sorted copy) with an index computed via `self._pending_reviews.index(entry)` at open-time (`on_data_table_row_selected`, see §23.3) — so a currently-open review's Next/Prev navigation, and its behavior when a brand-new block arrives mid-review (today: it becomes reachable via Next, since `ReviewScreen` holds the live list by reference), are both unaffected by this epic. The alternative (sorting `_pending_reviews` in place) was rejected specifically because `poll_data()`'s `refresh_queue()` call is not screen-scoped — it fires on the 0.5s timer regardless of which screen is active, so an in-place sort could silently reshuffle the list an open `ReviewScreen` is mid-navigation through.

### 23.3 STORY-1803: multi-target split rows

`refresh_queue()` (rewritten): iterates `ordered` (§23.2); for each entry, `n = len(entry.targets)`. `n <= 1`: one row (`Resource` = the single target's identity, or `"—"` if `n == 0` — preserves today's no-target case). `n > 1`: one row per target, `Resource` = `f"{t.identity} ({i} of {n})"`, `Kind` = that target's own kind (no longer the joined-kinds string — `_format_kinds()` is deleted, dead code now that Kind is always single-target). All rows for one entry share its `Tool`/`Reason`/`Count`/`Last Seen` cells. A parallel list, `self._queue_rows: list[ReviewEntry]`, gets one (possibly repeated) entry reference per rendered row — `on_data_table_row_selected` looks up `entry = self._queue_rows[event.cursor_row]`, then `index = self._pending_reviews.index(entry)`, then pushes `ReviewScreen(self._pending_reviews, index, ...)` exactly as today. Clicking any of an entry's N rows opens the same review — this story only changes what's visible in the list, per its own 3rd AC.

New `#queue` columns, final order: `ID`, `Tool`, `Resource`, `Kind`, `Reason`, `Count`, `Last Seen`.

### 23.4 STORY-1804: skip / skip-all with confirm

`_resolve_as_skipped(entry)`: `self._append_review_resolved(entry)` (now the per-occurrence loop, §23.1) then `self._forget_entry(entry)` — no `PolicyRule` write, no `ScanCache` touch, satisfying the story's core constraint by construction (this function simply never imports or calls anything from `onboard.py`/`scan_cache.py`).

`"s"` (`action_skip_selected`): resolves `self._queue_rows[table.cursor_row]` directly, no confirmation gate — single, cursor-scoped, same standard as Deny (today's Deny button has none either; Skip is no more destructive than Deny, which already ships unconfirmed).

`"S"` (`action_skip_all`): **two-step arm/confirm**, resolving Smith's Gate 1 finding (must match STORY-1808's delete-confirmation standard). `MonitorApp` gains `self._skip_all_armed: bool = False`. First `"S"`: if not armed, set armed, update a new `#queue-status` `Static` to `f"Press S again to skip all {len(self._pending_reviews)} pending reviews, or any other key to cancel."`, return without acting. Second consecutive `"S"`: armed is `True` → resolve every entry in `list(self._pending_reviews)` via `_resolve_as_skipped`, clear armed, update `#queue-status` to `f"Skipped {n} reviews."`. Any other key event while armed (`on_key`, checked before dispatch) clears `armed` and the status line — the existing DataTable row-select/open-review flow and the `"r"` Rules binding are otherwise unaffected, they just also happen to disarm skip-all if pressed mid-confirm, which is the correct "anything else cancels" behavior. This is a small, local flag rather than a new modal `Screen` — consistent with this app's existing inventory (queue, review, rules) and cheap enough not to warrant one.

### 23.5 STORY-1805: bigger command view

`ReviewScreen` CSS: `#tool-input { max-height: 4; ... }` → `max-height: 12`; `overflow-y: auto` (already present) is unchanged — this raises the cap, not the mechanism, per the story's own framing. `test_allow_form_fields_all_stay_within_a_standard_80x24_screen` (Sprint 11) is re-run as part of Trin's Phase UAT; if the taller `#tool-input` no longer leaves room for Verify/Deny/Allow on an 80x24 terminal, `Screen`'s own default vertical scroll (Textual, no extra code) is the fallback — acceptable per STORY-1805's 2nd AC ("fits and remains reachable," not "never scrolls").

### 23.6 STORY-1806: pattern-field undo/redo

Confirmed by reading the installed `textual==8.2.8` `Input` widget source directly (`.venv/lib/python*/site-packages/textual/widgets/_input.py`): `BINDINGS` covers cursor movement, selection, and deletion only — no `undo`/`redo` action or binding exists. This is genuinely new behavior, not wiring up a framework feature.

New small helper class in `monitor_app.py`, `_InputHistory`: wraps a bounded `list[str]` undo stack + a `list[str]` redo stack for one `Input`. `push(value)` — no-op if `value` equals the top of the undo stack (avoids pushing on every keystroke when nothing changed, e.g. a no-op re-render), else appends and clears the redo stack (standard undo/redo semantics: any new edit invalidates prior redo history). `undo()`/`redo()` pop/move between the two stacks and return the value to restore, or `None` at either boundary (no-op, same "boundary = no-op" convention as `RulesScreen._move`/`ReviewScreen`'s Prev/Next-at-0/len-1).

`ReviewScreen` gets two `_InputHistory` instances, constructed fresh inside `refresh_header()` (already the per-entry reset point for both fields — `_refresh_allow_form_defaults()` runs there) so undo history never crosses a Next/Prev entry switch, satisfying the story's 3rd AC by reusing the existing reset hook rather than adding a new one. `on_input_changed` pushes the new value onto whichever field's history. New key bindings on `ReviewScreen`: `ctrl+z` → `action_undo_field` (undoes whichever of the two Inputs currently has focus, via `self.focused`), `ctrl+y` (and `ctrl+shift+z`, both bound to the same action for cross-platform familiarity) → `action_redo_field`. Restoring a value sets `Input.value` directly and does not re-push onto the same history (the push guard above handles this: setting `.value` to a value already equal to the new stack top is a no-op push).

### 23.7 STORY-1807/1808: Rules screen edit + delete

**Edit widget shape (Open Question 4): reuse `ReviewScreen`'s allow-form pattern, plus one more `RadioSet` for Trust.** Tool/Pattern as `Input`s (`compact=True`, matching `ReviewScreen`), Sensitivity/Mode as `RadioSet`s over `VALID_SENSITIVITIES`/`VALID_RULE_MODES` (identical widget choice and reasoning as `ReviewScreen` — a fixed vocabulary shouldn't be free-text). `Trust` gets its own `RadioSet` over `VALID_TRUST_LEVELS` (3 values, same "can't type an invalid value" reasoning, `policy_config.py`) — `ReviewScreen`'s form has no Trust field today (STORY-1808/E17 shipped Trust as read-only in the Rules table only), so this is new, not copied. `Description` stays a plain `Input` (free text, no fixed vocabulary to enforce).

`RulesScreen` gains an inline edit mode: `"e"` on the row under cursor mounts the form (above `#rule-confirm`, below the `#rules` table) pre-filled from that row's real current `PolicyRule` values; `Enter` (or a Save button, matching `ReviewScreen`'s Enter-submits convention) validates via `PolicyRule(...)` construction (reuses its existing `__post_init__` checks — invalid regex/sensitivity/mode/trust surfaces as `PolicyConfigError`, rendered the same way `ReviewScreen`'s `#allow-error` does) and calls `update_rule`. `Escape` cancels, unmounts the form, writes nothing — matches `ReviewScreen`'s own Escape-leaves-it-alone convention.

**Write-helper convention (Open Question 5): mirror `swap_rule_order` exactly, not `PolicyRule`-object round-tripping.** New `policy_config.py` functions:
```python
def update_rule(policy_path: Path, index: int, rule: PolicyRule) -> None: ...
def delete_rule(policy_path: Path, index: int) -> None: ...
```
Both open with the identical read/validate block `swap_rule_order` already has (`yaml.safe_load`, `OSError`/`YAMLError` → `PolicyConfigError`, `rules` list-type check). `update_rule` builds the replacement dict using `onboard.write_rule`'s existing shape convention (`tool`/`pattern`/`sensitivity`/`mode` always present; `scanner`/`description` included only if non-empty; `trust` included only if not `"high"`, its default) and assigns `data["rules"][index] = rule_dict` — a full replace, not a field-by-field merge, so an edited rule serializes identically to one freshly authored via `write_rule`, with no leftover stale keys from before the edit. `delete_rule` does `del data["rules"][index]`. Both write back via the same `yaml.safe_dump(data, sort_keys=False, default_flow_style=False)` call every other writer in this file uses, and both raise `IndexError` on an out-of-range `index` rather than silently no-op'ing — same caller-bounds-checks-first contract `swap_rule_order`'s own docstring already establishes.

`RulesScreen` delete (`"d"`) reuses STORY-1804's armed/confirm idiom verbatim (`self._delete_armed: bool`, first `"d"` arms + shows `"Press d again to delete rule #N, or any other key to cancel."` in `#rule-confirm`, second consecutive `"d"` executes + shows `"Deleted rule #N — saved."`) — one shared shape for the app's two genuinely destructive actions, not two bespoke ones.

### 23.7a Pattern widen action + breadcrumbs (direct user request, 2026-08-07, post-launch follow-up)

"Hard to select text and type in the field" for a long real file path, with the most common edit being "truncate the tail to a wildcard" — addressed two ways, sharing one model:

- `ReviewScreen._pattern_for_widen_level(target, level)`: `level` trailing path segments (`Path(target.identity).parts`) collapsed into a gitignore `/**` — `level=0` is the exact literal default (`_default_pattern_for`), `level=len(parts)-1` collapses to just the root.
- `alt+w` (`action_widen_pattern`) increments `self._widen_level` by one and applies the resulting pattern — a bare `w` was rejected: Textual's `Input` consumes printable characters before any Screen-level single-letter binding ever sees them, and the Pattern field being focused is the whole point.
- A new `#pattern-breadcrumbs` row (below the Tool/Pattern fields) mounts one compact `Button` per path segment for a single file-kind target (same single-target scoping the Pattern field's own pre-fill already uses; empty for a multi-target call or a URL target — gitignore `/**` isn't a valid regex tail for `URLScanner`'s plain-regex `pattern`). Clicking segment `i` sets `_widen_level = len(parts) - 1 - i` directly — both paths converge on the same `_widen_level`/`_pattern_for_widen_level` state, so alt+w after a breadcrumb click continues progressively from wherever the click left off.
- Both call `_apply_pattern()`, which just sets `Input.value` — the existing `Input.Changed` handler (already wired for typed edits) picks it up for free: live `Matches?` recompute (§22.4) and undo/redo history push (§23.6), no separate plumbing needed.

**Real bug found writing this, not assumed safe**: `Horizontal.remove_children()`/`.mount()` are real (queued) DOM mutations, not instant Python-level list edits — the first version called them fire-and-forget from a sync `_refresh_pattern_breadcrumbs()`, and Next/Prev between two entries crashed (`DuplicateIds`) because the previous entry's buttons hadn't actually been removed yet by the time the new ones mounted under the same `breadcrumb-N` ids. Fixed by making the whole call chain properly async (`_refresh_pattern_breadcrumbs` → `_refresh_allow_form_defaults` → `refresh_header` → `on_mount`/`action_next_review`/`action_prev_review`/`on_button_pressed`) and `await`-ing both the removal and the mount, in that order — caught by this feature's own Next/Prev breadcrumb-reset test, not left to production.

### 23.8 Not yet decided / explicitly deferred

- Decision-undo/redo (undoing a Verify/Allow/Deny after the fact) — explicitly out of scope this epic; the user was asked directly and chose to defer it, since Allow/Verify write to shared files (`scalene_policy.yaml`/`scan_cache.json`) that something else may have already relied on by the time an "undo" would fire. Revisit as its own story/architecture pass.
- The armed/confirm idiom (§23.4, §23.7) is new to this app and now used twice, independently implemented per screen (`MonitorApp._skip_all_armed`, `RulesScreen._delete_armed`) rather than factored into one shared mixin/helper — deliberately not generalized yet on a 2-instance base (this file's own established preference against premature abstraction). Worth extracting if a 3rd destructive action appears in a future epic.

### References
`src/scalene/monitor_data.py` (`ReviewEntry` restructure, `review_aggregation_key`, `build_review_entry`), `src/scalene/monitor_app.py` (`MonitorApp._pending_by_key`/`_forget_entry`/`_resolve_as_skipped`/`action_skip_selected`/`action_skip_all`, `refresh_queue()` rewrite, `ReviewScreen._InputHistory`/undo-redo bindings, `RulesScreen` edit/delete), `src/scalene/policy_config.py` (`update_rule`, `delete_rule`), `src/scalene/onboard.py` (`write_rule`'s dict-shape convention, reused by `update_rule`), `docs/USER_STORIES.md` (E18, STORY-1801–1808).
