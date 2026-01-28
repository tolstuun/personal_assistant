"""Source management routes for Admin UI."""

import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.admin.auth import require_auth
from src.admin.templates_config import templates
from src.core.models import Category, Source, SourceType
from src.core.storage.postgres import get_db

router = APIRouter(prefix="/sources")


@router.get("", response_class=HTMLResponse)
async def list_sources(
    request: Request,
    category_id: uuid.UUID | None = None,
    _: bool = Depends(require_auth)
) -> HTMLResponse:
    """
    List all sources, optionally filtered by category.

    Args:
        request: FastAPI request.
        category_id: Optional category filter.

    Returns:
        Sources list page HTML.
    """
    db = await get_db()

    async with db.session() as session:
        stmt = (
            select(Source)
            .options(selectinload(Source.category))
            .order_by(Source.name)
        )

        if category_id:
            stmt = stmt.where(Source.category_id == category_id)

        result = await session.execute(stmt)
        sources = result.scalars().all()

        # Get categories for filter dropdown
        cat_stmt = select(Category).order_by(Category.name)
        cat_result = await session.execute(cat_stmt)
        categories = cat_result.scalars().all()

    return templates.TemplateResponse(
        "sources/list.html",
        {
            "request": request,
            "sources": sources,
            "categories": categories,
            "selected_category_id": category_id,
            "source_types": [t.value for t in SourceType],
        }
    )


@router.get("/new", response_class=HTMLResponse)
async def new_source_form(
    request: Request,
    _: bool = Depends(require_auth)
) -> HTMLResponse:
    """
    Display new source form.

    Args:
        request: FastAPI request.

    Returns:
        New source form HTML.
    """
    db = await get_db()

    async with db.session() as session:
        stmt = select(Category).order_by(Category.name)
        result = await session.execute(stmt)
        categories = result.scalars().all()

    return templates.TemplateResponse(
        "sources/form.html",
        {
            "request": request,
            "source": None,
            "categories": categories,
            "source_types": [t.value for t in SourceType],
        }
    )


@router.post("")
async def create_source(
    request: Request,
    name: str = Form(...),
    url: str = Form(...),
    source_type: str = Form(...),
    category_id: str = Form(...),
    keywords: str = Form(""),
    fetch_interval_minutes: int = Form(60),
    enabled: str = Form(""),
    _: bool = Depends(require_auth)
) -> RedirectResponse:
    """
    Create a new source.

    Args:
        request: FastAPI request.
        name: Source name.
        url: Source URL.
        source_type: Type (website, twitter, reddit).
        category_id: Associated category UUID as string.
        keywords: Comma-separated keywords.
        fetch_interval_minutes: Fetch interval.
        enabled: Checkbox value ("true" or "").

    Returns:
        Redirect to sources list.
    """
    # Validate category_id
    if not category_id:
        # TODO: Show error message to user
        return RedirectResponse(url="/admin/sources/new", status_code=303)

    try:
        category_uuid = uuid.UUID(category_id)
    except ValueError:
        return RedirectResponse(url="/admin/sources/new", status_code=303)

    # Convert checkbox value to boolean
    is_enabled = enabled == "true"

    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]

    db = await get_db()

    async with db.session() as session:
        source = Source(
            name=name,
            url=url,
            source_type=SourceType(source_type),
            category_id=category_uuid,
            keywords=keyword_list,
            fetch_interval_minutes=fetch_interval_minutes,
            enabled=is_enabled,
        )
        session.add(source)
        await session.commit()

    return RedirectResponse(url="/admin/sources", status_code=303
    )


@router.get("/{source_id}/edit", response_class=HTMLResponse)
async def edit_source_form(
    request: Request,
    source_id: uuid.UUID,
    _: bool = Depends(require_auth)
) -> HTMLResponse:
    """
    Display edit source form.

    Args:
        request: FastAPI request.
        source_id: Source UUID.

    Returns:
        Edit source form HTML.
    """
    db = await get_db()

    async with db.session() as session:
        stmt = select(Source).where(Source.id == source_id)
        result = await session.execute(stmt)
        source = result.scalar_one_or_none()

        if not source:
            return Response(status_code=404, content="Source not found")

        cat_stmt = select(Category).order_by(Category.name)
        cat_result = await session.execute(cat_stmt)
        categories = cat_result.scalars().all()

    return templates.TemplateResponse(
        "sources/form.html",
        {
            "request": request,
            "source": source,
            "categories": categories,
            "source_types": [t.value for t in SourceType],
        }
    )


@router.post("/{source_id}")
async def update_source(
    request: Request,
    source_id: uuid.UUID,
    name: str = Form(...),
    url: str = Form(...),
    source_type: str = Form(...),
    category_id: str = Form(...),
    keywords: str = Form(""),
    fetch_interval_minutes: int = Form(60),
    enabled: str = Form(""),
    _: bool = Depends(require_auth)
) -> RedirectResponse:
    """
    Update a source via POST (HTML forms can't send PUT).

    Args:
        request: FastAPI request.
        source_id: Source UUID.
        name: Updated name.
        url: Updated URL.
        source_type: Updated type.
        category_id: Updated category UUID as string.
        keywords: Updated keywords.
        fetch_interval_minutes: Updated interval.
        enabled: Checkbox value ("true" or "").

    Returns:
        Redirect to sources list.
    """
    # Validate category_id
    if not category_id:
        return RedirectResponse(
            url=f"/admin/sources/{source_id}/edit", status_code=303
        )

    try:
        category_uuid = uuid.UUID(category_id)
    except ValueError:
        return RedirectResponse(
            url=f"/admin/sources/{source_id}/edit", status_code=303
        )

    # Convert checkbox value to boolean
    is_enabled = enabled == "true"

    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]

    db = await get_db()

    async with db.session() as session:
        stmt = (
            select(Source)
            .where(Source.id == source_id)
        )
        result = await session.execute(stmt)
        source = result.scalar_one_or_none()

        if not source:
            return RedirectResponse(url="/admin/sources", status_code=303)

        source.name = name
        source.url = url
        source.source_type = SourceType(source_type)
        source.category_id = category_uuid
        source.keywords = keyword_list
        source.fetch_interval_minutes = fetch_interval_minutes
        source.enabled = is_enabled
        await session.commit()

    return RedirectResponse(url="/admin/sources", status_code=303)


@router.post("/{source_id}/toggle")
async def toggle_source(
    request: Request,
    source_id: uuid.UUID,
    _: bool = Depends(require_auth)
) -> HTMLResponse:
    """
    Toggle source enabled status.

    Args:
        request: FastAPI request.
        source_id: Source UUID.

    Returns:
        Updated source row HTML.
    """
    db = await get_db()

    async with db.session() as session:
        stmt = (
            select(Source)
            .options(selectinload(Source.category))
            .where(Source.id == source_id)
        )
        result = await session.execute(stmt)
        source = result.scalar_one_or_none()

        if not source:
            return Response(status_code=404, content="Source not found")

        source.enabled = not source.enabled
        await session.commit()

        await session.refresh(source)

    return templates.TemplateResponse(
        "sources/_row.html",
        {"request": request, "source": source}
    )


@router.delete("/{source_id}")
async def delete_source(
    source_id: uuid.UUID,
    _: bool = Depends(require_auth)
) -> Response:
    """
    Delete a source.

    Args:
        source_id: Source UUID.

    Returns:
        Empty response for HTMX (removes row).
    """
    db = await get_db()

    async with db.session() as session:
        stmt = select(Source).where(Source.id == source_id)
        result = await session.execute(stmt)
        source = result.scalar_one_or_none()

        if source:
            await session.delete(source)
            await session.commit()

    return Response(status_code=200, content="")
