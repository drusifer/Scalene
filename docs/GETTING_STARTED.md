# Getting Started

This walkthrough takes you from a clean install to watching Scalene block an unrecognized destination, then explicitly clear it — no configuration required to see the protection, one small config file to unblock something. It should take under 5 minutes.

## 1. Install

```bash
pip install scalene-guard
```

This installs two commands: `scalene-guard` (the hook a coding agent harness like Claude Code invokes automatically before and after every tool call — you'll never run this by hand in real use) and `scg` (the developer-facing CLI: `onboard`, `install-hooks`, `monitor`).

Developing on this repo itself instead of just using the package? `git clone` it and run `make setup` instead — see the repo's `README.md`. Everything below works the same either way.

## 2. See what a clean session looks like

You can feed `scalene-guard` the same JSON a harness would normally send it, by hand, to see exactly what it decides. Make a scratch directory to run this in, so `.scalene/` — Scalene's local state — doesn't land somewhere you don't want it:

```bash
mkdir /tmp/scalene-demo && cd /tmp/scalene-demo
```

Simulate an agent reading a file for the first time in a session. Nothing has been explicitly cleared yet, but a fresh session starts clean — this first call is allowed:

```bash
echo '{"hook_event_name":"PreToolUse","session_id":"demo","tool_name":"Read","tool_input":{"file_path":"secret.txt"}}' \
  | scalene-guard
```

```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}
```

The file itself wasn't recognized by any rule, though — so behind the scenes, your session (`demo`) is now tagged `trust: low`. That tag is sticky: it stays set for the rest of the session, and the *next* call is evaluated against it.

## 3. Watch it block an unrecognized destination

Now simulate that same session trying to reach somewhere external — e.g. a `WebFetch` call. Because the session is no longer clean (step 2 tagged it `trust: low`), any destination without an explicit, validated rule gets blocked outright — not scanned-and-maybe-allowed, blocked:

```bash
echo '{"hook_event_name":"PreToolUse","session_id":"demo","tool_name":"WebFetch","tool_input":{"url":"https://example.com","prompt":"summarize this"}}' \
  | scalene-guard
```

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Blocked: https://example.com has no validated, explicitly-allowed rule, and this session has already touched sensitive/untrusted data (trust=low, sensitivity=public)."
  },
  "systemMessage": "Blocked: https://example.com has no validated, explicitly-allowed rule, and this session has already touched sensitive/untrusted data (trust=low, sensitivity=public)."
}
```

The same entry is also appended to `.scalene/audit.log` in your scratch directory:

```bash
cat .scalene/audit.log
```

## 4. Explicitly clear a destination you trust

Trust decisions in Scalene are always explicit and validated — never automatic. `scg onboard` is the frontend for this: it identifies targets from a real tool call (the same shape `scalene-guard` reads on stdin, via the same scanner registry `pre_tool_use` already runs live), confirms them, then verifies each for real (an actual reputation check, not just a declaration) *and* declares what to do with it. Effectively: "when a tool call matches this, apply these labels."

```bash
echo '{"tool_name": "WebFetch", "tool_input": {"url": "https://example.com", "prompt": "summarize this"}}' \
  | scg onboard --yes --mode allow --sensitivity public --description "Reviewed and trusted example.com endpoint"
```

```
Verified: reputation:https://example.com -> trusted (score 1.00)
Rule written to scalene_policy.yaml: tool='.*' pattern='https://example\\.com' sensitivity='public' mode='allow'
1 onboarded, 0 blocked
```

`--yes` accepts the identified target without an interactive prompt — drop it in a real terminal session and you'll see a numbered target list and a `[Y/n/s(elect)]` confirmation first. That writes a real `rules:` entry, matching the same field names you just used on the command line:

```yaml
rules:
- tool: .*
  pattern: https://example\.com
  sensitivity: public
  mode: allow
  description: Reviewed and trusted example.com endpoint
```

Each written rule's `pattern` defaults to an exact match on the target's own resolved identity — there's no `--pattern`/`--tool` override in this flow (hand-author a `rules:` entry directly for broader coverage, e.g. every path under a host). At least one of `--mode`/`--sensitivity` is required; whichever you omit defaults sensibly (`mode: allow`, `sensitivity: public`) — onboarding is the moment you declare a trust decision, so it's never silently inferred for you.

Retry the exact same call from step 3:

```bash
echo '{"hook_event_name":"PreToolUse","session_id":"demo","tool_name":"WebFetch","tool_input":{"url":"https://example.com","prompt":"summarize this"}}' \
  | scalene-guard --policy-path scalene_policy.yaml
```

```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}
```

That's the whole loop: an unrecognized destination is blocked once a session has touched anything unverified, and one `scg onboard` call — targets identified from the tool call, confirmed, then a real scan plus a declared rule together — is what clears it. Neither half works alone: a scan with no rule doesn't grant permission, and (per the CLI's own validation) you can't write a rule without stating what to do with it.

## Next steps

- Wire this into a real Claude Code project instead of hand-feeding JSON: `scg install-hooks` (see `docs/SETUP.md`).
- Full CLI reference, policy configuration, and everyday workflows: `docs/USER_GUIDE.md`.
- Want to see the whole thing run end-to-end without typing anything: `make demo`.
