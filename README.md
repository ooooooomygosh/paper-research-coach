<div align="center">

<img src="docs/images/logo.svg" width="88" height="88" alt="Paper Research Coach">

# Paper Research Coach

**不止读懂论文。形成自己的研究判断。**

把 **PDF 原文、你的问题和你的思考** 放在同一处的本地阅读工作台，也是一套可装进 Claude Code / Codex / Pi 的 AI 带读 Skill。<br>
它不替你写摘要，而是陪你一处一处核对证据，把判断留在你自己手里。

[![Verification](https://github.com/ooooooomygosh/paper-research-coach/actions/workflows/verify.yml/badge.svg)](https://github.com/ooooooomygosh/paper-research-coach/actions/workflows/verify.yml)
[![Release](https://img.shields.io/github/v/release/ooooooomygosh/paper-research-coach?include_prereleases&label=release&color=365c47)](https://github.com/ooooooomygosh/paper-research-coach/releases)
[![Python](https://img.shields.io/badge/python-3.10%2B-526653)](docs/QUICKSTART.md)
[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-Claude%20Code%20%C2%B7%20Codex%20%C2%B7%20Pi-7f9871)](#快速开始)
[![License: MIT](https://img.shields.io/badge/license-MIT-526653)](LICENSE)

**简体中文** · [English](README.en.md) · [快速上手](docs/QUICKSTART.md) · [阅读方法论](docs/METHOD.md) · [工作台指南](docs/WORKBENCH.md) · [设计说明](docs/DESIGN.md) · [参与贡献](CONTRIBUTING.md)

</div>

<br>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/reading-dark.webp">
  <img src="docs/images/reading.webp" alt="真实工作台：左侧 PDF 原文，右侧围绕同一处原文的带读对话；用户的问题下方附带所引用的原文。">
</picture>

<p align="center"><sub>真实界面，跟随系统深浅色 · 合成论文与明确标注的预设对话，非实时模型输出；截图时未连接模型 · <a href="docs/SHOWCASE.md">如何复现</a></sub></p>

> [!NOTE]
> **预览软件，不是已验证的教学产品。** 最新安装包在 [Releases](https://github.com/ooooooomygosh/paper-research-coach/releases) 页面**最上面**的版本（预发布版，所以 GitHub 的 “Latest” 标签不会指向它）。用 Claude Code 插件或 `npx skills add` 安装的 Skill 直接取自主分支，始终是最新的。

## 和“AI 总结论文”有什么不同

|  | 常见的 AI 论文助手 | Paper Research Coach |
|---|---|---|
| **一次给你什么** | 一整页摘要 | 一处原文、一个疑问、最多一个思考任务 |
| **谁来下判断** | AI 直接给结论 | 先给暂定判断，再用原文证据核对；你可以要提示、要直接解释，或请它反驳你 |
| **你的想法** | 散落在对话里 | 原话逐字保存，与 AI 评论分开，并带页码锚点 |
| **证据从哪来** | 难以回到出处 | 每条消息和笔记都能一键回到 PDF 原位；PDF 换版后旧锚点标为待核实 |
| **读完留下什么** | 又一份总结 | 暂定判断、未解问题和最小可检验的下一步 |
| **数据在哪** | 上传云端 | PDF 与笔记存本机；只有你发出的对话会交给所配置的模型 |

## 为什么这样读

研究表明，我们最常用的读法——重读、高亮、写摘要——恰恰是效果最弱的几种；材料在眼前时的“熟悉感”很容易冒充理解，而 AI 代写的流畅摘要会让这种错觉更严重。这套方法把力气花在**让你自己预测、核对、解释和回忆**上，综合了三类来源：

| 来源 | 代表 | 带来的做法 |
|---|---|---|
| 研究者经验 | 沈向洋·华刚“三个层次、四个阶段与十个问题”、王树义《如何高效读论文》（转述 Peter Carr）、Keshav、李沐、Nielsen、Hamming | 不逐字线性读：摘要→结论→图表→引言→讨论，方法最后、随时可停；速读/精读/研读；用十个问题检查覆盖；读完落到下一步研究 |
| 科学方法论 | Platt《Strong Inference》、Chamberlin 多重工作假说、Popper、Toulmin | 关键结论先列替代解释，找能区分它们的证据和强简单基线 |
| 学习科学 | 认知学徒制、脚手架、认知负荷、提取练习、生成效应、自我解释 | 一次一个动作；先预测再看证据；帮助按能力逐步撤去；原话保存；合上材料回忆 |

目标是每读一篇都把你往上推一级：从**消极阅读**（知道讲了什么）到**积极阅读**（有什么用）、**批判性阅读**（是否言之成理）、**创造性阅读**（我能用它做什么）。随身带走的一句话：每读一篇，都要能回答**这篇论文改变了什么判断、我凭什么相信它、它如何改变我的下一步**。

👉 七条原则、八步路线的由来、每条做法背后的理论与书单，见 **[阅读方法论](docs/METHOD.md)**。这些来源支持设计动机，不代表本工具的学习效果已被验证。

## 亮点

<table>
<tr>
<td width="33%" valign="top">

**💬 围绕原文对话**<br>
选中一句话，点“讨论这处”，引用会跟着你的问题一起发出，也会留在对话里。Enter 发送，Shift + Enter 换行。

</td>
<td width="33%" valign="top">

**🖍️ 标记与想法分开**<br>
高亮是论文的话，笔记是你的话。“原文标记”不会被当成你的观点拿去讨论；随时在同一处“写下想法”。

</td>
<td width="33%" valign="top">

**🧭 可以跑题，也能回来**<br>
八步阅读路线是证据地图，不是课程表。局部问题解决后，主线返回点仍在原处。

</td>
</tr>
<tr>
<td valign="top">

**🌗 让人专注的界面**<br>
默认收起书库，只留原文和对话。支持沉浸模式、深色模式、双指缩放、适宽和阅读位置恢复。

</td>
<td valign="top">

**🌐 照顾非母语阅读**<br>
区分语言障碍和概念障碍；不必先翻译整篇。可选的双语 PDF 中，高亮与笔记按译本分别保存。

</td>
<td valign="top">

**🔌 两种用法，一套方法**<br>
只想要 AI 带读就装 Skill；想边看原文边讨论就运行本地工作台。Zotero、翻译和导出都是可选项。

</td>
</tr>
</table>

<table>
<tr>
<td width="50%"><img src="docs/images/welcome.webp" alt="欢迎页：从一篇值得读的论文开始"></td>
<td width="50%"><img src="docs/images/annotations.webp" alt="双语 PDF 中分别保存的高亮与框选批注"></td>
</tr>
<tr>
<td align="center"><sub>首次打开：导入一篇 PDF 就能开始</sub></td>
<td align="center"><sub>双栏视图中按译本分别保存的高亮与框选（两栏均为合成英文，仅测试版式）</sub></td>
</tr>
</table>

## 快速开始

### 方式一：在 Claude Code 中使用（推荐）

```text
/plugin marketplace add ooooooomygosh/paper-research-coach
/plugin install paper-research-coach@paper-research-coach
```

然后附上论文，说：**“带我读这篇论文，先从作者最关键的发现开始。”** 使用宿主原有的模型配置，不需要本项目的 Python、Node.js、Zotero 或单独的模型密钥。

### 方式二：Codex、Pi 等其他宿主

```bash
npx skills add ooooooomygosh/paper-research-coach
```

<details>
<summary>不用 npx：手动安装 Skill</summary>

从 [Releases](https://github.com/ooooooomygosh/paper-research-coach/releases) 下载 `paper-research-coach-skill-*.zip`，把**完整文件夹**解压到宿主的技能目录：

| 宿主 | 用户级技能目录 |
|---|---|
| Codex | `~/.agents/skills/paper-research-coach/` |
| Claude Code | `~/.claude/skills/paper-research-coach/` |
| Pi | `~/.pi/agent/skills/paper-research-coach/` |

不要只复制 `SKILL.md`，它需要同目录的 `references` 与 `assets`。兼容规范不等于每个宿主和模型都已验证。

</details>

### 方式三：本地工作台（边看原文边讨论）

需要 **Python 3.10+**。从 [Releases](https://github.com/ooooooomygosh/paper-research-coach/releases) 下载 `.whl`，在下载目录运行：

```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install "./paper_research_coach-<版本>-py3-none-any.whl"   # 替换为实际文件名
prc open        # 打开你的书库
prc-demo        # 或者：先用三页合成论文试一试，不读取个人文献
```

打开后只做三件事：**导入一篇 PDF → 选中一处原文 → 提出当前问题。** 发布的 wheel 已包含界面，不需要 Node.js。工作台内的 AI 对话使用本机已登录的 Codex CLI；没有它也能正常阅读、标注和记笔记。Windows、源码运行和故障排查见[快速上手](docs/QUICKSTART.md)。

## 一个典型回合

> **你：** 这个提升会不会只是测量次数更多？
>
> **教练：** 先核对图 1 中两组的测量预算。如果预算相同，这个解释还能成立吗？想直接听解释也可以。

<sub>写作示例，不是实时模型输出。读懂一个局部问题、决定跳过一篇论文，也都是有效结果。</sub>

| 你正在遇到的事 | 它如何帮忙 |
|---|---|
| “我看懂了句子，但没明白作者发现了什么。” | 区分背景、独特观察和方法，先抓问题，再解释机制。 |
| “这张图真的能证明这个结论吗？” | 围绕同一证据页核对预算、对照、替代解释和适用边界。 |
| “英文和概念卡在一起了。” | 选中原文直接讨论；翻译、概念补充和论文论证分开讲。 |
| “刚有一个想法，切换页面就丢了。” | 原话与 AI 评论分开保存，保留出处；返回原文，接续同一条对话。 |
| “读完后，我的研究下一步是什么？” | 留下暂定判断、未解问题和最小检验，必要时导出笔记或汇报提纲。 |

## 数据与边界

- PDF 与阅读记录存本机，服务只监听本机地址。**本地存储不等于离线 AI**：启用教练或翻译时，相关内容会发送到所配置的模型服务。
- Zotero 写入需要你明确授权；启动链接包含访问凭证，不要分享。备份与权限说明见[安全指南](docs/SECURITY.md)。
- 目前没有学习收益的真人试验结论；未宣称 Safari / iPad / Apple Pencil 完整认证；不保证自动识别所有扫描 PDF；多附件的 Zotero 条目目前选择首个 PDF，请核对原文版本。详见[验证记录](docs/TESTING.md)与[审视清单](docs/FINAL-REVIEW.md)。

## 常见问题

<details>
<summary><b>需要额外付费或单独的 API Key 吗？</b></summary>

Skill 使用宿主（Claude Code、Codex、Pi）已有的模型配置。工作台的 AI 对话目前通过本机已登录的 Codex CLI 进行；不使用 AI 时，阅读、标注、笔记和导出都不需要模型。

</details>

<details>
<summary><b>它会自动给我“打分”或判断我是否掌握了吗？</b></summary>

不会。只有在你开启“记录实际回答与学习反馈”后，才会按具体能力保存一次表现，并引用你当时的原话和判断依据。点击按钮、读过 AI 解释、完成步骤数都不算掌握的证据。

</details>

<details>
<summary><b>能和 Zotero、Obsidian 一起用吗？</b></summary>

可以，但都是可选项。Zotero 同步需要 Zotero 10+ 开启本地 API 并由你授权；OneDrive / Obsidian 目录、整篇双语翻译、复习和汇报导出见[工作台指南](docs/WORKBENCH.md)。

</details>

<details>
<summary><b>扫描版 PDF 可以用吗？</b></summary>

当前不保证自动 OCR。可以用框选区域把图像发给教练讨论；空的文字层不等于空白页。

</details>

## 参与改进

报告问题时，请描述“我本来要读什么、哪一步打断了我”，而不只是提出一个新按钮。开发环境、测试和截图复现见[贡献指南](CONTRIBUTING.md)。请不要上传私人 PDF、数据库、启动链接或模型凭证。

如果这个项目对你有帮助，欢迎点一个 Star ⭐，这能让更多认真读论文的人找到它。

<a href="https://star-history.com/#ooooooomygosh/paper-research-coach&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=ooooooomygosh/paper-research-coach&type=Date&theme=dark">
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=ooooooomygosh/paper-research-coach&type=Date" width="600">
  </picture>
</a>

## 许可与致谢

原创代码与文档采用 [MIT](LICENSE)。阅读方法的来源与第三方许可分别见[来源与致谢](docs/SOURCES.md)和[翻译组件说明](docs/THIRD_PARTY_TRANSLATION.md)。
