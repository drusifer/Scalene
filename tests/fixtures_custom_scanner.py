"""Minimal Scanner-protocol implementation used only to test that
scanner.load_scanners() can dynamically import and register a
config-declared scanner (sec18.1, STORY-1501). Not a real scanner -- no
production code imports this module."""

from __future__ import annotations

from scalene.scanner import Resource, ScanResult


class DummyScanner:
    name = "dummy"

    def identify(self, tool_name: str, args: dict) -> list[Resource]:
        value = args.get("dummy_field")
        if not value:
            return []
        return [Resource(kind="dummy", identity=value, scanner_name=self.name)]

    def scan(self, resource: Resource) -> ScanResult:
        return ScanResult(label="public")


class NotAScanner:
    """Deliberately missing identify()/scan() -- used to test protocol
    validation rejects a class that doesn't actually satisfy Scanner."""

    name = "not_a_scanner"
