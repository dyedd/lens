from __future__ import annotations

from typing import TYPE_CHECKING

from ..app_state import logger

if TYPE_CHECKING:
    from ..app_state import AppState


async def run_model_group_reconcile(
    state: AppState, *, should_raise: bool = False
) -> None:
    """Save rule members and place uncovered models.

    Callers run this after their own change is committed, so a reconcile
    failure is logged instead of turning a saved change into an error.
    Startup raises instead: groups whose members all come from rules have
    no saved rows until the first reconcile after the upgrade, so serving
    without one would route those groups nowhere.
    """
    try:
        report = await state.group_repo.reconcile_group_members()
    except Exception:
        if should_raise:
            raise
        logger.exception("Model group reconcile failed")
        return
    if report.has_changes or report.pending:
        logger.info(
            "Model group reconcile: added=%s removed=%s created=%s pending=%s",
            len(report.added),
            len(report.removed),
            len(report.created_groups),
            len(report.pending),
        )
