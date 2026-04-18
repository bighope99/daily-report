# daily-report プロジェクトルール

## プロジェクト概要
2分間隔でアクティブウィンドウ + OCR テキストを記録する日報素材収集ツール。Mac / Windows 両対応。

## macOS LaunchAgent + 画面収録
- LaunchAgent から画面キャプチャするには `.app` バンドル + `AssociatedBundleIdentifiers` が必要（macOS Sequoia 以降）
- 詳細は `.claude/skills/macos-launchagent-screen-capture/SKILL.md` を参照
- `PIL.ImageGrab` は macOS の launchd 環境で動作しない。`screencapture` コマンドを使うこと
- Windows では従来通り `PIL.ImageGrab` を使用

## 環境変数
- launchd 環境はシェルプロファイルを読まないため、`start.sh` / `DailyReport.app/Contents/MacOS/run.sh` に環境変数をハードコードしている
- `DAILY_REPORT_LOG_DIR` — ログ保存先（Google Drive パス）
- PATH に `/opt/homebrew/bin` を含めること（tesseract 等の homebrew パッケージ用）

## LaunchAgent 操作
- 登録: `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.daily-report.plist`
- 停止: `launchctl bootout gui/$(id -u)/com.daily-report`
- `launchctl load/unload` は非推奨。`bootstrap/bootout` を使う
