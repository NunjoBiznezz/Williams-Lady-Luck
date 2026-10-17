#!/bin/bash
# Run make_stencils.py with its own small Python environment (~/.venvs/stencils).
# First run creates it (needs internet once); after that it works offline.
#   bash scripts/stencils.sh "UL slingshot.svg" [options]
set -e
VENV="$HOME/.venvs/stencils"
HERE="$(cd "$(dirname "$0")" && pwd)"
if [ ! -x "$VENV/bin/python" ]; then
  echo "Setting up $VENV (one time)..."
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --upgrade pip
  "$VENV/bin/pip" install --quiet -r "$HERE/requirements-stencils.txt"
fi
exec "$VENV/bin/python" "$HERE/make_stencils.py" "$@"
