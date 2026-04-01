import tkinter as tk
from pynput import keyboard
import threading
import time

class KeyVisualizer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("pydirectinput 除錯監控器")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.85)
        
        # 狀態儲存
        self.active_keys = set()
        self.last_action = "等待訊號..."
        
        self.keys_to_watch = {
            'a': 'A', 's': 'S', 'd': 'D', 'f': 'F', 'g': 'G',
            'space': 'Space', 'up': 'Up', 'left': 'Left', 'down': 'Down', 'right': 'Right'
        }
        
        self.labels = {}
        self.setup_ui()
        
        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()

    def setup_ui(self):
        frame = tk.Frame(self.root, bg="#1e1e1e", padx=15, pady=15)
        frame.pack()

        # 狀態列：顯示最後偵測到的動作
        self.status_label = tk.Label(frame, text=self.last_action, fg="#00FF00", bg="#1e1e1e", font=("Consolas", 10))
        self.status_label.grid(row=0, column=0, columnspan=3, pady=(0, 10))

        # 按鍵網格佈局
        layout = {
            'a': (1, 1), 's': (2, 0), 'd': (2, 1), 'f': (2, 2), 'g': (2, 3),
            'space': (3, 0, 3), 'up': (4, 0), 'left': (4, 1), 'down': (4, 2), 'right': (4, 3)
        }

        for key, pos in layout.items():
            col_span = pos[2] if len(pos) > 2 else 1
            lbl = tk.Label(frame, text=self.keys_to_watch[key], 
                          width=8 * col_span, height=2, 
                          fg="#888888", bg="#333333", font=("Arial", 9, "bold"))
            lbl.grid(row=pos[0], column=pos[1], columnspan=col_span, padx=2, pady=2)
            self.labels[key] = lbl

    def _get_key_name(self, key):
        """ 統一轉換鍵盤名稱，增加對 pydirectinput 的捕捉穩定度 """
        try:
            if hasattr(key, 'char') and key.char:
                return key.char.lower()
            k = str(key).replace('Key.', '').split('_')[0] # 處理 ctrl_l, shift_r 等
            return k.lower()
        except:
            return None

    def on_press(self, key):
        k = self._get_key_name(key)
        if k in self.labels:
            self.labels[k].config(bg="#FF5555", fg="white") # 按下時用紅色，更顯眼
            self.status_label.config(text=f"偵測到按下: {k}")

    def on_release(self, key):
        k = self._get_key_name(key)
        if k in self.labels:
            self.labels[k].config(bg="#333333", fg="#888888")
            self.status_label.config(text=f"偵測到放開: {k}")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = KeyVisualizer()
    app.run()