"""Recognise which provider sealed a piece of opaque reasoning state.

Several providers speak the same wire protocol but seal reasoning with their own
key. A history that passed through one provider therefore holds a blob another
provider cannot read, and replaying it gets the request rejected with an error
that looks like the client's fault. This module names the sealing family so the
caller can drop a blob that does not belong to the target model.
"""

from __future__ import annotations

import base64
import binascii

ANTHROPIC = "anthropic"
OPENAI = "openai"
GEMINI = "gemini"
GROK = "grok"
UNKNOWN = ""

_OPENAI_MARKERS = ("gpt", "codex", "o1", "o3", "o4", "davinci")


def model_family(model: str) -> str:
    """Name the provider family a model name belongs to."""
    name = (model or "").lower()
    if "claude" in name or "anthropic" in name:
        return ANTHROPIC
    if "gemini" in name or "palm" in name:
        return GEMINI
    if "grok" in name:
        return GROK
    if any(marker in name for marker in _OPENAI_MARKERS):
        return OPENAI
    return UNKNOWN


def sealed_by(value: str) -> str:
    """Name the provider family that sealed ``value``, if it is recognisable."""
    value = (value or "").strip()
    lowered = value.lower()
    for prefix, family in (
        ("gpt#", OPENAI),
        ("claude#", ANTHROPIC),
        ("gemini#", GEMINI),
    ):
        if lowered.startswith(prefix):
            return family
    # OpenAI encrypts reasoning with Fernet, whose base64 tokens decode to a
    # structure starting ``gAAAA``.
    if value.startswith("gAAAA"):
        return OPENAI
    decoded = _decode(value)
    if decoded is None:
        return UNKNOWN
    if b"claude" in decoded or b"anthropic" in decoded:
        return ANTHROPIC
    if b"gemini" in decoded:
        return GEMINI
    return UNKNOWN


def fits(value: str, target_model: str) -> bool:
    """Return whether ``value`` may be replayed to a model named ``target_model``.

    An unidentifiable blob is kept: guessing wrong would break requests that
    work today.
    """
    sealed = sealed_by(value)
    target = model_family(target_model)
    return not sealed or not target or sealed == target


def _decode(value: str) -> bytes | None:
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (binascii.Error, ValueError):
        return None
