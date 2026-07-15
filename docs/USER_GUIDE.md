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

Reads one hook JSON payload from stdin, writes one JSON response to stdout, using Claude Code's real `PreToolUse`/`PostToolUse` hook contract (`hookSpecificOutput.permissionDecision`/`updatedInput` for `PreToolUse`; an empty response for `PostToolUse`, which is pure bookkeeping). You won't invoke this directly in normal use — see [docs/SETUP.md](SETUP.md) for wiring it into `.claude/settings.json`.

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

Launches a live TUI over `.scalene/audit.log` and session taint state — see mask events as they happen and act on suggested rules without leaving the terminal. Requires the optional `monitor` extra: `pip install scalene-guard[monitor]` (already included if you used `make setup` in this repo). Takes no flags yet.

## Onboarding workflow: the fast path

Don't start by hand-writing `--target` — you don't need to know a destination's scheme from memory. Whenever a call gets masked, Scalene's response includes a `systemMessage` with a ready-to-run onboarding command built from the *exact call that was just masked*, e.g. `scg onboard --target https://<domain-this-call-reaches>` with the placeholder filled in from the real destination. You saw this in [Getting Started](GETTING_STARTED.md) step 4 — the `systemMessage` there is the actual output, not a mocked example.

The same suggestion is also what `scg monitor`'s onboarding action runs when you select a mask event and apply it — the console is a UI shell over this exact command, not a separate code path.

**Masking is content-gated, not just session-gated.** A session touching sensitive data earlier is necessary but not sufficient — Scalene only actually masks (and only reports) a call when that specific value scans as a real secret via `detect-secrets`. An ordinary command like `ls -la` or `git status` in a tainted session is allowed through untouched; only a call whose argument actually looks like a credential gets masked. The message says exactly what was detected (e.g. "Possible AWS Access Key detected"), not just that the session was generically risky. It also says whether the destination was *known* to be untrusted (a real reputation finding) versus simply *not yet verified* (no scan has completed for it yet) — the two read differently on purpose, so a brand-new-but-probably-fine destination doesn't sound as alarming as a confirmed-bad one.

Only fall back to hand-writing `--target` yourself if you want to pre-emptively verify something *before* it's ever been blocked (there's no prior call to generate a suggestion from):

- `--target https://<host>` (or `http://`): runs a reputation check on that host now; on success, future calls to it are trusted immediately instead of paying the first-sighting cost.
- `--target file://<path>`: runs a secrets scan on that path now; on success, future reads of it are marked non-sensitive immediately.

Both kinds of target run the same safety check the live hook would eventually run in the background anyway — `scg onboard` just runs it synchronously, right now, instead of waiting for a real call to trigger it. If the check fails, nothing is written to the cache — see [Troubleshooting](#troubleshooting) below.

## Resource verification & the scan cache

Scalene doesn't match calls against hand-authored rules — each scanner (`secrets`, `reputation`) identifies the file paths and URLs a call actually touches, and looks each one up in a project-wide, time-bounded cache (`.scalene/scan_cache.json`, gitignored — it's runtime state, not something you edit or commit):

| Cache state for a resource | What happens |
|---|---|
| Never seen before | Falls back to the same fail-safe defaults as always (`sensitive_by_default`/`untrusted_by_default`) — no added latency for this call. A scan is kicked off in the background so the *next* call to the same resource is faster. |
| Seen recently (within 24h, file unchanged) | Uses the cached, real result directly. |
| Seen a while ago, or a file's content changed since | Uses the last-known result for this call, and re-scans in the background so the next call reflects reality. |

`scalene_policy.yaml` still controls the two knobs that apply when nothing more specific is known:

```yaml
defaults:
  sensitive_by_default: true
  untrusted_by_default: true
  mode: mask   # or "block" — what to do when a real secret is detected (see below)
```

**`mode`** controls what happens when a call is both provenance-risky (tainted-sensitive session, untrusted destination) *and* the specific value actually scans as a real secret:

- `mask` (default): the value is replaced with the mask literal and the call proceeds — the agent keeps working, just without the secret.
- `block`: the call is denied outright (`permissionDecision: "deny"`) with a plain-language reason. Use this if you'd rather stop and reconsider than have the agent silently continue with a masked argument.

Full field-level class model (`PolicyConfig`, `Scanner`, `MatchResult`) is in [docs/ARCHITECTURE.md](ARCHITECTURE.md) §13.

## Troubleshooting

Scalene is built to **fail safe** — an internal problem should degrade to "treat everything as sensitive/untrusted" (the safest default), never to a crash that blocks your agent session or, worse, silently allows something it shouldn't.

| Situation | What happens |
|---|---|
| No `scalene_policy.yaml` at all | Falls back to `PolicyConfig()` defaults (`sensitive_by_default`/`untrusted_by_default` both `true`). |
| `scalene_policy.yaml` exists but is malformed (invalid YAML, wrong types, unreadable) | Falls back to the same fail-safe defaults as a missing file, with a warning logged (`scalene.guard` logger) — **never crashes** `scalene-guard`. |
| Malformed hook input (bad JSON on stdin) or an unrecognized hook event | Returns `{}` — an empty response, which Claude Code's hook contract treats as "allow, no changes" — the call proceeds unmodified rather than blocking your agent. |
| A resource has never been scanned yet | Falls back to the fail-safe defaults for that call (same as an unconfigured resource always has) — not an error, just "not yet verified." |
| The scan cache store itself is corrupted or unwritable, or a scanner's own scan couldn't run at all | This is the one case that's genuinely fatal, not fail-safe: `scalene-guard` exits non-zero with a plain-language reason on stderr (never a raw traceback) — this means the scanning machinery itself is broken, not that a scan found something bad. |
| `scg onboard` blocked | Nothing is written to the scan cache. The failure reason is always plain language (e.g. `Onboarding blocked: secrets check failed — Possible AWS Access Key detected`) — never a raw library exception. |

If you see a raw Python traceback from `scalene-guard` or `scg`, that's a bug — please file an issue rather than assuming it's expected.
