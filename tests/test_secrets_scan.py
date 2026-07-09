"""Tests for the rapid credentials/secrets scan (STORY-501 allowlist AC)."""

import unittest

from scalene.secrets_scan import scan_text_for_secrets


class TestScanTextForSecrets(unittest.TestCase):
    def test_clean_text_finds_nothing(self):
        self.assertEqual(scan_text_for_secrets("just some ordinary markdown docs"), [])

    def test_detects_aws_access_key(self):
        # Fake key built via concatenation so it isn't a contiguous literal that
        # secret scanners (e.g. gitleaks) would flag in this source file.
        fake_key = "AKIA" + "ABCDEFGHIJKLMNOP"
        findings = scan_text_for_secrets(f"key = {fake_key}")
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


if __name__ == "__main__":
    unittest.main()
