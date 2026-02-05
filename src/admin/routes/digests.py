"""Digest generation routes for Admin UI."""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from src.admin.auth import require_auth
from src.admin.templates_config import templates
from src.core.services.digest import DigestService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/digests")


@router.post("/generate", response_class=HTMLResponse)
async def generate_digest(
    request: Request,
    _: bool = Depends(require_auth),
) -> HTMLResponse:
    """
    Generate a digest from unprocessed articles.

    Returns an HTMX partial showing the result or error.

    Args:
        request: FastAPI request.

    Returns:
        HTML fragment with generation result.
    """
    service = DigestService()

    try:
        digest = await service.generate()

        return templates.TemplateResponse(
            "digests/_result.html",
            {
                "request": request,
                "success": True,
                "digest": digest,
            },
        )

    except ValueError as e:
        logger.warning(f"Digest generation failed: {e}")
        return templates.TemplateResponse(
            "digests/_result.html",
            {
                "request": request,
                "success": False,
                "error": str(e),
            },
        )

    except Exception as e:
        logger.error(f"Unexpected error generating digest: {e}")
        return templates.TemplateResponse(
            "digests/_result.html",
            {
                "request": request,
                "success": False,
                "error": "An unexpected error occurred. Check server logs.",
            },
        )
