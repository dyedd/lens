from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from ..models.upstream_rules import HeaderRule, ParamOverrideRule


@dataclass(frozen=True, slots=True)
class RuleContext:
    """The upstream request identity used by every rule layer."""

    path: str
    model_name: str
    protocol: str


@dataclass(frozen=True, slots=True)
class RuleLayer:
    """One ordered source of upstream request rules."""

    name: str
    headers: Sequence[HeaderRule] = ()
    params: Sequence[ParamOverrideRule] = ()


class RuleEvaluationError(ValueError):
    """Raised when a valid rule cannot be applied to a request."""

    def __init__(self, message: str, *, source: str) -> None:
        super().__init__(f"Invalid upstream rule for {source}: {message}")
        self.source = source


def request_rule_context(url: str, *, model_name: Any, protocol: Any) -> RuleContext:
    """Build the context from the final upstream URL and target model."""
    return RuleContext(
        path=urlsplit(url).path,
        model_name=str(model_name or ""),
        protocol=getattr(protocol, "value", str(protocol)),
    )


def rules_from_config(config: Mapping[str, Any] | None, key: str) -> list[Any]:
    """Parse a persisted ``{rules: [...]}`` config through its rule model."""
    if not config:
        return []
    rule_type = HeaderRule if key == "headers" else ParamOverrideRule
    return [rule_type.model_validate(rule) for rule in config.get("rules", [])]


def apply_param_rules(
    body: Mapping[str, Any], layers: Sequence[RuleLayer]
) -> dict[str, Any]:
    """Apply parameter layers in order, with later layers taking precedence."""
    merged = deepcopy(dict(body))
    for layer in layers:
        for rule in layer.params:
            if rule.path == "model":
                raise RuleEvaluationError(
                    "model cannot be overridden", source=layer.name
                )
            _apply_param_rule(merged, rule)
    return merged


def param_rule_layers(
    global_config: Mapping[str, Any] | None,
    *,
    channel_rules: Sequence[ParamOverrideRule] = (),
    model_group_rules: Sequence[ParamOverrideRule] = (),
) -> list[RuleLayer]:
    """Build the standard ordered global/channel/model-group parameter layers."""
    return [
        RuleLayer("global settings", params=rules_from_config(global_config, "params")),
        RuleLayer("channel", params=channel_rules),
        RuleLayer("model group", params=model_group_rules),
    ]


def apply_header_rules(
    headers: Mapping[str, str],
    layers: Sequence[RuleLayer],
    *,
    context: RuleContext,
) -> dict[str, str]:
    """Apply header layers in order, using one shared request context."""
    result: dict[str, str] = {}
    merge_headers(result, headers)
    for layer in layers:
        for rule in layer.headers:
            if rule.name.lower() in {"authorization", "x-api-key", "x-goog-api-key"}:
                continue
            if not header_rule_matches(rule, context):
                continue
            name = rule.name.strip()
            if rule.action == "remove":
                _remove_header(result, name, rule.value)
            elif rule.action == "override":
                set_header(result, name, rule.value)
            else:
                current = _get_header(result, name)
                set_header(
                    result, name, f"{current}, {rule.value}" if current else rule.value
                )
    return result


def header_rule_matches(rule: HeaderRule, context: RuleContext) -> bool:
    match = rule.match
    if match is None:
        return True
    return all(
        value is None or bool(re.search(value, candidate))
        for value, candidate in (
            (match.path_regex, context.path),
            (match.model_regex, context.model_name),
            (match.protocol_regex, context.protocol),
        )
    )


def _apply_param_rule(body: dict[str, Any], rule: ParamOverrideRule) -> None:
    parts = rule.path.split(".")
    parent: Any = body
    for part in parts[:-1]:
        if isinstance(parent, dict):
            if part not in parent or not isinstance(parent[part], (dict, list)):
                if rule.action == "delete":
                    return
                parent[part] = [] if part.isdigit() else {}
            parent = parent[part]
        elif isinstance(parent, list) and part.isdigit() and int(part) < len(parent):
            parent = parent[int(part)]
        else:
            return
    leaf = parts[-1]
    if isinstance(parent, dict):
        if rule.action == "set":
            parent[leaf] = deepcopy(rule.value)
        else:
            parent.pop(leaf, None)
    elif isinstance(parent, list) and leaf.isdigit() and int(leaf) < len(parent):
        if rule.action == "delete":
            parent.pop(int(leaf))
        else:
            parent[int(leaf)] = deepcopy(rule.value)


def _get_header(headers: Mapping[str, str], name: str) -> str | None:
    return next(
        (value for key, value in headers.items() if key.lower() == name.lower()), None
    )


def merge_headers(headers: dict[str, str], updates: Mapping[str, str] | None) -> None:
    if updates:
        for key, value in updates.items():
            set_header(headers, key, value)


def set_header(headers: dict[str, str], key: str, value: str) -> None:
    trimmed_key = key.strip()
    if not trimmed_key:
        return
    lower_key = trimmed_key.lower()
    for existing_key in list(headers):
        if existing_key.lower() == lower_key:
            headers.pop(existing_key)
            break
    headers[trimmed_key] = str(value)


def _remove_header(headers: dict[str, str], name: str, token: str) -> None:
    for key in list(headers):
        if key.lower() != name.lower():
            continue
        if not token:
            headers.pop(key)
            return
        tokens = [
            part.strip()
            for part in headers[key].split(",")
            if part.strip().lower() != token.lower()
        ]
        if tokens:
            headers[key] = ", ".join(tokens)
        else:
            headers.pop(key)
