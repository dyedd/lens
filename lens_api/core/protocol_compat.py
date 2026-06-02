"""协议可达性判断 —— 中立层。

persistence、gateway 等多层都需要判断「某渠道原生协议能否服务某请求协议」。
把这份能力放在 core 这一中立位置，避免 persistence 反向依赖 gateway。
具体的请求/响应转换实现仍在 gateway/converters，但「能否转换」的事实表在此。
"""

from __future__ import annotations

from ..models import ProtocolKind

# 支持的协议转换对：(渠道原生协议, 可服务的请求协议)
SUPPORTED_CONVERSIONS: frozenset[tuple[str, str]] = frozenset(
    {
        (ProtocolKind.OPENAI_CHAT.value, ProtocolKind.ANTHROPIC.value),
        (ProtocolKind.OPENAI_CHAT.value, ProtocolKind.OPENAI_RESPONSES.value),
    }
)


def can_reach_protocol(
    channel_protocol: ProtocolKind, group_protocol: ProtocolKind
) -> bool:
    """渠道原生协议 channel_protocol 能否服务请求协议 group_protocol（含原生同协议）。"""
    if channel_protocol == group_protocol:
        return True
    return (channel_protocol.value, group_protocol.value) in SUPPORTED_CONVERSIONS


def needs_conversion(
    client_protocol: ProtocolKind, channel_protocol: ProtocolKind
) -> bool:
    """客户端请求协议 client_protocol 命中渠道 channel_protocol 时是否需要转换。"""
    return (channel_protocol.value, client_protocol.value) in SUPPORTED_CONVERSIONS


def conversion_matrix() -> dict[str, list[str]]:
    """导出「渠道原生协议 → 可服务的请求协议列表」映射，供前端等外部消费。

    含原生自身（每个协议至少能服务自己），保证前端无需另行硬编码自反规则。
    """
    matrix: dict[str, list[str]] = {p.value: [p.value] for p in ProtocolKind}
    for channel_value, reachable_value in SUPPORTED_CONVERSIONS:
        targets = matrix.setdefault(channel_value, [channel_value])
        if reachable_value not in targets:
            targets.append(reachable_value)
    return matrix
