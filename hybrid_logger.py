import time
import json
import os
import datetime
import win32gui
import psutil
from PIL import ImageGrab
import pytesseract

# ==========================================
# 設定
# ==========================================
LOG_DIR = r"G:\マイドライブ\50_個人\日報用"
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

DAY_START_HOUR = 3
RETENTION_DAYS = 7
INTERVAL = 300  # 5分

# 高負荷と判定する閾値（%）
CPU_THRESHOLD = 85.0
MEM_THRESHOLD = 90.0

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
            file_date = datetime.datetime.strptime(parts[1], "%Y-%m-%d").date()
            if file_date < cutoff_date:
                os.remove(os.path.join(LOG_DIR, filename))
                print(f"[Deleted] {filename}")
        except (ValueError, IndexError):
            continue

def get_active_window_title():
    try:
        hwnd = win32gui.GetForegroundWindow()
        return win32gui.GetWindowText(hwnd)
    except Exception:
        return "Unknown"

def is_system_overloaded():
    """CPUとメモリの使用率をチェックし、閾値を超えているか判定する"""
    # 0.5秒間サンプリングしてCPU使用率を取得
    cpu_usage = psutil.cpu_percent(interval=0.5)
    mem_usage = psutil.virtual_memory().percent
    
    is_heavy = cpu_usage >= CPU_THRESHOLD or mem_usage >= MEM_THRESHOLD
    return is_heavy, cpu_usage, mem_usage

def perform_ocr():
    """メモリ上でスクショを取得し、直接OCRにかける（ディスクI/Oゼロ）"""
    try:
        # アクティブウィンドウの座標計算をサボらず全画面を撮る（マルチモニタ環境では要調整）
        screenshot = ImageGrab.grab()
        # 画像データを保存せず、直接Tesseractに渡す
        text = pytesseract.image_to_string(screenshot, lang='jpn+eng')
        return text.strip()
    except Exception as e:
        return f"[OCR Error] {str(e)}"

def save_log(title, ocr_text, cpu_usage, mem_usage, status):
    logical_date = get_logical_date()
    date_str = logical_date.strftime("%Y-%m-%d")
    pc_name = os.environ.get('COMPUTERNAME', 'UnknownPC')
    filepath = os.path.join(LOG_DIR, f"activity_{date_str}_{pc_name}.jsonl")
    
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "device": pc_name,
        "status": status,
        "load": f"CPU:{cpu_usage}%, MEM:{mem_usage}%",
        "window_title": title,
        "ocr_text": ocr_text[:500]  # ノイズ削減のため先頭500文字に制限
    }
    
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
    cleanup_old_logs()
    last_cleanup_date = get_logical_date()

    while True:
        try:
            current_date = get_logical_date()
            if current_date != last_cleanup_date:
                cleanup_old_logs()
                last_cleanup_date = current_date
            
            title = get_active_window_title()
            if title:
                is_heavy, cpu, mem = is_system_overloaded()
                
                if is_heavy:
                    # 重い時はOCRをスキップしてタイトルだけ記録
                    save_log(title, "[SKIPPED_DUE_TO_HIGH_LOAD]", cpu, mem, "SKIP_OCR")
                else:
                    # 余裕がある時だけOCR実行
                    ocr_text = perform_ocr()
                    save_log(title, ocr_text, cpu, mem, "FULL_OCR")
                
        except Exception as e:
            print(f"Loop Error: {e}")

        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()