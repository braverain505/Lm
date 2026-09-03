"""Local file storage for uploaded media (student photos, avatars).

Files are stored under ``settings.storage_base_dir`` as
``{kind}/{school_id}/{random}.{ext}`` and served read-only through the
``/api/uploads/...`` route. The random filename doubles as the access token,
so URLs are effectively unguessable (public GET, no auth — needed by the
PIN-based parent portal report card).
"""
import uuid
from pathlib import Path

from ..config import settings
from ..core.errors import NotFoundError, ValidationError

ALLOWED_IMAGE_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def _storage_root() -> Path:
    root = Path(settings.storage_base_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_image_upload(data: bytes, content_type: str, school_id: str, kind: str = "students") -> str:
    """Persist an image upload and return the relative storage path."""
    ext = ALLOWED_IMAGE_TYPES.get((content_type or "").lower())
    if ext is None:
        raise ValidationError("Only JPEG, PNG and WebP images are allowed")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValidationError("Image is too large (max 5 MB)")
    name = f"{uuid.uuid4().hex}{ext}"
    rel = f"{kind}/{school_id}/{name}"
    dest = _storage_root() / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return rel


def resolve_upload(rel_path: str) -> Path:
    """Resolve a relative storage path to a file, guarding against traversal.

    Hardened against path traversal attacks including encoding tricks.
    """
    # Reject any path with traversal attempts or absolute paths
    if ".." in rel_path or rel_path.startswith("/") or "\\" in rel_path:
        raise ValidationError("Invalid file path")

    # Normalize and decode any URL encoding
    import urllib.parse
    rel_path = urllib.parse.unquote(rel_path)

    # Double-check after decoding
    if ".." in rel_path or rel_path.startswith("/"):
        raise ValidationError("Invalid file path")

    root = _storage_root().resolve()
    target = (root / rel_path).resolve()

    # Verify target is still under root after resolution
    if not str(target).startswith(str(root)):
        raise ValidationError("Invalid file path")

    # Provide detailed debugging info if file not found
    if not target.is_file():
        import os
        # Log for debugging: check if parent directory exists
        parent_exists = target.parent.is_dir()
        raise NotFoundError(f"File not found: {rel_path} (resolved to {target}, parent exists: {parent_exists})")

    return target