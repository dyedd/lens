from __future__ import annotations

from typing import Any

from ...models import ProtocolKind
from .payload_serialization import _stringify_text_content
from .usage import _parse_sse_payloads


def extract_site_model_output(protocol: ProtocolKind, raw_payload: Any) -> str:
    """Extract a concise display value from a model-probe response."""
    if protocol == ProtocolKind.OPENAI_CHAT:
        return _extract_openai_chat_output(raw_payload)
    if protocol == ProtocolKind.OPENAI_RESPONSES:
        return _extract_openai_responses_output(raw_payload)
    if protocol == ProtocolKind.OPENAI_EMBEDDING:
        return _extract_embedding_output(raw_payload)
    if protocol == ProtocolKind.RERANK:
        return _summarize_rerank_result(raw_payload)
    if protocol == ProtocolKind.ANTHROPIC:
        return _extract_anthropic_output(raw_payload)
    if protocol == ProtocolKind.GEMINI:
        return _extract_gemini_output(raw_payload)
    if protocol == ProtocolKind.OPENAI_IMAGE:
        return _extract_image_output(raw_payload)
    return ""


def extract_site_model_stream_output(protocol: ProtocolKind, raw_content: str) -> str:
    """Extract display text from a streaming model-probe response."""
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


def _extract_openai_chat_output(raw_payload: Any) -> str:
    choices = raw_payload.get("choices")
    if not isinstance(choices, list):
        return ""
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        text = _stringify_text_content(message.get("content")).strip()
        if text:
            return text
    return ""


def _extract_openai_responses_output(raw_payload: Any) -> str:
    output_text = raw_payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    output = raw_payload.get("output")
    if not isinstance(output, list):
        return ""
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
    return "\n".join(parts)


def _extract_embedding_output(raw_payload: Any) -> str:
    data = raw_payload.get("data")
    if not isinstance(data, list):
        return ""
    for item in data:
        if not isinstance(item, dict):
            continue
        vector = item.get("embedding")
        if isinstance(vector, list):
            return f"<vector dim={len(vector)}>"
        if isinstance(vector, str) and vector:
            return f"<vector base64 len={len(vector)}>"
    return ""


def _extract_anthropic_output(raw_payload: Any) -> str:
    content = raw_payload.get("content")
    if not isinstance(content, list):
        return ""
    parts = [
        str(item.get("text")).strip()
        for item in content
        if isinstance(item, dict) and item.get("type") == "text" and item.get("text")
    ]
    return "\n".join(parts)


def _extract_gemini_output(raw_payload: Any) -> str:
    candidates = raw_payload.get("candidates")
    if not isinstance(candidates, list):
        return ""
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
            return "\n".join(parts)
    return ""


def _extract_image_output(raw_payload: Any) -> str:
    data = raw_payload.get("data")
    if not isinstance(data, list):
        return ""
    for item in data:
        if not isinstance(item, dict):
            continue
        revised = item.get("revised_prompt")
        if isinstance(revised, str) and revised.strip():
            return revised.strip()
    return ""


def _summarize_rerank_result(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        return ""
    top_result = max(
        (item for item in results if isinstance(item, dict)),
        key=lambda item: _coerce_relevance_score(item.get("relevance_score")),
        default=None,
    )
    if top_result is None:
        return ""
    score = _coerce_relevance_score(top_result.get("relevance_score"))
    index = top_result.get("index")
    document = top_result.get("document")
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
