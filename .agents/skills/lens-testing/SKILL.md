---
name: lens-testing
description: 指导 Lens 后端 HTTP 接口测试的设计与编写，以覆盖核心功能正常成功流程为主。
---

# Lens 后端接口测试

## 核心目标

验证核心 HTTP 接口在合法输入下的端到端完成度，确保外部契约（HTTP contract）稳定并返回预期数据。测试重心在于守住真实业务主线，而非穷举内部实现细节。

## 编写原则

- **入口与途径**：测试文件位于 `backend/tests/api/test_<area>_api.py`，所有请求必须通过 `client` 夹具发起，真实穿透 HTTP 路由与中间件。严禁绕过 HTTP 直接调用服务层或手动组装 `Request`。
- **流程精简与闭环**：每个核心业务域仅保留一条主线成功流程。管理端 CRUD 集中在单个用例内闭环验证（列表 → 新增 → 查看 → 修改 → 删除）；网关路由通过单条用例集中覆盖所支持的公开协议入口；代理上游、模型同步、请求日志等流程仅保留一条代表性成功链路。
- **状态准备**：依赖公开接口或公共夹具构建前置状态，优先复用 `admin_headers`、`create_site`、`create_model_group`、`create_gateway_key`、`create_regex_rule` 等共享 fixture。
- **Mock 边界**：Mock 必须严格限制在网络边界（如替换 upstream 发送实现），确保鉴权、路由决策、协议转换与日志等完整链路真实执行；路由分发层可打桩下一层代理入口函数，避免重复向下穿透。严禁直接 mock 待测函数本身。
- **断言与命名**：测试名称直接描述业务成功预期（如 `test_site_crud_round_trip`）。仅断言 HTTP 状态码与调用方依赖的关键数据；不重复断言框架默认行为（如全局统一的未授权拦截、Pydantic 禁止额外字段的 schema 校验等），不依赖无序集合的返回顺序。

## 维护步骤

1. **确定改动范围**：结合 `git status --short` 识别目标接口及对应的测试文件。
2. **增补与同步**：接口新增或外部契约发生变化时，在对应领域测试中补充或调整最短的正常成功流程；内部重构只要未改变外部契约，无需新增测试。
3. **局部格式化**：仅格式化和修复改动触碰的文件。
4. **运行测试套件**：先用单文件验证改动，再并行跑通后端 API 全量测试，确保套件全绿。
5. **收尾与状态确认**：通过 `git diff --check` 和 `git status --short` 确保无异常空格、临时文件或未预期的工作区变动。

## 常用命令

所有后端命令均从仓库根目录执行，且必须使用 `uv run --no-sync`：

```bash
# 格式化与静态检查（仅针对触碰的文件）
uv run --no-sync ruff format <paths>
uv run --no-sync ruff check --fix <paths>

# 调试单业务域测试（串行）
uv run --no-sync python -m pytest backend/tests/api/test_<area>_api.py -q --confcutdir=backend/tests

# 完整后端 API 测试（并行）
uv run --no-sync python -m pytest backend/tests/api -q --confcutdir=backend/tests -n auto --dist worksteal
```

依赖安装与同步遵循仓库现有的 `uv sync --locked`（或镜像环境下的 `uv sync --frozen`）规范。
