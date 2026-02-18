import cv2
import numpy as np

import os
print(os.path.exists('test.png'))
def nothing(x):
    pass

# 1. 讀取你剛剛截下來的「完整遊戲畫面」
image = cv2.imread('test.png')

# 2. 填入你剛剛量出來的 region (X, Y, W, H)
X, Y, W, H = 10, 165, 270, 255 # <--- 請替換成你的真實數據
minimap = image[Y:Y+H, X:X+W]
hsv = cv2.cvtColor(minimap, cv2.COLOR_BGR2HSV)

# 建立調參視窗
cv2.namedWindow('HSV Calibrator', cv2.WINDOW_NORMAL)
cv2.resizeWindow('HSV Calibrator', 400, 300)

# 建立滑桿 (楓之谷玩家的黃點通常 H 在 20~40 之間)
cv2.createTrackbar('H Min', 'HSV Calibrator', 20, 179, nothing)
cv2.createTrackbar('S Min', 'HSV Calibrator', 100, 255, nothing)
cv2.createTrackbar('V Min', 'HSV Calibrator', 100, 255, nothing)
cv2.createTrackbar('H Max', 'HSV Calibrator', 40, 179, nothing)
cv2.createTrackbar('S Max', 'HSV Calibrator', 255, 255, nothing)
cv2.createTrackbar('V Max', 'HSV Calibrator', 255, 255, nothing)

print("🎛️ 請調整滑桿，直到右邊的視窗(Mask)「只剩下代表玩家的白點」，其餘背景都是全黑。")
print("按 [ESC] 鍵退出並印出最終參數。")

while True:
    h_min = cv2.getTrackbarPos('H Min', 'HSV Calibrator')
    s_min = cv2.getTrackbarPos('S Min', 'HSV Calibrator')
    v_min = cv2.getTrackbarPos('V Min', 'HSV Calibrator')
    h_max = cv2.getTrackbarPos('H Max', 'HSV Calibrator')
    s_max = cv2.getTrackbarPos('S Max', 'HSV Calibrator')
    v_max = cv2.getTrackbarPos('V Max', 'HSV Calibrator')

    lower = np.array([h_min, s_min, v_min])
    upper = np.array([h_max, s_max, v_max])

    # 產生遮罩
    mask = cv2.inRange(hsv, lower, upper)
    
    # 顯示原圖與遮罩
    cv2.imshow('Original Minimap', minimap)
    cv2.imshow('Mask (White=Detected)', mask)

    if cv2.waitKey(1) & 0xFF == 27: # 27 是 ESC 鍵
        print("\n✅ 調參完成！請將以下參數填入 MinimapParser：")
        print(f"self.lower_yellow = np.array([{h_min}, {s_min}, {v_min}])")
        print(f"self.upper_yellow = np.array([{h_max}, {s_max}, {v_max}])")
        break

cv2.destroyAllWindows()