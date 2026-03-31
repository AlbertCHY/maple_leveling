class CombatTargeting:
    def __init__(self, skill_range, safety_attack_range, y_diff):
        """
        :param safety_attack_range: 安全攻擊距離，從這個距離開始原地攻擊
        :param skill_range: 技能攻擊距離，在這個範圍內但是超過安全攻擊距離，則向前跳躍攻擊
        """
        self.skill_range = skill_range
        self.safety_attack_range = safety_attack_range
        self.y_diff = y_diff

    @classmethod
    def from_config(cls, config):
        return cls(config["combat"]["skill_range"], 
                   config["combat"]["safety_attack_range"],
                   config["combat"]["y_diff"])

    def find_target_and_check_range(self, player_pos, monsters_pos, direction):
        """
        :param player_pos: 玩家座標 (x_center, y_center, width, height)
        :param monsters_pos: 怪物陣列，格式為 [(x_center, y_center, w, h), ...]
        :param direction: "right" 或 "left"
        :return: (是否在攻擊範圍內, 是否需要跳躍攻擊)
        """
        if not player_pos or not monsters_pos:
            return False, False

        px, py, _, _ = player_pos
        valid_targets = []

        # 1. 根據巡邏方向與Y軸範圍過濾怪物
        for mx, my, mw, _ in monsters_pos:
            if direction == "right" and mx > px and abs(py - my) < self.y_diff:
                valid_targets.append((mx, my, mw))
            elif direction == "left" and mx < px and abs(py - my) < self.y_diff:
                valid_targets.append((mx, my, mw))

        if not valid_targets:
            return False, False
        # 2. 找出距離最近的怪物 (基於中心點 X 座標差距)
        # 使用 lambda 函數快速按距離排序
        closest_monster = min(valid_targets, key=lambda m: abs(m[0] - px))
        tx, ty, tw = closest_monster
        # print(f"玩家中心點: ({px}, {py}), 最近怪物中心點: ({tx}, {ty})\033[K", end="")
        # 3. 計算距離
        distance_to_monster = abs(tx - px) - tw/2 # 減去怪物寬度的一半，得到邊緣距離

        # 4. 判斷是否可以攻擊
        can_attack = distance_to_monster <= self.skill_range
        if can_attack and distance_to_monster <= self.safety_attack_range:
            use_jump_attack = False
        else:
            use_jump_attack = True

        return can_attack, use_jump_attack
    
    