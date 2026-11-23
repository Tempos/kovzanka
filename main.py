from contextlib import asynccontextmanager

from dotenv import load_dotenv
from sqlalchemy import inspect, text

from app.api import auth, inventory, pages, queue, status
from app.api.auth import get_password_hash
from app.bot import init_telegram_bot, stop_telegram_bot
from app.inventory import init_inventory_db
from app.models import User

load_dotenv()
from fastapi.staticfiles import StaticFiles

from app.db import engine, SessionLocal
from app.models import Base
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter
from fastapi import Cookie, FastAPI, HTTPException, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse
import os


def ensure_columns():
    inspector = inspect(engine)
    queue_columns = inspector.get_columns("queue")
    columns = [col["name"] for col in queue_columns]

    with engine.begin() as conn:
        # Queue registration supports guests without a phone number. Existing
        # MySQL installations may still have the original NOT NULL definition
        # because SQLAlchemy create_all() does not alter existing columns.
        phone_column = next((col for col in queue_columns if col["name"] == "phone"), None)
        if phone_column and not phone_column["nullable"] and engine.dialect.name == "mysql":
            conn.execute(text("ALTER TABLE queue MODIFY COLUMN phone TEXT NULL;"))
            print("[DB MIGRATION] Колонка phone у таблиці queue тепер допускає NULL.")

        if "issue_status" not in columns:
            conn.execute(text("ALTER TABLE queue ADD COLUMN issue_status VARCHAR(64) DEFAULT NULL;"))
            print("[DB MIGRATION] Додано колонку issue_status до таблиці queue.")

        if "issue_note" not in columns:
            conn.execute(text("ALTER TABLE queue ADD COLUMN issue_note TEXT DEFAULT NULL;"))
            print("[DB MIGRATION] Додано колонку issue_note до таблиці queue.")


def init_default_users(db: SessionLocal):
    default_users = [
        {"username": "admin", "role": "admin", "password": os.getenv("ADMIN_PIN", "0000")},
        {"username": "kasa1", "role": "kasa1", "password": os.getenv("KASA1_PIN", "1111")},
        {"username": "kasa2", "role": "kasa2", "password": os.getenv("KASA2_PIN", "2222")}
    ]
    for user_data in default_users:
        existing = db.query(User).filter(User.username == user_data["username"]).first()
        if not existing:
            hashed_password = get_password_hash(user_data["password"])
            new_user = User(username=user_data["username"], password_hash=hashed_password, role=user_data["role"])
            db.add(new_user)
    db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_columns()

    db = SessionLocal()
    try:
        init_inventory_db(db)
        init_default_users(db)
    finally:
        db.close()
    await init_telegram_bot()
    yield
    await stop_telegram_bot()


app = FastAPI(
    title="Ice Rink Queue System API",
    version="1.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/openapi.json", include_in_schema=False)
def get_openapi_endpoint(admin_session: str = Cookie(None)):
    if not auth.is_authenticated_kasa2(admin_session):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return get_openapi(title=app.title, version=app.version, routes=app.routes)


# Custom Protected Swagger UI Docs
@app.get("/docs", include_in_schema=False)
def custom_swagger_ui(request: Request, admin_session: str = Cookie(None), ):
    if not auth.is_authenticated_kasa2(admin_session):
        return RedirectResponse(url="/login?next=/docs", status_code=303)
    return get_swagger_ui_html(openapi_url="/openapi.json", title="API Docs - Персонал")


# Attach limiter to app state and exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

for item in [auth, inventory, pages, queue, status]:
    app.include_router(item.router)
