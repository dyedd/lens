# 需求文档：模型组多协议声明 + 协议兼容/转换路径（groups 侧对称扩展）

## 关联背景

前一任务 [`address-protocol-combo-refactor`](../address-protocol-combo-refactor/requirements.md) 已落地（commits `7d14117..cf466a1`）：
- **地址（`SiteBaseUrl`）** 现在声明 `compatible_protocols`（一个地址可同时声明支持的协议集合）
- **组合（`SiteProtocolConfig`）** = 地址 + 密钥绑定（移除了原 `protocol` 字段）
- 渠道侧已经是"按地址兼容协议展开多个 ChannelConfig"的模型

**本任务是 groups 侧的对称扩展**：让模型组也能在创建/编辑时多选协议，与渠道侧的多协议声明配套使用。

## 目标

将"创建模型组"的协议选择从**单选**升级为**多选**，并明确地复用底层已有的**协议转换矩阵**（`gateway/converters/__init__.py: _SUPPORTED_CONVERSIONS`），让用户能用一个模型组（如 `GPT-5.5`）同时对外提供多个协议入口（OpenAI Chat / OpenAI Responses / Anthropic / ...），而无需复制创建。

## 当前架构（问题）

```
ModelGroup {
  id, name,
  protocol: ProtocolKind,      ← 单选，每个 group 绑死一个对外协议
  strategy, route_group_id, ...,
  items: list[ModelGroupItem]  ← 每项有 protocol（来自候选渠道）
}

POST /api/admin/model-group-candidates { protocol } → 单协议候选
```

### 痛点
1. 用户为 `GPT-5.5` 想同时支持 OpenAI Chat + OpenAI Responses + Anthropic 入口时，必须创建 3 份模型组（名字相同但 protocol 不同），管理碎片化、价格重复维护
2. 已有的协议转换矩阵（OpenAI Chat 渠道可服务 Anthropic/Responses 请求）能力**没有在 group 这一层得到表达**
3. 列表筛选 `protocolFilter` 只能按单协议过滤，无法表达"这个 group 同时支持哪些协议"

### 后端基础能力（已就绪 ✓）

`lens_api/gateway/converters/__init__.py`：
```python
_SUPPORTED_CONVERSIONS = {
  (OPENAI_CHAT, ANTHROPIC),         # OpenAI Chat 渠道 → 服务 Anthropic 请求
  (OPENAI_CHAT, OPENAI_RESPONSES),  # OpenAI Chat 渠道 → 服务 Responses 请求
}

can_reach_protocol(channel_protocol, group_protocol) -> bool
needs_conversion(client_protocol, channel_protocol) -> bool
convert_request / convert_response / convert_stream_iterator
```

`lens_api/persistence/domain_store.py: list_group_candidates` 已经按 `can_reach_protocol(ch.protocol, payload.protocol)` 过滤候选 — **协议兼容判定已在用，只是入口被局限到了单协议**。

## 目标架构

```
ModelGroup {
  id, name,
  protocols: list[ProtocolKind],    ← 多选（至少 1 项）
  strategy, route_group_id, ...,
  items: list[ModelGroupItem]       ← 每项的 protocol 不变（来自候选渠道）
}

POST /api/admin/model-group-candidates {
  protocols: list[ProtocolKind]      ← 多协议查询
}
```

### 候选过滤规则（保留单向转换路径）

候选的 channel 满足：
```
∃ p ∈ payload.protocols, can_reach_protocol(channel.protocol, p) == True
```
即只要该渠道能为 **任一** 用户所选协议提供服务（自身原生 OR 通过已注册的转换），即为候选。

### 运行时路由规则

客户端协议 `P` 命中模型组 `G`（通过 `name → group` 解析），要求：
1. `P in G.protocols` （否则 404 / 不存在）
2. 在 `G.items` 中筛选 `can_reach_protocol(item.protocol, P) == True` 的子集
3. 按 `G.strategy` 选 primary + fallbacks（仍由 router.py 处理，传入 protocol=P）

> 现在 router.py 已经按 protocol 过滤 `active = _build_active_pool(channels, protocol, ...)`，所需扩展是路由前 protocol 必须在 group.protocols 内。

## 五个子目标

### 1. 后端数据模型
- `ModelGroupEntity.protocols_json: Text default '[]'`（Alembic migration 替换原 `protocol` 列）
- `ModelGroup.protocols: list[ProtocolKind] = Field(min_length=1)`（pydantic）
- `ModelGroupCreate.protocols`、`ModelGroupUpdate.protocols`、`ModelGroupItem`（保留 protocol 不变）
- `ModelGroupCandidatesRequest.protocols: list[ProtocolKind]`（替换原 `protocol`）

### 2. 候选 API 多协议过滤
- `domain_store.list_group_candidates`：循环判断 `any(can_reach_protocol(ch.protocol, p) for p in protocols)`
- 返回结果中每个 `ModelGroupCandidateItem.protocol` 仍是 channel 原生协议（用户在 UI 上能看到"这个候选源会被用于哪些组的协议"）

### 3. 网关运行时
- 入站请求映射 group 时：从所有 group 中找 `name == request_model AND protocol in group.protocols` 的；多个 group 命中需保留现有去歧规则（如优先非 route_group）
- 路由层：构造 active pool 时同样按 `can_reach_protocol(item.protocol, request_protocol)` 过滤

### 4. 前端 groups-screen UI
- `FormState.protocol → protocols: ProtocolKind[]`（多选 checkbox，至少 1 项）
- 默认 `["openai_chat"]`
- 创建表单顶部新增"对外协议"多选区域
- 候选区域提示该候选源能服务哪些已选协议（如 `Anthropic（转换自 OpenAI Chat）` 之类的徽标）
- 列表卡片用 badge 阵列展示 group.protocols（替换原单 protocol badge）
- `protocolFilter`：列表筛选改为 `protocols.includes(filter)`
- `changeProtocol` → `toggleProtocol`：切换协议时不清空 items（与之前的清空逻辑相反 — 多协议下 items 不应被清空，除非用户主动剔除）；切换协议改变候选池

### 5. 路由组对接 + 价格
- `routeTargetOptions`：路由目标组必须**包含**当前组的所有协议（`current.protocols ⊆ target.protocols`），否则不可选
- 价格保持单一份（不按协议拆分）— 现有 `ModelPriceItem.protocols: list[ProtocolKind]` 字段已经是多协议结构，落地时填入 group.protocols 即可

## 约束

- **向前兼容数据**：Alembic migration 必须把现有 `protocol` 单字段平滑转为 `protocols = [protocol]`
- **零行为破坏**：单协议用户的体验等价于今天（多协议是可选能力）
- **复用现有转换矩阵**：不引入新协议对，未来要加新转换路径只改 `_SUPPORTED_CONVERSIONS` 一处
- **API 兼容**：`POST /api/admin/model-groups` payload 字段名 `protocol → protocols` 是破坏性变更，但前后端同一仓库内可同步切换；不保留旧字段
- **测试覆盖**：必须包含 router.py 在多协议场景下的路由验证、candidates 接口的过滤验证、网关协议命中验证

## 验收标准

1. ✅ 创建 group `GPT-5.5`，多选 OpenAI Chat + OpenAI Responses + Anthropic
2. ✅ 候选区显示能服务这三个协议的所有 channel 来源（包括通过转换覆盖的）
3. ✅ 保存后，三个协议入口都能命中该 group：
   - `POST /v1/chat/completions` model=GPT-5.5 → OK
   - `POST /v1/responses` model=GPT-5.5 → OK
   - `POST /v1/messages` model=GPT-5.5 → OK
4. ✅ 列表筛选选择"Anthropic" → 显示包含 Anthropic 的所有 group（包括 GPT-5.5）
5. ✅ 现有单协议 group 继续工作（迁移后等价）
6. ✅ Alembic migration 双向（upgrade/downgrade）都能跑通
7. ✅ 关键单元测试通过 + 现有测试套件不被破坏

## 待 Phase 2 多模型构思的开放问题

1. **同名跨协议合并**：用户为同一名 `GPT-5.5` 创建两个 group（一个含 Chat，一个含 Anthropic）。前端是否合并显示？还是后端在创建/更新时主动合并？
   - 倾向：API 层禁止"name 已存在且 protocols 有交集"的重复创建，并主动建议"合并到现有组"
2. **route_group 限制**：路由目标必须 `current.protocols ⊆ target.protocols` 还是只需有交集即可？
   - 倾向：必须包含（严格），防止运行时找不到对应协议入口
3. **candidates 显示策略**：每个候选源是否区分"原生提供"vs"通过转换提供"？UI 怎么呈现？
   - 倾向：每个候选只显示 channel 的原生 protocol（一个 badge），并在 hover 上提示"通过转换覆盖：A → B"
4. **`ModelGroupItem.protocol` 字段**：保留还是移除？
   - 倾向：保留（运行时路由需要原生协议来判断是否要转换；也保证 fallback 数据完整性）

## 需求完整性评分

按 0-10 体系自评：

| 维度 | 评分 | 说明 |
|------|------|------|
| 目标明确性 (0-3) | **3** | "单选→多选"的语义清晰，与前任务地址多协议对称 |
| 预期结果 (0-3) | **3** | 5 个验收标准可机检 |
| 边界范围 (0-2) | **2** | 模型/路由/UI 三层都已划定 |
| 约束条件 (0-2) | **2** | 兼容性、迁移、API、测试覆盖均列明 |
| **总分** | **10/10** | 4 个开放问题留给 Phase 2 多模型对比 |

**结论：评分 ≥ 7，可进入 Phase 2 多模型构思。**
