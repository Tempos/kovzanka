from fastapi.testclient import TestClient

from app.api.auth import get_password_hash
from app.models import QueueItem, QueueStatus, SkateInventory, User
from tests.conftest import login_as


def _seed_users_and_stock(db_session):
    db_session.add_all([
        User(username="admin", password=get_password_hash("admin-pass"), role="admin"),
        User(username="kasa2", password=get_password_hash("kasa2-pass"), role="kasa2"),
        SkateInventory(size="38 (фігурні)", total_stock=5, maintenance_count=1, is_deleted=False),
    ])
    db_session.commit()


def test_kasa2_cannot_modify_inventory_or_see_maintenance_count(client: TestClient, db_session):
    _seed_users_and_stock(db_session)
    login_as(client, "kasa2", "kasa2-pass")

    create_res = client.post(
        "/api/inventory",
        json={"size": "40", "category": "figure", "total_stock": 3, "maintenance_count": 0},
    )
    assert create_res.status_code == 401

    patch_res = client.patch(
        "/api/inventory",
        json={"size": "38 (фігурні)", "total_stock": 6},
    )
    assert patch_res.status_code == 401

    delete_res = client.delete("/api/inventory", params={"size": "38 (фігурні)"})
    assert delete_res.status_code == 401

    get_res = client.get("/api/inventory")
    assert get_res.status_code == 200
    assert "maintenance_count" not in get_res.json()["38 (фігурні)"]


def test_admin_can_create_update_and_delete_inventory(client: TestClient, db_session):
    _seed_users_and_stock(db_session)
    login_as(client, "admin", "admin-pass")

    get_res = client.get("/api/inventory")
    assert get_res.status_code == 200
    assert get_res.json()["38 (фігурні)"]["maintenance_count"] == 1

    create_res = client.post(
        "/api/inventory",
        json={"size": "40", "category": "figure", "total_stock": 4, "maintenance_count": 0},
    )
    assert create_res.status_code == 200
    assert create_res.json()["size"] == "40 (фігурні)"

    patch_res = client.patch(
        "/api/inventory",
        json={"size": "38 (фігурні)", "total_stock": 4},
    )
    assert patch_res.status_code == 200
    assert client.get("/api/inventory").json()["38 (фігурні)"]["total"] == 4


def test_admin_cannot_lower_total_stock_below_in_use(client: TestClient, db_session):
    _seed_users_and_stock(db_session)
    db_session.add(
        QueueItem(
            ticket_number=501,
            phone="380991234567",
            people_count=2,
            shoe_sizes=["38 (фігурні)", "38 (фігурні)"],
            status=QueueStatus.SERVED,
            duration_minutes=60,
        )
    )
    db_session.commit()
    login_as(client, "admin", "admin-pass")

    res = client.patch("/api/inventory", json={"size": "38 (фігурні)", "total_stock": 1})
    assert res.status_code == 400
