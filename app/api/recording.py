import os
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database import get_db
from ..config import settings
from ..schemas.recording import RecordingResponse
from ..schemas.common import SuccessResponse
from ..services.file_service import FileService
from ..services.audio_processor import AudioProcessor
from ..utils.security import get_optional_user
from ..utils.exceptions import ValidationError, ProcessingError
from ..models.user import User
from ..models.segment import Segment
from ..models.recording import Recording

router = APIRouter(prefix="/api/recording", tags=["recording"])


@router.post("/upload", response_model=RecordingResponse)
async def upload_recording(
    file: UploadFile = File(...),
    segment_id: int = Form(...),
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a user recording for analysis.

    This endpoint can work without authentication for file upload,
    but authenticated users will have the recordings associated with their account.

    A segment_id is required to associate the recording with the original segment for analysis.

    Args:
        file: User recording audio file
        segment_id: Required associated segment ID for analysis
        current_user: Optional authenticated user
        db: Database session

    Returns:
        RecordingResponse: Created recording information
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )

        # Validate segment_id
        result = await db.execute(select(Segment).where(Segment.id == segment_id))
        segment = result.scalar_one_or_none()
        if not segment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Segment with ID {segment_id} not found"
            )

        # Get file extension
        file_extension = os.path.splitext(file.filename)[1].lower().lstrip('.')

        # Save uploaded file
        recording_filename, recording_file_path = await FileService.save_uploaded_file(
            file, settings.storage_recordings_path, current_user
        )

        # Get audio info
        audio_info = AudioProcessor.get_audio_info(recording_file_path)

        # Create recording record in database
        user_id = current_user.id if current_user else None
        recording = await FileService.create_recording_record(
            db=db,
            user_id=user_id,
            segment_id=segment_id,
            file_path=recording_file_path,
            vocal_file_path=None,
            duration=audio_info["duration"],
            original_filename=file.filename,
            file_format=file_extension,
            sample_rate=audio_info["sample_rate"],
            channels=audio_info["channels"]
        )

        return RecordingResponse(
            id=recording.id,
            user_id=recording.user_id,
            segment_id=recording.segment_id,
            file_path=recording.file_path,
            vocal_file_path=recording.vocal_file_path,
            duration=recording.duration,
            original_filename=recording.original_filename,
            file_format=recording.file_format,
            sample_rate=recording.sample_rate,
            channels=recording.channels,
            created_at=recording.created_at
        )

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
            detail=f"Recording upload failed: {str(e)}"
        )


@router.get("/", response_model=list[RecordingResponse])
async def get_recordings(
    segment_id: Optional[int] = None,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user recordings.

    Args:
        segment_id: Optional filter by segment ID
        current_user: Optional authenticated user
        db: Database session

    Returns:
        list[RecordingResponse]: List of recordings
    """
    try:
        # Build query
        query = select(Recording)

        # Filter by user if authenticated
        if current_user:
            query = query.where(Recording.user_id == current_user.id)

        # Filter by segment_id if provided
        if segment_id:
            query = query.where(Recording.segment_id == segment_id)

        # Execute query
        result = await db.execute(query.order_by(Recording.created_at.desc()))
        recordings = result.scalars().all()

        return [
            RecordingResponse(
                id=recording.id,
                user_id=recording.user_id,
                segment_id=recording.segment_id,
                file_path=recording.file_path,
                vocal_file_path=recording.vocal_file_path,
                duration=recording.duration,
                original_filename=recording.original_filename,
                file_format=recording.file_format,
                sample_rate=recording.sample_rate,
                channels=recording.channels,
                created_at=recording.created_at
            )
            for recording in recordings
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get recordings: {str(e)}"
        )


@router.get("/{recording_id}", response_model=RecordingResponse)
async def get_recording(
    recording_id: int,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get specific recording information.

    Args:
        recording_id: Recording ID
        current_user: Optional authenticated user
        db: Database session

    Returns:
        RecordingResponse: Recording information
    """
    try:
        result = await db.execute(select(Recording).where(Recording.id == recording_id))
        recording = result.scalar_one_or_none()

        if not recording:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recording not found"
            )

        # Check ownership if authenticated
        if current_user and recording.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this recording"
            )

        return RecordingResponse(
            id=recording.id,
            user_id=recording.user_id,
            segment_id=recording.segment_id,
            file_path=recording.file_path,
            vocal_file_path=recording.vocal_file_path,
            duration=recording.duration,
            original_filename=recording.original_filename,
            file_format=recording.file_format,
            sample_rate=recording.sample_rate,
            channels=recording.channels,
            created_at=recording.created_at
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get recording: {str(e)}"
        )