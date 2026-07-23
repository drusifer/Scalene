# `*user consult` — Elaborate Interactive Onboarding TUI (2026-07-22)

## Request (direct user, verbatim intent)

Make onboarding "super easy" while keeping the impact of allow-list decisions
plainly obvious. Build out the `scg monitor`-shaped TUI into something more
elaborate, run in a separate shell/process from the agent session:

- Live view of scanner activity (mostly "waiting for assets to scan").
- Scrolly log of tool calls, with entries highlighted when they match rules,
  and per-tag coloring (e.g. sensitive-call tags visually distinct).
- On a trust/sensitivity violation from the hook, the hook **pauses and
  awaits a user decision** — if the TUI is running, it drives the decision
  via a dashboard: the tool being called, which scanners matched, identified
  targets, each target's onboard/validated status + a "dirty" flag.
- Three options: **Verify**, **Allow**, **Deny**. Default is **Deny**.
  **Allow is disabled until Verify completes** (with activity indicators
  while scanners are verifying).
- **Allow** opens a form showing the real Tool Call (can be a large JSON
  object), with the match-expression fields pre-filled with tight defaults.
- State/config for `sg`/scalene must live **outside the sandbox**,
  read-only inside it, so an agent can never edit its own rules. Same for
  the log, if possible.

## Grounding — what actually exists today (checked before answering)

- `scg monitor` already exists (`src/scalene/monitor_app.py`,
  `monitor_data.py`, `monitor.py`) — Textual TUI, 0.5s poll loop, read-only.
  Sessions/trust/sensitivity, a block-event log, and a resource-cache panel.
  It's a fine foundation, not built from scratch.
- `pre_tool_use` (`hook_adapter.py:69`) is a single **synchronous** function
  call, invoked once per tool call by Claude Code's hook mechanism. There is
  currently **zero IPC** between it and any other process. It returns
  `allow` or `deny` immediately — no in-between state.
- **sec15 (docs/ARCHITECTURE.md, 2026-07-17, direct user design session)
  deliberately removed** the one prior feature that had this exact shape:
  STORY-702's editable/appliable onboard-suggestion workflow. The
  `BlockEvent` docstring is explicit: "STORY-702's editable-and-applyable
  suggested-onboard-command workflow is removed — clearing a destination now
  always takes two explicit steps (a real scan, then a hand-authored rule),
  not one runnable command." That redesign happened specifically to get
  *out* of having an in-flight, awaiting-decision state at the hook
  boundary.
- No "dirty flag" concept exists anywhere in `scan_cache.py`,
  `resource_verifier.py`, or `PolicyRule`. Closest existing concept is
  `ScanCache`'s `pending_since` (an in-flight scan reservation, not a
  validated/dirty distinction on a target).
- `PolicyRule.jsonpath` already exists and is explicitly documented as
  "retained for forward-compatibility... not required for the common case"
  (`policy_config.py:61-78`) — the "tight defaults" ask is compatible with
  the current schema, not a new field.
- No hook-timeout behavior is documented anywhere in this repo. The one
  Claude Code hook contract detail that *was* nailed down (exit code 2
  blocks `PreToolUse`) was only trusted after Neo live-verified it against
  the real installed hook (`docs/ARCHITECTURE.md:482`), not from docs alone.

## Feedback

### What's strong about this, and should survive scoping

1. **The pre-filled form directly closes a gap I flagged on 2026-07-09**
   (`*user consult` — onboarding UX for allowlisting tool calls, recorded in
   `context.md`): a developer has never seen the actual tool-call JSON shape
   before being asked to hand-write a `jsonpath`/regex `pattern`. A form
   built from the real blocking call, with tight defaults, is exactly the
   fix I recommended then (option 1, "actionable mask made from the real
   call") — just now delivered as an interactive form instead of a
   copy-paste command. This is the best part of the proposal.
2. **Default Deny + Allow disabled until Verify completes** is genuine
   Nielsen #5 (error prevention) — the destructive path (letting something
   through) is structurally harder to reach than the safe one. It also
   matches this project's own restrictive-by-default posture, which I
   flagged as a value worth protecting in the E14 CLI UX review (finding
   #3, where flags drifting toward permissive defaults was called out as a
   regression risk).
3. **Read-only state/config inside the sandbox, read-write only outside** is
   the right trust boundary and consistent with sec15's fail-closed
   philosophy generally. An agent that could edit its own rule file mid-
   session would defeat the point of the whole access-control model —
   good instinct to name it explicitly rather than leave it implicit.

### Real concerns — need answers before this becomes architecture

1. **The "pause and await" mechanism's feasibility is unverified, and this
   project has a standing rule about exactly this kind of claim.** Making
   `pre_tool_use` block (or poll) on an external signal from a separate TUI
   process is buildable — but it lives or dies on how long Claude Code will
   let a `PreToolUse` hook hang before it times out and takes its own
   default action, a number I don't see confirmed anywhere in this repo. If
   there's a hard timeout and no one is watching the TUI when the block
   fires, "await the user" silently degrades into "block after N seconds" —
   which may be fine (Deny-by-default already covers it) but has to be a
   *verified, deliberate* fallback, not an assumed one. This is the same
   shape of claim Tank had to live-verify against the URLhaus API rather
   than trust vendor docs — Sprint 9's retro item, not a hypothetical.
   **This is Morpheus's question to answer, and it should be answered
   against the real hook contract before anything else here gets designed.**
2. **This reverses sec15, and that needs to be a conscious decision, not
   scope creep.** sec15 removed an in-flight awaiting-decision hook state on
   purpose. This proposal reintroduces that same shape with a human instead
   of a heuristic behind it — which might genuinely be the right call now,
   but it should be written up as "revise sec15" with the old rationale on
   the table, not layered on top as if sec15 never happened.
3. **Color-only tagging will fail this persona's own accessibility
   standard** (my SKILL.md: "avoid color-only feedback"). Tag colors are
   fine as a secondary cue; each log row needs a text/symbol distinguisher
   too so it's legible over a stripped-palette SSH session or for a
   colorblind user.
4. **"Dirty flag" isn't defined anywhere in the real system today.** This
   project has already shipped one bug from exactly this gap — the
   `trust=trusted` wording bug I caught at the Sprint 9 Phase 4 gate was a
   UI label naming a value that doesn't exist in the real vocabulary. Pin
   down what "dirty" means against real state (stale scan? touched-but-
   unvalidated? modified-since-last-scan?) before it's built, not after.
5. **Per-scanner "activity" needs a real backing signal.** `ScanCache.
   pending_since` models an in-flight reservation per *resource*, not per
   *scanner*. A dashboard row per scanner ("waiting for assets") is new data
   `monitor_data.py` doesn't collect today — worth scoping explicitly rather
   than assuming the data already exists.

## Recommendation

Route to Cypher as a real epic — this is sprint-scale, not a narrow
consult: it touches architecture (Morpheus: sync/async hook boundary,
sandbox exposure model), security posture (Tank: read-only mount boundary),
and UX (me, ongoing). Before Morpheus commits to an architecture, get a
**live-verified** answer on Claude Code's real `PreToolUse` hook timeout
behavior — that's the load-bearing constraint the whole "pause and await"
design rests on.

I'd approve the *shape* of the interaction design once it's written up as
stories (dashboard-on-block, Verify-gates-Allow, pre-filled form from the
real call) — it's a strong, concrete answer to a UX gap I've been flagging
since 2026-07-09. My blocking concern is purely the sync/async feasibility
question, and that one isn't mine to answer.

## Follow-up — non-blocking retry-prompt design (2026-07-22, same session)

User's response to concern #1: don't block the hook at all. Instead, on a
block, return a message that tells the agent to wait while the user reviews
in the TUI ("chill for a minute"); the user separately types "retry" (in
their normal chat with the agent) once they've onboarded (or not) via the
TUI, and the agent re-attempts the call.

**This fully resolves concern #1.** `decide_access` already returns
synchronously and deterministically, and the `reason` string already
reaches the agent via `systemMessage`/`permissionDecisionReason`
(`hook_adapter.py:43-60`) — no new hook contract, no IPC, no blocking, so
there is nothing to time out. It's also smaller than a sec15 reversal: the
call is still genuinely denied, not left in a partial/masked state, so
sec15's "validated-allow or blocked outright" model stays intact.

**New nuance for the eventual story**: `decide_access` already distinguishes
two block paths (`resource_verifier.py:190-223`) — `confirmed_bad` (a real
issue found, or a rule explicitly sets a non-allow mode) vs. `uncleared` (no
rule yet, nothing wrong found, just not reviewed). The retry-prompt wording
must differ per path or an agent will spin-retry a hard deny:
- **uncleared** → "Blocked pending user review — wait, then retry once
  reviewed."
- **confirmed_bad** → "Blocked — a real issue was found or explicitly
  denied. Don't retry without a rule change."

Same principle as my Sprint 4 Gate 1 finding (don't let "not yet verified"
read as "rejected") — here it's the inverse risk: don't let "explicitly
denied" read as "just wait and retry."

Net effect: the TUI's job shrinks to what `monitor_app.py`/`monitor_data.py`
already do well — watch `.scalene/audit.log` for block events (existing
`AuditTail`), show the Verify/Allow/Deny dashboard, and have Allow write the
rule through the existing rule-authoring path. No new sync mechanism
between hook and TUI at all.

## Follow-up — "dirty flag" definition (2026-07-22, same session)

User's answer: dirty = validation expired. **This maps directly onto code
that already exists** — correcting my concern #4 above, this is not
undefined vocabulary. `ScanCache.is_fresh()` (`scan_cache.py:131-139`,
docs/ARCHITECTURE.md sec13.3's "3-state lookup: no entry / fresh / expired")
already computes exactly this, and it's two conditions, not one:
- TTL expired (`FRESHNESS_SECONDS` elapsed since `scanned_at`), **or**
- for file resources, the file's mtime changed since the scan ran — an edit
  dirties the entry immediately, independent of the TTL.

User also asked for a way to **see** expiration status. Real, concrete gap:
the resource-cache panel (`monitor_app.py`'s `refresh_scan_results`) shows a
"Last Scanned" relative-time column but never calls `is_fresh()` — it
leaves the TTL comparison to the user, which fails Nielsen #1 (visibility
of system status). Fix is a Fresh/Expired column or badge next to it.

**Scoping note, not free**: `discover_scan_results` (`monitor_data.py`)
reads raw cache entries keyed by string (`f"{scanner_name}:{identity}"`),
not `Resource` objects — it can't call `is_fresh()` as-is, since the
file-mtime check needs a real `Resource`. Small reconstruction step needed,
not a pure display tweak. Worth Neo/Morpheus knowing this up front.

## Status

Discussion only. No code changed, no stories written yet. Not blocking
anything in-flight (Sprint 9/E15 is closed). Both concerns Smith raised
originally (hook-timeout feasibility, undefined "dirty flag" vocabulary)
are now resolved in-discussion — nothing outstanding blocks Cypher from
scoping this as a real epic.
