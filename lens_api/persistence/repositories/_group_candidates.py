from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from ...core.model_group_status import (
    ModelGroupChannelLookup,
    build_model_group_channel_lookups,
    evaluate_model_group_item,
    model_group_item_key,
)
from ...models import ModelGroupItemState, ModelGroupItemView
from ..shared import (
    ModelGroupCandidateItem,
    ModelGroupCandidatesRequest,
    ModelGroupCandidatesResponse,
    ModelGroupCandidateSubitem,
    ModelGroupItemInput,
    ProtocolKind,
    can_reach_protocol,
)


@dataclass
class _CandidateAggregate:
    native_protocols: list[ProtocolKind] = field(default_factory=list)
    protocol_channels: dict[ProtocolKind, str] = field(default_factory=dict)
    site_id: str = ""
    channel_name: str = ""
    credential_name: str = ""
    credential_number: int = 0
    base_url: str = ""
    model_name: str = ""
    credential_id: str = ""
    protocol_config_id: str = ""


class _GroupCandidatesMixin:
    async def _list_group_candidates(
        self, payload: ModelGroupCandidatesRequest
    ) -> ModelGroupCandidatesResponse:
        all_channels = await self._channel_store.list_channels()
        channels_by_id = build_model_group_channel_lookups(all_channels)
        protocols_filter = list(dict.fromkeys(payload.protocols))
        selected_item_keys = {model_group_item_key(item) for item in payload.items}
        candidate_aggregates: dict[tuple[str, str, str], _CandidateAggregate] = {}

        for channel in all_channels:
            for model in channel.models:
                item = ModelGroupItemInput(
                    channel_id=channel.id,
                    credential_id=model.credential_id,
                    model_name=model.model_name,
                    enabled=True,
                )
                evaluation = evaluate_model_group_item(
                    item,
                    channels_by_id,
                    protocols_filter or [channel.protocol],
                )
                if evaluation.state != ModelGroupItemState.READY:
                    continue

                model_key = (
                    evaluation.protocol_config_id,
                    model.credential_id,
                    model.model_name,
                )
                credential = channels_by_id[channel.id].credentials_by_id[
                    model.credential_id
                ]
                if model_key not in candidate_aggregates:
                    candidate_aggregates[model_key] = _CandidateAggregate(
                        protocol_config_id=evaluation.protocol_config_id,
                        site_id=channel.site_id,
                        credential_id=model.credential_id,
                        credential_name=model.credential_name,
                        credential_number=credential.number,
                        model_name=model.model_name,
                        channel_name=channel.name,
                        base_url=str(channel.base_url),
                    )
                aggregate = candidate_aggregates[model_key]
                if channel.protocol not in aggregate.native_protocols:
                    aggregate.native_protocols.append(channel.protocol)
                aggregate.protocol_channels.setdefault(channel.protocol, channel.id)

        candidates: list[ModelGroupCandidateItem] = []
        for aggregate in candidate_aggregates.values():
            recommended_items = self._recommended_candidate_items(
                aggregate,
                protocols_filter,
            )
            remaining_items = [
                item
                for item in recommended_items
                if model_group_item_key(item) not in selected_item_keys
            ]
            if not remaining_items:
                continue

            candidates.append(
                ModelGroupCandidateItem(
                    site_id=aggregate.site_id,
                    channel_name=aggregate.channel_name,
                    credential_id=aggregate.credential_id,
                    credential_name=aggregate.credential_name,
                    credential_number=aggregate.credential_number,
                    base_url=aggregate.base_url,
                    model_name=aggregate.model_name,
                    protocol_config_id=aggregate.protocol_config_id,
                    protocols=sorted(
                        aggregate.native_protocols, key=lambda protocol: protocol.value
                    ),
                    items=[
                        ModelGroupCandidateSubitem(
                            channel_id=item.channel_id,
                            protocol_config_id=aggregate.protocol_config_id,
                            protocol=channels_by_id[item.channel_id].channel.protocol,
                            credential_id=item.credential_id,
                            model_name=item.model_name,
                            enabled=item.enabled,
                        )
                        for item in remaining_items
                    ],
                )
            )

        candidates.sort(
            key=lambda candidate: (candidate.channel_name, candidate.model_name)
        )
        evaluated_items = [
            self._candidate_item_view(
                item,
                index,
                channels_by_id,
                protocols_filter,
            )
            for index, item in enumerate(payload.items)
        ]
        return ModelGroupCandidatesResponse(
            candidates=candidates,
            evaluated_items=evaluated_items,
        )

    @staticmethod
    def _recommended_candidate_items(
        aggregate: _CandidateAggregate,
        protocols_filter: list[ProtocolKind],
    ) -> list[ModelGroupItemInput]:
        chosen: dict[str, ModelGroupItemInput] = {}
        requested_protocols = protocols_filter or aggregate.native_protocols
        for required_protocol in requested_protocols:
            native_protocol = (
                required_protocol
                if required_protocol in aggregate.protocol_channels
                else next(
                    (
                        protocol
                        for protocol in aggregate.native_protocols
                        if can_reach_protocol(protocol, required_protocol)
                    ),
                    None,
                )
            )
            if native_protocol is None:
                continue
            channel_id = aggregate.protocol_channels[native_protocol]
            chosen.setdefault(
                channel_id,
                ModelGroupItemInput(
                    channel_id=channel_id,
                    credential_id=aggregate.credential_id,
                    model_name=aggregate.model_name,
                    enabled=True,
                ),
            )
        return list(chosen.values())

    @staticmethod
    def _candidate_item_view(
        item: ModelGroupItemInput,
        index: int,
        channels_by_id: Mapping[str, ModelGroupChannelLookup],
        protocols_filter: list[ProtocolKind],
    ) -> ModelGroupItemView:
        evaluation = evaluate_model_group_item(
            item,
            channels_by_id,
            protocols_filter,
        )
        channel_lookup = channels_by_id.get(item.channel_id)
        channel = channel_lookup.channel if channel_lookup is not None else None
        credential = (
            channel_lookup.credentials_by_id.get(item.credential_id)
            if channel_lookup is not None
            else None
        )
        return ModelGroupItemView(
            channel_id=item.channel_id,
            channel_name=channel.name if channel is not None else "",
            protocol=evaluation.protocol,
            protocol_config_id=evaluation.protocol_config_id,
            credential_id=item.credential_id,
            credential_name=credential.remark if credential is not None else "",
            credential_number=credential.number if credential is not None else 0,
            model_name=item.model_name,
            enabled=item.enabled,
            sort_order=index,
            state=evaluation.state,
            reasons=list(evaluation.reasons),
        )
