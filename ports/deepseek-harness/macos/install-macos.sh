#!/usr/bin/env bash
# Paper Research Coach · DeepSeek Harness 插件 · macOS 源码构建与安装
#
# 仓库不附带 Windows 运行库，因此 macOS 侧不用 PRC-DSH-*.zip：直接在本目录
# 用源码构建前端，建一个原生 Python 环境，再把插件注册进 Harness 的 desktop profile。
#
# 用法：
#   bash macos/install-macos.sh --assets-from <含 runtime/assets 的目录>
#   bash macos/install-macos.sh --assets-from ~/PRC-DSH/package --app "/Applications/DeepSeek Harness.app"
#
# 前置：DeepSeek Harness 0.2.1-rc.5、uv、Node.js 24 + npm、Python 3.12（uv 可自备）。
set -euo pipefail

NAME="@local/dsh-paper-research-coach"
HOST_VERSION="0.2.1-rc.5"
DSH_HOME="${DSH_HOME:-$HOME/.dsh}"
PROFILE="$DSH_HOME/profiles/desktop"
APP="${DSH_APP:-/Applications/DeepSeek Harness.app}"
ASSETS_FROM=""
SKIP_FRONTEND=0

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION=$(node -p "require('$ROOT/package.json').version")

while [ $# -gt 0 ]; do
  case "$1" in
    --assets-from) ASSETS_FROM="${2:?缺少目录}"; shift 2 ;;
    --app) APP="${2:?缺少路径}"; shift 2 ;;
    --skip-frontend) SKIP_FRONTEND=1; shift ;;
    -h|--help) sed -n '2,12p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "未知参数：$1" >&2; exit 1 ;;
  esac
done

PAYLOAD="$DSH_HOME/builtin-plugins/paper-research-coach-${VERSION}-mac"

say() { printf '\n== %s\n' "$*"; }

say "0/8 环境检查"
[ -d "$APP" ] || { echo "未找到 $APP；用 --app 指定 Harness.app" >&2; exit 1; }
[ -d "$PROFILE" ] || { echo "未找到 profile：$PROFILE（先启动一次 Harness 并登录，再退出）" >&2; exit 1; }
command -v node >/dev/null || { echo "需要 Node.js 24" >&2; exit 1; }
command -v uv >/dev/null || { echo "需要 uv（brew install uv）" >&2; exit 1; }
HOST_VER=$(node -p "require('$APP/Contents/Resources/app/dsh/package.json').version" 2>/dev/null || echo unknown)
[ "$HOST_VER" = "$HOST_VERSION" ] || echo "   注意：宿主是 $HOST_VER，插件只验证过 $HOST_VERSION"

say "1/8 复制插件源码到 $PAYLOAD"
mkdir -p "$PAYLOAD"
rsync -a --exclude 'macos' --exclude 'upstream/frontend/node_modules' --exclude '.gitignore' \
  --exclude 'runtime/python' --exclude 'runtime/venv' --exclude 'runtime/assets' "$ROOT/" "$PAYLOAD/"

say "2/8 构建前端（tsc --noEmit && vite build → upstream/src/paper_research_coach/static）"
if [ "$SKIP_FRONTEND" = "1" ] && [ -f "$PAYLOAD/upstream/src/paper_research_coach/static/index.html" ]; then
  echo "   已存在构建产物，跳过"
else
  npm --prefix "$PAYLOAD/upstream/frontend" ci --no-audit --no-fund >/dev/null
  npm --prefix "$PAYLOAD/upstream/frontend" run build 2>&1 | tail -3
fi
[ -f "$PAYLOAD/upstream/src/paper_research_coach/static/index.html" ] || { echo "前端构建产物缺失" >&2; exit 1; }

say "3/8 翻译资源（字体 / doclayout 模型 / tiktoken 词表）"
if [ -z "$(ls -A "$PAYLOAD/runtime/assets" 2>/dev/null || true)" ]; then
  if [ -n "$ASSETS_FROM" ] && [ -d "$ASSETS_FROM/runtime/assets" ]; then
    mkdir -p "$PAYLOAD/runtime/assets"
    # 同一卷优先硬链接，省掉 300+ MB 复制
    cp -al "$ASSETS_FROM/runtime/assets/." "$PAYLOAD/runtime/assets/" 2>/dev/null \
      || cp -a "$ASSETS_FROM/runtime/assets/." "$PAYLOAD/runtime/assets/"
    echo "   复用 $ASSETS_FROM/runtime/assets"
  else
    echo "   缺 runtime/assets：请用 --assets-from 指向已含翻译资源的目录" >&2
    echo "   资源可从已验证的 Windows 包 package/runtime/assets 取得，或用真机跑一次翻译后从 BabelDOC 缓存补齐" >&2
    exit 1
  fi
fi
python3 - "$PAYLOAD" <<'PY'
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
manifest = json.load(open(root / "runtime/ASSET-MANIFEST.json"))["files"]
root = root / "runtime/assets"
bad = [rel for rel, info in manifest.items()
       if not (root / rel).is_file()
       or hashlib.sha256((root / rel).read_bytes()).hexdigest() != info["sha256"]]
print(f"   清单 {len(manifest)} 项，缺失或哈希不符 {len(bad)} 项")
for rel in bad[:5]:
    print("    ", rel)
sys.exit(1 if bad else 0)
PY

say "4/8 Python 环境（runtime/venv）"
[ -x "$PAYLOAD/runtime/venv/bin/python3" ] || uv venv "$PAYLOAD/runtime/venv" --python 3.12
uv pip install --python "$PAYLOAD/runtime/venv/bin/python3" \
  fastapi uvicorn httpx filelock pypdf PyYAML platformdirs packaging pypdfium2 pillow "PyPDF2==3.0.1"
# 中文/双语 PDF。bitstring 必须 <5：BabelDOC 0.6.4 仍 from bitstring import BitStream
uv pip install --python "$PAYLOAD/runtime/venv/bin/python3" "BabelDOC==0.6.4" "bitstring<5"

say "5/8 Python 侧自检"
PYTHONPATH="$PAYLOAD/upstream/src" "$PAYLOAD/runtime/venv/bin/python3" - <<'PY'
import importlib.metadata as m
import PyPDF2
from paper_research_coach import embedded, learning, server, studio, workspace_api
print("   BabelDOC", m.version("BabelDOC"), "| PyPDF2", PyPDF2.__version__, "| server/learning/studio 导入正常")
PY

say "6/8 注册到 desktop profile"
mkdir -p "$PROFILE/node_modules/@local"
ln -sfn "$PAYLOAD" "$PROFILE/node_modules/$NAME"
[ -f "$PROFILE/package.json.prc-backup" ] || cp "$PROFILE/package.json" "$PROFILE/package.json.prc-backup"
python3 - "$PROFILE/package.json" "$NAME" "$PAYLOAD" <<'PY'
import json, pathlib, sys
path, name, payload = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
data = json.loads(path.read_text())
data.setdefault("dependencies", {})[name] = "link:" + payload
bundles = data.setdefault("dsh", {}).setdefault("profile", {}).setdefault("bundles", [])
if name not in bundles:
    bundles.append(name)
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
print("   dependencies/bundles 已写入")
PY

say "7/8 允许工作台打开独立窗口（宿主主进程一行放行）"
MAIN="$APP/Contents/Resources/app/lib/main.js"
if [ -f "$MAIN" ]; then
  [ -f "$MAIN.prc-backup" ] || cp "$MAIN" "$MAIN.prc-backup"
  python3 - "$MAIN" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1]); text = p.read_text()
anchor = '''\t\tview.webContents.setWindowOpenHandler(({ url }) => {
\t\t\tconst destination = new URL(url);
'''
allow = '''\t\t\tif (destination.protocol === "dsh-app:" && destination.hostname === "app") return { action: "allow", overrideBrowserWindowOptions: { title: "论文研读", autoHideMenuBar: true, webPreferences: { nodeIntegration: false, contextIsolation: true, sandbox: true } } };
'''
if 'destination.protocol === "dsh-app:"' in text:
    print("   已放行，跳过")
elif anchor in text:
    p.write_text(text.replace(anchor, anchor + allow, 1)); print("   main.js 已打补丁")
else:
    print("   宿主窗口处理器结构不同，跳过（只影响「独立窗口」，工作台本身不受影响）")
PY
else
  echo "   未找到 $MAIN（宿主结构变化），跳过"
fi

say "8/8 完成"
echo "插件：$PAYLOAD"
echo "数据：$DSH_HOME/paper-research-coach"
echo "回滚：$PROFILE/package.json.prc-backup、$MAIN.prc-backup"
echo "现在退出 Harness（⌘Q，含托盘）重新打开，侧栏出现「论文研读」。"
