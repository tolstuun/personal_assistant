"""Operations routes for Admin UI."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from src.admin.auth import require_auth
from src.admin.templates_config import templates
from src.core.models.job_runs import JobRun
from src.core.storage.postgres import get_db

router = APIRouter()


@router.get("/operations", response_class=HTMLResponse)
async def operations(
    request: Request,
    _: bool = Depends(require_auth),
) -> HTMLResponse:
    """
    Display operations page with recent job runs.

    Shows the latest fetch cycle status and a table of recent job runs.
    """
    db = await get_db()

    async with db.session() as session:
        # Get latest fetch_cycle run
        latest_fetch_stmt = (
            select(JobRun)
            .where(JobRun.job_name == "fetch_cycle")
            .order_by(JobRun.started_at.desc())
            .limit(1)
        )
        result = await session.execute(latest_fetch_stmt)
        latest_fetch = result.scalar_one_or_none()

        # Get last 20 job runs overall
        recent_stmt = (
            select(JobRun)
            .order_by(JobRun.started_at.desc())
            .limit(20)
        )
        result = await session.execute(recent_stmt)
        recent_runs = result.scalars().all()

    return templates.TemplateResponse(
        "operations.html",
        {
            "request": request,
            "latest_fetch": latest_fetch,
            "recent_runs": recent_runs,
        },
    )
