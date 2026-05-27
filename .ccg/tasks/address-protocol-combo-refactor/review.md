# Phase 5 审查报告 — Round 1（综合手动 + Codex 审查）

## 质量关卡

| 关卡 | 结果 |
|------|------|
| verify-change | ✅ 通过 |
| verify-security | ✅ 通过（本次变更无新漏洞） |
| verify-quality | ✅ 通过（0 错误，38 警告均为预存） |
| Python 语法检查 | ✅ 通过 |

---

## Critical（必须修复）

### C1：Migration Step 8 SQL 错误——发现模型失联

**位置**：`migrations/versions/3e9a1f7c_address_protocols_combo_refactor.py:109-119`

**问题**：Step 8 的子查询先 `WHERE p.id = site_discovered_models.protocol_config_id` 过滤，再做窗口函数 `MIN(p.id) OVER (PARTITION BY ...)`，但此时分区只有一行，`MIN(p.id)` 仍然是原 ID——没有真正映射到 canonical combo_id。Step 9 删除非 canonical 行后，这些模型指向的 `protocol_config_id` 已被删除，全部失联。

**修复**：改用与 Step 6/7 相同的 JOIN 写法：
```sql
UPDATE site_discovered_models
SET protocol_config_id = (
    SELECT canon.canonical_id
    FROM site_protocol_configs p
    JOIN (
        SELECT site_id, base_url_id, credential_id, MIN(id) AS canonical_id
        FROM site_protocol_configs GROUP BY site_id, base_url_id, credential_id
    ) AS canon ON canon.site_id = p.site_id
        AND canon.base_url_id = p.base_url_id
        AND canon.credential_id = p.credential_id
    WHERE p.id = site_discovered_models.protocol_config_id
)
WHERE protocol_config_id IN (SELECT id FROM site_protocol_configs)
```
同理 Step 6/7 中的窗口函数也改为 GROUP BY 子查询（避免 SQLite 版本兼容性风险）。

---

### C2：`service.py` 模型发现接口仍读 `payload.protocol`

**位置**：`lens_api/gateway/service.py`（`fetch_site_models()` 函数）

**问题**：`SiteModelFetchRequest.protocol` 已被移除，改为 `compatible_protocols`。但 `service.py` 中的 `fetch_site_models()` 仍访问 `payload.protocol`，且构造 `SiteModelFetchItem` 时不填 `protocol` 字段——运行时会触发 AttributeError 或 Pydantic 校验失败。

**修复**：`service.py` 中按 `payload.compatible_protocols` 分协议逐一执行发现，每条结果填入对应 `protocol`。

---

### C3：`list_site_runtime_summaries()` 引用已删除的 `protocol` 列

**位置**：`lens_api/persistence/domain_store.py`（`list_site_runtime_summaries()` 约 line 1888）

**问题**：`SiteProtocolConfigEntity.protocol` 已删除，但该方法仍用于排序（ORDER BY）；且该方法通过 `SiteProtocolConfigEntity.id == RequestLogEntity.channel_id` 关联，但迁移后 `request_logs.channel_id` 已是复合 ID，不再等于 combo ID。运行时汇总请求会崩溃。

**修复**：移除 `.protocol.asc()` 排序引用；更新日志关联逻辑，支持从复合 channel_id 提取 combo_id 做关联。

---

### C4：旧备份导入：`StrictBaseModel(extra="forbid")` 在兼容代码前报错

**位置**：`lens_api/models.py`（`SiteProtocolConfig` 使用 `StrictBaseModel`）

**问题**：`ConfigBackupDump` 使用 `SiteConfig → SiteProtocolConfig`，而 `StrictBaseModel(extra="forbid")` 会在 Pydantic 解析时直接拒绝旧备份中的 `protocol` 字段——早于 `backup_store._replace_sites()` 中的兼容逻辑执行。旧备份完全无法导入。

**修复**：为备份使用专用的宽松模型（`extra="ignore"`），或在 `ConfigBackupDump` 解析前做原始 JSON 预处理升级（将旧 `protocol` 字段从 protocol_configs 中移出）。

---

### C5：`groups-screen.tsx` channelMap 键名不匹配

**位置**：`ui/src/components/screens/groups-screen.tsx:780-793`

**问题**：`channelMap` 以 combo ID（`protocol.id`）为键，但 `ModelGroupItem.channel_id` 是复合 ID（`{combo_id}_{protocol}`）。所有 `channelMap.get(item.channel_id)` 查询返回 `undefined`，渠道名称、地址、协议显示为空。

**修复**：channelMap 改为按复合 channel ID 构建：
```typescript
for (const combo of site.protocols) {
  const baseUrl = site.base_urls.find(b => b.id === combo.base_url_id);
  for (const p of (baseUrl?.compatible_protocols ?? [])) {
    map.set(`${combo.id}_${p}`, {
      id: `${combo.id}_${p}`,
      name: site.name,
      base_url: baseUrl?.url ?? "",
      protocol: p,
    });
  }
}
```

---

## Warning（建议修复）

| # | 问题 | 位置 |
|---|------|------|
| W1 | `delete_site()` 和 `_cleanup_*` 方法仍按裸 combo ID 清理，不处理复合 ID | `channel_store.py:94, 696, 728` |
| W2 | `list_group_candidates()` 返回 `credential_number=0`, `site_id=""` | `domain_store.py:603-614` |
| W3 | Migration Step 6/7 使用窗口函数（SQLite 3.25+ 才支持），改 GROUP BY 更兼容 | migration file |
| W4 | Migration 未在 DB 层扩展 `channel_id` 列至 `String(160)` | migration file |
| W5 | `_flatten_site` 中 `m.protocol is None` 的模型被展开到所有协议（语义不明确） | `channel_store.py:325` |

---

## Summary

- **Critical: 5**（C1~C5，全部需要修复才能正常运行）
- **Warning: 5**（W1~W5，建议修复）
