from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from datetime import datetime


class ScanRequest(BaseModel):
    url: str


class PolicyPageOut(BaseModel):
    category: str
    status: str
    url: Optional[str] = None
    title: Optional[str] = None
    confidence: float = 0.0

    class Config:
        from_attributes = True


class ScanOut(BaseModel):
    scan_id: str
    url: str
    domain: Optional[str] = None
    status: str
    score: float = 0.0
    total_links_found: int = 0
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    results: List[PolicyPageOut] = []

    class Config:
        from_attributes = True


class ScanCreateResponse(BaseModel):
    scan_id: str
    status: str
    message: str
