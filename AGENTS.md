# Project Agents Rules

## Frontend Verification

- 默认不要主动执行 `pnpm build` 作为前端改动后的验证手段。
- 用户通常会在 `pnpm dev` 中自行观察前端改动结果，因此前端修改后默认不运行 `pnpm build`。
- 只有在用户明确要求时，才执行 `pnpm build`、生产构建验证或等价的前端构建命令。

## Backend And Schema

- 默认不保留老版本兼容代码、兼容字段、兼容表结构或运行时垫片，除非用户明确要求。
- 数据库 schema 变更必须优先使用显式迁移方案，不要依赖应用启动时的隐式 `create_all`、补列、重建表或自动兼容逻辑。
- Python ORM 采用 `SQLAlchemy`，数据库迁移采用 `Alembic`。


## Commit Workflow

- 每完成一个相对独立的功能后，默认先提醒用户是否提交当前功能。
- 只有在用户明确表示“可以提交”后，才执行提交。
- 用户明确要求使用 `$commit` skill 时，必须先暂存相关改动，再严格按 `$commit` skill 流程生成并执行 commit。
- 如果暂存区为空，不要自行扩大发散提交范围，先明确告知用户没有检测到已暂存变更。
