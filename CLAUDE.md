# Lens 项目协作指南

## 项目简介

Lens 是一个多供应商 LLM 网关，统一处理客户端认证、模型组路由、协议转换、上游调用与故障转移，以及请求和用量日志。

## 开发环境

- Python 3.11 或更高版本，使用 uv 管理后端依赖。
- 前端使用 pnpm。

```bash
uv sync --extra dev --locked
cd ui && pnpm install && cd ..
uv run lens db upgrade
uv run lens dev
```

- 需要单独启动时使用 `uv run lens serve` 和 `cd ui && pnpm dev`。环境变量、部署方式、端口和数据库配置以 `README.md` 为准。
- 每完成一个独立功能点，只有在用户明确要求时才提交 git。
- 每次修改代码后，对你本次修改的文件进行格式化：前端文件使用 npx prettier --write <文件路径>，后端文件使用 black <文件路径>
- 新增路由或修复可复现 bug 时，应包含对应的行为测试；其它修改无需新增测试文件。

## 测试与验证

```bash
# 后端：按受影响范围替换目标测试
python -m compileall -q lens_api scripts migrations
uv run python -m pytest tests/api/test_version_api.py -q --confcutdir=tests

# 前端
cd ui
pnpm exec tsc --noEmit
pnpm lint

# 通用
git diff --check
git status --short
```

## 代码风格

编写的代码需要满足：`STYLING.md`，注意按需加载。

## 禁止事项

- 禁止重写已有 Alembic migration。
- 禁止输出 .env、密钥相关内容。
