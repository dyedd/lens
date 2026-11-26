# 维护与发布文档

文档站源码位于主分支 `docs/` 目录，使用 VitePress `1.6.4` 构建。功能变更与对应文档更新可以在同一个 PR 中一并提交。

## 本地预览与构建

在 `docs/` 目录安装依赖并启动开发服务：

```bash
cd docs
pnpm install --frozen-lockfile
pnpm dev
```

访问终端提示的本地地址并进入 `/lens/` 路径。提交前请运行生产构建与预览，VitePress 构建阶段会自动校验站内链接有效性：

```bash
pnpm build
pnpm preview
```

## 目录与内容分工

| 路径 | 职责边界 |
| --- | --- |
| `README.md` / `README_EN.md` | 仓库门面：核心价值、能力矩阵、1 分钟启动、代表性截图与文档/贡献入口（避免与指南重复长篇操作） |
| `docs/guide/` | 面向用户的操作与排错指南（部署、渠道接入、模型组、客户端、监控隐私、设置迁移） |
| `docs/reference/` | 参数级参考手册（环境变量、网关设置键、冷却公式、隐私规则字段与限额） |
| `docs/development/` | 面向贡献者与深度用户：环境搭建（`setup.md`）、系统设计（`architecture.md`）、工作流（`workflow.md`）、源码解析（`source-guide.md`）、文档维护（`documentation.md`） |
| `docs/diagrams/` 与 `docs/public/images/` | 机制图 Mermaid 源文件与导出的 SVG，以及控制台脱敏截图 |
| `docs/public/version.txt` | 与 `backend/app/__init__.py` 同步的源码版本号 |
| `docs/.vitepress/config.ts` | 导航栏、侧边栏、本地中文分词搜索与 Pages 基础路径配置 |

新增文档页面时，记得同步更新 `docs/.vitepress/config.ts` 的 `sidebar` 并在首页 `docs/index.md` 或相关页面补充链接。

## 更新控制台截图

1. 使用 `LENS_DATABASE_URL` 启动一个隔离的演示数据库（参见 [搭建开发环境](./setup#隔离开发数据库（强烈推荐）)）。
2. 录入明显可辨认为虚构演示数据的站点名称、虚拟 Key 与测试请求。
3. 将截取的清晰界面图片保存到 `docs/public/images/`，在 Markdown 中使用 `/images/文件名.png`（VitePress 会自动拼接 `/lens/` 前缀）。
4. 切勿在截图或示例中包含真实上游 Key、管理员密码或生产业务隐私数据。

## GitHub Pages 与 CI / Release 联动

- **文档构建与发布（`.github/workflows/docs.yml`）**：
  - 针对 `docs/**` 或 `docs.yml` 的 PR 会执行 `pnpm build` 验证链接并上传构建产物（不部署公网站点）；
  - 合入 `main` 后自动构建并部署到 <https://dyedd.github.io/lens/>；
  - 公开站点的 `version.txt` 会在发布步骤中通过 `gh release view` 查询**最新正式 Release** 版本生成，避免预发版提前触发实例更新提示。
- **与应用 CI 的隔离（`.github/workflows/build.yml`）**：
  - 当提交仅修改 `docs/**`、`*.md`、`screenshots/**` 或 `.github/workflows/docs.yml` 时，CI 会自动跳过后端测试、前端构建与 Docker 镜像任务；
  - 每天 UTC `03:00` 检查的自动发版工作流（`release.yml`）也只统计应用代码提交数（累计 5 个应用提交触发自动发版），纯文档提交不计入。
- **版本同步工具**：发版脚本使用 `uv run --no-sync python scripts/bump_version.py` 同步更新 `backend/app/__init__.py` 与 `docs/public/version.txt`（支持 `--dry-run` 预演）。
