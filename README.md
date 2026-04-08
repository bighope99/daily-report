# daily-report / hybrid_logger

5分ごとにアクティブウィンドウとOCRで画面テキストを記録し、日報作成の素材を自動収集するツール。

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

#### ステップ4: 動作確認（手動で起動してみる）

```bash
cd ~/daily-report
python3 hybrid_logger.py
```

こんな表示が出れば OK：

```
[Config] LOG_DIR=/Users/.../日報用
[Config] TESSERACT_CMD=tesseract
[Config] Platform=Darwin
```

`Ctrl + C` で止める。

#### ステップ5: PC起動時に自動で立ち上がるようにする

Mac には「LaunchAgents」という仕組みがあり、ここに設定ファイルを置くとログイン時に自動実行される（Windowsのスタートアップフォルダと同じ概念）。

**1. 設定ファイルを作る**

ターミナルで以下をそのまま実行する。`/Users/ユーザー名` の部分だけ自分のものに変える：

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
    <string>/usr/bin/python3</string>
    <string>/Users/ユーザー名/daily-report/hybrid_logger.py</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>DAILY_REPORT_LOG_DIR</key>
    <string>/Users/ユーザー名/Library/CloudStorage/GoogleDrive-メールアドレス/マイドライブ/日報用</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/tmp/hybrid_logger.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/hybrid_logger.log</string>
</dict>
</plist>
EOF
```

> **注意**: `.env` ファイルは LaunchAgents からは読み込まれないため、`EnvironmentVariables` のブロックにも同じパスを書く必要がある。

**2. 登録して今すぐ起動する**

```bash
launchctl load ~/Library/LaunchAgents/com.daily-report.plist
```

**3. 動いているか確認する**

```bash
# プロセスが起動しているか確認
pgrep -fl hybrid_logger

# ログを見る
tail -f /tmp/hybrid_logger.log
```

これで次回ログイン時から自動で起動するようになる。

#### 停止・登録解除

```bash
# 今すぐ停止（PIDファイルを使って該当プロセスだけ終了）
kill $(cat ~/daily-report-logs/hybrid_logger.pid)

# 自動起動を解除（ファイルも消す）
launchctl unload ~/Library/LaunchAgents/com.daily-report.plist
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

## ログ仕様

**ファイル名**: `activity_YYYY-MM-DD.jsonl`（日付ごとに1ファイル）

**1エントリの形式**:
```json
{
  "timestamp": "2026-02-20T10:30:00",
  "window_title": "Visual Studio Code",
  "ocr_text": "（画面テキスト 最大500文字）"
}
```

---

## 複数PCでの利用

複数PCで同じGoogle Driveフォルダを `DAILY_REPORT_LOG_DIR` に設定すると、ログを1つのファイルにまとめられます。

Google Drive の同期競合で重複ファイルが生成された場合、起動時と1時間ごとに自動でマージ・削除されます。
