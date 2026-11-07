from __future__ import annotations

import json

import pytest
from conftest import run_async, seed_request_log, valid_site_payload

from app.persistence.entities import (
    GatewayApiKeyEntity,
    ModelGroupEntity,
    RequestLogEntity,
    SiteEntity,
)


def test_legacy_backup_combines_regex_flags(client, admin_headers) -> None:
    backup = {
        "exported_at": "2026-01-01T00:00:00",
        "lens_version": "test",
        "regex_rules": [
            {"id": "first", "pattern": "(?s)^claude-"},
            {"id": "second", "pattern": "^gpt-"},
        ],
        "groups": [
            {
                "id": "legacy",
                "name": "legacy",
                "strategy": "failover",
                "match_rule_ids": ["first", "second"],
            }
        ],
    }
    restored = client.post(
        "/api/admin/backups/import",
        headers=admin_headers,
        files={"file": ("legacy.json", json.dumps(backup), "application/json")},
    )
    assert restored.status_code == 200, restored.text
    group = client.get("/api/admin/model-groups/legacy", headers=admin_headers)
    assert group.status_code == 200, group.text
    assert "claude-" in group.json()["match_regex"]
    assert "gpt-" in group.json()["match_regex"]


@pytest.mark.parametrize("rule_ids", [[{}], [[]], "first"])
def test_legacy_backup_rejects_invalid_rule_ids_without_overwriting(
    client, admin_headers, create_model_group, rule_ids
) -> None:
    group = create_model_group(name="preserved")
    backup = {
        "exported_at": "2026-01-01T00:00:00",
        "lens_version": "test",
        "regex_rules": [{"id": "first", "pattern": "^gpt-"}],
        "groups": [{"id": "legacy", "name": "legacy", "match_rule_ids": rule_ids}],
    }
    response = client.post(
        "/api/admin/backups/import",
        headers=admin_headers,
        files={"file": ("legacy.json", json.dumps(backup), "application/json")},
    )
    assert response.status_code == 400, response.text
    preserved = client.get("/api/admin/model-groups", headers=admin_headers)
    assert [item["id"] for item in preserved.json()] == [group["id"]]


@pytest.mark.parametrize(
    ("base_url", "protocol"),
    [
        ("https://upstream.example/v1", "openai_chat"),
        ("https://api.anthropic.com", "anthropic"),
        ("https://generativelanguage.googleapis.com", "gemini"),
    ],
)
def test_legacy_auto_backup_restores_concrete_protocols_and_references(
    client, admin_headers, create_site, create_model_group, base_url, protocol
) -> None:
    payload = valid_site_payload(protocols=[protocol])
    payload["base_urls"][0]["url"] = base_url
    create_site(payload)
    create_model_group(
        name="gpt-4o",
        items=[
            {
                "channel_id": f"pc-1_{protocol}",
                "credential_id": "cred-1",
                "model_name": "gpt-4o",
                "enabled": True,
            }
        ],
    )
    backup = client.get("/api/admin/backups/export", headers=admin_headers).json()
    config = backup["sites"][0]["protocols"][0]
    config["protocols"] = ["auto"]
    config["models"][0]["protocol"] = "auto"
    member = backup["groups"][0]["items"][0]
    member["channel_id"] = "pc-1_auto"
    member["protocol"] = "auto"
    if protocol == "openai_chat":
        config["protocols"].append(protocol)
        config["models"].append(
            {**config["models"][0], "id": "concrete-model", "protocol": protocol}
        )
        backup["groups"][0]["items"].append(
            {**member, "channel_id": f"pc-1_{protocol}", "protocol": protocol}
        )
    backup["include_request_logs"] = True
    backup["request_logs"] = [
        {
            "protocol": "openai_chat",
            "channel_id": "pc-1_auto",
            "success": True,
            "created_at": "2026-01-01T00:00:00",
            "attempts": [
                {
                    "channel_id": "pc-1_auto",
                    "channel_name": "legacy",
                    "success": True,
                }
            ],
        }
    ]
    restored = client.post(
        "/api/admin/backups/import",
        headers=admin_headers,
        files={"file": ("legacy.json", json.dumps(backup), "application/json")},
    )
    assert restored.status_code == 200, restored.text
    exported = client.get(
        "/api/admin/backups/export?include_logs=true", headers=admin_headers
    ).json()
    restored_config = exported["sites"][0]["protocols"][0]
    assert restored_config["protocols"] == [protocol]
    assert len(restored_config["models"]) == 1
    assert restored_config["models"][0]["protocol"] == protocol
    assert len(exported["groups"][0]["items"]) == 1
    assert exported["groups"][0]["items"][0]["channel_id"] == f"pc-1_{protocol}"
    assert exported["request_logs"][0]["channel_id"] == f"pc-1_{protocol}"
    assert (
        exported["request_logs"][0]["attempts"][0]["channel_id"] == f"pc-1_{protocol}"
    )


def test_stored_json_errors_preserve_data_and_return_server_error(
    client, admin_headers, app_state, create_site_group_and_key, caplog
) -> None:
    site, group, key = create_site_group_and_key()
    log = seed_request_log(app_state)
    cases = (
        (SiteEntity, site["id"], "headers_json", "/api/admin/sites"),
        (ModelGroupEntity, group["id"], "headers_json", "/api/admin/model-groups"),
        (
            GatewayApiKeyEntity,
            key["id"],
            "allowed_models_json",
            "/api/admin/gateway-api-keys",
        ),
        (
            RequestLogEntity,
            log.id,
            "attempts_json",
            f"/api/admin/request-logs/{log.id}",
        ),
    )

    async def replace_column(entity, record_id, column, value):
        async with app_state.session_factory.begin() as session:
            row = await session.get(entity, record_id)
            previous = getattr(row, column)
            setattr(row, column, value)
            return previous

    for entity, record_id, column, endpoint in cases:
        for malformed in ('{"private-test-marker":', '{"private-test-marker": 1}'):
            previous = run_async(replace_column(entity, record_id, column, malformed))
            response = client.get(endpoint, headers=admin_headers)
            assert response.status_code == 500, response.text
            assert "private-test-marker" not in response.text
            restored = run_async(replace_column(entity, record_id, column, previous))
            assert restored == malformed
        assert client.get(endpoint, headers=admin_headers).status_code == 200
    assert "private-test-marker" not in caplog.text


def test_backup_restores_archived_overview(client, admin_headers, app_state) -> None:
    codex = seed_request_log(app_state, user_agent="codex-tui/0.1")
    claude = seed_request_log(app_state, user_agent="claude-cli/1.0")

    async def align_log_times():
        async with app_state.session_factory.begin() as session:
            codex_row = await session.get(RequestLogEntity, codex.id)
            claude_row = await session.get(RequestLogEntity, claude.id)
            claude_row.created_at = codex_row.created_at

    run_async(align_log_times())
    exported = client.get(
        "/api/admin/backups/export?include_logs=true", headers=admin_headers
    )
    assert exported.status_code == 200
    backup = exported.json()
    assert backup["request_logs"][0]["stats_archived"] is True
    assert backup["request_logs"][0]["attribution_archived"] is True
    assert backup["stats"]["request_daily"][0]["request_count"] == 2
    hourly = backup["stats"]["attribution_hourly"]
    assert len(hourly) == 2
    assert {row["agent"] for row in hourly} == {"codex", "claude_code"}
    assert hourly[0]["upstream_model"] == "gpt-4o"
    assert hourly[0]["cache_read_input_tokens"] == 1

    cleared = client.delete("/api/admin/request-logs", headers=admin_headers)
    assert cleared.status_code == 204
    restored = client.post(
        "/api/admin/backups/import",
        headers=admin_headers,
        files={"file": ("lens-backup.json", json.dumps(backup), "application/json")},
    )
    assert restored.status_code == 200, restored.text
    reexported = client.get(
        "/api/admin/backups/export?include_logs=true", headers=admin_headers
    )
    assert reexported.status_code == 200
    assert reexported.json()["stats"] == backup["stats"]
    summary = client.get("/api/admin/overview-summary?days=-1", headers=admin_headers)
    assert summary.status_code == 200
    assert summary.json()["request_count"]["value"] == 2
    agents = client.get(
        "/api/admin/overview-attribution?days=-1&dimension=agent&metric=requests",
        headers=admin_headers,
    )
    assert agents.status_code == 200, agents.text
    assert {row["key"]: row["requests"] for row in agents.json()["items"]} == {
        "codex": 1,
        "claude_code": 1,
    }
