from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..shared import RequestLogDetail, RequestLogEntity


class _RequestLogDetailReadMixin:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_request_log(self, log_id: int) -> RequestLogDetail:
        """Return a hydrated request log by identifier."""
        async with self._session_factory() as session:
            entity = await session.get(RequestLogEntity, log_id)
            if entity is None:
                raise KeyError(log_id)
            remarks = await self._gateway_key_repo._gateway_key_remarks_by_id(
                session, [entity.gateway_key_id]
            )
            gateway_has_multiple_keys = await self._gateway_has_multiple_keys(session)
            credential_counts = await self._request_log_channel_credential_counts(
                session, [entity.channel_id]
            )
            return self._to_request_log_detail(
                entity,
                gateway_key_remark=remarks.get(entity.gateway_key_id or ""),
                gateway_has_multiple_keys=gateway_has_multiple_keys,
                channel_has_multiple_credentials=(
                    credential_counts.get(entity.channel_id or "", 0) > 1
                ),
            )
