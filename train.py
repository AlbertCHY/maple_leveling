import os
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader, random_split
from torchvision import models, transforms
from PIL import Image
from sklearn.model_selection import train_test_split
import time

# === 設定參數 ===
CONFIG = {
    "data_csv": "training_data/data_log.csv",
    "img_dir": "training_data/images",
    "batch_size": 32,
    "lr": 0.001,
    "epochs": 20,
    "model_save_path": "maple_pilot_v1.pth",
    "device": "cuda" if torch.cuda.is_available() else "cpu",
    # 這裡的順序必須跟你的 CSV header 完全一致
    "target_keys": ['up', 'down', 'left', 'right', 'space', 'f', 's', 'a', 'g']
}

# === 1. 自定義 Dataset ===
class MapleDataset(Dataset):
    def __init__(self, df, img_dir, transform=None):
        self.df = df
        self.img_dir = img_dir
        self.transform = transform
        self.target_cols = CONFIG["target_keys"]

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        # 讀取圖片路徑
        img_name = self.df.iloc[idx, 0] # 假設第一欄是檔名
        img_path = os.path.join(self.img_dir, str(img_name))
        
        # 讀取圖片 (使用 PIL 以配合 TorchVision Transforms)
        try:
            image = Image.open(img_path).convert('RGB')
        except:
            # 容錯處理：如果讀不到圖，給一張全白圖 (雖不完美但能防止崩潰)
            image = Image.new('RGB', (448, 256), (255, 255, 255))

        # 讀取標籤 (多標籤分類)
        labels = self.df.iloc[idx, 1:].values.astype('float32')
        
        if self.transform:
            image = self.transform(image)
            
        return image, torch.tensor(labels)

# === 2. 權重計算函數 (我們討論過的策略) ===
def calculate_pos_weights(df, device):
    target_keys = CONFIG["target_keys"]
    total_samples = len(df)
    
# 1. 計算正樣本數
    pos_counts = np.array([df[k].sum() for k in target_keys])
    
    # 2. 計算負樣本數 (Total - Pos)
    neg_counts = total_samples - pos_counts
    
    # 3. 使用標準公式: Neg / Pos
    # 加上 1e-5 避免除以 0
    weights = neg_counts / (pos_counts + 1e-5)
    
    # 轉成 Dictionary 方便操作
    weight_dict = dict(zip(target_keys, weights))
    
    # 4. 人工微調 (Game Logic Intervention)
    # 這裡的數值是基於「風險控管」而非純數學
    adjustments = {
        # === 高風險動作 (寧願不按，不可亂按 -> 調低) ===
        'down':  min(weight_dict['down'] * 0.7, 15.0), # 下跳很危險，打 7 折
        
        # === 困難特徵 (特徵太小，怕學不到 -> 調高) ===
        's':     weight_dict['s'] * 1.5, # 斬殺圖示太小，加權 1.5 倍
        
        # === 模糊特徵 (怪多怪少很主觀 -> 適度限制) ===
        'g':     min(weight_dict['g'], 30.0), # 限制最大值，避免太神經質
        
        # === 基礎動作 (維持原樣或設為 1) ===
        # 'f':     1.0,  # 攻擊通常不需要加權，因為樣本夠多
        # 'space': 1.0   # 跳躍同上
    }
    
    final_weights = []
    for k in target_keys:
        val = adjustments.get(k, weight_dict[k])
        # 限制最大權重，避免梯度爆炸
        final_weights.append(min(val, 50.0))
    
    print("\n[權重設定]")
    for k, w in zip(target_keys, final_weights):
        print(f"  {k}: {w:.2f}")
        
    return torch.tensor(final_weights).to(device)

# === 3. 訓練主流程 ===
def train_model():
    print(f"使用裝置: {CONFIG['device']}")
    
    # 讀取資料
    df = pd.read_csv(CONFIG['data_csv'])
    # 簡單清洗：確保欄位對應正確
    df = df[["image_file"] + CONFIG["target_keys"]]
    
    # 切分訓練集與驗證集 (80% / 20%)
    train_df, val_df = train_test_split(df, test_size=0.2, random_state=42)
    
    # 影像增強 (Augmentation)
    # 注意：不要隨便用 HorizontalFlip，因為 Left/Right 是不同標籤
    train_transforms = transforms.Compose([
        transforms.Resize((256, 448)),
        transforms.ColorJitter(brightness=0.2, contrast=0.2), # 模擬不同光影
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    
    val_transforms = transforms.Compose([
        transforms.Resize((256, 448)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    
    train_dataset = MapleDataset(train_df, CONFIG['img_dir'], transform=train_transforms)
    val_dataset = MapleDataset(val_df, CONFIG['img_dir'], transform=val_transforms)
    
    train_loader = DataLoader(train_dataset, batch_size=CONFIG['batch_size'], shuffle=True, num_workers=4, pin_memory=True)
    val_loader = DataLoader(val_dataset, batch_size=CONFIG['batch_size'], shuffle=False, num_workers=4, pin_memory=True)
    
    # === 模型定義 (Efficientnet B0) ===
    model = models.efficientnet_b0(weights='DEFAULT')
    
    # 修改最後一層全連接層
    in_features = model.classifier[1].in_features
    num_classes = len(CONFIG["target_keys"])
    model.classifier[1] = nn.Linear(in_features, num_classes)
    
    model = model.to(CONFIG['device'])
    
    # === Loss 與 Optimizer ===
    pos_weights = calculate_pos_weights(df, CONFIG['device'])
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weights)
    optimizer = optim.AdamW(model.parameters(), lr=CONFIG['lr'])
    
    # === 訓練迴圈 ===
    best_val_loss = float('inf')
    
    # 初始化混合精度工具
    scaler = torch.cuda.amp.GradScaler()

    for epoch in range(CONFIG['epochs']):
        start_time = time.time()
        model.train()
        train_loss = 0.0
        
        for images, labels in train_loader:
            images, labels = images.to(CONFIG['device']), labels.to(CONFIG['device'])
            
            optimizer.zero_grad()
            # 使用自動混合精度
            with torch.cuda.amp.autocast():
                outputs = model(images)
                loss = criterion(outputs, labels)

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            
            train_loss += loss.item() * images.size(0)
            
        train_loss /= len(train_dataset)
        
        # 驗證階段
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            with torch.cuda.amp.autocast():
                for images, labels in val_loader:
                    images, labels = images.to(CONFIG['device']), labels.to(CONFIG['device'])
                    outputs = model(images)
                    loss = criterion(outputs, labels)
                    val_loss += loss.item() * images.size(0)
        
        val_loss /= len(val_dataset)
        
        print(f"Epoch {epoch+1}/{CONFIG['epochs']} | "
              f"Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | "
              f"Time: {time.time()-start_time:.1f}s")
        
        # 儲存最佳模型
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), CONFIG['model_save_path'])
            print(f"  >>> 模型已儲存 (Val Loss: {val_loss:.4f})")
            
    print("=== 訓練完成 ===")

if __name__ == "__main__":
    # Windows 下多線程需要這行
    torch.multiprocessing.freeze_support()
    train_model()