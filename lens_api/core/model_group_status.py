from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from ..models.channels import ChannelConfig, ChannelDiscoveredModel, ChannelKeyItem
from ..models.model_groups import (
    ModelGroupItem,
    ModelGroupItemInput,
    ModelGroupItemReason,
    ModelGroupItemState,
)
from ..models.protocols import ChannelStatus, ProtocolKind
from .protocol_reachability import can_reach_protocol
from .runtime_channel_ids import split_runtime_channel_id

_INVALID_REASONS = frozenset(
    {
        ModelGroupItemReason.CHANNEL_NOT_FOUND,
        ModelGroupItemReason.PROTOCOL_UNREACHABLE,
        ModelGroupItemReason.CREDENTIAL_NOT_FOUND,
        ModelGroupItemReason.MODEL_NOT_FOUND,
    }
)
_UNAVAILABLE_REASONS = frozenset(
    {
        ModelGroupItemReason.CHANNEL_DISABLED,
        ModelGroupItemReason.CREDENTIAL_DISABLED,
        ModelGroupItemReason.MODEL_DISABLED,
    }
)


@dataclass(frozen=True, slots=True)
class ModelGroupItemEvaluation:
    protocol_config_id: str
    protocol: ProtocolKind | None
    state: ModelGroupItemState
    reasons: tuple[ModelGroupItemReason, ...]


@dataclass(frozen=True, slots=True)
class ModelGroupChannelLookup:
    channel: ChannelConfig
    credentials_by_id: Mapping[str, ChannelKeyItem]
    models_by_key: Mapping[tuple[str, str], ChannelDiscoveredModel]


def build_model_group_channel_lookups(
    channels: Iterable[ChannelConfig],
) -> dict[str, ModelGroupChannelLookup]:
    return {
        channel.id: ModelGroupChannelLookup(
            channel=channel,
            credentials_by_id={key.id: key for key in channel.keys},
            models_by_key={
                (model.credential_id, model.model_name): model
                for model in channel.models
            },
        )
        for channel in channels
    }


def model_group_item_key(
    item: ModelGroupItemInput | ModelGroupItem,
) -> tuple[str, str, str]:
    return item.channel_id, item.credential_id, item.model_name


def evaluate_model_group_item(
    item: ModelGroupItemInput | ModelGroupItem,
    channels_by_id: Mapping[str, ModelGroupChannelLookup],
    required_protocols: Sequence[ProtocolKind],
) -> ModelGroupItemEvaluation:
    parsed_channel_id = split_runtime_channel_id(item.channel_id)
    protocol_config_id = (
        parsed_channel_id[0] if parsed_channel_id is not None else item.channel_id
    )
    protocol = parsed_channel_id[1] if parsed_channel_id is not None else None
    reasons: list[ModelGroupItemReason] = []

    if not item.enabled:
        reasons.append(ModelGroupItemReason.MANUAL_DISABLED)

    channel_lookup = channels_by_id.get(item.channel_id)
    if channel_lookup is None:
        reasons.append(ModelGroupItemReason.CHANNEL_NOT_FOUND)
        return _evaluation(protocol_config_id, protocol, reasons)

    channel = channel_lookup.channel
    protocol = channel.protocol
    if not any(
        can_reach_protocol(channel.protocol, required_protocol)
        for required_protocol in required_protocols
    ):
        reasons.append(ModelGroupItemReason.PROTOCOL_UNREACHABLE)
    if channel.status != ChannelStatus.ENABLED:
        reasons.append(ModelGroupItemReason.CHANNEL_DISABLED)

    credential = channel_lookup.credentials_by_id.get(item.credential_id)
    if credential is None:
        reasons.append(ModelGroupItemReason.CREDENTIAL_NOT_FOUND)
    elif not credential.enabled or not credential.key.strip():
        reasons.append(ModelGroupItemReason.CREDENTIAL_DISABLED)

    model = channel_lookup.models_by_key.get((item.credential_id, item.model_name))
    if model is None:
        reasons.append(ModelGroupItemReason.MODEL_NOT_FOUND)
    elif not model.enabled:
        reasons.append(ModelGroupItemReason.MODEL_DISABLED)

    return _evaluation(protocol_config_id, protocol, reasons)


def _evaluation(
    protocol_config_id: str,
    protocol: ProtocolKind | None,
    reasons: list[ModelGroupItemReason],
) -> ModelGroupItemEvaluation:
    reason_set = set(reasons)
    if reason_set & _INVALID_REASONS:
        state = ModelGroupItemState.INVALID
    elif reason_set & _UNAVAILABLE_REASONS:
        state = ModelGroupItemState.UNAVAILABLE
    elif ModelGroupItemReason.MANUAL_DISABLED in reason_set:
        state = ModelGroupItemState.DISABLED
    else:
        state = ModelGroupItemState.READY
    return ModelGroupItemEvaluation(
        protocol_config_id=protocol_config_id,
        protocol=protocol,
        state=state,
        reasons=tuple(reasons),
    )
