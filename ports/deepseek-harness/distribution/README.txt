Paper Research Coach · DeepSeek Harness 内置版 1.1.0

这是可以直接发给其他人的 Windows x64 离线依赖安装包。
兼容已验证版本：DeepSeek Harness 0.2.1-rc.5。
需要安装盘至少 1 GB、用户数据盘至少 4 GB 可用空间。
阅读分析调用接收方自己登录的 Harness 账户，正常使用需要网络。

安装
1. 先安装并启动 DeepSeek Harness 0.2.1-rc.5，登录自己的账户，然后退出（包括托盘）。
2. 将本 ZIP 完整解压到路径较短的普通本地目录（例如 C:\PRC）。不要在 ZIP 预览窗口里直接运行。
3. 双击“安装.cmd”。安装器会识别 Harness 目录；找不到时会弹窗选择 DeepSeek Harness.exe。
4. 按提示继续；只有安装目录受保护时才会出现 Windows 管理员授权提示。
5. 重新打开 Harness，点击左侧“论文研读”。不必单独安装 Python、Node、Codex CLI 或填写 API Key。

功能
1.1.0 新增两项内置功能，插件名称仍为 Paper Research Coach：
• 知识库学习：多份材料提取与来源映射、快速概览/系统学习、六模块交互学习页、
  概念关系与术语、方法库搜索/对比/应用、逐字引文核对、单元进度与笔记、练习与错题、
  有出处的知识库追问、构建停止/恢复、版本保留及 HTML/Markdown/知识库 ZIP 导出。
• 交互式讲解：基于问题、论文页或知识库生成图文互动页，复用 Answer me with HTML
  的流程图、时序图、树、公式、表格、问答等组件；可编辑草稿、修订、换主题、保存版本和导出。
两项功能统一使用接收方 Harness 登录账户，无需单独配置密钥。
同名概念按来源单元保留不同含义；单元笔记与练习按学习版本保存。
知识库回答仅依据本次检索片段，未检索到依据不表示整库没有。
交互讲解的历史版本仅供查看/导出；继续生成须返回当前草稿并核对来源。
学习模板内的主题、画像和页内笔记按知识库共享；方法搜索使用当前发布版本。
添加材料不会立即发起模型请求；点击构建、生成或发送后才调用账户。
长材料会分段多次请求。文本提取覆盖与逐字引文检查不代表独立语义完整性审查；
扫描页、图像及版面细节需另行核对。MOBI/AZW 需本机已有 Calibre。
升级旧版时，先退出 Harness，使用原包“卸载.cmd”，再安装新版；论文与学习数据保留。

1.0.1 修复 PDF 文字选区产生大量重叠方框的问题：按行合并、去重，文字使用柔和高亮，
仅手动框选区域保留边框。已有碎片批注也会合并显示；选区浮层按实际尺寸避让原文。
保留原项目的 PDF 阅读器和 UI、八章主线、任务卡、支线图文解释、公式与图表、
任务日志、复盘树及独立窗口、笔记与证据定位、翻译队列、中文/双语 PDF、
Zotero/目录同步、研究脉络、比较、想法、复习和导出。

分发
把整个 ZIP 发给对方即可。包内没有作者的登录凭证、账户配置、论文、对话或本机应用备份。
内置 Python、翻译字体和版面模型，安装依赖无需在线下载。
PDF 提取复用内置 PDFium，支持中文文字层和逐页定位；原版提取器所用 PyPDF2 也随包提供。
此包不包含 DeepSeek Harness 主程序；接收方必须自行安装兼容版本。

安装机制与数据
安装器在接收方本机备份并构建应用包，加入默认插件组合和插件管理清单。
不会更改已签名的 Harness.exe，也不会关闭应用的完整性校验。
不同宿主版本或不兼容的应用结构会被拒绝，原应用不被覆盖。
运行库复制到 Harness 用户目录的 builtin-plugins；应用内与用户配置均引用它。
论文和笔记位于 Harness 用户目录的 paper-research-coach。
备份与安装收据位于 plugin-installations/paper-research-coach。
用户目录通常是 %USERPROFILE%\.dsh；设置 DSH_HOME 时使用该目录。
安装成功后可以移动或删除本次解压目录。建议保留 ZIP，以便日后卸载或重新安装。

卸载
退出 Harness，重新解压同一份 ZIP，双击“卸载.cmd”。
应用包未被其他工具改变时恢复原包，仅移除本插件写入的配置，保留其他插件。
如官方更新已替换应用包，卸载会保留新版本，只移除本插件的用户配置。
如其他工具修改了仍含本插件的应用包，卸载会停止，防止覆盖其修改。
卸载保留论文、笔记、账号、运行库与备份。

排查
• “检查安装包.cmd”可核对每个发布文件的 SHA-256；不会安装或修改 Harness。
• 提示仍在运行：从托盘彻底退出 Harness 后再试。
• 提示版本不符：使用此包对应的 Harness 0.2.1-rc.5；未来版本需另行适配。
• 使用非默认配置时，在终端中运行：
  安装.cmd --installation "E:\Apps\DeepSeek Harness" --home "E:\HarnessData" --profile "E:\HarnessData\profiles\desktop"
• 不要通过右键“以管理员身份运行”启动安装脚本。普通双击即可，安装器按需请求授权，
  确保使用当前登录用户自己的账户和数据目录。

来源与许可
原项目：https://github.com/ooooooomygosh/paper-research-coach（2.0.0rc13）
学习功能：https://github.com/dmoshehun-prog/learn-from-materials（1.1.0，MIT）
交互页面：https://github.com/QingYunA/answer-me-with-html（0.5.10，MIT）
固定源码版本与嵌入式适配说明见 package/integrations/SOURCES.json 和 package/THIRD_PARTY.md。
说明见 package/THIRD_PARTY.md；源代码、原版 LICENSE 以及第三方许可均随包提供。
BabelDOC 为 AGPL-3.0；其 Python 源码和许可证包含在内置运行库中。
本包为第三方插件集成版，并非 DeepSeek 官方发行。
