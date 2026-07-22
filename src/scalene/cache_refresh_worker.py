"""Background scan-cache refresh worker (STORY-1003).

Spawned as a detached `subprocess.Popen` (no `.wait()`, no daemon) by
`scan_cache.refresh_if_needed`'s fire-and-forget path -- the "child scanning
process" docs/ARCHITECTURE.md sec13.3 describes, which writes its result
directly into `.scalene/scan_cache.json` (via `ScanCache.put`'s own
`FileLock`) whenever it finishes, independent of whether the parent
`scalene-guard` process that spawned it has already exited.

Usage: python -m scalene.cache_refresh_worker <scanner_name> <kind> <identity> <cache_path>
"""

from __future__ import annotations

import os
import sys

from .scan_cache import ScanCache
from .scanner import SCANNERS, Resource


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        return 2

    scanner_name, kind, identity, cache_path = argv
    # sec18.1 (STORY-1501, implementation-time scope decision): this worker
    # is a detached subprocess with no shared memory with the parent
    # scalene-guard process, so it can't see a config-declared scanner
    # without also being handed the project's policy_path and re-loading
    # PolicyConfig itself here. Deliberately NOT done this epic -- no real
    # config-declared scanner ships yet, so there's no concrete case to
    # plumb this against, and doing so would mean threading policy_path
    # through _spawn_background_refresh()/refresh_if_needed() too (neither
    # currently carries it). A config-declared scanner's resources are
    # still fully identified/scanned via the synchronous decide_access()/
    # onboard() paths (both use config.scanners); only a *background*
    # refresh of a stale cache entry for such a resource would silently
    # no-op here (return 2, "unknown scanner") until the next lookup
    # retries via the normal fail-safe path -- a real, bounded, documented
    # gap, not a correctness bug. Revisit when a real config-declared
    # scanner actually ships.
    scanner = SCANNERS.get(scanner_name)
    if scanner is None:
        return 2

    # STORY-601 AC2: this worker's own actions must never recurse back
    # through policy evaluation -- Scanner.scan() already isolates via
    # subprocess_isolation.run_scanner, this is defense in depth for any
    # future scanner that calls tool-adjacent code directly in-process.
    os.environ["SCALENE_BYPASS"] = "1"

    resource = Resource(kind=kind, identity=identity, scanner_name=scanner_name)
    try:
        result = scanner.scan(resource)
        ScanCache(cache_path).put(resource, result)
    except Exception:
        # A genuine scanner-machinery failure (ScannerMachineryError,
        # ScanCacheError, or anything else unexpected -- not an ordinary
        # finding, Scanner.scan() implementations already fail safe into a
        # ScanResult for those). Leaving no cache entry means the next
        # lookup sees "no entry" and retries via the normal fail-safe path,
        # rather than silently caching a wrong/missing result. This worker
        # is detached from the parent scalene-guard process, so there's no
        # one left to report this failure to beyond a non-zero exit code
        # here -- 2026-07-15 (Phase 4): now also covers the cache-write
        # step itself, which earlier versions of this worker left
        # unprotected (Morpheus's Phase 2 review carry-forward note).
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
