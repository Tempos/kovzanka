from datetime import datetime, timedelta, timezone
from app.api.auth import get_password_hash, verify_kasa1, verify_kasa2
from app.models import QueueItem, QueueStatus, User
from main import app
from tests.conftest import login_as
from fastapi.testclient import TestClient
from app.models import QueueItem, QueueStatus
from app.api.auth import verify_kasa1, verify_kasa2
from main import app

def _seed_staff_users(db_session):
    db_session.add_all([
        User(username="admin", password=get_password_hash("admin-pass"), role="admin"),
        User(username="kasa1", password=get_password_hash("kasa1-pass"), role="kasa1"),
        User(username="kasa2", password=get_password_hash("kasa2-pass"), role="kasa2"),
    ])
    db_session.commit()


def test_create_queue_item_via_api(client: TestClient, db_session):
    """Перевіряє створення талона через публічний/касовий API ендпоінт."""
    app.dependency_overrides[verify_kasa1] = lambda: True
    try:
        payload = {
            "phone": "+380991234567",
            "shoe_sizes": ["38", "39"],
            "duration_minutes": 60,
            "comment": "Тестовий візит",
        }
        response = client.post("/api/queue", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["ticket_number"] >= 101
        assert data["people_count"] == 2
        assert data["shoe_sizes"] == ["38", "39"]
    finally:
        app.dependency_overrides.pop(verify_kasa1, None)


def test_mass_extend_unauthorized_fails(client: TestClient, db_session):
    """Перевіряє, що масове подовження сесій без коректних облікових даних адміністратора блокується (403)."""
    _seed_staff_users(db_session)
    app.dependency_overrides[verify_kasa2] = lambda: True
    try:
        payload = {"username": "admin", "password": "wrong_password", "minutes": 15}
        response = client.post("/api/queue/mass-extend", json=payload)
        assert response.status_code == 403
        assert "Невірний логін або пароль адміністратора" in response.json().get("detail", "")
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
            status=QueueStatus.WAITING,
        )
        db_session.add(ticket)
        db_session.commit()

        response = client.post(f"/api/queue/{ticket.id}/cancel", json={"reason": "ні"})
        assert response.status_code in [400, 422]
    finally:
        app.dependency_overrides.pop(verify_kasa2, None)


def test_login_trims_username_and_pages_have_no_store_header(client: TestClient, db_session):
    _seed_staff_users(db_session)
    login_res = client.post("/api/login", json={"username": "  admin  ", "password": "admin-pass"})
    assert login_res.status_code == 200
    assert login_res.json()["username"] == "admin"

    for path in ["/", "/staff", "/kasa1", "/kasa2"]:
        page_res = client.get(path)
        assert page_res.status_code == 200
        assert "no-store" in page_res.headers.get("cache-control", "")


def test_users_crud_redirects_with_users_modal_param(client: TestClient, db_session):
    _seed_staff_users(db_session)
    login_as(client, "admin", "admin-pass")

    create_res = client.post(
        "/users/create",
        data={"username": "  cashier_test  ", "password": "pw1", "role": "kasa2"},
        follow_redirects=False,
    )
    assert create_res.status_code == 303
    assert create_res.headers["location"] == "/staff?users_modal=1"

    created_user = db_session.query(User).filter(User.username == "cashier_test").first()
    assert created_user is not None

    edit_res = client.post(
        f"/users/{created_user.id}/edit",
        data={"username": "cashier_edited", "password": "", "role": "kasa1"},
        follow_redirects=False,
    )
    assert edit_res.status_code == 303
    assert edit_res.headers["location"] == "/staff?users_modal=1"

    delete_res = client.post(f"/users/{created_user.id}/delete", follow_redirects=False)
    assert delete_res.status_code == 303
    assert delete_res.headers["location"] == "/staff?users_modal=1"
    assert db_session.query(User).filter(User.id == created_user.id).first() is None


def test_mass_extend_success_handles_calling_without_called_at(client: TestClient, db_session):
    _seed_staff_users(db_session)
    app.dependency_overrides[verify_kasa2] = lambda: True
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        served = QueueItem(
            ticket_number=310,
            phone="380991110000",
            people_count=1,
            shoe_sizes=["36"],
            duration_minutes=60,
            status=QueueStatus.SERVED,
            session_start=now,
            session_end=now + timedelta(minutes=60),
        )
        calling = QueueItem(
            ticket_number=311,
            phone="380992220000",
            people_count=1,
            shoe_sizes=["37"],
            duration_minutes=60,
            status=QueueStatus.CALLING,
            called_at=None,
        )
        db_session.add_all([served, calling])
        db_session.commit()

        res = client.post(
            "/api/queue/mass-extend",
            json={"username": "admin", "password": "admin-pass", "minutes": 20},
        )
        assert res.status_code == 200
        assert res.json() == {"status": "success", "updated_count": 2}

        db_session.refresh(served)
        db_session.refresh(calling)
        assert served.duration_minutes == 80
        assert calling.called_at is not None
    finally:
        app.dependency_overrides.pop(verify_kasa2, None)