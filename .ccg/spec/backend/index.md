# Backend Spec — 可复用编码约定

> 通过 `.ccg/tasks/model-group-multi-protocol/` 任务沉淀的经验。

## Alembic 迁移：跨方言兼容性

**Rule**：当迁移涉及 JSON 字段的 SQL 表达式时，必须按 `op.get_bind().dialect.name` 分支处理。

**Why**：项目 README 声明支持 SQLite + PostgreSQL，但常见的 `json_extract(col, '$[0]')` 是 SQLite 专属。直接写一份 SQL 会在 PG 环境下让 downgrade 崩溃，且本地仅跑 SQLite 测试时无法暴露。

**How to apply**：
```python
def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute("UPDATE t SET col = json_extract(col_json, '$[0]')")
    elif dialect == "postgresql":
        op.execute("UPDATE t SET col = (col_json::jsonb -> 0) #>> '{}'")
    else:
        raise RuntimeError(f"Unsupported dialect for downgrade: {dialect}")
```

**坑点**：
- `HAVING c > 1`（用列别名）在 PG 不支持，要写 `HAVING COUNT(*) > 1`
- SQLite 的 `||` 字符串拼接 PG 也支持，但 JSON 数组应优先用 `json_build_array(x)::text` for PG
- 添加迁移时必须实跑 `alembic downgrade -1 && alembic upgrade head`（仅 SQLite 也好，至少证明双向通）

**关联**：[[migration-test-coverage]]

---

## Migration 必须测：upgrade/downgrade 双向 + 同名预检

**Rule**：每个改 schema 的 migration 都要有对应测试覆盖。

**Why**：本次原本计划里就要求 migration 测试，但被遗漏。直到 Codex 二次审查指出"没测试 = 上线时回退能不能成功是未知数"。

**How to apply**：在 `tests/test_<feature>_migration.py` 至少覆盖：
1. `test_upgrade_backfills_xxx` — 旧字段→新字段回填正确
2. `test_upgrade_rejects_duplicate_<key>` — 唯一性约束预检拦截
3. `test_downgrade_restores_<canonical>` — downgrade 取一个规范值
4. `test_upgrade_rebuilds_unique_index` — 新唯一索引真的生效

实现技巧：使用 SQLite in-memory + 直接调用迁移函数（参数 mock `op`），比起架 alembic env 更轻量。

---

## 备份恢复必须感知"运行时复合 ID"

**Rule**：当存储层使用复合 ID（如 `{combo_id}_{protocol}`），备份导入逻辑必须保留复合 ID，**不要**把它压回原始组件。

**Why**：本次 backup_store 在 group items 写回时 `channel_id=combo_id`，但运行时 channel_store._flatten_site 生成的渠道 ID 是 `f"{combo.id}_{protocol.value}"`。恢复后 group items 找不到匹配渠道，模型组变成无可用节点 — 而单测能跑通（因为单测建了空数据库）。

**How to apply**：
1. 备份导出：保留实际运行时使用的 ID
2. 备份导入：
   - 若 ID 已是复合形态（含 `_<protocol>` 后缀）→ 直接使用
   - 若 ID 是裸形态（旧备份）→ 根据 group.protocols ∩ combo.compatible_protocols 第一个匹配协议补全
3. 测试必须含 "导出→清库→导入→运行时路由能命中" 的端到端往返

---

## 多协议组路由：双层防护

**Rule**：多协议 group 路由请求时，必须 service 层 + router 层各做一次"请求协议是否被支持"的过滤。

**Why**：service 层只判断 `request_protocol in group.protocols` 不够 — group 内的 items 可能混合多个原生协议，路由器必须再用 `can_reach_protocol(item.channel.protocol, request_protocol)` 过滤，否则会把不兼容的 item 选为 primary 进而触发上游错误。

**How to apply**：
- service 层：在 `_resolve_routing_plan` 入口判断 `request_protocol in group.protocols` → 否则 LookupError
- router 层：在 `_filter_enabled_targets`（route_targets 分支）调用 `can_reach_protocol(target.channel.protocol, protocol)` 二次过滤
- route_group 跳转后两层判断都要再跑一次（防止目标组协议不全）
- 测试必须覆盖"chat 渠道服务 anthropic 请求"等转换路径
