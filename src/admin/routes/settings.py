"""Settings management routes for Admin UI."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, Response

from src.admin.auth import require_auth
from src.admin.templates_config import templates
from src.core.services.settings import SettingsService

router = APIRouter(prefix="/settings")


@router.get("", response_class=HTMLResponse)
async def list_settings(
    request: Request,
    _: bool = Depends(require_auth),
) -> HTMLResponse:
    """
    List all settings.

    Args:
        request: FastAPI request.

    Returns:
        Settings list page HTML.
    """
    service = SettingsService()
    settings = await service.get_all()

    return templates.TemplateResponse(
        "settings/list.html",
        {
            "request": request,
            "settings": settings,
        },
    )


@router.post("/{key}")
async def update_setting(
    request: Request,
    key: str,
    _: bool = Depends(require_auth),
    value: str = Form(None),
    value_bool: str = Form(None),
    value_list: list[str] = Form(None),
) -> Response:
    """
    Update a setting value.

    Handles different input types based on the setting type.

    Args:
        request: FastAPI request.
        key: Setting key.
        value: Value for text/number/time settings.
        value_bool: Value for boolean settings ("true" or "false").
        value_list: Values for multiselect settings.

    Returns:
        Updated setting row HTML for HTMX swap.
    """
    service = SettingsService()

    # Get setting type to determine how to parse the value
    all_settings = await service.get_all()
    if key not in all_settings:
        return Response(status_code=404, content="Setting not found")

    setting_type = all_settings[key]["type"]

    try:
        # Parse value based on type
        if setting_type == "number":
            parsed_value = int(value) if value else None
        elif setting_type == "time":
            parsed_value = value
        elif setting_type == "boolean":
            parsed_value = value_bool == "true"
        elif setting_type == "multiselect":
            parsed_value = value_list if value_list else []
        else:
            parsed_value = value

        if parsed_value is None and setting_type != "multiselect":
            return Response(status_code=400, content="Value required")

        await service.set(key, parsed_value)

        # Return updated row for HTMX swap
        updated_settings = await service.get_all()
        return templates.TemplateResponse(
            "settings/_setting_row.html",
            {
                "request": request,
                "key": key,
                "setting": updated_settings[key],
            },
        )

    except ValueError as e:
        return Response(status_code=400, content=str(e))
    except KeyError as e:
        return Response(status_code=404, content=str(e))


@router.delete("/{key}")
async def reset_setting(
    request: Request,
    key: str,
    _: bool = Depends(require_auth),
) -> Response:
    """
    Reset a setting to its default value.

    Args:
        request: FastAPI request.
        key: Setting key.

    Returns:
        Updated setting row HTML for HTMX swap.
    """
    service = SettingsService()

    try:
        await service.reset(key)

        # Return updated row for HTMX swap
        updated_settings = await service.get_all()
        return templates.TemplateResponse(
            "settings/_setting_row.html",
            {
                "request": request,
                "key": key,
                "setting": updated_settings[key],
            },
        )

    except KeyError as e:
        return Response(status_code=404, content=str(e))
