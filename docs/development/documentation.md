# 维护与发布文档

文档源码放在主分支的 `docs/`。修改时创建普通工作分支，通过 PR 合并；功能变化和对应文档可以放在同一个 PR 中。

## 本地预览

在 `docs/` 安装依赖并启动：

```bash
cd docs
pnpm install --frozen-lockfile
pnpm dev
```

打开终端显示的地址，并进入 `/lens/`。文档站使用 VitePress 1.6.4，与 `frontend/` 的依赖和构建命令分开。

提交前构建并预览生产产物：

```bash
pnpm build
pnpm preview
```

构建会检查页面内部链接。预览时再确认导航、图片、页面目录、移动端布局和搜索结果。

## 内容组织

| 位置 | 内容 |
| --- | --- |
| `guide/` | 部署和日常操作：前提、步骤、预期结果与排错 |
| `reference/` | 环境变量、默认值和配置语义 |
| `development/` | 环境搭建、架构和文档维护 |
| `public/images/` | 操作截图和架构图 |
| `public/version.txt` | 与源码同步的版本号，构建后位于站点根路径 |
| `diagrams/` | 架构图的 Mermaid 源文件 |
| `.vitepress/config.ts` | 导航、侧栏、搜索和 Pages 路径 |

新增页面后更新侧栏，并从相关页面链接过去。README 展示项目价值、UI 集合、快速启动和文档入口，详细说明在这里维护。

## 更新截图

先用隔离数据库启动 Lens，准备虚构站点和凭证，再在浏览器中完成页面操作并截图。示例中的站点名称应能辨认是演示数据。

截图存入 `public/images/`，用与操作对应的文件名。只保留需要展示的页面或弹窗范围，等待加载完成后再截图。不要包含真实 Key、管理员密码、请求正文或个人数据。

Markdown 使用带说明的图片：

```markdown
![模型组及其路由策略](/images/model-groups.png)
```

路径由 VitePress 加上站点的 `base`。配图附近写清点击位置和完成后的状态。修改控件名称或操作流程时，同步检查截图和正文。

## GitHub Pages

仓库第一次接入时，在 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**。源码合并到 `main` 后，`.github/workflows/docs.yml` 会构建并发布文档。

默认站点地址：

<https://dyedd.github.io/lens/>

当前配置的 `base` 是 `/lens/`。如果改为其他仓库名或根域名，需同步修改 `base` 和 favicon 路径。

- 文档 PR：安装锁定依赖、构建文档并上传 Pages 产物。
- 文档合并到 `main`：构建成功后部署。
- 手动发布：运行 **Actions → Docs → Run workflow**，选择 `main`。
- 应用正式发版成功：Release 工作流调用 Docs，刷新文档与在线版本文件。
- 构建失败：查看日志中的链接、资源路径或 Markdown 编译错误，修正后重新运行。

PR 不会部署公开站点；需要预览时在本地运行 `pnpm preview`。

## 与应用 CI 和发版的关系

CI 根据实际文件变化判断是否需要应用检查。仅修改 `docs/**`、Markdown、`screenshots/**` 或文档工作流时，后端、前端和镜像任务跳过；混合修改应用代码时仍正常执行。

自动发版仍在每天 UTC 03:00 检查：自上一个版本标签起累计 5 个应用提交才发版。纯文档提交不计入；手动应用发版也至少需要 1 个应用提交。发布说明可以包含同时合入的文档改动。

`.dockerignore` 排除整个 `docs/`、截图和两个 README。文档依赖、缓存和构建输出都不会传入 Docker 构建上下文。

## 同步应用版本号

在仓库根目录运行升版本命令，默认递增 patch，并同时更新 `backend/app/__init__.py` 与 `docs/public/version.txt`：

```bash
uv run --no-sync python scripts/bump_version.py --dry-run
uv run --no-sync python scripts/bump_version.py
```

`--dry-run` 只输出下一版本，不写文件。Release 工作流复用同一命令，并传入 `--base-version`：若源码已提前升版本，就沿用源码版本；否则递增已发布版本的 patch。源码落后于基准时命令会报错。

应用的“版本检测”计划任务读取 <https://dyedd.github.io/lens/version.txt>，文件只包含一行版本号，例如 `0.2.14`。检测到更新后，界面链接到对应的 GitHub Release。

公开站点只提供成功发布的版本。Docs 部署时使用工作流令牌查询一次最新正式 Release，并据此生成构建产物中的 `version.txt`。因此，升版本提交后的镜像构建即使失败，站点也不会提前提示该版本；各个 Lens 实例无需请求 GitHub API。文档站不可访问或返回无效内容时，检测任务记录失败，并保留上一次成功的检测结果。
