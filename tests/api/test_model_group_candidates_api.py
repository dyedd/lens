from __future__ import annotations

import pytest

from conftest import openai_chat_channel_id, valid_site_payload


@pytest.mark.parametrize("exclude", [False, True])
def test_model_group_candidates_return_site_models(
    client,
    admin_headers,
    create_site,
    exclude,
) -> None:
    site = create_site(valid_site_payload(model_name="gpt-4o-mini"))
    items = []
    if exclude:
        items.append(
            {
                "channel_id": openai_chat_channel_id(),
                "credential_id": "cred-1",
                "model_name": "gpt-4o-mini",
            }
        )

    response = client.post(
        "/api/admin/model-group-candidates",
        headers=admin_headers,
        json={"protocols": ["openai_chat"], "items": items},
    )

    assert response.status_code == 200
    payload = response.json()
    candidates = payload["candidates"]
    if exclude:
        assert candidates == []
        evaluated_item = payload["evaluated_items"][0]
        assert evaluated_item["site_id"] == site["id"]
        return
    assert len(candidates) == 1
    assert candidates[0]["site_id"] == site["id"]
    assert candidates[0]["model_name"] == "gpt-4o-mini"
    candidate_item = candidates[0]["items"][0]
    assert candidate_item["channel_id"] == openai_chat_channel_id()
    assert candidate_item["credential_id"] == "cred-1"
