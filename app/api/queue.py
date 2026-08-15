from typing import List
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.db import DBSession
from app.models import QueueItem, QueueStatus
from app.schemas import CreateQueueRequest, UserStatusResponse, QueueItemResponse
from app.ws_manager import manager

router = APIRouter(prefix="/api", tags=["Queue API"])


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
    # Повертаємо тільки ті талони, які ще в процесі
    return (
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
        comment=req.comment,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    await manager.broadcast("QUEUE_UPDATED")
    return item


@router.patch("/queue/{item_id}/status", response_model=QueueItemResponse)
async def update_status(item_id: int, status: QueueStatus, db: DBSession):
    item = db.query(QueueItem).filter(QueueItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Запис не знайдено")

    item.status = status
    db.commit()

    await manager.broadcast("QUEUE_UPDATED")
    return item


@router.get("/public/status/{tracking_token}", response_model=UserStatusResponse)
def get_user_status(tracking_token: str, db: DBSession):
    item = (
        db.query(QueueItem)
        .filter(QueueItem.tracking_token == tracking_token)
        .first()
    )

    if not item:
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
    item = (
        db.query(QueueItem)
        .filter(QueueItem.ticket_number == ticket)
        .first()
    )

    if not item:
        raise HTTPException(status_code=404, detail="Запис не знайдено")

    position = 0
    if item.status == QueueStatus.WAITING:
        position = (
            db.query(QueueItem)
            .filter(
                QueueItem.status == QueueStatus.WAITING,
                QueueItem.id < item.id
            )
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