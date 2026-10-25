from __future__ import annotations


def test_regex_rule_crud_round_trip(client, admin_headers, create_regex_rule) -> None:
    assert client.get("/api/admin/regex-rules", headers=admin_headers).json() == []

    rule = create_regex_rule("GPT", "^gpt-")
    assert rule["name"] == "GPT"

    update = client.put(
        f"/api/admin/regex-rules/{rule['id']}",
        headers=admin_headers,
        json={"name": "OpenAI", "pattern": "^gpt-4"},
    )
    assert update.status_code == 200
    assert update.json()["pattern"] == "^gpt-4"

    delete = client.delete(
        f"/api/admin/regex-rules/{rule['id']}", headers=admin_headers
    )
    assert delete.status_code == 204
    assert client.get("/api/admin/regex-rules", headers=admin_headers).json() == []
