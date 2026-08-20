"""Import DTOs: upload payloads, batch/row views, mapping + fix requests."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ..services.import_service import MAX_ROWS_PER_BATCH


class ImportRowUpload(BaseModel):
    """One raw CSV row as the client parsed it — never normalized server-side."""

    row_number: int = Field(ge=1)
    data: dict[str, Any]


class ImportCreate(BaseModel):
    entity_type: str = Field(min_length=1, max_length=40)
    filename: str = Field(default="upload.csv", max_length=255)
    rows: list[ImportRowUpload] = Field(min_length=1, max_length=MAX_ROWS_PER_BATCH)


class ImportFieldOut(BaseModel):
    """A target field the mapping UI can bind a source column to."""

    name: str
    label: str
    required: bool
    kind: str
    options: list[str] | None = None
    max_length: int | None = None


class ImportRowOut(BaseModel):
    """A row with its raw data, validation errors, fixes, and effective values."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    batch_id: uuid.UUID
    row_number: int
    data: dict[str, Any]
    status: str
    errors: dict[str, list[str]] | None = None
    fixes: dict[str, Any] = {}
    effective: dict[str, Any] = {}
    imported_entity_id: uuid.UUID | None = None

    @classmethod
    def from_row(cls, row) -> "ImportRowOut":
        from ..models.imports import ImportRow

        effective = dict(row.data)
        effective.update(row.fixes or {})
        return cls(
            id=row.id,
            batch_id=row.batch_id,
            row_number=row.row_number,
            data=row.data,
            status=row.status,
            errors=row.errors or {},
            fixes=row.fixes or {},
            effective=effective,
            imported_entity_id=row.imported_entity_id,
        )


class ImportBatchOut(BaseModel):
    """Batch header + counters. The UI polls this while status == running."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    entity_type: str
    filename: str
    status: str
    columns: list[str]
    column_mapping: dict[str, str] | None = None
    parent_batch_id: uuid.UUID | None = None
    total_rows: int
    rows_valid: int
    rows_invalid: int
    rows_imported: int
    rows_failed: int
    error_summary: dict[str, int] = {}
    created_by: uuid.UUID | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class MappingIn(BaseModel):
    mapping: dict[str, str]


class FixIn(BaseModel):
    fixes: dict[str, Any]


class ReimportIn(BaseModel):
    filename: str | None = Field(default=None, max_length=255)


class ImportRowsOut(BaseModel):
    rows: list[ImportRowOut]
    total: int