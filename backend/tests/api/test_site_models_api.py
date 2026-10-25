from __future__ import annotations

from typing import Any


def test_fetch_site_models_returns_models(client, admin_headers, monkeypatch) -> None:
    from app.gateway.service.tasks.model_discovery import UpstreamModel

    async def fake_fetch(channel: Any) -> list[UpstreamModel]:
        assert channel.keys[0].id == "cred-a"
        return [
            UpstreamModel(name="gpt-4o", context_window=128_000),
            UpstreamModel(name="gpt-4o-mini"),
        ]

    import app.gateway.service.admin.sites as sites

    monkeypatch.setattr(sites, "fetch_upstream_models", fake_fetch)

    response = client.post(
        "/api/admin/site-model-discoveries",
        headers=admin_headers,
        json={
            "base_url": "https://upstream.example/v1",
            "headers": [],
            "credentials": [
                {"id": "cred-a", "name": "primary", "api_key": "upstream-secret"}
            ],
            "credential_ids": ["cred-a"],
        },
    )

    assert response.status_code == 200
    assert [item["model_name"] for item in response.json()] == [
        "gpt-4o",
        "gpt-4o-mini",
    ]


def _model(
    model_name: str,
    *,
    credential_id: str = "cred-a",
    **fields: Any,
) -> dict[str, Any]:
    return {
        "credential_id": credential_id,
        "model_name": model_name,
        "enabled": True,
        "protocol": "openai_chat",
        **fields,
    }


def _sync_site_payload(
    *,
    include_rules: list[str] | None = None,
    models: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "name": "Multi-key Site",
        "model_sync_include_rule_ids": include_rules or [],
        "model_sync_exclude_rule_ids": [],
        "base_urls": [{"id": "base-1", "url": "https://upstream.example/v1"}],
        "credentials": [
            {"id": "cred-a", "name": "key-a", "api_key": "secret-a"},
            {"id": "cred-b", "name": "key-b", "api_key": "secret-b"},
        ],
        "protocols": [
            {
                "id": "pc-1",
                "base_url_id": "base-1",
                "protocols": ["openai_chat"],
                "models": (models if models is not None else [_model("manual-only")]),
            }
        ],
    }


def _create_sync_site(client, admin_headers, payload: dict[str, Any]) -> None:
    response = client.post("/api/admin/sites", headers=admin_headers, json=payload)
    assert response.status_code == 201, response.text


def _patch_upstream_models(monkeypatch, fetch: Any) -> None:
    import app.gateway.service.tasks.model_sync as model_sync
    from app.gateway.service.tasks.model_discovery import UpstreamModel

    async def fetch_models(channel: Any) -> list[UpstreamModel]:
        return [
            item if isinstance(item, UpstreamModel) else UpstreamModel(name=item)
            for item in await fetch(channel)
        ]

    monkeypatch.setattr(model_sync, "fetch_upstream_models", fetch_models)


def _run_model_sync(client, admin_headers) -> dict[str, Any]:
    response = client.post(
        "/api/admin/channel-model-sync", headers=admin_headers, json={}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _stored_models(client, admin_headers) -> set[tuple[str, str, bool]]:
    site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    return {
        (model["credential_id"], model["model_name"], model["upstream_missing"])
        for model in site["protocols"][0]["models"]
    }


def test_channel_model_sync_adds_matching_models(
    client,
    admin_headers,
    create_regex_rule,
    monkeypatch,
) -> None:
    rule = create_regex_rule("GPT", "^(gpt-4o|O1-mini)$")
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(include_rules=[rule["id"]]),
    )

    async def fake_fetch(channel: Any) -> list[str]:
        assert len(channel.keys) == 1
        return ["gpt-4o", "O1-mini", "claude-3-opus"]

    _patch_upstream_models(monkeypatch, fake_fetch)
    result = _run_model_sync(client, admin_headers)

    assert {item["status"] for item in result["items"]} == {"updated"}
    assert _stored_models(client, admin_headers) == {
        ("cred-a", "manual-only", True),
        ("cred-a", "gpt-4o", False),
        ("cred-a", "O1-mini", False),
        ("cred-b", "gpt-4o", False),
        ("cred-b", "O1-mini", False),
    }
