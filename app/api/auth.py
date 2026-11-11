import os
import secrets
from typing import Optional

from fastapi import APIRouter, Request, Response, Cookie, HTTPException, status
from pydantic import BaseModel

from app.limiter import limiter

router = APIRouter(tags=["API Endpoints"])

# Session stores for each station
KASA1_SESSIONS = set()
KASA2_SESSIONS = set()

KASA1_PIN = os.getenv("KASA1_PIN", "1111")
KASA2_PIN = os.getenv("KASA2_PIN", "2222")


class RoleLoginRequest(BaseModel):
    pin: str
    role: Optional[str] = None


@router.post("/api/login")
@limiter.limit("5/minute")
def login(data: RoleLoginRequest, request: Request, response: Response):
    session_token = secrets.token_hex(32)
    assigned_role = None

    # Determine role based on explicit request or matching PIN
    if data.role == "kasa1" and data.pin == KASA1_PIN:
        assigned_role = "kasa1"
    elif data.role == "kasa2" and data.pin == KASA2_PIN:
        assigned_role = "kasa2"
    elif not data.role:
        if data.pin == KASA1_PIN:
            assigned_role = "kasa1"
        elif data.pin == KASA2_PIN:
            assigned_role = "kasa2"

    if not assigned_role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невірний PIN-код")

    # Set appropriate cookie and session record
    if assigned_role == "kasa1":
        KASA1_SESSIONS.add(session_token)
        cookie_name = "kasa1_session"
    else:
        KASA2_SESSIONS.add(session_token)
        cookie_name = "kasa2_session"

    response.set_cookie(
        key=cookie_name,
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=os.getenv("COOKIE_SECURE", "true").lower() == "true",
        max_age=36000
    )
    return {"status": "success", "role": assigned_role}


@router.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("kasa1_session")
    response.delete_cookie("kasa2_session")
    return {"status": "logged_out"}


# Helper session checks
def is_authenticated_kasa1(kasa1_session: str = None) -> bool:
    return bool(kasa1_session and kasa1_session in KASA1_SESSIONS)


def is_authenticated_kasa2(kasa2_session: str = None) -> bool:
    return bool(kasa2_session and kasa2_session in KASA2_SESSIONS)


# FastAPI dependencies for backend endpoints
def verify_kasa1(kasa1_session: str = Cookie(None)):
    if not is_authenticated_kasa1(kasa1_session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Необхідна авторизація Каси 1 (Реєстрація)"
        )


def verify_kasa2(kasa2_session: str = Cookie(None)):
    if not is_authenticated_kasa2(kasa2_session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Необхідна авторизація Каси 2 (Видача)"
        )

def is_authenticated_worker(session: str) -> bool:
    return bool(session and (is_authenticated_kasa1(session) or is_authenticated_kasa2(session)))