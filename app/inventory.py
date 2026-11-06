from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

SKATE_INVENTORY_STOCK: Dict[str, int] = {}
for size in range(26, 49):
    SKATE_INVENTORY_STOCK[f"{size} (фігурні)"] = 5
    SKATE_INVENTORY_STOCK[f"{size} (хокейні)"] = 5


def calculate_live_inventory(active_items: List[Any]) -> Dict[str, Dict[str, Any]]:
    """Computes real-time availability, queue counts, and turn-around times with target timestamps."""
    current_time = datetime.now(timezone.utc)

    inventory: Dict[str, Dict[str, Any]] = {
        size_key: {
            "total": total,
            "in_use": 0,
            "in_queue": 0,
            "available": total,
            "target_timestamp": None,
            "next_available_in_mins": None,
        }
        for size_key, total in SKATE_INVENTORY_STOCK.items()
    }

    for item in active_items:
        status_val = item.status.value if hasattr(item.status, "value") else str(item.status)
        if status_val in ("ЧЕКАЄ", "WAITING", "PENDING", "ВИКЛИКАЄТЬСЯ", "CALLING", "QueueStatus.WAITING", "QueueStatus.CALLING"):
            for raw_size in item.shoe_sizes if isinstance(item.shoe_sizes, list) else []:
                size_key = str(raw_size)
                if size_key not in inventory:
                    candidate = f"{size_key} (фігурні)"
                    if candidate in inventory:
                        size_key = candidate
                if size_key in inventory:
                    inventory[size_key]["in_queue"] += 1

    size_end_times: Dict[str, List[datetime]] = {}

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

        for raw_size in item.shoe_sizes if isinstance(item.shoe_sizes, list) else []:
            size_key = str(raw_size)
            if size_key not in inventory:
                candidate = f"{size_key} (фігурні)"
                if candidate in inventory:
                    size_key = candidate

            if size_key in inventory:
                inv = inventory[size_key]
                inv["in_use"] += 1
                if size_key not in size_end_times:
                    size_end_times[size_key] = []
                size_end_times[size_key].append(end_time)

    for size_key, inv in inventory.items():
        inv["available"] = max(0, inv["total"] - inv["in_use"])
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

    return inventory