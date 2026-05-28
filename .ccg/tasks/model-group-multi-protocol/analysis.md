# 多模型分析综合报告

> 综合 Codex (backend, session=`019e6e7a-40bb-7482-b3fc-50d775726d7d`) 与 Gemini (frontend, session=`96a2f140-a770-4f4d-9101-64b2bb7776bc`) 的并行独立分析

## 共识点（双模型一致）

| 议题 | 决策 |
|------|------|
| 数据迁移 | 单步替换（不双写）：`protocol` → `protocols_json: Text`（JSON 数组），Alembic upgrade 回填 `[protocol]`，downgrade 取 `protocols[0]` |
| `ModelGroupItem.protocol` | **保留**（运行时判断是否需要转换 + UI 显示"原生 vs 转换"） |
| 同名跨协议合并 | **禁止重名**（name 唯一）；后端拒绝创建/更新出同名组；前端引导用户编辑现有组 |
| route_group 限制 | 目标组的 `protocols` 必须**覆盖**当前组的 `protocols`（严格包含，不是交集） |
| `_SUPPORTED_CONVERSIONS` | 复用现有矩阵，不引入新协议对 |

## 后端关键发现（Codex）

### 真正风险点
- **不是字段重命名**，而是运行时路由：多协议组的 items 池混合多协议，路由前必须按"本次请求协议"二次过滤
- 双层防护：
  1. service 层 `_resolve_routing_plan`：先验证 `request_protocol in group.protocols`
  2. router 层 `route_targets` 分支：用 `can_reach_protocol(target.channel.protocol, request_protocol)` 过滤

### 强依赖单协议的位置全表（共 11 处）
1. `lens_api/models.py:478` `ModelGroup.protocol`
2. `lens_api/models.py:524` `ModelGroupCreate.protocol`
3. `lens_api/models.py:545` `ModelGroupUpdate.protocol`
4. `lens_api/models.py:618` `ModelGroupCandidatesRequest.protocol`
5. `lens_api/persistence/entities.py:112` `ModelGroupEntity.protocol`
6. `lens_api/persistence/domain_store.py:550 find_group_by_name(protocol, name)` ← 核心查询
7. `lens_api/persistence/domain_store.py:576-579 list_group_candidates` 单协议过滤
8. `lens_api/persistence/domain_store.py:710-918` create/update/validate 全部按单协议
9. `lens_api/gateway/service.py:3005 _resolve_routing_plan` 入站映射
10. `lens_api/gateway/service.py:1534-1545` `/v1/models` 列表过滤
11. `lens_api/gateway/router.py:415-436` `route_targets` 缺少协议兼容过滤
12. `lens_api/persistence/backup_store.py:406-440 + 903-1018` 备份导入导出

### 测试基线
- 当前仅有 `tests/test_channel_store.py`（4 测试通过）
- 缓存目录显示曾有 embedding / models endpoint / route 相关测试，需重建

## 前端关键发现（Gemini）

### UI 决策
| 问题 | 决策 |
|------|------|
| 多选协议组件 | **ToggleGroup type="multiple"**（与渠道侧 compatible_protocols 一致） |
| 切换协议时 items 行为 | **保留 items，标记失效**（不清空，给失效项置灰 + tooltip + 一键清理按钮） |
| 候选条目展示 | 仅显示原生 protocol badge；旁附 ghost badge 或 tooltip 提示"可转换至: X, Y" |
| 候选 channel 分组结构 | 保留 channel → protocol 两级分组 |
| 列表筛选 | **保留单选筛选**，逻辑改为 `group.protocols.includes(filter)` |
| 列表卡片 protocols badge | `flex flex-wrap gap-1.5`，桌面端不折叠 |
| 校验 | 至少选 1 个协议；全不选时 ToggleGroup 红框 + 错误文案 + Save 禁用 |

### 国际化文案（新增）
- `External Protocols` / `对外协议`
- `At least one protocol is required.` / `至少需要选择一项协议。`
- `Incompatible with current protocols` / `不兼容当前所选的对外协议`
- `Converts to: {protocols}` / `转换兼容: {protocols}`
- `Remove incompatible items` / `移除失效节点`

## 方案对比

### 方案 A：单步全量替换（推荐 ✅）
- 后端：models / entities / domain_store / service / router / backup_store 同步替换
- 前端：FormState.protocol → protocols，UI 用 ToggleGroup
- 迁移：单条 Alembic migration upgrade/downgrade
- 测试：新增多协议端到端测试 + 现有测试同步

**优点**：一次性，没有过渡期复杂度
**缺点**：API payload 字段名是破坏性变更（项目单仓库，可接受）

### 方案 B：渐进双写
- 保留 `protocol` 字段同时加 `protocols_json`，双读双写
- 稳定后再删旧字段

**缺点**：项目规模小，前后端同发布，双写收益不大，复杂度高 — **不推荐**

### 方案 C：UI 收敛 + 后端不动
- 仅在 UI 层把"同名多协议组"合并显示
- 后端继续按 `(name, protocol)` 唯一

**缺点**：不能解决根本问题（路由仍按单协议），与需求目标冲突 — **不推荐**

## 最终推荐：方案 A

理由：
1. 与需求架构目标完全对齐
2. 个人项目，无外部 API 兼容压力
3. 双模型独立得出相同结论，高置信度
4. 与前任务 `address-protocol-combo-refactor` 的迁移风格保持一致

## 剩余决策（写入 plan.md 时确认）

- ✅ 同名合并：禁止重名
- ✅ route_group：严格包含
- ✅ ModelGroupItem.protocol：保留
- ⏳ 失效项 UI：保留 + 标记（待 plan.md 细化交互）
- ⏳ candidates 接口字段：`protocol → protocols: list[ProtocolKind]`（破坏性，前后端同步）
