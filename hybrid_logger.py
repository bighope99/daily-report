import time
import json
import os
import sys
import datetime
import re
import platform
import glob as glob_module
import subprocess
from PIL import ImageGrab
import psutil
import pytesseract

# python-dotenv が入っていれば .env / .env.local を読み込む（スクリプトと同じディレクトリを基準にする）
try:
    from dotenv import load_dotenv
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(_script_dir, '.env'))
    load_dotenv(os.path.join(_script_dir, '.env.local'), override=True)
except ImportError:
    pass

# Windows 専用モジュール
if platform.system() == "Windows":
    import win32gui
    import ctypes

# ==========================================
# 設定
# ==========================================
_IS_WINDOWS = platform.system() == "Windows"
_IS_MAC = platform.system() == "Darwin"

# ログ保存先（環境変数 DAILY_REPORT_LOG_DIR で上書き可能）
_DEFAULT_LOG_DIR = os.path.expanduser("~/daily-report-logs")
LOG_DIR = os.environ.get("DAILY_REPORT_LOG_DIR", _DEFAULT_LOG_DIR)

# Tesseract パス（環境変数 TESSERACT_CMD で上書き可能）
if _IS_WINDOWS:
    _DEFAULT_TESSERACT = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
else:
    _DEFAULT_TESSERACT = "tesseract"  # Mac: brew install tesseract でPATHに入る
TESSERACT_CMD = os.environ.get("TESSERACT_CMD", _DEFAULT_TESSERACT)
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

DAY_START_HOUR = 3
RETENTION_DAYS = 7
INTERVAL = 120  # 2分

# 高負荷と判定する閾値（%）
CPU_THRESHOLD = 85.0
MEM_THRESHOLD = 90.0

# OCRテキスト取得範囲
OCR_SKIP_CHARS = 300   # 先頭から読み飛ばす文字数（ヘッダー・メニュー領域）
OCR_END_CHARS = 1000    # 取得終了位置

# 競合コピーマージの実行間隔（秒）
MERGE_INTERVAL = 3600  # 1時間

# ==========================================
# ロジック
# ==========================================

def get_logical_date():
    now = datetime.datetime.now()
    adjusted_time = now - datetime.timedelta(hours=DAY_START_HOUR)
    return adjusted_time.date()

def cleanup_old_logs():
    cutoff_date = get_logical_date() - datetime.timedelta(days=RETENTION_DAYS)
    if not os.path.exists(LOG_DIR): return

    for filename in os.listdir(LOG_DIR):
        if not filename.endswith(".jsonl"): continue
        try:
            parts = filename.split('_')
            if len(parts) < 2: continue
            file_date = datetime.datetime.strptime(parts[1].split()[0], "%Y-%m-%d").date()
            if file_date < cutoff_date:
                os.remove(os.path.join(LOG_DIR, filename))
                print(f"[Deleted] {filename}")
        except (ValueError, IndexError):
            continue

def merge_conflict_copies(date_str):
    """Google Drive等が生成した競合コピー（例: activity_2026-04-06 (1).jsonl）を本体にマージして削除"""
    pattern = os.path.join(LOG_DIR, f"activity_{date_str}*.jsonl")
    main_file = os.path.join(LOG_DIR, f"activity_{date_str}.jsonl")
    for path in glob_module.glob(pattern):
        if path == main_file:
            continue
        try:
            with open(path, 'r', encoding='utf-8') as src:
                content = src.read()
            if content.strip():
                with open(main_file, 'a', encoding='utf-8') as dst:
                    if not content.endswith('\n'):
                        content += '\n'
                    dst.write(content)
                print(f"[Merged] {os.path.basename(path)} → {os.path.basename(main_file)}")
            os.remove(path)
            print(f"[Deleted conflict copy] {os.path.basename(path)}")
        except Exception as e:
            print(f"[Merge Error] {path}: {e}")

def get_active_window_title():
    if _IS_WINDOWS:
        try:
            hwnd = win32gui.GetForegroundWindow()
            return win32gui.GetWindowText(hwnd)
        except Exception:
            return "Unknown"
    elif _IS_MAC:
        try:
            script = 'tell application "System Events" to get name of first application process whose frontmost is true'
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=3
            )
            return result.stdout.strip() or "Unknown"
        except Exception:
            return "Unknown"
    else:
        return "Unknown"

def is_session_locked():
    """画面ロック中か確認する"""
    if _IS_WINDOWS:
        hDesk = ctypes.windll.user32.OpenInputDesktop(0, False, 0x0100)
        if hDesk:
            ctypes.windll.user32.CloseDesktop(hDesk)
            return False
        return True
    elif _IS_MAC:
        try:
            result = subprocess.run(
                ["ioreg", "-n", "IOHIDSystem"],
                capture_output=True, text=True, timeout=3
            )
            return "CGSSessionScreenIsLocked" in result.stdout and '"CGSSessionScreenIsLocked" = Yes' in result.stdout
        except Exception:
            return False
    else:
        return False

def is_system_overloaded():
    """CPUとメモリの使用率をチェックし、閾値を超えているか判定する"""
    cpu_usage = psutil.cpu_percent(interval=0.5)
    mem_usage = psutil.virtual_memory().percent
    is_heavy = cpu_usage >= CPU_THRESHOLD or mem_usage >= MEM_THRESHOLD
    return is_heavy, cpu_usage, mem_usage

def perform_ocr():
    """メモリ上でスクショを取得し、直接OCRにかける（ディスクI/Oゼロ）"""
    try:
        screenshot = ImageGrab.grab()
        text = pytesseract.image_to_string(screenshot, lang='jpn+eng')
        cleaned = re.sub(r'\s+', ' ', text).strip()
        if len(cleaned) >= OCR_SKIP_CHARS:
            return cleaned[OCR_SKIP_CHARS:OCR_END_CHARS]
        return cleaned
    except Exception as e:
        return f"[OCR Error] {str(e)}"

def save_log(title, ocr_text):
    logical_date = get_logical_date()
    date_str = logical_date.strftime("%Y-%m-%d")
    filepath = os.path.join(LOG_DIR, f"activity_{date_str}.jsonl")

    entry = {"timestamp": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}
    entry["window_title"] = title
    entry["ocr_text"] = ocr_text[:500]

    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Write Error: {e}")

# ==========================================
# メインループ
# ==========================================

def main():
    print(f"[Config] LOG_DIR={LOG_DIR}")
    print(f"[Config] TESSERACT_CMD={TESSERACT_CMD}")
    print(f"[Config] Platform={platform.system()}")

    cleanup_old_logs()
    last_cleanup_date = get_logical_date()
    last_merge_time = time.time()

    # 起動時に競合コピーをマージ
    merge_conflict_copies(get_logical_date().strftime("%Y-%m-%d"))

    while True:
        try:
            current_date = get_logical_date()
            if current_date != last_cleanup_date:
                cleanup_old_logs()
                last_cleanup_date = current_date

            # 1時間ごとに競合コピーをマージ
            if time.time() - last_merge_time >= MERGE_INTERVAL:
                merge_conflict_copies(current_date.strftime("%Y-%m-%d"))
                last_merge_time = time.time()

            if is_session_locked():
                time.sleep(INTERVAL)
                continue

            title = get_active_window_title()
            if title:
                is_heavy, cpu, mem = is_system_overloaded()

                if is_heavy:
                    save_log(title, "[SKIPPED_DUE_TO_HIGH_LOAD]")
                else:
                    ocr_text = perform_ocr()
                    save_log(title, ocr_text)

        except Exception as e:
            print(f"Loop Error: {e}")

        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
