#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
PLIST_TEMPLATE="$PROJECT_ROOT/macos/com.daily-report.plist.template"
PLIST_DST="$HOME/Library/LaunchAgents/com.daily-report.plist"
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"

echo "=== daily-report macOS install ==="
echo "PROJECT_ROOT: $PROJECT_ROOT"

# 既存 LaunchAgent 停止
launchctl bootout "gui/$(id -u)/com.daily-report" 2>/dev/null && echo "Stopped existing LaunchAgent." || true

# plist 生成（テンプレートの {{PROJECT_ROOT}} を実パスに置換）
mkdir -p "$HOME/Library/LaunchAgents"
sed "s|{{PROJECT_ROOT}}|$PROJECT_ROOT|g" "$PLIST_TEMPLATE" > "$PLIST_DST"
echo "Generated: $PLIST_DST"

# run.sh を実行可能に
chmod +x "$PROJECT_ROOT/DailyReport.app/Contents/MacOS/run.sh"

# LaunchServices へのバンドル登録（TCC が bundle ID を認識するために必要）
if [ -x "$LSREGISTER" ]; then
  "$LSREGISTER" -f "$PROJECT_ROOT/DailyReport.app"
  echo "Registered DailyReport.app with LaunchServices."
fi

# LaunchAgent 起動
launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"
echo "LaunchAgent started."

echo ""
echo "=== 次のステップ ==="
echo "1. tccutil reset ScreenCapture com.daily-report.app  （初回または権限が効いていない場合）"
echo "2. システム設定 > プライバシーとセキュリティ > 画面収録 で DailyReport を ON にする"
echo "3. 2分後に \$DAILY_REPORT_LOG_DIR/debug_hybrid_logger.log で screencapture rc=0 を確認"
