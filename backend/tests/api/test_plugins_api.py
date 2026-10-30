from __future__ import annotations

from typing import Any

from conftest import assert_error
from fastapi.testclient import TestClient

BASE_PLUGIN = """
from app.plugins.contract import (
    EXT_REQUEST_OBSERVER,
    PluginContext,
    PluginDefinition,
    PluginManifest,
    RequestRecord,
)


class Observer:
    def extension(self) -> str:
        return EXT_REQUEST_OBSERVER

    async def completed(self, record: RequestRecord) -> None:
        return None


def register(context: PluginContext) -> None:
    context.add_request_observer(Observer())


PLUGIN = PluginDefinition(
    manifest=PluginManifest(id="base_plugin", name="Base"),
    register=register,
)
"""

DEPENDENT_PLUGIN = """
from app.plugins.contract import (
    EXT_UPSTREAM_RESPONSE,
    PluginContext,
    PluginDefinition,
    PluginManifest,
)


class Stamp:
    def extension(self) -> str:
        return EXT_UPSTREAM_RESPONSE

    def matches(self, response) -> bool:
        return False

    async def apply(self, response, ctx):
        return None


def register(context: PluginContext) -> None:
    context.add_response_hook(Stamp())


PLUGIN = PluginDefinition(
    manifest=PluginManifest(
        id="dependent_plugin", name="Dependent", requires=("base_plugin",)
    ),
    register=register,
)
"""

SETTINGS_PLUGIN = """
from app.plugins.contract import PluginDefinition, PluginManifest, PluginSetting

PLUGIN = PluginDefinition(
    manifest=PluginManifest(
        id="settings_plugin",
        name="Settings",
        settings=(
            PluginSetting(
                key="ratio",
                label="Ratio",
                type="float",
                default=0.5,
                min_value=0.0,
                max_value=1.0,
            ),
            PluginSetting(key="token", label="Token", secret=True),
        ),
    ),
    register=lambda context: None,
)
"""

TOOLBOX_PLUGIN = """
from app.persistence.cronjob_store import CronjobSpec
from app.plugins.contract import (
    EXT_ROUTE_STRATEGY,
    EXT_UPSTREAM_CREDENTIAL,
    PluginContext,
    PluginDefinition,
    PluginManifest,
)


class Credential:
    def extension(self) -> str:
        return EXT_UPSTREAM_CREDENTIAL

    def matches(self, call) -> bool:
        return False

    async def apply(self, call, ctx):
        return None


class Reversed:
    def __init__(self, name: str) -> None:
        self.name = name

    def extension(self) -> str:
        return EXT_ROUTE_STRATEGY

    def order(self, pool, seats):
        return list(reversed(range(len(seats))))


async def tick() -> None:
    return None


def register(context: PluginContext) -> None:
    context.add_upstream_hook(Credential())
    context.add_route_strategy(Reversed("reversed"))
    # 名称不合法或 `toolbox/<name>` 超过模型组 strategy 列长度的策略会被忽略。
    context.add_route_strategy(Reversed("bad name"))
    context.add_route_strategy(Reversed("name_longer_than_the_strategy_column"))
    context.add_cronjob(
        CronjobSpec(
            id="toolbox_tick",
            name="Toolbox tick",
            description="",
            default_interval_hours=24,
        ),
        tick,
    )
    # 与平台计划任务同 id 的任务被跳过，不顶替平台的处理函数。
    context.add_cronjob(
        CronjobSpec(
            id="version_check",
            name="Not the platform job",
            description="",
            default_interval_hours=24,
        ),
        tick,
    )


PLUGIN = PluginDefinition(
    manifest=PluginManifest(id="toolbox", name="Toolbox"),
    register=register,
)
"""


def _list_plugins(
    client: TestClient, admin_headers: dict[str, str]
) -> dict[str, dict[str, Any]]:
    response = client.get("/api/admin/plugins", headers=admin_headers)
    assert response.status_code == 200, response.text
    return {item["id"]: item for item in response.json()}


def _cronjob_names(client: TestClient, admin_headers: dict[str, str]) -> dict[str, str]:
    response = client.get("/api/admin/cronjobs", headers=admin_headers)
    assert response.status_code == 200, response.text
    return {item["id"]: item["name"] for item in response.json()}


def _settings_by_key(plugin: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["key"]: item for item in plugin["settings"]}


def test_plugin_dependency_round_trip(
    client: TestClient, admin_headers: dict[str, str], install_plugin: Any
) -> None:
    base = install_plugin(BASE_PLUGIN, "base_plugin")
    assert base["extensions"] == ["request_observer"]
    dependent = install_plugin(DEPENDENT_PLUGIN, "dependent_plugin")
    assert dependent["state"] == "active"
    assert dependent["extensions"] == ["upstream_response"]

    disabled = client.put(
        "/api/admin/plugins/base_plugin",
        headers=admin_headers,
        json={"enabled": False},
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["state"] == "disabled"
    pending = _list_plugins(client, admin_headers)["dependent_plugin"]
    assert pending["state"] == "pending"
    assert pending["extensions"] == []

    enabled = client.put(
        "/api/admin/plugins/base_plugin",
        headers=admin_headers,
        json={"enabled": True},
    )
    assert enabled.status_code == 200, enabled.text
    restored = _list_plugins(client, admin_headers)["dependent_plugin"]
    assert restored["state"] == "active"
    assert restored["extensions"] == ["upstream_response"]


def test_plugin_settings_round_trip(
    client: TestClient, admin_headers: dict[str, str], install_plugin: Any
) -> None:
    install_plugin(SETTINGS_PLUGIN, "settings_plugin")
    url = "/api/admin/plugins/settings_plugin/settings"

    saved = client.put(
        url,
        headers=admin_headers,
        json={"values": {"ratio": "0.25", "token": "s3cret"}},
    )
    assert saved.status_code == 200, saved.text
    assert "s3cret" not in saved.text
    settings = _settings_by_key(saved.json())
    assert settings["ratio"]["value"] == 0.25
    assert settings["token"]["value"] == ""
    assert settings["token"]["is_set"] is True

    out_of_range = client.put(
        url, headers=admin_headers, json={"values": {"ratio": 1.5}}
    )
    assert_error(out_of_range, 400)

    # null 恢复默认值；密钥传 "" 保持原值。
    kept = client.put(
        url, headers=admin_headers, json={"values": {"ratio": None, "token": ""}}
    )
    assert kept.status_code == 200, kept.text
    settings = _settings_by_key(kept.json())
    assert settings["ratio"]["value"] == 0.5
    assert settings["token"]["is_set"] is True

    cleared = client.put(url, headers=admin_headers, json={"values": {"token": None}})
    assert cleared.status_code == 200, cleared.text
    assert _settings_by_key(cleared.json())["token"]["is_set"] is False


def test_plugin_reload_lists_contributions(
    client: TestClient, admin_headers: dict[str, str], install_plugin: Any
) -> None:
    toolbox = install_plugin(TOOLBOX_PLUGIN, "toolbox")
    assert toolbox["state"] == "active"
    assert toolbox["source"] == "external"
    assert toolbox["extensions"] == ["route_strategy", "upstream_credential"]
    assert toolbox["strategies"] == ["toolbox/reversed"]
    strategy_stats = {item["extension"]: item for item in toolbox["stats"]}[
        "route_strategy"
    ]
    assert strategy_stats["last_outcome"] == "invalid"
    assert strategy_stats["failures"] == 2
    assert (
        "toolbox/name_longer_than_the_strategy_column" in strategy_stats["last_error"]
    )
    assert toolbox["cronjobs"] == [{"id": "toolbox_tick", "name": "Toolbox tick"}]
    # 平台计划任务始终在；插件追加的任务随重载出现。
    names = _cronjob_names(client, admin_headers)
    assert names["version_check"] == "版本检测"
    assert "toolbox_tick" in names

    # 导入失败的插件也列出来，带着原因。
    broken = install_plugin("raise RuntimeError('broken on import')\n", "broken")
    assert broken["state"] == "failed"
    assert broken["source"] == "external"
    assert "broken on import" in broken["error"]
