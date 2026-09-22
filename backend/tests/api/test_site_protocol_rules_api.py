from __future__ import annotations


def test_site_protocol_headers_round_trip_as_rule_list(
    client,
    admin_headers,
    create_site,
) -> None:
    payload = {
        "name": "Rules Site",
        "tags": [],
        "headers": [
            {
                "name": "X-Trace",
                "action": "override",
                "value": "enabled",
            }
        ],
        "base_urls": [
            {
                "id": "base-rules",
                "url": "https://upstream.example/v1",
            }
        ],
        "credentials": [
            {
                "id": "cred-rules",
                "name": "primary",
                "api_key": "upstream-secret",
            }
        ],
        "protocols": [
            {
                "id": "pc-rules",
                "base_url_id": "base-rules",
                "models": [
                    {
                        "credential_id": "cred-rules",
                        "model_name": "gpt-4o",
                        "enabled": True,
                        "protocol": "openai_chat",
                    }
                ],
            }
        ],
    }

    created = create_site(payload)

    assert created["headers"] == [
        {
            "name": "X-Trace",
            "action": "override",
            "value": "enabled",
            "match": None,
        }
    ]
