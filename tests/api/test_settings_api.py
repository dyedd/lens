from __future__ import annotations

import json

import pytest

from conftest import assert_error
from lens_api.persistence.shared import (
    SETTING_RELAY_LOG_BODY_ENABLED,
    SETTING_RELAY_LOG_KEEP_PERIOD,
    SETTING_SITE_NAME,
    SETTING_TIME_ZONE,
    SETTING_UPSTREAM_HEADERS_CONFIG,
    SETTING_UPSTREAM_PARAM_OVERRIDE_CONFIG,
)


def test_list_settings_requires_admin(client) -> None:
    response = client.get("/api/admin/settings")

    assert_error(response, 401, "Not authenticated")


def test_update_settings_normalizes_known_values(client, admin_headers) -> None:
    response = client.put(
        "/api/admin/settings",
        headers=admin_headers,
        json={
            "items": [
                {"key": SETTING_SITE_NAME, "value": "  "},
                {"key": SETTING_TIME_ZONE, "value": "Asia/Shanghai"},
                {"key": SETTING_RELAY_LOG_BODY_ENABLED, "value": "YES"},
                {"key": SETTING_RELAY_LOG_KEEP_PERIOD, "value": " 14 "},
            ]
        },
    )

    assert response.status_code == 200
    settings = {item["key"]: item["value"] for item in response.json()}
    assert settings[SETTING_SITE_NAME] == "Lens"
    assert settings[SETTING_TIME_ZONE] == "Asia/Shanghai"
    assert settings[SETTING_RELAY_LOG_BODY_ENABLED] == "true"
    assert settings[SETTING_RELAY_LOG_KEEP_PERIOD] == "14"

    listed = client.get("/api/admin/settings", headers=admin_headers)
    assert listed.status_code == 200
    assert {item["key"]: item["value"] for item in listed.json()} == settings


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        (SETTING_RELAY_LOG_KEEP_PERIOD, "abc", "Invalid integer setting"),
        (SETTING_RELAY_LOG_BODY_ENABLED, "maybe", "Invalid boolean setting"),
        (SETTING_TIME_ZONE, "Mars/Base", "Invalid IANA time zone"),
    ],
)
def test_update_settings_rejects_invalid_known_values(
    client,
    admin_headers,
    key: str,
    value: str,
    message: str,
) -> None:
    response = client.put(
        "/api/admin/settings",
        headers=admin_headers,
        json={"items": [{"key": key, "value": value}]},
    )

    assert_error(response, 400, message)


def test_update_settings_normalizes_upstream_headers_config(
    client,
    admin_headers,
) -> None:
    response = client.put(
        "/api/admin/settings",
        headers=admin_headers,
        json={
            "items": [
                {
                    "key": SETTING_UPSTREAM_HEADERS_CONFIG,
                    "value": (
                        '{"global":{" X-Test ":" value "},'
                        '"rules":[{"name":" r ","models":[" gpt-4o ",""],'
                        '"headers":{"Authorization":" Bearer token "}}]}'
                    ),
                }
            ]
        },
    )

    assert response.status_code == 200
    stored = json.loads({
        item["key"]: item["value"]
        for item in response.json()
    }[SETTING_UPSTREAM_HEADERS_CONFIG])
    assert stored["global"] == {"X-Test": "value"}
    assert stored["rules"][0]["models"] == ["gpt-4o"]
    assert stored["rules"][0]["headers"] == {"Authorization": "Bearer token"}


def test_update_settings_rejects_model_param_override(
    client,
    admin_headers,
) -> None:
    response = client.put(
        "/api/admin/settings",
        headers=admin_headers,
        json={
            "items": [
                {
                    "key": SETTING_UPSTREAM_PARAM_OVERRIDE_CONFIG,
                    "value": '{"global":{"model":"gpt-4o"}}',
                }
            ]
        },
    )

    assert_error(response, 400, "model cannot be overridden")
