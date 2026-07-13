from __future__ import annotations

from ..shared import Any, UTC, ZoneInfo, datetime, timedelta


class _OverviewCommonMixin:
    def _to_utc_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _request_log_prune_cutoff(*, keep_days: int, time_zone: ZoneInfo) -> datetime:
        local_now = datetime.now(time_zone)
        local_cutoff = local_now.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=max(keep_days, 1) - 1)
        return local_cutoff.astimezone(UTC).replace(tzinfo=None)

    @classmethod
    def _daily_stats_by_local_bucket(
        cls, rows: list[Any], time_zone: ZoneInfo
    ) -> dict[str, dict[str, float]]:
        buckets: dict[str, dict[str, float]] = {}
        for row in rows:
            (
                created_at,
                success,
                latency_ms,
                input_tokens,
                cache_read_input_tokens,
                cache_write_input_tokens,
                output_tokens,
                total_tokens,
                input_cost_usd,
                output_cost_usd,
                total_cost_usd,
            ) = row
            utc_created_at = cls._to_utc_datetime(created_at)
            if utc_created_at is None:
                continue
            date_value = utc_created_at.astimezone(time_zone).strftime("%Y%m%d")
            current = buckets.setdefault(
                date_value,
                {
                    "request_count": 0.0,
                    "successful_requests": 0.0,
                    "failed_requests": 0.0,
                    "wait_time_ms": 0.0,
                    "input_tokens": 0.0,
                    "cache_read_input_tokens": 0.0,
                    "cache_write_input_tokens": 0.0,
                    "output_tokens": 0.0,
                    "total_tokens": 0.0,
                    "input_cost_usd": 0.0,
                    "output_cost_usd": 0.0,
                    "total_cost_usd": 0.0,
                },
            )
            success_value = 1.0 if int(success) else 0.0
            current["request_count"] += 1.0
            current["successful_requests"] += success_value
            current["failed_requests"] += 0.0 if success_value else 1.0
            current["wait_time_ms"] += float(latency_ms)
            current["input_tokens"] += float(input_tokens)
            current["cache_read_input_tokens"] += float(cache_read_input_tokens)
            current["cache_write_input_tokens"] += float(cache_write_input_tokens)
            current["output_tokens"] += float(output_tokens)
            current["total_tokens"] += float(total_tokens)
            current["input_cost_usd"] += float(input_cost_usd)
            current["output_cost_usd"] += float(output_cost_usd)
            current["total_cost_usd"] += float(total_cost_usd)
        return buckets

    @classmethod
    def _model_rows_by_local_bucket(
        cls, rows: list[Any], format_text: str, time_zone: ZoneInfo
    ) -> list[tuple[str, str, int, int, float]]:
        buckets: dict[tuple[str, str], list[float]] = {}
        for created_at, model, total_tokens, total_cost in rows:
            if not model or created_at is None:
                continue
            utc_created_at = cls._to_utc_datetime(created_at)
            if utc_created_at is None:
                continue
            bucket = utc_created_at.astimezone(time_zone).strftime(format_text)
            key = (bucket, str(model))
            current = buckets.setdefault(key, [0.0, 0.0, 0.0])
            current[0] += 1
            current[1] += float(total_tokens)
            current[2] += float(total_cost)
        return [
            (date_value, model, int(values[0]), int(values[1]), float(values[2]))
            for (date_value, model), values in sorted(buckets.items())
        ]
