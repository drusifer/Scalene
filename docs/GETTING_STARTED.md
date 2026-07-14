# Getting Started

This walkthrough takes you from a clean install to watching Scalene mask a real, tainted tool call — no configuration required. It should take under 5 minutes.

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

Simulate an agent reading a file for the first time in a session. Nothing is tainted yet, so nothing is masked:

```bash
echo '{"hook_event_name":"PreToolUse","session_id":"demo","tool_name":"Read","tool_input":{"file_path":"secret.txt"}}' \
  | scalene-guard
```

```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}
```

## 3. Tell Scalene what that file actually contained

In real use, the harness sends the tool's result back through `PostToolUse` automatically. This is where Scalene decides whether what was just read counts as sensitive data (by default: everything does, until you configure otherwise — see `docs/USER_GUIDE.md` for how to loosen this). This hook is pure bookkeeping and has nothing to report back, so it always returns an empty response:

```bash
echo '{"hook_event_name":"PostToolUse","session_id":"demo","tool_name":"Read","tool_response":{"content":"AKIAIOSFODNN7EXAMPLE"}}' \
  | scalene-guard
```

```json
{}
```

Nothing looks different yet — but your session (`demo`) is now internally flagged as having touched sensitive, untrusted data. That flag is sticky: it stays set for the rest of the session.

## 4. Watch it mask an outbound call

Now simulate the same session trying to send that same value somewhere external — e.g. a `WebFetch` call. (We're using a fake AWS-access-key-shaped string above and below — `AKIAIOSFODNN7EXAMPLE` — because Scalene's masking is content-aware: it only acts when the value actually scans as a real secret, not just because the session touched *something* sensitive earlier. An ordinary value here would be allowed through unmasked.)

```bash
echo '{"hook_event_name":"PreToolUse","session_id":"demo","tool_name":"WebFetch","tool_input":{"url":"https://example.com","prompt":"AKIAIOSFODNN7EXAMPLE"}}' \
  | scalene-guard
```

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "Scalene masked the 'prompt' argument to WebFetch: Possible AWS Access Key detected. To allow this exact call going forward, run:\nscg onboard --list-type trust --tool WebFetch --jsonpath '$.prompt' --pattern '^AKIAIOSFODNN7EXAMPLE$' --target '<domain-this-call-reaches>'",
    "updatedInput": {"url": "https://example.com", "prompt": "[MASKED_BY_POLICY_PROVENANCE_GUARD]"}
  },
  "systemMessage": "Scalene masked the 'prompt' argument to WebFetch: Possible AWS Access Key detected. To allow this exact call going forward, run:\nscg onboard --list-type trust --tool WebFetch --jsonpath '$.prompt' --pattern '^AKIAIOSFODNN7EXAMPLE$' --target '<domain-this-call-reaches>'"
}
```

The secret never leaves in the clear — `prompt` was structurally replaced before the call would run. This is the concrete masked event: the same entry is also appended to `.scalene/audit.log` in your scratch directory:

```bash
cat .scalene/audit.log
```

That's the whole loop: read something sensitive, try to send it somewhere untrusted, get masked instead of leaked — with a ready-to-run command printed for the one case where you actually meant to allow it.

## Next steps

- Wire this into a real Claude Code project instead of hand-feeding JSON: `scg install-hooks` (see `docs/SETUP.md`).
- Full CLI reference, policy configuration, and everyday workflows: `docs/USER_GUIDE.md`.
- Want to see the whole thing run end-to-end without typing anything: `make demo`.
