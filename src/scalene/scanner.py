"""Scanner protocol + registry (STORY-1001, STORY-1002).

docs/ARCHITECTURE.md sec13.2: replaces the old PolicyRule/allowlist matching
model (sec13.1) -- each scanner owns its own resource-detection logic (no
user-authored jsonpath/pattern), and scan() reuses today's
secrets_scan.py/LocalHeuristicChecker unchanged via the existing isolated
subprocess boundary (subprocess_isolation.run_scanner, STORY-601), so scan
results stay at parity with pre-Sprint-4 behavior.

Bash's `command` string gets no dedicated scanner type (sec13.2 decision) --
it's simply one more string value that both FileScanner's and URLScanner's
generic fallback regexes look at, same as any other tool's args.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

from .subprocess_isolation import run_scanner

# Per-tool field that carries a file path directly, as opposed to a value
# that merely might contain one (STORY-1002: known fields first, generic
# fallback for everything else).
_FILE_PATH_FIELDS = {
    "Read": "file_path",
    "Write": "file_path",
    "Edit": "file_path",
}

# Per-tool field that carries a URL directly.
_URL_FIELDS = {
    "WebFetch": "url",
}

# Conservative on purpose: only path-shaped tokens with an explicit `/`,
# `./`, or `../` prefix match, so ordinary words in a Bash command (e.g.
# "echo hello world") don't produce false-positive file resources.
_PATH_FALLBACK_RE = re.compile(r"(?P<path>\.{0,2}/[\w./+-]+)")

# STORY-1101 (docs/ARCHITECTURE.md sec14.2): captures the full URL (scheme +
# host + path), stopping at the first '?' -- identity is per-URL, not
# per-host, so scanning one path can no longer vouch for an unbounded set of
# other paths under the same host. Query string dropped to keep cache keys
# bounded.
_URL_FALLBACK_RE = re.compile(r"(?P<url>https?://[^\s\"'?]+)")

# Full URL span (scheme + host + path/query), used only to exclude a URL's
# internal slashes from _PATH_FALLBACK_RE -- otherwise "https://host/a/b"
# gets mistaken for a file path (every WebFetch call would spuriously
# produce a bogus FileScanner resource; caught in Phase 1 UAT).
_URL_SPAN_RE = re.compile(r"https?://\S+")


def _find_paths_excluding_urls(text: str) -> list[str]:
    url_spans = [m.span() for m in _URL_SPAN_RE.finditer(text)]
    paths = []
    for match in _PATH_FALLBACK_RE.finditer(text):
        start, end = match.span()
        if any(start < url_end and end > url_start for url_start, url_end in url_spans):
            continue
        paths.append(match.group("path"))
    return paths


@dataclass(frozen=True)
class Resource:
    kind: str  # "file" | "url" -- extensible, not a closed enum
    identity: str  # cache key material: absolute path, or full URL (sec14.2 -- not bare host)
    scanner_name: str


@dataclass(frozen=True)
class ScanResult:
    label: str  # "public" | "sensitive" | "trusted" | "untrusted"
    reason: str = ""
    reputation: float | None = None  # sec17.6: 0.0 (worst) .. 1.0 (best); None where no graded signal exists


class ScannerMachineryError(Exception):
    """Raised by Scanner.scan() when the scan itself couldn't run (STORY-1004:
    scanning-machinery failure, e.g. subprocess spawn failure or the target
    couldn't even be read) -- distinct from an ordinary finding, which is
    always returned as a ScanResult, never raised."""


class Scanner(Protocol):
    name: str  # "secrets", "reputation", ... -- the label namespace this scanner owns

    def identify(self, tool_name: str, args: dict) -> list[Resource]:
        """Find candidate resources this scanner cares about within a call's args."""
        ...

    def scan(self, resource: Resource) -> ScanResult:
        """Verify one resource. Runs in an isolated subprocess; never raises."""
        ...


def _string_args(args: dict) -> list[str]:
    return [value for value in args.values() if isinstance(value, str) and value]


class FileScanner:
    name = "secrets"

    def identify(self, tool_name: str, args: dict) -> list[Resource]:
        identities: list[str] = []

        known_field = _FILE_PATH_FIELDS.get(tool_name)
        known_value = args.get(known_field) if known_field else None
        if isinstance(known_value, str) and known_value:
            identities.append(os.path.abspath(known_value))

        for value in _string_args(args):
            for path in _find_paths_excluding_urls(value):
                identities.append(os.path.abspath(path))

        seen: set[str] = set()
        resources = []
        for identity in identities:
            if identity in seen:
                continue
            seen.add(identity)
            resources.append(Resource(kind="file", identity=identity, scanner_name=self.name))
        return resources

    def scan(self, resource: Resource) -> ScanResult:
        result = run_scanner("secrets", resource.identity)
        if result.get("machinery_error"):
            raise ScannerMachineryError(result.get("reason", "secrets scan machinery failed"))
        if result.get("ok", False):
            return ScanResult(label="public")
        return ScanResult(label="sensitive", reason=result.get("reason", ""))


class URLScanner:
    name = "reputation"

    def identify(self, tool_name: str, args: dict) -> list[Resource]:
        urls: list[str] = []

        known_field = _URL_FIELDS.get(tool_name)
        known_value = args.get(known_field) if known_field else None
        if isinstance(known_value, str) and known_value:
            urls.extend(m.group("url") for m in _URL_FALLBACK_RE.finditer(known_value))

        for value in _string_args(args):
            urls.extend(m.group("url") for m in _URL_FALLBACK_RE.finditer(value))

        seen: set[str] = set()
        resources = []
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            resources.append(Resource(kind="url", identity=url, scanner_name=self.name))
        return resources

    def scan(self, resource: Resource) -> ScanResult:
        # sec14.2: identity is per-URL for cache-key granularity, but the
        # reputation heuristic itself is host-level (a URL's path doesn't
        # change whether its host is reputable) -- extract the host if
        # identity parses as a URL, otherwise treat identity as already
        # being a bare host (onboard.py / direct-construction callers).
        host = urlparse(resource.identity).hostname or resource.identity
        result = run_scanner("reputation", host)
        if result.get("machinery_error"):
            raise ScannerMachineryError(result.get("reason", "reputation scan machinery failed"))
        reputation = result.get("reputation")
        if result.get("ok", False):
            return ScanResult(label="trusted", reputation=reputation)
        return ScanResult(label="untrusted", reason=result.get("reason", ""), reputation=reputation)


SCANNERS: dict[str, Scanner] = {"secrets": FileScanner(), "reputation": URLScanner()}
