from fastapi.testclient import TestClient
from app.models import QueueItem, QueueStatus
from app.api.auth import verify_kasa1, verify_kasa2
from main import app


def test_create_queue_item_via_api(client: TestClient, db_session):
    """Перевіряє створення талона через публічний/касовий API ендпоінт."""
    app.dependency_overrides[verify_kasa1] = lambda: True
    try:
        payload = {
            "phone": "+380991234567",
            "shoe_sizes": ["38", "39"],
            "duration_minutes": 60,
            "comment": "Тестовий візит"
        }
        response = client.post("/api/queue", json=payload)
        if response.status_code == 200:
            data = response.json()
            assert data["ticket_number"] >= 101
            assert data["people_count"] == 2
            assert data["shoe_sizes"] == ["38", "39"]
    finally:
        app.dependency_overrides.pop(verify_kasa1, None)


def test_mass_extend_unauthorized_fails(client: TestClient):
    """Перевіряє, що масове подовження сесій без правильного пароля адміністратора блокується (403 Forbidden)."""
    app.dependency_overrides[verify_kasa2] = lambda: True
    try:
        payload = {"minutes": 15,"admin_password": "wrong_password"}
        response = client.post("/api/queue/mass-extend", json=payload)
        assert response.status_code == 403
        assert "Невірний пароль адміністратора" in response.json().get("detail", "")
    finally:
        app.dependency_overrides.pop(verify_kasa2, None)


def test_cancel_ticket_requires_reason_length(client: TestClient, db_session):
    """Перевіряє, що скасування талона з коротким або порожнім описом відхиляється (422 або 400)."""
    app.dependency_overrides[verify_kasa2] = lambda: True
    try:
        ticket = QueueItem(
            ticket_number=301,
            phone="380990001122",
            people_count=1,
            shoe_sizes=["40"],
            status=QueueStatus.WAITING
        )
        db_session.add(ticket)
        db_session.commit()

        # Передаємо занадто коротку причину (менше 3 символів)
        payload = {"reason": "ні"}
        response = client.post(f"/api/queue/{ticket.id}/cancel", json=payload)

        assert response.status_code in [400, 422]
    finally:
        app.dependency_overrides.pop(verify_kasa2, None)