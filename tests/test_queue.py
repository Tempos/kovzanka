from app.models import QueueItem, QueueStatus, SkateInventory
from app.inventory import revert_unfulfillable_calling_tickets


def test_revert_unfulfillable_calling_tickets_single_size(db_session):
    # 1. Налаштовуємо інвентар
    inv = SkateInventory(size="28 (фігурні)", total_stock=5, maintenance_count=0, is_deleted=False)
    db_session.add(inv)

    # 2. Талони
    ticket1 = QueueItem(
        ticket_number=101,
        phone="380991112233",
        people_count=5,
        shoe_sizes=["28", "28", "28", "28", "28"],
        status=QueueStatus.CALLING
    )
    ticket2 = QueueItem(
        ticket_number=102,
        phone="380992223344",
        people_count=5,
        shoe_sizes=["28", "28", "28", "28", "28"],
        status=QueueStatus.CALLING
    )

    db_session.add_all([ticket1, ticket2])
    db_session.commit()

    ticket1.status = QueueStatus.SERVED
    db_session.commit()

    reverted = revert_unfulfillable_calling_tickets(db_session)
    db_session.refresh(ticket2)

    assert reverted is True
    assert ticket2.status == QueueStatus.WAITING
    assert ticket2.called_at is None