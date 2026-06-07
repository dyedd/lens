from __future__ import annotations

from .shared import (
    Any,
    AsyncSession,
    GATEWAY_API_KEY_CHARS,
    GatewayApiKey,
    GatewayApiKeyCreate,
    GatewayApiKeyEntity,
    GatewayApiKeyUpdate,
    REQUEST_LOG_TERMINAL_STATUSES,
    RequestLogEntity,
    UTC,
    datetime,
    func,
    json,
    secrets,
    select,
    uuid,
)


class DomainGatewayKeysMixin:
    async def list_gateway_api_keys(self) -> list[GatewayApiKey]:
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
            spent_by_key = await self._gateway_key_spend_by_id(
                session, [row.id for row in rows]
            )
            return [
                self._to_gateway_api_key(row, spent_by_key.get(row.id, 0.0))
                for row in rows
            ]

    async def get_gateway_api_key_by_secret(self, secret: str) -> GatewayApiKey | None:
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
            spent = (await self._gateway_key_spend_by_id(session, [entity.id])).get(
                entity.id, 0.0
            )
            return self._to_gateway_api_key(entity, spent)

    async def create_gateway_api_key(
        self, payload: GatewayApiKeyCreate
    ) -> GatewayApiKey:
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
                expires_at=self._parse_gateway_key_expires_at(payload.expires_at),
                created_at=now,
                updated_at=now,
            )
            session.add(entity)
            await session.commit()
            await session.refresh(entity)
            return self._to_gateway_api_key(entity, 0.0)

    async def update_gateway_api_key(
        self, key_id: str, payload: GatewayApiKeyUpdate
    ) -> GatewayApiKey:
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
            spent = (await self._gateway_key_spend_by_id(session, [entity.id])).get(
                entity.id, 0.0
            )
            return self._to_gateway_api_key(entity, spent)

    async def delete_gateway_api_key(self, key_id: str) -> None:
        async with self._session_factory() as session:
            entity = await session.get(GatewayApiKeyEntity, key_id)
            if entity is None:
                raise KeyError(key_id)
            await session.delete(entity)
            await session.commit()

    async def count_active_gateway_api_keys(self) -> int:
        now = datetime.now(UTC).replace(tzinfo=None)
        keys = await self.list_gateway_api_keys()
        return sum(1 for key in keys if self._is_gateway_api_key_usable(key, now=now))

    @staticmethod
    def _normalize_gateway_key_id(gateway_key_id: str | None) -> str | None:
        normalized = (gateway_key_id or "").strip()
        return normalized or None

    @classmethod
    def _apply_gateway_key_filter(
        cls, stmt: Any, *, gateway_key_id: str | None = None
    ) -> Any:
        normalized = cls._normalize_gateway_key_id(gateway_key_id)
        if normalized is None:
            return stmt
        if normalized == "n/a":
            return stmt.where(RequestLogEntity.gateway_key_id.is_(None))
        return stmt.where(RequestLogEntity.gateway_key_id == normalized)

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
            exists = (
                await session.execute(
                    select(GatewayApiKeyEntity.id)
                    .where(GatewayApiKeyEntity.api_key == secret)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if exists is None:
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

    async def _gateway_key_spend_by_id(
        self, session: AsyncSession, key_ids: list[str]
    ) -> dict[str, float]:
        unique_ids = [item for item in dict.fromkeys(key_ids) if item]
        if not unique_ids:
            return {}
        rows = (
            await session.execute(
                select(
                    RequestLogEntity.gateway_key_id,
                    func.sum(RequestLogEntity.total_cost_usd),
                )
                .where(RequestLogEntity.gateway_key_id.in_(unique_ids))
                .where(
                    RequestLogEntity.lifecycle_status.in_(REQUEST_LOG_TERMINAL_STATUSES)
                )
                .group_by(RequestLogEntity.gateway_key_id)
            )
        ).all()
        return {str(key_id): float(total) for key_id, total in rows}

    @classmethod
    def _to_gateway_api_key(
        cls, entity: GatewayApiKeyEntity, spent_cost_usd: float
    ) -> GatewayApiKey:
        return GatewayApiKey(
            id=entity.id,
            remark=entity.remark,
            api_key=entity.api_key,
            enabled=bool(entity.enabled),
            allowed_models=cls._load_gateway_key_models(entity.allowed_models_json),
            max_cost_usd=max(float(entity.max_cost_usd), 0.0),
            spent_cost_usd=max(float(spent_cost_usd), 0.0),
            expires_at=cls._format_datetime(entity.expires_at),
            created_at=cls._format_datetime(entity.created_at),
            updated_at=cls._format_datetime(entity.updated_at),
        )

    @classmethod
    def _is_gateway_api_key_usable(cls, key: GatewayApiKey, *, now: datetime) -> bool:
        if not key.enabled:
            return False
        if key.expires_at:
            try:
                expires_at = cls._parse_gateway_key_expires_at(key.expires_at)
            except ValueError:
                return False
            if expires_at is not None and expires_at <= now:
                return False
        return not (key.max_cost_usd > 0 and key.spent_cost_usd >= key.max_cost_usd)

    @staticmethod
    def _split_comma_lines(raw_value: str) -> list[str]:
        items: list[str] = []
        seen: set[str] = set()
        for chunk in raw_value.replace("\r", "\n").replace("，", ",").splitlines():
            for item in chunk.split(","):
                normalized = item.strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                items.append(normalized)
        return items

    @staticmethod
    def _parse_bool(value: str | None, *, default: bool) -> bool:
        if value is None:
            return default
        return value.strip().lower() not in {"0", "false", "no", "off"}

    @staticmethod
    def _parse_int(value: str | None, *, default: int) -> int:
        if value is None:
            return default
        return int(value.strip())

    @staticmethod
    def _parse_float(value: str | None, *, default: float) -> float:
        if value is None:
            return default
        return float(value.strip())

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
