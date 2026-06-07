from __future__ import annotations

from .runtime_context import (
    Any,
    ChannelConfig,
    HTTPException,
    ProtocolKind,
    SiteModelTestRequest,
    SiteModelTestResult,
    UpstreamRequest,
    UpstreamRequestError,
    app_state,
    build_upstream_request,
    httpx,
    perf_counter,
    resolve_upstream_proxy_url,
    settings,
)
from .upstream_http import (
    _default_lens_user_agent,
    _format_channel_error,
    _format_http_response_error,
    _format_transport_error,
    _resolve_http_client,
)
from .routing_plan import (
    _apply_param_override,
    _elapsed_ms,
)
from .usage import _parse_sse_payloads
from .payload_serialization import _decode_content_bytes, _stringify_text_content


def _site_model_probe_channel(payload: SiteModelTestRequest) -> ChannelConfig:
    return ChannelConfig(
        id="model-test",
        name=payload.credential.name or "model-test",
        protocol=payload.protocol,
        base_url=payload.base_url,
        api_key=payload.credential.api_key,
        headers=payload.headers,
        model_patterns=[],
        keys=[
            {
                "id": payload.credential.id,
                "key": payload.credential.api_key,
                "remark": payload.credential.name,
                "enabled": True,
            }
        ],
        models=[],
        channel_proxy=payload.channel_proxy,
        param_override=payload.param_override,
        match_regex="",
    )


async def _call_site_model_probe_channel(
    *,
    channel: ChannelConfig,
    body: dict[str, Any],
    model_name: str,
    credential_id: str,
) -> SiteModelTestResult:
    upstream = build_upstream_request(
        channel,
        body,
        settings,
        credential_id=credential_id,
        user_agent=_default_lens_user_agent(),
    )
    runtime = await app_state.domain_store.get_runtime_settings()
    proxy_url = resolve_upstream_proxy_url(channel, runtime["proxy_url"])
    client, close_client = _resolve_http_client(proxy_url)

    started_at = perf_counter()
    try:
        return await _run_site_model_probe_request(
            client=client,
            upstream=upstream,
            channel=channel,
            model_name=model_name,
            credential_id=credential_id,
            started_at=started_at,
        )
    finally:
        if close_client:
            await client.aclose()


async def _run_site_model_probe_request(
    *,
    client: httpx.AsyncClient,
    upstream: UpstreamRequest,
    channel: ChannelConfig,
    model_name: str,
    credential_id: str,
    started_at: float,
) -> SiteModelTestResult:
    try:
        response = await client.request(
            upstream.method,
            upstream.url,
            headers=upstream.headers,
            json=upstream.json_body,
        )
        latency_ms = _elapsed_ms(started_at)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            await exc.response.aread()
            detail = _format_http_response_error(exc.response)
            return SiteModelTestResult(
                success=False,
                status_code=exc.response.status_code,
                latency_ms=latency_ms,
                model_name=model_name,
                credential_id=credential_id,
                error_message=detail,
            )
        content_type = (response.headers.get("content-type") or "").lower()
        if "text/event-stream" in content_type:
            raw_content = _decode_content_bytes(response.content) or ""
            output_text = _site_model_probe_stream_output_text(
                channel.protocol, raw_content
            )
        else:
            raw_payload = response.json()
            output_text = _site_model_probe_output_text(channel.protocol, raw_payload)
        return SiteModelTestResult(
            success=True,
            status_code=response.status_code,
            latency_ms=latency_ms,
            model_name=model_name,
            credential_id=credential_id,
            output_text=output_text,
        )
    except httpx.HTTPError as exc:
        return SiteModelTestResult(
            success=False,
            status_code=502,
            latency_ms=_elapsed_ms(started_at),
            model_name=model_name,
            credential_id=credential_id,
            error_message=_format_transport_error(exc, upstream.url),
        )
    except ValueError as exc:
        return SiteModelTestResult(
            success=False,
            status_code=502,
            latency_ms=_elapsed_ms(started_at),
            model_name=model_name,
            credential_id=credential_id,
            error_message=f"Invalid upstream response: {exc}",
        )


def _site_model_probe_output_text(protocol: ProtocolKind, raw_payload: Any) -> str:
    output_text = ""
    if protocol == ProtocolKind.OPENAI_CHAT:
        choices = raw_payload.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                message = choice.get("message")
                if not isinstance(message, dict):
                    continue
                text = _stringify_text_content(message.get("content")).strip()
                if text:
                    output_text = text
                    break
    elif protocol == ProtocolKind.OPENAI_RESPONSES:
        output_text_raw = raw_payload.get("output_text")
        if isinstance(output_text_raw, str) and output_text_raw.strip():
            output_text = output_text_raw.strip()
        else:
            output = raw_payload.get("output")
            if isinstance(output, list):
                parts: list[str] = []
                for item in output:
                    if not isinstance(item, dict):
                        continue
                    content = item.get("content")
                    if not isinstance(content, list):
                        continue
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "output_text":
                            text = part.get("text")
                            if isinstance(text, str) and text.strip():
                                parts.append(text.strip())
                output_text = "\n".join(parts)
    elif protocol == ProtocolKind.OPENAI_EMBEDDING:
        data = raw_payload.get("data")
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                vector = item.get("embedding")
                if isinstance(vector, list):
                    output_text = f"<vector dim={len(vector)}>"
                    break
                if isinstance(vector, str) and vector:
                    output_text = f"<vector base64 len={len(vector)}>"
                    break
    elif protocol == ProtocolKind.RERANK:
        output_text = _summarize_rerank_result(raw_payload)
    elif protocol == ProtocolKind.ANTHROPIC:
        content = raw_payload.get("content")
        if isinstance(content, list):
            parts = [
                str(item.get("text")).strip()
                for item in content
                if isinstance(item, dict)
                and item.get("type") == "text"
                and item.get("text")
            ]
            output_text = "\n".join(parts)
    elif protocol == ProtocolKind.GEMINI:
        candidates = raw_payload.get("candidates")
        if isinstance(candidates, list):
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                content = candidate.get("content")
                if not isinstance(content, dict):
                    continue
                parts_list = content.get("parts")
                if not isinstance(parts_list, list):
                    continue
                parts = [
                    str(part.get("text")).strip()
                    for part in parts_list
                    if isinstance(part, dict) and part.get("text")
                ]
                if parts:
                    output_text = "\n".join(parts)
                    break
    return output_text


def _site_model_probe_stream_output_text(
    protocol: ProtocolKind, raw_content: str
) -> str:
    if protocol != ProtocolKind.OPENAI_CHAT:
        return ""

    parts: list[str] = []
    for payload in _parse_sse_payloads(raw_content):
        choices = payload.get("choices")
        if not isinstance(choices, list):
            continue
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            delta = choice.get("delta")
            if not isinstance(delta, dict):
                continue
            text = _stringify_text_content(delta.get("content"))
            if text:
                parts.append(text)
    return "".join(parts).strip()


def _site_model_probe_body(payload: SiteModelTestRequest) -> dict[str, Any]:
    text = payload.prompt.strip()
    if payload.protocol == ProtocolKind.OPENAI_CHAT:
        return {
            "model": payload.model_name,
            "messages": [{"role": "user", "content": text}],
            "max_tokens": 64,
            "stream": False,
        }
    if payload.protocol == ProtocolKind.OPENAI_RESPONSES:
        return {
            "model": payload.model_name,
            "input": text,
            "max_output_tokens": 64,
            "stream": False,
        }
    if payload.protocol == ProtocolKind.OPENAI_EMBEDDING:
        return {
            "model": payload.model_name,
            "input": text,
        }
    if payload.protocol == ProtocolKind.RERANK:
        query, documents = _rerank_test_prompt(text)
        return {
            "model": payload.model_name,
            "query": query,
            "documents": documents,
            "top_n": min(3, len(documents)),
            "return_documents": True,
        }
    if payload.protocol == ProtocolKind.ANTHROPIC:
        return {
            "model": payload.model_name,
            "messages": [{"role": "user", "content": text}],
            "max_tokens": 64,
            "stream": False,
        }
    if payload.protocol == ProtocolKind.GEMINI:
        return {
            "model": payload.model_name,
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {"maxOutputTokens": 64},
            "stream": False,
        }
    raise HTTPException(
        status_code=500, detail=f"Unsupported protocol={payload.protocol.value}"
    )


def _apply_site_model_probe_param_override(
    channel: ChannelConfig, body: dict[str, Any], payload: SiteModelTestRequest
) -> dict[str, Any] | SiteModelTestResult:
    try:
        prepared_body = _apply_param_override(channel, body)
    except UpstreamRequestError as exc:
        return SiteModelTestResult(
            success=False,
            status_code=exc.status_code,
            latency_ms=0,
            model_name=payload.model_name,
            credential_id=payload.credential.id,
            error_message=_format_channel_error(exc.detail),
        )
    if payload.protocol == ProtocolKind.RERANK:
        prepared_body.pop("stream", None)
    else:
        prepared_body["stream"] = False
    return prepared_body


def _summarize_rerank_result(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        return ""
    top = max(
        (item for item in results if isinstance(item, dict)),
        key=lambda item: _coerce_relevance_score(item.get("relevance_score")),
        default=None,
    )
    if top is None:
        return ""
    score = _coerce_relevance_score(top.get("relevance_score"))
    index = top.get("index")
    document = top.get("document")
    document_text = ""
    if isinstance(document, dict):
        text_value = document.get("text")
        if isinstance(text_value, str):
            document_text = text_value
    elif isinstance(document, str):
        document_text = document
    snippet = document_text.strip().replace("\n", " ")
    if len(snippet) > 120:
        snippet = snippet[:117] + "..."
    parts: list[str] = [f"top score={score:.4f}"]
    if isinstance(index, int):
        parts.append(f"index={index}")
    if snippet:
        parts.append(f"document={snippet}")
    return "; ".join(parts)


def _coerce_relevance_score(value: Any) -> float:
    try:
        if value is None:
            return float("-inf")
        return float(value)
    except (TypeError, ValueError):
        return float("-inf")


def _rerank_test_prompt(text: str) -> tuple[str, list[str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) >= 2:
        return lines[0], lines[1:]
    query = lines[0] if lines else text.strip()
    return query, [query]
