"""Tests for the scan cache store (STORY-1003).

Sprint 4 (E10) Phase 2: docs/ARCHITECTURE.md sec13.3. Covers the 3-state
lookup table (none/fresh/expired), file-lock-protected read/write (same
pattern as taint_state.py), and the background-refresh dedup that keeps a
storm of repeated first-sighting lookups from spawning redundant/orphaned
subprocesses (task.md Phase 2 exit criteria).
"""

import concurrent.futures
import subprocess
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scalene.scan_cache import FRESHNESS_SECONDS, CacheEntry, ScanCache, ScanCacheError, refresh_if_needed
from scalene.scanner import Resource, ScanResult

from _env_guards import disable_remote_reputation, restore_remote_reputation

# docs/ARCHITECTURE.md sec18.3 (STORY-1503): refresh_if_needed() on a real
# cache miss spawns a real background subprocess -- Trin's Phase 3 UAT
# found this file (unlike test_resource_verifier.py) calls it directly and
# was missed by Neo's own file sweep. See _env_guards.py.
setUpModule = disable_remote_reputation
tearDownModule = restore_remote_reputation


def _try_reserve_in_a_real_separate_process(args: tuple[str, Resource]) -> bool:
    # Module-level (not a closure) so it's picklable for ProcessPoolExecutor
    # -- each call runs in a genuinely separate OS process, no shared
    # interpreter state, exercising the same cross-process race a real
    # scalene-guard invocation (a fresh process per hook call) would hit.
    cache_path, resource = args
    return ScanCache(cache_path).try_reserve(resource)


class TestScanCacheGetPut(unittest.TestCase):
    def test_get_on_empty_cache_returns_none(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            resource = Resource(kind="url", identity="internal.example.com", scanner_name="reputation")
            self.assertIsNone(cache.get(resource))

    def test_put_then_get_round_trips(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            resource = Resource(kind="url", identity="internal.example.com", scanner_name="reputation")
            cache.put(resource, ScanResult(label="trusted"))

            entry = cache.get(resource)
            self.assertIsInstance(entry, CacheEntry)
            self.assertEqual(entry.label, "trusted")
            self.assertEqual(entry.reason, "")

    def test_put_records_reason(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            resource = Resource(kind="url", identity="203.0.113.42", scanner_name="reputation")
            cache.put(resource, ScanResult(label="untrusted", reason="IP-literal targets are untrusted by default"))

            entry = cache.get(resource)
            self.assertEqual(entry.label, "untrusted")
            self.assertIn("IP-literal", entry.reason)

    def test_put_for_a_file_resource_records_mtime(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "clean.md"
            target.write_text("ordinary text")
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            resource = Resource(kind="file", identity=str(target), scanner_name="secrets")
            cache.put(resource, ScanResult(label="public"))

            entry = cache.get(resource)
            self.assertIsNotNone(entry.mtime)

    def test_different_resources_do_not_collide(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            file_resource = Resource(kind="file", identity="/abs/a.txt", scanner_name="secrets")
            url_resource = Resource(kind="url", identity="a.txt", scanner_name="reputation")
            cache.put(file_resource, ScanResult(label="public"))
            cache.put(url_resource, ScanResult(label="untrusted", reason="test"))

            self.assertEqual(cache.get(file_resource).label, "public")
            self.assertEqual(cache.get(url_resource).label, "untrusted")

    def test_all_entries_returns_every_raw_entry(self):
        # STORY-1005: scg monitor's resource panel reads this directly.
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            file_resource = Resource(kind="file", identity="/abs/a.txt", scanner_name="secrets")
            url_resource = Resource(kind="url", identity="internal.example.com", scanner_name="reputation")
            cache.put(file_resource, ScanResult(label="public"))
            cache.put(url_resource, ScanResult(label="trusted"))

            entries = cache.all_entries()
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries["secrets:/abs/a.txt"]["label"], "public")
            self.assertEqual(entries["reputation:internal.example.com"]["label"], "trusted")

    def test_all_entries_on_empty_cache_returns_empty_dict(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            self.assertEqual(cache.all_entries(), {})

    def test_cache_survives_reload_from_disk(self):
        with TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "scan_cache.json"
            resource = Resource(kind="url", identity="internal.example.com", scanner_name="reputation")
            ScanCache(cache_path).put(resource, ScanResult(label="trusted"))

            reloaded = ScanCache(cache_path)
            entry = reloaded.get(resource)
            self.assertEqual(entry.label, "trusted")

    def test_corrupted_cache_file_raises_scan_cache_error(self):
        # 2026-07-15 (Phase 4, STORY-1004): changed from Phase 2's original
        # "fails safe to empty" behavior -- now that a clean, plain-language
        # fatal exit exists (cli.py), silently treating a corrupted cache as
        # empty would quietly degrade protection (every resource looks
        # first-seen forever) without ever telling anyone it's broken.
        with TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "scan_cache.json"
            cache_path.write_text("{not valid json")
            cache = ScanCache(cache_path)
            resource = Resource(kind="url", identity="internal.example.com", scanner_name="reputation")
            with self.assertRaises(ScanCacheError):
                cache.get(resource)


class TestScanCacheUnwritable(unittest.TestCase):
    def test_unwritable_store_raises_scan_cache_error(self):
        with TemporaryDirectory() as tmp:
            read_only_dir = Path(tmp) / "readonly"
            read_only_dir.mkdir()
            cache_path = read_only_dir / "scan_cache.json"
            read_only_dir.chmod(0o500)  # r-x, no write
            try:
                cache = ScanCache(cache_path)
                resource = Resource(kind="url", identity="internal.example.com", scanner_name="reputation")
                with self.assertRaises(ScanCacheError):
                    cache.put(resource, ScanResult(label="trusted"))
            finally:
                read_only_dir.chmod(0o700)  # restore so TemporaryDirectory cleanup can remove it


class TestScanCacheFreshness(unittest.TestCase):
    def test_recent_entry_with_unchanged_mtime_is_fresh(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "clean.md"
            target.write_text("ordinary text")
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            resource = Resource(kind="file", identity=str(target), scanner_name="secrets")
            cache.put(resource, ScanResult(label="public"))

            entry = cache.get(resource)
            self.assertTrue(cache.is_fresh(resource, entry))

    def test_entry_older_than_freshness_window_is_not_fresh(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            resource = Resource(kind="url", identity="internal.example.com", scanner_name="reputation")
            stale_entry = CacheEntry(label="trusted", reason="", scanned_at=time.time() - FRESHNESS_SECONDS - 1)
            self.assertFalse(cache.is_fresh(resource, stale_entry))

    def test_file_entry_is_not_fresh_after_mtime_changes(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "clean.md"
            target.write_text("ordinary text")
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            resource = Resource(kind="file", identity=str(target), scanner_name="secrets")
            cache.put(resource, ScanResult(label="public"))
            entry = cache.get(resource)

            time.sleep(0.01)
            target.write_text("changed content")
            self.assertFalse(cache.is_fresh(resource, entry))

    def test_file_entry_is_not_fresh_if_file_no_longer_exists(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "clean.md"
            target.write_text("ordinary text")
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            resource = Resource(kind="file", identity=str(target), scanner_name="secrets")
            cache.put(resource, ScanResult(label="public"))
            entry = cache.get(resource)

            target.unlink()
            self.assertFalse(cache.is_fresh(resource, entry))


class TestRefreshIfNeeded(unittest.TestCase):
    def test_no_entry_returns_none_and_spawns_a_background_scan(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "clean.md"
            target.write_text("ordinary text")
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            resource = Resource(kind="file", identity=str(target), scanner_name="secrets")

            with patch("scalene.scan_cache.subprocess.Popen") as mock_popen:
                result = refresh_if_needed(resource, cache)

            self.assertIsNone(result)
            mock_popen.assert_called_once()

    def test_fresh_entry_returns_cached_label_and_does_not_spawn(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "clean.md"
            target.write_text("ordinary text")
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            resource = Resource(kind="file", identity=str(target), scanner_name="secrets")
            cache.put(resource, ScanResult(label="public"))

            with patch("scalene.scan_cache.subprocess.Popen") as mock_popen:
                result = refresh_if_needed(resource, cache)

            self.assertEqual(result.label, "public")
            mock_popen.assert_not_called()

    def test_expired_entry_returns_last_known_label_but_still_spawns(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            resource = Resource(kind="url", identity="internal.example.com", scanner_name="reputation")
            cache.put(resource, ScanResult(label="trusted"))
            # Force staleness by rewriting scanned_at directly into the store.
            data = cache._read()
            data[f"{resource.scanner_name}:{resource.identity}"]["scanned_at"] = time.time() - FRESHNESS_SECONDS - 1
            cache.cache_path.write_text(__import__("json").dumps(data))

            with patch("scalene.scan_cache.subprocess.Popen") as mock_popen:
                result = refresh_if_needed(resource, cache)

            self.assertEqual(result.label, "trusted")
            mock_popen.assert_called_once()

    def test_new_resource_lookup_does_not_block_on_the_scan(self):
        # STORY-1003 AC / Morpheus's watch-item: the no-cache-entry path must
        # be zero-added-latency versus today's fail-safe-default behavior --
        # spawning is fire-and-forget, never waits for the scan to finish.
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "clean.md"
            target.write_text("ordinary text")
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            resource = Resource(kind="file", identity=str(target), scanner_name="secrets")

            start = time.monotonic()
            result = refresh_if_needed(resource, cache)
            elapsed = time.monotonic() - start

            self.assertIsNone(result)
            self.assertLess(elapsed, 3.0)


class TestRefreshDedupAndNoOrphanedProcesses(unittest.TestCase):
    """task.md Phase 2 exit criteria: a real repeated-invocation test proving
    no orphaned processes -- both that concurrent first-sighting lookups of
    the SAME resource dedup to one spawn (not N), and that the one spawned
    process actually terminates cleanly rather than hanging/leaking."""

    def test_repeated_lookup_of_same_uncached_resource_spawns_only_once(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "clean.md"
            target.write_text("ordinary text")
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            resource = Resource(kind="file", identity=str(target), scanner_name="secrets")

            spawned = []
            real_popen = subprocess.Popen

            def spy(*args, **kwargs):
                proc = real_popen(*args, **kwargs)
                spawned.append(proc)
                return proc

            with patch("scalene.scan_cache.subprocess.Popen", side_effect=spy):
                for _ in range(5):
                    refresh_if_needed(resource, cache)

            self.assertEqual(len(spawned), 1)

            exit_code = spawned[0].wait(timeout=15)
            self.assertEqual(exit_code, 0)

            entry = cache.get(resource)
            self.assertIsNotNone(entry)
            self.assertEqual(entry.label, "public")

    def test_different_uncached_resources_each_get_their_own_spawn(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            resource_a = Resource(kind="url", identity="internal.example.com", scanner_name="reputation")
            resource_b = Resource(kind="url", identity="another.example.com", scanner_name="reputation")

            with patch("scalene.scan_cache.subprocess.Popen") as mock_popen:
                refresh_if_needed(resource_a, cache)
                refresh_if_needed(resource_b, cache)

            self.assertEqual(mock_popen.call_count, 2)

    def test_stale_reservation_does_not_permanently_block_future_scans(self):
        # A crashed/killed worker that never called put() shouldn't wedge a
        # resource out of ever being rescanned.
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            resource = Resource(kind="url", identity="internal.example.com", scanner_name="reputation")

            self.assertTrue(cache.try_reserve(resource))
            self.assertFalse(cache.try_reserve(resource))  # still fresh, dedup holds

            # Simulate an expired reservation (worker died without cleaning up).
            data = cache._read()
            key = f"{resource.scanner_name}:{resource.identity}"
            data[key]["pending_since"] = time.time() - 3600
            import json

            cache.cache_path.write_text(json.dumps(data))

            self.assertTrue(cache.try_reserve(resource))

    def test_dedup_holds_under_real_cross_process_concurrency(self):
        # Trin's UAT addition: Neo's dedup test calls try_reserve() 5x
        # sequentially within one process, which FileLock trivially
        # serializes. The claim that actually matters is dedup across
        # SEPARATE scalene-guard invocations (separate OS processes, no
        # shared memory) racing on the exact same never-cached resource --
        # verified here with real OS processes, not simulated.
        with TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "scan_cache.json"
            resource = Resource(kind="url", identity="internal.example.com", scanner_name="reputation")

            with concurrent.futures.ProcessPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(_try_reserve_in_a_real_separate_process, [(cache_path, resource)] * 8))

            self.assertEqual(sum(results), 1)


if __name__ == "__main__":
    unittest.main()
