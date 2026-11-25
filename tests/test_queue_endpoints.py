from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.api.auth import verify_admin, verify_kasa2
from app.models import QueueItem, QueueStatus, SkateInventory
from main import app


def test_extend_and_revert_via_api(client: TestClient, db_session):
    app.dependency_overrides[verify_kasa2] = lambda: True
    try:
        now = datetime.now(timezone.utc)
        item = QueueItem(
            ticket_number=401,
            phone="380991234567",
            people_count=1,
            shoe_sizes=["36 (фігурні)"],
            status=QueueStatus.SERVED,
            duration_minutes=60,
            session_start=now,
            session_end=now + timedelta(minutes=65),
        )
        db_session.add(item)
        db_session.commit()

        ext_res = client.patch(f"/api/queue/{item.id}/extend", json={"minutes": 15})
        assert ext_res.status_code == 200
        assert ext_res.json()["duration_minutes"] == 75

        rev1_res = client.post(f"/api/queue/{item.id}/revert")
        assert rev1_res.status_code == 200
        assert rev1_res.json()["status"] == QueueStatus.CALLING.value

        rev2_res = client.post(f"/api/queue/{item.id}/revert")
        assert rev2_res.status_code == 200
        assert rev2_res.json()["status"] == QueueStatus.WAITING.value
    finally:
        app.dependency_overrides.pop(verify_kasa2, None)


def test_issue_status_set_and_clear_note(client: TestClient, db_session):
    app.dependency_overrides[verify_kasa2] = lambda: True
    try:
        item = QueueItem(
            ticket_number=402,
            phone="380991234568",
            people_count=1,
            shoe_sizes=["38 (фігурні)"],
            status=QueueStatus.WAITING,
        )
        db_session.add(item)
        db_session.commit()

        set_res = client.patch(
            f"/api/queue/{item.id}/issue",
            json={"issue_status": "warning", "issue_note": "  Заміна пари  "},
        )
        assert set_res.status_code == 200
        assert set_res.json()["issue_status"] == "warning"
        assert set_res.json()["issue_note"] == "Заміна пари"

        clear_res = client.patch(
            f"/api/queue/{item.id}/issue",
            json={"issue_status": None, "issue_note": "Ignored"},
        )
        assert clear_res.status_code == 200
        assert clear_res.json()["issue_status"] is None
        assert clear_res.json()["issue_note"] is None
    finally:
        app.dependency_overrides.pop(verify_kasa2, None)


def test_patch_inventory_blocks_below_in_use(client: TestClient, db_session):
    app.dependency_overrides[verify_admin] = lambda: True
    try:
        db_session.add(SkateInventory(size="39 (фігурні)", total_stock=3, maintenance_count=0, is_deleted=False))
        db_session.add(
            QueueItem(
                ticket_number=403,
                phone="380991234569",
                people_count=2,
                shoe_sizes=["39 (фігурні)", "39 (фігурні)"],
                status=QueueStatus.SERVED,
                duration_minutes=60,
            )
        )
        db_session.commit()

        res = client.patch("/api/inventory", json={"size": "39 (фігурні)", "total_stock": 1})
        assert res.status_code == 400
    finally:
        app.dependency_overrides.pop(verify_admin, None)
