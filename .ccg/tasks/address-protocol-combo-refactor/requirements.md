# 需求文档：地址多协议声明 + 组合概念重构

## 需求完整性评分：10/10 ✅

## 目标

将 Lens 渠道配置从"三合一"（protocol + address + key）改为"二合一"：
- **地址（SiteBaseUrl）** 声明该地址支持哪些协议（`compatible_protocols`）
- **组合（原 SiteProtocolConfig）** = 地址绑定 + 密钥绑定，不再含 `protocol` 字段

## 当前架构（问题）

```
SiteProtocolConfigEntity {
  id, site_id,
  protocol,         ← 每条配置绑死一个协议
  base_url_id,
  credential_id,
  ...
}
```

用户必须为同一地址+密钥的每个协议重复创建一条配置，管理碎片化。

## 目标架构

```
SiteBaseUrlEntity {
  id, site_id, url, name,
  compatible_protocols_json  ← 新增：["openai_chat", "anthropic", ...]
}

SiteProtocolConfigEntity {
  id, site_id,
  # protocol 字段移除
  base_url_id,
  credential_id,
  ...
}
```

`_flatten_site()` 展开逻辑：
```
for combo in site.protocols:
    address = combo.base_url_id → SiteBaseUrl
    for protocol in address.compatible_protocols:
        yield ChannelConfig(id=f"{combo.id}:{protocol}", protocol=protocol, ...)
```

## 五个子目标

### 1. 地址新增"兼容协议"多选字段
- `SiteBaseUrlEntity.compatible_protocols_json`（Text, default="[]"）
- `SiteBaseUrl.compatible_protocols: list[ProtocolKind]`
- `SiteBaseUrlInput.compatible_protocols: list[ProtocolKind]`
- UI：地址编辑区新增多选 checkbox

### 2. 组合概念（移除 protocol 字段）
- `SiteProtocolConfigEntity` 去掉 `protocol` 列（需 Alembic migration）
- `SiteProtocolConfig.protocol` 字段删除
- `SiteProtocolConfigInput.protocol` 字段删除
- UI：协议配置表单中去掉"协议"下拉，UI 标签改为"组合"
- 去重逻辑：由 (protocol, base_url_id, credential_id) → (base_url_id, credential_id)

### 3. Get Models 按协议展开
- `SiteModelFetchRequest` 去掉 `protocol`（或改为按地址推导）
- `SiteModelFetchItem` 新增 `protocol: ProtocolKind`
- 后端：fetch_models 对每个模型 × 地址兼容协议 → 展开多条
- API: `POST /api/admin/site-model-discoveries` 返回结构变化

### 4. 渠道前端模型聚合视图
- 渠道详情页新增区域：按模型名聚合，展示"支持协议"和"来源组合"
- 去重和聚合在前端完成（纯计算，无新 API）

### 5. 模型创建时的渠道匹配
- `POST /api/admin/model-group-candidates` 现有接口，结果展示协议来源
- 前端 groups-screen 显示候选时展示组合的协议覆盖情况

## 约束

- **向下兼容**：已有数据需通过 Alembic migration 迁移
  - 迁移策略：从现有 `SiteProtocolConfigEntity.protocol` 反推到对应的 `SiteBaseUrlEntity.compatible_protocols_json`
  - 即：若某地址有多条不同 protocol 的协议配置 → 合并到地址的 compatible_protocols
- **路由层不变**：`router.py` 的 `channel.protocol` 过滤逻辑不改，通过展开 ChannelConfig 保持兼容
- **暂不含逆向协议转换**

## 变更影响链

```
DB schema
  → entities.py (SiteBaseUrlEntity, SiteProtocolConfigEntity)
  → models.py (SiteBaseUrl, SiteProtocolConfig, SiteModelFetchRequest/Item)
  → channel_store.py (_flatten_site, _upsert_protocols, fetch_models_preview)
  → api/routes/sites.py (response_model 变化)
  → ui/src/lib/api.ts (类型定义)
  → ui/src/components/screens/channels-screen.tsx (FormState, FormProtocol, UI)
  → ui/src/components/screens/groups-screen.tsx (候选视图)
```

## ChannelConfig ID 策略（重要决策点）

当前：`ChannelConfig.id = SiteProtocolConfigEntity.id`（一对一）

重构后：一个 combo 展开为 N 个 ChannelConfig（N = 地址兼容协议数量）
- 方案 A：`id = f"{combo.id}_{protocol.value}"`（复合 ID）
- 方案 B：`id = combo.id`，多个 ChannelConfig 共享同一 id（会破坏路由唯一性）
- **推荐方案 A**：复合 ID 保持路由 ID 唯一性

## 验收标准

1. 可以在地址上通过多选界面选择多个兼容协议
2. 新建"组合"时只需选地址和密钥，不需要指定协议
3. 同一地址+密钥的组合可以自动覆盖该地址支持的所有协议
4. Get Models 对单个组合返回多条（模型 × 协议）
5. 渠道详情页有模型聚合视图
6. 已有数据迁移后正常工作
7. 路由系统行为不变（通过展开后的 ChannelConfig 保持）
