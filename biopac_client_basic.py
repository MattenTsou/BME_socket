# biopac_client_fast.py  (BIOPAC PC)
import socket
import time
import pyautogui
import pyperclip

SERVER_IP = "192.168.50.222"
PORT = 50007
INTERVAL_SEC = 1.0   # 每秒抓一次 EEG，可再調整

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
