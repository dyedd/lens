# 快速开始

准备一台已安装 Docker Engine 和 Docker Compose 的主机，以及一个可调用的上游 API 账号。完成本页后，你可以登录 Lens，并开始接入第一个模型。

## 用 Docker Compose 部署

在 Linux 或 macOS 的终端执行：

```bash
mkdir lens && cd lens
curl -fsSLO https://raw.githubusercontent.com/dyedd/lens/main/scripts/docker/deploy.sh
sh deploy.sh
```

脚本准备 Compose 配置、数据目录和签名密钥。随后拉取镜像并启动：

```bash
docker compose pull
docker compose up -d
docker compose ps
```

默认访问地址是 `http://127.0.0.1:3000`。部署在远程主机时，将 `127.0.0.1` 换成主机地址。

Compose 将宿主机的 `./data` 挂载到容器 `/app/data`。数据库和初始管理员密码放在这里。更换存储位置时只修改挂载左侧：

```yaml
volumes:
  - ./data:/app/data
```

## 首次登录

启动时会自动迁移数据库。管理员账号默认是 `admin`，初始随机密码写入数据目录：

```bash
docker compose exec app cat /app/data/admin-password
```

登录后进入 **设置 → 常规** 修改管理员密码，再删除初始密码文件：

```bash
docker compose exec app rm /app/data/admin-password
```

![设置中的常规选项与管理员账号](/images/settings.png)

`LENS_AUTH_SECRET_KEY` 用于签署管理端登录令牌，和管理员密码、上游 API Key、网关 Key 是不同的值。不要把它填进客户端。

## 跑通第一个请求

1. 打开 **渠道**，新建渠道，填写上游地址和凭证。
2. 保存后获取模型，选中需要接入的模型并确认。
3. 打开 **模型组**，确认对外模型名和可用成员。
4. 在 **设置 → 网关密钥** 创建 Key。
5. 将 Lens 地址、网关 Key、模型组名称填入客户端。

详细步骤分别见 [接入站点与模型](./sites)、[模型组](./model-groups) 和 [客户端接入](./clients)。第一次调用成功后，可在 **请求日志** 中看到一次成功请求。

## 修改端口与数据库

部署目录的 `.env` 保存环境配置。默认端口为 `3000`，Compose 使用同一个 `LENS_PORT` 值作为宿主机和容器端口。修改后重新创建容器：

```bash
docker compose up -d
```

默认使用 SQLite。已有 PostgreSQL 时，在 `.env` 配置：

```dotenv
LENS_DATABASE_URL=postgresql+psycopg://lens:YOUR_DATABASE_PASSWORD@postgresql:5432/lens
```

将用户名、密码、主机和数据库替换为实际值。密码中的特殊字符需要 URL 编码。容器之间用共享 Docker 网络中的服务名连接；容器里的 `localhost` 指向该容器本身。

切换数据库不会自动搬迁数据。先执行 [备份与迁移](./maintenance#备份与迁移)，再修改连接地址。完整环境变量见 [配置参考](../reference/configuration)。

## 升级

先导出备份，并保留数据目录，再执行：

```bash
docker compose pull
docker compose up -d
docker compose logs --tail=100 app
```

镜像默认使用 `latest` 正式版；`dev` 跟随主分支。需要固定版本时，在 Compose 的 `image` 中填写已发布的 `vX.Y.Z` 标签。

镜像启动时会执行数据库迁移。升级失败时先查看日志和迁移版本，不要删除数据目录来重试。

## 常见问题

| 现象 | 先检查 |
| --- | --- |
| 页面打不开 | `docker compose ps` 是否正常，主机端口是否放行 |
| 服务启动后退出 | `docker compose logs --tail=100 app` 中的数据库连接和密钥校验错误 |
| 找不到初始密码文件 | 数据目录是否正确挂载；已有管理员时不会重新生成 |
| 客户端返回 401 | 使用的是网关 Key；Key 是否启用、过期或超出限额 |
| 客户端返回 503 | 模型组是否有可用成员，以及健康页中的冷却状态 |
