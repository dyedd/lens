from __future__ import annotations

from typing import Any

from fastapi import Depends, Response

from ....models import (
    ModelGroup,
    ModelGroupCandidatesRequest,
    ModelGroupCandidatesResponse,
    ModelGroupCreate,
    ModelGroupEnsureFromSiteRequest,
    ModelGroupEnsureFromSiteResponse,
    ModelGroupUpdate,
)
from ..auth import get_current_admin
from ..app_state import app_state


async def list_model_groups(_: Any = Depends(get_current_admin)) -> list[ModelGroup]:
    """List all configured model groups."""
    return await app_state.group_repo.list_groups()


async def get_model_group(
    group_id: str, _: Any = Depends(get_current_admin)
) -> ModelGroup:
    """Return one model group by identifier."""
    return await app_state.group_repo.get_group(group_id)


async def list_model_group_candidates(
    payload: ModelGroupCandidatesRequest, _: Any = Depends(get_current_admin)
) -> ModelGroupCandidatesResponse:
    """List site models eligible for a model group."""
    return await app_state.group_repo.list_group_candidates(payload)


async def ensure_model_groups_from_site(
    payload: ModelGroupEnsureFromSiteRequest, _: Any = Depends(get_current_admin)
) -> ModelGroupEnsureFromSiteResponse:
    """Create or extend model groups from selected site models."""
    return await app_state.group_repo.ensure_groups_from_site(payload)


async def create_model_group(
    payload: ModelGroupCreate, _: Any = Depends(get_current_admin)
) -> ModelGroup:
    """Create a model group."""
    return await app_state.group_repo.create_group(payload)


async def update_model_group(
    group_id: str, payload: ModelGroupUpdate, _: Any = Depends(get_current_admin)
) -> ModelGroup:
    """Update a model group."""
    return await app_state.group_repo.update_group(group_id, payload)


async def delete_model_group(
    group_id: str, _: Any = Depends(get_current_admin)
) -> Response:
    """Delete a model group."""
    await app_state.group_repo.delete_group(group_id)
    return Response(status_code=204)
