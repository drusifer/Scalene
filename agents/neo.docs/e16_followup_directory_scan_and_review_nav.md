# Fast-track fix (post-E16): directory Verify no-op + review navigation

## Bug: Verify had no effect on a directory target
- `FileScanner.scan()` → `run_scanner("secrets", target)` → `scan_worker._scan_secrets()` did
  `open(target).read()` unconditionally. A directory raises `IsADirectoryError`.
- That's caught by `scan_worker.main()`'s generic `except Exception` and reported as
  `machinery_error: True`, which makes `FileScanner.scan()` raise `ScannerMachineryError`.
- `monitor_app.py`'s `action_verify()` catches `ScannerMachineryError` per-target with
  `continue` (correct fail-safe behavior for the live TUI, not the fatal-exit hook path) —
  but that meant a directory target just silently never got verified, with no error shown.
  User-visible symptom: "pressing Verify on a directory had no effect."

**Fix** (`src/scalene/scan_worker.py`): `_scan_secrets()` now checks `os.path.isdir(target)`.
For a directory, it walks every file recursively (`os.walk`), scanning each with the same
`scan_text_for_secrets()` used for a single file, aggregating findings. A single unreadable
file inside the tree (permission denied, broken symlink) is skipped rather than failing the
whole directory scan. Empty/all-clean directories return `public`; any secret anywhere in the
tree returns `sensitive` with the offending file path(s) named in `reason`.

**Known limitation, not fixed here (scope discipline):** `ScanCache` freshness for a directory
resource keys off `os.stat(dir).st_mtime`, which only changes when direct children are
added/removed — not when a nested file's *contents* change deeper in the tree. A directory's
cached "fresh" scan can go stale without the mtime check catching it. Worth a follow-up if
directory-target Allow rules become common; out of scope for this fix (the bug was "no
effect", not "freshness correctness").

Tests: `tests/test_scanner.py` — `test_directory_target_scans_every_file_inside_and_is_public_when_all_clean`,
`test_directory_target_with_a_secret_in_a_nested_file_is_sensitive`, `test_empty_directory_target_is_public`.

## Feature: Next/Prev + "Review X of Y" in scg monitor's ReviewScreen
Direct user request: know how many reviews remain, browse them without closing the screen.

- `ReviewScreen.__init__` now takes `(pending: list[ReviewEntry], index: int, ...)` instead of
  a single `entry` — `pending` is the same list object as `MonitorApp._pending_reviews` (not a
  copy), so Next/Prev browse it in place. List length is stable while the screen is open (an
  item is only removed on resolve, which closes the screen).
- New `#review-position` Static shows "Review {index+1} of {total}"; Prev/Next buttons
  (`prev-btn`/`next-btn`) plus `n`/`p` key bindings navigate; `refresh_header()` re-points the
  tool/session/tool-input display and resets the allow-form/error state for whichever entry is
  now showing (a different entry shouldn't inherit a previous one's open form or error text).

**Bug fix enabled by this change:** `dismiss()` used to pass a bare `True`/`False`/`None`, and
`MonitorApp.action_open_review()`'s callback closed over the *original* entry the screen was
opened with (`self._pending_reviews[0]`) to know what to dequeue. Once Next/Prev can move the
screen to a *different* entry before Deny/Allow is pressed, that closure would have dequeued
the wrong entry. Fixed by having `dismiss()` pass back the actual entry that was resolved
(`self._entry` at dismiss time, or `None` for a plain Escape) — `MonitorApp._on_review_resolved`
now receives that and dequeues by it directly, no closure-captured entry needed.

Existing tests all still pass unchanged (`tests/test_monitor_app.py`, 46 tests) — none
constructed `ReviewScreen` directly, all drive through `MonitorApp.action_open_review`/Pilot
clicks, so the constructor signature change was transparent. No new tests added yet for
Next/Prev itself — flagged for Trin's UAT pass.

`make test`: 442/442.
