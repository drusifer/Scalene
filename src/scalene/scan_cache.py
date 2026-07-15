"""Scan cache store (STORY-1003): .scalene/scan_cache.json, project-wide,
filelock-protected like taint_state.py's per-session files.

docs/ARCHITECTURE.md sec13.3: 3-state lookup (no entry / fresh / expired).
The "no entry" path returns None so the caller applies its own existing
fail-safe default (identical latency/behavior to today, per STORY-1003) --
this module never invents its own default label. Freshness for file
resources additionally requires an unchanged mtime (STORY-1003 AC: a
changed file must be re-verified, not trusted forever from one scan).

Background refresh is a detached `subprocess.Popen` (cache_refresh_worker.py,
no daemon) with an in-cache "pending_since" reservation so a storm of
repeated lookups for the same never-cached resource dedups to one spawn,
not N (task.md Phase 2 exit criteria: no orphaned/redundant processes). A
stale reservation (a worker that died without writing a result) expires on
its own after PENDING_TIMEOUT_SECONDS so one crashed worker can't
permanently wedge a resource out of ever being rescanned.

2026-07-15 (Sprint 4 Phase 4, STORY-1004): a corrupted/unwritable cache
store now raises ScanCacheError rather than silently degrading to "empty"
(Phase 2's original behavior) -- STORY-1004's fatal-exit boundary exists
specifically so this can be surfaced honestly (a clean, plain-language
non-zero exit) instead of silently treating every resource as first-seen
forever, which would quietly degrade protection without ever telling
anyone the cache store itself is broken.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from filelock import FileLock

from .scanner import Resource, ScanResult

DEFAULT_CACHE_PATH = Path(".scalene") / "scan_cache.json"
FRESHNESS_SECONDS = 24 * 60 * 60
PENDING_TIMEOUT_SECONDS = 5 * 60


class ScanCacheError(Exception):
    """Raised when the scan cache store itself is unreadable/unwritable
    (STORY-1004: a scanning-machinery failure, not an ordinary lookup)."""


@dataclass(frozen=True)
class CacheEntry:
    label: str
    reason: str
    scanned_at: float
    mtime: float | None = None


def _cache_key(resource: Resource) -> str:
    return f"{resource.scanner_name}:{resource.identity}"


class ScanCache:
    def __init__(self, cache_path: Path = DEFAULT_CACHE_PATH):
        self.cache_path = Path(cache_path)

    def _lock_path(self) -> Path:
        return Path(str(self.cache_path) + ".lock")

    @contextmanager
    def _locked(self):
        try:
            with FileLock(str(self._lock_path())):
                yield
        except OSError as exc:
            raise ScanCacheError(f"Scan cache store {self.cache_path} lock is unusable: {exc}") from exc

    def _read(self) -> dict:
        if not self.cache_path.exists():
            return {}
        try:
            return json.loads(self.cache_path.read_text())
        except json.JSONDecodeError as exc:
            raise ScanCacheError(f"Scan cache store {self.cache_path} is corrupted: {exc}") from exc
        except OSError as exc:
            raise ScanCacheError(f"Scan cache store {self.cache_path} is unreadable: {exc}") from exc

    def _write(self, data: dict) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(data))
        except OSError as exc:
            raise ScanCacheError(f"Scan cache store {self.cache_path} is unwritable: {exc}") from exc

    def get(self, resource: Resource) -> CacheEntry | None:
        with self._locked():
            data = self._read()
        raw = data.get(_cache_key(resource))
        if raw is None or "label" not in raw:
            return None
        return CacheEntry(
            label=raw["label"],
            reason=raw.get("reason", ""),
            scanned_at=raw.get("scanned_at", 0.0),
            mtime=raw.get("mtime"),
        )

    def put(self, resource: Resource, result: ScanResult) -> None:
        entry: dict = {
            "label": result.label,
            "reason": result.reason,
            "scanned_at": time.time(),
        }
        if resource.kind == "file" and os.path.exists(resource.identity):
            entry["mtime"] = os.stat(resource.identity).st_mtime

        with self._locked():
            data = self._read()
            data[_cache_key(resource)] = entry
            self._write(data)

    def all_entries(self) -> dict:
        """All raw cache entries, keyed by f"{scanner_name}:{identity}"
        (STORY-1005: `scg monitor`'s resource panel reads this directly, not
        a parallel summary that could drift from the real store)."""
        with self._locked():
            return self._read()

    def is_fresh(self, resource: Resource, entry: CacheEntry) -> bool:
        if time.time() - entry.scanned_at >= FRESHNESS_SECONDS:
            return False
        if resource.kind == "file":
            if not os.path.exists(resource.identity):
                return False
            if entry.mtime is None or os.stat(resource.identity).st_mtime != entry.mtime:
                return False
        return True

    def try_reserve(self, resource: Resource) -> bool:
        """Atomically claim the right to spawn a background scan for this
        resource. Returns False if another reservation is still fresh
        (dedup) -- otherwise stakes a new reservation and returns True."""
        key = _cache_key(resource)
        with self._locked():
            data = self._read()
            existing = data.get(key, {})
            pending_since = existing.get("pending_since")
            if pending_since is not None and time.time() - pending_since < PENDING_TIMEOUT_SECONDS:
                return False
            existing["pending_since"] = time.time()
            data[key] = existing
            self._write(data)
        return True


def _spawn_background_refresh(resource: Resource, cache_path: Path) -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "scalene.cache_refresh_worker",
            resource.scanner_name,
            resource.kind,
            resource.identity,
            str(cache_path),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def refresh_if_needed(resource: Resource, cache: ScanCache) -> CacheEntry | None:
    """The 3-state lookup (docs/ARCHITECTURE.md sec13.3): returns the entry
    to use for *this* call -- None means no entry exists yet (caller applies
    its own fail-safe default), otherwise the last-known label (fresh or
    stale). Fires a fire-and-forget background scan whenever the entry is
    missing or stale, deduped via ScanCache.try_reserve so concurrent
    lookups of the same resource spawn at most one worker."""
    entry = cache.get(resource)
    if entry is not None and cache.is_fresh(resource, entry):
        return entry

    if cache.try_reserve(resource):
        _spawn_background_refresh(resource, cache.cache_path)

    return entry
