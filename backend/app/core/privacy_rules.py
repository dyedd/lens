"""Bounded local detectors for credentials and personal identifiers."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from itertools import chain
from time import monotonic

import regex

from app.models.privacy import REGEX_TIMEOUT_SECONDS, PrivacyCategory, PrivacyConfig

MAX_PRIVACY_TEXT_LENGTH = 2_000_000
MAX_PRIVACY_MATCHES = 4096
DETECTION_BUDGET_SECONDS = 0.5
PLACEHOLDER_PATTERN = regex.compile(r"\[\[LENS_[A-Z]+_[0-9a-f]{32}\]\]")
SECRET_FIELD_PATTERN = regex.compile(
    r"(?i)^(?:api[_-]?key|access[_-]?(?:key|token)|client[_-]?secret|"
    r"password|passwd|pwd|secret|token|auth(?:orization)?|private[_-]?key|"
    r"密码|口令|密钥|令牌)$"
)

_SECRET_PATTERNS = (
    r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----[\s\S]+?-----END (?:[A-Z]+ )?PRIVATE KEY-----",
    r"\b(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{16,}|AIza[A-Za-z0-9_-]{30,}|"
    r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"xox[baprs]-[A-Za-z0-9-]{16,}|AKIA[A-Z0-9]{16})\b",
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b",
    r"\b[a-zA-Z][a-zA-Z0-9+.-]*://[^\s/:@]+:[^\s/@]+@[^\s]+",
    r"""(?ix)(?:["']?\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password|passwd|pwd|secret|token)\b["']?|["']?(?:密码|口令|密钥|令牌)["']?)\s*[:=：]\s*(?:"(?P<quoted>(?:\\.|[^"\\\r\n])+)"|'(?P<single>(?:\\.|[^'\\\r\n])+)'|(?P<plain>[^\s,;，；}\]]{4,}))""",
)
_PERSONAL_PATTERNS = (
    ("email", r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"),
    (
        "phone",
        r"(?<!\d)(?:\+?86[ -]?)?1[3-9]\d{9}(?!\d)|(?<!\w)\+[1-9]\d{0,2}[ -]?(?:\d[ -]?){7,12}\d(?!\d)",
    ),
    ("identity", r"(?<!\d)[1-9]\d{16}[\dXx](?!\d)"),
    ("card", r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)"),
)


class PrivacyError(ValueError):
    """A privacy failure with a safe message suitable for client responses."""


@dataclass(frozen=True, slots=True)
class PrivacySpan:
    start: int
    end: int
    category: PrivacyCategory


def _valid_personal(kind: str, value: str) -> bool:
    digits = "".join(character for character in value if character.isdigit())
    if kind == "identity":
        try:
            date(int(value[6:10]), int(value[10:12]), int(value[12:14]))
        except ValueError:
            return False
        weights = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
        return (
            "10X98765432"[
                sum(int(n) * w for n, w in zip(value[:17], weights, strict=True)) % 11
            ]
            == value[-1].upper()
        )
    if kind == "card":
        if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
            return False
        total = 0
        for index, character in enumerate(reversed(digits)):
            number = int(character) * (2 if index % 2 else 1)
            total += number - 9 if number > 9 else number
        return total % 10 == 0
    return True


class PrivacyDetector:
    def __init__(self, config: PrivacyConfig) -> None:
        self.config = config
        self.patterns: list[tuple[PrivacyCategory, str, regex.Pattern]] = []
        if "secrets" in config.categories:
            self.patterns.extend(
                ("secrets", "secret", regex.compile(pattern, regex.VERSION1))
                for pattern in _SECRET_PATTERNS
            )
        if "personal" in config.categories:
            self.patterns.extend(
                ("personal", kind, regex.compile(pattern, regex.VERSION1))
                for kind, pattern in _PERSONAL_PATTERNS
            )
        self.patterns.extend(
            ("custom", "custom", regex.compile(rule.pattern, regex.VERSION1))
            for rule in config.regex_rules
        )

    def spans(
        self,
        text: str,
        *,
        field_name: str = "",
        known_values: Iterable[tuple[str, PrivacyCategory]] = (),
    ) -> list[PrivacySpan]:
        if len(text) > MAX_PRIVACY_TEXT_LENGTH:
            raise PrivacyError("Privacy text limit exceeded")
        started_at = monotonic()
        spans: list[PrivacySpan] = []
        protected = [match.span() for match in PLACEHOLDER_PATTERN.finditer(text)]
        if len(protected) > MAX_PRIVACY_MATCHES:
            raise PrivacyError("Privacy match limit exceeded")
        for exception in self.config.exceptions:
            offset = 0
            while (position := text.find(exception, offset)) >= 0:
                protected.append((position, position + len(exception)))
                offset = position + len(exception)
                if len(protected) > MAX_PRIVACY_MATCHES:
                    raise PrivacyError("Privacy match limit exceeded")
        if (
            "secrets" in self.config.categories
            and text
            and SECRET_FIELD_PATTERN.fullmatch(field_name)
        ):
            spans.append(PrivacySpan(0, len(text), "secrets"))
        try:
            for category, kind, pattern in self.patterns:
                for match in pattern.finditer(text, timeout=REGEX_TIMEOUT_SECONDS):
                    start, end = match.span()
                    if start == end:
                        raise PrivacyError("Privacy pattern matched empty text")
                    if kind == "secret" and match.groupdict():
                        for group in ("quoted", "single", "plain"):
                            if match.groupdict().get(group) is not None:
                                start, end = match.span(group)
                                break
                    if category != "personal" or _valid_personal(kind, text[start:end]):
                        spans.append(PrivacySpan(start, end, category))
                    if len(spans) > MAX_PRIVACY_MATCHES:
                        raise PrivacyError("Privacy match limit exceeded")
                if monotonic() - started_at > DETECTION_BUDGET_SECONDS:
                    raise PrivacyError("Privacy detection time limit exceeded")
            for word, category in chain(
                ((word, "custom") for word in self.config.words), known_values
            ):
                offset = 0
                while (position := text.find(word, offset)) >= 0:
                    spans.append(PrivacySpan(position, position + len(word), category))
                    offset = position + len(word)
                    if len(spans) > MAX_PRIVACY_MATCHES:
                        raise PrivacyError("Privacy match limit exceeded")
                if monotonic() - started_at > DETECTION_BUDGET_SECONDS:
                    raise PrivacyError("Privacy detection time limit exceeded")
        except (TimeoutError, regex.error) as exc:
            raise PrivacyError("Privacy detection failed") from exc
        accepted: list[PrivacySpan] = []
        for span in sorted(
            spans, key=lambda span: (span.start, -(span.end - span.start))
        ):
            if any(start <= span.start and span.end <= end for start, end in protected):
                continue
            if accepted and span.start < accepted[-1].end:
                continue
            accepted.append(span)
        return accepted
