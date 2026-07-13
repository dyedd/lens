from __future__ import annotations

from typing import Any

from conftest import create_site_group_and_key, gateway_headers, valid_site_payload
from lens_api.core.runtime_channel_ids import compose_runtime_channel_id
from lens_api.models import ProtocolKind
from lens_api.persistence.shared import SETTING_MODEL_LIST_COMPAT_MODE_ENABLED


def _protocol_group_item(protocol: str, model_name: str) -> dict[str, Any]:
    return {
        "channel_id": compose_runtime_channel_id("pc-1", ProtocolKind(protocol)),
        "credential_id": "cred-1",
        "model_name": model_name,
        "enabled": True,
    }


def test_openai_model_list_filters_enabled_groups_and_allowed_models(
    client,
    create_site_group_and_key,
    create_gateway_key,
) -> None:
    _site, _group, unrestricted_key = create_site_group_and_key()
    restricted_key = create_gateway_key(allowed_models=["other-model"])

    unrestricted = client.get("/v1/models", headers=gateway_headers(unrestricted_key))
    restricted = client.get("/v1/models", headers=gateway_headers(restricted_key))

    assert unrestricted.status_code == 200
    assert [item["id"] for item in unrestricted.json()["data"]] == ["gpt-4o"]
    assert restricted.status_code == 200
    assert restricted.json()["data"] == []


def test_openai_model_list_matches_allowed_models_case_insensitively(
    client,
    create_site_group_and_key,
    create_gateway_key,
) -> None:
    create_site_group_and_key()
    key = create_gateway_key(allowed_models=[" GPT-4O "])

    response = client.get("/v1/models", headers=gateway_headers(key))

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == "gpt-4o"


def test_openai_model_list_excludes_groups_without_enabled_members(
    client,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    create_site(valid_site_payload(model_name="gpt-4o"))
    disabled_member = _protocol_group_item("openai_chat", "gpt-4o")
    disabled_member["enabled"] = False
    create_model_group(name="gpt-4o", items=[disabled_member])
    key = create_gateway_key()

    response = client.get("/v1/models", headers=gateway_headers(key))

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_openai_model_list_can_expose_route_group_name(
    client,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    create_site(valid_site_payload(model_name="internal-model"))
    execution = create_model_group(
        name="internal-model",
        items=[_protocol_group_item("openai_chat", "internal-model")],
    )
    create_model_group(
        name="public-model",
        route_group_id=execution["id"],
    )
    key = create_gateway_key(allowed_models=["public-model"])

    response = client.get("/v1/models", headers=gateway_headers(key))

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == ["public-model"]


def test_anthropic_model_list_uses_anthropic_shape(
    client,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    create_site(
        valid_site_payload(protocols=["anthropic"], model_name="claude-3-haiku")
    )
    create_model_group(
        name="claude-3-haiku",
        protocols=["anthropic"],
        items=[_protocol_group_item("anthropic", "claude-3-haiku")],
    )
    key = create_gateway_key()

    response = client.get(
        "/v1/models",
        headers={**gateway_headers(key), "anthropic-version": "2023-06-01"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"][0]["id"] == "claude-3-haiku"
    assert payload["first_id"] == "claude-3-haiku"
    assert payload["has_more"] is False


def test_gemini_model_list_uses_gemini_shape(
    client,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    create_site(valid_site_payload(protocols=["gemini"], model_name="gemini-pro"))
    create_model_group(
        name="gemini-pro",
        protocols=["gemini"],
        items=[_protocol_group_item("gemini", "gemini-pro")],
    )
    key = create_gateway_key()

    response = client.get("/v1beta/models", headers=gateway_headers(key))

    assert response.status_code == 200
    assert response.json()["models"][0]["name"] == "models/gemini-pro"


def test_model_list_compat_mode_exposes_non_openai_groups(
    client,
    admin_headers,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    create_site(valid_site_payload(protocols=["gemini"], model_name="gemini-pro"))
    create_model_group(
        name="gemini-pro",
        protocols=["gemini"],
        items=[_protocol_group_item("gemini", "gemini-pro")],
    )
    key = create_gateway_key()

    normal = client.get("/v1/models", headers=gateway_headers(key))
    client.put(
        "/api/admin/settings",
        headers=admin_headers,
        json={
            "items": [{"key": SETTING_MODEL_LIST_COMPAT_MODE_ENABLED, "value": "true"}]
        },
    )
    compatible = client.get("/v1/models", headers=gateway_headers(key))

    assert normal.status_code == 200
    assert normal.json()["data"] == []
    assert compatible.status_code == 200
    assert compatible.json()["data"][0]["id"] == "gemini-pro"
