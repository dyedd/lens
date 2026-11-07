from __future__ import annotations

import logging

from pydantic import TypeAdapter, ValidationError

from ..core.errors import StoredDataError

STRING_LIST = TypeAdapter(list[str])


def load_json_column[T](raw: str, schema: TypeAdapter[T], column: str) -> T:
    try:
        return schema.validate_json(raw)
    except ValidationError as exc:
        # 列内容可能含密钥，只记录列名；原因链留给内部诊断。
        logging.getLogger(__name__).error("Invalid stored JSON in %s", column)
        raise StoredDataError() from exc


def load_allowed_models(raw: str | None) -> list[str]:
    models = load_json_column(raw or "[]", STRING_LIST, "allowed_models_json")
    return list(dict.fromkeys(model.strip() for model in models if model.strip()))


def load_base_url_ids(raw: str | None) -> list[str] | None:
    return (
        load_json_column(raw, STRING_LIST, "base_url_ids_json")
        if raw is not None
        else None
    )
