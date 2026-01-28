"""Dashboard routes for Admin UI."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select

from src.admin.auth import require_auth
from src.admin.templates_config import templates
from src.core.models import Category, Source
from src.core.storage.postgres import get_db

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    _: bool = Depends(require_auth)
) -> HTMLResponse:
    """
    Display dashboard with overview of categories and sources.

    Args:
        request: FastAPI request.

    Returns:
        Dashboard page HTML.
    """
    db = await get_db()

    async with db.session() as session:
        # Get categories with source counts
        stmt = (
            select(
                Category,
                func.count(Source.id).label("source_count")
            )
            .outerjoin(Source, Category.id == Source.category_id)
            .group_by(Category.id)
            .order_by(Category.name)
        )
        result = await session.execute(stmt)
        categories_with_counts = result.all()

        # Get total counts
        total_categories = len(categories_with_counts)

        sources_stmt = select(func.count(Source.id))
        total_sources = await session.scalar(sources_stmt) or 0

        enabled_stmt = select(func.count(Source.id)).where(Source.enabled == True)  # noqa: E712
        enabled_sources = await session.scalar(enabled_stmt) or 0

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "categories": categories_with_counts,
            "total_categories": total_categories,
            "total_sources": total_sources,
            "enabled_sources": enabled_sources,
        }
    )
