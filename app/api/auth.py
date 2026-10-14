import os

from fastapi import APIRouter, Response, Cookie, HTTPException

from app.schemas import LoginRequest

router = APIRouter()
WORKER_PIN = os.getenv("WORKER_PIN", "1234")


@router.post("/api/login")
def login(data: LoginRequest, response: Response):
    if data.pin == WORKER_PIN:
        # Set a secure, HTTP-Only session cookie valid for the active work day
        response.set_cookie(
            key="worker_session",
            value="authenticated_staff",
            httponly=True,
            samesite="lax",
            max_age=36000
        )
        return {"status": "success"}
    raise HTTPException(status_code=401, detail="Невірний пароль")


@router.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("worker_session")
    return {"status": "logged_out"}


def is_authenticated_worker(worker_session: str = Cookie(None)) -> bool:
    """Helper dependency to safely check if the active user is a worker"""
    return worker_session == "authenticated_staff"


def verify_worker(worker_session: str = Cookie(None)):
    """Dependency check to wrap around Kasa 1 and Kasa 2 routes"""
    if worker_session != "authenticated_staff":
        raise HTTPException(status_code=403, detail="Доступ заборонено")
    return True
