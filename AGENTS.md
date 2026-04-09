# Project Agents Rules

<!-- BEGIN:nextjs-agent-rules -->

# Next.js: ALWAYS read docs before coding

Before any Next.js work, find and read the relevant doc in `node_modules/next/dist/docs/`. Your training data is outdated — the docs are the source of truth.

<!-- END:nextjs-agent-rules -->

## Frontend Verification

- 默认不要主动执行 `pnpm build` 作为前端改动后的验证手段。
- 用户通常会在 `pnpm dev` 中自行观察前端改动结果，因此前端修改后默认不运行 `pnpm build`。
- 只有在用户明确要求时，才执行 `pnpm build`、生产构建验证或等价的前端构建命令。

## Frontend Style Consistency

- 修改前端功能时，默认只改功能和必要交互，不得擅自改变现有页面风格、配色、排版、间距、组件视觉语言。
- 新增功能也必须沿用当前页面和设计系统的既有风格；除非用户明确授权，否则不得顺手重设计、换主题或覆盖原视觉风格。
- 默认不要在前端页面中主动添加说明性文案、引导语、提示句、解释性副标题；除非用户明确要求，否则界面文案只保留必要标题、字段名、按钮文案和状态信息。
- 如果发现历史改动已经偏离既有风格，优先参考相关页面的既有实现或历史 commit 恢复风格一致性，再继续功能修改。

## Backend And Schema

- 默认不保留老版本兼容代码、兼容字段、兼容表结构或运行时垫片，除非用户明确要求。
- 数据库 schema 变更必须优先使用显式迁移方案，不要依赖应用启动时的隐式 `create_all`、补列、重建表或自动兼容逻辑。
- Python ORM 采用 `SQLAlchemy`，数据库迁移采用 `Alembic`。

## Python Execution Environment

- 默认以当前会话的临时 conda 环境作为 Python 执行环境，不默认使用项目内 `.venv`。
- 执行 Python、测试、脚本前，先确认 `python` 指向的解释器与依赖可用性；不要想当然切到 `.venv`。
- 只有在用户明确指定，或当前 conda 环境缺少项目依赖且已确认 `.venv` 才是可用环境时，才改用 `.venv`。


## Commit Workflow

- 每完成一个相对独立的功能后，默认先提醒用户是否提交当前功能。
- 只有在用户明确表示“可以提交”后，才执行提交。
- 用户明确要求使用 `$commit` skill 时，必须先暂存相关改动，再严格按 `$commit` skill 流程生成并执行 commit。
- 如果暂存区为空，不要自行扩大发散提交范围，先明确告知用户没有检测到已暂存变更。
