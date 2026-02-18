import time
import random

class BuffTask:
    def __init__(self, name, keys, window_start, window_end, base_cast_delay):
        """
        :param name: BUFF 名稱 (除錯用)
        :param keys: 技能按鍵列表，例如 ['q', 'w', 'e', 'r']
        :param window_start: 隨機觸發區間的下限 (秒)
        :param window_end: 隨機觸發區間的上限 (秒)
        :param base_cast_delay: 技能施放的基礎動畫時間
        """
        self.name = name
        self.keys = keys
        self.window_start = window_start
        self.window_end = window_end
        self.base_cast_delay = base_cast_delay
        
        # 初始化下一次施放時間 (為了讓程式一啟動就先上滿 BUFF，我們設定為現在)
        self.next_cast_time = time.time() + random.uniform(0, 3)

    def is_ready(self, current_time):
        """檢查是否已經到達計畫的施放時間"""
        return current_time >= self.next_cast_time

    def schedule_next(self, current_time):
        """安排下一次的施放時間"""
        # 在 4分30秒 (270秒) 到 5分鐘 (300秒) 之間隨機取一個值
        delay = random.uniform(self.window_start, self.window_end)
        self.next_cast_time = current_time + delay
        print(f"⏱️ [{self.name}] 下一次施放預計在 {delay:.1f} 秒後")

class BuffManager:
    def __init__(self, controller):
        """
        :param controller: 我們之前寫好的 HumanizedController 實例
        """
        self.controller = controller
        
        # 註冊所有的 BUFF 任務
        self.tasks = [
            # 5分鐘 BUFF: 區間設為 270秒 ~ 300秒
            BuffTask("5分鐘常規BUFF", ['q', 'w', 'e', 'r'], 270, 300, base_cast_delay=0.8),
            # 10分鐘 BUFF: 區間設為 570秒 ~ 600秒
            BuffTask("10分鐘攻擊力BUFF", ['pageup'], 570, 600, base_cast_delay=0.8)
        ]

    def check_and_cast(self):
        """
        在主迴圈中每一幀呼叫此方法。
        回傳 True 代表「剛剛放了 BUFF」，回傳 False 代表「沒事發生」。
        """
        current_time = time.time()
        buff_casted = False

        for task in self.tasks:
            if task.is_ready(current_time):
                print(f"\n✨ [狀態切換] 暫停動作，開始施放: {task.name} ({task.keys})")
                
                # 依序按下技能鍵
                for key in task.keys:
                    self.controller.tap_key(key)
                    
                    # 以 0.5 秒為基準，加入常態分佈的隨機波動 (標準差設為 0.1)
                    # max(0.4, ...) 是為了確保就算隨機到極端值，也不會低於 0.4 秒，以免按太快遊戲沒判定到
                    actual_delay = max(0.7, random.gauss(task.base_cast_delay, 0.1))
                    print(f"施放 {key} 後等待 {actual_delay:.2f} 秒")
                    time.sleep(actual_delay)
                
                # 施放完畢後，重新排程下一次的時間
                task.schedule_next(time.time())
                buff_casted = True
                
        return buff_casted