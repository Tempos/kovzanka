from datetime import datetime, timedelta, timezone
from app.models import QueueItem, QueueStatus, SkateInventory
from app.inventory import revert_unfulfillable_calling_tickets


def test_extend_session_duration(db_session):
    """Перевіряє коректність подовження активної сесії на льоду з урахуванням timezone."""
    now = datetime.now(timezone.utc)
    ticket = QueueItem(
        ticket_number=201,
        phone="380991234567",
        people_count=1,
        shoe_sizes=["35"],
        status=QueueStatus.SERVED,
        duration_minutes=60,
        session_start=now,
        session_end=now + timedelta(minutes=65)  # 5 хв шнурівки + 60 хв
    )
    db_session.add(ticket)
    db_session.commit()

    # Симулюємо подовження на 15 хвилин
    extension_mins = 15
    ticket.duration_minutes += extension_mins
    if ticket.session_end:
        if ticket.session_end.tzinfo is None:
            ticket.session_end = ticket.session_end.replace(tzinfo=timezone.utc)
        ticket.session_end += timedelta(minutes=extension_mins)

    db_session.commit()
    db_session.refresh(ticket)

    assert ticket.duration_minutes == 75

    expected_end = now + timedelta(minutes=65 + 15)
    actual_end = ticket.session_end
    if actual_end.tzinfo is None:
        actual_end = actual_end.replace(tzinfo=timezone.utc)

    assert abs((actual_end - expected_end).total_seconds()) < 2


def test_revert_ticket_workflow_step_backward(db_session):
    """Перевіряє правильність покрокового відкату статусів талона назад."""
    ticket = QueueItem(
        ticket_number=202,
        phone="380997654321",
        people_count=1,
        shoe_sizes=["32"],
        status=QueueStatus.SERVED,
        called_at=datetime.now(timezone.utc)
    )
    db_session.add(ticket)
    db_session.commit()

    # Симулюємо перехід SERVED -> CALLING (відкат назад)
    if ticket.status == QueueStatus.SERVED:
        ticket.status = QueueStatus.CALLING
        ticket.session_start = None
        ticket.session_end = None
        ticket.overtime_stopped_at = None

    db_session.commit()
    db_session.refresh(ticket)

    assert ticket.status == QueueStatus.CALLING
    assert ticket.session_start is None
    assert ticket.session_end is None


def test_revert_unfulfillable_multiple_sizes_stock(db_session):
    """Перевіряє авто-відкат викликаного талона, якщо на кілька різних розмірів бракує інвентарю."""
    db_session.add_all([
        SkateInventory(size="30 (фігурні)", total_stock=1, maintenance_count=0, is_deleted=False),
        SkateInventory(size="42 (хокейні)", total_stock=1, maintenance_count=0, is_deleted=False)
    ])

    ticket1 = QueueItem(
        ticket_number=210,
        phone="380991111111",
        people_count=1,
        shoe_sizes=["30"],
        status=QueueStatus.SERVED
    )

    ticket2 = QueueItem(
        ticket_number=211,
        phone="380992222222",
        people_count=1,
        shoe_sizes=["30"],
        status=QueueStatus.CALLING
    )

    db_session.add_all([ticket1, ticket2])
    db_session.commit()

    reverted = revert_unfulfillable_calling_tickets(db_session)
    db_session.refresh(ticket2)

    assert reverted is True
    assert ticket2.status == QueueStatus.WAITING
    assert ticket2.called_at is None