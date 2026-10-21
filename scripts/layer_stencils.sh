#!/bin/bash
# Old name, kept so it still works: same as stencils.sh (picks the right generator itself).
exec bash "$(cd "$(dirname "$0")" && pwd)/stencils.sh" "$@"
