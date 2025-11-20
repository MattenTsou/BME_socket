# BME_socket

**BIOPAC PC（實驗室電腦）**：跑 Biopac Student Lab（BSL），透過 Python 自動按快捷鍵擷取波形資料，並經由 TCP socket 傳送 EEG raw data。
**Own PC（自己的電腦）**：開 socket server 接收 EEG raw data，切成 **1 秒（500 筆）** 的資料區段，之後可接前處理 / 特徵 / 模型 / 遊戲控制。

---

## 檔案結構

在兩台電腦分別放置以下檔案：

- **Own PC（接收端 / 分析端）**
  - `eeg_server.py`：socket server，接收 BIOPAC PC 傳來的 EEG raw data，並切出「最新 1 秒」資料。

- **BIOPAC PC（送出端 / 量測端）**
  - `biopac_client.py`：socket client，控制 Biopac Student Lab：
    - 程式啟動後自動切到 Biopac 視窗且按下開始測波形（Ctrl+Space）
    - 之後週期性執行：選取波形 → 轉成文字 → 剪下 → 從剪貼簿讀 raw data → 傳給 Own PC

---

## 環境需求

### 兩台電腦共同條件

- 同一個區網（同一個 Wi-Fi 或同一個有線網路）
- 有安裝 Python 3（建議 3.8 以上）


### BIOPAC (實驗室左邊電腦已有)
pip install pyautogui pyperclip


**##執行步驟**

Step 0：確認網路與 IP，修改biopac_client.py的IP
Step 1：開啟 BIOPAC
Step 2：在 Own PC 啟動 eeg_server.py
Step 3：在 BIOPAC PC 啟動 biopac_client.py




