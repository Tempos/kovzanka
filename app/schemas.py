from datetime import datetime
from typing import List, Optional, Any

from pydantic import BaseModel, ConfigDict, field_validator

from app.models import QueueStatus


class CreateQueueRequest(BaseModel):
    phone: str
    shoe_sizes: List[str]
    duration_minutes: int = 60
    comment: Optional[str] = None


class ExtendSessionRequest(BaseModel):
    minutes: int = 15  # За замовчуванням +15 хвилин


class LoginRequest(BaseModel):
    pin: str


class QueueItemResponse(BaseModel):
    id: int
    ticket_number: int
    tracking_token: str
    phone: str
    people_count: int
    shoe_sizes: List[str]
    comment: Optional[str] = None
    status: QueueStatus
    duration_minutes: int
    session_start: Optional[datetime]
    session_end: Optional[datetime]

    @field_validator("shoe_sizes", mode="before")
    @classmethod
    def coerce_shoe_sizes(cls, v: Any) -> List[str]:
        if isinstance(v, list):
            return [str(item) for item in v]
        return v

    model_config = ConfigDict(from_attributes=True)


class UserStatusResponse(BaseModel):
    ticket_number: int
    status: QueueStatus
    people_count: int
    shoe_sizes: List[str]
    position_in_queue: int
    estimated_wait_minutes: int

    @field_validator("shoe_sizes", mode="before")
    @classmethod
    def coerce_shoe_sizes(cls, v: Any) -> List[str]:
        if isinstance(v, list):
            return [str(item) for item in v]
        return v
