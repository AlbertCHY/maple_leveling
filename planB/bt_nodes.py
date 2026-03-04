import time
import random
from behavior_tree import Node, NodeStatus


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
    """非阻塞式的 BUFF 施放節點"""
    def __init__(self, buff_manager):
        self.buff_manager = buff_manager
        # 狀態機變數
        self.active_task = None   # 目前正在執行的 BuffTask (例如 5分鐘BUFF)
        self.key_index = 0        # 記錄目前施放到清單中的第幾個按鍵
        self.resume_time = 0.0    # 記錄下一次可以執行動作的時間戳

    def tick(self, context):
        current_time = time.time()
        controller = context.get("controller")

        # ==========================================
        # 正在施放 BUFF 的過程中
        # ==========================================
        if self.active_task is not None:
            # 時間還沒到，繼續等待動畫結束，直接退出 Tick 釋放資源
            if current_time < self.resume_time:
                return NodeStatus.RUNNING 

            # 時間到了，檢查是否還有按鍵沒按
            if self.key_index < len(self.active_task.keys):
                key = self.active_task.keys[self.key_index]
                
                print(f"✨ [{self.active_task.name}] 施放技能，按下按鍵: '{key}'")
                controller.update_movement(None) # 確保施法時不亂走
                controller.tap_key(key)
                
                # 設定下一個按鍵的等待時間 (加上常態分佈隨機性)
                delay = controller.get_guassian(self.active_task.base_cast_delay, 0.1, self.active_task.base_cast_delay*0.9)
                self.resume_time = current_time + delay
                self.key_index += 1
                
                return NodeStatus.RUNNING
                
            # 所有按鍵都按完了！
            else:
                print(f"✅ [{self.active_task.name}] 施放完畢！")
                self.active_task.schedule_next(current_time) # 重新排程下一次施放時間
                
                # 重置狀態機，準備迎接未來的任務
                self.active_task = None
                self.key_index = 0
                return NodeStatus.SUCCESS

        # ==========================================
        # 平常巡邏時，檢查是否有 BUFF 需要施放
        # ==========================================
        task = self.buff_manager.get_ready_task(current_time)
        if task:
            # 發現需要放 BUFF，進入施法狀態！
            self.active_task = task
            self.key_index = 0
            
            # 給予一個停頓確保前一個動作停止
            print(f"\n🛑 [狀態切換] 準備施放 {task.name}，停下腳步...")
            controller.update_movement(None)
            self.resume_time = current_time + random.uniform(1.0, 1.2)
            
            return NodeStatus.RUNNING

        return NodeStatus.FAILURE # 不需要放 BUFF，讓 Selector 繼續往下執行巡邏


# ==========================================
# 2. 巡邏與動作節點 (Action Nodes)
# ==========================================
class ClearPlatformNode(Node):
    """平台清怪節點"""
    def __init__(self, direction, bound_x):
        self.direction = direction
        self.bound_x = bound_x
        self.dynamic_bound = random.uniform(self.bound_x - 2, self.bound_x + 2)
        self.is_attacking = False
        self.attack_end_time = 0

    def tick(self, context):
        controller = context.get("controller")
        combat = context.get("combat")
        gps_px = context.get("gps_px")
        yolo_player = context.get("yolo_player")
        yolo_monsters = context.get("yolo_monsters")
        current_time = time.time()
        
        # 狀態檢查：如果正在攻擊，檢查動畫是否結束
        if self.is_attacking:
            if current_time >= self.attack_end_time:
                self.is_attacking = False
                return NodeStatus.RUNNING
            return NodeStatus.RUNNING
        
        # 呼叫戰鬥邏輯
        target_in_range, jump_or_not = combat.find_target_and_check_range(
            yolo_player, yolo_monsters, self.direction
        )

        if target_in_range:
            self.is_attacking = True
            self.attack_end_time = current_time + controller.get_guassian(0.6, 0.01, 0.55)
            if jump_or_not:
                print(f"⚔️ [{self.direction.upper()}] 前跳攻擊！")
                controller.jump_attack(self.direction, 'f', timming=0.01)
            else:
                print(f"⚔️ [{self.direction.upper()}] 攻擊！")
                controller.update_movement(None)
                controller.tap_key('f')
        else:
            controller.update_movement(self.direction) # 繼續走

            # 檢查是否到達邊界
            if (self.direction == "left" and gps_px <= self.dynamic_bound) or \
               (self.direction == "right" and gps_px >= self.dynamic_bound):
                controller.update_movement(None)
                self.dynamic_bound = random.uniform(self.bound_x - 2, self.bound_x + 2) # 重新骰一次下次的邊界
                return NodeStatus.SUCCESS # 走到盡頭了，任務完成！
            
        return NodeStatus.RUNNING # 還在清怪中

class JumpDownNode(Node):
    """下跳節點"""
    def __init__(self, target_floor_y):
        self.target_floor_y = target_floor_y

    def tick(self, context):
        controller = context.get("controller")
        gps_py = context.get("gps_py")

        # 如果已經到達目標樓層，重置狀態並回傳成功
        if gps_py >= self.target_floor_y:
            return NodeStatus.SUCCESS

        # 如果還在上層，執行跳躍並等待落地
        else:
            controller.jump_down()
            time.sleep(0.3) # 等待落地動畫，防止半空連按
            
        return NodeStatus.RUNNING

class NavigateUpNode(Node):
    """導航爬繩節點"""
    def __init__(self, target_rope_x, target_floor_y):
        self.target_rope_x = target_rope_x
        self.target_floor_y = target_floor_y
        self.is_climbing = False # 是否正在爬繩狀態
        self.prev_y = None # 上一幀的 Y 座標，用來檢測是否有在爬繩
        self.last_jump_time = 0 # 記錄起跳時間
        self.finish_counter = 0 # 紀錄爬完繩的等待狀態

    def tick(self, context):
        controller = context.get("controller")
        gps_px = context.get("gps_px")
        gps_py = context.get("gps_py")
        distance_to_rope = gps_px - self.target_rope_x
        current_time = time.time()

        # 如果抵達目標樓層，回傳成功
        if gps_py <= self.target_floor_y:
            controller.sleep_gaussian(0.05, 0.01, 0.045)
            controller.update_movement(None) # 爬過一定高度才放開左右以解決在離繩子一定範圍內失去方向時的原地跳躍
            if self.prev_y == gps_py:
                self.finish_counter += 1
                if self.finish_counter >= 4: # Y變動停止超過4次刷新 當作爬完繩子
                    controller.hold_key_end("up")
                    self.finish_counter = 0
                    self.is_climbing = False
                    return NodeStatus.SUCCESS
            else:
                self.finish_counter = 0

        # 找繩子並爬上去
        elif abs(distance_to_rope) <= 10:
            if not self.is_climbing:
                controller.tap_key("space")
                controller.hold_key_start("up")
                self.is_climbing = True
                self.last_jump_time = current_time
                self.prev_y = gps_py
            else:
                if current_time - self.last_jump_time > 0.8:
                    # 如果已經在爬繩了，但 Y 座標沒有下降，重置爬繩狀態
                    if  gps_py >= self.prev_y:
                        controller.hold_key_end("up")
                        self.is_climbing = False
        else:
            # 如果離開了繩子範圍，重置爬繩狀態
            if self.is_climbing:
                controller.hold_key_end("up")
                self.is_climbing = False

            if distance_to_rope > 0:
                controller.update_movement('left')  # 人在繩子右邊，往左走
            else:
                controller.update_movement('right') # 人在繩子左邊，往右走
        self.prev_y = gps_py

        return NodeStatus.RUNNING