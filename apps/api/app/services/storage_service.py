"""Image storage via Base64 in database for Render free-tier compatibility.

Previously used local filesystem, but Render free tier has ephemeral storage.
Now images are converted to Base64 and stored directly in the database.

For school logos:
- Convert image bytes to Base64 string
- Prepend MIME type: "data:image/png;base64,..."
- Store in school.logo_url as a data URL
- Frontend displays directly: <img src={school.logo_url} />

For student photos:
- Still stored as file paths (can be migrated later if needed)
"""
import base64
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


def save_image_as_base64(data: bytes, content_type: str) -> str:
    """Convert image to Base64 data URL for database storage.

    Returns a data URL like: data:image/png;base64,iVBORw0KG...
    """
    ext = ALLOWED_IMAGE_TYPES.get((content_type or "").lower())
    if ext is None:
        raise ValidationError("Only JPEG, PNG and WebP images are allowed")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValidationError("Image is too large (max 5 MB)")

    # Convert to Base64
    b64 = base64.b64encode(data).decode('ascii')
    # Return as data URL
    return f"data:{content_type};base64,{b64}"


def _storage_root() -> Path:
    root = Path(settings.storage_base_dir)
    try:
        root.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        # If we can't create the directory, log it but continue
        # This allows the app to start even if storage is misconfigured
        import sys
        print(f"WARNING: Could not create storage directory {root}: {e}", file=sys.stderr)
    return root


def save_image_upload(data: bytes, content_type: str, school_id: str, kind: str = "students") -> str:
    """Persist an image upload and return the relative storage path.

    Note: This is legacy filesystem storage. For new uploads (especially logos),
    use save_image_as_base64() instead which stores in the database.
    """
    ext = ALLOWED_IMAGE_TYPES.get((content_type or "").lower())
    if ext is None:
        raise ValidationError("Only JPEG, PNG and WebP images are allowed")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValidationError("Image is too large (max 5 MB)")
    name = f"{uuid.uuid4().hex}{ext}"
    rel = f"{kind}/{school_id}/{name}"
    dest = _storage_root() / rel
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Write file and verify it was actually written
    dest.write_bytes(data)
    if not dest.is_file() or dest.stat().st_size != len(data):
        raise ValidationError(f"Failed to persist file: {rel}")

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