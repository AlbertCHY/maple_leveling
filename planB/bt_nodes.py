from behavior_tree import Node, NodeStatus
import time

# ==========================================
# 1. 優先級中斷節點 (Interrupt Nodes)
# ==========================================
class FallRecoveryNode(Node):
    """底層救援節點"""
    def tick(self, context):
        maple_bot = context.get("maple_bot")
        gps_px = context.get("gps_px")
        gps_py = context.get("gps_py")

        # 如果掉到底層，啟動救援機制
        if gps_py >= maple_bot.constants["LOWER_FLOOR_Y"]:
            print(f"\r⚠️ [行為樹] 執行底層救援... (X:{gps_px} Y:{gps_py}) \033[K", end="")
            if gps_py <= maple_bot.constants["MID_FLOOR_Y"]:
                maple_bot._update_movement(None)
                return NodeStatus.SUCCESS # 救援完畢！

            maple_bot._find_rope(gps_px, maple_bot.constants["ROPE_RESCUE"], 2.5)
            return NodeStatus.RUNNING # 還在救援中
            
        return NodeStatus.FAILURE # 沒掉下去，此節點判定失敗，讓行為樹往下走

class BuffNode(Node):
    """Buff 檢查與施放節點"""
    def tick(self, context):
        maple_bot = context.get("maple_bot")
        if maple_bot.buff_manager.check_and_cast():
            maple_bot._update_movement(None)
            return NodeStatus.SUCCESS # 剛放完 Buff
        return NodeStatus.FAILURE # 不需要放 Buff

# ==========================================
# 2. 巡邏與動作節點 (Action Nodes)
# ==========================================
class ClearPlatformNode(Node):
    """平台清怪節點"""
    def __init__(self, direction, bound_x):
        self.direction = direction
        self.bound_x = bound_x

    def tick(self, context):
        maple_bot = context.get("maple_bot")
        gps_px = context.get("gps_px")
        yolo_player = context.get("yolo_player")
        yolo_monsters = context.get("yolo_monsters")
        
        # 呼叫戰鬥邏輯
        reached_edge = maple_bot._handle_combat_state(
            self.direction, 
            self.bound_x, 
            gps_px, 
            yolo_player, 
            yolo_monsters
        )

        if reached_edge:
            return NodeStatus.SUCCESS # 走到盡頭了，任務完成！
        return NodeStatus.RUNNING # 還在清怪中

class JumpDownNode(Node):
    """下跳節點"""
    def __init__(self, target_floor_y):
        self.target_floor_y = target_floor_y

    def tick(self, context):
        maple_bot = context.get("maple_bot")
        gps_py = context.get("gps_py")

        # 如果已經到達目標樓層，重置狀態並回傳成功
        if gps_py >= self.target_floor_y:
            return NodeStatus.SUCCESS

        # 如果還在上層，執行跳躍並等待落地
        else:
            maple_bot.controller.jump_down()
            time.sleep(0.5) # 等待落地動畫，防止半空連按
            
        return NodeStatus.RUNNING

class NavigateUpNode(Node):
    """導航爬繩節點"""
    def __init__(self, target_rope_x, target_floor_y):
        self.target_rope_x = target_rope_x
        self.target_floor_y = target_floor_y
        self.is_jumping = False # 是否已經執行過跳躍抓繩的動作了
        self.is_climbing = False # 是否正在爬繩中

    def tick(self, context):
        maple_bot = context.get("maple_bot")
        gps_px = context.get("gps_px")
        gps_py = context.get("gps_py")
        distance_to_rope = gps_px - self.target_rope_x

        # 如果抵達目標樓層，回傳成功
        if gps_py <= self.target_floor_y:
            maple_bot._update_movement(None)
            maple_bot.controller.sleep_gaussian(0.05, 0.01, 0.04)
            maple_bot.controller.tap("space") # 跳躍提早離開繩子
            maple_bot.controller.sleep_gaussian(0.1, 0.02, 0.08)
            maple_bot.controller.hold_key_end("up")
            self.is_climbing = False
            self.is_jumping = False
            return NodeStatus.SUCCESS

        # 找繩子並爬上去
        if abs(distance_to_rope) <= 7 and not self.is_climbing:
            maple_bot.controller.sleep_gaussian(0.05, 0.01, 0.04) # 模擬人類反應時間
            maple_bot.controller.hold_key_start("up") # 按住上鍵準備抓繩
            self.is_climbing = True # 標記正在爬繩中，避免重複觸發
        if abs(distance_to_rope) <= 2 and self.is_jumping:
            maple_bot.controller.hold_key_end("space") # 放開跳躍鍵
            self.is_jumping = False
        elif abs(distance_to_rope) <= 5 and not self.is_jumping:
            maple_bot.controller.sleep_gaussian(0.05, 0.01, 0.04)
            maple_bot.controller.hold_key_start("space") # 按住跳嘗試抓繩
            self.is_jumping = True # 標記已經跳過了，避免重複跳躍
        elif abs(distance_to_rope) > 5:
            maple_bot.controller.hold_key_end("space") # 放開跳躍鍵
            self.is_jumping = False # 重置跳躍狀態
        
        if distance_to_rope > 0:
            maple_bot._update_movement('left')
        else:
            maple_bot._update_movement('right')

        return NodeStatus.RUNNING