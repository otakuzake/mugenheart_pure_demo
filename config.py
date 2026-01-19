import os
import sys

# ==========================================
# 📍 パス解決ロジック (内と外を使い分ける！)
# ==========================================
if getattr(sys, 'frozen', False):
    # 【EXE実行時】
    # 内部: EXEの中身（jsonなどの同梱ファイル）
    INTERNAL_DIR = sys._MEIPASS
    # 外部: EXEが置いてあるフォルダ（APIキーなど）
    EXTERNAL_DIR = os.path.dirname(sys.executable)
else:
    # 【開発時】どっちも同じ場所
    INTERNAL_DIR = os.path.dirname(os.path.abspath(__file__))
    EXTERNAL_DIR = INTERNAL_DIR

# ==========================================
# ⚙️ 設定値
# ==========================================

# ComfyUIのアドレス
# ★ここをブラウザで見た「8188」に合わせる！
COMFYUI_SERVER_ADDRESS = "127.0.0.1:8188"
CLIENT_ID = "MugenHeartClient"

# ★画像生成レシピ（EXEの中にある！）
WORKFLOW_FILE = os.path.join(INTERNAL_DIR, "workflow_t2i_sfw.json")

# プロンプトの接頭辞
PONY_PREFIX = "score_9, score_8_up, score_7_up, score_6_up, score_5_up, score_4_up, source_anime, rating_explicit, my_game_style, "

# APIキーは「EXEの外」にある！
API_KEY_PATH = os.path.join(EXTERNAL_DIR, "api_key.json")

# ==========================================
# 🎮 体験版モード設定
# ==========================================
IS_DEMO_MODE = True  # 体験版モード: TrueにするとComfyUIを使わず固定画像を使用
DEMO_HP_URL = "https://x.com/MugenH50915"  # 体験版終了後の公式Xリンク