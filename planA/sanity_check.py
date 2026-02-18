import torch
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import os
import cv2
import numpy as np
import matplotlib.pyplot as plt

# 設定路徑
DATA_DIR = "training_data"
IMG_DIR = os.path.join(DATA_DIR, "images")
LOG_FILE = os.path.join(DATA_DIR, "data_log.csv")

# 定義你的按鍵順序 (必須與 CSV 欄位順序一致)
KEY_COLUMNS = ['up', 'down', 'left', 'right', 'space', 'f', 's', 'a', 'g']

class MapleDataset(Dataset):
    def __init__(self, csv_file, img_dir, transform=None):
        self.annotations = pd.read_csv(csv_file)
        self.img_dir = img_dir
        self.transform = transform

    def __len__(self):
        return len(self.annotations)

    def __getitem__(self, index):
        # 讀取圖片路徑
        img_name = self.annotations.iloc[index, 0] # 第一欄是檔名
        img_path = os.path.join(self.img_dir, str(img_name))
        
        # 讀取圖片
        image = cv2.imread(img_path)
        if image is None:
            print(f"警告: 找不到圖片 {img_path}")
            # 回傳一個全黑圖片避免報錯，實際訓練時應該要清理掉壞資料
            image = np.zeros((224, 224, 3), dtype=np.uint8)
            
        # 轉換顏色 BGR -> RGB (因為 Matplotlib 和 PyTorch 喜歡 RGB)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # 讀取標籤 (從第二欄開始是按鍵狀態)
        labels = torch.tensor(self.annotations.iloc[index, 1:].values.astype(np.float32))

        if self.transform:
            image = self.transform(image)

        return image, labels, img_name

def visualize_sample():
    # 建立 Dataset
    dataset = MapleDataset(csv_file=LOG_FILE, img_dir=IMG_DIR)
    
    # 隨機抓 4 張圖來檢查
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    indices = np.random.choice(len(dataset), 4, replace=False)
    
    for ax, idx in zip(axes.flat, indices):
        image, label, name = dataset[idx]
        
        # 解析標籤：把 [1, 0, 0, 1...] 轉成文字 ['Up', 'Right']
        active_keys = [KEY_COLUMNS[i] for i, val in enumerate(label) if val == 1]
        label_text = "+".join(active_keys) if active_keys else "No Action"
        
        ax.imshow(image)
        ax.set_title(f"File: {name}\nAction: {label_text}", color='blue', fontsize=10)
        ax.axis('off')
    
    plt.tight_layout()
    plt.show()
    print(f"資料集總數: {len(dataset)} 張")

if __name__ == "__main__":
    visualize_sample()