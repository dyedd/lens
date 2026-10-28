from __future__ import annotations


def test_global_regex_rule_api_is_removed(client, admin_headers) -> None:
    response = client.post(
        "/api/admin/regex-rules",
        headers=admin_headers,
        json={"name": "GPT", "pattern": "^gpt-"},
    )

    assert response.status_code == 404
