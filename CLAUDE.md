# Lens 项目协作指南

Lens 是统一处理认证、模型组路由、协议转换、上游调用、故障转移和请求/用量日志的多供应商 LLM 网关。本文件适用于仓库内工作；部署、端口和环境变量以 `README.md` 为准。

## 环境与边界

- Python `>=3.14` 由 `uv` 管理，前端由 `pnpm` 管理。根 `pyproject.toml` 是 uv workspace；后端在 `backend/`，源码为 `backend/app/`，API 测试为 `backend/tests/api/`，迁移为 `backend/app/alembic/`。
- 后端工具使用 `uv run --no-sync`，从仓库根目录执行。缺依赖时先用 `uv sync --locked`；确认是镜像索引导致的锁文件误报时才改用 `uv sync --frozen`。
- 更新依赖时为该次 `uv lock` 设置 `UV_DEFAULT_INDEX=https://pypi.org/simple`，避免本机镜像配置重写索引 URL；检查锁文件下载地址仍来自 `pypi.org` 和 `files.pythonhosted.org`。
- 前端命令从 `frontend/` 执行。开发启动和部署步骤见 [README.md](README.md)。
- 不重写已有 Alembic migration，不输出 `.env` 或任何密钥内容。只有用户明确要求时才提交、推送或改写 Git 历史。

## 代码风格

所有代码改动遵循 [STYLING.md](STYLING.md)。修改前读取通用、类型命名、领域术语、动作动词和模块边界，再读取对应的 Python 或 TypeScript / React 章节。

## 工作流

1. 先看 `git status`、相关调用链和现有测试，再确定最小改动范围。
2. 复用现有边界和工具；共享行为先查所有调用方，在共同边界修根因。
3. 网关代码按解析、校验、路由计划、协议转换、上游传输、响应转换和日志收尾分阶段；错误语义使用 `app/core/errors.py` 的领域异常，协议 envelope 统一由 `gateway/service/error_responses.py` 生成。
4. 修改代码后只格式化触碰的文件：后端运行 `uv run --no-sync ruff format <paths>` 和 `uv run --no-sync ruff check --fix <paths>`；前端运行 `cd frontend && pnpm exec biome check --write <paths>`。
5. 仅在认证授权、持久化或数据丢失、协议兼容、路由或故障转移等高风险后端 HTTP 合同需要保护时补充最小 API 行为测试；不为前端、工具函数、服务层、实现细节或一般可复现 bug 自动新增测试。具体写法和运行方式见 [lens-testing](.agents/skills/lens-testing/SKILL.md)。
6. 完成后复查 `git diff --check`、`git status --short`，并明确报告未运行的检查或与本次无关的既有失败。

提交前运行 `uv run --no-sync prek install -f` 安装本地格式化 hook；仅在需要全仓检查时运行 `uv run --no-sync prek run --all-files`。前端 hook 会格式化整个 `frontend/`，提交前复查它产生的差异，保持提交范围。

## 常用检查

```bash
# 后端（从仓库根目录）
uv run --no-sync python -m compileall -q backend/app backend/tests scripts
uv run --no-sync python -m pytest backend/tests/api -q --confcutdir=backend/tests -n auto --dist worksteal
# 仅调试单点回归时串行运行
uv run --no-sync python -m pytest backend/tests/api/test_<area>_api.py -q --confcutdir=backend/tests

# 迁移检查：先将 LENS_DATABASE_URL 指向隔离的测试数据库
uv run --no-sync lens db upgrade
cd backend
uv run --no-sync python -m alembic check
cd ..

# 前端（从 frontend/）
cd frontend
pnpm lint
# 通常做类型检查；需要构建验证时改用 pnpm build（已包含 tsc）
pnpm exec tsc --noEmit
pnpm build
```

以上是按改动选择的检查命令，不是每次依次执行的脚本。后端测试默认并行，单点调试除外；纯文档改动检查内容、链接和差异即可。全量 CI 见 [.github/workflows/build.yml](.github/workflows/build.yml)。
