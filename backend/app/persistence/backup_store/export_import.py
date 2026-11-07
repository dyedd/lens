from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from app.core.model_group_matching import combine_model_group_patterns
from app.models.backups import ConfigBackupDump

# Group fields older backups still carry but current groups no longer use.
_LEGACY_GROUP_KEYS = ("match_models", "source_tags", "new_member_position", "origin")
# Retired site and site-model fields still present in older backups.
_LEGACY_SITE_KEYS = (
    "model_sync_enabled",
    "model_name_prefixes",
    "model_sync_include_rule_ids",
)
_LEGACY_SITE_MODEL_KEYS = (
    "source",
    "upstream_missing",
    "upstream_missing_since",
)


def _migrate_legacy_group_fields(data: object) -> object:
    """将旧备份中的规则引用转为规则内容，并移除废弃字段。"""
    if not isinstance(data, dict):
        return data
    legacy_rules = data.get("regex_rules", [])
    if not isinstance(legacy_rules, list):
        legacy_rules = []
    rules_by_id = {
        str(rule.get("id")): str(rule.get("pattern") or "")
        for rule in legacy_rules
        if isinstance(rule, dict) and rule.get("id")
    }
    data.pop("regex_rules", None)
    groups = data.get("groups")
    if not isinstance(groups, list):
        return data
    for group in groups:
        if isinstance(group, dict):
            for key in _LEGACY_GROUP_KEYS:
                group.pop(key, None)
            rule_ids = group.pop("match_rule_ids", [])
            if not isinstance(rule_ids, list) or any(
                not isinstance(rule_id, str) for rule_id in rule_ids
            ):
                raise ValueError("Backup regex rule references must be strings")
            if not group.get("match_regex"):
                patterns = [
                    rules_by_id[rule_id]
                    for rule_id in rule_ids
                    if rule_id in rules_by_id and rules_by_id[rule_id]
                ]
                if patterns:
                    group["match_regex"] = combine_model_group_patterns(patterns)
                    group["match_regex_operator"] = "or"
                elif rule_ids:
                    raise ValueError("Backup references missing regex rules")
    return data


def _migrate_legacy_sites(data: object) -> object:
    """兼容退役字段和 Auto 协议，并保留原有成员与日志引用。"""
    if not isinstance(data, dict):
        return data
    sites = data.get("sites")
    if not isinstance(sites, list):
        return data
    legacy_protocols: dict[str, str] = {}
    for site in sites:
        if not isinstance(site, dict):
            continue
        for key in _LEGACY_SITE_KEYS:
            site.pop(key, None)
        base_urls = site.get("base_urls", [])
        urls_by_id = (
            {
                str(base_url.get("id")): str(base_url.get("url", ""))
                for base_url in base_urls
                if isinstance(base_url, dict)
            }
            if isinstance(base_urls, list)
            else {}
        )
        protocols = site.get("protocols")
        if not isinstance(protocols, list):
            continue
        for protocol in protocols:
            if not isinstance(protocol, dict):
                continue
            declared = protocol.get("protocols", [])
            if not isinstance(declared, list):
                continue
            concrete = [name for name in declared if name != "auto"]
            host = (
                urlparse(urls_by_id.get(str(protocol.get("base_url_id")), "")).hostname
                or ""
            ).lower()
            # 与 c9f2a4b6d8e0 的在线数据迁移使用同一选择规则。
            if "anthropic" in concrete and "gemini" not in concrete:
                target = "anthropic"
            elif "gemini" in concrete and "anthropic" not in concrete:
                target = "gemini"
            elif "anthropic" in host or "claude" in host:
                target = "anthropic"
            elif "gemini" in host or "generativelanguage" in host:
                target = "gemini"
            else:
                target = "openai_chat"
            config_id = str(protocol.get("id", ""))
            legacy_protocols[f"{config_id}_auto"] = target
            if "auto" in declared:
                protocol["protocols"] = concrete or [target]
            models = protocol.get("models")
            if not isinstance(models, list):
                continue
            concrete_models = {
                (str(model.get("credential_id")), str(model.get("model_name")))
                for model in models
                if isinstance(model, dict) and model.get("protocol") == target
            }
            migrated_models = []
            for model in models:
                if isinstance(model, dict):
                    for key in _LEGACY_SITE_MODEL_KEYS:
                        model.pop(key, None)
                    if model.get("protocol") in ("auto", None):
                        identity = (
                            str(model.get("credential_id")),
                            str(model.get("model_name")),
                        )
                        if identity in concrete_models:
                            continue
                        model["protocol"] = target
                        concrete_models.add(identity)
                migrated_models.append(model)
            protocol["models"] = migrated_models

    groups = data.get("groups", [])
    for group in groups if isinstance(groups, list) else []:
        if not isinstance(group, dict):
            continue
        for field in ("items", "excluded_items"):
            members = group.get(field, [])
            if not isinstance(members, list):
                continue
            concrete_members = {
                (
                    str(member.get("channel_id")),
                    str(member.get("credential_id")),
                    str(member.get("model_name")),
                )
                for member in members
                if isinstance(member, dict)
                and str(member.get("channel_id")) not in legacy_protocols
            }
            migrated_members = []
            for member in members:
                if isinstance(member, dict):
                    is_legacy = str(member.get("channel_id")) in legacy_protocols
                    _migrate_legacy_channel_reference(member, legacy_protocols)
                    identity = (
                        str(member.get("channel_id")),
                        str(member.get("credential_id")),
                        str(member.get("model_name")),
                    )
                    if is_legacy and identity in concrete_members:
                        continue
                    concrete_members.add(identity)
                migrated_members.append(member)
            group[field] = migrated_members
    logs = data.get("request_logs", [])
    for log in logs if isinstance(logs, list) else []:
        if not isinstance(log, dict):
            continue
        attempts = log.get("attempts", [])
        references = [log, *attempts] if isinstance(attempts, list) else [log]
        for reference in references:
            if isinstance(reference, dict):
                _migrate_legacy_channel_reference(reference, legacy_protocols)
    stats = data.get("stats", {})
    hourly = stats.get("attribution_hourly", []) if isinstance(stats, dict) else []
    for row in hourly if isinstance(hourly, list) else []:
        if isinstance(row, dict):
            _migrate_legacy_channel_reference(row, legacy_protocols)
    return data


def _migrate_legacy_channel_reference(
    reference: dict[str, Any], legacy_protocols: dict[str, str]
) -> None:
    channel_id = reference.get("channel_id")
    if not isinstance(channel_id, str) or channel_id not in legacy_protocols:
        return
    protocol = legacy_protocols[channel_id]
    reference["channel_id"] = f"{channel_id.removesuffix('_auto')}_{protocol}"
    if reference.get("protocol") == "auto":
        reference["protocol"] = protocol


def parse_dump(payload: bytes) -> ConfigBackupDump:
    """Parse and validate a serialized configuration backup."""
    try:
        data = _migrate_legacy_group_fields(json.loads(payload))
        data = _migrate_legacy_sites(data)
        return ConfigBackupDump.model_validate(data)
    except ValueError as exc:
        raise ValueError("Invalid backup file") from exc
