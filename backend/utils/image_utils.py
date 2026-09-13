"""
utils/image_utils.py — File-handling helpers for uploaded images.

Provides utilities for persisting in-memory uploads or bytes to disk
(so the pipeline can work with filesystem paths), validating that a file
is a genuine image, and cleaning up temporary files after each analysis run.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, UnidentifiedImageError

import config

from typing import Any

logger = logging.getLogger(__name__)


def save_temp_upload(file_or_bytes: Any, filename: str | None = None) -> str:
    """
    Write an uploaded file (FastAPI UploadFile, file-like, or raw bytes) to disk
    with a unique filename inside config.TEMP_DIR.

    Args:
        file_or_bytes: An UploadFile, file-like object with .read()/.getbuffer(), or raw bytes.
        filename: Optional filename hint to preserve file extension.

    Returns:
        Absolute path (as a string) to the saved temporary file.
    """
    detected_name = filename or getattr(file_or_bytes, "filename", None) or getattr(file_or_bytes, "name", None) or "upload.jpg"
    suffix: str = Path(detected_name).suffix or ".jpg"
    temp_path: Path = config.TEMP_DIR / f"{uuid.uuid4().hex}{suffix}"

    if isinstance(file_or_bytes, (bytes, bytearray)):
        content = bytes(file_or_bytes)
    elif hasattr(file_or_bytes, "file") and hasattr(file_or_bytes.file, "read"):
        content = file_or_bytes.file.read()
    elif hasattr(file_or_bytes, "read"):
        content = file_or_bytes.read()
    elif hasattr(file_or_bytes, "getbuffer"):
        content = bytes(file_or_bytes.getbuffer())
    else:
        raise ValueError("Unsupported upload file type")

    with open(temp_path, "wb") as f:
        f.write(content)
    return str(temp_path)


def validate_image_file(path: str | Path) -> bool:
    """
    Check whether the file at *path* is a valid, openable image.

    Uses PIL's ``Image.verify()`` to detect corrupt or non-image files
    without fully decoding pixel data.

    Args:
        path: Filesystem path to the file to validate.

    Returns:
        ``True`` if the file is a valid image, ``False`` otherwise.
    """
    try:
        with Image.open(path) as img:
            img.verify()
        return True
    except (UnidentifiedImageError, OSError):
        return False


def cleanup_all_temp() -> None:
    """
    Delete every file in :data:`config.TEMP_DIR`.

    Called after each analysis run completes. ID photos and selfies are
    sensitive personal data — they should not remain on disk longer than
    the analysis takes.

    Any per-file deletion failures are logged and silently skipped so that
    one locked file does not prevent the rest from being cleaned up.
    """
    deleted = 0
    for f in config.TEMP_DIR.glob("*"):
        try:
            f.unlink()
            deleted += 1
        except OSError:
            logger.warning("Failed to delete temp file: %s", f, exc_info=True)

    logger.debug("Cleaned up %d temp file(s)", deleted)
