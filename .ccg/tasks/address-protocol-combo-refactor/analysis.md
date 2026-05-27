# 双模型分析综合报告

## 后端分析（Codex）摘要

### 核心结论
- **推荐方案 A（保守落地）+ 2个必要补丁**：
  1. `SiteDiscoveredModelEntity` 新增 `protocol` 列
  2. `SiteModelFetchItem` 新增 `protocol: ProtocolKind`

### 关键影响面（Codex 实地核查）
当前所有通过 `channel_id == SiteProtocolConfigEntity.id` 关联的组件：

| 组件 | 位置 | 变化 |
|------|------|------|
| 路由健康状态 | `router.py` 内存 Dict | 复合 ID 保持独立熔断 |
| 模型组条目 | `ModelGroupItemEntity.channel_id` | 迁移为复合 ID |
| 模型组候选 | `DomainStore.list_group_candidates()` | 改基于展开 channels |
| 路由执行计划 | `service.py` channel_map | 已兼容（展开后 ID 唯一） |
| 站点运行摘要 | `domain_store.py` 日志聚合 | 需适配复合 ID |
| 备份恢复 | `backup_store.py` | 需包含地址协议、发现模型协议 |

### 关键风险（高优先级）
1. **迁移冲突**：同一 (base_url, credential) 的多条旧配置若有不同的 headers/proxy/override/enabled，**无法自动合并**，必须在迁移时检测冲突并 abort，要求人工处理
2. **模型发现失去协议维度**：不加 `protocol` 列会导致不同协议拉取的模型混合，某协议显示实际不可用的模型
3. **`channel_id` 字符串长度**：`String(80)` 可能不足（UUID + `_` + 协议名），建议扩至 `String(160)`

### 迁移策略要点
```sql
-- Step 1: 地址回填兼容协议
ALTER TABLE site_base_urls ADD COLUMN compatible_protocols_json TEXT NOT NULL DEFAULT '[]';
UPDATE site_base_urls AS b SET compatible_protocols_json = (
  SELECT json_group_array(protocol) FROM (
    SELECT DISTINCT p.protocol FROM site_protocol_configs AS p
    WHERE p.site_id = b.site_id AND p.base_url_id = b.id ORDER BY p.protocol
  )
);

-- Step 2: 发现模型回填协议
ALTER TABLE site_discovered_models ADD COLUMN protocol VARCHAR(40);
UPDATE site_discovered_models SET protocol = (
  SELECT p.protocol FROM site_protocol_configs AS p
  WHERE p.id = site_discovered_models.protocol_config_id
);

-- Step 3: 冲突检测（abort if any rows returned）
SELECT site_id, base_url_id, credential_id, COUNT(*) AS row_count,
  COUNT(DISTINCT CAST(enabled AS TEXT)||'|'||headers_json||'|'||channel_proxy||'|'||param_override||'|'||match_regex) AS variants
FROM site_protocol_configs GROUP BY site_id, base_url_id, credential_id
HAVING COUNT(*) > 1 AND variants > 1;

-- Step 4: 模型组迁移到复合 ID
UPDATE model_group_items SET channel_id = (
  SELECT m.combo_id || '_' || m.protocol FROM combo_migration_map AS m
  WHERE m.old_id = model_group_items.channel_id
);
```

---

## 前端分析（Gemini）摘要

### 核心结论
- 地址协议多选：**推荐 ToggleGroup**（方案C）— 6个协议选项有限，一目了然，无需下拉
- `FormProtocol` 重命名为 `FormCombo`，`FormState.protocols` → `FormState.combos`
- 组合表单去掉协议下拉，三列布局 → 两列

### 类型变更要点
```typescript
type FormBaseUrl = Omit<SiteBaseUrlInput, "id"> & {
  id: string;
  compatible_protocols: ProtocolKind[]; // 新增
};

type FormCombo = {  // 原 FormProtocol
  id?: string | null;
  // protocol: ProtocolKind; ← 移除
  enabled: boolean;
  base_url_id: string;
  credential_id: string;
  models: SiteModelInput[];
  headers: HeaderItem[];
  channel_proxy: string;
  param_override: string;
  match_regex: string;
  manual_model_name: string;
  expanded: boolean;
};
```

### 模型聚合视图
```typescript
function useAggregatedModels(combos: FormCombo[], baseUrls: FormBaseUrl[]) {
  return useMemo(() => {
    const aggregate: Record<string, { protocols: Set<ProtocolKind>; sources: Set<string> }> = {};
    combos.forEach((combo, index) => {
      if (!combo.enabled) return;
      const baseUrl = baseUrls.find(b => b.id === combo.base_url_id);
      if (!baseUrl) return;
      combo.models.forEach(model => {
        if (!aggregate[model.model_name]) {
          aggregate[model.model_name] = { protocols: new Set(), sources: new Set() };
        }
        baseUrl.compatible_protocols.forEach(p => aggregate[model.model_name].protocols.add(p));
        aggregate[model.model_name].sources.add(`组合 ${index + 1}`);
      });
    });
    return aggregate;
  }, [combos, baseUrls]);
}
```

### UX 注意事项
1. 新增 Helper Text："组合用于将地址与密钥绑定，具体兼容协议由所选地址决定"
2. 地址无兼容协议时，聚合视图对应模型显示 ⚠ 警告
3. i18n: `组合`/`Combo`, `兼容协议`/`Compatible Protocols`, `模型总览`/`Model Overview`

---

## 综合决策

### 已确定的设计决策
1. **方案 A** 保守落地，不引入新关联表
2. **复合 ChannelConfig.id** = `f"{combo.id}_{protocol.value}"`（运行时构造，不落库主键）
3. **`SiteDiscoveredModelEntity` 新增 `protocol` 列**（关键！）
4. **`SiteModelFetchItem` 新增 `protocol` 字段**（关键！）
5. **迁移时冲突检测**：发现冲突立即 abort，不静默合并
6. **Downgrade 不支持**（与现有迁移一致）
7. **ToggleGroup** 用于地址协议多选
8. **`channel_id` 列扩至 `String(160)`**

### 还需澄清的问题（已在 plan 中处理）
- `request_logs.channel_id` 是否迁移旧历史数据？→ 决定：迁移（保持历史摘要连续）
- `domain_store.py` 的 `can_reach_protocol()` 保留不变（保持 openai_chat → anthropic 可达能力）
