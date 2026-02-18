import time
from enum import Enum
import numpy as np
import keyboard

# 假設這些是你已經寫好的模組 (請確保檔案都在同一目錄下)
from vision import GamePerception
from gps import MinimapParser
from controller import HumanizedController
from buff import BuffManager
from combat import CombatTargeting

class BotState(Enum):
    TOP_CLEARING = 1
    JUMP_DOWN = 2
    MID_CLEARING = 3
    NAVIGATE_UP = 4
    FALL_RECOVERY = 5

class MapleBot:
    def __init__(self):
        print("🔧 系統初始化中...")
        self.vision = GamePerception()
        self.gps = MinimapParser(region=(10, 160, 270, 250)) # 替換為你的真實 region
        self.controller = HumanizedController()
        self.buff_manager = BuffManager(self.controller)
        self.combat = CombatTargeting(skill_range=90, penetration_ratio=-0.25)
        
        # 初始狀態：預設從上層開始清怪 (也可以寫邏輯依據 GPS 自動判斷初始狀態)
        self.state = BotState.TOP_CLEARING
        self.current_movement = None

        # --- GPS 常數 (請替換為你實際小地圖的數據) ---
        self.BOUND_LEFT = 30        # 左側盡頭 X
        self.BOUND_RIGHT = 220      # 右側盡頭 X
        self.MID_FLOOR_Y = 100       # 中層 Y (大於這個值代表到了中層)
        self.TOP_FLOOR_Y = 100       # 上層 Y (小於這個值代表到了上層)
        self.LOWER_FLOOR_Y = 300     # 底層 Y (掉下去了)
        self.ROPE_GPS_X = 200       # 繩子在小地圖上的 X 座標

    def update_movement(self, direction):
        """非阻塞式方向鍵控制"""
        if self.current_movement != direction:
            if self.current_movement:
                self.controller.stop_moving(self.current_movement)
            if direction:
                self.controller.start_moving(direction)
            self.current_movement = direction

    def handle_combat_state(self, direction, bound_x, gps_px, yolo_data):
        """
        處理清怪狀態的微觀決策
        :return: bool, 是否已經抵達邊界？
        """
        # 1. 檢查是否抵達邊界 (巨觀)
        if (direction == 'left' and gps_px <= bound_x) or \
           (direction == 'right' and gps_px >= bound_x):
            self.update_movement(None)
            return True # 已經抵達邊界，通知主迴圈切換狀態

        # 2. 戰鬥邏輯 (微觀)
        yolo_player = yolo_data['player']
        yolo_monsters = yolo_data['monsters']
        if yolo_player:
            target, in_range = self.combat.find_target_and_check_range(
                yolo_player, yolo_monsters, direction
            )
            if target and in_range:
                self.update_movement(None) # 停下腳步
                print(f"⚔️ [{direction.upper()}] 攻擊！")
                self.controller.tap_key('f')
                #time.sleep(self.controller._get_gaussian_time(0.6, 0.1, 0.4))
            else:
                self.update_movement(direction) # 繼續走
        else:
            self.update_movement(direction) # 沒看到玩家 (可能被特效擋住)，盲走
            
        return False # 還沒抵達邊界

    def run(self):
        # print("=== MaplePilot 啟動 ===")
        # print(" [F12]: 緊急停止並退出")
        # print(" [F11]: 暫停/恢復 AI")
        # print("請在 3 秒內切換視窗...")

        time.sleep(3) 
        # is_paused = False
        try:
            while True:
                # # === 1. 緊急停止 (Solution 1) ===
                # if keyboard.is_pressed('f12'):
                #     print("\n[緊急停止] 使用者按下 F12")
                #     break
                
                # # === 2. 暫停開關 ===
                # if keyboard.is_pressed('f11'):
                #     is_paused = not is_paused
                #     print(f"\n[狀態切換] AI {'暫停中' if is_paused else '運作中'}")
                #     self.update_movement(None)
                #     time.sleep(0.5) # 防止連點

                # if is_paused:
                #     time.sleep(0.1)
                #     continue

                # ---------------------------------------------------------
                # 1. 全局感知 (Sensor Fusion)
                # ---------------------------------------------------------
                frame = self.vision.sct.grab(self.vision.region)
                frame_np = np.array(frame)
                
                _, yolo_data, _ = self.vision.get_vision(frame_np) # 假設你把 get_vision 改成吃 frame_np
                gps_data = self.gps.parse(frame_np)

                if not gps_data['player']:
                    self.update_movement(None)
                    time.sleep(0.1)
                    continue # 找不到 GPS (可能在過圖)，原地等待

                gps_px, gps_py = gps_data['player']

                # ---------------------------------------------------------
                # 2. 全局防呆與優先權中斷
                # ---------------------------------------------------------
                # 墜落檢查
                if gps_py >= self.LOWER_FLOOR_Y and self.state != BotState.FALL_RECOVERY:
                    print("⚠️ 警告：意外墜落！切換至救援狀態...")
                    self.update_movement(None)
                    self.state = BotState.FALL_RECOVERY
                    continue

                # BUFF 檢查 (最高優先權)
                if self.buff_manager.check_and_cast():
                    self.update_movement(None)
                    continue # 剛放完 BUFF，跳過這幀的其餘動作

                # ---------------------------------------------------------
                # 3. 狀態機核心路由 (State Machine Routing)
                # ---------------------------------------------------------
                print(f"當前位置: {gps_data['player']}")
                if self.state == BotState.TOP_CLEARING:
                    # 在上層，向左清怪，目標是 BOUND_LEFT
                    reached_edge = self.handle_combat_state('left', self.BOUND_LEFT, gps_px, yolo_data)
                    if reached_edge:
                        print("🏁 到達上層左邊緣，準備下跳...")
                        self.state = BotState.JUMP_DOWN

                elif self.state == BotState.JUMP_DOWN:
                    self.controller.jump_down() # 執行 down + space
                    # 等待並確認是否落到中層
                    time.sleep(0.5) # 給予掉落時間
                    print("下跳結束: gps_py:", gps_py, "MID_FLOOR_Y:", self.MID_FLOOR_Y)
                    if gps_py >= self.MID_FLOOR_Y:
                        print("✅ 成功抵達中層！")
                        self.state = BotState.MID_CLEARING

                elif self.state == BotState.MID_CLEARING:
                    # 在中層，向右清怪，目標是 BOUND_RIGHT
                    reached_edge = self.handle_combat_state('right', self.BOUND_RIGHT, gps_px, yolo_data)
                    if reached_edge:
                        print("🏁 到達中層右邊緣，準備尋找繩子...")
                        self.state = BotState.NAVIGATE_UP

                elif self.state == BotState.NAVIGATE_UP:
                    # 尋找繩子並往上爬
                    distance_to_rope = gps_px - self.ROPE_GPS_X
                    
                    # 判斷是否已經爬到上層
                    if gps_py <= self.TOP_FLOOR_Y:
                        print("✅ 成功抵達上層！重新開始巡邏迴圈。")
                        self.update_movement(None)
                        self.state = BotState.TOP_CLEARING
                        continue

                    # 導航至繩子正下方
                    if abs(distance_to_rope) <= 2: # 允許 2 個 GPS 像素的誤差
                        self.update_movement(None)
                        print("📍 對齊繩子，開始攀爬...")
                        self.controller.climb_rope(duration=3.0)
                    elif distance_to_rope > 2:
                        self.update_movement('left')
                    else:
                        self.update_movement('right')

                elif self.state == BotState.FALL_RECOVERY:
                    # 實作你的底層爬回中層邏輯
                    # 例如：固定走向某個座標，然後爬繩子
                    print("🔄 執行底層救援... (請根據地形實作)")
                    # 假設救援成功：
                    # self.state = BotState.MID_CLEARING

                # 控制迴圈頻率
                time.sleep(0.03)

        except KeyboardInterrupt:
            print("\n🛑 接收到中斷訊號，正在安全關閉系統...")
        finally:
            self.update_movement(None) # 確保程式結束時釋放所有按鍵

# --- 程式進入點 ---
if __name__ == "__main__":
    bot = MapleBot()
    bot.run()