import time
import json
import os
import sys
import datetime
import re
import platform
import glob as glob_module
import subprocess
import logging
import logging.handlers
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
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
    import win32process
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

# タイムアウト（秒）：Windows APIやOCRがハングした場合に強制スキップ
API_TIMEOUT = 30

# ==========================================
# デバッグロガー設定
# ==========================================

def _setup_logger():
    os.makedirs(LOG_DIR, exist_ok=True)
    log_path = os.path.join(LOG_DIR, "debug_hybrid_logger.log")
    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    lg = logging.getLogger("hybrid_logger")
    lg.setLevel(logging.DEBUG)
    lg.addHandler(handler)
    return lg

logger = _setup_logger()

# ==========================================
# タイムアウトラッパー
# ==========================================

def _run_with_timeout(fn, timeout=API_TIMEOUT, fallback=None):
    """fnをタイムアウト付きで実行。タイムアウト時はfallbackを返す。"""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn)
        try:
            return future.result(timeout=timeout)
        except FuturesTimeoutError:
            logger.error(f"TIMEOUT ({timeout}s): {fn.__name__ if hasattr(fn, '__name__') else fn}")
            return fallback() if callable(fallback) else fallback

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
                logger.info(f"Deleted old log: {filename}")
        except (ValueError, IndexError):
            continue

def merge_fallback_logs():
    """ローカルフォールバックディレクトリのログをLOG_DIRにマージする"""
    fallback_dir = os.path.expanduser("~/daily-report-logs")
    if not os.path.exists(fallback_dir):
        return
    for filename in os.listdir(fallback_dir):
        if not filename.endswith(".jsonl"):
            continue
        src_path = os.path.join(fallback_dir, filename)
        dst_path = os.path.join(LOG_DIR, filename)
        try:
            with open(src_path, 'r', encoding='utf-8') as src:
                content = src.read()
            if not content.strip():
                os.remove(src_path)
                continue
            with open(dst_path, 'a', encoding='utf-8') as dst:
                if not content.endswith('\n'):
                    content += '\n'
                dst.write(content)
            os.remove(src_path)
            logger.info(f"Merged fallback: {filename} → LOG_DIR")
        except PermissionError:
            logger.warning(f"Fallback merge skipped (still locked): {filename}")
        except Exception as e:
            logger.error(f"Fallback merge error {filename}: {e}")

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
                logger.info(f"Merged: {os.path.basename(path)} → {os.path.basename(main_file)}")
            os.remove(path)
            logger.info(f"Deleted conflict copy: {os.path.basename(path)}")
        except Exception as e:
            logger.error(f"Merge error {path}: {e}")

def _get_active_window_info_impl():
    if _IS_WINDOWS:
        try:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid).name()
            return title, process
        except Exception as e:
            logger.warning(f"get_active_window_info failed: {e}")
            return "Unknown", "Unknown"
    elif _IS_MAC:
        try:
            script = '''
tell application "System Events"
    set frontApp to first application process whose frontmost is true
    set appName to name of frontApp
    try
        set winTitle to title of front window of frontApp
    on error
        set winTitle to appName
    end try
    return appName & "|" & winTitle
end tell'''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=5
            )
            output = result.stdout.strip()
            if "|" in output:
                process, title = output.split("|", 1)
                return title.strip() or process.strip(), process.strip()
            return output or "Unknown", output or "Unknown"
        except Exception as e:
            logger.warning(f"get_active_window_info failed: {e}")
            return "Unknown", "Unknown"
    else:
        return "Unknown", "Unknown"

def get_active_window_info():
    result = _run_with_timeout(_get_active_window_info_impl, fallback=("Unknown", "Unknown"))
    return result if result is not None else ("Unknown", "Unknown")

def _is_session_locked_impl():
    if _IS_WINDOWS:
        ctypes.windll.user32.OpenInputDesktop.restype = ctypes.c_void_p
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

def is_session_locked():
    result = _run_with_timeout(_is_session_locked_impl, fallback=False)
    return bool(result)

def is_system_overloaded():
    """CPUとメモリの使用率をチェックし、閾値を超えているか判定する"""
    cpu_usage = psutil.cpu_percent(interval=0.5)
    mem_usage = psutil.virtual_memory().percent
    is_heavy = cpu_usage >= CPU_THRESHOLD or mem_usage >= MEM_THRESHOLD
    return is_heavy, cpu_usage, mem_usage

def _capture_active_window_impl():
    if _IS_WINDOWS:
        try:
            hwnd = win32gui.GetForegroundWindow()
            rect = win32gui.GetWindowRect(hwnd)  # (left, top, right, bottom)
            return ImageGrab.grab(bbox=rect)
        except Exception:
            return ImageGrab.grab()
    elif _IS_MAC:
        try:
            script = '''
tell application "System Events"
    set frontApp to first application process whose frontmost is true
    set winPos to position of front window of frontApp
    set winSize to size of front window of frontApp
    return ((item 1 of winPos) as string) & "," & ((item 2 of winPos) as string) & "," & ((item 1 of winSize) as string) & "," & ((item 2 of winSize) as string)
end tell'''
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=5)
            x, y, w, h = map(int, result.stdout.strip().split(","))
            return ImageGrab.grab(bbox=(x, y, x + w, y + h))
        except Exception:
            return ImageGrab.grab()
    return ImageGrab.grab()

def capture_active_window():
    return _run_with_timeout(_capture_active_window_impl, fallback=None)

def _perform_ocr_impl(screenshot):
    text = pytesseract.image_to_string(screenshot, lang='jpn+eng')
    cleaned = re.sub(r'\s+', ' ', text).strip()
    if len(cleaned) >= OCR_SKIP_CHARS:
        return cleaned[OCR_SKIP_CHARS:OCR_END_CHARS]
    return cleaned

def perform_ocr(screenshot=None):
    """スクショをOCRにかける（ディスクI/Oゼロ）"""
    try:
        if screenshot is None:
            screenshot = ImageGrab.grab()
        result = _run_with_timeout(
            lambda: _perform_ocr_impl(screenshot),
            fallback="[OCR TIMEOUT]"
        )
        return result if result is not None else "[OCR TIMEOUT]"
    except Exception as e:
        logger.error(f"perform_ocr error: {e}")
        return f"[OCR Error] {str(e)}"

def save_log(title, process, ocr_text):
    logical_date = get_logical_date()
    date_str = logical_date.strftime("%Y-%m-%d")
    filepath = os.path.join(LOG_DIR, f"activity_{date_str}.jsonl")

    entry = {"timestamp": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}
    entry["process"] = process
    entry["window_title"] = title
    entry["ocr_text"] = ocr_text[:500]
    line = json.dumps(entry, ensure_ascii=False) + "\n"

    # Google Drive等のファイルロックに対してリトライ
    for attempt in range(4):
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(line)
            logger.debug(f"Saved log: {process} / {title[:40]}")
            return
        except PermissionError as e:
            if attempt < 3:
                logger.warning(f"Write permission denied (attempt {attempt+1}/3), retrying in 5s: {e}")
                time.sleep(5)
            else:
                # フォールバック: ローカルディレクトリに書く
                fallback_dir = os.path.expanduser("~/daily-report-logs")
                fallback_path = os.path.join(fallback_dir, f"activity_{date_str}.jsonl")
                try:
                    os.makedirs(fallback_dir, exist_ok=True)
                    with open(fallback_path, 'a', encoding='utf-8') as f:
                        f.write(line)
                    logger.warning(f"Wrote to fallback: {fallback_path}")
                except Exception as e2:
                    logger.error(f"Fallback write also failed: {e2}")
        except Exception as e:
            logger.error(f"Write error: {e}")
            return

def update_heartbeat():
    """ループが生きていることを示すハートビートファイルを更新する"""
    try:
        hb_path = os.path.join(LOG_DIR, "hybrid_logger.heartbeat")
        with open(hb_path, 'w', encoding='utf-8') as f:
            f.write(datetime.datetime.now().isoformat())
    except Exception as e:
        logger.warning(f"Heartbeat write failed: {e}")

# ==========================================
# メインループ
# ==========================================

def main():
    logger.info(f"Starting hybrid_logger. LOG_DIR={LOG_DIR} TESSERACT_CMD={TESSERACT_CMD} Platform={platform.system()}")

    # PIDファイル管理（二重起動防止）
    os.makedirs(LOG_DIR, exist_ok=True)
    pid_file = os.path.join(LOG_DIR, "hybrid_logger.pid")
    if os.path.exists(pid_file):
        try:
            existing_pid = int(open(pid_file).read().strip())
            if psutil.pid_exists(existing_pid):
                logger.error(f"Already running (PID {existing_pid}). Exiting.")
                sys.exit(1)
        except (ValueError, OSError):
            pass
    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))

    try:
        cleanup_old_logs()
        last_cleanup_date = get_logical_date()
        last_merge_time = time.time()

        # 起動時にマージ
        merge_fallback_logs()
        merge_conflict_copies(get_logical_date().strftime("%Y-%m-%d"))

        while True:
            try:
                update_heartbeat()

                current_date = get_logical_date()
                if current_date != last_cleanup_date:
                    cleanup_old_logs()
                    last_cleanup_date = current_date

                # 1時間ごとに競合コピー＆フォールバックをマージ
                if time.time() - last_merge_time >= MERGE_INTERVAL:
                    merge_fallback_logs()
                    merge_conflict_copies(current_date.strftime("%Y-%m-%d"))
                    last_merge_time = time.time()

                logger.debug("Checking session lock...")
                locked = is_session_locked()
                if locked:
                    time.sleep(INTERVAL)
                    continue

                logger.debug("Getting active window...")
                title, process = get_active_window_info()
                logger.debug(f"Active window: {process} / {title[:40]}")

                if title:
                    is_heavy, cpu, mem = is_system_overloaded()
                    logger.debug(f"System load: cpu={cpu:.1f}% mem={mem:.1f}% heavy={is_heavy}")

                    if is_heavy:
                        save_log(title, process, "[SKIPPED_DUE_TO_HIGH_LOAD]")
                    else:
                        logger.debug("Capturing screenshot...")
                        screenshot = capture_active_window()
                        if screenshot is None:
                            logger.error("Screenshot capture returned None, skipping OCR")
                        else:
                            logger.debug("Running OCR...")
                            ocr_text = perform_ocr(screenshot)
                            logger.debug(f"OCR done: {len(ocr_text)} chars")
                            save_log(title, process, ocr_text)
                else:
                    logger.debug("No active window title, skipping")

            except Exception as e:
                logger.error(f"Loop error: {e}", exc_info=True)

            time.sleep(INTERVAL)
    finally:
        if os.path.exists(pid_file):
            os.remove(pid_file)
        logger.info("hybrid_logger stopped.")

if __name__ == "__main__":
    main()
