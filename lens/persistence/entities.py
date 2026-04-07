from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, Integer, String, Text
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
    base_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")


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

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    protocol: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    strategy: Mapped[str] = mapped_column(String(32), nullable=False, default="round_robin")
    match_regex: Mapped[str] = mapped_column(Text, nullable=False, default="")


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


class RequestLogEntity(Base):
    __tablename__ = "request_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    protocol: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    requested_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    matched_group_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    channel_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    channel_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    gateway_key_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    success: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_stream: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_token_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resolved_model: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    output_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    request_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False, index=True)


class ModelPriceEntity(Base):
    __tablename__ = "model_prices"

    model_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    input_price_per_million: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    output_price_per_million: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cache_read_price_per_million: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cache_write_price_per_million: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


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
