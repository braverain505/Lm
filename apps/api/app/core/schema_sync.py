"""Bring the database schema up to head at API startup.

Render starts Uvicorn directly, and a free instance has **no shell, no
pre-deploy command and no one-off jobs** — so a pending Alembic revision has no
other route to the database. Without this, a migration that adds a column to a
model simply never reaches an already-provisioned database: ``create_all`` in
the squashed baseline skips tables that already exist, and the first ORM query
that selects the new column dies with
``column users.failed_login_count does not exist`` (a 500 on every login).

Two layers, deliberately:

1. ``alembic upgrade head`` — the real mechanism, which also keeps the recorded
   revision in step with the schema. It runs under a Postgres advisory lock so
   that several Uvicorn workers booting at once serialise on one migration
   instead of racing. The Alembic config is *searched for* rather than assumed:
   the app package may be imported from its source tree (dev, Docker) or from
   ``site-packages`` (``pip install .`` copies it there), and Render's service
   root directory may be the repo root or ``apps/api``.

2. ``_ensure_required_columns()`` — a safety net for the columns the app cannot
   serve a request without. It uses the app's own engine, which is known to work
   because ``/api/health`` reports the database as connected, so the login can be
   restored even when the Alembic path is unusable in a given deployment. It
   only issues DDL for columns that are genuinely absent.

Set ``AUTO_MIGRATE=0`` to disable (for a deployment that runs migrations
out-of-band).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from sqlalchemy import inspect

from .database import engine

# Alembic is a declared runtime dependency, but its absence must never stop the
# API from booting — that would turn "login is broken" into "the whole site is
# down". Layer 2 below does not need it.
try:
    from alembic import command
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
except ImportError:  # pragma: no cover
    command = Config = MigrationContext = ScriptDirectory = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Arbitrary but fixed: every worker of every deploy must contend on the *same*
# key, or two boots could run DDL concurrently.
_ADVISORY_LOCK_KEY = 0x5C4A001

# Columns added to the models without an incremental revision reaching
# already-provisioned databases, plus the exact DDL Alembic revision
# 0011_login_lockout_columns applies. Types mirror the model declarations:
# mapped_column(Integer, default=0, nullable=False) and DateTime(timezone=True).
_REQUIRED_COLUMNS: dict[str, dict[str, str]] = {
    "users": {
        "failed_login_count": "INTEGER NOT NULL DEFAULT 0",
        "locked_until": "TIMESTAMPTZ",
    },
}

_DISABLED = {"0", "false", "no", "off"}


def _enabled() -> bool:
    return os.getenv("AUTO_MIGRATE", "1").strip().lower() not in _DISABLED


def _describe(missing: dict[str, list[str]]) -> str:
    return ", ".join(
        f"{table}.{column}" for table, columns in missing.items() for column in columns
    )


# --- Layer 1: Alembic -------------------------------------------------------


def _find_alembic() -> tuple[Path, Path] | None:
    """Locate the shipped ``alembic.ini`` and script directory.

    Two things vary between deployments and neither is knowable from inside the
    app: whether ``app`` was imported from its source tree or from
    ``site-packages`` (``pip install .`` copies it), and whether the working
    directory is the repo root or ``apps/api``. So search the plausible spots
    instead of assuming one, and log which one won.
    """
    here = Path(__file__).resolve()
    roots = [Path.cwd(), *here.parents[1:4]]
    candidates = [root for root in roots]
    candidates += [root / "apps" / "api" for root in roots]

    seen: set[Path] = set()
    for base in candidates:
        if base in seen:
            continue
        seen.add(base)
        ini = base / "alembic.ini"
        if ini.is_file() and (base / "alembic").is_dir():
            return ini, base / "alembic"
    return None


def _alembic_config() -> Config | None:
    if Config is None:
        logger.warning("Alembic is not installed; skipping it and using the column repair")
        return None

    found = _find_alembic()
    if found is None:
        logger.error(
            "Could not find alembic.ini next to the app (searched from cwd=%s and %s); "
            "skipping Alembic and relying on the direct column repair",
            Path.cwd(),
            Path(__file__).resolve().parent,
        )
        return None

    ini, scripts = found
    logger.info("Running Alembic from %s", ini)
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(scripts))
    # The app configured logging at import (see app/main.py). env.py would
    # otherwise call fileConfig(), resetting the root logger to WARN and
    # blanking the API's own INFO logs — including the deploy log this module
    # reports to.
    cfg.attributes["skip_logging_config"] = True
    return cfg


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
    # Alembic >= 1.13 returns the base revision *string* from get_base(); the
    # older API returned the Script object. Accept either, so the recovery path
    # — the one that exists to rescue a stale database — cannot itself crash and
    # leave the upgrade to fail.
    base = script.get_base()
    base_revision = getattr(base, "revision", base)
    if not base_revision:
        logger.warning(
            "Recorded Alembic revision %r no longer exists (revision history was "
            "squashed) and no base revision was found to stamp; leaving the "
            "upgrade to the direct column repair",
            current,
        )
        return
    logger.warning(
        "Recorded Alembic revision %r no longer exists (revision history was "
        "squashed); stamping base %r before upgrading",
        current,
        base_revision,
    )
    command.stamp(cfg, base_revision)


def _run_alembic_upgrade(lock_conn) -> None:
    """Upgrade to head. Never raises."""
    try:
        cfg = _alembic_config()
        if cfg is None:
            return
        script = ScriptDirectory.from_config(cfg)

        current = _recorded_revision(lock_conn)
        lock_conn.commit()
        known = {rev.revision for rev in script.walk_revisions()}
        if current and current not in known:
            _recover_obsolete_revision(cfg, script, current)

        command.upgrade(cfg, "head")
        logger.info("Alembic upgrade complete (head: %s)", script.get_current_head())
    except Exception:
        logger.exception(
            "Alembic upgrade failed; falling back to the direct column repair"
        )


# --- Layer 2: the safety net ------------------------------------------------


def _missing_required_columns() -> dict[str, list[str]]:
    inspector = inspect(engine)
    missing: dict[str, list[str]] = {}
    for table, columns in _REQUIRED_COLUMNS.items():
        if not inspector.has_table(table):
            missing[table] = list(columns)
            continue
        present = {c["name"] for c in inspector.get_columns(table)}
        absent = [column for column in columns if column not in present]
        if absent:
            missing[table] = absent
    return missing


def _ensure_required_columns() -> None:
    """Guarantee the columns the app cannot serve a request without.

    Idempotent, and only issues DDL for columns that are genuinely absent, so a
    healthy boot costs two inspector queries and no table locks. Table and
    column names come from ``_REQUIRED_COLUMNS`` (never from input), so the
    interpolation into DDL is safe. Never raises.
    """
    try:
        missing = _missing_required_columns()
        if not missing:
            logger.info("Schema check: every required column is present")
            return

        logger.warning("Schema check: missing %s — applying the column repair", _describe(missing))
        with engine.begin() as conn:
            for table, columns in missing.items():
                for column in columns:
                    conn.exec_driver_sql(
                        f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS '
                        f'"{column}" {_REQUIRED_COLUMNS[table][column]}'
                    )

        still_missing = _missing_required_columns()
        if still_missing:
            logger.error(
                "Column repair did not stick; still missing: %s. Login will "
                "keep failing until these exist.",
                _describe(still_missing),
            )
        else:
            logger.info(
                "Schema check: repaired %s — login should work now",
                _describe(missing),
            )
    except Exception:
        logger.exception("Required-column check failed; login may keep failing")


def sync_schema() -> None:
    """Bring the schema to head, then guarantee the columns the app needs.

    Never raises: a failed migration must not stop the API from starting, since
    endpoints that don't need the new schema keep working. Everything is logged
    for the deploy log.
    """
    if not _enabled():
        logger.info("Schema sync skipped (AUTO_MIGRATE is off)")
        return

    try:
        with engine.connect() as lock_conn:
            # Session-scoped lock: it survives the commit below and covers both
            # layers, which run on their own connections.
            lock_conn.exec_driver_sql("SELECT pg_advisory_lock(%s)", (_ADVISORY_LOCK_KEY,))
            lock_conn.commit()
            try:
                _run_alembic_upgrade(lock_conn)
                _ensure_required_columns()
            finally:
                lock_conn.exec_driver_sql("SELECT pg_advisory_unlock(%s)", (_ADVISORY_LOCK_KEY,))
                lock_conn.commit()
    except Exception:
        logger.exception("Schema sync could not run")
