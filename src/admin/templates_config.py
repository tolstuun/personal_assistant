"""
Template configuration for Admin UI.

Provides a shared Jinja2Templates instance with the correct path.
"""

from pathlib import Path

from fastapi.templating import Jinja2Templates

# Get absolute path to templates directory
_templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))
