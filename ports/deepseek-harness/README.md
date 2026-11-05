# Paper Research Coach · DeepSeek Harness 内置版

Paper Research Coach **1.1.0** 可内置到 **DeepSeek Harness 0.2.1-rc.5**（Windows x64 分发包；macOS 走源码构建，见 [`macos/README.md`](macos/README.md)），从 Harness 侧栏的“论文研读”进入。文献阅读、分析、知识库构建和互动讲解统一调用 Harness 当前登录账户的 `deepseek-account` 模型接口，无需另填 API Key 或启动 Codex CLI。插件名称继续使用 **Paper Research Coach**。

这是第三方适配版。发布用的安装 ZIP 只有 Windows x64；macOS 没有预打包产物，但源码可在本机构建并注册进 Harness profile，步骤和限制见 [`macos/README.md`](macos/README.md)。其他 Harness 版本尚未验证。插件包不包含 Harness 主程序；模型调用仍需要网络及可用的 Harness 账户。

## 功能

- 保留原版 React 工作台的 PDF 阅读、八章主线、任务卡、支线讲解、复盘树、笔记与证据定位、翻译、Zotero/目录同步、研究脉络、想法与导出。
- **知识库学习**：导入 PDF、DOCX、PPTX、EPUB 和文本材料，提取并映射来源；生成六模块学习页、概念与术语、方法库、练习与错题；保存单元进度、笔记、历史版本，支持有出处的追问、停止/恢复构建及 HTML/Markdown/知识库导出。
- **交互式讲解**：从问题、论文页或知识库取材，生成包含流程图、时序图、树、公式、表格和问答的互动页面；支持 Markdown 编辑、主题切换、修订、版本保存和离线 HTML 导出。
- 修复 PDF 文本选区出现大量重叠方框的问题：按行合并、去重；文字采用柔和高亮，手动框选保留边框，浮层避让原文。

学习页基于 [Learn from Materials](https://github.com/dmoshehun-prog/learn-from-materials)，互动页面复用 [Answer me with HTML](https://github.com/QingYunA/answer-me-with-html) 的实际渲染器。固定提交及适配文件见 [integrations/SOURCES.json](integrations/SOURCES.json)，署名和许可证见 [THIRD_PARTY.md](THIRD_PARTY.md)。添加材料本身不发起模型请求；点击构建、生成或发送后才调用账户。

文本提取覆盖和逐字引文校验不等于独立语义完整性审查；扫描页、图像和版面细节需要另行核对。练习答案为模型生成的参考答案，进度不代表掌握度。MOBI/AZW 需要另行安装 Calibre。

## 安装分发包

本目录提供源码，不在 Git 中存放约 476 MiB 的安装 ZIP、Python 运行库、翻译模型或字体。仓库首页的独立工作台 wheel/Skill ZIP 也不是 Harness 插件安装包。

维护者使用下方脚本构建后，会生成 `dist/PRC-DSH-1.1.0-win-x64.zip`。将整个 ZIP 发给接收方；接收方安装并登录兼容的 Harness，退出应用及托盘后完整解压，双击 `安装.cmd`，再启动 Harness。检查和卸载分别使用 `检查安装包.cmd`、`卸载.cmd`。升级旧版时，先用旧包卸载，再安装新版；论文和学习记录保留。

安装器在接收方机器上核对宿主版本、逐项校验文件、备份并更新应用包和插件清单，不包含开发者的应用包或账户配置。受保护的应用目录会按需请求 Windows 管理员授权。卸载保留论文、笔记和账户数据；具体操作见 [distribution/README.txt](distribution/README.txt)。

默认学习数据在 `%USERPROFILE%\.dsh\paper-research-coach`；设置 `DSH_HOME` 时跟随该目录。凭证由 Harness 管理；后端只监听回环地址，通过宿主身份检查和临时桥接凭证访问。嵌入学习页隔离运行，问题先带回可编辑输入框，再由用户发送。

## 源码组织

这个目录保留已验证的 **2.0.0rc13 内置工作台快照**，与仓库根目录的独立工作台分开。它是完整的适配源码贡献，不会替换独立工作台的 provider 或发布流程。

| 路径 | 内容 |
|---|---|
| `host/`、`client/`、`locale/` | Harness 账户桥接、服务生命周期、侧栏入口与本地化 |
| `upstream/src/`、`upstream/frontend/` | 工作台快照，以及账户接入、学习工作区和高亮修复 |
| `integrations/` | 两个项目的固定源码、模板、渲染器与许可 |
| `distribution/`、`scripts/build_release.py` | 可转发安装包、校验、备份、卸载与恢复 |
| `runtime/requirements.lock.txt`、`runtime/ASSET-MANIFEST.json` | Python 依赖版本和已验证翻译资源的哈希清单 |
| `macos/` | macOS 源码构建：`install-macos.sh`、`uninstall-macos.sh`、`import-legacy.sh` 与说明 |
| `SOURCE_SNAPSHOT.json` | 原项目版本、提交和公开源码文件哈希 |

原仓库与第三方仓库中的 Skill 文档作为随附源码保留；不会自动安装额外代理或服务。后续同步独立工作台需要显式移植并重新验证此快照。

## 开发与验证

使用 Python 3.12、Node.js 24 和 npm。在本目录中运行（Windows PowerShell）：

```powershell
python -m venv .venv
npm --prefix upstream/frontend ci
npm --prefix upstream/frontend run build
& ./.venv/Scripts/python.exe -X utf8 upstream/scripts/prepare_licenses.py
& ./.venv/Scripts/python.exe -X utf8 -m pip install -e './upstream[dev]' PyPDF2==3.0.1
& ./.venv/Scripts/python.exe -X utf8 scripts/prepare_integrations.py
& ./.venv/Scripts/python.exe -X utf8 scripts/verify_source.py
```

验证脚本运行原版及新增 Python 测试、账户桥接与真实渲染器测试、TypeScript 检查、前端测试和构建，不连接账户或安装 Harness。[专用 CI](../../.github/workflows/deepseek-harness.yml) 使用 Windows 运行相同检查。原版 Skill/文档校验仍可在 `upstream/` 中运行。

已完成的 Windows 1.1.0 验证：209 项 Python 测试通过、7 项跳过；115 项前端测试、7 项 Node 测试通过。另以合成材料完成登录账户冒烟、桌面交互和真实宿主包的隔离安装/卸载检查。这些历史验证不等于本次 CI 已连接账户。macOS 侧的构建与冒烟记录写在 `macos/README.md`，只覆盖 Apple silicon 一台机器，不代表 Windows 分发包等价或已覆盖 Intel Mac；本仓库不附带个人账户收据、桌面日志或论文。

账户冒烟需要自有 Harness 运行时及登录账户，可能消耗账户额度。设置 `DSH_PRC_TEST_REFERENCE_PATH` 为解包后的 `dsh` 目录，再运行 `node scripts/smoke-harness.mjs`；设置 `PRC_LEARNING_TEST=1` 可检查学习工作区。脚本使用单独的测试书库，只发送合成教学材料。不要将该运行时或测试数据提交到仓库。

## 构建可分发安装包

构建使用完整的 Windows x64 可搬移运行库，包含 Python、锁定依赖及 BabelDOC 0.6.4 字体/版面模型缓存。Git 源码不包含这些二进制文件。可从已验证安装包的 `package/runtime` 提供运行库；自行组装时须遵守 Python、Microsoft 运行库和各依赖的分发许可，并按清单准备资源。

```powershell
# 假定已有一份已验证运行库；此操作只准备构建目录，不安装 Harness。
python -X utf8 scripts/prepare_bundle.py --runtime 'C:/PRC-DSH/package/runtime'
& ./runtime/python/python.exe -X utf8 scripts/verify_source.py
& ./runtime/python/python.exe -X utf8 scripts/build_release.py
```

`prepare_bundle.py` 核对翻译资源哈希，复制运行库，修正本地源码优先路径并检查关键依赖；`build_release.py` 收集源码、资源、许可证和安装器，检查私有数据排除项，生成逐文件 SHA-256 清单、ZIP CRC 和 ZIP 摘要。构建前需先完成前端构建。

安装器仅支持已验证的 Harness **0.2.1-rc.5**。宿主升级可能替换内置包，需重新核验兼容性后再分发；此版本关闭独立工作台的自动更新，避免装入未适配的版本。
