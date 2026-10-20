#!/bin/bash
# Run make_layer_stencils.py with the same small Python environment as stencils.sh (~/.venvs/stencils).
#   bash scripts/layer_stencils.sh "stencils/CL dancing girl.svg" [options]
set -e
VENV="$HOME/.venvs/stencils"
HERE="$(cd "$(dirname "$0")" && pwd)"
if [ ! -x "$VENV/bin/python" ]; then
  echo "Setting up $VENV (one time)..."
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --upgrade pip
  "$VENV/bin/pip" install --quiet -r "$HERE/requirements-stencils.txt"
fi
exec "$VENV/bin/python" "$HERE/make_layer_stencils.py" "$@"
