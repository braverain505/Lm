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
    Returns the served ``photo_url`` to store on the student."""
    data = await file.read()
    rel = storage_service.save_image_upload(
        data, file.content_type or "", str(ctx.school.id), kind="students"
    )
    return UploadOut(photo_url=f"/api/uploads/{rel}")


@router.post("/school-logo", response_model=UploadOut)
async def upload_school_logo(
    db: DbSession,
    file: UploadFile = File(...),
    ctx=Depends(require_permission(SCHOOL_MANAGE)),
):
    """Upload the school crest/logo; it is stored and immediately reflected on
    report cards (school.logo_url)."""
    data = await file.read()
    rel = storage_service.save_image_upload(
        data, file.content_type or "", str(ctx.school.id), kind="schools"
    )
    ctx.school.logo_url = f"/api/uploads/{rel}"
    db.commit()
    return UploadOut(photo_url=ctx.school.logo_url)


@router.get("/{file_path:path}")
def get_upload(file_path: str):
    """Serve a stored file read-only. Paths contain a random token, so the URL
    is effectively private (required for the PIN-based portal report card)."""
    target = storage_service.resolve_upload(file_path)
    return FileResponse(target, media_type=_MIME.get(target.suffix.lower(), "application/octet-stream"))