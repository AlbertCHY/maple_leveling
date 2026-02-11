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
            # 容錯處理：如果讀不到圖，給一張全黑圖 (雖不完美但能防止崩潰)
            image = Image.new('RGB', (224, 224), (0, 0, 0))

        # 讀取標籤 (多標籤分類)
        labels = self.df.iloc[idx, 1:].values.astype('float32')
        
        if self.transform:
            image = self.transform(image)
            
        return image, torch.tensor(labels)

# === 2. 權重計算函數 (我們討論過的策略) ===
def calculate_pos_weights(df, device):
    target_keys = CONFIG["target_keys"]
    total_samples = len(df)
    
    # 計算每個類別的正樣本數
    pos_counts = [df[k].sum() for k in target_keys]
    
    # 基礎權重公式: Total / Positive
    # 避免除以 0
    weights = [total_samples / (c + 10) for c in pos_counts]
    
    # --- 人工微調區 (根據你的業務邏輯) ---
    weight_dict = dict(zip(target_keys, weights))
    
    # 覆蓋規則
    adjustments = {
        'down': 20.0,  # 下跳：稍微加強
        's':    40.0,  # 斬殺技：大幅加強
        'g':    25.0,  # 減防：適中
        'a':    15.0,  # 瞬移
        'space': 1.0,  # 基礎動作
        'f':     1.0   # 基礎動作
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
        transforms.Resize((224, 224)),
        transforms.ColorJitter(brightness=0.2, contrast=0.2), # 模擬不同光影
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    
    val_transforms = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    
    train_dataset = MapleDataset(train_df, CONFIG['img_dir'], transform=train_transforms)
    val_dataset = MapleDataset(val_df, CONFIG['img_dir'], transform=val_transforms)
    
    train_loader = DataLoader(train_dataset, batch_size=CONFIG['batch_size'], shuffle=True, num_workers=4, pin_memory=True)
    val_loader = DataLoader(val_dataset, batch_size=CONFIG['batch_size'], shuffle=False, num_workers=4, pin_memory=True)
    
    # === 模型定義 (MobileNetV3 Small) ===
    model = models.mobilenet_v3_small(weights='DEFAULT')
    
    # 修改最後一層全連接層
    # MobileNetV3 的分類器結構: classifier[3] 是最後一層 Linear
    in_features = model.classifier[3].in_features
    num_classes = len(CONFIG["target_keys"])
    model.classifier[3] = nn.Linear(in_features, num_classes)
    
    model = model.to(CONFIG['device'])
    
    # === Loss 與 Optimizer ===
    pos_weights = calculate_pos_weights(df, CONFIG['device'])
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weights)
    optimizer = optim.AdamW(model.parameters(), lr=CONFIG['lr'])
    
    # === 訓練迴圈 ===
    best_val_loss = float('inf')
    
    for epoch in range(CONFIG['epochs']):
        start_time = time.time()
        model.train()
        train_loss = 0.0
        
        for images, labels in train_loader:
            images, labels = images.to(CONFIG['device']), labels.to(CONFIG['device'])
            
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item() * images.size(0)
            
        train_loss /= len(train_dataset)
        
        # 驗證階段
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
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