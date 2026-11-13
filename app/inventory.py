from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy.exc import IntegrityError

from app.models import SkateInventory


def init_inventory_db(db_session):
    """Ensures all default sizes exist, respecting intentional deletions."""
    try:
        for size in range(26, 49):
            for category in ["фігурні", "хокейні"]:
                size_name = f"{size} ({category})"

                if not (existing := db_session.query(SkateInventory).filter(SkateInventory.size == size_name).first()):
                    db_session.add(SkateInventory(size=size_name,total_stock=10,maintenance_count=0,is_deleted=False))
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


def _resolve_size_key(raw_size: Any, inventory: Dict[str, Any]) -> str:
    """Resolves a raw size into a matching inventory key with a fallback."""
    size_key = str(raw_size)
    if size_key not in inventory:
        candidate = f"{size_key} (фігурні)"
        if candidate in inventory:
            return candidate
    return size_key


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
