import os
from datetime import datetime, timezone
from typing import List, Dict, Any

# A baseline dictionary defining structural stock capacity overrides.
# You can customize these pairs freely as your stock shifts.
SKATE_INVENTORY_STOCK: Dict[int, int] = {
    size: 10 for size in range(26, 49)
}


# Example override if you ever need to adjust popular sizes later:
# SKATE_INVENTORY_STOCK[38] = 15
# SKATE_INVENTORY_STOCK[42] = 12

def calculate_live_inventory(active_items: List[Any]) -> Dict[int, Dict[str, Any]]:
    """ Computes real-time availability and upcoming turn-around return times.
        Processes items currently out on the ice (status == SERVED).
    """
    current_time = datetime.now(timezone.utc)

    # Initialize the baseline dictionary tracking layout
    inventory = {}
    for size, total in SKATE_INVENTORY_STOCK.items():
        inventory[size] = {
            "total": total,
            "in_use": 0,
            "available": total,
            "next_available_in_mins": None
        }

    for item in active_items:
        # Safeguard array reading if it's stored as raw string lists or text
        sizes = item.shoe_sizes if isinstance(item.shoe_sizes, list) else []

        # Determine the time remaining until this individual session concludes
        if item.session_end:
            # Ensure naive database datetimes are handled as UTC matching our clock
            end_time = item.session_end.replace(
                tzinfo=timezone.utc) if item.session_end.tzinfo is None else item.session_end
            seconds_remaining = (end_time - current_time).total_seconds()
            minutes_remaining = max(0, int(seconds_remaining // 60))
        else:
            minutes_remaining = item.duration_minutes

        for size in sizes:
            try:
                size_int = int(size)
            except (ValueError, TypeError):
                continue

            if size_int in inventory:
                inventory[size_int]["in_use"] += 1
                inventory[size_int]["available"] = max(0, inventory[size_int]["total"] - inventory[size_int]["in_use"])

                # If this size is fully checked out, track when the next pair returns
                if inventory[size_int]["available"] == 0:
                    current_min = inventory[size_int]["next_available_in_mins"]
                    if current_min is None or minutes_remaining < current_min:
                        inventory[size_int]["next_available_in_mins"] = minutes_remaining

    return inventory
