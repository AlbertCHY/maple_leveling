import time
import numpy as np
import random
import keyboard
import tomllib

# 匯入原有模組
from vision import GamePerception
from gps import MinimapParser
from controller import HumanizedController
from buff import BuffManager
from combat import CombatTargeting

# 匯入全新的行為樹模組
from behavior_tree import Selector, MemorySequence
from bt_nodes import FallRecoveryNode, BuffNode, ClearPlatformNode, JumpDownNode, NavigateUpNode

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
        self.constants = self.config["constant"]
        self.current_movement = None

        # 建立 AI 大腦：行為樹 (Behavior Tree)
        self._build_behavior_tree()

    def _build_behavior_tree(self):
        """將你的巡邏路線像樂高一樣組裝起來"""
        
        # 核心巡邏迴圈
        patrol_sequence = MemorySequence([
            ClearPlatformNode('left', self.constants["BOUND_LEFT"]),                              # 1. 上層向左清
            JumpDownNode(self.constants["TOP_FLOOR_Y"]),                                          # 2. 下跳到中層
            ClearPlatformNode('right', self.constants["BOUND_MID_RIGHT"]),                        # 3. 中層向右清
            NavigateUpNode(self.constants["ROPE_BETWEEN_MID"], self.constants["MID_FLOOR_Y"]),    # 4. 爬繩到中層高平台
            ClearPlatformNode('left', self.constants["ROPE_TO_TOP"]),                             # 5. 高平台向左清
            NavigateUpNode(self.constants["ROPE_TO_TOP"], self.constants["TOP_FLOOR_Y"]),         # 6. 爬繩回上層
            ClearPlatformNode('right', self.constants["BOUND_RIGHT"])                             # 7. 上層向右清 (完畢後自動回到步驟 1)
        ])

        # 根節點：決定當下最高優先級的行為
        self.root = Selector([
            FallRecoveryNode(),   # 優先級 1：掉落救援 (保命最重要)
            BuffNode(),           # 優先級 2：施放 BUFF (打怪前先上狀態)
            patrol_sequence       # 優先級 3：正常巡邏與打怪
        ])

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
        print("=== Maple Leveler (行為樹版) 啟動 ===")
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
                    time.sleep(0.5)

                if is_paused:
                    time.sleep(0.1)
                    continue

                # 全局感知
                frame = self.vision.sct.grab(self.config["game_screen"])
                frame_np = np.array(frame)
                
                yolo_data = self.vision.get_vision(frame_np)
                gps_data = self.gps.parse(frame_np)
                
                if not gps_data['player']:
                    continue

                print(f"\r當前位置: {gps_data['player']} \033[K", end="")

                # 驅動行為樹
                context = {
                    'maple_bot': self,
                    'gps_px': gps_data['player'][0],
                    'gps_py': gps_data['player'][1],
                    'yolo_player': yolo_data['player'],
                    'yolo_monsters': yolo_data['monsters']
                }
                
                self.root.tick(context)

                # 控制迴圈頻率
                time.sleep(0.02)

        except KeyboardInterrupt:
            print("\n🛑 接收到中斷訊號，正在安全關閉系統...")
        finally:
            self._update_movement(None)

if __name__ == "__main__":
    bot = MapleBot()
    bot.run()