# User Guide

Day-to-day reference for Scalene's CLI, policy configuration, and common workflows. New to Scalene? Start with [docs/GETTING_STARTED.md](GETTING_STARTED.md) instead — this guide assumes you've already seen the basic loop once.

## Commands

Scalene installs two binaries: `scalene-guard` (the hook Claude Code invokes automatically — you normally never run this by hand) and `scg` (the developer-facing CLI you actually use).

### `scalene-guard`

```
usage: scalene-guard [-h] [--policy-path POLICY_PATH] [--state-dir STATE_DIR]

options:
  -h, --help            show this help message and exit
  --policy-path POLICY_PATH
  --state-dir STATE_DIR
```

Reads one hook JSON payload from stdin, writes one JSON response to stdout, using Claude Code's real `PreToolUse`/`PostToolUse` hook contract (`hookSpecificOutput.permissionDecision`/`updatedInput` for `PreToolUse`; an empty response for `PostToolUse`, which is pure bookkeeping). You won't invoke this directly in normal use — see [docs/SETUP.md](SETUP.md) for wiring it into `.claude/settings.json`.

### `scg onboard`

```
usage: scg onboard [-h] --target TARGET --tool TOOL --jsonpath JSONPATH
                   --pattern PATTERN [--description DESCRIPTION]
                   [--policy-path POLICY_PATH]

options:
  -h, --help            show this help message and exit
  --target TARGET       file://<path> (runs a secrets scan) or
                        http(s)://<host> (runs a reputation check)
  --tool TOOL
  --jsonpath JSONPATH
  --pattern PATTERN
  --description DESCRIPTION
  --policy-path POLICY_PATH
```

Adds one rule to `scalene_policy.yaml`'s single `allowlist`, after running a safety check first (see [Onboarding workflow](#onboarding-workflow-the-fast-path) below — you should almost never need to type this command's flags out by hand). There's no separate `--list-type` flag: `--target`'s URI scheme *is* the list type — `file://` and `http(s)://` targets get verified differently and affect different parts of the decision (see [Policy configuration](#policy-configuration) below), but they live in one list and go through one command.

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

Don't start by hand-writing `scg onboard`'s four required flags — you shouldn't need to know Scalene's JSONPath/pattern format from scratch. Whenever a call gets masked, Scalene's response includes a `systemMessage` with a ready-to-run onboarding command built from the *exact call that was just masked*: the real tool name, a JSONPath into the field that matched, and an escaped literal pattern of the real value. You saw this in [Getting Started](GETTING_STARTED.md) step 4 — the `systemMessage` there is the actual output, not a mocked example.

The same suggestion is also what `scg monitor`'s onboarding action runs when you select a mask event and apply it — the console is a UI shell over this exact command, not a separate code path.

**Masking is content-gated, not just session-gated.** A session touching sensitive data earlier is necessary but not sufficient — Scalene only actually masks (and only reports) a call when that specific value scans as a real secret via `detect-secrets` (the same engine `scg onboard`'s allowlist check uses). An ordinary command like `ls -la` or `git status` in a tainted session is allowed through untouched; only a call whose argument actually looks like a credential gets masked. The message says exactly what was detected (e.g. "Possible AWS Access Key detected"), not just that the session was generically risky.

Only fall back to hand-writing the flags yourself if you want to pre-emptively allow something *before* it's ever been blocked (there's no prior call to generate a suggestion from). In that case:

- `--target http://<host>` or `--target https://<host>`: exempts calls from *this exact tool* whose *this exact field* matches your pattern from ever being masked, once the session is already tainted.
- `--target file://<path>`: marks matching *read* results as non-sensitive in the first place, so they never taint the session at all.
- `--jsonpath`: a [JSONPath](https://github.com/h2non/jsonpath-ng) expression into the tool's argument/response dict (e.g. `$.command` for `Bash`, `$.prompt` for `WebFetch`).
- `--pattern`: a Python regex matched against the field's string value.

Both kinds of target run a safety check *before* writing anything: a `file://` target runs a secrets scan on that path (via `detect-secrets`); an `http(s)://` target runs a reputation check on that host. If the check fails, nothing is written — see [Troubleshooting](#troubleshooting) below.

## Policy configuration

Project-level rules live in `scalene_policy.yaml` at your project root. If the file is missing (or unreadable — see Troubleshooting), Scalene falls back to fail-safe defaults: everything read counts as sensitive, everything called counts as untrusted, until you say otherwise.

```yaml
defaults:
  sensitive_by_default: true
  untrusted_by_default: true
  mode: mask   # or "block" — what to do when a real secret is detected (see below)

allowlist:
  - tool: "Read"
    jsonpath: "$.file_path"
    pattern: "^/workspace/public/.*"
    target: "file:///workspace/public"
    description: "Public asset directory — never sensitive"

  - tool: "WebFetch"
    jsonpath: "$.url"
    pattern: "^https://internal\\.example\\.com/"
    target: "https://internal.example.com"
    description: "Internal API — always trusted"
```

One list, one command (`scg onboard`) — a rule's `target` scheme (`file://` vs `http(s)://`) is what determines whether it counts toward "not sensitive" or "trusted destination"; `tool`/`jsonpath`/`pattern` determine which calls it matches, same as before.

**`mode`** controls what happens when a call is both provenance-risky (tainted-sensitive session, untrusted destination) *and* the specific value actually scans as a real secret:

- `mask` (default): the value is replaced with the mask literal and the call proceeds — the agent keeps working, just without the secret.
- `block`: the call is denied outright (`permissionDecision: "deny"`) with a plain-language reason. Use this if you'd rather stop and reconsider than have the agent silently continue with a masked argument.

Full field-level class model (`PolicyConfig`, `PolicyRule`, `MatchResult`) is in [docs/ARCHITECTURE.md](ARCHITECTURE.md) §4; the schema's field capabilities (nested JSON, shell strings, URLs, file paths, DB targets) are specified in [docs/BRD.md](BRD.md) §2.3.2. This guide won't repeat either — edit `scalene_policy.yaml` by hand for pre-emptive rules, or prefer `scg onboard` (previous section) so the safety checks run automatically.

## Troubleshooting

Scalene is built to **fail safe** — an internal problem should degrade to "treat everything as sensitive/untrusted" (the safest default), never to a crash that blocks your agent session or, worse, silently allows something it shouldn't.

| Situation | What happens |
|---|---|
| No `scalene_policy.yaml` at all | Falls back to `PolicyConfig()` defaults (`sensitive_by_default`/`untrusted_by_default` both `true`, empty rule lists). |
| `scalene_policy.yaml` exists but is malformed (invalid YAML, wrong types, unreadable) | Falls back to the same fail-safe defaults as a missing file, with a warning logged (`scalene.guard` logger) — **never crashes** `scalene-guard`. |
| Malformed hook input (bad JSON on stdin) or an unrecognized hook event | Returns `{}` — an empty response, which Claude Code's hook contract treats as "allow, no changes" — the call proceeds unmodified rather than blocking your agent. |
| A policy rule's JSONPath fails to evaluate against a real call (e.g. a typo'd expression) | That one rule fails safe to sensitive=true/untrusted=false for this call — logged as a warning, other rules still apply. |
| `scg onboard` blocked | Nothing is written to `scalene_policy.yaml`. The failure reason is always plain language (e.g. `Onboarding blocked: secrets check failed — Possible AWS Access Key detected`) — never a raw library exception, even after the `detect-secrets` upgrade (STORY-801). |

If you see a raw Python traceback from `scalene-guard` or `scg`, that's a bug — please file an issue rather than assuming it's expected.
