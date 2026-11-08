import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, DateTime, Enum, Integer, String, Column
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase


class Base(DeclarativeBase):
    pass


class SkateInventory(Base):
    __tablename__ = "skate_inventory"

    id = Column(Integer, primary_key=True, index=True)
    size = Column(String, unique=True, index=True, nullable=False)  # e.g., "26", "38_hok"
    total_stock = Column(Integer, default=0, nullable=False)
    maintenance_count = Column(Integer, default=0, nullable=False)


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
        Enum(QueueStatus), default=QueueStatus.WAITING, index=True
    )

    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    session_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    session_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc))
