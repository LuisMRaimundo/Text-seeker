"""Installer policy tests — Windows private runtime must not use embeddable Python."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETUP_PS1 = ROOT / "installers" / "windows" / "setup.ps1"


class TestWindowsInstallerRuntimePolicy(unittest.TestCase):
    def test_setup_ps1_does_not_reference_embed_zip(self):
        text = SETUP_PS1.read_text(encoding="utf-8")
        lower = text.lower()
        self.assertIn("python-$pythonversion-amd64.exe".lower(), lower)
        self.assertNotIn("embed-amd64.zip", lower)
        self.assertNotIn("bootstrap.pypa.io/get-pip", lower)
        self.assertNotIn("python-embed.zip", lower)
        self.assertNotIn("set-content -path $_.fullname -value ($lines -join", lower)
        self.assertIn("Include_tcltk=1", text)
        self.assertIn("Assert-OfficialPythonInstallerUrl", text)
        self.assertIn("Remove-LegacyEmbedRuntime", text)

    def test_config_official_python_url_only(self):
        import sys

        sys.path.insert(0, str(ROOT / "installers" / "common"))
        from config import (  # noqa: E402
            assert_official_windows_python_installer_url,
            windows_python_installer_url,
        )

        url = windows_python_installer_url()
        assert_official_windows_python_installer_url(url)
        self.assertTrue(url.endswith("-amd64.exe"))
        self.assertNotIn("embed", url.lower())


if __name__ == "__main__":
    unittest.main()
