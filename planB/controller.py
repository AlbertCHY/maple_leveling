import time
import random
import pydirectinput

class HumanizedController:
    def __init__(self):
        # 關閉 pydirectinput 預設的死板延遲
        pydirectinput.PAUSE = 0 
        self.current_movement = None

    def sleep_gaussian(self, mu, sigma, min_val):
        """產生常態分佈的隨機延遲，模擬人類反應神經"""
        delay = random.gauss(mu, sigma) # 以 mu 為平均值，sigma 為標準差產生隨機數
        time.sleep(max(min_val, delay)) # 確保不會小於 min_val 秒，以避免極端值

    def get_guassian(self, mu, sigma, min_val):
        delay = random.gauss(mu, sigma)
        return max(min_val, delay)

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
        #pydirectinput.keyUp(direction)
        self.sleep_gaussian(0.04, 0.01, 0.02)
    
    def hold_key_start(self, key):
        """模擬按住按鍵不放"""
        pydirectinput.keyDown(key)

    def hold_key_end(self, key):
        """模擬鬆開按住的按鍵"""
        pydirectinput.keyUp(key)
        # 鬆開按鍵後，給予極短的神經反應延遲，防止鍵盤太頻繁輸入
        self.sleep_gaussian(0.04, 0.01, 0.02)

    def update_movement(self, direction):
        if self.current_movement == direction:
            return
        if self.current_movement:
            self.hold_key_end(self.current_movement)
        if direction:
            self.hold_key_start(direction)
        self.current_movement = direction