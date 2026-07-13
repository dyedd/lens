from __future__ import annotations

from sqlalchemy import case

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..shared import (
    AsyncSession,
    GATEWAY_API_KEY_CHARS,
    GatewayApiKey,
    GatewayApiKeyCreate,
    GatewayApiKeyEntity,
    GatewayApiKeyUpdate,
    UTC,
    datetime,
    json,
    secrets,
    select,
    update,
    uuid,
)


class GatewayApiKeyRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_gateway_api_keys(self) -> list[GatewayApiKey]:
        """List gateway API keys in creation order."""
        async with self._session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(GatewayApiKeyEntity).order_by(
                            GatewayApiKeyEntity.created_at.asc(),
                            GatewayApiKeyEntity.id.asc(),
                        )
                    )
                )
                .scalars()
                .all()
            )
            return [self._to_gateway_api_key(row) for row in rows]

    async def find_gateway_api_key_by_secret(
        self, secret: str
    ) -> GatewayApiKey | None:
        """Find a gateway API key by its secret value."""
        normalized = secret.strip()
        if not normalized:
            return None
        async with self._session_factory() as session:
            entity = (
                await session.execute(
                    select(GatewayApiKeyEntity)
                    .where(GatewayApiKeyEntity.api_key == normalized)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if entity is None:
                return None
            return self._to_gateway_api_key(entity)

    async def create_gateway_api_key(
        self, payload: GatewayApiKeyCreate
    ) -> GatewayApiKey:
        """Create and persist a gateway API key."""
        now = datetime.now(UTC).replace(tzinfo=None)
        async with self._session_factory() as session:
            secret = await self._generate_unique_gateway_api_key(session)
            entity = GatewayApiKeyEntity(
                id=uuid.uuid4().hex,
                remark=payload.remark.strip(),
                api_key=secret,
                enabled=1 if payload.enabled else 0,
                allowed_models_json=self._dump_gateway_key_models(
                    payload.allowed_models
                ),
                max_cost_usd=max(float(payload.max_cost_usd), 0.0),
                spent_cost_usd=0.0,
                expires_at=self._parse_gateway_key_expires_at(payload.expires_at),
                created_at=now,
                updated_at=now,
            )
            session.add(entity)
            await session.commit()
            await session.refresh(entity)
            return self._to_gateway_api_key(entity)

    async def update_gateway_api_key(
        self, key_id: str, payload: GatewayApiKeyUpdate
    ) -> GatewayApiKey:
        """Update a persisted gateway API key."""
        async with self._session_factory() as session:
            entity = await session.get(GatewayApiKeyEntity, key_id)
            if entity is None:
                raise KeyError(key_id)
            entity.remark = payload.remark.strip()
            entity.enabled = 1 if payload.enabled else 0
            entity.allowed_models_json = self._dump_gateway_key_models(
                payload.allowed_models
            )
            entity.max_cost_usd = max(float(payload.max_cost_usd), 0.0)
            entity.expires_at = self._parse_gateway_key_expires_at(payload.expires_at)
            entity.updated_at = datetime.now(UTC).replace(tzinfo=None)
            await session.commit()
            await session.refresh(entity)
            return self._to_gateway_api_key(entity)

    async def delete_gateway_api_key(self, key_id: str) -> None:
        """Delete a gateway API key by identifier."""
        async with self._session_factory() as session:
            entity = await session.get(GatewayApiKeyEntity, key_id)
            if entity is None:
                raise KeyError(key_id)
            await session.delete(entity)
            await session.commit()

    @staticmethod
    def _load_gateway_key_models(raw_value: str | None) -> list[str]:
        if not raw_value:
            return []
        payload = json.loads(raw_value)
        if not isinstance(payload, list):
            raise ValueError("Invalid gateway API key allowed models JSON")
        models: list[str] = []
        seen: set[str] = set()
        for item in payload:
            normalized = str(item).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            models.append(normalized)
        return models

    @staticmethod
    def _dump_gateway_key_models(models: list[str]) -> str:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in models:
            value = str(item).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        return json.dumps(normalized, ensure_ascii=True, separators=(",", ":"))

    @classmethod
    async def _generate_unique_gateway_api_key(cls, session: AsyncSession) -> str:
        for _ in range(10):
            secret = cls._generate_gateway_api_key()
            existing_key_id = (
                await session.execute(
                    select(GatewayApiKeyEntity.id)
                    .where(GatewayApiKeyEntity.api_key == secret)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if existing_key_id is None:
                return secret
        raise RuntimeError("Unable to generate unique gateway API key")

    @staticmethod
    def _generate_gateway_api_key() -> str:
        return "sk-lens-" + "".join(
            secrets.choice(GATEWAY_API_KEY_CHARS) for _ in range(48)
        )

    @staticmethod
    def _parse_gateway_key_expires_at(value: str | None) -> datetime | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError("Invalid gateway API key expiration time") from exc
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(UTC).replace(tzinfo=None)
        return parsed

    @staticmethod
    def _format_datetime(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC).isoformat()

    async def _adjust_gateway_key_spend(
        self, session: AsyncSession, gateway_key_id: str | None, delta: float
    ) -> None:
        if not gateway_key_id or delta == 0:
            return
        next_spend = GatewayApiKeyEntity.spent_cost_usd + float(delta)
        await session.execute(
            update(GatewayApiKeyEntity)
            .where(GatewayApiKeyEntity.id == gateway_key_id)
            .values(
                spent_cost_usd=case(
                    (next_spend < 0, 0.0),
                    else_=next_spend,
                )
            )
        )

    @classmethod
    def _to_gateway_api_key(cls, entity: GatewayApiKeyEntity) -> GatewayApiKey:
        return GatewayApiKey(
            id=entity.id,
            remark=entity.remark,
            api_key=entity.api_key,
            enabled=bool(entity.enabled),
            allowed_models=cls._load_gateway_key_models(entity.allowed_models_json),
            max_cost_usd=max(float(entity.max_cost_usd), 0.0),
            spent_cost_usd=max(float(entity.spent_cost_usd), 0.0),
            expires_at=cls._format_datetime(entity.expires_at),
            created_at=cls._format_datetime(entity.created_at),
            updated_at=cls._format_datetime(entity.updated_at),
        )

    @staticmethod
    async def _gateway_key_remarks_by_id(
        session: AsyncSession, key_ids: list[str | None]
    ) -> dict[str, str]:
        unique_ids = [
            item
            for item in dict.fromkeys(
                str(key_id).strip() for key_id in key_ids if key_id
            )
            if item
        ]
        if not unique_ids:
            return {}
        rows = (
            await session.execute(
                select(GatewayApiKeyEntity.id, GatewayApiKeyEntity.remark).where(
                    GatewayApiKeyEntity.id.in_(unique_ids)
                )
            )
        ).all()
        return {
            str(key_id): str(remark).strip()
            for key_id, remark in rows
            if key_id is not None
        }
