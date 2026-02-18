import time
import random
import cv2
import numpy as np
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
import win32gui, win32ui, win32con, win32api
import keyboard  # 用於模擬鍵盤與監聽熱鍵

# === 全域設定 ===
CONFIG = {
    "model_path": "maple_pilot_v1.pth",
    "target_keys": ['up', 'down', 'left', 'right', 'space', 'f', 's', 'a', 'g'],
    "resize_shape": (256, 448), 
    "device": "cuda" if torch.cuda.is_available() else "cpu",
    "thresholds": {
        'down': 0.85, 
        's': 0.40,     
        'g': 0.60,     
        'default': 0.50
    },
    # === 新增：攻擊節奏控制 ===
    "attack_cooldown": 0.5, # 按下攻擊後，幾秒內不準再按攻擊 (讓角色有時間走路)
    "move_only_window": 0.1 # 攻擊前是否強制先走一小段 (可選)
}

# === 1. 工具函式 ===
def human_key_press(key, hold_time=None):
    if hold_time is None:
        hold_time = random.uniform(0.05, 0.10)
    keyboard.press(key)
    time.sleep(hold_time)
    keyboard.release(key)

def release_all_keys():
    """放開所有定義的按鍵，避免卡鍵"""
    for k in CONFIG['target_keys']:
        keyboard.release(k)

# === 2. 節奏控制器 (解決原地發呆問題) ===
class ActionThrottler:
    def __init__(self):
        self.last_attack_time = 0
        # 定義哪些鍵是「攻擊類」，會造成硬直
        self.attack_keys = ['f', 's', 'a', 'g']
        
    def filter_actions(self, active_actions):
        """
        過濾 AI 的指令。如果剛攻擊過，強制過濾掉攻擊鍵，只保留移動鍵。
        """
        current_time = time.time()
        filtered_actions = []
        is_attacking_now = False

        # 檢查 AI 這次想不想攻擊
        for key in active_actions:
            if key in self.attack_keys:
                is_attacking_now = True
                break
        
        # 判斷是否在「強制冷卻期」
        if current_time - self.last_attack_time < CONFIG['attack_cooldown']:
            # 冷卻中：只允許非攻擊鍵 (移動、跳躍) 通過
            for key in active_actions:
                if key not in self.attack_keys:
                    filtered_actions.append(key)
            # (Debug用) 如果過濾了攻擊，可以在這裡 print
        else:
            # 非冷卻中：允許所有指令
            filtered_actions = active_actions
            
            # 如果這幀真的執行了攻擊，更新時間戳記
            if is_attacking_now:
                self.last_attack_time = current_time

        return filtered_actions

# === 3. 螢幕擷取 ===
def grab_screen(region=None):
    hwin = win32gui.GetDesktopWindow()
    if region:
        left, top, w, h = region
    else:
        w = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        h = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
        top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)

    hwindc = win32gui.GetWindowDC(hwin)
    srcdc = win32ui.CreateDCFromHandle(hwindc)
    memdc = srcdc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(srcdc, w, h)
    memdc.SelectObject(bmp)
    memdc.BitBlt((0, 0), (w, h), srcdc, (left, top), win32con.SRCCOPY)
    
    signedIntsArray = bmp.GetBitmapBits(True)
    img = np.frombuffer(signedIntsArray, dtype='uint8')
    img.shape = (h, w, 4)
    
    srcdc.DeleteDC()
    memdc.DeleteDC()
    win32gui.ReleaseDC(hwin, hwindc)
    win32gui.DeleteObject(bmp.GetHandle())

    return cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)

# === 4. Buff 管理器 (維持原樣) ===
class BuffManager:
    def __init__(self):
        self.base_interval = 270 
        self.random_window = 30
        self.buff_keys = ['q', 'w', 'e', 'r']
        self.schedule_next_run()

    def schedule_next_run(self):
        delay = self.base_interval + random.uniform(0, self.random_window)
        self.next_run_time = time.time() + delay
        print(f"[Buff] 下次施放: {time.strftime('%H:%M:%S', time.localtime(self.next_run_time))}")

    def check_and_execute(self):
        if time.time() > self.next_run_time:
            print("\n=== 啟動 Buff 模式 ===")
            release_all_keys()
            time.sleep(0.5)
            for key in self.buff_keys:
                human_key_press(key)
                time.sleep(0.5 + random.uniform(0, 0.2))
            print("=== Buff 完畢 ===\n")
            self.schedule_next_run()
            return True
        return False

# === 5. 模型載入 ===
def load_model():
    print("正在載入 EfficientNet-B0...")
    model = models.efficientnet_b0(weights=None)
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(in_features, len(CONFIG['target_keys']))
    
    model.load_state_dict(torch.load(CONFIG['model_path'], map_location=CONFIG['device']))
    model = model.to(CONFIG['device'])
    model.eval()
    
    preprocess = transforms.Compose([
        transforms.Resize(CONFIG['resize_shape']),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    return model, preprocess

# === 6. 主程式 ===
def main():
    model, preprocess = load_model()
    buff_manager = BuffManager()
    throttler = ActionThrottler() # 實例化節奏控制器
    
    # 請填入你的視窗座標
    GAME_REGION = (0, 40, 1366, 768) 
    
    print("=== MaplePilot 啟動 ===")
    print(" [F12]: 緊急停止並退出")
    print(" [F11]: 暫停/恢復 AI")
    print("請在 3 秒內切換視窗...")
    time.sleep(3) 

    is_paused = False

    with torch.no_grad():
        while True:
            # === 1. 緊急停止 (Solution 1) ===
            if keyboard.is_pressed('f12'):
                print("\n[緊急停止] 使用者按下 F12")
                release_all_keys()
                break
            
            # === 2. 暫停開關 ===
            if keyboard.is_pressed('f11'):
                is_paused = not is_paused
                print(f"\n[狀態切換] AI {'暫停中' if is_paused else '運作中'}")
                release_all_keys()
                time.sleep(0.5) # 防止連點

            if is_paused:
                time.sleep(0.1)
                continue

            # === 3. Buff 檢查 ===
            if buff_manager.check_and_execute():
                continue
            
            # === 4. AI 推論 ===
            loop_start = time.time()
            
            img_pil = Image.fromarray(grab_screen(GAME_REGION))
            input_tensor = preprocess(img_pil).unsqueeze(0).to(CONFIG['device'])
            
            if CONFIG['device'] == 'cuda':
                with torch.cuda.amp.autocast():
                    outputs = model(input_tensor)
            else:
                outputs = model(input_tensor)
            
            probs = torch.sigmoid(outputs).cpu().numpy()[0]
            
            # 取得原始 AI 建議的所有按鍵
            raw_actions = []
            for i, key in enumerate(CONFIG['target_keys']):
                threshold = CONFIG['thresholds'].get(key, CONFIG['thresholds']['default'])
                if probs[i] > threshold:
                    raw_actions.append(key)
            
            # === 5. 節奏控制 (Solution 2) ===
            # 這一步會把連續的攻擊指令過濾掉，強迫加入移動窗口
            final_actions = throttler.filter_actions(raw_actions)

            # === 6. 執行按鍵 ===
            # 我們需要遍歷「所有」可能的按鍵，更新它們的狀態 (按下或放開)
            for key in CONFIG['target_keys']:
                if key in final_actions:
                    keyboard.press(key)
                else:
                    keyboard.release(key)
            
            # 簡單的 Debug 顯示 (只顯示目前的動作)
            print(f"\r動作: {final_actions} \033[K", end="")
            
            # 控制頻率
            time.sleep(0.01)

    print("程式已結束。")

if __name__ == "__main__":
    main()