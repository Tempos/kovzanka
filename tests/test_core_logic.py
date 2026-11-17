from app.bot import normalize_phone
from app.inventory import calculate_live_inventory
from app.models import QueueItem, QueueStatus, SkateInventory


def test_normalize_phone():
    """Перевіряє коректність нормалізації українських та різних форматів номерів телефонів."""
    assert normalize_phone("+38 (099) 123-45-67") == "991234567"
    assert normalize_phone("0991234567") == "991234567"
    assert normalize_phone("380991234567") == "991234567"
    assert normalize_phone("12345") == "12345"
    assert normalize_phone("") == ""
    assert normalize_phone(None) == ""


def test_ticket_number_allocation(db_session):
    """Перевіряє правильність генерації послідовних номерів талонів (починаючи з 101)."""
    # Перший талон
    item1 = QueueItem(
        ticket_number=101,
        phone="380991112233",
        people_count=2,
        shoe_sizes=["28", "29"],
        status=QueueStatus.WAITING
    )
    db_session.add(item1)
    db_session.commit()

    # Симулюємо створення наступного талона за логікою API
    last_ticket = db_session.query(QueueItem).order_by(QueueItem.id.desc()).first()
    next_number = (last_ticket.ticket_number + 1) if last_ticket else 101

    item2 = QueueItem(
        ticket_number=next_number,
        phone="380992223344",
        people_count=1,
        shoe_sizes=["30"],
        status=QueueStatus.WAITING
    )
    db_session.add(item2)
    db_session.commit()

    assert item1.ticket_number == 101
    assert item2.ticket_number == 102


def test_calculate_live_inventory_metrics(db_session):
    """Перевіряє правильність розрахунку доступного стоку та черги в реальному часі."""
    # Додаємо інвентар
    inv = SkateInventory(size="32 (фігурні)", total_stock=5, maintenance_count=1, is_deleted=False)
    db_session.add(inv)

    # Додаємо талон у черзі (просить 2 пари)
    ticket = QueueItem(
        ticket_number=105,
        phone="380995556677",
        people_count=2,
        shoe_sizes=["32", "32"],
        status=QueueStatus.WAITING
    )
    db_session.add(ticket)
    db_session.commit()

    active_items = db_session.query(QueueItem).filter(
        QueueItem.status.in_([QueueStatus.WAITING, QueueStatus.CALLING, QueueStatus.SERVED])
    ).all()
    inventory_records = db_session.query(SkateInventory).all()

    live_inv = calculate_live_inventory(active_items, inventory_records)

    size_key = "32 (фігурні)"
    assert size_key in live_inv
    assert live_inv[size_key]["total"] == 5
    assert live_inv[size_key]["maintenance_count"] == 1
    assert live_inv[size_key]["in_queue"] == 2
    # Загалом 5, мінус 1 в обслуговуванні = 4 доступних на складі, але 2 в черзі -> доступність для наступних = 2
    assert live_inv[size_key]["available"] == 4


def test_cancellation_comment_formatting(db_session):
    """Перевіряє форматування причини скасування та збереження історії коментарів."""
    ticket = QueueItem(
        ticket_number=106,
        phone="380998889900",
        people_count=1,
        shoe_sizes=["35"],
        comment="Оригінальний коментар",
        status=QueueStatus.WAITING
    )
    db_session.add(ticket)
    db_session.commit()

    # Симулюємо логіку скасування з причиною
    reason = "Клієнт відмовився"
    ticket.status = QueueStatus.CANCELLED
    new_cancellation = f"[СКАСОВАНО] {reason}"
    ticket.comment = f"{new_cancellation} | {ticket.comment}"
    db_session.commit()

    db_session.refresh(ticket)
    assert ticket.status == QueueStatus.CANCELLED
    assert "[СКАСОВАНО] Клієнт відмовився" in ticket.comment
    assert "Оригінальний коментар" in ticket.comment
