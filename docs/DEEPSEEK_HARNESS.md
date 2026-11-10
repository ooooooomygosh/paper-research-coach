# 在 DeepSeek Harness 中使用 Paper Research Coach 1.3.1

从 Harness 侧栏“论文研读”进入。插件使用当前登录账户，工作台内核为 **2.0.0rc15**，无需另填 API Key 或启动 Codex CLI。

## 安装

本次发布面向 **macOS Apple silicon**，原生测试宿主为 **Harness 0.2.2-rc.1**。

1. 在 [DSH 1.3.1 Release](https://github.com/ooooooomygosh/paper-research-coach/releases/tag/dsh-v1.3.1) 下载 `PRC-DSH-1.3.1-mac.zip`。
2. 完全退出 Harness 及托盘，解压 ZIP，双击 `安装.command`。
3. 重新打开 Harness，从侧栏进入“论文研读”。

同一 Release 提供 `dsh-release.json`、ZIP `.sha256` 和 `SHA256SUMS`。独立工作台的 wheel/Skill ZIP 用于另外的入口，不能作为 DSH 插件安装包。源码安装见 [macOS 构建](../ports/deepseek-harness/macos/README.md)。

Windows 历史包为 `PRC-DSH-1.2.0-win-x64.zip`。本次没有新版 Windows 分发和原生安装验证；请勿把旧包描述成 1.3.1。

## 阅读、批注和讲解

在中文或双语 PDF 上划线提问，保留当前语言和位置；点击引文才定位，带读可跟随证据。只能匹配到段落时说明对应范围，无法可靠匹配时保持待核实。

页面标记连接完整批注；用户笔记在 PDF、研读页和图谱共用原记录。保存批注不改原 PDF；下载时生成含批注副本。Zotero 原附件只接收可靠原始坐标。

短回答留在对话里，知识详解可展开到大阅读区，与论文并排、全屏或主动开独立窗口。窄窗口使用全宽切换。切换展示保持追问草稿和阅读点，不触发重新生成。

四阶段为“判断是否值得读 → 理解关键机制 → 核查证据与边界 → 形成并回忆自己的判断”，可跳转、暂放；速览、理解和研读有各自结束条件。旧八步记录与原话保留，继续时接续原问题和位置。

“论文对照批注”按选段、章节或全文建立索引，逐段生成、停止续做、修订和导出。离线 HTML 内嵌图片与字体，用户批注是导出时快照。[具体操作与边界](../ports/deepseek-harness/docs/BILINGUAL-READING.md)

## DSH 插件更新

安装 1.3.1 后，由插件宿主检查本仓库的 **`dsh-v*` 专属发布**。默认定期检查，核对宿主版本、平台和 SHA-256 后后台暂存整包；在下次完全退出 Harness 并重新打开时安装，运行中的阅读进程不替换。

“设置 → 版本与更新”显示实际 DSH 插件版本、已准备的版本和提示，可点击“检查 DSH 插件更新”。`staged` 表示下载与校验已完成、等待下次启动，不表示当前窗口已经换版。检查失败或没有兼容平台资产时继续使用当前版本。1.3.1 之前的版本首次升级需使用安装包。

目前自动安装只提供 macOS arm64 资产，Windows 不会安装 macOS 包。DSH 内的独立 wheel 自动更新保持关闭；`prc update` 面向独立工作台。机器、宿主或平台变化后需要重新核验兼容性。

## 数据与回退

数据默认在 `~/.dsh/paper-research-coach`；Windows 默认 `%USERPROFILE%\.dsh\paper-research-coach`；设置 `DSH_HOME` 时跟随它。升级保留论文、译文缓存、笔记、对话和旧八步记录，新增阅读计划不覆盖旧 Session。

运行中的 SQLite 数据库应使用 backup API 形成一致性快照，不只复制主数据库文件。更新保留上一版和备份；安装失败或新后端未确认时按更新器状态恢复。手动回退时使用匹配的数据快照，不让旧程序保存新版独有记录。外部编辑导出 HTML 不会自动写回书库。

## 验证

源代码回归、合成浏览器交互、旧数据副本升级、离线零外部请求及真实账户的合成 PDF 问答/高亮分别记录。自动更新使用隔离清单与本地包测试；本次不把它描述为已经完成未来版本的公网自动升级。没有真实 Zotero 写入和真人学习效果结论。[完整记录](../ports/deepseek-harness/docs/BILINGUAL-READING.md)

## English

**Paper Research Coach DSH 1.3.1** uses workbench core **2.0.0rc15** and the signed-in Harness account. Download the macOS Apple silicon package from the [dedicated release](https://github.com/ooooooomygosh/paper-research-coach/releases/tag/dsh-v1.3.1), fully quit Harness, extract it and open `安装.command`. Native-host validation uses Harness **0.2.2-rc.1**. This release does not provide or validate a new Windows installer; the 1.2.0 Windows package is historical.

Selections retain the current PDF language and reading position. Detailed explanations expand into a large reading area with adjustable PDF comparison, fullscreen and explicit popout. The flexible four-stage route resumes saved legacy questions and retains eight-step records. Bilingual study pages share existing notes and export one offline HTML snapshot.

The DSH updater checks only `dsh-v*` releases, validates host/platform compatibility and SHA-256, and stages a package for the next full Harness restart. Settings display the actual plugin version and manual check. It never installs the standalone wheel. Automatic installation currently targets macOS arm64; an unsupported platform keeps its installed version. Older builds first install 1.3.1 manually. Papers, translations, notes and conversations are preserved; rollback uses a matching backup.

Validation separates source tests, synthetic browser checks, legacy-data copies and real-account synthetic PDF navigation. Local update-package tests are not a future public-network upgrade test. No learning-effectiveness trial or real Zotero write is claimed.
