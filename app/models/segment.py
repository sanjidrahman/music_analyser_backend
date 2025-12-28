from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Segment(Base):
    __tablename__ = "segments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    file_path = Column(String, nullable=False)
    vocal_file_path = Column(String, nullable=True)
    duration = Column(Float, nullable=False)
    start_time = Column(Float, default=0.0)
    end_time = Column(Float, nullable=False)
    original_filename = Column(String, nullable=False)
    file_format = Column(String, nullable=False)
    sample_rate = Column(Integer, nullable=True)
    channels = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)  # For file cleanup

    # Relationships
    user = relationship("User", backref="segments")
    attempts = relationship("Attempt", back_populates="segment")
    recordings = relationship("Recording", back_populates="segment")