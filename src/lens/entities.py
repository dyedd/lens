from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class AdminUserEntity(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ProviderEntity(Base):
    __tablename__ = "providers"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    protocol: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="enabled")
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    headers_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    model_patterns_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")


class ModelGroupEntity(Base):
    __tablename__ = "model_groups"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    protocol: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    strategy: Mapped[str] = mapped_column(String(32), nullable=False, default="round_robin")
    provider_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class GatewayKeyEntity(Base):
    __tablename__ = "gateway_keys"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    secret: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


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
    provider_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    gateway_key_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    success: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False, index=True)
