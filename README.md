# Paper Research Coach

### 不止读懂论文。形成自己的研究判断。

把 **PDF 原文、一个具体问题和你的思考** 放在一起的本地阅读工作台，也是一套可独立安装的带读 Skill。面向想认真读懂、核实并迁移论文的研究者，而不是再生成一份摘要。

[English](README.en.md) · [开始使用](docs/QUICKSTART.md) · [工作台指南](docs/WORKBENCH.md) · [设计与审视](docs/FINAL-REVIEW.md)

[![Verification](https://github.com/ooooooomygosh/paper-research-coach/actions/workflows/verify.yml/badge.svg)](https://github.com/ooooooomygosh/paper-research-coach/actions/workflows/verify.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-526653.svg)](LICENSE)

> **预览软件，不是已验证的教学产品。** 当前源码准备发布 `2.0.0rc6`；合并并通过发布流程前，Releases 中的 rc5 不包含本轮改动，包括新增的 `prc-demo` 示例入口。

## 读论文时，它帮你做什么？

原文始终在场，AI 不代替你作判断。你可以从图、公式或一句不理解的英文开始，不用按固定顺序走完课程。

| 你正在遇到的事 | 工作台如何帮忙 |
|---|---|
| “我看懂了句子，但没明白作者发现了什么。” | 区分背景、独特观察和方法，先抓问题，再解释机制。 |
| “这张图真的能证明这个结论吗？” | 围绕同一证据页核对预算、对照、替代解释和适用边界。 |
| “英文和概念卡在一起了。” | 选中原文直接讨论；翻译、概念补充和论文论证分别讲，不要求先翻译整篇。 |
| “刚有一个想法，切换页面就丢了。” | 原话与 AI 评论分开保存，保留出处；返回原文，接续同一条阅读对话。 |
| “读完后，我的研究下一步是什么？” | 留下暂定判断、未解问题和最小检验，必要时导出笔记或汇报提纲。 |

一个典型回合，不是一整页总结：

> **你：** 这个提升会不会只是测量次数更多？  
> **教练：** 先核对图 1 中两组的测量预算。如果预算相同，这个解释还能成立吗？想直接听解释也可以。

*上面是写作示例，不是实时模型输出。读懂一个局部问题、决定跳过一篇论文，也都是有效结果。*

## 先选一种用法

### 只要 AI 带读：安装 Skill

从 [Releases](https://github.com/ooooooomygosh/paper-research-coach/releases) 下载 `paper-research-coach-skill-*.zip`，解压**完整文件夹**到宿主的技能目录。无需本项目的 Python、Node.js、Zotero 或单独模型密钥；使用宿主原有的模型配置。

| 宿主 | 用户级技能目录 |
|---|---|
| Codex | `~/.agents/skills/paper-research-coach/` |
| Claude Code | `~/.claude/skills/paper-research-coach/` |
| Pi | `~/.pi/agent/skills/paper-research-coach/` |

附上论文，说：**“用 paper-research-coach 带我读这篇论文，先从作者最关键的发现开始。”** 不要只复制 `SKILL.md`，它需要同目录的 references 与 assets。兼容规范不等于每个宿主和模型都已验证。

### 想边看原文边讨论：安装工作台

需要 **Python 3.10+**。从 [Releases](https://github.com/ooooooomygosh/paper-research-coach/releases) 下载 `.whl`，在下载目录运行：

```bash
python3 -m venv .venv
source .venv/bin/activate
# 将文件名替换为实际下载的 wheel；不要安装源码压缩包来代替它。
python -m pip install "./paper_research_coach-<版本>-py3-none-any.whl"
prc open
```

Windows、源码运行和安装失败处理见 [快速上手](docs/QUICKSTART.md)。**发布 wheel 已包含界面，日常使用不需要 Node.js。** 工作台内 AI 对话使用本机已登录的 Codex CLI；Skill 的多宿主兼容不代表工作台已经接入全部宿主。

打开后只做三件事：**导入一篇 PDF → 选中一处原文 → 提出当前问题。** 不必先设置 Zotero、整篇翻译或文献目录。

本轮版本新增独立示例入口：

```bash
prc-demo
```

它用三页原创合成材料打开临时书库，不读取个人文献，不自动调用模型，不自动授权记录或同步。端口默认 `8766`；按 `Ctrl+C` 退出并清理。需要保留的笔记请先导出到临时目录之外。rc5 用户请先使用本轮源码或安装包含它的新版本。

## 安静的界面，有边界的帮助

默认收起书库，把空间留给原文和对话。支持适宽、阅读位置恢复、可调整分栏、沉浸模式、PDF 搜索和导航。笔记、同步、模型设置放在次级工具中，不在每个回合要求你管理流程。

Zotero 同步、OneDrive / Obsidian 目录、整篇双语翻译、复习和汇报导出都是**可选**能力：[工作台指南](docs/WORKBENCH.md)。原文位置与用户原话优先；旧版 PDF 的位置不冒充新版证据。

## 数据去哪了？哪些事还不能保证？

PDF 与阅读记录存本机，服务只监听本机地址。**本地存储不等于离线 AI**：启用教练或翻译时，相关内容会发送到所配置的模型服务。Zotero 写入需明确授权；启动链接包含访问凭证，不要分享。备份与权限说明见 [安全指南](docs/SECURITY.md)。

当前没有学习收益的真人试验结论；未宣称 Safari / iPad / Apple Pencil 完整认证。它不是跨设备实时协作产品，也不支持自动可靠地识别所有扫描 PDF。多附件 Zotero 条目目前选择首个 PDF，请核对原文版本。详细边界见 [验证记录](docs/TESTING.md) 与 [审视清单](docs/FINAL-REVIEW.md)。

## 参与改进

[贡献指南](CONTRIBUTING.md) 包含开发环境、测试和截图复现方式。报告问题时，请描述“我本来要读什么、哪一步打断了我”，而不只是提出一个新按钮。不要上传私人 PDF、数据库、启动链接或模型凭证。

原创代码与文档采用 [MIT](LICENSE)。阅读方法来源与第三方许可分别见 [来源与致谢](docs/SOURCES.md) 和 [翻译组件说明](docs/THIRD_PARTY_TRANSLATION.md)。
