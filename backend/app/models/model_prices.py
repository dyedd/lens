from typing import Literal

from pydantic import Field, model_validator

from app.core.model_prices import PRICE_PAYLOAD_FIELDS

from .protocols import ProtocolKind
from .validation import StrictBaseModel


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

    @model_validator(mode="after")
    def resolve_free_pricing(self) -> "ModelPriceItem":
        if not any(getattr(self, field) > 0 for field in PRICE_PAYLOAD_FIELDS):
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


class ModelPriceListResponse(StrictBaseModel):
    items: list[ModelPriceItem] = Field(default_factory=list)
    last_synced_at: str | None = None
