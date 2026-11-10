# Paper Research Coach · DeepSeek Harness 内置版

> 本地开发版 **1.3.0** 已增加当前语言定位、讲解大阅读区、四阶段软路线及双语对照批注 HTML。使用与升级说明见 [双语研读](docs/BILINGUAL-READING.md)。已验证 macOS DSH 0.2.2-rc.1 的真实账户合成材料调用；下文 1.2.0 为既有公开分发记录，未声明发布新的 Windows ZIP。


Paper Research Coach **1.2.0** 可内置到 **DeepSeek Harness 0.2.1-rc.5**（Windows x64 分发包；macOS 走源码构建，见 [`macos/README.md`](macos/README.md)），从 Harness 侧栏的“论文研读”进入。文献阅读、分析、知识库构建和互动讲解统一调用 Harness 当前登录账户的 `deepseek-account` 模型接口，无需另填 API Key 或启动 Codex CLI。插件名称继续使用 **Paper Research Coach**。

这是第三方适配版。仓库里只发 Windows x64 的安装 ZIP；macOS 不发预打包产物，用 [`macos/install-macos.sh`](macos/install-macos.sh) 从源码构建并注册进 Harness profile，步骤和限制见 [`macos/README.md`](macos/README.md)。两个平台都在 Harness 0.2.1-rc.5 上跑过。已有版本的适配记录见上述平台说明；本次界面改版的验证范围见下文。其他 Harness 版本尚未验证。插件包不包含 Harness 主程序；模型调用仍需要网络及可用的 Harness 账户。

## 功能

- 保留原版 React 工作台的 PDF 阅读、八章主线、任务卡、支线讲解、复盘树、笔记与证据定位、翻译、Zotero/目录同步、研究脉络、想法与导出。
- **知识库学习**：导入 PDF、DOCX、PPTX、EPUB 和文本材料，提取并映射来源；生成六模块学习页、概念与术语、方法库、练习与错题；保存单元进度、笔记、历史版本，支持有出处的追问、停止/恢复构建及 HTML/Markdown/知识库导出。
- **交互式讲解**：从问题、论文页或知识库取材，生成包含流程图、时序图、树、公式、表格和问答的互动页面；支持 Markdown 编辑、主题切换、修订、版本保存和离线 HTML 导出。
- **阅读界面与翻译入口**：顶部集中阅读、知识库、讲解、翻译与显示原文；控件图标有独立 SVG 源文件，按钮和边框取消高光。讲解成品优先显示，修改要求按需展开。翻译面板可操作当前论文和批量后台队列，切换页面不会取消任务；完全退出 Harness 后停止计算，已保存进度可恢复。
- **标准阅读与可操作讲解**：讲解界面一键导出结合七个阅读环节与本项目方法论的阅读提示；导出本身不调用模型。可另选概念、步骤、比较、参数、证据五类组件，由登录账户生成结构化内容；页内操作在本地运行，带着状态继续提问前仍可编辑。匹配的原文依据保留版本与页码，可定位当前论文。
- 修复 PDF 文本选区出现大量重叠方框的问题：按行合并、去重；文字采用柔和高亮，手动框选保留边框，浮层避让原文。
- 教练默认 **DeepSeek Flash + high 思考深度**；模型未声明的档位不会提交，失败时说明具体原因（额度、限流、上下文），并把诊断写进 `~/.dsh/paper-research-coach/logs/`。

学习页基于 [Learn from Materials](https://github.com/dmoshehun-prog/learn-from-materials)，互动页面复用 [Answer me with HTML](https://github.com/QingYunA/answer-me-with-html) 的实际渲染器。固定提交及适配文件见 [integrations/SOURCES.json](integrations/SOURCES.json)，署名和许可证见 [THIRD_PARTY.md](THIRD_PARTY.md)。添加材料本身不发起模型请求；点击构建、生成或发送后才调用账户。

文本提取覆盖和逐字引文校验不等于独立语义完整性审查；扫描页、图像和版面细节需要另行核对。练习答案为模型生成的参考答案，进度不代表掌握度。MOBI/AZW 需要另行安装 Calibre。

参数探索仅支持有范围和单位的线性、幂函数与指数函数教学示意，不复算论文实验。已有讲解沿用图文文档模式，历史版本只读且保留。阅读逻辑、交互契约、验证范围与后续开发方案见 [阅读改版说明](docs/READING_REDESIGN.md)。

## 安装分发包

本目录提供源码，不在 Git 中存放约 476 MiB 的安装 ZIP、Python 运行库、翻译模型或字体。仓库首页的独立工作台 wheel/Skill ZIP 也不是 Harness 插件安装包。

维护者使用下方脚本构建后，会生成 `dist/PRC-DSH-1.2.0-win-x64.zip`。将整个 ZIP 发给接收方；接收方安装并登录兼容的 Harness，退出应用及托盘后完整解压，双击 `安装.cmd`，再启动 Harness。检查和卸载分别使用 `检查安装包.cmd`、`卸载.cmd`。升级旧版时，先用旧包卸载，再安装新版；论文和学习记录保留。

安装器在接收方机器上核对宿主版本、逐项校验文件、备份并更新应用包和插件清单，不包含开发者的应用包或账户配置。受保护的应用目录会按需请求 Windows 管理员授权。卸载保留论文、笔记和账户数据；具体操作见 [distribution/README.txt](distribution/README.txt)。

默认学习数据在 `%USERPROFILE%\.dsh\paper-research-coach`；设置 `DSH_HOME` 时跟随该目录。凭证由 Harness 管理；后端只监听回环地址，通过宿主身份检查和临时桥接凭证访问。嵌入学习页隔离运行，问题先带回可编辑输入框，再由用户发送。

## 源码组织

这个目录保留已验证的 **2.0.0rc14 内置工作台快照**，与仓库根目录的独立工作台分开。它是完整的适配源码贡献，不会替换独立工作台的 provider 或发布流程。

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

## 同步独立工作台

快照与根目录的独立工作台分开演进，落后时两边的功能就不一致。同步的做法：

1. 取 `SOURCE_SNAPSHOT.json` 里 `upstream.commit`（基线）到新版本之间独立工作台改过的文件。插件没改过的文件直接换成新版本；插件也改过的做三方合并（基线、插件版本、新版本）。根目录的 README 和文档不要带进快照，它们讲的就是这个插件。
2. 运行下面的 `scripts/verify_source.py`。合并没有文本冲突不等于行为正确，要靠测试确认。
3. 运行 `python scripts/refresh_snapshot.py write --baseline <新版本的提交>`，更新 `SOURCE_SNAPSHOT.json`（版本、基线、每个文件的哈希、相对基线有改动的文件）。之后任何改动都可以用 `python scripts/refresh_snapshot.py check` 确认这份记录没有过期。
4. 更新各处写着“基于工作台 x.y.z”的说明（`README.md`、`docs/DEEPSEEK_HARNESS.md`、`功能与验收.md`、`THIRD_PARTY.md`、`distribution/README.txt`）。构建清单里的 `upstreamVersion` 已改为从 `upstream/` 里的包读取，不用再手改。

最近一次同步：独立工作台 **2.0.0rc14**。

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
