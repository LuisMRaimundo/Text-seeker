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

    def test_tesseract_uses_fallback_urls_not_mannheim_only(self):
        text = SETUP_PS1.read_text(encoding="utf-8")
        lower = text.lower()
        self.assertIn("$tesseractinstallerurls", lower)
        self.assertIn("invoke-downloadwithfallback", lower)
        self.assertIn("github.com/ub-mannheim/tesseract/releases/download/", lower)
        self.assertIn("digi.bib.uni-mannheim.de/tesseract/", lower)
        self.assertNotIn("$tesseractinstallerurl =", lower)

        import sys

        sys.path.insert(0, str(ROOT / "installers" / "common"))
        from config import windows_tesseract_installer_urls  # noqa: E402

        urls = windows_tesseract_installer_urls()
        self.assertGreaterEqual(len(urls), 2)
        self.assertTrue(urls[0].startswith("https://github.com/UB-Mannheim/tesseract/"))
        self.assertIn("digi.bib.uni-mannheim.de", urls[1])

    def test_tesseract_and_poppler_failures_are_warning_only(self):
        text = SETUP_PS1.read_text(encoding="utf-8")
        lower = text.lower()
        self.assertIn(
            "tesseract download failed; ocr for scanned images may be unavailable",
            lower,
        )
        self.assertIn("invoke-downloadoptional", lower)
        self.assertIn("poppler download failed", lower)
        # Python/Tkinter remain hard-fail.
        self.assertIn("throw", text[text.lower().find("function test-pythontkinter") :])
        self.assertIn("throw", text[text.lower().find("function install-privatepython") :])

    def test_python_tkinter_remains_hard_fail(self):
        text = SETUP_PS1.read_text(encoding="utf-8")
        tk_section = text[text.index("function Test-PythonTkinter") : text.index("function Install-PythonPackages")]
        self.assertIn("throw", tk_section)
        self.assertIn("Tkinter is not available", tk_section)


if __name__ == "__main__":
    unittest.main()
