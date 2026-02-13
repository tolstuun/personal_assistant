"""Operations routes for Admin UI."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select

from src.admin.auth import require_auth
from src.admin.templates_config import templates
from src.core.models.job_runs import JobRun
from src.core.models.security_digest import Article, Digest
from src.core.services.settings import SettingsService
from src.core.storage.postgres import get_db
from src.core.utils.time import utcnow_naive
from src.workers.daily_digest_worker import compute_next_run_utc

router = APIRouter()


@router.get("/operations", response_class=HTMLResponse)
async def operations(
    request: Request,
    _: bool = Depends(require_auth),
) -> HTMLResponse:
    """
    Display operations page with recent job runs.

    Shows the latest fetch cycle status, digest scheduler status,
    and a table of recent job runs.
    """
    db = await get_db()
    settings = SettingsService()

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

        # Get latest digest_scheduler run
        latest_scheduler_stmt = (
            select(JobRun)
            .where(JobRun.job_name == "digest_scheduler")
            .order_by(JobRun.started_at.desc())
            .limit(1)
        )
        result = await session.execute(latest_scheduler_stmt)
        latest_scheduler_run = result.scalar_one_or_none()

        # Get latest digest
        latest_digest_stmt = (
            select(Digest)
            .order_by(Digest.created_at.desc())
            .limit(1)
        )
        result = await session.execute(latest_digest_stmt)
        latest_digest = result.scalar_one_or_none()

        # Count articles in latest digest (explicit query to avoid lazy-load)
        digest_article_count = 0
        if latest_digest is not None:
            count_stmt = (
                select(func.count())
                .select_from(Article)
                .where(Article.digest_id == latest_digest.id)
            )
            result = await session.execute(count_stmt)
            digest_article_count = result.scalar_one()

        # Get last 20 job runs overall
        recent_stmt = (
            select(JobRun)
            .order_by(JobRun.started_at.desc())
            .limit(20)
        )
        result = await session.execute(recent_stmt)
        recent_runs = result.scalars().all()

    # Read digest settings
    try:
        digest_time = await settings.get("digest_time")
    except Exception:
        digest_time = "08:00"

    try:
        telegram_notifications = await settings.get("telegram_notifications")
    except Exception:
        telegram_notifications = True

    # Compute next scheduled run
    now = utcnow_naive()
    next_run = compute_next_run_utc(now, digest_time)

    return templates.TemplateResponse(
        "operations.html",
        {
            "request": request,
            "latest_fetch": latest_fetch,
            "recent_runs": recent_runs,
            "digest_time": digest_time,
            "telegram_notifications": telegram_notifications,
            "next_digest_run": next_run,
            "latest_digest": latest_digest,
            "digest_article_count": digest_article_count,
            "latest_scheduler_run": latest_scheduler_run,
        },
    )
