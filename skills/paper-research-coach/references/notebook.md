# 原话、评论与断点

## 写入原则

获得用户同意后，实质想法按原话保存，包括不完整、犹豫和后来证明错误的内容。AI评论是另一条 author=assistant 的记录，使用 PAPER/EXTERNAL/INFERENCE/IDEA 标签并在 links 中关联用户笔记 ID。用户后来修正可作为新笔记或有历史的显式编辑。不得悄悄删除先前误解。

用户拒绝记录时不写思想笔记，不以“后台自动整理”绕过拒绝。不要反复询问。在笔记编辑器主动输入就是该条笔记的保存请求；对话自动捕获为原话笔记则检查 Session.note_consent。工作台对话历史在本机保存，原话笔记是额外的研究记录。权限可随时撤回。

位置至少记录论文 ID 与版本、PDF 页索引或未定位状态。印刷页码可为罗马数字或附录编号；不是 PDF 页索引。摘录、section、figure、rects 有什么写什么。只有实际核实的位置才标 verified。PDF区域坐标采用未旋转 PDF user-space，左下角原点；不要从文本猜坐标。

在工作台中以 SQLite 为准。Markdown/CSV是导出视图，不能把两套文件当作并列权威状态。每次提交有 operation_id 和 expected_revision；冲突时重读并保留双方，不默认覆盖。

## 无工作台时

使用项目中的 `paper-notes/<paper-slug>/notes.md` 与 `session.md`，先确认这是用户愿意保存笔记的目录。不要扫描无关私人目录。没有文件工具时，只在对话中给出可复制文本，不声称后台已保存。

以下是可显式导入工作台的笔记块。每条使用唯一稳定 ID；一段思想只产生一条用户记录。`content` 是两标记间的原始文本，示例中的空格/换行也视为原话。

```markdown
<!-- prc-note {"id":"thought-001","author":"user","provenance":"USER"} -->
我怀疑这里的增益只是来自额外的信息，而不是这个模块本身。
<!-- /prc-note -->

<!-- prc-note {"id":"comment-001","author":"assistant","provenance":"INFERENCE","links":["thought-001"]} -->
可以用信息预算匹配的对照区分这两个解释；当前节选没有报告该对照。
<!-- /prc-note -->
```

已核实位置可在 JSON 元数据加入完整 `anchor`；没有完整版本信息时使用 unresolved，导入后再定位。不要把 `<paper-id>` 占位符作为真实ID写入。

```text
prc import-markdown PAPER_ID /absolute/path/to/notes.md
```

相同 ID、相同内容重复导入不产生第二条笔记；同 ID 不同内容要求明确另存或修订。此操作只导入 notes，随后根据 session.md 显式提交 Session 断点。

## 断点只保留必要信息

论文与版本；本轮目标；depth与stage；当前位置；已经建立的一个关键认识；未完成问题；一项下一步；具体能力的帮助程度；对话笔记授权状态。可使用 assets/session.md。

暂停时先保存再说明已保存。恢复先读取，引用用户尚未讨论的想法接上。AI只有实际回应一条笔记后才能将 discussed=true；保存笔记不表示已经理解或讨论。
