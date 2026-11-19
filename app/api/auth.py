import hashlib
import os
import secrets
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.limiter import limiter
from app.models import User

router = APIRouter(tags=["API Endpoints"])

# Session stores for each station
KASA1_SESSIONS = set()
KASA2_SESSIONS = set()
ADMIN_SESSIONS = set()


class RoleLoginRequest(BaseModel):
    password: str
    role: Optional[str] = None


@router.post("/api/login")
@limiter.limit("5/minute")
def login(data: RoleLoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    users = db.query(User).all()

    if not (user := next((u for u in users if verify_password(data.password, u.password_hash)), None)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невірний пароль")

    assigned_role = (user.role or "").strip().lower()
    session_token = secrets.token_hex(32)

    if assigned_role == "admin":
        ADMIN_SESSIONS.add(session_token)
        KASA1_SESSIONS.add(session_token)
        KASA2_SESSIONS.add(session_token)
        cookie_name = "admin_session"
    elif assigned_role in ("kasa1", "cashier1"):
        KASA1_SESSIONS.add(session_token)
        cookie_name = "kasa1_session"
    elif assigned_role in ("kasa2", "cashier2", "cashier"):
        KASA2_SESSIONS.add(session_token)
        cookie_name = "kasa2_session"
    else:
        # Безпечний дефолт для будь-яких інших ролей
        KASA2_SESSIONS.add(session_token)
        cookie_name = "kasa2_session"

    response.set_cookie(
        key=cookie_name,
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=os.getenv("COOKIE_SECURE", "true").lower() == "true",
        max_age=36000,
    )
    return {"status": "success", "role": assigned_role}


@router.get("/logout")
def logout_endpoint(
        request: Request,
        response: Response,
        kasa1_session: Optional[str] = Cookie(None),
        kasa2_session: Optional[str] = Cookie(None),
        admin_session: Optional[str] = Cookie(None),
):
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
    if admin_session:
        ADMIN_SESSIONS.discard(admin_session)

    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("kasa1_session")
    response.delete_cookie("kasa2_session")
    response.delete_cookie("admin_session")
    return response


def get_authenticated_roles(
        admin_session: Optional[str] = None,
        kasa1_session: Optional[str] = None,
        kasa2_session: Optional[str] = None,
) -> set[str]:
    roles: set[str] = set()
    if admin_session and admin_session in ADMIN_SESSIONS:
        roles.update({"admin", "kasa1", "kasa2"})
    if kasa1_session and kasa1_session in KASA1_SESSIONS:
        roles.add("kasa1")
    if kasa2_session and kasa2_session in KASA2_SESSIONS:
        roles.add("kasa2")
    return roles


def has_any_role(
        allowed_roles: set[str],
        admin_session: Optional[str] = None,
        kasa1_session: Optional[str] = None,
        kasa2_session: Optional[str] = None,
) -> bool:
    return bool(get_authenticated_roles(admin_session, kasa1_session, kasa2_session) & allowed_roles)


def build_role_context(
        admin_session: Optional[str] = None,
        kasa1_session: Optional[str] = None,
        kasa2_session: Optional[str] = None,
) -> dict:
    roles = get_authenticated_roles(admin_session, kasa1_session, kasa2_session)
    is_admin = "admin" in roles
    is_kasa2 = "kasa2" in roles and not is_admin
    is_kasa1 = "kasa1" in roles and not is_admin and not is_kasa2
    role = "admin" if is_admin else "kasa2" if is_kasa2 else "kasa1" if is_kasa1 else None

    return {
        "is_admin": is_admin,
        "is_kasa1": is_kasa1,
        "is_kasa2": is_kasa2,
        "role": role,
        "roles": roles,
    }


def is_authenticated_kasa1(kasa1_session: Optional[str] = None, admin_session: Optional[str] = None) -> bool:
    return "kasa1" in get_authenticated_roles(admin_session=admin_session, kasa1_session=kasa1_session)


def is_authenticated_kasa2(kasa2_session: Optional[str] = None, admin_session: Optional[str] = None) -> bool:
    return "kasa2" in get_authenticated_roles(admin_session=admin_session, kasa2_session=kasa2_session)


def is_authenticated_admin(admin_session: Optional[str] = None) -> bool:
    return "admin" in get_authenticated_roles(admin_session=admin_session)


# FastAPI dependencies
def verify_kasa1(kasa1_session: Optional[str] = Cookie(None), admin_session: Optional[str] = Cookie(None)):
    if not is_authenticated_kasa1(kasa1_session, admin_session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Необхідна авторизація Каси 1")


def verify_kasa2(kasa2_session: Optional[str] = Cookie(None), admin_session: Optional[str] = Cookie(None)):
    if not is_authenticated_kasa2(kasa2_session, admin_session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Необхідна авторизація Каси 2")


def verify_admin(admin_session: Optional[str] = Cookie(None)):
    if not is_authenticated_admin(admin_session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Необхідні права адміністратора")


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """Перевірка пароля через вбудований hashlib з унікальною сіллю"""
    try:
        if not stored_hash or "$" not in stored_hash:
            return False
        salt, pwd_hash = stored_hash.split("$", 1)
        check_hash = hashlib.sha256((salt + plain_password).encode("utf-8")).hexdigest()
        return check_hash == pwd_hash
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Генерація безпечного хешу з сіллю через hashlib"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${pwd_hash}"
