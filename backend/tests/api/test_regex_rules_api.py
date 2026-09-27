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
        "sites": [],
        "groups": [],
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
            {**valid_site_payload(), "model_sync_exclude_rule_ids": ["missing"]},
            id="site",
        ),
        pytest.param(
            "/api/admin/model-groups",
            {"name": "family", "match_rule_ids": ["missing"]},
            id="group",
        ),
    ],
)
def test_writes_reject_unknown_regex_rule_ids(
    client, admin_headers, path: str, payload: dict[str, Any]
) -> None:
    response = client.post(path, headers=admin_headers, json=payload)

    assert_error(response, 400, "Regex rule not found: missing")


def test_updating_rule_pattern_changes_referencing_group_members(
    client,
    admin_headers,
    create_site,
    create_regex_rule,
) -> None:
    create_site(valid_site_payload(model_name="gpt-4o"))
    rule = create_regex_rule("Family", "^claude-")
    group = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={"name": "family", "match_rule_ids": [rule["id"]]},
    ).json()

    response = client.put(
        f"/api/admin/regex-rules/{rule['id']}",
        headers=admin_headers,
        json={"pattern": "^gpt-"},
    )
    members = client.get(
        f"/api/admin/model-groups/{group['id']}", headers=admin_headers
    ).json()["items"]

    assert group["items"] == []
    assert response.json()["groups"] == [{"id": group["id"], "name": "family"}]
    assert [(item["model_name"], item["matched_by_rule"]) for item in members] == [
        ("gpt-4o", True)
    ]


def test_deleting_rule_removes_it_from_referencing_site_and_group(
    client,
    admin_headers,
    create_site,
    create_regex_rule,
) -> None:
    kept = create_regex_rule("Keep", "^gpt-")
    dropped = create_regex_rule("Drop", "-preview$")
    site = create_site(
        {
            **valid_site_payload(),
            "model_sync_include_rule_ids": [dropped["id"], kept["id"]],
            "model_sync_exclude_rule_ids": [dropped["id"]],
        }
    )
    group = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={"name": "family", "match_rule_ids": [dropped["id"], kept["id"]]},
    ).json()

    response = client.delete(
        f"/api/admin/regex-rules/{dropped['id']}", headers=admin_headers
    )

    assert response.status_code == 204
    stored_site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    assert (
        stored_site["model_sync_include_rule_ids"],
        stored_site["model_sync_exclude_rule_ids"],
    ) == ([kept["id"]], [])
    stored_group = client.get(
        f"/api/admin/model-groups/{group['id']}", headers=admin_headers
    ).json()
    assert stored_group["match_rule_ids"] == [kept["id"]]
    assert client.get("/api/admin/regex-rules", headers=admin_headers).json() == [
        {
            **kept,
            "sites": [{"id": site["id"], "name": site["name"]}],
            "groups": [{"id": group["id"], "name": "family"}],
        }
    ]
