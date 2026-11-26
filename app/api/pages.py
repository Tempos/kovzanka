from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.auth import build_role_context, get_password_hash, has_any_role, verify_admin
from app.db import get_db
from app.models import User

router = APIRouter(tags=["UI Pages"])
templates = Jinja2Templates(directory="static")

ALLOWED_USER_ROLES = {"admin", "kasa1", "kasa2"}


def _render_page(
        request: Request,
        name: str,
        admin_session: Optional[str],
        kasa1_session: Optional[str],
        kasa2_session: Optional[str],
        *,
        required_roles: Optional[set[str]] = None,
        login_redirect: str = "/login",
        extra_context: Optional[dict] = None,
):
    if required_roles and not has_any_role(required_roles, admin_session, kasa1_session, kasa2_session):
        return RedirectResponse(url=login_redirect, status_code=303)

    context = build_role_context(admin_session, kasa1_session, kasa2_session)
    if extra_context:
        context.update(extra_context)

    response = templates.TemplateResponse(request=request, name=name, context=context)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@router.get("/")
def read_root(
        request: Request,
        admin_session: Optional[str] = Cookie(None),
        kasa1_session: Optional[str] = Cookie(None),
        kasa2_session: Optional[str] = Cookie(None),
):
    return _render_page(request, "index.html", admin_session, kasa1_session, kasa2_session)


@router.get("/display")
def display_page(
        request: Request,
        admin_session: Optional[str] = Cookie(None),
        kasa1_session: Optional[str] = Cookie(None),
        kasa2_session: Optional[str] = Cookie(None),
):
    return _render_page(request, "display.html", admin_session, kasa1_session, kasa2_session)


@router.get("/inventory")
def inventory_page(
        request: Request,
        admin_session: Optional[str] = Cookie(None),
        kasa1_session: Optional[str] = Cookie(None),
        kasa2_session: Optional[str] = Cookie(None),
):
    return _render_page(
        request,
        "inventory.html",
        admin_session,
        kasa1_session,
        kasa2_session,
        required_roles={"admin", "kasa1", "kasa2"},
        login_redirect="/login?next=/inventory",
    )


@router.get("/kasa1")
def kasa1_page(
        request: Request,
        kasa1_session: Optional[str] = Cookie(None),
        kasa2_session: Optional[str] = Cookie(None),
        admin_session: Optional[str] = Cookie(None),
):
    return _render_page(
        request,
        "kasa1.html",
        admin_session,
        kasa1_session,
        kasa2_session,
        required_roles={"kasa1", "admin"},
        login_redirect="/login?role=kasa1&next=/kasa1",
    )


@router.get("/kasa2")
def kasa2_page(
        request: Request,
        kasa1_session: Optional[str] = Cookie(None),
        kasa2_session: Optional[str] = Cookie(None),
        admin_session: Optional[str] = Cookie(None),
):
    return _render_page(
        request,
        "kasa2.html",
        admin_session,
        kasa1_session,
        kasa2_session,
        required_roles={"kasa2", "admin"},
        login_redirect="/login?role=kasa2&next=/kasa2",
    )


@router.get("/staff")
def staff_page(
        request: Request,
        kasa1_session: Optional[str] = Cookie(None),
        kasa2_session: Optional[str] = Cookie(None),
        admin_session: Optional[str] = Cookie(None),
        db: Session = Depends(get_db),
):
    ctx = build_role_context(admin_session, kasa1_session, kasa2_session)
    if not (ctx["is_admin"] or ctx["is_kasa1"] or ctx["is_kasa2"]):
        return RedirectResponse(url="/login?next=/staff", status_code=303)

    users = db.query(User).all() if ctx["is_admin"] else []
    return _render_page(
        request,
        "staff.html",
        admin_session,
        kasa1_session,
        kasa2_session,
        extra_context={"users": users},
    )


@router.get("/status")
def status_page(
        request: Request,
        admin_session: Optional[str] = Cookie(None),
        kasa1_session: Optional[str] = Cookie(None),
        kasa2_session: Optional[str] = Cookie(None),
):
    return _render_page(request, "status.html", admin_session, kasa1_session, kasa2_session)


@router.get("/login")
def login_page(
        request: Request,
        admin_session: Optional[str] = Cookie(None),
        kasa1_session: Optional[str] = Cookie(None),
        kasa2_session: Optional[str] = Cookie(None),
):
    return _render_page(request, "login.html", admin_session, kasa1_session, kasa2_session)


@router.post("/users/create", dependencies=[Depends(verify_admin)])
def create_user(
        username: str = Form(...), password: str = Form(...), role: str = Form("kasa2"), db: Session = Depends(get_db)
):
    username = username.strip()
    role = role.strip().lower()
    if not username or not password:
        raise HTTPException(status_code=400, detail="Логін та пароль обов'язкові")
    if role not in ALLOWED_USER_ROLES:
        raise HTTPException(status_code=400, detail="Неприпустима роль користувача")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Користувач з таким логіном вже існує")

    password = get_password_hash(password)
    new_user = User(username=username, password=password, role=role)
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/staff?users_modal=1", status_code=303)


@router.post("/users/{user_id}/edit", dependencies=[Depends(verify_admin)])
def edit_user(
        user_id: int,
        username: str = Form(...),
        password: str = Form(None),
        role: str = Form(...),
        db: Session = Depends(get_db)
):
    if not (user := db.query(User).filter(User.id == user_id).first()):
        raise HTTPException(status_code=404, detail="Користувача не знайдено")
    if not (username := username.strip()):
        raise HTTPException(status_code=400, detail="Логін не може бути порожнім")
    if (role := role.strip().lower()) not in ALLOWED_USER_ROLES:
        raise HTTPException(status_code=400, detail="Неприпустима роль користувача")
    if db.query(User).filter(User.username == username, User.id != user_id).first():
        raise HTTPException(status_code=400, detail="Користувач з таким логіном вже існує")

    user.username = username
    user.role = role
    if password and password.strip():
        user.password = get_password_hash(password)

    db.commit()
    return RedirectResponse(url="/staff?users_modal=1", status_code=303)


@router.post("/users/{user_id}/delete", dependencies=[Depends(verify_admin)])
def delete_user(user_id: int, db: Session = Depends(get_db)):
    if user := db.query(User).filter(User.id == user_id).first():
        db.delete(user)
        db.commit()
    return RedirectResponse(url="/staff?users_modal=1", status_code=303)
