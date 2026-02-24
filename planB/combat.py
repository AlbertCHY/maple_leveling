class CombatTargeting:
    def __init__(self, skill_range, foward_jump_attack_range, attack_range):
        """
        :param skill_range: 技能攻擊的距離範圍，如果怪物在這個範圍內，準備攻擊
        :param foward_jump_attack_range: 前跳攻擊的距離範圍，如果怪物在這個範圍內，使用前跳攻擊
        :param attack_range: 普通攻擊的距離範圍，如果怪物在這個範圍內，直接攻擊

        """
        self.skill_range = skill_range
        self.attack_range = attack_range

    @classmethod
    def from_config(cls, config):
        return cls(config["combat"]["skill_range"], 
                   config["combat"]["attack_range"])

    def find_target_and_check_range(self, player_pos, monsters_pos, direction):
        """
        :param player_pos: 玩家座標 (x, y)
        :param monsters_pos: 怪物陣列，格式為 [(x_center, y_center, w, h), ...]
        :param direction: 'right' 或 'left'
        :return: (目標怪物座標, 是否在攻擊範圍內)
        """
        if not player_pos or not monsters_pos:
            return None, False

        px, py, pw, ph = player_pos
        pcx = px + (pw // 2) # 玩家中心點 X 座標
        pcy = py + (ph // 2) # 玩家中心點 Y 座標
        valid_targets = []

        # 1. 根據巡邏方向過濾怪物
        for mx, my, mw, mh in monsters_pos:
            mcx = mx + (mw // 2) # 怪物中心點 X 座標
            mcy = my + (mh // 2) # 怪物中心點 Y 座標
            if direction == 'right' and mcx > pcx and abs(mcy - pcy) < 100: # 加入 Y 軸容差，避免選到上下太多的怪物
                valid_targets.append((mcx, mcy))
            elif direction == 'left' and mcx < pcx and abs(mcy - pcy) < 100:
                valid_targets.append((mcx, mcy))

        if not valid_targets:
            return False, None
        
        # 2. 找出距離最近的怪物 (基於中心點 X 座標差距)
        # 使用 lambda 函數快速按距離排序
        closest_monster = min(valid_targets, key=lambda m: abs(m[0] - pcx))
        mx, my = closest_monster

        # 3. 計算距離
        distance_to_monster = abs(mx - pcx)

        # 4. 判斷是否可以攻擊
        can_attack = distance_to_monster <= self.skill_range
        if can_attack:
            jump_or_not = False if distance_to_monster <= self.attack_range else True

        return can_attack, jump_or_not