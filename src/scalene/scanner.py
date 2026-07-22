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

2026-07-22 (docs/ARCHITECTURE.md sec19, direct user session): URLScanner
recognizes any URI scheme (ftp://, ws://, s3://, ...), not just http(s) --
with one deliberate exception, file://, which is a filesystem reference
wearing a URI shape and is FileScanner's resource instead. Neither scanner
requires a caller to know which one applies to a given string; both run
their generic fallback over every tool's args unconditionally.
"""

from __future__ import annotations

import importlib
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

# Generic URI scheme prefix (RFC 3986 scheme grammar, simplified) -- matches
# any protocol (https://, ftp://, ws://, s3://, ...), not just http(s).
_URI_SCHEME = r"[a-zA-Z][a-zA-Z0-9+.-]*://"

# 2026-07-22 (direct user request): URLScanner handles any URL with a
# protocol -- EXCEPT file://, which is a filesystem reference wearing a URI
# shape and belongs to FileScanner instead (see _FILE_URI_RE below).
# Deliberately matches ANY scheme here, including file:// -- filtering it
# out belongs in the caller (URLScanner.identify(), below), not in this
# regex: a `(?!file://)` lookahead only blocks a match *starting* at that
# exact position, but finditer still retries one character later and
# happily matches "ile://..." as if "ile" were a scheme name (a real bug
# found via a test that actually exercised it, not assumed safe).
# STORY-1101 (docs/ARCHITECTURE.md sec14.2): captures the full URL (scheme +
# host + path), stopping at the first '?' -- identity is per-URL, not
# per-host, so scanning one path can no longer vouch for an unbounded set of
# other paths under the same host. Query string dropped to keep cache keys
# bounded.
_URL_FALLBACK_RE = re.compile(r"(?P<url>" + _URI_SCHEME + r"[^\s\"'?]+)")

# file:// is a filesystem reference, not a fetchable URL -- FileScanner's
# own resource, stripped down to the real path (matches _resolve_resource()'s
# existing file:// handling in onboard.py, same normalization).
_FILE_URI_RE = re.compile(r"file://(?P<path>[^\s\"']+)")


def _is_file_uri(url: str) -> bool:
    return url.lower().startswith("file://")

# Full URI span (any scheme, including file://) -- used only to exclude a
# URI's internal slashes from _PATH_FALLBACK_RE, so "https://host/a/b" (or
# "file:///a/b") doesn't get double-counted as a stray path fragment on top
# of its own correct extraction (URLScanner's or _FILE_URI_RE's).
_ANY_URI_SPAN_RE = re.compile(_URI_SCHEME + r"\S+")


def _find_paths_excluding_urls(text: str) -> list[str]:
    url_spans = [m.span() for m in _ANY_URI_SPAN_RE.finditer(text)]
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


# docs/ARCHITECTURE.md sec18.2 (STORY-1502): kept to exactly the two paths
# the user named -- not expanded to a broader guessed list. A developer can
# add their own restricted paths today via scalene_policy.yaml's `rules:`
# (sec14.1); this constant is a hardcoded floor, not the whole mechanism.
_HARDCODED_RESTRICTED_PREFIXES = (
    "/etc",
    os.path.expanduser("~/.ssh"),
)


def _is_hardcoded_restricted(identity: str) -> bool:
    """True if `identity` (an absolute file path) is exactly one of, or
    strictly under, a hardcoded restricted prefix -- not a naive
    str.startswith, which would also match a false positive like
    "/etcetera/file" against the "/etc" prefix."""
    for prefix in _HARDCODED_RESTRICTED_PREFIXES:
        if identity == prefix or identity.startswith(prefix.rstrip("/") + os.sep):
            return True
    return False


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
            # 2026-07-22 (direct user request): file:// is a filesystem
            # reference wearing a URI shape -- recognized here, not by
            # URLScanner, regardless of which tool/field it appears in.
            for m in _FILE_URI_RE.finditer(value):
                identities.append(os.path.abspath(m.group("path")))

        seen: set[str] = set()
        resources = []
        for identity in identities:
            if identity in seen:
                continue
            seen.add(identity)
            resources.append(Resource(kind="file", identity=identity, scanner_name=self.name))
        return resources

    def scan(self, resource: Resource) -> ScanResult:
        # sec18.2 (STORY-1502): a hardcoded-restricted path short-circuits
        # before the secrets-scan subprocess ever runs -- deliberate, not
        # just an optimization: Scalene shouldn't need to read the byte
        # contents of e.g. ~/.ssh/id_rsa to know it's sensitive. The
        # distinct reason text (vs. a real secrets finding) resolves
        # Smith's Gate 1 non-blocking note (don't let a clean file read as
        # "a secret was found").
        if _is_hardcoded_restricted(resource.identity):
            return ScanResult(label="sensitive", reason="path matches a hardcoded restricted system location")

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
            urls.extend(
                m.group("url") for m in _URL_FALLBACK_RE.finditer(known_value) if not _is_file_uri(m.group("url"))
            )

        for value in _string_args(args):
            urls.extend(
                m.group("url") for m in _URL_FALLBACK_RE.finditer(value) if not _is_file_uri(m.group("url"))
            )

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


class ScannerRegistryError(ValueError):
    """Raised by load_scanners() on a bad `scanners:` config section --
    caught and re-raised as PolicyConfigError by policy_config.from_yaml
    (avoids scanner.py importing back from policy_config.py)."""


def load_scanners(raw_config: dict) -> dict[str, Scanner]:
    """docs/ARCHITECTURE.md sec18.1 (STORY-1501): builds the registry a
    PolicyConfig uses, starting from the 2 builtins (always present -- an
    empty/absent `scanners:` section reproduces today's exact behavior) plus
    any `extra:` entries the project's scalene_policy.yaml declares.

    `raw_config` is `scalene_policy.yaml`'s `scanners:` section (or {}) --
    parsing/shape-validation of the YAML itself is policy_config.py's job;
    this function only resolves and validates the scanner classes it names.
    """
    scanners: dict[str, Scanner] = dict(SCANNERS)

    extra = raw_config.get("extra", []) or []
    if not isinstance(extra, list):
        raise ScannerRegistryError("'scanners.extra' must be a list")

    for i, entry in enumerate(extra):
        if not isinstance(entry, dict):
            raise ScannerRegistryError(f"'scanners.extra[{i}]' must be a mapping")
        try:
            name = entry["name"]
            import_path = entry["import"]
        except KeyError as exc:
            raise ScannerRegistryError(f"'scanners.extra[{i}]' is missing required field {exc}") from exc

        if name in scanners:
            raise ScannerRegistryError(
                f"'scanners.extra[{i}]' name {name!r} collides with an existing scanner "
                f"(builtin or already-registered)"
            )

        if ":" not in import_path:
            raise ScannerRegistryError(
                f"'scanners.extra[{i}].import' must be \"module.path:ClassName\", got {import_path!r}"
            )
        module_path, _, class_name = import_path.partition(":")
        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            raise ScannerRegistryError(f"'scanners.extra[{i}].import' {import_path!r} could not be imported: {exc}") from exc
        try:
            cls = getattr(module, class_name)
        except AttributeError as exc:
            raise ScannerRegistryError(
                f"'scanners.extra[{i}].import' {import_path!r}: module has no attribute {class_name!r}"
            ) from exc

        try:
            instance = cls()
        except Exception as exc:
            raise ScannerRegistryError(f"'scanners.extra[{i}]' ({import_path}) could not be constructed: {exc}") from exc

        if not (hasattr(instance, "name") and hasattr(instance, "identify") and hasattr(instance, "scan")):
            raise ScannerRegistryError(
                f"'scanners.extra[{i}]' ({import_path}) does not satisfy the Scanner protocol "
                f"(needs .name, .identify(), .scan())"
            )

        scanners[name] = instance

    return scanners
