import os
import secrets
from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status
from pydantic import BaseModel
from starlette.responses import RedirectResponse

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


from urllib.parse import urlparse

@router.post("/logout")
def logout_endpoint(
    request: Request,
    response: Response,
    kasa1_session: Optional[str] = Cookie(None),
    kasa2_session: Optional[str] = Cookie(None),
):
    # Reject cross-site requests by verifying Origin or Referer matches the host
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    host = request.url.netloc

    is_same_origin = bool(
        origin
        and urlparse(origin).netloc == host
        or not origin
        and referer
        and urlparse(referer).netloc == host
    )
    if not is_same_origin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-site logout requests are not allowed")

    if kasa1_session:
        KASA1_SESSIONS.discard(kasa1_session)
    if kasa2_session:
        KASA2_SESSIONS.discard(kasa2_session)

    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("kasa1_session")
    response.delete_cookie("kasa2_session")
    return response


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
