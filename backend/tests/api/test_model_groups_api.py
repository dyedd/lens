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


@pytest.mark.parametrize("protocol", [ProtocolKind.OPENAI_IMAGE, ProtocolKind.AUTO])
def test_model_group_model_test_uses_persisted_image_credential(
    client,
    admin_headers,
    app_state,
    create_site,
    create_model_group,
    monkeypatch,
    protocol,
) -> None:
    channel_id = compose_runtime_channel_id("pc-image", protocol)
    site_payload = valid_site_payload(
        protocol_config_id="pc-image",
        protocols=[protocol.value],
        model_name="gpt-image-1",
    )
    site_payload["headers"] = [
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
    monkeypatch.setattr(probe, "resolve_http_client", lambda _proxy: upstream_client)
    request_payload = {
        "channel_id": channel_id,
        "credential_id": "cred-1",
        "model_name": "gpt-image-1",
        "prompt": "draw a lens",
    }
    if protocol == ProtocolKind.AUTO:
        request_payload["protocol"] = "openai_image"
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


def test_model_group_defaults_to_failover(client, admin_headers) -> None:
    response = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={"name": "default-failover-group", "items": []},
    )

    assert response.status_code == 201, response.text
    assert response.json()["strategy"] == "failover"


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
            "name": "custom-group",
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
    assert item["credential_mask"] == "ups…cret"
    assert item["base_url"] == "https://upstream.example/"


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
            "name": "custom-group",
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


def test_near_named_channel_model_stays_unplaced_and_is_listed(
    client,
    admin_headers,
    create_site,
    create_model_group,
) -> None:
    existing = create_model_group(name="claude-opus-4.5")
    create_site(valid_site_payload(model_name="claude-opus-4-5"))

    groups = client.get("/api/admin/model-groups", headers=admin_headers).json()
    response = client.get("/api/admin/unplaced-models", headers=admin_headers)

    assert [group["name"] for group in groups] == ["claude-opus-4.5"]
    assert response.status_code == 200, response.text
    [item] = response.json()["items"]
    assert item["model_name"] == "claude-opus-4-5"
    assert item["match_key"] == "claudeopus45"
    assert item["similar_group_ids"] == [existing["id"]]
    assert item["similar_group_names"] == ["claude-opus-4.5"]
    assert item["similar_model_names"] == []
    assert item["providers"] == [
        {
            "site_id": item["providers"][0]["site_id"],
            "channel_name": "OpenAI Site",
            "credential_id": "cred-1",
            "credential_name": "primary-key",
            "credential_number": 1,
            "credential_mask": "ups…cret",
            "base_url": "https://upstream.example/",
            "protocols": ["openai_chat"],
        }
    ]


def _create_group(client, admin_headers, **payload: object) -> dict[str, object]:
    response = client.post(
        "/api/admin/model-groups", headers=admin_headers, json=payload
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_merge_model_group_folds_source_into_target(
    client,
    admin_headers,
    create_site,
) -> None:
    create_site(valid_site_payload())
    target = next(
        group
        for group in client.get("/api/admin/model-groups", headers=admin_headers).json()
        if group["name"] == "gpt-4o"
    )
    client.put(
        f"/api/admin/model-groups/{target['id']}",
        headers=admin_headers,
        json={"match_regex": "-mini$"},
    )
    source = _create_group(
        client,
        admin_headers,
        name="gpt-4o-latest",
        match_models=["gpt-4o-2026", "GPT-4O"],
        match_regex="^gpt-4o-2",
        items=[_member()],
    )
    alias = _create_group(
        client, admin_headers, name="alias", route_group_id=source["id"]
    )
    vision = _create_group(
        client, admin_headers, name="vision", fallback_group_ids=[source["id"]]
    )

    response = client.post(
        f"/api/admin/model-groups/{source['id']}/merge",
        headers=admin_headers,
        json={"target_group_id": target["id"]},
    )

    assert response.status_code == 200, response.text
    merged = response.json()
    assert merged["match_models"] == ["gpt-4o", "gpt-4o-latest", "gpt-4o-2026"]
    assert merged["match_regex"] == "(?:-mini$)|(?:^gpt-4o-2)"
    assert [
        (item["model_name"], item["matched_by_rule"]) for item in merged["items"]
    ] == [("gpt-4o", False)]
    assert_error(
        client.get(f"/api/admin/model-groups/{source['id']}", headers=admin_headers),
        404,
    )
    assert (
        (
            client.get(
                f"/api/admin/model-groups/{alias['id']}", headers=admin_headers
            ).json()["route_group_id"]
        )
        == target["id"]
    )
    assert (
        client.get(
            f"/api/admin/model-groups/{vision['id']}", headers=admin_headers
        ).json()["fallback_group_ids"]
    ) == [target["id"]]


@pytest.mark.parametrize(
    ("target_name", "status_code"),
    [
        pytest.param("source", 409, id="itself"),
        pytest.param("route", 409, id="route-group"),
        pytest.param(None, 404, id="missing"),
    ],
)
def test_merge_model_group_rejects_invalid_targets(
    client,
    admin_headers,
    target_name,
    status_code,
) -> None:
    source = _create_group(client, admin_headers, name="source")
    execution = _create_group(client, admin_headers, name="execution")
    groups = {
        "source": source,
        "route": _create_group(
            client, admin_headers, name="route", route_group_id=execution["id"]
        ),
    }
    target_id = groups[target_name]["id"] if target_name else "missing"

    response = client.post(
        f"/api/admin/model-groups/{source['id']}/merge",
        headers=admin_headers,
        json={"target_group_id": target_id},
    )

    assert_error(response, status_code)
