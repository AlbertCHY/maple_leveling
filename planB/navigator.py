import json
from collections import deque

class Navigator:
    def __init__(self, map_file_path):
        """讀取地圖地理資料並建立 NavGraph"""
        with open(map_file_path, "r", encoding="utf-8") as f:
            self.map_data = json.load(f)
            
        self.platforms = self.map_data.get("platforms", {})
        self.links = self.map_data.get("links", [])
        
        # 建立相鄰矩陣 (Adjacency List) 供 BFS 快速尋路
        # 格式: {"P_TOP": [{"to": "P_MID", "action": "JUMP_DOWN", "trigger_x": 170}], ...}
        self.graph = {p_id: [] for p_id in self.platforms.keys()}
        for link in self.links:
            self.graph[link["from"]].append(link)

    def get_current_platform(self, gps_px, gps_py):
        """
        根據當下的 GPS 座標，判斷玩家站在哪個平台上。
        """
        if gps_px is None or gps_py is None:
            return None
            
        for p_id, p_data in self.platforms.items():
            # 判斷 Y 軸是否在平台容差範圍內 (假設平台高度會有 ±3 的浮動)
            if abs(gps_py - p_data["y"]) <= 3:
                # 判斷 X 軸是否在平台左右邊界內
                if p_data["x_min"] <= gps_px <= p_data["x_max"]:
                    return p_id
        return None
    
    def get_target_platform_xy(self, target_p_id):
        platform_data = self.platforms[target_p_id]
        x = (platform_data["x_max"] + platform_data["x_min"]) / 2
        y = platform_data["y"]
        return x, y

    def find_path(self, start_p_id, target_p_id):
        """
        使用 BFS (廣度優先搜尋) 找出最短連線路徑
        :return: 動作清單，例如 [{"action": "JUMP_DOWN", "trigger_x": 170, "to": "P_MID"}, ...]
                 如果無法到達，回傳 None
        """
        if start_p_id == target_p_id:
            return [] # 已經在目標平台上了

        # BFS 佇列: 存放 (當前平台ID, 走到這的路徑清單)
        queue = deque([(start_p_id, [])])
        visited = set([start_p_id])

        while queue:
            current_p, current_path = queue.popleft()

            # 遍歷所有相鄰的連線 (可以去的下一個平台)
            for edge in self.graph.get(current_p, []):
                next_p = edge["to"]
                
                if next_p not in visited:
                    # 建立新的路徑紀錄
                    new_path = list(current_path) 
                    new_path.append(edge) # 紀錄需要執行的動作 (edge)
                    
                    # 如果找到目標了，立刻回傳這條路徑！
                    if next_p == target_p_id:
                        return new_path
                        
                    visited.add(next_p)
                    queue.append((next_p, new_path))
                    
        return None # 遍歷完整張圖都找不到路 (通常是 JSON 沒寫好斷線了)