# macOS 上的 DeepSeek Harness 插件构建

`PRC-DSH-1.1.0-win-x64.zip` 里是 Windows x64 的 Python 运行库和 `.cmd` 安装器，macOS 用不上。
不过这个目录的源码本身是平台无关的：host 走 Node，工作台和翻译是纯 Python，`service.py` 里本来就有
`sys.platform == "darwin"` 分支，README 只是没有 macOS 的打包与验证记录。这里补上这条路径。

| 项目 | Windows 分发包 | macOS（本目录脚本） |
| --- | --- | --- |
| 安装位置 | 改 `app.asar` + junction | `~/.dsh/builtin-plugins/paper-research-coach-<版本>-mac` |
| 注册 | 写入 `app.asar` 内的 `dsh/package.json`、`desktop-runtime.json` | 只改 `~/.dsh/profiles/desktop/package.json` 的 `dependencies` + `dsh.profile.bundles` |
| Python | 自带 `runtime/python/python.exe` | `runtime/venv`（uv，CPython 3.12 arm64） |
| 前端 | 包内预构建 `static/` | 本机 `npm ci && tsc --noEmit && vite build` |
| 翻译资源 | 包内 `runtime/assets` | 复用同一份资源，按 `runtime/ASSET-MANIFEST.json` 逐项校验哈希 |
| 独立窗口 | patch asar 内 `setWindowOpenHandler` | patch `Resources/app/lib/main.js` 同一处（有备份可回滚） |
| 数据 | `%USERPROFILE%\.dsh\paper-research-coach` | `~/.dsh/paper-research-coach` |

宿主代码只改了一处：`host/index.js` 原本写死 `runtime/python/python.exe`，现在按顺序找
`config.python`、Windows 自带解释器、`runtime/venv/bin/python3`，Windows 行为不变。

## 安装

前置：DeepSeek Harness **0.2.1-rc.5**（先启动一次并登录，让 `~/.dsh/profiles/desktop` 存在）、
Node.js 24、`uv`、Python 3.12（uv 可以代管）。

```bash
# 1. 取插件源码（40 MB，比整仓克隆小）
git clone --depth 1 --filter=blob:none --sparse https://github.com/ooooooomygosh/paper-research-coach.git ~/prc-src
cd ~/prc-src && git sparse-checkout set ports/deepseek-harness

# 2. 准备翻译资源（字体、doclayout ONNX、tiktoken 词表；仓库不含二进制）
#    从已验证的 Windows 包取：unzip PRC-DSH-1.1.0-win-x64.zip -d ~/PRC-DSH

# 3. 构建并安装
cd ~/prc-src/ports/deepseek-harness
bash macos/install-macos.sh --assets-from ~/PRC-DSH/PRC-DSH-1.1.0/package
```

脚本依次：复制源码 → 前端构建 → 资源哈希校验 → 建 venv 装依赖（含 `BabelDOC==0.6.4` 与
`bitstring<5`，后者不锁死会让 `from bitstring import BitStream` 直接 ImportError）→ 冒烟导入 →
注册 profile → 主进程窗口放行 → 打印回滚位置。

装完退出 Harness（⌘Q，含托盘）重开，侧栏出现「论文研读」。

卸载：

```bash
bash macos/uninstall-macos.sh                 # 保留运行时，方便回滚
bash macos/uninstall-macos.sh --purge-runtime --restore-host
```

论文、笔记、账户配置和翻译缓存在 `~/.dsh/paper-research-coach`，卸载不动。

## 从浏览器版迁移数据

独立工作台（`prc serve`，常见是 launchd 常驻在 8765 端口）和插件用同一套 SQLite 结构：

```bash
bash macos/import-legacy.sh          # 移动；旧路径留软链
bash macos/import-legacy.sh --copy   # 复制，旧目录保留
```

脚本会先 `launchctl bootout` 掉旧的 `io.paper-research-coach.workbench`——不停的话两个进程会同时写
一个库；然后把数据目录搬进 `~/.dsh/paper-research-coach`，并把 `translation_jobs` 里指向旧目录的
绝对路径改成新前缀，最后跑 `pragma quick_check` 并打印记录数。

## 已验证（本机 macOS 26.5 / Apple silicon / Harness 0.2.1-rc.5 / 插件 1.1.0）

- `tsc --noEmit` 通过，`vite build` 产出 `static/`，`host/index.js` 与 `studio-renderer.mjs` 在 Node 24 下可导入
- 后端 `-m paper_research_coach.embedded` 输出 `{"event":"ready","port":…}`，`/api/state`、`/api/records/note`、
  `/api/coach/status`（`已连接 DeepSeek Harness 登录账户`）、`/api/translation/settings`（`component.ready=true`）、
  `/api/workspace`（`{studios:[],kbs:[],jobs:[]}`）、`/api/text/<paper>/0` 均正常
- 工作台页面与 `assets/*.js|css|woff2`、`pdf.worker.min.mjs` 全部 200；客户端工厂写入预加载清单，侧栏 `论文研读` 注册成功
- `/api/update` 返回 `disabled:true, auto:false, managed_by:"DeepSeek Harness"`，内置版不会自动装入未适配版本
- 138 篇论文 / 160 条笔记 / 138 个会话从浏览器版迁移后完整可用；183 个翻译资源按清单哈希全部匹配

## 已知限制

- 译文生成走 CPU 版 doclayout（`babeldoc_worker.py` 里主动绕开 CoreML 编译），首次翻译较慢。
- Harness 升级会替换 `Resources/app`，`lib/main.js` 的窗口补丁随之丢失；只影响「独立窗口」，
  插件本身走 profile 不受影响，重跑安装脚本即可补回。
- 学习页与互动讲解会调用 Harness 登录账户的模型，消耗额度；只导入材料不触发。
- 未在 Intel Mac 与其他 macOS 版本上验证。
