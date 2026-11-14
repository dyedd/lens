---
layout: home

hero:
  name: Lens
  text: 一个入口，连接多个模型供应商
  tagline: 统一管理上游凭证、模型组、协议转换和故障转移。
  image:
    src: /logo.svg
    alt: Lens
  actions:
    - theme: brand
      text: 部署并开始使用
      link: /guide/quick-start
    - theme: alt
      text: 了解系统架构
      link: /development/architecture

features:
  - title: 接入上游
    details: 按站点维护地址和凭证，获取模型，再通过模型组对外提供统一名称。
    link: /guide/sites
  - title: 接入客户端
    details: 支持 OpenAI、Anthropic、Gemini 等入口；对话协议可按成员配置转换。
    link: /guide/clients
  - title: 查看请求
    details: 从概览查看用量，在请求日志中检查耗时、费用和每次上游尝试。
    link: /guide/monitoring
---

## 从这里开始

| 你要完成的事 | 文档 |
| --- | --- |
| 在服务器部署 Lens | [快速开始](./guide/quick-start) |
| 接入服务商并设置主备模型 | [站点与模型](./guide/sites) · [模型组](./guide/model-groups) |
| 给客户端配置 URL、Key 和模型名 | [客户端接入](./guide/clients) |
| 排查失败、冷却和费用 | [用量与请求日志](./guide/monitoring) |
| 备份与升级 | [设置与维护](./guide/maintenance) |
| 修改代码 | [开发环境](./development/setup) · [系统架构](./development/architecture) |

## 管理界面

![Lens 概览：请求量、Token、费用与趋势](/images/overview.png)

本文档中的界面截图来自本地运行的 Lens，使用虚构站点、凭证和请求数据。截图中的价格与用量只用于说明界面。
