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

_URL_FALLBACK_RE = re.compile(r"https?://(?P<host>[^/\s:\"']+)")


@dataclass(frozen=True)
class Resource:
    kind: str  # "file" | "url" -- extensible, not a closed enum
    identity: str  # cache key material: absolute path, or host
    scanner_name: str


@dataclass(frozen=True)
class ScanResult:
    label: str  # "public" | "sensitive" | "trusted" | "untrusted"
    reason: str = ""


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
            for match in _PATH_FALLBACK_RE.finditer(value):
                identities.append(os.path.abspath(match.group("path")))

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
        if result.get("ok", False):
            return ScanResult(label="public")
        return ScanResult(label="sensitive", reason=result.get("reason", ""))


class URLScanner:
    name = "reputation"

    def identify(self, tool_name: str, args: dict) -> list[Resource]:
        hosts: list[str] = []

        known_field = _URL_FIELDS.get(tool_name)
        known_value = args.get(known_field) if known_field else None
        if isinstance(known_value, str) and known_value:
            hosts.extend(m.group("host") for m in _URL_FALLBACK_RE.finditer(known_value))

        for value in _string_args(args):
            hosts.extend(m.group("host") for m in _URL_FALLBACK_RE.finditer(value))

        seen: set[str] = set()
        resources = []
        for host in hosts:
            if host in seen:
                continue
            seen.add(host)
            resources.append(Resource(kind="url", identity=host, scanner_name=self.name))
        return resources

    def scan(self, resource: Resource) -> ScanResult:
        result = run_scanner("reputation", resource.identity)
        if result.get("ok", False):
            return ScanResult(label="trusted")
        return ScanResult(label="untrusted", reason=result.get("reason", ""))


SCANNERS: dict[str, Scanner] = {"secrets": FileScanner(), "reputation": URLScanner()}
