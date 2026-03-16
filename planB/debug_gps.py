import cv2
import numpy as np
import mss

class MinimapDebugger:
    def __init__(self):
        # ==========================================
        # ⚠️ 請在這裡填入你目前使用的 GPS 參數
        # ==========================================
        self.region = (10, 160, 270, 250)  # (X, Y, W, H)
        # self.region = (10, 170, 310, 190)
        self.lower_yellow = np.array([27, 200, 200])
        self.upper_yellow = np.array([30, 255, 255])
        
        self.sct = mss.mss()

    def run(self):
        print("📡 GPS 即時監控雷達已啟動！")
        print("💡 觀察重點：")
        print("  1. 右側的黑白遮罩中，是否只有『一個』穩定的小白點？")
        print("  2. 當你跳躍或移動時，白點是否會閃爍、消失或分裂？")
        print("  3. 綠色框框有沒有不小心抓到地圖上的其他黃色物件？")
        print("按 [Q] 鍵退出程式。\n")

        x, y, w, h = self.region

        while True:
            # 1. 擷取畫面
            sct_img = self.sct.grab({"top": 22, "left": 0, "width": 2560, "height": 1392})
            frame = np.array(sct_img)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

            # 2. 裁切小地圖
            minimap = frame[y:y+h, x:x+w]
            
            # 3. 轉換色彩並產生遮罩
            hsv = cv2.cvtColor(minimap, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, self.lower_yellow, self.upper_yellow)

            # 4. 尋找輪廓
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            display_img = minimap.copy()
            found_player = False

            for cnt in contours:
                bx, by, bw, bh = cv2.boundingRect(cnt)
                
                # 這是我們目前的過濾條件：寬高都小於 20 的物件
                if 10 < bw < 20 and 10 < bh < 20:
                    cX = bx + (bw // 2)
                    cY = by + (bh // 2)
                    
                    # 在原圖上畫出綠色邊界框與紅色中心點
                    cv2.rectangle(display_img, (bx, by), (bx+bw, by+bh), (0, 255, 0), 1)
                    cv2.circle(display_img, (cX, cY), 2, (0, 0, 255), -1)
                    
                    print(f"\r📍 即時座標: X={cX:3d}, Y={cY:3d} | 點大小: {bw}x{bh}  ", end="")
                    found_player = True
                    break # 找到一個就中斷

            if not found_player:
                print("\r⚠️ 丟失玩家訊號！ (可能被遮蔽或參數太嚴)         ", end="")

            # 5. 影像並排與放大顯示 (為了讓你肉眼好觀察)
            # 將單通道的 mask 轉為三通道，才能跟原圖合併
            mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR) 
            combined = np.hstack((display_img, mask_bgr))
            
            # 放大 2.5 倍顯示
            scale = 2.5
            combined_resized = cv2.resize(combined, (int(w * 2 * scale), int(h * scale)), interpolation=cv2.INTER_NEAREST)

            cv2.imshow("GPS Radar (Left: Vision, Right: Mask)", combined_resized)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        cv2.destroyAllWindows()

if __name__ == "__main__":
    debugger = MinimapDebugger()
    debugger.run()