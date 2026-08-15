from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["UI Pages"])


@router.get("/")
def read_root():
    return FileResponse("static/index.html")


@router.get("/kasa1")
def kasa1_page():
    return FileResponse("static/kasa1.html")


@router.get("/kasa2")
def kasa2_page():
    return FileResponse("static/kasa2.html")


@router.get("/display")
def display_page():
    return FileResponse("static/display.html")


@router.get("/status")
def status_page():
    return FileResponse("static/status.html")