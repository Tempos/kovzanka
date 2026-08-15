from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import Base, engine
from app.api import pages, queue

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Ice Rink Queue System API", version="1.0 MVP")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(queue.router)
app.include_router(pages.router)
