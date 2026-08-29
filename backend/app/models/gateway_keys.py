from pydantic import Field, field_validator

from .validation import StrictBaseModel


class GatewayApiKeyBase(StrictBaseModel):
    remark: str = ""
    enabled: bool = True
    allowed_models: list[str] = Field(default_factory=list)
    max_cost_usd: float = Field(default=0.0, ge=0.0)
    expires_at: str | None = None

    @field_validator("allowed_models")
    @classmethod
    def canonicalize_allowed_models(cls, models: list[str]) -> list[str]:
        canonical_models: list[str] = []
        seen: set[str] = set()
        for item in models:
            value = str(item).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            canonical_models.append(value)
        return canonical_models


class GatewayApiKeyCreate(GatewayApiKeyBase):
    pass


class GatewayApiKeyUpdate(GatewayApiKeyBase):
    pass


class GatewayApiKey(GatewayApiKeyBase):
    id: str
    api_key: str
    spent_cost_usd: float = 0.0
    created_at: str
    updated_at: str
