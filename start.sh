#!/bin/sh
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required." >&2
  exit 1
fi

echo "Paper Finder is starting at http://127.0.0.1:5051"
exec python3 app.py
