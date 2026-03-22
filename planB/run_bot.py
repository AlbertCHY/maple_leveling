import mss
import os
import cv2
import numpy as np
import time
from ultralytics import YOLO

SCREEN_REGION = {"top": 22, "left": 0, "width": 2560, "height": 1370}

class GamePerception:
    def __init__(self, model_path="runs/detect/train6/weights/best.pt"):
        print("載入 YOLO 大腦中...")
        # 載入訓練好的最佳權重
        self.model = YOLO(model_path)
        self.sct = mss.mss()
        # 預設抓取主螢幕，如果你的遊戲在特定位置，這裡可以改成對應的 bounding box
        self.region = SCREEN_REGION

    def get_vision(self):
        """擷取畫面並進行 YOLO 即時推論"""
        # 1. 擷取畫面
        sct_img = self.sct.grab(self.region)
        
        # 2. 將 mss 的 BGRA 格式轉成 OpenCV 可以吃、YOLO 喜歡的 BGR 格式
        frame = np.array(sct_img)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

        # 3. 進行預測 (conf=0.5 代表信心度大於 50% 才算數，過濾雜訊)
        # verbose=False 可以關閉終端機狂刷 log
        results = self.model.predict(source=frame, conf=0.4, device=0, verbose=False)

        # 4. 解析座標
        perception_data = {
            "player": None,
            "monsters": []
        }

        class_names = self.model.names

        for box in results[0].boxes:
            # .item() 可以安全地將 PyTorch Tensor 轉成 Python 原生整數
            cls_id = int(box.cls[0].item())
            name = class_names[cls_id] # 動態取得名稱：'player' 或 'monster'
            
            # .tolist() 確保 Tensor 轉換為原生 list，避免 map(int) 報錯
            x_center, y_center, w, h = map(int, box.xywh[0].tolist())
            
            if name == 'player':
                perception_data["player"] = (x_center, y_center)
            elif name == 'blackboar':
                perception_data["monsters"].append((x_center, y_center))

        return frame, perception_data, results[0]

# --- 測試你的即時感知系統 ---
if __name__ == "__main__":
    vision_system = GamePerception()
        
    # 建立除錯資料夾
    # os.makedirs("debug_vision", exist_ok=True)
    
    # 1. 強制初始化一個可縮放的視窗 (避免亂彈新視窗)
    window_name = "YOLO Debug Vision"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    # 如果你有雙螢幕，可以把這個視窗移到另一個螢幕，不要擋住遊戲
    cv2.resizeWindow(window_name, 800, 600) 

    print("👀 感知系統啟動！")
    print("操作說明：")
    print(" - 點擊 Debug 視窗並按 [S] 鍵：儲存當下畫面進行分析")
    print(" - 點擊 Debug 視窗並按 [Q] 鍵：退出程式")

    try:
        while True:
            start_time = time.time()
            
            # 取得當下畫面的情報
            frame, data, raw_result = vision_system.get_vision()
            
            # 計算 FPS
            fps = 1.0 / (time.time() - start_time)
            
            print(f"\rFPS: {fps:.1f} | 玩家座標: {data['player']} | 看到 {len(data['monsters'])} 隻怪物 \033[K", end="")
            
            # 取得 YOLO 畫好框的影像矩陣 (包含標籤與信心度)
            annotated_frame = raw_result.plot()
            
            # 顯示在單一視窗中
            cv2.imshow(window_name, annotated_frame)
            
            # 讀取鍵盤輸入 (1ms 延遲，確保畫面能順利更新)
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                break
            # elif key == ord('s'):
            #     # 2. 熱鍵快照功能：存檔讓你慢慢看
            #     filename = f"debug_vision/snapshot_{int(time.time()*1000)}.jpg"
            #     cv2.imwrite(filename, annotated_frame)
            #     print(f"📸 已儲存異常畫面快照至：{filename}")
            
    except KeyboardInterrupt:
        print("系統關閉。")
        cv2.destroyAllWindows()