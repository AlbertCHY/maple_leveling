# Maple Leveling — MapleStory 自動練等 AI 實驗專案

一個探索遊戲自動化與電腦視覺應用的實驗性專案，實作了兩種截然不同的架構來解決 2D 橫向卷軸遊戲（MapleStory / 骨龍區）的自動巡邏、尋路、打怪與輔助狀態管理：

- **Plan A（端到端模仿學習 / End-to-End Imitation Learning）**：直接截取遊戲畫面，使用 `EfficientNet-B0` 進行多標籤分類，預測當下應按下的鍵盤組合。
- **Plan B（模組化感知 + 導航圖 + 行為樹 / Modular CV + NavGraph + Behavior Tree）**：結合 `YOLOv8` 物件偵測、小地圖 HSV 玩家定位（GPS）、BFS 圖論尋路與非阻塞式行為樹（Behavior Tree）進行精準可控的自動化決策（目前主要開發與使用架構）。

> ⚠️ **免責聲明（Disclaimer）**  
> 本專案僅供電腦視覺、行為樹架構與強化／模仿學習等技術研究與個人學習交流之用，請勿用於違反遊戲服務條款之行為，使用者須自行承擔相關風險。

---

## 目錄

- [專案架構與兩種方案比較](#專案架構與兩種方案比較)
- [開發演進與實驗紀錄](#開發演進與實驗紀錄)
- [目錄結構](#目錄結構)
- [Plan B 核心系統設計](#plan-b-核心系統設計)
- [Plan A 端到端模仿學習](#plan-a-端到端模仿學習)
- [環境需求與安裝](#環境需求與安裝)
- [使用指南（Plan B）](#使用指南plan-b)
- [使用指南（Plan A）](#使用指南plan-a)
- [輔助與除錯工具](#輔助與除錯工具)
- [待改進項目](#待改進項目)

---

## 專案架構與兩種方案比較

| 比較項目 | Plan A（端到端模仿學習） | Plan B（YOLO + GPS + 行為樹） |
| --- | --- | --- |
| **核心技術** | `EfficientNet-B0` 多標籤分類（Behavior Cloning） | `YOLOv8m` 偵測 + OpenCV HSV 小地圖定位 + BFS 尋路 + Behavior Tree |
| **決策可解釋性** | 低（黑盒影像到按鍵映射） | 高（明確的平台座標、路徑規劃與節點狀態） |
| **容錯與恢復能力** | 易受畫面干擾、容易原地卡住或下跳失誤 | 具備偏離路線偵測與自動重新規劃路徑（Re-routing） |
| **防呆與擬人化** | 僅透過 `ActionThrottler` 限制攻擊冷卻 | 支援常態分佈延遲、動態邊界擾動、非阻塞 Buff 排程 |
| **資料需求** | 需錄製大量「畫面 + 按鍵」操作紀錄 | 需標註玩家與怪物 YOLO 資料集，並測繪地圖 JSON |

---

## 開發演進與實驗紀錄

本專案從「端到端行為模仿」起步，歷經多次實測與架構重構後演化為目前的「模組化感知 + 行為樹 + 動態導航圖」架構。以下是各階段的設計決策、問題分析與實測數據：

### 階段一：Plan A — 行為模仿與多標籤圖像分類

- **模型選型**：考量時間序列模型（如 RNN/CNN+LSTM）訓練難度高且不易收斂，改採單幀 CNN（`EfficientNet-B0`）多標籤分類，以 CSV 紀錄每張截圖對應的按鍵狀態。
- **資料採集與前處理**：
  - 累積約 **10,000 張**遊戲截圖，保持原始長寬比縮小以配合 PyTorch 輸入。
  - 針對「下跳、爬繩、低頻率技能」等稀有動作進行額外補錄。
  - 依 `pos_weight` 公式搭配人工風險微調設定各按鍵權重，應對類別不平衡。
- **實驗結果與瓶頸**：
  - **v1 訓練**：`Validation Loss ≈ 0.55`。由於主攻擊技能在樣本中佔比極高，加上模型輸出按鍵頻率過高，角色容易卡在原地連續攻擊，因此加入 `ActionThrottler` 強制攻擊後硬直與移動窗口。
  - **v2 清洗重錄**：重新錄製資料並剔除人工遊玩時的不規律跳躍與雜亂路線，`Validation Loss` 降至 **≈ 0.45**，但實戰仍出現「有怪不打、無怪空揮、動作雜亂、按鍵節奏不自然」等問題，練等效率低，最終決定轉向 **Plan B**。

### 階段二：Plan B — YOLOv8 物件偵測 + 有限狀態機（FSM）

- **資料標註策略調整**：
  - 改用原始解析度截圖並以 **Roboflow** 手動標註；實測多類別精細標註耗時且在少樣本下效果不佳，因此精簡為僅標註「玩家（`Player`）」與「目標怪物（`bone_dragon`）」以大幅提升標註效率。
  - 搭配變色（Color Jitter）與遮擋（Occlusion）資料增強並調整尺寸配合 YOLOv8。
  - 僅使用約 **200 張**原始截圖以 `YOLOv8m` 進行遷移學習（Transfer Learning），即達成 **`mAP50-95 ≈ 0.6`**。
- **系統雛形（`main_old.py`）**：
  - 以有限狀態機（FSM）串聯 `vision.py`、`gps.py`、`combat.py`、`buff.py` 與 `controller.py`（高斯分佈按壓延遲）。
  - 主迴圈依序檢查 Buff 倒數、判斷是否偏離預定路線，並於固定巡邏狀態間切換；若掉落至意外樓層則進入救援狀態移動至指定繩索爬回原路線。
  - **初版實測**：打完一輪氣場約需 **2.5 小時（150 分鐘）**，清怪覆蓋率與移動效率仍有優化空間。

### 階段三：行為樹重構、動態尋路與模型泛化補強

- **路線與動作優化**：調整繞圖路線以確保清怪數量，並設計跳躍攻擊機制來模擬人類操作並提高推進效率。
- **非阻塞式行為樹重構（`behavior_tree.py` / `bt_nodes.py`）**：
  - 針對 FSM 難以擴充與 `time.sleep()` 阻塞主迴圈的問題，重構為行為樹架構。
  - 將爬繩、攻擊硬直與 Buff 施放後的等待全面改寫為**非阻塞狀態機（Non-blocking）**，確保每幀都能持續進行視覺感知與座標監控。
- **效率實測基準（打完氣場耗時）**：
  - **人工手動練等**：約 **90 分鐘**
  - **Plan B 穩定版自動練等**：約 **150 分鐘**
- **動態圖論尋路（`navigator.py` / `DynamicPatrolNode`）**：將寫死的跨平台轉移序列改為以地圖 JSON + BFS 動態計算「當前平台 → 目標平台」的最短路徑與動作，實現更強的容錯與偏離恢復能力。
- **外觀變動對偵測的影響**：實測發現遊戲角色「更換裝備外觀」後，原本 YOLO 模型辨識率會明顯下降；透過將訓練資料量**擴增一倍**重新訓練後，恢復穩定辨識效果。

---

## 目錄結構

```text
maple_leveling/
├── .gitignore
├── planA/                          # 方案 A：端到端模仿學習
│   ├── data_collector.py           # 遊戲畫面與鍵盤操作資料蒐集器
│   ├── sanity_check.py             # 資料集影像與標籤對齊抽樣檢查
│   ├── train.py                    # EfficientNet-B0 多標籤分類訓練腳本
│   └── main.py                     # 即時推論與按鍵執行主程式
└── planB/                          # 方案 B：模組化感知與行為樹（主要架構）
    ├── config/
    │   └── config.toml             # 螢幕範圍、YOLO、小地圖 HSV、Buff、戰鬥與地圖參數
    ├── main.py                     # MapleBot 行為樹版主程式
    ├── main_old.py                 # 舊版有限狀態機 (FSM) 實作（保留參考）
    ├── vision.py                   # YOLOv8 即時玩家與怪物座標偵測 (GamePerception)
    ├── gps.py                      # 小地圖黃點 HSV 過濾定位 (MinimapParser)
    ├── navigator.py                # 地圖圖論載入與 BFS 最短路徑尋路 (Navigator)
    ├── behavior_tree.py            # 行為樹核心節點：Selector / Sequence / MemorySequence
    ├── bt_nodes.py                 # 行為節點：Buff、動態巡邏、清怪、下跳、水平跳、爬繩
    ├── combat.py                   # 戰鬥目標過濾與攻擊／跳攻距離判定 (CombatTargeting)
    ├── controller.py               # 常態分佈擬人化鍵盤控制器 (HumanizedController)
    ├── buff.py                     # 多組週期性 Buff 排程管理 (BuffManager)
    ├── data_collector.py           # YOLO 訓練截圖蒐集工具
    ├── train.py                    # YOLOv8m 模型訓練腳本
    ├── map_data_collector.py       # 互動式地圖平台與連接點測繪工具
    ├── hsv_adjuster.py             # 小地圖黃點 HSV 閾值即時調整視窗
    ├── debug_gps.py                # 小地圖定位與黑白遮罩即時除錯監控
    ├── debug_keyboard.py           # Tkinter 懸浮鍵盤按壓狀態視覺化工具
    └── run_bot.py                  # YOLO 偵測結果與 FPS 即時預覽視窗
```

> **注意**：訓練資料集（`training_data/`、`yolo_dataset/`、`roboflow_dataset/`）、模型權重檔（`*.pt`、`*.pth`）以及由測繪工具產生的地圖檔（`planB/config/map_bonedragon.json`）未包含在版控中，請依照下方指南自行蒐集／建立。

---

## Plan B 核心系統設計

`planB/main.py` 中的 `MapleBot` 在每個 tick（約 50 Hz）執行「全局感知 → 行為樹決策 → 擬人化輸入」流程：

1. **畫面與視覺感知（`vision.py`）**
   - 透過 `mss` 擷取 `config.toml` 設定的 `[game_screen]` 區域。
   - 使用 `YOLOv8` 模型即時偵測 `Player` 與怪物（預設標籤為 `bone_dragon`）的中心座標與寬高 `(x, y, w, h)`。

2. **小地圖 GPS 定位（`gps.py`）**
   - 裁切 `[mini_map]` 區域並轉換至 HSV 色彩空間。
   - 過濾黃色玩家標記（`lower_yellow` ~ `upper_yellow`），篩選輪廓大小 `10 < bw < 20` 且 `10 < bh < 20`，取得玩家在小地圖上的座標 `(gps_px, gps_py)`。

3. **圖論尋路（`navigator.py`）**
   - 從 `config/map_bonedragon.json` 讀取平台定義（`platforms`：`y`, `x_min`, `x_max`）與平台間轉換動作（`links`：`from`, `to`, `action`, `trigger_x`）。
   - 使用廣度優先搜尋（BFS）計算從當前平台到目標平台的最短動作序列，支援 `JUMP_DOWN`、`CLIMB_ROPE`、`JUMP_LEFT`、`JUMP_RIGHT`。

4. **行為樹決策（`behavior_tree.py` & `bt_nodes.py`）**
   - 根節點為 `Selector([BuffNode, DynamicPatrolNode])`：
     - **`BuffNode`（優先級 1）**：非阻塞狀態機，依 `[buff.5min]`、`[buff.10min]` 等隨機區間（如 270~300 秒）停下腳步並依序施放 Buff。
     - **`DynamicPatrolNode`（優先級 2）**：依序巡邏指定平台清單（如 `["P_TOP", "P_MID_1", "P_MID_2", "P_MID_3"]`）。
       - **偏離路線自動修正**：若偵測到角色掉出預期平台集合（例如誤落底層），立即中斷當前動作並以曼哈頓距離尋找最近的巡邏點，透過 BFS 重新規劃路徑。
       - **`ClearPlatformNode`**：預判下一個目標平台的出口位置，先往遠離出口方向清怪，抵達隨機化的動態邊界後再折返往出口方向清怪，減少無效折返。
       - **`RopeUpNode` / `JumpDownNode` / `JumpToPlatformNode`**：負責移動至 `trigger_x` 並完成跨平台移動，其中 `RopeUpNode` 內建座標停滯計數器（`idle_counter`）與起跳逾時重置機制以防止卡死。

5. **戰鬥判定與擬人化控制（`combat.py` & `controller.py`）**
   - `CombatTargeting` 根據巡邏方向與 `y_diff` 篩選前方同層怪物，計算邊緣距離後區分「原地攻擊（`<= safety_attack_range`）」與「跳躍攻擊（`<= skill_range`）」。
   - `HumanizedController` 使用 `pydirectinput` 模擬硬體層級按鍵，所有按壓與停頓時間皆採常態分佈隨機延遲（`sleep_gaussian`）。

---

## Plan A 端到端模仿學習

`planA/` 採用行為複製（Behavior Cloning）架構：

- **資料蒐集（`planA/data_collector.py`）**：以約 10 Hz 截圖並縮放為 `320x180`，同步記錄 `['up', 'down', 'left', 'right', 'space', 'f', 's', 'a', 'g']` 按鍵狀態至 `training_data/data_log.csv`。
- **模型訓練（`planA/train.py`）**：
  - 使用預訓練 `EfficientNet-B0`（輸入解析度 `256x448`）進行 9 維多標籤分類。
  - 自動依據正負樣本比計算 `BCEWithLogitsLoss(pos_weight=...)` 以應對稀有按鍵（如 `down`、`s`）的不平衡問題，並支援混合精度（AMP）與 Early Stopping。
- **推論執行（`planA/main.py`）**：透過 `win32gui` 截圖並以不同按鍵的獨立信心閾值（`thresholds`）輸出操作，搭配 `ActionThrottler` 強制加入攻擊冷卻移動窗口與 `BuffManager` 定時上 Buff。

---

## 環境需求與安裝

- **作業系統**：Windows（因使用 `pydirectinput`、`keyboard` 及 `win32gui` 等 Windows API）
- **Python 版本**：建議 Python 3.11+（`planB/main.py` 使用標準庫 `tomllib`）
- **硬體建議**：支援 CUDA 的 NVIDIA GPU（如 RTX 系列）以加速 `YOLOv8` / `EfficientNet` 訓練與即時推論

### 安裝依賴套件

```bash
pip install numpy opencv-python mss keyboard ultralytics pydirectinput pynput torch torchvision pillow pandas scikit-learn matplotlib pywin32
```

> 若需使用 GPU 加速，請依本機 CUDA 版本從 [PyTorch 官網](https://pytorch.org/) 安裝對應的 `torch` / `torchvision`。

---

## 使用指南（Plan B）

請在 `planB/` 目錄下執行下列步驟（部分設定與工具採用相對路徑，如 `config/config.toml`）：

```bash
cd planB
```

### 1. 調整設定檔 `config/config.toml`

- `[game_screen]`：設定遊戲視窗的 `top`、`left`、`width`、`height`。
- `[model]`：設定訓練完成的 YOLO 權重路徑（預設 `"model/bone_dragon_2/weights/best.pt"`）與 `conf` 閾值。
- `[mini_map]`：設定小地圖裁切範圍 `region = [x, y, w, h]` 與玩家黃點 HSV 範圍。
- `[buff.*]` 與 `[combat]`：調整角色 Buff 按鍵、施放區間、攻擊距離與技能鍵。

### 2. 校準小地圖 HSV 參數

1. 先截取一張完整遊戲畫面存為 `planB/test.png`。
2. 修改 `hsv_adjuster.py` 中的 `X, Y, W, H` 後執行，調整滑桿使遮罩僅保留玩家白點：
   ```bash
   python hsv_adjuster.py
   ```
3. 使用即時監控工具確認移動與跳躍時白點訊號穩定：
   ```bash
   python debug_gps.py
   ```

### 3. 蒐集資料並訓練 YOLO 模型（若尚未有權重檔）

1. 蒐集遊戲截圖（`F8` 開始/暫停、`ESC` 退出）：
   ```bash
   python data_collector.py
   ```
2. 標註 `Player` 與目標怪物（如 `bone_dragon`）後，修改 `train.py` 中的 `data.yaml` 路徑並開始訓練：
   ```bash
   python train.py
   ```
3. 使用 `run_bot.py` 開啟偵測預覽視窗驗證辨識效果與 FPS（按 `Q` 退出）：
   ```bash
   python run_bot.py
   ```

### 4. 測繪地圖節點與路徑（產生 `config/map_bonedragon.json`）

執行互動式測繪工具，在遊戲中手動走位建立平台與連接動作：

```bash
python map_data_collector.py
```

- `F8`：記錄平台左邊緣起點並輸入平台 ID（例如 `P_TOP`）
- `F9`：記錄平台右邊緣終點並儲存平台範圍
- `F10`：記錄跨平台連接點（輸入起點平台、目標平台與動作 `JUMP_DOWN` / `CLIMB_ROPE` 等）
- `ESC`：儲存至 `config/map_bonedragon.json` 並退出

### 5. 啟動自動化機器人

> 注意：因遊戲視窗與 `keyboard`／`pydirectinput` 可能需要管理員權限，若無法順利送出按鍵，請以**系統管理員身分**執行終端機。

```bash
python main.py
```

- 啟動後有 **3 秒** 時間切換至遊戲視窗。
- `F11`：暫停 / 恢復 AI 運作
- `F12`：停止並退出程式

---

## 使用指南（Plan A）

```bash
cd planA
```

1. **蒐集操作樣本**（按 `P` 開始/暫停、`ESC` 儲存並退出）：
   ```bash
   python data_collector.py
   ```
2. **檢查資料集標籤是否正確**：
   ```bash
   python sanity_check.py
   ```
3. **訓練 EfficientNet-B0 模型**（輸出 `maple_pilot_v1.pth`）：
   ```bash
   python train.py
   ```
4. **啟動自動駕駛**（調整 `main.py` 內的 `GAME_REGION` 後執行，`F11` 暫停/恢復、`F12` 緊急停止）：
   ```bash
   python main.py
   ```

---

## 輔助與除錯工具

- **`planB/debug_keyboard.py`**：使用 `Tkinter` + `pynput` 建立置頂半透明小視窗，即時亮起方向鍵、`Space`、`A/S/D/F/G`，用來確認 `pydirectinput` 的按鍵按下／放開事件是否正確觸發。
- **`planB/debug_gps.py`**：將小地圖原圖與 HSV 二值化遮罩放大 2.5 倍並排顯示，即時印出玩家 `(X, Y)` 座標與 Bounding Box 尺寸，協助排查訊號遺失或雜訊誤判。
- **`planB/run_bot.py`**：獨立的 YOLO 推論預覽視窗，用於檢查模型框選準確度與推論 FPS。

---

## 待改進項目

根據 `planB/config/config.toml` 與目前實作，後續可繼續擴充的方向包含：

- 原地超時防卡死機制（擴展至更多節點而不僅限於 `RopeUpNode`）
- 換平台與清怪時對背後漏怪的鎖定／清怪策略調整
- 更細緻的爬繩失敗判斷與跳躍攻擊觸發時機調優
- 自動補血／補魔（HP/MP 偵測）與測謊／玩家進入地圖偵測機制
