from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.models import QueueStatus


class CreateQueueRequest(BaseModel):
    phone: str
    shoe_sizes: List[int]
    duration_minutes: int = 60
    comment: Optional[str] = None


class ExtendSessionRequest(BaseModel):
    minutes: int = 15  # За замовчуванням +15 хвилин


class UserStatusResponse(BaseModel):
    ticket_number: int
    status: QueueStatus
    people_count: int
    shoe_sizes: List[int]
    position_in_queue: int
    estimated_wait_minutes: int


class QueueItemResponse(BaseModel):
    id: int
    ticket_number: int
    tracking_token: str
    phone: str
    people_count: int
    shoe_sizes: List[int]
    comment: Optional[str] = None
    status: QueueStatus
    duration_minutes: int
    session_start: Optional[datetime]
    session_end: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)
