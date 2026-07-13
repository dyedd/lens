from __future__ import annotations

from conftest import assert_error


def test_model_group_sync_filter_is_normalized_and_validated(
    client,
    admin_headers,
) -> None:
    created = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "filtered",
            "protocols": ["openai_chat"],
            "sync_filter_mode": "contains",
            "sync_filter_query": "  gpt  ",
        },
    )
    invalid = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "invalid-filter",
            "protocols": ["openai_chat"],
            "sync_filter_mode": "regex",
            "sync_filter_query": "[",
        },
    )

    assert created.status_code == 201
    assert created.json()["sync_filter_mode"] == "contains"
    assert created.json()["sync_filter_query"] == "gpt"
    assert_error(invalid, 422, "Request validation failed")


def test_create_route_group_rejects_invalid_route_targets(
    client,
    admin_headers,
    create_model_group,
) -> None:
    target = create_model_group(name="target", protocols=["openai_chat"])
    route = create_model_group(
        name="route",
        protocols=["openai_chat"],
        route_group_id=target["id"],
    )

    missing = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "missing-target",
            "protocols": ["openai_chat"],
            "route_group_id": "missing",
        },
    )
    missing_protocol = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "missing-protocol",
            "protocols": ["openai_chat", "gemini"],
            "route_group_id": target["id"],
        },
    )
    chained = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "chained",
            "protocols": ["openai_chat"],
            "route_group_id": route["id"],
        },
    )

    assert_error(missing, 400, "Route target model group not found")
    assert_error(missing_protocol, 400, "Route target protocols must cover")
    assert_error(chained, 400, "Route target must be an execution group")


def test_update_model_group_rejects_self_route(
    client, admin_headers, create_model_group
) -> None:
    group = create_model_group(name="self-route")

    response = client.put(
        f"/api/admin/model-groups/{group['id']}",
        headers=admin_headers,
        json={"route_group_id": group["id"]},
    )

    assert_error(response, 400, "cannot route to itself")


def test_update_referenced_execution_group_preserves_route_group_contracts(
    client,
    admin_headers,
    create_model_group,
) -> None:
    execution = create_model_group(
        name="execution",
        protocols=["openai_chat", "gemini"],
    )
    create_model_group(
        name="route",
        protocols=["openai_chat"],
        route_group_id=execution["id"],
    )
    target = create_model_group(name="target", protocols=["openai_chat", "gemini"])

    remove_protocol = client.put(
        f"/api/admin/model-groups/{execution['id']}",
        headers=admin_headers,
        json={"protocols": ["openai_chat"]},
    )
    become_route = client.put(
        f"/api/admin/model-groups/{execution['id']}",
        headers=admin_headers,
        json={"route_group_id": target["id"]},
    )

    assert_error(remove_protocol, 400, "cannot remove protocols")
    assert_error(become_route, 400, "cannot become route groups")


def test_update_route_group_clears_sync_filter(
    client,
    admin_headers,
    create_model_group,
) -> None:
    target = create_model_group(name="target")
    source = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "source",
            "protocols": ["openai_chat"],
            "sync_filter_mode": "contains",
            "sync_filter_query": "gpt",
        },
    ).json()

    response = client.put(
        f"/api/admin/model-groups/{source['id']}",
        headers=admin_headers,
        json={"route_group_id": target["id"]},
    )

    assert response.status_code == 200
    assert response.json()["route_group_id"] == target["id"]
    assert response.json()["sync_filter_mode"] == ""
    assert response.json()["sync_filter_query"] == ""


def test_delete_model_group_rejects_referenced_execution_group(
    client,
    admin_headers,
    create_model_group,
) -> None:
    execution_group = create_model_group(name="gpt-4o")
    create_model_group(
        name="public-gpt-4o",
        route_group_id=execution_group["id"],
    )

    response = client.delete(
        f"/api/admin/model-groups/{execution_group['id']}",
        headers=admin_headers,
    )

    assert_error(response, 400, "still referenced")
