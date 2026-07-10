"""Rapid credentials/secrets scan (STORY-501 allowlist-onboarding AC).

STORY-801: uses `detect-secrets` (~25 provider/pattern detectors) instead of a
few hand-rolled regexes. Never enables detect-secrets' opt-in `--only-verified`
API-validation feature (Stripe/Twilio/IBM Cloud/etc. "is this secret still
live" check) — that would introduce real network egress, which this scan must
never do (docs/ARCHITECTURE.md sec 11.5).

`scan_file()` (not the `scan_line()` adhoc-string API) is used deliberately:
`scan_line()` skips its own entropy-limit filtering for non-quoted matches
(by design — it's meant for showing raw entropy scores in `detect-secrets
scan --string` CLI output), which floods plain English text with false
positives. `scan_file()` applies the full, filtered detection path, so the
scanned text is written to a real temporary file first.
"""

from __future__ import annotations

import os
import tempfile

from detect_secrets.core.scan import scan_file
from detect_secrets.settings import default_settings


def scan_text_for_secrets(text: str) -> list[str]:
    """Return a list of human-readable findings; empty list means clean."""
    if not text:
        return []

    fd, path = tempfile.mkstemp(suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        with default_settings():
            findings = [f"Possible {secret.type} detected" for secret in scan_file(path)]
    finally:
        os.unlink(path)

    # Preserve order, drop exact duplicate messages (e.g. the same secret
    # repeated across lines, or matched by more than one plugin on one line).
    return list(dict.fromkeys(findings))
