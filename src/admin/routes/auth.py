"""Authentication routes for Admin UI."""

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.admin.auth import (
    clear_session_cookie,
    create_session_cookie,
    verify_password,
)
from src.admin.templates_config import templates

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str | None = None) -> HTMLResponse:
    """
    Display login form.

    Args:
        request: FastAPI request.
        error: Optional error message to display.

    Returns:
        Login page HTML.
    """
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": error}
    )


@router.post("/login")
async def login(request: Request, password: str = Form(...)) -> RedirectResponse:
    """
    Process login form.

    Args:
        request: FastAPI request.
        password: Submitted password.

    Returns:
        Redirect to dashboard on success, back to login on failure.
    """
    if verify_password(password):
        response = RedirectResponse(url="/admin/", status_code=303)
        create_session_cookie(response)
        return response

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid password"},
        status_code=401
    )


@router.get("/logout")
async def logout() -> RedirectResponse:
    """
    Log out and clear session.

    Returns:
        Redirect to login page.
    """
    response = RedirectResponse(url="/admin/login", status_code=303)
    clear_session_cookie(response)
    return response
