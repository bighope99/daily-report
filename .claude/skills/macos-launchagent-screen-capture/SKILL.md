---
name: macos-launchagent-screen-capture
description: macOS で LaunchAgent からスクリーンキャプチャ付きプロセスを自動起動する方法。launchd、画面収録権限、screencapture、RunAtLoad、plist、自動起動、ログイン時実行、could not create image、AssociatedBundleIdentifiers に関する作業で使用すること。Python スクリプトの macOS 常駐化や、PIL.ImageGrab が launchd で動かない問題にも対応。
---

# macOS LaunchAgent + 画面収録パターン

macOS Sequoia 以降、LaunchAgent から起動したプロセスが画面キャプチャしようとすると `could not create image from display` で失敗する。これは macOS の TCC（Transparency, Consent, and Control）が、LaunchAgent プロセスに画面収録権限を付与する手段を提供していないため。

ターミナルから手動実行すれば動くのに、LaunchAgent 経由だと動かない — この差が混乱の原因になる。

## 解決の全体像

3つのピースを組み合わせる:

1. **`.app` バンドル** — macOS が「アプリケーション」として認識し、画面収録のダイアログで選択できるようにする
2. **`AssociatedBundleIdentifiers`** — LaunchAgent plist でプロセスと `.app` を紐付ける。これにより macOS が「このプロセスは DailyReport.app の一部だ」と認識し、権限が適用される
3. **`screencapture` コマンド** — `PIL.ImageGrab` の代替。launchd 環境でも `.app` 権限経由で動作する

## .app バンドルの作り方

最小構成は3ファイル。コード署名は不要。

```
MyApp.app/
└── Contents/
    ├── Info.plist
    └── MacOS/
        └── run.sh
```

**Info.plist** で重要なのは `CFBundleIdentifier`（後で plist から参照する）と `LSUIElement`（Dock に表示しない）:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleIdentifier</key>
  <string>com.example.myapp</string>
  <key>CFBundleName</key>
  <string>MyApp</string>
  <key>CFBundleExecutable</key>
  <string>run.sh</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>LSUIElement</key>
  <true/>
  <key>NSScreenCaptureUsageDescription</key>
  <string>Screen capture is required for this application.</string>
</dict>
</plist>
```

**run.sh** には環境変数をすべて明示する。launchd は `~/.zshrc` を読まないため、PATH は `/usr/bin:/bin:/usr/sbin:/sbin` しかない。homebrew のツール（tesseract 等）を使うなら `/opt/homebrew/bin` を足す:

```bash
#!/bin/bash
export HOME=/Users/ユーザー名
export PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin
export MY_ENV_VAR="value"
/usr/bin/python3 /path/to/script.py
```

作成後 `chmod +x run.sh` すること。

## LaunchAgent plist の書き方

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.example.myapp</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/MyApp.app/Contents/MacOS/run.sh</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>AssociatedBundleIdentifiers</key>
  <array>
    <string>com.example.myapp</string>
  </array>
  <key>StandardOutPath</key>
  <string>/tmp/myapp.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/myapp.log</string>
</dict>
</plist>
```

ポイント:
- `ProgramArguments` は `.app` 内の実行ファイルを直接指定する（`open -W` は不安定なため使わない）
- `AssociatedBundleIdentifiers` の値は Info.plist の `CFBundleIdentifier` と一致させる
- 置き場所は `~/Library/LaunchAgents/`

## 画面収録権限の付与

1. `システム設定 > プライバシーとセキュリティ > 画面収録` を開く
2. `+` ボタンで `.app` を追加（python3 等のコマンドは追加できないが、.app なら追加できる）
3. トグルをオンにする
4. 権限変更後は LaunchAgent を再起動する（再起動しないと反映されない）

## LaunchAgent の操作コマンド

```bash
# 登録して起動
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.example.myapp.plist

# 停止して登録解除
launchctl bootout gui/$(id -u)/com.example.myapp

# 再起動（よく使う）
launchctl bootout gui/$(id -u)/com.example.myapp
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.example.myapp.plist

# 状態確認
launchctl list | grep myapp
```

`launchctl load/unload` は非推奨。`bootstrap/bootout` を使う。

## screencapture による画面キャプチャ（macOS 専用）

`PIL.ImageGrab` は launchd 環境で動作しない。macOS では `screencapture` コマンドで一時ファイルに保存し、PIL で読み込む:

```python
import subprocess, tempfile, os
from PIL import Image

def capture_screen_mac():
    tmp_path = os.path.join(tempfile.gettempdir(), "capture.png")
    try:
        result = subprocess.run(
            ["screencapture", "-x", tmp_path],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and os.path.exists(tmp_path):
            img = Image.open(tmp_path)
            img.load()
            os.remove(tmp_path)
            return img
    except Exception:
        pass
    return None
```

`-x` はシャッター音を消す。Windows では従来通り `PIL.ImageGrab` を使い、`platform.system()` で分岐する。

## うまくいかないときのチェックリスト

| 症状 | 原因 | 対処 |
|------|------|------|
| `could not create image from display` | 画面収録権限がない | `.app` を画面収録に追加 → LaunchAgent 再起動 |
| プロセスが起動しない | plist のパスが間違っている | `cat /tmp/myapp.log` でエラー確認 |
| tesseract が見つからない | PATH に homebrew がない | run.sh で `/opt/homebrew/bin` を PATH に追加 |
| .env が読まれない | launchd はシェルプロファイルを読まない | run.sh 内で `export` するか、python-dotenv で読み込む |
| 二重起動する | PID ファイルが残っている | PID ファイルを手動削除 |
| `AttributeError: 'NoneType'` | logger の setup 関数が `return` していない | `_setup_logger()` が logger オブジェクトを返しているか確認 |
