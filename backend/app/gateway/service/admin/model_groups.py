from __future__ import annotations

from typing import Any

from fastapi import Depends, Request, Response

from ....models.model_groups import (
    ModelGroupCandidatesRequest,
    ModelGroupCandidatesResponse,
    ModelGroupCreate,
    ModelGroupItemState,
    ModelGroupMergeRequest,
    ModelGroupModelTestRequest,
    ModelGroupPlacementRequest,
    ModelGroupPlacementResponse,
    ModelGroupUpdate,
    ModelGroupView,
    UnplacedModelsResponse,
)
from ....models.protocols import ProtocolKind
from ....models.site_model_test import SiteModelTestRequest, SiteModelTestResult
from ..app_state import app_state
from ..auth import get_current_admin
from ..tasks.site_model_probe import run_site_model_probe


async def list_model_groups(
    _: Any = Depends(get_current_admin),
) -> list[ModelGroupView]:
    """List all configured model groups."""
    return await app_state.group_repo.list_groups()


async def get_model_group(
    group_id: str, _: Any = Depends(get_current_admin)
) -> ModelGroupView:
    """Return one model group by identifier."""
    return await app_state.group_repo.get_group(group_id)


async def list_model_group_candidates(
    payload: ModelGroupCandidatesRequest, _: Any = Depends(get_current_admin)
) -> ModelGroupCandidatesResponse:
    """List site models eligible for a model group."""
    return await app_state.group_repo.list_group_candidates(payload)


async def test_model_group_model(
    group_id: str,
    payload: ModelGroupModelTestRequest,
    request: Request,
    _: Any = Depends(get_current_admin),
) -> SiteModelTestResult:
    """Probe one available persisted member of a model group."""
    channels = await app_state.channel_store.list_channels()
    group = await app_state.group_repo.get_group(group_id, channels=channels)
    member = next(
        (
            item
            for item in group.items
            if (item.channel_id, item.credential_id, item.model_name)
            == (payload.channel_id, payload.credential_id, payload.model_name)
        ),
        None,
    )
    if member is None:
        raise ValueError("Model is not a member of the model group")
    if not member.enabled or member.state != ModelGroupItemState.READY:
        raise ValueError("Model group member is unavailable")
    channel = next(item for item in channels if item.id == member.channel_id)
    credential = next(item for item in channel.keys if item.id == member.credential_id)

    protocol = channel.protocol
    if protocol == ProtocolKind.AUTO:
        if payload.protocol is None or payload.protocol == ProtocolKind.AUTO:
            raise ValueError("Choose a client protocol for the model test")
        protocol = payload.protocol
    elif payload.protocol is not None and payload.protocol != protocol:
        raise ValueError("Test protocol must match the configured upstream protocol")

    probe_payload = SiteModelTestRequest(
        protocol=protocol,
        base_url=channel.base_url,
        headers=channel.headers,
        proxy_mode=channel.proxy_mode,
        channel_proxy=channel.channel_proxy,
        param_override=channel.param_override,
        credential={
            "id": credential.id,
            "name": credential.remark,
            "api_key": credential.key,
        },
        model_name=member.model_name,
        prompt=payload.prompt,
    )
    return await run_site_model_probe(
        probe_payload,
        request,
        model_group_headers=group.headers,
        model_group_param_override=group.param_override,
    )


async def create_model_group(
    payload: ModelGroupCreate, _: Any = Depends(get_current_admin)
) -> ModelGroupView:
    """Create a model group."""
    return await app_state.group_repo.create_group(payload)


async def update_model_group(
    group_id: str, payload: ModelGroupUpdate, _: Any = Depends(get_current_admin)
) -> ModelGroupView:
    """Update a model group."""
    return await app_state.group_repo.update_group(group_id, payload)


async def delete_model_group(
    group_id: str, _: Any = Depends(get_current_admin)
) -> Response:
    """Delete a model group."""
    await app_state.group_repo.delete_group(group_id)
    return Response(status_code=204)


async def merge_model_group(
    group_id: str, payload: ModelGroupMergeRequest, _: Any = Depends(get_current_admin)
) -> ModelGroupView:
    """Merge a model group into another execution group."""
    return await app_state.group_repo.merge_group(group_id, payload.target_group_id)


async def list_unplaced_models(
    _: Any = Depends(get_current_admin),
) -> UnplacedModelsResponse:
    """List channel models that no execution group covers."""
    return UnplacedModelsResponse(
        items=await app_state.group_repo.list_unplaced_models()
    )


async def place_models(
    payload: ModelGroupPlacementRequest, _: Any = Depends(get_current_admin)
) -> ModelGroupPlacementResponse:
    """Create failover groups for unplaced models without near-name conflicts."""
    return await app_state.group_repo.place_models(payload.model_names)
