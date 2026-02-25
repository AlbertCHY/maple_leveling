import time
import random
import pydirectinput

class HumanizedController:
    def __init__(self):
        # 關閉 pydirectinput 預設的死板延遲
        pydirectinput.PAUSE = 0 

    def sleep_gaussian(self, mu, sigma, min_val):
        """產生常態分佈的隨機延遲，模擬人類反應神經"""
        delay = random.gauss(mu, sigma) # 以 mu 為平均值，sigma 為標準差產生隨機數
        time.sleep(max(min_val, delay)) # 確保不會小於 min_val 秒，以避免極端值

    def tap_key(self, key, press_time_mu=0.05, press_time_sigma=0.01):
        """模擬單次按鍵 (如：攻擊 技能)"""
        pydirectinput.keyDown(key)
        self.sleep_gaussian(press_time_mu, press_time_sigma, 0.04) # 鍵盤按壓時間
        pydirectinput.keyUp(key)
        self.sleep_gaussian(0.04, 0.01, 0.02) # 放開按鍵後的肌肉僵直/反應時間

    def jump_down(self):
        """模擬下跳 (下 + 跳)"""
        pydirectinput.keyDown("down")
        self.sleep_gaussian(0.05, 0.01, 0.03)
        self.tap_key("space")
        self.sleep_gaussian(0.08, 0.02, 0.05)
        pydirectinput.keyUp("down")
        self.sleep_gaussian(0.04, 0.01, 0.02)

    def jump_attack(self, direction, key, timming):
        """模擬向前跳躍攻擊 (跳 + 攻擊鍵)"""
        pydirectinput.keyDown(direction)
        self.sleep_gaussian(0.05, 0.01, 0.03)
        pydirectinput.keyDown("space")
        self.sleep_gaussian(0.05, 0.02, 0.05)
        pydirectinput.keyUp("space")
        self.sleep_gaussian(timming, 0.05, timming*0.9) # 根據 timming 參數調整攻擊按鍵的按下時間
        self.tap_key(key)
        pydirectinput.keyUp(direction)
        self.sleep_gaussian(0.04, 0.01, 0.02)

            
    def start_moving(self, direction):
        """模擬按下方向鍵不放"""
        pydirectinput.keyDown(direction)

    def stop_moving(self, direction):
        """模擬鬆開方向鍵"""
        pydirectinput.keyUp(direction)
        # 鬆開按鍵後，給予極短的神經反應延遲，防止鍵盤太頻繁輸入
        self.sleep_gaussian(0.04, 0.01, 0.02)

    def climb_rope(self, duration):
        """模擬跳起來抓繩並攀爬，duration 是攀爬的持續時間"""
        pydirectinput.keyDown("up")
        self.sleep_gaussian(0.05, 0.01, 0.04)
        self.tap_key("space")
        # 爬繩需要一段時間，加入一點隨機性
        actual_duration = duration + random.uniform(0, 0.1)
        time.sleep(actual_duration)
        pydirectinput.keyUp("up")
        self.sleep_gaussian(0.05, 0.01, 0.03)