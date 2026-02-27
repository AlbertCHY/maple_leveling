import random
from behavior_tree import Node, NodeStatus
import time

# ==========================================
# 1. 優先級中斷節點 (Interrupt Nodes)
# ==========================================
class FallRecoveryNode(Node):
    """底層救援節點 (包裝了 NavigateUpNode)"""
    def __init__(self, activate_y, target_rope_x, target_floor_y, patrol_sequence, resume_index):
        self.activate_y = activate_y
        self.climb_node = NavigateUpNode(target_rope_x, target_floor_y)
        self.patrol_sequence = patrol_sequence # 傳入巡邏序列的參考，讓它能夠修改巡邏流程的記憶位置
        self.resume_index = resume_index # 掉落救援結束後，巡邏流程要從哪個步驟繼續
        self.is_recovering = False

    def tick(self, context):
        gps_py = context.get('gps_py')

        # 1. 觸發條件：掉到底層，鎖定進入救援狀態
        if gps_py >= self.activate_y:
            self.is_recovering = True

        # 2. 執行救援
        if self.is_recovering:
            print("[行為樹] 執行底層救援中...")
            
            # 把 context 轉交給肚子裡的 climb_node 去執行
            status = self.climb_node.tick(context)
            
            if status == NodeStatus.SUCCESS:
                # 爬到目標樓層了！解除救援狀態
                self.is_recovering = False
                self.patrol_sequence.current_idx = self.resume_index
                print(f"\n✅ 救援完畢！記憶已覆寫，從步驟 {self.resume_index} 繼續。")
                
                return NodeStatus.SUCCESS
                
            return NodeStatus.RUNNING # 還在爬

        return NodeStatus.FAILURE # 沒掉下去，沒事

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
        self.is_climbing = False # 是否正在爬繩中
        self.prev_y = None # 上一幀的 Y 座標，用來檢測是否有在爬繩
        self.last_jump_time = 0 # 記錄起跳時間
        self.finish_counter = 0

    def tick(self, context):
        maple_bot = context.get("maple_bot")
        gps_px = context.get("gps_px")
        gps_py = context.get("gps_py")
        distance_to_rope = gps_px - self.target_rope_x
        current_time = time.time()

        # 如果抵達目標樓層，回傳成功
        if gps_py <= self.target_floor_y:
            if self.prev_y == gps_py:
                self.finish_counter += 1
                if self.finish_counter >= 5:
                    maple_bot.controller.hold_key_end("up")
                    self.is_climbing = False
                    return NodeStatus.SUCCESS
            else:
                self.finish_counter = 0

        # 找繩子並爬上去
        elif abs(distance_to_rope) <= 10:
            maple_bot._update_movement('none')
            if not self.is_climbing:
                maple_bot.controller.tap_key("space")
                maple_bot.controller.hold_key_start("up")
                self.is_climbing = True
                self.last_jump_time = current_time
                self.prev_y = gps_py
            else:
                if current_time - self.last_jump_time > 1:
                    # 如果已經在爬繩了，但 Y 座標沒有下降，重置爬繩狀態
                    if  gps_py >= self.prev_y:
                        maple_bot.controller.hold_key_end("up")
                        self.is_climbing = False
        else:
            # 如果之前被怪撞飛離開了繩子範圍，重置爬繩狀態
            if self.is_climbing:
                maple_bot.controller.hold_key_end("up")
                self.is_climbing = False

            if distance_to_rope > 0:
                maple_bot._update_movement('left')  # 人在繩子右邊，往左走
            else:
                maple_bot._update_movement('right') # 人在繩子左邊，往右走
        self.prev_y = gps_py

        return NodeStatus.RUNNING