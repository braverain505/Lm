"""Legacy data import: wizard endpoints (3.1) + history, re-import, and live
progress (3.2).

The router stays thin: validate the payload, delegate to ``import_service``,
serialize. The one piece of machinery here is the background ``run`` — the
request returns 202 while ``run_import_job`` opens its own session and commits
per chunk, so ``GET /imports/{id}`` shows live ``rows_imported`` progress.
"""
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from ..core.deps import DbSession, require_permission
from ..core.errors import ConflictError
from ..core.permissions import IMPORTS_CREATE, IMPORTS_FIX, IMPORTS_VIEW
from ..models.imports import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_RUNNING,
)
from ..schemas.imports import (
    FixIn,
    ImportBatchOut,
    ImportCreate,
    ImportFieldOut,
    ImportRowOut,
    ImportRowsOut,
    MappingIn,
    ReimportIn,
)
from ..services import import_service

router = APIRouter(prefix="/imports", tags=["imports"])


@router.get("/fields", response_model=list[ImportFieldOut])
def import_fields(
    ctx=Depends(require_permission(IMPORTS_VIEW)),
    entity_type: str = Query(...),
):
    """Target fields for the column-mapping step of a given entity type."""
    return [
        ImportFieldOut(
            name=f.name,
            label=f.label,
            required=f.required,
            kind=f.kind,
            options=list(f.options) if f.options else None,
            max_length=f.max_length,
        )
        for f in import_service.entity_fields(entity_type)
    ]


@router.get("", response_model=list[ImportBatchOut])
def import_history(
    db: DbSession,
    ctx=Depends(require_permission(IMPORTS_VIEW)),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Import history, newest first (3.2)."""
    batches = import_service.list_batches(db, ctx.school.id, limit=limit, offset=offset)
    return [ImportBatchOut.model_validate(b) for b in batches]


@router.post("", response_model=ImportBatchOut, status_code=201)
def create_import(
    payload: ImportCreate,
    db: DbSession,
    ctx=Depends(require_permission(IMPORTS_CREATE)),
):
    """Store a parsed file's raw rows (JSONB) for the wizard's mapping step."""
    batch = import_service.create_batch(
        db,
        ctx.school.id,
        entity_type=payload.entity_type,
        filename=payload.filename,
        rows=[r.model_dump() for r in payload.rows],
        created_by=ctx.user.id,
    )
    db.commit()
    return ImportBatchOut.model_validate(batch)


@router.get("/{batch_id}", response_model=ImportBatchOut)
def import_detail(
    batch_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(IMPORTS_VIEW)),
):
    """Batch header + counters — polled by the UI for live import progress."""
    batch = import_service.get_batch(db, ctx.school.id, batch_id)
    # Reload committed state so a poll issued right after the background job
    # finishes sees completed/failed, not a status cached earlier in this
    # session.
    db.refresh(batch)
    return ImportBatchOut.model_validate(batch)


@router.get("/{batch_id}/rows", response_model=ImportRowsOut)
def import_rows(
    batch_id: uuid.UUID,
    db: DbSession,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx=Depends(require_permission(IMPORTS_VIEW)),
):
    """Page through a batch's rows, optionally filtered (e.g. status=invalid
    for the fix screen)."""
    batch = import_service.get_batch(db, ctx.school.id, batch_id)
    rows, total = import_service.list_rows(
        db, batch, status=status, limit=limit, offset=offset
    )
    return ImportRowsOut(
        rows=[ImportRowOut.from_row(r) for r in rows],
        total=total,
    )


@router.post("/{batch_id}/mapping", response_model=ImportBatchOut)
def set_mapping(
    batch_id: uuid.UUID,
    payload: MappingIn,
    db: DbSession,
    ctx=Depends(require_permission(IMPORTS_CREATE)),
):
    """Bind source columns to target fields and re-validate every row."""
    batch = import_service.set_mapping(db, ctx.school.id, batch_id, payload.mapping)
    db.commit()
    return ImportBatchOut.model_validate(batch)


@router.put("/{batch_id}/rows/{row_id}/fix", response_model=ImportRowOut)
def set_row_fix(
    batch_id: uuid.UUID,
    row_id: uuid.UUID,
    payload: FixIn,
    db: DbSession,
    ctx=Depends(require_permission(IMPORTS_FIX)),
):
    """Layer a pre-import fix over one row and re-validate it (3.1)."""
    row = import_service.set_row_fixes(db, ctx.school.id, batch_id, row_id, payload.fixes)
    db.commit()
    return ImportRowOut.from_row(row)


@router.post("/{batch_id}/run", response_model=ImportBatchOut, status_code=202)
def run_import(
    batch_id: uuid.UUID,
    db: DbSession,
    background_tasks: BackgroundTasks,
    ctx=Depends(require_permission(IMPORTS_CREATE)),
):
    """Kick off the import. Returns 202 immediately; the background job
    commits per chunk so the detail endpoint reports live progress (3.2)."""
    batch = import_service.get_batch(db, ctx.school.id, batch_id)
    if batch.status in (STATUS_RUNNING, STATUS_COMPLETED, STATUS_FAILED):
        raise ConflictError(f"Import already {batch.status}")
    if not batch.column_mapping:
        raise ConflictError("Set a column mapping before running the import")

    # Persist the transition so pollers (and the background job's own session)
    # observe "running"; the job then owns RUNNING -> completed/failed.
    batch.status = STATUS_RUNNING
    db.commit()
    background_tasks.add_task(import_service.run_import_job, str(batch_id))
    return ImportBatchOut.model_validate(batch)


@router.post("/{batch_id}/reimport", response_model=ImportBatchOut, status_code=201)
def reimport(
    batch_id: uuid.UUID,
    db: DbSession,
    payload: ReimportIn | None = None,
    ctx=Depends(require_permission(IMPORTS_CREATE)),
):
    """Create a child batch reusing the parent's raw rows with a fresh mapping
    (3.2 — re-import without re-uploading)."""
    filename = payload.filename if payload else None
    batch = import_service.reimport(
        db,
        ctx.school.id,
        batch_id,
        created_by=ctx.user.id,
        filename=filename,
    )
    db.commit()
    return ImportBatchOut.model_validate(batch)