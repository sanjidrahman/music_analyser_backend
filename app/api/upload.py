import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..config import settings
from ..schemas.segment import SegmentResponse, SupportedFormatsResponse
from ..schemas.common import SuccessResponse
from ..services.file_service import FileService
from ..services.audio_processor import AudioProcessor
from ..utils.security import get_optional_user
from ..utils.exceptions import ValidationError, ProcessingError
from ..models.user import User

router = APIRouter(prefix="/api", tags=["upload"])


@router.get("/formats/supported", response_model=SupportedFormatsResponse)
async def get_supported_formats():
    """
    Get supported audio formats and upload limits.

    Returns:
        SupportedFormatsResponse: Supported formats and limits
    """
    return SupportedFormatsResponse(
        formats=settings.allowed_audio_formats,
        max_size_mb=settings.max_upload_size_mb,
        min_duration_seconds=settings.min_segment_duration,
        max_duration_seconds=settings.max_segment_duration
    )


@router.post("/upload-and-process", response_model=SegmentResponse)
async def upload_and_process_song(
    file: UploadFile = File(...),
    start_time: float = Form(0.0),
    end_time: Optional[float] = Form(None),
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a song and extract a segment with vocal separation.

    This endpoint can work without authentication for file processing,
    but authenticated users will have the files associated with their account.

    Args:
        file: Audio file to upload
        start_time: Start time for segment extraction (seconds)
        end_time: End time for segment extraction (seconds)
        current_user: Optional authenticated user
        db: Database session

    Returns:
        SegmentResponse: Created segment information
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )

        # Get file extension
        file_extension = os.path.splitext(file.filename)[1].lower().lstrip('.')

        # Save uploaded file temporarily
        temp_dir = os.path.join(settings.storage_path, "temp")
        os.makedirs(temp_dir, exist_ok=True)

        temp_filename, temp_file_path = await FileService.save_uploaded_file(
            file, temp_dir, current_user
        )

        try:
            # Get audio info for validation
            audio_info = AudioProcessor.get_audio_info(temp_file_path)

            # Validate end_time
            if end_time is None:
                end_time = audio_info["duration"]
            else:
                end_time = min(end_time, audio_info["duration"])

            # Generate output filenames
            segment_filename = f"segment_{temp_filename}"
            vocal_filename = f"vocals_{temp_filename}"

            segment_file_path = os.path.join(settings.storage_segments_path, segment_filename)
            vocal_file_path = os.path.join(settings.storage_vocals_path, vocal_filename)

            # Process audio (extract segment and separate vocals)
            processing_results = AudioProcessor.process_song(
                temp_file_path,
                segment_file_path,
                vocal_file_path,
                start_time,
                end_time
            )

            # Create segment record in database
            user_id = current_user.id if current_user else None
            segment = await FileService.create_segment_record(
                db=db,
                user_id=user_id,
                file_path=segment_file_path,
                vocal_file_path=vocal_file_path if processing_results["vocals_separated"] else None,
                duration=processing_results["segment_duration"],
                start_time=start_time,
                end_time=end_time,
                original_filename=file.filename,
                file_format=file_extension,
                sample_rate=processing_results["sample_rate"],
                channels=processing_results["channels"]
            )

            return SegmentResponse(
                id=segment.id,
                user_id=segment.user_id,
                file_path=segment.file_path,
                vocal_file_path=segment.vocal_file_path,
                duration=segment.duration,
                start_time=segment.start_time,
                end_time=segment.end_time,
                original_filename=segment.original_filename,
                file_format=segment.file_format,
                sample_rate=segment.sample_rate,
                channels=segment.channels,
                created_at=segment.created_at,
                expires_at=segment.expires_at
            )

        finally:
            # Clean up temporary file
            try:
                os.remove(temp_file_path)
            except:
                pass

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ProcessingError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Audio processing failed: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )


@router.post("/cleanup-expired", response_model=SuccessResponse)
async def cleanup_expired_files(
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Clean up expired segment files (admin/maintenance endpoint).

    Args:
        current_user: Optional authenticated user
        db: Database session

    Returns:
        SuccessResponse: Cleanup results
    """
    try:
        deleted_count = await FileService.cleanup_expired_files(db)
        return SuccessResponse(
            message=f"Cleaned up {deleted_count} expired segments",
            data={"deleted_count": deleted_count},
            timestamp=datetime.utcnow()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cleanup failed: {str(e)}"
        )