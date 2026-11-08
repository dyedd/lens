import { defineConfig } from "vitepress";

export default defineConfig({
  lang: "zh-CN",
  title: "Lens",
  description: "Lens 多协议 LLM 网关：部署、使用、架构与插件开发文档。",
  base: "/lens/",
  cleanUrls: true,
  lastUpdated: true,
  head: [["link", { rel: "icon", href: "/lens/logo.svg" }]],
  themeConfig: {
    logo: "/logo.svg",
    nav: [
      { text: "使用指南", link: "/guide/quick-start" },
      { text: "配置参考", link: "/reference/configuration" },
      { text: "开发文档", link: "/development/setup" },
    ],
    sidebar: [
      {
        text: "部署与使用",
        items: [
          { text: "快速开始", link: "/guide/quick-start" },
          { text: "接入站点与模型", link: "/guide/sites" },
          { text: "管理模型组", link: "/guide/model-groups" },
          { text: "客户端接入", link: "/guide/clients" },
          { text: "查看用量与排查请求", link: "/guide/monitoring" },
          { text: "设置、备份与维护", link: "/guide/maintenance" },
        ],
      },
      {
        text: "配置参考",
        items: [{ text: "环境变量与网关设置", link: "/reference/configuration" }],
      },
      {
        text: "开发",
        items: [
          { text: "搭建开发环境", link: "/development/setup" },
          { text: "系统架构", link: "/development/architecture" },
          { text: "插件开发", link: "/development/plugins" },
          { text: "维护与发布文档", link: "/development/documentation" },
        ],
      },
    ],
    socialLinks: [{ icon: "github", link: "https://github.com/dyedd/lens" }],
    search: {
      provider: "local",
      options: {
        miniSearch: {
          options: {
            tokenize: (text) =>
              [...new Intl.Segmenter("zh-CN", { granularity: "word" }).segment(text)]
                .filter(({ isWordLike }) => isWordLike)
                .map(({ segment }) => segment),
          },
        },
        translations: {
          button: { buttonText: "搜索文档", buttonAriaLabel: "搜索文档" },
          modal: {
            displayDetails: "显示详细列表",
            resetButtonTitle: "清除搜索",
            backButtonTitle: "返回搜索",
            noResultsText: "未找到相关内容",
            footer: {
              selectText: "选择",
              selectKeyAriaLabel: "回车键",
              navigateText: "切换",
              navigateUpKeyAriaLabel: "向上键",
              navigateDownKeyAriaLabel: "向下键",
              closeText: "关闭",
              closeKeyAriaLabel: "退出键",
            },
          },
        },
      },
    },
    outline: { label: "本页目录", level: [2, 3] },
    docFooter: { prev: "上一页", next: "下一页" },
    lastUpdated: { text: "最后更新" },
    editLink: {
      pattern: "https://github.com/dyedd/lens/edit/main/docs/:path",
      text: "在 GitHub 上编辑此页",
    },
    sidebarMenuLabel: "目录",
    returnToTopLabel: "返回顶部",
    darkModeSwitchLabel: "外观",
    lightModeSwitchTitle: "切换到浅色模式",
    darkModeSwitchTitle: "切换到深色模式",
    footer: { message: "基于 MIT 许可发布。" },
  },
});
