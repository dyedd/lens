"""Decide whether provider-opaque reasoning state may be replayed upstream.

Lens only replays opaque state when the target protocol matches the protocol
that produced it. That is necessary but not sufficient: several providers speak
the same wire protocol and seal their reasoning with their own key, so a model
group that fails over from one to another would replay the first provider's
blob to the second and collect a 400 that reads like a client error.

The rule implemented here is conservative: reject only when both the blob's
family and the target model's family are identified and they disagree. An
unidentified blob keeps the previous behaviour of being replayed, so nothing
that worked before starts failing for lack of a guess.
"""

from __future__ import annotations

import base64
import binascii

from ...models.protocols import ProtocolKind

FAMILY_ANTHROPIC = "anthropic"
FAMILY_OPENAI = "openai"
FAMILY_GEMINI = "gemini"
FAMILY_GROK = "grok"
FAMILY_UNKNOWN = ""


def model_family(model: str) -> str:
    """Identify the provider family a model name belongs to."""
    name = (model or "").lower()
    if not name:
        return FAMILY_UNKNOWN
    if "claude" in name or "anthropic" in name:
        return FAMILY_ANTHROPIC
    if "gemini" in name or "palm" in name:
        return FAMILY_GEMINI
    if "grok" in name:
        return FAMILY_GROK
    for marker in ("gpt", "codex", "o1", "o3", "o4", "davinci"):
        if marker in name:
            return FAMILY_OPENAI
    return FAMILY_UNKNOWN


def signature_family(opaque: str) -> str:
    """Identify the provider family that sealed ``opaque``, if recognisable."""
    value = (opaque or "").strip()
    if not value:
        return FAMILY_UNKNOWN
    lowered = value.lower()
    if lowered.startswith("gpt#"):
        return FAMILY_OPENAI
    if lowered.startswith("claude#"):
        return FAMILY_ANTHROPIC
    if lowered.startswith("gemini#"):
        return FAMILY_GEMINI
    # OpenAI encrypts reasoning with Fernet, whose base64 tokens start with the
    # version byte and therefore decode to a structure beginning ``gAAAA``.
    if value.startswith("gAAAA"):
        return FAMILY_OPENAI
    decoded = _try_base64(value)
    if decoded is None:
        return FAMILY_UNKNOWN
    if b"claude" in decoded or b"anthropic" in decoded:
        return FAMILY_ANTHROPIC
    if b"gemini" in decoded:
        return FAMILY_GEMINI
    return FAMILY_UNKNOWN


def _try_base64(value: str) -> bytes | None:
    padded = value + "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(padded)
    except (binascii.Error, ValueError):
        return None


def can_replay(
    *,
    origin: ProtocolKind,
    target: ProtocolKind,
    opaque: str,
    target_model: str,
) -> bool:
    """Return whether ``opaque`` may be sent to an upstream serving ``target``."""
    if not opaque:
        return False
    if origin is not target:
        return False
    sealed = signature_family(opaque)
    if not sealed:
        return True
    target_family = model_family(target_model)
    if not target_family:
        return True
    return sealed == target_family
