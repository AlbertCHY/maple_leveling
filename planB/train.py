from ultralytics import YOLO

def main():
    # print("📥 步驟 1: 開始從 Roboflow 下載資料集...")
    # # ==========================================
    # # 請把下方這段替換成 Roboflow 網頁上提供給你的那串 Python 程式碼
    # # (注意：請確保不要洩漏你的私人 API Key 給別人，自己本機跑就好)
    # rf = Roboflow(api_key="你的_API_KEY")
    # project = rf.workspace("你的工作區").project("你的專案名稱")
    # version = project.version(1) # 看你是第幾個版本
    # dataset = version.download("yolov8")
    # # ==========================================
    # print(f"✅ 資料集已下載至: {dataset.location}")

    print("🚀 步驟 2: 載入 YOLOv8m 預訓練模型...")
    # 使用中型模型，獲得更好的特徵擷取能力
    model = YOLO('yolov8m.pt') 

    print("🔥 步驟 3: RTX 4070 啟動，開始正式訓練！")
    # 關鍵超參數設定
    results = model.train(
        data="roboflow/data.yaml", # 自動抓取剛剛下載的路徑
        epochs=150,      # 200張圖，我們跑 150 輪讓它充分學習
        imgsz=640,       # 保持 640x640 的標準輸入
        batch=16,        # 你的 RTX 4070 絕對吃得下 batch 16
        device=0,        # 使用你的 GPU
        workers=4,       # 資料載入的執行緒數量
        patience=30      # Early Stopping (防過擬合)：如果 30 輪都沒有進步，就提早結束
    )
    
    print("🎉 訓練大功告成！最好的權重已經存放在 runs/detect/train/weights/best.pt")

if __name__ == '__main__':
    main()