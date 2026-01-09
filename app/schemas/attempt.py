from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime


class PitchAnalysis(BaseModel):
    pitch_over_time: List[float]  # Pitch values sampled over time
    time_stamps: List[float]  # Corresponding time stamps
    notes_matched: int
    notes_total: int
    confidence_scores: List[float]  # Confidence for each pitch detection


class AttemptAnalysis(BaseModel):
    pitch_analysis: PitchAnalysis
    rhythm_similarity: float  # 0-100
    tempo_difference_bpm: float
    beat_alignment_score: float  # 0-100
    mfcc_similarity: float  # 0-100, for tone similarity
    duration_difference_ms: float  # Difference in milliseconds


class AttemptCreate(BaseModel):
    segment_id: int
    recording_id: int


class AttemptResponse(BaseModel):
    id: int
    user_id: int
    segment_id: int
    recording_id: int
    overall_score: float
    pitch_accuracy: float
    rhythm_accuracy: float
    tone_similarity: float
    timing_accuracy: float
    detailed_analysis: Optional[Dict[str, Any]]
    duration_warning: Optional[Dict[str, Any]]
    analysis_version: str
    created_at: datetime

    class Config:
        from_attributes = True


class AttemptSummary(BaseModel):
    id: int
    overall_score: float
    pitch_accuracy: float
    rhythm_accuracy: float
    tone_similarity: float
    timing_accuracy: float
    segment_filename: str
    recording_filename: str
    created_at: datetime

    class Config:
        from_attributes = True