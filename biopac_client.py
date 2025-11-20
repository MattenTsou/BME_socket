# biopac_client_fast.py  (BIOPAC PC)
import socket
import time
import pyautogui
import pyperclip

SERVER_IP = "192.168.50.222"
PORT = 50007
INTERVAL_SEC = 1.0   # 每秒抓一次 EEG，可再調整

def focus_biopac_and_start():   #自動切到 BIOPAC 視窗並按下開始錄影 
    """
    1. 找到 Biopac Student Lab 視窗，切到最前面
    2. 按一次 Ctrl+Space 開始測波形
    """
    time.sleep(1.0)  # 預留一點時間看到訊息 / 系統穩定

    try:
        # 這個字串請依視窗標題調整，如 "Biopac Student Lab" 或 "Biopac"
        wins = pyautogui.getWindowsWithTitle("Biopac Student Lab")
        if wins:
            win = wins[0]
            win.activate()   # 切到 BSL 視窗
            # win.maximize() # 如果你想順便最大化可以打開這行
            time.sleep(0.5)  # 等它真的在最前面
        else:
            # 找不到就退而求其次 Alt+Tab 一次（假設你已經先切好）
            pyautogui.hotkey('alt', 'tab')
            time.sleep(0.5)
    except Exception as e:
        print(f"[Client] 無法透過 getWindowsWithTitle 切視窗：{e}")
        # 退回 Alt+Tab
        pyautogui.hotkey('alt', 'tab')
        time.sleep(0.5)

    # 按下開始錄影（若已在錄，會變成停止，再按一次即可）
    pyautogui.hotkey('ctrl', 'space')
    time.sleep(0.3)
    print("[Client] 已自動切到 BIOPAC 並按下開始錄影 (Ctrl+Space)")

def grab_eeg_once() -> str:
    """
    假設：BSL 已經在錄影狀態，視窗在最前面。
    只做：
      1. Ctrl+A 全選
      2. Ctrl+L 轉成文字
      3. Ctrl+X 剪下（清空畫面，下次只剩新資料）
      4. 從剪貼簿取得文字
    """

    # 1. 全選目前所有波形
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.05)

    # 2. 轉成文字 / Copy Wave Data（依你實際快捷鍵調整）
    pyautogui.hotkey('ctrl', 'l')
    time.sleep(0.15)   # 視 BSL 速度可略調 0.1~0.3

    # 3. 剪下，避免資料越積越多
    pyautogui.hotkey('ctrl', 'x')
    time.sleep(0.05)

    # 4. 從剪貼簿拿 raw data
    text = pyperclip.paste()
    return text

def main():
    SEP = "\n===END===\n"

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        # 關 Nagle，降低延遲
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        print("[Client] Connecting to server...")
        sock.connect((SERVER_IP, PORT))
        print("[Client] Connected.")

        # === 在開始 while 之前，自動切到 BIOPAC 並按一次開始錄影 ===
        focus_biopac_and_start()

        block_id = 0
        while True:
            text = grab_eeg_once()
            # 確保不是空資料
            if not text.strip():
                print("[Client] 拿到空資料，跳過一次")
            else:
                block_id += 1
                msg = text + SEP
                sock.sendall(msg.encode("utf-8"))
                print(f"[Client] 已送出第 {block_id} 塊 EEG 文字，長度 {len(text)} 字元")

            # 控制更新頻率（決定每包大約幾筆）
            time.sleep(INTERVAL_SEC)

if __name__ == "__main__":
    main()
