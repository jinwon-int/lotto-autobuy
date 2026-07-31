#!/usr/bin/env bash
# Build an isolated Lotto AutoBuy runtime on Termux.
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
TERMUX_PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
BOOTSTRAP_PYTHON="${LOTTO_BOOTSTRAP_PYTHON:-$TERMUX_PREFIX/bin/python3}"
VENV_DIR="${LOTTO_VENV_DIR:-$HOME/.hermes/venvs/lotto}"

if ! [ -x "$BOOTSTRAP_PYTHON" ]; then
  printf 'lotto bootstrap: Python is not executable: %s\n' "$BOOTSTRAP_PYTHON" >&2
  exit 1
fi

"$BOOTSTRAP_PYTHON" -m venv "$VENV_DIR"
VENV_PYTHON="$VENV_DIR/bin/python"

"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -r "$REPO_DIR/requirements-termux.txt"
"$VENV_PYTHON" -m pip install --no-deps "dhapi==4.2.4"

"$VENV_PYTHON" -c "import Crypto, requests, yaml"
"$VENV_DIR/bin/dhapi" --help >/dev/null

printf 'lotto bootstrap: runtime ready at %s\n' "$VENV_DIR"
