"""Bring the database schema up to head at API startup.

Render starts Uvicorn directly, and a free instance has **no shell, no
pre-deploy command and no one-off jobs** — so a pending Alembic revision has no
other route to the database. Without this, a migration that adds a column to a
model simply never reaches an already-provisioned database: ``create_all`` in
the squashed baseline skips tables that already exist, and the first ORM query
that selects the new column dies with
``column users.failed_login_count does not exist`` (a 500 on every login).

The upgrade runs under a Postgres advisory lock so that several Uvicorn workers
booting at once serialise on one migration instead of racing.

Set ``AUTO_MIGRATE=0`` to disable (for a deployment that runs migrations
out-of-band).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from .database import engine

logger = logging.getLogger(__name__)

# Resolved from this file, never the cwd: the API is started from different
# working directories (Docker's /srv/api, Render's build root) and a relative
# "alembic" would silently locate nothing.
_API_DIR = Path(__file__).resolve().parents[1]
_ALEMBIC_INI = _API_DIR / "alembic.ini"
_ALEMBIC_DIR = _API_DIR / "alembic"

# Arbitrary but fixed: every worker of every deploy must contend on the *same*
# key, or two boots could run DDL concurrently.
_ADVISORY_LOCK_KEY = 0x5C4A001

# Columns that were added to the models without an incremental revision reaching
# already-provisioned databases. Verified after the upgrade so a silent no-op is
# reported in the deploy log instead of resurfacing as a mystery 500.
_EXPECTED_COLUMNS: dict[str, tuple[str, ...]] = {
    "users": ("failed_login_count", "locked_until"),
    "student_pins": ("failed_pin_count", "pin_locked_until"),
}

_DISABLED = {"0", "false", "no", "off"}


def _enabled() -> bool:
    return os.getenv("AUTO_MIGRATE", "1").strip().lower() not in _DISABLED


def _alembic_config() -> Config:
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("script_location", str(_ALEMBIC_DIR))
    # The app configured logging at import (see app/main.py). Alembic's env.py
    # calls fileConfig() unless asked not to, which would reset the root logger
    # to WARN and blank the API's own INFO logs — including the deploy log this
    # module reports to.
    cfg.attributes["skip_logging_config"] = True
    return cfg


def _recover_obsolete_revision(cfg: Config, script: ScriptDirectory, current: str) -> None:
    """Stamp the squashed base when the database recorded a revision that no
    longer exists.

    The old 12-revision chain (0001..0009, plus three hash-named revisions) was
    deleted in favour of ``0010_squashed_baseline``, so a database still
    recording e.g. ``0009_photo_urls_text`` would make ``upgrade`` abort with
    "Can't locate revision identified by ...". Such a database holds the old
    head's schema, which *is* the squashed base, so stamping the base is the
    documented remediation — and it lets the upgrade that follows apply the
    revisions the database genuinely still needs.
    """
    base = script.get_base().revision
    logger.warning(
        "Recorded Alembic revision %r no longer exists (revision history was "
        "squashed); stamping base %r before upgrading",
        current,
        base,
    )
    command.stamp(cfg, base)


def _recorded_revision(conn) -> str | None:
    """The revision the database has recorded, or ``None`` when it has never
    been migrated (no ``alembic_version`` table yet — the normal state of a
    freshly provisioned database). A read failure is treated as "unknown" and
    left for ``upgrade`` to resolve, rather than aborting the whole sync.
    """
    try:
        revision = MigrationContext.configure(conn).get_current_revision()
    except Exception:
        logger.warning("Could not read the recorded revision; assuming none", exc_info=True)
        # A failed statement aborts the Postgres transaction, and the caller's
        # commit() would then raise PendingRollbackError — skipping the sync
        # entirely, which is the exact failure this module exists to prevent.
        # The advisory lock is session-scoped, so a rollback does not drop it.
        conn.rollback()
        return None
    return revision


def _verify_columns() -> None:
    """Report the login/PIN lockout columns in the logs after the upgrade."""
    inspector = inspect(engine)
    missing: list[str] = []
    for table, columns in _EXPECTED_COLUMNS.items():
        if not inspector.has_table(table):
            missing.append(f"{table} (whole table)")
            continue
        present = {c["name"] for c in inspector.get_columns(table)}
        missing += [f"{table}.{c}" for c in columns if c not in present]

    if missing:
        logger.error(
            "Schema sync finished but these columns are still missing: %s. "
            "Login and the PIN portal will keep failing until they exist.",
            ", ".join(missing),
        )
    else:
        logger.info("Schema sync verified: login/PIN lockout columns present")


def sync_schema() -> None:
    """Upgrade the database to head.

    Never raises: a failed migration must not stop the API from starting, since
    endpoints that don't need the new schema keep working. Failures are logged
    with a traceback for the deploy log.
    """
    if not _enabled():
        logger.info("Schema sync skipped (AUTO_MIGRATE is off)")
        return

    try:
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)

        with engine.connect() as lock_conn:
            # Session-scoped lock: it survives the commit below and covers the
            # upgrade, which Alembic runs on its own connection.
            lock_conn.exec_driver_sql(
                "SELECT pg_advisory_lock(%s)", (_ADVISORY_LOCK_KEY,)
            )
            lock_conn.commit()
            try:
                current = _recorded_revision(lock_conn)
                lock_conn.commit()
                known = {rev.revision for rev in script.walk_revisions()}
                if current and current not in known:
                    _recover_obsolete_revision(cfg, script, current)
                command.upgrade(cfg, "head")
            finally:
                lock_conn.exec_driver_sql(
                    "SELECT pg_advisory_unlock(%s)", (_ADVISORY_LOCK_KEY,)
                )
                lock_conn.commit()

        logger.info("Schema sync complete (head: %s)", script.get_current_head())
        _verify_columns()
    except Exception:
        logger.exception(
            "Schema sync failed; starting with whatever schema the database "
            "already has"
        )
