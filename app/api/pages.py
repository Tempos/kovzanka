from fastapi import APIRouter, Request, Cookie
from fastapi.responses import FileResponse, RedirectResponse

from app.api.auth import is_authenticated_worker

router = APIRouter(tags=["UI Pages"])


@router.get("/")
def read_root():
    return FileResponse("static/index.html")


@router.get("/kasa1")
def kasa1_page(worker_session: str = Cookie(None)):
    if not is_authenticated_worker(worker_session):
        return RedirectResponse(url="/login", status_code=303)
    return FileResponse("static/kasa1.html")


@router.get("/kasa2")
def kasa2_page(worker_session: str = Cookie(None)):
    if not is_authenticated_worker(worker_session):
        return RedirectResponse(url="/login", status_code=303)
    return FileResponse("static/kasa2.html")


@router.get("/display")
def display_page():
    return FileResponse("static/display.html")


@router.get("/inventory")
def inventory_page(request: Request, worker_session: str = Cookie(None)):
    if not is_authenticated_worker(worker_session):
        return RedirectResponse(url="/login?next=/inventory", status_code=303)
    return FileResponse("static/inventory.html")


@router.get("/status")
def status_page():
    return FileResponse("static/status.html")


@router.get("/login")
def login_page():
    return FileResponse("static/login.html")
