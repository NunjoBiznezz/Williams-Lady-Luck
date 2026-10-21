#!/bin/bash
# Make stencils with their own small Python environment (~/.venvs/stencils).
# First run creates it (needs internet once); after that it works offline.
# Runs make_all_stencils.py, which looks at each source SVG and calls the right generator.
#   bash scripts/stencils.sh                               every source SVG in stencils/
#   bash scripts/stencils.sh "stencils/UL slingshot.svg"   just one (options may follow)
#   bash scripts/stencils.sh --dry-run                     show what would be made
set -e
VENV="$HOME/.venvs/stencils"
HERE="$(cd "$(dirname "$0")" && pwd)"
if [ ! -x "$VENV/bin/python" ]; then
  echo "Setting up $VENV (one time)..."
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --upgrade pip
  "$VENV/bin/pip" install --quiet -r "$HERE/requirements-stencils.txt"
fi
exec "$VENV/bin/python" "$HERE/make_all_stencils.py" "$@"
