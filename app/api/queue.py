import re
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.auth import KASA2_PIN, verify_kasa1, verify_kasa2
from app.bot import send_telegram_notification
from app.db import DBSession, get_db
from app.inventory import revert_unfulfillable_calling_tickets
from app.models import QueueItem, QueueStatus
from app.schemas import CancelTicketRequest, CreateQueueRequest, ExtendSessionRequest, MassExtendRequest, \
    QueueItemResponse, UpdateTicketRequest
from app.ws_manager import manager

router = APIRouter(prefix="/api", tags=["API Endpoints"])


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
    active_items = (
        db.query(QueueItem)
        .filter(QueueItem.status.in_([
            QueueStatus.WAITING,
            QueueStatus.CALLING,
            QueueStatus.SERVED
        ]))
        .order_by(QueueItem.created_at.asc())
        .all()
    )

    recent_closed = (
        db.query(QueueItem)
        .filter(QueueItem.status.in_([QueueStatus.RETURNED, QueueStatus.CANCELLED]))
        .order_by(QueueItem.id.desc())
        .limit(10)
        .all()
    )

    return active_items + recent_closed


@router.patch("/queue/{item_id}", response_model=QueueItemResponse, dependencies=[Depends(verify_kasa2)])
async def update_ticket_details(item_id: int, payload: UpdateTicketRequest, db: Session = Depends(get_db)):
    if not (item := db.query(QueueItem).filter(QueueItem.id == item_id).first()):
        raise HTTPException(status_code=404, detail="Запис не знайдено")

    allowed_statuses = [QueueStatus.WAITING, QueueStatus.CALLING, QueueStatus.SERVED, "ЧЕКАЄ", "ВИКЛИКАЄТЬСЯ",
                        "ОБСЛУГОВУЄТЬСЯ"]
    if item.status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="Неможливо редагувати квиток у поточному статусі")

    if payload.duration_minutes is not None:
        old_duration = item.duration_minutes
        item.duration_minutes = payload.duration_minutes
        if item.session_end:
            # Preserve any remaining lacing buffer by shifting session_end by the duration delta
            diff = payload.duration_minutes - old_duration
            item.session_end = item.session_end + timedelta(minutes=diff)

    if payload.shoe_sizes is not None:
        item.shoe_sizes = payload.shoe_sizes
        item.people_count = len(payload.shoe_sizes)

    if payload.comment is not None:
        item.comment = payload.comment.strip() or None

    db.commit()
    db.refresh(item)
    await manager.broadcast("QUEUE_UPDATED")
    return item


@router.post("/queue", response_model=QueueItemResponse, dependencies=[Depends(verify_kasa1)])
async def create_queue_entry(req: CreateQueueRequest, db: DBSession):
    # 1. Look up existing Telegram chat ID based on phone number
    norm_phone = "".join(filter(str.isdigit, req.phone))
    norm_phone_key = norm_phone[-9:] if len(norm_phone) >= 9 else norm_phone

    existing_chat_id = None
    if norm_phone_key:
        linked_items = db.query(QueueItem).filter(QueueItem.telegram_chat_id.isnot(None)).all()
        for r in linked_items:
            r_norm = "".join(filter(str.isdigit, r.phone))
            r_norm_key = r_norm[-9:] if len(r_norm) >= 9 else r_norm
            if r_norm_key == norm_phone_key:
                existing_chat_id = r.telegram_chat_id
                break

    # 2. Retry loop for atomic ticket number allocation under concurrency
    for _ in range(5):
        last_ticket = db.query(QueueItem).order_by(QueueItem.id.desc()).first()
        next_number = (last_ticket.ticket_number + 1) if last_ticket else 101

        item = QueueItem(
            ticket_number=next_number,
            phone=req.phone,
            people_count=len(req.shoe_sizes),
            shoe_sizes=req.shoe_sizes,
            duration_minutes=req.duration_minutes,
            comment=req.comment,
            telegram_chat_id=existing_chat_id,
        )
        db.add(item)
        try:
            db.commit()
            db.refresh(item)
            await manager.broadcast("QUEUE_UPDATED")
            return item
        except IntegrityError:
            db.rollback()
            continue

    raise HTTPException(status_code=500, detail="Could not allocate unique ticket number due to high concurrency.")


@router.post("/queue/{item_id}/cancel", response_model=QueueItemResponse, dependencies=[Depends(verify_kasa2)])
async def cancel_ticket_with_reason(item_id: int, payload: CancelTicketRequest, db: Session = Depends(get_db)):
    if not (item := db.query(QueueItem).filter(QueueItem.id == item_id).first()):
        raise HTTPException(status_code=404, detail="Запис не знайдено")

    if not payload.reason or len(payload.reason.strip()) < 3:
        raise HTTPException(status_code=422, detail="Вкажіть причину скасування (мінімум 3 символи)")

    item.status = QueueStatus.CANCELLED

    # Очищаємо попередні мітки [СКАСОВАНО], щоб залишалася лише актуальна причина та оригінальний коментар
    base_comment = item.comment or ""
    if base_comment:
        base_comment = re.sub(r'\[СКАСОВАНО][^|]*(\|\s*)?', '', base_comment).strip(' |')

    new_cancellation = f"[СКАСОВАНО] {payload.reason.strip()}"
    item.comment = f"{new_cancellation} | {base_comment}" if base_comment else new_cancellation

    db.commit()
    db.refresh(item)
    await manager.broadcast("QUEUE_UPDATED")
    return item


@router.patch("/queue/{item_id}/extend", response_model=QueueItemResponse, dependencies=[Depends(verify_kasa2)])
async def extend_session(item_id: int, payload: ExtendSessionRequest, db: Session = Depends(get_db)):
    if not (item := db.query(QueueItem).filter(QueueItem.id == item_id).first()):
        raise HTTPException(status_code=404, detail="Запис не знайдено")

    if item.status not in [QueueStatus.SERVED, "SERVED", "ОБСЛУГОВУЄТЬСЯ"]:
        raise HTTPException(status_code=400, detail="Можна продовжувати лише активні сесії")

    item.duration_minutes += payload.minutes
    if item.session_end:
        item.session_end += timedelta(minutes=payload.minutes)

    item.overtime_stopped_at = None

    db.commit()
    db.refresh(item)

    await manager.broadcast("QUEUE_UPDATED")
    return item


@router.post("/queue/{item_id}/revert", dependencies=[Depends(verify_kasa2)])
async def revert_ticket_status(item_id: int, db: Session = Depends(get_db)):
    if not (ticket := db.query(QueueItem).filter(QueueItem.id == item_id).first()):
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Step backward through the workflow states
    if ticket.status == QueueStatus.RETURNED:
        ticket.status = QueueStatus.SERVED
    elif ticket.status == QueueStatus.SERVED:
        ticket.status = QueueStatus.CALLING
        ticket.called_at = datetime.now(timezone.utc)
        ticket.session_start = None
        ticket.session_end = None
        ticket.overtime_stopped_at = None
    elif ticket.status == QueueStatus.CALLING:
        ticket.status = QueueStatus.WAITING
        ticket.called_at = None
        ticket.session_start = None
        ticket.session_end = None
        ticket.overtime_stopped_at = None
    elif ticket.status == QueueStatus.CANCELLED:
        ticket.status = QueueStatus.WAITING
        ticket.called_at = None
        ticket.session_start = None
        ticket.session_end = None
        ticket.overtime_stopped_at = None
    else:
        raise HTTPException(status_code=400, detail="Цей статус не можна відкотити")

    db.commit()
    db.refresh(ticket)
    await manager.broadcast("QUEUE_UPDATED")
    return ticket


@router.patch("/queue/{item_id}/status", response_model=QueueItemResponse)
async def update_status(item_id: int, status: QueueStatus, db: DBSession):
    if not (item := db.get(QueueItem, item_id)):
        raise HTTPException(status_code=404, detail="Запис не знайдено")

    old_status = item.status
    item.status = status
    now = datetime.now(timezone.utc)

    is_calling = str(status) in [str(QueueStatus.CALLING), "CALLING", "ВИКЛИКАЄТЬСЯ"]
    was_not_calling = str(old_status) not in [str(QueueStatus.CALLING), "CALLING", "ВИКЛИКАЄТЬСЯ"]

    if is_calling and not item.called_at:
        item.called_at = now

    if status == QueueStatus.SERVED and not item.session_start:
        item.session_start = now
        # Add 5 minutes lacing grace window before the main skating duration begins
        item.session_end = now + timedelta(minutes=5 + item.duration_minutes)

    db.commit()

    if status == QueueStatus.SERVED:
        revert_unfulfillable_calling_tickets(db)

    db.refresh(item)

    if is_calling and was_not_calling and item.telegram_chat_id:
        try:
            await send_telegram_notification(
                str(item.telegram_chat_id),
                f"🎟️ Шановний гість! Ваш талон **#{item.ticket_number}** викликається на видачу ковзанів."
                f" Будь ласка, підійдіть до стійки видачі протягом 5 хвилин!"
            )
        except Exception as e:
            print(f"[ERROR] Failed to send Telegram notification: {e}")

    await manager.broadcast("QUEUE_UPDATED")
    await manager.broadcast("INVENTORY_UPDATED")
    return item


@router.post("/queue/{item_id}/skip-lacing", response_model=QueueItemResponse, dependencies=[Depends(verify_kasa2)])
async def skip_lacing_window(item_id: int, db: Session = Depends(get_db)):
    """Immediately ends the 5-minute lacing window and starts the main ice timer."""
    if not (item := db.query(QueueItem).filter(QueueItem.id == item_id).first()):
        raise HTTPException(status_code=404, detail="Запис не знайдено")

    if item.status not in [QueueStatus.SERVED, "SERVED", "ОБСЛУГОВУЄТЬСЯ"]:
        raise HTTPException(status_code=400, detail="Можна запустити лише для активного сеансу")

    now = datetime.now(timezone.utc)
    item.session_end = now + timedelta(minutes=item.duration_minutes)

    db.commit()
    db.refresh(item)
    await manager.broadcast("QUEUE_UPDATED")
    return item


@router.post("/queue/{item_id}/stop-timer", response_model=QueueItemResponse, dependencies=[Depends(verify_kasa2)])
async def toggle_stop_timer(item_id: int, db: Session = Depends(get_db)):
    """Зупиняє або відновлює нарахування часу / overtime до остаточного закриття квитка."""
    if not (item := db.query(QueueItem).filter(QueueItem.id == item_id).first()):
        raise HTTPException(status_code=404, detail="Запис не знайдено")

    if item.status not in [QueueStatus.SERVED, "SERVED", "ОБСЛУГОВУЄТЬСЯ"]:
        raise HTTPException(status_code=400, detail="Зупинити таймер можна лише для активного сеансу")

    now = datetime.now(timezone.utc)
    if item.overtime_stopped_at is None:
        item.overtime_stopped_at = now
    else:
        # Якщо відновлюємо таймер після паузи — зсуваємо session_end на тривалість паузи
        stopped_at = item.overtime_stopped_at
        if stopped_at.tzinfo is None:
            stopped_at = stopped_at.replace(tzinfo=timezone.utc)
        paused_delta = now - stopped_at
        if item.session_end:
            item.session_end += paused_delta
        item.overtime_stopped_at = None

    db.commit()
    db.refresh(item)
    await manager.broadcast("QUEUE_UPDATED")
    return item


@router.post("/queue/mass-extend", dependencies=[Depends(verify_kasa2)])
async def mass_extend_sessions(payload: MassExtendRequest, db: Session = Depends(get_db)):
    if payload.admin_password != KASA2_PIN:
        raise HTTPException(status_code=403, detail="Невірний пароль адміністратора")

    if payload.minutes <= 0:
        raise HTTPException(status_code=400, detail="Кількість хвилин має бути більшою за нуль")

    now = datetime.now(timezone.utc)
    updated_count = 0

    active_items = db.query(QueueItem).filter(
        QueueItem.status.in_([
            QueueStatus.CALLING, "CALLING", "ВИКЛИКАЄТЬСЯ",
            QueueStatus.SERVED, "SERVED", "ОБСЛУГОВУЄТЬСЯ"
        ])
    ).all()

    for item in active_items:
        if str(item.status) in [str(QueueStatus.CALLING), "CALLING", "ВИКЛИКАЄТЬСЯ"]:
            item.called_at += timedelta(minutes=payload.minutes) if item.called_at else now
        else:
            item.duration_minutes += payload.minutes
            if item.session_end:
                item.session_end += timedelta(minutes=payload.minutes)
            else:
                item.session_start = item.session_start or now
                item.session_end = now + timedelta(minutes=item.duration_minutes)

            item.overtime_stopped_at = None
        updated_count += 1
    db.commit()
    await manager.broadcast("QUEUE_UPDATED")
    return {"status": "success", "updated_count": updated_count}
