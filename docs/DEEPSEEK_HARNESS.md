# 在 DeepSeek Harness 中使用 Paper Research Coach

Paper Research Coach 提供可内置到 **DeepSeek Harness** 的第三方适配版本。安装后从 Harness 侧栏的“论文研读”进入，保留原项目的阅读工作台和 UI，通过 Harness 当前登录账户的 `deepseek-account` 接口完成文献阅读、分析和学习，无需额外配置 API Key 或 Codex CLI。

适配插件当前源码版本为 **1.2.0**，基于工作台 **2.0.0rc13**，要求 Harness **0.2.1-rc.5**。Windows x64 提供分发包构建方式；macOS（Apple silicon）没有预打包产物，在装有 Node.js 24 与 uv 的机器上从源码构建并注册进 Harness profile，步骤见 [`ports/deepseek-harness/macos/README.md`](../ports/deepseek-harness/macos/README.md)。已有 1.1.0 的两个平台实跑记录；本次改版的检查范围见适配目录说明，其他 Harness 版本需要重新验证。该适配版并非 DeepSeek 官方发行。

## 两个新增学习入口

**知识库学习**整合 Learn from Materials：导入多份材料并保留来源映射，构建概览或系统学习页，学习概念和方法，保存单元笔记、进度、练习及错题，以来源片段支撑追问。支持停止/恢复构建、历史版本和离线导出。

**交互式讲解**整合 Answer me with HTML：围绕一个问题、论文页或知识库生成含流程图、公式、表格和问答的图文页面，支持编辑草稿、更换主题、修订和 HTML 导出。插件名称保持 **Paper Research Coach**。

1.2.0 将翻译与显示原文集中在顶部，增加一键导出的“标准阅读”提示，以及概念、步骤、比较、参数与证据五类可操作组件。控件使用独立 SVG 源文件与无高光样式；讲解成品优先显示，修改按需展开。参数图仅作教学示意，引用与导出保留已知来源版本。具体逻辑、边界和后续开发方案见 [阅读改版说明](../ports/deepseek-harness/docs/READING_REDESIGN.md)。

原有 PDF 阅读、八章主线、支线讲解、复盘树、笔记、翻译和书库同步继续保留。PDF 高亮修复将碎片选区按行合并并去重，减少重复方框与文字遮挡。教练默认用 **DeepSeek Flash + high 思考深度**，模型未声明的档位不会提交；一轮失败时会说明具体原因（额度、限流、上下文等），不再只显示通用提示。

仅添加材料不会调用模型；点击构建、生成或发送后才通过登录账户请求模型。逐字引文校验不代表语义完整性或学习效果已经独立验证，扫描页与图中细节仍需人工核对。

## 安装与源码

[Harness 适配目录](../ports/deepseek-harness/README.md) 包含完整源码快照、固定版本的第三方源码、安装器、验证脚本和分发构建说明。它与根目录的独立工作台发布流程分开维护。

Git 仓库不存储运行库、字体/模型缓存或大型安装 ZIP。维护者准备已验证运行库并构建后，生成 `PRC-DSH-1.2.0-win-x64.zip`。接收方需自行安装兼容的 Harness 并登录；退出应用后完整解压 ZIP，运行 `安装.cmd`，重启后点击“论文研读”。卸载使用同包 `卸载.cmd`，保留论文及学习记录。仓库现有 wheel 和 Skill ZIP 不能代替这个 Harness 插件包。

数据默认保存在 `%USERPROFILE%\.dsh\paper-research-coach`；配置 `DSH_HOME` 后使用对应目录。登录凭证由 Harness 管理，不随插件打包。安装器检查宿主版本和文件完整性，备份接收方的原应用包，并提供恢复流程。内置版关闭独立工作台的自动更新；宿主更新后应重新核对兼容性。

## English

The **Paper Research Coach 1.2.0** source port embeds the full 2.0.0rc13 workbench in **DeepSeek Harness 0.2.1-rc.5**. Windows x64 has a distributable-package builder; macOS (Apple silicon) is built from source and registered into a Harness profile — see [`ports/deepseek-harness/macos/README.md`](../ports/deepseek-harness/macos/README.md). Historical native-host checks cover 1.1.0 on both platforms; the port notes describe this redesign's validation scope. Other host versions have not been validated. It uses the signed-in Harness account through `deepseek-account`, adds knowledge-base learning and interactive explanations, and fixes overlapping PDF text highlights. Version 1.2.0 adds compact matte controls, standard-reading prompt export, global translation/source controls, and five bounded interactive component types. Parameter curves are explicitly illustrative, and exports retain known source versions. No separate API key or Codex CLI is required. The coach defaults to DeepSeek Flash at high reasoning, never submits a level the model does not declare, and names the cause when a turn fails.

The [port source and build guide](../ports/deepseek-harness/README.md) includes both pinned MIT-licensed integrations, account bridges, tests and the distributable installer. Runtime binaries, cached translation assets, personal data and credentials are excluded from Git. The standalone wheel/Skill releases are separate from the Harness installer ZIP. This is a third-party integration, not an official DeepSeek distribution.
