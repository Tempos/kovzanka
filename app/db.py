import os
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

if mysql_host := os.getenv("MYSQL_HOST"):
    required_vars = ["MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE"]
    if missing := [var for var in required_vars if not os.getenv(var)]:
        raise RuntimeError(
            f"CRITICAL: MYSQL_HOST is set, but missing required MySQL environment variables: {', '.join(missing)}"
        )

    database_url = URL.create(
        "mysql+pymysql",
        username=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        host=mysql_host,
        port=int(os.getenv("MYSQL_PORT", "3306")),
        database=os.environ["MYSQL_DATABASE"],
        query={"charset": "utf8mb4"},
    )

    # Enforce TLS encryption and certificate verification
    ssl_args = {"ssl": {}}
    if ca_path := os.getenv("MYSQL_SSL_CA"):
        ssl_args["ssl"]["ca"] = ca_path

    engine = create_engine(database_url, pool_pre_ping=True, connect_args=ssl_args)
else:
    engine = create_engine("sqlite:///./ice_rink.db", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DBSession = Annotated[Session, Depends(get_db)]
