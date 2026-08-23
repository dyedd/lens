from enum import Enum


class ProtocolKind(str, Enum):
    OPENAI_CHAT = "openai_chat"
    OPENAI_RESPONSES = "openai_responses"
    OPENAI_EMBEDDING = "openai_embedding"
    OPENAI_IMAGE = "openai_image"
    RERANK = "rerank"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class ChannelProxyMode(str, Enum):
    INHERIT = "inherit"
    DIRECT = "direct"
    CUSTOM = "custom"


class RequestLogStatusFilter(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RequestLogLifecycleStatus(str, Enum):
    CONNECTING = "connecting"
    STREAMING = "streaming"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RequestLogSortMode(str, Enum):
    LATEST = "latest"
    COST = "cost"
    LATENCY = "latency"
    TOKENS = "tokens"


class ChannelStatus(str, Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class ModelSource(str, Enum):
    MANUAL = "manual"
    SYNCED = "synced"


class ChannelModelSyncStatus(str, Enum):
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    FAILED = "failed"


class RoutingStrategy(str, Enum):
    ROUND_ROBIN = "round_robin"
    FAILOVER = "failover"


class ModelGroupSyncFilterMode(str, Enum):
    NONE = ""
    CONTAINS = "contains"
    REGEX = "regex"


class UpstreamHeaderRuleMatchType(str, Enum):
    EXACT = "exact"
    REGEX = "regex"


class CronjobStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DISABLED = "disabled"


class CronjobScheduleType(str, Enum):
    INTERVAL = "interval"
    DAILY = "daily"
    WEEKLY = "weekly"
