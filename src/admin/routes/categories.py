"""Category management routes for Admin UI."""

import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.admin.auth import require_auth
from src.admin.templates_config import templates
from src.core.models import Category
from src.core.storage.postgres import get_db

router = APIRouter(prefix="/categories")

# Valid digest sections
DIGEST_SECTIONS = ["security_news", "product_news", "market"]


@router.get("", response_class=HTMLResponse)
async def list_categories(
    request: Request,
    _: bool = Depends(require_auth)
) -> HTMLResponse:
    """
    List all categories.

    Args:
        request: FastAPI request.

    Returns:
        Categories list page HTML.
    """
    db = await get_db()

    async with db.session() as session:
        stmt = (
            select(Category)
            .options(selectinload(Category.sources))
            .order_by(Category.name)
        )
        result = await session.execute(stmt)
        categories = result.scalars().all()

    return templates.TemplateResponse(
        "categories/list.html",
        {
            "request": request,
            "categories": categories,
            "digest_sections": DIGEST_SECTIONS,
        }
    )


@router.get("/new", response_class=HTMLResponse)
async def new_category_form(
    request: Request,
    _: bool = Depends(require_auth)
) -> HTMLResponse:
    """
    Display new category form.

    Args:
        request: FastAPI request.

    Returns:
        New category form HTML.
    """
    return templates.TemplateResponse(
        "categories/form.html",
        {
            "request": request,
            "category": None,
            "digest_sections": DIGEST_SECTIONS,
        }
    )


@router.post("", response_class=HTMLResponse)
async def create_category(
    request: Request,
    name: str = Form(...),
    digest_section: str = Form(...),
    keywords: str = Form(""),
    _: bool = Depends(require_auth)
) -> HTMLResponse:
    """
    Create a new category.

    Args:
        request: FastAPI request.
        name: Category name.
        digest_section: Section in digest.
        keywords: Comma-separated keywords.

    Returns:
        Redirect to categories list or form with errors.
    """
    # Parse keywords
    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]

    db = await get_db()

    async with db.session() as session:
        category = Category(
            name=name,
            digest_section=digest_section,
            keywords=keyword_list,
        )
        session.add(category)
        await session.commit()

    # Return HTMX redirect
    return Response(
        status_code=200,
        headers={"HX-Redirect": "/admin/categories"}
    )


@router.get("/{category_id}/edit", response_class=HTMLResponse)
async def edit_category_form(
    request: Request,
    category_id: uuid.UUID,
    _: bool = Depends(require_auth)
) -> HTMLResponse:
    """
    Display edit category form.

    Args:
        request: FastAPI request.
        category_id: Category UUID.

    Returns:
        Edit category form HTML.
    """
    db = await get_db()

    async with db.session() as session:
        stmt = select(Category).where(Category.id == category_id)
        result = await session.execute(stmt)
        category = result.scalar_one_or_none()

        if not category:
            return Response(status_code=404, content="Category not found")

    return templates.TemplateResponse(
        "categories/form.html",
        {
            "request": request,
            "category": category,
            "digest_sections": DIGEST_SECTIONS,
        }
    )


@router.put("/{category_id}", response_class=HTMLResponse)
async def update_category(
    request: Request,
    category_id: uuid.UUID,
    name: str = Form(...),
    digest_section: str = Form(...),
    keywords: str = Form(""),
    _: bool = Depends(require_auth)
) -> HTMLResponse:
    """
    Update a category.

    Args:
        request: FastAPI request.
        category_id: Category UUID.
        name: Updated name.
        digest_section: Updated section.
        keywords: Updated comma-separated keywords.

    Returns:
        Updated category row HTML for HTMX swap.
    """
    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]

    db = await get_db()

    async with db.session() as session:
        stmt = (
            select(Category)
            .options(selectinload(Category.sources))
            .where(Category.id == category_id)
        )
        result = await session.execute(stmt)
        category = result.scalar_one_or_none()

        if not category:
            return Response(status_code=404, content="Category not found")

        category.name = name
        category.digest_section = digest_section
        category.keywords = keyword_list
        await session.commit()

        # Refresh to get updated data
        await session.refresh(category)

    return templates.TemplateResponse(
        "categories/_row.html",
        {"request": request, "category": category}
    )


@router.delete("/{category_id}")
async def delete_category(
    category_id: uuid.UUID,
    _: bool = Depends(require_auth)
) -> Response:
    """
    Delete a category.

    Args:
        category_id: Category UUID.

    Returns:
        Empty response for HTMX (removes row).
    """
    db = await get_db()

    async with db.session() as session:
        stmt = select(Category).where(Category.id == category_id)
        result = await session.execute(stmt)
        category = result.scalar_one_or_none()

        if category:
            await session.delete(category)
            await session.commit()

    return Response(status_code=200, content="")
