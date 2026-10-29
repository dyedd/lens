# 用户插件示例

Lens 的插件是**扩展核心边界**的模块，不是平台功能开关。计划任务、设置这类属于 Lens 自身能力；插件用来接入「不同用户有不同做法」的部分。

## 安装

把插件目录（或单个 `.py` 文件）放进插件目录，重启 Lens：

```
data/plugins/<plugin_id>/plugin.py     # 目录形式
data/plugins/<plugin_id>.py            # 单文件形式
```

插件目录默认 `./data/plugins`，可用 `LENS_PLUGINS_DIR` 覆盖。Docker 部署时 `./data` 已挂载到 `/app/data`，无需额外配置；如需独立目录，再加一个卷并设置该环境变量。

插件出现在 **设置 → 插件**，可随时启用或停用。停在扩展点外的插件不影响转发。

## 扩展点

| 标识 | 用途 | 接口 |
| --- | --- | --- |
| `upstream_request` | 改写出站请求 | `matches(call)` / `async apply(call) -> UpstreamCall` |
| `upstream_credential` | 为渠道签发凭据 | 同上，改 `headers` 即可替换鉴权 |
| `upstream_response` | 改写上游返回的响应（非流式） | `matches(response)` / `async apply(response) -> UpstreamResponse` |
| `request_observer` | 只读观察已完成请求 | `async completed(record) -> None` |
| `model_catalog` | 为渠道补充模型 | `matches(channel)` / `async models(channel) -> [CatalogEntry]` |

所有扩展点 **fail open**：插件抛错只记录日志，请求照原样发出。

## 设置与依赖

清单里可以声明设置项，Lens 会为它生成表单，值在 `context.settings` 里读取：

```python
settings=(
    PluginSetting(key="marker_header", label="标记头", type="string", default="x-lens-plugin"),
    PluginSetting(key="observe", label="记录请求", type="bool", default=True),
),
```

类型支持 `bool` / `int` / `string` / `enum`（`enum` 需给 `options`）。保存设置后会重新注册插件，因此新的值立即生效。

`requires=("other_plugin",)` 声明依赖：依赖被停用时，本插件进入 `pending`，不挂任何扩展点。

## 热加载

改完插件文件后调用 `POST /api/admin/plugins/reload`（设置页右上角的重扫按钮）即可，无需重启进程。

## 写一个插件

```python
from app.plugins.contract import (
    EXT_REQUEST_OBSERVER,
    PluginContext,
    PluginDefinition,
    PluginManifest,
    RequestRecord,
)

MANIFEST = PluginManifest(
    id="my_plugin",
    name="我的插件",
    description="一句话说明",
    version="0.1.0",
    author="your-name",
)

class Observer:
    def extension(self) -> str:
        return EXT_REQUEST_OBSERVER

    async def completed(self, record: RequestRecord) -> None:
        ...

def register(context: PluginContext) -> None:
    context.add_request_observer(Observer())

PLUGIN = PluginDefinition(manifest=MANIFEST, register=register)
```

`id` 用小写字母、数字与下划线；`api_version` 默认与当前内核一致，不匹配的插件会被标记为 `failed` 并给出原因。

## 目录里的示例

- [`request_counter/plugin.py`](request_counter/plugin.py)：最小可用的观察者插件，复制到 `data/plugins/request_counter/plugin.py` 后重启即可。
