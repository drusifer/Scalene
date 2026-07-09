"""Rapid credentials/secrets scan (STORY-501 allowlist-onboarding AC).

Deliberately simple pattern matching, not a full entropy/ML scanner — this is a
fast pre-write gate for onboarding, not a general-purpose secret detector.
"""

from __future__ import annotations

import re

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private key header", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "generic secret assignment",
        re.compile(r"(?i)(api[_-]?key|secret|token|password)\w*\s*[:=]\s*[\"']?[A-Za-z0-9_\-/+=]{16,}"),
    ),
]


def scan_text_for_secrets(text: str) -> list[str]:
    """Return a list of human-readable findings; empty list means clean."""
    if not text:
        return []
    findings = []
    for label, pattern in _PATTERNS:
        if pattern.search(text):
            findings.append(f"Possible {label} detected")
    return findings
