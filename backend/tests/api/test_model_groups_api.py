from __future__ import annotations

import json

import httpx
import pytest
from conftest import (
    assert_error,
    openai_chat_channel_id,
    run_async,
    valid_site_payload,
)

from app.core.runtime_channel_ids import compose_runtime_channel_id
from app.models.protocols import ProtocolKind


def _member(
    *,
    channel_id: str | None = None,
    credential_id: str = "cred-1",
    model_name: str = "gpt-4o",
    enabled: bool = True,
) -> dict[str, object]:
    return {
        "channel_id": channel_id or openai_chat_channel_id(),
        "credential_id": credential_id,
        "model_name": model_name,
        "enabled": enabled,
    }


def test_model_group_model_test_uses_persisted_image_credential(
    client,
    admin_headers,
    app_state,
    create_site,
    create_model_group,
    monkeypatch,
) -> None:
    protocol = ProtocolKind.OPENAI_IMAGE
    channel_id = compose_runtime_channel_id("pc-image", protocol)
    site_payload = valid_site_payload(
        protocol_config_id="pc-image",
        protocols=[protocol.value],
        model_name="gpt-image-1",
    )
    site_payload["protocols"][0]["headers"] = [
        {
            "name": "X-Persisted-Header",
            "action": "override",
            "value": "model-group-test",
        },
        {
            "name": "User-Agent",
            "action": "override",
            "value": "configured-model-group-probe",
        },
    ]
    create_site(site_payload)
    group = create_model_group(
        name="image-group",
        items=[
            _member(
                channel_id=channel_id,
                model_name="gpt-image-1",
            )
        ],
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer upstream-secret"
        assert request.headers["X-Persisted-Header"] == "model-group-test"
        assert request.headers["User-Agent"] == "configured-model-group-probe"
        assert json.loads(request.content) == {
            "model": "gpt-image-1",
            "prompt": "draw a lens",
            "n": 1,
            "size": "1024x1024",
        }
        return httpx.Response(
            200,
            json={"data": [{"revised_prompt": "a polished lens"}]},
            request=request,
        )

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    import app.gateway.service.tasks.site_model_probe as probe

    monkeypatch.setattr(probe, "app_state", app_state)
    monkeypatch.setattr(probe, "_resolve_http_client", lambda _proxy: upstream_client)
    request_payload = {
        "channel_id": channel_id,
        "credential_id": "cred-1",
        "model_name": "gpt-image-1",
        "prompt": "draw a lens",
    }
    injected_response = client.post(
        f"/api/admin/model-groups/{group['id']}/model-tests",
        headers=admin_headers,
        json={**request_payload, "api_key": "injected"},
    )
    assert injected_response.status_code == 422, injected_response.text
    try:
        response = client.post(
            f"/api/admin/model-groups/{group['id']}/model-tests",
            headers=admin_headers,
            json=request_payload,
        )
    finally:
        run_async(upstream_client.aclose())

    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    assert response.json()["output_text"] == "a polished lens"
    assert "upstream-secret" not in response.text


@pytest.mark.parametrize(
    ("model_name", "disable_site", "message"),
    [
        ("not-a-member", False, "not a member"),
        ("gpt-4o", True, "unavailable"),
    ],
)
def test_model_group_model_test_rejects_non_member_or_unavailable_member(
    client,
    admin_headers,
    create_site,
    create_model_group,
    model_name,
    disable_site,
    message,
) -> None:
    site = create_site(valid_site_payload())
    group = create_model_group(
        items=[_member()],
    )
    if disable_site:
        disabled = client.put(
            f"/api/admin/sites/{site['id']}/enabled",
            headers=admin_headers,
            json={"enabled": False},
        )
        assert disabled.status_code == 200, disabled.text

    response = client.post(
        f"/api/admin/model-groups/{group['id']}/model-tests",
        headers=admin_headers,
        json={
            "channel_id": openai_chat_channel_id(),
            "credential_id": "cred-1",
            "model_name": model_name,
            "prompt": "ping",
        },
    )

    assert_error(response, 400, message)


def test_model_group_crud_round_trip(client, admin_headers, create_model_group) -> None:
    assert client.get("/api/admin/model-groups", headers=admin_headers).json() == []

    group = create_model_group(name="gpt-4o")
    assert group["name"] == "gpt-4o"
    assert group["client_protocols"] == []

    detail = client.get(f"/api/admin/model-groups/{group['id']}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["id"] == group["id"]

    update = client.put(
        f"/api/admin/model-groups/{group['id']}",
        headers=admin_headers,
        json={
            "name": "gpt-4.1",
            "headers": [{"name": "X-Group", "action": "override", "value": "second"}],
        },
    )
    assert update.status_code == 200
    assert update.json()["name"] == "gpt-4.1"
    assert update.json()["headers"] == [
        {"name": "X-Group", "action": "override", "value": "second", "match": None}
    ]

    delete = client.delete(
        f"/api/admin/model-groups/{group['id']}", headers=admin_headers
    )
    assert delete.status_code == 204
    assert client.get("/api/admin/model-groups", headers=admin_headers).json() == []


def test_model_group_fallback_groups_round_trip(
    client, admin_headers, create_model_group
) -> None:
    primary = create_model_group(name="primary")
    fallback = create_model_group(name="fallback")

    response = client.put(
        f"/api/admin/model-groups/{primary['id']}",
        headers=admin_headers,
        json={"fallback_group_ids": [fallback["id"]]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["fallback_group_ids"] == [fallback["id"]]


def test_model_group_rejects_missing_fallback_group(
    client, admin_headers, create_model_group
) -> None:
    group = create_model_group(name="primary")

    response = client.put(
        f"/api/admin/model-groups/{group['id']}",
        headers=admin_headers,
        json={"fallback_group_ids": ["missing"]},
    )

    assert_error(response, 400, "Fallback model group not found")


def test_model_group_derives_client_protocols_from_member(
    client, admin_headers, create_site
) -> None:
    create_site(valid_site_payload())

    response = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={"name": "derived", "items": [_member()]},
    )

    assert response.status_code == 201, response.text
    assert response.json()["client_protocols"] == [
        "openai_chat",
        "openai_responses",
        "anthropic",
    ]


def test_model_group_strategy_switch_preserves_shared_member_order(
    client,
    admin_headers,
    create_site,
) -> None:
    site_payload = valid_site_payload(model_name="model-a")
    site_payload["protocols"][0]["models"].append(
        {
            "credential_id": "cred-1",
            "model_name": "model-b",
            "enabled": True,
            "protocol": "openai_chat",
        }
    )
    create_site(site_payload)
    created = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "ordered-group",
            "strategy": "round_robin",
            "items": [
                _member(model_name="model-a"),
                _member(model_name="model-b"),
            ],
        },
    )
    assert created.status_code == 201
    group_id = created.json()["id"]

    failover = client.put(
        f"/api/admin/model-groups/{group_id}",
        headers=admin_headers,
        json={"strategy": "failover"},
    )
    assert failover.status_code == 200
    assert [item["model_name"] for item in failover.json()["items"]] == [
        "model-a",
        "model-b",
    ]

    reordered = client.put(
        f"/api/admin/model-groups/{group_id}",
        headers=admin_headers,
        json={
            "items": [
                _member(model_name="model-b"),
                _member(model_name="model-a"),
            ]
        },
    )
    assert reordered.status_code == 200

    round_robin = client.put(
        f"/api/admin/model-groups/{group_id}",
        headers=admin_headers,
        json={"strategy": "round_robin"},
    )
    assert round_robin.status_code == 200
    assert [item["model_name"] for item in round_robin.json()["items"]] == [
        "model-b",
        "model-a",
    ]


def test_create_model_group_rejects_duplicate_names(
    client,
    admin_headers,
    create_model_group,
) -> None:
    create_model_group(name="gpt-4o")

    response = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={"name": "gpt-4o"},
    )

    assert_error(response, 400, "Model group already exists")


def test_create_model_group_with_site_member_hydrates_member_metadata(
    client,
    admin_headers,
    create_site,
) -> None:
    site = create_site(valid_site_payload())

    response = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "gpt-4o",
            "items": [_member()],
        },
    )

    assert response.status_code == 201
    item = response.json()["items"][0]
    assert item["channel_id"] == openai_chat_channel_id()
    assert item["site_id"] == site["id"]
    assert item["channel_name"] == "OpenAI Site"
    assert item["protocol"] == "openai_chat"
    assert item["credential_id"] == "cred-1"
    assert item["credential_name"] == "primary-key"


def test_create_model_group_rejects_blank_name(client, admin_headers) -> None:
    response = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={"name": " "},
    )

    assert_error(response, 400, "Model group name is required")


@pytest.mark.parametrize(
    ("site_overrides", "member_overrides", "message"),
    [
        (None, {"channel_id": "missing_openai_chat"}, "Channels not found"),
        ({}, {"credential_id": "missing"}, "Credential not found in channel"),
        ({"protocol_enabled": False}, {}, "is disabled"),
        ({"credential_enabled": False}, {}, "Credential is disabled"),
        (
            {"model_name": "gpt-4o"},
            {"model_name": "missing-model"},
            "Model not found in channel",
        ),
    ],
)
def test_create_model_group_rejects_invalid_members(
    client,
    admin_headers,
    create_site,
    site_overrides,
    member_overrides,
    message,
) -> None:
    if site_overrides is not None:
        create_site(valid_site_payload(**site_overrides))

    response = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "gpt-4o",
            "items": [_member(**member_overrides)],
        },
    )

    assert_error(response, 400, message)


def test_model_group_missing_resources_return_not_found(
    client,
    admin_headers,
) -> None:
    get_response = client.get("/api/admin/model-groups/missing", headers=admin_headers)
    update_response = client.put(
        "/api/admin/model-groups/missing",
        headers=admin_headers,
        json={"name": "unused"},
    )
    delete_response = client.delete(
        "/api/admin/model-groups/missing", headers=admin_headers
    )

    assert_error(get_response, 404, "missing")
    assert_error(update_response, 404, "missing")
    assert_error(delete_response, 404, "missing")
