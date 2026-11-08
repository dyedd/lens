# 客户端接入

客户端需要三个值：Lens 地址、网关 API Key、模型组名称。管理员登录令牌和上游服务商的 Key 都不应填到客户端。

## 创建网关 Key

打开 **设置 → 网关密钥**，点击 **创建网关密钥**：

1. 填写用途备注。
2. 按需限制可用模型组、费用上限和有效期。
3. 创建后复制 Key，填入客户端的 API Key 项。

![网关密钥列表中的模型权限、费用上限和启停状态](/images/api-keys.png)

客户端的 `model` 必须是 Lens 中已有的模型组名称。先确认组里有可用成员。默认部署地址是 `http://127.0.0.1:3000`；远程部署时换成实际域名。

例如，可建立 `gpt-6.1-sol`、`claude-opus-5-5` 同名组，也可以通过 `daily-chat` 别名引用执行组。下面的 `your-model-group` 等占位名称都应替换为自己的组名。使用 GPT-6.1 Sol 的工具调用时，客户端和上游均选择 [Responses API](https://developers.openai.com/api/docs/models/gpt-6.1-sol)。

| 客户端接口 | Base URL / 请求路径 |
| --- | --- |
| OpenAI SDK | Base URL 为 `http://127.0.0.1:3000/v1` |
| Anthropic SDK | Base URL 为 `http://127.0.0.1:3000` |
| Chat Completions | `POST /v1/chat/completions` |
| Responses | `POST /v1/responses` |
| Anthropic Messages | `POST /v1/messages` |
| Gemini | `POST /v1beta/models/{模型组}:generateContent` |
| Embeddings | `POST /v1/embeddings` |
| Images | `POST /v1/images/generations` 或 `/v1/images/edits` |
| Rerank | `POST /v1/rerank` |

## 先验证模型列表

以下 curl 示例适用于 Bash。将示例 Key 换成自己的网关 Key：

```bash
curl http://127.0.0.1:3000/v1/models \
  -H "Authorization: Bearer sk-lens-..."
```

返回的模型列表受 Key 的模型权限限制。选择可用模型组后，发送一次简单请求。

## OpenAI Chat

```bash
curl http://127.0.0.1:3000/v1/chat/completions \
  -H "Authorization: Bearer sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-model-group",
    "messages": [{"role": "user", "content": "hello"}]
  }'
```

PowerShell 7 可使用：

```powershell
$headers = @{ Authorization = "Bearer sk-lens-..." }
$body = @{
    model = "your-model-group"
    messages = @(@{ role = "user"; content = "hello" })
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Uri "http://127.0.0.1:3000/v1/chat/completions" -Method Post -Headers $headers -ContentType "application/json" -Body $body
```

Python 客户端安装 `openai` SDK 后：

```python
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

`LENS_API_KEY` 是这里给客户端使用的环境变量，不是 Lens 服务端的启动配置。

## OpenAI Responses

```bash
curl http://127.0.0.1:3000/v1/responses \
  -H "Authorization: Bearer sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{"model":"your-model-group","input":"hello"}'
```

对话接口支持流式输出。在请求体中设置 `"stream": true`，使用 curl 时加上 `-N` 以便即时显示事件。

## Anthropic Messages

```bash
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

Python 客户端安装 `anthropic` SDK 后：

```python
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

## Gemini

```bash
curl "http://127.0.0.1:3000/v1beta/models/your-gemini-group:generateContent" \
  -H "x-goog-api-key: sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{"contents":[{"role":"user","parts":[{"text":"hello"}]}]}'
```

流式请求使用 `streamGenerateContent`。路径中的模型组名称应进行 URL 编码；简单的字母、数字与连字符名称无需额外处理。

## 向量、图像与重排

这些接口需要对应能力的模型组，不会自动把普通对话模型变成向量或图像模型。

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

图片编辑还支持 multipart 上传；图像接口支持 JSON 请求和 `stream: true` 事件流。图像单价在价格配置中按张设置。

Rerank 转发到上游的 `/v1/rerank`。使用 Cohere v2 时，按服务商要求配置带 `/v2` 的上游 Base URL。

## Codex

在 `~/.codex/config.toml` 中选择自定义提供商。将模型名替换为实际可用的 Lens 模型组：

```toml
model = "your-model-group"
model_provider = "lens"

[model_providers.lens]
name = "Lens"
base_url = "http://127.0.0.1:3000/v1"
env_key = "LENS_API_KEY"
wire_api = "responses"
```

启动 Codex 的终端需要设置 `LENS_API_KEY`。例如 PowerShell：

```powershell
$env:LENS_API_KEY = "sk-lens-..."
codex
```

这里使用 Responses 接口和环境变量认证。先验证简单 Responses 请求，再验证工具调用和流式输出。提供商配置以 [Codex 官方说明](https://learn.chatgpt.com/docs/config-file/config-advanced#custom-model-providers) 为准。

## Claude Code

选择包含 Claude 上游的模型组，在启动终端设置网关地址、Key 和模型。例如 PowerShell：

```powershell
$env:ANTHROPIC_BASE_URL = "http://127.0.0.1:3000"
$env:ANTHROPIC_AUTH_TOKEN = "sk-lens-..."
$env:ANTHROPIC_MODEL = "your-claude-group"
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL = "your-small-claude-group"
claude
```

两个模型组都需要提前配置。若只配置一个组，可以让这两个变量使用同一个名称。需要固定 Sonnet / Opus 别名时，再设置 `ANTHROPIC_DEFAULT_SONNET_MODEL` / `ANTHROPIC_DEFAULT_OPUS_MODEL`。

这些变量控制请求地址、认证和模型选择，详见 [Claude Code 环境变量](https://code.claude.com/docs/en/env-vars) 与 [模型配置](https://code.claude.com/docs/en/model-config)。

## 确认请求结果

成功后打开 **请求日志**，确认模型组、实际渠道和用量。常见问题的排查步骤见 [查看用量与排查请求](./monitoring)。
