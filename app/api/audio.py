import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from ..config import settings

router = APIRouter(prefix="/api/audio", tags=["audio"])


@router.get("/{file_path:path}")
async def get_audio_file(file_path: str):
    """
    Serve audio files from the storage directory.

    This endpoint serves audio files from various storage locations:
    - ./storage/segments/ - Original segment files
    - ./storage/vocals/ - Vocal-separated files
    - ./storage/recordings/ - User recording files

    Args:
        file_path: Path to the audio file relative to storage root

    Returns:
        FileResponse: Audio file with appropriate content type
    """
    try:
        # Decode the file path (handles URL encoding)
        decoded_path = file_path.replace('%2F', '/').replace('%20', ' ')

        # Security check: Ensure the path doesn't try to escape storage directory
        if '..' in decoded_path or decoded_path.startswith('/'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid file path"
            )

        # Construct the full file path
        storage_root = Path(settings.storage_path).resolve()
        full_file_path = storage_root / decoded_path

        # Security check: Ensure the resolved path is still within storage
        try:
            full_file_path.resolve().relative_to(storage_root)
        except (ValueError, RuntimeError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Path outside storage directory"
            )

        # Check if file exists
        if not full_file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audio file not found: {file_path}"
            )

        # Check if it's actually a file
        if not full_file_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Path is not a file: {file_path}"
            )

        # Determine media type based on file extension
        file_extension = full_file_path.suffix.lower()
        media_type = {
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.m4a': 'audio/mp4',
            '.flac': 'audio/flac',
            '.ogg': 'audio/ogg',
            '.webm': 'audio/webm'
        }.get(file_extension, 'application/octet-stream')

        # Serve the file with proper headers for audio streaming
        return FileResponse(
            path=str(full_file_path),
            media_type=media_type,
            filename=full_file_path.name,
            headers={
                'Accept-Ranges': 'bytes',
                'Cache-Control': 'public, max-age=3600',  # Cache for 1 hour
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error serving audio file: {str(e)}"
        )