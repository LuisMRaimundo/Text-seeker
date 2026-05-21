# Quick Guide: Boolean Queries

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
- Accents are normalized (e.g., `ação` ≈ `acao`).
