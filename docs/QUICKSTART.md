# 快速上手 / Quick start

[中文首页](../README.md) · [English home](../README.en.md)

## 选对安装方式 / Pick the right package

Skill ZIP：放进现有宿主，不运行本地服务。Wheel (`.whl`)：带完整界面的工作台，Python 3.10+，不需要 Node。Source archive：面向开发，需要 Node.js 24.15+ 构建界面。不要把 GitHub 的 “Source code (zip)” 当成即装即用的应用。

The Skill ZIP is for an existing agent host. The wheel includes the built UI. Source archives require a frontend build. This repository does not promise a published PyPI package or a signed desktop installer.

**版本 / Version:** 双指缩放和译文批注需要 `2.0.0rc7` 或更新版本；安装包尚未生成时可使用下面的源码方式。rc5 不包含 `prc-demo`。预发布下载在 [Releases](https://github.com/ooooooomygosh/paper-research-coach/releases)，不要依赖 `/latest`。Check the version of the file you downloaded; main can be ahead of release packages.

## macOS / Linux：从 wheel 安装

在下载目录执行，将文件名替换成实际文件名。Use the actual downloaded filename.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install "./paper_research_coach-<版本>-py3-none-any.whl"
prc open
```

以后在同一虚拟环境运行 `prc open`。它启动或复用本机服务，并带入当前浏览器所需的访问凭证。不要复制或分享含 token 的启动链接。

## Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install ".\paper_research_coach-<version>-py3-none-any.whl"
.\.venv\Scripts\prc.exe open
```

直接运行环境里的程序，无需更改 PowerShell 执行策略。These commands avoid changing execution policy; Windows is not claimed as fully hardware-tested in this review.

## 第一轮阅读 / Your first reading

导入一篇本机 PDF。阅读目标可留空。选中一句或查看一张图，把当前疑问发给教练；可以明确说“直接解释”或“只给我一个提示”。不用先翻译整篇、连接 Zotero 或填写整套研究档案。AI 对话需要本机安装并登录的 Codex CLI；普通 PDF / 笔记操作不要求你先发送模型请求。

Import one local PDF; the goal is optional. Select a passage and ask one question. Direct explanation and small hints are both valid. Configure neither Zotero nor translation unless you need them. The workbench’s AI backend requires an installed, authenticated Codex CLI; ordinary PDF and note use does not require sending a model request.

## 不用私人论文体验 / Try without personal papers

```bash
prc-demo
# Optional: prc-demo --port 8767 --no-open
```

独立临时书库，合成论文和标明来源的示例笔记；不自动调用模型。默认端口 8766，主工作台默认 8765，不覆盖个人书库。终端保持运行，`Ctrl+C` 退出后清理。不是永久保存或部署方式；需要保留时先下载导出文件到临时目录之外。

A disposable synthetic library, not a live AI demonstration or a persistent installation. It does not alter your normal library. Keep the terminal running and export outside the temporary folder before stopping. A port conflict produces an error; use `--port` rather than stopping an unrelated service.

## 从源码运行 / Run the current source

Python 3.10+、Node.js 24.15+。以下使用 POSIX shell；Windows 使用对应虚拟环境内的 Python 与 prc 路径。

```bash
git clone https://github.com/ooooooomygosh/paper-research-coach.git
cd paper-research-coach
python3 -m venv .venv
source .venv/bin/activate
npm ci --prefix frontend
npm --prefix frontend run build
python scripts/prepare_licenses.py
python -m pip install -e '.[dev]'
prc-demo
```

审查 PR 时先 checkout 对应分支；不要误以为 main 已包含未合并改动。When reviewing a PR, check out its branch before building.

## 卡住时 / Troubleshooting

| 现象 / Symptom | 操作 / Action |
|---|---|
| `prc` 找不到 | 激活安装它的虚拟环境，或直接运行该环境下的可执行文件。Use the environment where you installed it. |
| `prc-demo` 找不到 | rc5 没有这个入口。使用本轮源码，或安装包含它的新 wheel。Do not assume an older download has it. |
| 浏览器要求连接本机 | 再运行 `prc open`，不要仅打开普通地址。每个浏览器需要自己的登录 cookie。 |
| PDF 打开了，但 AI 没连接 | 查看教练连接状态，检查本机 Codex CLI 登录。不要把模型密钥贴进问题报告。 |
| 源码运行提示没有前端 | 运行 `npm ci --prefix frontend` 和 `npm --prefix frontend run build`。 |
| 扫描 PDF 不能选中文字 | 先使用已有文字层的 PDF。当前不保证自动 OCR；可用框选图像讨论。 |
| 翻译组件不可用 | 翻译是可选模块。先正常读原文，再按 [工作台指南](WORKBENCH.md) 安装独立 BabelDOC 环境。 |

`prc doctor` 显示环境与数据目录。分享诊断前删除用户路径、论文题目等私人信息；永远不要提交 session-token、数据库、完整启动链接或模型凭证。

更多：[工作台指南](WORKBENCH.md) · [English workbench guide](WORKBENCH.en.md) · [安全边界](SECURITY.md)。
