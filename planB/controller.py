import time
import random
import pydirectinput

class HumanizedController:
    def __init__(self):
        # 關閉 pydirectinput 預設的死板延遲
        pydirectinput.PAUSE = 0 

    def _sleep_gaussian(self, mu, sigma, min_val):
        """產生常態分佈的隨機延遲，模擬人類反應神經"""
        delay = random.gauss(mu, sigma)
        time.sleep(max(min_val, delay))

    def tap_key(self, key, press_time_mu=0.06, press_time_sigma=0.015):
        """模擬單次按鍵 (如：攻擊 F, 喝水, 瞬移 A)"""
        pydirectinput.keyDown(key)
        self._sleep_gaussian(press_time_mu, press_time_sigma, 0.03) # 鍵盤按壓時間
        pydirectinput.keyUp(key)
        self._sleep_gaussian(0.05, 0.02, 0.02) # 放開按鍵後的肌肉僵直/反應時間

    def hold_key_for(self, key, duration):
        """模擬長按按鍵 (如：走路)"""
        # duration 可以加入一點隨機抖動
        actual_duration = duration + random.uniform(-0.05, 0.05)
        pydirectinput.keyDown(key)
        time.sleep(max(0.1, actual_duration))
        pydirectinput.keyUp(key)
        self._sleep_gaussian(0.04, 0.01, 0.02)

    def jump_down(self):
        """模擬下跳 (下 + 跳)"""
        pydirectinput.keyDown('down')
        self._sleep_gaussian(0.05, 0.01, 0.03)
        self.tap_key('space')
        self._sleep_gaussian(0.1, 0.02, 0.05)
        pydirectinput.keyUp('down')

    def jump_teleport(self, teleport_key='a'):
        """模擬跳躍瞬移 (跳 + 瞬移)"""
        self.tap_key('alt') # 跳躍
        self._sleep_gaussian(0.08, 0.02, 0.05) # 空中的極短延遲
        self.tap_key(teleport_key)

    # def cast_buffs(self, keys):
    #     """模擬施放連續 Buff"""
    #     for key in keys:
    #         self.tap_key(key)
    #         self._sleep_gaussian(0.6, 0.1, 0.4) # Buff 之間的動畫延遲，需要根據遊戲實際情況調整
            
    def start_moving(self, direction):
        """模擬按下方向鍵不放"""
        pydirectinput.keyDown(direction)

    def stop_moving(self, direction):
        """模擬鬆開方向鍵"""
        pydirectinput.keyUp(direction)
        # 鬆開按鍵後，給予極短的神經反應延遲，防止鍵盤連擊誤判
        self._sleep_gaussian(0.04, 0.01, 0.02)

    def climb_rope(self, duration):
        """模擬按住上鍵爬繩"""
        pydirectinput.keyDown('up')
        self._sleep_gaussian(0.05, 0.01, 0.03) # 跳起來抓繩
        self.tap_key('space')
        self._sleep_gaussian(0.1, 0.02, 0.05)
        # 爬繩需要一段時間，加入一點隨機性
        actual_duration = duration + random.uniform(-0.1, 0.2)
        time.sleep(actual_duration)
        pydirectinput.keyUp('up')
        self._sleep_gaussian(0.05, 0.01, 0.03)