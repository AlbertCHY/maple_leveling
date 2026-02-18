import mss
from ultralytics import YOLO
import cv2

SCREEN_REGION = {"top": 22, "left": 0, "width": 2560, "height": 1392}

class GamePerception:
    def __init__(self, model_path="runs/detect/train/weights/best.pt"):
        print("載入 YOLO 大腦中...")
        # 載入你剛剛訓練好的最強權重
        self.model = YOLO(model_path)
        self.sct = mss.mss()
        # 預設抓取主螢幕，如果你的遊戲在特定位置，這裡可以改成對應的 bounding box
        self.region = SCREEN_REGION

    def get_vision(self, frame):
        """進行 YOLO 即時推論"""
        # 2. 將 mss 的 BGRA 格式轉成 OpenCV 可以吃、YOLO 喜歡的 BGR 格式
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

        # 3. 進行預測 (conf=0.5 代表信心度大於 50% 才算數，過濾雜訊)
        # verbose=False 可以關閉終端機狂刷 log
        results = self.model.predict(source=frame, conf=0.5, device=0, verbose=False)

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
            
            if name == 'Player':
                perception_data["player"] = (x_center, y_center, w, h)
            elif name == 'Mobs':
                perception_data["monsters"].append((x_center, y_center, w, h))

        return frame, perception_data, results[0]