from __future__ import annotations

import json

from ..models.protocols import ProtocolKind

_PROTOCOL_KIND_BY_VALUE = {protocol.value: protocol for protocol in ProtocolKind}


def parse_supported_protocols(raw: str | None) -> list[ProtocolKind]:
    try:
        values = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(values, list):
        return []

    protocols: list[ProtocolKind] = []
    for value in values:
        protocol = _PROTOCOL_KIND_BY_VALUE.get(str(value))
        if protocol is None:
            continue
        if protocol not in protocols:
            protocols.append(protocol)
    return protocols


def deduplicate_protocols(protocols: list[ProtocolKind]) -> list[ProtocolKind]:
    return list(dict.fromkeys(protocols))


def dump_protocols(protocols: list[ProtocolKind]) -> str:
    return json.dumps(
        [protocol.value for protocol in dict.fromkeys(protocols)],
        ensure_ascii=True,
    )
