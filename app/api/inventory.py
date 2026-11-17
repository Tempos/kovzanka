import re
import traceback

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.auth import is_authenticated_kasa2, verify_kasa2
from app.db import get_db
from app.inventory import calculate_live_inventory, process_range_expansion, upsert_inventory_item
from app.models import QueueItem, QueueStatus, SkateInventory
from app.schemas import InventoryItemCreate, InventoryUpdatePayload
from app.ws_manager import manager

router = APIRouter(prefix="/api", tags=["API Endpoints"])


@router.post("/inventory", dependencies=[Depends(verify_kasa2)])
async def create_inventory_item(payload: InventoryItemCreate, db: Session = Depends(get_db)):
    """Create a single inventory item, an adjustable range item, or expand a numeric range."""
    try:
        raw_size = payload.size.strip()
        cat_suffix = " (хокейні)" if payload.category == "hockey" else " (фігурні)"

        if payload.expand_range and re.match(r"^(\d+)\s*[-–]\s*(\d+)$", raw_size):
            result = process_range_expansion(db, raw_size, cat_suffix, payload.total_stock)
            await manager.broadcast("INVENTORY_UPDATED")
            return result

        formatted_size = f"{raw_size}{cat_suffix}"
        item = upsert_inventory_item(db, formatted_size, payload.total_stock, payload.maintenance_count)

        await manager.broadcast("INVENTORY_UPDATED")
        return item
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"CRITICAL ERROR in create_inventory_item: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Внутрішня помилка сервера: {str(e)}") from e


@router.patch("/inventory", dependencies=[Depends(verify_kasa2)])
async def update_inventory_item(payload: InventoryUpdatePayload, db: Session = Depends(get_db)):
    if not (item := db.query(SkateInventory).filter(SkateInventory.size == payload.size).first()):
        raise HTTPException(status_code=404, detail="Розмір не знайдено")

    total = payload.total_stock if payload.total_stock is not None else item.total_stock
    maintenance = payload.maintenance_count if payload.maintenance_count is not None else item.maintenance_count

    # Обчислюємо поточні видані ковзани для цього розміру (in_use)
    active_skaters = db.query(QueueItem).filter(
        QueueItem.status.in_([QueueStatus.WAITING, QueueStatus.CALLING, QueueStatus.SERVED])
    ).all()
    db_inventory_all = db.query(SkateInventory).filter(SkateInventory.is_deleted == False).all()
    live_inventory = calculate_live_inventory(active_skaters, db_inventory_all)

    in_use = 0
    if payload.size in live_inventory:
        in_use = live_inventory[payload.size].get("in_use", 0)

    if total < in_use:
        text = f"Неможливо зменшити загальну кількість нижче кількості виданих ковзанів ({in_use} на руках)!"
        raise HTTPException(status_code=400, detail=text)

    if maintenance > total:
        text = "Кількість ковзанів на ремонті не може перевищувати загальну кількість!"
        raise HTTPException(status_code=400, detail=text)

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

    db_inventory = db.query(SkateInventory).filter(SkateInventory.is_deleted == False).all()
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
