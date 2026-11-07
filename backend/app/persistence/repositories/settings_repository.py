from __future__ import annotations

import json
from time import monotonic

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.cooldown_rules import compile_detection_rules
from app.core.time_zone import validate_time_zone_name
from app.models.settings import RuntimeSettings, SettingItem
from app.persistence.entities import SettingEntity
from app.persistence.settings_keys import (
    SETTING_AUTH_ACCESS_TOKEN_MINUTES,
    SETTING_CIRCUIT_BREAKER_AUTH_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_BACKOFF_MULTIPLIER,
    SETTING_CIRCUIT_BREAKER_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_ESCALATE_THRESHOLD,
    SETTING_CIRCUIT_BREAKER_ESCALATE_WINDOW,
    SETTING_CIRCUIT_BREAKER_FAILURE_WINDOW,
    SETTING_CIRCUIT_BREAKER_MAX_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_NETWORK_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_NETWORK_THRESHOLD,
    SETTING_CIRCUIT_BREAKER_NOT_FOUND_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_RATE_LIMIT_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_THRESHOLD,
    SETTING_CIRCUIT_BREAKER_TIMEOUT_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_TIMEOUT_THRESHOLD,
    SETTING_COOLDOWN_DETECTION_RULES,
    SETTING_CORS_ALLOW_ORIGINS,
    SETTING_FAILOVER_AFFINITY_SECONDS,
    SETTING_FAILOVER_COOLED_WAIT_SECONDS,
    SETTING_FIRST_TOKEN_TIMEOUT_SECONDS,
    SETTING_HEALTH_MIN_SAMPLES,
    SETTING_HEALTH_PENALTY_WEIGHT,
    SETTING_HEALTH_SCORING_ENABLED,
    SETTING_HEALTH_WINDOW_SECONDS,
    SETTING_MAX_REQUEST_BODY_BYTES,
    SETTING_PROXY_URL,
    SETTING_RELAY_LOG_BODY_ENABLED,
    SETTING_RELAY_LOG_KEEP_ENABLED,
    SETTING_RELAY_LOG_KEEP_PERIOD,
    SETTING_SITE_LOGO_URL,
    SETTING_SITE_NAME,
    SETTING_STREAM_IDLE_TIMEOUT_SECONDS,
    SETTING_TIME_ZONE,
    SETTING_UPSTREAM_HEADERS_CONFIG,
    SETTING_UPSTREAM_PARAM_OVERRIDE_CONFIG,
)

from ...models.cooldown_rules import CooldownDetectionRulesConfig
from ...models.upstream_rules import (
    UpstreamHeadersConfig,
    UpstreamParamOverrideConfig,
)
from ..editable_settings import effective_editable_setting_items


class SettingsRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        import asyncio

        self._session_factory = session_factory
        self._settings_cache: list[SettingItem] | None = None
        self._settings_cache_at = 0.0
        self._settings_cache_ttl_seconds = 2.0
        self._settings_cache_lock = asyncio.Lock()
        self._runtime_settings_cache: RuntimeSettings | None = None
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

    def _clone_runtime_settings(self, runtime: RuntimeSettings) -> RuntimeSettings:
        cloned = runtime.copy()
        cloned["cors_allow_origins"] = list(runtime["cors_allow_origins"])
        cloned["upstream_headers_config"] = runtime[
            "upstream_headers_config"
        ].model_copy(deep=True)
        cloned["upstream_param_override_config"] = runtime[
            "upstream_param_override_config"
        ].model_copy(deep=True)
        return cloned

    @staticmethod
    def _split_comma_lines(raw_value: str) -> list[str]:
        items: list[str] = []
        seen: set[str] = set()
        for chunk in raw_value.replace("\r", "\n").replace("，", ",").splitlines():
            for item in chunk.split(","):
                trimmed_item = item.strip()
                if not trimmed_item or trimmed_item in seen:
                    continue
                seen.add(trimmed_item)
                items.append(trimmed_item)
        return items

    async def get_runtime_settings(self) -> RuntimeSettings:
        """Return effective runtime settings with short-lived caching."""
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
        time_zone = validate_time_zone_name(mapping.get(SETTING_TIME_ZONE))
        runtime: RuntimeSettings = {
            "proxy_url": mapping.get(SETTING_PROXY_URL, "").strip(),
            "auth_access_token_minutes": int(
                mapping[SETTING_AUTH_ACCESS_TOKEN_MINUTES]
            ),
            "first_token_timeout_seconds": float(
                mapping[SETTING_FIRST_TOKEN_TIMEOUT_SECONDS]
            ),
            "stream_idle_timeout_seconds": float(
                mapping[SETTING_STREAM_IDLE_TIMEOUT_SECONDS]
            ),
            "max_request_body_bytes": int(mapping[SETTING_MAX_REQUEST_BODY_BYTES]),
            "time_zone": time_zone,
            "cors_allow_origins": cors_allow_origins or ["*"],
            "relay_log_body_enabled": mapping[SETTING_RELAY_LOG_BODY_ENABLED] == "true",
            "relay_log_keep_enabled": mapping[SETTING_RELAY_LOG_KEEP_ENABLED] == "true",
            "relay_log_keep_period": int(mapping[SETTING_RELAY_LOG_KEEP_PERIOD]),
            "circuit_breaker_threshold": int(
                mapping[SETTING_CIRCUIT_BREAKER_THRESHOLD]
            ),
            "circuit_breaker_failure_window_seconds": int(
                mapping[SETTING_CIRCUIT_BREAKER_FAILURE_WINDOW]
            ),
            "circuit_breaker_timeout_threshold": int(
                mapping[SETTING_CIRCUIT_BREAKER_TIMEOUT_THRESHOLD]
            ),
            "circuit_breaker_network_threshold": int(
                mapping[SETTING_CIRCUIT_BREAKER_NETWORK_THRESHOLD]
            ),
            "circuit_breaker_cooldown": int(mapping[SETTING_CIRCUIT_BREAKER_COOLDOWN]),
            "circuit_breaker_auth_cooldown": int(
                mapping[SETTING_CIRCUIT_BREAKER_AUTH_COOLDOWN]
            ),
            "circuit_breaker_not_found_cooldown": int(
                mapping[SETTING_CIRCUIT_BREAKER_NOT_FOUND_COOLDOWN]
            ),
            "circuit_breaker_rate_limit_cooldown": int(
                mapping[SETTING_CIRCUIT_BREAKER_RATE_LIMIT_COOLDOWN]
            ),
            "circuit_breaker_timeout_cooldown": int(
                mapping[SETTING_CIRCUIT_BREAKER_TIMEOUT_COOLDOWN]
            ),
            "circuit_breaker_network_cooldown": int(
                mapping[SETTING_CIRCUIT_BREAKER_NETWORK_COOLDOWN]
            ),
            "circuit_breaker_backoff_multiplier": float(
                mapping[SETTING_CIRCUIT_BREAKER_BACKOFF_MULTIPLIER]
            ),
            "circuit_breaker_max_cooldown": int(
                mapping[SETTING_CIRCUIT_BREAKER_MAX_COOLDOWN]
            ),
            "failover_cooled_wait_seconds": int(
                mapping[SETTING_FAILOVER_COOLED_WAIT_SECONDS]
            ),
            "circuit_breaker_escalate_threshold": int(
                mapping[SETTING_CIRCUIT_BREAKER_ESCALATE_THRESHOLD]
            ),
            "circuit_breaker_escalate_window_seconds": int(
                mapping[SETTING_CIRCUIT_BREAKER_ESCALATE_WINDOW]
            ),
            "failover_affinity_seconds": int(
                mapping[SETTING_FAILOVER_AFFINITY_SECONDS]
            ),
            "health_scoring_enabled": mapping[SETTING_HEALTH_SCORING_ENABLED] == "true",
            "health_window_seconds": int(mapping[SETTING_HEALTH_WINDOW_SECONDS]),
            "health_penalty_weight": float(mapping[SETTING_HEALTH_PENALTY_WEIGHT]),
            "health_min_samples": int(mapping[SETTING_HEALTH_MIN_SAMPLES]),
            "upstream_headers_config": UpstreamHeadersConfig.model_validate_json(
                mapping[SETTING_UPSTREAM_HEADERS_CONFIG]
            ),
            "upstream_param_override_config": UpstreamParamOverrideConfig.model_validate_json(
                mapping[SETTING_UPSTREAM_PARAM_OVERRIDE_CONFIG],
            ),
            "cooldown_detection_rules": compile_detection_rules(
                CooldownDetectionRulesConfig.model_validate(
                    json.loads(mapping[SETTING_COOLDOWN_DETECTION_RULES])
                ).rules
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
        """List effective administrator-editable settings with defaults."""
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
