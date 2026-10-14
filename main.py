from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import auth, pages, queue
from app.db import engine
from app.models import Base

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Ice Rink Queue System API", version="1.0")
app.mount("/static", StaticFiles(directory="static"), name="static")

for item in [auth, pages, queue]:
    app.include_router(item.router)
