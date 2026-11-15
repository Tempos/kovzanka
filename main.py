from contextlib import asynccontextmanager

from dotenv import load_dotenv

from app.api import auth, inventory, pages, queue, status
from app.bot import init_telegram_bot, stop_telegram_bot
from app.inventory import init_inventory_db

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

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        init_inventory_db(db)
    finally:
        db.close()

    await init_telegram_bot()
    yield
    await stop_telegram_bot()


app = FastAPI(title="Ice Rink Queue System API", version="1.0", lifespan=lifespan,
              docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/openapi.json", include_in_schema=False)
def get_openapi_endpoint(kasa1_session: str = Cookie(None), kasa2_session: str = Cookie(None)):
    session = kasa1_session or kasa2_session
    if not auth.is_authenticated_worker(session):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return get_openapi(title=app.title, version=app.version, routes=app.routes)


# 3. Custom Protected Swagger UI Docs
@app.get("/docs", include_in_schema=False)
def custom_swagger_ui(request: Request, kasa1_session: str = Cookie(None), kasa2_session: str = Cookie(None)):
    session = kasa1_session or kasa2_session
    if not auth.is_authenticated_worker(session):
        return RedirectResponse(url="/login?next=/docs", status_code=303)
    return get_swagger_ui_html(openapi_url="/openapi.json", title="API Docs - Персонал")


# Attach limiter to app state and exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

for item in [auth, inventory, pages, queue, status]:
    app.include_router(item.router)
