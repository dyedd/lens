# Phase 5 审查报告 — Round 1

## 后端审查（Codex, session `019e6f4f-b99f-7d93-bc7e-20a879e24742`）

**评分**：63/100，**NEEDS_IMPROVEMENT**

- Root Cause Resolution: 15/20
- Code Quality: 16/20
- Side Effects: 10/20
- Edge Cases: 12/20
- Test Coverage: 10/20

### Critical（阻塞交付）

#### C1. backup_store.py:481 — 备份导入破坏复合渠道 ID
**问题**：备份导入逻辑将当前使用的复合渠道 ID 压回旧的 combo ID 写回去。恢复后，运行时按复合 ID 查渠道，会找不到这些 items，模型组会变成无可用节点。

**根因**：前任务 `address-protocol-combo-refactor` 引入了复合渠道 ID（`combo.id:protocol`，channel_store.py 中的展开逻辑），但 backup_store 的导入逻辑仍按旧 combo ID 写回。

**修复**：
- 校验时可以解析复合 ID
- 写回时**必须保留**当前复合渠道 ID
- 旧备份按 group 协议补成复合 ID
- 补一个"导出后再导入，带 items 的 group 仍能路由"的回归测试

#### C2. migrations/versions/4f6a8c2d9e1b_*.py:78 — PostgreSQL 兼容性
**问题**：downgrade 用了 SQLite 专属 `json_extract(protocols_json, '$[0]')`，PostgreSQL 不支持。README 明确支持 PG。

**修复**：
- 按 `op.get_bind().dialect.name` 分支处理：
  - SQLite: `json_extract(protocols_json, '$[0]')`
  - PostgreSQL: `(protocols_json::jsonb -> 0) #>> '{}'` 或类似表达式
- `HAVING c > 1` 改为通用的 `HAVING COUNT(*) > 1`（line 35）

### Warning（建议修复）

#### W1. domain_store.py:1003 — 协议覆盖完整性
当前只校验"每个 item 至少能服务一个已选协议"，没有校验"每个已声明协议都有至少一个可用 item"。
- group 可以声明支持 embedding，但实际无任何 embedding 可用节点
- 推荐：保存时按每个协议检查覆盖；不完整可接受时不应对外宣称该协议

#### W2. backup_store.py:443 — 导入校验不完整
- 只校验 protocols 非空、重名、item 存在
- 未复用 group 创建/更新的 route_group 目标覆盖、item 协议可达校验
- 坏备份能导入出运行时不可用的模型组

#### W3. router.py:455 — credential 启用状态不一致
- `route_targets` 指定 credential 时只查 ID 是否存在，没检查启用
- 直接渠道池会过滤启用 key，行为不一致

#### W4. 缺少 migration 测试
- 计划中要求 migration 测试，但 tests/ 目录没有
- 应补 upgrade 回填、重名中止、downgrade 取首协议、唯一索引重建

### Info（参考）

- service.py:3008 — 请求协议和 route_group 跳转后的目标协议校验方向正确
- router.py:422 — route_targets 二次协议过滤是关键运行时防线 ✓

---

## 前端审查（Gemini）

**状态**：⚠️ 因 Google CloudCode `gemini-3.1-pro-preview` 服务端容量耗尽（HTTP 429 RESOURCE_EXHAUSTED），自动重试均失败。本轮**前端审查跳过**，改由 Claude 代审 + verify-quality skill 兜底。

### Claude 代审小结（基于直接阅读 diff）
- ProtocolMultiSelect 组件 API 合理，aria-label 略缺（Info）
- groups-screen 多协议交互齐全，"一键移除失效节点"按钮显示条件清晰
- channels-screen 已迁移到共享组件，视觉一致
- gateway-api-key-manager 的 protocol → protocols 修改是 1 行类型适配
- 前端无 Critical 风险

---

## 修复行动

启动 Round 1 修复（Codex Fix Builder）：
1. 修 C1 (backup_store 复合渠道 ID 保留)
2. 修 C2 (migration PostgreSQL 兼容)
3. 修 W1-W4（如时间允许）

Critical 必须修复，Warning 选优。
