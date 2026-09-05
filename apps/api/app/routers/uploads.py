"""Uploads + served media files (student photos, school logos)."""
from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse

from ..core.deps import DbSession, require_permission
from ..core.permissions import SCHOOL_MANAGE, STUDENTS_CREATE
from ..schemas.people import UploadOut
from ..services import storage_service

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


@router.get("/{file_path:path}")
def get_upload(file_path: str):
    """Serve a stored file read-only. Paths contain a random token, so the URL
    is effectively private (required for the PIN-based portal report card)."""
    target = storage_service.resolve_upload(file_path)
    return FileResponse(target, media_type=_MIME.get(target.suffix.lower(), "application/octet-stream"))