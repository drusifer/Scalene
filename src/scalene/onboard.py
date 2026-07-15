"""`scg onboard` CLI (STORY-501, re-scoped 2026-07-15 per docs/ARCHITECTURE.md
sec13.4): pre-seed the resource cache for a target you already know is fine,
instead of paying the first-sighting cost live.

- `file://<path>` -- runs a secrets scan on that local path (STORY-601,
  isolated subprocess). On success, seeds the cache with label "public".
- `http://<host>` / `https://<host>` -- runs a reputation check on that
  host. On success, seeds the cache with label "trusted".

Drops `--tool`/`--jsonpath`/`--pattern`/`--description` entirely -- there's
no rule to author anymore, just a resource to check now instead of later
(sec13.1). Runs `scan()` synchronously: this is the one deliberately-
blocking scan path left in the system, and that's fine -- it's a one-off
CLI invocation, not the hot hook path. No more `scalene_policy.yaml`
allowlist writes, no diff-printing (there's no YAML edit to diff) --
prints the resolved label instead.

STORY-1004: a scanner-machinery failure (ScannerMachineryError) or a broken
cache store (ScanCacheError) both surface as a real OnboardError here too --
pre-seeding must fail loudly, not silently succeed with a wrong/missing
cache entry.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from .scan_cache import DEFAULT_CACHE_PATH, ScanCache, ScanCacheError
from .scanner import SCANNERS, Resource, ScannerMachineryError

_BLOCKED_LABELS = ("sensitive", "untrusted")


class OnboardError(Exception):
    """Raised when onboarding is blocked. The message is the clear, user-facing reason."""


def _resolve_resource(target: str) -> Resource:
    """URI-scheme dispatch (unchanged from pre-Sprint-4): returns the
    Resource to scan for `target`. Raises OnboardError for any scheme
    other than file/http/https.

    File identities are normalized via os.path.abspath -- the same
    normalization FileScanner.identify() applies during live evaluation --
    so a resource pre-seeded here uses the exact same cache key a real
    hook call would look up."""
    parsed = urlparse(target)
    if parsed.scheme == "file":
        path = target[len("file://") :]
        return Resource(kind="file", identity=os.path.abspath(path), scanner_name="secrets")
    if parsed.scheme in ("http", "https"):
        return Resource(kind="url", identity=parsed.hostname or "", scanner_name="reputation")
    raise OnboardError(f"--target must be a file://, http://, or https:// URI (got {target!r})")


def onboard(target: str, cache_path: Path = DEFAULT_CACHE_PATH) -> dict:
    """Returns {"resource": Resource, "label": str} on success. Raises
    OnboardError (no cache write) on failure."""
    resource = _resolve_resource(target)
    scanner = SCANNERS[resource.scanner_name]

    try:
        result = scanner.scan(resource)
    except ScannerMachineryError as exc:
        raise OnboardError(f"Onboarding blocked: scan machinery failed — {exc}") from exc

    if result.label in _BLOCKED_LABELS:
        raise OnboardError(f"Onboarding blocked: {resource.scanner_name} check failed — {result.reason}")

    try:
        ScanCache(cache_path).put(resource, result)
    except ScanCacheError as exc:
        raise OnboardError(f"Onboarding blocked: could not write to the scan cache — {exc}") from exc

    return {"resource": resource, "label": result.label}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scg onboard")
    parser.add_argument(
        "--target",
        required=True,
        help="file://<path> (runs a secrets scan) or http(s)://<host> (runs a reputation check)",
    )
    parser.add_argument("--cache-path", default=str(DEFAULT_CACHE_PATH))
    args = parser.parse_args(argv)

    try:
        result = onboard(args.target, cache_path=Path(args.cache_path))
    except OnboardError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    resource = result["resource"]
    print(f"Pre-seeded the scan cache: {resource.scanner_name}:{resource.identity} -> {result['label']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
