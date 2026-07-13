from __future__ import annotations

from .api import create_app
from .gateway import service

app = create_app(service)

__all__ = ["app"]
