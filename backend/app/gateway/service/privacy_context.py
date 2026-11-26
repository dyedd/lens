"""Request-owned privacy mappings and bounded authenticated history references."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field
from time import monotonic
from typing import Any, cast

from app.core.privacy_rules import (
    MAX_PRIVACY_MATCHES,
    PLACEHOLDER_PATTERN,
    PrivacyDetector,
    PrivacyError,
)
from app.models.privacy import PrivacyCategory, PrivacyConfig, PrivacyHit
from app.models.protocols import ProtocolKind

from .privacy_content import (
    SIGNATURE_FIELDS,
    signed_nodes,
    transform_business,
    transform_content,
)

HISTORY_MAX_ENTRIES = 256
HISTORY_MAX_BYTES = 16_000_000
HISTORY_TTL_SECONDS = 3600
REQUEST_MAPPING_MAX_BYTES = 2_000_000
PLACEHOLDER_CANDIDATE = re.compile(r"\[\[LENS_[A-Z_0-9a-f]*\]*")


@dataclass(slots=True)
class PrivacyHistoryEntry:
    scope: str
    mapping: dict[str, str]
    sealed: dict[str, tuple[dict[str, Any], dict[str, Any]]]
    created_at: float = field(default_factory=monotonic)
    size: int = 0


class PrivacyHistory:
    def __init__(self) -> None:
        self.entries: OrderedDict[tuple[str, str, str], PrivacyHistoryEntry] = (
            OrderedDict()
        )
        self.size = 0

    def get(
        self, gateway_key_id: str, kind: str, reference: str
    ) -> PrivacyHistoryEntry | None:
        identity = (gateway_key_id, kind, reference)
        entry = self.entries.get(identity)
        if entry is not None and monotonic() - entry.created_at >= HISTORY_TTL_SECONDS:
            self.size -= self.entries.pop(identity).size
            return None
        if entry is not None:
            self.entries.move_to_end(identity)
        return entry

    def put(
        self, gateway_key_id: str, kind: str, reference: str, context: PrivacyContext
    ) -> None:
        identity = (gateway_key_id, kind, reference)
        entry = PrivacyHistoryEntry(
            context.scope, dict(context.mapping), deepcopy(context.sealed)
        )
        previous = self.get(gateway_key_id, kind, reference)
        if kind == "session" and previous is not None and previous.scope == entry.scope:
            entry.mapping = {**previous.mapping, **entry.mapping}
            entry.sealed = {**deepcopy(previous.sealed), **entry.sealed}
            if (
                len(entry.mapping) > MAX_PRIVACY_MATCHES
                or sum(len(value.encode()) for value in entry.mapping.values())
                > REQUEST_MAPPING_MAX_BYTES
            ):
                raise PrivacyError("Privacy session mapping limit exceeded")
        entry.size = len(
            json.dumps([identity, entry.mapping, entry.sealed], ensure_ascii=True)
        )
        if entry.size > HISTORY_MAX_BYTES:
            raise PrivacyError("Privacy history limit exceeded")
        previous = self.entries.pop(identity, None)
        self.size -= previous.size if previous is not None else 0
        self.entries[identity] = entry
        self.size += entry.size
        while len(self.entries) > HISTORY_MAX_ENTRIES or self.size > HISTORY_MAX_BYTES:
            _, removed = self.entries.popitem(last=False)
            self.size -= removed.size


class PrivacyContext:
    def __init__(
        self,
        config: PrivacyConfig,
        secret_key: str,
        *,
        gateway_key_id: str = "preview",
        history: PrivacyHistory | None = None,
        session_id: str | None = None,
    ) -> None:
        self.config = config.model_copy(deep=True)
        self.detector = PrivacyDetector(self.config)
        self.secret_key = secret_key.encode()
        self.gateway_key_id = gateway_key_id
        self.history = history
        self.session_id = session_id
        self.scope = session_id or secrets.token_hex(16)
        self.mapping: dict[str, str] = {}
        self.sealed: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
        self.hits: dict[PrivacyCategory, set[str]] = {}
        self.mapping_bytes = 0
        if config.enabled and history is not None and session_id:
            entry = history.get(gateway_key_id, "session", session_id)
            if entry is not None:
                self._load(entry)

    def _load(self, entry: PrivacyHistoryEntry) -> None:
        self.mapping.update(entry.mapping)
        self.sealed.update(deepcopy(entry.sealed))
        self.scope = entry.scope
        self.mapping_bytes = sum(len(value.encode()) for value in self.mapping.values())
        if (
            self.mapping_bytes > REQUEST_MAPPING_MAX_BYTES
            or len(self.mapping) > MAX_PRIVACY_MATCHES
            or len(self.sealed) > MAX_PRIVACY_MATCHES
            or len(json.dumps(self.sealed, ensure_ascii=True)) > HISTORY_MAX_BYTES
        ):
            raise PrivacyError("Privacy mapping limit exceeded")

    def load_references(self, body: dict[str, Any]) -> None:
        if not self.config.enabled:
            return
        if self.session_id and len(self.session_id) > 256:
            raise PrivacyError("Privacy session reference is too long")
        references: list[tuple[str, str]] = []
        previous = body.get("previous_response_id")
        if isinstance(previous, str) and previous:
            references.append(("response", previous))
        for node in signed_nodes(body):
            references.extend(
                ("signature", node[name])
                for name in SIGNATURE_FIELDS
                if isinstance(node.get(name), str) and node[name]
            )
        for kind, reference in references:
            entry = (
                self.history.get(self.gateway_key_id, kind, reference)
                if self.history is not None
                else None
            )
            if entry is None:
                raise PrivacyError(
                    "Privacy history is unavailable; resend complete unsigned history"
                )
            if self.session_id and entry.scope != self.scope:
                raise PrivacyError("Privacy history belongs to another session")
            self._load(entry)

    def summary(self) -> list[PrivacyHit]:
        return [
            PrivacyHit(
                category=category,
                action=self.config.action,
                count=len(tokens),
                placeholders=sorted(tokens),
            )
            for category, tokens in sorted(self.hits.items())
        ]

    def mask_text(
        self, text: str, field_name: str = "", *, log_only: bool = False
    ) -> str:
        if not self.config.enabled:
            return text
        try:
            spans = self.detector.spans(
                text,
                field_name=field_name,
                known_values=(
                    (original, cast(PrivacyCategory, token.split("_")[1].lower()))
                    for token, original in self.mapping.items()
                ),
            )
        except PrivacyError:
            raise
        except Exception as exc:
            raise PrivacyError("Privacy detection failed") from exc
        pieces: list[str] = []
        offset = 0
        for span in spans:
            original = text[span.start : span.end]
            digest = hmac.new(
                self.secret_key,
                json.dumps(
                    [
                        "lens/privacy/v1",
                        self.gateway_key_id,
                        self.scope,
                        span.category,
                        original,
                    ],
                    ensure_ascii=True,
                ).encode(),
                hashlib.sha256,
            ).hexdigest()[:32]
            placeholder = f"[[LENS_{span.category.upper()}_{digest}]]"
            if not log_only:
                if placeholder not in self.mapping:
                    self.mapping_bytes += len(original.encode())
                    if (
                        len(self.mapping) >= MAX_PRIVACY_MATCHES
                        or self.mapping_bytes > REQUEST_MAPPING_MAX_BYTES
                    ):
                        raise PrivacyError("Privacy mapping limit exceeded")
                    self.mapping[placeholder] = original
                self.hits.setdefault(span.category, set()).add(placeholder)
            pieces.extend((text[offset : span.start], placeholder))
            offset = span.end
        pieces.append(text[offset:])
        if not log_only and spans and self.config.action == "block":
            raise PrivacyError("Request blocked by privacy rules")
        return (
            text if not log_only and self.config.action == "warn" else "".join(pieces)
        )

    def prepare(self, body: dict[str, Any], protocol: ProtocolKind) -> dict[str, Any]:
        if not self.config.enabled:
            return body

        def replay(node: dict[str, Any]) -> dict[str, Any]:
            for name in SIGNATURE_FIELDS:
                signature = node.get(name)
                if not isinstance(signature, str) or not signature:
                    continue
                stored = self.sealed.get(signature)
                if stored is None or node not in stored:
                    raise PrivacyError(
                        "Privacy signed content does not match its history"
                    )
                checked = transform_content(stored[0], protocol, self.mask_text)
                if checked != stored[0]:
                    raise PrivacyError(
                        "Privacy rules require changes to signed content; resend unsigned history"
                    )
                return deepcopy(stored[0])
            return node

        return transform_content(body, protocol, self.mask_text, replay)

    def validate_restoration(self, text: str) -> None:
        for match in PLACEHOLDER_CANDIDATE.finditer(text):
            candidate = match.group()
            if PLACEHOLDER_PATTERN.fullmatch(candidate):
                continue
            if any(
                placeholder.startswith(candidate.rstrip("]"))
                for placeholder in self.mapping
            ):
                raise PrivacyError(
                    "Incomplete privacy placeholder in upstream response"
                )

    def restore_text(self, text: str, field_name: str = "") -> str:
        if not self.mapping:
            return text
        self.validate_restoration(text)
        pattern = "|".join(re.escape(token) for token in self.mapping)
        return re.sub(pattern, lambda match: self.mapping[match.group()], text)

    def restore(self, body: Any, protocol: ProtocolKind) -> Any:
        if not self.config.enabled:
            return body

        def remember(node: dict[str, Any]) -> dict[str, Any]:
            restored = transform_content(node, protocol, self.restore_text)
            for name in SIGNATURE_FIELDS:
                signature = node.get(name)
                if isinstance(signature, str) and signature:
                    self.sealed[signature] = (deepcopy(node), deepcopy(restored))
                    if (
                        len(self.sealed) > MAX_PRIVACY_MATCHES
                        or len(json.dumps(self.sealed, ensure_ascii=True))
                        > HISTORY_MAX_BYTES
                    ):
                        raise PrivacyError("Privacy signed history limit exceeded")
                    if self.history is not None:
                        self.history.put(
                            self.gateway_key_id, "signature", signature, self
                        )
            return restored

        restored = transform_content(body, protocol, self.restore_text, remember)
        if self.history is not None:
            response_id = body.get("id") if isinstance(body, dict) else None
            if (
                protocol == ProtocolKind.OPENAI_RESPONSES
                and isinstance(body, dict)
                and isinstance(body.get("output"), list)
                and isinstance(response_id, str)
                and response_id
            ):
                self.history.put(self.gateway_key_id, "response", response_id, self)
            self.remember_session()
        return restored

    def remember_session(self) -> None:
        if self.config.enabled and self.history is not None and self.session_id:
            self.history.put(self.gateway_key_id, "session", self.session_id, self)

    def clean_log(
        self, text: str | None, *, collect_values: bool = False
    ) -> str | None:
        if text is None or not self.config.enabled:
            return text
        replacements = {
            original: placeholder
            for placeholder, original in sorted(
                self.mapping.items(), key=lambda pair: -len(pair[1])
            )
        }
        pattern = (
            re.compile(
                PLACEHOLDER_PATTERN.pattern
                + "|"
                + "|".join(re.escape(original) for original in replacements)
            )
            if replacements
            else None
        )

        def clean(value: str, field_name: str) -> str:
            if pattern is not None:
                value = pattern.sub(
                    lambda match: replacements.get(match.group(), match.group()), value
                )
            return self.mask_text(value, field_name, log_only=not collect_values)

        try:
            try:
                parsed = json.loads(text)
            except ValueError:
                return clean(text, "")
            return json.dumps(transform_business(parsed, clean), ensure_ascii=True)
        except (PrivacyError, RecursionError):
            return "[privacy content unavailable]"
