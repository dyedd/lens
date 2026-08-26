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
- 后端工具链全部来自 dev extra（`pytest`、`pytest-xdist`、`black`），一律以 `uv run --no-sync <工具>` 调用，不要用全局安装的版本。缺工具时先补 `uv sync --extra dev --locked`；本机配了镜像索引导致 `--locked` 误报漂移时改用 `--frozen`，并且不要执行 `uv lock`，否则会把 `uv.lock` 里的 URL 全部改写成镜像地址。
- 每完成一个独立功能点，只有在用户明确要求时才提交 git。
- 每次修改代码后，对你本次修改的文件进行格式化：前端文件使用 `npx prettier --write <文件路径>`，后端文件使用 `uv run --no-sync black <文件路径>`
- 仅在认证授权、数据持久化或丢失、网关协议兼容、路由或故障转移等高风险后端 HTTP 合同需要保护时，补充或更新最小 API 行为测试；不要为前端、工具函数、服务层、实现细节或一般可复现 bug 自动新增测试。
- 测试写法与运行方式遵循 `.agents/skills/lens-testing/SKILL.md`。

## 测试与验证

```bash
# 后端：后端测试一律并行运行
python -m compileall -q lens_api scripts migrations
uv run --no-sync black <本次修改的文件>
uv run --no-sync python -m pytest tests/api -q --confcutdir=tests -n auto --dist worksteal
uv run --no-sync python -m pytest tests/api/test_<area>_api.py -q --confcutdir=tests  # 仅调试单点回归时运行

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
