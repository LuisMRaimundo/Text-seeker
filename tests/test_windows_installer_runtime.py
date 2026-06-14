"""Installer policy tests — Windows explicit installer with user choices."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "installers" / "common"
WINDOWS = ROOT / "installers" / "windows"
SETUP_UI = WINDOWS / "installer_ui.ps1"
INSTALL_BAT = WINDOWS / "Install and Run.bat"


class TestWindowsInstallerRuntimePolicy(unittest.TestCase):
    def test_launcher_runs_explicit_installer_ui(self):
        install = INSTALL_BAT.read_text(encoding="utf-8").lower()
        ui = SETUP_UI.read_text(encoding="utf-8").lower()
        self.assertIn("installer_ui.ps1", install)
        self.assertNotIn("setup.ps1", install)
        self.assertNotIn("embed-amd64.zip", ui)
        self.assertNotIn("get-pip.py", ui)

    def test_installer_exposes_python_tesseract_poppler_path_choices(self):
        ui = SETUP_UI.read_text(encoding="utf-8").lower()
        cfg = (WINDOWS / "installer_config.ps1").read_text(encoding="utf-8").lower()
        for needle in (
            "pythonmode",
            "tesseractmode",
            "popplermode",
            "pathpolicy",
            "process_local",
            "skip",
            "private",
            "detected",
            "custom",
        ):
            self.assertIn(needle, ui + cfg, msg=needle)
        self.assertIn("get-detectedpythoninstallations", cfg)
        self.assertIn("install_state.json", cfg)

    def test_forbidden_embed_python_runtime(self):
        cfg = (WINDOWS / "installer_config.ps1").read_text(encoding="utf-8").lower()
        self.assertIn("embed-amd64", cfg)
        self.assertIn("get-pip.py", cfg)
        self.assertIn("remove-legacyembedruntime", cfg)
        self.assertNotIn("embed-amd64.zip", cfg)

    def test_tesseract_fallback_urls_not_mannheim_only(self):
        cfg = (WINDOWS / "installer_config.ps1").read_text(encoding="utf-8").lower()
        self.assertIn("tesseractinstallerurls", cfg)
        self.assertIn("invoke-downloadwithfallback", cfg)
        self.assertIn("github.com/ub-mannheim/tesseract", cfg)
        sys.path.insert(0, str(COMMON))
        from config import windows_tesseract_installer_urls  # noqa: E402

        urls = windows_tesseract_installer_urls()
        self.assertGreaterEqual(len(urls), 2)

    def test_tesseract_poppler_warning_only_python_hard_fail(self):
        cfg = (WINDOWS / "installer_config.ps1").read_text(encoding="utf-8")
        lower = cfg.lower()
        self.assertIn("tesseract unavailable; ocr for scanned images may not work.", lower)
        self.assertIn("poppler unavailable; scanned-pdf conversion may not work.", lower)
        self.assertIn("throw", cfg[cfg.lower().find("install-privatepythonto") :])
        self.assertIn("throw", cfg[cfg.lower().find("install-pythonpackagesto") :])

    def test_default_path_policy_process_local_only(self):
        cfg = (WINDOWS / "installer_config.ps1").read_text(encoding="utf-8").lower()
        ui = SETUP_UI.read_text(encoding="utf-8").lower()
        self.assertIn("pathpolicy = 'process_local'", cfg)
        self.assertIn("process-local path only", ui)
        install = INSTALL_BAT.read_text(encoding="utf-8").lower()
        self.assertNotIn("setenvironmentvariable", install)
        self.assertNotIn("add-tools-to-user-path", install)

    def test_user_path_modification_opt_in_via_installer_only(self):
        cfg = (WINDOWS / "installer_config.ps1").read_text(encoding="utf-8").lower()
        self.assertIn("apply-userpathpolicy", cfg)
        self.assertIn("user_path_modified", cfg)
        self.assertFalse((WINDOWS / "Add-Tools-To-User-Path.bat").exists())
        self.assertFalse((WINDOWS / "START-HERE.bat").exists())
        self.assertFalse((WINDOWS / "setup.ps1").exists())

    def test_install_state_json_semantics_in_config(self):
        sys.path.insert(0, str(COMMON))
        from config import (  # noqa: E402
            INSTALL_STATE_FILE,
            STATE_OCR_CAPABILITY,
            STATE_PATH_POLICY,
            STATE_PYTHON_MODE,
            load_install_state,
            ocr_tools_stamp,
        )

        self.assertTrue(str(INSTALL_STATE_FILE).endswith("install_state.json"))
        self.assertEqual(ocr_tools_stamp(tesseract_ok=True, poppler_ok=True), "ok")
        self.assertEqual(ocr_tools_stamp(tesseract_ok=False, poppler_ok=False), "missing")
        self.assertIsNone(load_install_state())
        self.assertEqual(STATE_PYTHON_MODE, "python_mode")
        self.assertEqual(STATE_PATH_POLICY, "path_policy")
        self.assertEqual(STATE_OCR_CAPABILITY, "ocr_capability")

    def test_process_local_path_from_state(self):
        sys.path.insert(0, str(COMMON))
        from config import process_path_parts_from_state  # noqa: E402

        py = ROOT / "installers" / "runtime" / "windows" / "python" / "python.exe"
        state = {
            "python_scripts_path": str(py.parent / "Scripts"),
            "venv_path": "",
            "tesseract_path": str(ROOT / "installers" / "runtime" / "windows" / "tesseract" / "tesseract.exe"),
            "poppler_bin": str(ROOT / "installers" / "runtime" / "windows" / "poppler" / "bin"),
            "tesseract_mode": "private",
            "poppler_mode": "private",
        }
        parts = process_path_parts_from_state(state, py)
        joined = ";".join(parts).lower()
        self.assertIn("python", joined)
        self.assertIn("scripts", joined)
        self.assertIn("tesseract", joined)
        self.assertIn("poppler", joined)

    def test_doctor_and_launch_use_install_state(self):
        bootstrap = (COMMON / "bootstrap.py").read_text(encoding="utf-8")
        self.assertIn("load_install_state", bootstrap)
        self.assertIn("process_path_parts_from_state", bootstrap)
        self.assertIn("GUI can launch", bootstrap)
        self.assertIn("OCR capability", bootstrap)
        self.assertIn("Text search available", bootstrap)
        launch = bootstrap[bootstrap.index("def launch_gui") : bootstrap.index("def _doctor_line")]
        self.assertNotIn("raise RuntimeError", launch)
        self.assertIn("WARNING: Tesseract unavailable", launch)

    def test_wizard_navigation_reaches_install_step(self):
        sys.path.insert(0, str(COMMON))
        # Regression: WinForms handler must not mix $step with $script:step
        ui = SETUP_UI.read_text(encoding="utf-8")
        self.assertIn("$script:WizardStep", ui)
        self.assertIn("Move-InstallerWizardStep", ui)
        self.assertNotIn("$script:step++", ui.lower())

        logic_path = WINDOWS / "installer_wizard_logic.ps1"
        self.assertTrue(logic_path.is_file())
        text = logic_path.read_text(encoding="utf-8")
        self.assertIn("Get-InstallerWizardNavigationState", text)
        self.assertIn("InstallEnabled", text)

        tests_ps1 = WINDOWS / "tests" / "InstallWizard.Tests.ps1"
        self.assertTrue(tests_ps1.is_file())

    def test_installer_ps1_files_are_pure_ascii(self):
        # Windows PowerShell 5.1 reads BOM-less .ps1 as Windows-1252; non-ASCII
        # characters (e.g. em-dash) corrupt parsing. Keep installer scripts ASCII.
        for name in ("installer_ui.ps1", "installer_config.ps1", "installer_wizard_logic.ps1"):
            data = (WINDOWS / name).read_bytes()
            non_ascii = [b for b in data if b > 127]
            self.assertEqual(
                non_ascii,
                [],
                msg=f"{name} contains non-ASCII bytes: {non_ascii[:8]}",
            )

    def test_python_selection_default_not_cpython_root(self):
        cfg = (WINDOWS / "installer_config.ps1").read_text(encoding="utf-8")
        # Default Python must never be a bare 'C:\Python'.
        self.assertNotRegex(cfg, r"PythonPath\s*=\s*['\"]C:\\Python['\"]")
        # Default mode is system or private; private points under the runtime.
        self.assertIn("$pyMode = if ($detectedPy) { 'system' } else { 'private' }", cfg)
        self.assertIn("DefaultPrivatePythonDir", cfg)

    def test_custom_python_path_is_resolved_and_validated(self):
        cfg = (WINDOWS / "installer_config.ps1").read_text(encoding="utf-8")
        self.assertIn("function Resolve-PythonExePath", cfg)
        self.assertIn("function Test-PythonCandidate", cfg)
        # Validation must check version, pip, tkinter.
        self.assertIn("PythonMinMinor", cfg)
        self.assertIn("import tkinter", cfg)
        self.assertIn("-m pip --version", cfg)

    def test_python_step_block_reason_logic(self):
        logic = (WINDOWS / "installer_wizard_logic.ps1").read_text(encoding="utf-8")
        self.assertIn("function Get-PythonStepBlockReason", logic)
        self.assertIn("Selected Python is not valid", logic)
        self.assertIn("Install private Python", logic)
        # Private mode must not be blocked at the Python step.
        self.assertRegex(logic, r"if \(\$Mode -eq 'private'\) \{ return \$null \}")

    def test_wizard_gates_next_on_python_step(self):
        ui = SETUP_UI.read_text(encoding="utf-8")
        self.assertIn("Test-CanLeaveCurrentStep", ui)
        self.assertIn("Get-PythonStepBlockReason", ui)
        # Next handler must respect the gate.
        self.assertIn("if (-not (Test-CanLeaveCurrentStep)) { return }", ui)

    def test_private_python_install_is_robust(self):
        cfg = (WINDOWS / "installer_config.ps1").read_text(encoding="utf-8")
        # Must not use the automatic $args variable for installer arguments.
        self.assertNotRegex(cfg, r"\$args\s*=")
        # Must tolerate async completion and TargetDir being ignored (repair mode).
        self.assertIn("Wait-ForFile", cfg)
        self.assertIn("Find-PythonExeUnder", cfg)
        self.assertIn("LOCALAPPDATA", cfg)
        # 3010 (reboot-requested) is treated as success.
        self.assertIn("3010", cfg)
        # Honors a private TargetDir.
        self.assertIn("TargetDir=$TargetDir", cfg)

    def test_official_python_installer_only(self):
        sys.path.insert(0, str(COMMON))
        from config import (  # noqa: E402
            assert_official_windows_python_installer_url,
            windows_python_installer_url,
        )

        url = windows_python_installer_url()
        assert_official_windows_python_installer_url(url)
        self.assertTrue(url.endswith("-amd64.exe"))


if __name__ == "__main__":
    unittest.main()
