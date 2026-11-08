# 插件示例

把示例目录复制到 `data/plugins/`，Lens 会自动发现。可在 **设置 → 插件** 中启停、配置和查看调用统计。

| 示例 | 用途 |
| --- | --- |
| [request_counter](./request_counter/plugin.py) | 观察已完成的请求，记录模型、状态码和耗时 |
| [channel_credential_bridge](./channel_credential_bridge/plugin.py) | 为指定渠道提供凭据并添加标记头 |
| [response_header_stamp](./response_header_stamp/plugin.py) | 为非流式回复添加响应头，依赖凭据桥接示例 |

完整的安装步骤、七个扩展点、设置、热加载与验证方法见 [插件开发文档](../../docs/development/plugins.md)。
