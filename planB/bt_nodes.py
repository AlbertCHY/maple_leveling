import time
import random
from behavior_tree import Node, NodeStatus


# ==========================================
# 1. 優先級中斷節點 (Interrupt Nodes)
# ==========================================
class FallRecoveryNode(Node):
    """底層救援節點 (包裝了 RopeUpNode)"""
    def __init__(self, activate_y, target_rope_x, target_floor_y, patrol_sequence, resume_index):
        self.activate_y = activate_y
        self.climb_node = RopeUpNode(target_rope_x, target_floor_y)
        self.patrol_sequence = patrol_sequence # 傳入巡邏序列的參考，讓它能夠修改巡邏流程的記憶位置
        self.resume_index = resume_index # 掉落救援結束後，巡邏流程要從哪個步驟繼續
        self.is_recovering = False

    def tick(self, context):
        gps_py = context.get("gps_py")

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
                
                print(f"✨ [{self.active_task.name}] 施放技能，按下按鍵: {key}")
                controller.update_movement(None) # 確保施法時不亂走
                controller.tap_key(key)
                
                # 設定下一個按鍵的等待時間 (加上常態分佈隨機性)
                delay = controller.get_guassian(self.active_task.base_cast_delay, 0.1, self.active_task.base_cast_delay-0.05)
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
    """雙向折返掃蕩清怪節點"""
    def __init__(self, platform_info, exit_x):
        self.platform_info = platform_info
        self.exit_x = exit_x
        self.is_attacking = False
        self.attack_end_time = 0

        self.attack_range = 30 # 根據攻擊距離提早結束
        
        # 決定初始清怪方向 (背對出口的方向)
        mid_x = (platform_info["x_min"] + platform_info["x_max"]) / 2
        self.phase = 1
        if self.exit_x > mid_x:
            # 出口偏右，先往左清
            self.direction = "left"
            self.bound_x = platform_info["x_min"] + self.attack_range
        else:
            # 出口偏左，先往右清
            self.direction = "right"
            self.bound_x = platform_info["x_max"] - self.attack_range
            
        # 賦予動態邊界 (加入常態分佈，防外掛偵測)
        self.dynamic_bound = random.randint(self.bound_x - 2, self.bound_x + 2)

    def tick(self, context):
        controller = context.get("controller")
        combat = context.get("combat")
        gps_px = context.get("gps_px")
        yolo_player = context.get("yolo_player")
        yolo_monsters = context.get("yolo_monsters")
        current_time = time.time()
        
        # ==========================================
        # 1. 戰鬥動畫狀態鎖
        # ==========================================
        if self.is_attacking:
            if current_time >= self.attack_end_time:
                self.is_attacking = False
            return NodeStatus.RUNNING
        
        # ==========================================
        # 2. 戰鬥大腦判定
        # ==========================================
        target_in_range, jump_or_not = combat.find_target_and_check_range(
            yolo_player, yolo_monsters, self.direction
        )

        if target_in_range:
            self.is_attacking = True
            self.attack_end_time = current_time + controller.get_guassian(0.75, 0.01, 0.7)
            controller.update_movement(None) 
            controller.tap_key('f')
            
            # if jump_or_not:
            #     print(f"⚔️ [{self.direction.upper()}] 前跳攻擊！")
            #     controller.jump_attack(self.direction, 'f', timming=0.01)
            # else:
            #     print(f"⚔️ [{self.direction.upper()}] 攻擊！")
            #     # controller.update_movement(None)
            #     controller.tap_key('f')
        else:
            # ==========================================
            # 3. 尋敵移動與邊界折返邏輯
            # ==========================================
            controller.update_movement(self.direction) 

            # 檢查是否到達當前方向的動態邊界
            if (self.direction == 'left' and gps_px <= self.dynamic_bound) or \
               (self.direction == 'right' and gps_px >= self.dynamic_bound):
                
                if self.phase == 1:
                    # 第一階段完成 (抵達遠離出口的盡頭)，準備折返！
                    print("🔄 抵達平台盡頭，開始折返清怪！")
                    self.phase = 2
                    self.direction = "right" if self.direction == "left" else "left"
                    controller.update_movement(self.direction)
                    
                    # 將目標邊界設為另一端的盡頭
                    self.bound_x = self.platform_info["x_max"] - self.attack_range if self.direction == "right" else self.platform_info["x_min"] + self.attack_range
                    self.dynamic_bound = random.randint(self.bound_x - 2, self.bound_x + 2)
                    
                elif self.phase == 2:
                    # 雙向清怪完畢！停下腳步並結束任務
                    print("✅ 平台掃蕩完畢！")
                    controller.update_movement(None)
                    return NodeStatus.SUCCESS 
            
        return NodeStatus.RUNNING

# class ClearPlatformNode(Node):
#     """平台清怪節點"""
#     def __init__(self, direction, bound_x):
#         self.direction = direction
#         self.bound_x = bound_x
#         self.dynamic_bound = self.bound_x + 10 if direction == "left" else self.bound_x - 10
#         self.is_attacking = False
#         self.attack_end_time = 0

#     def tick(self, context):
#         controller = context.get("controller")
#         combat = context.get("combat")
#         gps_px = context.get("gps_px")
#         yolo_player = context.get("yolo_player")
#         yolo_monsters = context.get("yolo_monsters")
#         current_time = time.time()
        
#         # 狀態檢查：如果正在攻擊，檢查動畫是否結束
#         if self.is_attacking:
#             if current_time >= self.attack_end_time:
#                 self.is_attacking = False
#                 return NodeStatus.RUNNING
#             return NodeStatus.RUNNING
        
#         # 呼叫戰鬥邏輯
#         target_in_range, jump_or_not = combat.find_target_and_check_range(
#             yolo_player, yolo_monsters, self.direction
#         )

#         if target_in_range:
#             self.is_attacking = True
#             self.attack_end_time = current_time + controller.get_guassian(0.7, 0.01, 0.65)
#             if jump_or_not:
#                 # print(f"⚔️ [{self.direction.upper()}] 前跳攻擊！")
#                 # controller.jump_attack(self.direction, "f", timming=0.01)
#                 pass
#             else:
#                 # print(f"⚔️ [{self.direction.upper()}] 攻擊！")
#                 # controller.update_movement(None)
#                 controller.tap_key("f")
#         else:
#             controller.update_movement(self.direction) # 繼續走
#             self.bomb_counter = 0

#             # 檢查是否到達邊界
#             if (self.direction == "left" and gps_px <= self.dynamic_bound) or \
#                (self.direction == "right" and gps_px >= self.dynamic_bound):
#                 controller.update_movement(None)
#                 self.dynamic_bound = random.randint(self.bound_x - 2, self.bound_x + 2) # 重新骰一次下次的邊界
#                 print("Platform Clean")
#                 return NodeStatus.SUCCESS # 走到盡頭了，任務完成！
            
#         return NodeStatus.RUNNING # 還在清怪中

class JumpDownNode(Node):
    """下跳節點"""
    def __init__(self, trigger_x, target_floor_y):
        self.trigger_x = random.randint(trigger_x - 3, trigger_x + 3)
        self.target_floor_y = target_floor_y - 10 # 忽視平台Y軸誤差

    def tick(self, context):
        controller = context.get("controller")
        gps_px = context.get("gps_px")
        gps_py = context.get("gps_py")

        # 如果已經到達目標樓層，重置狀態並回傳成功
        if gps_py >= self.target_floor_y:
            return NodeStatus.SUCCESS

        distance = gps_px - self.trigger_x

        # 抵達目標，停下腳步並執行下跳
        if abs(distance) <= 5:
            controller.update_movement(None)
            print(f"⬇️ 抵達下跳點 {self.trigger_x}，執行下跳！")
            controller.jump_down()
            time.sleep(0.6) # 等待落地動畫，防止半空連按
        # 前往下跳點
        else:
            if distance > 0:
                controller.update_movement("left")
            else:
                controller.update_movement("right")
            
        return NodeStatus.RUNNING

class JumpToPlatformNode(Node):
    """水平跳躍節點 (支援向左或向右跳)"""
    def __init__(self, trigger_x, direction, target_platform):
        self.trigger_x = random.randint(trigger_x - 3, trigger_x + 3)
        self.direction = direction
        self.target_platform = target_platform
        
        self.has_jumped = False
        self.jump_end_time = 0

    def tick(self, context):
        controller = context.get("controller")
        gps_px = context.get("gps_px")
        gps_py = context.get("gps_py")
        navigator = context.get("navigator")
        
        current_platform = navigator.get_current_platform(gps_px, gps_py)
        current_time = time.time()

        # 1. 如果已經成功抵達目標平台，提早結束！
        if current_platform == self.target_platform:
            controller.update_movement(None)
            self.has_jumped = False
            return NodeStatus.SUCCESS

        # 2. 如果已經起跳，處於空中滯留狀態
        if self.has_jumped:
            if current_time >= self.jump_end_time:
                # 動畫時間結束，回傳 SUCCESS 交給大腦判定有沒有真正成功
                return NodeStatus.SUCCESS 
            return NodeStatus.RUNNING

        # 3. 走向起跳點 (容差值設為 3 像素，避免因為速度過快錯過)
        distance = gps_px - self.trigger_x
        
        if abs(distance) <= 3:
            # 抵達起跳點，執行跳躍！
            # controller.update_movement(None) # 先停下腳步
            print(f"🦘 抵達起跳點 {self.trigger_x}，向 {self.direction} 跳躍！")
            
            # 模擬人類按鍵：按住方向鍵 -> 按跳 -> 鬆開方向鍵
            controller.hold_key_start(self.direction)
            controller.sleep_gaussian(0.05, 0.01, 0.03) 
            controller.tap_key("space")
            controller.hold_key_end(self.direction)
            
            self.has_jumped = True
            self.jump_end_time = current_time + 0.8 # 設定空中飛行的等待時間 (非阻塞)
        else:
            # 還沒到起跳點，繼續走
            controller.update_movement("left" if distance > 0 else "right")

        return NodeStatus.RUNNING

class RopeUpNode(Node):
    """導航爬繩節點"""
    def __init__(self, target_rope_x, target_floor_y):
        self.target_rope_x = target_rope_x
        self.target_floor_y = target_floor_y + 5 # 忽視平台Y軸誤差
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
            controller.update_movement(None) # 爬過一定高度才放開左右以解決在離繩子一定範圍內失去方向時的原地跳躍
            if self.prev_y == gps_py:
                self.finish_counter += 1
                if self.finish_counter >= 4: # Y變動停止超過4次刷新 當作爬完繩子
                    controller.hold_key_end("up")
                    self.finish_counter = 0
                    self.is_climbing = False
                    controller.sleep_gaussian(0.05, 0.01, 0.045)
                    return NodeStatus.SUCCESS
            else:
                self.finish_counter = 0

        # 找繩子並爬上去
        else:
            if abs(distance_to_rope) <= 10:
                if not self.is_climbing:
                    controller.tap_key("space")
                    controller.hold_key_start("up")
                    self.is_climbing = True
                    self.last_jump_time = current_time
                else:
                    if current_time - self.last_jump_time > 0.8:
                        # 如果已經在爬繩了，但 Y 座標沒有下降，重置爬繩狀態
                        if  gps_py > self.prev_y:
                            controller.hold_key_end("up")
                            self.is_climbing = False
            else:
                # 如果離開了繩子範圍，重置爬繩狀態
                if self.is_climbing:
                    controller.hold_key_end("up")
                    self.is_climbing = False

            if distance_to_rope > 1:
                controller.update_movement("left")  # 人在繩子右邊，往左走
            elif distance_to_rope < -1:
                controller.update_movement("right") # 人在繩子左邊，往右走
        self.prev_y = gps_py

        return NodeStatus.RUNNING
    
class DynamicPatrolNode(Node):
    def __init__(self, patrol_route):
        self.patrol_route = patrol_route  
        self.route_idx = 0                
        
        self.current_path = []            
        self.active_sub_node = None       
        
        # 記錄當前動作「合法」的所在平台
        self.expected_platforms = set()   

    def _find_nearest_route_index(self, current_platform, navigator, gps_x, gps_y):
        """計算巡邏清單中，離目前平台最近的目標"""
        if current_platform in self.patrol_route:
            return self.patrol_route.index(current_platform)
            
        min_dist = float("inf")
        best_idx = self.route_idx
        
        for idx, target_p in enumerate(self.patrol_route):
            path = navigator.find_path(current_platform, target_p)
            if path is not None:
                p_x, p_y = navigator.get_target_platform_xy(target_p)
                dist = abs(p_x - gps_x) + abs(p_y - gps_y)
                if dist < min_dist:
                    min_dist = dist
                    best_idx = idx
                
        return best_idx

    def tick(self, context):
        navigator = context.get("navigator")
        gps_px = context.get("gps_px")
        gps_py = context.get("gps_py")

        current_platform = navigator.get_current_platform(gps_px, gps_py)

        # ==========================================
        # 1. 檢查是否偏離路線
        # ==========================================
        if self.active_sub_node is not None and current_platform is not None:
            if current_platform not in self.expected_platforms:
                print(f"⚠️ 偏離路線！目前在 {current_platform}，預期在 {self.expected_platforms}")
                
                # 強制中斷當前動作與路徑
                self.active_sub_node = None
                self.current_path = []
                
                # 💡 動態重算最近的巡邏點
                self.route_idx = self._find_nearest_route_index(current_platform, navigator, gps_px, gps_py)
                print(f"🔄 重新規劃路線，改為前往最近的巡邏點: {self.patrol_route[self.route_idx]}")
                
                return NodeStatus.RUNNING

        # ==========================================
        # 2. 執行子動作
        # ==========================================
        if self.active_sub_node is not None:
            print(f"\r執行 {self.active_sub_node} \033[K", end="")
            status = self.active_sub_node.tick(context)
            if status == NodeStatus.SUCCESS:
                self.active_sub_node = None # 動作完成，清空狀態
            elif status == NodeStatus.FAILURE:
                self.active_sub_node = None
                self.current_path = [] # 動作失敗，清空路徑逼迫下一幀重算
            return NodeStatus.RUNNING

        # ==========================================
        # 3. 抵達目標平台，開始清怪
        # ==========================================
        target_platform = self.patrol_route[self.route_idx]

        if current_platform == target_platform:
            platform_info = navigator.platforms[current_platform]

            next_route_idx = (self.route_idx + 1) % len(self.patrol_route)
            next_target_platform = self.patrol_route[next_route_idx]

            lookahead_path = navigator.find_path(current_platform, next_target_platform)
            if lookahead_path:
                exit_x = lookahead_path[0].get("trigger_x")
            else:
                # 防呆：如果剛好是同一個平台或找不到路，以中心點為預設出口
                exit_x = (platform_info["x_max"] + platform_info["x_min"]) / 2

            print(f"🎯 抵達目標 {target_platform}，預判出口在 X={exit_x}，開始雙向清怪！")
            
            # 將平台資訊與出口 X 座標傳給清怪節點
            self.active_sub_node = ClearPlatformNode(platform_info, exit_x)
            
            self.expected_platforms = {current_platform}
            self.route_idx = next_route_idx # 切換到下一個目標
            return NodeStatus.RUNNING

        # ==========================================
        # 4. 需要大腦規劃路徑
        # ==========================================
        if not self.current_path and current_platform is not None:
            self.current_path = navigator.find_path(current_platform, target_platform)
            if not self.current_path:
                print(f"🚨 找不到從 {current_platform} 到 {target_platform} 的路徑！")
                return NodeStatus.FAILURE

        # ==========================================
        # 5. 按照路徑派發下一步動作
        # ==========================================
        if self.current_path:
            next_step = self.current_path.pop(0)
            target_p = next_step.get("to")
            _, platform_y = navigator.get_target_platform_xy(target_p)
            action = next_step.get("action")
            trigger_x = next_step.get("trigger_x")
            
            print(f"🚶 執行: {next_step["action"]} 前往 {target_p}")

            if action == "JUMP_DOWN":
                self.active_sub_node = JumpDownNode(trigger_x, platform_y)
            elif action == "CLIMB_ROPE":
                self.active_sub_node = RopeUpNode(trigger_x, platform_y)
            elif action in ["JUMP_LEFT", "JUMP_RIGHT"]:
                direction = "left" if action == "JUMP_LEFT" else "right"
                self.active_sub_node = JumpToPlatformNode(trigger_x, direction, target_p)

            # 💡 設定動作期間的合法平台：起點與終點都算合法
            self.expected_platforms = {current_platform, target_p}

        return NodeStatus.RUNNING