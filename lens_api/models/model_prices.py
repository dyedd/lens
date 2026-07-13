from pydantic import Field

from .common import StrictBaseModel
from .protocols import ProtocolKind

class ModelPriceItem(StrictBaseModel):
    model_key: str
    display_name: str
    protocols: list[ProtocolKind] = Field(default_factory=list)
    input_price_per_million: float = 0.0
    output_price_per_million: float = 0.0
    cache_read_price_per_million: float = 0.0
    cache_write_price_per_million: float = 0.0


class ModelPriceUpdate(StrictBaseModel):
    model_key: str = Field(min_length=1)
    display_name: str = ""
    input_price_per_million: float = Field(default=0.0, ge=0.0)
    output_price_per_million: float = Field(default=0.0, ge=0.0)
    cache_read_price_per_million: float = Field(default=0.0, ge=0.0)
    cache_write_price_per_million: float = Field(default=0.0, ge=0.0)


class ModelPriceListResponse(StrictBaseModel):
    items: list[ModelPriceItem] = Field(default_factory=list)
    last_synced_at: str | None = None
