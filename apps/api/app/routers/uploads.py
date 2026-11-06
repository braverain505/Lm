"""Uploads + served media files (student photos, school logos, signatures)."""
from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..core.deps import DbSession, require_permission
from ..core.errors import NotFoundError
from ..core.permissions import SCHOOL_MANAGE, STUDENTS_CREATE
from ..schemas.people import UploadOut
from ..services import results_service, storage_service


class PrincipalSignatureCaption(BaseModel):
    """The name printed under the uploaded signature (``None`` clears it)."""

    name: str | None = Field(default=None, max_length=120)

router = APIRouter(prefix="/uploads", tags=["uploads"])

_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


@router.post("/student-photo", response_model=UploadOut)
async def upload_student_photo(
    file: UploadFile = File(...),
    ctx=Depends(require_permission(STUDENTS_CREATE)),
):
    """Upload a student photo ahead of creating/updating the student record.
    Returns a Base64 data URL (like school logos) to store on the student —
    kept in the database so photos survive Render's ephemeral filesystem."""
    data = await file.read()
    # Store as Base64 data URL in database (Render free-tier has ephemeral
    # storage, so file-backed uploads vanish on restart).
    photo_url = storage_service.save_image_as_base64(data, file.content_type or "")
    return UploadOut(photo_url=photo_url)


@router.post("/school-logo", response_model=UploadOut)
async def upload_school_logo(
    db: DbSession,
    file: UploadFile = File(...),
    ctx=Depends(require_permission(SCHOOL_MANAGE)),
):
    """Upload the school crest/logo; stored as Base64 in database for Render
    free-tier compatibility (ephemeral storage). Returns a data URL that can
    be used directly in <img src={...} />."""
    data = await file.read()
    # Store as Base64 data URL in database
    logo_url = storage_service.save_image_as_base64(data, file.content_type or "")
    ctx.school.logo_url = logo_url
    db.commit()
    return UploadOut(photo_url=logo_url)


@router.post("/principal-signature", response_model=UploadOut)
async def upload_principal_signature(
    db: DbSession,
    file: UploadFile = File(...),
    name: str | None = Form(None),
    ctx=Depends(require_permission(SCHOOL_MANAGE)),
):
    """Upload the head teacher's signature for the report card.

    A photograph or scan of the signature on white paper works best. Stored as
    a Base64 data URL in the school's settings (the same way the logo is kept
    in the database, since Render's filesystem is ephemeral), and printed above
    the principal's line on every card the school produces — including a
    reopened term's reprint, which draws the same stored image.
    """
    data = await file.read()
    url = storage_service.save_image_as_base64(data, file.content_type or "")
    results_service.set_principal_signature(db, ctx.school, url=url, name=name)
    db.commit()
    return UploadOut(photo_url=url)


@router.patch("/principal-signature")
def update_principal_signature_caption(
    payload: PrincipalSignatureCaption,
    db: DbSession,
    ctx=Depends(require_permission(SCHOOL_MANAGE)),
):
    """Change the name printed under the signature without re-uploading it."""
    signature = results_service.principal_signature(ctx.school)
    if signature is None:
        raise NotFoundError("This school has not uploaded a signature yet")
    stored = results_service.set_principal_signature(
        db, ctx.school, url=signature["url"], name=payload.name
    )
    db.commit()
    return stored


@router.delete("/principal-signature")
def delete_principal_signature(
    db: DbSession,
    ctx=Depends(require_permission(SCHOOL_MANAGE)),
):
    """Remove the signature; cards fall back to the ruled principal line."""
    results_service.clear_principal_signature(db, ctx.school)
    db.commit()
    return {"removed": True}


@router.get("/{file_path:path}")
def get_upload(file_path: str):
    """Serve a stored file read-only. Paths contain a random token, so the URL
    is effectively private (required for the PIN-based portal report card)."""
    target = storage_service.resolve_upload(file_path)
    return FileResponse(target, media_type=_MIME.get(target.suffix.lower(), "application/octet-stream"))