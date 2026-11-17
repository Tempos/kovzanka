import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import QueueItem, QueueStatus, SkateInventory


def init_inventory_db(db_session):
    """Ensures all default sizes exist, respecting intentional deletions."""
    try:
        for size in range(26, 49):
            for category in ["фігурні", "хокейні"]:
                size_name = f"{size} ({category})"

                if not (existing := db_session.query(SkateInventory).filter(SkateInventory.size == size_name).first()):
                    db_session.add(
                        SkateInventory(size=size_name, total_stock=10, maintenance_count=0, is_deleted=False))
                elif existing.is_deleted:
                    continue  # Skip recreating sizes that were explicitly deleted by an admin
        db_session.commit()
    except IntegrityError:
        db_session.rollback()


def calculate_live_inventory(active_items: List[Any], db_inventory_records: List[Any]) -> Dict[str, Dict[str, Any]]:
    """Computes real-time availability from actual database records."""
    current_time = datetime.now(timezone.utc)

    inventory = _build_base_inventory(db_inventory_records)
    _process_queue_items(active_items, inventory)
    size_end_times = _process_served_items(active_items, inventory, current_time)
    _finalize_inventory_metrics(inventory, size_end_times, current_time)

    return inventory


def process_range_expansion(db_session, raw_size: str, cat_suffix: str, total_stock: int) -> dict:
    """Expand a numeric range (e.g., '20-25') into individual inventory sizes."""
    if not (range_match := re.match(r"^(\d+)\s*[-–]\s*(\d+)$", raw_size)):
        raise HTTPException(status_code=400, detail="Невірний формат діапазону")

    start, end = int(range_match[1]), int(range_match[2])
    if start > end:
        raise HTTPException(status_code=400, detail="Початковий розмір не може бути більшим за кінцевий")

    created_count = 0
    for size_num in range(start, end + 1):
        size_str = f"{size_num}{cat_suffix}"
        if existing_item := db_session.query(SkateInventory).filter(SkateInventory.size == size_str).first():
            existing_item.is_deleted = False
            existing_item.total_stock = total_stock
            existing_item.maintenance_count = 0
            created_count += 1
            continue

        db_session.add(SkateInventory(
            size=size_str,
            total_stock=total_stock,
            maintenance_count=0,
            is_deleted=False
        ))
        created_count += 1

    db_session.commit()
    return {"success": True, "created_count": created_count}


def revert_unfulfillable_calling_tickets(db: Session) -> bool:
    """
    Автоматично повертає назад у статус 'ЧЕКАЄ' ті талони у статусі 'ВИКЛИКАЄТЬСЯ',
    на які вже не вистачає реального вільного інвентарю.
    """
    active_items = db.query(QueueItem).filter(
        QueueItem.status.in_([QueueStatus.WAITING, QueueStatus.CALLING, QueueStatus.SERVED])
    ).all()

    db_inventory_records = db.query(SkateInventory).filter(SkateInventory.is_deleted == False).all()
    inventory = calculate_live_inventory(active_items, db_inventory_records)

    calling_tickets = [
        item for item in active_items
        if (item.status.value if hasattr(item.status, "value") else str(item.status)) in ("ВИКЛИКАЄТЬСЯ", "CALLING",
                                                                                          QueueStatus.CALLING)
    ]
    # Сортуємо за часом виклику, щоб першими оброблялися найстаріші виклики
    calling_tickets.sort(key=lambda x: x.called_at or x.created_at)

    reverted = False
    for ticket in calling_tickets:
        needed = Counter(ticket.shoe_sizes or [])
        can_fulfill = True

        for raw_size, count in needed.items():
            size_key = _resolve_size_key(raw_size, inventory)
            available = inventory.get(size_key, {}).get("available", 0)
            if available < count:
                can_fulfill = False
                break
            # Тимчасово списуємо з локального розрахунку, щоб наступні викликані талони теж це врахували
            inventory[size_key]["available"] -= count

        if not can_fulfill:
            ticket.status = QueueStatus.WAITING
            ticket.called_at = None
            reverted = True

    if reverted:
        db.commit()
    return reverted


def upsert_inventory_item(db_session, size: str, total_stock: int, maintenance_count: int = 0) -> SkateInventory:
    """Restore a soft-deleted item or create a new one. Raises 400 if an active item already exists."""
    if existing_item := db_session.query(SkateInventory).filter(SkateInventory.size == size).first():
        existing_item.is_deleted = False
        existing_item.total_stock = total_stock
        existing_item.maintenance_count = maintenance_count
        db_session.commit()
        db_session.refresh(existing_item)
        return existing_item

    item = SkateInventory(
        size=size,
        total_stock=total_stock,
        maintenance_count=maintenance_count,
        is_deleted=False
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


def _build_base_inventory(db_inventory_records: List[Any]) -> Dict[str, Dict[str, Any]]:
    """Builds initial inventory dictionary dynamically from database rows."""
    inventory: Dict[str, Dict[str, Any]] = {}
    for record in db_inventory_records:
        if getattr(record, "is_deleted", False):
            continue
        m_count = getattr(record, "maintenance_count", 0)
        inventory[record.size] = {
            "total": record.total_stock,
            "maintenance_count": m_count,
            "in_use": 0,
            "in_queue": 0,
            "available": record.total_stock - m_count,
            "target_timestamp": None,
            "next_available_in_mins": None,
        }
    return inventory


def _finalize_inventory_metrics(
        inventory: Dict[str, Dict[str, Any]], size_end_times: Dict[str, List[datetime]], current_time: datetime
):
    """Computes final availability, deficits, and estimated wait times."""
    for size_key, inv in inventory.items():
        inv["available"] = max(0, inv["total"] - inv["in_use"] - inv["maintenance_count"])
        deficit = inv["in_queue"] - inv["available"]

        if deficit > 0 and size_key in size_end_times:
            sorted_ends = sorted(size_end_times[size_key])
            target_dt = sorted_ends[deficit - 1] if deficit <= len(sorted_ends) else sorted_ends[-1]
            inv["target_timestamp"] = int(target_dt.timestamp())
            diff_mins = max(1, int((target_dt - current_time).total_seconds() / 60))
            inv["next_available_in_mins"] = diff_mins
        else:
            inv["target_timestamp"] = None
            inv["next_available_in_mins"] = None


def _process_queue_items(active_items: List[Any], inventory: Dict[str, Dict[str, Any]]):
    """Accumulates items currently waiting in queue per size."""
    queue_statuses = (
        "ЧЕКАЄ", "WAITING", "PENDING", "ВИКЛИКАЄТЬСЯ", "CALLING",
        "QueueStatus.WAITING", "QueueStatus.CALLING"
    )
    for item in active_items:
        status_val = item.status.value if hasattr(item.status, "value") else str(item.status)
        if status_val in queue_statuses:
            for raw_size in item.shoe_sizes if isinstance(item.shoe_sizes, list) else []:
                size_key = _resolve_size_key(raw_size, inventory)
                if size_key in inventory:
                    inventory[size_key]["in_queue"] += 1


def _process_served_items(
        active_items: List[Any], inventory: Dict[str, Dict[str, Any]], current_time: datetime
) -> Dict[str, List[datetime]]:
    """Accumulates items currently in use and tracks session end times."""
    served_statuses = ("ОБСЛУГОВУЄТЬСЯ", "SERVED", "QueueStatus.SERVED")
    size_end_times: Dict[str, List[datetime]] = {}

    for item in active_items:
        status_val = item.status.value if hasattr(item.status, "value") else str(item.status)
        if status_val not in served_statuses:
            continue

        if item.session_end:
            end_time = item.session_end if item.session_end.tzinfo else item.session_end.replace(tzinfo=timezone.utc)
        else:
            duration = getattr(item, "duration_minutes", 0) or 0
            end_time = current_time + timedelta(minutes=duration)

        for raw_size in item.shoe_sizes if isinstance(item.shoe_sizes, list) else []:
            size_key = _resolve_size_key(raw_size, inventory)
            if size_key in inventory:
                inv = inventory[size_key]
                inv["in_use"] += 1
                if size_key not in size_end_times:
                    size_end_times[size_key] = []
                size_end_times[size_key].append(end_time)

    return size_end_times


def _resolve_size_key(raw_size: Any, inventory: Dict[str, Any]) -> str:
    """Resolves a raw size into a matching inventory key with robust fallback."""
    size_key = str(raw_size).strip()
    if size_key in inventory:
        return size_key

    clean_target = size_key.split("(")[0].strip().lower()

    # Шукаємо збіг за номером і категорією (наприклад, 'фіг' vs 'фігурні')
    for inv_key in inventory.keys():
        clean_inv = str(inv_key).split("(")[0].strip().lower()
        if clean_inv == clean_target:
            if "хок" in size_key.lower() and "хок" in inv_key.lower():
                return inv_key
            if "фіг" in size_key.lower() and "фіг" in inv_key.lower():
                return inv_key

    # Запасний варіант: чистий збіг за номером
    for inv_key in inventory.keys():
        clean_inv = str(inv_key).split("(")[0].strip().lower()
        if clean_inv == clean_target:
            return inv_key

    candidate = f"{size_key} (фігурні)"
    if candidate in inventory:
        return candidate
    return size_key
