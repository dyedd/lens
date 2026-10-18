from __future__ import annotations

from typing import Any

import pytest
from conftest import assert_error, valid_site_payload


def test_regex_rule_crud_happy_path(client, admin_headers, create_regex_rule) -> None:
    created = client.post(
        "/api/admin/regex-rules",
        headers=admin_headers,
        json={"name": "  GPT  ", "pattern": " (?i)^gpt- ", "description": " OpenAI "},
    )
    rule_id = created.json()["id"]
    create_regex_rule("claude", "^claude-")

    updated = client.put(
        f"/api/admin/regex-rules/{rule_id}",
        headers=admin_headers,
        json={"pattern": "^gpt-4", "description": None},
    )
    listed = client.get("/api/admin/regex-rules", headers=admin_headers)
    deleted = client.delete(f"/api/admin/regex-rules/{rule_id}", headers=admin_headers)

    assert created.status_code == 201, created.text
    assert created.json() == {
        "id": rule_id,
        "name": "GPT",
        "pattern": "^gpt-",
        "description": "OpenAI",
        "groups": [],
        "sites": [],
    }
    assert updated.status_code == 200, updated.text
    assert updated.json() == {**created.json(), "pattern": "^gpt-4"}
    assert [rule["name"] for rule in listed.json()] == ["claude", "GPT"]
    assert deleted.status_code == 204
    assert [
        rule["name"]
        for rule in client.get("/api/admin/regex-rules", headers=admin_headers).json()
    ] == ["claude"]


@pytest.mark.parametrize(
    ("payload", "status_code"),
    [
        pytest.param({"name": "gpt", "pattern": "^gpt-4"}, 409, id="duplicate-name"),
        pytest.param({"name": "Broken", "pattern": "("}, 422, id="invalid-regex"),
    ],
)
def test_create_regex_rule_rejects_duplicate_names_and_invalid_patterns(
    client,
    admin_headers,
    create_regex_rule,
    payload: dict[str, str],
    status_code: int,
) -> None:
    create_regex_rule("GPT", "^gpt-")

    response = client.post(
        "/api/admin/regex-rules", headers=admin_headers, json=payload
    )

    assert_error(response, status_code)
    assert len(client.get("/api/admin/regex-rules", headers=admin_headers).json()) == 1


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        pytest.param(
            "/api/admin/sites",
            {**valid_site_payload(), "model_sync_include_rule_ids": ["missing"]},
            id="site",
        ),
        pytest.param(
            "/api/admin/model-groups",
            {"name": "family", "items": [], "match_rule_ids": ["missing"]},
            id="group",
        ),
    ],
)
def test_writes_reject_unknown_regex_rule_ids(
    client, admin_headers, path: str, payload: dict[str, Any]
) -> None:
    response = client.post(path, headers=admin_headers, json=payload)

    assert_error(response, 400, "Regex rule not found: missing")


def test_deleting_rule_removes_it_from_referencing_sites(
    client,
    admin_headers,
    create_site,
    create_regex_rule,
) -> None:
    kept = create_regex_rule("Keep", "^gpt-")
    dropped = create_regex_rule("Drop", "-preview$")
    site_payload = valid_site_payload()
    site_payload["model_sync_include_rule_ids"] = [dropped["id"], kept["id"]]
    create_site(site_payload)

    response = client.delete(
        f"/api/admin/regex-rules/{dropped['id']}", headers=admin_headers
    )

    assert response.status_code == 204
    stored_site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    assert stored_site["model_sync_include_rule_ids"] == [kept["id"]]
    rules = client.get("/api/admin/regex-rules", headers=admin_headers).json()
    assert all(rule["id"] != dropped["id"] for rule in rules)
    assert next(rule for rule in rules if rule["id"] == kept["id"]) == {
        **kept,
        "sites": [{"id": stored_site["id"], "name": stored_site["name"]}],
    }
