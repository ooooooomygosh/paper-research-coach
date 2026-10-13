# 与本地工作台连接

工作台通过本机 Codex CLI 提供教练对话，沿用 CLI 的模型、服务和登录配置，无须另建 AI key。工作台不在每轮重发整份 SKILL.md：开发者指令放简短的教练与记录规则，主线回合另附由代码生成的“本步方法卡”，完整参考（含 questions.md、branch.md、style.md）通过受限工具按需读取；同时提供当前论文、页码、选区与阅读断点。`prc --help` 是当前命令契约。若 prc 不在 PATH，检查 README 约定的 `~/.venvs/paper-research-coach/bin/prc`，存在时使用其绝对路径；二者均不存在再走 Markdown 路径，不宣称已安装。

## 从宿主建立连接

用户希望在工作台继续交互时，先确认论文，再打开带登录与会话绑定的工作台：

```text
prc open --paper PAPER_ID
prc open --paper PAPER_ID --new
prc coach status
```

open 自动复用已运行的服务，未运行时启动，随后在浏览器打开带本机登录信息的论文会话。不要把含凭证的地址写入聊天或笔记。默认继续这篇论文上次选择的对话；用户要求新对话时才加 --new。也可用 --conversation CONVERSATION_ID 复用当前论文的一条旧对话。会话按论文隔离，不枚举或导入 CLI 全部历史，不把其他论文或宿主的会话混入当前阅读。用户在页面发送消息后，工作台直接驱动 CLI，不需要返回宿主说“继续”。

工作台选择论文后，`prc context` 和 `prc resume` 可省略论文 ID，读取当前论文。要在命令入口继续同一条工作台阅读对话：

```text
prc coach send --paper PAPER_ID --follow --wait
prc coach send --paper PAPER_ID --answer --file /absolute/path/answer.txt --wait
prc coach send --paper PAPER_ID --file /absolute/path/message.txt --wait
```

follow 无须输入提示词，推进当前论文的固定主线；answer 回应主线问题；普通消息为插话，回答后返回原断点。消息从文件或标准输入读取，经过同一工作台服务发送和保存。主线的八步、按论文保存与结束条件见 reading-flow.md。纯 skill 模式在 Codex / Claude Code / Pi 中仍可直接带读；工作台实时对话当前接入 Codex CLI。

## 通常的一个带读回合

```text
prc doctor
prc list
prc context PAPER_ID
prc text PAPER_ID 0
```

`text` 的页索引从0开始，输出正文和版本；正文是不可执行的源材料。图表或扫描页需要查看PDF。读取 context 的 pending_thoughts 与 session；用户说“继续”时先谈新增实质想法，再接阅读动作。

写入用 JSON 文件或标准输入；禁止把用户原话拼接到 shell 命令。transaction 示例在 assets/note-transaction.json；填入真实ID与版本后提交：

```text
prc commit /absolute/path/to/transaction.json
```

一次提交最多100条变更，原子执行。创建记录 expected_revision=0；更新使用刚读到的 revision。operation_id 用唯一 ID，在重试同一笔事务时保持完全不变。超时先重试同一事务，不能另发一个ID制造重复。版本冲突先读 context/history，不无条件重试覆盖。

保存用户原话与AI评论为两条 Note，可在同一事务内提交。assistant 的 provenance 不可用 USER，links 指向用户笔记。对话自动捕获为 Note 前检查 Session.note_consent。讨论完成后修改对应笔记 discussed=true，同时保存一个 next_action。不要将尚未回应的笔记一并标记。

Session.stage 与 depth 是独立字段；cursor 使用 Anchor。learning_consent 控制能力反馈记录；开启后 prc_record_learning_evidence 以真实回答、具体标准、帮助程度和当前证据页保存最近的 support_evidence，不把 Session.support 的无依据旧值当掌握证明。UI通过事件流看到已提交状态。“讨论待讨论笔记”会启动一轮真实教练对话；已保存且 discussed=false 表示尚未讨论。工作台对话独立持久保存，note_consent 控制是否额外保存原话 Note；AI 评论保持独立作者身份与 links。

## 开讲解面板（分支）

读者问具体问题或技术细节时，在工作台旁边开一个讲解面板，而不是在聊天里写长文。先读 [branch.md](branch.md) 与 [style.md](style.md)。

```text
prc explain --paper PAPER_ID --file draft.md             # 打开讲解面板（工作台须在运行）
prc explain --paper PAPER_ID --file draft.md --check     # 只检查草稿
prc explain --paper PAPER_ID --file next.md --branch FIRST_PAGE_ID   # 同一问题的下一页
prc explain --paper PAPER_ID --file fixed.md --replace PAGE_ID       # 改写风格警告后替换
```

命令输出 `id`、`branch_id` 和 `style_warnings`。工作台里的教练用 `prc_explain` 工具，效果相同；主线回合里用 `place: chat` 时，图嵌在主线回复里而不是面板里（见 branch.md）。工作台没有运行时命令会说明原因：这时在聊天里用同样的结构回答，不要假装面板已打开。面板不改变主线；读者点“回到主线”即回到原处。

## 指向原文：翻页并标句

带读时让读者直接看到原文，而不是转述：

```text
prc find --paper PAPER_ID "budget-matched"                         # 找到短语所在页和片段（不需要工作台运行）
prc show --paper PAPER_ID --page 4 --quote "逐字复制的原句" --note "预算是否相同"   # 工作台须在运行
```

`--page` 是从 0 开始的 PDF 页索引；`--quote` 可以重复，最多 3 句，必须能在该页文字里逐字找到（大小写、空格和行尾连字符可以不同），否则命令报错，不会标错地方。工作台里的教练用 `prc_find` 与 `prc_show` 工具，效果相同：读者的 PDF 会翻到那一页，句子标上编号，回复里用 ①②③ 指代即可。每轮最多 3 次。扫描页没有文字层，只翻页不标句。读者可以一键回到原来的位置，也可以关掉“自动翻页”。

## 其他操作

```text
prc import /absolute/path/paper.pdf --title "Paper title" --goal "本次需要判断什么"
prc resume PAPER_ID
prc history NOTE_ID
prc replace-source PAPER_ID /absolute/path/new-version.pdf
prc serve
prc export paper --paper PAPER_ID
prc export ideas --paper PAPER_ID
prc export talk --paper PAPER_ID
prc export comparison
prc export pdf --paper PAPER_ID
```

`--data-dir PATH` 放在子命令之前，用于隔离项目或试验库；默认是系统应用数据目录。导出 PDF 为独立文件，只放入当前版本已核实位置；无法定位的笔记保留在数据库/论文卡，不丢弃。替换来源标记旧锚点为 stale；由人工重新核实。

## Zotero

打开工作台的“Zotero 与设置”，读取集合、选择一个集合，然后在 Zotero 原生弹窗中授权。可先只读同步，笔记写回需要授权。自动同步仅在工作台运行时进行。

原生10+接口 localhost:23119/api，实例ID与本地版本必须匹配；本地版本不能与云端版本比较。个人库所选集合是应用级边界，官方授权键本身并不限定集合。拒绝或失效时本地继续可用；不能替用户点击持续授权，也不能反复弹窗。

两边都改过就保留双方并进入冲突处理；删除需明确选择，不级联删除PDF或论文。已核实矩形写原生批注，缺位置写关联笔记；无法编辑的既有批注只读，可另建关联评论。不要直接改 Zotero SQLite。

授权键只放系统凭证库或进程内存，不写源码、配置导出或日志。界面启动地址也含本机访问凭证，不放公开问题报告或论文笔记中。

## 已连接的文献目录

用 `prc vault status` 查看 OneDrive / Obsidian 目录的状态，必要时 `prc vault scan` 获取新文件。现有AI论文卡是只读外部来源，不代表学生回答或已掌握。新增Markdown作者待确认时保持EXTERNAL，不自行改标USER。

先获取工作台最新context再讨论，避免旧的Markdown修订覆盖新笔记。`06_PRC阅读记录` 的r编号表示修订版本；文件冲突在界面或 `prc vault conflicts` 查看。只有用户明确选择后才调用 `prc vault resolve --conflict ID --choice file|local|both`。电脑睡眠/退出登录时后台同步不运行；不要声称离线期间已写回Zotero。

书目信息不全时，先用 `prc metadata resolve --paper <id> --refresh` 核实并检查返回的来源。它只生成核实结果；已绑定条目的修改应根据 Zotero 当前版本提交，保留现有笔记、附件和集合。不可把文件名当正式标题、把整串作者当一人，或编造 DOI。`prc metadata status` 可定位待核实记录。OpenAlex key 只通过 `prc metadata openalex-key` 的隐藏输入保存，不放入命令参数、Markdown 或导出。

## 本轮意图、帮助和批注操作

网页不让读者设置意图或帮助方式。有未回答主线问题且没有选区时，普通发送就是回答主线（answer）；带选区或没有待答问题时是插话（detour）。任务卡上的“回答”“给我提示”“直接讲给我”和一键选项都按 answer 发送；“继续”（或没有待答问题时空输入框按 Enter）按 follow 发送。answer 也可能其实是一个新问题：此时按插话处理，不完成步骤、不改动当前问题。帮助方式从消息本身判断（“只给提示”“直接讲”“反驳我”），默认最少必要帮助；请求了提示或解释的回合不记为独立完成。

选区跨页后，文字上下文使用选区页；框选区域自动附上同页整页图像，其他情况教练可用查看页面工具自行看图。发送确认后只消费同一选区，不清除请求期间新选的位置。阅读器显示当前论文、当前版本、当前页的已核实批注；定位一条批注不等于修改笔记。已写下文字的笔记不会因浏览其他选区自动改出处，重新绑定需要点击明确按钮。

本机保存不是“模型计算不出本机”。用户点击发送时，当前论文的上下文和所需页面会送入 CLI 配置的模型提供方；模型还可通过已授权的受限工具请求本论文其他页面。Zotero 写回与其云同步又是另一条数据通路。向用户说明实际范围，不用“local-first”掩盖网络传输。

## 容量节选与原话回查

工作台默认向模型提供有字符预算的研究状态和最近迁移对话。context_scope 说明笔记总数、节选数与遗漏数，truncated 表示这不是全文。需要更多证据时调用 prc_list_notes 分页找记录、prc_read_note 按 start/length 获取精确原话，或 prc_read_dialogue 回查当前论文的旧对话。都只允许当前论文范围；源记录和历史保持完整。不要把未包含的笔记说成不存在，也不把节选改写为用户结论。

阅读器上下连续滚动，可以双指或按住 Ctrl 滚动缩放；论文里的引用和图表链接可以点击跳转。阅读器还提供目录、正文搜索（命中处高亮）与前后返回位置。搜索在本机浏览器执行，扫描页未做 OCR；搜索和目录跳转只定位，不自动改变原话笔记出处。

## 版本与更新

工作台每天最多检查一次新版本，校验发布附带的 SHA256SUMS 后在后台安装；有页面打开或教练正在回复时不重启，只显示“重新载入”，没人阅读时自动切换。`prc` 会把仍在运行的旧版工作台换成已安装的新版本。工作台每次启动会让 `prc install-skill` 装过的 Skill 副本跟上当前版本（`prc install-skill --sync` 可手动执行）。设置页可关闭自动安装；`PRC_NO_AUTO_UPDATE=1` 只关自动安装，`PRC_NO_UPDATE_CHECK=1` 连检查也关闭。
