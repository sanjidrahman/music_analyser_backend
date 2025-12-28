import os
import uuid
from fastapi import UploadFile, status

from ..config import settings
from .exceptions import create_http_exception


def validate_audio_file(file: UploadFile) -> None:
    """Validate uploaded audio file."""
    if file.size and file.size > settings.max_upload_size_bytes:
        raise create_http_exception(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {settings.max_upload_size_mb}MB"
        )

    if not file.filename:
        raise create_http_exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided"
        )

    file_extension = os.path.splitext(file.filename)[1].lower().lstrip('.')
    if file_extension not in settings.allowed_audio_formats:
        raise create_http_exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File format '{file_extension}' not supported. Allowed formats: {', '.join(settings.allowed_audio_formats)}"
        )

    allowed_mime_types = {
        'wav': 'audio/wav',
        'mp3': 'audio/mpeg',
        'm4a': 'audio/mp4',
        'flac': 'audio/flac',
        'ogg': 'audio/ogg',
        'webm': 'audio/webm'
    }

    if file.content_type and file.content_type not in allowed_mime_types.values():
        raise create_http_exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Content type '{file.content_type}' not supported"
        )


def generate_unique_filename(original_filename: str) -> str:
    """Generate unique filename to avoid conflicts."""
    file_extension = os.path.splitext(original_filename)[1]
    unique_id = str(uuid.uuid4())
    return f"{unique_id}{file_extension}"