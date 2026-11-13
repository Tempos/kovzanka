from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.models import QueueStatus
from pydantic import BaseModel, Field


class CancelTicketRequest(BaseModel):
    reason: str = Field(..., min_length=3, description="Причина скасування є обов'язковою")


class CreateQueueRequest(BaseModel):
    phone: str
    shoe_sizes: List[str]
    duration_minutes: int = 60
    comment: Optional[str] = None


class ExtendSessionRequest(BaseModel):
    minutes: int = 15  # За замовчуванням +15 хвилин


class InventoryItemCreate(BaseModel):
    size: str
    total_stock: int
    maintenance_count: int = 0


class InventoryUpdatePayload(BaseModel):
    size: str
    total_stock: Optional[int] = None
    maintenance_count: Optional[int] = None


class InventoryItemUpdate(BaseModel):
    total_stock: Optional[int] = None
    maintenance_count: Optional[int] = None


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
        return [str(item) for item in v] if isinstance(v, list) else v

    model_config = ConfigDict(from_attributes=True)


class UpdateTicketRequest(BaseModel):
    duration_minutes: int | None = None
    shoe_sizes: List[str] | None = None
    comment: Optional[str] = None


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
        return [str(item) for item in v] if isinstance(v, list) else v
