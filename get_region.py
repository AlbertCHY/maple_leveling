import pygetwindow as gw
import time

def find_game_window(window_title="MapleStory Worlds-Artale"):
    # 搜尋視窗
    windows = gw.getWindowsWithTitle(window_title)
    
    if not windows:
        print(f"錯誤：找不到標題包含 '{window_title}' 的視窗。請確認遊戲已開啟。")
        return None
    
    game_window = windows[0]
    
    # 視窗是否最小化？
    if game_window.isMinimized:
        print("偵測到遊戲視窗被最小化，正在還原...")
        game_window.restore()
        time.sleep(1)

    # 取得座標與尺寸
    # 注意：mss 的 region 格式為 {'top': y, 'left': x, 'width': w, 'height': h}
    # 但 pygetwindow 包含視窗邊框(標題列)，我們通常需要微調切掉邊框
    # 假設標題列約 30px, 左右邊框約 3-5px (視 Windows 設定而定)
    
    border_left = 8
    border_top = 30 # 標題列高度
    border_right = 8
    border_bottom = 8

    region = {
        "top": game_window.top + border_top,
        "left": game_window.left + border_left,
        "width": game_window.width - (border_left + border_right),
        "height": game_window.height - (border_top + border_bottom)
    }
    
    print(f"找到視窗: {game_window.title}")
    print(f"原始位置: {game_window.box}")
    print(f"建議設定的 SCREEN_REGION: {region}")
    return region

if __name__ == "__main__":
    find_game_window()