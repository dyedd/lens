from __future__ import annotations

from dataclasses import dataclass, field

from ..shared import (
    ModelGroupCandidateItem,
    ModelGroupCandidatesRequest,
    ModelGroupCandidatesResponse,
    ModelGroupItemInput,
    ProtocolKind,
    _parse_runtime_channel_id,
    can_reach_protocol,
)


@dataclass
class _CandidateAggregate:
    native_protocols: list[ProtocolKind] = field(default_factory=list)
    protocol_channels: dict[ProtocolKind, str] = field(default_factory=dict)
    channel_name: str = ""
    credential_name: str = ""
    base_url: str = ""
    model_name: str = ""
    credential_id: str = ""
    protocol_config_id: str = ""


class _GroupCandidatesMixin:
    async def _list_group_candidates(
        self, payload: ModelGroupCandidatesRequest
    ) -> ModelGroupCandidatesResponse:
        from ..channel_store import ChannelStore

        channel_store = ChannelStore(self._session_factory)
        all_channels = await channel_store.list_channels()

        protocols_filter: list[ProtocolKind] = list(dict.fromkeys(payload.protocols))

        excluded_model_ids: set[tuple[str, str, str]] = set()
        for item in payload.exclude_items:
            parsed = _parse_runtime_channel_id(item.channel_id)
            if parsed is not None:
                excluded_protocol_config_id, _ = parsed
                excluded_model_ids.add(
                    (excluded_protocol_config_id, item.credential_id, item.model_name)
                )

        candidate_aggregates: dict[tuple[str, str, str], _CandidateAggregate] = {}

        for channel in all_channels:
            if channel.status.value != "enabled":
                continue
            parsed = _parse_runtime_channel_id(channel.id)
            if parsed is None:
                continue
            protocol_config_id, native_protocol = parsed

            enabled_credential_ids: set[str] = {
                key.id for key in channel.keys if key.enabled
            }

            for model in channel.models:
                if not model.enabled:
                    continue
                if model.credential_id not in enabled_credential_ids:
                    continue

                model_key = (protocol_config_id, model.credential_id, model.model_name)
                if model_key not in candidate_aggregates:
                    candidate_aggregates[model_key] = _CandidateAggregate(
                        protocol_config_id=protocol_config_id,
                        credential_id=model.credential_id,
                        credential_name=model.credential_name,
                        model_name=model.model_name,
                        channel_name=channel.name,
                        base_url=str(channel.base_url),
                    )
                aggregate = candidate_aggregates[model_key]
                if native_protocol not in aggregate.native_protocols:
                    aggregate.native_protocols.append(native_protocol)
                if native_protocol not in aggregate.protocol_channels:
                    aggregate.protocol_channels[native_protocol] = channel.id

        candidates: list[ModelGroupCandidateItem] = []

        for model_key, aggregate in candidate_aggregates.items():
            protocol_config_id, credential_id, model_name = model_key

            if protocols_filter:
                if not any(
                    can_reach_protocol(native_protocol, required_protocol)
                    for native_protocol in aggregate.native_protocols
                    for required_protocol in protocols_filter
                ):
                    continue

            if model_key in excluded_model_ids:
                continue

            rep_protocol = self._representative_candidate_protocol(
                aggregate.native_protocols,
                aggregate.protocol_channels,
                protocols_filter,
            )
            rep_channel_id = aggregate.protocol_channels.get(
                rep_protocol, next(iter(aggregate.protocol_channels.values()))
            )

            recommended_items: list[ModelGroupItemInput] = []
            if protocols_filter:
                chosen: dict[str, ModelGroupItemInput] = {}
                uncovered: list[ProtocolKind] = []
                for required_protocol in protocols_filter:
                    if required_protocol in aggregate.protocol_channels:
                        channel_id = aggregate.protocol_channels[required_protocol]
                        if channel_id not in chosen:
                            chosen[channel_id] = ModelGroupItemInput(
                                channel_id=channel_id,
                                credential_id=credential_id,
                                model_name=model_name,
                                enabled=True,
                            )
                    else:
                        uncovered.append(required_protocol)
                for required_protocol in uncovered:
                    fallback_native = next(
                        (
                            native_protocol
                            for native_protocol in aggregate.native_protocols
                            if can_reach_protocol(native_protocol, required_protocol)
                        ),
                        None,
                    )
                    if fallback_native is not None:
                        channel_id = aggregate.protocol_channels[fallback_native]
                        chosen.setdefault(
                            channel_id,
                            ModelGroupItemInput(
                                channel_id=channel_id,
                                credential_id=credential_id,
                                model_name=model_name,
                                enabled=True,
                            ),
                        )
                recommended_items = list(chosen.values())

            candidates.append(
                ModelGroupCandidateItem(
                    site_id="",
                    channel_id=rep_channel_id,
                    channel_name=aggregate.channel_name,
                    protocol=rep_protocol,
                    credential_id=credential_id,
                    credential_name=aggregate.credential_name,
                    credential_number=0,
                    base_url=aggregate.base_url,
                    model_name=model_name,
                    protocol_config_id=protocol_config_id,
                    protocols=sorted(aggregate.native_protocols, key=lambda p: p.value),
                    protocol_channels=aggregate.protocol_channels,
                    items=recommended_items,
                )
            )

        candidates.sort(
            key=lambda candidate: (candidate.channel_name, candidate.model_name)
        )

        return ModelGroupCandidatesResponse(candidates=candidates)

    @staticmethod
    def _representative_candidate_protocol(
        native_protocols: list[ProtocolKind],
        protocol_channels: dict[ProtocolKind, str],
        protocols_filter: list[ProtocolKind],
    ) -> ProtocolKind:
        if protocols_filter:
            for protocol in protocols_filter:
                if protocol in protocol_channels:
                    return protocol
            for selected_protocol in protocols_filter:
                for native_protocol in native_protocols:
                    if can_reach_protocol(native_protocol, selected_protocol):
                        return native_protocol
        return native_protocols[0]
