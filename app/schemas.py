from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.models import QueueStatus


class CreateQueueRequest(BaseModel):
    phone: str
    shoe_sizes: List[int]
    comment: Optional[str] = None


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
    comment: Optional[str]
    status: QueueStatus

    model_config = ConfigDict(from_attributes=True)