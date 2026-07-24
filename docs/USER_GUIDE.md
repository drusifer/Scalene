# User Guide

Day-to-day reference for Scalene's CLI, policy configuration, and common workflows. New to Scalene? Start with [docs/GETTING_STARTED.md](GETTING_STARTED.md) instead — this guide assumes you've already seen the basic loop once.

## Commands

Scalene installs two binaries: `scalene-guard` (the hook Claude Code invokes automatically — you normally never run this by hand) and `scg` (the developer-facing CLI you actually use).

### `scalene-guard`

```
usage: scalene-guard [-h] [--policy-path POLICY_PATH] [--state-dir STATE_DIR]
                      [--cache-path CACHE_PATH]

options:
  -h, --help            show this help message and exit
  --policy-path POLICY_PATH
  --state-dir STATE_DIR
  --cache-path CACHE_PATH
```

Reads one hook JSON payload from stdin, writes one JSON response to stdout, using Claude Code's real `PreToolUse`/`PostToolUse` hook contract (`hookSpecificOutput.permissionDecision` for `PreToolUse` — the full allow/block decision; an empty response for `PostToolUse`, which is a no-op — every resource a call touches is knowable from its arguments alone, so `PreToolUse` already makes the complete decision before the call ever runs). You won't invoke this directly in normal use — see [docs/SETUP.md](SETUP.md) for wiring it into `.claude/settings.json`.

### `scg onboard`

```
usage: scg onboard [-h] [--call CALL] [--yes] [--only ONLY] [--list]
                   [--sensitivity {public,internal,restricted}]
                   [--mode {allow,block}] [--scanner SCANNER]
                   [--description DESCRIPTION] [--policy-path POLICY_PATH]
                   [--cache-path CACHE_PATH]

options:
  -h, --help            show this help message and exit
  --call CALL           Path to a JSON {tool_name, tool_input} file (default:
                        read from stdin)
  --yes, -y             Onboard every identified target without an interactive
                        prompt
  --only ONLY           Comma-separated identities to onboard, skipping the
                        prompt (fails if a named identity wasn't identified)
  --list                List onboarded targets from the scan cache (optionally
                        filtered by --scanner) instead of onboarding
  --sensitivity {public,internal,restricted}
                        public|internal|restricted (default 'public' if --mode
                        is given)
  --mode {allow,block}  allow|block (default 'allow' if --sensitivity is
                        given)
  --scanner SCANNER     Optional disambiguating scanner name (usually
                        inferred); also filters --list
  --description DESCRIPTION
                        Why this rule exists (recommended)
  --policy-path POLICY_PATH
  --cache-path CACHE_PATH

Reads a tool call ({"tool_name": ..., "tool_input": ...}) from stdin by default,
or --call PATH -- the same field names scalene-guard's own hook contract already
uses. Every scanner's identify() runs against it; identified targets are confirmed
(interactively, or via --yes/--only) before anything is scanned or written.

At least one of --sensitivity/--mode is required -- onboarding is the moment you
declare a trust decision, so it's never silently inferred. Whichever you omit
defaults sensibly (mode: allow, sensitivity: public).

--mode does not accept 'mask': under the live access-control decision
(docs/ARCHITECTURE.md sec15), a rule's mode only ever distinguishes 'allow' from
'not allow' -- mask would silently behave exactly like block.
```

`scg onboard` identifies targets automatically from a real tool call by traversing the same scanner registry `pre_tool_use` already runs live — you no longer resolve or type a `file://`/`https://` URI by hand. Give it a tool call (piped as JSON on stdin, or `--call PATH`), and it runs every registered scanner's `identify()` against it, collecting every distinct resource found across all scanner types in one pass.

**Confirmation always happens before anything is scanned or written.** With a real terminal attached, you get a numbered list of what was identified and a `[Y/n/s(elect)]` prompt (`Y` accepts everything, `n` aborts as a clean no-op, `s` lets you exclude specific numbered entries). For scripts and automation, two non-interactive escapes exist: `--yes` accepts every identified target, `--only <identity,...>` accepts exactly a named subset (and fails loudly, naming what's missing, if an identity you named wasn't actually identified). If neither is given and there's no real terminal to prompt, `scg onboard` fails immediately with a clear error rather than hanging.

Once targets are confirmed, each one is scanned for real and, on a clean result (or an explicit `--mode block`), a `rules:` entry is written to `scalene_policy.yaml` — the frontend for authoring a rule, effectively: "when a tool call matches these conditions, apply these context labels." Flag names match `PolicyRule`'s field names exactly — no separate vocabulary between the CLI and the YAML schema. `--sensitivity`/`--mode`/`--scanner`/`--description` apply once, to every confirmed target in the batch, since confirming a tool call is confirming one coherent trust decision about it; each written rule's `pattern` defaults to an exact match on that target's own identity, `tool` to `".*"` (there's no `--tool`/`--pattern` override in this flow — hand-author a `rules:` entry directly in `scalene_policy.yaml` if you need a broader pattern or tool filter than a specific confirmed target).

**Batch semantics, not all-or-nothing**: one target failing (e.g. `--mode allow` requested but the scan found something) doesn't abort the others — you get a clear per-target result line and a final `N onboarded, M blocked` summary. A scan that comes back bad blocks that target when requesting `--mode allow` (can't claim something is safe when the scanner disagrees) — but not `--mode block`, the real use case for declaring a known-bad resource blocked, backed by the finding rather than despite it. When a scanner reports a graded reputation score (currently `reputation`'s 3 local heuristics), it's shown alongside the label (`-> trusted (score 1.00)`).

**`scg onboard --list [--scanner NAME]`** shows what's already been onboarded — a read-only view grouped by scanner, reading `.scalene/scan_cache.json` directly rather than a second store that could drift from it.

**Known limitation:** writing a rule re-parses and re-serializes the whole policy file — any hand-added comments in an existing `scalene_policy.yaml` will not survive an onboard-triggered rewrite.

### `scg install-hooks`

```
usage: scg install-hooks [-h] [--settings-path SETTINGS_PATH]

options:
  -h, --help            show this help message and exit
  --settings-path SETTINGS_PATH
```

Wires `scalene-guard` into `PreToolUse`/`PostToolUse` in `.claude/settings.json`. Merges non-destructively and is idempotent — safe to run again. Full detail: [docs/SETUP.md](SETUP.md).

### `scg monitor`

Launches a live TUI over `.scalene/audit.log`, session trust/sensitivity tags, and the resource cache — every tool call tagged and legible without color, a per-scanner activity panel, and an interactive Verify/Allow/Deny dashboard for reviewing and clearing blocked calls without leaving the terminal. Requires the optional `monitor` extra: `pip install scalene-guard[monitor]` (already included if you used `make setup` in this repo). Takes no flags.

**Full walkthrough with screenshots: [docs/MONITOR_GUIDE.md](MONITOR_GUIDE.md).**

## The access-control model

Scalene's core decision (docs/ARCHITECTURE.md §15) is whether a tool call is **permitted**, not whether its content gets scrubbed. Every session carries two independent, sticky tags, both clean at session start and only ever ratcheting toward more restrictive:

- **`trust`**: `low` | `med` | `high` (starts `high`).
- **`sensitivity`**: `public` | `internal` | `restricted` (starts `public`).

For each resource (file path or URL) a call touches:

| Situation | Result |
|---|---|
| Matches a rule, cache confirms clean, `mode: allow` | Proceeds. `sensitivity` escalates to the rule's level if higher than current. Bypasses the block-when-tainted gate below entirely — this is what onboarding + a rule is *for*. |
| Cache confirms the resource is actually bad (real scan finding), or a matching rule's `mode` isn't `allow` | **Blocked**, unconditionally — a rule can declare intent, but it never overrides a real, validated bad finding. |
| No matching rule, and the session is still clean (`trust: high`, `sensitivity: public`) | Proceeds — nothing sensitive is at risk yet. Afterward, `trust` drops to `low` (fail-safe: an unrecognized resource could be anything). |
| No matching rule, and the session is already tainted | **Blocked** — no explicit clearance exists for this destination while risk is already present. |

Tags persist for the life of the session (most-restrictive-wins if multiple calls touch different classifications) and are only cleared by starting a new session.

Clearing a destination is always explicit and validated — one `scg onboard` call, covered above under [`scg onboard`](#scg-onboard), does both halves (a real scan, and declaring what to do with it) together. See [Getting Started](GETTING_STARTED.md) for a full worked example.

## Resource verification & the scan cache

Each scanner (`secrets`, `reputation`) identifies the file paths and URLs a call actually touches, and looks each one up in a project-wide, time-bounded cache (`.scalene/scan_cache.json`, gitignored — it's runtime state, not something you edit or commit):

| Cache state for a resource | What happens |
|---|---|
| Never seen before | Treated as unmatched (see the access-control table above) — no added latency for this call. A scan is kicked off in the background so the *next* call to the same resource is faster. |
| Seen recently (within 24h, file unchanged) | Uses the cached, real result directly. |
| Seen a while ago, or a file's content changed since | Uses the last-known result for this call, and re-scans in the background so the next call reflects reality. |

`scalene_policy.yaml` has no required fields — an empty (or missing) file means nothing has been explicitly claimed, so every unrecognized destination is subject to the block-when-tainted gate. An optional `rules:` list declares explicit, validated trust decisions:

```yaml
rules:
  - tool: "WebFetch"                              # regex against the tool name (".*" = any)
    pattern: "https://internal\\.example\\.com/.*" # regex against the resource's identity (file path or URL)
    sensitivity: internal                           # public | internal | restricted
    mode: allow                                     # allow | block
    scanner: reputation                             # optional — inferred otherwise
    description: "Internal wiki — reviewed and trusted"
```

**Trust vs. sensitivity are independent.** Trust answers "could this source cause the agent to do something malicious" (verified per exact resource — onboarding one path never vouches for a whole host). Sensitivity answers "what's the blast radius if something does go wrong," exactly three levels (`public`/`internal`/`restricted`), set per-rule.

Full field-level class model (`PolicyConfig`, `PolicyRule`, `Scanner`, `TaintState`, `AccessDecision`) is in [docs/ARCHITECTURE.md](ARCHITECTURE.md) §15.

## Deployment: keeping the policy file read-only from the agent

`scalene_policy.yaml` and `.scalene/audit.log` are the rules constraining an agent session and the record of what it did — an agent that could edit either would defeat the point. Scalene's own code already fails cleanly if a write is attempted against a read-only policy file (a clear "Onboarding blocked: could not write \<path\> — \<reason\>" message, not a raw traceback), but Scalene doesn't control the sandbox an agent harness runs its tool calls in, so the actual read-only *enforcement* is an operator/deployment choice, not application code:

- Run the agent's own tool execution (wherever `scalene-guard` is invoked as a hook) with `scalene_policy.yaml` and `.scalene/audit.log` mounted **read-only**.
- Run `scg monitor` — and any `scg onboard` invocation you make yourself — **outside** that boundary, with normal write access to the same underlying files, so Allow/onboard decisions still work for you as the operator.
- Concretely: a read-only bind mount (Docker: `-v $(pwd)/scalene_policy.yaml:/workspace/scalene_policy.yaml:ro`) or OS file permissions, depending on how the agent harness is deployed.

This is the same class of isolation question as scanner-subprocess isolation (docs/ARCHITECTURE.md §6/§18.5) — the concrete mechanism depends on your environment (local/Docker/cloud), not something Scalene prescribes a single answer for.

## Troubleshooting

Scalene is built to **fail safe** — an internal problem should degrade to blocking an ambiguous call, never to a crash that blocks your agent session or, worse, silently allows something it shouldn't.

| Situation | What happens |
|---|---|
| No `scalene_policy.yaml` at all | Nothing has been claimed — every unrecognized destination is subject to the block-when-tainted gate, same as an empty `rules:` list. |
| `scalene_policy.yaml` exists but is malformed (invalid YAML, wrong types, unreadable) | Falls back to the same as a missing file, with a warning logged (`scalene.guard` logger) — **never crashes** `scalene-guard`. |
| A rule's `tool`/`pattern` isn't a valid regex | Rejected at config-load time with a clear `PolicyConfigError`, not deep in the hot path on the next matching call. |
| Malformed hook input (bad JSON on stdin) or an unrecognized hook event | Returns `{}` — an empty response, which Claude Code's hook contract treats as "allow, no changes" — the call proceeds unmodified rather than blocking your agent. |
| A resource has never been scanned yet | Treated as unmatched for this call (see the access-control table above) — not an error, just "not yet verified." |
| The scan cache store itself is corrupted or unwritable, or a scanner's own scan couldn't run at all | This is the one case that's genuinely fatal, not fail-safe: `scalene-guard` exits non-zero with a plain-language reason on stderr (never a raw traceback) — this means the scanning machinery itself is broken, not that a scan found something bad. |
| `scg onboard` blocked | Nothing is written to the scan cache. The failure reason is always plain language (e.g. `Onboarding blocked: secrets check failed — Possible AWS Access Key detected`) — never a raw library exception. |

If you see a raw Python traceback from `scalene-guard` or `scg`, that's a bug — please file an issue rather than assuming it's expected.
