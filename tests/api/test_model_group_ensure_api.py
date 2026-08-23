from __future__ import annotations

import pytest

from conftest import assert_error, valid_site_payload
from lens_api.core.runtime_channel_ids import compose_runtime_channel_id
from lens_api.models import ProtocolKind


def _save_models_from_preview(payload: dict) -> list[dict]:
    return [
        {
            "protocol_config_id": item["protocol_config_id"],
            "credential_id": item["credential_id"],
            "model_name": item["model_name"],
            "group_name": item["group_name"],
            "protocols": item["protocols"],
        }
        for item in payload["model_groups"]["items"]
    ]


def test_transactional_site_save_groups_manual_and_synced_models(
    client,
    admin_headers,
) -> None:
    site_payload = valid_site_payload(model_name="gpt-manual")
    protocol_config = site_payload["protocols"][0]
    protocol_config["models"].append(
        {
            "credential_id": "cred-1",
            "model_name": "gpt-synced",
            "enabled": True,
            "protocol": "openai_chat",
            "source": "synced",
        }
    )
    protocol_config["sync_targets"] = [
        {
            "credential_id": "cred-1",
            "model_name": "gpt-synced",
            "protocol": "openai_chat",
        }
    ]

    preview = client.post(
        "/api/admin/sites/with-model-groups",
        headers=admin_headers,
        json={**site_payload, "dry_run": True},
    )

    assert preview.status_code == 201, preview.text
    preview_payload = preview.json()
    assert preview_payload["model_groups"]["created_count"] == 2
    assert client.get("/api/admin/sites", headers=admin_headers).json() == []
    assert client.get("/api/admin/model-groups", headers=admin_headers).json() == []

    committed = client.post(
        "/api/admin/sites/with-model-groups",
        headers=admin_headers,
        json={
            **site_payload,
            "site_id": preview_payload["site"]["id"],
            "dry_run": False,
            "models": _save_models_from_preview(preview_payload),
        },
    )

    assert committed.status_code == 201, committed.text
    groups = client.get("/api/admin/model-groups", headers=admin_headers).json()
    assert {group["name"] for group in groups} == {"gpt-manual", "gpt-synced"}
    assert {item["model_name"] for group in groups for item in group["items"]} == {
        "gpt-manual",
        "gpt-synced",
    }
    stored_models = client.get("/api/admin/sites", headers=admin_headers).json()[0][
        "protocols"
    ][0]["models"]
    assert {model["model_name"]: model["source"] for model in stored_models} == {
        "gpt-manual": "manual",
        "gpt-synced": "synced",
    }

    repeated_preview = client.put(
        f"/api/admin/sites/{preview_payload['site']['id']}/with-model-groups",
        headers=admin_headers,
        json={**site_payload, "dry_run": True},
    )
    assert repeated_preview.status_code == 200, repeated_preview.text
    assert repeated_preview.json()["model_groups"]["items"] == []


def test_transactional_site_save_rolls_back_when_group_write_fails(
    client,
    admin_headers,
    app_state,
    monkeypatch,
) -> None:
    async def fail_group_write(*_args, **_kwargs):
        raise RuntimeError("group write failed")

    monkeypatch.setattr(
        app_state.group_repo,
        "ensure_groups_from_site_in_session",
        fail_group_write,
    )
    response = client.post(
        "/api/admin/sites/with-model-groups",
        headers=admin_headers,
        json={**valid_site_payload(), "dry_run": False},
    )

    assert response.status_code == 500
    assert client.get("/api/admin/sites", headers=admin_headers).json() == []
    assert client.get("/api/admin/model-groups", headers=admin_headers).json() == []


def test_transactional_site_save_adds_members_without_protocol_confirmation(
    client,
    admin_headers,
    create_site,
    create_model_group,
) -> None:
    site_payload = valid_site_payload(
        name="Original Site",
        protocols=["openai_image"],
        model_name="gpt-image",
    )
    site = create_site(site_payload)
    group = create_model_group(name="gpt", protocols=["openai_chat"])
    updated_payload = {**site_payload, "name": "Updated Site"}

    preview = client.put(
        f"/api/admin/sites/{site['id']}/with-model-groups",
        headers=admin_headers,
        json={**updated_payload, "dry_run": True},
    )

    assert preview.status_code == 200, preview.text
    preview_payload = preview.json()
    assert preview_payload["model_groups"]["items"][0]["status"] == "update"
    stored_site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    assert stored_site["name"] == "Original Site"

    committed = client.put(
        f"/api/admin/sites/{site['id']}/with-model-groups",
        headers=admin_headers,
        json={
            **updated_payload,
            "dry_run": False,
            "models": _save_models_from_preview(preview_payload),
        },
    )

    assert committed.status_code == 200, committed.text
    assert committed.json()["site"]["name"] == "Updated Site"
    stored_group = client.get(
        f"/api/admin/model-groups/{group['id']}", headers=admin_headers
    ).json()
    assert stored_group["client_protocols"] == ["openai_image"]
    assert stored_group["items"][0]["model_name"] == "gpt-image"


def test_transactional_site_save_detects_protocol_added_to_grouped_model(
    client,
    admin_headers,
    create_site,
    create_model_group,
) -> None:
    site = create_site(valid_site_payload(model_name="shared-model"))
    group = create_model_group(
        name="shared-model",
        items=[
            {
                "channel_id": compose_runtime_channel_id(
                    "pc-1", ProtocolKind.OPENAI_CHAT
                ),
                "credential_id": "cred-1",
                "model_name": "shared-model",
                "enabled": True,
            }
        ],
    )
    updated_payload = valid_site_payload(
        model_name="shared-model",
        protocols=["openai_chat", "anthropic"],
    )

    preview = client.put(
        f"/api/admin/sites/{site['id']}/with-model-groups",
        headers=admin_headers,
        json={**updated_payload, "dry_run": True},
    )

    assert preview.status_code == 200, preview.text
    preview_payload = preview.json()
    assert preview_payload["model_groups"]["items"][0]["protocols"] == ["anthropic"]
    assert preview_payload["model_groups"]["items"][0]["status"] == "update"

    committed = client.put(
        f"/api/admin/sites/{site['id']}/with-model-groups",
        headers=admin_headers,
        json={
            **updated_payload,
            "dry_run": False,
            "models": _save_models_from_preview(preview_payload),
        },
    )

    assert committed.status_code == 200, committed.text
    stored_group = client.get(
        f"/api/admin/model-groups/{group['id']}", headers=admin_headers
    ).json()
    assert stored_group["client_protocols"] == [
        "openai_chat",
        "openai_responses",
        "anthropic",
    ]
    assert {item["channel_id"] for item in stored_group["items"]} == {
        compose_runtime_channel_id("pc-1", ProtocolKind.OPENAI_CHAT),
        compose_runtime_channel_id("pc-1", ProtocolKind.ANTHROPIC),
    }


def test_transactional_site_save_removes_deleted_model_protocol_from_group(
    client,
    admin_headers,
    create_site,
    create_model_group,
) -> None:
    site = create_site(
        valid_site_payload(
            model_name="shared-model",
            protocols=["openai_chat", "gemini"],
        )
    )
    group = create_model_group(
        name="shared-model",
        protocols=["openai_chat", "gemini"],
        items=[
            {
                "channel_id": compose_runtime_channel_id(
                    "pc-1", ProtocolKind.OPENAI_CHAT
                ),
                "credential_id": "cred-1",
                "model_name": "shared-model",
                "enabled": True,
            },
            {
                "channel_id": compose_runtime_channel_id("pc-1", ProtocolKind.GEMINI),
                "credential_id": "cred-1",
                "model_name": "shared-model",
                "enabled": True,
            },
        ],
    )

    response = client.put(
        f"/api/admin/sites/{site['id']}/with-model-groups",
        headers=admin_headers,
        json={
            **valid_site_payload(model_name="shared-model"),
            "dry_run": False,
        },
    )

    assert response.status_code == 200, response.text
    stored_group = client.get(
        f"/api/admin/model-groups/{group['id']}", headers=admin_headers
    ).json()
    assert stored_group["client_protocols"] == [
        "openai_chat",
        "openai_responses",
        "anthropic",
    ]
    assert [item["channel_id"] for item in stored_group["items"]] == [
        compose_runtime_channel_id("pc-1", ProtocolKind.OPENAI_CHAT)
    ]


def test_transactional_site_save_suggests_case_insensitive_containing_group(
    client,
    admin_headers,
    create_model_group,
) -> None:
    create_model_group(name="glm", protocols=["openai_chat"])
    create_model_group(name="GLM5.2", protocols=["openai_chat"])

    preview = client.post(
        "/api/admin/sites/with-model-groups",
        headers=admin_headers,
        json={
            **valid_site_payload(model_name="zai.org/glm5.2"),
            "dry_run": True,
        },
    )

    assert preview.status_code == 201, preview.text
    item = preview.json()["model_groups"]["items"][0]
    assert item["group_name"] == "GLM5.2"
    assert item["status"] == "update"


@pytest.mark.parametrize("dry_run", [True, False])
def test_ensure_model_groups_from_site_creates_group(
    client,
    admin_headers,
    create_site,
    dry_run,
) -> None:
    site = create_site(valid_site_payload(model_name="gpt-4o-mini"))

    response = client.post(
        "/api/admin/model-groups/ensure-from-site",
        headers=admin_headers,
        json={
            "site_id": site["id"],
            "dry_run": dry_run,
            "models": [
                {
                    "protocol_config_id": "pc-1",
                    "credential_id": "cred-1",
                    "model_name": "gpt-4o-mini",
                    "protocols": ["openai_chat"],
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dry_run"] is dry_run
    assert payload["created_count"] == 1
    assert payload["items"][0]["status"] == "create"
    if dry_run:
        return
    groups = client.get("/api/admin/model-groups", headers=admin_headers)

    assert payload["items"][0]["group_id"]
    assert groups.status_code == 200
    assert groups.json()[0]["name"] == "gpt-4o-mini"
    assert groups.json()[0]["items"][0]["model_name"] == "gpt-4o-mini"


def test_ensure_model_groups_from_site_skips_duplicate_selection(
    client,
    admin_headers,
    create_site,
) -> None:
    site = create_site(valid_site_payload(model_name="gpt-4o-mini"))
    model = {
        "protocol_config_id": "pc-1",
        "credential_id": "cred-1",
        "model_name": "gpt-4o-mini",
        "protocols": ["openai_chat"],
    }

    response = client.post(
        "/api/admin/model-groups/ensure-from-site",
        headers=admin_headers,
        json={"site_id": site["id"], "dry_run": True, "models": [model, model]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["created_count"] == 1
    assert payload["skipped_count"] == 1
    assert [
        item["skipped_reason"] for item in payload["items"] if item["skipped_reason"]
    ] == ["duplicate_selection"]


def test_ensure_model_groups_from_site_skips_invalid_selections(
    client,
    admin_headers,
    create_site,
) -> None:
    site = create_site(valid_site_payload(model_name="gpt-4o-mini"))

    response = client.post(
        "/api/admin/model-groups/ensure-from-site",
        headers=admin_headers,
        json={
            "site_id": site["id"],
            "dry_run": True,
            "models": [
                {
                    "protocol_config_id": "missing",
                    "credential_id": "cred-1",
                    "model_name": "gpt-4o-mini",
                    "protocols": ["openai_chat"],
                },
                {
                    "protocol_config_id": "pc-1",
                    "credential_id": "missing",
                    "model_name": "gpt-4o-mini",
                    "protocols": ["openai_chat"],
                },
                {
                    "protocol_config_id": "pc-1",
                    "credential_id": "cred-1",
                    "model_name": "missing-model",
                    "protocols": ["openai_chat"],
                },
            ],
        },
    )

    assert response.status_code == 200
    reasons = [item["skipped_reason"] for item in response.json()["items"]]
    assert reasons == [
        "protocol_config_not_found",
        "credential_not_found",
        "model_not_available",
    ]


def test_ensure_model_groups_from_site_skips_disabled_resources(
    client,
    admin_headers,
    create_site,
) -> None:
    disabled_channel_site = create_site(
        valid_site_payload(
            name="Disabled Channel",
            base_id="base-disabled-channel",
            credential_id="cred-disabled-channel",
            protocol_config_id="pc-disabled-channel",
            protocol_enabled=False,
        )
    )
    disabled_credential_site = create_site(
        valid_site_payload(
            name="Disabled Credential",
            base_id="base-disabled-credential",
            credential_id="cred-disabled-credential",
            protocol_config_id="pc-disabled-credential",
            credential_enabled=False,
        )
    )
    disabled_model_site = create_site(
        valid_site_payload(
            name="Disabled Model",
            base_id="base-disabled-model",
            credential_id="cred-disabled-model",
            protocol_config_id="pc-disabled-model",
            model_enabled=False,
        )
    )

    channel_response = client.post(
        "/api/admin/model-groups/ensure-from-site",
        headers=admin_headers,
        json={
            "site_id": disabled_channel_site["id"],
            "dry_run": True,
            "models": [
                {
                    "protocol_config_id": "pc-disabled-channel",
                    "credential_id": "cred-disabled-channel",
                    "model_name": "gpt-4o",
                    "protocols": ["openai_chat"],
                }
            ],
        },
    )
    credential_response = client.post(
        "/api/admin/model-groups/ensure-from-site",
        headers=admin_headers,
        json={
            "site_id": disabled_credential_site["id"],
            "dry_run": True,
            "models": [
                {
                    "protocol_config_id": "pc-disabled-credential",
                    "credential_id": "cred-disabled-credential",
                    "model_name": "gpt-4o",
                    "protocols": ["openai_chat"],
                }
            ],
        },
    )
    model_response = client.post(
        "/api/admin/model-groups/ensure-from-site",
        headers=admin_headers,
        json={
            "site_id": disabled_model_site["id"],
            "dry_run": True,
            "models": [
                {
                    "protocol_config_id": "pc-disabled-model",
                    "credential_id": "cred-disabled-model",
                    "model_name": "gpt-4o",
                    "protocols": ["openai_chat"],
                }
            ],
        },
    )

    assert channel_response.status_code == 200
    assert credential_response.status_code == 200
    assert model_response.status_code == 200
    assert channel_response.json()["items"][0]["skipped_reason"] == "channel_disabled"
    assert (
        credential_response.json()["items"][0]["skipped_reason"]
        == "credential_disabled"
    )
    assert model_response.json()["items"][0]["skipped_reason"] == "model_not_available"


def test_ensure_model_groups_from_site_updates_existing_group_from_member(
    client,
    admin_headers,
    create_site,
    create_model_group,
) -> None:
    site = create_site(
        valid_site_payload(protocols=["gemini"], model_name="shared-model")
    )
    existing = create_model_group(name="shared-model", protocols=["openai_chat"])
    model = {
        "protocol_config_id": "pc-1",
        "credential_id": "cred-1",
        "model_name": "shared-model",
        "protocols": ["gemini"],
    }

    preview = client.post(
        "/api/admin/model-groups/ensure-from-site",
        headers=admin_headers,
        json={
            "site_id": site["id"],
            "dry_run": False,
            "models": [model],
        },
    )
    detail = client.get(
        f"/api/admin/model-groups/{existing['id']}", headers=admin_headers
    )

    assert preview.status_code == 200
    assert preview.json()["updated_count"] == 1
    assert detail.status_code == 200
    assert detail.json()["client_protocols"] == ["gemini"]
    assert detail.json()["items"][0]["protocol"] == "gemini"


def test_ensure_model_groups_from_missing_site_returns_not_found(
    client,
    admin_headers,
) -> None:
    response = client.post(
        "/api/admin/model-groups/ensure-from-site",
        headers=admin_headers,
        json={"site_id": "missing", "dry_run": True, "models": []},
    )

    assert_error(response, 404, "missing")
