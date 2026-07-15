# Scalene Setup

## Install

```bash
pip install scalene-guard
```

This installs two commands:

- `scalene-guard` — the hook command Claude Code invokes directly. You do not run this yourself.
- `scg` — the developer-facing CLI (`onboard`, `install-hooks`).

## Register the hooks

```bash
scg install-hooks
```

This wires `PreToolUse` and `PostToolUse` hooks into your project's `.claude/settings.json` so Claude Code invokes `scalene-guard` before and after every tool call. It merges non-destructively — any existing settings, other tool matchers, and other commands already on the `*` matcher are all preserved — and is idempotent (safe to run again). If you're developing on this repo itself, `make install-scalene-hooks` does the same thing (`TARGET=<path>` to target a different project; defaults to `.`).

Equivalently, you can hand-edit `.claude/settings.json` yourself:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [{ "type": "command", "command": "scalene-guard" }]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [{ "type": "command", "command": "scalene-guard" }]
      }
    ]
  }
}
```

`scalene-guard` reads the hook's JSON payload from stdin, dispatches on the payload's `hook_event_name` field (`PreToolUse` or `PostToolUse`), and writes a JSON response to stdout using Claude Code's real hook contract (`hookSpecificOutput.permissionDecision`/`updatedInput`). Malformed input or an unrecognized event both fail safe to `{}` (empty output, treated as "allow, no change") — Scalene never blocks the agent due to an internal error.

## Policy configuration

Create `scalene_policy.yaml` at your project root (see `docs/ARCHITECTURE.md` §13 for the schema). If the file is missing, Scalene falls back to fail-safe defaults (`sensitive_by_default: true`, `untrusted_by_default: true`).

## Onboarding a false positive

```bash
scg onboard --target file://path/to/file.md

scg onboard --target https://internal.example.com
```

`--target`'s scheme decides what gets checked: a `file://` target runs a secrets scan on that path before writing (seeds the cache as "public" on success); an `http(s)://` target runs a reputation check on that host (seeds the cache as "trusted" on success). Both run in an isolated subprocess before writing anything, directly into `.scalene/scan_cache.json` — the same cache the live hook consults. On success it prints the resolved label. On failure, nothing is written — you get a clear reason instead.

## State and audit files

Scalene stores per-session taint state and the audit log under `.scalene/` at your project root. This directory is git-ignored (`.gitignore`) and is not a CI artifact — there is no CI workflow in this repo that captures build artifacts, so no further exclusion is needed there.
