# Scalene Setup

## Install

```bash
# Core hook (`scalene-guard`) and CLI (`scg`)
pip install scalene-guard

# Include the live approval-queue TUI (`scg monitor`)
pip install "scalene-guard[monitor]"
```

This installs two commands:

- `scalene-guard` — the hook command Claude Code invokes directly. You do not run this yourself.
- `scg` — the developer-facing CLI (`install-hooks`, `onboard`, `monitor`). Run `scg --help` for subcommand usage.

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

`scalene-guard` reads the hook's JSON payload from stdin, dispatches on the payload's `hook_event_name` field (`PreToolUse` or `PostToolUse`), and writes a JSON response to stdout using Claude Code's real hook contract (`hookSpecificOutput.permissionDecision` — `"allow"` or `"deny"`). Malformed input or an unrecognized event both fail safe to `{}` (empty output, treated as "allow, no change") — Scalene never blocks the agent due to an internal error.

## Policy configuration

On the first hook invocation in a project without a `scalene_policy.yaml`, Scalene automatically creates one at your project root with a default rule for your project folder (`sensitivity: internal`, `mode: allow`). If the file cannot be created, read, or parsed, Scalene falls back to fail-safe defaults (every resource treated as unruled) and logs a warning without crashing.

You can hand-edit `scalene_policy.yaml`, author rules via `scg onboard`, or manage them interactively in `scg monitor`. See [docs/USER_GUIDE.md](USER_GUIDE.md) for the full policy schema, OLOY mode, and environment variables (`SCALENE_OLOY`, `SCALENE_URLHAUS_AUTH_KEY`).

## Clearing a blocked call

The easiest day-to-day workflow is the live approval queue (`scg monitor`, see [docs/MONITOR_GUIDE.md](MONITOR_GUIDE.md)). From the command line, `scg onboard` identifies targets from a real tool call (the same shape `scalene-guard` reads on stdin), not a hand-typed URI:

```bash
echo '{"tool_name": "Read", "tool_input": {"file_path": "path/to/existing_file.md"}}' \
  | scg onboard --yes --mode allow

echo '{"tool_name": "WebFetch", "tool_input": {"url": "https://internal.example.com"}}' \
  | scg onboard --yes --mode allow
```

Every registered scanner's `identify()` runs against the call; an existing file path gets a secrets scan, a URL gets a reputation check. `--yes` accepts every identified target without an interactive confirmation prompt (drop it for a real terminal session and you'll see a numbered list + `[Y/n/s(elect)]` prompt first). Each scan runs in an isolated subprocess before anything is written — on success, both the resource cache (`.scalene/scan_cache.json`) and a `rules:` entry in `scalene_policy.yaml` are written; on failure, nothing is written and you get a clear per-target reason instead. Full reference: [docs/USER_GUIDE.md](USER_GUIDE.md#scg-onboard).

## State and audit files

Scalene stores per-session taint state, the scan cache, and the audit log under `.scalene/` at your project root. Add `.scalene/` to your project's `.gitignore` — it is local runtime state, not source code to commit or publish.
