#!/usr/bin/env bash
# 把独立工作台（浏览器版，`prc serve`）的数据导入 Harness 插件。
#
# 两套程序都用 2.0.0rc13 的 SQLite 结构，但目录不同：
#   独立工作台  ~/Library/Application Support/paper-research-coach
#   插件        ${DSH_HOME:-~/.dsh}/paper-research-coach
#
# 用法：bash macos/import-legacy.sh [--from <旧数据目录>] [--copy]
#   --copy 复制而不是移动（旧目录多留一份，占 1.3 GB 翻译缓存）
#
# 注意：旧版常驻服务（如 launchd 的 io.paper-research-coach.workbench）必须先停，
# 否则两个进程会同时写一个 SQLite 文件。
set -euo pipefail

DSH_HOME="${DSH_HOME:-$HOME/.dsh}"
NEW="$DSH_HOME/paper-research-coach"
OLD="$HOME/Library/Application Support/paper-research-coach"
MODE="move"

while [ $# -gt 0 ]; do
  case "$1" in
    --from) OLD="${2:?缺少目录}"; shift 2 ;;
    --copy) MODE="copy"; shift ;;
    -h|--help) sed -n '2,16p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "未知参数：$1" >&2; exit 1 ;;
  esac
done

STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="$(dirname "$NEW")/paper-research-coach-import-backup-$STAMP"

echo "== 1/6 备份"
mkdir -p "$BACKUP"
if [ -f "$OLD/notebook.sqlite3" ]; then
  cp "$OLD/notebook.sqlite3" "$BACKUP/notebook.sqlite3.before-import"
  echo "   旧库副本：$BACKUP"
fi

echo "== 2/6 停止旧服务"
launchctl bootout "gui/$(id -u)/io.paper-research-coach.workbench" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/io.paper-research-coach.workbench.plist"
pkill -f "paper_research_coach.cli" 2>/dev/null || true
sleep 1

echo "== 3/6 迁移目录（$MODE）"
if [ -L "$OLD" ]; then
  echo "   $OLD 已是软链 → $(readlink "$OLD")，跳过"
  TARGET=$(readlink "$OLD")
else
  [ -d "$NEW" ] && mv "$NEW" "$BACKUP/previous-plugin-datadir"
  if [ "$MODE" = "copy" ]; then
    cp -a "$OLD" "$NEW"
  else
    mv "$OLD" "$NEW"
    ln -s "$NEW" "$OLD"
    echo "   已移动，旧路径留软链"
  fi
  TARGET="$NEW"
fi

echo "== 4/6 重写库内绝对路径（翻译产物的 artifacts 指向旧目录时需要）"
python3 - "$TARGET/notebook.sqlite3" "$OLD" "$NEW" <<'PY'
import sqlite3, sys
db_path, old, new = sys.argv[1], sys.argv[2], sys.argv[3]
def residual(db, needle):
    total = 0
    for (table,) in db.execute("select name from sqlite_master where type='table'"):
        for (column,) in db.execute(f"pragma table_info({table})"):
            try:
                total += db.execute(
                    f"select count(*) from {table} where cast({column} as text) like ?",
                    (f"%{needle}%",)).fetchone()[0]
            except sqlite3.Error:
                continue
    return total

db = sqlite3.connect(db_path)
before = residual(db, old)
touched = 0
for (table,) in db.execute("select name from sqlite_master where type='table'"):
    for (column,) in db.execute(f"pragma table_info({table})"):
        try:
            db.execute(f"update {table} set {column}=replace({column},?,?)", (old, new))
            touched += 1
        except sqlite3.Error:
            continue
db.commit()
after = residual(db, old)
db.close()
print(f"   重写 {touched} 列的旧前缀；命中行数 {before} → 残留 {after}")
PY

echo "== 5/6 完整性"
sqlite3 "$NEW/notebook.sqlite3" "pragma quick_check;" | head -1
sqlite3 "$NEW/notebook.sqlite3" "select kind, count(*) from records group by kind;"

echo "== 6/6 完成"
echo "   数据：$NEW"
echo "   浏览器版如仍要用，指向同一目录起服务即可（不要与 Harness 同时开）："
echo "   python -m paper_research_coach.cli --data-dir \"$NEW\" serve --port 8765"
