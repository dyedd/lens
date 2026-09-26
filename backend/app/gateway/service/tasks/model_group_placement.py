from __future__ import annotations

from typing import TYPE_CHECKING

from ..app_state import logger

if TYPE_CHECKING:
    from ..app_state import AppState


async def run_model_group_placement(state: AppState) -> None:
    """Place newly available channel models into groups without failing the caller.

    Callers run this after their own change is committed, so a placement
    failure is logged instead of turning a saved change into an error.
    """
    try:
        result = await state.group_repo.place_models()
    except Exception:
        logger.exception("Model group placement failed")
        return
    if result.created or result.unplaced:
        logger.info(
            "Model group placement: created=%s unplaced=%s",
            len(result.created),
            len(result.unplaced),
        )
