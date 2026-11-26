# 客户端接入

客户端只需要三个参数即可接入 Lens：**网关地址**、**网关密钥（Gateway Key）** 和 **模型组名称**。

## 第一步：创建网关密钥

进入 **设置 → 网关密钥** 点击 **创建网关密钥**：

1. **用途备注**：填写客户端或项目名，便于后续在请求日志与概览归因中识别。
2. **可用模型组**：留空表示允许调用全部模型组；或显式勾选允许访问的模型组列表（同时影响 `/v1/models` 返回的可见列表）。
3. **费用上限与有效期**：可设置累计美元上限（`max_cost_usd`）与过期时间（`expires_at`），超限或过期后自动拒绝请求（`401`）。
4. **启停控制**：支持随时一键禁用或删除，无需修改上游配置。

![网关密钥列表中的模型权限、费用上限和启停状态](/images/api-keys.png)

## 第二步：了解接口与认证方式

Lens 默认监听 `http://127.0.0.1:3000`（Docker 部署），支持三种网关认证头，可按客户端习惯任选其一：
- `Authorization: Bearer sk-lens-...`
- `x-api-key: sk-lens-...`
- `x-goog-api-key: sk-lens-...`

此外，客户端可携带可选请求头 `x-lens-session-id`（最长 256 字符），用于在开启 **规则隐私** 时隔离不同会话的脱敏占位符恢复映射。

| 协议入口 | 请求路径 | 跨协议转换支持 |
| --- | --- | --- |
| **OpenAI Chat** | `POST /v1/chat/completions` | 支持与 Responses / Anthropic / Gemini 双向转换 |
| **OpenAI Responses** | `POST /v1/responses` | 支持与 Chat / Anthropic / Gemini 双向转换 |
| **Anthropic Messages** | `POST /v1/messages` | 支持与 Chat / Responses / Gemini 双向转换；自动将 `messages` 中的 `system` 角色提升为顶层 `system` |
| **Gemini** | `POST /v1beta/models/{模型组}:generateContent`<br>`POST /v1beta/models/{模型组}:streamGenerateContent` | 支持与 Chat / Responses / Anthropic 双向转换 |
| **Embeddings** | `POST /v1/embeddings` | 仅直通具备向量能力的上游模型 |
| **Images** | `POST /v1/images/generations`<br>`POST /v1/images/edits`（支持 JSON 与 multipart 文件上传） | 仅直通具备图像能力的上游模型 |
| **Rerank** | `POST /v1/rerank` | 仅直通重排上游（上游地址以 `/v2` 结尾时自动适配 Cohere v2） |
| **模型目录** | `GET /v1/models` · `GET /v1beta/models` | 按当前网关密钥权限动态返回可用模型组 |

> [!TIP]
> **同协议零损直通 vs 跨协议转换**：当客户端协议与上游成员协议一致时，Lens 仅替换模型名、规则参数与认证头后**原样转发**，完整保留 Prompt Caching 与服务商特有字段（如 `previous_response_id`）；仅在协议不同时才经过 Unified IR 进行转换。

## 第三步：验证模型列表

```bash
curl http://127.0.0.1:3000/v1/models \
  -H "Authorization: Bearer sk-lens-..."
```

返回的列表中仅包含该网关密钥有权访问、且至少拥有一个就绪成员的模型组。

## SDK 与 API 调用示例

下列示例中的 `your-model-group` 请替换为 Lens 中实际存在的模型组名称；如需要指定推理强度，可附加后缀如 `your-model-group(high)`。

### OpenAI Chat & Responses

::: code-group

```bash [Chat Completions (cURL)]
curl http://127.0.0.1:3000/v1/chat/completions \
  -H "Authorization: Bearer sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-model-group",
    "messages": [{"role": "user", "content": "hello"}]
  }'
```

```python [OpenAI Python SDK]
import os
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:3000/v1",
    api_key=os.environ["LENS_API_KEY"],
)
completion = client.chat.completions.create(
    model="your-model-group",
    messages=[{"role": "user", "content": "hello"}],
)
print(completion.choices[0].message.content)
```

```bash [Responses API (cURL)]
curl -N http://127.0.0.1:3000/v1/responses \
  -H "Authorization: Bearer sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{"model":"your-model-group","input":"hello","stream":true}'
```

```powershell [PowerShell 7]
$headers = @{ Authorization = "Bearer sk-lens-..." }
$body = @{
    model = "your-model-group"
    messages = @(@{ role = "user"; content = "hello" })
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Uri "http://127.0.0.1:3000/v1/chat/completions" `
  -Method Post -Headers $headers -ContentType "application/json" -Body $body
```

:::

### Anthropic Messages

::: code-group

```bash [Anthropic Messages (cURL)]
curl http://127.0.0.1:3000/v1/messages \
  -H "x-api-key: sk-lens-..." \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-anthropic-group",
    "max_tokens": 256,
    "messages": [{"role": "user", "content": "hello"}]
  }'
```

```python [Anthropic Python SDK]
import os
from anthropic import Anthropic

client = Anthropic(
    base_url="http://127.0.0.1:3000",
    api_key=os.environ["LENS_API_KEY"],
)
message = client.messages.create(
    model="your-anthropic-group",
    max_tokens=256,
    messages=[{"role": "user", "content": "hello"}],
)
print(message.content[0].text)
```

:::

### Gemini

```bash
curl "http://127.0.0.1:3000/v1beta/models/your-gemini-group:generateContent" \
  -H "x-goog-api-key: sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{"contents":[{"role":"user","parts":[{"text":"hello"}]}]}'
```

流式输出使用 `:streamGenerateContent`。如果模型组名包含 `/` 等特殊字符，路径段需先做 URL 编码。

### Embeddings / Images / Rerank

::: code-group

```bash [Embeddings]
curl http://127.0.0.1:3000/v1/embeddings \
  -H "Authorization: Bearer sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{"model":"your-embedding-group","input":"hello world"}'
```

```bash [Images]
curl http://127.0.0.1:3000/v1/images/generations \
  -H "Authorization: Bearer sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-image-group",
    "prompt": "a white cat",
    "n": 1,
    "size": "1024x1024"
  }'
```

```bash [Rerank]
curl http://127.0.0.1:3000/v1/rerank \
  -H "Authorization: Bearer sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-rerank-group",
    "query": "What is the capital of France?",
    "documents": ["Paris is the capital of France.", "Berlin is the capital of Germany."],
    "top_n": 1
  }'
```

:::

## 编程工具接入

### Codex

在 `~/.codex/config.toml` 中配置自定义模型提供商（参考 [Codex 官方配置文档](https://learn.chatgpt.com/docs/config-file/config-advanced#custom-model-providers)）：

```toml
model = "your-model-group"
model_provider = "lens"

[model_providers.lens]
name = "Lens"
base_url = "http://127.0.0.1:3000/v1"
env_key = "LENS_API_KEY"
wire_api = "responses"
```

在终端注入环境变量后启动（PowerShell 示例）：

```powershell
$env:LENS_API_KEY = "sk-lens-..."
codex
```

> [!TIP]
> 在模型管理界面可以使用 **测试模型 → Codex 模式** 预先验证上游是否接受 Codex 的 Responses 请求头与载荷格式。

### Claude Code

配置 Anthropic 兼容地址与模型组映射（参考 [Claude Code 环境变量](https://code.claude.com/docs/en/env-vars)）：

::: code-group

```powershell [PowerShell]
$env:ANTHROPIC_BASE_URL = "http://127.0.0.1:3000"
$env:ANTHROPIC_AUTH_TOKEN = "sk-lens-..."
$env:ANTHROPIC_MODEL = "your-claude-group"
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL = "your-small-claude-group"
claude
```

```bash [Bash / Zsh]
export ANTHROPIC_BASE_URL="http://127.0.0.1:3000"
export ANTHROPIC_AUTH_TOKEN="sk-lens-..."
export ANTHROPIC_MODEL="your-claude-group"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="your-small-claude-group"
claude
```

:::

如果只配置了一个模型组，可将 `ANTHROPIC_DEFAULT_HAIKU_MODEL`（以及按需设置的 `SONNET` / `OPUS` 环境变量）指向同一个模型组名。同样建议先在 Lens 中使用 **测试模型 → Claude Code 模式** 验证上游兼容性。
