# Getting Started

This walkthrough takes you from a clean install to watching Scalene block an unrecognized destination, then explicitly clear it — no configuration required to see the protection, one `scg onboard` call to unblock something. It should take under 5 minutes.

## 1. Install

```bash
pip install scalene-guard
```

Want the live approval-queue TUI (`scg monitor`) as well? Quote the extra so shells like `zsh` don't interpret the brackets:

```bash
pip install "scalene-guard[monitor]"
```

This installs two commands: `scalene-guard` (the hook a coding agent harness like Claude Code invokes automatically before and after every tool call — you'll never run this by hand in real use) and `scg` (the developer-facing CLI: `install-hooks`, `onboard`, `monitor`).

Developing on this repo itself instead of just using the package? `git clone` it and run `make setup` instead — see the repo's [README.md](../README.md). Everything below works the same either way.

## 2. See what a clean session looks like

You can feed `scalene-guard` the same JSON a harness would normally send it, by hand, to see exactly what it decides. Make a scratch directory to run this in, so `.scalene/` — Scalene's local state — and `scalene_policy.yaml` don't land somewhere you don't want them:

```bash
mkdir /tmp/scalene-demo && cd /tmp/scalene-demo
```

Simulate an agent reading a file inside your project directory for the first time in a session. A fresh session starts clean (`trust=high, sensitivity=public`) — this first call is allowed:

```bash
echo '{"hook_event_name":"PreToolUse","session_id":"demo","tool_name":"Read","tool_input":{"file_path":"secret.txt"}}' \
  | scalene-guard
```

```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}
```

On the very first run in a project without a policy file, Scalene automatically creates `scalene_policy.yaml` with one default rule covering your project folder (`sensitivity: internal`, `mode: allow`) — so normal reads inside your own workspace don't immediately hit a wall. Because `secret.txt` lives inside `/tmp/scalene-demo`, your session (`demo`) is now tagged **`sensitivity=internal`** (`trust=high`). That tag is sticky: it stays set for the rest of the session, and the *next* call is evaluated against it. (Touching an unrecognized path *outside* your project folder would also drop `trust` to `low`.)

## 3. Watch it block an unrecognized destination

Now simulate that same session trying to reach somewhere external — e.g. a `WebFetch` call. Because the session is no longer clean (step 2 tagged it `sensitivity=internal`), any destination without an explicit, allowed rule gets blocked outright:

```bash
echo '{"hook_event_name":"PreToolUse","session_id":"demo","tool_name":"WebFetch","tool_input":{"url":"https://example.com","prompt":"summarize this"}}' \
  | scalene-guard
```

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Blocked: https://example.com has no explicitly-allowed rule, and this session has already touched sensitive/untrusted data (trust=high, sensitivity=internal). Wait for review, then retry."
  },
  "systemMessage": "Blocked: https://example.com has no explicitly-allowed rule, and this session has already touched sensitive/untrusted data (trust=high, sensitivity=internal). Wait for review, then retry."
}
```

The same entry is also appended to `.scalene/audit.log` in your scratch directory:

```bash
cat .scalene/audit.log
```

## 4. Explicitly clear a destination you trust

Trust decisions in Scalene are always explicit and validated — never automatic. `scg onboard` is the CLI frontend for this (or use `scg monitor` for an interactive review queue): it identifies targets from a real tool call (the same shape `scalene-guard` reads on stdin, via the same scanner registry `pre_tool_use` already runs live), confirms them, then verifies each for real (an actual reputation check, not just a declaration) *and* writes the rule. Effectively: "when a tool call matches this, apply these labels."

```bash
echo '{"tool_name": "WebFetch", "tool_input": {"url": "https://example.com", "prompt": "summarize this"}}' \
  | scg onboard --yes --mode allow --sensitivity public --description "Reviewed and trusted example.com endpoint"
```

```
Verified: reputation:https://example.com -> trusted (score 1.00)
Rule written to scalene_policy.yaml: tool='.*' pattern='https://example\\.com' sensitivity='public' mode='allow'
1 onboarded, 0 blocked
```

`--yes` accepts the identified target without an interactive prompt — drop it in a real terminal session and you'll see a numbered target list and a `[Y/n/s(elect)]` confirmation first. That inserts your new rule into `scalene_policy.yaml` ahead of the auto-created project-folder rule (first matching rule wins):

```yaml
rules:
- tool: .*
  pattern: https://example\.com
  sensitivity: public
  mode: allow
  description: Reviewed and trusted example.com endpoint
- tool: .*
  pattern: '/tmp/scalene-demo

    /tmp/scalene-demo/**'
  sensitivity: internal
  mode: allow
  description: project folder default (auto-created)
```

Each written rule's `pattern` defaults to an exact match on the target's own resolved identity — there's no `--pattern`/`--tool` override in this flow (hand-author a `rules:` entry directly, or edit it in `scg monitor`, for broader coverage such as every path under a host). At least one of `--mode`/`--sensitivity` is required; whichever you omit defaults sensibly (`mode: allow`, `sensitivity: public`) — onboarding is the moment you declare a trust decision, so it's never silently inferred for you.

Retry the exact same call from step 3:

```bash
echo '{"hook_event_name":"PreToolUse","session_id":"demo","tool_name":"WebFetch","tool_input":{"url":"https://example.com","prompt":"summarize this"}}' \
  | scalene-guard --policy-path scalene_policy.yaml
```

```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}
```

That's the whole loop: an unrecognized destination is blocked once a session has touched anything beyond clean public data, and one `scg onboard` call (or a Verify → Allow in `scg monitor`) — targets identified from the tool call, confirmed, then a real scan plus a declared rule together — is what clears it. Neither half works alone: a scan with no rule doesn't grant permission, and (per the CLI's own validation) you can't write a rule without stating what to do with it.

## Next steps

- Wire this into a real Claude Code project instead of hand-feeding JSON: `scg install-hooks` (see [docs/SETUP.md](SETUP.md)).
- Review, verify, and approve blocked calls interactively in a live terminal TUI: [docs/MONITOR_GUIDE.md](MONITOR_GUIDE.md).
- Full CLI reference, OLOY mode, policy configuration, and everyday workflows: [docs/USER_GUIDE.md](USER_GUIDE.md).
- Want to see the whole thing run end-to-end without typing anything (from a git clone of the repo): `make demo`.
