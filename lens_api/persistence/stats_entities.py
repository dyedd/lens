from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


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
    cache_read_input_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    cache_write_input_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
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
