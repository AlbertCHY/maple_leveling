import time
from enum import Enum
import numpy as np
import random
import keyboard
import tomllib

# 假設這些是你已經寫好的模組 (請確保檔案都在同一目錄下)
from vision import GamePerception
from gps import MinimapParser
from controller import HumanizedController
from buff import BuffManager
from combat import CombatTargeting

class BotState(Enum):
    TOP_CLEARING_LEFT = 1
    JUMP_DOWN = 2
    MID_CLEARING_RIGHT = 3
    NAVIGATE_UP_1 = 4
    MID_CLEARING_LEFT = 5
    NAVIGATE_UP_2 = 6
    TOP_CLEARING_RIGHT = 7
    FALL_RECOVERY = 0

class MapleBot:
    def __init__(self):
        print("🔧 系統初始化中...")
        with open("config.toml", "rb") as f:
            self.config = tomllib.load(f)

        self.vision = GamePerception.from_config(self.config)
        self.gps = MinimapParser.from_config(self.config)
        self.controller = HumanizedController()
        self.buff_manager = BuffManager.from_config(self.controller, self.config)
        self.combat = CombatTargeting.from_config(self.config)
        
        # 初始狀態：預設從上層開始清怪 (也可以寫邏輯依據 GPS 自動判斷初始狀態)
        self.state = BotState.TOP_CLEARING_LEFT
        self.current_movement = None

        # --- GPS 常數 ---
        self.BOUND_LEFT = 25        # 左側平台盡頭 X
        self.BOUND_RIGHT = 250      # 右側平台盡頭
        self.BOUND_MID_RIGHT = 210  # 右側中平台盡頭 X
        self.TOP_FLOOR_Y = 100      # 上層 Y 分界
        self.MID_FLOOR_Y = 135      # 中層 Y 分界
        self.LOWER_FLOOR_Y = 180    # 此Y以下代表掉到最底層
        self.ROPE_UPPER_1 = 245     # 中層到上層繩子1
        self.ROPE_UPPER_2 = 195     # 中層到上層繩子2
        self.ROPE_RESCUE_X = 205    # 底層到中層繩子

    def update_movement(self, direction):
        """非阻塞式方向鍵控制"""
        if self.current_movement == direction:
            return
        if self.current_movement:
            self.controller.stop_moving(self.current_movement)
        if direction:
            self.controller.start_moving(direction)
        self.current_movement = direction

    def handle_combat_state(self, direction, bound_x, gps_px, yolo_player, yolo_monsters):
        """
        處理清怪狀態的微觀決策
        :return: bool, 是否已經抵達邊界？
        """
        # 戰鬥邏輯：根據 GPS 和 YOLO 資料決定是否攻擊或繼續移動
        target_in_range, jump_or_not = self.combat.find_target_and_check_range(yolo_player, yolo_monsters, direction)
        # if target_in_range and not jump_or_not:
        #     print(f"⚔️ [{direction.upper()}] 攻擊！")
        #     self.controller.tap_key('f')
        #     time.sleep(0.2 + random.uniform(-0.01, 0.01)) # 等待攻擊動畫結束
        if target_in_range:
            if jump_or_not:
                print(f"⚔️ [{direction.upper()}] 前跳攻擊！")
                self.controller.jump_attack(direction, 'f', timming=0.025)
                time.sleep(0.6 + random.uniform(-0.01, 0.01)) # 等待跳躍動畫結束
            else:
                print(f"⚔️ [{direction.upper()}] 攻擊！")
                self.controller.tap_key('f')
                time.sleep(0.2 + random.uniform(-0.01, 0.01)) # 等待攻擊動畫結束
        else:
            self.update_movement(direction) # 繼續走
            if (direction == 'left' and gps_px <= random.uniform(bound_x, bound_x + 5)) or \
            (direction == 'right' and gps_px >= random.uniform(bound_x, bound_x + 5)):
                self.update_movement(None)
                return True # 已經抵達邊界，通知主迴圈切換狀態
            
        return False # 還沒抵達邊界

    def run(self):
        print("=== Maple Leveler 啟動 ===")
        print(" [F12]: 緊急停止並退出")
        print(" [F11]: 暫停/恢復")
        print("請在 3 秒內切換到遊戲視窗...")
        time.sleep(3) 
        is_paused = False

        try:
            while True:
                # === 手動停止 ===
                if keyboard.is_pressed('f12'):
                    is_paused = True
                    print("\n[緊急停止] 使用者按下 F12")
                    self.update_movement(None)
                    break
                
                # === 暫停開關 ===
                if keyboard.is_pressed('f11'):
                    is_paused = not is_paused
                    print(f"\n[狀態切換] AI {'暫停中' if is_paused else '運作中'}")
                    self.update_movement(None)
                    time.sleep(0.5) # 防止連點

                if is_paused:
                    time.sleep(0.1)
                    continue

                # ---------------------------------------------------------
                # 全局感知 (Sensor Fusion)
                # ---------------------------------------------------------
                frame = self.vision.sct.grab(self.config["game_screen"])
                frame_np = np.array(frame)
                
                yolo_data = self.vision.get_vision(frame_np) # 傳出畫面回傳 YOLO 辨識的物件資料
                yolo_player = yolo_data['player']
                yolo_monsters = yolo_data['monsters']
                if not yolo_player:
                    continue

                gps_data = self.gps.parse(frame_np) # 傳出畫面回傳小地圖的目標座標
                if not gps_data['player']: # 小地圖上沒找到玩家
                    continue
                gps_px, gps_py = gps_data['player']

                # ---------------------------------------------------------
                # 墜落檢查與BUFF檢查
                # ---------------------------------------------------------
                # 墜落檢查
                if gps_py >= self.LOWER_FLOOR_Y and self.state != BotState.FALL_RECOVERY:
                    print("⚠️ 警告：意外墜落！切換至救援狀態...")
                    self.update_movement(None)
                    self.state = BotState.FALL_RECOVERY
                    continue

                # BUFF 檢查
                if self.buff_manager.check_and_cast():
                    self.update_movement(None)
                    continue # 剛放完 BUFF，跳過這幀的其餘動作

                # ---------------------------------------------------------
                # 狀態機核心路由 (State Machine Routing)
                # ---------------------------------------------------------
                print(f"\r當前位置: {gps_data['player']} \033[K", end="")

                if self.state == BotState.TOP_CLEARING_LEFT:
                    # 在上層，向左清怪，目標是 BOUND_LEFT
                    reached_edge = self.handle_combat_state('left', self.BOUND_LEFT, gps_px, yolo_player, yolo_monsters)
                    if reached_edge:
                        print("🏁 到達上層左邊緣，準備下跳...")
                        self.state = BotState.JUMP_DOWN

                elif self.state == BotState.JUMP_DOWN:
                    if gps_py >= self.TOP_FLOOR_Y:
                        if gps_px >= self.BOUND_LEFT:
                            self.update_movement("left")
                        else:
                            self.update_movement("right")
                            self.state = BotState.MID_CLEARING_RIGHT
                    else:
                        self.controller.jump_down() # 執行 down + space

                elif self.state == BotState.MID_CLEARING_RIGHT:
                    # 在中層，向右清怪，目標是 BOUND_MID_RIGHT
                    reached_edge = self.handle_combat_state('right', self.BOUND_MID_RIGHT, gps_px, yolo_player, yolo_monsters)
                    if reached_edge:
                        print("🏁 到達中層第二階段點，準備尋找繩子...")
                        self.state = BotState.NAVIGATE_UP_2

                elif self.state == BotState.NAVIGATE_UP_1:                
                    # 判斷是否已經爬到上層
                    if gps_py <= self.MID_FLOOR_Y:
                        print("✅ 成功抵達中層第二階段 走到最右邊。")
                        self.update_movement("right")
                        if gps_px >= self.BOUND_RIGHT: # 確保走到最右邊
                            self.update_movement(None)
                            self.state = BotState.MID_CLEARING_LEFT
                    else:
                        # 導航至繩子正下方
                        distance_to_rope = gps_px - self.ROPE_UPPER_1
                        if abs(distance_to_rope) <= 2: # 允許 1 個 GPS 像素的誤差
                            self.update_movement(None)
                            self.controller.tap_key('space') # 先跳起來抓繩
                            print("📍 對齊繩子，開始攀爬...")
                            self.controller.climb_rope(duration=random.uniform(2, 2.2))
                        elif distance_to_rope > 2:
                            self.update_movement('left')
                        else:
                            self.update_movement('right')

                elif self.state == BotState.MID_CLEARING_LEFT:
                    reached_edge = self.handle_combat_state('left', self.ROPE_UPPER_2, gps_px, yolo_player, yolo_monsters)
                    if reached_edge:
                        print("🏁 到達中層轉上層點，準備去上層...")
                        self.state = BotState.NAVIGATE_UP_2

                elif self.state == BotState.NAVIGATE_UP_2:                 
                    # 判斷是否已經爬到上層
                    if gps_py <= self.TOP_FLOOR_Y:
                        print("✅ 成功抵達上層！ 向右清怪")
                        self.update_movement("right")
                        self.state = BotState.TOP_CLEARING_RIGHT
                    else:
                    # 導航至繩子正下方
                        distance_to_rope = gps_px - self.ROPE_UPPER_2
                        if abs(distance_to_rope) <= 2: # 允許 2 個 GPS 像素的誤差
                            self.update_movement(None)
                            self.controller.tap_key('space') # 先跳起來抓繩
                            print("📍 對齊繩子，開始攀爬...")
                            self.controller.climb_rope(duration=2.5)
                        elif distance_to_rope > 2:
                            self.update_movement('left')
                        else:
                            self.update_movement('right')

                elif self.state == BotState.TOP_CLEARING_RIGHT:
                    reached_edge = self.handle_combat_state('right', self.BOUND_RIGHT, gps_px, yolo_player, yolo_monsters)
                    if reached_edge:
                        print("🏁 到達上層右邊緣，重新開始迴圈")
                        self.state = BotState.TOP_CLEARING_LEFT

                elif self.state == BotState.FALL_RECOVERY:
                    print("🔄 執行底層救援...")
                    
                    # 判斷是否已經爬回中層
                    if gps_py <= self.LOWER_FLOOR_Y:
                        print("✅ 成功抵達中層！回到上層繼續")
                        self.update_movement(None)
                        self.state = BotState.NAVIGATE_UP_2
                        continue
                    
                    # 尋找繩子並往上爬
                    distance_to_rope = gps_px - self.ROPE_RESCUE_X
                    # 導航至繩子正下方
                    if abs(distance_to_rope) <= 2:
                        self.update_movement(None)
                        self.controller.tap_key("space") # 先跳起來抓繩
                        print("📍 對齊繩子，開始攀爬...")
                        self.update_movement(None)
                        self.controller.climb_rope(duration=2)
                    elif distance_to_rope > 2:
                        self.update_movement('left')
                    else:
                        self.update_movement('right')

                # 控制迴圈頻率
                time.sleep(0.02)

        except KeyboardInterrupt:
            print("\n🛑 接收到中斷訊號，正在安全關閉系統...")
        finally:
            self.update_movement(None) # 確保程式結束時釋放所有按鍵

# --- 程式進入點 ---
if __name__ == "__main__":
    bot = MapleBot()
    bot.run()