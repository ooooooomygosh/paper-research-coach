# Paper Research Coach

**把一篇论文读成自己的研究判断。**

面向研究生的带读 skill 和本地阅读工作台：选论文 → 抓住贡献 → 检验证据 → 留下思考 → 形成研究问题 → 复习与汇报。默认中文，也可跟随用户语言。

**当前为 2.0.0rc4 预览版。** 本地工作台、OneDrive 目录连接与 Zotero 10.0.4 核心往返已实测。不同宿主、特殊批注与真人试读范围见验证记录。

[English](README.en.md) · [体验审视与改进路线](docs/EXPERIENCE-REVIEW.md) · [完整设计思考](docs/DESIGN.md) · [来源与致谢](docs/SOURCES.md) · [验证记录](docs/TESTING.md)

## 一轮阅读是什么样

> 先看图 1 中预算相同的两组结果。你刚才怀疑“只是额外信息的收益”，这个对照正好能检验它。先预测一下：如果这个解释成立，预算匹配后差距应该怎样变化？

教练只推进一个具体动作。想直接听答案就直接讲；可以回看材料、插话、暂停，也可以不记笔记。不会把每篇论文都变成固定页数的摘要。

- **贡献与证据**：最少背景后形成暂定判断，核对最近前作、核心机制与最有区分力的证据。
- **逐渐独立**：按贡献判断、机制解释、证据解读等具体能力，调整“示范／共同完成／仅提示／独立完成”。
- **忠实记录**：用户原话与 AI 评论分开，保留位置、来源类别、关联与修订历史。
- **研究问题**：从失败、矛盾、机制或成本进入，形成可证伪假设、简单强基线和最小检验。
- **持续积累**：查看有依据的论文关系、统一比较表、下一篇候选和可调整的复习队列。

## 两种使用方式

### 只安装 skill

不需要 Python、Node.js、Zotero 或额外 AI key。下载 skill 压缩包，解压得到整个 `paper-research-coach` 文件夹，放入任一宿主的技能目录：

| 宿主 | 用户级目录 |
|---|---|
| Codex | `~/.agents/skills/paper-research-coach/` |
| Claude Code | `~/.claude/skills/paper-research-coach/` |
| Pi | `~/.pi/agent/skills/paper-research-coach/` |

在新会话中附上论文，说“用 paper-research-coach 开始跟读”即可。研究目标和可用时间可以补充，不要求专门编写 prompt。有文件工具时使用 Markdown 笔记；没有工具时也可以纯文本带读。不要只复制主入口，references 和 assets 是完整技能的一部分。

规范兼容不等于所有模型都已通过实测；具体宿主与模型范围见 [验证记录](docs/TESTING.md)。

### 加上本地阅读工作台

需要 Python 3.10+。在 [GitHub Releases](https://github.com/ooooooomygosh/paper-research-coach/releases) 下载 `.whl` 安装包。前端已经包含在包内，日常使用不用安装 Node.js。

```bash
python3 -m venv ~/.venvs/paper-research-coach
source ~/.venvs/paper-research-coach/bin/activate
python -m pip install /path/to/paper_research_coach-2.0.0rc4-py3-none-any.whl
prc install-skill --host codex
prc serve
```

将 `codex` 换成 `claude` 或 `pi` 可安装到相应目录。Windows 使用 `python -m venv`，并运行虚拟环境中的 `Scripts/Activate.ps1`。软件支持 Python 3.10+；跨操作系统实测范围单独记录。

macOS 完成上述安装后，可双击仓库中的 `scripts/open-workbench.command` 打开界面，也可运行 `prc open`。它复用已经运行的服务，未运行时自动启动，并向浏览器带入本机登录信息。不同浏览器首次连接需要分别通过这个入口打开；不要只复制不含登录信息的普通地址。

浏览器打开后，导入 PDF 或连接 Zotero。在阅读页右侧“教练对话”点击“开始跟读”，无需先输入提示词；选中文字或框选图表后提问，页码、选区和阅读断点会自动带入。回复逐步显示，可以停止，刷新后恢复。教练使用本机 Codex CLI 的现有配置，并在每轮显式加载本项目 skill。图表讨论可勾选“同时发送当前整页图像（不只是选区）”；跨页选区需先返回该页再附图。

每篇论文沿用八步主线：阅读目标 → 独特贡献 → 问题设定 → 方法机制 → 证据核查 → 边界与判断 → 研究启发 → 回忆与复习。“继续主线”推进当前步骤；有待回答问题且无选区时，普通发送默认回答主线，也可在“本轮意图”显式选择插话。选区讨论和批注快捷按钮属于插话，回答后回到原断点。帮助方式可选“一起推敲/只给提示/直接解释/检验我的判断”，不改写你的原话，也不代表能力评分。完整八步和本轮实际回忆记录都完成后，才显示本轮结束；刷新、新建对话或切换旧对话保留这篇论文的主线。

“阅读笔记”保留原话与独立 AI 评论；“讨论待讨论笔记”把记录直接交给教练。下一步、研究想法和复习题可以由教练保存并在工作台继续。对话记录保存在本机；阅读设置可控制是否额外生成原话笔记。**“已保存”与“AI 已讨论”是两个状态。** PDF 中持续显示当前版本已核实的批注；可以适宽阅读并从本页批注列表定位。已有文字的笔记不会因浏览新选区自动改出处，需要明确重新绑定。主线“已核查”可展开依据，但不等于独立掌握。

从 CLI 打开绑定论文的会话：`prc open --paper PAPER_ID`；加 `--new` 为这篇论文新建对话。工作台的会话选择器只显示当前论文的旧对话，“新对话”另开空白记录，切换论文时分别恢复各自的选择。`prc coach send --file message.txt --wait` 在 CLI 继续同一条工作台对话；省略论文 ID 时沿用工作台当前选择。工作台不读取 CLI 的全部对话历史。实时工作台当前支持 Codex CLI；纯 skill 仍支持 Codex、Claude Code 与 Pi。

消息与选中的论文材料经 CLI 发给其配置的模型服务，凭证由 CLI 管理。工作台只在你发送消息时启动推理，无需另设模型密钥。

## Zotero 10 双向同步

1. 打开 Zotero，在“设置 → 高级”启用本机应用通信。
2. 工作台打开“Zotero 与设置”，读取并选择一个个人文献库集合。
3. 点击授权，在 **Zotero 自身弹窗** 中作出选择。持续同步需要“始终允许”；“允许”只给一次写入。
4. 工作台运行时定期同步。失联时先在本地保存，恢复后重试。

书目和附件信息从 Zotero 获取；笔记、高亮与可编辑文字批注支持往返修改。首次连接采用条目的第一个 PDF 附件；多版本请使用独立条目或明确管理主 PDF，避免把不同附件的坐标混在一起。已下载 PDF 作为只读来源。

两侧同时改过会保留双方版本并提示选择；删除等待确认。不会自动删除论文或附件。PDF 换版后旧位置标为待重新核实。没有位置的想法作为关联笔记，有核实矩形的内容作为原生批注。

Zotero 的授权键本身可访问所有可编辑文献库，本应用另行限定所选集合。键存系统凭证库或进程内存，不放源码和导出中。真实接口测试范围与仍需确认项见 [TESTING.md](docs/TESTING.md)。

## 连接 OneDrive / Obsidian 文献目录

先在工作台选择 Zotero 集合并授权，再在“Zotero 连接”中填写文献目录。也可运行：

```bash
prc vault configure --path /path/to/literature
prc vault scan
prc vault status
prc service install
```

`service install` 在 macOS 注册登录后自动运行的本地服务；关闭阅读窗口仍持续检查，电脑睡眠或退出登录期间暂停。每 30 秒检查目录，Zotero 运行时每 5 秒同步。其他平台运行 `prc serve`。`prc service status` 查看状态，`prc service stop` 停止当前后台服务。

- 新增 PDF 按实际内容去重。已有相同附件时复用 Zotero 条目并保留原分类；新增文件以链接附件关联，原 PDF 不搬动。多条 Zotero 记录对应同一文件时提示处理重复项。
- 支持已有 `01_论文卡片` 中的 `原文PDF路径` / `原文PDF` 元数据。卡片保留原话和 AI 来源，作为只读外部资料接入；“模型审读完成”不会被视为学生已掌握。
- 新笔记与可编辑的 Zotero 笔记写入 `06_PRC阅读记录/<论文编号>/`。`r` 后数字表示修订版本，内容文件只追加、不覆盖；编辑已有版本会回读到工作台，同时修改时保留冲突。新建 Markdown 初始标为作者待确认的外部资料。
- PDF 改版会使旧锚点失效；文件暂时不可用或删除不会删除工作台记录。已有 Zotero 存储附件仍保持原样，只有字节一致的 PDF 才允许写回区域坐标。

SQLite、授权与同步队列留在本机应用目录。只有导出的笔记进入选定文件夹并由 OneDrive 同步。原卡、模板、Obsidian 设置及既有自动化不被改写。

新建 Zotero 书目前，工作台用 PDF 首页核对正式题名，再查询 Crossref、arXiv 和可选的 OpenAlex，按顺序逐人保存作者。查不到可靠信息时保留本地论文并列入待核实，不创建空作者条目，也不阻止其他论文同步。仅发送 DOI 或题名，不上传 PDF。可运行 `prc metadata openalex-key` 把自己的 OpenAlex key 保存在系统钥匙串；`prc metadata resolve --paper <论文ID> --refresh` 重新核实，`prc metadata status` 查看来源记录。

## 每天怎样使用

1. 双击启动入口，或在 Codex 中说“用 paper-research-coach 打开工作台”。新浏览器也通过启动入口连接。
2. 新论文可在页面“导入论文”选择已下载的 PDF；也可先用 Zotero Connector 保存论文，再将它放进工作台选中的集合，工作台自动索引。无需为每篇论文重新安装软件。
3. 选择论文后点“开始跟读”，以后点“继续主线”。对话选择器只管理这篇论文；“新对话”清空对话上下文，论文的笔记和主线仍保留。
4. 选中文字或框选图表，在“阅读笔记”写下想法；点击位置标签可回到出处。在“教练对话”提问或讨论待讨论笔记，评论另存，原话保留。
5. 下次打开“继续阅读”接上断点；到“复习队列”先凭记忆回答，记录帮助程度与实际表现，保存后回到教练获取反馈。默认间隔为 1／3／7／14 天。

笔记、对话、研究想法、阅读进度和复习回答首先保存到本机应用数据目录。已授权 Zotero 时，笔记和批注同步到对应条目；连接文献目录后，笔记修订写入 `06_PRC阅读记录` 并由 OneDrive 同步。复习记录与对话保存在本机，GitHub 只发布软件与 Skill。页面“导出”可保存论文卡、研究想法、比较表和独立批注 PDF。

## 常用操作

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

`prc --data-dir /path/to/library serve` 可使用独立数据目录。`text` 使用从0开始的PDF页索引。结构化提交接受 JSON 文件或标准输入，使用操作ID防重和版本检查；不要把用户原话拼入命令文本。

导出包括 Markdown 论文卡、研究问题卡、汇报提纲、比较 CSV 与独立批注 PDF。未定位或旧版本笔记仍在论文卡中，不会被错误画到新版PDF上。默认复习间隔1／3／7／14天可修改，不发送系统通知。

## 从源码运行与验证

```bash
git clone https://github.com/ooooooomygosh/paper-research-coach.git
cd paper-research-coach
python3 -m venv .venv
source .venv/bin/activate
npm ci --prefix frontend
npm --prefix frontend test
npm --prefix frontend run build
python scripts/prepare_licenses.py
python -m pip install -e '.[dev]'
pytest -q
python scripts/validate_skill.py
prc serve
```

生成合成教学示例：

```bash
python examples/create_demo.py .prc/demo
prc --data-dir .prc/demo serve
```

构建安装包：`python scripts/package_release.py`。输出的 skill ZIP、Python wheel 与源码 sdist 位于 `dist/`。源码开发需要 Node.js 24.15+，发布包运行不需要。

通过全部检查的 main 分支构建为当前版本建立预览版并附上两个安装包。同版本的后续构建保留既有发布物；升级版本时发布新的预览版。

## 数据、证据与许可

SQLite 保存权威状态及历史；Markdown 和 CSV 从它生成。个人论文、阅读记录、授权和运行状态不进入仓库。备份、访问控制与问题报告见 [SECURITY.md](docs/SECURITY.md)。

软件通过测试不等于教学效果已被证明。我们提供 [真人试读协议](docs/HUMAN-TRIAL.md)，观察理解准确性、独立解释、迁移和所需帮助量；当前没有真人学习收益数据。

项目原创代码与文档采用 [MIT](LICENSE)。感谢 Research-Starter-Kit、cangjie-skill，以及 Keshav、Sweeney、Nielsen、CREATE、QALMRI、认知学徒制与提取练习相关作者。第三方资料仅引用和独立改写，不将其全文纳入 MIT；随包分发的 PDF.js、React、Lucide 等保留各自许可。
