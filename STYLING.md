# Lens 代码风格

适用于后端、前端和脚本。按修改范围读取对应语言章节；通用、命名与模块边界适用于所有代码。格式和自动检查以 `backend/pyproject.toml`、`frontend/biome.json` 为准，执行命令见 [项目协作指南](CLAUDE.md)。

## 通用

- 可读性、职责边界和行为稳定性优先于文件数量与代码行数。
- 名称应表达领域对象和动作；上下文不足时避免笼统的 `process`、`handle`、`data`、`item`、`value`、`result`。局部变量和约定俗成的事件处理名称以清晰为准。
- 只捕获能够恢复、转换或补充上下文的异常；内部异常转换保留异常链，HTTP 错误遵循现有 API 错误处理约定。
- 异步路径不得执行阻塞 I/O；客户端、会话、文件和连接池必须有明确的生命周期。
- 公共函数、复杂函数和跨模块数据结构使用明确的类型标注。
- 多个独立返回值使用具名结构，不使用依赖位置记忆的长元组。
- 注释只说明代码无法直接表达的约束或取舍，不描述显而易见的实现过程。

## Python

- 模块、函数、方法和变量使用 `snake_case`；类使用 `PascalCase`；常量使用 `UPPER_SNAKE_CASE`。
- 私有成员使用前导下划线，但不要用下划线掩盖缺失的模块边界。
- 文件名应表达领域和方向，例如 `site_payload_processing.py`、`channel_row_mapping.py`。
- 布尔值优先使用 `is_`、`has_`、`can_`、`should_`。
- 访问持久化或远端资源的函数使用准确的 `get`、`find`、`list`、`load` 或 `fetch`。
- 纯函数的名称应说明输入与输出的关系，避免使用笼统的 `process` 或 `transform`。

## TypeScript / React

- React 组件文件使用 `PascalCase.tsx`；Hook 文件使用 `useXxx.ts`；工具文件使用 `camelCase.ts`。
- 布尔状态和属性优先使用 `is`、`has`、`can`、`should`。
- 事件处理函数使用 `handleXxx` 或更具体的动作名称。
- mapper 名称表达转换方向，例如 `siteToFormState`、`formStateToSitePayload`。
- 列表构造函数表达结果，例如 `buildGroupRows`、`buildModelEntries`。
- Props、API 数据和公共 Hook 使用明确类型；不得用 `any` 绕过边界建模。
- 组件负责展示与交互；需要复用或有独立编排职责的状态逻辑放入 Hook，纯转换与格式化逻辑按职责组织。仅在单处使用的简单逻辑可以留在组件或同文件中。

## 类型命名

| 后缀 | 含义 |
| --- | --- |
| `Entity` | 数据库 ORM 行 |
| `Input` | 应用层或嵌套输入结构 |
| `Request` / `Response` | HTTP 请求或响应结构 |
| `Payload` | 协议或序列化数据 |
| `Config` | 运行时或聚合配置 |
| `View` | 读取或展示模型 |
| `Plan` | 已计算的执行计划 |
| `Target` | 执行目标 |
| `State` | 状态快照 |
| `Evaluation` | 评估结果 |

## 领域术语

沿用项目既有含义，不因个人偏好改名。

| 术语 | 含义 |
| --- | --- |
| `Site` | 供应商账号 |
| `Channel` | 站点的协议出口，运行时 ID 为 `{protocol_config_id}_{protocol}` |
| `Credential` | 站点密钥；冷却语境中的 `key` 指同一对象 |
| `ModelGroup` | 对外模型名的路由单元；执行组直接承载成员，路由组转发给执行组 |
| `RouteTarget` | channel × credential × model 的组合 |

## 动作动词

| 动词 | 用途 |
| --- | --- |
| `parse` | 外部表示转为结构化值 |
| `validate` | 判断并拒绝非法输入 |
| `coerce` | 转换为目标类型或范围 |
| `resolve` | 根据上下文选择最终值 |
| `build` | 组装对象、请求或视图 |
| `serialize` / `dump` | 写成 JSON、字符串、bytes 或线格式 |
| `convert` | 跨协议、schema 或领域映射 |
| `format` | 生成展示文本 |
| `get` / `find` / `list` | 必需查找、可选查找、集合读取 |
| `fetch` / `load` | 远端获取、本地读取 |
| `create` / `update` / `delete` | 持久化变更 |
| `replace` / `ensure` / `sync` / `run` | 全量替换、幂等确保、对账同步、执行流程 |

`normalize` 不是默认前缀；只有纯函数、幂等且仍表示同一语义值时才使用。否则选择能表达真实动作的动词。

## 模块边界

- 函数和模块围绕清晰职责组织；共享代码必须有明确的领域职责，不因文件行数或单次复用机械拆分。
- 公共入口只导出稳定、经过选择的 API，不承载业务实现或反向导出。
- 不新增没有领域含义的 `shared.py`、`common.py`、`utils.py`、`data.py` 或 `helper.py` 聚合模块。
- 数据库行映射、输入校验、协议转换、远端传输、展示格式化和持久化副作用属于不同边界。
- API 字段、数据库列、setting key、协议字段和协议事件属于外部合同，不因内部风格重命名。

## 请求与错误边界

- 网关请求按“解析输入 → 校验 → 生成路由计划 → 协议转换 → 上游传输 → 转换响应 → 写入日志”组织；每一阶段只负责自己的输入和输出。
- 新增或修改的资源缺失、业务冲突和跨层客户端错误使用 `backend/app/core/errors.py` 中的领域异常表达；不要用 `KeyError`、`LookupError` 或裸 `RuntimeError` 让全局处理器猜测 HTTP 语义。纯输入解析仍可使用 `ValueError`，但必须在边界转换为稳定响应。
- 领域异常保留异常链；内部程序错误继续抛出并记录为 500，不把实现细节、上游原始密钥或完整请求体放进公开消息。
- 协议错误统一通过 `gateway/service/error_responses.py` 生成；OpenAI、Anthropic、Gemini 的 envelope 只能在该边界适配，业务层不要各自拼接错误 JSON。
- 事务由修改入口持有；跨表写入在同一 `AsyncSession` 中完成，提交后再读取展示模型。请求日志记录最终状态和尝试链，不以日志副作用替代业务成功判定。
