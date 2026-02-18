import mss
import cv2
import numpy as np
import time
import os
import keyboard

CAPTURE_INTERVAL = 0.8  # 每次截圖的間隔時間 (秒)
OUTPUT_DIR = "yolo_dataset"  # 圖片存檔目錄
SCREEN_REGION = {"top": 22, "left": 0, "width": 2560, "height": 1370} # 定義截圖區域
class GameDataCollector:
    def __init__(self, output_dir, capture_interval):
        """
        初始化截圖工具
        :param output_dir: 圖片存檔目錄
        :param capture_interval: 每次截圖的間隔時間 (秒)。
                                 建議設為 1.0 或 0.5 秒，避免截取太多高度重複的廢圖。
        """
        self.output_dir = output_dir
        self.capture_interval = capture_interval
        self.is_recording = False
        
        # 確保輸出目錄存在
        os.makedirs(self.output_dir, exist_ok=True)
        self.sct = mss.mss()

    def toggle_recording(self):
        """切換錄製狀態"""
        self.is_recording = not self.is_recording
        status = "🔴 開始" if self.is_recording else "⏸️ 暫停"
        print(f"\n[系統提示] {status} 連續截圖...")

    def run(self):
        print("=======================================")
        print(" 📸 楓之谷 YOLO 資料蒐集工具已啟動！")
        print(" [F8] 鍵 : 開始/暫停截圖")
        print(" [ESC] 鍵: 退出程式")
        print(f" 儲存路徑: {os.path.abspath(self.output_dir)}")
        print("=======================================")

        # 註冊熱鍵
        keyboard.on_press_key("f8", lambda _: self.toggle_recording())

        img_count = 0
        while True:
            # 監聽退出鍵
            if keyboard.is_pressed('esc'):
                print("\n[系統提示] 退出程式，辛苦了！")
                break

            if self.is_recording:
                # 1. 截圖
                img = np.array(self.sct.grab(SCREEN_REGION))
                # 去除 Alpha 通道 (BGRA -> BGR) 並縮小圖片以節省空間
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

                # 2. 生成檔名與紀錄
                timestamp = int(time.time() * 1000)
                filename = f"{timestamp}.jpg"
                cv2.imwrite(os.path.join(self.output_dir, filename), img)
                
                img_count += 1
                if img_count % 100 == 0:
                    print(f"已蒐集 {img_count} 張樣本...")
                    
                # 等待一段時間再截下一張，避免資料過度相似
                time.sleep(self.capture_interval)
            else:
                # 暫停狀態下稍微 sleep 降低 CPU 負載
                time.sleep(0.1)

if __name__ == "__main__":
    collector = GameDataCollector(output_dir=OUTPUT_DIR, capture_interval=CAPTURE_INTERVAL)
    collector.run()