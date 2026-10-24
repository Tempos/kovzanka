from dotenv import load_dotenv

load_dotenv()
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import auth, pages, queue
from app.db import engine
from app.models import Base
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Ice Rink Queue System API", version="1.0")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Attach limiter to app state and exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

for item in [auth, pages, queue]:
    app.include_router(item.router)
