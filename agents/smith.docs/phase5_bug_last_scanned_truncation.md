# Sprint 4 Phase 5 — UX Bug: "Last Scanned" column truncation

**CMD:** `MonitorApp` at a realistic 120-column terminal width, with real `scan_cache.json` entries present.

**EXPECTED:** The "Last Scanned" column header and its timestamp values are readable.

**ACTUAL:** The header truncates to " La" and timestamp values render as an unreadable " 20" — reproduced with a real rendered screenshot (`app.export_screenshot()`), not assumed. The absolute `YYYY-MM-DD HH:MM:SS` format (19 characters) doesn't fit once a third panel splits the same horizontal space the previous two panels had to themselves.

**UX ISSUE:** Violates Nielsen #1 (visibility of system status) — the entire point of a monitoring panel is legibility, and the one column meant to convey recency is the one that's illegible. Not a hypothetical or narrow-terminal edge case: 120 columns is a common default width, not unusually small.

## Recommended direction (for Trin/Neo to weigh, not a mandate)
Shorten the timestamp format — a relative "X ago" style (e.g. "2m ago", "3h ago", "1d ago") is both shorter and arguably more useful for a live monitoring view than an absolute timestamp, and avoids the ambiguity of a bare time-of-day format losing the date.
