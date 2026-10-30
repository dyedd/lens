from collections.abc import Sequence

from ..models.protocols import ProtocolKind
from ..models.sites import (
    SiteBaseUrl,
    SiteCredential,
    SiteModelInput,
    SiteProtocolConfigInput,
)
from .model_protocols import ENDPOINT_KIND_PROTOCOLS


def resolve_model_base_url_id(
    base_urls: Sequence[SiteBaseUrl],
    credentials: Sequence[SiteCredential],
    credential_id: str,
    protocol: ProtocolKind,
) -> str | None:
    candidates: list[tuple[int, str]] = []
    for url in base_urls:
        if url.kind == "models":
            continue
        owned = [item for item in credentials if item.base_url_id == url.id]
        bound = owned or [item for item in credentials if not item.base_url_id]
        if not any(item.id == credential_id for item in bound):
            continue
        pinned = ENDPOINT_KIND_PROTOCOLS.get(url.kind)
        if pinned is not None and pinned != protocol:
            continue
        priority = 2 if pinned is not None else int(url.kind == "china")
        candidates.append((priority, url.id))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def build_model_endpoint_configs(
    base_urls: Sequence[SiteBaseUrl],
    credentials: Sequence[SiteCredential],
    configs: Sequence[SiteProtocolConfigInput],
) -> list[SiteProtocolConfigInput]:
    configs_by_url = {config.base_url_id: config for config in configs}
    models_by_url: dict[str, dict[tuple[str, str, ProtocolKind], SiteModelInput]] = {
        config.base_url_id: {} for config in configs
    }
    for config in configs:
        for model in config.models:
            url_id = (
                resolve_model_base_url_id(
                    base_urls, credentials, model.credential_id, model.protocol
                )
                or config.base_url_id
            )
            if url_id not in configs_by_url:
                url_id = config.base_url_id
            key = (model.credential_id, model.model_name.strip(), model.protocol)
            models = models_by_url[url_id]
            if key not in models or config.base_url_id == url_id:
                models[key] = model
    return [
        config.model_copy(
            update={"models": list(models_by_url[config.base_url_id].values())}
        )
        for config in configs
    ]
