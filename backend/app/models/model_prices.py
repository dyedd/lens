from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.core.model_prices import (
    CONTEXT_TIER_PRICE_FIELDS,
    MAX_CONTEXT_PRICE_TIERS,
    PRICE_PAYLOAD_FIELDS,
)

from .protocols import ProtocolKind
from .validation import StrictBaseModel

MAX_CONTEXT_TIER_INPUT_TOKENS = 100_000_000


class ModelPriceContextTier(StrictBaseModel):
    """Token prices that replace the base prices above an input-token threshold."""

    above_input_tokens: int = Field(gt=0, le=MAX_CONTEXT_TIER_INPUT_TOKENS)
    input_price_per_million: float = Field(default=0.0, ge=0.0, allow_inf_nan=False)
    output_price_per_million: float = Field(default=0.0, ge=0.0, allow_inf_nan=False)
    cache_read_price_per_million: float = Field(
        default=0.0, ge=0.0, allow_inf_nan=False
    )
    cache_write_price_per_million: float = Field(
        default=0.0, ge=0.0, allow_inf_nan=False
    )


def _has_context_tier_price(tiers: list[ModelPriceContextTier]) -> bool:
    return any(
        getattr(tier, field) > 0
        for tier in tiers
        for field in CONTEXT_TIER_PRICE_FIELDS
    )


class ModelPriceItem(StrictBaseModel):
    model_key: str
    display_name: str
    protocols: list[ProtocolKind] = Field(default_factory=list)
    input_price_per_million: float = 0.0
    image_input_price_per_million: float = 0.0
    output_price_per_million: float = 0.0
    cache_read_price_per_million: float = 0.0
    cache_write_price_per_million: float = 0.0
    image_price_per_image: float = 0.0
    pricing_mode: Literal["free", "tokens", "non_tokens"] = "free"
    manual_override: bool = False
    context_tiers: list[ModelPriceContextTier] = Field(
        default_factory=list, max_length=MAX_CONTEXT_PRICE_TIERS
    )

    @model_validator(mode="after")
    def resolve_free_pricing(self) -> "ModelPriceItem":
        if not any(
            getattr(self, field) > 0 for field in PRICE_PAYLOAD_FIELDS
        ) and not _has_context_tier_price(self.context_tiers):
            self.pricing_mode = "free"
        elif self.pricing_mode == "free":
            self.pricing_mode = (
                "non_tokens" if self.image_price_per_image > 0 else "tokens"
            )
        return self


class ModelPriceUpdate(StrictBaseModel):
    model_key: str = Field(min_length=1)
    display_name: str = ""
    input_price_per_million: float = Field(default=0.0, ge=0.0, allow_inf_nan=False)
    image_input_price_per_million: float | None = Field(
        default=None, ge=0.0, allow_inf_nan=False
    )
    output_price_per_million: float = Field(default=0.0, ge=0.0, allow_inf_nan=False)
    cache_read_price_per_million: float = Field(
        default=0.0, ge=0.0, allow_inf_nan=False
    )
    cache_write_price_per_million: float = Field(
        default=0.0, ge=0.0, allow_inf_nan=False
    )
    image_price_per_image: float = Field(default=0.0, ge=0.0, allow_inf_nan=False)
    pricing_mode: Literal["free", "tokens", "non_tokens"] | None = None
    context_tiers: list[ModelPriceContextTier] = Field(
        default_factory=list, max_length=MAX_CONTEXT_PRICE_TIERS
    )

    @field_validator("context_tiers")
    @classmethod
    def validate_unique_context_thresholds(
        cls, tiers: list[ModelPriceContextTier]
    ) -> list[ModelPriceContextTier]:
        thresholds = [tier.above_input_tokens for tier in tiers]
        if len(set(thresholds)) != len(thresholds):
            raise ValueError("Context tier thresholds must be unique")
        return sorted(tiers, key=lambda tier: tier.above_input_tokens)


class ModelPriceListResponse(StrictBaseModel):
    items: list[ModelPriceItem] = Field(default_factory=list)
    last_synced_at: str | None = None
