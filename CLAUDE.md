# Lens 项目协作规范

## 适用范围

- 本文件是项目级约束；用户最新指令优先。若本文件与实际代码、配置或测试冲突，先核对再改。
- 先读后写：改文件前先读相关入口、调用方、数据模型和已有测试，不凭文件名或直觉推断行为。
- 最小改动：只解决当前问题，不做顺手清理、无关重排、全文件重格式化或未来扩展式抽象。
- 代码注释用英文；项目说明、计划和交付说明用中文。

## 项目事实

- 后端：Python 3.11+、FastAPI、Pydantic v2、SQLAlchemy、Alembic，包配置在 `pyproject.toml`。
- 前端：Next.js 16 App Router、React 19、TypeScript strict、Tailwind v4、shadcn/ui、TanStack Query。
- 前端包管理使用 `pnpm`；本地开发流程以 `README.md` 为准。
- 仓库没有声明 black、ruff 或 prettier 配置时，不新增格式化工具，也不把格式化作为无条件步骤。

## 关键目录和边界

- `lens_api/api/app.py`：FastAPI 工厂，负责中间件、异常处理和路由注册。
- `lens_api/api/routes/`：路由层，每个路由模块通过 `register(app, service_module)` 接入。
- `lens_api/gateway/service/__init__.py`：服务层聚合和公共入口，改动时必须保护现有导入面和 `app` 暴露方式。
- `lens_api/gateway/`：网关核心，包括路由计划、上游请求、协议转换、流式处理和请求日志。
- `lens_api/core/protocol_reachability.py`：协议可达性和协议转换判断的事实来源，不要用直接相等替代。
- `lens_api/models/__init__.py`：Pydantic 模型和 `__all__` 公共导出，拆分或移动时必须保留外部导入兼容。
- `lens_api/persistence/`：ORM 实体和 Repository。数据库结构变更只通过新增 Alembic 迁移实现。
- `ui/src/app/`：Next.js App Router 路由。
- `ui/src/components/screens/`：页面级组件，现有文件命名以 kebab-case/lowercase 为主，新增文件跟随所在目录模式。
- `ui/src/components/ui/`：shadcn/ui 原语，优先复用，不随意重写基础组件。
- `ui/src/lib/`、`ui/src/hooks/`：API 客户端、工具函数和复用 Hooks。
- `migrations/versions/`：禁止修改已有迁移文件；需要数据库变更时新增迁移。
- `tests/` 被 `.gitignore` 忽略；若确实要提交该目录下测试，必须明确使用 `git add -f tests/...`。

## 工作约束

- 禁止输出 `.env`、密钥、Token、数据库密码或任何凭证内容。
- 未经用户明确要求，不执行 `git push`、删除类危险命令、生产构建或发布命令。
- 未经用户明确要求，不修改项目级配置文件，例如 `pyproject.toml`、`package.json`、`tsconfig.json`。
- 新依赖必须先说明必要性；优先使用标准库、现有依赖和项目已有工具函数。
- 每完成一个独立功能点，只有在用户明确要求时才提交 commit。
- 发现工作区已有改动时，默认视为用户改动；不要回滚，相关时先理解并在其基础上继续。

## 后端规范

- 路由层保持薄：参数校验、调用 service、返回响应；业务逻辑放在 service 或 repository。
- 全局异常处理通过 `@app.exception_handler` 统一接入；路由内不要堆叠重复 `try/except`。
- 请求和响应模型继承 `StrictBaseModel`，除非已有模型或外部协议明确需要其它行为。
- `async def` 内不要直接调用同步阻塞 I/O；使用异步库，或把同步工作放到同步函数/线程池边界。
- Repository 负责数据访问；不要让路由或 UI 形状直接泄漏进 ORM 实体。
- 涉及协议转换、模型组候选、流式生命周期、请求日志时，先读当前实现和测试；不要根据未持久化字段或稀疏上游 payload 发明规则。
- 新增一组模块内自定义异常时，定义 `class Error(Exception)` 作为该模块异常基类，其它异常从它派生；不要为满足该规则单独重命名无关既有异常。
- 确需宽捕获时使用 `except Exception as exc`，并且必须记录、转换为边界错误或重新抛出；不要静默吞掉异常。
- 禁止新增运行时可变全局状态；允许模块级常量、类型别名、编译后的正则和脚本默认参数。
- 模块级常量放在文件头部 import 之后，使用全大写下划线命名。
- 函数返回值不要超过 3 个；更多结果用 dataclass、Pydantic model、namedtuple 或 dict 等具名结构承载。
- 判断整数是否为零时使用显式比较，例如 `count == 0`，避免把零值语义和空容器语义混在一起。
- 单行不超过 120 个字符；新增或重写函数原则上不超过 120 行，超过时优先拆出有明确职责的 helper。
- 对外接口或复杂行为需要 docstring 时使用三个双引号；不要为了形式化要求批量添加版权头、联系人或空洞 docstring。

## 前端规范

- 使用函数组件和 Hooks，不新增 class 组件。
- TypeScript 保持 strict；避免 `any`。确实无法表达时，缩小作用域并说明原因。
- 数据请求优先走 `ui/src/lib/` 的既有 API 客户端和 TanStack Query 模式。
- 业务异步优先使用 `async/await`；Next.js 动态导入等框架惯用 `.then()` 形式可以保留。
- 错误不能静默吞掉；按现有模式转为 toast、表单状态、Query 错误或上抛。
- UI 改动必须贴合现有 shadcn/Tailwind 风格、密度、间距和文案语气，不做重设计或换主题。
- 界面文案保持必要和短促；不要添加解释性、营销式或教程式文本。

## 验证

- 修 bug 先复现；能写测试时先用最小测试锁定行为。
- 改动后运行最小相关验证，不用无关全量命令代替针对性验证。
- 后端常用验证：
  - `python -m py_compile <文件路径>`
  - `pytest <测试路径或 -k 表达式>`
- 前端常用验证：
  - `cd ui && pnpm lint`
  - `cd ui && pnpm exec tsc --noEmit`
- 通用检查：
  - `git diff --check`
  - `git status --short`
- 生产构建、推送、删除和发布类命令只在用户明确要求时执行。

## 常用命令

### 后端

- `pip install -e ".[dev]"`：安装本地开发依赖。
- `lens serve`：启动后端。
- `lens dev`：后端和前端联调。
- `lens db upgrade`：应用迁移。
- `lens db revision -m "desc"`：生成新迁移；需要自动生成时再追加 `--autogenerate`。

### 前端

- `cd ui && pnpm install`：安装前端依赖。
- `cd ui && pnpm dev`：启动前端开发服务器。
- `cd ui && pnpm lint`：运行 ESLint。
