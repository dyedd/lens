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
from app.persistence.backup_store.export_import import BackupExportImportMixin


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


@pytest.mark.parametrize("protocol", [ProtocolKind.OPENAI_IMAGE])
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


def test_delete_group_rejects_a_fallback_reference(
    client, admin_headers, create_model_group
) -> None:
    fallback = create_model_group(name="fallback")
    primary = create_model_group(name="primary")
    updated = client.put(
        f"/api/admin/model-groups/{primary['id']}",
        headers=admin_headers,
        json={"fallback_group_ids": [fallback["id"]]},
    )
    assert updated.status_code == 200, updated.text

    response = client.delete(
        f"/api/admin/model-groups/{fallback['id']}", headers=admin_headers
    )

    assert_error(response, 409, "referenced as a fallback")


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
        "gemini",
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


def test_remove_unplaced_model_only_touches_unplaced_channel_models(
    client,
    admin_headers,
    create_site,
    create_model_group,
) -> None:
    create_model_group(name="claude-opus-4.5")
    create_site(valid_site_payload(model_name="claude-opus-4-5"))

    rejected = client.post(
        "/api/admin/unplaced-model-removals",
        headers=admin_headers,
        json={"model_names": ["claude-opus-4.5"]},
    )
    removed = client.post(
        "/api/admin/unplaced-model-removals",
        headers=admin_headers,
        json={"model_names": ["claude-opus-4-5"]},
    )
    unplaced = client.get("/api/admin/unplaced-models", headers=admin_headers)
    [site] = client.get("/api/admin/sites", headers=admin_headers).json()

    assert_error(rejected, 400, "claude-opus-4.5")
    assert removed.status_code == 200, removed.text
    assert removed.json() == {"deleted": 1}
    assert unplaced.json()["items"] == []
    assert site["protocols"][0]["models"] == []


def _create_group(client, admin_headers, **payload: object) -> dict[str, object]:
    response = client.post(
        "/api/admin/model-groups", headers=admin_headers, json=payload
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_new_group_receives_same_named_model_member(
    client,
    admin_headers,
    create_site,
) -> None:
    group = _create_group(client, admin_headers, name="claude-opus-4-5")

    create_site(valid_site_payload(model_name="claude-opus-4-5"))
    stored = client.get(f"/api/admin/model-groups/{group['id']}", headers=admin_headers)
    unplaced = client.get("/api/admin/unplaced-models", headers=admin_headers)

    assert stored.json()["items"] and [
        (item["model_name"], item["source"]) for item in stored.json()["items"]
    ] == [("claude-opus-4-5", "placement")]
    assert unplaced.json()["items"] == []


def test_group_name_matches_case_insensitive_substrings(
    client,
    admin_headers,
    create_site,
) -> None:
    group = _create_group(client, admin_headers, name="GPT-4o")

    create_site(valid_site_payload(model_name="vendor/GPT-4O-2024"))

    stored = client.get(
        f"/api/admin/model-groups/{group['id']}", headers=admin_headers
    ).json()
    assert [item["model_name"] for item in stored["items"]] == ["vendor/GPT-4O-2024"]


def test_group_name_and_local_regex_can_use_or_or_and(
    client,
    admin_headers,
    create_site,
) -> None:
    or_group = _create_group(
        client,
        admin_headers,
        name="family",
        match_regex="claude-",
        match_regex_operator="or",
    )
    and_group = _create_group(
        client,
        admin_headers,
        name="strict",
        match_regex="claude-",
        match_regex_operator="and",
    )

    create_site(valid_site_payload(model_name="claude-sonnet-4"))
    create_site(
        valid_site_payload(
            name="Family Site",
            base_id="base-2",
            credential_id="cred-2",
            protocol_config_id="pc-2",
            model_name="family-v2",
        )
    )
    create_site(
        valid_site_payload(
            name="Strict Site",
            base_id="base-3",
            credential_id="cred-3",
            protocol_config_id="pc-3",
            model_name="strict-claude-4",
        )
    )

    or_items = client.get(
        f"/api/admin/model-groups/{or_group['id']}", headers=admin_headers
    ).json()["items"]
    and_items = client.get(
        f"/api/admin/model-groups/{and_group['id']}", headers=admin_headers
    ).json()["items"]
    assert [item["model_name"] for item in or_items] == [
        "claude-sonnet-4",
        "family-v2",
        "strict-claude-4",
    ]
    assert [item["model_name"] for item in and_items] == ["strict-claude-4"]


def test_group_rejects_invalid_local_regex(client, admin_headers) -> None:
    response = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={"name": "broken", "match_regex": "("},
    )

    assert_error(response, 422)


def test_old_backup_rules_become_local_group_regex() -> None:
    dump = BackupExportImportMixin.parse_dump(
        json.dumps(
            {
                "exported_at": "now",
                "lens_version": "test",
                "regex_rules": [
                    {"id": "legacy", "name": "Legacy", "pattern": "^claude-"}
                ],
                "groups": [
                    {
                        "id": "group",
                        "name": "family",
                        "strategy": "failover",
                        "match_rule_ids": ["legacy"],
                        "items": [],
                        "excluded_items": [],
                    }
                ],
            }
        ).encode()
    )

    assert dump.groups[0].match_regex == "^claude-"
    assert dump.groups[0].match_rule_ids == []


def test_old_backup_rules_keep_long_combined_patterns() -> None:
    rules = [
        {"id": str(index), "name": f"Rule {index}", "pattern": "a" * 500}
        for index in range(20)
    ]
    dump = BackupExportImportMixin.parse_dump(
        json.dumps(
            {
                "exported_at": "now",
                "lens_version": "test",
                "regex_rules": rules,
                "groups": [
                    {
                        "id": "group",
                        "name": "family",
                        "strategy": "failover",
                        "match_rule_ids": [rule["id"] for rule in rules],
                        "items": [],
                        "excluded_items": [],
                    }
                ],
            }
        ).encode()
    )

    assert len(dump.groups[0].match_regex) > 10_000


def test_old_backup_model_status_fields_are_ignored() -> None:
    dump = BackupExportImportMixin.parse_dump(
        json.dumps(
            {
                "exported_at": "now",
                "lens_version": "test",
                "sites": [
                    {
                        "id": "site",
                        "name": "site",
                        "enabled": True,
                        "tags": [],
                        "base_urls": [],
                        "credentials": [],
                        "protocols": [
                            {
                                "id": "pc",
                                "base_url_id": "base",
                                "protocols": ["openai_chat"],
                                "models": [
                                    {
                                        "id": "model",
                                        "credential_id": "credential",
                                        "model_name": "gpt-4o",
                                        "enabled": True,
                                        "protocol": "openai_chat",
                                        "upstream_missing": True,
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ).encode()
    )

    assert dump.sites[0].protocols[0].models[0].model_name == "gpt-4o"


def test_group_rule_edits_rejoin_members_on_next_reconcile(
    client,
    admin_headers,
    create_site,
) -> None:
    group = _create_group(
        client,
        admin_headers,
        name="family",
        match_regex="^gpt-",
        match_regex_operator="or",
    )
    create_site(valid_site_payload())
    joined = client.get(
        f"/api/admin/model-groups/{group['id']}", headers=admin_headers
    ).json()
    assert [item["model_name"] for item in joined["items"]] == ["gpt-4o"]

    client.put(
        f"/api/admin/model-groups/{group['id']}",
        headers=admin_headers,
        json={"match_regex": "^claude-", "match_regex_operator": "or"},
    )
    create_site(
        valid_site_payload(
            name="Claude Site",
            base_id="base-2",
            credential_id="cred-2",
            protocol_config_id="pc-2",
            model_name="claude-sonnet-4",
        )
    )

    stored = client.get(
        f"/api/admin/model-groups/{group['id']}", headers=admin_headers
    ).json()
    assert [(item["model_name"], item["source"]) for item in stored["items"]] == [
        ("claude-sonnet-4", "placement")
    ]


def test_route_groups_clear_local_match_rules(client, admin_headers) -> None:
    execution = _create_group(client, admin_headers, name="execution")
    created = _create_group(
        client,
        admin_headers,
        name="alias",
        route_group_id=execution["id"],
        match_regex="^claude-",
    )
    group = _create_group(client, admin_headers, name="family", match_regex="^claude-")

    updated = client.put(
        f"/api/admin/model-groups/{group['id']}",
        headers=admin_headers,
        json={"route_group_id": execution["id"]},
    )

    assert created["match_regex"] == ""
    assert updated.status_code == 200, updated.text
    assert updated.json()["match_regex"] == ""


def test_merge_model_group_folds_source_into_target(
    client,
    admin_headers,
    create_site,
) -> None:
    create_site(valid_site_payload())
    # Automatic placement already owns the name "gpt-4o"; use a free name.
    target = _create_group(client, admin_headers, name="gpt-4o-merged")
    source = _create_group(
        client,
        admin_headers,
        name="gpt-4o-latest",
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
    assert [(item["model_name"], item["source"]) for item in merged["items"]] == [
        ("gpt-4o", "manual")
    ]
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


def test_merge_keeps_target_match_operator_when_source_has_no_regex(
    client,
    admin_headers,
) -> None:
    target = _create_group(
        client,
        admin_headers,
        name="family",
        match_regex="claude-",
        match_regex_operator="and",
    )
    source = _create_group(client, admin_headers, name="other")

    response = client.post(
        f"/api/admin/model-groups/{source['id']}/merge",
        headers=admin_headers,
        json={"target_group_id": target["id"]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["match_regex"] == "claude-"
    assert response.json()["match_regex_operator"] == "and"


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


def test_group_candidates_list_available_channel_models(
    client,
    admin_headers,
    create_site,
) -> None:
    create_site(valid_site_payload(name="Prod Site"))
    create_site(
        valid_site_payload(
            name="Test Site",
            base_id="base-2",
            credential_id="cred-2",
            protocol_config_id="pc-2",
            model_name="gpt-4o-mini",
        )
    )

    response = client.post(
        "/api/admin/model-group-candidates",
        headers=admin_headers,
        json={"items": []},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert sorted(item["model_name"] for item in payload["candidates"]) == [
        "gpt-4o",
        "gpt-4o-mini",
    ]
    assert payload["evaluated_items"] == []


def test_place_models_without_group_reports_unplaced_conflicts(
    client,
    admin_headers,
    create_site,
    create_model_group,
) -> None:
    create_model_group(name="claude-opus-4.5")
    create_site(valid_site_payload(model_name="claude-opus-4-5"))

    response = client.post(
        "/api/admin/model-group-placements",
        headers=admin_headers,
        json={"model_names": ["claude-opus-4-5"]},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["created"] == []
    assert payload["joined"] == []
    assert [item["model_name"] for item in payload["unplaced"]] == ["claude-opus-4-5"]


def test_place_models_into_existing_group_joins_conflicted_model(
    client,
    admin_headers,
    create_site,
    create_model_group,
) -> None:
    target = create_model_group(name="claude-opus-4.5")
    site = create_site(valid_site_payload(model_name="claude-opus-4-5"))

    response = client.post(
        "/api/admin/model-group-placements",
        headers=admin_headers,
        json={"model_names": ["claude-opus-4-5"], "group_id": target["id"]},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["created"] == []
    assert [
        (change["model_name"], change["credential_id"]) for change in payload["joined"]
    ] == [("claude-opus-4-5", "cred-1")]
    stored = client.get(
        f"/api/admin/model-groups/{target['id']}", headers=admin_headers
    ).json()
    assert [(item["model_name"], item["source"]) for item in stored["items"]] == [
        ("claude-opus-4-5", "manual")
    ]
    unplaced = client.get("/api/admin/unplaced-models", headers=admin_headers).json()
    assert unplaced["items"] == []

    # A later site save re-runs the reconcile; the explicit membership stays.
    client.put(
        f"/api/admin/sites/{site['id']}",
        headers=admin_headers,
        json=valid_site_payload(model_name="claude-opus-4-5"),
    )
    kept = client.get(
        f"/api/admin/model-groups/{target['id']}", headers=admin_headers
    ).json()
    assert [item["model_name"] for item in kept["items"]] == ["claude-opus-4-5"]


def test_renaming_group_keeps_its_joined_members(
    client,
    admin_headers,
    create_site,
) -> None:
    create_site(valid_site_payload(model_name="gpt-4o"))
    group = next(
        item
        for item in client.get("/api/admin/model-groups", headers=admin_headers).json()
        if item["name"] == "gpt-4o"
    )

    renamed = client.put(
        f"/api/admin/model-groups/{group['id']}",
        headers=admin_headers,
        json={"name": "gpt-4o-prod", "strategy": "failover"},
    )

    assert renamed.status_code == 200, renamed.text
    assert [
        (item["model_name"], item["source"]) for item in renamed.json()["items"]
    ] == [("gpt-4o", "manual")]
