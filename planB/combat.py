class CombatTargeting:
    def __init__(self, skill_range, penetration_ratio):
        """
        :param skill_range: 你的主要攻擊技能 (F) 的有效射程 (像素)
        :param penetration_ratio: 侵入係數 (0.0~1.0)，決定角色要多貼近怪物的視覺邊緣
        """
        self.skill_range = skill_range
        self.penetration_ratio = penetration_ratio

    def find_target_and_check_range(self, player_pos, monsters_data, patrol_direction):
        """
        :param player_pos: 玩家座標 (x, y)
        :param monsters_data: 怪物陣列，格式為 [(x_center, y_center, w, h), ...]
                              (注意：需要你在感知層把 YOLO 的 w, h 也傳過來)
        :param patrol_direction: 'right' 或 'left'
        :return: (目標怪物座標, 是否在攻擊範圍內)
        """
        if not player_pos or not monsters_data:
            return None, False

        px, py, _, _ = player_pos
        valid_targets = []

        # 1. 根據巡邏方向過濾怪物
        for mx, my, mw, mh in monsters_data:
            if patrol_direction == 'right' and mx > px and abs(my-py) < 100: # 加入 Y 軸容差，避免選到上下太多的怪物
                valid_targets.append((mx, my, mw, mh))
            elif patrol_direction == 'left' and mx < px and abs(my-py) < 100:
                valid_targets.append((mx, my, mw, mh))

        if not valid_targets:
            return None, False
        
        # 2. 找出距離最近的怪物 (基於中心點 X 座標差距)
        # 使用 lambda 函數快速按距離排序
        closest_monster = min(valid_targets, key=lambda m: abs(m[0] - px))
        mx, my, mw, mh = closest_monster

        # 3. 計算動態邊緣距離 (方案 B 核心邏輯)
        # 距離 = |玩家X - 怪物中心X| - (怪物寬度的一半 * (1 - 侵入係數))
        distance_to_edge = abs(px - mx) - ((mw / 2) * (1 - self.penetration_ratio))

        # 4. 判斷是否可以攻擊
        can_attack = distance_to_edge <= self.skill_range
        # print(f"🔍 目標怪物座標: ({mx}, {my}), {'可攻擊' if can_attack else '不可攻擊'}")
        return closest_monster, can_attack
