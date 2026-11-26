---
layout: home

hero:
  name: Lens
  text: 一个入口，连接多个模型供应商
  tagline: 统一管理上游站点、凭证密钥、模型组路由、协议转换、熔断冷却与费用日志。
  image:
    src: /logo.svg
    alt: Lens
  actions:
    - theme: brand
      text: 部署并开始使用
      link: /guide/quick-start
    - theme: alt
      text: 系统架构与源码
      link: /development/architecture

features:
  - title: 上游站点与模型发现
    details: 按站点维护多地址、多密钥与代理规则，自动同步上游模型目录并支持 6 种外部平台备份一键导入。
    link: /guide/sites
  - title: 模型组路由与故障切换
    details: 通过执行组与别名组解耦客户端模型名，支持故障切换、平滑轮询、协议转换与推理强度后缀。
    link: /guide/model-groups
  - title: 可观测性与隐私保护
    details: 追踪每次上游尝试、首字延迟与成本倍率，提供基于本地规则的隐私脱敏与可逆恢复。
    link: /guide/monitoring
  - title: 工作流与源码解析
    details: 从请求编排、Unified IR 协议转换、熔断状态机到前后端模块与扩展配方，完整拆解源码实现。
    link: /development/source-guide
---

## 按目标阅读文档

| 你要完成的事 | 推荐文档 |
| --- | --- |
| 使用 Docker Compose / 1Panel 部署并首次登录 | [快速开始与部署](./guide/quick-start) |
| 接入供应商、测试模型连通性与批量导入 | [接入站点与模型](./guide/sites) |
| 配置主备切换、平滑轮询、别名与匹配规则 | [管理模型组与路由](./guide/model-groups) |
| 在 OpenAI / Anthropic / Gemini SDK、Codex、Claude Code 中使用 | [客户端接入](./guide/clients) |
| 排查 401/429/503、查看尝试链、开启规则隐私 | [监控、隐私与排错](./guide/monitoring) |
| 配置全局参数、同步价格、计划任务与全量备份迁移 | [设置、计费、备份与迁移](./guide/maintenance) · [配置参考](./reference/configuration) |
| 理解系统设计、运行工作流与源码目录结构 | [系统架构](./development/architecture) · [核心工作流](./development/workflow) · [源码解析](./development/source-guide) |

## 管理界面

![Lens 概览：请求量、Token、费用与趋势](/images/overview.png)

> 本文档中的界面截图来自本地运行的 Lens，使用虚构站点、凭证与请求数据，仅用于说明控制台功能与布局。
