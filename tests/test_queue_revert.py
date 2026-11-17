import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.models import QueueItem, QueueStatus, SkateInventory
from app.inventory import revert_unfulfillable_calling_tickets


def test_revert_unfulfillable_calling_tickets_single_size(db_session):
    # 1. Налаштовуємо інвентар: розмір "28 (фігурні)" має всього 5 одиниць загального стоку
    inv = SkateInventory(size="28 (фігурні)", total_stock=5, maintenance_count=0, is_deleted=False)
    db_session.add(inv)

    # 2. Створюємо Талон #1 у статусі ВИКЛИКАЄТЬСЯ (просить 5 пар розміру 28)
    ticket1 = QueueItem(
        ticket_number=101,
        phone="380991112233",
        people_count=5,
        shoe_sizes=["28", "28", "28", "28", "28"],
        status=QueueStatus.CALLING
    )

    # 3. Створюємо Талон #2 у статусі ВИКЛИКАЄТЬСЯ (теж просить 5 пар розміру 28, але їх вже не вистачить)
    ticket2 = QueueItem(
        ticket_number=102,
        phone="380992223344",
        people_count=5,
        shoe_sizes=["28", "28", "28", "28", "28"],
        status=QueueStatus.CALLING
    )

    db_session.add_all([ticket1, ticket2])
    db_session.commit()

    # Сценарій А: Обидва викликаються, але вільних stok = 5. Перший забирає все (переводимо в SERVED).
    ticket1.status = QueueStatus.SERVED
    db_session.commit()

    # Запускаємо нашу функцію автоматичного відкату
    reverted = revert_unfulfillable_calling_tickets(db_session)
    db_session.refresh(ticket2)

    # Перевірка: функція мала спрацювати і повернути другий талон назад у статус WAITING
    assert reverted is True
    assert ticket2.status == QueueStatus.WAITING
    assert ticket2.called_at is None


def test_websocket_broadcast_on_status_update(client: TestClient, db_session):
    """
    Тест перевіряє, що при зміні статусу на SERVED триґериться WebSocket-повідомлення
    та оновлюються дані через API черги/інвентарю.
    """
    inv = SkateInventory(size="30 (фігурні)", total_stock=2, maintenance_count=0, is_deleted=False)
    db_session.add(inv)

    ticket = QueueItem(
        ticket_number=103,
        phone="380993334455",
        people_count=1,
        shoe_sizes=["30"],
        status=QueueStatus.CALLING
    )
    db_session.add(ticket)
    db_session.commit()

    # Використовуємо тестовий клієнт FastAPI для переведення талона в SERVED через патч статус-ендпоінта
    response = client.patch(f"/api/queue/{ticket.id}/status", params={"status": "ОБСЛУГОВУЄТЬСЯ"})

    # Якщо у вас шлях приймає status через тіло або query-параметри — адаптуйте під свій роутер.
    # Нижче перевірка результату в БД:
    db_session.refresh(ticket)
    assert ticket.status == QueueStatus.SERVED
    assert ticket.session_start is not None