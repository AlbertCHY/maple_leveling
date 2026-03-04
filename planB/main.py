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
        with open("config_bonedragon.toml", "rb") as f:
            self.config = tomllib.load(f)

        self.vision = GamePerception.from_config(self.config)
        self.gps = MinimapParser.from_config(self.config)
        self.controller = HumanizedController()
        self.buff_manager = BuffManager.from_config(self.config, self.controller)
        self.combat = CombatTargeting.from_config(self.config)
        self.constants = self.config["constant"]
        

        # 建立 AI 大腦：行為樹 (Behavior Tree)
        self._build_behavior_tree()

    def _build_behavior_tree(self):
        """將你的巡邏路線像樂高一樣組裝起來"""
        
        # 核心巡邏迴圈
        patrol_sequence = MemorySequence([
            ClearPlatformNode('left', self.constants["BOUND_LEFT_X"]),                                  # 1. 上層向左清
            JumpDownNode(self.constants["TOP_MID_BOUND_Y"]),                                            # 2. 下跳到中層
            ClearPlatformNode('right', self.constants["ROPE_BETWEEN_MID_X"]),                           # 3. 中層向右清
            NavigateUpNode(self.constants["ROPE_BETWEEN_MID_X"], self.constants["ROPE_BETWEEN_MID_Y"]), # 4. 爬繩到中層高平台
            ClearPlatformNode('right', self.constants["BOUND_RIGHT_X"]),                                # 5. 高平台向右清
            ClearPlatformNode('left', self.constants["ROPE_TO_TOP_X"]),                                 # 6. 高平台向左清
            NavigateUpNode(self.constants["ROPE_TO_TOP_X"], self.constants["ROPE_TO_TOP_Y"]),           # 7. 爬繩回上層
            ClearPlatformNode('right', self.constants["BOUND_RIGHT_X"])                                 # 8. 上層向右清
        ])

        # 根節點：決定當下最高優先級的行為
        self.root = Selector([
            BuffNode(self.buff_manager),            # 優先級 1：施放 BUFF (打怪前先上狀態)
            FallRecoveryNode(                       # 優先級 2：掉落救援
                self.constants["MID_BOT_BOUND_Y"],
                self.constants["ROPE_RESCUE_X"],
                self.constants["ROPE_RESCUE_Y"],
                patrol_sequence,
                2                                   # 掉落救援結束後，巡邏流程從第 3 步 (中層向右清) 繼續
            ), 
            patrol_sequence                         # 優先級 3：正常巡邏與打怪
        ])

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
                    self.controller.update_movement(None)
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
                print(f"\r小地圖位置: {gps_data['player']} \033[K", end="")

                # 驅動行為樹
                context = {
                'controller': self.controller,
                'combat': self.combat,
                'movement_manager': self.movement_manager,
                'gps_px': gps_data['player'][0],
                'gps_py': gps_data['player'][1],
                'yolo_player': yolo_data['player'],
                'yolo_monsters': yolo_data['monsters']
                }
                
                self.root.tick(context)

                # 控制迴圈頻率6
                time.sleep(0.02)

        except KeyboardInterrupt:
            print("\n🛑 接收到中斷訊號，正在安全關閉系統...")
        finally:
            self.controller.update_movement(None)

if __name__ == "__main__":
    bot = MapleBot()
    bot.run()