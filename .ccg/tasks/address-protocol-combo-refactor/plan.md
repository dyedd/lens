# 实施计划：地址多协议声明 + 组合概念重构

## 架构决策摘要

| 决策 | 选定方案 |
|------|---------|
| 复合 Channel ID | `f"{combo.id}_{protocol.value}"` — 运行时构造，不落 DB 主键 |
| 发现模型协议维度 | `SiteDiscoveredModelEntity` 新增 `protocol` 列（关键！） |
| 地址协议 UI | ToggleGroup（横向 badge 式多选） |
| 迁移冲突处理 | 检测到冲突 → abort，要求人工拆分 |
| Downgrade | `raise NotImplementedError` |
| 旧备份向后兼容 | 备份导入时自动转换旧 `protocol` 字段到地址 `compatible_protocols` |
| DomainStore 访问展开 channels | 在方法内按需创建 `ChannelStore` 实例 |

---

## 变更分层（Layer = 执行依赖顺序）

### Layer 0 — DB 迁移（无代码依赖）

**文件**：`migrations/versions/{timestamp}_address_protocols_combo_refactor.py`（新建）

**Upgrade 步骤**（顺序执行）：

1. `site_base_urls` ADD `compatible_protocols_json TEXT NOT NULL DEFAULT '[]'`
2. `site_discovered_models` ADD `protocol VARCHAR(40)` (nullable)
3. **Back-fill 地址协议**（从旧 protocol_configs 汇总）：
   ```sql
   UPDATE site_base_urls AS b SET compatible_protocols_json = COALESCE(
     (SELECT json_group_array(protocol) FROM (
       SELECT DISTINCT p.protocol FROM site_protocol_configs p
       WHERE p.site_id = b.site_id AND p.base_url_id = b.id ORDER BY p.protocol
     )), '[]'
   );
   ```
4. **Back-fill 发现模型协议**：
   ```sql
   UPDATE site_discovered_models SET protocol = (
     SELECT p.protocol FROM site_protocol_configs p WHERE p.id = site_discovered_models.protocol_config_id
   );
   ```
5. **冲突检测**（有结果则 raise + 中止）：
   ```sql
   SELECT site_id, base_url_id, credential_id, COUNT(*) AS n,
     COUNT(DISTINCT CAST(enabled AS TEXT)||'|'||headers_json||'|'||channel_proxy||'|'||param_override||'|'||match_regex) AS variants
   FROM site_protocol_configs GROUP BY site_id, base_url_id, credential_id
   HAVING n > 1 AND variants > 1;
   ```
6. **创建 combo 迁移映射**（临时表）：
   ```sql
   CREATE TEMP TABLE combo_migration_map AS
   SELECT id AS old_id,
     MIN(id) OVER (PARTITION BY site_id, base_url_id, credential_id) AS combo_id,
     site_id, base_url_id, credential_id, protocol
   FROM site_protocol_configs;
   ```
7. **更新发现模型** → 指向 canonical combo_id：
   ```sql
   UPDATE site_discovered_models SET protocol_config_id = (
     SELECT m.combo_id FROM combo_migration_map m WHERE m.old_id = site_discovered_models.protocol_config_id
   );
   ```
8. **更新模型组 channel_id** → 复合 ID：
   ```sql
   UPDATE model_group_items SET channel_id = (
     SELECT m.combo_id || '_' || m.protocol FROM combo_migration_map m WHERE m.old_id = model_group_items.channel_id
   ) WHERE channel_id IN (SELECT old_id FROM combo_migration_map);
   ```
9. **更新请求日志 channel_id** → 复合 ID：
   ```sql
   UPDATE request_logs SET channel_id = (
     SELECT m.combo_id || '_' || m.protocol FROM combo_migration_map m WHERE m.old_id = request_logs.channel_id
   ) WHERE channel_id IN (SELECT old_id FROM combo_migration_map);
   ```
10. **删除重复 combo rows**（保留 canonical）：
    ```sql
    DELETE FROM site_protocol_configs WHERE id IN (
      SELECT old_id FROM combo_migration_map WHERE old_id != combo_id
    );
    ```
11. **批量操作移除 protocol 列**（SQLite via `batch_alter_table`）：
    ```python
    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.drop_index("ix_site_protocol_configs_protocol")
        batch_op.drop_column("protocol")
    ```

**Downgrade**：
```python
def downgrade() -> None:
    raise NotImplementedError(
        "Downgrade not supported: protocol configs were merged into combos"
    )
```

---

### Layer 1a — `lens_api/persistence/entities.py`

变更点：
- `SiteBaseUrlEntity`：ADD `compatible_protocols_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")`
- `SiteProtocolConfigEntity`：REMOVE `protocol: Mapped[str]` 及其 `index=True`
- `SiteDiscoveredModelEntity`：ADD `protocol: Mapped[str | None] = mapped_column(String(40), nullable=True)`
- `ModelGroupItemEntity.channel_id`：`String(80)` → `String(160)`
- `RequestLogEntity.channel_id`：`String(80)` → `String(160)`

---

### Layer 1b — `lens_api/models.py`

变更点：
- `SiteBaseUrl`：ADD `compatible_protocols: list[ProtocolKind] = Field(default_factory=list)`
- `SiteBaseUrlInput`：ADD `compatible_protocols: list[ProtocolKind] = Field(default_factory=list)`
- `SiteProtocolConfig`：REMOVE `protocol: ProtocolKind`
- `SiteProtocolConfigInput`：
  - REMOVE `protocol: ProtocolKind`
  - ADD `protocol: ProtocolKind | None = None`（保留为可选 deprecated 字段，供旧备份兼容；保存时忽略）
- `SiteModel`：ADD `protocol: ProtocolKind | None = None`
- `SiteModelInput`：ADD `protocol: ProtocolKind | None = None`
- `SiteModelFetchRequest`：REMOVE `protocol: ProtocolKind`；ADD `compatible_protocols: list[ProtocolKind] = Field(default_factory=list)`
- `SiteModelFetchItem`：ADD `protocol: ProtocolKind`

---

### Layer 2a — `lens_api/persistence/channel_store.py`

变更点：

**1. `_flatten_site()`** — 核心重构
```python
def _flatten_site(self, site: SiteConfig) -> list[ChannelConfig]:
    credentials_by_id = {item.id: item for item in site.credentials}
    base_urls_by_id = {item.id: item for item in site.base_urls}
    items = []
    for combo in site.protocols:
        bound_base_url = base_urls_by_id.get(combo.base_url_id)
        if bound_base_url is None:
            raise ValueError(...)
        protocols = bound_base_url.compatible_protocols
        if not protocols:
            continue
        keys = self._build_channel_keys(combo, credentials_by_id)
        if not keys:
            continue
        active_key = next((k for k in keys if k.enabled), keys[0])
        for protocol in protocols:
            protocol_models = [m for m in combo.models if m.protocol == protocol or m.protocol is None]
            items.append(ChannelConfig(
                id=f"{combo.id}_{protocol.value}",
                name=site.name,
                protocol=protocol,
                base_url=bound_base_url.url,
                api_key=active_key.key,
                status=ChannelStatus.ENABLED if combo.enabled else ChannelStatus.DISABLED,
                headers=combo.headers,
                model_patterns=[m.model_name for m in protocol_models if m.enabled],
                keys=keys,
                models=self._build_channel_models(combo, credentials_by_id, protocol),
                channel_proxy=combo.channel_proxy,
                param_override=combo.param_override,
                match_regex=combo.match_regex,
            ))
    return items
```

**2. `_build_channel_models()`** — 增加 `protocol` 过滤参数

**3. `_group_base_urls()`** — 反序列化 `compatible_protocols_json`

**4. `_upsert_base_urls()`** — 保存 `compatible_protocols_json`

**5. `_normalize_base_urls()`** — 处理 `compatible_protocols`，去重规范化

**6. `_group_protocols()`** — 移除 `protocol=row.protocol`（entity 已无此列）

**7. `_group_models()`** — 读取 `row.protocol`（nullable），传给 `SiteModel.protocol`

**8. `_upsert_protocols()` 去重逻辑** — 改为 `(base_url_id, credential_id)` 唯一键

**9. `_upsert_protocol_models()`** — 保存 `protocol` 到 `SiteDiscoveredModelEntity`

**10. `_upsert_site_payload()` 验证** — 移除 `if not protocols: raise ValueError`；改为验证启用的 combo 必须有对应地址有 `compatible_protocols`

**11. `fetch_models_preview()`** — 改为按 `compatible_protocols` 迭代，每个协议独立拉取，返回含 `protocol` 的多条 `SiteModelFetchItem`

**新增辅助函数**：
```python
@staticmethod
def _composite_channel_id(combo_id: str, protocol_value: str) -> str:
    return f"{combo_id}_{protocol_value}"
```

---

### Layer 2b — `lens_api/persistence/domain_store.py`

**新增辅助函数**：
```python
def _parse_composite_channel_id(channel_id: str) -> tuple[str, ProtocolKind] | None:
    for protocol in ProtocolKind:
        suffix = f"_{protocol.value}"
        if channel_id.endswith(suffix):
            return channel_id[:-len(suffix)], protocol
    return None
```

**1. `list_group_candidates()`** — 完全重写，改用展开 channels：
```python
async def list_group_candidates(self, payload) -> ModelGroupCandidatesResponse:
    channel_store = ChannelStore(self._session_factory)
    channels = await channel_store.list()
    # filter by protocol if needed (保留 can_reach_protocol 逻辑)
    # build candidates from channel.models
    ...
```

**2. `_validate_group_payload()`** — 改用展开 channels 验证：
- 不再查 `SiteProtocolConfigEntity.id.in_(channel_ids)`
- 改为：load 展开 channels，build `channel_by_id` dict，验证每个 `item.channel_id` 存在于其中
- 验证 protocol 可达：`can_reach_protocol(channel.protocol, group_protocol)` 不变
- 验证模型存在：从 `channel.models` 直接查找（已在 ChannelConfig 中）

**3. `_load_channel_protocols()`** — 改为从复合 ID 提取（无 DB 查询）：
```python
async def _load_channel_protocols(self, session, channel_ids):
    result = {}
    for cid in channel_ids:
        parsed = self._parse_composite_channel_id(cid)
        if parsed:
            result[cid] = parsed[1]
    return result
```

**4. `_load_channel_site_names()`** — 提取 combo_id 后查 `SiteProtocolConfigEntity.id`（entity 仍以 combo_id 为主键）

**5. `_load_credential_names_by_channel()`** — 同上，用 combo_id 查询

**6. `_load_credential_numbers_by_channel()`** — 同上

---

### Layer 3 — `lens_api/persistence/backup_store.py`

变更点：

**导入时旧备份兼容处理**：在 `_replace_sites()` 中，如果 `protocol_config.protocol` 不为 None（旧备份格式）：
- 对每个 protocol_config，读取其 `protocol` 并将其加入对应 base_url 的 `compatible_protocols`（如果 base_url 的 `compatible_protocols` 为空）
- 然后以 combo 方式保存（不传 protocol 给实体）

具体改动：
- 移除 `protocol=protocol.protocol.value` from `SiteProtocolConfigEntity(...)` 构造
- 移除 `SiteProtocolConfigEntity` 排序中的 `SiteProtocolConfigEntity.protocol.asc()`（查询改 `id.asc()`）
- 导出时，`SiteProtocolConfig` 已无 `protocol` 字段，自动正确
- 导入时，遇到旧格式 `protocol.protocol` 不为 None：将 protocol 合并到 base_url 的 `compatible_protocols` set

`service.py`：**不需要修改**。展开后的 `ChannelConfig` 已包含 `protocol`，`channel_map` 键为复合 ID，与迁移后的 `model_group_items.channel_id` 匹配。

---

### Layer 4a — `ui/src/lib/api.ts`

TypeScript 类型变更：
- `SiteBaseUrl` / `SiteBaseUrlInput`：ADD `compatible_protocols: ProtocolKind[]`
- `SiteProtocolConfig`：REMOVE `protocol: ProtocolKind`
- `SiteProtocolConfigInput`：REMOVE `protocol: ProtocolKind`
- `SiteModelFetchPayload`：REMOVE `protocol`；ADD `compatible_protocols: ProtocolKind[]`
- `SiteModelFetchItem`：ADD `protocol: ProtocolKind`
- `SiteModelInput`：ADD `protocol?: ProtocolKind | null`

---

### Layer 4b — `ui/src/components/screens/channels-screen.tsx`

**类型变更**：
```typescript
type FormBaseUrl = Omit<SiteBaseUrlInput, "id"> & {
  id: string;
  compatible_protocols: ProtocolKind[];  // 新增
};

type FormCombo = {    // 原 FormProtocol
  id?: string | null;
  // protocol 字段移除
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

type FormState = {
  name: string;
  base_urls: FormBaseUrl[];
  credentials: FormCredential[];
  combos: FormCombo[];   // 原 protocols
};
```

**组件变更**：
- `emptyCombo()` — 原 `emptyProtocol()`，移除 `protocol` 字段
- `emptyForm()` → `combos: [emptyCombo(baseUrlId)]`
- `ProtocolConfigItem` → `ComboConfigItem`：
  - 移除"协议"下拉列（`NativeSelect` for protocol）
  - 三列 grid → 二列 grid：`xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_32px_auto]`
  - Section label: "协议配置" → "组合" / "Combos"
- **地址编辑区新增 ToggleGroup**（每个地址下方）：
  ```tsx
  <ToggleGroup type="multiple" value={baseUrl.compatible_protocols}
    onValueChange={(vals) => updateBaseUrl(idx, { compatible_protocols: vals })}>
    {protocolOptions.map(opt => (
      <ToggleGroupItem key={opt.value} value={opt.value}
        className="h-7 px-3 text-xs rounded-full border ...">
        {opt.label}
      </ToggleGroupItem>
    ))}
  </ToggleGroup>
  ```
- `toForm()` — 映射 `site.protocols` → `FormCombo[]`（无 protocol），`site.base_urls` → `FormBaseUrl[]`（含 compatible_protocols）
- `toPayload()` — 生成 `combos`（无 protocol），`base_urls`（含 compatible_protocols）
- `duplicateProtocolCredentialKeys()` → `duplicateComboKeys()`：新唯一键 `[base_url_id, credential_id].join(":")`
- `onFetchModels()` — 从 `form.base_urls.find(combo.base_url_id).compatible_protocols` 传入 fetch 请求
- **新增组件 `SiteModelAggregateView`**：
  - 使用 `useAggregatedModels(combos, baseUrls)` hook（`useMemo`）
  - 聚合：模型名 → { protocols: Set, sources: Set }
  - 展示：表格，列：模型名 | 协议（badge） | 来源组合
  - 空状态：友好提示文案
  - 放置位置：渠道展开区（site detail panel）内的新 Tab 或独立 section
- Helper text 新增："组合用于将地址与密钥绑定，兼容协议由所选地址决定"
- i18n 新增：`组合`/`Combo`、`兼容协议`/`Compatible Protocols`、`模型总览`/`Model Overview`

---

### Layer 4c — `ui/src/components/screens/groups-screen.tsx`

变更点：
- 候选模型列表已通过 `ModelGroupCandidateItem.protocol` 展示协议（无需大改）
- 确认 `exclude_items` 中的 `channel_id` 使用复合 ID 格式（后端已处理）
- 小修：候选项 `channel_id` 格式显示上无需改动（用户不可见 channel_id）

---

## 文件变更清单

| Layer | 文件 | 类型 | 主要变更 |
|-------|------|------|---------|
| L0 | `migrations/versions/XXX_...py` | **NEW** | DB 迁移 |
| L1a | `lens_api/persistence/entities.py` | MODIFY | 实体结构 |
| L1b | `lens_api/models.py` | MODIFY | Pydantic 模型 |
| L2a | `lens_api/persistence/channel_store.py` | MODIFY | 核心逻辑 |
| L2b | `lens_api/persistence/domain_store.py` | MODIFY | 候选/校验逻辑 |
| L3 | `lens_api/persistence/backup_store.py` | MODIFY | 向后兼容 |
| L4a | `ui/src/lib/api.ts` | MODIFY | TypeScript 类型 |
| L4b | `ui/src/components/screens/channels-screen.tsx` | MODIFY | 主要 UI 重构 |
| L4c | `ui/src/components/screens/groups-screen.tsx` | MODIFY | 候选显示微调 |

---

## 风险与缓解

| 风险 | 级别 | 缓解 |
|------|------|------|
| 旧数据迁移冲突（同地址+密钥，不同配置） | High | 迁移时严格检测，abort + 详细错误信息 |
| 复合 ID 导致 ModelGroup 静默失效 | High | 迁移步骤 8 确保 channel_id 同步更新 |
| 旧备份导入失败 | Medium | `SiteProtocolConfigInput.protocol` optional + 导入转换逻辑 |
| 历史请求日志 channel_id 断联 | Low | 迁移步骤 9 可选执行（已含） |

---

## 测试要点

1. 单 combo 多协议展开 → 产生多个 ChannelConfig，协议独立健康状态
2. 地址无 compatible_protocols → combo 不产生运行时渠道，用户提示
3. 迁移冲突检测 → 发现冲突时 migration 中止，输出哪条数据冲突
4. 模型组旧 channel_id → 迁移后正确映射为复合 ID，路由不断线
5. 备份/恢复循环：导出新格式 → 重新导入 ✓；导入旧格式备份 ✓
6. Get Models 返回含 protocol 字段，按协议展开
7. 渠道模型聚合视图正确汇总多来源
