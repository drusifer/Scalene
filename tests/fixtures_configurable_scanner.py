"""Minimal Scanner subclass used only to test that load_scanners() (STORY-1501)
passes a config-declared scanner's own `scanners.extra[].config` sub-block
through Scanner.from_config() (2026-07-30). Not a real scanner -- no
production code imports this module."""

from __future__ import annotations

from scalene.scanner import Resource, ScanResult, Scanner


class ConfigurableScanner(Scanner):
    name = "configurable"

    def __init__(self, endpoint: str = "") -> None:
        self.endpoint = endpoint

    @classmethod
    def from_config(cls, raw_config: dict) -> "ConfigurableScanner":
        return cls(endpoint=raw_config.get("endpoint", ""))

    def identify(self, tool_name: str, args: dict) -> list[Resource]:
        return []

    def scan(self, resource: Resource) -> ScanResult:
        return ScanResult(label="public")
