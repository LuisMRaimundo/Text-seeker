"""Installer policy tests — Windows private runtime must not use embeddable Python."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETUP_PS1 = ROOT / "installers" / "windows" / "setup.ps1"
INSTALL_BAT = ROOT / "installers" / "windows" / "Install and Run.bat"
ADD_PATH_BAT = ROOT / "installers" / "windows" / "Add-Tools-To-User-Path.bat"
COMMON = ROOT / "installers" / "common"


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
        sys.path.insert(0, str(COMMON))
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

        sys.path.insert(0, str(COMMON))
        from config import windows_tesseract_installer_urls  # noqa: E402

        urls = windows_tesseract_installer_urls()
        self.assertGreaterEqual(len(urls), 2)
        self.assertTrue(urls[0].startswith("https://github.com/UB-Mannheim/tesseract/"))
        self.assertIn("digi.bib.uni-mannheim.de", urls[1])

    def test_tesseract_and_poppler_failures_are_warning_only(self):
        text = SETUP_PS1.read_text(encoding="utf-8")
        lower = text.lower()
        self.assertIn("tesseract unavailable; ocr for scanned images may not work.", lower)
        self.assertIn("poppler unavailable; scanned-pdf conversion may not work.", lower)
        self.assertIn("invoke-downloadoptional", lower)
        self.assertIn("ocr_tools=", lower)
        # Python/Tkinter remain hard-fail.
        self.assertIn("throw", text[text.lower().find("function test-pythontkinter") :])
        self.assertIn("throw", text[text.lower().find("function install-privatepython") :])

    def test_python_tkinter_remains_hard_fail(self):
        text = SETUP_PS1.read_text(encoding="utf-8")
        tk_section = text[text.index("function Test-PythonTkinter") : text.index("function Install-PythonPackages")]
        self.assertIn("throw", tk_section)
        self.assertIn("Tkinter is not available", tk_section)

    def test_default_installer_does_not_modify_global_or_user_path(self):
        setup = SETUP_PS1.read_text(encoding="utf-8").lower()
        install = INSTALL_BAT.read_text(encoding="utf-8").lower()
        self.assertIn("prependpath=0", setup)
        self.assertNotIn("setenvironmentvariable", setup)
        self.assertNotIn("add-tools-to-user-path", install)
        self.assertNotIn("setenvironmentvariable", install)

    def test_add_tools_to_user_path_is_opt_in_only(self):
        text = ADD_PATH_BAT.read_text(encoding="utf-8").lower()
        self.assertIn("optional", text)
        self.assertIn("pause", text)
        install = INSTALL_BAT.read_text(encoding="utf-8").lower()
        self.assertNotIn("add-tools-to-user-path", install)

    def test_process_local_path_includes_runtime_dirs(self):
        sys.path.insert(0, str(COMMON))
        from bootstrap import windows_process_path_parts  # noqa: E402
        from config import runtime_python_exe, windows_poppler_bin, windows_tesseract_dir  # noqa: E402

        py = runtime_python_exe("windows")
        parts = [Path(p) for p in windows_process_path_parts(py)]
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[0], py.parent)
        self.assertEqual(parts[1], py.parent / "Scripts")
        self.assertEqual(parts[2], windows_tesseract_dir())
        self.assertEqual(parts[3], windows_poppler_bin())

    def test_ocr_tools_stamp_values(self):
        sys.path.insert(0, str(COMMON))
        from config import ocr_tools_stamp, stamp_payload  # noqa: E402

        self.assertEqual(ocr_tools_stamp(tesseract_ok=True, poppler_ok=True), "ok")
        self.assertEqual(ocr_tools_stamp(tesseract_ok=True, poppler_ok=False), "partial")
        self.assertEqual(ocr_tools_stamp(tesseract_ok=False, poppler_ok=True), "partial")
        self.assertEqual(ocr_tools_stamp(tesseract_ok=False, poppler_ok=False), "missing")
        self.assertIn("ocr_tools=partial", stamp_payload(tesseract_ok=True, poppler_ok=False))

    def test_launch_does_not_require_tesseract_or_poppler(self):
        sys.path.insert(0, str(COMMON))
        bootstrap_src = (COMMON / "bootstrap.py").read_text(encoding="utf-8")
        launch_section = bootstrap_src[bootstrap_src.index("def launch_gui") : bootstrap_src.index("def _doctor_line")]
        self.assertNotIn("raise RuntimeError", launch_section)
        self.assertIn("WARNING: Tesseract OCR not found", launch_section)
        self.assertIn("WARNING: Poppler not found", launch_section)


if __name__ == "__main__":
    unittest.main()
