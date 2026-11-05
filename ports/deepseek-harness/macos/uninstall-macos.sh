#!/usr/bin/env bash
# 卸载 macOS 上的 Paper Research Coach 插件：只移除注册与（可选）运行时，保留论文、笔记与账户配置。
#
# 用法：bash macos/uninstall-macos.sh [--purge-runtime] [--restore-host]
#   --purge-runtime  同时删除 ~/.dsh/builtin-plugins/paper-research-coach-*-mac
#   --restore-host   还原 Harness 主进程 lib/main.js 的窗口放行补丁
set -euo pipefail

NAME="@local/dsh-paper-research-coach"
DSH_HOME="${DSH_HOME:-$HOME/.dsh}"
PROFILE="$DSH_HOME/profiles/desktop"
APP="${DSH_APP:-/Applications/DeepSeek Harness.app}"

PURGE=0
RESTORE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --purge-runtime) PURGE=1; shift ;;
    --restore-host) RESTORE=1; shift ;;
    -h|--help) sed -n '2,8p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "未知参数：$1" >&2; exit 1 ;;
  esac
done

echo "== 1/3 从 profile 注销"
if [ -f "$PROFILE/package.json" ]; then
  python3 - "$PROFILE/package.json" "$NAME" <<'PY'
import json, pathlib, sys
path, name = pathlib.Path(sys.argv[1]), sys.argv[2]
data = json.loads(path.read_text())
data.get("dependencies", {}).pop(name, None)
bundles = data.get("dsh", {}).get("profile", {}).get("bundles", [])
bundles[:] = [item for item in bundles if item != name]
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
print("   依赖与 bundle 条目已移除")
PY
fi
rm -f "$PROFILE/node_modules/$NAME"

echo "== 2/3 宿主补丁"
MAIN="$APP/Contents/Resources/app/lib/main.js"
if [ "$RESTORE" = "1" ] && [ -f "$MAIN.prc-backup" ]; then
  cp "$MAIN.prc-backup" "$MAIN"
  echo "   已还原 lib/main.js"
else
  echo "   保留窗口放行补丁（只影响是否允许独立窗口）；加 --restore-host 可还原"
fi

echo "== 3/3 运行时"
for dir in "$DSH_HOME"/builtin-plugins/paper-research-coach-*-mac; do
  [ -d "$dir" ] || continue
  if [ "$PURGE" = "1" ]; then
    rm -rf "$dir"
    echo "   已删除 $dir"
  else
    echo "   保留 $dir（加 --purge-runtime 删除）"
  fi
done

echo
echo "论文、笔记、账户配置与翻译缓存都在 $DSH_HOME/paper-research-coach，未改动。"
echo "退出并重开 Harness 生效。"
