from lens_api.models import (
    ProtocolKind,
    SiteBaseUrl,
    SiteConfig,
    SiteCredential,
    SiteModel,
    SiteModelInput,
    SiteProtocolConfig,
)
from lens_api.persistence.channel_store import ChannelStore, _deduplicate_combo_models


def _model(
    model_name: str,
    protocol: ProtocolKind | None,
    credential_id: str = "key-1",
    enabled: bool = True,
) -> SiteModelInput:
    return SiteModelInput(
        credential_id=credential_id,
        model_name=model_name,
        protocol=protocol,
        enabled=enabled,
    )


def test_deduplicate_combo_models_merges_same_name_across_protocols() -> None:
    models = _deduplicate_combo_models(
        [
            _model("kimi-k2.6", ProtocolKind.OPENAI_CHAT),
            _model("kimi-k2.6", ProtocolKind.OPENAI_RESPONSES),
        ]
    )

    assert len(models) == 1
    assert models[0].model_name == "kimi-k2.6"
    assert models[0].protocol is None


def test_deduplicate_combo_models_keeps_distinct_credentials() -> None:
    models = _deduplicate_combo_models(
        [
            _model("kimi-k2.6", ProtocolKind.OPENAI_CHAT, credential_id="key-1"),
            _model("kimi-k2.6", ProtocolKind.OPENAI_CHAT, credential_id="key-2"),
        ]
    )

    assert len(models) == 2


def test_deduplicate_combo_models_merges_exact_duplicates_without_widening_protocol() -> None:
    models = _deduplicate_combo_models(
        [
            _model("kimi-k2.6", ProtocolKind.OPENAI_CHAT, enabled=False),
            _model("kimi-k2.6", ProtocolKind.OPENAI_CHAT, enabled=True),
        ]
    )

    assert len(models) == 1
    assert models[0].protocol == ProtocolKind.OPENAI_CHAT
    assert models[0].enabled is True


def test_flatten_site_uses_site_name_for_channel_display() -> None:
    site = SiteConfig(
        id="site-1",
        name="Actual Channel",
        base_urls=[
            SiteBaseUrl(
                id="base-1",
                url="https://api.example.com",
                compatible_protocols=[ProtocolKind.OPENAI_CHAT],
            )
        ],
        credentials=[
            SiteCredential(id="key-1", name="Primary", api_key="sk-test")
        ],
        protocols=[
            SiteProtocolConfig(
                id="combo-1",
                name="组合 1",
                base_url_id="base-1",
                credential_id="key-1",
                models=[
                    SiteModel(
                        id="model-1",
                        credential_id="key-1",
                        credential_name="Primary",
                        model_name="gpt-5-mini",
                        protocol=ProtocolKind.OPENAI_CHAT,
                    )
                ],
            )
        ],
    )

    channels = ChannelStore(None)._flatten_site(site)  # type: ignore[arg-type]

    assert len(channels) == 1
    assert channels[0].name == "Actual Channel"
