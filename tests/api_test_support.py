from __future__ import annotations

import asyncio
from typing import Any

from fastapi.responses import JSONResponse

from lens_api.core.runtime_channel_ids import compose_runtime_channel_id
from lens_api.models import ProtocolKind, RequestLogLifecycleStatus


def run_async(awaitable: Any) -> Any:
    """Run an awaitable to completion in a fresh event loop."""
    return asyncio.run(awaitable)


def valid_site_payload(
    *,
    name: str = "OpenAI Site",
    base_id: str = "base-1",
    credential_id: str = "cred-1",
    protocol_config_id: str = "pc-1",
    protocols: list[str] | None = None,
    model_name: str = "gpt-4o",
    credential_enabled: bool = True,
    base_url_enabled: bool = True,
    protocol_enabled: bool = True,
    model_enabled: bool = True,
) -> dict[str, Any]:
    """Build a valid site API payload with optional field overrides."""
    protocol_values = protocols or [ProtocolKind.OPENAI_CHAT.value]
    return {
        "name": name,
        "base_urls": [
            {
                "id": base_id,
                "url": "https://upstream.example/v1",
                "name": "primary",
                "enabled": base_url_enabled,
                "supported_protocols": protocol_values,
            }
        ],
        "credentials": [
            {
                "id": credential_id,
                "name": "primary-key",
                "api_key": "upstream-secret",
                "enabled": credential_enabled,
            }
        ],
        "protocols": [
            {
                "id": protocol_config_id,
                "name": "primary",
                "protocols": protocol_values,
                "enabled": protocol_enabled,
                "base_url_id": base_id,
                "credential_id": credential_id,
                "models": [
                    {
                        "credential_id": credential_id,
                        "model_name": model_name,
                        "enabled": model_enabled,
                        "protocol": protocol,
                    }
                    for protocol in protocol_values
                ],
            }
        ],
    }


def gateway_headers(key: dict[str, Any]) -> dict[str, str]:
    """Build bearer authorization headers for a gateway API key."""
    return {"Authorization": f"Bearer {key['api_key']}"}


def openai_chat_channel_id(protocol_config_id: str = "pc-1") -> str:
    """Build the runtime OpenAI chat channel identifier used by tests."""
    return compose_runtime_channel_id(protocol_config_id, ProtocolKind.OPENAI_CHAT)


def seed_request_log(
    app_state: Any,
    *,
    protocol: str = ProtocolKind.OPENAI_CHAT.value,
    requested_group_name: str | None = "gpt-4o",
    resolved_group_name: str | None = "gpt-4o",
    channel_id: str | None = None,
    channel_name: str | None = "OpenAI Site",
    gateway_key_id: str | None = None,
    status_code: int | None = 200,
    success: bool = True,
    error_message: str | None = None,
) -> Any:
    """Insert a representative request log through the current repository."""
    return run_async(
        app_state.request_log_store.create_request_log(
            protocol=protocol,
            user_agent="pytest",
            requested_group_name=requested_group_name,
            resolved_group_name=resolved_group_name,
            upstream_model_name=resolved_group_name,
            channel_id=channel_id or openai_chat_channel_id(),
            channel_name=channel_name,
            gateway_key_id=gateway_key_id,
            status_code=status_code,
            success=success,
            lifecycle_status=(
                RequestLogLifecycleStatus.SUCCEEDED
                if success
                else RequestLogLifecycleStatus.FAILED
            ),
            is_stream=False,
            first_token_latency_ms=12,
            latency_ms=34,
            input_tokens=10,
            cache_read_input_tokens=1,
            cache_write_input_tokens=2,
            output_tokens=20,
            total_tokens=30,
            input_cost_usd=0.01,
            output_cost_usd=0.02,
            total_cost_usd=0.03,
            request_content='{"model":"gpt-4o"}',
            response_content='{"ok":true}',
            attempts=[
                {
                    "channel_id": channel_id or openai_chat_channel_id(),
                    "channel_name": channel_name or "OpenAI Site",
                    "credential_id": "cred-1",
                    "credential_name": "primary-key",
                    "model_name": resolved_group_name,
                    "status_code": status_code,
                    "success": success,
                    "duration_ms": 34,
                    "error_message": error_message,
                }
            ],
            error_message=error_message,
        )
    )


def assert_error(response: Any, status_code: int, message: str | None = None) -> None:
    """Assert the standard API error response shape and optional message."""
    assert response.status_code == status_code, response.text
    payload = response.json()
    assert "error" in payload
    if message is not None:
        assert message in payload["error"]["message"]


def json_response(payload: dict[str, Any], status_code: int = 200) -> JSONResponse:
    """Create a JSON response for gateway test doubles."""
    return JSONResponse(payload, status_code=status_code)
