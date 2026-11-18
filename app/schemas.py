from datetime import datetime
from typing import Any, List, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from app.models import QueueStatus


class CreateQueueRequest(BaseModel):
    phone: str
    shoe_sizes: List[str]
    duration_minutes: int = 60
    comment: Optional[str] = None


class CancelTicketRequest(BaseModel):
    reason: str = Field(..., min_length=3, description="Причина скасування є обов'язковою")


class ExtendSessionRequest(BaseModel):
    minutes: int = 15


class InventoryItemCreate(BaseModel):
    size: str = Field(..., max_length=64)
    category: str = Field("figure", max_length=32)
    total_stock: int = Field(..., ge=0)
    maintenance_count: int = Field(0, ge=0)
    expand_range: bool = Field(False, validation_alias=AliasChoices("expand_range", "expandRange"))


class InventoryItemUpdate(BaseModel):
    total_stock: Optional[int] = None
    maintenance_count: Optional[int] = None


class InventoryUpdatePayload(BaseModel):
    size: str
    total_stock: Optional[int] = None
    maintenance_count: Optional[int] = None


class LoginRequest(BaseModel):
    pin: str


class MassExtendRequest(BaseModel):
    admin_password: Optional[str] = None
    password: Optional[str] = None  # Підтримуємо обидва варіанти на випадок різного фронтенду
    minutes: int = 10

    @property
    def effective_password(self) -> str:
        return self.admin_password or self.password or ""


class QueueItemResponse(BaseModel):
    id: int
    ticket_number: int
    tracking_token: str
    phone: str
    people_count: int
    shoe_sizes: List[str]
    comment: Optional[str] = None
    status: QueueStatus

    called_at: Optional[datetime] = None
    duration_minutes: int
    overtime_stopped_at: Optional[datetime] = None
    session_start: Optional[datetime]
    session_end: Optional[datetime]

    @field_validator("shoe_sizes", mode="before")
    @classmethod
    def coerce_shoe_sizes(cls, v: Any) -> List[str]:
        return [str(item) for item in v] if isinstance(v, list) else v

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
        return [str(item) for item in v] if isinstance(v, list) else v


class UpdateTicketRequest(BaseModel):
    duration_minutes: int | None = None
    shoe_sizes: List[str] | None = None
    comment: Optional[str] = None
