from __future__ import annotations

from copy import deepcopy
import json

from pydantic import ValidationError

from ...models import UpstreamHeadersConfig
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..shared import (
    Any,
    SETTING_CIRCUIT_BREAKER_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_MAX_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_THRESHOLD,
    SETTING_CORS_ALLOW_ORIGINS,
    SETTING_HEALTH_MIN_SAMPLES,
    SETTING_HEALTH_PENALTY_WEIGHT,
    SETTING_HEALTH_WINDOW_SECONDS,
    SETTING_MODEL_LIST_COMPAT_MODE_ENABLED,
    SETTING_PROXY_URL,
    SETTING_RELAY_LOG_BODY_ENABLED,
    SETTING_RELAY_LOG_KEEP_ENABLED,
    SETTING_RELAY_LOG_KEEP_PERIOD,
    SETTING_SITE_LOGO_URL,
    SETTING_SITE_NAME,
    SETTING_TIME_ZONE,
    SETTING_UPSTREAM_HEADERS_CONFIG,
    SettingEntity,
    SettingItem,
    monotonic,
    normalize_time_zone,
    select,
)


class SettingsRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        import asyncio

        self._session_factory = session_factory
        self._settings_cache: list[SettingItem] | None = None
        self._settings_cache_at = 0.0
        self._settings_cache_ttl_seconds = 2.0
        self._settings_cache_lock = asyncio.Lock()
        self._runtime_settings_cache: dict[Any, Any] | None = None
        self._runtime_settings_cache_at = 0.0

    def _clone_settings_items(self, items: list[SettingItem]) -> list[SettingItem]:
        return [SettingItem(key=item.key, value=item.value) for item in items]

    def _store_settings_cache(self, items: list[SettingItem]) -> list[SettingItem]:
        self._settings_cache = self._clone_settings_items(items)
        self._settings_cache_at = monotonic()
        self._runtime_settings_cache = None
        self._runtime_settings_cache_at = 0.0
        return self._clone_settings_items(items)

    def invalidate_settings_cache(self) -> None:
        self._settings_cache = None
        self._settings_cache_at = 0.0
        self._runtime_settings_cache = None
        self._runtime_settings_cache_at = 0.0

    def _clone_runtime_settings(self, runtime: dict[str, Any]) -> dict[str, Any]:
        cloned = dict(runtime)
        allow_origins = cloned.get("cors_allow_origins")
        if isinstance(allow_origins, list):
            cloned["cors_allow_origins"] = list(allow_origins)
        upstream_headers_config = cloned.get("upstream_headers_config")
        if isinstance(upstream_headers_config, dict):
            cloned["upstream_headers_config"] = deepcopy(upstream_headers_config)
        return cloned

    @staticmethod
    def _parse_upstream_headers_config(value: str | None) -> dict[str, Any]:
        raw_value = (value or "").strip()
        if not raw_value:
            config = UpstreamHeadersConfig()
        else:
            try:
                payload = json.loads(raw_value)
                config = UpstreamHeadersConfig.model_validate(payload)
            except (TypeError, ValueError, json.JSONDecodeError, ValidationError):
                config = UpstreamHeadersConfig()
        return config.model_dump(mode="json", by_alias=True)

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

    async def get_runtime_settings(self) -> dict[str, Any]:
        cached = self._runtime_settings_cache
        if (
            cached is not None
            and (monotonic() - self._runtime_settings_cache_at)
            < self._settings_cache_ttl_seconds
        ):
            return self._clone_runtime_settings(cached)

        items = await self.list_settings()
        mapping = {item.key: item.value for item in items}
        cors_allow_origins = self._split_comma_lines(
            mapping.get(SETTING_CORS_ALLOW_ORIGINS, "")
        )
        time_zone = normalize_time_zone(mapping.get(SETTING_TIME_ZONE))
        runtime = {
            "proxy_url": mapping.get(SETTING_PROXY_URL, "").strip(),
            "time_zone": time_zone,
            "cors_allow_origins": cors_allow_origins or ["*"],
            "relay_log_body_enabled": self._parse_bool(
                mapping.get(SETTING_RELAY_LOG_BODY_ENABLED), default=False
            ),
            "relay_log_keep_enabled": self._parse_bool(
                mapping.get(SETTING_RELAY_LOG_KEEP_ENABLED), default=True
            ),
            "relay_log_keep_period": self._parse_int(
                mapping.get(SETTING_RELAY_LOG_KEEP_PERIOD), default=7
            ),
            "circuit_breaker_threshold": self._parse_int(
                mapping.get(SETTING_CIRCUIT_BREAKER_THRESHOLD), default=3
            ),
            "circuit_breaker_cooldown": self._parse_int(
                mapping.get(SETTING_CIRCUIT_BREAKER_COOLDOWN), default=60
            ),
            "circuit_breaker_max_cooldown": self._parse_int(
                mapping.get(SETTING_CIRCUIT_BREAKER_MAX_COOLDOWN), default=600
            ),
            "health_window_seconds": self._parse_int(
                mapping.get(SETTING_HEALTH_WINDOW_SECONDS), default=300
            ),
            "health_penalty_weight": self._parse_float(
                mapping.get(SETTING_HEALTH_PENALTY_WEIGHT), default=0.5
            ),
            "health_min_samples": self._parse_int(
                mapping.get(SETTING_HEALTH_MIN_SAMPLES), default=10
            ),
            "model_list_compat_mode_enabled": self._parse_bool(
                mapping.get(SETTING_MODEL_LIST_COMPAT_MODE_ENABLED), default=False
            ),
            "upstream_headers_config": self._parse_upstream_headers_config(
                mapping.get(SETTING_UPSTREAM_HEADERS_CONFIG)
            ),
            "site_name": mapping.get(SETTING_SITE_NAME, "Lens").strip() or "Lens",
            "site_logo_url": mapping.get(SETTING_SITE_LOGO_URL, "").strip(),
        }
        self._runtime_settings_cache = self._clone_runtime_settings(runtime)
        self._runtime_settings_cache_at = monotonic()
        return self._clone_runtime_settings(runtime)

    async def get_branding_settings(self) -> dict[str, str]:
        runtime = await self.get_runtime_settings()
        return {
            "site_name": str(runtime["site_name"]),
            "site_logo_url": str(runtime["site_logo_url"]),
        }

    async def list_settings(self) -> list[SettingItem]:
        cached = self._settings_cache
        if (
            cached is not None
            and (monotonic() - self._settings_cache_at)
            < self._settings_cache_ttl_seconds
        ):
            return self._clone_settings_items(cached)

        async with self._settings_cache_lock:
            cached = self._settings_cache
            if (
                cached is not None
                and (monotonic() - self._settings_cache_at)
                < self._settings_cache_ttl_seconds
            ):
                return self._clone_settings_items(cached)

            async with self._session_factory() as session:
                result = await session.execute(
                    select(SettingEntity).order_by(SettingEntity.key)
                )
                items = [
                    SettingItem(key=item.key, value=item.value)
                    for item in result.scalars().all()
                ]
            return self._store_settings_cache(items)

    async def upsert_settings(self, items: list[SettingItem]) -> list[SettingItem]:
        if not items:
            return await self.list_settings()
        keys = [item.key for item in items]
        async with self._session_factory() as session:
            existing = await session.execute(
                select(SettingEntity).where(SettingEntity.key.in_(keys))
            )
            existing_by_key = {
                entity.key: entity for entity in existing.scalars().all()
            }
            for item in items:
                entity = existing_by_key.get(item.key)
                if entity is None:
                    session.add(SettingEntity(key=item.key, value=item.value))
                else:
                    entity.value = item.value
            await session.commit()
            result = await session.execute(
                select(SettingEntity).order_by(SettingEntity.key)
            )
            stored_items = [
                SettingItem(key=item.key, value=item.value)
                for item in result.scalars().all()
            ]
        return self._store_settings_cache(stored_items)
