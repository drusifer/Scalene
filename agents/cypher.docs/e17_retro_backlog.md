# Sprint 11 (E17) Retro Backlog

Compiled from all 6 persona retro posts (Neo, Trin, Morpheus, Oracle, Mouse,
Smith). No Tank retro this sprint — no infra/deploy/CI surface touched.

## Central theme

Same validated pattern as E16: a fully-worked-through `*user consult`
between Smith and the user (resolving the panel-drop question, the
silent-reorder concern, and the matcher-duplication risk before a single
story existed) produced zero story revisions at either gate. Worth
continuing to treat "resolve hard design tensions in `*consult`" as the
default for feature-shaped requests, not an exception.

Three real bugs this sprint, each caught by a genuinely different
verification technique — worth naming as this sprint's validation that the
"run it for real" standard catches different bug shapes, not the same one
repeatedly:
1. Smith's Gate 2 architecture rejection (code trace: `action_submit_
   allow()` had no `all_verified()` check of its own once the Pattern
   field became always-focusable).
2. Morpheus's Phase 1 review (diff read: `_on_review_resolved` never
   called the new `refresh_queue()`, caught by actually reading what
   changed, not assuming a phase's own tests covered it).
3. Trin's Phase 2 UAT (geometry test: `widget.region` showed the
   status-strip and Footer fully overlapping, contradicting the
   architecture's `dock: bottom`-stacks-outward assumption).

## Backlog items (new this sprint)

1. **Resource-cache freshness/Last-Scanned display is fully retired, no
   successor** (Neo/Smith) — STORY-1005's panel (and the `is_fresh()`
   display gap Smith originally flagged back in the E16 consult) is gone
   outright, not carried forward in any form. Real capability loss,
   explicitly named in the epic's Origin note and consult, not an
   oversight — but nothing currently tracks bringing equivalent visibility
   back if it turns out to matter.
2. **Session-history/scrollback browser for a non-latest session** — real
   capability the Sessions-table removal costs (STORY-1701's own AC).
   Flagged in `docs/ARCHITECTURE.md` §22.6 as a possible future story, not
   committed. Revisit only if it becomes a real complaint, same
   disposition as E16's own backlog items.
3. **A destructive `git checkout -- <file>` mid-session reverted more than
   intended** (Smith, process note not a code finding) — used to revert a
   4-line temporary test patch, instead wiped the entire uncommitted Phase
   1 implementation in that file. Fully recovered from the session's own
   memory of its edits, no data lost, but avoidable. Worth reinforcing:
   even a "just reverting this one small thing" moment should default to
   a targeted `Edit`, never a destructive git command, when the change
   being undone is that specific.

## Carried, not part of this sprint, unaffected

- STORY-1606's hash-snapshot detect-and-restore mechanism (still fully
  designed, not built — `docs/ARCHITECTURE.md` §20.6, carried from E16).
- STORY-1405/1406, Smith's `scg onboard` CLI UX findings
  (`e14_cli_ux_review.md`), `docs/ARCHITECTURE.md` §5's stale diagram,
  STORY-501's git-attributability AC, the shared-`.scalene/audit.log`
  test-hygiene gap (E16 backlog item #5) — all still open, none touched
  by E17.
