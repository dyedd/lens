from __future__ import annotations


def test_site_protocol_headers_round_trip_as_rule_list(
    client,
    admin_headers,
    create_site,
) -> None:
    payload = {
        "name": "Rules Site",
        "tags": [],
        "base_urls": [
            {
                "id": "base-rules",
                "url": "https://upstream.example/v1",
                "name": "primary",
                "enabled": True,
                "supported_protocols": ["openai_chat"],
            }
        ],
        "credentials": [
            {
                "id": "cred-rules",
                "name": "primary",
                "api_key": "upstream-secret",
                "enabled": True,
            }
        ],
        "protocols": [
            {
                "id": "pc-rules",
                "name": "primary",
                "protocols": ["openai_chat"],
                "enabled": True,
                "headers": [
                    {
                        "name": "X-Trace",
                        "action": "override",
                        "value": "enabled",
                    }
                ],
                "param_override": [],
                "base_url_id": "base-rules",
                "credential_ids": ["cred-rules"],
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

    protocol = created["protocols"][0]
    assert protocol["headers"] == [
        {
            "name": "X-Trace",
            "action": "override",
            "value": "enabled",
            "match": None,
        }
    ]
