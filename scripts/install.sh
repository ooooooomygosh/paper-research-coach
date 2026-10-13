#!/bin/sh
# Install (or update) the Paper Research Coach workbench. macOS and Linux.
#
#   curl -fsSL https://raw.githubusercontent.com/ooooooomygosh/paper-research-coach/main/scripts/install.sh | sh
#
# What it does, in order: finds the newest release (pre-releases included), downloads its wheel,
# checks the SHA-256 against the release's SHA256SUMS, and installs it in its own environment
# with uv, pipx or python -m venv (the first one it finds). It never uses sudo, never edits
# your shell files, and never touches your library. Run it again to update; or run `prc update`.
#
# Options:  --install-uv   install uv first when nothing else is available
#           --open         start the workbench when done
#           --shortcut     also put a double-click launcher on your Desktop
# Test hooks: PRC_RELEASES_URL, PRC_INSTALL_METHOD=uv|pipx|venv, PRC_VENV_DIR, PRC_BIN_DIR
set -eu

REPO="ooooooomygosh/paper-research-coach"
RELEASES_URL="${PRC_RELEASES_URL:-https://api.github.com/repos/$REPO/releases?per_page=10}"
VENV_DIR="${PRC_VENV_DIR:-$HOME/.paper-research-coach/venv}"
BIN_DIR="${PRC_BIN_DIR:-$HOME/.local/bin}"
INSTALL_UV=0
OPEN=0
SHORTCUT=0
for arg in "$@"; do
  case "$arg" in
    --install-uv) INSTALL_UV=1 ;;
    --open) OPEN=1 ;;
    --shortcut) SHORTCUT=1 ;;
    -h|--help) sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) printf 'Unknown option: %s\n' "$arg" >&2; exit 2 ;;
  esac
done

say() { printf '%s\n' "$*"; }
fail() { printf '\n没有安装成功 / Install failed: %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

have curl || fail "需要 curl / curl is required."

TMP="$(mktemp -d "${TMPDIR:-/tmp}/prc-install.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT INT TERM

say "Paper Research Coach · 安装 / Install"

# 1. The newest release that carries a wheel (the API lists newest first).
say "· 查找最新版本 / Finding the newest release…"
curl -fsSL -H 'Accept: application/vnd.github+json' -H 'User-Agent: prc-install' "$RELEASES_URL" -o "$TMP/releases.json" \
  || fail "无法连接 GitHub。请检查网络，或到 Releases 页面手动下载。/ Could not reach GitHub."
WHEEL_URL="$(grep -o '"browser_download_url": *"[^"]*paper_research_coach-[^"/]*-py3-none-any\.whl"' "$TMP/releases.json" | head -n 1 | sed 's/.*: *"\(.*\)"/\1/')"
[ -n "$WHEEL_URL" ] || fail "没有找到可安装的发布版本。/ No installable release found."
WHEEL_NAME="${WHEEL_URL##*/}"
SUMS_URL="${WHEEL_URL%/*}/SHA256SUMS"
VERSION="${WHEEL_NAME#paper_research_coach-}"
VERSION="${VERSION%%-py3-none-any.whl}"
say "  最新版本 / Newest: $VERSION"

# 2. Download and verify.
say "· 下载并校验 / Downloading and verifying…"
curl -fsSL "$WHEEL_URL" -o "$TMP/$WHEEL_NAME" || fail "下载失败 / Download failed."
curl -fsSL "$SUMS_URL" -o "$TMP/SHA256SUMS" \
  || fail "这个版本没有校验文件（SHA256SUMS），为安全起见不安装。/ This release has no SHA256SUMS; refusing to install unverified code."
EXPECTED="$(grep " $WHEEL_NAME\$" "$TMP/SHA256SUMS" | head -n 1 | cut -d ' ' -f 1)"
[ -n "$EXPECTED" ] || fail "校验文件里没有这个安装包。/ SHA256SUMS does not list this wheel."
if have sha256sum; then ACTUAL="$(sha256sum "$TMP/$WHEEL_NAME" | cut -d ' ' -f 1)"
elif have shasum; then ACTUAL="$(shasum -a 256 "$TMP/$WHEEL_NAME" | cut -d ' ' -f 1)"
else fail "需要 sha256sum 或 shasum。/ sha256sum or shasum is required."; fi
[ "$EXPECTED" = "$ACTUAL" ] || fail "校验值不符，已停止。/ Checksum mismatch; nothing was installed."

# 3. Pick an installer: uv (it can also fetch Python), pipx, or a plain venv.
METHOD="${PRC_INSTALL_METHOD:-}"
if [ -z "$METHOD" ]; then
  if have uv; then METHOD=uv
  elif have pipx; then METHOD=pipx
  elif have python3 && python3 -c 'import sys, venv; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then METHOD=venv
  elif [ "$INSTALL_UV" = 1 ]; then
    say "· 安装 uv / Installing uv (https://astral.sh/uv)…"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    have uv || fail "uv 安装后仍找不到。/ uv is still not on PATH."
    METHOD=uv
  else
    fail "没有找到 uv、pipx，也没有 Python 3.10 或更新版本。
  最省事：先安装 uv（它会自动准备 Python），然后重新运行本脚本：
    curl -LsSf https://astral.sh/uv/install.sh | sh
  或者给本脚本加上 --install-uv，让它代你安装 uv。
  Easiest: install uv (it fetches Python for you) and run this again, or add --install-uv."
  fi
fi

say "· 安装 / Installing with $METHOD…"
case "$METHOD" in
  uv)
    uv tool install --force --python 3.12 "$TMP/$WHEEL_NAME" >"$TMP/install.log" 2>&1 || { cat "$TMP/install.log" >&2; fail "uv 安装失败 / uv install failed."; }
    uv tool update-shell >/dev/null 2>&1 || true
    ;;
  pipx)
    pipx install --force "$TMP/$WHEEL_NAME" >"$TMP/install.log" 2>&1 || { cat "$TMP/install.log" >&2; fail "pipx 安装失败 / pipx install failed."; }
    pipx ensurepath >/dev/null 2>&1 || true
    ;;
  venv)
    mkdir -p "$(dirname "$VENV_DIR")" "$BIN_DIR"
    python3 -m venv "$VENV_DIR" && "$VENV_DIR/bin/python" -m pip install --quiet --upgrade "$TMP/$WHEEL_NAME" >"$TMP/install.log" 2>&1 \
      || { cat "$TMP/install.log" >&2; fail "venv 安装失败 / venv install failed."; }
    ln -sf "$VENV_DIR/bin/prc" "$BIN_DIR/prc"
    ;;
  *) fail "未知的安装方式：$METHOD" ;;
esac

# 4. Find the installed command so we can show a working next step even before PATH is refreshed.
PRC=""
case "$METHOD" in
  uv) PRC="$(uv tool dir --bin 2>/dev/null || true)/prc" ;;
  pipx) PRC="$(pipx environment --value PIPX_BIN_DIR 2>/dev/null || true)/prc" ;;
  venv) PRC="$VENV_DIR/bin/prc" ;;
esac
[ -x "$PRC" ] || { have prc && PRC="$(command -v prc)"; }
[ -x "$PRC" ] || fail "安装完成，但找不到 prc 程序。/ Installed, but the prc command was not found."
say "  已安装 / Installed: $("$PRC" --version)"
# Skill copies made earlier by `prc install-skill` follow this version too.
"$PRC" install-skill --sync >/dev/null 2>&1 || true

if [ "$SHORTCUT" = 1 ]; then "$PRC" shortcut || true; fi

cat <<EOF

完成。/ Done.

  打开工作台 / Open the workbench:   prc
  桌面图标 / Desktop launcher:        prc shortcut
  更新 / Updates:                     自动。工作台会在后台校验并安装新版本，Skill 副本随之更新；
                                      也可以随时运行 prc update。/ Automatic; or run prc update.

如果终端提示找不到 prc，请重新打开终端（安装器已把 prc 放进 PATH）。
If the terminal cannot find prc, open a new terminal window.
Claude Code 用户：在 Claude Code 里运行 /plugin marketplace add $REPO 安装 Skill。
EOF

if [ "$OPEN" = 1 ]; then exec "$PRC"; fi
