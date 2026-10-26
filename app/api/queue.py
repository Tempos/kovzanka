from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.api.auth import verify_worker
from app.db import DBSession, get_db
from app.inventory import calculate_live_inventory
from app.models import QueueItem, QueueStatus
from app.schemas import CreateQueueRequest, UserStatusResponse, QueueItemResponse, ExtendSessionRequest
from app.ws_manager import manager

router = APIRouter(prefix="/api", tags=["API Endpoints"])


@router.get("/inventory", dependencies=[Depends(verify_worker)])
def get_inventory_status(db: Session = Depends(get_db)):
    """Exposes current counts to cashiers for inventory tracking."""
    active_skaters = db.query(QueueItem).filter(
        QueueItem.status.in_([
            QueueStatus.WAITING,
            QueueStatus.CALLING,
            QueueStatus.SERVED
        ])
    ).all()
    return calculate_live_inventory(active_skaters)


@router.websocket("/ws/queue")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.get("/queue", response_model=List[QueueItemResponse])
def get_full_queue(db: DBSession):
    return (  # Повертаємо тільки ті талони, які ще в процесі
        db.query(QueueItem)
        .filter(QueueItem.status.in_([
            QueueStatus.WAITING,
            QueueStatus.CALLING,
            QueueStatus.SERVED
        ]))
        .order_by(QueueItem.created_at.asc())
        .all()
    )


@router.post("/queue", response_model=QueueItemResponse)
async def create_queue_entry(req: CreateQueueRequest, db: DBSession):
    last_ticket = db.query(QueueItem).order_by(QueueItem.id.desc()).first()
    next_number = (last_ticket.ticket_number + 1) if last_ticket else 101

    item = QueueItem(
        ticket_number=next_number,
        phone=req.phone,
        people_count=len(req.shoe_sizes),
        shoe_sizes=req.shoe_sizes,
        duration_minutes=req.duration_minutes,
        comment=req.comment,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    await manager.broadcast("QUEUE_UPDATED")
    return item


@router.patch("/queue/{item_id}/status", response_model=QueueItemResponse)
async def update_status(item_id: int, status: QueueStatus, db: DBSession):
    if not (item := db.get(QueueItem, item_id)):
        raise HTTPException(status_code=404, detail="Запис не знайдено")

    item.status = status

    if status == QueueStatus.SERVED and not item.session_start:
        now = datetime.now(timezone.utc)
        item.session_start = now
        item.session_end = now + timedelta(minutes=item.duration_minutes)

    db.commit()
    db.refresh(item)
    await manager.broadcast("QUEUE_UPDATED")
    return item


@router.patch("/queue/{item_id}/extend", response_model=QueueItemResponse, dependencies=[Depends(verify_worker)])
async def extend_session(item_id: int, payload: ExtendSessionRequest, db: Session = Depends(get_db)):
    if not (item := db.query(QueueItem).filter(QueueItem.id == item_id).first()):
        raise HTTPException(status_code=404, detail="Запис не знайдено")

    if item.status not in [QueueStatus.SERVED, "SERVED", "ОБСЛУГОВУЄТЬСЯ"]:
        raise HTTPException(status_code=400, detail="Можна продовжувати лише активні сесії")

    item.duration_minutes += payload.minutes
    if item.session_end:
        item.session_end += timedelta(minutes=payload.minutes)

    db.commit()
    db.refresh(item)

    await manager.broadcast("QUEUE_UPDATED")
    return item


@router.get("/public/status/{tracking_token}", response_model=UserStatusResponse)
def get_user_status(tracking_token: str, db: DBSession):
    if not (item := db.query(QueueItem).filter(QueueItem.tracking_token == tracking_token).first()):
        raise HTTPException(status_code=404, detail="Запис не знайдено")

    position = (
        db.query(QueueItem)
        .filter(QueueItem.status == QueueStatus.WAITING, QueueItem.id < item.id)
        .count()
    )

    return UserStatusResponse(
        ticket_number=item.ticket_number,
        status=item.status,
        people_count=item.people_count,
        shoe_sizes=item.shoe_sizes,
        position_in_queue=position,
        estimated_wait_minutes=position * 5,
    )


@router.get("/public/status/ticket/{ticket}", response_model=UserStatusResponse)
def get_user_status_by_ticket(ticket: int, db: DBSession):
    if not (item:= (db.query(QueueItem).filter(QueueItem.ticket_number == ticket).first())):
        raise HTTPException(status_code=404, detail="Запис не знайдено")

    position = 0
    if item.status == QueueStatus.WAITING:
        position = (
            db.query(QueueItem)
            .filter(QueueItem.status == QueueStatus.WAITING, QueueItem.id < item.id)
            .count()
        )

    return UserStatusResponse(
        ticket_number=item.ticket_number,
        status=item.status,
        people_count=item.people_count,
        shoe_sizes=item.shoe_sizes,
        position_in_queue=position,
        estimated_wait_minutes=position * 5,
    )
