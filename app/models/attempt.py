from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, Text, JSON, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    segment_id = Column(Integer, ForeignKey("segments.id"), nullable=False, index=True)
    recording_id = Column(Integer, ForeignKey("recordings.id"), nullable=False, index=True)

    # Overall scores (0-100)
    overall_score = Column(Float, nullable=False)

    # Detailed scores (0-100)
    pitch_accuracy = Column(Float, nullable=False)
    rhythm_accuracy = Column(Float, nullable=False)
    tone_similarity = Column(Float, nullable=False)
    timing_accuracy = Column(Float, nullable=False)

    # Detailed analysis data (JSON)
    detailed_analysis = Column(JSON, nullable=True)

    # Duration warning (JSONB)
    duration_warning = Column(JSON, nullable=True)

    # Metadata
    analysis_version = Column(String, default="1.0")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", backref="attempts")
    segment = relationship("Segment", back_populates="attempts")
    recording = relationship("Recording", back_populates="attempts")