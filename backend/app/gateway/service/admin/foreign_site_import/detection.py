from __future__ import annotations

import csv
import io
import json
from typing import Any, Literal

ForeignFormat = Literal["lens", "metapi", "sub2api", "ccload", "all_api_hub", "octopus"]

_SUB2API_TYPES = {"sub2api-data", "sub2api-bundle"}


class UnknownForeignFormatError(ValueError):
    """Raised when a dropped file matches none of the supported backup formats."""


def detect_foreign_format(raw: bytes) -> tuple[ForeignFormat, dict[str, Any] | str]:
    """Classify a backup file and return its format id with the decoded content."""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UnknownForeignFormatError("Backup file is not UTF-8 text") from exc

    payload = _decode_json_object(text)
    if isinstance(payload, dict):
        payload = _unwrap_response_envelope(payload)
        if _is_lens_backup(payload):
            return "lens", payload
        if _is_metapi_backup(payload):
            return "metapi", payload
        if _is_sub2api_backup(payload):
            return "sub2api", payload
        if _is_all_api_hub_backup(payload):
            return "all_api_hub", payload
        if _is_octopus_backup(payload):
            return "octopus", payload
    if _is_ccload_csv(text):
        return "ccload", text
    raise UnknownForeignFormatError("Unrecognized backup file format")


def _decode_json_object(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _unwrap_response_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    """Unwrap a re-saved `{code, message, data}` API response."""
    data = payload.get("data")
    if isinstance(data, dict) and set(payload) <= {"code", "message", "data"}:
        return data
    return payload


def _is_lens_backup(payload: dict[str, Any]) -> bool:
    return isinstance(payload.get("lens_version"), str) and isinstance(
        payload.get("sites"), list
    )


def _is_metapi_backup(payload: dict[str, Any]) -> bool:
    accounts = payload.get("accounts")
    return isinstance(accounts, dict) and isinstance(accounts.get("sites"), list)


def _is_sub2api_backup(payload: dict[str, Any]) -> bool:
    if payload.get("type") in _SUB2API_TYPES:
        return True
    return "exported_at" in payload and isinstance(payload.get("accounts"), list)


def _is_all_api_hub_backup(payload: dict[str, Any]) -> bool:
    if not isinstance(payload.get("version"), str):
        return False
    return "timestamp" in payload and (
        "accounts" in payload or "apiCredentialProfiles" in payload
    )


def _is_octopus_backup(payload: dict[str, Any]) -> bool:
    if not isinstance(payload.get("version"), int):
        return False
    return "exported_at" in payload and ("channels" in payload or "groups" in payload)


def _is_ccload_csv(text: str) -> bool:
    first_line = text.splitlines()[:1]
    if not first_line:
        return False
    try:
        headers = next(csv.reader(io.StringIO(first_line[0])))
    except (csv.Error, StopIteration):
        return False
    normalized = {header.strip().lower() for header in headers}
    return {"name", "urls", "models"} <= normalized
