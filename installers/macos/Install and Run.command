#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
ROOT="$(pwd)"

echo ""
echo "  text-seeker"
echo "  ==========="
echo ""

bash "$ROOT/installers/macos/setup-runtime.sh"

PY="$ROOT/installers/runtime/macos/python/bin/python3"
BOOT="$ROOT/installers/common/bootstrap.py"

if [[ ! -x "$PY" ]]; then
  echo "ERROR: Portable Python setup failed." >&2
  read -r -p "Press Enter to close..."
  exit 1
fi

"$PY" "$BOOT" launch || {
  code=$?
  echo ""
  echo "The app exited with code $code."
  read -r -p "Press Enter to close..."
  exit "$code"
}
