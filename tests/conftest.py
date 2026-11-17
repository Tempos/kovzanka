import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db as db_module
import main as main_module
from app.db import get_db
from app.models import Base
from main import app

test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

db_module.engine = test_engine
db_module.SessionLocal = TestSessionLocal


@pytest.fixture(autouse=True)
def mock_telegram(monkeypatch):
    """Mock out telegram init/stop so tests don't try to connect to Telegram API."""
    monkeypatch.setattr(main_module, "init_telegram_bot", lambda: _async_noop())
    monkeypatch.setattr(main_module, "stop_telegram_bot", lambda: _async_noop())


async def _async_noop():
    pass


@pytest.fixture(autouse=True)
def db_session(mock_telegram):
    """Creates clean database tables for each test and drops them afterward."""
    Base.metadata.create_all(bind=test_engine)
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(autouse=True)
def override_dependency(db_session):
    """Overrides get_db in FastAPI to use the test session."""

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(db_session):
    """Returns a TestClient configured with test overrides and mocked lifespan."""
    return TestClient(app)
