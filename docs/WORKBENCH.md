# 工作台使用指南

[项目首页](../README.md) · [快速上手](QUICKSTART.md) · [English](WORKBENCH.en.md)

本指南对应当前源码；安装包功能以下载版本为准。历史 Zotero 和宿主测试见 [验证记录](TESTING.md)，不是本轮重新验证的声明。安装只需查看快速上手，不必先完成下面所有配置。

## 阅读与持续对话

用 `prc open` 启动或复用本机服务并连接浏览器。新浏览器也通过这个入口认证。macOS 安装后可使用仓库中的 `scripts/open-workbench.command`；不要分享带 token 的启动链接。

阅读时默认收起书库，宽屏约 70% PDF／30% 对话，可拖动分隔线；窄屏上下排列。PDF 默认适宽，按论文与版本保存页码、页内位置和缩放。页码输入后按 Enter 或离开输入框才跳转，Esc 取消编辑。

沉浸模式保留 PDF 和对话，靠近上边缘或键盘聚焦时显示操作，触屏保留小入口。快捷键是 Cmd / Ctrl + Shift + Enter。Esc 按层关闭弹窗、工具、选区，再退出沉浸；切换不清空草稿。

每篇论文绑定一条本地阅读对话和一个原生 Codex 线程。刷新、重新打开、服务重启或切换教练模型沿用该线程。旧对话在“更多 → 教练”中只读查看。`prc open --paper PAPER_ID` 与 `prc coach send --file message.txt --wait` 继续同一对话；兼容的 `--new` 参数也沿用当前绑定。恢复失败时保留原绑定和消息，创建结果未知时先查回。

自动初始化说明最多 3000 字符，普通回合自动位置提示最多 300 字符。用户原话、明确选区和主动附图单独保留；整页文字、整套笔记与历史副本不默认重复发送，教练按需读页、看图和查记录。开场约 100–200 字，普通解释约 200–500 字；需要推导时可以展开。

“更多 → 教练”提供帮助偏好、主线、模型和连接；“更多 → 笔记”保存原话与独立评论。你可以直接问当前句子、要求解释或只要提示，不必先翻译整篇。八步是完整核查的覆盖范围，不是局部解释的门禁；点击继续、AI 解释或英文流畅不等于掌握。原话笔记授权与实际表现记录授权分别控制。

## 可选：整篇双语翻译

“更多 → 翻译”独立选择模型和思考深度，沿用本机 Codex 登录，可以与教练不同。默认配置为 GPT-6-Luna / low；以连接中实际可用的模型列表为准。启动时锁定模型和语言。

默认同时处理 2 篇论文、共 4 个模型请求，可在设置调整为 1–4 篇及 1–8 个请求。多个浏览器共用后台队列。设置中的批量翻译支持标题、作者、年份搜索与勾选；已有当前版本译文或任务会复用。关闭网页不会停止后台任务，但电脑和服务需保持运行。

中文及中英并排 PDF 生成后即可读，不必等待句子对齐。对齐期间可查对应段落；可靠句子映射完成后可查对应中文。“讨论这处”附上原文及原始位置，不把译文坐标当成源证据。**没有译文时也能直接讨论原文选区。**

组件固定 BabelDOC 0.6.4，建议独立 Python 3.12 环境。先安装 [uv](https://docs.astral.sh/uv/)，将路径替换成 `prc doctor` 的 `data_dir`：

```bash
uv venv --python 3.12 "/path/to/prc-data/babeldoc-env"
uv pip install --python "/path/to/prc-data/babeldoc-env/bin/python" "BabelDOC==0.6.4"
```

Windows 解释器为 `babeldoc-env/Scripts/python.exe`。已有环境可在启动前设置 `PRC_BABELDOC_PYTHON`。基础工作台支持 Python 3.10+；翻译组件版本限制与许可见 [第三方说明](THIRD_PARTY_TRANSLATION.md)。不必为了翻译重新安装基础工作台，也无需另外提供模型密钥；仍需有效的 Codex 登录和模型使用权限。

首次翻译下载上游版面、字体及分词资源，随后复用缓存。配置快照、段落缓存和任务保存在本机，按论文版本、模型、语言和组件版本区分。服务重启自动恢复未完成队列，已有 PDF 则继续对齐；主动停止的任务保持停止。换版后旧译文存档并退出当前视图。自动写回 Zotero、跨设备翻译同步和独立模型 API 后端不在此功能范围内。

## 可选：Zotero 10 同步

打开 Zotero 的本机应用通信设置，在工作台“Zotero 与设置”选择个人文献库集合，然后在 **Zotero 自身弹窗** 授权。持续同步需要“始终允许”；一次“允许”不等于永久写权限。

书目和附件来自 Zotero，笔记、高亮与可编辑文字批注支持往返修改。当前采用条目的第一个 PDF 附件。多附件或多版本请先确认主 PDF，避免混用坐标；本轮没有新增附件选择器。已下载 PDF 只读使用。

同时修改保留双方版本并提示选择；删除需要确认，不自动删除论文或附件。换版后旧位置待重新核实。无位置的想法保存为关联笔记，核实矩形的位置可写为原生批注。离线先保存本机，连接恢复再重试。

Zotero 授权键可访问所有可编辑文献库，本应用另行限定所选集合。键保存在系统凭证库或进程内存，不进入源码和导出。接口实测范围、未覆盖类型见 [验证记录](TESTING.md)。

## 可选：OneDrive / Obsidian 文献目录

先选择 Zotero 集合并授权，再填写本机文献目录，或运行：

```bash
prc vault configure --path /path/to/literature
prc vault scan
prc vault status
prc service install
```

`service install` 在 macOS 注册登录服务；电脑睡眠或退出登录时暂停。其他平台使用 `prc serve`。默认每 10 分钟检查目录和 Zotero，也可在阅读工具中“刷新同步”。`prc service status` 查看状态，`prc service stop` 停止后台服务。

新 PDF 按实际内容去重，已有相同附件则复用条目、保留原分类；新文件通过链接附件关联，不搬动原文件。多条 Zotero 记录对应同一文件时提示处理，不随意选取。

支持既有 `01_论文卡片` 的 `原文PDF路径` / `原文PDF` 元数据。原卡作为只读外部材料保留用户与 AI 来源，模型审读不视为学生掌握。新笔记与可编辑 Zotero 笔记写入 `06_PRC阅读记录/<论文编号>/`，修订文件追加而非覆盖。编辑既有版本会回读，并保留并发冲突；新建 Markdown 初始为作者待确认的外部资料。

PDF 改版使旧锚点失效，暂时不可用或删除不删除工作台记录。只有字节一致的 PDF 才允许写回区域坐标。SQLite、授权和同步队列留在本机，只有导出的笔记进入指定目录并由 OneDrive 同步；原卡、模板、Obsidian 设置和既有自动化不改写。

创建 Zotero 书目前核对 PDF 首页题名，再查询 Crossref、arXiv 和可选 OpenAlex，按顺序保存作者。未获可靠结果则保留本机论文并列入待核实，不创建空作者条目、不阻止其他论文同步。查询只发送 DOI 或题名，不上传 PDF。

```bash
prc metadata openalex-key
prc metadata resolve --paper PAPER_ID --refresh
prc metadata status
```

## 保存、复习与导出

笔记、对话、研究想法、进度和复习原始回答先存本机。Zotero 和文件夹同步仅在连接、授权后执行。复习先凭记忆回答，再获取反馈；默认间隔 1 / 3 / 7 / 14 天可调整，不发送系统通知。

```bash
prc doctor
prc import /path/to/paper.pdf --title "Paper title" --goal "我需要判断什么"
prc list
prc context PAPER_ID
prc resume PAPER_ID
prc text PAPER_ID 0
prc commit /path/to/transaction.json
prc history NOTE_ID
prc replace-source PAPER_ID /path/to/new-version.pdf
prc import-markdown PAPER_ID /path/to/notes.md
prc export paper --paper PAPER_ID
prc export ideas --paper PAPER_ID
prc export talk --paper PAPER_ID
prc export comparison
prc export pdf --paper PAPER_ID
```

`text` 使用从 0 开始的 PDF 页索引。结构化提交接受 JSON 文件或标准输入，含防重操作 ID、版本检查；不要将用户原话拼成命令。导出为 Markdown 论文卡、研究问题卡、汇报提纲、比较 CSV 和独立批注 PDF。未定位或旧版笔记仍保留在卡片中，不误画到新版 PDF。

## 开发、版本与数据边界

开发安装与排错见 [快速上手](QUICKSTART.md)，检查命令见 [贡献指南](../CONTRIBUTING.md)，合成界面展示见 [SHOWCASE.md](SHOWCASE.md)。`prc-demo` 使用临时书库，退出前须导出要保留的内容。

`python scripts/package_release.py` 在 `dist/` 输出 Skill ZIP、wheel 和源码 sdist。main 上验证成功后为当前版本建立预览版；同版本保留原发布物，不覆盖，升级版本才建立新预览版。

SQLite 是权威状态，Markdown/CSV 是导出。本地保存不等于离线 AI。备份、模型数据流和访问边界见 [安全指南](SECURITY.md)。测试通过不等于教育效果，见 [真人试读协议](HUMAN-TRIAL.md) 与 [审视清单](FINAL-REVIEW.md)。原创代码与文档采用 [MIT](../LICENSE)，第三方保留自身许可与 [来源](SOURCES.md)。
