# Lens 代码风格

## 通用

- 可读性、职责边界和行为稳定性优先于文件数量与代码行数。
- 名称应表达领域对象和动作；避免含义宽泛的 `process`、`handle`、`data`、`item`、`value`、`result`。
- 一个函数只承担一个清晰的变化原因。解析、校验、转换、构造和副作用应保持边界。
- 只捕获能够恢复、转换或补充上下文的异常；转换异常时保留异常链。
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
- 组件负责展示与交互，Hook 负责编排状态或数据，纯转换与格式化逻辑放在独立模块。

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

领域术语沿用项目既有含义，不因个人偏好改名。核心词义：Site 是供应商账号，Channel 是它的协议出口（运行时 ID `{protocol_config_id}_{protocol}`），Credential 是站点密钥（冷却语境的 "key" 同物），ModelGroup 是对外模型名的路由单元（执行组直接承载成员，路由组转发给执行组），RouteTarget = channel × credential × model。

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

- 模块围绕单一变化原因组织；共享代码必须有明确的领域职责。
- 公共入口只导出稳定、经过选择的 API，不承载业务实现或反向导出。
- 不新增没有领域含义的 `shared.py`、`common.py`、`utils.py`、`data.py` 或 `helper.py` 聚合模块。
- 数据库行映射、输入校验、协议转换、远端传输、展示格式化和持久化副作用属于不同边界。
- API 字段、数据库列、setting key、协议字段和协议事件属于外部合同，不因内部风格重命名。
