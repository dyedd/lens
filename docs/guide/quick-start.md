# 快速开始与部署

本页介绍如何通过 Docker 部署 Lens、完成首次安全登录并跑通第一条推理请求。部署前请准备一台已安装 Docker Engine 与 Docker Compose 的主机，以及至少一个可用的上游 API 账号。

## 部署方式

### 方式一：标准 Docker Compose（推荐）

在 Linux 或 macOS 终端执行以下命令：

```bash
mkdir lens && cd lens
curl -fsSLO https://raw.githubusercontent.com/dyedd/lens/main/scripts/docker/deploy.sh
sh deploy.sh
docker compose pull
docker compose up -d
docker compose ps
```

`deploy.sh` 会自动下载 `docker-compose.yml` 与 `.env.example`，生成随机 64 位十六进制 `LENS_AUTH_SECRET_KEY` 写入 `.env`（权限 `600`），并创建 `./data` 目录挂载到容器 `/app/data`。

> [!TIP]
> 在 Windows 主机或无法运行 `sh` 的环境，可手动下载仓库根目录的 `docker-compose.yml` 与 `.env.example` 为 `.env`，再在 PowerShell 生成密钥：
> ```powershell
> -join ((1..32) | ForEach-Object { "{0:x2}" -f (Get-Random -Minimum 0 -Maximum 256) })
> ```
> 将结果填入 `.env` 的 `LENS_AUTH_SECRET_KEY=` 后执行 `docker compose up -d`。

### 方式二：1Panel 容器编排部署

仓库内置了面向 1Panel 环境的 [`docker-compose-1panel.yml`](https://github.com/dyedd/lens/blob/main/docker-compose-1panel.yml)：

- 数据目录默认映射为 `/opt/1panel/apps/lens/data:/app/data`；
- 容器加入外部网络 `1panel-network`，可直接通过容器名访问同网络的 PostgreSQL 或反代容器（例如 Nginx / OpenResty）。

部署时同样需要配置包含 64 位十六进制 `LENS_AUTH_SECRET_KEY` 的 `.env` 文件。

## 首次登录与安全加固

容器启动入口脚本会自动执行数据库迁移（可通过 `LENS_SKIP_DB_UPGRADE=1` 跳过），若尚未存在管理员账号，会创建默认账号 `admin` 并将随机初始密码写入数据目录：

```bash
docker compose exec app cat /app/data/admin-password
```

1. 打开浏览器访问 `http://127.0.0.1:3000`（远程主机请替换为实际 IP 或域名）。
2. 使用账号 `admin` 和上述命令读出的密码登录。
3. 立即进入 **设置 → 常规** 修改管理员密码（如需改用户名也可同步修改），确认保存。
4. 删除初始密码文件，避免明文长期滞留磁盘：

```bash
docker compose exec app rm /app/data/admin-password
```

![设置中的常规选项与管理员账号](/images/settings.png)

> [!WARNING]
> **区分三种密钥**：
> - `LENS_AUTH_SECRET_KEY`：仅用于签发管理端 JWT 登录令牌（UTF-8 编码需至少 32 字节），**切勿**填进任何客户端。
> - **上游 API Key**：保存在 **渠道** 中，仅由 Lens 请求上游供应商时使用。
> - **网关密钥（Gateway Key）**：在 **设置 → 网关密钥** 创建，专门用于外部客户端调用 Lens 推理接口。

## 跑通第一条请求

首次配置按以下顺序完成：

1. **接入渠道**：打开 **渠道 → 新建渠道**，填写供应商 Base URL 与上游 API Key（详见 [接入站点与模型](./sites)）。
2. **获取并启用模型**：保存后拉取上游模型目录（或使用 **模型规则** 批量加入），确认协议类型后保存。
3. **核对模型组**：打开 **模型组**，查看自动生成的同名组或调整成员顺序与策略（详见 [管理模型组与路由](./model-groups)）。
4. **创建网关密钥**：在 **设置 → 网关密钥** 新建密钥，按需限制可用模型组与费用上限。
5. **接入客户端**：将 Lens 地址、网关密钥和模型组名填入 SDK 或编码工具，调用后在 **请求日志** 中确认成功（详见 [客户端接入](./clients)）。

## 修改端口与数据库

部署目录 `.env` 控制进程启动参数（修改后需 `docker compose up -d` 重建容器生效，完整变量见 [环境变量与网关设置](../reference/configuration)）：

- **监听端口**：`LENS_PORT` 默认 `3000`，Compose 将宿主机与容器端口保持一致映射。
- **持久化目录**：如需迁移 SQLite 数据位置，只修改 `docker-compose.yml` 卷映射左侧的宿主机路径。
- **切换 PostgreSQL**：SQLite 适合单机轻量部署；生产或高并发场景建议在 `.env` 配置 PostgreSQL：

```dotenv
LENS_DATABASE_URL=postgresql+psycopg://lens:YOUR_DATABASE_PASSWORD@postgresql:5432/lens
```

> [!NOTE]
> 切换数据库不会自动迁移旧库数据。请先按 [备份与迁移](./maintenance#备份与迁移) 导出 JSON 备份，切换连接并待新库迁移完成后再通过界面导入恢复。密码中的特殊字符需进行 URL 编码；容器内 `localhost` 指向自身，同宿主机容器间请使用共享 Docker 网络中的服务名。

## 升级与回滚

1. 在管理界面 **设置 → 备份与迁移** 导出完整配置备份（按需勾选网关密钥与日志），必要时同时备份宿主机 `./data`。
2. 拉取新镜像并重建容器：

```bash
docker compose pull
docker compose up -d
docker compose logs --tail=100 app
```

- 默认镜像标签为 `latest`（对应正式 Release）；`dev` 跟随 `main` 分支；固定版本可在 `docker-compose.yml` 中指定 `ghcr.io/dyedd/lens:vX.Y.Z`。
- 容器启动会自动执行 Alembic 迁移。**如果升级失败，请先查看容器日志与数据库修订版本，切勿直接删除 `./data` 目录。**

## 启动阶段常见问题

| 现象 | 排查方向 |
| --- | --- |
| 管理界面无法访问 | 执行 `docker compose ps` 检查容器是否运行；确认防火墙与 `LENS_PORT` 端口一致 |
| 容器启动后立即退出 | 执行 `docker compose logs --tail=100 app`，重点检查 `LENS_AUTH_SECRET_KEY` 长度与 `LENS_DATABASE_URL` 连通性 |
| 找不到 `/app/data/admin-password` | 检查 `./data:/app/data` 卷是否正确挂载；数据库已存在管理员时不会重复生成 |
| 推理接口返回 `401` | 确认客户端使用的是 **网关密钥** 而非上游 Key 或管理员密码，并检查密钥是否启用、过期或超额 |
| 推理接口返回 `503` | 检查对应模型组是否有已启用的成员，并在 **健康状态** 页确认是否全部目标处于冷却 |
