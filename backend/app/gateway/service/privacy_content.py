"""Protocol content boundaries for rule privacy transformations."""

import json
from collections.abc import Callable, Iterator
from typing import Any

from app.models.protocols import ProtocolKind

TextTransform = Callable[[str, str], str]
SealedTransform = Callable[[dict[str, Any]], dict[str, Any]]
SIGNATURE_FIELDS = ("signature", "thoughtSignature", "encrypted_content")
ANTHROPIC_TOOL_TYPES = {"tool_use", "server_tool_use", "mcp_tool_use"}
_TEXT_FIELDS = {
    "text",
    "thinking",
    "reasoning_content",
    "refusal",
    "description",
    "instructions",
    "system",
    "prompt",
    "revised_prompt",
    "query",
}
_CONTENT_FIELDS = {
    "system",
    "instructions",
    "messages",
    "input",
    "contents",
    "systemInstruction",
    "system_instruction",
    "content",
    "parts",
    "output",
    "summary",
    "reasoning",
    "choices",
    "candidates",
    "message",
    "delta",
    "item",
    "response",
    "content_block",
}
_TOOL_FIELDS = {
    "tools",
    "functions",
    "function_declarations",
    "functionDeclarations",
    "tool_calls",
    "function",
    "function_call",
    "functionCall",
    "functionResponse",
}
_SCHEMA_FIELDS = {
    "parameters",
    "input_schema",
    "parametersJsonSchema",
    "responseJsonSchema",
    "json_schema",
}


def signed_nodes(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        if any(
            isinstance(value.get(field), str) and value[field]
            for field in SIGNATURE_FIELDS
        ):
            yield value
        for field in _CONTENT_FIELDS | _TOOL_FIELDS:
            if field in value:
                yield from signed_nodes(value[field])
    elif isinstance(value, list):
        for child in value:
            yield from signed_nodes(child)


def transform_business(
    value: Any, transform: TextTransform, field_name: str = ""
) -> Any:
    if isinstance(value, str):
        return transform(value, field_name)
    if isinstance(value, list):
        return [transform_business(child, transform, field_name) for child in value]
    if isinstance(value, dict):
        return {
            name: transform_business(child, transform, name)
            for name, child in value.items()
        }
    return value


def transform_json_text(value: str, transform: TextTransform) -> str:
    try:
        parsed = json.loads(value)
    except ValueError:
        return transform(value, "")
    return json.dumps(
        transform_business(parsed, transform), ensure_ascii=False, separators=(",", ":")
    )


def transform_content(
    value: Any,
    protocol: ProtocolKind,
    transform: TextTransform,
    sealed: SealedTransform | None = None,
) -> Any:
    def schema_descriptions(schema: Any) -> Any:
        if isinstance(schema, dict):
            return {
                name: transform(child, "")
                if name == "description" and isinstance(child, str)
                else child
                if name in {"enum", "const", "default"}
                else schema_descriptions(child)
                for name, child in schema.items()
            }
        if isinstance(schema, list):
            return [schema_descriptions(child) for child in schema]
        return schema

    def visit(node: Any) -> Any:
        if isinstance(node, str):
            return transform(node, "")
        if isinstance(node, list):
            return [visit(child) for child in node]
        if not isinstance(node, dict):
            return node
        if sealed is not None and any(node.get(field) for field in SIGNATURE_FIELDS):
            return sealed(node)
        result = dict(node)
        for name, child in node.items():
            if name in _TEXT_FIELDS and isinstance(child, str):
                result[name] = transform(child, "")
            elif name == "arguments" and isinstance(child, str):
                result[name] = transform_json_text(child, transform)
            elif (
                name in {"args", "arguments"}
                or (name == "input" and node.get("type") in ANTHROPIC_TOOL_TYPES)
                or (name == "response" and "name" in node)
            ):
                result[name] = transform_business(child, transform)
            elif name == "output" and node.get("type") in {
                "function_call_output",
                "custom_tool_call_output",
            }:
                result[name] = (
                    transform_json_text(child, transform)
                    if isinstance(child, str)
                    else transform_business(child, transform)
                )
            elif name == "content" and (
                node.get("type") == "tool_result" or node.get("role") == "tool"
            ):
                result[name] = (
                    transform_json_text(child, transform)
                    if isinstance(child, str)
                    else visit(child)
                )
            elif name in _CONTENT_FIELDS | _TOOL_FIELDS:
                result[name] = visit(child)
            elif name in _SCHEMA_FIELDS:
                result[name] = schema_descriptions(child)
            elif (
                name in {"documents", "results", "document"}
                and protocol == ProtocolKind.RERANK
            ):
                result[name] = visit(child)
            elif name == "data" and protocol == ProtocolKind.OPENAI_IMAGE:
                result[name] = visit(child)
        return result

    return visit(value)
