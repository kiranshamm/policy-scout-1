import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Enum as SAEnum, Text
from sqlalchemy.orm import relationship
from database import Base


class ScanStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class PolicyStatus(str, enum.Enum):
    found = "found"
    missing = "missing"


class Scan(Base):
    __tablename__ = "scans"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    url = Column(String, nullable=False)
    domain = Column(String, nullable=True)
    status = Column(SAEnum(ScanStatus), default=ScanStatus.queued)
    score = Column(Float, default=0.0)
    total_links_found = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    pages = relationship("PolicyPage", back_populates="scan", cascade="all, delete-orphan")


class PolicyPage(Base):
    __tablename__ = "policy_pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_id = Column(String, ForeignKey("scans.id"), nullable=False)
    category = Column(String, nullable=False)
    url = Column(String, nullable=True)
    title = Column(String, nullable=True)
    status = Column(SAEnum(PolicyStatus), default=PolicyStatus.missing)
    confidence = Column(Float, default=0.0)
    screenshot_path = Column(String, nullable=True)

    scan = relationship("Scan", back_populates="pages")
