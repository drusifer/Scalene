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
usage: scg onboard [-h] --target TARGET [--cache-path CACHE_PATH]

options:
  -h, --help            show this help message and exit
  --target TARGET       file://<path> (runs a secrets scan) or
                        http(s)://<host> (runs a reputation check)
  --cache-path CACHE_PATH
```

Pre-seeds the resource cache (`.scalene/scan_cache.json`) for a target you already know is fine, after running a safety check first (see [Onboarding workflow](#onboarding-workflow-the-fast-path) below — you should almost never need to type `--target` out by hand). `--target`'s URI scheme resolves which scanner runs: `file://` paths get a secrets scan, `http(s)://` hosts get a reputation check. There's nothing else to specify — no tool name, no JSONPath, no pattern — the cache is keyed by the resource itself (the file's path, or the host), not by which call touched it.

### `scg install-hooks`

```
usage: scg install-hooks [-h] [--settings-path SETTINGS_PATH]

options:
  -h, --help            show this help message and exit
  --settings-path SETTINGS_PATH
```

Wires `scalene-guard` into `PreToolUse`/`PostToolUse` in `.claude/settings.json`. Merges non-destructively and is idempotent — safe to run again. Full detail: [docs/SETUP.md](SETUP.md).

### `scg monitor`

Launches a live TUI over `.scalene/audit.log`, session trust/sensitivity tags, and the resource cache — see block events as they happen, and see what's actually in `.scalene/scan_cache.json` (resource, label, last-scanned time) without leaving the terminal. The resource panel reads the cache file directly — it's not a separate summary that could drift from what the live hook actually consults. Requires the optional `monitor` extra: `pip install scalene-guard[monitor]` (already included if you used `make setup` in this repo). Takes no flags yet.

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

**Clearing a destination always takes two explicit steps** — never one:

1. **Verify it for real**: `scg onboard --target <uri>` runs an actual scan (secrets scan for `file://`, reputation check for `http(s)://`) and seeds the cache on success.
2. **Write a rule** in `scalene_policy.yaml` saying what to do with a verified destination — onboarding alone only affects classification data, it never grants permission on its own.

```
usage: scg onboard [-h] --target TARGET [--cache-path CACHE_PATH]

options:
  -h, --help            show this help message and exit
  --target TARGET       file://<path> (runs a secrets scan) or
                        http(s)://<host> (runs a reputation check)
  --cache-path CACHE_PATH
```

See [Getting Started](GETTING_STARTED.md) for a full worked example of both steps.

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
