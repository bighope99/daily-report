#!/bin/bash
# DailyReport.app/Contents/MacOS/run.sh
# launchd から起動されるエントリポイント。パスはすべて動的解決。

# .app/Contents/MacOS/ から 3階層上が PROJECT_ROOT
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

export HOME="${HOME:-$(eval echo ~$(whoami))}"

# Homebrew（Apple Silicon: /opt/homebrew、Intel: /usr/local）を自動検出
for brew_prefix in /opt/homebrew /usr/local; do
  if [ -d "$brew_prefix/bin" ]; then
    export PATH="$brew_prefix/bin:$PATH"
    break
  fi
done
export PATH="$PATH:/usr/bin:/bin:/usr/sbin:/sbin"

# Python user site-packages をバージョンに合わせて動的取得
PYVER="$(/usr/bin/python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")'  2>/dev/null)"
if [ -n "$PYVER" ]; then
  export PYTHONUSERBASE="$HOME/Library/Python/$PYVER"
  export PYTHONPATH="$PYTHONUSERBASE/lib/python/site-packages${PYTHONPATH:+:$PYTHONPATH}"
fi

# DAILY_REPORT_LOG_DIR は $PROJECT_ROOT/.env から hybrid_logger.py が python-dotenv で読む
# ここでは上書きしない（.env を使う）

exec /usr/bin/python3 "$PROJECT_ROOT/hybrid_logger.py"
