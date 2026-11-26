# 搭建开发环境

Lens 采用单仓多包结构：后端为 Python uv workspace（`backend/`），管理控制台位于 `frontend/`，文档站位于 `docs/`。三者各自管理依赖并在需要时联动运行。

## 环境要求与初始化

| 工具 | 版本要求 / CI 配置 |
| --- | --- |
| Python | 3.14 或更高版本（由 `uv` 管理，见 `.python-version`） |
| uv | CI 使用 `0.11.28` |
| Node.js | CI 使用 `22` |
| pnpm | `10.17.1` |
| Git | 源码获取与提交 |

在仓库根目录执行初始化（Windows 推荐使用 PowerShell 7）：

```bash
git clone https://github.com/dyedd/lens.git
cd lens
uv sync --locked
cd frontend
pnpm install --frozen-lockfile
cd ..
```

> [!TIP]
> 如果本地配置了第三方 PyPI 镜像导致 `uv sync --locked` 提示锁校验差异，可改用 `uv sync --frozen` 严格按锁文件安装。若你修改了依赖需要更新 `uv.lock`，请显式指定官方源以避免将个人镜像地址写入锁文件：
> ```powershell
> $env:UV_DEFAULT_INDEX = "https://pypi.org/simple"
> uv lock
> ```

## 初始化本地配置与独立开发库

首次在本地运行前，生成随机 JWT 签名密钥并执行初始化：

```bash
uv run --no-sync python -c "import os, secrets; from pathlib import Path; path = Path('.env'); os.umask(0o077); path.exists() or path.write_text(f'LENS_AUTH_SECRET_KEY={secrets.token_hex(32)}\n', encoding='utf-8')"
uv run --no-sync lens setup
```

`lens setup` 会依次运行数据库迁移、初始化管理员 `admin`（随机密码写入 `data/admin-password`）并安装/构建前端产物至 `backend/app/frontend/`。

### 隔离开发数据库（强烈推荐）

如果当前仓库目录同时存放着你的日常测试数据，开发或编写文档截图时请使用环境变量指向独立数据库与端口（PowerShell 示例）：

```powershell
$env:LENS_DATABASE_URL = "sqlite+aiosqlite:///./data/dev.db"
$env:LENS_PORT = "18081"
uv run --no-sync lens migrate
uv run --no-sync lens dev
```

迁移命令与服务进程必须使用同一套 `LENS_DATABASE_URL`。新开终端窗口后请重新设置环境变量。

## 启动前后端与日常调试

一键同时启动 FastAPI 后端与 Vite 前端开发服务器：

```bash
uv run --no-sync lens dev
```

| 服务 | 默认地址 | 说明 |
| --- | --- | --- |
| Vite 开发服务器 | `http://127.0.0.1:3000` | 浏览器访问与本地代理入口，将 `/api`、`/v1`、`/v1beta` 代理到后端 |
| FastAPI 后端 | `http://127.0.0.1:18080` | 端口由 `LENS_PORT` 控制；`lens dev` 会自动传入 `VITE_LENS_DEV_BACKEND` |

- **仅启动后端**（挂载已构建的生产前端静态资源）：`uv run --no-sync lens serve`
- **分终端手动启动**：若在 `frontend/` 单独运行 `pnpm dev` 且后端不在 `18080` 端口，需在前端终端设置 `$env:VITE_LENS_DEV_BACKEND = "http://127.0.0.1:18081"`。
- **热重载边界**：前端修改由 Vite 即时热更新；修改 Python 源码后需重启 `lens dev` / `lens serve`；验证生产静态包需在 `frontend/` 执行 `pnpm build` 后再访问后端端口。

启动后建议做一次最小闭环确认：访问 `http://127.0.0.1:3000` 登录 → 接入一个本地或测试上游 → 创建网关密钥 → 发送一条测试请求 → 在 **请求日志** 确认记录落盘。

## Lens CLI 命令速查

所有 CLI 命令均从仓库根目录通过 `uv run --no-sync lens ...` 执行（实现见 [`cli.py`](https://github.com/dyedd/lens/blob/main/backend/app/cli.py)）：

| 命令 | 说明 |
| --- | --- |
| `lens setup` | 执行 `migrate` 并构建前端静态资源 |
| `lens dev` | 同时启动 FastAPI 与 Vite 开发服务器（退出时自动清理前端进程树） |
| `lens serve [--host] [--port] [--ui-static-dir]` | 启动 API 服务（默认绑定 `127.0.0.1` 与 `LENS_PORT`） |
| `lens migrate` | 升级数据库至 `head` 并在无管理员时初始化 `admin` |
| `lens seed-admin --username ... (--password ... \| --generate-password [--password-file ...])` | 单独初始化管理员账号 |
| `lens db upgrade [revision]` | 升级 Alembic 迁移（默认 `head`） |
| `lens db downgrade [revision]` | 回退迁移（默认 `-1`；执行前务必备份数据） |
| `lens db revision -m "说明"` | 根据 SQLAlchemy ORM 变更自动生成新迁移脚本 |
| `lens db current` / `lens db history` | 查看当前修订与迁移历史 |
| `lens db stamp [revision]` | 仅标记数据库版本而不执行迁移脚本 |

> [!WARNING]
> 已合入的 Alembic 迁移文件应保持不可变；任何表结构调整请新增迁移修订（Revision）。

## 代码检查与测试验证

提交代码前，按修改范围运行对应校验（与 `.github/workflows/build.yml` 保持一致）：

### 后端检查（仓库根目录执行）

```bash
# 1. 字节码语法检查
uv run --no-sync python -m compileall -q backend/app backend/tests scripts

# 2. 格式化与 Lint（仅针对修改的文件）
uv run --no-sync ruff format backend/app/path/to/file.py
uv run --no-sync ruff check --fix backend/app/path/to/file.py

# 3. 运行 API 套件或全量测试
uv run --no-sync python -m pytest backend/tests/api -q --confcutdir=backend/tests -n auto --dist worksteal
# 完整测试套件：
uv run --no-sync python -m pytest backend/tests -q --confcutdir=backend/tests -n auto --dist worksteal
```

### 数据库迁移一致性校验（独立空库）

```powershell
$env:LENS_DATABASE_URL = "sqlite+aiosqlite:///./data/migration-check.db"
uv run --no-sync lens db upgrade
Push-Location backend
uv run --no-sync python -m alembic check
Pop-Location
Remove-Item Env:LENS_DATABASE_URL
```

### 前端检查（`frontend/` 目录执行）

```bash
pnpm exec biome check --write src/path/to/file.ts   # 仅格式化与检查改动文件
pnpm exec biome ci .                                 # 全量 Lint 检查
pnpm test                                            # Vitest 单元测试
pnpm build                                           # 内含 tsc --noEmit 类型检查与 Vite 打包
```

## 本地构建 Docker 镜像

在已通过 `scripts/docker/deploy.sh` 或手动准备好 `.env` 与 `data/` 的根目录执行：

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

文档站开发与预览命令见 [维护与发布文档](./documentation)。
