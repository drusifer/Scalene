"""Local, offline reputation/threat-intel heuristics (STORY-501 decision #4).

No paid external API in v1 (architecture §7.4) — a `ReputationChecker` interface
means a real API can be added later without touching callers.

2026-07-21 (docs/ARCHITECTURE.md sec18.3, STORY-1503): that real API arrives
here -- URLHausChecker (abuse.ch) plus composite_check(), which combines it
with LocalHeuristicChecker. Runs inside scan_worker.py's existing isolated
subprocess (STORY-601) -- the right place for a new outbound network call,
not a new isolation mechanism.

2026-07-21 (Tank's Phase 3 review, corrected same day): the endpoint was
originally chosen and documented as keyless -- Tank verified directly
against the live API (not just its docs) and found it now requires a real
Auth-Key. Corrected here: the key is read from SCALENE_URLHAUS_AUTH_KEY
(never hardcoded/committed -- see .env.example), and its absence is treated
as a real, honest "unavailable" condition (composite_check() degrades to
local-only), not a doomed unauthenticated request.
"""

from __future__ import annotations

import ipaddress
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Protocol

# sec18.3 (STORY-1503): composite_check() runs inside scan_worker.py's
# isolated subprocess (STORY-601) -- a real, separate process the test
# suite's own mocks can never reach. Setting this env var (which
# subprocess_isolation.run_scanner already copies the parent's os.environ
# into the child's) is the only way for the test suite to keep this
# codebase's standing no-live-network-in-tests convention across that
# process boundary, without gating production behavior on "am I under
# test." Unset (the real, production default): the external check runs.
_SKIP_REMOTE_ENV_VAR = "SCALENE_SKIP_REMOTE_REPUTATION"

SUSPICIOUS_LABEL_LENGTH = 30

# Host-lookup endpoint (docs/ARCHITECTURE.md sec18.3). Originally chosen and
# documented as keyless -- Tank's Phase 3 review verified against the real
# API (not its docs) and found it now requires an Auth-Key. Free to obtain
# (https://auth.abuse.ch/), never hardcoded here -- read from the env var
# below, documented in .env.example.
_URLHAUS_HOST_ENDPOINT = "https://urlhaus-api.abuse.ch/v1/host/"
_URLHAUS_TIMEOUT_SECONDS = 3.0
_URLHAUS_AUTH_KEY_ENV_VAR = "SCALENE_URLHAUS_AUTH_KEY"


_NUM_HEURISTICS = 3


@dataclass(frozen=True)
class ReputationResult:
    is_trusted: bool
    reason: str = ""
    score: float = 1.0  # docs/ARCHITECTURE.md sec17.6: 1.0 - (triggered heuristics / 3)


class ReputationChecker(Protocol):
    def check(self, target: str) -> ReputationResult: ...


class LocalHeuristicChecker:
    """Domain heuristics: IP-literal targets, punycode homographs, suspicious
    (unusually long) domain labels. No network calls.

    docs/ARCHITECTURE.md sec17.6: all 3 heuristics are evaluated unconditionally
    (not first-match-wins) so `score` reflects real evaluated signal, not a
    relabeled boolean -- `is_trusted` keeps its original any-trip-fails
    meaning, unchanged."""

    def check(self, target: str) -> ReputationResult:
        if not target:
            return ReputationResult(is_trusted=False, reason="Empty target", score=0.0)

        reasons = []
        if self._is_ip_literal(target):
            reasons.append("IP-literal targets are untrusted by default")
        if self._is_punycode(target):
            reasons.append("Punycode-encoded domain (possible homograph attack)")
        if self._has_suspicious_label(target):
            reasons.append(f"Suspicious domain label longer than {SUSPICIOUS_LABEL_LENGTH} characters")

        if not reasons:
            return ReputationResult(is_trusted=True, score=1.0)

        score = 1.0 - (len(reasons) / _NUM_HEURISTICS)
        return ReputationResult(is_trusted=False, reason="; ".join(reasons), score=score)

    @staticmethod
    def _is_ip_literal(target: str) -> bool:
        try:
            ipaddress.ip_address(target)
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_punycode(target: str) -> bool:
        return any(label.startswith("xn--") for label in target.split("."))

    @staticmethod
    def _has_suspicious_label(target: str) -> bool:
        return any(len(label) > SUSPICIOUS_LABEL_LENGTH for label in target.split("."))


class ReputationCheckUnavailable(Exception):
    """Raised by URLHausChecker.check() when the external source couldn't be
    reached (network error, timeout, non-200, malformed response) -- distinct
    from a real "clean" finding. composite_check() catches this specifically
    so a network hiccup can never look like "checked, came back clean"."""


def _query_urlhaus(host: str, timeout: float) -> dict:
    """The actual HTTP call, isolated in its own function so tests can mock
    it directly rather than needing a live network connection (this project
    has no live-network tests anywhere else either).

    Raises ReputationCheckUnavailable immediately (no request sent) if
    SCALENE_URLHAUS_AUTH_KEY isn't set -- Tank's Phase 3 finding: the real
    endpoint returns a bare {"error": "Unauthorized"} without one, which
    isn't worth a doomed round-trip to discover every time."""
    auth_key = os.environ.get(_URLHAUS_AUTH_KEY_ENV_VAR)
    if not auth_key:
        raise ReputationCheckUnavailable(
            f"{_URLHAUS_AUTH_KEY_ENV_VAR} is not set -- get a free key at https://auth.abuse.ch/ "
            f"and set it to enable real external reputation checks"
        )

    data = urllib.parse.urlencode({"host": host}).encode("ascii")
    request = urllib.request.Request(
        _URLHAUS_HOST_ENDPOINT, data=data, method="POST", headers={"Auth-Key": auth_key}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class URLHausChecker:
    """docs/ARCHITECTURE.md sec18.3 (STORY-1503): queries URLhaus's (abuse.ch)
    keyless host-lookup endpoint. `query_status == "ok"` with at least one
    listed URL still `url_status == "online"` means URLhaus considers this
    host an active malware-distribution point right now -- untrusted,
    `score=0.0` (real external confirmation, not a heuristic guess, so no
    partial credit). Anything else real ("no_results", or every listed URL
    offline) is trusted from this source's perspective."""

    def check(self, target: str) -> ReputationResult:
        try:
            payload = _query_urlhaus(target, timeout=_URLHAUS_TIMEOUT_SECONDS)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ReputationCheckUnavailable(f"URLhaus request failed: {exc}") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ReputationCheckUnavailable(f"URLhaus returned a malformed response: {exc}") from exc

        query_status = payload.get("query_status")
        if query_status == "no_results":
            return ReputationResult(is_trusted=True, score=1.0)
        if query_status == "ok":
            urls = payload.get("urls") or []
            if any(entry.get("url_status") == "online" for entry in urls if isinstance(entry, dict)):
                return ReputationResult(
                    is_trusted=False,
                    reason="URLhaus lists this host as an active malware distribution point",
                    score=0.0,
                )
            return ReputationResult(is_trusted=True, score=1.0)

        # Any other query_status (e.g. "invalid_host") is a real signal the
        # request itself was malformed, not a network/availability problem --
        # still not a finding we can act on, so treat it the same as
        # unavailable rather than silently calling it clean.
        raise ReputationCheckUnavailable(f"URLhaus returned unexpected query_status: {query_status!r}")


def composite_check(target: str) -> ReputationResult:
    """docs/ARCHITECTURE.md sec18.3 (STORY-1503): always runs the free,
    offline LocalHeuristicChecker; attempts URLHausChecker on top. Combines
    any-bad-wins (sec13.1.1's existing ANY-match-is-unsafe convention) and
    min-score (sec14.4's most-restrictive-wins aggregation, applied here to
    a graded score instead of a sensitivity/mode rank). On
    ReputationCheckUnavailable, degrades to the local-only result but with a
    marker appended to `reason` -- Smith's Gate 1 non-blocking note: a
    developer must be able to tell "checked externally, came back clean"
    apart from "external check didn't run this time"."""
    local = LocalHeuristicChecker().check(target)

    if os.environ.get(_SKIP_REMOTE_ENV_VAR) == "1":
        reason = f"{local.reason}; external reputation check disabled" if local.reason else (
            "external reputation check disabled"
        )
        return ReputationResult(is_trusted=local.is_trusted, reason=reason, score=local.score)

    try:
        remote = URLHausChecker().check(target)
    except ReputationCheckUnavailable as exc:
        degraded_reason = f"{local.reason}; external reputation check unavailable: {exc}" if local.reason else (
            f"external reputation check unavailable: {exc}"
        )
        return ReputationResult(is_trusted=local.is_trusted, reason=degraded_reason, score=local.score)

    is_trusted = local.is_trusted and remote.is_trusted
    score = min(local.score, remote.score)
    reasons = [r for r in (local.reason, remote.reason) if r]
    return ReputationResult(is_trusted=is_trusted, reason="; ".join(reasons), score=score)
