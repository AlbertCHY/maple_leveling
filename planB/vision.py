import mss
from ultralytics import YOLO
import cv2

class GamePerception:
    def __init__(self, model_path, conf):
        print("載入 YOLO 模型中...")
        self.model = YOLO(model_path)
        self.sct = mss.mss()
        self.conf = conf            # 信心度閾值 (0.5 代表 50%)

    @classmethod
    def from_config(cls, config):
        return cls(model_path=config["model"]["path"], conf=config["model"]["conf"])

    def get_vision(self, frame):
        """進行 YOLO 即時推論"""
        # 將 mss 的 BGRA 格式轉成 OpenCV 可以吃、YOLO 喜歡的 BGR 格式
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

        # 進行預測
        # verbose=False 可以關閉終端機大量log
        results = self.model.predict(source=frame, conf=self.conf, device=0, verbose=False)

        boxes_xywh = results[0].boxes.xywh.cpu().numpy() # 所有的座標 (N, 4)
        label_ID = results[0].boxes.cls.cpu().numpy().astype(int)  # 所有的類別 ID (N,)
        label_names = self.model.names # 根據訓練時的手動標籤取得名稱

        perception_data = {
            "player": None,
            "monsters": []
        }

        for xywh, id in zip(boxes_xywh, label_ID):
            name = label_names[id] # 根據ID取得對應名稱
            tuple_xywh = tuple(xywh.astype(int))
            
            # 根據名稱分類資料
            if name == 'Player':
                perception_data["player"] = tuple_xywh
            elif name == 'Mobs':
                perception_data["monsters"].append(tuple_xywh)

        return frame, perception_data, results[0]