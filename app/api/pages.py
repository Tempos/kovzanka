from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.auth import get_password_hash, is_authenticated_admin, is_authenticated_kasa1, is_authenticated_kasa2
from app.db import get_db
from app.models import User

router = APIRouter(tags=["UI Pages"])
templates = Jinja2Templates(directory="static")


@router.get("/")
def read_root():
    return FileResponse("static/index.html")


@router.get("/display")
def display_page():
    return FileResponse("static/display.html")


@router.get("/inventory")
def inventory_page(request: Request, admin_session: str = Cookie(None), kasa2_session: str = Cookie(None)):
    is_admin = is_authenticated_admin(admin_session) or is_authenticated_kasa2(kasa2_session)
    return templates.TemplateResponse(request, "inventory.html", {"is_admin": is_admin})


@router.get("/kasa1")
def kasa1_page(request: Request, kasa1_session: str = Cookie(None), admin_session: str = Cookie(None)):
    if not (is_authenticated_kasa1(kasa1_session) or is_authenticated_admin(admin_session)):
        return RedirectResponse(url="/login?role=kasa1&next=/kasa1", status_code=303)

    is_admin = is_authenticated_admin(admin_session)
    is_kasa1 = is_authenticated_kasa1(kasa1_session) and not is_admin

    return templates.TemplateResponse(
        request=request,
        name="kasa1.html",
        context={"is_admin": is_admin, "is_kasa1": is_kasa1, "is_kasa2": False}
    )


@router.get("/kasa2")
def kasa2_page(request: Request, kasa2_session: str = Cookie(None), admin_session: str = Cookie(None)):
    if not (is_authenticated_kasa2(kasa2_session) or is_authenticated_admin(admin_session)):
        return RedirectResponse(url="/login?role=kasa2&next=/kasa2", status_code=303)

    is_admin = is_authenticated_admin(admin_session)
    is_kasa2 = is_authenticated_kasa2(kasa2_session) and not is_admin

    return templates.TemplateResponse(
        request=request,
        name="kasa2.html",
        context={"is_admin": is_admin, "is_kasa2": is_kasa2, "is_kasa2": False}
    )


@router.get("/staff")
def staff_page(request: Request, kasa1_session: str = Cookie(None), kasa2_session: str = Cookie(None),
               admin_session: str = Cookie(None), db: Session = Depends(get_db)):
    if not (is_authenticated_kasa1(kasa1_session) or is_authenticated_kasa2(kasa2_session) or is_authenticated_admin(
            admin_session)):
        return RedirectResponse(url="/login?next=/staff", status_code=303)

    is_admin = is_authenticated_admin(admin_session)
    is_kasa2 = is_authenticated_kasa2(kasa2_session) and not is_admin
    is_kasa1 = is_authenticated_kasa1(kasa1_session) and not is_admin
    users = db.query(User).all() if is_admin else []

    return templates.TemplateResponse(
        request=request,
        name="staff.html",
        context={"is_admin": is_admin, "is_kasa2": is_kasa2, "is_kasa1": is_kasa1, "users": users}
    )


@router.get("/status")
def status_page():
    return FileResponse("static/status.html")


@router.get("/login")
def login_page():
    return FileResponse("static/login.html")


@router.post("/users/create")
def create_user(
        username: str = Form(...), password: str = Form(...), role: str = Form("kasa2"), db: Session = Depends(get_db)
):
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Користувач з таким логіном вже існує")

    hashed_password = get_password_hash(password)
    new_user = User(username=username, password_hash=hashed_password, role=role)
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/users/{user_id}/edit")
def edit_user(user_id: int, username: str = Form(...), password: str = Form(None), role: str = Form(...),
              db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Користувача не знайдено")

    user.username = username
    user.role = role
    if password and password.strip():
        user.password_hash = get_password_hash(password)

    db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/users/{user_id}/delete")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    if user := db.query(User).filter(User.id == user_id).first():
        db.delete(user)
        db.commit()
    return RedirectResponse(url="/admin", status_code=303)
