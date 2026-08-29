# Lens 项目协作指南

## 项目简介

Lens 是一个多供应商 LLM 网关，统一处理客户端认证、模型组路由、协议转换、上游调用与故障转移，以及请求和用量日志。

## 开发环境

- Python 3.14 或更高版本，使用 uv 管理后端依赖。
- 前端使用 pnpm。

```bash
uv sync --locked
cd frontend && pnpm install && cd ..
uv run --no-sync lens db upgrade
uv run --no-sync lens dev
```

- 需要单独启动时使用 `uv run --no-sync lens serve` 和 `cd frontend && pnpm dev`。环境变量、部署方式、端口和数据库配置以 `README.md` 为准。
- 仓库是 uv workspace：根 `pyproject.toml` 只声明成员，后端项目在 `backend/pyproject.toml`（包名 `app`，源码 `backend/app/`，Alembic 在 `backend/app/alembic/`，测试在 `backend/tests/`），前端在 `frontend/`。所有 `uv` 和 `pytest` 命令都在仓库根执行。
- 后端工具链全部来自 dev 依赖组（`pytest`、`pytest-xdist`、`ruff`、`prek`），一律以 `uv run --no-sync <工具>` 调用，不要用全局安装的版本。缺工具时先补 `uv sync --locked`；本机配了镜像索引导致 `--locked` 误报漂移时改用 `--frozen`。
- 本机 `UV_DEFAULT_INDEX` 指向清华镜像，直接 `uv lock` 会把 `uv.lock` 里的 URL 全部改写成镜像地址。确实需要改依赖时用 `UV_DEFAULT_INDEX=https://pypi.org/simple uv lock`，改完确认 lock 里只有 `pypi.org` 和 `files.pythonhosted.org`。
- 每完成一个独立功能点，只有在用户明确要求时才提交 git。
- 每次修改代码后，对你本次修改的文件进行格式化：前端文件使用 `cd frontend && pnpm exec biome check --write <文件路径>`，后端文件使用 `uv run --no-sync ruff format <文件路径> && uv run --no-sync ruff check --fix <文件路径>`
- 提交前格式化：先执行 `uv run --no-sync prek install -f` 安装本地 hook；需要手动检查全部文件时执行 `uv run --no-sync prek run --all-files`。hook 只负责本地格式化和 Ruff/ Biome 修正，不接管提交、不自动 push。
- 仅在认证授权、数据持久化或丢失、网关协议兼容、路由或故障转移等高风险后端 HTTP 合同需要保护时，补充或更新最小 API 行为测试；不要为前端、工具函数、服务层、实现细节或一般可复现 bug 自动新增测试。
- 测试写法与运行方式遵循 `.agents/skills/lens-testing/SKILL.md`。

## 测试与验证

```bash
# 后端：后端测试一律并行运行
python -m compileall -q backend/app backend/tests scripts
uv run --no-sync ruff format <本次修改的文件>
uv run --no-sync ruff check <本次修改的文件>
uv run --no-sync python -m pytest backend/tests/api -q --confcutdir=backend/tests -n auto --dist worksteal
uv run --no-sync python -m pytest backend/tests/api/test_<area>_api.py -q --confcutdir=backend/tests  # 仅调试单点回归时运行

# 前端
cd frontend
pnpm format       # 本地格式化
pnpm lint         # 只读检查
pnpm exec tsc --noEmit
pnpm build

# 通用
git diff --check
git status --short
```

## 代码风格

编写的代码需要满足：`STYLING.md`，注意按需加载。

## 禁止事项

- 禁止重写已有 Alembic migration。
- 禁止输出 .env、密钥相关内容。
