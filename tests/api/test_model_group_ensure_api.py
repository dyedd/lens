from __future__ import annotations

import pytest

from conftest import assert_error, valid_site_payload


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


def test_ensure_model_groups_from_site_updates_existing_group_with_protocol_extension(
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

    without_extension = client.post(
        "/api/admin/model-groups/ensure-from-site",
        headers=admin_headers,
        json={
            "site_id": site["id"],
            "dry_run": True,
            "allow_protocol_extension": False,
            "models": [model],
        },
    )
    with_extension = client.post(
        "/api/admin/model-groups/ensure-from-site",
        headers=admin_headers,
        json={
            "site_id": site["id"],
            "dry_run": False,
            "allow_protocol_extension": True,
            "models": [model],
        },
    )
    detail = client.get(
        f"/api/admin/model-groups/{existing['id']}", headers=admin_headers
    )

    assert without_extension.status_code == 200
    assert without_extension.json()["items"][0]["status"] == "skipped"
    assert without_extension.json()["items"][0]["skipped_reason"] == (
        "protocol_extension_required"
    )
    assert without_extension.json()["items"][0]["missing_protocols"] == ["gemini"]
    assert with_extension.status_code == 200
    assert with_extension.json()["updated_count"] == 1
    assert detail.status_code == 200
    assert detail.json()["protocols"] == ["openai_chat", "gemini"]
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
