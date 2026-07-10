"""Tests for the rapid credentials/secrets scan (STORY-501 allowlist AC,
upgraded to detect-secrets per STORY-801)."""

import socket
import unittest
from unittest.mock import patch

from scalene.secrets_scan import scan_text_for_secrets


class TestScanTextForSecrets(unittest.TestCase):
    def test_clean_text_finds_nothing(self):
        self.assertEqual(scan_text_for_secrets("just some ordinary markdown docs"), [])

    def test_detects_aws_access_key(self):
        # Fake key built via concatenation so it isn't a contiguous literal that
        # secret scanners (e.g. gitleaks) would flag in this source file.
        fake_key = "AKIA" + "ABCDEFGHIJKLMNOP"
        findings = scan_text_for_secrets(f'key = "{fake_key}"')
        self.assertTrue(any("AWS" in f for f in findings))

    def test_detects_private_key_header(self):
        header = "-----BEGIN" + " PRIVATE KEY-----"
        footer = "-----END" + " PRIVATE KEY-----"
        findings = scan_text_for_secrets(f"{header}\nMIIB...\n{footer}")
        self.assertTrue(any("private key" in f.lower() for f in findings))

    def test_detects_generic_secret_assignment(self):
        placeholder_value = "8f3a9c2e7b1d" + "4f6a0c5e8b2d7f1a4c6e"
        findings = scan_text_for_secrets(f'api_secret = "{placeholder_value}"')
        self.assertTrue(len(findings) >= 1)

    def test_never_raises_on_empty_text(self):
        self.assertEqual(scan_text_for_secrets(""), [])

    def test_detects_bare_provider_token_old_regexes_missed(self):
        # STORY-801 motivation: a bare provider token with no "secret=/token="
        # keyword context around it. The old 3 hand-rolled regexes (AWS key,
        # private-key header, generic `keyword = value` assignment) cannot
        # catch this shape at all — there's no keyword, just the token itself.
        # Built via concatenation to avoid tripping this repo's own gitleaks hook.
        fake_token = "ghp_" + "1234567890abcdef1234567890abcdef1234"
        findings = scan_text_for_secrets(fake_token)
        self.assertTrue(any("github" in f.lower() for f in findings))

    def test_never_attempts_network_access(self):
        # Architecture requirement (docs/ARCHITECTURE.md sec 11.5): detect-secrets
        # must never verify secrets against a live API. That's an opt-in-only
        # feature (--only-verified) we must never enable. Guard it directly by
        # blocking any socket connection during a scan and confirming it still
        # works cleanly.
        fake_key = "AKIA" + "ABCDEFGHIJKLMNOP"
        with patch.object(socket.socket, "connect", side_effect=AssertionError("network access attempted")):
            findings = scan_text_for_secrets(f'key = "{fake_key}"')
        self.assertTrue(any("AWS" in f for f in findings))


if __name__ == "__main__":
    unittest.main()
