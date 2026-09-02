from pydantic import Field

from .validation import StrictBaseModel


def health_tier(total_count: int, success_count: int) -> str:
    """Sole grading vocabulary for request health, shared with the admin UI."""
    if not total_count:
        return "no-data"
    if success_count == total_count:
        return "healthy"
    if not success_count:
        return "all-failed"
    rate = success_count / total_count
    if rate >= 0.99:
        return "mostly-healthy"
    if rate >= 0.9:
        return "partial"
    return "major"


class HealthBucket(StrictBaseModel):
    started_at: str
    ended_at: str
    success_count: int = 0
    total_count: int = 0
    tier: str = "no-data"


class HealthItem(StrictBaseModel):
    name: str
    success_count: int = 0
    total_count: int = 0
    tier: str = "no-data"
    buckets: list[HealthBucket] = Field(default_factory=list)


class HealthSummary(StrictBaseModel):
    started_at: str
    ended_at: str
    items: list[HealthItem] = Field(default_factory=list)
    next_offset: int | None = None
