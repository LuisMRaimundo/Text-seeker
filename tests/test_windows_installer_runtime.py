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
        # venv/managed Python failures are hard-fail (throw); OCR tools are warning-only.
        self.assertIn("throw", cfg[cfg.lower().find("function new-textseekervenv") :])
        self.assertIn("throw", cfg[cfg.lower().find("function install-managedpython") :])

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

    def test_process_local_path_includes_venv_scripts(self):
        sys.path.insert(0, str(COMMON))
        from config import process_path_parts_from_state  # noqa: E402

        rt = ROOT / "installers" / "runtime" / "windows"
        venv_py = rt / "venv" / "Scripts" / "python.exe"
        state = {
            "venv_python_path": str(venv_py),
            "base_python_path": str(rt / "python" / "python.exe"),
            "tesseract_path": str(rt / "tesseract" / "tesseract.exe"),
            "poppler_bin_path": str(rt / "poppler" / "bin"),
            "tesseract_mode": "private_installed",
            "poppler_mode": "private_installed",
        }
        parts = process_path_parts_from_state(state, venv_py)
        joined = ";".join(parts).lower()
        # venv Scripts is the launch interpreter dir and must be on the process PATH.
        self.assertIn(str(venv_py.parent).lower(), joined)
        self.assertIn("venv", joined)
        self.assertIn("scripts", joined)
        self.assertIn("tesseract", joined)
        self.assertIn("poppler", joined)

    def test_venv_is_launch_python(self):
        sys.path.insert(0, str(COMMON))
        import importlib
        import config as _config
        importlib.reload(_config)
        from config import resolve_python_exe_from_state, STATE_VENV_PYTHON_PATH  # noqa: E402

        # venv python is preferred over a base/system python in state.
        self.assertEqual(STATE_VENV_PYTHON_PATH, "venv_python_path")
        # The resolver prefers the venv key (file existence aside, key order matters).
        src = (COMMON / "config.py").read_text(encoding="utf-8")
        self.assertIn("STATE_VENV_PYTHON_PATH, STATE_PYTHON_PATH, STATE_BASE_PYTHON_PATH", src)

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

    def test_clean_machine_defaults_to_managed_python(self):
        cfg = (WINDOWS / "installer_config.ps1").read_text(encoding="utf-8")
        # Default Python must never be a bare 'C:\Python'.
        self.assertNotRegex(cfg, r"PythonPath\s*=\s*['\"]C:\\Python['\"]")
        # No-compatible-Python default = managed; detected default only when one exists.
        self.assertIn("$pyMode = if ($detectedPy) { 'detected' } else { 'managed' }", cfg)
        # Custom never the default; custom path empty unless detected.
        self.assertIn("PythonPath = if ($detectedPy) { $detectedPy.Path } else { '' }", cfg)

    def test_managed_python_uses_standalone_build(self):
        cfg = (WINDOWS / "installer_config.ps1").read_text(encoding="utf-8")
        self.assertIn("function Install-ManagedPython", cfg)
        managed = cfg[cfg.index("function Install-ManagedPython"):cfg.index("function New-TextSeekerVenv")]
        # Self-contained relocatable build: download + extract, no .exe installer.
        self.assertIn("python-build-standalone", cfg)
        self.assertIn("install_only", cfg)
        self.assertIn("tar.exe", managed)
        self.assertNotIn("Start-Process -FilePath $installerPath", managed)
        self.assertNotIn("TargetDir=", managed)
        # Validated end to end before use.
        self.assertIn("Test-PrivatePythonValid", managed)

    def test_always_creates_project_venv(self):
        cfg = (WINDOWS / "installer_config.ps1").read_text(encoding="utf-8")
        self.assertIn("function New-TextSeekerVenv", cfg)
        self.assertIn("-m venv", cfg)
        # requirements install target is the venv python, not global.
        venv = cfg[cfg.index("function New-TextSeekerVenv"):]
        self.assertIn("$venvPy -m pip install -r $Requirements", venv)
        # Invoke-InstallerRun launches from the venv python.
        self.assertIn("$venvPy = New-TextSeekerVenv", cfg)
        self.assertIn("$launchPy = $venvPy", cfg)

    def test_resolver_functions_return_clean_scalar_paths(self):
        # Functions must not leak command stdout (pip/venv/tar) into their return value,
        # or the launch path becomes an array and Split-Path fails on empty strings.
        cfg = (WINDOWS / "installer_config.ps1").read_text(encoding="utf-8")
        self.assertIn("return [string]$venvPy", cfg)
        self.assertIn("return [string]$pyExe", cfg)
        # pip/venv/tar invocations capture their output instead of emitting it.
        self.assertIn("-m venv $VenvDir 2>&1 | Out-String", cfg)
        self.assertIn("$null = & $venvPy -m pip install", cfg)
        self.assertIn("-xf $archive -C $extractDir 2>&1 | Out-String", cfg)

    def test_install_state_records_paths_and_status(self):
        cfg = (WINDOWS / "installer_config.ps1").read_text(encoding="utf-8")
        for field in ("base_python_path", "venv_python_path", "packages_installed",
                      "tesseract_mode", "tesseract_path", "poppler_mode", "poppler_bin_path",
                      "path_policy", "gui_ready", "ocr_capability",
                      "install_timestamp", "installer_version"):
            self.assertIn(field, cfg, msg=field)

    def test_gui_ready_independent_of_ocr(self):
        cfg = (WINDOWS / "installer_config.ps1").read_text(encoding="utf-8")
        # gui_ready derives from the venv Python validation, not from OCR tools.
        self.assertIn("$guiReady = [bool](Test-PrivatePythonValid -PyExe $launchPy)", cfg)
        self.assertIn("gui_ready = $guiReady", cfg)

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
        self.assertIn("managed Python install", logic)
        # Managed mode must not be blocked at the Python step.
        self.assertIn("$Mode -eq 'managed'", logic)

    def test_wizard_gates_next_on_python_step(self):
        ui = SETUP_UI.read_text(encoding="utf-8")
        self.assertIn("Test-CanLeaveCurrentStep", ui)
        self.assertIn("Get-PythonStepBlockReason", ui)
        # Next handler must respect the gate.
        self.assertIn("if (-not (Test-CanLeaveCurrentStep)) { return }", ui)

    def test_managed_install_is_robust(self):
        cfg = (WINDOWS / "installer_config.ps1").read_text(encoding="utf-8")
        # Must not use the automatic $args variable for installer arguments.
        self.assertNotRegex(cfg, r"\$args\s*=")
        # Full end-to-end validation of the interpreter (import tkinter + Tk()).
        self.assertIn("VALID OK", cfg)
        self.assertIn("import tkinter", cfg)
        # Standalone archive must contain python.exe or it fails clearly.
        self.assertIn("did not contain python.exe", cfg)
        # Validation probe self-locates bundled Tcl/Tk and logs the real error.
        self.assertIn("TCL_LIBRARY", cfg)
        self.assertIn("LastPythonProbeOutput", cfg)

    def test_venv_tcl_sitecustomize(self):
        cfg = (WINDOWS / "installer_config.ps1").read_text(encoding="utf-8")
        # venv gets a sitecustomize so the GUI locates Tcl/Tk on every launch.
        self.assertIn("function Write-VenvTclSiteCustomize", cfg)
        self.assertIn("sitecustomize.py", cfg)
        self.assertIn("Write-VenvTclSiteCustomize -VenvDir", cfg)

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
