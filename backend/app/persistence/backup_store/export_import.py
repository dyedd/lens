from __future__ import annotations

import json

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


def _drop_legacy_group_fields(data: object) -> object:
    """Strip retired per-group rule fields so older backups still import."""
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
            if not group.get("match_regex") and isinstance(rule_ids, list):
                patterns = [
                    rules_by_id[rule_id]
                    for rule_id in rule_ids
                    if rule_id in rules_by_id and rules_by_id[rule_id]
                ]
                if patterns:
                    group["match_regex"] = (
                        patterns[0]
                        if len(patterns) == 1
                        else "(?:" + ")|(?:".join(patterns) + ")"
                    )
                    group["match_regex_operator"] = "or"
                elif rule_ids:
                    raise ValueError("Backup references missing regex rules")
    return data


def _drop_legacy_site_fields(data: object) -> object:
    """Strip retired site and site-model fields so older backups still import."""
    if not isinstance(data, dict):
        return data
    sites = data.get("sites")
    if not isinstance(sites, list):
        return data
    for site in sites:
        if not isinstance(site, dict):
            continue
        for key in _LEGACY_SITE_KEYS:
            site.pop(key, None)
        protocols = site.get("protocols")
        if not isinstance(protocols, list):
            continue
        for protocol in protocols:
            models = protocol.get("models") if isinstance(protocol, dict) else None
            if not isinstance(models, list):
                continue
            for model in models:
                if isinstance(model, dict):
                    for key in _LEGACY_SITE_MODEL_KEYS:
                        model.pop(key, None)
    return data


def parse_dump(payload: bytes) -> ConfigBackupDump:
    """Parse and validate a serialized configuration backup."""
    try:
        data = _drop_legacy_group_fields(json.loads(payload))
        data = _drop_legacy_site_fields(data)
        return ConfigBackupDump.model_validate(data)
    except ValueError as exc:
        raise ValueError("Invalid backup file") from exc
