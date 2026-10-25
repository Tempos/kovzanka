from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

SKATE_INVENTORY_STOCK: Dict[int, int] = {size: 10 for size in range(26, 49)}


def calculate_live_inventory(active_items: List[Any]) -> Dict[int, Dict[str, Any]]:
    """Computes real-time availability, queue counts, and turn-around times with target timestamps."""
    current_time = datetime.now(timezone.utc)

    inventory: Dict[int, Dict[str, Any]] = {
        size: {
            "total": total,
            "in_use": 0,
            "in_queue": 0,
            "available": total,
            "target_timestamp": None,
        }
        for size, total in SKATE_INVENTORY_STOCK.items()
    }

    # 1. Count items waiting or being called in the queue (visibility only)
    for item in active_items:
        status_val = item.status.value if hasattr(item.status, "value") else str(item.status)
        if status_val in ("ЧЕКАЄ", "WAITING", "PENDING", "ВИКЛИКАЄТЬСЯ", "CALLING", "QueueStatus.WAITING", "QueueStatus.CALLING"):
            for size in item.shoe_sizes if isinstance(item.shoe_sizes, list) else []:
                try:
                    size_int = int(size)
                except (ValueError, TypeError):
                    continue
                if size_int in inventory:
                    inventory[size_int]["in_queue"] += 1

    # 2. Track the earliest session end time per size for deficit queue situations
    size_earliest_end: Dict[int, datetime] = {}

    for item in active_items:
        status_val = item.status.value if hasattr(item.status, "value") else str(item.status)
        if status_val not in ("ОБСЛУГОВУЄТЬСЯ", "SERVED", "QueueStatus.SERVED"):
            continue

        if item.session_end:
            end_time = item.session_end.replace(
                tzinfo=timezone.utc) if item.session_end.tzinfo is None else item.session_end
        else:
            duration = getattr(item, "duration_minutes", 0) or 0
            end_time = current_time + timedelta(minutes=duration)

        for size in item.shoe_sizes if isinstance(item.shoe_sizes, list) else []:
            try:
                size_int = int(size)
            except (ValueError, TypeError):
                continue

            if size_int in inventory:
                inv = inventory[size_int]
                inv["in_use"] += 1

                current_avail = inv["total"] - inv["in_use"]
                if (current_avail < 0 or inv["in_queue"] > current_avail) and (size_int not in size_earliest_end or end_time < size_earliest_end[size_int]):
                    size_earliest_end[size_int] = end_time

    # 3. Calculate final available stock and set target_timestamp
    for size_int, inv in inventory.items():
        inv["available"] = max(0, inv["total"] - inv["in_use"])

        if inv["in_queue"] > inv["available"] and size_int in size_earliest_end:
            inv["target_timestamp"] = int(size_earliest_end[size_int].timestamp())
        else:
            inv["target_timestamp"] = None

    return inventory