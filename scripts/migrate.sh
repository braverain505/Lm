#!/usr/bin/env bash
# SchoolOS API — migrate + seed the dev database.
# Usage:  bash scripts/migrate.sh        (migrate)
#         bash scripts/migrate.sh seed   (migrate + seed demo data)
set -euo pipefail

cd "$(dirname "$0")/../apps/api"

VENV_PY="${VENV_PY:-../.venv/bin/python}"
if [ ! -x "${VENV_PY}" ]; then
  VENV_PY=python3
fi

# PYTHONNOUSERSITE=1 pins imports to the venv — without it, a stale alembic in
# ~/.local/lib/python3.11/site-packages can shadow the venv's copy and the
# wrong environment runs the migration.
export PYTHONNOUSERSITE=1

"${VENV_PY}" -m alembic upgrade head

if [ "${1:-}" = "seed" ]; then
  "${VENV_PY}" -m app.seed
fi