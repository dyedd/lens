# 搭建开发环境

Lens 后端是 Python uv workspace，前端位于 `frontend/`，文档站位于 `docs/`。三者分别安装依赖和运行。

## 工具与目录

| 工具 | 版本要求 / 项目配置 |
| --- | --- |
| Python | 3.14 或更新版本，由 uv 管理 |
| uv | CI 使用 0.11.28 |
| Node.js | CI 使用 22 |
| pnpm | 项目使用 10.17.1 |
| Git | 用于获取源码和提交变更 |

Windows 使用 PowerShell 7。以下初始化命令也可在支持这些工具的 Linux / macOS 终端中执行。

```bash
git clone https://github.com/dyedd/lens.git
cd lens
uv sync --locked
cd frontend
pnpm install --frozen-lockfile
cd ..
```

如果本地镜像索引使 `uv sync --locked` 误报锁文件漂移，可用 `uv sync --frozen` 按现有锁文件安装。更新锁文件时应显式使用官方索引，避免把个人镜像写进锁文件：

```powershell
$env:UV_DEFAULT_INDEX = "https://pypi.org/simple"
uv lock
```

## 初始化本地配置

在仓库根目录运行。命令仅在 `.env` 不存在时创建随机签名密钥：

```bash
uv run --no-sync python -c "import os, secrets; from pathlib import Path; path = Path('.env'); os.umask(0o077); path.exists() or path.write_text(f'LENS_AUTH_SECRET_KEY={secrets.token_hex(32)}\n', encoding='utf-8')"
uv run --no-sync lens setup
```

`lens setup` 执行数据库迁移、创建初始管理员并构建前端。默认数据库为 `data/data.db`，初始管理员密码写入 `data/admin-password`。用账号 `admin` 登录后修改密码。

### 使用独立的开发数据

如果仓库目录已经用于日常服务，先给开发进程指定新的数据库，再运行初始化与启动命令。下面的 PowerShell 环境变量只影响当前终端及其子进程：

```powershell
$env:LENS_DATABASE_URL = "sqlite+aiosqlite:///./data/dev-docs.db"
$env:LENS_PORT = "18081"
uv run --no-sync lens migrate
uv run --no-sync lens dev
```

相对路径以执行命令时的仓库根目录为基准。重新打开终端后，应再次设置相同的值；否则进程会使用 `.env` 或默认配置。迁移和服务必须指向同一个数据库。初始管理员信息和签名密钥的准备方式与上面相同。

## 启动前后端

```bash
uv run --no-sync lens dev
```

| 地址 | 用途 |
| --- | --- |
| `http://127.0.0.1:3000` | Vite 开发界面，也是浏览器与客户端访问入口 |
| `http://127.0.0.1:18080` | FastAPI，默认端口可由 `LENS_PORT` 修改 |

Vite 将 `/api`、`/v1` 和 `/v1beta` 代理到后端。`lens dev` 会把后端地址传给 Vite，并在退出时关闭它启动的前端进程。

启动后按以下顺序确认环境：

1. 查看终端，确认数据库连接和 API 启动没有错误。
2. 打开 Vite 输出的地址。`3000` 被占用时，以终端实际端口为准。
3. 登录管理界面，确认看到的是预期开发数据库中的渠道和模型组。
4. 接入一个测试上游，创建网关 Key，按 [客户端接入](../guide/clients) 发出简单请求。
5. 打开请求日志，确认最终状态、上游渠道与模型符合配置。

页面能打开只说明前端服务可用；完成上述请求才能同时检查认证、模型组、上游连接和日志写入。

只运行后端：

```bash
uv run --no-sync lens serve
```

`lens serve` 也会提供已经构建的前端。前端产物位于 `backend/app/frontend/`，由 `frontend/pnpm build` 生成；只改 Python 时无需反复构建。

若分两个终端启动，前端默认代理到 `18080`。后端使用其他端口时，在前端终端设置 `VITE_LENS_DEV_BACKEND`：

```powershell
$env:VITE_LENS_DEV_BACKEND = "http://127.0.0.1:18081"
cd frontend
pnpm dev
```

前端源码由 Vite 自动更新。修改 Python 代码后，停止并重新运行 `lens dev`。验证生产静态页面时，先在 `frontend/` 运行 `pnpm build`，再访问 `lens serve` 的后端端口。

| 现象 | 检查方法 |
| --- | --- |
| 页面能开，但管理 API 连接失败 | 比较 API 监听端口与 `VITE_LENS_DEV_BACKEND`；修改变量后重启 Vite |
| 启动提示缺少表或数据库版本不匹配 | 在相同环境变量下运行 `lens db current`，确认数据库后执行 `lens migrate` |
| 修改前端后，后端端口的页面没有变化 | 开发时访问 Vite 地址；检查生产页时重新构建前端 |

## 常用 CLI

以下命令从仓库根目录执行：

| 命令 | 行为 |
| --- | --- |
| `uv run --no-sync lens setup` | 迁移数据库、初始化管理员、构建前端 |
| `uv run --no-sync lens dev` | 同时启动 API 与 Vite |
| `uv run --no-sync lens serve` | 启动 API，提供已构建的管理界面 |
| `uv run --no-sync lens migrate` | 升级数据库并初始化管理员 |
| `uv run --no-sync lens db upgrade` | 仅升级数据库 |
| `uv run --no-sync lens db current` | 查看当前数据库修订 |
| `uv run --no-sync lens db history` | 查看迁移历史 |
| `uv run --no-sync lens db revision -m "说明"` | 根据 ORM 变化生成新迁移 |
| `uv run --no-sync lens db downgrade` | 回退一步；使用前确认数据影响并备份 |

已有迁移脚本保持不变，结构调整通过新迁移实现。

## 验证改动

后端命令从仓库根目录执行：

```bash
uv run --no-sync python -m compileall -q backend/app backend/tests scripts
uv run --no-sync python -m pytest backend/tests/api -q --confcutdir=backend/tests -n auto --dist worksteal
```

格式化只处理本次触碰的文件：

```bash
uv run --no-sync ruff format backend/app/path/to/file.py
uv run --no-sync ruff check --fix backend/app/path/to/file.py
```

前端命令在 `frontend/` 执行：

```bash
pnpm exec biome ci .
pnpm exec tsc --noEmit
pnpm build
```

`pnpm build` 已包含类型检查，需要完整构建验证时不必再重复执行 `tsc`。

迁移验证应使用单独的空数据库。例如在 PowerShell 中：

```powershell
$env:LENS_DATABASE_URL = "sqlite+aiosqlite:///./data/migration-check.db"
uv run --no-sync lens db upgrade
Push-Location backend
uv run --no-sync python -m alembic check
Pop-Location
Remove-Item Env:LENS_DATABASE_URL
```

检查结束后，按需清理这个测试数据库。不要把迁移试验指向日常使用的数据库。

## 本地构建 Docker 镜像

在已准备 `.env` 和 `data/` 的源码目录执行：

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

首次准备这些文件可在支持 `sh` 的终端运行 `sh scripts/docker/deploy.sh`。镜像构建单独编译管理界面并安装后端运行依赖。文档目录与截图已由 `.dockerignore` 排除。

文档开发命令见 [维护与发布文档](./documentation)。
