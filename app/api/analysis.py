import os
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from ..database import get_db
from ..config import settings
from ..schemas.attempt import AttemptResponse, AttemptCreate
from ..schemas.common import SuccessResponse
from ..services.audio_processor import AudioProcessor
from ..services.analyzer import AudioAnalyzer
from ..services.file_service import FileService
from ..utils.security import get_current_user
from ..utils.exceptions import ProcessingError, ValidationError
from ..models.user import User
from ..models.segment import Segment
from ..models.recording import Recording
from ..models.attempt import Attempt

router = APIRouter(prefix="/api", tags=["analysis"])


class AnalyzeRequest(BaseModel):
    segment_id: int
    recording_id: int


@router.post("/analyze", response_model=AttemptResponse)
async def analyze_recording(
    request: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Analyze user recording against original segment.

    Requires authentication. Compares user recording with original segment
    and provides detailed scoring based on pitch, rhythm, tone, and timing.

    Args:
        request: Analysis request with segment_id and recording_id
        current_user: Authenticated user
        db: Database session

    Returns:
        AttemptResponse: Analysis results and scores
    """
    try:
        # Get segment
        segment = await db.get(Segment, request.segment_id)
        if not segment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Segment not found"
            )

        # Get recording
        recording = await db.get(Recording, request.recording_id)
        if not recording:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recording not found"
            )

        # Check if user owns the recording or if it's anonymous
        if recording.user_id and recording.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to analyze this recording"
            )

        # Check if files exist
        if not AudioProcessor.get_audio_info(segment.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Segment file not found"
            )

        if not AudioProcessor.get_audio_info(recording.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recording file not found"
            )

        # Separate vocals from user recording if not already done
        user_vocals_file = None
        if not recording.vocal_file_path:
            # Generate vocal file path for user recording
            recording_filename = os.path.basename(recording.file_path)
            vocal_filename = f"vocals_user_recording_{recording.id}_{recording_filename}"
            user_vocals_file = os.path.join(settings.storage_vocals_path, vocal_filename)

            # Separate vocals using existing function
            os.makedirs(settings.storage_vocals_path, exist_ok=True)
            vocals_success = AudioProcessor.separate_vocals(recording.file_path, user_vocals_file)

            if vocals_success:
                # Update recording with vocal file path
                recording.vocal_file_path = user_vocals_file
                await db.commit()
        else:
            # Use existing vocal file
            user_vocals_file = recording.vocal_file_path

        # Use vocal file if available, otherwise use original segment
        reference_file = segment.vocal_file_path if segment.vocal_file_path else segment.file_path
        user_file = user_vocals_file if user_vocals_file else recording.file_path

        # Perform analysis
        try:
            analysis_results = AudioAnalyzer.analyze_singing_similarity(
                reference_file,
                recording.file_path
            )
        except ProcessingError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Analysis failed: {str(e)}"
            )

        # Create attempt record
        attempt = Attempt(
            user_id=current_user.id,
            segment_id=segment.id,
            recording_id=recording.id,
            overall_score=analysis_results["overall_score"],
            pitch_accuracy=analysis_results["pitch_accuracy"],
            rhythm_accuracy=analysis_results["rhythm_accuracy"],
            tone_similarity=analysis_results["tone_similarity"],
            timing_accuracy=analysis_results["timing_accuracy"],
            detailed_analysis=analysis_results["detailed_analysis"]
        )

        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)

        return AttemptResponse(
            id=attempt.id,
            user_id=attempt.user_id,
            segment_id=attempt.segment_id,
            recording_id=attempt.recording_id,
            overall_score=attempt.overall_score,
            pitch_accuracy=attempt.pitch_accuracy,
            rhythm_accuracy=attempt.rhythm_accuracy,
            tone_similarity=attempt.tone_similarity,
            timing_accuracy=attempt.timing_accuracy,
            detailed_analysis=attempt.detailed_analysis,
            analysis_version=attempt.analysis_version,
            created_at=attempt.created_at
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )


@router.get("/analysis-summary/{attempt_id}")
async def get_analysis_summary(
    attempt_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed analysis summary for an attempt.

    Args:
        attempt_id: Attempt ID
        current_user: Authenticated user
        db: Database session

    Returns:
        dict: Detailed analysis summary
    """
    try:
        attempt = await db.get(Attempt, attempt_id)
        if not attempt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attempt not found"
            )

        # Check ownership
        if attempt.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this attempt"
            )

        # Return detailed analysis
        return {
            "attempt_id": attempt.id,
            "overall_score": attempt.overall_score,
            "scores": {
                "pitch_accuracy": attempt.pitch_accuracy,
                "rhythm_accuracy": attempt.rhythm_accuracy,
                "tone_similarity": attempt.tone_similarity,
                "timing_accuracy": attempt.timing_accuracy
            },
            "detailed_analysis": attempt.detailed_analysis,
            "created_at": attempt.created_at
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get analysis summary: {str(e)}"
        )