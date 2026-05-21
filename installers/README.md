# Autonomous installers (no Python required)

These launchers install a **private copy** of Python and all **text-seeker** libraries on **first run**, then open the desktop search window. You do **not** need Python, pip, or conda installed.

**Requirements:** Internet on first run (~200–400 MB download). Disk space ~600 MB after install. Windows 10/11, macOS 11+, or recent Linux (x86_64 or arm64).

**Optional (for scanned PDFs and images):**

- **[Tesseract OCR](https://github.com/tesseract-ocr/tesseract)** — text recognition from images and scanned pages
- **Poppler** — renders PDF pages for OCR (`pdf2image`); see [README_STARTING.md](../README_STARTING.md)

The app runs without either tool for normal text-based PDFs, DOCX, HTML, TXT, Excel, and CSV.

---

## Windows 10 / 11

1. Open the project folder (or your ZIP after unpacking).
2. Double-click:

   **`installers\windows\Install and Run.bat`**

3. Wait for the first-time setup (several minutes).
4. The **text-seeker** window opens. Keep the console window open while you use the app.

To stop: close the search window, then close the console or press **Ctrl+C**.

---

## macOS

1. In Terminal, make the launcher executable (once):

   ```bash
   chmod +x "installers/macos/Install and Run.command"
   chmod +x installers/macos/setup-runtime.sh
   ```

2. Double-click **`installers/macos/Install and Run.command`**  
   (If blocked: **System Settings → Privacy & Security → Open Anyway**.)

---

## Linux

```bash
chmod +x installers/linux/install-and-run.sh installers/linux/setup-runtime.sh
./installers/linux/install-and-run.sh
```

---

## What gets installed?

| Location | Contents |
|----------|----------|
| `installers/runtime/` | Private Python + pip packages (gitignored) |
| Desktop | **text-seeker** Tkinter GUI |

To reinstall: delete `installers/runtime/` and run the launcher again.

---

## Troubleshooting

| Problem | What to try |
|---------|-------------|
| Setup failed | Check internet; retry after deleting `installers/runtime/` |
| GUI does not open | Run `installers\runtime\windows\python\python.exe app.py --gui` from project root (Windows) |
| OCR missing / no text in scans | Install Tesseract; set `TESSERACT_PATH` if needed — [README_STARTING.md](../README_STARTING.md) |
| PDF OCR fails, text PDFs OK | Install Poppler and add its `bin` to PATH (or `POPPLER_PATH` on Windows) — [README_STARTING.md](../README_STARTING.md) |

Diagnostics (any Python 3.10+):

```bash
python installers/common/bootstrap.py doctor
```
