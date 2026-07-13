from __future__ import annotations

from dataclasses import dataclass, field

from ...models import ChannelConfig


@dataclass(slots=True)
class RouteTarget:
    """Describe a channel, model, and credential routing target."""

    channel: ChannelConfig
    model_name: str | None = None
    credential_id: str | None = None
    credential_name: str | None = None


@dataclass(slots=True)
class RouteSelection:
    """Contain a selected primary route and its ordered fallbacks."""

    primary: RouteTarget
    fallbacks: list[RouteTarget] = field(default_factory=list)


__all__ = ["RouteSelection", "RouteTarget"]
