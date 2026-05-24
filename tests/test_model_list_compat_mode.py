from lens_api.gateway import service
from lens_api.models import GatewayApiKey, ModelGroup, ProtocolKind, RoutingStrategy
from lens_api.persistence.domain_store import (
    SETTING_MODEL_LIST_COMPAT_MODE_ENABLED,
    DomainStore,
)


def _group(name: str, protocol: ProtocolKind) -> ModelGroup:
    return ModelGroup(
        id=f"{protocol.value}:{name}",
        name=name,
        protocol=protocol,
        strategy=RoutingStrategy.ROUND_ROBIN,
    )


def _gateway_key(*, allowed_models: list[str] | None = None) -> GatewayApiKey:
    return GatewayApiKey(
        id="gateway-key",
        api_key="sk-lens-test",
        allowed_models=allowed_models or [],
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


def test_openai_model_list_keeps_default_protocol_filter() -> None:
    payload = service._build_openai_models_payload(
        [
            _group("gpt-4.1", ProtocolKind.OPENAI_CHAT),
            _group("claude-sonnet-4", ProtocolKind.ANTHROPIC),
            _group("gemini-2.5-pro", ProtocolKind.GEMINI),
        ],
        _gateway_key(),
    )

    assert payload == {
        "object": "list",
        "data": [
            {
                "id": "gpt-4.1",
                "object": "model",
                "created": 0,
                "owned_by": "lens",
            }
        ],
    }


def test_compat_model_list_includes_all_protocols() -> None:
    payload = service._build_openai_models_payload(
        [
            _group("gpt-4.1", ProtocolKind.OPENAI_CHAT),
            _group("gpt-4.1-responses", ProtocolKind.OPENAI_RESPONSES),
            _group("text-embedding-3-large", ProtocolKind.OPENAI_EMBEDDING),
            _group("claude-sonnet-4", ProtocolKind.ANTHROPIC),
            _group("gemini-2.5-pro", ProtocolKind.GEMINI),
        ],
        _gateway_key(),
        service._ALL_MODEL_LIST_PROTOCOLS,
    )

    assert [item["id"] for item in payload["data"]] == [
        "claude-sonnet-4",
        "gemini-2.5-pro",
        "gpt-4.1",
        "gpt-4.1-responses",
        "text-embedding-3-large",
    ]
    assert payload["object"] == "list"
    assert all(item["object"] == "model" for item in payload["data"])


def test_compat_model_list_respects_allowed_models() -> None:
    payload = service._build_openai_models_payload(
        [
            _group("gpt-4.1", ProtocolKind.OPENAI_CHAT),
            _group("claude-sonnet-4", ProtocolKind.ANTHROPIC),
            _group("gemini-2.5-pro", ProtocolKind.GEMINI),
        ],
        _gateway_key(allowed_models=["claude-sonnet-4", "gemini-2.5-pro"]),
        service._ALL_MODEL_LIST_PROTOCOLS,
    )

    assert [item["id"] for item in payload["data"]] == [
        "claude-sonnet-4",
        "gemini-2.5-pro",
    ]


def test_anthropic_model_list_keeps_anthropic_format() -> None:
    payload = service._build_anthropic_models_payload(
        [
            _group("gpt-4.1", ProtocolKind.OPENAI_CHAT),
            _group("claude-sonnet-4", ProtocolKind.ANTHROPIC),
        ],
        _gateway_key(),
    )

    assert payload == {
        "data": [
            {
                "id": "claude-sonnet-4",
                "type": "model",
                "display_name": "claude-sonnet-4",
                "created_at": "1970-01-01T00:00:00Z",
            }
        ],
        "first_id": "claude-sonnet-4",
        "last_id": "claude-sonnet-4",
        "has_more": False,
    }


def test_model_list_compat_mode_setting_defaults_to_disabled() -> None:
    assert (
        DomainStore._parse_bool(
            None,
            default=False,
        )
        is False
    )


def test_model_list_compat_mode_setting_parses_true() -> None:
    assert (
        DomainStore._parse_bool(
            "true",
            default=False,
        )
        is True
    )
    assert SETTING_MODEL_LIST_COMPAT_MODE_ENABLED == "model_list_compat_mode_enabled"
