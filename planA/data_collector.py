import time
import cv2
import mss
import keyboard
import numpy as np
import os
import pandas as pd
from datetime import datetime

# 設定存檔路徑
DATA_DIR = "training_data"
IMG_DIR = os.path.join(DATA_DIR, "images")
LOG_FILE = os.path.join(DATA_DIR, "data_log.csv")

if not os.path.exists(IMG_DIR):
    os.makedirs(IMG_DIR)

# 設定截圖區域 (請根據你的遊戲視窗調整)
# 如果是全螢幕，可以使用 mss().monitors[1]
SCREEN_REGION = {"top": 22, "left": 0, "width": 2560, "height": 1370} 

# 定義要監聽的按鍵 (不包含 QWER，那些用規則寫)
KEYS_TO_LOG = ['up', 'down', 'left', 'right', 'space', 'f', 's', 'a', 'g']

def get_keys_status():
    """回傳目前按鍵狀態的列表，1表示按下，0表示沒按"""
    return [1 if keyboard.is_pressed(k) else 0 for k in KEYS_TO_LOG]

def main():
    print("=== 資料蒐集器啟動 ===")
    print(f"監聽按鍵: {KEYS_TO_LOG}")
    print("按 'P' 鍵開始/暫停蒐集，按 'ESC' 結束程式")
    
    is_recording = False
    data_records = []
    sct = mss.mss()
    
    frame_count = 0
    last_time = time.time()

    while True:
        # 控制邏輯
        if keyboard.is_pressed('esc'):
            print("正在儲存並退出...")
            break
        if keyboard.is_pressed('p'):
            is_recording = not is_recording
            print(f"錄製狀態: {'[ON]' if is_recording else '[OFF]'}")
            time.sleep(0.3) # 防止連點

        if is_recording:
            # 1. 截圖
            img = np.array(sct.grab(SCREEN_REGION))
            # 去除 Alpha 通道 (BGRA -> BGR) 並縮小圖片以節省空間
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            # 建議 Resize，例如 224x224 或 320x240，這對訓練速度影響很大
            img_resized = cv2.resize(img, (320, 180)) 
            
            # 2. 取得按鍵狀態
            keys_status = get_keys_status()
            
            # 3. 生成檔名與紀錄
            timestamp = int(time.time() * 1000)
            filename = f"{timestamp}.jpg"
            cv2.imwrite(os.path.join(IMG_DIR, filename), img_resized)
            
            # 紀錄一筆資料 [filename, up, down, left, ...]
            record = [filename] + keys_status
            data_records.append(record)
            
            frame_count += 1
            if frame_count % 100 == 0:
                print(f"已蒐集 {frame_count} 張樣本...")
            
            # 控制採樣率 (例如每秒 10-15 張即可，不需要 60 張)
            time.sleep(0.1) 

    # 結束後儲存 CSV
    if data_records:
        columns = ["image_file"] + KEYS_TO_LOG
        df = pd.DataFrame(data_records, columns=columns)
        
        # 如果檔案已存在，附加在後面；否則建立新檔
        if os.path.exists(LOG_FILE):
            df.to_csv(LOG_FILE, mode='a', header=False, index=False)
        else:
            df.to_csv(LOG_FILE, mode='w', header=True, index=False)
            
        print(f"成功儲存 {len(data_records)} 筆資料至 {LOG_FILE}")
    
    print("程式結束")

if __name__ == "__main__":
    main()
