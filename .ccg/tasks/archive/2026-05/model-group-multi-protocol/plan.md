# 实施计划：模型组多协议声明 + 协议兼容/转换路径

> 综合 Codex 后端规划（session=`019e6e7a-40bb-7482-b3fc-50d775726d7d`）和 Gemini 前端规划（session=`96a2f140-a770-4f4d-9101-64b2bb7776bc`）

## 核心决策摘要

| 议题 | 决策 |
|------|------|
| 字段重命名 | `ModelGroup.protocol` (str) → `protocols` (list[ProtocolKind], min_length=1) |
| 存储 | `model_groups.protocol` → `model_groups.protocols_json: Text` (JSON 数组) |
| 同名约束 | name 唯一（数据库唯一索引 + 应用层校验） |
| route_group | 目标组 protocols ⊇ 当前组 protocols |
| ModelGroupItem.protocol | 保留（运行时转换判定） |
| 路由防护 | 双层：service 层（请求协议 ∈ group.protocols）+ router 层（route_targets 用 can_reach_protocol 二次过滤） |
| UI 多选 | `ToggleGroup type="multiple"`（与渠道侧一致），保留 items + 失效项标记 + 一键清理 |
| 候选展示 | 仅原生协议带色 badge + tooltip 提示转换覆盖 |
| 列表筛选 | 单选 + `group.protocols.includes(filter)` |
| 列表卡片 | `flex flex-wrap gap-1.5` 多 badge 平铺 |

---

## Layer 1：基础契约层（无依赖，可并行）

### 1.1 后端：[lens_api/models.py](lens_api/models.py)
- `ModelGroup`: `protocol: ProtocolKind` → `protocols: list[ProtocolKind] = Field(min_length=1)`
- `ModelGroupCreate`: 同上
- `ModelGroupUpdate`: `protocol: ProtocolKind | None` → `protocols: list[ProtocolKind] | None = Field(default=None, min_length=1)`
- `ModelGroupCandidatesRequest`: `protocol: ProtocolKind | None` → `protocols: list[ProtocolKind] = Field(default_factory=list)`
- `ModelGroupItem`: **保留 `protocol` 字段不变**

### 1.2 后端：[lens_api/persistence/entities.py](lens_api/persistence/entities.py)
- `ModelGroupEntity.protocol: Mapped[str]` → `ModelGroupEntity.protocols_json: Mapped[str] = mapped_column(Text, default="[]")`
- 删除 `protocol` 列对应的索引
- name 索引改为唯一

### 1.3 数据迁移：`migrations/versions/4f6a8c2d9e1b_model_group_protocols_json.py`

**upgrade()**：
1. 预检：扫描 `model_groups` 表，若存在同名多组 → `op.execute("SELECT name FROM model_groups GROUP BY name HAVING COUNT(*) > 1")` 抛错中止
2. `batch_alter_table("model_groups")`：
   - 新增 `protocols_json TEXT NOT NULL DEFAULT '[]'`
3. 回填：`UPDATE model_groups SET protocols_json = '["' || protocol || '"]'`
4. 删除 `ix_model_groups_protocol` 旧索引
5. 删除 `protocol` 列
6. 删除原 `ix_model_groups_name`，重建为唯一索引
7. 可选：去掉 `protocols_json` 的 server_default（保留 ORM default）

**downgrade()**：
1. `batch_alter_table`：新增 `protocol VARCHAR(40) NOT NULL DEFAULT 'openai_chat'`
2. 回填：`UPDATE model_groups SET protocol = json_extract(protocols_json, '$[0]')`；空数组兜底 `openai_chat`
3. 删除 name 唯一索引，重建非唯一索引
4. 重建 `ix_model_groups_protocol`
5. 删除 `protocols_json`
6. 移除 `protocol` 临时 server_default

> **限制**：downgrade 只保留第一个协议，多协议数据信息丢失（需在 docstring 注明）

### 1.4 前端：[ui/src/lib/api.ts](ui/src/lib/api.ts)
- `ModelGroup.protocol` → `protocols: ProtocolKind[]`
- `ModelGroupPayload.protocol` → `protocols: ProtocolKind[]`
- `ModelGroupCandidatesPayload.protocol?` → `protocols?: ProtocolKind[]`
- 新增辅助：
  ```ts
  const FRONTEND_SUPPORTED_CONVERSIONS: Partial<Record<ProtocolKind, ProtocolKind[]>> = {
    openai_chat: ["anthropic", "openai_responses"],
  };
  canReachProtocol(channelProtocol, groupProtocol): boolean
  isItemValidForProtocols(itemProtocol, selectedProtocols[]): boolean
  ```

### 1.5 前端：新建 [ui/src/components/ui/protocol-multi-select.tsx](ui/src/components/ui/protocol-multi-select.tsx)
- 从 channels-screen.tsx 提取，封装 `ToggleGroup type="multiple"` + compact label + 配色
- 接口：`{ value: ProtocolKind[]; onChange: (val: ProtocolKind[]) => void; locale: 'zh-CN'|'en-US'; allowedProtocols?: ProtocolKind[] }`
- 同时让 channels-screen.tsx 改用此组件（确保共享）

---

## Layer 2：业务逻辑层（依赖 Layer 1）

### 2.1 后端：[lens_api/persistence/domain_store.py](lens_api/persistence/domain_store.py)

**新增私有工具**：
- `_parse_group_protocols(entity) -> list[ProtocolKind]` — 读 JSON 字符串
- `_dump_group_protocols(protocols) -> str` — 写 JSON 字符串
- `_normalize_group_protocols(protocols) -> list[ProtocolKind]` — 去重 + 校验非空
- `_group_supports_protocol(group_or_entity, protocol) -> bool`

**重构的方法**：
- `find_group_by_name(protocol, name)` — 仍接受单 protocol 参数（service.py 调用）
  - 改为：按 name 查询单一组（依赖 name 唯一），再 `protocol in entity.protocols` 校验
- `list_group_candidates(payload)` — 改用 `payload.protocols`，过滤规则：`any(can_reach_protocol(ch.protocol, p) for p in payload.protocols)`
- `create_group(payload)` — 写入 `protocols_json`，调用多协议版 `_validate_group_payload`
- `update_group(group_id, payload)` — 计算 `next_protocols`；如组被 route_group 引用，禁止收缩协议
- `_validate_group_payload(...)`:
  - name 唯一校验
  - route_group 目标 protocols ⊇ 当前 protocols
  - 每个 item 至少能服务 `any(can_reach_protocol(item.channel.protocol, p) for p in protocols)`
- `_to_group(entity)` — 返回 `protocols`
- `list_model_prices` / `upsert_model_price` — 从 `entity.protocols_json` 聚合协议列表

### 2.2 后端：[lens_api/gateway/converters/__init__.py](lens_api/gateway/converters/__init__.py)
- 不改实现，复用 `can_reach_protocol`、`needs_conversion`
- 仅添加内部测试用例（在 Layer 1 测试文件中覆盖）

---

## Layer 3：运行时与外围层（依赖 Layer 2）

### 3.1 后端：[lens_api/gateway/service.py](lens_api/gateway/service.py)
- `_filtered_group_names` — `group.protocol in protocols` → `set(group.protocols) & set(request_protocols)` 非空
- `_resolve_routing_plan(protocol, requested_model)`:
  - 按 name 找 group（不传 protocol 参数）
  - 验证 `protocol in group.protocols`，否则 raise 404
  - route_group 跳转后再次验证目标组支持此 protocol
  - 构造 `route_targets` 时只保留 `can_reach_protocol(item.channel.protocol, protocol)` 的 item
- 管理 API handlers（model_groups.py 路由）：无需手写错误码，依赖全局 ValueError → 400 / LookupError → 404

### 3.2 后端：[lens_api/gateway/router.py](lens_api/gateway/router.py)
- 导入 `from ..gateway.converters import can_reach_protocol`
- `_filter_enabled_targets` 中 `route_targets is not None` 分支：
  - 新增：`can_reach_protocol(target.channel.protocol, protocol)` 过滤
- 普通 channels 分支保持精确协议匹配不变

### 3.3 后端：[lens_api/persistence/backup_store.py](lens_api/persistence/backup_store.py)
- `_load_groups`（导出）：使用 `protocols`，不再输出 `protocol`
- `_replace_groups`（导入）：
  - 优先读 `protocols`
  - fallback 旧 `protocol` → `[protocol]`
  - 同名 group 去重从 `(protocol, name)` → `name`，重名直接拒绝（不自动合并）

### 3.4 前端：[ui/src/components/screens/groups-screen.tsx](ui/src/components/screens/groups-screen.tsx)

**类型与状态**：
- `FormState.protocol: ProtocolKind` → `protocols: ProtocolKind[]`
- `emptyForm.protocols: ["openai_chat"]`
- `toForm`：`group.protocols`
- `toPayload`：`form.protocols`

**交互**：
- 移除 `changeProtocol`，新增 `toggleProtocol(protocol: ProtocolKind)`：仅切换 `form.protocols`，不清空 items
- `candidatePayload`：`{ protocols: form.protocols, exclude_items: [...] }`
- `CandidateRow`：新增 tooltip "✨ 转换兼容: {protocols}" 当 `FRONTEND_SUPPORTED_CONVERSIONS[item.protocol]` 与 form.protocols 有交集
- `SelectedMemberRow`：当 `!isItemValidForProtocols(item.protocol, form.protocols)` → `bg-destructive/10 border-destructive` + 警告图标 + tooltip "不兼容当前所选的对外协议"
- 已选列表头部：当存在失效项 → 展示按钮 "一键移除失效节点"

**列表卡片**：
- 单 badge → `flex flex-wrap gap-1.5` 多 badge

**列表筛选**：
- 单选 dropdown 保留，逻辑改为 `if (protocolFilter !== "all" && !group.protocols.includes(protocolFilter)) return false`

**校验**：
- ToggleGroup 红色边框 + 错误文案 "至少需要选择一项协议。" 当 `form.protocols.length === 0`
- Save 按钮 `disabled={form.protocols.length === 0 || ...}`

---

## i18n 文案（新增）

| 位置 | zh-CN | en-US |
|------|-------|-------|
| 表单字段标题 | 对外协议 | External Protocols |
| 必填校验 | 至少需要选择一项协议。 | At least one protocol is required. |
| 候选区空态 | 请先在上方选择对外协议以加载候选节点。 | Select external protocols above to load candidates. |
| 失效项 tooltip | 不兼容当前所选的对外协议 | Incompatible with current protocols |
| 转换提示 tooltip | ✨ 转换兼容: {protocols} | ✨ Converts to: {protocols} |
| 清理按钮 | 一键移除失效节点 | Remove invalid items |
| 重名错误 | 模型组已存在: {name} | Model group already exists: {name} |
| 路由目标协议不足 | 路由目标协议必须覆盖源协议: {missing} | Route target protocols must cover source protocols: {missing} |

---

## 测试用例清单

| 文件 | 测试用例 |
|------|---------|
| `tests/test_model_group_protocols.py` (新) | `test_create_group_requires_protocols`, `test_create_group_rejects_duplicate_name`, `test_group_candidates_match_any_selected_protocol`, `test_group_candidates_deduplicate_same_channel_credential_model`, `test_group_item_must_reach_at_least_one_group_protocol`, `test_route_group_target_must_cover_all_protocols`, `test_to_group_returns_protocols` |
| `tests/test_model_group_routing.py` (新) | `test_resolve_group_by_name_and_openai_chat_protocol`, `test_resolve_group_by_name_and_responses_protocol`, `test_resolve_group_by_name_and_anthropic_protocol`, `test_resolve_group_rejects_unsupported_protocol`, `test_route_targets_filtered_by_request_protocol`, `test_openai_chat_channel_can_serve_anthropic_group_request` |
| `tests/test_router_protocol_compat.py` (新) | `test_route_targets_are_filtered_with_can_reach_protocol`, `test_direct_channel_pool_still_requires_exact_protocol`, `test_router_raises_when_all_route_targets_incompatible` |
| `tests/test_model_group_migration.py` (新) | `test_upgrade_backfills_protocols_json`, `test_upgrade_rejects_duplicate_group_names`, `test_downgrade_restores_first_protocol`, `test_upgrade_rebuilds_name_unique_index` |
| `tests/test_backup_model_group_protocols.py` (新) | `test_export_uses_protocols`, `test_import_old_protocol_field_as_single_protocol_list`, `test_import_rejects_duplicate_group_names`, `test_import_rejects_empty_protocols` |
| `tests/test_channel_store.py` (既有) | 无需主动修改 |

---

## 边界 Case 处理矩阵

| 场景 | 处理 | HTTP 码 | 文案 |
|------|------|---------|------|
| 创建缺失 protocols | Pydantic 拒绝 | 422 | `Field required: protocols` |
| protocols 为空 | Pydantic 拒绝 | 422 | `List should have at least 1 item` |
| protocols 含未知值 | Pydantic 拒绝 | 422 | `Input should be ...` |
| 创建同名 group | 后端拒绝 | 400 | `Model group already exists: {name}` |
| 更新改重名 | 后端拒绝 | 400 | 同上 |
| items channel 不存在 | 后端拒绝 | 400 | `Channels not found: ...` |
| item 对所有 protocols 都不可达 | 后端拒绝 | 400 | `Channels cannot reach any selected protocol: ...` |
| route_group 指向自己 | 后端拒绝 | 400 | `Model group cannot route to itself` |
| route_group 目标协议不全 | 后端拒绝 | 400 | `Route target protocols must cover source protocols: ...` |
| 被引用的执行组收缩协议 | 后端拒绝 | 400 | `Execution groups referenced by route groups cannot remove protocols` |
| 请求协议 ∉ group.protocols | 运行时未匹配 | 404 | `No model group matched {model}` |
| 迁移时存在同名多协议组 | 中止迁移 | migration error | `Migration aborted: duplicate model group names found: ...` |

---

## 验收路径（手工 QA）

1. **多选表单**：点击 Create Group → 顶部 ToggleGroup 默认 `chat` 选中
2. **多协议组创建**：勾选 `chat` + `responses` + `anthropic` → 输入 `GPT-5.5` → 添加候选 → 保存
3. **三入口命中**：分别 `POST /v1/chat/completions`、`/v1/responses`、`/v1/messages` model=GPT-5.5 → 全部 200
4. **转换提示**：在表单内取消 `anthropic` 仅留 `chat`，OpenAI Chat 候选条目 hover 应显示 "可转换至: Anthropic, Responses"
5. **失效标记**：勾选某协议后再取消 → 已选列表中相关 item 整行变红 + 警告图标
6. **一键清理**：点击"移除失效节点" → 相关 item 清空
7. **全不选阻断**：取消所有协议 → ToggleGroup 红框，Save 禁用
8. **列表渲染**：列表卡片显示三个 badge 平铺
9. **列表筛选**：选择 `responses` 过滤 → GPT-5.5 出现
10. **同名拒绝**：尝试再创建一个 name=GPT-5.5 的组 → 400 `Model group already exists`
11. **Migration**：`alembic downgrade -1 && alembic upgrade head` 在测试库跑通
12. **现有数据兼容**：单协议老组在升级后行为不变

---

## Phase 4 子任务拆分（用于 Builder 并行执行）

### Layer 1 子任务（无依赖，3 个并行）

**L1-A：后端契约**
- 文件范围：`lens_api/models.py`, `lens_api/persistence/entities.py`
- 验证：`./.venv/bin/python -m pytest -q` + `python -c "from lens_api.models import ModelGroup"`

**L1-B：数据迁移**
- 文件范围：`migrations/versions/4f6a8c2d9e1b_model_group_protocols_json.py`（新增）
- 验证：`alembic upgrade head` + `alembic downgrade -1` + `alembic upgrade head`

**L1-C：前端契约 + 共享组件**
- 文件范围：`ui/src/lib/api.ts`, `ui/src/components/ui/protocol-multi-select.tsx`（新增）
- 验证：`cd ui && pnpm typecheck`

### Layer 2 子任务（依赖 L1，2 个并行）

**L2-A：持久化层**
- 文件范围：`lens_api/persistence/domain_store.py`
- 验证：新增 `tests/test_model_group_protocols.py` 通过

**L2-B：备份层**
- 文件范围：`lens_api/persistence/backup_store.py`
- 验证：新增 `tests/test_backup_model_group_protocols.py` 通过

### Layer 3 子任务（依赖 L2，3 个并行）

**L3-A：网关路由**
- 文件范围：`lens_api/gateway/service.py`, `lens_api/gateway/router.py`
- 验证：新增 `tests/test_model_group_routing.py` + `tests/test_router_protocol_compat.py` 通过

**L3-B：前端业务逻辑**
- 文件范围：`ui/src/components/screens/groups-screen.tsx`
- 验证：`cd ui && pnpm typecheck && pnpm build`

**L3-C：channels-screen 切换至共享组件**
- 文件范围：`ui/src/components/screens/channels-screen.tsx`（用 ProtocolMultiSelect 替换 inline 实现）
- 验证：`cd ui && pnpm typecheck`，地址多选 UI 视觉无回归

### Layer 4 子任务（最终集成）

**L4-Review**：
- 启动开发环境：`./.venv/bin/python -m lens_api` + `cd ui && pnpm dev`
- 跑完整手工 QA 验收路径（12 步）
- 全量 `pytest -q` 通过

---

## 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| Migration 遇到同名多协议组 | 中止失败 | 预检脚本提前发现，人工合并后再迁移 |
| router 二次过滤遗漏导致误路由 | 高 | service + router 双层防护 + 测试用例覆盖 |
| route_group 协议覆盖校验疏漏 | 中 | _validate_group_payload 集中校验 |
| 前端失效项判定与后端 can_reach_protocol 不同步 | 中 | FRONTEND_SUPPORTED_CONVERSIONS 提取为常量，注释明确 "Mirror of backend _SUPPORTED_CONVERSIONS" |
| backup 旧格式导入丢字段 | 低 | fallback 逻辑 + 测试覆盖 |
| `/v1/models` 列表筛选改为集合交集后语义变化 | 低 | 单测覆盖 |
