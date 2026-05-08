from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class AdminUserEntity(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class SiteEntity(Base):
    __tablename__ = "sites"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)


class SiteBaseUrlEntity(Base):
    __tablename__ = "site_base_urls"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    site_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class SiteCredentialEntity(Base):
    __tablename__ = "site_credentials"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    site_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    api_key: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class SiteProtocolConfigEntity(Base):
    __tablename__ = "site_protocol_configs"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    site_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    protocol: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    headers_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    channel_proxy: Mapped[str] = mapped_column(Text, nullable=False, default="")
    param_override: Mapped[str] = mapped_column(Text, nullable=False, default="")
    match_regex: Mapped[str] = mapped_column(Text, nullable=False, default="")
    base_url_id: Mapped[str] = mapped_column(String(80), nullable=False, default="")


class SiteProtocolCredentialBindingEntity(Base):
    __tablename__ = "site_protocol_credential_bindings"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    protocol_config_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    credential_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class SiteDiscoveredModelEntity(Base):
    __tablename__ = "site_discovered_models"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    protocol_config_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    credential_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ModelGroupEntity(Base):
    __tablename__ = "model_groups"
    __table_args__ = (
        CheckConstraint(
            "sync_filter_mode IN ('', 'contains', 'regex')",
            name="ck_model_groups_sync_filter_mode",
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    protocol: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    strategy: Mapped[str] = mapped_column(String(32), nullable=False, default="round_robin")
    route_group_id: Mapped[str] = mapped_column(String(80), nullable=False, default="", index=True)
    sync_filter_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    sync_filter_query: Mapped[str] = mapped_column(Text, nullable=False, default="")


class ModelGroupItemEntity(Base):
    __tablename__ = "model_group_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    channel_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    credential_id: Mapped[str] = mapped_column(String(80), nullable=False, default="", index=True)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class SettingEntity(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class GatewayApiKeyEntity(Base):
    __tablename__ = "gateway_api_keys"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    remark: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    api_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    allowed_models_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    max_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class RequestLogEntity(Base):
    __tablename__ = "request_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    protocol: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    requested_group_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    resolved_group_name: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    upstream_model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    channel_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    channel_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    gateway_key_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lifecycle_status: Mapped[str] = mapped_column(String(32), nullable=False, default="succeeded", index=True)
    is_stream: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_token_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_read_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_write_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    output_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    request_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    stats_archived: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False, index=True)


class ModelPriceEntity(Base):
    __tablename__ = "model_prices"

    model_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    input_price_per_million: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    output_price_per_million: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cache_read_price_per_million: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cache_write_price_per_million: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class CronjobEntity(Base):
    __tablename__ = "cronjobs"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    schedule_type: Mapped[str] = mapped_column(String(16), nullable=False, default="interval")
    interval_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    run_at_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    weekdays_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="idle", index=True)
    last_started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    next_run_at: Mapped[datetime | None] = mapped_column(nullable=True, index=True)
    lease_owner: Mapped[str] = mapped_column(String(80), nullable=False, default="", index=True)
    lease_until: Mapped[datetime | None] = mapped_column(nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ImportedStatsTotalEntity(Base):
    __tablename__ = "imported_stats_total"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    input_token: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_token: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    output_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    wait_time: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request_success: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ImportedStatsDailyEntity(Base):
    __tablename__ = "imported_stats_daily"

    date: Mapped[str] = mapped_column(String(8), primary_key=True)
    input_token: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_token: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    output_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    wait_time: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request_success: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class RequestLogDailyStatsEntity(Base):
    __tablename__ = "request_log_daily_stats"

    date: Mapped[str] = mapped_column(String(8), primary_key=True)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wait_time_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_read_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_write_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    output_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class OverviewModelDailyStatsEntity(Base):
    __tablename__ = "overview_model_daily_stats"

    date: Mapped[str] = mapped_column(String(8), primary_key=True)
    model: Mapped[str] = mapped_column(String(200), primary_key=True)
    requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
