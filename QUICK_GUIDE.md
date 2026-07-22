# Quick Guide: Boolean Queries

**text-seeker** searches local folders with boolean logic. Supported types: **TXT, PDF, DOCX, HTML, Markdown, Excel, CSV, images (OCR)**.

## Operators
- `AND` (also `&&`)
- `OR` (also `||`)
- `NOT` (also `!` or `~`)
- `NEAR/x` (words within distance `x`)

## Precedence (highest → lowest)
1. `NOT`
2. `NEAR/x`
3. `AND`
4. `OR`

Use parentheses to control grouping.

## Examples
- **Simple term**: `spectral`
- **Wildcard**: `textur*` (matches `texture`, `textural`, etc.)
- **Single‑char wildcard**: `colo?r` (matches `color` / `colour`)
- **Phrase**: `"spectral density"`
- **Near**: `texture NEAR/4 uniform`
- **Grouped**: `texture NEAR/4 (uniform OR homogeneous)`
- **Exclude**: `texture AND NOT noise`

## Common Pitfalls
- `A NEAR/4 B OR C` means `(A NEAR/4 B) OR C`.  
  If you want A near any of them, use:  
  `A NEAR/4 (B OR C)`
- Typos matter: `homogeneneous` won’t match `homogeneous`.

## Notes
- Matching is case‑insensitive.
- Accents are normalized by default (e.g., `ação` ≈ `acao`). Use **accent-sensitive** in the GUI or `--accent-sensitive` on the CLI to disable folding.
- **Stemming** is on by default in the GUI (e.g. `piano` matches `pianos`). CLI: `--stem` / `--no-stem`.
- On large folders, watch the GUI **status line** and progress bar (indexing, then search). For a quick first pass: **OCR Mode = never**, or temporarily uncheck **Use Indexing**.
- Full CLI and architecture: [README_STARTING.md](README_STARTING.md), [TECHNICAL_MANUAL.md](TECHNICAL_MANUAL.md).
