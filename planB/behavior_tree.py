from enum import Enum

# 定義節點的執行狀態
class NodeStatus(Enum):
    SUCCESS = 1
    FAILURE = 2
    RUNNING = 3

# 所有節點的基礎類別 (Base Class)
class Node:
    def tick(self, context):
        """
        每次主迴圈呼叫時執行。必須被子類別覆寫。
        :param context: 存放全域資料的字典 (例如 gps_data, yolo_data, bot_instance)
        :return: NodeStatus
        """
        raise NotImplementedError("請在子類別實作 tick 方法")

# ==========================================
# 控制節點 (Control Flow Nodes)
# ==========================================
class Selector(Node):
    """
    選擇器 (OR)：由上往下執行子節點。
    - 遇到 SUCCESS 或 RUNNING，立刻回傳該狀態 (中斷後續節點)。
    - 遇到 FAILURE，繼續嘗試下一個子節點。
    - 全部 FAILURE，才回傳 FAILURE。
    （用途：處理不同優先級的任務，例如 保命 > Buff > 打怪）
    """
    def __init__(self, children):
        self.children = children

    def tick(self, context):
        for child in self.children:
            status = child.tick(context)
            if status != NodeStatus.FAILURE:
                return status
        return NodeStatus.FAILURE

class Sequence(Node):
    """
    序列 (AND)：由上往下執行子節點。
    - 遇到 FAILURE 或 RUNNING，立刻回傳該狀態 (中斷後續節點)。
    - 遇到 SUCCESS，繼續執行下一個子節點。
    - 全部 SUCCESS，才回傳 SUCCESS。
    （用途：處理嚴格的前置條件動作，例如 檢查有沒有怪 -> 走到怪面前 -> 攻擊）
    """
    def __init__(self, children):
        self.children = children

    def tick(self, context):
        for child in self.children:
            status = child.tick(context)
            if status != NodeStatus.SUCCESS:
                return status
        return NodeStatus.SUCCESS

class MemorySequence(Node):
    """
    記憶序列：會記住自己上次執行到哪一個子節點。
    - 如果子節點回傳 RUNNING，它也回傳 RUNNING (並記住位置)。
    - 如果子節點回傳 SUCCESS，它會把指標移到下一個子節點。
    - 全部子節點都 SUCCESS，它才回傳 SUCCESS，並將指標歸零。
    - 遇到 FAILURE，指標歸零，並回傳 FAILURE。
    （用途：用來執行「巡邏流程」，就算中途被打斷去放 Buff，回來還能繼續走）
    """
    def __init__(self, children):
        self.children = children
        self.current_idx = 0

    def tick(self, context):
        while self.current_idx < len(self.children):
            status = self.children[self.current_idx].tick(context)
            
            if status == NodeStatus.RUNNING:
                return NodeStatus.RUNNING
            elif status == NodeStatus.FAILURE:
                self.current_idx = 0 # 失敗就重置
                return NodeStatus.FAILURE
            elif status == NodeStatus.SUCCESS:
                self.current_idx += 1 # 成功就換下一個任務

        self.current_idx = 0 # 整個巡邏清單都做完了，完美重置！
        return NodeStatus.SUCCESS
# ==========================================
# 條件節點與行為節點 (葉節點 Leaf Nodes) - 範例
# ==========================================
# (我們之後會把 MapleBot 的邏輯包裝成這種節點)
# class CheckFallRecoveryNode(Node):
#     def tick(self, context):
#         gps_py = context['gps_py']
#         bot = context['bot']
        
#         if gps_py >= bot.LOWER_FLOOR_Y:
#             print("⚠️ [行為樹] 偵測到墜落，需要救援！")
#             return NodeStatus.SUCCESS # 條件成立，允許執行後續救援動作
#         return NodeStatus.FAILURE # 沒墜落，回傳失敗，讓 Selector 繼續往下看