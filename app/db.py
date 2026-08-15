from typing import Annotated
from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

DATABASE_URL = "sqlite:///./ice_rink.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DBSession = Annotated[Session, Depends(get_db)]
