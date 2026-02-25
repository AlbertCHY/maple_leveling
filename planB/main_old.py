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
    TOP_CLEARING_LEFT = 1   # 在上層，向左清怪
    JUMP_DOWN = 2           # 從上層下跳到中層
    MID_CLEARING_RIGHT = 3  # 在中層，向右清怪到最低處
    NAVIGATE_UP_1 = 4       # 從中層低平台導航到中層高平台
    MID_CLEARING_LEFT = 5   # 在中層高平台，向左清怪到折返點
    NAVIGATE_UP_2 = 6       # 從中層導航回上層
    TOP_CLEARING_RIGHT = 7  # 在上層，向右清怪
    FALL_RECOVERY = 0       # 從最底層回到中層低平台

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

    def _update_movement(self, direction):
        """非阻塞式方向鍵控制"""
        if self.current_movement == direction:
            return
        if self.current_movement:
            self.controller.stop_moving(self.current_movement)
        if direction:
            self.controller.start_moving(direction)
        self.current_movement = direction

    def _handle_combat_state(self, direction, bound_x, gps_px, yolo_player, yolo_monsters):
        """
        處理清怪狀態的微觀決策
        :return: bool, 是否已經抵達邊界？
        """
        # 戰鬥邏輯：根據 GPS 和 YOLO 資料決定是否攻擊或繼續移動
        target_in_range, jump_or_not = self.combat.find_target_and_check_range(yolo_player, yolo_monsters, direction)
        if target_in_range:
            if jump_or_not:
                print(f"⚔️ [{direction.upper()}] 前跳攻擊！")
                self.controller.jump_attack(direction, 'f', timming=0.025)
                time.sleep(0.6 + random.uniform(-0.01, 0.01)) # 等待跳躍動畫結束
            else:
                print(f"⚔️ [{direction.upper()}] 攻擊！")
                self._update_movement(None)
                self.controller.tap_key('f')
                time.sleep(0.2 + random.uniform(-0.01, 0.01)) # 等待攻擊動畫結束
        else:
            self._update_movement(direction) # 繼續走
            if (direction == 'left' and gps_px <= random.uniform(bound_x - 3, bound_x)) or \
            (direction == 'right' and gps_px >= random.uniform(bound_x, bound_x + 3)):
                self._update_movement(None)
                return True # 已經抵達邊界，通知主迴圈切換狀態
            
        return False # 還沒抵達邊界
    
    def _find_rope(self, gps_px, target_rope_x, duration):
        """導航至繩子位置的輔助函數"""
        distance_to_rope = gps_px - target_rope_x
        if abs(distance_to_rope) <= 5:
            self._update_movement(None)
            self.controller.climb_rope(duration)
        elif distance_to_rope > 0:
            self._update_movement('left')
        else:
            self._update_movement('right')

    def run(self):
        print("=== Maple Leveler 啟動 ===")
        print(" [F11]: 暫停/恢復")
        print("請在 3 秒內切換到遊戲視窗...")
        time.sleep(3) 
        is_paused = False

        try:
            while True:
                # === 暫停開關 ===
                if keyboard.is_pressed('f11'):
                    is_paused = not is_paused
                    print(f"\n[狀態切換] AI {'暫停中' if is_paused else '運作中'}")
                    self._update_movement(None)
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
                # if not yolo_player: 以小地圖為準 yolo沒找到玩家就依照gps操作 攻擊當作沒目標

                gps_data = self.gps.parse(frame_np) # 傳出畫面回傳小地圖的目標座標
                if not gps_data['player']: # 小地圖上沒找到玩家 直接進到下個迴圈
                    continue
                gps_px, gps_py = gps_data['player']

                # ---------------------------------------------------------
                # 墜落檢查與BUFF檢查
                # ---------------------------------------------------------
                # 墜落檢查
                if gps_py >= self.config["constant"]["LOWER_FLOOR_Y"] and self.state != BotState.FALL_RECOVERY:
                    print("⚠️ 警告：意外墜落！切換至救援狀態...")
                    self._update_movement(None)
                    self.state = BotState.FALL_RECOVERY
                    continue

                # BUFF 檢查
                if self.buff_manager.check_and_cast():
                    self._update_movement(None)
                    continue # 剛放完 BUFF，跳過這幀的其餘動作

                # ---------------------------------------------------------
                # 狀態機核心路由 (State Machine Routing)
                # ---------------------------------------------------------
                print(f"\r當前位置: {gps_data['player']} \033[K", end="")

                match self.state:
                    case BotState.TOP_CLEARING_LEFT:
                        # 在上層，向左清怪，目標是 BOUND_LEFT
                        reached_edge = self._handle_combat_state('left', self.config["constant"]["BOUND_LEFT"], gps_px, yolo_player, yolo_monsters)
                        if reached_edge:
                            print("到達上層左邊緣，準備下跳...")
                            self.state = BotState.JUMP_DOWN
                            time.sleep(0.5) # 等待下跳動畫結束

                    case BotState.JUMP_DOWN:
                        if gps_py >= self.config["constant"]["TOP_FLOOR_Y"]:
                            self._update_movement("right")
                            self.state = BotState.MID_CLEARING_RIGHT
                        else:
                            self.controller.jump_down() # 執行 down + space

                    case BotState.MID_CLEARING_RIGHT:
                        # 在中層，向右清怪，目標是 BOUND_MID_RIGHT
                        reached_edge = self._handle_combat_state('right', self.config["constant"]["BOUND_MID_RIGHT"], gps_px, yolo_player, yolo_monsters)
                        if reached_edge:
                            print("清完中層低平台，找繩子前往中層高平台")
                            self.state = BotState.NAVIGATE_UP_1

                    case BotState.NAVIGATE_UP_1:                
                        # 判斷是否已經爬到上層
                        if gps_py <= self.config["constant"]["MID_FLOOR_Y"]:
                            print("抵達中層高平台 走到最右邊。")
                            self._update_movement("right")
                            if gps_px >= random.uniform(self.config["constant"]["BOUND_RIGHT"], self.config["constant"]["BOUND_RIGHT"] + 3): # 確保走到最右邊
                                self._update_movement(None)
                                self.state = BotState.MID_CLEARING_LEFT
                        else:
                            # 導航至繩子
                            self._find_rope(gps_px, self.config["constant"]["ROPE_BETWEEN_MID"], 1.5)

                    case BotState.MID_CLEARING_LEFT:
                        reached_edge = self._handle_combat_state('left', self.config["constant"]["ROPE_TO_TOP"], gps_px, yolo_player, yolo_monsters)
                        if reached_edge:
                            print("到達中層轉上層點，準備去上層...")
                            self.state = BotState.NAVIGATE_UP_2

                    case BotState.NAVIGATE_UP_2:                 
                        # 判斷是否已經爬到上層
                        if gps_py <= self.config["constant"]["TOP_FLOOR_Y"]:
                            print("抵達上層！ 向右清怪")
                            self._update_movement("right")
                            self.state = BotState.TOP_CLEARING_RIGHT
                        else:
                        # 導航至繩子
                            self._find_rope(gps_px, self.config["constant"]["ROPE_TO_TOP"], 2.5)

                    case BotState.TOP_CLEARING_RIGHT:
                        reached_edge = self._handle_combat_state('right', self.config["constant"]["BOUND_RIGHT"], gps_px, yolo_player, yolo_monsters)
                        if reached_edge:
                            print("到達上層右邊緣，重新開始迴圈")
                            self.state = BotState.TOP_CLEARING_LEFT

                    case BotState.FALL_RECOVERY:
                        print("🔄 執行底層救援...")
                        
                        # 判斷是否已經爬回中層
                        if gps_py <= self.config["constant"]["LOWER_FLOOR_Y"]:
                            print("抵達中層！回到上層繼續")
                            self._update_movement(None)
                            self.state = BotState.NAVIGATE_UP_2
                            continue
                        
                        # 尋找繩子
                        self._find_rope(gps_px, self.config["constant"]["ROPE_RESCUE"], 2.5)

                # 控制迴圈頻率
                time.sleep(0.02)

        except KeyboardInterrupt:
            print("\n🛑 接收到中斷訊號，正在安全關閉系統...")
        finally:
            self._update_movement(None) # 確保程式結束時釋放所有按鍵

# --- 程式進入點 ---
if __name__ == "__main__":
    bot = MapleBot()
    bot.run()