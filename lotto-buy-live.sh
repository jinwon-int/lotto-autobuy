#!/usr/bin/env bash
# Live Termux entrypoint. The dedicated venv prevents unrelated service
# virtualenvs or system Python upgrades from changing the lotto runtime.
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
LOTTO_PYTHON="${LOTTO_PYTHON:-$HOME/.hermes/venvs/lotto/bin/python}"
LOTTO_BIN_DIR="$(dirname -- "$LOTTO_PYTHON")"
CREDENTIALS_FILE="$HOME/.dhapi/credentials"

if ! [ -x "$LOTTO_PYTHON" ]; then
  printf 'lotto live: runtime missing: %s\n' "$LOTTO_PYTHON" >&2
  printf 'lotto live: run scripts/bootstrap-termux.sh first\n' >&2
  exit 1
fi

if ! [ -x "$LOTTO_BIN_DIR/dhapi" ]; then
  printf 'lotto live: dhapi missing from runtime: %s\n' "$LOTTO_BIN_DIR" >&2
  printf 'lotto live: run scripts/bootstrap-termux.sh first\n' >&2
  exit 1
fi

if ! [ -s "$CREDENTIALS_FILE" ]; then
  printf 'lotto live: dhapi credentials missing: %s\n' "$CREDENTIALS_FILE" >&2
  exit 1
fi

cd "$SCRIPT_DIR"
export PATH="$LOTTO_BIN_DIR:${PREFIX:-/data/data/com.termux/files/usr}/bin:$PATH"
export DRY_RUN=false
export LOTTO_STATE_FILE="${LOTTO_STATE_FILE:-$HOME/.hermes/state/lotto-last-purchase.json}"
exec "$LOTTO_PYTHON" "$SCRIPT_DIR/lotto_buy.py"
