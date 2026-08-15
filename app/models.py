import enum
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import JSON, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase


class Base(DeclarativeBase):
    pass


class QueueStatus(str, enum.Enum):
    WAITING = "ЧЕКАЄ"
    CALLING = "ВИКЛИКАЄТЬСЯ"
    SERVED = "ОБСЛУГОВУЄТЬСЯ"
    RETURNED = "ПОВЕРНЕНО"
    CANCELLED = "СКАСОВАНО"


class QueueItem(Base):
    __tablename__ = "queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticket_number: Mapped[int] = mapped_column(Integer, index=True)
    tracking_token: Mapped[str] = mapped_column(
        String, unique=True, default=lambda: str(uuid.uuid4())[:8]
    )
    phone: Mapped[str] = mapped_column(String)
    people_count: Mapped[int] = mapped_column(Integer)
    shoe_sizes: Mapped[list] = mapped_column(JSON)
    comment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[QueueStatus] = mapped_column(
        Enum(QueueStatus), default=QueueStatus.WAITING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
