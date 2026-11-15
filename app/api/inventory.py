from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.auth import is_authenticated_kasa2, verify_kasa2
from app.db import get_db
from app.inventory import calculate_live_inventory
from app.models import QueueItem, QueueStatus, SkateInventory
from app.schemas import InventoryItemCreate, InventoryUpdatePayload
from app.ws_manager import manager

router = APIRouter(prefix="/api", tags=["API Endpoints"])


@router.post("/inventory", dependencies=[Depends(verify_kasa2)])
async def create_inventory_item(payload: InventoryItemCreate, db: Session = Depends(get_db)):
    if db.query(SkateInventory).filter(SkateInventory.size == payload.size).first():
        raise HTTPException(status_code=400, detail="Такий розмір вже існує в базі")

    item = SkateInventory(
        size=payload.size,
        total_stock=payload.total_stock,
        maintenance_count=payload.maintenance_count
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    await manager.broadcast("INVENTORY_UPDATED")
    return item


@router.patch("/inventory", dependencies=[Depends(verify_kasa2)])
async def update_inventory_item(payload: InventoryUpdatePayload, db: Session = Depends(get_db)):
    if not (item := db.query(SkateInventory).filter(SkateInventory.size == payload.size).first()):
        raise HTTPException(status_code=404, detail="Розмір не знайдено")

    new_total = payload.total_stock if payload.total_stock is not None else item.total_stock
    new_maint = payload.maintenance_count if payload.maintenance_count is not None else item.maintenance_count

    # Enforce total-stock and maintenance-count invariant on the server
    if new_maint > new_total:
        raise HTTPException(
            status_code=400,
            detail="Кількість ковзанів на ремонті не може перевищувати загальну кількість!"
        )

    if payload.total_stock is not None:
        item.total_stock = max(0, payload.total_stock)
    if payload.maintenance_count is not None:
        item.maintenance_count = max(0, payload.maintenance_count)

    db.commit()
    await manager.broadcast("INVENTORY_UPDATED")
    return item


@router.get("/inventory")
def get_inventory_status(request: Request, db: Session = Depends(get_db)):
    """Exposes current counts to cashiers for inventory tracking."""
    active_skaters = db.query(QueueItem).filter(
        QueueItem.status.in_([QueueStatus.WAITING, QueueStatus.CALLING, QueueStatus.SERVED])
    ).all()

    db_inventory = db.query(SkateInventory).all()
    live_inventory = calculate_live_inventory(active_skaters, db_inventory)

    # Check if the requester is authenticated as Kasa 2 / Admin
    kasa2_cookie = request.cookies.get("kasa2_session")
    is_admin = is_authenticated_kasa2(kasa2_cookie)

    for item in db_inventory:
        if item.size not in live_inventory:
            live_inventory[item.size] = {
                "total": item.total_stock,
                "in_use": 0,
                "available": max(0, item.total_stock - item.maintenance_count),
                "in_queue": 0,
                "target_timestamp": None
            }

        live_inventory[item.size]["total"] = item.total_stock

        if is_admin:  # Expose maintenance_count strictly to authenticated admin/staff
            live_inventory[item.size]["maintenance_count"] = item.maintenance_count

    return live_inventory


@router.delete("/inventory", dependencies=[Depends(verify_kasa2)])
async def delete_inventory_item(size: str, db: Session = Depends(get_db)):
    if not (item := db.query(SkateInventory).filter(SkateInventory.size == size).first()):
        raise HTTPException(status_code=404, detail="Розмір не знайдено")

    item.is_deleted = True
    db.commit()
    await manager.broadcast("INVENTORY_UPDATED")
    return {"success": True}
