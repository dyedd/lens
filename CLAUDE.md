# Lens 项目编码规范

## 项目概要

- 运行环境：Conda 环境 `temp`
- 后端：FastAPI + Python 3.11+，异步优先，全局异常处理
- 前端：Next.js 16 (App Router) + React 19 + TypeScript 5 + Tailwind v4 + shadcn/ui
- 数据获取：TanStack Query；通知：sonner；图标：lucide-react
- 代码注释用英文，规范文档用中文

## 项目结构

- `lens_api/api/routes/` — 路由，每文件导出 `register(app, service_module)`
- `lens_api/api/app.py` — FastAPI 工厂 `create_app(service_module)`
- `lens_api/gateway/` — 网关核心（service/router/upstreams/converters）
- `lens_api/persistence/` — ORM 实体 + Repository（`*_store.py`）
- `lens_api/core/` — 横切关注点（config/db/auth）
- `lens_api/models.py` — Pydantic 模型，继承 `StrictBaseModel(extra="forbid")`
- `ui/src/app/` — App Router 路由（`(dashboard)`、`login/` 等）
- `ui/src/components/screens/` — 页面级组件
- `ui/src/components/ui/` — shadcn/ui 原语
- `ui/src/components/{auth,settings,shell}/` — 领域组件
- `ui/src/lib/` — API 客户端、工具函数
- `ui/src/hooks/` — 自定义 Hooks
- `migrations/versions/` — Alembic 迁移，**禁止修改已有文件**

## 一、通用原则

- 保持现有视觉风格（配色、间距、组件样式），新增组件必须完全遵循已有模式，禁止重设计或换主题
- UI/UX 改动前先提供 ASCII 示意图
- 界面仅保留必要标题、按钮、状态文字，禁止添加引导性/说明性文案
- 禁止自动执行构建、删除、推送等危险命令，禁止修改全局配置文件（`package.json`、`tsconfig.json`、`pyproject.toml` 等），除非用户明确要求
- 只修改指定文件，不得擅自新增文件或引入新依赖
- 每次修改代码后，对你本次修改的文件进行格式化：前端文件使用 `npx prettier --write <文件路径>`，后端文件使用 `black <文件路径>`

## 二、前端规范（React / Next.js）

- 全部使用函数组件 + Hooks，禁止 class 组件
- TypeScript 严格模式，**禁止** `any` 类型，复杂类型抽取为 `interface`/`type`
- 异步操作 **一律** `async/await`，**禁止** `.then()` / `.catch()` 链式调用
- 数据获取通过 Hooks（`useEffect` 内 async 函数或 TanStack Query）统一管理
- 错误处理：
  - 渲染错误由 `ErrorBoundary` 统一捕获，JSX 内不得使用 `try/catch`
  - 事件处理内部可 `try/catch`，但错误必须抛给 `ErrorBoundary` 或全局错误状态，禁止静默吞掉
  - 网络请求等异步错误通过全局拦截器或 `useErrorBoundary` 统一处理

## 三、后端规范（FastAPI）

- 全局异常处理：`@app.exception_handler` 统一捕获，路由函数避免大量 `try/except`
- 路由保持干净：参数校验 → 调用 service → 返回
- 异步优先：
  - 路由声明 `async def`，调用异步库用 `await`
  - 调用同步库用 `def`，由 FastAPI 放入线程池，**禁止** 在 `async def` 内直接调用同步阻塞函数
  - **禁止** 使用 `.then()` 风格
- 请求/响应模型继承 `StrictBaseModel(extra="forbid")`
- 数据访问采用 Repository 模式，ORM 实体定义在 `persistence/entities.py`
- 所有函数必须有类型注解，遵循 PEP 8，使用 `black` 格式化
- 数据库变更只通过新增 Alembic 迁移实现，**禁止修改已存在的迁移文件**

## 四、AI 行为约束

- **禁止自动执行**：`pnpm build`、`npm run build`、`rm -rf`、`git push`、修改全局配置文件
- `.env` 文件包含密钥，**禁止输出其内容**
- 每完成一个独立功能点，**必须征得用户同意**后再执行 `commit`
- 非必要不注释

## 五、常用命令

### 后端

- `lens serve` — 启动后端
- `lens dev` — 后端 + 前端联调
- `lens db upgrade` — 应用迁移
- `lens db revision -m "desc" --autogenerate` — 生成新迁移

### 前端

- `cd ui && pnpm dev` — 启动开发服务器
- `cd ui && pnpm lint` — 运行 ESLint
