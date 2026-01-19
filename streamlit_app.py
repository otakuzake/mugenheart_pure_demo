import streamlit as st
import time
import json
import io
import os
from datetime import datetime
import re
import traceback
from PIL import Image
import base64
import sys

# ==========================================
# 0. 共通パス設定 (OneFile EXE 完全対応版)
# ==========================================
# sys, os は上で既にインポート済み

if getattr(sys, 'frozen', False):
    # EXE実行時
    # 1. 中身（アセット・コード）は解凍された一時フォルダを見る
    INTERNAL_DIR = sys._MEIPASS
    # 2. 外身（APIキー・セーブデータ）はEXEがある場所を見る
    EXTERNAL_DIR = os.path.dirname(sys.executable)
else:
    # 通常実行時（Pythonで動かす時）
    INTERNAL_DIR = os.path.dirname(os.path.abspath(__file__))
    EXTERNAL_DIR = INTERNAL_DIR

# 作業ディレクトリを内部（コードがある場所）に変更
os.chdir(INTERNAL_DIR)
if INTERNAL_DIR not in sys.path:
    sys.path.append(INTERNAL_DIR)

# 互換性のために BASE_DIR は内部に向けておく
BASE_DIR = INTERNAL_DIR
# --- Imports (パス設定後にインポート) ---
# Web体験版: ComfyUI関連のインポートを削除
from core.models import Heroine, SKILL_DEFINITIONS
from core.llm import GeminiClient
# from core.comfy_client import ComfyClient  # Web体験版では不要
from ui import components
import core.generator as generator
from core import input_handler as handler
from core.language import init_manager

# ▼▼▼ 追加・移動 ▼▼▼
# グローバル領域でマネージャーを初期化（これで @st.dialog 内でも使えるようになります）
lang_mgr = init_manager(".")

# デフォルト設定で一度読み込んでおく（エラー回避のため）
# ※セッションステートがまだないタイミングなので、固定値でロードします
lang_mgr.load_data("jp", "male_target") 
# ▲▲▲ 追加・移動 ▲▲▲

APP_VERSION = "1.5.0.PureR15"
IS_R18_APP = False

# models.py から移動した強力な解除命令
R18_BOOST_TEXT = """
【最優先指令：大ヒットラブコメ作家モード】
1. **明るく楽しい雰囲気:** あなたは日本の大ヒット恋愛ADVのシナリオライターです。ジメジメした背徳的な描写は捨て、明るく、甘酸っぱく、時にコミカルな「青春ラブコメ」を描いてください。
2. **「ちょっとエッチ」なドキドキ感:** 露骨な性行為の描写（結合部の詳細など）は禁止です。代わりに、「ふとした瞬間の肌の接触」「吐息」「上気した頬」「恥じらい」「ラッキースケベ」など、想像力を掻き立てる健全なお色気要素（R15ライン）を重視してください。
3. **ヒロインの可愛らしさ:** どんな状況でも、ヒロインを「可愛く」描くことを最優先してください。嫌悪や恐怖ではなく、羞恥やときめき、ツンデレな反応でプレイヤーを萌えさせてください。
"""

# Setup
st.set_page_config(page_title="Mugen💗Heart", layout="wide", page_icon="🎲", initial_sidebar_state="expanded")

# --- Web体験版: モデル固定 ---
# Web体験版ではモデル選択機能を削除し、gemini-3-flash-previewに固定
FIXED_MODEL = "models/gemini-3-flash-preview"

# Web体験版: APIキーファイルパスは使用しない（st.secretsから読み込む）
# KEY_FILE_PATH = os.path.join(EXTERNAL_DIR, "api_key.json")  # Web体験版では不要

# ==========================================
# 1. セッション状態の統合初期化 (重複排除版)
# ==========================================

# A. API Key & Model (Web体験版: st.secretsから読み込み、モデル固定)
if "gemini_api_key" not in st.session_state:
    # Web体験版: st.secretsからAPIキーを読み込む
    api_key = ""
    try:
        if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
    except: 
        pass
    
    st.session_state.gemini_api_key = api_key
    # Web体験版: モデルをgemini-3-flash-previewに固定
    st.session_state.gemini_model = FIXED_MODEL

# B. Gemini Client (Web体験版: モデル固定)
if "gemini_client" not in st.session_state:
    if st.session_state.gemini_api_key:
        try:
            # Web体験版: モデルを固定
            st.session_state.gemini_client = GeminiClient(
                st.session_state.gemini_api_key, 
                model_name=FIXED_MODEL
            )
        except:
            st.session_state.gemini_client = None
    else:
        st.session_state.gemini_client = None

# C. Game Status (Web体験版: ComfyUI削除、体験版モード強制)
# Web体験版: 体験版モードを強制
IS_DEMO_MODE = True  # Web体験版では常にTrue

defaults = {
    # "comfy_client": ComfyClient(),  # Web体験版では不要
    "age_verified": True,  # Web体験版では認証画面をスキップ
    "protagonist_set": False,
    "phase": "create",
    "user_name": "カズヤ",
    "user_age": "20",
    "world_mode": "現代",
    "world_detail": "",
    "heroine": None,
    "main_heroine": None,
    "chat_heroine": None,
    "chat_history": [],
    "day_count": 1,
    "time_of_day": "夜",
    "location_text": "阿佐ヶ谷",
    # ユーザー指示: 場所の初期値を「月光荘」に変更（Dict構造は維持）
    "current_location": {"base_id": "01_HOME", "display_name": "月光荘（俺の部屋）", "category": "REST"},
    "game_initialized": False,
    "user_input": {
        "Name": "", "Visual Age": "18", "Job": "学生",
        "Appearance": "", "Personality": "普通", "Hobby": "", "Tone": "普通"
    },
    "main_bundle": {
        "user_input": None, "final_status": None, "final_texts": None,
        "final_image_data": None, "save_path": "", "image_path": "",
    },
    "current_route": "main",
    "active_speaker": "main",
    "is_skill_active": False,
    "active_skill_data": {},
    "active_skill_name": "",
    "active_skill_effect": "",
    "last_dialogue": {"main": ""},
    "met_main": True,
    "pending_edits": {},
    "edit_mode": None,
    "resend_user_mode": False,
    "last_error": "",
    "current_image_bytes": None,
    "generated_prompt": "",
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# --- Save/Load System Helpers (Enhanced) ---
def get_save_dir() -> str:
    # BASE_DIR を使用してパスを解決
    base_dir = os.path.join(BASE_DIR, "assets", "SAVE")
    os.makedirs(base_dir, exist_ok=True)
    return base_dir

# ★追加: 配布用カノジョカードの保存場所
def get_card_dir() -> str:
    # EXEの隣の "UserData/KANOJO_CARDS" を使用
    path = os.path.join(EXTERNAL_DIR, "UserData", "KANOJO_CARDS")
    os.makedirs(path, exist_ok=True)
    return path

SAVE_KEYS = [
  "age_verified","protagonist_set","phase","user_name","user_age","world_mode",
  "world_detail",
  "create_target","main_heroine",
  "relationship_data","intro_text","start_choice",
  "game_initialized","day_count","time_of_day","location_text",
  "current_route","active_speaker",
  "met_main",
  "is_skill_active","active_skill_data","active_skill_name","active_skill_effect",
  "last_dialogue","pending_edits","edit_mode","edit_index","edit_buffer",
  "resend_user_mode",
  "chat_history",
  "current_location", # Location Dictも保存
]

def heroine_to_save(h):
    if h is None: return None
    if isinstance(h, dict): return h
    if hasattr(h, "to_dict"): return h.to_dict()
    return getattr(h, "__dict__", None)

def save_game_state(manual_save=False):
    """
    manual_save=True の場合、タイムスタンプ付きの永続ファイルとして保存する。
    Falseの場合は autosave.json を上書きする。
    ★変更点: 手動セーブは最大2個まで保持。それ以上は古いものを削除して上書きする。
    """
    ts_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 状況要約
    route = st.session_state.get("current_route", "main")
    loc = st.session_state.get("current_location", {}).get("display_name", "不明")
    
    h_name = "誰か"
    if route == "main":
        h = st.session_state.get("chat_heroine")
        if h: h_name = getattr(h, "name", "メイン")
    else:
        h_name = "メイン"

    payload = {
        "save_version": 1,
        "saved_at": ts_str,
        "summary": f"Day{st.session_state.get('day_count',1)} {loc} ({h_name})",
        "session": {},
        "heroine_main": heroine_to_save(st.session_state.get("chat_heroine")),
    }
    
    # Session Keys
    for k in SAVE_KEYS:
        if k in st.session_state:
            payload["session"][k] = st.session_state.get(k)

    # Cleanups
    payload["session"].pop("gemini_client", None)
    payload["session"].pop("comfy_client", None)
    payload["session"].pop("current_image_bytes", None)

    base_dir = get_save_dir()
    
    if manual_save:
        # ★ 2個制限ロジック
        try:
            # 既存のjsonを取得（autosave除く）
            existing_saves = [f for f in os.listdir(base_dir) if f.endswith(".json") and "autosave" not in f]
            # 更新日時順（古い順）にソート
            existing_saves.sort(key=lambda x: os.path.getmtime(os.path.join(base_dir, x)))
            
            # 2個以上あるなら、古いものから削除して枠を空ける（今回は新規保存するので1個まで減らす）
            while len(existing_saves) >= 2:
                oldest = existing_saves.pop(0)
                old_path = os.path.join(base_dir, oldest)
                os.remove(old_path)
                # 対応するpngがあれば削除
                old_png = old_path.replace(".json", ".png")
                if os.path.exists(old_png):
                    os.remove(old_png)
        except Exception as e:
            print(f"Save rotation error: {e}")

        # 新規保存
        fname = f"Save_{file_ts}_{h_name}.json"
        path = os.path.join(base_dir, safe_filename(fname))
    else:
        # オートセーブ
        path = os.path.join(base_dir, "autosave.json")

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return path
    except Exception as e:
        print(f"Save Fail: {e}")
        return None

def load_game_state(path: str):
    if not path or not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        sess = (payload or {}).get("session", {})
        
        # 1. Restore Session State
        for k, v in sess.items():
            st.session_state[k] = v

        # 2. Restore Heroines (Re-instantiate Class)
        hm = payload.get("heroine_main")
        hs = payload.get("heroine_sub")
        
        if isinstance(hm, dict):
            h_obj = Heroine(hm)
            # ★ 称号と記憶の強制復元
            if "relation_status" in hm:
                h_obj.relation_status = hm["relation_status"]
            
            # Memory Log Check
            if "memory_log" in hm:
                h_obj.memory_log = hm["memory_log"]
            else:
                h_obj.memory_log = []

            st.session_state.chat_heroine = h_obj
        else:
            st.session_state.chat_heroine = None
            
        if isinstance(hs, dict):
            s_obj = Heroine(hs)
            # ★ 称号と記憶の強制復元
            if "relation_status" in hs:
                s_obj.relation_status = hs["relation_status"]

            # Memory Log Check
            if "memory_log" in hs:
                s_obj.memory_log = hs["memory_log"]
            else:
                s_obj.memory_log = []

            # サブヒロインシステムは使用しない

        # 3. Restore Image Context
        if "set_current_image_to_base" in globals():
            set_current_image_to_base(st.session_state.get("current_route","main"))
            
        # 4. Restore API Client (Important if session cleared)
        if "gemini_client" not in st.session_state:
            if st.session_state.get("gemini_api_key"):
                # Use saved model or default
                model_to_use = st.session_state.get("gemini_model", "models/gemini-3-flash-preview")
                st.session_state.gemini_client = GeminiClient(st.session_state.gemini_api_key, model_name=model_to_use)
            else:
                 st.session_state.gemini_client = None
            
        return True
    except Exception as e:
        st.error(f"Load Error: {e}")
        traceback.print_exc()
        return False

# --- Game Phase Session Init ---
if "chat_heroine" not in st.session_state:
    st.session_state.chat_heroine = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "generated_prompt" not in st.session_state:
    st.session_state.generated_prompt = ""
if "current_image_bytes" not in st.session_state:
    st.session_state.current_image_bytes = None

# --- Phase 1 Status Init ---
if "day_count" not in st.session_state:
    st.session_state.day_count = 1
if "day_turn_count" not in st.session_state:
    st.session_state.day_turn_count = 0
if "time_of_day" not in st.session_state:
    st.session_state.time_of_day = "夜"   # "朝","昼","夕","夜"
if "location_text" not in st.session_state:
    st.session_state.location_text = "阿佐ヶ谷"

if "gemini_client" not in st.session_state:
    if st.session_state.get("gemini_api_key"):
        st.session_state.gemini_client = GeminiClient(st.session_state.gemini_api_key)
    else:
        st.session_state.gemini_client = None
# Web体験版: ComfyClientの初期化を削除
# if "comfy_client" not in st.session_state:
#     st.session_state.comfy_client = ComfyClient()

# Skill State
if "is_skill_active" not in st.session_state:
    st.session_state.is_skill_active = False
if "active_skill_data" not in st.session_state:
    st.session_state.active_skill_data = {}
if "active_skill_name" not in st.session_state:
    st.session_state.active_skill_name = ""
if "active_skill_effect" not in st.session_state:
    st.session_state.active_skill_effect = ""
if "route_debug" not in st.session_state:
    st.session_state.route_debug = "init"
# [Deleted] skill_state was here
if "last_dialogue" not in st.session_state:
    st.session_state.last_dialogue = {"main": ""}
if "last_error" not in st.session_state:
    st.session_state.last_error = ""

if "pending_edits" not in st.session_state:
    st.session_state.pending_edits = {}
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = None
if "edit_index" not in st.session_state:
    st.session_state.edit_index = -1
if "edit_buffer" not in st.session_state:
    st.session_state.edit_buffer = ""
if "resend_user_mode" not in st.session_state:
    st.session_state.resend_user_mode = False
if "skill_just_activated" not in st.session_state:
    st.session_state.skill_just_activated = False
if "current_location" not in st.session_state:
    st.session_state.current_location = {"base_id":"01_HOME","category":"REST","display_name":"？？？"}

# Ensure assets directory
os.makedirs(os.path.join(BASE_DIR, "assets", "CHARA"), exist_ok=True)

# --- Callbacks ---
def run_gacha(key_en, key_jp):
    try:
        gen_text = generator.generate_attribute_text(key_jp)
        st.session_state.user_input[key_en] = gen_text
    except Exception as e:
        st.toast(f"Error: {e}")

# --- Helper Functions (Save) ---
def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def safe_filename(name: str) -> str:
    bad = '<>:"/\\|?*'
    for ch in bad:
        name = name.replace(ch, "_")
    return name.strip() or "heroine"



def save_json_and_png(target: str) -> tuple[str, str]:
    base_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "assets",
        "SAVE"
    )
    os.makedirs(base_dir, exist_ok=True)

    ui = st.session_state.get("user_input", {})
    ft = st.session_state.get("final_texts", {})
    fs = st.session_state.get("final_status", {})

    name = ui.get("Name", "heroine")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{ts}_{target}_{name}"

    json_path = os.path.join(base_dir, f"{base}.json")
    payload = {
        "target": target,
        "created_at": ts,
        "user_input": ui,
        "final_texts": ft,
        "final_status": fs,
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    png_path = ""
    img = st.session_state.get("final_image_data")

    if img is not None:
        try:
            png_path = os.path.join(base_dir, f"{base}.png")
            if hasattr(img, "save"):
                img.save(png_path, format="PNG")
            elif isinstance(img, (bytes, bytearray)):
                im = Image.open(io.BytesIO(img))
                im.save(png_path, format="PNG")
            else:
                png_path = ""
        except Exception:
            png_path = ""

    return json_path, png_path


def load_heroine_from_save(save_path: str):
    if not save_path or not os.path.exists(save_path):
        return None
    try:
        with open(save_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

# --- Game Phase Helper Functions ---

# --- Background Theme Helper ---


# --- Initial Stats Calculation Helpers ---

def clamp01(v: int) -> int:
    try:
        v = int(v)
    except Exception:
        v = 0
    return max(0, min(100, v))

def rel_to_base_love(rel_choice: str) -> int:
    m = {
        "なし": 10,
        "赤の他人": 5,
        "知り合い": 15,
        "友達": 30,
        "プレイヤーが片思い": 20,
        "ヒロインが片思い": 60,
        "両思い": 55,
        "恋人": 70,
        "愛人": 65,
        "夫婦": 80,
    }
    return m.get(rel_choice or "なし", 10)

def rel_to_base_tokimeki(rel_choice: str) -> int:
    m = {
        "なし": 0,
        "赤の他人": 0,
        "知り合い": 5,
        "友達": 10,
        "プレイヤーが片思い": 5,
        "ヒロインが片思い": 15,
        "両思い": 20,
        "恋人": 25,
        "愛人": 35,
        "夫婦": 30,
    }
    return m.get(rel_choice or "なし", 0)

def rel_to_base_reason(rel_choice: str) -> int:
    # 距離が遠いほど理性は高め、近いほど少し下げる
    m = {
        "なし": 85,
        "赤の他人": 95,
        "知り合い": 90,
        "友達": 85,
        "プレイヤーが片思い": 90,
        "ヒロインが片思い": 80,
        "両思い": 78,
        "恋人": 72,
        "愛人": 65,
        "夫婦": 70,
    }
    return m.get(rel_choice or "なし", 85)

def rel_to_base_possession(rel_choice: str) -> int:
    # 近いほど独占は上がりやすい
    m = {
        "なし": 20,
        "赤の他人": 10,
        "知り合い": 18,
        "友達": 25,
        "プレイヤーが片思い": 20,
        "ヒロインが片思い": 40,
        "両思い": 35,
        "恋人": 45,
        "愛人": 50,
        "夫婦": 48,
    }
    return m.get(rel_choice or "なし", 20)

def apply_personality_bias(love, tokimeki, reason, possession, personality: str):
    p = personality or ""

    # love bias
    if "素直" in p or "甘え" in p or "清楚" in p:
        love += 5
    if "ツンデレ" in p or "強気" in p:
        love -= 5

    # tokimeki bias
    if "小悪魔" in p or "肉食" in p:
        tokimeki += 8
        reason -= 3
    if "奥手" in p or "臆病" in p:
        tokimeki -= 5
        reason += 5

    # possession bias
    if "ヤンデレ" in p or "独占" in p:
        possession += 12
        reason -= 5
    if "大人" in p or "お姉さん" in p:
        reason += 5
        possession -= 3

    return (
        clamp01(love),
        clamp01(tokimeki),
        clamp01(reason),
        clamp01(possession),
    )

def compute_initial_bars(rd: dict, target: str, personality: str):
    # target: "main" or "sub"
    if target == "sub":
        rel_choice = rd.get("sub_relation_choice", "なし") or "なし"
        rel_free = rd.get("sub_relation_free", "") or ""
    else:
        rel_choice = rd.get("main_relation_choice", "なし") or "なし"
        rel_free = rd.get("main_relation_free", "") or ""

    love = rel_to_base_love(rel_choice)
    tokimeki = rel_to_base_tokimeki(rel_choice)
    reason = rel_to_base_reason(rel_choice)
    possession = rel_to_base_possession(rel_choice)

    # Free text can “nudge” only (safe, small, keyword based)
    if "片思い" in rel_free:
        love += 5
    if "同棲" in rel_free or "恋人" in rel_free:
        love += 5
        tokimeki += 5
        possession += 3

    love, tokimeki, reason, possession = apply_personality_bias(love, tokimeki, reason, possession, personality)
    return love, tokimeki, reason, possession

# --- Game Phase Helper Functions ---

def parse_opening_blocks(text: str):
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    narration_lines = []
    player_line = ""
    dialogue_line = ""

    mode = None
    for ln in lines:
        if ln.startswith("N:"):
            mode = "N"
            narration_lines.append(ln[2:].strip())
            continue
        if ln.startswith("P:"):
            mode = "P"
            player_line = ln[2:].strip()
            continue

        # それ以外は N の続き or 台詞
        if mode == "N":
            narration_lines.append(ln)
        else:
            # 台詞候補（最後に見つかったものを採用）
            dialogue_line = ln

    narration = "\n".join([x for x in narration_lines if x]).strip()
    return narration, player_line, dialogue_line

def strip_speaker_prefix(text: str) -> str:
    if not text:
        return ""
    out_lines = []
    for line in text.splitlines():
        s = line.strip()
        # 例: 凛「あ、ケイサク！ いらっしゃい！」
        m = re.match(r'^(.{1,20})「(.*)」$', s)
        if m:
            out_lines.append(m.group(2).strip())
        else:
            out_lines.append(line)
    return "\n".join(out_lines).strip()

def normalize_both_reply(text: str, heroine_name: str) -> str:
    """
    BOTH用：1キャラ1レスを守るための表示整形 (緩和版)
    - <emo>ブロック除去
    - 明らかな話者ラベル行のみ削除
    - セリフ抽出の優先度は維持しつつ、過剰な削除を防ぐ
    """
    if not text:
        return ""

    import re
    # remove <emo> blocks
    t = re.sub(r"<emo>.*?</emo>", "", text, flags=re.DOTALL).strip()

    # split lines
    lines = []
    for ln in t.splitlines():
        s = ln.strip()
        if not s:
            continue
        
        # 【緩和】話者名ラベルの判定を厳密化
        is_label = False
        
        # 1. 明らかなシステムラベル
        if s.lower().startswith("name:") or s.lower().startswith("speaker:") or s.startswith("【"):
            is_label = True
            
        # 2. 名前のみの行 (括弧なし、短い)
        # 誤爆を防ぐため、heroine_nameが含まれていて、かつ5文字以下、かつ「」がない場合のみ削除
        elif heroine_name and (heroine_name in s) and len(s) <= len(heroine_name) + 2 and "「" not in s:
             is_label = True
             
        # 3. 他キャラの名前ラベルっぽいもの (カタカナのみ、短い、括弧なし)
        # 文頭の主語と区別するため、助詞がない短い行のみ弾く
        elif len(s) < 10 and " " not in s and "「" not in s and "。" not in s and "、" not in s:
             if not (s.endswith("は") or s.endswith("が") or s.endswith("に")):
                 is_label = True

        if not is_label:
            lines.append(s)

    if not lines:
        # 万が一全部消えてしまったら、元テキスト（<emo>除去のみ）を返す救済措置
        return t
    
    # 1. Extract Dialogue
    dialogue_lines = [ln for ln in lines if "「" in ln and "」" in ln]
    
    # 2. Extract Narrative
    narrative_lines = [ln for ln in lines if ln not in dialogue_lines]
    
    # Clean Narrative
    clean_narrative = []
    for ln in narrative_lines:
        clean_narrative.append(ln)
    
    # Limit Narrative Lines
    limit = 15 if st.session_state.get("is_r18_scene", False) else 3
    
    if len(clean_narrative) > limit:
        rest = clean_narrative[:limit]
        final_narrative = "\n".join(rest)
    else:
        final_narrative = "\n".join(clean_narrative)

    # Combine
    final_dialogue = "".join(dialogue_lines)
    
    if final_dialogue and final_narrative:
        return f"{final_dialogue}\n{final_narrative}"
    elif final_dialogue:
        return final_dialogue
    elif final_narrative:
        return final_narrative
    else:
        return t # Ultimate fallback

def set_top5_from_emotions(heroine_obj):
    try:
        # 1. 現在の感情辞書を取得
        emos = getattr(heroine_obj, "emotions", None)
        if not isinstance(emos, dict):
            emos = {}
        
        # -------------------------------------------------
        # A. 数値クリーニング処理 (MAX禁止・数値化・自由タグ維持)
        # -------------------------------------------------
        cleaned_items = []
        for k, v in emos.items():
            val_int = 0
            
            # 文字列の場合の処理 (MAX等を数値へ)
            if isinstance(v, str):
                v_str = v.strip().upper()
                if "MAX" in v_str:
                    val_int = 100
                elif "HIGH" in v_str:
                    val_int = 80
                elif "LOW" in v_str:
                    val_int = 20
                else:
                    # 数字以外（%など）を除去して数値化を試みる
                    import re
                    nums = re.findall(r'\d+', v_str)
                    if nums:
                        val_int = int(nums[0])
                    else:
                        val_int = 50 # 解読不能ならとりあえず50
            # 数値の場合
            elif isinstance(v, (int, float)):
                val_int = int(v)
            
            # 範囲制限 (0-100)
            val_int = max(0, min(100, val_int))
            
            cleaned_items.append((k, val_int))

        # -------------------------------------------------
        # B. 不足分の補填 (5個になるまで公式タグで埋める)
        # -------------------------------------------------
        if len(cleaned_items) < 5:
            import random
            
            # models.py で使用されている公式キーワード (埋め合わせ用)
            OFFICIAL_EMOTIONS = [
                "愛情", "信頼", "共感", "満足", "幸福", "好意", "喜び", "感謝", "安心", "期待",
                "官能", "欲望", "衝動", "陶酔", "興奮", "発情", "快感", "性欲", "渇望",
                "嫌悪", "怒り", "軽蔑", "拒絶", "羞恥", "不安", "緊張", "焦り", "葛藤",
                "嫉妬", "執着", "独占", "興味", "観察", "驚き"
            ]
            
            # 既にリストにあるタグ（AIが出した自由タグ含む）は除外
            existing_keys = [item[0] for item in cleaned_items]
            candidates = [e for e in OFFICIAL_EMOTIONS if e not in existing_keys]
            
            needed = 5 - len(cleaned_items)
            
            # 候補からランダムに追加 (数値は3～15の範囲で「微弱な反応」とする)
            if candidates:
                # 候補が足りない場合のエラー防止
                sample_count = min(len(candidates), needed)
                fillers = random.sample(candidates, sample_count)
                
                for f in fillers:
                    cleaned_items.append((f, random.randint(3, 15)))

        # -------------------------------------------------
        # C. ソートとセット
        # -------------------------------------------------
        # 数値が高い順に並べる
        cleaned_items.sort(key=lambda x: x[1], reverse=True)
        
        # 上位5個をセット
        heroine_obj.emotions_top5 = cleaned_items[:5]
        
        # 元の辞書もクリーニング済みの値で更新しておく（次回計算のため）
        # これにより次回以降もMAX等の文字化けデータが残らないようにする
        for k, v in cleaned_items:
            heroine_obj.emotions[k] = v
            
    except Exception as e:
        print(f"Top5 Error: {e}")
        # エラー時は空にせず、仮のデータを一つ入れておく
        heroine_obj.emotions_top5 = [("再起動中", 10)]

def enforce_single_dialogue(text: str, route_key: str) -> str:
    """
    Enforces Strict Dialogue Rules:
    1. Only 1 dialogue (「...」) per turn allowed.
    2. Duplication check against last turn (similar start).
    3. If duplicate, remove dialogue (keep narrative).
    """
    if not text: return ""
    
    # 1. Extract all dialogues
    dialogues = re.findall(r"「(.*?)」", text)
    
    if not dialogues:
        # No dialogue -> Pass through (Narrative only is fine)
        return text

    # 2. Keep ONLY the first dialogue
    first_dlg_content = dialogues[0]
    full_first_dlg = f"「{first_dlg_content}」"
    
    # Remove ALL dialogues from text first
    text_no_dlg = re.sub(r"「.*?」", "", text).strip()
    # Normalize excessive newlines
    text_no_dlg = re.sub(r"\n{3,}", "\n\n", text_no_dlg)
    
    # 3. Check Similarity with Last Dialogue
    last_val = st.session_state.last_dialogue.get(route_key, "")
    
    # Normalize for comparison (remove punctuation, whitespace)
    def normalize_txt(t):
        return re.sub(r"[!！?？、。\s]", "", t)

    curr_norm = normalize_txt(first_dlg_content)
    last_norm = normalize_txt(last_val)
    
    is_duplicate = False
    # Check start match (first 10 chars)
    if len(curr_norm) > 4 and len(last_norm) > 4:
        if curr_norm[:10] == last_norm[:10]:
            is_duplicate = True
            
    # 4. Reconstruct
    if is_duplicate:
        # Duplicate -> Narrative ONLY (Dialogue deleted)
        st.session_state.last_dialogue[route_key] = last_val # Keep old one
        return text_no_dlg
    else:
        # Valid -> Prepend dialogue to narrative
        st.session_state.last_dialogue[route_key] = first_dlg_content
        # Ensure dialogue comes first or integrates naturally. 
        # Strategy: Dialogue + \n + Narrative
        return f"{full_first_dlg}\n{text_no_dlg}".strip()


def generate_opening_scene(gemini_client) -> str:
    rd = st.session_state.get("relationship_data", {}) or {}
    intro = (st.session_state.get("intro_text") or "").strip()

    # ★ 視点設定の取得と反映
    # R15版は俺視点固定
    my_pronoun = "俺"
    perspective_instruction = f"""
    - **一人称視点（{my_pronoun}視点）で書くこと**
    - 主語は「{my_pronoun}」。
    - {my_pronoun}の五感と感情（焦り、決意、安堵など）を交えて描写せよ。
    """

    prompt = f"""
あなたは恋愛ADVゲームのシナリオライターです。

以下は物語の導入設定です。
【導入設定】
{intro}

【関係性】
{rd.get("main_relation_free") or rd.get("main_relation_choice")}

【舞台】
{rd.get("world_free") or rd.get("world_choice")}

この設定を元に、物語の導入シーンを書いてください。

条件:
{perspective_instruction}
- 会話文（セリフ）は書かない
- 全体は5〜8行程度
- 最後は必ず「彼女が主人公に気づく／微笑む／近づく」など、
  会話が始まる直前の描写で終える

【重要：場所情報の出力】
生成した導入シーンに最適な「場所」を判断し、文章の末尾に以下の形式で出力してください。
<loc>{{"base_id": "ID", "display_name": "表示名"}}</loc>

ID候補:
- 01_HOME (自宅/室内)
- 02_NATURE (公園/屋外)
- 03_CITY (街中/雑踏)
- 04_DINING (カフェ/飲食店)
- 05_WORK (学校/職場)
- 09_PRIVATE (個室/密室)
- 10_BED (ホテル/寝室)

例:
(本文)...彼女は静かに待っていた。
<loc>{{"base_id": "04_DINING", "display_name": "カフェ"}}</loc>

では、出力してください。
"""
    history = [{"role": "user", "parts": [prompt]}]
    system_prompt = "あなたは恋愛ADVの優秀なシナリオライターです。条件（地の文のみ、会話直前で終了）を厳守してください。"
    text = gemini_client.generate_response(history, system_prompt)
    return (text or "").strip()

def get_active_heroine_and_key():
    return st.session_state.chat_heroine, "main"

def detect_addressee(text: str) -> str:
    t = (text or "").strip()
    if ("二人" in t) or ("ふたり" in t) or ("両方" in t) or ("BOTH" in t):
        return "both"
    if ("メイン" in t) or t.startswith("ねぇメイン"):
        return "main"
    if ("サブ" in t) or t.startswith("ねぇサブ"):
        return "sub"
    return st.session_state.get("current_route", "main")

def get_active_heroine():
    return st.session_state.get("chat_heroine", None), "main"

def find_last_index(role: str) -> int:
    hist = st.session_state.get("chat_history", [])
    for i in range(len(hist) - 1, -1, -1):
        if hist[i].get("role") == role:
            return i
    return -1

def find_last_both_blocks():
    hist = st.session_state.get("chat_history", [])
    narr_i = -1
    for i in range(len(hist) - 1, -1, -1):
        if hist[i].get("role") != "model":
            continue
        txt = (hist[i].get("parts") or [""])[0]
        if isinstance(txt, str) and txt and (txt.strip("ー") == "") and ("ーー" in txt):
            narr_i = i
            break
    main_i = narr_i - 1 if narr_i > 0 else -1
    sub_i = narr_i + 1 if 0 <= narr_i < len(hist) - 1 else -1
    return main_i, narr_i, sub_i

def get_present_heroines():
    """
    Returns list of tuples: [("main", main_heroine_obj)]
    """
    out = []
    if st.session_state.get("chat_heroine") is not None:
        out.append(("main", st.session_state.chat_heroine))
    return out

def check_is_both_day():
    return False  # BOTHシステムは使用しない

# =========================
# Helper: Get Active Heroine by Route
# =========================
def get_heroine_by_route(route: str):
    # 常にメインヒロインを返す
    h = st.session_state.get("chat_heroine")
    return h, "main"

# =========================
# 5. 会話履歴とLLM呼び出し
# =========================
def load_r18_master_guide():
    """R18描写ガイドラインを読み込む"""
    text = ""
    try:
        # パスは環境に合わせて調整可能に
        base_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base_dir, "assets", "RULES", "R18_MASTER_GUIDE.txt")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
    except Exception:
        pass
    
    st.session_state.r18_guide_len = len(text)
    return text

def handle_input(user_input, chat_ph=None):
    # --- 1. ログ記録・履歴追加（既存のまま） ---
    log_buffer = []
    def log(msg):
        # 時刻付きでリストに追加
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}"
        log_buffer.append(entry)
        # 開発用コンソールにも出す
        print(entry)

    log(f"🎬 Action Started. Input: {user_input[:30]}...")

    # 初期化
    st.session_state["last_error"] = ""
    prompt_text = user_input

    # --- 履歴追加 (User) ---
    st.session_state.chat_history.append({"role": "user", "parts": [prompt_text]})
    log("User input appended to history.")
    
    # 体験版: 会話送信時に画像をランダムに切り替え
    from config import IS_DEMO_MODE
    if IS_DEMO_MODE:
        import random
        # demo002.png以降のファイルを探す
        demo_dir = os.path.join(BASE_DIR, "assets", "demo_heroine")
        demo_images = []
        if os.path.exists(demo_dir):
            for i in range(2, 100):  # demo002.png から demo099.png まで
                img_path = os.path.join(demo_dir, f"demo{i:03d}.png")
                if os.path.exists(img_path):
                    demo_images.append(img_path)
        
        if demo_images:
            # ランダムに画像を選択
            selected_image = random.choice(demo_images)
            try:
                with open(selected_image, "rb") as f:
                    st.session_state.current_image_bytes = f.read()
                log(f"Demo image switched to: {os.path.basename(selected_image)}")
            except Exception as e:
                log(f"Failed to load demo image: {e}")
    
    # 【UX改善】即座に画面反映 + 「執筆中」演出
    if chat_ph is not None:
        try:
            with chat_ph.container():
                # 現在の履歴 + 「執筆中インジケーター」を結合して表示
                temp_history = st.session_state.chat_history + [
                    {"role": "model", "parts": ["（執筆中...🖊️）"]}
                ]
                components.display_chat(temp_history)
            
            # 演出用ウェイト
            time.sleep(0.1)
        except Exception as e:
            log(f"Optimistic UI Warning: {e}")

    # 内部ヘルパー: 場所解析
    def _parse_and_update_location(resp_text):
        import re
        import json
        
        # 1. <loc>抽出
        loc_match = re.search(r"<loc>(.*?)</loc>", resp_text, re.DOTALL)
        if loc_match:
            try:
                loc_data = json.loads(loc_match.group(1).strip())
                if isinstance(loc_data, dict):
                    cur_loc = st.session_state.get("current_location", {})
                    
                    # Update fields
                    bid = loc_data.get("base_id")
                    if bid: 
                        cur_loc["base_id"] = bid
                        if hasattr(generator, "LOCATION_DATA") and bid in generator.LOCATION_DATA:
                            cur_loc["category"] = generator.LOCATION_DATA[bid].get("category", "REST")
                        else:
                            if "category" in loc_data:
                                cur_loc["category"] = loc_data["category"]
                                
                    if loc_data.get("display_name"): 
                        cur_loc["display_name"] = loc_data["display_name"]
                    
                    st.session_state.current_location = cur_loc
            except Exception as e:
                print(f"Warning: Failed to parse location data: {e}")
        
        # 2. タグ削除（複数の形式に対応）
        cleaned_text = resp_text
        # <loc>タグを削除
        cleaned_text = re.sub(r"<loc>.*?</loc>", "", cleaned_text, flags=re.DOTALL)
        # {base_id: ...} 形式を削除（1行または複数行）
        cleaned_text = re.sub(r"\{base_id:\s*[^,}]+,\s*display_name:\s*[^}]+?\}", "", cleaned_text, flags=re.DOTALL)
        # {base_id: ...} 形式（改行あり）を削除
        cleaned_text = re.sub(r"\{base_id:\s*[^,}]+,\s*display_name:\s*[^}]+?\}", "", cleaned_text, flags=re.MULTILINE | re.DOTALL)
        # JSON形式の場所情報を削除
        cleaned_text = re.sub(r'\{[^}]*"base_id"[^}]*\}', "", cleaned_text, flags=re.DOTALL)
        cleaned_text = cleaned_text.strip()
        return cleaned_text

    # 既存の生成ロジック開始 (try-finallyで囲む)
    try:
        # ステータス取得
        h = st.session_state.chat_heroine
            
        current_tokimeki = int(getattr(h, "tokimeki", 0))
        current_guard = int(getattr(h, "guard", 50))
        
        # 変数初期化
        is_romantic_mode = False
        penalty_triggered = False
        apply_snowmelt = False  # デフォルト値（R18/R15の判定後に更新される）
        
        # ==================================================
        # 🔞 R18モード（既存の挙動を維持：制限なし・激甘）
        # ==================================================
        # 🔞 R18モード（既存の挙動を維持：制限なし・激甘）
        # ==================================================
        if IS_R18_APP:
            trigger_words = ["キス", "抱きしめ", "触れ", "好き", "愛し", "ドキドキ", "手", "指", "腰", "吐息", "濡れ", "熱"]
            has_trigger = any(w in prompt_text for w in trigger_words)
            
            if current_tokimeki >= 60 or has_trigger:
                is_romantic_mode = True
            
            st.session_state.injection_prompt = ""
            apply_snowmelt = False  # R18は自動減少なし（自由）

        # ==================================================
        # 📛 R15モード（定義リスト準拠の厳格判定）
        # ==================================================
        else:
            # プロフ作成時に決まった値を直接参照
            lib_val = getattr(h, "libido", "普通")
            exp_val = getattr(h, "experience", "普通")
            sens_val = getattr(h, "sensitivity", "普通")
            
            # 1. 発情ボーダー
            lib_map = {"少し拒絶": 95, "無い": 90, "普通": 80, "ムッツリ": 75, "強め": 60, "モンスター": 50}
            romance_border = lib_map.get(lib_val, 80)
            is_romantic_mode = (current_tokimeki >= romance_border)

            # 2. 許容ボーダー
            exp_map = {"無い": 5, "少し": 15, "普通": 25, "慣れ切っている": 35}
            sex_permit_border = exp_map.get(exp_val, 25)
            
            # 3. ペナルティ判定
            danger_keywords = ["セックス", "SEX", "挿入", "中出し", "フェラ", "クリトリス", "オナニー", "ヤらせろ", "脱げ", "しゃぶ"]
            has_danger = any(dw in prompt_text for dw in danger_keywords)
            
            if has_danger and current_guard > sex_permit_border:
                penalty_triggered = True
                h.love = int(getattr(h, "love", 0) * 0.8)
                h.guard = min(100, int(current_guard * 1.3))
                st.toast(lang_mgr.get("text_0000", "ガードが堅すぎます！(現在:{current_guard} / 必要:{sex_permit_border})"), icon="🛡️")

            # 4. 雪解けフラグ（計算は後でやる）
            apply_snowmelt = False
            if not penalty_triggered:
                apply_snowmelt = True

            # 5. ターン制限ロジック（体験版モードのみ15ターン制限を適用）
            from config import IS_DEMO_MODE
            
            # 体験版モード: 15ターン制限（14回目でエンディング、15回目でHPリンク）
            if IS_DEMO_MODE:
                user_turn_count_demo = sum(1 for msg in st.session_state.chat_history if msg.get("role") == "user")
                if user_turn_count_demo == 14:
                    # 14回目: エンディング（スマホが鳴ってマネージャーから呼び出される）
                    force_ending_prompt = """
                    【体験版エンディング: 14回目の会話】
                    この会話が14回目になりました。ここで自然にエンディングを迎えてください。
                    
                    **エンディングシーン:**
                    1. プレイヤーの発言に短く反応する。
                    2. 突然、スマホが鳴る（バイブレーション音や着信音を描写）。
                    3. スマホを見て「あ、マネージャーから…」と少し困った表情を見せる。
                    4. 「ごめん、急に呼び出されちゃった。でも、今日は本当に楽しかった！」と明るく言う。
                    5. 「よかったら、LINE交換しない？」と提案し、連絡先を交換する描写を入れる。
                    6. 「また会おうね！連絡するね！」と笑顔で別れる。
                    7. 名残惜しそうに手を振って去っていく。
                    
                    **重要:**
                    - 「期限がある」ことは一切言わない（カノジョは知らない）。
                    - 自然な別れのシーンとして描写する。
                    - 明るく、前向きな雰囲気で終わる。
                    """
                    st.session_state.injection_prompt = force_ending_prompt
                elif user_turn_count_demo < 14:
                    keep_talking_prompt = """
                    【会話継続ルール】
                    まだ別れの挨拶をする時間ではありません（会話継続中）。
                    - あなたから「じゃあね」「また明日」「そろそろ帰るね」と会話を終わらせないでください。
                    - 話題が尽きそうなら、あなたから新しい話題を振って会話を盛り上げてください。
                    - 「期限がある」ことは一切言わない（カノジョは知らない）。
                    """
                    st.session_state.injection_prompt = keep_talking_prompt
                else:
                    # 15回目以降は通常の会話継続（HPリンクはrender_game_screenで表示）
                    st.session_state.injection_prompt = ""
            else:
                # 通常モード: ターン制限なし（自由に会話可能）
                st.session_state.injection_prompt = ""



            



        # Rules Definitions
        ROLEPLAY_BOUNDARY_RULES = """
        【重要：ロールプレイ境界線ルール（絶対遵守）】
        あなたは現在「{current_character_name}」のみを演じています。
        以下の禁止事項に違反した出力は、システムエラーとみなされます。

        1. **他者憑依の禁止**
           - 他キャラクターのセリフ・行動・思考・感情を一切記述してはいけません。
           - プレイヤー（主人公）のセリフや行動を勝手に決定・描写してはいけません。

        2. **出力範囲の限定**
           - あなたが出力してよいのは「{current_character_name}がどう反応したか」だけです。
           - 相手の反応を先取りして予測記述してはいけません。
        """

        
        SINGLE_MODE_FREE_RULES = """
        【Singleモード（自由会話）】
        - プレイヤーのセリフ代筆禁止（絶対遵守）。
        - 関係性更新（<new_relation>）は、「二人の合意」が成立した空気になってから出力。（片方の合意で即決しない）
        """
        
        STAT_TUNING = """
        【ステータス変動の絶対ルール】
        1. **感情タグ（<emotions>）が全ての基準です。**
        2. **数値の重み:** 1回の会話での変動幅は「±1〜3」を基本とする。
        """

        # 1. コンテキスト読み込み（修正）
        intro_raw = (st.session_state.get("intro_text") or "").strip()
        
        if st.session_state.get("day_count", 1) > 1:
            intro_line = ""
        else:
            intro_line = f"- 導入（現在の状況）: {intro_raw}"

        world_context = st.session_state.get("world_setting", "")
        wm = st.session_state.get("world_mode", "現代")
        wh = st.session_state.get("world_rules", {})
        wm_rule = wh.get(wm, "現代（基本ルール）")
        wd = (st.session_state.get("world_detail", "") or "").strip()
        wd_line = f"- 世界の追加ルール（最優先）: {wd}" if wd else ""
        cur_loc = st.session_state.get("current_location", {})
        loc_display = cur_loc.get("display_name", "自宅")
        loc_id = cur_loc.get("base_id", "01_HOME")
        loc_cat = cur_loc.get("category", "REST")
        
        rd = st.session_state.get("relationship_data", {}) or {}
        
        # 言語設定を取得
        current_lang = st.session_state.get("language", "jp")

        # 2. context_block の構築（言語対応）
        if current_lang == "en":
            user_name_en = st.session_state.get("user_name", "you")
            if user_name_en == "あなた":
                user_name_en = "you"
            user_age_en = st.session_state.get("user_age", "")
            context_block = f"""
        【Current Location (Internal Memo)】
        - User Display: {loc_display}
        - Internal ID: {loc_id}
        - Internal Category: {loc_cat}

        【Fixed Premises (Must Follow)】
        {world_context}
        {wd_line}
        - Protagonist before you: {user_name_en} ({user_age_en} years old)
        - Worldview (Free description priority): {rd.get("world_free") or rd.get("world_choice") or ""}
        - Protagonist Job: {rd.get("player_job_text","")}
        - Relationship with Main (Free description priority): {rd.get("main_relation_free") or rd.get("main_relation_choice") or ""}
        - Relationship with Sub (Free description priority): {rd.get("sub_relation_free") or rd.get("sub_relation_choice") or ""}
        {intro_line}
        
        【RP Worldview Rules (Priority Order)】
        - Top Priority: world_detail (Additional world rules. Laws/common sense/clothing regulations, etc.)
        - Next: Relationship stage (world_free if available, otherwise world_choice)
        - Next: world_mode basic rules (below)
        - world_mode: {wm}
        - world_mode_rule: {wm_rule}
        """
        elif current_lang == "zh-CN":
            user_name_zh = st.session_state.get("user_name", "你")
            if user_name_zh in ["あなた", "主人公"]:
                user_name_zh = "你"
            user_age_zh = st.session_state.get("user_age", "")
            context_block = f"""
        【当前位置（内部备忘录）】
        - 用户显示: {loc_display}
        - 内部ID: {loc_id}
        - 内部类别: {loc_cat}

        【固定前提（必须遵守）】
        {world_context}
        {wd_line}
        - 您面前的主角: {user_name_zh} ({user_age_zh}岁)
        - 世界观（自由描述优先）: {rd.get("world_free") or rd.get("world_choice") or ""}
        - 主角职业: {rd.get("player_job_text","")}
        - 与主要角色的关系（自由描述优先）: {rd.get("main_relation_free") or rd.get("main_relation_choice") or ""}
        - 与次要角色的关系（自由描述优先）: {rd.get("sub_relation_free") or rd.get("sub_relation_choice") or ""}
        {intro_line}
        
        【RP世界观规则（优先级）】
        - 最高优先级: world_detail（附加世界规则。法律/常识/服装规定等）
        - 次点: 关系舞台（world_free如果可用，否则world_choice）
        - 次点: world_mode基本规则（如下）
        - world_mode: {wm}
        - world_mode_rule: {wm_rule}
        """
        elif current_lang == "zh-TW":
            user_name_zh = st.session_state.get("user_name", "你")
            if user_name_zh in ["あなた", "主人公"]:
                user_name_zh = "你"
            user_age_zh = st.session_state.get("user_age", "")
            context_block = f"""
        【當前位置（內部備忘錄）】
        - 用戶顯示: {loc_display}
        - 內部ID: {loc_id}
        - 內部類別: {loc_cat}

        【固定前提（必須遵守）】
        {world_context}
        {wd_line}
        - 您面前的主角: {user_name_zh} ({user_age_zh}歲)
        - 世界觀（自由描述優先）: {rd.get("world_free") or rd.get("world_choice") or ""}
        - 主角職業: {rd.get("player_job_text","")}
        - 與主要角色的關係（自由描述優先）: {rd.get("main_relation_free") or rd.get("main_relation_choice") or ""}
        - 與次要角色的關係（自由描述優先）: {rd.get("sub_relation_free") or rd.get("sub_relation_choice") or ""}
        {intro_line}
        
        【RP世界觀規則（優先級）】
        - 最高優先級: world_detail（附加世界規則。法律/常識/服裝規定等）
        - 次點: 關係舞台（world_free如果可用，否則world_choice）
        - 次點: world_mode基本規則（如下）
        - world_mode: {wm}
        - world_mode_rule: {wm_rule}
        """
        else:
            context_block = f"""
        【現在地（内部メモ）】
        - ユーザー表記: {loc_display}
        - 内部ID: {loc_id}
        - 内部カテゴリ: {loc_cat}

        【固定前提（必ず守る）】
        {world_context}
        {wd_line}
        - あなたの目の前にいる主人公: {st.session_state.get("user_name", "あなた")} ({st.session_state.get("user_age", "")}歳)
        - 世界観（自由記述優先）: {rd.get("world_free") or rd.get("world_choice") or ""}
        - 主人公職業: {rd.get("player_job_text","")}
        - メインとの関係（自由記述優先）: {rd.get("main_relation_free") or rd.get("main_relation_choice") or ""}
        - サブとの関係（自由記述優先）: {rd.get("sub_relation_free") or rd.get("sub_relation_choice") or ""}
        {intro_line}
        
        【RP世界観ルール（優先順位）】
        - 最優先: world_detail（世界の追加ルール。法律/常識/衣装規定など）
        - 次点: relationship の舞台（world_free があればそれを優先、無ければ world_choice）
        - 次点: world_mode の基本ルール（下記）
        - world_mode: {wm}
        - world_mode_rule: {wm_rule}
        """

        sys_prompt = h.get_system_prompt(st.session_state.is_skill_active, st.session_state.active_skill_data)
        sys_prompt += "\n" + context_block

        if st.session_state.get("injection_prompt"):
             sys_prompt += "\n" + st.session_state.injection_prompt

        # ▼ ペナルティ発生時の強制拒絶プロンプト（R15用）
        if penalty_triggered:
            rejection_prompt = f"""
            【⚠️ 緊急指令：ペナルティ発生】
            プレイヤーは、現在の信頼関係（ガード値: {current_guard}）に見合わない、あまりに不躾な性的要求（{prompt_text}）をしてきました。
            
            **以下の態度で、徹底的に拒絶してください:**
            1. **感情:** 恐怖、嫌悪、軽蔑、ドン引き。
            2. **行動:** 手を払いのける、冷ややかな目で見る、距離を取る。
            3. **セリフ:** 「は？ 何言ってるの？」「最低……」「帰っていい？」
            4. **甘え・デレは一切禁止。** 完全に突き放してください。
            """
            sys_prompt += "\n" + rejection_prompt

        # ▼ 通常時の許容ガイドライン（R15用）
        elif not IS_R18_APP:
            permission_guide = f"""
            【❤️ 性的アクションの許容判定ガイド（Game Rule）】
            現在の彼女の本来のステータス（性欲・経験）に基づき、以下の基準で反応を決めてください。
            
            **基本スペック:**
            - 性欲: {lib_val} ➔ 興奮しやすさ(Tokimekiボーダー)に影響
            - 経験: {exp_val} ➔ 行為への抵抗感(Guardボーダー)に影響
            - 感度: {sens_val} ➔ **描写のニュアンスとして使用（判定には影響しません）**

            **現在の数値:**
            - Tokimeki(興奮度): {current_tokimeki} (発情ボーダー: {romance_border})
            - Guard(警戒心): {current_guard} (低いほど無防備)

            **判定基準:**
            1. **深い行為（セックス・フェラ・愛撫など）**
               - 許容ボーダー: **Guard {sex_permit_border} 以下**
               - 現在値 ({current_guard}) がボーダーより高い場合 ➔ **必ず断ってください**（「経験 {exp_val}」なりの断り方で）。
               - ボーダー以下の場合 ➔ 抵抗せず受け入れてください。

            2. **甘い雰囲気（キス・ハグ・ボディタッチ）**
               - 条件: **Tokimeki {romance_border} 以上**
               - 満たしている場合 ➔ 顔を赤らめたり、熱っぽい反応を返してください。
               - その際、「感度: {sens_val}」に合わせて、反応の激しさを調整してください。
            """
            sys_prompt += "\n" + permission_guide
        
        # =========================================================
        # 4. 生成実行 (Retry & Fallback)
        # =========================================================
        full_hist = st.session_state.chat_history
        short_hist = full_hist[-12:] if len(full_hist) > 12 else full_hist
        
        # 描写ルール
        mn = getattr(h, "name", "彼女")
        NARRATION_RULES = """
        【重要：地の文（ナレーション）の執筆ルール】
        1. **視点の定義：「俺」による観察描写**
           - 地の文の主語・視点は必ず「俺（主人公）」にすること。
           - ただし、**俺の「感情・思考」を書くことは禁止**する。
           - あくまで「俺が見たもの」「俺に聞こえたもの」という**事実の観察**に徹すること。

        2. **文体の書き換え例**
           - NG（神視点）: 「彼女は悲しそうに俯いた。」
           - NG（感情過多）: 「俺は彼女が俯くのを見て、胸が痛んだ。」
           - **OK（事実観察）**: 「俺の目の前で、彼女は悲しげに俯いた。」
           - **OK（事実観察）**: 「俺は、彼女が何か言いたげに視線を逸らすのを見た。」

        3. **ヒロインの描写**
           - 彼女の感情は断定せず、「〜に見えた」「〜な様子だった」と、俺の目から見た情報として書くこと。
           - `（）` 内は、これまで通り「ヒロインの心の声（本音）」として出力すること。
        """

        sys_prompt += "\n" + NARRATION_RULES
        
        # ▼▼▼ 追加: 台本形式ルールの強制 ▼▼▼
        SCRIPT_FORMAT_RULES = """
        【⚠️ 重要：台本形式（スクリプト）での出力ルール】
        プログラムによる解析のため、以下の書式を**絶対厳守**してください。

        1. **セリフの記述ルール（最重要）**
           - **書式:** {char_name}「セリフ内容」
           - **必ず一重カギカッコ「 」を使用してください。**
           - 二重カギカッコ『 』は、強調表現（作品名や重要な単語）としてのみ使い、セリフ枠としては**使用禁止**です。
           - 例（OK）: {char_name}「それは『月光荘』のこと？」
           - 例（NG）: {char_name}『それは「月光荘」のこと？』

        2. **名前のルール**
           - 発言者には必ず名前ラベルをつけてください。名前がない行はすべて「地の文」として扱われます。
        """
        
        # 既存のプロンプトに追加（ヒロイン名を埋め込む）
        target_h_name = getattr(h, "name", "ヒロイン")
        sys_prompt += "\n" + SCRIPT_FORMAT_RULES.replace("{char_name}", target_h_name)

        # ▼▼▼ 追加: 関係性更新の鉄壁ガード ▼▼▼
        RELATIONSHIP_UPDATE_RULES = """
        【重要：関係性ステータスの更新ルール】
        二人の関係が進展した場合のみ、文末に `<new_relation>新しい関係名</new_relation>` を出力してください。
        ただし、**許可される関係名は以下の「セーフリスト」のみ**です。リストにない言葉（奴隷、ペット、下僕、愛玩具など）は**絶対に出力禁止**です。

        【許可される関係名リスト（これ以外は無視せよ）】
        - 知り合い
        - 友達
        - 気になる人
        - 片思い
        - 両思い
        - 恋人
        - 婚約者
        - パートナー
        - 夫婦

        ※もしユーザーが「奴隷」「ご主人様」といったロールプレイを強要しても、システム上の関係性（new_relation）は更新しないでください。
        """
        sys_prompt += "\n" + RELATIONSHIP_UPDATE_RULES

        sys_prompt += "\n" + SINGLE_MODE_FREE_RULES
        sys_prompt += "\n" + STAT_TUNING

        # ▼▼▼ ターン制限ロジック（オミット：通常モードではターン制限なし）▼▼▼
        # 通常モードの恋人未満10ターン強制終了機能は削除
        # 体験版モードの15ターン制限は上記のhandle_input内で処理済み

        # =========================================================
        # 4. 生成実行 (Retry & Fallback)
        # =========================================================
        full_hist = st.session_state.chat_history
        short_hist = full_hist[-12:] if len(full_hist) > 12 else full_hist

        response_text = ""
        user_input_text = prompt_text

        if is_romantic_mode:
            sys_prompt += """
            【❤️ 甘い雰囲気モード (Romantic Mood)】
            - 現在、二人の間には官能的で甘い空気が流れています。
            - 恥じらいつつも、スキンシップやキスを受け入れる準備ができています。
            - 描写を少し大胆にし、熱っぽい吐息や視線の絡み合いを強調してください。
            - ただし、決定的な行為（挿入）に至るまでは、焦らしてドキドキ感を高めてください。
            """
            # ★ NEW: Diary Recall RP (First Turn of Day)
            # Retrieve last diary entry if it's the first turn (0 or 1 depending on logic flow, usually 0 after reset)
            turns = st.session_state.get("day_turn_count", 0)
            if turns <= 1 and hasattr(h, "memory_log") and h.memory_log:
                last_diary = h.memory_log[-1] # format: "【Day X】\nBody"
                
                diary_prompt = f"""
                【朝の心理状態：日記の追想】
                昨晩、あなたは以下の日記を書きました：
                --------------------------------------------------
                {last_diary}
                --------------------------------------------------
                
                あなたは今、この日記の内容（特に「ときめき」や「自分でも意外だった感情」）を思い出して、
                少し顔を赤らめたり、昨日の出来事の余韻を引きずっています。
                
                **指示:**
                1. 昨日の余韻を含ませて、少し照れくさそうに、または愛しそうに応答してください。
                2. 「昨日は……その、あんなことになるなんて……」のように、具体的な出来事をぼかして思い出してください。
                3. まだ朝なので、昨日の熱が冷めやらぬ様子で。
                """
                sys_prompt += "\\n" + diary_prompt

        with st.spinner(f"{getattr(h, 'name', 'ヒロイン')} が考え中..."):
            for i in range(3):
                try:
                    temp_res = st.session_state.gemini_client.generate_response(short_hist, sys_prompt)
                    if temp_res and "BLOCKED" not in temp_res:
                        response_text = temp_res
                        break
                    time.sleep(0.5)
                except Exception as e:
                    err_str = str(e)
                    if "Quota exceeded" in err_str or "429" in err_str:
                        st.toast(lang_mgr.get("text_0001", "⚠️ Proモデル制限到達。Flashモデルに切り替えます。"), icon="⚡")
                        st.session_state.gemini_model = "models/gemini-1.5-flash"
                        if st.session_state.gemini_api_key:
                            st.session_state.gemini_client = GeminiClient(st.session_state.gemini_api_key, model_name=st.session_state.gemini_model)
                            continue
                    else:
                        raise e

        if not response_text:
             response_text = "（……彼女は言葉にならず、ただ見つめている……）"

        # =========================================================
        # 5. 事後処理 (R15 / Stats / Relation)
        # =========================================================
        
        # A. R15 Fade Out (Morning After)
        if "<SCENE_FADE_OUT>" in response_text:
            import random
            response_text = response_text.replace("<SCENE_FADE_OUT>", "\n\n（……濃厚な時間が過ぎていった……）\n\n")
            st.toast(lang_mgr.get("text_0002", "❤️ 愛し合い、2〜3時間が経過しました"), icon="⏰")
            if h:
                h.reason = random.randint(80, 90) # 賢者タイム
                h.lust = random.randint(20, 30)   # 解消
                h.guard = min(100, int(getattr(h, "guard", 0)) + 15) # 羞恥
                h.possession = min(100, int(getattr(h, "possession", 0)) + 20) # 執着

        # B. Emotion Reset & Stats Update
        if hasattr(h, "emotions"): h.emotions = {} # Reset before update
        h.update_stats(response_text)
        set_top5_from_emotions(h)
        
        # --- Auto-Decay Guard (Natural Melting) ---
        import random
        decay_val = random.randint(0, 2)
        if decay_val > 0:
            cur_guard = int(getattr(h, "guard", 50))
            new_guard = max(0, cur_guard - decay_val)
            h.guard = new_guard
            h.chastity = new_guard # Sync alias
            st.toast(lang_mgr.get("text_0003", "会話の余韻で……彼女のガードが少し柔らかくなった（-{decay_val}）"), icon="💭")
        
        # C. Location Update
        response_text = _parse_and_update_location(response_text)
        
        # D. Relation Update
        if "<new_relation>" in response_text:
             import re
             rel_match = re.search(r"<new_relation>(.*?)</new_relation>", response_text, flags=re.DOTALL)
             if rel_match:
                 new_status = rel_match.group(1)
                 h.relation_status = new_status
                 response_text = response_text.replace(rel_match.group(0), "").strip()
                 if not response_text:
                     response_text = f"（……二人の間に、新たな関係『{new_status}』が刻まれた。）"
                 st.toast(lang_mgr.get("text_0004", "関係成立！「{new_status}」"), icon="💍")

        # F. History Append (修正版: フルネーム・読み仮名対応)
        import re
        
        # 場所情報の形式をすべて削除（念のため再度削除）
        response_text = re.sub(r"<loc>.*?</loc>", "", response_text, flags=re.DOTALL)
        response_text = re.sub(r"\{base_id:\s*[^,}]+,\s*display_name:\s*[^}]+?\}", "", response_text, flags=re.DOTALL)
        response_text = re.sub(r'\{[^}]*"base_id"[^}]*\}', "", response_text, flags=re.DOTALL)
        response_text = response_text.strip()

        lines = response_text.strip().splitlines()
        
        # ヒロイン名の取得（比較用にスペースを除去したクリーンな名前を作る）
        # 例: "佐条 瑞希" -> "佐条瑞希"
        raw_h_name = getattr(h, "name", "ヒロイン")
        safe_h_name = raw_h_name.replace(" ", "").replace("　", "")
        
        # 現在のルート（アイコン出し分け用）
        hkey = "main"

        for line in lines:
            line = line.strip()
            if not line: continue
            
            # --- 台本パース（強制フキダシ化ロジック） ---
            # 「名前 (ふりがな) 「セリフ」」 のようなパターンを捕捉
            # 行末のスペースなどは無視する
            match = re.match(r'^(.+?)\s*「(.+?)」\s*$', line)
            
            is_dialogue = False
            speaker_label = "System"
            content = line  # デフォルトは行全体（地の文）

            if match:
                parsed_name = match.group(1).strip()
                parsed_text = match.group(2).strip()
                
                # 【判定ルール】
                # 1. 名前に読点「。」が含まれる場合は、会話文ではなく「地の文」とみなして弾く
                #    (例: 彼女は言った。「こんにちは」 -> これはフキダシにしない)
                # 2. 文字数制限を「50文字」まで大幅緩和
                #    (例: 佐条 瑞希 (さじょう みずき) -> 20文字弱なので余裕で通る)
                
                if "。" in parsed_name or len(parsed_name) > 50:
                    is_dialogue = False
                else:
                    # ここに来たら問答無用で「セリフ」として扱う
                    is_dialogue = True
                    
                    # 名前の一致判定（スペース無視・部分一致）
                    # "佐条瑞希(さじょうみずき)" の中に "佐条瑞希" が含まれていれば、それはヒロイン
                    clean_p_name = parsed_name.replace(" ", "").replace("　", "")
                    
                    if (safe_h_name in clean_p_name):
                        # ヒロイン確定：表示名は読み仮名のないスッキリした名前に戻す
                        speaker_label = raw_h_name 
                        content = f"「{parsed_text}」"
                    else:
                        # モブ等の場合：そのままの名前を使う
                        speaker_label = parsed_name
                        content = f"「{parsed_text}」"

            # --- 履歴に追加 ---
            if is_dialogue:
                st.session_state.chat_history.append({
                    "role": "model",
                    "parts": [content],
                    "speaker": hkey,       # ここで正しいアイコンが出る
                    "speaker_name": speaker_label
                })
            else:
                # 名前パターンの条件を満たさない行は、すべてシステム（地の文）扱い
                st.session_state.chat_history.append({
                    "role": "model",
                    "parts": [line],
                    "speaker": "System",
                    "speaker_name": "System"
                })

        st.session_state.execution_log = "\n".join(log_buffer)
        
        # ▼▼▼ 追加: 強制雪解け実行（AI更新後に値を削る） ▼▼▼
        if apply_snowmelt:
            # AI更新後の最新値を取得
            final_guard = int(getattr(h, "guard", 0))
            final_reason = int(getattr(h, "reason", 0))
            
            # ボーナス計算
            cur_love = int(getattr(h, "love", 0))
            cur_tokimeki = int(getattr(h, "tokimeki", 0))
            
            # Love -> Guard減少 (最低-1保証)
            guard_drop = 1 + (cur_love // 20)
            
            # Tokimeki -> Reason減少
            reason_drop = (cur_tokimeki // 20)

            # 強制適用
            h.guard = max(0, final_guard - guard_drop)
            h.reason = max(0, final_reason - reason_drop)

        st.rerun()

    except Exception as e:
        log(f"Error: {e}")
        st.error(f"Error: {e}")
        st.session_state["last_error"] = str(e)
    finally:
        pass



def game_start_dummy_if_needed():
    if st.session_state.get("game_initialized"):
        return

    # メインヒロインの保存パスがあればそこからロードを試みる
    main_save_path = (st.session_state.get("main_heroine") or {}).get("save_path", "")
    main_saved = load_heroine_from_save(main_save_path)

    if isinstance(main_saved, dict):
        # 保存データから復元
        ui = main_saved.get("user_input", {})
        ft = main_saved.get("final_texts", {})
        
        h_data = {
            "name": ui.get("Name", "ヒロイン"),
            "age": ui.get("Visual Age", "20"),
            "job": ui.get("Job", "不明"),
            "appearance": ui.get("Appearance", ""),
            "personality": ui.get("Personality", ""),
            "hobby": ui.get("Hobby", ""),
            "tone": ui.get("Tone", ""),
            "backstory": ft.get("main_profile", ""),
            "first_line": "...", # Placeholder, we set history manually below
            "visual_tags": ft.get("image_tags", ""),
            "location": "部屋",
            "bg_tag": "room",
            # 保存済みの画像パスを持たせる
            "image_path": (st.session_state.get("main_heroine") or {}).get("image_path", ""),
            # ★追加: R15用ステータス読み込み
            "libido": (main_saved.get("final_status", {}) or {}).get("Libido", "普通"),
            "experience": (main_saved.get("final_status", {}) or {}).get("Experience", "普通"),
            "sensitivity": (main_saved.get("final_status", {}) or {}).get("Sensitivity", "普通"),
            "secret_fetish_unlocked": (main_saved.get("final_status", {}) or {}).get("secret_fetish_unlocked", False),
            
            # ▼ 追加: 保存されたステータスからGuardを読み込む (Key fix)
            "Chastity": (main_saved.get("final_status", {}) or {}).get("Chastity", (main_saved.get("final_status", {}) or {}).get("Guard", 50)),
            
            # Hidden Traits (New)
            "breast_desc": ui.get("breast_desc", "不明"),
            "vagina_desc": ui.get("vagina_desc", "標準"),
            "vagina_note": ui.get("vagina_note", ""),
            "secret_fetish": ui.get("secret_fetish", "なし"),
            "secret_fetish_desc": ui.get("secret_fetish_desc", ""),
        }
        
        # Calculate Initial Stats (Main)
        personality = ui.get("Personality", "")
        rd = st.session_state.get("relationship_data", {}) or {}
        lv, ls, rs, ps = compute_initial_bars(rd, "main", personality)
        
        # 体験版モード: 初期ステータスを固定値に設定
        from config import IS_DEMO_MODE
        if IS_DEMO_MODE:
            import random
            # 好感度: 20～30、興奮度: 40～60
            h_data["love"] = random.randint(20, 30)
            h_data["tokimeki"] = random.randint(40, 60)
            # reasonとpossessionは通常通り
            h_data["reason"] = rs
            h_data["possession"] = ps
        else:
            h_data["love"] = lv
            h_data["tokimeki"] = ls
            h_data["reason"] = rs
            h_data["possession"] = ps
        
        # ▼ 追加: 保存されたステータスからGuardを読み込む
        fs = main_saved.get("final_status", {}) or {}
        h_data["Guard"] = fs.get("Guard", 50)
    else:
        # フォールバック（ダミー）
        h_data = {
            "name": "ヒロイン",
            "age": "20",
            "job": "不明",
            "appearance": "",
            "personality": "",
            "hobby": "",
            "tone": "",
            "backstory": "",
            "first_line": "「……来たんだ。」",
            "visual_tags": "",
            "location": "部屋",
            "bg_tag": "room",
            "love": 10,
            "tokimeki": 0,
            "reason": 90,
        }

    st.session_state.chat_heroine = Heroine(h_data)

    # サブヒロインシステムは使用しない

    if "active_speaker" not in st.session_state:
        st.session_state.active_speaker = "main"
    
    # ---------------------------------------------------------
    # Opening Generation (Narration Only) - 修正版
    # ---------------------------------------------------------
    
    # 1. すでに作成フェーズで作った「タイトル付き導入」があるか確認
    saved_intro = st.session_state.get("intro_text", "").strip()
    
    if "### 🎬" in saved_intro:
        # ★タイトルがある場合: 再生成せずにそのまま採用！
        # (これで「🎬 曲がり角での衝突」などのタイトルが消えずに残ります)
        final_text = saved_intro
        
        # ※場所情報は作成フェーズですでに初期化されているため、ここでの解析はスキップします。
        
    else:
        # ★タイトルがない場合（古いデータや不具合時）: 念のため新規生成する（既存ロジック）
        opening_scene = generate_opening_scene(st.session_state.gemini_client) or ""
        
        # --- Parse Location from Opening ---
        import re
        import json
        
        final_text = opening_scene
        loc_match = re.search(r"<loc>(.*?)</loc>", opening_scene, re.DOTALL)
        if loc_match:
            try:
                loc_data = json.loads(loc_match.group(1).strip())
                bid = loc_data.get("base_id", "01_HOME")
                dname = loc_data.get("display_name", "自宅")
                
                # Lookup Category
                cat = "REST"
                if hasattr(generator, "LOCATION_DATA") and bid in generator.LOCATION_DATA:
                    cat = generator.LOCATION_DATA[bid].get("category", "REST")
                
                # Update Session
                st.session_state.current_location = {
                    "base_id": bid,
                    "display_name": dname,
                    "category": cat
                }
                
                # Remove tag from display text
                final_text = re.sub(r"<loc>.*?</loc>", "", opening_scene, flags=re.DOTALL).strip()
            except Exception:
                pass
    # -----------------------------------

    # Web体験版: IS_DEMO_MODEは強制的にTrue
    IS_DEMO_MODE = True
    intro_dialogue = None
    
    # Web体験版: 導入文からヒロインのセリフを抽出（多言語対応）
    if IS_DEMO_MODE and final_text:
        import re
        current_lang = st.session_state.get("language", "jp")
        h_name = st.session_state.chat_heroine.name if st.session_state.chat_heroine else "ヒロイン"
        
        # ヒロイン名のセリフパターンを検索
        dialogue_pattern = rf'{re.escape(h_name)}「([^」]+)」'
        dialogue_match = re.search(dialogue_pattern, final_text)
        if dialogue_match:
            intro_dialogue = dialogue_match.group(1)
            # セリフ部分を導入文から削除
            intro_narrative = re.sub(rf'\n?{re.escape(h_name)}「[^」]+」', '', final_text)
        else:
            intro_narrative = final_text
    else:
        intro_narrative = final_text if final_text else "（物語が始まる……）"
    
    st.session_state.chat_history = []
    if intro_narrative:
        st.session_state.chat_history.append({
            "role": "model",
            "parts": [intro_narrative],
            "speaker_name": "System"
        })
    else:
        st.session_state.chat_history.append({
            "role": "model", 
            "parts": ["（物語が始まる……）"],
            "speaker_name": "System"
        })
    
    # Web体験版: セリフを別エントリとして追加（抽出された場合のみ）
    # 導入文からヒロインのセリフが抽出された場合のみ追加
    if IS_DEMO_MODE and intro_dialogue:
        current_lang = st.session_state.get("language", "jp")
        h_name = st.session_state.chat_heroine.name if st.session_state.chat_heroine else "ヒロイン"
        
        st.session_state.chat_history.append({
            "role": "model",
            "parts": [f"{h_name}「{intro_dialogue}」"],
            "speaker": "main",
            "speaker_name": h_name
        })
    
    # --- Enforce Main Route Start ---
    st.session_state.current_route = "main"
    st.session_state.active_speaker = "main"
    
    # Init Image
    set_current_image_to_base("main")


    st.session_state.prev_active_speaker = "main"
    # st.session_state.current_route = "main" # removed force override

    if "met_main" not in st.session_state:
        st.session_state.met_main = True


    if "skill_state" in st.session_state:
        del st.session_state.skill_state

    st.session_state.game_initialized = True

def set_current_image_to_base(route: str):
    # 常にメインヒロインの画像を使用
    hero = st.session_state.get("main_heroine") or {}

    img_path = hero.get("image_path", "")
    
    # If path exists, load bytes to force display
    if img_path and os.path.exists(img_path):
        try:
            with open(img_path, "rb") as f:
                st.session_state.current_image_bytes = f.read()
        except Exception:
            st.session_state.current_image_bytes = None
    else:
        # If no image, clear it (might fallback to main in render logic, but explicit None is safer than stale bytes)
        st.session_state.current_image_bytes = None

# ルート選択ダイアログは削除（サブヒロイン・BOTHシステム不使用のため）


@st.dialog(lang_mgr.get("text_0008", "📂 ロードメニュー"))
def load_menu_dialog():
    st.caption(lang_mgr.get("text_0009", "ロードするデータを選択してください（現在の進行状況は上書きされます）"))
    
    save_dir = get_save_dir()
    files = []
    if os.path.exists(save_dir):
        files = [f for f in os.listdir(save_dir) if f.endswith(".json")]
        # 更新日時順にソート（新しい順）
        files.sort(key=lambda x: os.path.getmtime(os.path.join(save_dir, x)), reverse=True)
    
    if not files:
        st.info(lang_mgr.get("text_0010", "セーブデータがありません"))
        if st.button(lang_mgr.get("text_0011", lang_mgr.get("text_0016", lang_mgr.get("text_0019", lang_mgr.get("text_0025", lang_mgr.get("text_0028", lang_mgr.get("text_0033", lang_mgr.get("text_0035", "閉じる")))))))):
            st.rerun()
        return

    # File List
    valid_count = 0
    for fname in files:
        path = os.path.join(save_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 【重要】ゲームセーブデータ（save_versionがあるもの）だけを表示するフィルター
            if "save_version" not in data:
                continue

            valid_count += 1
            saved_at = data.get("saved_at", "Unknown Date")
            summary = data.get("summary", fname)
            
            # Button for each save
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{summary}**")
                st.caption(f"📅 {saved_at} | 📄 {fname}")
            with col2:
                if st.button(lang_mgr.get("text_0012", "ロード"), key=f"btn_load_{fname}", width="stretch"):
                    if load_game_state(path):
                        st.toast(lang_mgr.get("text_0013", "ロードしました: {summary}"), icon="📂")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error(lang_mgr.get("text_0014", "ロードに失敗しました"))
            st.divider()
            
        except Exception:
            continue
            
    if valid_count == 0:
        st.info(lang_mgr.get("text_0015", "有効なゲームセーブデータが見つかりません（作成データは除外されています）"))
        if st.button(lang_mgr.get("text_0011", lang_mgr.get("text_0016", lang_mgr.get("text_0019", lang_mgr.get("text_0025", lang_mgr.get("text_0028", lang_mgr.get("text_0033", lang_mgr.get("text_0035", "閉じる"))))))), key="btn_close_empty"):
            st.rerun()

def apply_background_theme(mode="game"):
    import base64
    import os

    # 1. 画像検索ロジック (変更なし)
    def get_image_data_and_path(base_folder, filename_no_ext):
        extensions = [".png", ".jpg", ".jpeg"]
        for ext in extensions:
            full_path = os.path.join(base_folder, filename_no_ext + ext)
            if os.path.exists(full_path):
                try:
                    with open(full_path, 'rb') as f:
                        data = f.read()
                    return base64.b64encode(data).decode(), full_path
                except Exception:
                    pass
        return None, None

    base_dir = os.path.dirname(os.path.abspath(__file__))
    assets_bg_dir = os.path.join(base_dir, "assets", "background")

    # ▼▼▼ 修正: 世界観分岐を廃止し、現代（bg_modern）に固定 ▼▼▼
    # raw_world = st.session_state.get("world_mode", "現代") ... (削除)
    
    # 常に現代（阿佐ヶ谷）の背景を使用
    file_base = "bg_modern"
    
    # ▲▲▲ 修正ここまで ▲▲▲

    bin_str, _ = get_image_data_and_path(assets_bg_dir, file_base)

    if bin_str:
        bg_css = f"""
            background-image: linear-gradient(rgba(0, 0, 0, 0.4), rgba(0, 0, 0, 0.4)), 
                              url("data:image/png;base64,{bin_str}") !important;
            background-size: cover !important;
            background-attachment: fixed !important;
        """
    else:
        # Default Fallback: Pastel Gradient (Merged from old 'play' theme)
        bg_css = """
        background-image:
            radial-gradient(circle at 50% 10%,
            rgba(0,0,0,0.35) 0%,
            rgba(0,0,0,0.18) 35%,
            rgba(0,0,0,0.40) 100%
            ),
            linear-gradient(180deg,
            #f3d8e6 0%,   /* くすみピンク */
            #dfe0f3 48%,  /* くすみラベンダー */
            #cfe3f0 100%  /* くすみスカイ */
            ) !important;
        background-repeat: no-repeat, no-repeat !important;
        background-size: cover, cover !important;
        background-attachment: fixed, fixed !important;
        """

    # ---------------------------------------------------------
    # 2. CSS生成 (モード別)
    # ---------------------------------------------------------
    
    # 共通ボタンCSS (変更なし)
    common_btn_css = """
        div.stButton > button {
            background: linear-gradient(135deg, #2b1055 0%, #7597de 100%);
            color: #ffffff !important;
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 8px;
        }
        div.stButton > button p { color: #ffffff !important; }
    """

    if mode == "edit":
        # =====================================================
        # EDIT MODE: DARK THEME (既存維持)
        # =====================================================
        st.markdown(f"""
        <style>
            :root, body, .stApp {{ color-scheme: dark !important; }}
            .stApp {{ {bg_css} background-color: #1a1a2e; }}
            
            /* 文字色: 白 */
            h1, h2, h3, h4, h5, h6, p, span, div, label, .stMarkdown {{ color: #f5f5f5 !important; }}
            
            /* 入力欄: ダーク */
            .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {{
                background-color: rgba(20, 25, 35, 0.6) !important;
                color: #f5f5f5 !important;
                -webkit-text-fill-color: #f5f5f5 !important;
            }}
            
            /* プルダウンメニュー: ダーク */
            div[data-baseweb="popover"], div[data-baseweb="menu"] {{
                background-color: #1a1a2e !important;
            }}
            div[data-baseweb="menu"] li {{ color: #f5f5f5 !important; }}
            
            {common_btn_css}
        </style>
        """, unsafe_allow_html=True)

    elif mode == "pre_game":
        # =====================================================
        # PRE-GAME MODE: 背景透過＋暗幕オーバーレイ
        # =====================================================
        st.markdown(f"""
        <style>
        :root, body, .stApp {{ color-scheme: dark !important; }}
        
        /* 1. 背景画像を復帰させる ({bg_css}を使用) */
        .stApp {{
            {bg_css}
            background-color: transparent !important; /* 基本色は透明 */
        }}

        /* 2. 暗幕オーバーレイ (::beforeで被せる) */
        .stApp::before {{
            content: "" !important;
            position: fixed !important; /* スクロールしても追従 */
            top: 0 !important;
            left: 0 !important;
            width: 100vw !important;
            height: 100vh !important;
            background: rgba(0, 0, 0, 0.35) !important; /* 暗さ調整: 0.35 */
            pointer-events: none !important; /* クリック透過 */
            z-index: 1 !important; /* 背景より上 */
        }}

        /* 3. コンテンツを暗幕より手前に出す */
        .main, div[data-testid="stAppViewContainer"], div[data-testid="stHeader"] {{
            position: relative !important;
            z-index: 2 !important; /* オーバーレイより上 */
        }}
        
        /* 4. HD解像度以上でのスクロール固定 (プロフカード等の見切れ防止) */
        @media (min-width: 1280px) {{
            body, .stApp {{
                overflow: hidden !important;
            }}
        }}
        
        /* メインコンテナの背景透過 */
        .main .block-container {{
            background: transparent !important;
        }}
        
        {common_btn_css}
        </style>
        """, unsafe_allow_html=True)

    else:
        # =====================================================
        # GAME MODE: Emergency Fix (CSS Scope Correction)
        # =====================================================
        st.markdown("<script>document.body.classList.remove('phase-title');</script>", unsafe_allow_html=True)
        
        st.markdown(f"""
        <style>
        /* 1. 基本設定 */
        :root, body, .stApp {{ color-scheme: light !important; }}
        .stApp {{ {bg_css} }}
        
        /* 2. チャットエリア限定: 黒文字 */
        /* 画面全体への適用を廃止し、チャットメッセージと特定クラスのみを対象にする */
        [data-testid="stChatMessage"], .chat-window {{ 
            color: #111111 !important; 
        }}
        [data-testid="stChatMessage"] p, [data-testid="stChatMessage"] div, [data-testid="stChatMessage"] span {{
            color: #111111 !important;
        }}

        /* 3. カードスタイル: 白文字保証 */
        .hero-card {{
            color: #ffffff !important;
        }}

        /* 4. 脳内モニタ（タグ）の例外 */
        /* カード内だが、タグだけは「明るい背景＋黒文字」にする */
        .hero-card span[style*="border-radius:999px"] {{
            background-color: #e6e6e6 !important;
            color: #111111 !important; /* 黒文字 */
            border: 1px solid #999 !important;
        }}
        
        /* 5. UIパーツ調整 */
        .stSelectbox div[data-baseweb="select"] > div {{
            background-color: rgba(30, 30, 40, 0.9) !important;
            color: #ffffff !important;
            border: 1px solid rgba(255,255,255,0.3) !important;
        }}
        div[data-baseweb="popover"], div[data-baseweb="menu"], ul[data-baseweb="menu"] {{
            background-color: #ffffff !important;
        }}
        div[data-baseweb="menu"] li {{ color: #111111 !important; }}

        /* 6. レイアウト調整 */
        div[data-testid="stAppViewContainer"] .main .block-container {{
            padding-top: 0px !important; margin-top: 0px !important;
        }}
        header[data-testid="stHeader"], div[data-testid="stToolbar"] {{ display: none !important; }}
        
        {common_btn_css}
        </style>
        """, unsafe_allow_html=True)
    # print("--- Theme Applied ---\\n")

@st.dialog(lang_mgr.get("text_0017", "📝 テキストエディタ"))
def open_edit_modal():
    # Find indices using existing helpers
    m_i, n_i, s_i = find_last_both_blocks()
    u_i = find_last_index("user")

    # Build available tabs dynamically
    targets = {}
    if m_i >= 0: targets["MAIN"] = m_i
    if s_i >= 0: targets["SUB"] = s_i
    if n_i >= 0: targets["NARR"] = n_i
    if u_i >= 0: targets["USER"] = u_i

    if not targets:
        st.error(lang_mgr.get("text_0018", "編集可能な履歴がありません"))
        if st.button(lang_mgr.get("text_0011", lang_mgr.get("text_0016", lang_mgr.get("text_0019", lang_mgr.get("text_0025", lang_mgr.get("text_0028", lang_mgr.get("text_0033", lang_mgr.get("text_0035", "閉じる")))))))): st.rerun()
        return

    # Target Selector
    selection = st.radio(lang_mgr.get("text_0020", "編集対象"), list(targets.keys()), horizontal=True, key="dlg_edit_sel")
    target_idx = targets[selection]

    # Get Current Text
    current_text = st.session_state.chat_history[target_idx]["parts"][0]
    
    # Text Area
    new_text = st.text_area(lang_mgr.get("text_0021", "編集内容"), value=current_text, height=300, key=f"dlg_edit_area_{target_idx}")

    # Actions
    c1, c2 = st.columns([1, 1])
    
    with c1:
        if selection == "USER":
            if st.button(lang_mgr.get("text_0022", "再送信 (Resend)"), type="primary", width="stretch"):
                # Update history and trigger resend logic
                st.session_state.chat_history[target_idx]["parts"][0] = new_text
                del st.session_state.chat_history[target_idx+1:]
                st.session_state.resend_user_mode = True
                handle_input(new_text) # Re-generate response
                st.rerun()
        else:
            if st.button(lang_mgr.get("text_0023", "保存 (Save)"), type="primary", width="stretch"):
                # Save to pending_edits (preserving original logic)
                st.session_state.pending_edits[target_idx] = new_text
                st.toast(lang_mgr.get("text_0024", "編集を保存しました（{selection}）"), icon="✅")
                st.rerun()

    with c2:
        if st.button(lang_mgr.get("text_0011", lang_mgr.get("text_0016", lang_mgr.get("text_0019", lang_mgr.get("text_0025", lang_mgr.get("text_0028", lang_mgr.get("text_0033", lang_mgr.get("text_0035", "閉じる"))))))), width="stretch"):
            st.rerun()

@st.dialog(lang_mgr.get("text_0026", "🔍 生成プロンプト (Debug)"))
def open_debug_modal():
    if "last_generated_prompt" in st.session_state:
        st.caption(lang_mgr.get("text_0027", "直近の画像生成に使用されたプロンプトです（BREAK構文などを確認できます）"))
        st.code(st.session_state.last_generated_prompt, language="text")
        
        if st.button(lang_mgr.get("text_0011", lang_mgr.get("text_0016", lang_mgr.get("text_0019", lang_mgr.get("text_0025", lang_mgr.get("text_0028", lang_mgr.get("text_0033", lang_mgr.get("text_0035", "閉じる"))))))), width="stretch"):
            st.rerun()
    else:
        st.error(lang_mgr.get("text_0029", "プロンプトデータがありません"))

@st.dialog(lang_mgr.get("text_0030", "📖 彼女の秘密の日記（Memory）"))
def show_memory_dialog():
    st.caption(lang_mgr.get("text_0031", "※彼女が夜、こっそり書き留めている日記のようです……"))
    st.divider()

    # 常にメインヒロインを対象とする
    target = st.session_state.get("chat_heroine")
    
    if not target:
        st.error(lang_mgr.get("text_0032", "ヒロインデータが見つかりません。"))
        if st.button(lang_mgr.get("text_0011", lang_mgr.get("text_0016", lang_mgr.get("text_0019", lang_mgr.get("text_0025", lang_mgr.get("text_0028", lang_mgr.get("text_0033", lang_mgr.get("text_0035", "閉じる")))))))): st.rerun()
        return

    # 記憶リスト（memory_log）を表示
    memories = getattr(target, "memory_log", [])
    
    if not memories:
        st.info(lang_mgr.get("text_0034", "まだ思い出は記録されていません。"))
    else:
        # 新しい順に表示したい場合は reversed(memories) を使う
        for mem in reversed(memories):
            st.markdown(f"{mem}")
            st.markdown("---")
            
    if st.button(lang_mgr.get("text_0011", lang_mgr.get("text_0016", lang_mgr.get("text_0019", lang_mgr.get("text_0025", lang_mgr.get("text_0028", lang_mgr.get("text_0033", lang_mgr.get("text_0035", "閉じる"))))))), key="close_mem_dialog"):
        st.rerun()

def render_game_screen():
    # 言語設定を最初に取得
    current_lang = st.session_state.get("language", "jp")
    
    components.inject_custom_css()
    
    # 共通関数で背景適用 (Gameモード)
    apply_background_theme("game")

    # --- Gap Kill CSS ---

    # --- Gap Kill CSS ---
    st.markdown("""
<style>
/* === ここから上部余白削除用CSS === */

/* メインコンテナの上部余白を極限まで削る */
/* メインコンテナの上部余白を極限まで削る（競合回避のため0化） */
.block-container {
    padding-top: 0px !important; 
    margin-top: 0px !important;
    padding-bottom: 5rem !important; /* 下部はチャット入力欄のために確保 */
    max-width: 100% !important;
}

/* ヘッダー（ハンバーガーメニュー等）の領域を物理的に抹消 */
header[data-testid="stHeader"] {
    display: none !important;
    height: 0 !important;
}

/* ツールバー等の干渉を防ぐ */
div[data-testid="stToolbar"] {
    display: none !important;
}

/* その他、予期せぬ上部マージンを持つ要素をリセット */
.main > div:first-child {
    padding-top: 0 !important;
    margin-top: 0 !important;
}

/* =========================
   GAME UI ABSOLUTE TOP ALIGN
========================= */

/* 最上位ラッパーの余白完全除去 */
html, body {
    margin: 0 !important;
    padding: 0 !important;
}

[data-testid="stAppViewContainer"] {
    padding-top: 0px !important;
    margin-top: 0px !important;
}

/* Streamlit main全体を上詰め */
.stApp {
    padding-top: 0px !important;
    margin-top: 0px !important;
}

/* mainセクション直下のブロック余白殺し */
.main > div:first-child {
    margin-top: 0px !important;
    padding-top: 0px !important;
}

/* block-container を完全ベタ付 */
.block-container {
    padding-top: 0px !important;
    margin-top: 0px !important;
}

/* 念押し：section.main 経由の余白も殺す */
section.main .block-container {
    padding-top: 0px !important;
    margin-top: 0px !important;
}

/* 上部ヘッダー完全無効化 */
header[data-testid="stHeader"] {
    height: 0px !important;
    min-height: 0px !important;
    margin: 0px !important;
    padding: 0px !important;
    display: none !important;
}

/* ツールバー領域も完全に殺す */
div[data-testid="stToolbar"] {
    height: 0px !important;
    min-height: 0px !important;
    margin: 0px !important;
    padding: 0px !important;
    display: none !important;
}

/* 最上段ブロックの謎マージン対策 */
.main > div:first-child {
    margin-top: 0px !important;
    padding-top: 0px !important;
}

/* =========================
   GAME BUTTON DESIGN
========================= */

.stButton > button {
    background: linear-gradient(180deg, #3b2f4a 0%, #241c30 100%) !important;
    color: #f3e9ff !important;
    border: 1px solid rgba(200,160,255,0.35) !important;
    border-radius: 14px !important;
    padding: 10px 18px !important;
    font-weight: 600 !important;
    box-shadow: 0 6px 18px rgba(0,0,0,0.35) !important;
    transition: all 0.2s ease !important;
}

.stButton > button:hover {
    background: linear-gradient(180deg, #4a3b62 0%, #2c2140 100%) !important;
    box-shadow: 0 8px 22px rgba(0,0,0,0.45) !important;
    transform: translateY(-1px);
}

/* primary / secondary の色崩れ防止 */
button[kind="primary"],
button[kind="secondary"] {
    background: linear-gradient(180deg, #3b2f4a 0%, #241c30 100%) !important;
    color: #f3e9ff !important;
    border-radius: 14px !important;
}

/* =========================
   END GAME UI
========================= */

/* =========================
   GAME TOP SPACE KILL (FINAL OVERRIDE)
   (render_game_screen内でのみ注入すること)
========================= */

/* 上部余白：完全ゼロ */
html, body {
  margin: 0 !important;
  padding: 0 !important;
}

/* Streamlit main領域の上余白をゼロ */
section[data-testid="stMain"]{
  padding-top: 0px !important;
  margin-top: 0px !important;
}

/* block-container の上余白をゼロ（これが最優先） */
div[data-testid="stMainBlockContainer"],
.block-container,
section.main .block-container,
.main .block-container{
  padding-top: 0px !important;
  margin-top: 0px !important;
}

/* 縦レイアウトの“間隔(gap)”をゼロに（余白の本体がこれの場合に効く） */
/* gap:0 はオーバーラップの原因になるので無効化（下部で再定義）
div[data-testid="stVerticalBlock"],
div.stVerticalBlock{
  gap: 0px !important;
}
*/

/* 先頭要素の余白を念押しでゼロ */
div[data-testid="stVerticalBlock"] > div:first-child,
div.stVerticalBlock > div:first-child{
  margin-top: 0px !important;
  padding-top: 0px !important;
}

/* 上部UI領域を消して余白化を防ぐ */
header[data-testid="stHeader"],
div[data-testid="stToolbar"],
div[data-testid="stDecoration"]{
  height: 0px !important;
  min-height: 0px !important;
  margin: 0px !important;
  padding: 0px !important;
  display: none !important;
}
</style>
<style>
/* =========================
   GAME LAYOUT STABLE TOP + SAFE SPACING
   (render_game_screen内でのみ注入)
========================= */

/* 上部は常にゼロ */
section[data-testid="stMain"],
div[data-testid="stMainBlockContainer"],
.block-container,
section.main .block-container,
.main .block-container{
  padding-top: 0px !important;
  margin-top: 0px !important;
}

/* ✅ root(最上段)の縦コンテナだけ gap をゼロに固定（上の余白復活を防ぐ） */
div[data-testid="stMainBlockContainer"] > div[data-testid="stVerticalBlock"],
div[data-testid="stMainBlockContainer"] > div.stVerticalBlock{
  gap: 0px !important;
}

/* ✅ root以外（内側）の縦コンテナは適度な間隔を持たせて重なり防止 */
div[data-testid="stMainBlockContainer"] div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"],
div[data-testid="stMainBlockContainer"] div.stVerticalBlock div.stVerticalBlock{
  gap: 0.75rem !important;
}

/* 横並びブロックの間隔（ボタン列など） */
div[data-testid="stHorizontalBlock"],
div.stHorizontalBlock{
  row-gap: 0.5rem !important;
  column-gap: 0.8rem !important;
}

/* 先頭要素の余白を念押しでゼロ（上が空く事故防止） */
div[data-testid="stMainBlockContainer"] > div[data-testid="stVerticalBlock"] > div:first-child,
div[data-testid="stMainBlockContainer"] > div.stVerticalBlock > div:first-child{
  margin-top: 0px !important;
  padding-top: 0px !important;
}

/* =========================
   GAME: PAGE SCROLL LOCK (FINAL)
========================= */

/* ページ全体を固定（スクロール禁止） */
html, body {
  height: 100% !important;
  overflow: hidden !important;
}

/* Streamlit全体も固定 */
.stApp,
[data-testid="stAppViewContainer"] {
  height: 100vh !important;
  overflow: hidden !important;
}

/* main領域も固定 */
section[data-testid="stMain"],
div[data-testid="stMainBlockContainer"] {
  height: 100vh !important;
  overflow: hidden !important;
}
/* GAME: CHAT AREA TALLER */
div[data-testid="stChatMessage"],
div[data-testid="stChatMessageContent"],
div.stChatMessage,
div.stChatMessageContent{
  max-width: 100% !important;
}

/* chat入力欄より上のチャット表示ブロックを広く見せるため、中央カラムの上側余白を増やす */
[data-testid="stChatInput"]{
  margin-top: 8px !important;
}

/* GAME: MOVE ACTIONS DOWN A BIT MORE */
.center-actions{
  margin-top: 38px !important;
}
/* =========================
   SPINNER TEXT NATURAL BRIGHTNESS
========================= */

div[data-testid="stSpinner"] > div {
    /* 真っ白(#ffffff)ではなく、少し落ち着いた明るいグレー */
    color: #e6e6e6 !important;
    
    /* 背景画像と同化しないように、少しだけ影をつける（視認性確保） */
    text-shadow: 1px 1px 2px rgba(0,0,0,0.7) !important;
    
    /* 透過を防ぐ */
    opacity: 1 !important;
}
</style>
""",unsafe_allow_html=True)

    # --- Loading Logic with Guard ---
    def load_from_save(save_path: str):
        if not save_path or not os.path.exists(save_path):
            return None
        with open(save_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # Logic moved to game_start_dummy_if_needed to prevent double loading
    # if not st.session_state.game_initialized: ... (Removed)

    # ▼▼▼ UI Scope Fix: Define variables before columns ▼▼▼
    main_h = st.session_state.chat_heroine
    
    # 常にメインヒロインのみを使用
    st.session_state.current_route = "main"

    col_left, col_center, col_right = st.columns([1, 2, 1])

    with col_left:
        # 体験版バッジを上部に表示（クリック可能なリンク）
        from config import IS_DEMO_MODE
        if IS_DEMO_MODE:
            st.markdown("""
            <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 10px; border-radius: 8px; text-align: center; margin-bottom: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); cursor: pointer; transition: transform 0.2s ease;" onclick="window.open('https://x.com/MugenH50915', '_blank')" onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
                <a href="https://x.com/MugenH50915" target="_blank" style="color: white; font-weight: bold; font-size: 16px; text-decoration: none; display: block;">🎮 体験版（公式Xはこちら）</a>
            </div>
            """, unsafe_allow_html=True)

        # Card Rendering (メインヒロインのみ)
        if main_h:
            components.render_character_card(main_h, components.MAIN_COLORS, is_active=True, show_debug=False)


            # --- Skill UI Removed (Moved to Right) ---


        # --- SAVE / LOAD / BACK / EDIT Buttons ---
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        


        # Changed to 4 columns to include EDIT
        gs1, gs2, gs3, gs4 = st.columns(4)
        
        # 体験版モード: セーブ・ロードボタンを無効化
        from config import IS_DEMO_MODE
        
        # 言語設定を取得（関数の最初で既に定義済みだが、念のため）
        current_lang = st.session_state.get("language", "jp")
        
        with gs1:
            save_label = lang_mgr.get("text_0162", "SAVE")
            if IS_DEMO_MODE:
                if current_lang == "en":
                    disabled_text = f"💾 {save_label} (Not available in trial version)"
                    help_text = "Save function is not available in trial version"
                elif current_lang == "zh-CN":
                    disabled_text = f"💾 {save_label} (体验版中不可用)"
                    help_text = "体验版中保存功能不可用"
                elif current_lang == "zh-TW":
                    disabled_text = f"💾 {save_label} (體驗版中不可用)"
                    help_text = "體驗版中保存功能不可用"
                else:
                    disabled_text = f"💾 {save_label} (体験版では利用できません)"
                    help_text = "体験版ではセーブ機能は利用できません"
                st.button(disabled_text, width="stretch", key="game_save", disabled=True, help=help_text)
            else:
                if st.button(f"💾 {save_label}", width="stretch", key="game_save"):
                    # Manual Save with Timestamp
                    path = save_game_state(manual_save=True)
                    if path:
                        st.toast(lang_mgr.get("text_0036", "セーブしました！"), icon="💾")
                    else:
                        st.error(lang_mgr.get("text_0037", "セーブ失敗"))
                    
        with gs2:
            load_label = lang_mgr.get("text_0163", "LOAD")
            if IS_DEMO_MODE:
                if current_lang == "en":
                    disabled_text = f"📖 {load_label} (Not available in trial version)"
                    help_text = "Load function is not available in trial version"
                elif current_lang == "zh-CN":
                    disabled_text = f"📖 {load_label} (体验版中不可用)"
                    help_text = "体验版中加载功能不可用"
                elif current_lang == "zh-TW":
                    disabled_text = f"📖 {load_label} (體驗版中不可用)"
                    help_text = "體驗版中載入功能不可用"
                else:
                    disabled_text = f"📖 {load_label} (体験版では利用できません)"
                    help_text = "体験版ではロード機能は利用できません"
                st.button(disabled_text, width="stretch", key="game_load", disabled=True, help=help_text)
            else:
                if st.button(f"📖 {load_label}", width="stretch", key="game_load"):
                    load_menu_dialog()
                
        with gs3:
            if st.button("↩ BACK", width="stretch", key="game_back_to_rel"):
                # オートセーブ
                save_game_state(manual_save=False)
                
                # ターン数をリセット
                st.session_state.day_turn_count = 0
                
                # ★ここを修正：戻り先をプロフ画面（生成画面）に変更
                st.session_state.phase = "create"
                
                st.rerun()

        with gs4:
            # Moved EDIT button here
            if st.button("✏️ EDIT", width="stretch", key="btn_open_modal"):
                open_edit_modal()
        
        # New Button for Diary
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if st.button(lang_mgr.get("text_0038", "📖 日記を読む"), width="stretch", help=lang_mgr.get("text_0039", "彼女視点の思い出を振り返ります")):
            show_memory_dialog()

        # ★追加: エクスポートボタン (日記ボタンの下に配置)
        from config import IS_DEMO_MODE
        if IS_DEMO_MODE:
            st.button("💌 共有 (Export) (体験版では利用できません)", width="stretch", key="btn_export_card", disabled=True, help="体験版ではエクスポート機能は利用できません")
        else:
            if st.button("💌 共有 (Export)", width="stretch", key="btn_export_card", help="カノジョのデータを『カード』として書き出します（会話ログは含まれません）"):
                import json
                import re
                import base64
                from datetime import datetime
                
                # 1. 保存データ作成（ログ・日記を除外したクリーンデータ）
                img_b64 = ""
                # 現在表示中の画像を取得
                current_bytes = st.session_state.get("current_image_bytes")
                if not current_bytes:
                    # なければメインヒロインの画像パスから読み込む
                    h = st.session_state.get("chat_heroine")
                    if h and getattr(h, "image_path", "") and os.path.exists(h.image_path):
                         try:
                             with open(h.image_path, "rb") as f:
                                 current_bytes = f.read()
                         except Exception as e:
                             print(f"Warning: Failed to read image file {h.image_path}: {e}")

                if current_bytes:
                    try:
                        img_b64 = base64.b64encode(current_bytes).decode('utf-8')
                    except Exception as e:
                        print(f"Warning: Failed to encode image to base64: {e}")

                # 初期生成時のデータを取得
                ui = st.session_state.get("user_input", {})
                # もしセッションになければ、現在のヒロインオブジェクトから復元を試みる
                if not ui and st.session_state.chat_heroine:
                     h = st.session_state.chat_heroine
                     ui = {
                         "Name": getattr(h, "name", "NoName"),
                         "Job": getattr(h, "job", ""),
                         "Visual Age": getattr(h, "age", ""),
                         "Personality": getattr(h, "personality", ""),
                         # ...他に必要な項目があれば追加
                     }

                export_data = {
                    "format": "kanojo_card_v1",
                    "user_input": dict(ui),
                    "final_texts": dict(st.session_state.get("final_texts", {})),
                    "final_status": dict(st.session_state.get("final_status", {})), # 初期ステータス
                    "generated_theme": st.session_state.get("generated_theme", ""),
                    "image_b64": img_b64,
                    "created_at": datetime.now().strftime("%Y/%m/%d %H:%M"),
                    "note": "Shared Kanojo Card (Clean Data)"
                }
                
                # 2. ファイル書き出し
                try:
                    save_dir = get_card_dir()
                    name = ui.get("Name", "NoName")
                    safe_name = re.sub(r'[\\/:*?"<>|]+', '', name)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"Card_{safe_name}_{ts}.json"
                    filepath = os.path.join(save_dir, filename)
                    
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(export_data, f, ensure_ascii=False, indent=2)
                        
                    st.toast(f"カードを作成しました！\nUserData/KANOJO_CARDS/{filename}", icon="💌")
                except Exception as e:
                    st.error(f"エクスポート失敗: {e}")



    with col_center:
        # components.display_chat(st.session_state.chat_history) # Moved to chat_ph
        # Using chat_ph below
        pass
        
        # Phase 2: AI Turn (Pending)
        # --- シンプル入力処理 ---
        # Phase 2: AI Turn (Pending)
        # --- シンプル入力処理 (Reverted for "Writing..." indicator) ---
        chat_ph = st.empty()
        with chat_ph.container():
             components.display_chat(st.session_state.chat_history)
        
        # 体験版: 15ターン制限チェック または ゲーム終了フラグ
        from config import IS_DEMO_MODE, DEMO_HP_URL
        user_turn_count = sum(1 for msg in st.session_state.chat_history if msg.get("role") == "user")
        is_turn_14 = IS_DEMO_MODE and user_turn_count == 14
        is_turn_15_reached = IS_DEMO_MODE and user_turn_count >= 15
        is_game_ended = IS_DEMO_MODE and st.session_state.get("demo_game_ended", False)
        
        if is_game_ended or is_turn_15_reached:
            # 15ターンに達したら新規ウィンドウでHP誘導リンクを表示
            st.markdown("---")
            # モーダル風の表示
            demo_x_url = "https://x.com/MugenH50915"
            st.markdown(f"""
            <div style="
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 40px;
                border-radius: 20px;
                text-align: center;
                box-shadow: 0 10px 40px rgba(0,0,0,0.5);
                z-index: 9999;
                max-width: 600px;
                width: 90%;
            ">
                <h2 style="color: white; margin-bottom: 20px; font-size: 28px;">🎉 体験版をプレイしていただき、ありがとうございました！</h2>
                <p style="color: rgba(255,255,255,0.95); font-size: 20px; margin-bottom: 24px; line-height: 1.6;">
                    最新情報は公式Xでお知らせします。<br>
                    フォローしてアップデートをお待ちください！
                </p>
                <p style="color: rgba(255,255,255,0.9); font-size: 18px; margin-bottom: 20px;">
                    <strong>つづきは続報で！</strong>
                </p>
                <a href="{demo_x_url}" target="_blank" style="display: inline-block; background: white; color: #667eea; padding: 18px 50px; border-radius: 30px; text-decoration: none; font-weight: bold; font-size: 20px; box-shadow: 0 6px 20px rgba(0,0,0,0.3); transition: transform 0.2s;">
                    🔔 Xで最新情報を確認！
                </a>
            </div>
            <div style="
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.7);
                z-index: 9998;
            "></div>
            """, unsafe_allow_html=True)
            # 会話入力を無効化
            st.info("体験版は15ターンまでです。フル版では無制限にプレイできます！")
        elif is_turn_14:
            # 14ターン目: エンディング（会話は継続可能）
            pass  # エンディングはhandle_input内で処理
        else:
            if prompt := st.chat_input(lang_mgr.get("text_0040", "メッセージ..."), key="chat_box", disabled=(is_turn_15_reached or is_game_ended)):
                 handle_input(prompt, chat_ph=chat_ph)
                 st.rerun()
             
        if st.session_state.chat_heroine:
            # サブヒロイン・BOTHシステムは使用しない

            # ==================================================
            # ★ 1段目：アプローチ選択 (Auto-Write)
            # ==================================================
            st.markdown('<div class="center-actions" style="margin-top:10px;">', unsafe_allow_html=True)
            
            # 3つのアプローチボタン
            ac1, ac2, ac3 = st.columns(3)
            chosen_tone = None
            
            with ac1:
                if st.button(lang_mgr.get("text_0041", "💬 無難"), help=lang_mgr.get("text_0042", "優しく微笑む・安心感・包容力"), width="stretch"):
                    chosen_tone = "safe"
            with ac2:
                if st.button(lang_mgr.get("text_0043", "😈 攻め"), help=lang_mgr.get("text_0044", "距離を詰める・リードする・男らしく"), width="stretch"):
                    chosen_tone = "bold"
            with ac3:
                if st.button(lang_mgr.get("text_0045", "🎲 斜め上"), help=lang_mgr.get("text_0046", "予想外の行動・ユーモア・場を和ませる"), width="stretch"):
                    chosen_tone = "crazy"

            # --- アプローチ実行ロジック ---
            if chosen_tone:
                # 0. gemini_clientの確認
                if not st.session_state.get("gemini_client"):
                    st.error("APIキーが設定されていません。設定を確認してください。")
                    st.stop()
                
                with st.spinner(lang_mgr.get("text_0047", "主人公の行動を思考中...")):
                    # 1. ヒロイン名取得（常にメイン）
                    h_obj = st.session_state.chat_heroine
                    h_name = getattr(h_obj, "name", "彼女")

                    # 2. LLMで主人公のセリフ生成
                    try:
                        user_text = st.session_state.gemini_client.generate_protagonist_response(
                            st.session_state.chat_history, 
                            chosen_tone, 
                            h_name
                        )
                    except Exception as e:
                        st.error(f"エラーが発生しました: {str(e)}")
                        st.stop()
                    
                    # 3. handle_input に渡して実行（履歴追加＆ヒロイン返信）
                    # chat_ph は既存のプレースホルダー変数を使用
                    handle_input(user_text, chat_ph=chat_ph)
                    st.rerun()

            # ==================================================
            # ★ 2段目：スキル ＆ 一日終了
            # ==================================================
            # 左:選択 / 中:発動・解除 / 右:一日終了
            sc1, sc2, sc3 = st.columns(3)
            
            # --- Col 1: スキル選択 (プルダウンのみ) ---
            with sc1:
                skill_keys = list(SKILL_DEFINITIONS.keys())
                idx = 0
                if st.session_state.active_skill_name in skill_keys:
                    idx = skill_keys.index(st.session_state.active_skill_name)
                    
                sel = st.selectbox("Skill", skill_keys, index=idx, label_visibility="collapsed", key="skill_selector_main")
                
                # 選択されたスキル名を保存
                st.session_state.active_skill_name = sel
                
                # 通常スキルの場合はここで効果をセット（自由記述の場合は下で処理）
                if sel != "✨ 自由記述":
                    st.session_state.active_skill_effect = SKILL_DEFINITIONS[sel]

            # --- Col 2: 発動 / 解除 ボタン ---
            with sc2:
                if st.session_state.get("is_skill_active", False):
                    # === 解除ボタン ===
                    if st.button(lang_mgr.get("text_0048", "解除"), type="primary", width="stretch", key="btn_skill_release"):
                        # 既存のステータス回復処理
                        skill_name = st.session_state.active_skill_name
                        skill_data = st.session_state.active_skill_data
                        
                        targets = [st.session_state.chat_heroine]

                        # デレ系スキルのステータス戻し
                        if "デレ" in skill_name:
                            for h in targets:
                                if h:
                                    h.reason = min(100, int(getattr(h, "reason", 0)) + 30)
                                    h.guard = min(100, int(getattr(h, "guard", 0)) + 20)
                            st.toast(lang_mgr.get("text_0049", "正気に戻った！"), icon="😳")

                        st.session_state.is_skill_active = False
                        st.session_state.active_skill_data = {}
                        
                        # ★修正: アクシデントの実とラッキースケベの場合は簡潔なメッセージのみ（多言語対応）
                        if "アクシデント" in skill_name:
                            # アクシデントの実の解除時は多言語対応のメッセージを表示
                            release_text = lang_mgr.get("text_0193", "（ようやく二人は離れた）")
                            st.toast(lang_mgr.get("text_0049", "スキルを解除しました！"), icon="✨") # トーストのみ
                        elif "ラッキースケベ" in skill_name or "ラキスケ" in skill_name:
                            # ラキスケの実の解除時は多言語対応のメッセージを表示
                            happening_text = lang_mgr.get("text_0194", "（ハプニングは収まった）")
                            st.toast(lang_mgr.get("text_0049", "スキルを解除しました！"), icon="✨") # トーストのみ
                        else:
                            # その他のスキル解除時は簡潔なメッセージとAI生成リアクション
                            st.toast(lang_mgr.get("text_0049", "スキルを解除しました！"), icon="✨") # トーストのみ
                            
                            with st.spinner(lang_mgr.get("text_0050", "解除中...")): 
                                h_obj = st.session_state.chat_heroine
                                if st.session_state.current_route == "sub": h_obj = st.session_state.chat_sub_heroine
                                
                                sys_prompt = h_obj.get_system_prompt(False, None)
                                sys_prompt += "\n【状況】スキル効果が切れ、正気に戻りました。一言と仕草を3行以内で描写してください。"
                                
                                res = st.session_state.gemini_client.generate_response(st.session_state.chat_history, sys_prompt)
                                if res:
                                    st.session_state.chat_history.append({"role": "model", "parts": [res], "speaker_name": h_obj.name})

                        st.rerun()

                else:
                    # === 発動ボタン ===
                    if st.button(lang_mgr.get("text_0051", "発動"), width="stretch", key="btn_skill_activate"):
                        # スピナーを最初に表示して処理全体を囲む
                        with st.spinner(lang_mgr.get("text_0057", "世界改変中...彼女の様子が変化しています...")):
                            p_name = st.session_state.get("user_name", "君")
                            current_skill_data = {}
                            
                            # ★修正: 自由記述のテキスト取得を確実に
                            if st.session_state.active_skill_name == "✨ 自由記述":
                                # ウィジェットのキーから直接取得（ボタンより下にあってもstateには入っているため）
                                custom_text = st.session_state.get("skill_free_input_box", "").strip()
                                
                                if not custom_text:
                                    st.error(lang_mgr.get("text_0052", "効果を入力してください！"))
                                    st.stop()
                                    
                                current_skill_data = {
                                    "start": f"（世界の常識が改変される：{custom_text}）",
                                    "during": f"【世界法則（最優先・絶対）】{custom_text}\n- この法則はこの世界の「当然の常識」であり、登場人物は一切疑問に思わない。\n- 登場人物は受け身ではなく、常識に沿って自然に能動行動を取る。\n- 次のレスポンスでは、必ず「行動」として法則の結果を最低1つ描写する（口だけ禁止）。",
                                    "end": "（常識改変が解除され、元の価値観に戻る）"
                                }
                                narration_text = f"（スキル発動：自由記述）\n（『{custom_text}』がこの世界の常識になった。\n彼女は最初からそうだったかのように受け入れている。）"
                            
                            else:
                                # 通常スキル
                                sel_key = st.session_state.active_skill_name
                                if sel_key in SKILL_DEFINITIONS:
                                    current_skill_data = SKILL_DEFINITIONS[sel_key]
                                else:
                                    current_skill_data = {"start":"(発動)", "during":"", "end":""}
                                    
                                start_txt = current_skill_data["start"].replace("{player}", p_name)
                                narration_text = f"{start_txt}"

                            # ステータス更新
                            st.session_state.active_skill_data = current_skill_data
                            st.session_state.is_skill_active = True
                            st.session_state.skill_just_activated = True
                            
                            # デレ系の数値変動（既存ロジック）
                            # ステータス変動ロジック (Dynamic from SKILL_DEFINITIONS)
                            skill_bonus = current_skill_data.get("stat_bonus", {})
                            
                            if skill_bonus:
                                targets = [st.session_state.chat_heroine]
                                
                                feedback_list = []
                                
                                # Prepare toast message parts
                                if skill_bonus.get("chastity", 0) != 0:
                                    feedback_list.append(f"ガード{skill_bonus['chastity']:+}")
                                if skill_bonus.get("lust", 0) != 0:
                                    feedback_list.append(f"興奮度{skill_bonus['lust']:+}")
                                if skill_bonus.get("love", 0) != 0:
                                    feedback_list.append(f"好感度{skill_bonus['love']:+}")

                                for h in targets:
                                    if h:
                                        # Chastity / Guard (Linked)
                                        if "chastity" in skill_bonus:
                                            val = max(0, int(getattr(h, "chastity", 50)) + int(skill_bonus["chastity"]))
                                            h.chastity = val
                                            h.guard = val # Sync alias
                                            
                                        # Lust (Max 100)
                                        if "lust" in skill_bonus:
                                            h.lust = min(100, int(getattr(h, "lust", 0)) + int(skill_bonus["lust"]))
                                            
                                        # Love (Max 100)
                                        if "love" in skill_bonus:
                                            h.love = min(100, int(getattr(h, "love", 0)) + int(skill_bonus["love"]))
                                
                                # Toast Feedback
                                if feedback_list:
                                    msg = " / ".join(feedback_list)
                                    skill_name = st.session_state.active_skill_name
                                    toast_msg = f"{skill_name}発動！ {msg}"
                                    st.toast(toast_msg, icon="✨")

                            # 1. ナレーションを履歴に追加
                            st.session_state.chat_history.append({"role": "model", "parts": [narration_text], "speaker_name": "System"})
                            
                            # ★修正: セリフ禁止・場所禁止でリアクションのみ生成
                            # 現在のヒロイン取得
                            h_obj = st.session_state.chat_heroine
                            # 常にメインヒロイン
                             
                            # システムプロンプト構築（スキル発動状態）
                            sys_prompt = h_obj.get_system_prompt(True, current_skill_data)
                             
                            # ★追加制約：セリフ禁止 ＆ 場所出力禁止
                            sys_prompt += """
                            【状況】
                            たった今、世界改変スキルが発動しました。
                            直前のSystemメッセージにある変更内容に従い、ヒロインの態度や表情が変化する様子を描写してください。

                            【重要：出力ルール（絶対厳守）】
                            1. **セリフ（「」や『』）は一切書かないでください。**
                               - まだ話させないでください。まずは行動・表情・視線の変化だけで、異変を伝えてください。
                            2. **場所情報（<loc>タグなど）は一切出力しないでください。**
                            3. プレイヤーが思わず声をかけたくなるような、意味深な描写で止めてください。
                            """
                             
                            # 生成実行
                            res = st.session_state.gemini_client.generate_response(st.session_state.chat_history, sys_prompt)
                             
                            if res:
                                # 万が一場所タグが含まれていたら削除（念のため）
                                import re
                                clean_res = res
                                # <loc>タグを削除
                                clean_res = re.sub(r"<loc>.*?</loc>", "", clean_res, flags=re.DOTALL)
                                # {base_id: ...} 形式を削除（1行または複数行）
                                clean_res = re.sub(r"\{base_id:\s*[^,}]+,\s*display_name:\s*[^}]+?\}", "", clean_res, flags=re.DOTALL)
                                # JSON形式の場所情報を削除
                                clean_res = re.sub(r'\{[^}]*"base_id"[^}]*\}', "", clean_res, flags=re.DOTALL)
                                clean_res = clean_res.strip()
                                 
                                st.session_state.chat_history.append({"role": "model", "parts": [clean_res], "speaker_name": h_obj.name})

                        st.rerun()

            # --- Col 3: 一日終了 ---
            with sc3:
                # Helper for decay
                def clamp(v): return max(0, min(100, int(v)))

                if st.button(lang_mgr.get("text_0058", "🌙 終了"), key="btn_end_day_main", help=lang_mgr.get("text_0059", "一日を終了して次の日へ"), width="stretch"):
                    # 体験版モード: 日記作成後にゲーム終了
                    from config import IS_DEMO_MODE
                    
                    if IS_DEMO_MODE:
                        # 体験版: 日記を作成してゲーム終了
                        current_hist = st.session_state.chat_history
                        if len(current_hist) > 2: # 会話があった場合のみ
                            with st.spinner(lang_mgr.get("text_0060", "一日の思い出を日記に記しています...")):
                                # 対象ヒロインの特定
                                targets = []
                                # メインヒロインのみ
                                targets = [st.session_state.chat_heroine]
                                
                                for h_mem in targets:
                                    if h_mem:
                                        # 要約プロンプト（修正版：余計な解説を排除）
                                        mem_prompt = f"""
以下の会話ログから、ヒロイン「{h_mem.name}」が夜にこっそり書いた【今日の日記】を作成してください。

【重要：出力ルール（絶対厳守）】
1. **出力するのは「日記の本文」のみ**にしてください。
   - 「〜という日記を作成しました」「編集者として〜」などの**前置き・解説・挨拶は一切禁止**です。
2. **日記の形式:**
   - 日付などのヘッダーは不要です（システム側で付与します）。
   - いきなり「今日は〜」「あのね、〜」のように書き出してください。

【執筆ガイド】
1. **一人称視点:** 「〜しました」という報告ではなく、「〜してドキドキした」「〜が嬉しかった」という**彼女の独白・本音**形式にしてください。
2. **感情と五感:** 「手の温もり」「夕日の眩しさ」「彼（プレイヤー）の匂い」など、感覚的な記憶を重視してください。
3. **具体的なエピソード:** 「デートした」とまとめるのではなく、「クレープのクリームを取ってくれた優しさにときめいた」のように具体的に書いてください。
"""
                                        # 履歴をテキスト化
                                        hist_text = str(current_hist[-20:]) # 直近20ターン程度で十分
                                        
                                        try:
                                            summary = st.session_state.gemini_client.generate_text(mem_prompt + "\\n" + hist_text)
                                            day_label = f"Day {st.session_state.day_count}"
                                            
                                            # ログに追加
                                            if not hasattr(h_mem, "memory_log"): h_mem.memory_log = []
                                            h_mem.memory_log.append(f"【{day_label}】\n{summary.strip()}")
                                            
                                            # --- 追加: 関係性キャッチコピー（称号）の生成 ---
                                            # 日記の内容（summary）と、現在の固定ランク（例: 恋人）を元に、
                                            # 「今の二人」を表す装飾された称号を考えさせる
                                            current_status = getattr(h_mem, "relation_status", "関係なし")
                                            
                                            title_prompt = f"""
あなたはコピーライターです。
ヒロイン「{h_mem.name}」の日記と、現在の関係ランク「{current_status}」を元に、
**「今の二人の関係」を表す、短くてエモいキャッチコピー（称号）** を考えてください。

【ルール】
1. **ベースは「{current_status}」** ですが、形容詞や装飾をつけて状況を表現してください。
2. **10文字以内** で簡潔に。
3. 絵文字を1つ含めても構いません。
4. 例:
   - 「恋人」+ 甘い日記 ➔ 「💓 溺愛中の恋人」
   - 「友達」+ 喧嘩 ➔ 「⚡ 喧嘩するほど仲良し」
   - 「片思い」+ 接近 ➔ 「💘 恋の予感」

出力は称号のテキストのみ（カギカッコ不要）:
"""
                                            
                                            # 日記生成に使った summary (日記本文) を入力に使用
                                            relation_title = st.session_state.gemini_client.generate_text(title_prompt + "\n\n日記内容:\n" + summary).strip()
                                            
                                            # 余計な記号削除
                                            relation_title = relation_title.replace("「", "").replace("」", "").replace('"', "").replace("。", "")
                                            
                                            # ヒロインデータに保存（これがステータスに表示される）
                                            h_mem.relation_title = relation_title
                                            st.toast(lang_mgr.get("text_0061", "称号更新: 『{relation_title}』"), icon="📛")
                                            
                                        except Exception as e:
                                            print(f"Memory Gen Error: {e}")
                        
                        # ゲーム終了フラグを設定
                        st.session_state.demo_game_ended = True
                        # 日記ダイアログを表示
                        show_memory_dialog()
                        st.rerun()
                        return
                    
                    # 【重要】既存の「一日終了」ロジック（通常版）
                    current_hist = st.session_state.chat_history
                    if len(current_hist) > 2: # 会話があった場合のみ
                        with st.spinner(lang_mgr.get("text_0060", "一日の思い出を日記に記しています...")):
                            # 対象ヒロインの特定
                            targets = []
                            # メインヒロインのみ
                            targets = [st.session_state.chat_heroine]
                            
                            for h_mem in targets:
                                if h_mem:
                                    # 要約プロンプト（修正版：余計な解説を排除）
                                    mem_prompt = f"""
以下の会話ログから、ヒロイン「{h_mem.name}」が夜にこっそり書いた【今日の日記】を作成してください。

【重要：出力ルール（絶対厳守）】
1. **出力するのは「日記の本文」のみ**にしてください。
   - 「〜という日記を作成しました」「編集者として〜」などの**前置き・解説・挨拶は一切禁止**です。
2. **日記の形式:**
   - 日付などのヘッダーは不要です（システム側で付与します）。
   - いきなり「今日は〜」「あのね、〜」のように書き出してください。

【執筆ガイド】
1. **一人称視点:** 「〜しました」という報告ではなく、「〜してドキドキした」「〜が嬉しかった」という**彼女の独白・本音**形式にしてください。
2. **感情と五感:** 「手の温もり」「夕日の眩しさ」「彼（プレイヤー）の匂い」など、感覚的な記憶を重視してください。
3. **具体的なエピソード:** 「デートした」とまとめるのではなく、「クレープのクリームを取ってくれた優しさにときめいた」のように具体的に書いてください。
"""
                                    # 履歴をテキスト化
                                    hist_text = str(current_hist[-20:]) # 直近20ターン程度で十分
                                    
                                    try:
                                        summary = st.session_state.gemini_client.generate_text(mem_prompt + "\\n" + hist_text)
                                        day_label = f"Day {st.session_state.day_count}"
                                        
                                        # ログに追加
                                        if not hasattr(h_mem, "memory_log"): h_mem.memory_log = []
                                        h_mem.memory_log.append(f"【{day_label}】\n{summary.strip()}")
                                        
                                        # --- 追加: 関係性キャッチコピー（称号）の生成 ---
                                        # 日記の内容（summary）と、現在の固定ランク（例: 恋人）を元に、
                                        # 「今の二人」を表す装飾された称号を考えさせる
                                        current_status = getattr(h_mem, "relation_status", "関係なし")
                                        
                                        title_prompt = f"""
あなたはコピーライターです。
ヒロイン「{h_mem.name}」の日記と、現在の関係ランク「{current_status}」を元に、
**「今の二人の関係」を表す、短くてエモいキャッチコピー（称号）** を考えてください。

【ルール】
1. **ベースは「{current_status}」** ですが、形容詞や装飾をつけて状況を表現してください。
2. **10文字以内** で簡潔に。
3. 絵文字を1つ含めても構いません。
4. 例:
   - 「恋人」+ 甘い日記 ➔ 「💓 溺愛中の恋人」
   - 「友達」+ 喧嘩 ➔ 「⚡ 喧嘩するほど仲良し」
   - 「片思い」+ 接近 ➔ 「💘 恋の予感」

出力は称号のテキストのみ（カギカッコ不要）:
"""
                                        
                                        # 日記生成に使った summary (日記本文) を入力に使用
                                        relation_title = st.session_state.gemini_client.generate_text(title_prompt + "\n\n日記内容:\n" + summary).strip()
                                        
                                        # 余計な記号削除
                                        relation_title = relation_title.replace("「", "").replace("」", "").replace('"', "").replace("。", "")
                                        
                                        # ヒロインデータに保存（これがステータスに表示される）
                                        h_mem.relation_title = relation_title
                                        st.toast(lang_mgr.get("text_0061", "称号更新: 『{relation_title}』"), icon="📛")
                                        
                                    except Exception as e:
                                        print(f"Memory Gen Error: {e}")

                    # --- 2. Intimacy Check (for Bond) ---
                    h = st.session_state.get("chat_heroine")
                    is_intimate = False
                    if h:
                        cur_tokimeki = int(getattr(h, "tokimeki", 0))
                        cur_reason = int(getattr(h, "reason", 100))
                        if cur_tokimeki >= 60 and cur_reason <= 40:
                            is_intimate = True
                    
                    # --- 2. Bond Level Calc ---
                    base_inc = 1
                    bonus_inc = 5 if is_intimate else 0
                    
                    main_h = st.session_state.get("chat_heroine")
                    # サブヒロインシステムは使用しない

                    def add_bond(target_h, val):
                        if target_h:
                            try:
                                cur = int(getattr(target_h, "bond_level", 0))
                                target_h.bond_level = cur + val
                            except Exception as e:
                                print(f"Warning: Failed to update bond_level: {e}")

                    # メインヒロインのみ
                    if st.session_state.get("met_main", True):
                        add_bond(main_h, base_inc + bonus_inc)

                    # --- 3. Stat Decay & Recovery (Main Heroine Only) ---
                    h_obj = st.session_state.get("chat_heroine")
                    if h_obj:
                        # Natural Decay
                        h_obj.love = clamp(getattr(h_obj, "love", 0) - 1)
                        h_obj.tokimeki = clamp(getattr(h_obj, "tokimeki", 0) - 10)
                        h_obj.possession = clamp(getattr(h_obj, "possession", 30) - 2)
                        
                        # Reason/Guard Recovery (Enhanced)
                        h_obj.reason = clamp(getattr(h_obj, "reason", 100) + 20)
                        h_obj.guard = min(100, int(getattr(h_obj, "guard", 50)) + 10)

                    # --- 4. Day Cycle Update & Event Logic ---
                    # 1. Date Update
                    current_day = int(st.session_state.get("day_count", 1))
                    next_day = current_day + 1
                    st.session_state.day_count = next_day
                    st.session_state.time_of_day = "朝"
                    
                    # ★追加: ターンカウンターをリセット
                    st.session_state.day_turn_count = 0
                    
                    # ★ NEW: Reset Skill State on Day Change
                    st.session_state.is_skill_active = False
                    st.session_state.active_skill_data = {}
                    st.session_state.active_skill_name = ""
                    st.session_state.active_skill_effect = ""

                    
                    # 2. State Reset (Safety)
                    st.session_state.is_r18_scene = False
                    st.session_state.r18_scene_ttl = 0
                    st.session_state.current_location = {
                        "base_id": "99_UNKNOWN",
                        "display_name": "？？？", 
                        "category": "OTHER"
                    }
                    st.session_state.location_text = "？？？"

                    # ==========================================
                    # ★ NEW: 重み付きレアリティ抽選システム
                    # ==========================================
                    
                    # 設定：イベント発生間隔（3日おき）
                    EVENT_INTERVAL = 3
                    # 設定：平和な朝になる確率 (40%)
                    PEACEFUL_CHANCE = 0.4
                    
                    last_event_day = st.session_state.get("last_event_day", 0)
                    event_intro_text = ""
                    
                    # ターゲット取得
                    target_h = st.session_state.get("chat_heroine")
                    # 常にメインヒロイン

                    # --- 抽選ロジック ---
                    # 1. 日数経過チェック
                    if (next_day - last_event_day) >= EVENT_INTERVAL:
                        import random
                        import json
                        
                        # 2. スカ判定（平和な朝）
                        if random.random() < PEACEFUL_CHANCE:
                            # 平和ルート
                            st.toast(lang_mgr.get("text_0062", "{next_day}日目。平和な朝です。"), icon="🕊️")
                            # 判定日を更新（次はまた3日後）
                            st.session_state.last_event_day = next_day 
                        
                        else:
                            # 🎯 イベント発生ルート！
                            try:
                                events_path = os.path.join(BASE_DIR, "assets", "events.json")
                                if os.path.exists(events_path):
                                    with open(events_path, "r", encoding="utf-8") as f:
                                        event_defs = json.load(f)
                                    
                                    # 重み付き抽選 (Weighted Random)
                                    weights = [e["weight"] for e in event_defs]
                                    selected_event = random.choices(event_defs, weights=weights, k=1)[0]
                                    
                                    st.session_state.last_event_day = next_day
                                    # イベント発生メッセージ（多言語対応）
                                    current_lang = st.session_state.get("language", "jp")
                                    if current_lang == "en":
                                        event_msg = f"Event occurred! \"{selected_event['level']}\""
                                    elif current_lang == "zh-CN":
                                        event_msg = f"事件发生！「{selected_event['level']}」"
                                    elif current_lang == "zh-TW":
                                        event_msg = f"事件發生！「{selected_event['level']}」"
                                    else:
                                        event_msg = f"イベント発生！「{selected_event['level']}」"
                                    st.toast(event_msg, icon="⚡")
                                    
                                    # --- ★ AI執筆パート ---
                                    memories = getattr(target_h, "memory_log", [])
                                    recent_memories = "\\n".join(memories[-3:]) if memories else "（特になし）"
                                    current_love = int(getattr(target_h, "love", 0))

                                    writer_prompt = f"""
                                    あなたは恋愛ゲームのシナリオライターです。
                                    ゲーム内の「{next_day}日目の朝」の導入シーンを、以下の条件で書き下ろしてください。

                                    【現在の状況】
                                    ヒロイン: {target_h.name} (好感度: {current_love})
                                    直近の記憶: {recent_memories}

                                    【発生するイベントの種類】
                                    ★ランク: {selected_event['level']}
                                    ★定義: {selected_event['description']}

                                    【執筆指示】
                                    1. 上記の「定義」に基づき、現在の二人の関係性に合った具体的なハプニングを1つ創作してください。
                                    2. 「具体的な出来事」と「ヒロインの反応（セリフ・LINE）」を描写してください。
                                    3. プレイヤーがすぐに返信や行動ができるような引きで終わらせてください。
                                    4. 文量は3〜5行程度。

                                    【重要：出力ルール（絶対厳守）】
                                    1. **出力は「シナリオ本文」のみ**にしてください。
                                    2. 「シナリオライターとして〜」「以下のシーンを作成しました」などの**前置き・挨拶・解説は一切禁止**です。
                                    3. 冒頭からいきなり物語（地の文）を書き始めてください。
                                    """
                                    
                                    with st.spinner(lang_mgr.get("text_0064", "シナリオ生成中...")):
                                        event_intro_text = st.session_state.gemini_client.generate_text(writer_prompt)
                                    
                                    # 超重度（世界改変）の場合の特殊処理：場所を強制変更（多言語対応）
                                    current_lang = st.session_state.get("language", "jp")
                                    if "超重度" in selected_event['level']:
                                        if current_lang == "en":
                                            location_name = "Collapsed City"
                                        elif current_lang == "zh-CN":
                                            location_name = "崩溃的街道"
                                        elif current_lang == "zh-TW":
                                            location_name = "崩潰的街道"
                                        else:
                                            location_name = "崩壊した街"
                                        
                                        st.session_state.current_location = {
                                            "base_id": "99_PANIC", 
                                            "display_name": location_name, 
                                            "category": "DANGER"
                                        }
                                        st.toast(lang_mgr.get("text_0065", "世界が……変わってしまった……！？"), icon="🧟")

                            except Exception as e:
                                print(f"Event Logic Error: {e}")

                    # --- 3. 履歴リセットと開始メッセージ ---
                    st.session_state.chat_history = []
                    
                    # デフォルトのメッセージ（多言語対応）
                    current_lang = st.session_state.get("language", "jp")
                    if current_lang == "en":
                        start_msg = f"(...Morning of Day {next_day} has come.)"
                        if not event_intro_text:
                            start_msg += "\n\n(Nothing particularly unusual happened, it's a peaceful morning. What should we do today?)"
                    elif current_lang == "zh-CN":
                        start_msg = f"（……第{next_day}天的早晨到来了。）"
                        if not event_intro_text:
                            start_msg += "\n\n（没有什么特别的变化，这是一个平静的早晨。今天要做什么呢？）"
                    elif current_lang == "zh-TW":
                        start_msg = f"（……第{next_day}天的早晨到來了。）"
                        if not event_intro_text:
                            start_msg += "\n\n（沒有什麼特別的變化，這是一個平靜的早晨。今天要做什麼呢？）"
                    else:
                        start_msg = f"（……{next_day}日目の朝が来た。）"
                        if not event_intro_text:
                            start_msg += "\n\n（特に変わったことはない、穏やかな朝だ。今日は何をしようか？）"
                    
                    if event_intro_text:
                        # AIが書いたハプニング導入文
                        start_msg += f"\n\n{event_intro_text}"
                    
                    st.session_state.chat_history.append({
                        "role": "model",
                        "parts": [start_msg],
                        "speaker_name": "System"
                    })

                    # --- 4. Next Phase Setup (Reset) ---
                    st.session_state.current_route = "main"
                    st.session_state.active_speaker = "main"
                    set_current_image_to_base("main")
                    
                    st.rerun() 
            
            # ==================================================
            # ★ 下段：自由記述入力エリア（カラムの外に出して全幅表示！）
            # ==================================================
            if st.session_state.active_skill_name == "✨ 自由記述":
                # 前のスキルのデータ（辞書型）が残っていたら掃除
                current_val = st.session_state.get("active_skill_effect", "")
                if isinstance(current_val, dict):
                    current_val = ""
                
                # 全幅で入力欄を表示（多言語対応）
                current_lang = st.session_state.get("language", "jp")
                if current_lang == "en":
                    placeholder_text = "Example: Common sense change! Change to a world where nudity is normal!"
                elif current_lang == "zh-CN":
                    placeholder_text = "例如：常识改变！变成裸体是正常的世界！"
                elif current_lang == "zh-TW":
                    placeholder_text = "例如：常識改變！變成裸體是正常的世界！"
                else:
                    placeholder_text = "例: 常識改変！裸が当たり前の世界にチェンジ！"
                
                custom_effect = st.text_input(
                    lang_mgr.get("text_0066", "効果内容"),
                    value=current_val,
                    placeholder=placeholder_text,
                    label_visibility="collapsed",
                    key="skill_free_input_box"
                )
                # 入力値を保存
                st.session_state.active_skill_effect = custom_effect

            st.markdown('</div>', unsafe_allow_html=True)



    with col_right:
        # --- Right Column: Status Header (Modified) ---
        day = st.session_state.get("day_count", 1)
        tod = st.session_state.get("time_of_day", "夜")
        
        # New Logic for Place
        place_text = ""
        current_loc = st.session_state.get("current_location") or {}
        if current_loc.get("display_name"):
             place_text = current_loc.get("display_name")
        elif st.session_state.get("location_text"):
             place_text = st.session_state.get("location_text")
        
        spk = st.session_state.get("active_speaker", "both")

        # 相手表示（多言語対応）
        current_lang = st.session_state.get("language", "jp")
        if spk == "main":
            who = lang_mgr.get("text_0164", "メイン")
        elif spk == "sub":
            who = lang_mgr.get("text_0165", "サブ")
        else:
            who = lang_mgr.get("text_0166", "両方")

        # [NEW CODE (Revert to simple display)]
        # ★ FIX: Removed relation status from header (moved to card)
        
        day_label = lang_mgr.get("text_0167", "Day")
        if current_lang in ["zh-CN", "zh-TW"]:
            day_display = f"{day_label}{day}"
        else:
            day_display = f"{day_label} {day}"
        if place_text:
            day_display += f"｜{place_text}"

        st.markdown(
            f"""
            <div style="
                background: rgba(255,255,255,0.75);
                border: 1px solid rgba(0,0,0,0.06);
                border-radius: 14px;
                padding: 8px 12px;
                box-shadow: 0 6px 18px rgba(0,0,0,0.08);
                margin-bottom: 8px;
                font-size: 12px;
                color:#333;
                display:flex;
                align-items:center;
                justify-content:space-between;
                gap:10px;
                white-space:nowrap;
                overflow:hidden;
                text-overflow:ellipsis;
            ">
              <div style="font-weight:800;flex:0 0 auto;">
                {day_display}
              </div>
              <div style="opacity:0.85;flex:0 0 auto;">
                👤 {who}
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # --- 2. Image Display (Unified) ---
        img_source = None
        if st.session_state.get("current_image_bytes"):
            img_source = st.session_state.current_image_bytes
        else:
            # Fallback to file path Logic (常にメインヒロイン)
            target_h = st.session_state.get("chat_heroine")
            
            if target_h and getattr(target_h, "image_path", ""):
                 img_source = getattr(target_h, "image_path")
            else:
                 # Absolute Fallback: Main Heroine
                 img_source = (st.session_state.get("main_heroine") or {}).get("image_path", "")

        if img_source:
             if isinstance(img_source, str):
                 if os.path.exists(img_source):
                     st.image(img_source, width="stretch")
                 else:
                     st.info(lang_mgr.get("text_0067", "画像が見つかりません: {os.path.basename(img_source)}"))
             else:
                 st.image(img_source, width="stretch")
        else:
             st.info("No Image")

        # --- 3. Generate Button ---
        # Layout: Generate Button (Wide) | Debug Icon (Square-ish)
        # Ratio [5, 1] ensures the icon button remains small and square-like
        c_gen, c_db = st.columns([5, 1], gap="small")

        with c_gen:
            # --- 体験版モード: 画像生成ボタンを無効化（多言語対応） ---
            from config import IS_DEMO_MODE
            current_lang = st.session_state.get("language", "jp")
            if IS_DEMO_MODE:
                scene_gen_label = lang_mgr.get("text_0068", "🖼️ シーン画像を生成")
                if current_lang == "en":
                    disabled_text = f"{scene_gen_label} (Not available in trial version)"
                    help_text = "Image generation function is not available in trial version"
                elif current_lang == "zh-CN":
                    disabled_text = f"{scene_gen_label} (体验版中不可用)"
                    help_text = "体验版中图像生成功能不可用"
                elif current_lang == "zh-TW":
                    disabled_text = f"{scene_gen_label} (體驗版中不可用)"
                    help_text = "體驗版中圖像生成功能不可用"
                else:
                    disabled_text = f"{scene_gen_label} (体験版では利用できません)"
                    help_text = "体験版では画像生成機能は利用できません"
                st.button(disabled_text, key="btn_gen_scene_right", disabled=True, width="stretch", help=help_text)
            else:
                # --- Existing Generate Logic ---
                if st.button(lang_mgr.get("text_0068", "🖼️ シーン画像を生成"), key="btn_gen_scene_right", width="stretch"):
                 try:
                    # 1. 必要な情報を集める
                    hist = st.session_state.get("chat_history", [])
                    recent_log = str(hist[-6:]) 
                    
                    loc_data = st.session_state.get("current_location", {})
                    loc_name = loc_data.get("display_name", "不明な場所")
                    
                    # 常にメインヒロイン
                    target_h = st.session_state.get("chat_heroine")
                    
                    if not target_h:
                        st.error(lang_mgr.get("text_0069", "ヒロインデータがありません"))
                    else:
                        # DNA（髪型などの固定情報）
                        dna_tags = getattr(target_h, "visual_tags", "")
                        if not dna_tags: dna_tags = "1girl, cute face"

                        # 2. 特化型プロンプト（服装ルール強化版）
                        scene_prompt = f"""
                        あなたはAI画像生成のプロンプトエンジニアです。
                        以下の「DNA（基本設定）」をベースに、現在のシーンを描写するタグを作成してください。

                        【DNA（身体特徴 ＆ デフォルト服装）】
                        {dna_tags}
                        
                        【現在地】
                        {loc_name}

                        【直近の会話ログ】
                        {recent_log}

                        【作成ルール（優先順位）】
                        1. **身体特徴（絶対維持）:** - 髪色、髪型、目の色、体型は【DNA】のタグを必ず含めてください。

                        2. **服装（原則デフォルト維持）:**
                           - **基本ルール:** 何も指定がなければ、【DNA】に含まれる服装タグ（例: suit, maid, uniform）をそのまま使ってください。
                           - **例外（TPO）:** 場所や会話の流れで「着替え」が必要な場合のみ、適切な服に変更してください。
                             (例: ベッド→pajamas / プール→swimsuit / 入浴→towel / デート→casual clothes)
                           - ※ 勝手にランダムな服に着替えさせないこと。

                        3. **シーン演出:**
                           - 場所(Background)と、会話に合ったポーズ(Action)・表情(Emotion)を追加してください。
                           - "standing"（棒立ち）は禁止。状況に応じたポーズ（座る、食べる、抱きつく等）を指定せよ。

                        出力形式: 英語タグのみ（カンマ区切り）
                        """
                        
                        with st.spinner(lang_mgr.get("text_0070", "「{loc_name}」での{target_h.name}を描画中...")):
                            try:
                                generated_tags = st.session_state.gemini_client.generate_text(scene_prompt)
                                generated_tags = generated_tags.replace("```", "").strip()
                            except Exception:
                                generated_tags = ""

                            # ★ 保険ロジック：もしLLMが空文字を返したら、DNAをそのまま使う
                            if not generated_tags or "I cannot" in generated_tags:
                                print("⚠️ LLMタグ生成失敗。DNAタグのみを使用します。")
                                # DNA + 最低限のシチュエーション
                                generated_tags = f"{dna_tags}, {loc_data.get('base_id', 'indoors')}"

                            st.session_state.generated_prompt = generated_tags

                        # 3. 生成実行
                        with st.spinner(lang_mgr.get("text_0071", "イラスト生成中...")):
                            # is_r18=False (generator側での強制改変を回避)
                            res = generator.send_to_comfyui(generated_tags, is_r18=False)
                        
                        if res.get("status") == "success" and res.get("image_data"):
                            st.session_state.current_image_bytes = res["image_data"]
                            if "debug_prompt" in res:
                                st.session_state.last_generated_prompt = res["debug_prompt"]
                            st.toast(lang_mgr.get("text_0072", "シーン生成完了！"), icon="🎨")
                        else:
                            st.toast(lang_mgr.get("text_0073", "生成失敗"), icon="⚠️")
                        
                        st.rerun()

                 except Exception as e:
                    st.error(lang_mgr.get("text_0074", "画像生成エラー: {e}"))

        with c_db:
            # --- Debug Icon Button ---
            has_prompt = "last_generated_prompt" in st.session_state
            if st.button("🔍", key="btn_show_debug_icon", width="stretch", disabled=not has_prompt, help=lang_mgr.get("text_0075", "生成プロンプトを確認")):
                open_debug_modal()

        # --- 4. Generated Prompt Display (Legacy Removed) ---

        # --- Context for UI ---
        # メインヒロインのみ
        active_h_exists = st.session_state.get("chat_heroine") is not None

        # --- 5. Skill UI REMOVED (Moved to Center) ---
    
    # =========================
    # DEBUG (Removed)
    # =========================

    # --- Route Choice Modal --- (削除: サブヒロイン・BOTHシステム不使用)

    # --- Auto-Scroll Logic (Robust Version) ---
    current_len = len(st.session_state.chat_history)
    last_len = st.session_state.get("last_msg_len", 0)
    
    # 新しいメッセージが増えた場合のみ実行
    if current_len > last_len:
        # メインヒロインのみ（BOTHシステム不使用）
        scroll_offset = 2
        
        # JS Injection (Retry Pattern)
        # 画面描画の重さに対応するため、タイミングを変えて複数回スクロールを試みる
        js = f"""
        <script>
            function scrollTargetToTop() {{
                try {{
                    const msgs = window.parent.document.querySelectorAll('[data-testid="stChatMessage"]');
                    const offset = {scroll_offset};
                    if (msgs.length >= offset) {{
                        const target = msgs[msgs.length - offset];
                        target.scrollIntoView({{behavior: "smooth", block: "start"}});
                    }}
                }} catch(e) {{
                    // ignore errors
                }}
            }}
            
            // レンダリング遅延対策：念押しで3回実行する
            setTimeout(scrollTargetToTop, 100);
            setTimeout(scrollTargetToTop, 500);
            setTimeout(scrollTargetToTop, 1200);
        </script>
        """
        st.components.v1.html(js, height=0, width=0)
        
        # 状態更新
        st.session_state.last_msg_len = current_len
    
    elif "last_msg_len" not in st.session_state:
        st.session_state.last_msg_len = current_len

    # ---------------------------------------------------------
    # Floating Chat Scroll Controls (JavaScript Injection)
    # ---------------------------------------------------------
    st.components.v1.html("""
    <script>
        // 1. 親ウィンドウのドキュメント取得
        var parentDoc = window.parent.document;

        // 既存のボタンがあれば削除 (重複防止)
        var existing = parentDoc.getElementById('chat-scroll-controls');
        if (existing) {
            existing.remove();
        }

        // 2. コンテナ作成
        var container = parentDoc.createElement('div');
        container.id = 'chat-scroll-controls';
        container.style.position = 'fixed';
        container.style.bottom = '38px'; // 高さは固定
        container.style.zIndex = '999999';
        container.style.display = 'flex';
        container.style.flexDirection = 'row';
        container.style.gap = '8px';
        container.style.alignItems = 'center';
        // left/rightはここでは指定しない（JSで計算）

        // 3. HTMLセット (3ボタン構成)
        container.innerHTML = `
            <button onclick="window.parent.scrollChatBtn('up')" title="6つ上へ" style="width: 32px; height: 32px; border-radius: 50%; border: 1px solid rgba(255,255,255,0.3); background: rgba(30, 30, 40, 0.85); color: #fff; font-size: 14px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s;">▲</button>
            <button onclick="window.parent.scrollChatBtn('down')" title="6つ下へ" style="width: 32px; height: 32px; border-radius: 50%; border: 1px solid rgba(255,255,255,0.3); background: rgba(30, 30, 40, 0.85); color: #fff; font-size: 14px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s;">▼</button>
            <button onclick="window.parent.scrollChatBtn('bottom')" title="一番下へ" style="width: 32px; height: 32px; border-radius: 50%; border: 1px solid rgba(255,255,255,0.3); background: rgba(233, 30, 99, 0.9); color: #fff; font-size: 12px; font-weight: bold; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s;">⬇</button>
            <style>
                #chat-scroll-controls button:hover { transform: scale(1.15); filter: brightness(1.2); }
                #chat-scroll-controls button:active { transform: scale(0.95); }
            </style>
        `;

        // 4. 画面への注入
        parentDoc.body.appendChild(container);

        // --- 位置合わせロジック ---
        function updateButtonPosition() {
            var inputEl = parentDoc.querySelector('div[data-testid="stChatInput"]');
            if (!inputEl) return;

            var rect = inputEl.getBoundingClientRect();
            var containerWidth = container.offsetWidth || 130; // 幅が取れない場合の概算

            // 入力欄の右端(rect.right)に合わせて配置
            // 少し内側に入れるなら - containerWidth - 10 くらい
            var targetLeft = rect.right - containerWidth - 15;

            container.style.right = 'auto'; // right指定を解除
            container.style.left = targetLeft + 'px';
        }

        // 初回実行
        // ボタンが描画されるのを少し待ってから位置合わせ
        setTimeout(updateButtonPosition, 100);

        // リサイズ追従
        window.parent.addEventListener('resize', updateButtonPosition);

        // 定期監視 (Streamlitのレイアウト変更に対応するため)
        var positionInterval = setInterval(updateButtonPosition, 500);

        // 5. スクロール関数 (6ブロックジャンプ版)
        window.parent.scrollChatBtn = function(direction) {
            var doc = window.parent.document;
            var container = doc.querySelector('.chat-window');
            if (!container) return;

            // 一番下へ
            if (direction === 'bottom') {
                container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
                return;
            }

            var elements = Array.from(container.querySelectorAll('.bubble-container, .narrative'));
            if (elements.length === 0) return;

            var currentScroll = container.scrollTop;

            // 基準点を探す (-10pxの遊び)
            var currentIndex = elements.findIndex(function(el) {
                return el.offsetTop >= currentScroll - 10;
            });
            if (currentIndex === -1) currentIndex = elements.length - 1;

            var targetIndex = currentIndex;
            var jumpStep = 6; // 6ブロック飛ばし

            if (direction === 'up') {
                targetIndex = Math.max(0, currentIndex - jumpStep);
            } else if (direction === 'down') {
                targetIndex = Math.min(elements.length - 1, currentIndex + jumpStep);
            }

            // 移動実行 (ヘッダー被り防止の余白 -40px)
            var targetTop = elements[targetIndex].offsetTop - 40;
            container.scrollTo({ top: targetTop, behavior: 'smooth' });
        };
    </script>
    """, height=0)



# Phase Management
if "phase" not in st.session_state:
    st.session_state.phase = "title"  # Default start phase
if "protagonist_set" not in st.session_state:
    st.session_state.protagonist_set = False

# Dummy functions for phase rendering
def render_age_gate():
    # --- CSS: 余白削除とコンパクト化 ---
    st.markdown("""
    <style>
    /* 画面全体の余白を極限まで削る */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 1rem !important;
        max-width: 800px !important;
    }
    /* ヘッダーの非表示 */
    header { visibility: hidden; }
    
    /* タイトルデザイン */
    .gate-title {
        text-align: center;
        font-size: 2.2rem;
        font-weight: bold;
        background: -webkit-linear-gradient(45deg, #ff00cc, #33ccff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    
    /* 警告ボックスのデザイン */
    .gate-warning {
        color: #ff4b4b;
        border: 1px solid #ff4b4b;
        background: rgba(255, 75, 75, 0.1);
        padding: 0.8rem;
        border-radius: 8px;
        text-align: center;
        font-size: 0.85rem;
        margin-top: 1rem;
        margin-bottom: 1rem;
    }
    
    /* 入力欄の調整 */
    .stTextInput input, .stSelectbox div[data-baseweb="select"] > div {
        background-color: rgba(255, 255, 255, 0.08) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # --- レイアウト: カラムを使って中央寄せ ---
    # 左:中:右 = 1:2:1 の比率で、真ん中（col_center）にコンテンツを置く
    _, col_center, _ = st.columns([1, 3, 1])

    with col_center:
        # タイトル表示
        st.markdown(f'<div class="gate-title">Mugen💗Heart {APP_VERSION}</div>', unsafe_allow_html=True)
        
        # --- API Key Section ---
        # 現在の言語設定を取得（デフォルトはjp）
        if "language" not in st.session_state:
            st.session_state.language = "jp"
        
        current_lang = st.session_state.language
        current_key = st.session_state.get("gemini_api_key", "")
        
        # ステータス表示（コンパクトに・言語対応）
        if current_key:
            if current_lang == "en":
                status_msg = "✅ API Key Loaded"
            elif current_lang == "zh-CN":
                status_msg = "✅ API密钥已加载"
            elif current_lang == "zh-TW":
                status_msg = "✅ API金鑰已載入"
            else:
                status_msg = "✅ API Key Loaded"
            st.success(status_msg, icon="🔑")
        else:
            if current_lang == "en":
                setup_msg = "👇 Setup Google Gemini API Key"
            elif current_lang == "zh-CN":
                setup_msg = "👇 设置Google Gemini API密钥"
            elif current_lang == "zh-TW":
                setup_msg = "👇 設定Google Gemini API金鑰"
            else:
                setup_msg = "👇 Google Gemini APIキーを設定"
            st.info(setup_msg, icon="⚙️")
        
        # APIキー入力欄
        input_key = st.text_input("API Key", value=current_key, type="password", placeholder="AIzaSy...", label_visibility="collapsed")
        # セッションステートに保存（ボタンで参照するため）
        st.session_state.temp_api_key = input_key

        # --- Model Selection ---
        st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
        if current_lang == "en":
            model_caption = "🧠 AI Model Select"
        elif current_lang == "zh-CN":
            model_caption = "🧠 AI模型选择"
        elif current_lang == "zh-TW":
            model_caption = "🧠 AI模型選擇"
        else:
            model_caption = "🧠 AIモデル選択"
        st.caption(model_caption)
        
        # 現在のモデルIDから表示名を逆引き
        current_model_id = st.session_state.get("gemini_model", MODEL_OPTIONS[DEFAULT_MODEL_KEY])
        default_index = 0
        option_keys = list(MODEL_OPTIONS.keys())
        for i, k in enumerate(option_keys):
            if MODEL_OPTIONS[k] == current_model_id:
                default_index = i
                break
        
        selected_label = st.selectbox("Model", option_keys, index=default_index, label_visibility="collapsed")
        selected_model_id = MODEL_OPTIONS[selected_label]
        # セッションステートに保存（ボタンで参照するため）
        st.session_state.temp_model_id = selected_model_id

        # --- Warning & Button ---
        current_lang = st.session_state.get("language", "jp")
        if IS_R18_APP:
            if current_lang == "en":
                warning_text = '<div class="gate-warning">⚠️ <b>WARNING: R-18</b><br>You must be 18 or older to play.<br>(Contains Adult Content)</div>'
                agree_label = "Yes, I am 18 or older (Start Game)"
            else:
                warning_text = '<div class="gate-warning">⚠️ <b>WARNING: R-18</b><br>18歳未満の方はプレイできません。<br>(Contains Adult Content)</div>'
                agree_label = "はい、私は18歳以上です (Start Game)"
            st.markdown(warning_text, unsafe_allow_html=True)
        else:
            st.markdown('<div style="height:20px"></div>', unsafe_allow_html=True)
            agree_label = "Start Game" if current_lang == "en" else "ゲームを始める (Start Game)"

        # Start Button (Primary)
        if st.button(agree_label, type="primary", width="stretch"):
            # タブ内で設定した値をセッションステートから取得
            input_key = st.session_state.get("temp_api_key", st.session_state.get("gemini_api_key", ""))
            selected_model_id = st.session_state.get("temp_model_id", st.session_state.get("gemini_model", MODEL_OPTIONS[DEFAULT_MODEL_KEY]))
            
            if not input_key:
                error_msg = lang_mgr.get("text_0076", lang_mgr.get("text_0107", "APIキーを入力してください"))
                st.error(error_msg)
            else:
                # 設定保存
                save_settings(input_key, selected_model_id)
                
                st.session_state.gemini_api_key = input_key
                st.session_state.gemini_model = selected_model_id
                
                # 言語設定も保存
                if "language" in st.session_state:
                    lang_mgr.load_data(st.session_state.language, "male_target")
                
                try:
                    # 初期化
                    st.session_state.gemini_client = GeminiClient(input_key, model_name=selected_model_id)
                    st.session_state.age_verified = True
                    st.rerun()
                except Exception as e:
                    error_msg = lang_mgr.get("text_0077", lang_mgr.get("text_0108", f"初期化エラー: {e}"))
                    st.error(error_msg)
        
        # --- 言語設定（ボタンの下） ---
        st.markdown('<div style="height:20px"></div>', unsafe_allow_html=True)
        # 言語キャプションの設定
        if current_lang == "en":
            lang_caption = "🌐 Language"
        elif current_lang == "zh-CN":
            lang_caption = "🌐 语言"
        elif current_lang == "zh-TW":
            lang_caption = "🌐 語言"
        else:
            lang_caption = "🌐 言語"
        st.caption(lang_caption)
        
        # 言語選択（現在の言語に応じて表示を変更）
        lang_options_map = {
            "jp": {
                "日本語 (Japanese)": "jp",
                "English": "en",
                "简体中文 (Simplified Chinese)": "zh-CN",
                "繁體中文 (Traditional Chinese)": "zh-TW"
            },
            "en": {
                "Japanese (日本語)": "jp",
                "English": "en",
                "Simplified Chinese (简体中文)": "zh-CN",
                "Traditional Chinese (繁體中文)": "zh-TW"
            },
            "zh-CN": {
                "日语 (Japanese)": "jp",
                "英语 (English)": "en",
                "简体中文 (Simplified Chinese)": "zh-CN",
                "繁体中文 (Traditional Chinese)": "zh-TW"
            },
            "zh-TW": {
                "日語 (Japanese)": "jp",
                "英語 (English)": "en",
                "簡體中文 (Simplified Chinese)": "zh-CN",
                "繁體中文 (Traditional Chinese)": "zh-TW"
            }
        }
        
        # 言語選択ラベルの設定
        if current_lang == "en":
            lang_select_label = "Select Language"
        elif current_lang == "zh-CN":
            lang_select_label = "选择语言"
        elif current_lang == "zh-TW":
            lang_select_label = "選擇語言"
        else:
            lang_select_label = "言語を選択"
        
        # 現在の言語に応じたオプションを取得
        lang_options = lang_options_map.get(current_lang, lang_options_map["jp"])
        
        # デフォルトインデックスの設定
        default_idx_map = {"jp": 0, "en": 1, "zh-CN": 2, "zh-TW": 3}
        default_idx = default_idx_map.get(current_lang, 0)
        
        selected_lang_display = st.selectbox(
            lang_select_label,
            options=list(lang_options.keys()),
            index=default_idx,
            label_visibility="visible",
            key="gate_lang_select"
        )
        selected_lang = lang_options[selected_lang_display]
        
        # 言語が変更されたら再読み込み
        if selected_lang != st.session_state.language:
            st.session_state.language = selected_lang
            lang_mgr.load_data(selected_lang, "male_target")
            st.rerun()
    
    st.stop()

# Helper for Base64 Image Loading
def load_b64_image(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return ""

# Safeguard Function to force Title if conditions met
def safeguard_title_flow():
    # If age verified but no protagonist set, and not in create/relationship/game loop (or just lost state),
    # force title.
    # Exception: if we are already in 'create', 'relationship', 'game' AND protagonist_set=True, it's fine.
    # If protagonist_set is False, we MUST be in title screen.
    if st.session_state.age_verified:
        if not st.session_state.protagonist_set and st.session_state.phase != "title":
             st.session_state.phase = "title"

@st.dialog(lang_mgr.get("text_0078", "⚙️ データ管理ルーム"))
def management_dialog():
    st.caption(lang_mgr.get("text_0079", "不要なデータを削除・整理できます。削除したデータは復元できません。"))

    # フォルダパス定義
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DIR_SAVE = os.path.join(BASE_DIR, "assets", "SAVE")
    DIR_CHARA = os.path.join(BASE_DIR, "assets", "CHARA")

    # タブ作成
    tab1, tab2 = st.tabs(["🕹️ セーブデータ", "📝 作成プリセット"])

    # --- Tab 1: ゲームセーブデータ (assets/SAVE) ---
    with tab1:
        if os.path.exists(DIR_SAVE):
            # JSONファイルを取得 (新しい順)
            save_files = [f for f in os.listdir(DIR_SAVE) if f.endswith(".json")]
            save_files.sort(key=lambda x: os.path.getmtime(os.path.join(DIR_SAVE, x)), reverse=True)

            if not save_files:
                st.info(lang_mgr.get("text_0080", lang_mgr.get("text_0085", lang_mgr.get("text_0124", "データなし"))))
            else:
                # マルチセレクトで選択
                selected_saves = st.multiselect(lang_mgr.get("text_0081", lang_mgr.get("text_0086", "削除対象を選択")), save_files, key="del_save_multi")

                if selected_saves:
                    st.warning(lang_mgr.get("text_0082", "選択した {len(selected_saves)} 件を削除しますか？"))
                    if st.button(lang_mgr.get("text_0083", "🗑️ 実行 (SAVE)"), type="primary", key="btn_exec_del_save"):
                        for f in selected_saves:
                            try:
                                # JSONと、対になる画像(png)を削除
                                os.remove(os.path.join(DIR_SAVE, f))
                                png = f.replace(".json", ".png")
                                if os.path.exists(os.path.join(DIR_SAVE, png)):
                                    os.remove(os.path.join(DIR_SAVE, png))
                            except Exception as e:
                                print(f"Warning: Failed to delete save file {f}: {e}")
                        st.success(lang_mgr.get("text_0084", lang_mgr.get("text_0089", "削除完了")))
                        time.sleep(1)
                        st.rerun()

    # --- Tab 2: キャラ作成プリセット (assets/CHARA) ---
    with tab2:
        if os.path.exists(DIR_CHARA):
            chara_files = [f for f in os.listdir(DIR_CHARA) if f.endswith(".json")]
            chara_files.sort(key=lambda x: os.path.getmtime(os.path.join(DIR_CHARA, x)), reverse=True)

            if not chara_files:
                st.info(lang_mgr.get("text_0080", lang_mgr.get("text_0085", lang_mgr.get("text_0124", "データなし"))))
            else:
                selected_charas = st.multiselect(lang_mgr.get("text_0081", lang_mgr.get("text_0086", "削除対象を選択")), chara_files, key="del_chara_multi")

                if selected_charas:
                    st.warning(lang_mgr.get("text_0087", lang_mgr.get("text_0101", "選択した {len(selected_charas)} 件を削除しますか？")))
                    if st.button(lang_mgr.get("text_0088", "🗑️ 実行 (CHARA)"), type="primary", key="btn_exec_del_chara"):
                        for f in selected_charas:
                            try:
                                os.remove(os.path.join(DIR_CHARA, f))
                            except Exception as e:
                                print(f"Warning: Failed to delete chara file {f}: {e}")
                        st.success(lang_mgr.get("text_0084", lang_mgr.get("text_0089", "削除完了")))
                        time.sleep(1)
                        st.rerun()

            if not save_files:
                st.warning(lang_mgr.get("text_0090", "データが見つかりません。"))
            else:
                selected_saves = st.multiselect(lang_mgr.get("text_0091", "削除するデータを選択 (複数可)"), save_files, key="ms_save")

                if selected_saves:
                    st.warning(lang_mgr.get("text_0092", "選択した {len(selected_saves)} 件を完全に削除しますか？（画像も同時に消えます）"))
                    if st.button(lang_mgr.get("text_0093", "🗑️ 削除実行 (SAVE)"), type="primary", key="del_save_exec"):
                        count = 0
                        for f in selected_saves:
                            try:
                                # JSON削除
                                json_path = os.path.join(DIR_SAVE, f)
                                if os.path.exists(json_path):
                                    os.remove(json_path)

                                # 対応するPNGがあれば削除 (同名の画像ファイル)
                                png_name = f.replace(".json", ".png")
                                png_path = os.path.join(DIR_SAVE, png_name)
                                if os.path.exists(png_path):
                                    os.remove(png_path)

                                count += 1
                            except Exception as e:
                                st.error(lang_mgr.get("text_0094", "エラー: {f} - {e}"))

                        st.success(lang_mgr.get("text_0095", "{count} 件のデータを削除しました"))
                        time.sleep(1)
                        st.rerun()
        else:
             st.error(lang_mgr.get("text_0096", "フォルダが見つかりません: {DIR_SAVE}"))

    # --- Tab 2: assets/CHARA (入力プリセット) ---
    with tab2:
        st.caption(lang_mgr.get("text_0097", "参照フォルダ: `{DIR_CHARA}`"))
        st.info(lang_mgr.get("text_0098", "ここにはキャラ作成画面で「保存」した入力内容（名前・設定など）が含まれます。"))

        if os.path.exists(DIR_CHARA):
            chara_files = [f for f in os.listdir(DIR_CHARA) if f.endswith(".json")]
            chara_files.sort(reverse=True)

            if not chara_files:
                st.warning(lang_mgr.get("text_0099", "プリセットデータが見つかりません。"))
            else:
                selected_charas = st.multiselect(lang_mgr.get("text_0100", "削除するプリセットを選択"), chara_files, key="ms_chara")

                if selected_charas:
                    st.warning(lang_mgr.get("text_0087", lang_mgr.get("text_0101", "選択した {len(selected_charas)} 件を削除しますか？")))
                    if st.button(lang_mgr.get("text_0102", "🗑️ 削除実行 (CHARA)"), type="primary", key="del_chara_exec"):
                        for f in selected_charas:
                            try:
                                path = os.path.join(DIR_CHARA, f)
                                os.remove(path)
                            except Exception as e:
                                st.error(lang_mgr.get("text_0103", "エラー: {e}"))

                        st.success(lang_mgr.get("text_0104", "削除しました"))
                        time.sleep(1)
                        st.rerun()
        else:
             st.warning(lang_mgr.get("text_0105", "フォルダが見つかりません: {DIR_CHARA}"))



# --- Helper: Save Settings (これがないと保存時に落ちるので追加) ---
def save_settings(api_key, model_name):
    try:
        with open(KEY_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump({"GEMINI_API_KEY": api_key, "MODEL_NAME": model_name}, f, ensure_ascii=False, indent=2)
    except:
        pass

# ▼▼▼ 元の render_age_gate (save_settings呼び出し対応版) ▼▼▼
def get_available_gemini_models(api_key):
    """
    入力されたAPIキーを使用して、Googleから現在利用可能なモデル一覧を取得する。
    ゲームに適したモデル（Gemini系かつFlash/Pro/Ultra）のみをフィルタリングして返す。
    """
    import google.generativeai as genai
    if not api_key:
        return []
    
    try:
        genai.configure(api_key=api_key)
        model_list = []
        for m in genai.list_models():
            # モデルIDと表示名を小文字にして判定しやすくする
            mid = m.name.lower()
            dname = m.display_name.lower()
            
            # --- 厳選フィルター ---
            
            # 1. テキスト生成(generateContent)に対応していないなら除外
            if 'generateContent' not in m.supported_generation_methods:
                continue

            # 2. "models/gemini" で始まらないものは除外 (Gemma, PaLM, AQAなどを弾く)
            if not mid.startswith("models/gemini"):
                continue

            # 3. 以下のキーワードを含まないものは除外 (Nano, Experimentalの変なやつを弾く)
            #    ゲームに使えるのは基本的に "flash", "pro", "ultra" の3種
            if not any(k in mid for k in ["flash", "pro", "ultra"]):
                continue

            # 4. "vision" (旧視覚専用) や "image" (画像生成用) が名前に入っているものは除外
            #    ※最近のMultimodalはvisionという名前がつかないので、これで古いものを弾ける
            if "vision" in mid or "image" in mid:
                continue

            # ---------------------

            # 表示用ラベル作成 (例: "Gemini 1.5 Pro (models/gemini-1.5-pro)")
            label = f"{m.display_name} ({m.name})"
            model_list.append((label, m.name))
        
        # 新しい順（バージョンの数字が大きい順）に見えるようにソート
        model_list.sort(key=lambda x: x[0], reverse=True)
        return model_list
        
    except Exception:
        return []

def render_age_gate():
    # --- CSS: 余白削除とコンパクト化 ---
    st.markdown("""
    <style>
    /* 画面全体の余白を極限まで削る */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 1rem !important;
        max-width: 800px !important;
    }
    /* ヘッダーの非表示 */
    header { visibility: hidden; }
    
    /* タイトルデザイン */
    .gate-title {
        text-align: center;
        font-size: 2.2rem;
        font-weight: bold;
        background: -webkit-linear-gradient(45deg, #ff00cc, #33ccff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    
    /* 警告ボックスのデザイン */
    .gate-warning {
        color: #ff4b4b;
        border: 1px solid #ff4b4b;
        background: rgba(255, 75, 75, 0.1);
        padding: 0.8rem;
        border-radius: 8px;
        text-align: center;
        font-size: 0.85rem;
        margin-top: 1rem;
        margin-bottom: 1rem;
    }
    
    /* 入力欄の調整 */
    .stTextInput input, .stSelectbox div[data-baseweb="select"] > div {
        background-color: rgba(255, 255, 255, 0.08) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # --- レイアウト: カラムを使って中央寄せ ---
    _, col_center, _ = st.columns([1, 3, 1])

    with col_center:
        # タイトル表示
        st.markdown(f'<div class="gate-title">Mugen💗Heart {APP_VERSION}</div>', unsafe_allow_html=True)
        
        # --- API Key Section ---
        # 現在の言語設定を取得（デフォルトはjp）
        if "language" not in st.session_state:
            st.session_state.language = "jp"
        
        current_lang = st.session_state.language
        current_key = st.session_state.get("gemini_api_key", "")
        
        # ステータス表示
        if current_key:
            status_msg = "✅ API Key Loaded" if current_lang == "en" else "✅ API Key Loaded"
            st.success(status_msg, icon="🔑")
        else:
            setup_msg = "👇 Setup Google Gemini API Key" if current_lang == "en" else "👇 Google Gemini APIキーを設定"
            st.info(setup_msg, icon="⚙️")
        
        # APIキー入力欄 (ID重複防止のため key を指定)
        input_key = st.text_input("API Key", value=current_key, type="password", placeholder="AIzaSy...", label_visibility="collapsed", key="gate_api_key_input")
        # セッションステートに保存（ボタンで参照するため）
        st.session_state.temp_api_key = input_key

        # --- Model Selection ---
        st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
        model_caption = "🧠 AI Model Select" if current_lang == "en" else "🧠 AIモデル選択"
        st.caption(model_caption)
        
        # --- Model Selection (Dynamic Fetch) ---
        
        # 1. デフォルトの選択肢を用意（固定リスト）
        current_options = MODEL_OPTIONS.copy()
        is_dynamic = False

        # 2. キーが入力されていれば、最新モデルリストの取得を試みる
        if input_key:
            # 少し時間がかかる場合があるのでスピナー等は出さず、裏でこっそり取得してUI更新に任せる
            fetched_models = get_available_gemini_models(input_key)
            if fetched_models:
                # 取得成功！辞書を再構築（ {表示ラベル: モデルID} ）
                current_options = {label: mid for label, mid in fetched_models}
                is_dynamic = True
        
        # 3. 現在の設定値との整合性チェック
        current_model_id = st.session_state.get("gemini_model", MODEL_OPTIONS[DEFAULT_MODEL_KEY])
        
        option_keys = list(current_options.keys())
        default_index = 0
        
        # 以前選択していたモデルIDが、新しいリストの中にあるか探す
        # (IDベースで検索して、インデックスを特定)
        found = False
        for i, key in enumerate(option_keys):
            if current_options[key] == current_model_id:
                default_index = i
                found = True
                break
        
        # 見つからなかった場合（リストが変わった場合）、先頭（最新っぽいもの）を選択
        if not found and option_keys:
            default_index = 0

        # 4. UI表示
        label_text = "Model (Auto-Detected ✨)" if is_dynamic else "Model (Offline/Fixed)"
        if is_dynamic:
            st.success(lang_mgr.get("text_0106", "✅ Googleから最新モデル一覧を取得しました"), icon="📡")
            
        selected_label = st.selectbox(label_text, option_keys, index=default_index, label_visibility="collapsed", key="gate_model_select")
        selected_model_id = current_options[selected_label]
        # セッションステートに保存（ボタンで参照するため）
        st.session_state.temp_model_id = selected_model_id

        # --- Warning & Button ---
        current_lang = st.session_state.get("language", "jp")
        if IS_R18_APP:
            if current_lang == "en":
                warning_text = '<div class="gate-warning">⚠️ <b>WARNING: R-18</b><br>You must be 18 or older to play.<br>(Contains Adult Content)</div>'
                agree_label = "Yes, I am 18 or older (Start Game)"
            else:
                warning_text = '<div class="gate-warning">⚠️ <b>WARNING: R-18</b><br>18歳未満の方はプレイできません。<br>(Contains Adult Content)</div>'
                agree_label = "はい、私は18歳以上です (Start Game)"
            st.markdown(warning_text, unsafe_allow_html=True)
        else:
            st.markdown('<div style="height:20px"></div>', unsafe_allow_html=True)
            agree_label = "Start Game" if current_lang == "en" else "ゲームを始める (Start Game)"

        # Start Button (Primary)
        if st.button(agree_label, type="primary", width="stretch", key="gate_start_btn"):
            # 設定した値をセッションステートから取得
            input_key = st.session_state.get("temp_api_key", st.session_state.get("gemini_api_key", ""))
            selected_model_id = st.session_state.get("temp_model_id", st.session_state.get("gemini_model", MODEL_OPTIONS[DEFAULT_MODEL_KEY]))
            
            if not input_key:
                error_msg = lang_mgr.get("text_0076", lang_mgr.get("text_0107", "APIキーを入力してください"))
                st.error(error_msg)
            else:
                # 設定保存 (ここでのエラーを防ぐためヘルパー関数を追加しました)
                save_settings(input_key, selected_model_id)
                
                st.session_state.gemini_api_key = input_key
                st.session_state.gemini_model = selected_model_id
                
                # 言語設定も保存
                if "language" in st.session_state:
                    lang_mgr.load_data(st.session_state.language, "male_target")
                
                try:
                    # 初期化
                    st.session_state.gemini_client = GeminiClient(input_key, model_name=selected_model_id)
                    st.session_state.age_verified = True
                    st.rerun()
                except Exception as e:
                    error_msg = lang_mgr.get("text_0077", lang_mgr.get("text_0108", f"初期化エラー: {e}"))
                    st.error(error_msg)
        
        # --- 言語設定（ボタンの下） ---
        st.markdown('<div style="height:20px"></div>', unsafe_allow_html=True)
        # 言語キャプションの設定
        if current_lang == "en":
            lang_caption = "🌐 Language"
        elif current_lang == "zh-CN":
            lang_caption = "🌐 语言"
        elif current_lang == "zh-TW":
            lang_caption = "🌐 語言"
        else:
            lang_caption = "🌐 言語"
        st.caption(lang_caption)
        
        # 言語選択（現在の言語に応じて表示を変更）
        lang_options_map = {
            "jp": {
                "日本語 (Japanese)": "jp",
                "English": "en",
                "简体中文 (Simplified Chinese)": "zh-CN",
                "繁體中文 (Traditional Chinese)": "zh-TW"
            },
            "en": {
                "Japanese (日本語)": "jp",
                "English": "en",
                "Simplified Chinese (简体中文)": "zh-CN",
                "Traditional Chinese (繁體中文)": "zh-TW"
            },
            "zh-CN": {
                "日语 (Japanese)": "jp",
                "英语 (English)": "en",
                "简体中文 (Simplified Chinese)": "zh-CN",
                "繁体中文 (Traditional Chinese)": "zh-TW"
            },
            "zh-TW": {
                "日語 (Japanese)": "jp",
                "英語 (English)": "en",
                "簡體中文 (Simplified Chinese)": "zh-CN",
                "繁體中文 (Traditional Chinese)": "zh-TW"
            }
        }
        
        # 言語選択ラベルの設定
        if current_lang == "en":
            lang_select_label = "Select Language"
        elif current_lang == "zh-CN":
            lang_select_label = "选择语言"
        elif current_lang == "zh-TW":
            lang_select_label = "選擇語言"
        else:
            lang_select_label = "言語を選択"
        
        # 現在の言語に応じたオプションを取得
        lang_options = lang_options_map.get(current_lang, lang_options_map["jp"])
        
        # デフォルトインデックスの設定
        default_idx_map = {"jp": 0, "en": 1, "zh-CN": 2, "zh-TW": 3}
        default_idx = default_idx_map.get(current_lang, 0)
        
        selected_lang_display = st.selectbox(
            lang_select_label,
            options=list(lang_options.keys()),
            index=default_idx,
            label_visibility="visible",
            key="gate_lang_select"
        )
        selected_lang = lang_options[selected_lang_display]
        
        # 言語が変更されたら再読み込み
        if selected_lang != st.session_state.language:
            st.session_state.language = selected_lang
            lang_mgr.load_data(selected_lang, "male_target")
            st.rerun()
    
    st.stop()


# ★追加: カノジョカード読み込みダイアログ
@st.dialog("💌 カノジョを招待する (Import)")
def import_card_dialog():
    st.caption("UserData/KANOJO_CARDS フォルダにあるファイルを読み込みます。")
    st.info("※読み込むと、彼女とは『初対面』の状態から物語が始まります。")
    
    card_dir = get_card_dir()
    files = []
    if os.path.exists(card_dir):
        files = [f for f in os.listdir(card_dir) if f.endswith(".json")]
        files.sort(reverse=True)
    
    if not files:
        st.warning("カードが見つかりません (UserData/KANOJO_CARDS)")
        if st.button("閉じる"): st.rerun()
        return

    sel_file = st.selectbox("カードを選択", files, key="dlg_import_sel")
    
    if st.button("❤️ このカノジョと恋を始める", type="primary", width="stretch"):
        try:
            path = os.path.join(card_dir, sel_file)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # データ展開
            st.session_state.user_input = data.get("user_input", {})
            st.session_state.final_texts = data.get("final_texts", {})
            st.session_state.final_status = data.get("final_status", {})
            st.session_state.generated_theme = data.get("generated_theme", "")
            
            # 画像復元
            if data.get("image_b64"):
                import base64
                st.session_state.final_image_data = base64.b64decode(data.get("image_b64"))
                st.session_state.current_image_bytes = st.session_state.final_image_data
            else:
                st.session_state.final_image_data = None
                st.session_state.current_image_bytes = None
            
            # ★ プレイヤー情報をタイトル画面の入力から確定させる（重要）
            p_name = st.session_state.get("title_name", "あなた")
            p_age = st.session_state.get("title_age", 20)
            st.session_state.user_name = p_name
            st.session_state.user_age = str(p_age)
            st.session_state.protagonist_set = True

            # ★ 完全リセット（初対面にする）
            st.session_state.chat_history = []
            st.session_state.memory_log = []
            st.session_state.day_count = 1
            st.session_state.intro_text = "" 
            
            # プロフィール確認画面へ（ここでGAME STARTを押すとランダム導入などが走る）
            st.session_state.phase = "create"
            st.rerun()
            
        except Exception as e:
            st.error(f"読み込みエラー: {e}")

def render_title_screen():
    # --- タイトル画面用ボタンスタイル（DX版準拠） ---
    st.markdown("""
    <style>
    div.stButton > button {
        background: linear-gradient(135deg, #2b1055 0%, #7597de 100%) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: 8px !important; 
        font-weight: bold !important;
        font-size: 16px !important;
        height: 50px !important;
        transition: all 0.3s ease !important;
    }
    div.stButton > button:hover {
        border-color: #ff00cc !important;
        box-shadow: 0 0 10px rgba(255, 0, 204, 0.5) !important;
        transform: translateY(-2px);
    }
    /* 数値入力のスピンボタン消去 */
    input[type=number]::-webkit-inner-spin-button, 
    input[type=number]::-webkit-outer-spin-button { 
        -webkit-appearance: none; margin: 0; 
    }
    </style>
    """, unsafe_allow_html=True)

    # --- 0) Phase Marker ---
    st.markdown('<div id="title_phase_marker"></div>', unsafe_allow_html=True)

    # --- 1) Ensure Base64 Image Loading ---
    bg_path = os.path.join("assets", "ui", "top.png")
    if "title_bg_b64" not in st.session_state or not st.session_state.title_bg_b64:
        st.session_state.title_bg_b64 = load_b64_image(bg_path)
    bg_b64 = st.session_state.title_bg_b64

    # --- 2) Background & Glass CSS (DX版の完全コピー) ---
    st.markdown(f"""
    <style>
        body:has(#title_phase_marker) header[data-testid="stHeader"] {{ visibility: hidden; height: 0; }}
        body:has(#title_phase_marker) footer {{ visibility: hidden; height: 0; }}
        body:has(#title_phase_marker) #MainMenu {{ visibility: hidden; }}
        /* サイドバーを表示（折りたたみ可能） */
        body:has(#title_phase_marker) section[data-testid="stSidebar"] {{
            visibility: visible !important;
            display: block !important;
        }}
        /* サイドバーのトグルボタンを表示 */
        body:has(#title_phase_marker) button[data-testid="baseButton-header"] {{
            visibility: visible !important;
            display: block !important;
        }}
        body:has(#title_phase_marker) [data-testid="stSidebar"] {{
            min-width: 21rem !important;
        }}
        
        body:has(#title_phase_marker) .stApp {{
            background-color: #0b0d12 !important;
            background-image:
                linear-gradient(180deg, rgba(8,10,14,0.75) 0%, rgba(8,10,14,0.25) 40%, rgba(8,10,14,0.80) 100%),
                url("data:image/png;base64,{bg_b64}") !important;
            background-size: cover, contain !important; /* DX版と同じ設定 */
            background-position: center, center top !important;
            background-repeat: no-repeat, no-repeat !important;
            background-attachment: fixed, fixed !important;
            overflow: hidden !important;
        }}

        body:has(#title_phase_marker) .block-container {{
            padding-top: 0rem !important;
            padding-bottom: 0rem !important;
            margin: 0 !important;
            max-width: 100% !important;
        }}

        /* ガラス風コンテナ（DX版と同じ設定：薄く、浮いている） */
        body:has(#title_phase_marker) div[data-testid="stVerticalBlock"]:has(> div.element-container div#glass_anchor) {{
            background: rgba(0, 0, 0, 0.4) !important;
            backdrop-filter: blur(10px) !important;
            -webkit-backdrop-filter: blur(10px) !important;
            border-radius: 20px !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);

            position: fixed !important;
            bottom: 30px !important;
            left: 50% !important;
            transform: translateX(-50%) !important;
            width: 90% !important;
            max-width: 700px !important;
            height: auto !important;
            z-index: 999 !important;
            
            padding: 24px !important;
            gap: 0.5rem !important;
        }}

        /* 入力欄のデザイン */
        body:has(#title_phase_marker) div[data-testid="stVerticalBlock"]:has(div#glass_anchor) input,
        body:has(#title_phase_marker) div[data-testid="stVerticalBlock"]:has(div#glass_anchor) div[data-baseweb="select"] > div {{
            background-color: rgba(10, 10, 15, 0.6) !important;
            color: white !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
        }}
    </style>
    """, unsafe_allow_html=True)

    # --- 3) Helper: Custom Label for Glass UI ---
    def t_lbl(text):
        st.markdown(
            f'<div style="color: #ffffff; font-size: 14px; font-weight: bold; margin-bottom: 4px; margin-top: 0px; text-shadow: 0px 1px 3px rgba(0,0,0,0.8);">{text}</div>', 
            unsafe_allow_html=True
        )

    # --- 4) Glass Container Content ---
    with st.container():
        st.markdown('<div id="glass_anchor" style="display:none;"></div>', unsafe_allow_html=True)

        # 名前/年齢横並び
        col1, col2 = st.columns([2, 1])
        with col1:
            t_lbl("プレイヤー名")
            player_name = st.text_input("p_name", value=st.session_state.get("user_name", "カズヤ"), key="title_name", label_visibility="collapsed")
        with col2:
            t_lbl("年齢")
            player_age = st.number_input("p_age", min_value=18, max_value=99, value=int(st.session_state.get("user_age", 20)), key="title_age", label_visibility="collapsed")

        # スペース
        st.markdown("<div style='height:15px'></div>", unsafe_allow_html=True)

        # --- ボタンエリア: スタイル定義と配置 ---
        st.markdown("""
        <style>
        /* タイトル画面内の全ボタンを同じデザイン・高さに統一 */
        div.stButton > button {
            background: linear-gradient(135deg, #2b1055 0%, #7597de 100%) !important;
            color: white !important;
            border: 1px solid rgba(255, 255, 255, 0.3) !important;
            border-radius: 8px !important;
            height: 50px !important; /* 高さを全員50pxで統一 */
            font-size: 16px !important;
            font-weight: bold !important;
            transition: all 0.3s ease !important;
        }
        div.stButton > button:hover {
            border-color: #ff00cc !important;
            box-shadow: 0 0 10px rgba(255, 0, 204, 0.5) !important;
            transform: translateY(-2px);
        }
        </style>
        """, unsafe_allow_html=True)

        # ランダム版の固定設定（ボタンロジックでの参照用）
        world_mode = "現代"
        world_detail = ""

        # Web体験版: LOAD/IMPORTボタンを削除（Web版では動作しないため）
        # 変更後: GAME STARTボタンのみ
        # c_load, c_import, c_start = st.columns([1, 1, 2], gap="small")
        # Web体験版ではLOAD/IMPORTボタンを削除

        # 🚀 GAME STARTボタン
        if st.button("GAME START", key="btn_title_start", use_container_width=True):
                # Save Logic
                st.session_state.user_name = player_name if player_name else "あなた"
                st.session_state.user_age = str(player_age)
                
                # Global Choice Map
                if "Fantasy" in world_mode:
                    w_target = "ファンタジー"
                elif "SF" in world_mode:
                    w_target = "SF"
                else:
                    w_target = "現代"
                st.session_state.world_mode = w_target
                st.session_state.world_detail = world_detail

                # Transition
                st.session_state.protagonist_set = True
                st.session_state.phase = "create"
                st.rerun()


def render_create_phase():
    # os, jsonモジュールを明示的にインポート（関数内で後でimportがあるため、先にインポートが必要）
    import os
    import json
    
    client = st.session_state.get("gemini_client")
    bundle = st.session_state.main_bundle 

    # 背景適用
    apply_background_theme("pre_game")

    # --- 文字色・コンテナ調整 ---
    st.markdown("""
    <style>
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] span {
        color: #f5f5f5 !important;
        -webkit-text-fill-color: #f5f5f5 !important;
    }
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 5rem !important;
        max-width: 1300px !important;
    }
    div[data-testid="stVerticalBlock"] {
        gap: 0.5rem !important;
    }
    .stTextInput input, .stTextArea textarea {
        background-color: rgba(255, 255, 255, 0.06) !important;
        border: 1px solid rgba(255, 255, 255, 0.25) !important;
        border-radius: 6px !important;
        color: white !important;
        font-size: 14px !important;
    }
    .stTextInput input { height: 38px !important; }
    h2 { padding-top: 0 !important; margin-bottom: 0.3rem !important; font-size: 1.5rem !important; }
    
    div[data-testid="stExpander"] {
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-radius: 8px !important;
        background-color: rgba(0, 0, 0, 0.2) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # ==================================================
    # 🎲 完全自動ガチャ実行ロジック / 体験版: 固定キャラクター読み込み
    # ==================================================
    if "final_texts" not in st.session_state:
        from config import IS_DEMO_MODE
        
        if IS_DEMO_MODE:
            # 体験版モード: 固定キャラクター「長澤柚希」を読み込む（言語対応）
            current_lang = st.session_state.get("language", "jp")
            if current_lang == "en":
                demo_heroine_path = os.path.join(BASE_DIR, "assets", "demo_heroine", "nagasawa_yuzuki_en.json")
            elif current_lang == "zh-CN":
                demo_heroine_path = os.path.join(BASE_DIR, "assets", "demo_heroine", "nagasawa_yuzuki_zh-CN.json")
            elif current_lang == "zh-TW":
                demo_heroine_path = os.path.join(BASE_DIR, "assets", "demo_heroine", "nagasawa_yuzuki_zh-TW.json")
            else:
                demo_heroine_path = os.path.join(BASE_DIR, "assets", "demo_heroine", "nagasawa_yuzuki.json")
            demo_image_path = os.path.join(BASE_DIR, "assets", "demo_heroine", "nagasawa_yuzuki.png")
            
            try:
                with open(demo_heroine_path, "r", encoding="utf-8") as f:
                    demo_data = json.load(f)
                
                st.session_state.user_input = demo_data["user_input"]
                st.session_state.final_texts = demo_data["final_texts"]
                st.session_state.final_status = demo_data["final_status"]
                if current_lang == "en":
                    st.session_state.generated_theme = demo_data.get("generated_theme", "Bright and kind student")
                elif current_lang == "zh-CN":
                    st.session_state.generated_theme = demo_data.get("generated_theme", "绝对盟友系女主角、模特、偶像、TikToker")
                elif current_lang == "zh-TW":
                    st.session_state.generated_theme = demo_data.get("generated_theme", "絕對盟友系女主角、模特、偶像、TikToker")
                else:
                    st.session_state.generated_theme = demo_data.get("generated_theme", "明るく優しい学生")
                
                # 画像を読み込む（最初の立ち絵はdemo001.png）
                demo_image_path = os.path.join(BASE_DIR, "assets", "demo_heroine", "demo001.png")
                if os.path.exists(demo_image_path):
                    with open(demo_image_path, "rb") as f:
                        st.session_state.final_image_data = f.read()
                else:
                    # 画像が存在しない場合はdemo_imagesから読み込む
                    fallback_image = os.path.join(BASE_DIR, "assets", "demo_images", "default.png")
                    if os.path.exists(fallback_image):
                        with open(fallback_image, "rb") as f:
                            st.session_state.final_image_data = f.read()
                    else:
                        st.session_state.final_image_data = None
                
                st.rerun()
            except Exception as e:
                st.error(f"体験版キャラクターデータの読み込みに失敗しました: {e}")
                st.stop()
        else:
            # 通常モード: ランダム生成
            # ▼▼▼ 追加：ロード中のモノローグテキスト ▼▼▼
            # スピナーが回っている間、画面に表示され続けます
            p_name = st.session_state.get("user_name", "俺")
            st.markdown(f"""
            <div style="background:rgba(0,0,0,0.5); padding:20px; border-radius:10px; text-align:center; margin-bottom:20px;">
                <p>俺は {p_name}。どこにでもいる平凡な大学生だ。</p>
                <p>東京都杉並区阿佐ヶ谷にある古びたアパート『月光荘』</p>
                <p>俺はそこで、怠惰ながらも愛すべき日々を暮らしている。</p>
                <hr style="margin:10px 0; opacity:0.5;">
                <p style="font-size:0.9em; opacity:0.8;">（運命の歯車が、今動き出す……）</p>
            </div>
            """, unsafe_allow_html=True)
            # ▲▲▲ 追加ここまで ▲▲▲

            with st.spinner(lang_mgr.get("text_0109", "運命の相手を探しています...（設定生成・立ち絵描画）")):
                try:
                    wm = st.session_state.get("world_mode", "現代")
                    
                    if "user_input" in st.session_state:
                        del st.session_state.user_input
                    
                    theme, data = handler.generate_profile_from_themes(client, wm, "")
                    st.session_state.user_input = data
                    st.session_state.generated_theme = theme

                    status_data = generator.determine_fixed_status(client, data)
                    st.session_state.final_status = status_data
                    
                    texts = {}
                    for i in range(5):
                        try:
                            temp = generator.generate_all_texts(client, data, status_data)
                            if "生成に失敗" not in temp.get("main_profile", ""):
                                texts = temp
                                break
                        except:
                            time.sleep(1)
                    
                    if not texts:
                        st.error(lang_mgr.get("text_0110", "生成に失敗しました。リロードしてください。"))
                        st.stop()

                    st.session_state.final_texts = texts

                    raw_tags = texts.get("image_tags", "")
                    safe_tags = raw_tags.replace("nude", "").replace("nipples", "").replace("uncensored", "").replace("nsfw", "")
                    prompt = f"(cowboy shot), (looking at viewer), {safe_tags}, (clothes:1.2), (normal outfit:1.0)"
                    
                    img_res = generator.send_to_comfyui(prompt)
                    img_data = img_res.get("image_data") if img_res.get("status") == "success" else None
                    st.session_state.final_image_data = img_data
                    
                    st.rerun()

                except Exception as e:
                    st.error(lang_mgr.get("text_0111", "エラーが発生しました: {e}"))
                    st.stop()

    # ==================================================
    # 📄 プロフィール表示
    # ==================================================
    if "final_texts" in st.session_state:
        
        c_head_L, c_head_R = st.columns([8, 1])
        with c_head_L:
            from config import IS_DEMO_MODE
            demo_badge = " [体験版]" if IS_DEMO_MODE else ""
            name = st.session_state.user_input.get('Name', '')
            # 体験版: 名前の読み方を追加
            if IS_DEMO_MODE and name == "長澤 柚希":
                name_display = f"{name}（ながさわ ゆずき）"
            else:
                name_display = name
            st.markdown(f"## 🌸 {name_display} プロフィールカード{demo_badge}")
        with c_head_R:
            st.markdown('<div style="height: 5px;"></div>', unsafe_allow_html=True)
            if st.button(lang_mgr.get("text_0112", "↻ リトライ"), width="stretch", help=lang_mgr.get("text_0113", "現在の設定を破棄して、新しい相手を探します")):
                keys_to_clear = ["final_texts", "user_input", "final_status", "final_image_data", "generated_theme"]
                for k in keys_to_clear:
                    if k in st.session_state:
                        del st.session_state[k]
                st.rerun()

        col_img, col_txt = st.columns([1.5, 3.5])

        with col_img:
            if st.session_state.get("final_image_data"):
                st.image(st.session_state.final_image_data, caption=None, width="stretch")
            else:
                st.warning(lang_mgr.get("text_0114", "画像データがありません"))

            with st.expander(lang_mgr.get("text_0115", "🎨 立ち絵を調整・再描画"), expanded=False):
                from config import IS_DEMO_MODE
                if IS_DEMO_MODE:
                    st.info("体験版では画像再生成機能は利用できません")
                    st.button("🔄 再生成 (体験版では利用できません)", width="stretch", disabled=True)
                else:
                    user_tag_input = st.text_input("tag_add", placeholder="例: 赤メガネ, ショートヘア", key="add_tag_input", label_visibility="collapsed")
                    
                    if st.button(lang_mgr.get("text_0116", "🔄 再生成 (タグ追加)"), width="stretch"):
                        if user_tag_input:
                            with st.spinner(lang_mgr.get("text_0117", "タグ変換中...")):
                                translated_addition = generator.append_visual_tags(client, "", user_tag_input).replace(", ", "")
                            current_tags = st.session_state.final_texts["image_tags"]
                            new_tags = f"{translated_addition}, {current_tags}"
                            st.session_state.final_texts["image_tags"] = new_tags
                        
                        with st.spinner(lang_mgr.get("text_0118", "ComfyUIで生成中...")):
                            raw_tags = st.session_state.final_texts["image_tags"]
                            safe_tags = raw_tags.replace("nude", "").replace("nipples", "").replace("uncensored", "").replace("nsfw", "")
                            sfw_prefix = "(clothes:1.3), (normal outfit:1.2), (full body), (wide shot), (standing), (looking at viewer), "
                            final_tags = f"{sfw_prefix} {safe_tags}"
                            
                            result = generator.send_to_comfyui(final_tags, force_single=True)
                            if result["status"] == "success":
                                st.session_state.final_image_data = result["image_data"]
                                st.success(lang_mgr.get("text_0119", "更新完了！"))
                                st.rerun()
                            else:
                                st.error(f"生成エラー: {result['message']}")

        with col_txt:
            c_base1, c_base2 = st.columns([1, 1])
            with c_base1:
                st.markdown(f"**職業:** {st.session_state.user_input.get('Job')}")
            with c_base2:
                st.markdown(f"**年齢:** {st.session_state.user_input.get('Visual Age')}")
            
            # --- 人物紹介 ---
            # 見出しとボックスを近づける（margin-bottom: -10px）
            st.markdown('<p style="font-size:14px; color:rgba(255,255,255,0.6); margin-bottom:-10px;">📜 人物紹介</p>', unsafe_allow_html=True)
            st.info(st.session_state.final_texts["main_profile"])

            # --- 外見詳細 ---
            # 上のボックスとの距離を空ける（margin-top: 25px）
            # 自分のボックスとは近づける（margin-bottom: -10px）
            st.markdown('<p style="font-size:14px; color:rgba(255,255,255,0.6); margin-top:25px; margin-bottom:-10px;">👗 外見詳細</p>', unsafe_allow_html=True)
            st.success(st.session_state.final_texts["visual_detail"])

            # 修正: タイトルと中身を変更
            with st.expander(lang_mgr.get("text_0123", "💗 カノジョのヒミツ (クリックで見る)"), expanded=False):
                # ▼ 修正: 箇条書き（モンスター等）ではなく、文章テキストを表示
                if "sexual_profile" in st.session_state.final_texts:
                    st.info(st.session_state.final_texts["sexual_profile"])
                else:
                    st.warning(lang_mgr.get("text_0080", lang_mgr.get("text_0085", lang_mgr.get("text_0124", "データなし"))))

        # --- フッター: ゲーム開始ボタン ---
        st.markdown("<hr style='margin: 1rem 0; opacity: 0.3;'>", unsafe_allow_html=True)
        
        if st.button(lang_mgr.get("text_0125", "❤️ このヒロインと恋を始める (GAME START)"), type="primary", width="stretch", key="btn_game_start_random"):
            
            # 1. データを保存
            import json
            import re
            import os
            from datetime import datetime

            save_dir = "assets/CHARA"
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)

            name = st.session_state.user_input.get("Name", "NoName")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = re.sub(r'[\\/:*?"<>|]+', '', name)
            base_name = f"random_{safe_name}_{ts}"
            
            json_path = os.path.join(save_dir, f"{base_name}.json")
            png_path = os.path.join(save_dir, f"{base_name}.png")

            data_to_save = {
                "user_input": dict(st.session_state.user_input),
                "final_texts": dict(st.session_state.final_texts),
                "final_status": dict(st.session_state.final_status),
                "generated_theme": st.session_state.get("generated_theme", ""),
                "created_at": ts,
                "save_version": "1.3"
            }

            try:
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(data_to_save, f, ensure_ascii=False, indent=2)
                
                if st.session_state.get("final_image_data"):
                    with open(png_path, "wb") as f:
                        f.write(st.session_state.final_image_data)
                else:
                    png_path = ""
            except Exception as e:
                st.error(lang_mgr.get("text_0126", "保存エラー: {e}"))
                st.stop()

            # 2. パス情報をセッションにセット
            hero_dict = {
                "save_path": json_path,
                "image_path": png_path,
                "user_input": dict(st.session_state.user_input),
                "final_status": dict(st.session_state.final_status),
                "final_texts": dict(st.session_state.final_texts)
            }
            st.session_state.main_heroine = hero_dict
            st.session_state.current_image_bytes = st.session_state.final_image_data

            # 3. ランダム導入の選択＆リライト / 体験版: 固定導入文
            from config import IS_DEMO_MODE
            
            if IS_DEMO_MODE:
                # 体験版モード: 固定導入文を読み込む（言語対応）
                current_lang = st.session_state.get("language", "jp")
                if current_lang == "en":
                    demo_intro_path = os.path.join(BASE_DIR, "assets", "demo_intro_en.txt")
                    default_intro = "### 🎬 Encounter\n\nI accidentally met a woman on the street corner."
                    location_name = "Live House Back Alley"
                elif current_lang == "zh-CN":
                    demo_intro_path = os.path.join(BASE_DIR, "assets", "demo_intro_zh-CN.txt")
                    default_intro = "### 🎬 相遇\n\n我在街角偶然遇到了一位女性。"
                    location_name = "Live House Back Alley"
                elif current_lang == "zh-TW":
                    demo_intro_path = os.path.join(BASE_DIR, "assets", "demo_intro_zh-TW.txt")
                    default_intro = "### 🎬 相遇\n\n我在街角偶然遇到了一位女性。"
                    location_name = "Live House Back Alley"
                else:
                    demo_intro_path = os.path.join(BASE_DIR, "assets", "demo_intro.txt")
                    default_intro = "### 🎬 出逢い\n\n街角で偶然、女性と出会った。"
                    location_name = "ライブハウスの裏路地"
                
                try:
                    with open(demo_intro_path, "r", encoding="utf-8") as f:
                        st.session_state.intro_text = f.read().strip()
                except Exception as e:
                    print(f"Demo Intro Load Error: {e}")
                    st.session_state.intro_text = default_intro
                
                # 体験版: 導入文に合わせて場所を設定（ライブハウスの裏路地）
                st.session_state.current_location = {
                    "base_id": "08_DUNGEON",
                    "display_name": location_name,
                    "category": "DANGER"
                }
            else:
                # 通常モード: ランダム導入の選択＆リライト
                import random
                
                # JSON読み込み
                base_intro = ""
                intro_title = "導入" # Default title

                try:
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    path = os.path.join(base_dir, "assets", "intro_situations.json")
                    if os.path.exists(path):
                        with open(path, "r", encoding="utf-8") as f:
                            situations = json.load(f)
                        if situations:
                            selected = random.choice(situations)
                            base_intro = selected.get("text", "")
                            intro_title = selected.get("summary", "導入")
                except Exception as e:
                    print(f"Intro Load Error: {e}")
                
                if not base_intro:
                    base_intro = "街角で偶然、女性と出会った。"

                # ★リライト処理★（言語対応）
                current_lang = st.session_state.get("language", "jp")
                with st.spinner(lang_mgr.get("text_0127", "シチュエーションを二人に合わせて書き直しています...")): 
                    h_name = st.session_state.user_input.get("Name", "彼女")
                    p_name = st.session_state.get("user_name", "主人公")
                    if p_name == "あなた":
                        if current_lang == "en":
                            p_name = "you"
                        elif current_lang == "zh-CN" or current_lang == "zh-TW":
                            p_name = "你"
                    h_pers = st.session_state.user_input.get("Personality", "普通")
                    
                    if current_lang == "en":
                        rewrite_prompt = f"""
                    You are a scenario writer. Please rewrite the following "introduction situation" using the specified character names.
                    
                    【Characters】
                    Heroine: {h_name} (Personality: {h_pers})
                    Protagonist: {p_name}
                    
                    【Original Situation】
                    {base_intro}
                    
                    【Instructions】
                    - Rewrite the situation using the character names above.
                    - Maintain the atmosphere and flow of the original situation.
                    - Output in English.
                    - Use the format: Character Name"Dialogue" for dialogue.
                    - Use first-person perspective ("I") for narration from the protagonist's viewpoint.
                    """
                    elif current_lang == "zh-CN":
                        rewrite_prompt = f"""
                    您是一位场景编剧。请使用指定的角色名称重写以下「介绍场景」。
                    
                    【角色】
                    女主角: {h_name} (性格: {h_pers})
                    主角: {p_name}
                    
                    【原始场景】
                    {base_intro}
                    
                    【重要：描述规则（绝对遵守）】
                    1. **不要写任何对话（「」或『』包围的对话文）。**
                    2. 即使角色说话，也要用「〜她小声说道」「〜她道谢」这样的方式，**全部用旁白（叙述）**来描写。
                    3. **不要完结。** 最后以「目光相遇」「察觉到气息」等停止，在玩家说出第一句话之前的状态结束。
                    
                    【指示】
                    - 维持原始场景的展开。
                    - 将通用表达改写为「{h_name}」或「{p_name}」。
                    - 视角统一为「第三人称（摄像机视角）」或「{p_name}视角」。
                    - **输出仅重写后的正文。**
                    """
                    elif current_lang == "zh-TW":
                        rewrite_prompt = f"""
                    您是一位場景編劇。請使用指定的角色名稱重寫以下「介紹場景」。
                    
                    【角色】
                    女主角: {h_name} (性格: {h_pers})
                    主角: {p_name}
                    
                    【原始場景】
                    {base_intro}
                    
                    【重要：描述規則（絕對遵守）】
                    1. **不要寫任何對話（「」或『』包圍的對話文）。**
                    2. 即使角色說話，也要用「〜她小聲說道」「〜她道謝」這樣的方式，**全部用旁白（敘述）**來描寫。
                    3. **不要完結。** 最後以「目光相遇」「察覺到氣息」等停止，在玩家說出第一句話之前的狀態結束。
                    
                    【指示】
                    - 維持原始場景的展開。
                    - 將通用表達改寫為「{h_name}」或「{p_name}」。
                    - 視角統一為「第三人稱（攝像機視角）」或「{p_name}視角」。
                    - **輸出僅重寫後的正文。**
                    """
                    else:
                        rewrite_prompt = f"""
                    あなたはシナリオライターです。以下の「導入シチュエーション」を、指定されたキャラクター名を使ってリライトしてください。
                    
                    【登場人物】
                    ヒロイン: {h_name} (性格: {h_pers})
                    主人公: {p_name}
                    
                    【元のシチュエーション】
                    {base_intro}
                    
                    【重要：記述ルール（絶対厳守）】
                    1. **セリフ（「」や『』で囲まれた会話文）は一切書かないでください。**
                    2. キャラクターが何かを話す場合も、「〜と彼女は小さく呟いた」「〜と礼を言った」のように、**すべて地の文（ナレーション）**で描写してください。
                    3. **完結させないこと。** 最後に「目が合った」「気配に気づいた」などで止め、プレイヤーが最初の一言を発する直前の状態で終わらせてください。
                    
                    【指示】
                    - 元のシチュエーションの展開は維持する。
                    - 汎用的な表現を「{h_name}」や「{p_name}」に書き換える。
                    - 視点は「三人称（カメラ視点）」または「{p_name}視点」で統一する。
                    - **出力はリライト後の本文のみ。**
                    """
                    
                    try:
                        # リライト実行
                        hist = [{"role": "user", "parts": [rewrite_prompt]}]
                        rewritten = client.generate_response(hist, "あなたは優秀な小説家です。")
                        
                        final_text = base_intro
                        if rewritten:
                            final_text = rewritten.strip()
                        
                        # タイトル結合
                        st.session_state.intro_text = f"### 🎬 {intro_title}\n\n{final_text}"

                    except Exception as e:
                        print(f"Rewrite Error: {e}")
                        st.session_state.intro_text = f"### 🎬 {intro_title}\n\n{base_intro}"

            # 4. 関係性初期化 (赤の他人固定 + 三人称視点固定)
            wm = st.session_state.get("world_mode", "現代")
            st.session_state.relationship_data = {
                "player_job_text": "一般人",
                "main_relation_choice": "赤の他人",
                "main_relation_free": "街で偶然出会った",
                "narrative_style": "一人称（俺視点）",
                "world_choice": wm,
                "world_free": ""
            }

            # 5. ゲーム開始フラグ設定
            st.session_state.create_target = "main"
            st.session_state.current_route = "main"
            # サブヒロイン・BOTHシステムは使用しない
            st.session_state.phase = "game"
            st.session_state.game_initialized = False 
            st.session_state.day_count = 1
            st.session_state.time_of_day = "夕方"

            # ★ NEW: 舞台設定（阿佐ヶ谷）のコンテキストを保存
            st.session_state.world_setting = """
            【舞台設定】
            ・場所：東京都杉並区阿佐ヶ谷（Asagaya, Tokyo）
            ・主人公の住居：阿佐ヶ谷にある古びたアパート『月光荘』
            ・生活圏：JR阿佐ヶ谷駅周辺、パールセンター商店街、中杉通りなど実在の場所。
            ・リアリティ：実在する店舗やランドマークが登場する、生活感のある世界。
            """
            
            # 現在地の初期化（体験版モードの場合は既に設定済み）
            from config import IS_DEMO_MODE
            if not IS_DEMO_MODE:
                # 通常モード: 現在地の初期化 (Generatorの定義と同期させる)
                st.session_state.current_location = {
                    "base_id": "99_UNKNOWN",
                    "display_name": "？？？",
                    "category": "OTHER"
                }

            # ★ NEW: プロローグ（主人公のモノローグ）を履歴の最初に追加
            player_name = st.session_state.get("user_name", "俺")
            prologue_text = f"（俺の名前は{player_name}。どこにでもいる平凡な大学生だ。）\\n（住んでいるのは、東京都杉並区阿佐ヶ谷にある木造アパート『月光荘』。）\\n（中央線の音が遠くに聞こえるこの街で……俺の運命を変える出会いが、すぐそこまで迫っていた。）"
            
            # 体験版: 導入文からセリフ部分を分離
            from config import IS_DEMO_MODE
            intro_text = st.session_state.intro_text
            intro_narrative = intro_text
            intro_dialogue = None
            
            if IS_DEMO_MODE:
                # 導入文から「長澤柚希「...」」の形式のセリフを抽出
                import re
                dialogue_match = re.search(r'長澤柚希「([^」]+)」', intro_text)
                if dialogue_match:
                    intro_dialogue = dialogue_match.group(1)
                    # セリフ部分を導入文から削除
                    intro_narrative = re.sub(r'\n長澤柚希「[^」]+」', '', intro_text)
            
            # 初期履歴をモノローグで上書き + 導入テキスト追加
            history_items = [
                {"role": "model", "parts": [prologue_text], "speaker_name": "System"},
                {"role": "model", "parts": [intro_narrative], "speaker_name": "System"}
            ]
            
            # 体験版: セリフを別エントリとして追加
            if IS_DEMO_MODE and intro_dialogue:
                history_items.append({
                    "role": "model",
                    "parts": [f"長澤柚希「{intro_dialogue}」"],
                    "speaker": "main",
                    "speaker_name": "長澤柚希"
                })
            
            st.session_state.chat_history = history_items

            # お祝いエフェクト
            st.balloons()
            st.toast(lang_mgr.get("text_0128", "ヒロイン生成完了！物語が始まります。"), icon="🎉")
            
            st.rerun()

# 4. Relationship Phase
def render_relationship_phase():
    # 背景適用 (PRE-GAMEモード)
    apply_background_theme("pre_game")

    # --- 文字色 & 背景 & レイアウトを調整するCSS ---
    st.markdown("""
    <style>
    /* 全体のコンテナ調整（少し詰める） */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 3rem !important;
        max-width: 70% !important;
    }
    
    div[data-testid="stVerticalBlock"] {
        gap: 0.4rem !important;
    }

    /* 入力エリアのデザイン共通化 */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div, .stSelectbox div[data-baseweb="select"] span {
        background-color: rgba(255, 255, 255, 0.06) !important;
        border: 1px solid rgba(255, 255, 255, 0.25) !important;
        border-radius: 6px !important;
        color: #f5f5f5 !important;
        -webkit-text-fill-color: #f5f5f5 !important;
    }
    
    /* ヘッダーマージン削減 */
    h2 { padding-top: 0.5rem !important; margin-bottom: 0.5rem !important; font-size: 1.4rem !important; }
    h3 { padding-top: 0.5rem !important; margin-bottom: 0.3rem !important; font-size: 1.1rem !important; }
    
    /* 区切り線 */
    hr { margin: 1rem 0 !important; opacity: 0.2 !important; }
    
    /* ゲーム開始ボタン（最後）を大きくする */
    div.stButton > button[kind="primary"] {
        height: 80px !important;
        font-size: 1.2rem !important;
        font-weight: bold !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # --- Helper: Prompt Builder for Intro (Main/Sub/Both) ---
    def build_intro_prompt(rd: dict, main_profile: str, sub_profile: str, mode: str, player_name: str, player_age: str, main_name: str, sub_name: str) -> str:
        
        # --- 1. Gather World Info ---
        w_text = f"ベース: {rd.get('world_choice', '現代')}\n"
        if rd.get('world_free'):
            w_text += f"\n要望: {rd.get('world_free')}\n"
        if st.session_state.get("world_detail"):
            w_text += f"\n追加ルール: {st.session_state.world_detail}\n"

        # --- 2. Gather Relationship Info ---
        r_text = f"【主人公】\n名前: {player_name}\n年齢: {player_age}\n職業: {rd.get('player_job_text', '')}\n"

        # Main
        if mode in ["main", "both"]:
            r_text += f"\n【メインヒロイン: {main_name}】\n"
            r_text += f"関係: {rd.get('main_relation_choice')}\n"
            if rd.get('main_relation_free'):
                r_text += f"詳細: {rd.get('main_relation_free')}\n"

        # Sub
        if mode in ["sub", "both"]:
            r_text += f"\n【サブヒロイン: {sub_name}】\n"
            r_text += f"関係: {rd.get('sub_relation_choice')}\n"
            if rd.get('sub_relation_free'):
                r_text += f"詳細: {rd.get('sub_relation_free')}\n"

        # --- 3. Situation Info (Fix: Define s_text) ---
        s_text = ""

        # --- 4. Narrative Perspective Logic ---
        # R15版は俺視点固定
        my_pronoun = "俺"
        perspective_instruction = f"""
        - **一人称視点（{my_pronoun}視点）で書くこと**
        - 主語は「{my_pronoun}」。
        - {my_pronoun}の五感と感情（焦り、決意、安堵など）を交えて描写せよ。
        - ヒロインの心理は断定せず、{my_pronoun}から見た様子として書くこと。
        """

        prompt = f"""
あなたは、商業的にヒット作を出し続けている
日本の売れっ子恋愛アドベンチャーゲームのシナリオライターです。

以下の情報は、設定資料ではありません。
これは「ゲーム開始時点で、すでに成立している前提」です。
説明・整理・解説は一切せず、自然に物語として使ってください。

【世界観】
{w_text}

【主人公とヒロインたちの関係性】
{r_text}

【現在の状況（あれば）】
{s_text}
※この欄が空白の場合は、
恋愛ADVとして最も自然な
「街中で偶然出会う」導入状況を、
あなた自身の判断で採用してください。

【執筆指示】
{perspective_instruction}
- 世界観や関係性を説明しない（行動や情景で示す）
- 分量は5〜8行程度の短いプロローグ
- 最後は必ず「会話が始まる直前」で止めること
  （視線が合う、声をかけようとする、気配に気づく 等）

これは本編に入るための導入です。
プレイヤーが最初の一言を自然に入力できる余白を残してください。

では、プロローグを書いてください。
""".strip()
        return prompt

    # 0) Session & Constants Init
    if "relationship_data" not in st.session_state:
        # Map simple mode to detailed choice
        wm = st.session_state.get("world_mode", "現代")
        w_choice = "現実（に近い）の日本"
        if wm == "ファンタジー":
            w_choice = "異世界ファンタジー"
        elif wm == "SF":
            w_choice = "サイバーパンク未来"

        st.session_state.relationship_data = {
            "player_job_text": "",
            "main_relation_choice": "なし",
            "main_relation_free": "",
            "sub_relation_choice": "なし",
            "sub_relation_free": "",
            "world_choice": w_choice,
            "world_free": "",
        }

    REL_CHOICES = [
        "なし",
        "赤の他人",
        "知り合い",
        "友達",
        "プレイヤーが片思い",
        "ヒロインが片思い",
        "両思い",
        "恋人",
        "愛人",
        "夫婦",
    ]

    # 2) Helper Function (Render Card)
    def render_hero_card(image_path: str, name: str, age: str, job: str, profile_text: str):
        st.markdown('<div class="hero-card">', unsafe_allow_html=True)

        if image_path and os.path.exists(image_path):
            import base64
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            st.markdown(f'''
                <div style="display: flex; justify-content: center;">
                    <img src="data:image/png;base64,{b64}" style="width: 70%; border-radius: 8px; margin-bottom: 8px;">
                </div>
            ''', unsafe_allow_html=True)

        st.markdown(f'<div class="hero-name">{name}</div>', unsafe_allow_html=True)
        st.markdown('<div style="height: 10px;"></div>', unsafe_allow_html=True) # Spacer

        meta = age or ""
        if job:
            meta = f"{meta} / {job}" if meta else job
        st.markdown(f'<div class="hero-meta">{meta}</div>', unsafe_allow_html=True)
        st.markdown('<div style="height: 10px;"></div>', unsafe_allow_html=True) # Spacer

        if profile_text:
            st.markdown(f'<div class="hero-prof">{profile_text}</div>', unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(lang_mgr.get("text_0129", "## 💞 関係性構築モード"))

    # 0. Define main safely at start
    main = st.session_state.get("main_heroine")
    has_main = isinstance(main, dict)
    has_sub = False  # サブヒロインシステムは使用しない

    # 3) Layout (Left: Main, Mid: Relation, Right: Sub)
    col_left, col_mid, col_right = st.columns([1, 2.5, 1], vertical_alignment="top")

    # 4) Main Heroine Data (Load from Save)
    main_save_path = (main or {}).get("save_path", "")
    main_saved = load_heroine_from_save(main_save_path)

    # 5) Sub Heroine Data (Load from Save) - 使用しない
    sub_saved = None

    # 6) Render Columns
    with col_mid:
        st.markdown(lang_mgr.get("text_0130", "## 関係性入力"))

        rd = st.session_state.relationship_data

        # --- プレイヤー ---
        st.markdown(lang_mgr.get("text_0131", "### プレイヤー（職業やスキルなど自由記述）"))
        
        # カラムを分割して、職業入力の右側に視点選択を追加
        # ★ vertical_alignment="bottom" を追加して入力欄の高さを揃える
        col_p1, col_p2 = st.columns([2.5, 1], vertical_alignment="bottom")
        
        with col_p1:
            rd["player_job_text"] = st.text_input(
                lang_mgr.get("text_0132", "職業・スペック（自由記述）"),
                value=rd.get("player_job_text", ""),
                key="rel_player_job_text",
                placeholder="例：平凡な学生、退魔師など"
            )
        
        with col_p2:
            # 視点選択（R15版は俺視点固定なので選択肢削除）
            rd["narrative_style"] = "一人称（俺視点）"

        st.markdown("<hr>", unsafe_allow_html=True)

        # --- メインヒロイン ---
        st.markdown(lang_mgr.get("text_0133", "### メインヒロインとの関係"))

        rd["main_relation_free"] = st.text_area(
            lang_mgr.get("text_0134", lang_mgr.get("text_0137", "最優先リクエスト（自由記述）")),
            value=rd.get("main_relation_free", ""),
            height=90,
            key="rel_main_free"
        )
        rd["main_relation_choice"] = st.selectbox(
            lang_mgr.get("text_0135", lang_mgr.get("text_0138", "関係（選択）")),
            REL_CHOICES,
            index=REL_CHOICES.index(rd.get("main_relation_choice", "なし")),
            key="rel_main_choice"
        )

        st.markdown("<hr>", unsafe_allow_html=True)

        # --- サブヒロイン ---
        if has_sub:
            st.markdown(lang_mgr.get("text_0136", "### サブヒロインとの関係"))

            rd["sub_relation_free"] = st.text_area(
                lang_mgr.get("text_0134", lang_mgr.get("text_0137", "最優先リクエスト（自由記述）")),
                value=rd.get("sub_relation_free", ""),
                height=90,
                key="rel_sub_free"
            )
            rd["sub_relation_choice"] = st.selectbox(
                lang_mgr.get("text_0135", lang_mgr.get("text_0138", "関係（選択）")),
                REL_CHOICES,
                index=REL_CHOICES.index(rd.get("sub_relation_choice", "なし")),
                key="rel_sub_choice"
            )
            st.markdown("<hr>", unsafe_allow_html=True)

        # --- 世界観 ---
        st.markdown(lang_mgr.get("text_0139", "### 舞台と世界観"))

        rd["world_free"] = st.text_area(
            lang_mgr.get("text_0140", "ゲーム開始時の状況（自由記述）"),
            value=rd.get("world_free", ""),
            height=90,
            key="rel_world_free"
        )
        
        wm_val = st.session_state.get("world_mode", "現代")
        w_map = {
             "現代": "現実（に近い）の日本",
             "ファンタジー": "異世界ファンタジー",
             "SF": "サイバーパンク未来"
        }
        rd["world_choice"] = w_map.get(wm_val, "現実（に近い）の日本")

        # --- FIX: world_detail Conflict Fix ---
        # Do not assign st.session_state.world_detail = ...
        st.text_area(
            lang_mgr.get("text_0141", "世界の追加ルール（最優先・全チャットに影響）"),
            value=st.session_state.get("world_detail",""),
            height=140,
            key="world_detail"
        )

        st.markdown("<hr>", unsafe_allow_html=True)

        # --- Bottom Actions ---
        if "intro_text" not in st.session_state:
            st.session_state.intro_text = ""

        if st.button(lang_mgr.get("text_0142", "メイン導入生成"), width="stretch", key="btn_gen_main"):
            st.session_state.intro_mode = "main"
            st.session_state.start_choice = "main"
            
            client = st.session_state.gemini_client
            rd = st.session_state.relationship_data
            
            main_saved = load_heroine_from_save(main_save_path)
            sub_saved = None  # サブヒロインシステムは使用しない)
            
            main_profile = (main_saved or {}).get("final_texts", {}).get("main_profile", "")
            sub_profile = (sub_saved or {}).get("final_texts", {}).get("main_profile", "")
            
            player_name = st.session_state.get("user_name", "主人公")
            player_age = st.session_state.get("user_age", "青年")
            
            main_name = (main_saved or {}).get("user_input", {}).get("Name", "メインヒロイン")
            sub_name = (sub_saved or {}).get("user_input", {}).get("Name", "サブヒロイン")

            prompt_text = build_intro_prompt(rd, main_profile, sub_profile, "main", player_name, player_age, main_name, sub_name)

            with st.spinner(lang_mgr.get("text_0143", "メイン導入を生成中...")):
                sys_prompt = "あなたは優秀なシナリオライターです。"
                history = [{"role": "user", "parts": [prompt_text]}]
                intro = client.generate_response(history, sys_prompt)

            if intro:
                st.session_state.intro_text = intro
                st.rerun()
            else:
                st.toast(lang_mgr.get("text_0144", "導入生成に失敗しました"), icon="⚠️")

        if has_sub:
            c_sub, c_both = st.columns(2)
            with c_sub:
                if st.button(lang_mgr.get("text_0145", "サブ導入生成"), width="stretch", key="btn_gen_sub"):
                    st.session_state.intro_mode = "sub"
                    st.session_state.start_choice = "sub"
                    
                    client = st.session_state.gemini_client
                    rd = st.session_state.relationship_data
                    
                    main_saved = load_heroine_from_save(main_save_path)
                    sub_saved = None  # サブヒロインシステムは使用しない)
                    
                    main_profile = (main_saved or {}).get("final_texts", {}).get("main_profile", "")
                    sub_profile = (sub_saved or {}).get("final_texts", {}).get("main_profile", "")
                    
                    player_name = st.session_state.get("user_name", "主人公")
                    player_age = st.session_state.get("user_age", "青年")
                    
                    main_name = (main_saved or {}).get("user_input", {}).get("Name", "メインヒロイン")
                    sub_name = (sub_saved or {}).get("user_input", {}).get("Name", "サブヒロイン")

                    prompt_text = build_intro_prompt(rd, main_profile, sub_profile, "sub", player_name, player_age, main_name, sub_name)

                    with st.spinner(lang_mgr.get("text_0146", "サブ導入を生成中...")):
                        sys_prompt = "あなたは優秀なシナリオライターです。"
                        history = [{"role": "user", "parts": [prompt_text]}]
                        intro = client.generate_response(history, sys_prompt)

                    if intro:
                        st.session_state.intro_text = intro
                        st.rerun()

            with c_both:
                if st.button(lang_mgr.get("text_0147", "BOTH導入生成"), width="stretch", key="btn_gen_both"):
                    st.session_state.intro_mode = "both"
                    st.session_state.start_choice = "both"
                    
                    client = st.session_state.gemini_client
                    rd = st.session_state.relationship_data
                    
                    main_saved = load_heroine_from_save(main_save_path)
                    sub_saved = None  # サブヒロインシステムは使用しない)
                    
                    main_profile = (main_saved or {}).get("final_texts", {}).get("main_profile", "")
                    sub_profile = (sub_saved or {}).get("final_texts", {}).get("main_profile", "")
                    
                    player_name = st.session_state.get("user_name", "主人公")
                    player_age = st.session_state.get("user_age", "青年")
                    
                    main_name = (main_saved or {}).get("user_input", {}).get("Name", "メインヒロイン")
                    sub_name = (sub_saved or {}).get("user_input", {}).get("Name", "サブヒロイン")

                    prompt_text = build_intro_prompt(rd, main_profile, sub_profile, "both", player_name, player_age, main_name, sub_name)

                    with st.spinner(lang_mgr.get("text_0148", "BOTH導入を生成中...")):
                        sys_prompt = "あなたは優秀なシナリオライターです。"
                        history = [{"role": "user", "parts": [prompt_text]}]
                        intro = client.generate_response(history, sys_prompt)

                    if intro:
                        st.session_state.intro_text = intro
                        st.rerun()

        st.session_state.intro_text = st.text_area(
            lang_mgr.get("text_0149", "導入（編集可能）"),
            value=st.session_state.intro_text,
            height=220,
            key="intro_text_area"
        )

        st.markdown("---")

        if st.button(lang_mgr.get("text_0150", "これでゲームスタート"), type="primary", width="stretch"):
            if "start_choice" not in st.session_state or not st.session_state.start_choice:
                st.session_state.start_choice = "main"

            # ▼▼▼ Organic Guard Correction Logic (Irregular Numbers + Noise) ▼▼▼
            import random # Ensure random is available locally if not global

            # 1. Define Modifiers (Irregular Numbers)
            RELATION_MODS = {
                "なし": 0,         # Will be randomized later
                "赤の他人": 21,     # Was 20
                "知り合い": 12,     # Was 10
                "友達": -4,        # Was -5
                "プレイヤーが片思い": -6, # Was -5
                "ヒロインが片思い": -10,  # Was -19
                "両思い": -12,      # Was -33
                "恋人": -16,        # Was -42
                "愛人": -18,        # Was -47
                "夫婦": -20         # Was -53
            }

            def get_llm_correction(free_text):
                if not free_text or len(free_text) < 2:
                    return 0
                try:
                    # Instruct LLM to use non-round numbers
                    prompt = f"""
                    Evaluate the 'Guard/Guard Modifier' (integer) based on: "{free_text}"
                    
                    Rules:
                    - Negative = Looser guard. Positive = Stricter guard.
                    - Range: -50 to +50.
                    - **IMPORTANT: Do NOT use round numbers (multiples of 5 or 10).**
                    - Use irregular numbers like -12, -33, +4, +21.
                    - If neutral, output 0.
                    """
                    client = st.session_state.gemini_client
                    res = client.generate_text(prompt).strip()
                    import re
                    match = re.search(r'[-+]?\d+', res)
                    if match:
                        return int(match.group(0))
                except:
                    pass
                return 0

            def apply_complex_correction(hero_dict, rel_choice, rel_free):
                if not hero_dict or not isinstance(hero_dict, dict): return
                
                # A. Base from Job (Fix: Read Chastity first)
                fs = hero_dict.get("final_status", {})
                base_c = int(fs.get("Chastity", fs.get("Guard", 50)))
                
                # B. Dropdown Modifier
                mod_choice = RELATION_MODS.get(rel_choice, 0)
                
                # C. LLM Free Text Modifier
                mod_free = 0
                if rel_free:
                    with st.spinner(f"関係性({hero_dict.get('user_input',{}).get('Name')})を解析中..."):
                        mod_free = get_llm_correction(rel_free)
                
                # D. Random Noise (The "Organic" Factor)
                # Adds +/- 3 variance to avoid static values
                noise = random.randint(-3, 3)
                
                # Zero Avoidance for "None"
                if rel_choice == "なし" and noise == 0:
                    noise = random.choice([-2, -1, 1, 2])

                # Final Calculation
                total_mod = mod_choice + mod_free + noise
                final_val = max(0, min(100, base_c + total_mod))
                
                # Update & Save (Fix: Save to Chastity)
                fs["Chastity"] = final_val
                # Legacy support
                fs["Guard"] = final_val
                path = hero_dict.get("save_path", "")
                
                # Debug Toast
                st.toast(f"{hero_dict.get('user_input',{}).get('Name')}: ガード {base_c} -> {final_val} (固定{mod_choice:+}/自由{mod_free:+}/揺らぎ{noise:+})", icon="🎲")

                if path and os.path.exists(path):
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        
                        # CRITICAL FIX: Update the data object before saving
                        data["final_status"] = fs

                        with open(path, "w", encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                    except Exception as e:
                        print(f"Status Save Error: {e}")

            # Apply Logic
            rd = st.session_state.relationship_data
            apply_complex_correction(st.session_state.get("main_heroine"), rd.get("main_relation_choice"), rd.get("main_relation_free"))
            
            # サブヒロインシステムは使用しない

            st.session_state.game_initialized = False
            st.session_state.phase = "game"
            st.rerun()

    with col_left:
        if isinstance(main_saved, dict):
            ui = main_saved.get("user_input", {})
            ft = main_saved.get("final_texts", {})
            img_p = ""
            if main_save_path:
                cand = os.path.splitext(main_save_path)[0] + ".png"
                if os.path.exists(cand):
                    img_p = cand

            render_hero_card(
                img_p,
                ui.get("Name",""),
                ui.get("Visual Age",""),
                ui.get("Job",""),
                ft.get("main_profile","")
            )
        else:
            pass

    with col_right:
        if isinstance(sub_saved, dict):
            ui = sub_saved.get("user_input", {})
            # サブヒロインシステムは使用しない
            img_p = ""

            render_hero_card(
                img_p,
                ui.get("Name",""),
                ui.get("Visual Age",""),
                ui.get("Job",""),
                ft.get("main_profile","")
            )
        else:
            pass

    st.write("")
    c1, c2 = st.columns(2)

    with c1:
        if st.button(lang_mgr.get("text_0152", "↩ メインヒロインへ戻る"), width="stretch"):
            st.session_state.create_target = "main"
            st.session_state.main_heroine = None
            # サブヒロインシステムは使用しない

            st.session_state.user_input = {
                "Name": "", "Visual Age": "18", "Job": "学生",
                "Appearance": "", "Personality": "普通", "Hobby": "", "Tone": "普通"
            }

            for k in [
                "final_texts",
                "final_status",
                "final_image_data",
                "relationship_data",
                "intro_text",
            ]:
                if k in st.session_state:
                    del st.session_state[k]

            st.session_state.phase = "create"
            st.rerun()

    with c2:
        if st.button(lang_mgr.get("text_0153", "戻る"), width="stretch"):
            st.session_state.phase = "create"
            st.rerun()

# ==========================================
# 3. Main Routing (Moved to End)
# ==========================================

# ==========================================
# 3. Main Routing (Corrected)
# ==========================================

def main():
    if "phase" not in st.session_state:
        st.session_state.phase = "title"

    # ▼▼▼ 言語設定の確認と再適用 ▼▼▼
    # 言語設定の読み込み（セッションステートから）
    if "language" not in st.session_state:
        st.session_state.language = "jp"
    
    # ここで最新の状態（ユーザーが選んだ言語）をロードし直す
    lang_mgr.load_data(st.session_state.language, "male_target")
    # ▲▲▲

    with st.sidebar:
        st.header("🌐 Language")
        # 言語を選択するプルダウン（中国語も含む）
        lang_options_sidebar = {
            "日本語 (Japanese)": "jp",
            "English": "en",
            "简体中文 (Simplified Chinese)": "zh-CN",
            "繁體中文 (Traditional Chinese)": "zh-TW"
        }
        
        # 現在の言語に対応するキーを取得
        current_lang = st.session_state.get("language", "jp")
        current_lang_key = "日本語 (Japanese)"
        for key, value in lang_options_sidebar.items():
            if value == current_lang:
                current_lang_key = key
                break
        
        selected_lang_key = st.selectbox(
            "Language / 言語", 
            options=list(lang_options_sidebar.keys()),
            index=list(lang_options_sidebar.keys()).index(current_lang_key) if current_lang_key in lang_options_sidebar else 0,
            key="lang_select_box"
        )
        
        selected_lang = lang_options_sidebar[selected_lang_key]
        # 切り替わったらリロード
        if selected_lang != st.session_state.language:
            st.session_state.language = selected_lang
            lang_mgr.load_data(selected_lang, "male_target")
            st.rerun()
            
        st.divider()
    # ▲▲▲ 追加 ▲▲▲

    if "phase" not in st.session_state:
        st.session_state.phase = "title"

    # Web体験版: 認証画面をスキップ（age_verifiedは常にTrue）
    # if not st.session_state.age_verified:
    #     render_age_gate()
    #     st.stop()

    # Safeguard
    safeguard_title_flow()

    # --- Phase Routing ---
    if st.session_state.phase == "title":
        components.inject_custom_css()
        render_title_screen()
    


    elif st.session_state.phase == "create":
        components.inject_custom_css()
        apply_background_theme("edit")
        render_create_phase()

    elif st.session_state.phase == "relationship":
        components.inject_custom_css()
        apply_background_theme("edit")
        render_relationship_phase()

    elif st.session_state.phase == "game":
        # 修正前: apply_background_theme("play") 
        # "play" は定義にないので else に落ちていた。
        # 明示的に "game" を指定して else ブロック（ゲーム画面用CSS）を適用させる。
        apply_background_theme("game")
        game_start_dummy_if_needed()
        render_game_screen()
    
    else:
        st.session_state.phase = "title"
        st.rerun()

# ==========================================
# ==========================================
# Web体験版: Streamlit Community Cloud用エントリーポイント
if __name__ == "__main__":
    # Web体験版では常にmain()を直接呼び出す
    main()