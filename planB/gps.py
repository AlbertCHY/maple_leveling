import cv2
import numpy as np

class MinimapParser:
    def __init__(self, region):
        """
        初始化 GPS 小地圖系統
        :param region: 小地圖在螢幕上的座標與大小 (X, Y, W, H)
        """
        self.region = region
        
        # --- ⚠️ 請把剛剛調參神器跑出來的結果貼到這裡 ---
        self.lower_yellow = np.array([20, 100, 100])
        self.upper_yellow = np.array([40, 255, 255])

    def parse(self, frame):
        """
        解析遊戲畫面，回傳玩家在「小地圖上的絕對座標」
        :param frame: mss 擷取並轉換為 BGR 的完整遊戲畫面 (numpy array)
        :return: dict, 例如 {"player": (x, y)}。如果沒找到則回傳 None。
        """
        x, y, w, h = self.region
        
        # 1. 裁切小地圖區域
        minimap_img = frame[y:y+h, x:x+w]
        
        # 2. 轉換色彩空間並產生遮罩
        hsv = cv2.cvtColor(minimap_img, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower_yellow, self.upper_yellow)
        
        # 3. 尋找輪廓 (玩家黃點)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        player_pos = None
        for cnt in contours:
            # 放棄使用容易出錯的 area 和 moments，改用 Bounding Box (邊界框)
            bx, by, bw, bh = cv2.boundingRect(cnt)
            
            # 條件放寬：只要寬高大於 0 且小於 20 像素，我們就認定它是黃點
            if bw > 0 and bh > 0 and bw < 20 and bh < 20:
                # 計算中心點
                cX = bx + (bw // 2)
                cY = by + (bh // 2)
                player_pos = (cX, cY)
                break # 找到唯一的玩家黃點，提早結束迴圈
                    
        return {
            "player": player_pos
        }

# --- 單元測試 ---
# if __name__ == "__main__":
#     # 測試你的 GPS 模組是否正常運作
#     parser = MinimapParser(region=(10, 165, 270, 255))
#     test_image = cv2.imread("test.png")
#     result = parser.parse(test_image)
#     print(f"玩家 GPS 座標: {result['player']}")