#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ ! -f "$DIR/venv/bin/python" ]; then
  echo "venv not found — run: python3 -m venv venv && venv/bin/pip install -r requirements.txt"
  exit 1
fi

exec "$DIR/venv/bin/python" faucetplay_app.py "$@"
