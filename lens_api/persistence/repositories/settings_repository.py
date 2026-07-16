from __future__ import annotations

from copy import deepcopy
import json

from ...models import UpstreamHeadersConfig, UpstreamParamOverrideConfig
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..editable_settings import effective_editable_setting_items
from ..shared import (
    Any,
    SETTING_AUTH_ACCESS_TOKEN_MINUTES,
    SETTING_CIRCUIT_BREAKER_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_MAX_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_THRESHOLD,
    SETTING_CORS_ALLOW_ORIGINS,
    SETTING_HEALTH_MIN_SAMPLES,
    SETTING_HEALTH_PENALTY_WEIGHT,
    SETTING_HEALTH_WINDOW_SECONDS,
    SETTING_MAX_REQUEST_BODY_BYTES,
    SETTING_MODEL_LIST_COMPAT_MODE_ENABLED,
    SETTING_PROXY_URL,
    SETTING_RELAY_LOG_BODY_ENABLED,
    SETTING_RELAY_LOG_KEEP_ENABLED,
    SETTING_RELAY_LOG_KEEP_PERIOD,
    SETTING_REQUEST_TIMEOUT_SECONDS,
    SETTING_SITE_LOGO_URL,
    SETTING_SITE_NAME,
    SETTING_TIME_ZONE,
    SETTING_UPSTREAM_HEADERS_CONFIG,
    SETTING_UPSTREAM_PARAM_OVERRIDE_CONFIG,
    SettingEntity,
    SettingItem,
    monotonic,
    normalize_time_zone,
    select,
)


def _parse_upstream_config(
    value: str | None,
    config_type: type[UpstreamHeadersConfig] | type[UpstreamParamOverrideConfig],
) -> dict[str, Any]:
    raw_value = (value or "").strip()
    if not raw_value:
        config = config_type()
    else:
        try:
            config = config_type.model_validate(json.loads(raw_value))
        except (TypeError, ValueError):
            config = config_type()
    return config.model_dump(mode="json", by_alias=True)


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
        """Clear cached persisted and runtime settings."""
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
        upstream_param_override_config = cloned.get("upstream_param_override_config")
        if isinstance(upstream_param_override_config, dict):
            cloned["upstream_param_override_config"] = deepcopy(
                upstream_param_override_config
            )
        return cloned

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

    async def get_runtime_settings(self) -> dict[str, Any]:
        """Return normalized runtime settings with short-lived caching."""
        cached = self._runtime_settings_cache
        if (
            cached is not None
            and (monotonic() - self._runtime_settings_cache_at)
            < self._settings_cache_ttl_seconds
        ):
            return self._clone_runtime_settings(cached)

        items = effective_editable_setting_items(await self.list_settings())
        mapping = {item.key: item.value for item in items}
        cors_allow_origins = self._split_comma_lines(
            mapping.get(SETTING_CORS_ALLOW_ORIGINS, "")
        )
        time_zone = normalize_time_zone(mapping.get(SETTING_TIME_ZONE))
        runtime = {
            "proxy_url": mapping.get(SETTING_PROXY_URL, "").strip(),
            "auth_access_token_minutes": int(
                mapping[SETTING_AUTH_ACCESS_TOKEN_MINUTES]
            ),
            "request_timeout_seconds": float(mapping[SETTING_REQUEST_TIMEOUT_SECONDS]),
            "max_request_body_bytes": int(mapping[SETTING_MAX_REQUEST_BODY_BYTES]),
            "time_zone": time_zone,
            "cors_allow_origins": cors_allow_origins or ["*"],
            "relay_log_body_enabled": mapping[SETTING_RELAY_LOG_BODY_ENABLED] == "true",
            "relay_log_keep_enabled": mapping[SETTING_RELAY_LOG_KEEP_ENABLED] == "true",
            "relay_log_keep_period": int(mapping[SETTING_RELAY_LOG_KEEP_PERIOD]),
            "circuit_breaker_threshold": int(
                mapping[SETTING_CIRCUIT_BREAKER_THRESHOLD]
            ),
            "circuit_breaker_cooldown": int(mapping[SETTING_CIRCUIT_BREAKER_COOLDOWN]),
            "circuit_breaker_max_cooldown": int(
                mapping[SETTING_CIRCUIT_BREAKER_MAX_COOLDOWN]
            ),
            "health_window_seconds": int(mapping[SETTING_HEALTH_WINDOW_SECONDS]),
            "health_penalty_weight": float(mapping[SETTING_HEALTH_PENALTY_WEIGHT]),
            "health_min_samples": int(mapping[SETTING_HEALTH_MIN_SAMPLES]),
            "model_list_compat_mode_enabled": mapping[
                SETTING_MODEL_LIST_COMPAT_MODE_ENABLED
            ]
            == "true",
            "upstream_headers_config": _parse_upstream_config(
                mapping.get(SETTING_UPSTREAM_HEADERS_CONFIG), UpstreamHeadersConfig
            ),
            "upstream_param_override_config": _parse_upstream_config(
                mapping.get(SETTING_UPSTREAM_PARAM_OVERRIDE_CONFIG),
                UpstreamParamOverrideConfig,
            ),
            "site_name": mapping.get(SETTING_SITE_NAME, "Lens").strip() or "Lens",
            "site_logo_url": mapping.get(SETTING_SITE_LOGO_URL, "").strip(),
        }
        self._runtime_settings_cache = self._clone_runtime_settings(runtime)
        self._runtime_settings_cache_at = monotonic()
        return self._clone_runtime_settings(runtime)

    async def get_branding_settings(self) -> dict[str, str]:
        """Return the public branding subset of runtime settings."""
        runtime = await self.get_runtime_settings()
        return {
            "site_name": str(runtime["site_name"]),
            "site_logo_url": str(runtime["site_logo_url"]),
        }

    async def list_editable_settings(self) -> list[SettingItem]:
        """List normalized administrator-editable settings with defaults."""
        return effective_editable_setting_items(await self.list_settings())

    async def list_settings(self) -> list[SettingItem]:
        """List persisted settings with short-lived caching."""
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
        """Create or update settings and refresh the cache."""
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
