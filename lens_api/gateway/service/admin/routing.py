from __future__ import annotations

from typing import Any

from fastapi import Depends

from ..auth import get_current_admin
from ..app_state import app_state


async def get_router_snapshot(_: Any = Depends(get_current_admin)) -> dict[str, Any]:
    """Return the current routing and health snapshot."""
    channels = await app_state.channel_store.list_channels()
    return app_state.router.snapshot(channels).model_dump(mode="json")
