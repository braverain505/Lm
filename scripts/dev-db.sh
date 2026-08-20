#!/usr/bin/env bash
# SchoolOS dev database bootstrap: roles + databases for app / test.
# Run once after Postgres is installed:  bash scripts/dev-db.sh
#
# Auth: tries `sudo -u postgres` (peer auth, the Linux default) first. If that
# isn't available, falls back to plain psql and honors PGPASSWORD (set it if
# your postgres superuser has a password):
#     PGPASSWORD=your_pg_password bash scripts/dev-db.sh
set -euo pipefail

DB_ROLE="${DB_ROLE:-schoolos}"
DB_PASSWORD="${DB_PASSWORD:-schoolos}"
DB_NAME="${DB_NAME:-schoolos_dev}"
TEST_DB="${TEST_DB:-schoolos_test}"

# Pick a command prefix that can talk to the postgres superuser.
PSQL_PREFIX=()
if [ "$(id -un)" != "postgres" ] && command -v sudo >/dev/null 2>&1 && \
   sudo -n -u postgres true 2>/dev/null; then
  # Passwordless sudo to the postgres OS user — the peer-authenticated path.
  PSQL_PREFIX=(sudo -u postgres)
elif [ -z "${PGPASSWORD:-}" ]; then
  # No postgres OS access and no password given: try sudo (will prompt), else
  # plain psql (will prompt for the postgres password).
  if [ "$(id -un)" != "postgres" ] && command -v sudo >/dev/null 2>&1; then
    PSQL_PREFIX=(sudo -u postgres)
  fi
fi

psqlx() { "${PSQL_PREFIX[@]}" psql -v ON_ERROR_STOP=1 "$@"; }
createdbx() { "${PSQL_PREFIX[@]}" createdb "$@"; }

psqlx -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_ROLE}'" postgres | grep -q 1 \
  || psqlx -c "CREATE ROLE ${DB_ROLE} LOGIN PASSWORD '${DB_PASSWORD}'" postgres

for db in "${DB_NAME}" "${TEST_DB}"; do
  if psqlx -Atqc "SELECT 1 FROM pg_database WHERE datname = '${db}'" postgres | grep -q 1; then
    echo "database exists: ${db}"
  else
    createdbx -O "${DB_ROLE}" "${db}"
    echo "created database: ${db}"
  fi
done

echo "Dev DB ready: ${DB_ROLE} @ localhost:5432 (${DB_NAME}, ${TEST_DB})"