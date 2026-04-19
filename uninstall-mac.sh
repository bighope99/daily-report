#!/bin/bash

PLIST_DST="$HOME/Library/LaunchAgents/com.daily-report.plist"

echo "=== daily-report macOS uninstall ==="

launchctl bootout "gui/$(id -u)/com.daily-report" 2>/dev/null && echo "Stopped LaunchAgent." || echo "LaunchAgent was not running."

if [ -f "$PLIST_DST" ]; then
  rm "$PLIST_DST"
  echo "Removed: $PLIST_DST"
fi

echo "Done. TCC permissions remain — remove manually if needed:"
echo "  tccutil reset ScreenCapture com.daily-report.app"
