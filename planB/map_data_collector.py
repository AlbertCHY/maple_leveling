import time
import json
import keyboard
import mss
import numpy as np
import tomllib
from gps import MinimapParser # 引入你原本的 GPS 模組

class MapMapper:
    def __init__(self):
        print("啟動地圖測繪工具...")
        with open("config/config.toml", "rb") as f:
            self.config = tomllib.load(f)
            
        self.gps = MinimapParser.from_config(self.config)
        self.sct = mss.mss()
        self.screen_region = self.config["game_screen"]
        
        self.map_data = {
            "platforms": {},
            "links": []
        }
        
        # 暫存變數
        self.temp_platform_name = ""
        self.temp_x_min = None

    def get_current_gps(self):
        """抓取當下的小地圖座標"""
        frame = np.array(self.sct.grab(self.screen_region))
        gps_data = self.gps.parse(frame)
        return gps_data.get("player")

    def run(self):
        print("\n=== 快捷鍵說明 ===")
        print("[F8] : 記錄平台起點 (左邊緣)")
        print("[F9] : 記錄平台終點 (右邊緣) 並儲存平台")
        print("[F10]: 記錄動作連接點 (下跳/爬繩)")
        print("[ESC]: 儲存並退出")
        
        while True:
            if keyboard.is_pressed("f8"):
                pos = self.get_current_gps()
                if pos:
                    self.temp_x_min = pos[0]
                    self.temp_y = pos[1]
                    self.temp_platform_name = input(f"\n📍 抓取到起點 {pos}，請輸入平台名稱 (例如 P_TOP): ")
                    print(f"✅ 已記錄起點。請走到平台右邊緣並按下 F9。")
                time.sleep(0.5)

            elif keyboard.is_pressed("f9"):
                pos = self.get_current_gps()
                if pos and self.temp_x_min is not None:
                    x_max = pos[0]
                    self.map_data["platforms"][self.temp_platform_name] = {
                        "y": self.temp_y, # 假設平台是平的
                        "x_min": self.temp_x_min,
                        "x_max": x_max
                    }
                    print(f"✅ 平台 {self.temp_platform_name} 儲存成功！範圍: X({self.temp_x_min}~{x_max}), Y:{self.temp_y}")
                    self.temp_x_min = None # 重置
                time.sleep(0.5)

            elif keyboard.is_pressed("f10"):
                pos = self.get_current_gps()
                if pos:
                    print(f"\n🔗 抓取到連接點 {pos}")
                    from_p = input("從哪個平台出發 (例如 P_TOP): ")
                    to_p = input("前往哪個平台 (例如 P_MID): ")
                    action = input("動作是什麼？(輸入 JUMP_DOWN 或 CLIMB_ROPE): ")
                    
                    self.map_data["links"].append({
                        "from": from_p,
                        "to": to_p,
                        "action": action.upper(),
                        "trigger_x": pos[0]
                    })
                    print(f"✅ 連接點儲存成功！")
                time.sleep(0.5)

            elif keyboard.is_pressed("esc"):
                with open("config/map_bonedragon.json", "w", encoding="utf-8") as f:
                    json.dump(self.map_data, f, indent=4, ensure_ascii=False)
                print("\n💾 地圖資料已成功儲存至 config/map_bonedragon.json！ 退出程式。")
                break
                
            time.sleep(0.05)

if __name__ == "__main__":
    mapper = MapMapper()
    mapper.run()