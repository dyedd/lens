from __future__ import annotations

import pytest

from conftest import assert_error, openai_chat_channel_id, valid_site_payload


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


def test_list_model_groups_requires_admin(client) -> None:
    response = client.get("/api/admin/model-groups")

    assert_error(response, 401, "Not authenticated")


def test_model_group_crud_round_trip(client, admin_headers, create_model_group) -> None:
    assert client.get("/api/admin/model-groups", headers=admin_headers).json() == []

    group = create_model_group(name="gpt-4o")
    assert group["name"] == "gpt-4o"
    assert group["protocols"] == ["openai_chat"]

    detail = client.get(f"/api/admin/model-groups/{group['id']}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["id"] == group["id"]

    update = client.put(
        f"/api/admin/model-groups/{group['id']}",
        headers=admin_headers,
        json={"name": "gpt-4.1"},
    )
    assert update.status_code == 200
    assert update.json()["name"] == "gpt-4.1"

    delete = client.delete(
        f"/api/admin/model-groups/{group['id']}", headers=admin_headers
    )
    assert delete.status_code == 204
    assert client.get("/api/admin/model-groups", headers=admin_headers).json() == []


def test_create_model_group_rejects_duplicate_names(
    client,
    admin_headers,
    create_model_group,
) -> None:
    create_model_group(name="gpt-4o")

    response = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={"name": "gpt-4o", "protocols": ["openai_chat"]},
    )

    assert_error(response, 400, "Model group already exists")


def test_create_model_group_with_site_member_hydrates_member_metadata(
    client,
    admin_headers,
    create_site,
) -> None:
    create_site(valid_site_payload())

    response = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "gpt-4o",
            "protocols": ["openai_chat"],
            "items": [_member()],
        },
    )

    assert response.status_code == 201
    item = response.json()["items"][0]
    assert item["channel_id"] == openai_chat_channel_id()
    assert item["channel_name"] == "OpenAI Site"
    assert item["protocol"] == "openai_chat"
    assert item["credential_id"] == "cred-1"
    assert item["credential_name"] == "primary-key"


def test_create_model_group_rejects_blank_name(client, admin_headers) -> None:
    response = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={"name": " ", "protocols": ["openai_chat"]},
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
            "protocols": ["openai_chat"],
            "items": [_member(**member_overrides)],
        },
    )

    assert_error(response, 400, message)


def test_create_model_group_rejects_channel_that_cannot_reach_selected_protocol(
    client,
    admin_headers,
    create_site,
) -> None:
    create_site(valid_site_payload())

    response = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "embedding-group",
            "protocols": ["openai_embedding"],
            "items": [_member()],
        },
    )

    assert_error(response, 400, "Channels cannot reach any selected protocol")


def test_create_model_group_rejects_uncovered_selected_protocol(
    client,
    admin_headers,
    create_site,
) -> None:
    create_site(valid_site_payload())

    response = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "mixed-group",
            "protocols": ["openai_chat", "openai_embedding"],
            "items": [_member()],
        },
    )

    assert_error(response, 400, "Protocol openai_embedding has no reachable channel")


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
