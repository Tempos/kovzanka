import os
import secrets

from fastapi import APIRouter, Request, Response, Cookie, HTTPException, status

from app.limiter import limiter
from app.schemas import LoginRequest

router = APIRouter()

# In-memory active session store
ACTIVE_SESSIONS = set()
if not (WORKER_PIN := os.getenv("WORKER_PIN")):
    raise RuntimeError("Missing required environment variable: WORKER_PIN")


@router.post("/api/login")
@limiter.limit("5/minute")
def login(data: LoginRequest, request: Request, response: Response):
    if data.pin != WORKER_PIN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невірний PIN"
        )

    session_token = secrets.token_hex(32)
    ACTIVE_SESSIONS.add(session_token)

    response.set_cookie(
        key="worker_session",
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=True,
        max_age=36000
    )
    return {"status": "success"}


@router.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("worker_session")
    return {"status": "logged_out"}


def is_authenticated_worker(worker_session: str = Cookie(None)) -> bool:
    """Helper dependency to safely check if the active user is a worker"""
    return worker_session in ACTIVE_SESSIONS


def verify_worker(worker_session: str = Cookie(None)):
    if not is_authenticated_worker(worker_session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Необхідна авторизація працівника"
        )
