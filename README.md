# daily-report / hybrid_logger

5分ごとにアクティブウィンドウとOCRで画面テキストを記録し、日報作成の素材を自動収集するツール。

## 概要

- アクティブウィンドウのタイトルを取得
- CPU/メモリ使用率が高い場合はOCRをスキップ（軽量モード）
- 余裕があるときはスクリーンショットをOCRにかけてテキスト抽出
- 結果をJSONLファイルに追記（Google Drive等の共有フォルダへ保存可能）

## ログ仕様

**ファイル名**: `activity_YYYY-MM-DD.jsonl`（日付ごとに1ファイル）

**1エントリの形式**:
```json
{
  "timestamp": "2026-02-20T10:30:00.123456",
  "device": "MYPC",
  "status": "FULL_OCR",
  "load": "CPU:12.5%, MEM:65.3%",
  "window_title": "Visual Studio Code",
  "ocr_text": "（画面テキスト 最大500文字）"
}
```

| `status` 値 | 意味 |
|---|---|
| `FULL_OCR` | OCR実行済み |
| `SKIP_OCR` | 高負荷のためOCRスキップ |

## OCRテキスト処理

1. 連続する空白・改行を1スペースに圧縮
2. 300文字以上の場合は先頭300文字（ヘッダー・メニュー領域）を読み飛ばし、300〜800文字目を取得
3. 300文字未満の場合はそのまま取得

## 設定

`hybrid_logger.py` 冒頭の定数で変更可能：

| 定数 | デフォルト | 説明 |
|---|---|---|
| `LOG_DIR` | `G:\マイドライブ\50_個人\日報用` | ログ保存先 |
| `INTERVAL` | `300` | 記録間隔（秒） |
| `RETENTION_DAYS` | `7` | ログ保持日数 |
| `CPU_THRESHOLD` | `85.0` | OCRスキップするCPU使用率（%） |
| `MEM_THRESHOLD` | `90.0` | OCRスキップするメモリ使用率（%） |
| `DAY_START_HOUR` | `3` | 業務日の切り替わり時刻（深夜3時） |

## インストール

### 1. Tesseract OCR

https://github.com/UB-Mannheim/tesseract/wiki からインストーラーをダウンロードして実行。
インストール時に **Japanese** と **English** の言語データを選択すること。

### 2. Pythonを実行可能にする

```bash
pip install pywin32
```

### 3. 拡張機能のインストール

```bash
pip install psutil pillow pytesseract pywin32
```

## 実行

```bash
python hybrid_logger.py
```

タスクスケジューラ等でPC起動時に自動実行するとよい。
