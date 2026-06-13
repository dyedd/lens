from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..shared import (
    Any,
    AsyncSession,
    GatewayApiKeyEntity,
    RequestLogAttempt,
    RequestLogDetail,
    RequestLogEntity,
    RequestLogItem,
    RequestLogLifecycleStatus,
    SiteDiscoveredModelEntity,
    SiteProtocolConfigEntity,
    UTC,
    _channel_ids_by_protocol_config,
    json,
    select,
)


class RequestLogChannelResolutionMixin:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def _hydrate_request_logs(
        self,
        session: AsyncSession,
        entities: list[RequestLogEntity],
        *,
        gateway_has_multiple_keys: bool | None = None,
    ) -> list[RequestLogItem]:
        remarks = await self._gateway_key_repo._gateway_key_remarks_by_id(
            session, [entity.gateway_key_id for entity in entities]
        )
        if gateway_has_multiple_keys is None:
            gateway_has_multiple_keys = (
                await self._gateway_has_multiple_keys(session) if entities else False
            )
        credential_counts = await self._request_log_channel_credential_counts(
            session, [entity.channel_id for entity in entities]
        )
        return [
            self._to_request_log(
                entity,
                gateway_key_remark=remarks.get(entity.gateway_key_id or ""),
                gateway_has_multiple_keys=gateway_has_multiple_keys,
                channel_has_multiple_credentials=(
                    credential_counts.get(entity.channel_id or "", 0) > 1
                ),
            )
            for entity in entities
        ]

    @staticmethod
    async def _gateway_has_multiple_keys(session: AsyncSession) -> bool:
        rows = (await session.execute(select(GatewayApiKeyEntity.id).limit(2))).all()
        return len(rows) > 1

    async def _request_log_channel_credential_counts(
        self, session: AsyncSession, channel_ids: list[str | None]
    ) -> dict[str, int]:
        (
            channels_by_protocol_config,
            protocol_by_channel_id,
        ) = _channel_ids_by_protocol_config(channel_ids)

        if not channels_by_protocol_config:
            return {}

        protocol_config_ids = list(channels_by_protocol_config.keys())
        credentials_by_channel: dict[str, set[str]] = {
            channel_id: set()
            for channel_ids_for_protocol_config in channels_by_protocol_config.values()
            for channel_id in channel_ids_for_protocol_config
        }

        default_credential_rows = (
            await session.execute(
                select(
                    SiteProtocolConfigEntity.id,
                    SiteProtocolConfigEntity.credential_id,
                ).where(SiteProtocolConfigEntity.id.in_(protocol_config_ids))
            )
        ).all()
        for protocol_config_id, credential_id in default_credential_rows:
            if not credential_id:
                continue
            for channel_id in channels_by_protocol_config.get(
                str(protocol_config_id), []
            ):
                credentials_by_channel[channel_id].add(str(credential_id))

        model_credential_rows = (
            await session.execute(
                select(
                    SiteDiscoveredModelEntity.protocol_config_id,
                    SiteDiscoveredModelEntity.credential_id,
                    SiteDiscoveredModelEntity.protocol,
                ).where(
                    SiteDiscoveredModelEntity.protocol_config_id.in_(
                        protocol_config_ids
                    )
                )
            )
        ).all()
        for protocol_config_id, credential_id, model_protocol in model_credential_rows:
            if not credential_id:
                continue
            for channel_id in channels_by_protocol_config.get(
                str(protocol_config_id), []
            ):
                channel_protocol = protocol_by_channel_id.get(channel_id)
                if model_protocol is None:
                    continue
                if (
                    channel_protocol is not None
                    and str(model_protocol) != channel_protocol.value
                ):
                    continue
                credentials_by_channel[channel_id].add(str(credential_id))

        return {
            channel_id: len(credential_ids)
            for channel_id, credential_ids in credentials_by_channel.items()
        }

    @staticmethod
    def _request_log_primary_attempt(
        attempts: list[dict[str, Any]], channel_id: str | None
    ) -> dict[str, Any]:
        if channel_id:
            for attempt in reversed(attempts):
                if str(attempt.get("channel_id") or "") == channel_id:
                    return attempt
        return attempts[-1] if attempts else {}

    @staticmethod
    def _clean_reasoning_effort(value: Any) -> str | None:
        if isinstance(value, int) and value > 0:
            return str(value)
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if not normalized or len(normalized) > 32:
            return None
        if any(char.isspace() for char in normalized):
            return None
        return normalized

    @classmethod
    def _extract_reasoning_effort(cls, request_content: str | None) -> str | None:
        if not request_content:
            return None
        try:
            payload = json.loads(request_content)
        except (TypeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None

        for key in (
            "reasoning_effort",
            "reasoningEffort",
            "model_reasoning_effort",
            "modelReasoningEffort",
            "effort",
            "effortLevel",
        ):
            effort = cls._clean_reasoning_effort(payload.get(key))
            if effort:
                return effort

        reasoning = payload.get("reasoning")
        if isinstance(reasoning, dict):
            effort = cls._clean_reasoning_effort(reasoning.get("effort"))
            if effort:
                return effort
        else:
            effort = cls._clean_reasoning_effort(reasoning)
            if effort:
                return effort

        thinking = payload.get("thinking")
        if isinstance(thinking, dict):
            for key in ("effort", "budget_tokens"):
                effort = cls._clean_reasoning_effort(thinking.get(key))
                if effort:
                    return effort

        output_config = payload.get("output_config")
        if isinstance(output_config, dict):
            effort = cls._clean_reasoning_effort(output_config.get("effort"))
            if effort:
                return effort

        extra_body = payload.get("extra_body")
        if isinstance(extra_body, dict):
            effort = cls._extract_reasoning_effort(json.dumps(extra_body))
            if effort:
                return effort
        return None

    @classmethod
    def _to_request_log(
        cls,
        entity: RequestLogEntity,
        *,
        gateway_key_remark: str | None = None,
        gateway_has_multiple_keys: bool = False,
        channel_has_multiple_credentials: bool = False,
    ) -> RequestLogItem:
        attempts = cls._parse_attempts_json(entity.attempts_json)
        primary_attempt = cls._request_log_primary_attempt(attempts, entity.channel_id)
        credential_id = primary_attempt.get("credential_id")
        credential_name = primary_attempt.get("credential_name")
        reasoning_effort = cls._extract_reasoning_effort(
            entity.request_content
        ) or cls._clean_reasoning_effort(primary_attempt.get("reasoning_effort"))
        return RequestLogItem(
            id=entity.id,
            protocol=entity.protocol,
            user_agent=entity.user_agent,
            requested_group_name=entity.requested_group_name,
            resolved_group_name=entity.resolved_group_name,
            upstream_model_name=entity.upstream_model_name,
            channel_id=entity.channel_id,
            channel_name=entity.channel_name,
            credential_id=(
                credential_id.strip() if isinstance(credential_id, str) else None
            ),
            credential_name=(
                credential_name.strip() if isinstance(credential_name, str) else ""
            ),
            channel_has_multiple_credentials=channel_has_multiple_credentials,
            gateway_key_id=entity.gateway_key_id,
            gateway_key_remark=gateway_key_remark or None,
            gateway_has_multiple_keys=gateway_has_multiple_keys,
            reasoning_effort=reasoning_effort,
            status_code=entity.status_code,
            success=bool(entity.success),
            lifecycle_status=(
                RequestLogLifecycleStatus(entity.lifecycle_status)
                if entity.lifecycle_status
                in RequestLogLifecycleStatus._value2member_map_
                else (
                    RequestLogLifecycleStatus.SUCCEEDED
                    if entity.success
                    else RequestLogLifecycleStatus.FAILED
                )
            ),
            is_stream=bool(entity.is_stream),
            first_token_latency_ms=entity.first_token_latency_ms,
            latency_ms=entity.latency_ms,
            input_tokens=entity.input_tokens,
            cache_read_input_tokens=entity.cache_read_input_tokens,
            cache_write_input_tokens=entity.cache_write_input_tokens,
            output_tokens=entity.output_tokens,
            total_tokens=entity.total_tokens,
            input_cost_usd=entity.input_cost_usd,
            output_cost_usd=entity.output_cost_usd,
            total_cost_usd=entity.total_cost_usd,
            attempt_count=len(attempts),
            error_message=entity.error_message,
            created_at=entity.created_at.replace(tzinfo=UTC).isoformat(),
        )

    @classmethod
    def _to_request_log_detail(
        cls,
        entity: RequestLogEntity,
        *,
        gateway_key_remark: str | None = None,
        gateway_has_multiple_keys: bool = False,
        channel_has_multiple_credentials: bool = False,
    ) -> RequestLogDetail:
        return RequestLogDetail(
            **cls._to_request_log(
                entity,
                gateway_key_remark=gateway_key_remark,
                gateway_has_multiple_keys=gateway_has_multiple_keys,
                channel_has_multiple_credentials=channel_has_multiple_credentials,
            ).model_dump(),
            request_content=entity.request_content,
            response_content=entity.response_content,
            attempts=[
                RequestLogAttempt(**item)
                for item in cls._parse_attempts_json(entity.attempts_json)
            ],
        )

    @staticmethod
    def _parse_attempts_json(raw_value: str | None) -> list[dict[str, Any]]:
        if not raw_value:
            return []
        payload = json.loads(raw_value)
        if not isinstance(payload, list):
            raise ValueError("Invalid request log attempts JSON")
        if not all(isinstance(item, dict) for item in payload):
            raise ValueError("Invalid request log attempts JSON")
        return payload
