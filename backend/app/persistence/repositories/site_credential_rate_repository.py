from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..entities import SiteCredentialRateEntity


async def _update_rate(
    session_factory: async_sessionmaker[AsyncSession],
    credential_id: str,
    *,
    protocol_config_id: str,
    source: str,
    group_name: str,
    **values: object,
) -> bool:
    async with session_factory() as session:
        result = await session.execute(
            update(SiteCredentialRateEntity)
            .where(
                SiteCredentialRateEntity.credential_id == credential_id,
                SiteCredentialRateEntity.protocol_config_id == protocol_config_id,
                SiteCredentialRateEntity.source == source,
                SiteCredentialRateEntity.group_name == group_name,
            )
            .values(**values)
        )
        await session.commit()
        return result.rowcount == 1


class SiteCredentialRateRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def record_success(
        self,
        credential_id: str,
        *,
        multiplier: float,
        observed_at: str,
        synced_at: str,
        protocol_config_id: str,
        source: str,
        group_name: str,
    ) -> bool:
        return await _update_rate(
            self._session_factory,
            credential_id,
            protocol_config_id=protocol_config_id,
            source=source,
            group_name=group_name,
            multiplier=multiplier,
            observed_at=observed_at,
            last_synced_at=synced_at,
            last_error="",
        )

    async def record_failure(
        self,
        credential_id: str,
        error: str,
        *,
        protocol_config_id: str,
        source: str,
        group_name: str,
    ) -> bool:
        return await _update_rate(
            self._session_factory,
            credential_id,
            protocol_config_id=protocol_config_id,
            source=source,
            group_name=group_name,
            last_error=error[:2000],
        )
