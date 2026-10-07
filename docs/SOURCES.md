# 来源与证据层级

本 skill 将研究者经验、教学研究和产品设计判断分开。来源支持设计动机，不代表已验证本工具的教学效果。下面是独立改写的方法记录，不包含第三方全文。

| 来源 | 性质与已核实范围 | 采用的方法 → 行为 → 验证 |
|---|---|---|
| [Keshav, How to Read a Paper (2007)](https://web.stanford.edu/class/ee384m/Handouts/HowtoReadPaper.pdf) | 作者经验；全文 | 分层投入 → 深度与是否继续的决策 → 跳读/停止场景 |
| [Miriam Sweeney, How to Read for Grad School (2012)](https://miriamsweeney.net/2012/06/20/readforgradschool/) | 作者经验；网页全文 | 目的驱动与主动阅读 → 先定义阅读目标 → 新手有限时间场景 |
| [Research-Starter-Kit](https://github.com/LAMDA-NeSy/Research-Starter-Kit) | 科研经验；仓库及用户提供的五份阅读/找论文/ideas/科研/汇报文档 | 种子文献、朴素解法、机制、失败与听众 → selection/research/talk → 对应行为用例 |
| [Hoskins, Stevens & Nehm (2007), CREATE](https://www.animalbehaviorsociety.org/web/downloads/Hoskins%20et%20al.%202007%20CREATE.pdf) | 教学研究；原论文 | 对原始文献主动分析并思考后续实验 → 预测与检验 → 区分解释场景；尚无本工具学习收益试验 |
| [Brosowsky & Parshina (2017), QALMRI chapter](https://attentionandlearninglab.com/papers/2017_BrosowskyParshina.pdf) | 教学方法；原始章节 | 问题、替代解释、逻辑、方法、结果、推论 → claim/evidence 链 → 不充分证据场景 |
| [Collins, Brown & Holum (1991), Cognitive Apprenticeship](https://www.aft.org/ae/winter1991/collins_brown_holum) | 教学理论；原文 | 示范、辅导、逐步撤去支持 → 按具体能力调整 → 卡住/迁移场景 |
| [Karpicke & Blunt (2011)](https://doi.org/10.1126/science.1199327) | 提取练习实验；论文摘要与发表信息 | 主动重建知识 → 先回答再核对 → 保存答案和帮助量；1/3/7/14天并非该研究结论 |
| [Michael A. Nielsen, Principles of Effective Research (2004)](https://aykuterdem.github.io/resources/principles-of-effective-research.pdf) | 作者经验；全文，Aykut Erdem为托管者 | 问题选择与持续反思 → 最小检验与停止条件 → 无收益空间场景 |
| [李沐论文阅读分享的 Huwei 笔记](https://huweim.github.io/post/总结_如何读论文李沐/) | 二手整理；网页 | 结合研究动机与结构化读法 → 最少背景后抓贡献 → 来源层级检查 |
| [Peng Sida, learning_research](https://github.com/pengsida/learning_research) | 作者经验；README及入门内容，进阶外链未全部读到 | 用研究问题组织文献 → 单一检索问题 → 下一篇理由检查 |
| 王树义《如何高效读论文？》（知乎专栏 / 公众号“玉树芝兰”） | 作者经验；用户提供的 PDF 全文（2026-10-07 已读） | 按载体可靠程度排优先级、转述 Peter W. Carr 的非线性读法顺序（摘要→结论→图表→引言→结果讨论→方法）、随时停止、笔记以“不必再读原文”为标准、生词先记后查 → questions.md 读法顺序与卡点分流、selection.md 优先级、notebook.md 笔记标准 → linear-grind、park-unknown-term 场景 |
| 沈向洋、华刚《读科研论文的三个层次、四个阶段与十个问题》（微软亚洲研究院知乎账号） | 研究者经验；用户提供的 PDF 全文（2026-10-07 已读） | 速读/精读/研读，消极→积极→批判→创造性阅读，Kajiya 引言五问，批判性阅读问题（引自 Mitzenmacher），卡住时的路径，半页 review 与口头报告，华刚“十个问题”模板阅读 → questions.md、reading-flow.md 十问映射、review-talk.md 半页评述 → ten-questions-close、critical-to-creative 场景 |

规范与工程参考：[Agent Skills](https://agentskills.io/specification)、[cangjie-skill](https://github.com/kangarooking/cangjie-skill)、[Zotero local API](https://www.zotero.org/support/dev/web_api/v3/local_api)。借鉴 cangjie 的来源核验、能力拆解和行为验证思路；不宣称通过其完整流水线认证。

用户提供的两篇知乎文章最初访问受限，2026-10-07 由用户以 PDF 提供全文后已读并列入上表；全文不放入公开仓库。Research-Starter-Kit 部分致谢外链仍访问受限，不作为已读全文证据。两篇文章转引的 Peter W. Carr 读论文视频、Jim Kajiya《How to Get Your SIGGRAPH Paper Rejected》、[Michael Mitzenmacher《How to Read a Research Paper》](https://www.eecs.harvard.edu/~michaelm/postscripts/ReadPaper.pdf)、Pinker《风格感觉》“网、树、线”一章与万维钢《用强力研读书》仅经由转述采用，未单独核实原文。书籍《学术研究，你的成功之道》（凌晓峰、杨强）与 Science Research Writing 仅核实书目/简介，不把章节建议写成已核实内容。仓库完整设计说明另列访问范围与未采用内容。

### 本次体验审视的补充核验（2026-09-30）

[Bastani et al., PNAS 2025, doi:10.1073/pnas.2422633122](https://doi.org/10.1073/pnas.2422633122) 是高中数学情境的随机实验：有 AI 时的表现不能直接代表移除 AI 后的学习，受约束辅导的结果也不能推广成“任何苏格拉底提示词都有效”。这里只据此要求分别报告辅助任务表现与无辅助学习表现，不声称已验证博士论文阅读收益。

本次查看 [Keshav 作者文稿（2016-02-17 版本，Columbia 托管）](https://systems.cs.columbia.edu/ds2-class/papers/keshav-paper.pdf) 的两页全文：采用分层投入、允许筛选停止、重建论证三个设计启发，不将经验建议当成本产品试验结论。Zotero 本地 API 的实例、对象版本和授权范围按官方文档核实；主机/版本集成仍需实机验收。

### 方法论背景文献（2026-10-07 补充）

以下文献用于解释 [阅读方法论](METHOD.md) 中各项做法的理论动机。核实范围为：按发表信息核对书目与 DOI，并以学界通行的核心结论为准；未逐章复述，也不把它们当作本工具有效性的证据。

| 来源 | 性质 | 支撑的做法 |
|---|---|---|
| [Dunlosky et al. (2013), Improving Students' Learning With Effective Learning Techniques](https://doi.org/10.1177/1529100612453266) | 学习策略综述 | 不以摘要、高亮、重读为主；优先主动回忆与分散复习 |
| [Koriat & Bjork (2005), Illusions of competence](https://doi.org/10.1037/0278-7393.31.2.187) | 元认知实验 | 熟悉感不等于掌握；先回答再核对 |
| [Rozenblit & Keil (2002), The illusion of explanatory depth](https://doi.org/10.1207/s15516709cog2605_1) | 认知实验 | 要求逐步解释机制，而不是只问“懂了吗” |
| [Platt (1964), Strong Inference](https://doi.org/10.1126/science.146.3642.347) | 科学方法论 | 替代假设与能区分它们的关键检验 |
| [Chamberlin (1890), The Method of Multiple Working Hypotheses](https://doi.org/10.1126/science.ns-15.366.92) | 科学方法论 | 同时保留多个解释，避免过早认定 |
| [Slamecka & Graf (1978), The generation effect](https://doi.org/10.1037/0278-7393.4.6.592) | 记忆实验 | 先让学习者生成判断或预测 |
| [Kornell, Hays & Bjork (2009), Unsuccessful retrieval attempts enhance subsequent learning](https://doi.org/10.1037/a0015729) | 记忆实验 | 允许先猜错再看证据 |
| [Wood, Bruner & Ross (1976), The role of tutoring in problem solving](https://doi.org/10.1111/j.1469-7610.1976.tb00381.x) | 教学研究 | “脚手架”式帮助与逐步撤去 |
| [Sweller (1988), Cognitive load during problem solving](https://doi.org/10.1207/s15516709cog1202_4) | 认知负荷理论 | 一轮一个动作、至多一个思考任务 |
| [Kalyuga et al. (2003), The expertise reversal effect](https://doi.org/10.1207/S15326985EP3801_4) | 教学研究 | 帮助按具体能力和实际表现调整 |
| [Chi et al. (1994), Eliciting self-explanations improves understanding](https://doi.org/10.1207/s15516709cog1803_3) | 学习实验 | 保存并推进学习者自己的解释 |
| [Chi & Wylie (2014), The ICAP Framework](https://doi.org/10.1080/00461520.2014.965823) | 学习投入框架 | 从被动阅读走向建构与互动 |
| [Roediger & Karpicke (2006), Test-enhanced learning](https://doi.org/10.1111/j.1467-9280.2006.01693.x) | 记忆实验 | 回忆题与复习队列 |
| [Cepeda et al. (2006), Distributed practice in verbal recall tasks](https://doi.org/10.1037/0033-2909.132.3.354) | 元分析 | 间隔复习；具体间隔仍为可调起点 |
| [Alon (2009), How to Choose a Good Scientific Problem](https://doi.org/10.1016/j.molcel.2009.09.013) | 研究者经验 | 从阅读走向选题；可行性与兴趣 |
| [Schwartz (2008), The importance of stupidity in scientific research](https://doi.org/10.1242/jcs.033340) | 研究者经验 | 允许停止与“不知道”；未知是研究常态 |
| [Hamming (1986), You and Your Research](https://www.cs.virginia.edu/~robins/YouAndYourResearch.html) | 研究者经验；演讲文字稿 | 阅读服务于重要问题 |

书籍（仅核实书目，作为延伸阅读，不引用具体章节）：Adler & Van Doren《How to Read a Book》（1972 修订版）；Brown, Roediger & McDaniel《Make It Stick》（2014）；Booth, Colomb & Williams《The Craft of Research》；Toulmin《The Uses of Argument》（1958）；Popper《The Logic of Scientific Discovery》；Hamming《The Art of Doing Science and Engineering》（1997）；Ling & Yang《Crafting Your Research Future》（中文版《学术研究，你的成功之道》）。Bjork 的“合意困难”概念以 Kornell, Hays & Bjork (2009) 等实验为代表引用。
