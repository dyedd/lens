from __future__ import annotations

import pytest
from conftest import assert_error


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
    }
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
