# daily-report / hybrid_logger

2分ごとにアクティブウィンドウとOCRで画面テキストを記録し、日報作成の素材を自動収集するツール。

## 概要

- アクティブウィンドウのタイトルを取得
- CPU/メモリ使用率が高い場合はOCRをスキップ（軽量モード）
- 余裕があるときはスクリーンショットをOCRにかけてテキスト抽出
- 結果をJSONLファイルに追記（Google Drive等の共有フォルダへ保存可能）
- Google Drive の競合コピーを自動マージ（起動時・1時間ごと）

---

## セットアップ手順

### Mac の場合

#### ステップ1: 必要なソフトをインストール

ターミナルを開いて以下を実行する（Spotlight で「Terminal」と検索）。

```bash
# Homebrew がなければまず入れる
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Tesseract OCR（日本語 + 英語）
brew install tesseract tesseract-lang

# Python パッケージ
pip3 install psutil pillow pytesseract python-dotenv
```

#### ステップ2: このリポジトリを置く場所を決める

```bash
# 例: ホームディレクトリに置く場合
cd ~
git clone https://github.com/bighope99/daily-report.git
cd daily-report
```

#### ステップ3: ログ保存先を設定する

`.env` ファイルを作って、ログをどこに保存するか指定する。

```bash
cp .env.example .env
open -e .env   # テキストエディットで開く
```

開いたら `DAILY_REPORT_LOG_DIR=` の右側にパスを書く：

```
DAILY_REPORT_LOG_DIR=/Users/あなたの名前/Library/CloudStorage/GoogleDrive-メールアドレス/マイドライブ/日報用
```

> **Google Drive のパスの確認方法**
> Finder でそのフォルダを開き、フォルダを右クリック → 「情報を見る」→ 「場所」をコピーして、フォルダ名まで含めたフルパスを貼り付ける。
> または Finder でフォルダを表示した状態で `option + command + P` でパスバーを表示して確認する。

保存したら閉じる。

#### ステップ4: start.sh のパスを確認する

`start.sh` と `DailyReport.app/Contents/MacOS/run.sh` にはログ保存先やPATH等の環境変数がハードコードされている。自分の環境に合わせて編集すること：

```bash
# 確認するファイル
cat start.sh
cat DailyReport.app/Contents/MacOS/run.sh
```

特に以下の行を自分のパスに変更する：
- `HOME` — ホームディレクトリ
- `DAILY_REPORT_LOG_DIR` — ログ保存先（Google Drive のパス）
- `PYTHONUSERBASE` / `PYTHONPATH` — Python パッケージのパス

#### ステップ5: 動作確認（手動で起動してみる）

```bash
cd ~/daily-report
bash start.sh
```

2分後にログファイル（`activity_YYYY-MM-DD.jsonl`）にエントリが追加されれば OK。
`Ctrl + C` で止める。

#### ステップ6: 画面収録の権限を付与する

Mac では画面キャプチャに「画面収録」権限が必要。

1. `システム設定 > プライバシーとセキュリティ > 画面収録` を開く
2. `+` ボタンをクリック
3. リポジトリ内の `DailyReport.app` を選択して追加
4. トグルをオンにする

> **なぜ .app が必要？**
> macOS Sequoia 以降、LaunchAgent から起動したプロセスに画面収録権限を付与するには、`.app` バンドルに関連付ける必要がある。`DailyReport.app` はそのためのラッパーで、中身は `start.sh` と同じスクリプト。

#### ステップ7: PC起動時に自動で立ち上がるようにする

Mac の「LaunchAgents」に設定ファイルを置くとログイン時に自動実行される（Windowsのスタートアップフォルダと同じ概念）。

**1. 設定ファイルを作る**

ターミナルで以下をそのまま実行する。パスは自分のものに変える：

```bash
cat > ~/Library/LaunchAgents/com.daily-report.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.daily-report</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/ユーザー名/daily-report/DailyReport.app/Contents/MacOS/run.sh</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>AssociatedBundleIdentifiers</key>
  <string>com.daily-report.app</string>
  <key>StandardOutPath</key>
  <string>/tmp/hybrid_logger.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/hybrid_logger.log</string>
</dict>
</plist>
EOF
```

> **ポイント**:
> - `ProgramArguments` は `DailyReport.app` 内の `run.sh` を指定する
> - `AssociatedBundleIdentifiers` により、macOS がこのプロセスを `DailyReport.app` に関連付け、画面収録権限が適用される
> - `.env` ファイルは LaunchAgent からは読み込まれないため、環境変数は `run.sh` 内にハードコードしている

**2. 登録して今すぐ起動する**

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.daily-report.plist
```

**3. 動いているか確認する**

```bash
# プロセスが起動しているか確認
ps aux | grep hybrid_logger | grep -v grep

# エラーログを見る
cat /tmp/hybrid_logger.log

# デバッグログを見る（LOG_DIR内）
tail -20 /path/to/LOG_DIR/debug_hybrid_logger.log
```

これで次回ログイン時から自動で起動するようになる。

#### 停止・登録解除

```bash
# 今すぐ停止
launchctl bootout gui/$(id -u)/com.daily-report

# 再起動（停止 → 起動）
launchctl bootout gui/$(id -u)/com.daily-report
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.daily-report.plist

# 自動起動を完全に解除（ファイルも消す）
launchctl bootout gui/$(id -u)/com.daily-report
rm ~/Library/LaunchAgents/com.daily-report.plist
```

---

### Windows の場合

#### ステップ1: Tesseract OCR をインストール

https://github.com/UB-Mannheim/tesseract/wiki からインストーラーをダウンロードして実行。
インストール時に **Japanese** と **English** の言語データを選択すること。

#### ステップ2: Python パッケージをインストール

```bash
pip install psutil pillow pytesseract pywin32 python-dotenv
```

#### ステップ3: ログ保存先を設定する

`.env.example` を `.env` にコピーして編集する：

```
DAILY_REPORT_LOG_DIR=G:\マイドライブ\50_個人\日報用
```

#### ステップ4: PC起動時に自動実行する

1. `Win + R` → `shell:startup` を開く
2. 右クリック → 「新規作成」→「ショートカット」
3. リンク先に以下を入力（パスは自分の環境に合わせる）：

```
pythonw.exe "C:\Users\<ユーザー名>\daily-report\hybrid_logger.py"
```

4. 名前は何でも OK（例: `hybrid_logger`）→ 完了

次回 Windows ログイン時から自動実行される。

**今すぐ起動したい場合:**

```bash
pythonw hybrid_logger.py
```

**停止:**

```powershell
# PIDファイルを使って該当プロセスだけ終了（他の pythonw を巻き込まない）
$pidVal = Get-Content "$env:USERPROFILE\daily-report-logs\hybrid_logger.pid"
Stop-Process -Id $pidVal
```

---

## 設定値の一覧

| 定数 | デフォルト | 説明 |
|---|---|---|
| `INTERVAL` | `120` | 記録間隔（秒） |
| `RETENTION_DAYS` | `7` | ログ保持日数 |
| `CPU_THRESHOLD` | `85.0` | OCRスキップするCPU使用率（%） |
| `MEM_THRESHOLD` | `90.0` | OCRスキップするメモリ使用率（%） |
| `DAY_START_HOUR` | `3` | 業務日の切り替わり時刻（深夜3時） |
| `OCR_SKIP_CHARS` | `300` | OCRテキストの読み飛ばし文字数 |
| `OCR_END_CHARS` | `1000` | OCRテキストの取得終了位置 |

---

## ファイル構成

```
daily-report/
├── hybrid_logger.py          # メインスクリプト
├── start.sh                  # 手動起動・環境変数設定用
├── DailyReport.app/          # macOS 画面収録権限用の .app ラッパー
│   └── Contents/
│       ├── Info.plist         # バンドルID: com.daily-report.app
│       └── MacOS/
│           └── run.sh         # start.sh と同等（launchd 用）
├── .env                      # ログ保存先等の設定（git管理外）
└── README.md
```

---

## ログ仕様

**ファイル名**: `activity_YYYY-MM-DD.jsonl`（日付ごとに1ファイル）

**1エントリの形式**:
```json
{
  "timestamp": "2026-02-20T10:30:00",
  "process": "Google Chrome",
  "window_title": "GitHub - daily-report",
  "ocr_text": "（画面テキスト 最大500文字）"
}
```

---

## 複数PCでの利用

複数PCで同じGoogle Driveフォルダを `DAILY_REPORT_LOG_DIR` に設定すると、ログを1つのファイルにまとめられます。

Google Drive の同期競合で重複ファイルが生成された場合、起動時と1時間ごとに自動でマージ・削除されます。

---

## トラブルシューティング

### Mac: 画面キャプチャが動かない

`/tmp/hybrid_logger.log` やデバッグログに `could not create image from display` が出る場合：

1. `システム設定 > プライバシーとセキュリティ > 画面収録` で `DailyReport.app` が追加・有効になっているか確認
2. LaunchAgent を再起動: `launchctl bootout gui/$(id -u)/com.daily-report && launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.daily-report.plist`

### Mac: プロセスが起動しない

```bash
# LaunchAgent の状態確認
launchctl list | grep daily-report

# エラー確認
cat /tmp/hybrid_logger.log
```

### 二重起動防止

PIDファイル（`hybrid_logger.pid`）で制御。既にプロセスが動いている場合は起動しない。
プロセスが異常終了してPIDファイルが残った場合は手動で削除する：

```bash
rm /path/to/LOG_DIR/hybrid_logger.pid
```
