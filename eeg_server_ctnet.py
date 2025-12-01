# eeg_server_ctnet.py  (Own PC：使用 CTNet Ensemble 做即時分類 + 眨眼偵測)
import socket
import numpy as np

from inference import CTNetEnsembleInference  # 從你們 repo 來

HOST = '0.0.0.0'
PORT = 50007

FS = 500                   # Biopac 取樣率：500 Hz
WIN_SAMPLES = 1000         # CTNet window（約 2 秒）
STRIDE_SAMPLES = 300       # 每隔約 0.6 秒出一次結果

# === 眨眼偵測參數（需要依你的 raw 波形調整） ===
BLINK_AMP_THRESHOLD = 150.0          # 振幅門檻：|EEG| 超過這個就視為「很大」
BLINK_MIN_SAMPLES = int(0.02 * FS)   # 至少 20 ms 以上都很大才當眨眼（約 10 點）

# CTNet 的兩類（放鬆 / 專注），眨眼我們額外用 rule 判定
CLASS_NAMES = ['放鬆', '專注']


def detect_blink_from_block(values,
                            amp_threshold=BLINK_AMP_THRESHOLD,
                            min_samples=BLINK_MIN_SAMPLES):
    """
    用 raw data 的振幅來判斷這一批 samples 裡有沒有眨眼。
    values: list[float] 或 1D np.array
    Rule: 若 |x| > amp_threshold 的樣本數 >= min_samples，就視為眨眼。
    """
    arr = np.asarray(values, dtype=np.float32)
    if arr.size == 0:
        return False

    over = np.abs(arr) > float(amp_threshold)
    n_over = int(np.count_nonzero(over))

    return n_over >= int(min_samples)


class OnlineCTNet:
    """
    用 CTNetEnsembleInference 做「線上」推論的小包裝。
    每次收到新的 samples，就更新 buffer，
    滿足 stride 才用最後 WIN_SAMPLES 筆做一次分類。
    """

    def __init__(self):
        # ⚠️ 這裡的參數完全照 inference_example.py
        model_dir = "Loso_C_heads_2_depth_8_0"
        self.inferencer = CTNetEnsembleInference(
            model_dir=model_dir,
            dataset_type='C',
            heads=2, emb_size=16, depth=8,
            eeg1_f1=8, eeg1_kernel_size=64, eeg1_D=2,
            eeg1_pooling_size1=8, eeg1_pooling_size2=8,
            eeg1_dropout_rate=0.25, flatten_eeg1=240
        )

        # 內部 buffer：存 1D 浮點數列（累積所有 sample）
        self.buffer = []

        # 上一次做分類時 buffer 的長度（用來實現 stride）
        self.last_pred_pos = 0

    def append_and_maybe_predict(self, new_values):
        """
        new_values: list[float]，這次從 Biopac 來的新 sample（大約 1 秒 500 筆）
        回傳： (label_str, prob_array) 或 (None, None) 如果目前樣本還不夠
        """

        # 1. 加入 buffer
        self.buffer.extend(new_values)

        # 2. 若樣本還不夠做第一個 1000-window，就先不算
        if len(self.buffer) < WIN_SAMPLES:
            return None, None

        # 3. 控制 stride：若距離上一次分類不到 STRIDE_SAMPLES，就暫時不算
        if len(self.buffer) - self.last_pred_pos < STRIDE_SAMPLES:
            return None, None

        # 4. 取「最後 WIN_SAMPLES 筆」當作一個 window
        data = np.array(self.buffer[-WIN_SAMPLES:], dtype=np.float32)

        # 5. 用 CTNetEnsembleInference 來跑這個 window
        def gen():
            yield data

        last_result = None
        for result in self.inferencer.predict_realtime(
            gen(),
            window_size=len(data),
            stride=len(data),
            smoothing_window=3,   # 輕微平滑，避免太抖動
            callback=None
        ):
            last_result = result

        if last_result is None:
            return None, None

        pred = int(last_result['prediction'])
        prob = np.array(last_result['probability'], dtype=np.float32)

        # 更新 last_pred_pos：這次已經用到 buffer 的最後一點
        self.last_pred_pos = len(self.buffer)

        # 轉成文字 label（只有放鬆 / 專注兩種）
        if 0 <= pred < len(CLASS_NAMES):
            label = CLASS_NAMES[pred]
        else:
            label = f"cls_{pred}"

        return label, prob


def parse_lines_to_values(lines):
    """
    把 new_lines（每行一筆 raw text）轉成 float list。
    假設每行形式類似：
        "123.45"
      或 "0.123  0.456  0.789"（即最後一欄是我們要的值）
    有非數字會自動略過。
    """
    values = []
    for ln in lines:
        parts = ln.strip().split()
        if not parts:
            continue
        try:
            v = float(parts[-1])  # 取最後一欄
            values.append(v)
        except ValueError:
            continue
    return values


def main():
    classifier = OnlineCTNet()

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

        # 儲存「累積文字行數」，辨識每包是不是重新開始
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

                    # 這包 BIOPAC 給你的所有行（從 0 秒到現在）
                    all_lines = [ln for ln in block.splitlines() if ln.strip()]

                    # 若行數突然變少，代表 BIOPAC 重新開始錄影，把計數歸零
                    if total_line_count > len(all_lines):
                        total_line_count = 0

                    # 取「這次新增的那一段行」
                    new_lines = all_lines[total_line_count:]
                    total_line_count = len(all_lines)

                    if not new_lines:
                        print(f"[Server] Block {block_id}: 沒有新資料")
                        continue

                    # 轉成 float list（每個元素是一個 sample）
                    new_values = parse_lines_to_values(new_lines)
                    print(f"[Server] Block {block_id}: 新增 {len(new_values)} 筆樣本")

                    if not new_values:
                        continue

                    # ① 先做「眨眼偵測」（用 raw data）
                    blink = detect_blink_from_block(new_values)

                    # ② 丟進 CTNet 線上分類器（放鬆 / 專注）
                    label, prob = classifier.append_and_maybe_predict(new_values)

                    # 還沒累積到可以分類就先不印
                    if label is None:
                        continue

                    # ③ 整合成「狀態」，如果偵測到眨眼就覆蓋狀態
                    if blink:
                        state_label = "眨眼"
                        print(
                            f"  → 偵測狀態 = {state_label}（raw spike），"
                            f"CTNet prob(放鬆,專注) = {prob}"
                        )
                    else:
                        state_label = label
                        print(
                            f"  → 預測狀態 = {state_label}, "
                            f"prob(放鬆,專注) = {prob}"
                        )

                    # TODO: 在這裡接遊戲控制（鍵盤 / socket）
                    # if state_label == '放鬆': ...
                    # elif state_label == '專注': ...
                    # elif state_label == '眨眼': ...


if __name__ == "__main__":
    main()
