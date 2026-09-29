#!/bin/sh
# macOS: double-click after installing the wheel in the documented environment.
if command -v prc >/dev/null 2>&1; then
  exec prc serve
elif [ -x "$HOME/.venvs/paper-research-coach/bin/prc" ]; then
  exec "$HOME/.venvs/paper-research-coach/bin/prc" serve
else
  printf '%s\n' '请先按照 README 安装工作台；尚未找到 prc。' 'Install the workbench as described in README first.'
  read -r answer
  exit 1
fi
