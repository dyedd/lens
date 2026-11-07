"""Regex rule ids referenced by sites and model groups, stored as JSON lists."""

from __future__ import annotations

import json

from .json_columns import STRING_LIST, load_json_column


def dump_rule_ids(rule_ids: list[str]) -> str:
    return json.dumps(rule_ids, ensure_ascii=True)


def parse_rule_ids(raw: str) -> list[str]:
    return load_json_column(raw, STRING_LIST, "rule_ids_json")
