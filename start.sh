#!/bin/bash
# 手動実行用スクリプト。LaunchAgent と同じ環境でテスト起動したいときに使う。

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

export HOME="${HOME:-$(eval echo ~$(whoami))}"

for brew_prefix in /opt/homebrew /usr/local; do
  if [ -d "$brew_prefix/bin" ]; then
    export PATH="$brew_prefix/bin:$PATH"
    break
  fi
done
export PATH="$PATH:/usr/bin:/bin:/usr/sbin:/sbin"

PYVER="$(/usr/bin/python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")'  2>/dev/null)"
if [ -n "$PYVER" ]; then
  export PYTHONUSERBASE="$HOME/Library/Python/$PYVER"
  export PYTHONPATH="$PYTHONUSERBASE/lib/python/site-packages${PYTHONPATH:+:$PYTHONPATH}"
fi

exec /usr/bin/python3 "$PROJECT_ROOT/hybrid_logger.py"
