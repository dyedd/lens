from __future__ import annotations

from typing import Any

from conftest import gateway_headers, valid_site_payload

from app.core.runtime_channel_ids import compose_runtime_channel_id
from app.models.protocols import ProtocolKind


def _protocol_group_item(
    protocol: str,
    model_name: str,
    *,
    protocol_config_id: str = "pc-1",
    credential_id: str = "cred-1",
) -> dict[str, Any]:
    return {
        "channel_id": compose_runtime_channel_id(
            protocol_config_id, ProtocolKind(protocol)
        ),
        "credential_id": credential_id,
        "model_name": model_name,
        "enabled": True,
    }


def test_openai_model_list_returns_available_models(
    client,
    create_site_group_and_key,
) -> None:
    _site, _group, key = create_site_group_and_key()

    response = client.get("/v1/models", headers=gateway_headers(key))

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == "gpt-4o"


def test_gemini_model_list_returns_gemini_shape(
    client,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    create_site(valid_site_payload(protocols=["gemini"], model_name="gemini-pro"))
    create_model_group(
        name="gemini-pro",
        items=[_protocol_group_item("gemini", "gemini-pro")],
    )
    key = create_gateway_key()

    response = client.get("/v1beta/models", headers=gateway_headers(key))

    assert response.status_code == 200
    assert response.json()["models"][0]["name"] == "models/gemini-pro"
