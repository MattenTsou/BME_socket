# eeg_server_1sec.py  (Own PC：你的電腦)
import socket

HOST = '0.0.0.0'
PORT = 50007

FS = 500                 # 取樣率 500 Hz
WINDOW_SAMPLES = FS      # 想要的窗口長度：1 秒 ≈ 500 筆

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # 關掉 Nagle，降低小封包延遲
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        s.bind((HOST, PORT))
        s.listen(1)
        print(f"[Server] Listening on {HOST}:{PORT} ...")

        conn, addr = s.accept()
        print(f"[Server] Connected by {addr}")
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        buffer = ""
        SEP = "\n===END===\n"
        block_id = 0

        # 目前為止「BIOPAC 累積資料」的行數
        total_line_count = 0

        with conn:
            while True:
                data = conn.recv(4096)
                if not data:
                    print("[Server] Connection closed")
                    break

                buffer += data.decode("utf-8", errors="ignore")

                while SEP in buffer:
                    block, buffer = buffer.split(SEP, 1)
                    block = block.strip()
                    if not block:
                        continue

                    block_id += 1

                    # 這一包是 BIOPAC 「從 0 秒到現在的全部資料」
                    all_lines = [ln for ln in block.splitlines() if ln.strip()]

                    # 如果行數突然變少，代表 BIOPAC 重新開始錄影，重置計數
                    if total_line_count > len(all_lines):
                        total_line_count = 0

                    # 這一包裡「從上次之後新長出來」的那一段
                    new_lines = all_lines[total_line_count:]

                    # 更新累積行數
                    total_line_count = len(all_lines)

                    if not new_lines:
                        print(f"[Server] Block {block_id}: 沒有新資料")
                        continue

                    # 只保留「最新 1 秒」的資料
                    if len(new_lines) > WINDOW_SAMPLES:
                        new_lines = new_lines[-WINDOW_SAMPLES:]

                    print(
                        f"\n[Server] Block {block_id}: "
                        f"累積行數={len(all_lines)}，"
                        f"這次新樣本={len(new_lines)} 行（顯示前 5 行）"
                    )

                    for ln in new_lines[:5]:
                        print("  ", ln)
                    if len(new_lines) > 5:
                        print("  ...")

                    # 之後要做前處理 / 特徵 / 模型，就在這裡用 new_lines：
                    # process_eeg_1sec_window(new_lines)

if __name__ == "__main__":
    main()
