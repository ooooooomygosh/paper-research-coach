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
if [ -z "$ASSETS_FROM" ] && [ -d "$ROOT/runtime/assets" ]; then ASSETS_FROM="$ROOT"; fi

say() { printf '\n== %s\n' "$*"; }

say "0/8 环境检查"
[ -d "$APP" ] || { echo "未找到 $APP；用 --app 指定 Harness.app" >&2; exit 1; }
[ -d "$PROFILE" ] || { echo "未找到 profile：$PROFILE（先启动一次 Harness 并登录，再退出）" >&2; exit 1; }
command -v node >/dev/null || { echo "需要 Node.js 24" >&2; exit 1; }
command -v uv >/dev/null || { echo "需要 uv（brew install uv）" >&2; exit 1; }
HOST_VER=$(node -p "require('$APP/Contents/Resources/app/dsh/package.json').version" 2>/dev/null || echo unknown)
case "$HOST_VER" in
  0.2.1-rc.5|0.2.2-rc.1) ;;
  *) echo "当前宿主 ${HOST_VER} 尚未验证，安装未修改注册。" >&2; exit 1 ;;
esac

# Snapshot the current registration and live SQLite databases before an upgrade.
python3 - "$DSH_HOME" "$PROFILE/package.json" <<'PYBACKUP'
import datetime, pathlib, shutil, sqlite3, sys
home, profile = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
backup = home / "paper-research-coach-upgrades" / datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
backup.mkdir(parents=True, mode=0o700)
if profile.exists(): shutil.copy2(profile, backup / "profile-package.json")
data = home / "paper-research-coach"
for source in data.rglob("*.sqlite3") if data.exists() else ():
    if "backup" in str(source.relative_to(data)).lower(): continue
    target = backup / "data" / source.relative_to(data)
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source.as_uri()+"?mode=ro", uri=True) as original, sqlite3.connect(target) as copy:
        original.backup(copy)
    target.chmod(0o600)
print("升级备份：", backup)
PYBACKUP

say "1/8 复制插件源码到 $PAYLOAD"
mkdir -p "$PAYLOAD"
rsync -a --exclude '.test*' --exclude '__pycache__' --exclude '.pytest_cache' --exclude 'macos' --exclude 'upstream/frontend/node_modules' --exclude '.gitignore' \
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
python3 - "$PAYLOAD" <<'PYLOCK'
import pathlib, re, sys
root = pathlib.Path(sys.argv[1])
lines = (root / "runtime/requirements.lock.txt").read_text().splitlines()
(root / "runtime/macos-constraints.txt").write_text("\n".join(line for line in lines if re.match(r"^[A-Za-z0-9_.-]+==", line))+"\n")
PYLOCK
# Automatic DSH updates may reuse a COPY of the old environment only when the
# exact dependency lock agrees. It is never a writable link to the running version.
RUNTIME_REUSED=0
if [ -n "${PRC_DSH_RUNTIME_FROM:-}" ] && [ ! -d "$PAYLOAD/runtime/venv" ] \
   && cmp -s "$PAYLOAD/runtime/requirements.lock.txt" "$PRC_DSH_RUNTIME_FROM/runtime/requirements.lock.txt" \
   && [ -x "$PRC_DSH_RUNTIME_FROM/runtime/venv/bin/python3" ]; then
  cp -a "$PRC_DSH_RUNTIME_FROM/runtime/venv" "$PAYLOAD/runtime/venv"
  RUNTIME_REUSED=1
fi
if [ "$RUNTIME_REUSED" != "1" ]; then
[ -x "$PAYLOAD/runtime/venv/bin/python3" ] || uv venv "$PAYLOAD/runtime/venv" --python 3.12
uv pip install --constraint "$PAYLOAD/runtime/macos-constraints.txt" --python "$PAYLOAD/runtime/venv/bin/python3" \
  fastapi uvicorn httpx filelock pypdf PyYAML platformdirs packaging pypdfium2 pillow "PyPDF2==3.0.1" "keyring>=25,<26" "fonttools>=4.60,<5"
# 中文/双语 PDF。bitstring 必须 <5：BabelDOC 0.6.4 仍 from bitstring import BitStream
uv pip install --constraint "$PAYLOAD/runtime/macos-constraints.txt" --python "$PAYLOAD/runtime/venv/bin/python3" "BabelDOC==0.6.4" "bitstring<5"

fi

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

say "7/8 保留宿主窗口设置"
echo "   应用内大阅读区和全屏可直接使用；独立窗口被宿主阻止时保留当前讲解。"
MAIN="$APP/Contents/Resources/app/lib/main.js"

say "8/8 完成"
echo "插件：$PAYLOAD"
echo "数据：$DSH_HOME/paper-research-coach"
echo "回滚：$DSH_HOME/paper-research-coach-upgrades 中对应版本的注册与数据库备份"
echo "现在退出 Harness（⌘Q，含托盘）重新打开，侧栏出现「论文研读」。"
