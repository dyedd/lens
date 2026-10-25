# Lens 项目协作指南

Lens 是统一处理认证、模型组路由、协议转换、上游调用、故障转移和请求/用量日志的多供应商 LLM 网关。本指南适用于仓库内所有日常开发与协作；部署配置、端口分配与环境变量以 [README.md](README.md) 为准。

## 环境与边界

- **运行环境**：Python `>=3.14` 由 `uv` 管理，前端由 `pnpm` 管理。根目录 `pyproject.toml` 为 uv workspace；后端位于 `backend/`（源码在 `backend/app/`，API 测试在 `backend/tests/api/`，迁移脚本在 `backend/app/alembic/`）。
- **工具调用**：后端工具必须从仓库根目录使用 `uv run --no-sync` 执行。缺少依赖时优先执行 `uv sync --locked`；若因本地镜像索引导致锁文件误报漂移，改用 `uv sync --frozen`。
- **依赖锁定**：更新依赖执行 `uv lock` 时，显式指定 `UV_DEFAULT_INDEX=https://pypi.org/simple`，防止本机镜像配置重写索引 URL，并确保锁文件中的 wheel/tar 下载来源为 `pypi.org` 与 `files.pythonhosted.org`。
- **前端开发**：前端命令均在 `frontend/` 目录下执行。启动与构建步骤详见 [README.md](README.md)。
- **安全与历史约束**：严禁修改已有 Alembic 迁移脚本；严禁在日志、响应或代码中输出 `.env` 及任何真实密钥信息。除非用户明确指示，否则不得提交（commit）、推送（push）或改写 Git 历史。

## 代码风格

所有代码改动必须严格遵守 [STYLING.md](STYLING.md)。前端界面视觉必须遵守 [DESIGN.md](DESIGN.md)：分页、弹窗、表格外壳与容器（well）的 token 均以该规范为准。修改前需通读通用规则、类型命名、领域术语、动作动词和模块边界，再查阅对应的 Python 或 TypeScript / React 章节。

- **文案原则**：前端文案遵循 “Avoid unnecessary secondary labels and descriptions. Let the layout do the explaining.” —— 由页面结构、字段标签和交互控件承担主要解释，仅在涉及核心操作、状态流转、高危风险或无障碍访问时保留必要的辅助说明。

## 工作流

1. **界定最小范围**：查看 `git status`、相关调用链路与现有测试，明确最小改动范围。
2. **复用与边界治理**：优先复用现有边界与公共工具；修改共享逻辑前全面排查所有调用方，在公共边界解决根因。
3. **阶段分明与错误收口**：网关代码按“解析输入 → 参数校验 → 路由计划 → 协议转换 → 上游传输 → 响应转换 → 日志落盘”分阶段组织；业务异常统一使用 `app/core/errors.py` 中的领域异常表达，对外协议 envelope 响应统一由 `gateway/service/error_responses.py` 生成。
4. **精细格式化**：改动代码后仅针对触碰的文件进行格式化与检查：后端执行 `uv run --no-sync ruff format <paths>` 与 `uv run --no-sync ruff check --fix <paths>`；前端执行 `cd frontend && pnpm exec biome check --write <paths>`。
5. **测试驱动与防护**：后端 API 测试以 [lens-testing](.agents/skills/lens-testing/SKILL.md) 为准，以覆盖核心功能的正常成功流程为主并保持套件全绿；新功能或契约变动仅补充最小的 HTTP 行为测试，不为前端、工具函数、服务层或内部实现细节新增孤立测试。
6. **收尾与状态汇报**：完成后复查 `git diff --check` 与 `git status --short`，并在最终回复中明确说明未执行的检查或与本次改动无关的既有失败。

提交前建议运行 `uv run --no-sync prek install -f` 安装本地格式化 hook；全仓检查仅在明确需要时运行 `uv run --no-sync prek run --all-files`。前端 hook 会格式化整个 `frontend/`，提交前务必复查生成的变更，避免引入范围外修改。

## 常用检查

```bash
# 后端检查（仓库根目录执行）
uv run --no-sync python -m compileall -q backend/app backend/tests scripts
uv run --no-sync python -m pytest backend/tests/api -q --confcutdir=backend/tests -n auto --dist worksteal
# 仅在调试单点回归时串行执行
uv run --no-sync python -m pytest backend/tests/api/test_<area>_api.py -q --confcutdir=backend/tests

# 数据库迁移检查（须先将 LENS_DATABASE_URL 指向隔离的测试数据库）
uv run --no-sync lens db upgrade
cd backend
uv run --no-sync python -m alembic check
cd ..

# 前端检查（frontend/ 目录下执行）
cd frontend
pnpm lint
# 常规类型检查；需要完整构建验证时使用 pnpm build（内部已包含 tsc）
pnpm exec tsc --noEmit
pnpm build
```

上述命令应按改动范围按需选用，而非无差别顺序执行。后端测试默认并行运行，单点调试除外；纯文档改动仅需核对内容、链接及 diff 状态。全量 CI 流程参见 [.github/workflows/build.yml](.github/workflows/build.yml)。
