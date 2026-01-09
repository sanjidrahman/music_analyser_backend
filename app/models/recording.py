from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Recording(Base):
    __tablename__ = "recordings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    segment_id = Column(Integer, ForeignKey("segments.id"), nullable=True, index=True)
    file_path = Column(String, nullable=False)
    vocal_file_path = Column(String, nullable=True)
    duration = Column(Float, nullable=False)
    original_filename = Column(String, nullable=False)
    file_format = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # "recording" or "audio"
    sample_rate = Column(Integer, nullable=True)
    channels = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", backref="recordings")
    segment = relationship("Segment", back_populates="recordings")
    attempts = relationship("Attempt", back_populates="recording")