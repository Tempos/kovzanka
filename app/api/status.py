from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from app.db import DBSession
from app.inventory import calculate_live_inventory
from app.models import QueueItem, QueueStatus, SkateInventory
from app.schemas import UserStatusResponse

router = APIRouter(prefix="/api", tags=["API Endpoints"])


@router.get("/public/status/{tracking_token}", response_model=UserStatusResponse)
def get_user_status(tracking_token: str, db: DBSession):
    if not (item := db.query(QueueItem).filter(QueueItem.tracking_token == tracking_token).first()):
        raise HTTPException(status_code=404, detail="Запис не знайдено")

    position = (
        db.query(QueueItem)
        .filter(QueueItem.status == QueueStatus.WAITING, QueueItem.id < item.id)
        .count()
    )

    estimated_wait = _calculate_ticket_wait_time(item, db, position)

    return UserStatusResponse(
        ticket_number=item.ticket_number,
        status=item.status,
        people_count=item.people_count,
        shoe_sizes=item.shoe_sizes,
        position_in_queue=position,
        estimated_wait_minutes=estimated_wait,
    )


@router.get("/public/status/ticket/{ticket}", response_model=UserStatusResponse)
def get_user_status_by_ticket(ticket: int, db: DBSession):
    if not (item := (db.query(QueueItem).filter(QueueItem.ticket_number == ticket).first())):
        raise HTTPException(status_code=404, detail="Запис не знайдено")

    position = 0
    if item.status == QueueStatus.WAITING:
        position = (
            db.query(QueueItem)
            .filter(QueueItem.status == QueueStatus.WAITING, QueueItem.id < item.id)
            .count()
        )

    estimated_wait = _calculate_ticket_wait_time(item, db, position)

    return UserStatusResponse(
        ticket_number=item.ticket_number,
        status=item.status,
        people_count=item.people_count,
        shoe_sizes=item.shoe_sizes,
        position_in_queue=position,
        estimated_wait_minutes=estimated_wait,
    )


def _calculate_ticket_wait_time(item: QueueItem, db: Session, position: int) -> int:
    """Calculates wait time considering both queue position and inventory session end times."""
    active_skaters = db.query(QueueItem).filter(QueueItem.status.in_([
        QueueStatus.WAITING,
        QueueStatus.CALLING,
        QueueStatus.SERVED
    ])).all()
    db_inventory = db.query(SkateInventory).all()
    live_inventory = calculate_live_inventory(active_skaters, db_inventory)

    max_wait = position * 5
    for raw_size in (item.shoe_sizes or []):
        size_key = str(raw_size)
        if size_key not in live_inventory:
            candidate = f"{size_key} (фігурні)"
            if candidate in live_inventory:
                size_key = candidate

        if size_key in live_inventory:
            mins = live_inventory[size_key].get("next_available_in_mins")
            if mins is not None and mins > max_wait:
                max_wait = mins
    return max_wait
