"""Jinja2 templates instance — separate module to avoid circular imports."""
from pathlib import Path
from fastapi.templating import Jinja2Templates

templates_dir = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))
