import streamlit as st
import random
import json
import re
import os
import time
import urllib.request
import urllib.parse
import sys
from core.llm import GeminiClient

# ★★★★ これを追加！！ ★★★★
from config import COMFYUI_SERVER_ADDRESS, IS_DEMO_MODE
# ★★★★★★★★★★★★★★★★★

# ==========================================
# 📍 GPS修正：ファイルの場所を正確に特定！
# ==========================================
CURRENT_FILE_PATH = os.path.abspath(__file__)
CORE_DIR = os.path.dirname(CURRENT_FILE_PATH)
BASE_DIR = os.path.dirname(CORE_DIR)

print(f"📍 Generator BASE_DIR: {BASE_DIR}")

# ==========================================
# 0. 共通ヘルパー
# ==========================================
def get_gemini_client():
    if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
        return GeminiClient(st.secrets["GEMINI_API_KEY"])
    return None

# ==========================================
# 1. Constants & Definitions
# ==========================================
LIBIDO_LIST = ["少し拒絶", "無い", "普通", "ムッツリ", "強め", "モンスター"]
EXPERIENCE_LIST = ["無い", "少し", "普通", "慣れ切っている"]
SENSITIVITY_LIST = ["鈍い", "普通", "感じやすい", "すごく感じやすい"]

MAX_HISTORY = 10

LOC_CAT_REST = "REST"
LOC_CAT_SOCIAL = "SOCIAL"
LOC_CAT_DANGER = "DANGER"
LOC_CAT_EROS = "EROS"

LOCATION_DATA = {
    "01_HOME": {
        "base_id": "01_HOME",
        "category": LOC_CAT_REST,
        "fallback_display_name": "自宅",
        "tags": "indoors, private room",
        "air": "生活の拠点となる私的空間。安心感があり緊張は生まれにくい。"
    },
    "02_NATURE": {
        "base_id": "02_NATURE",
        "category": LOC_CAT_REST,
        "fallback_display_name": "公園・自然",
        "tags": "outdoors, nature, park",
        "air": "屋外の開放的な空間。自然の音や風を感じる。"
    },
    "03_CITY": {
        "base_id": "03_CITY",
        "category": LOC_CAT_SOCIAL,
        "fallback_display_name": "街中",
        "tags": "outdoors, city street, crowd",
        "air": "人通りの多い公共の場。周囲の目があるため派手な行動は控えがち。"
    },
    "04_DINING": {
        "base_id": "04_DINING",
        "category": LOC_CAT_SOCIAL,
        "fallback_display_name": "カフェ・飲食店",
        "tags": "indoors, cafe, restaurant",
        "air": "食事や会話を楽しむ場所。落ち着いた社交の場である。"
    },
    "05_WORK": {
        "base_id": "05_WORK",
        "category": LOC_CAT_SOCIAL,
        "fallback_display_name": "学校・職場",
        "tags": "indoors, classroom, office",
        "air": "規律と役割が求められる公的な場。私的な感情は抑えがち。"
    },
    "06_EVENT": {
        "base_id": "06_EVENT",
        "category": LOC_CAT_SOCIAL,
        "fallback_display_name": "イベント会場",
        "tags": "outdoors, amusement park, event",
        "air": "非日常を楽しむ賑やかな場。高揚感があり開放的になりやすい。"
    },
    "07_TRANSIT": {
        "base_id": "07_TRANSIT",
        "category": LOC_CAT_DANGER,
        "fallback_display_name": "移動中",
        "tags": "indoors, train, car",
        "air": "移動中の閉鎖空間。目的地への期待や旅の風情がある。"
    },
    "08_DUNGEON": {
        "base_id": "08_DUNGEON",
        "category": LOC_CAT_DANGER,
        "fallback_display_name": "路地裏・暗がり",
        "tags": "outdoors, back alley, dim light",
        "air": "危険と隣り合わせの緊張感ある場所。油断はできない。"
    },
    "09_PRIVATE": {
        "base_id": "09_PRIVATE",
        "category": LOC_CAT_EROS,
        "fallback_display_name": "個室・密室",
        "tags": "indoors, private room, dim light",
        "air": "二人きりになれる密室。他者の目を気にせず親密になれる。"
    },
    "10_BED": {
        "base_id": "10_BED",
        "category": LOC_CAT_EROS,
        "fallback_display_name": "ベッド・寝室",
        "tags": "indoors, bedroom, bed",
        "air": "最も無防備で親密な場所。身体的な接触や深い情愛を受け入れやすい。"
    }
}

# --- Generation Constants ---
CHECKPOINT_NAME = "bluePencil_v10.safetensors"
LORA_NAME = "ufotableStyle_v20.safetensors"
LORA_STRENGTH = 0.4
CLIP_STRENGTH = 1.0
# configの設定を使うように変更！
COMFY_URL = f"http://{COMFYUI_SERVER_ADDRESS}"

STYLE_PREFIX = "score_9, score_8_up, score_7_up, source_anime, visual novel, japanese anime style, moe, ufotable, highly detailed anime CG, cute girl, flat color, cel shading, "

FIXED_POSITIVE_HEADER = """
(masterpiece, best quality:1.4), (official art:1.2), (absurdres, highres:1.2), UareBrav, <lora:more_details:0.5>, 
(super fine illustration), detailed beautiful anime face, detailed eyes, vivid colors, cinematic lighting, sparkling, bloom, depth of field, 
"""
FIXED_POSITIVE_HEADER = FIXED_POSITIVE_HEADER.strip().replace("\n", " ")

R18_ADDITIONAL_TAGS = "(erotic:1.1), (soft erotic:1.2), shiny skin, blushing, slight sweat, emphasis on curves, dynamic angle, "

FIXED_NEGATIVE_PROMPT = "(worst quality, low quality:1.4), (realistic, photorealistic, 3d, cosplay:1.3), lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, jpeg artifacts, signature, watermark, username, blurry, male face, handsome male, detailed male face, ugly face, mutated hands, bad proportions, simple background, flat color"

BASE_STANDING_PROMPT = "1girl, solo, cinematic lighting, detailed face"
BASE_INTIMATE_PROMPT = "first person POV from male, (focus on girl:1.4), male back view, anonymous male, partial male body, no male face, detailed erect penis, close up penetration into pussy, wet skin, explicit genitalia, dynamic angle"
BASE_MULTI_INTIMATE = "first person POV from male, (focus on girls:1.4), male back view, anonymous male, partial male body, no male face, detailed erect penis in foreground, two girls interacting intimately with penis, close up vaginal penetration, oral sex on penis, wet saliva and love juice on shaft, dripping from pussies, explicit focus on genitalia interaction, dynamic wet composition"
BASE_MULTI_NORMAL = "two girls, intimate group pose, sitting together or standing close, casual clothes, warm atmosphere, detailed faces, two subjects close together, gentle interaction, side by side, soft embrace"


# ==========================================
# 2. Helper Logic
# ==========================================
def load_hidden_fetishes():
    """assets/pure_secrets.json からリストを読み込む。"""
    path = os.path.join(BASE_DIR, "assets", "pure_secrets.json")
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except:
            pass
    return [{"name": "不明 (JSON読込失敗)", "description": "データが見つかりませんでした"}]

def load_json_asset(path):
    """汎用JSONローダー"""
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return None
    return None

def pick_random_trait(asset_path, default_id, default_desc):
    """指定アセットからランダムに1つ特徴を選ぶ"""
    data = load_json_asset(asset_path)
    traits = (data or {}).get("traits", {})
    if isinstance(traits, dict) and traits:
        k = random.choice(list(traits.keys()))
        d = traits.get(k, {}) if isinstance(traits.get(k), dict) else {}
        desc = d.get("desc", "") if isinstance(d, dict) else ""
        return k, (desc or default_desc)
    return default_id, default_desc

def determine_chastity_from_job(client, job_text):
    """
    職業からChastity(0-100)を決定する。
    1. JSON辞書マッチング (高速)
    2. 失敗時、LLM判定 (高精度)
    """
    base_chastity = 50
    matched = False
    
    try:
        json_path = os.path.join(BASE_DIR, "assets", "job_stats.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            status_map = data.get("status_map", [])
            base_chastity = data.get("default_chastity", 50)
            
            for item in status_map:
                keyword = item.get("keyword", "")
                if keyword and keyword in job_text:
                    base_chastity = int(item.get("chastity", 50))
                    matched = True
                    break
    except Exception as e:
        print(f"Error loading job stats: {e}")

    # 2. LLM Fallback
    if not matched and client:
        try:
            prompt = f"職業『{job_text}』の一般的な貞操観念（ガードの堅さ）を推測し、0(最低)〜100(鉄壁)の整数値のみを出力してください。解説不要。"
            val_str = client.generate_text(prompt).strip()
            import re
            m = re.search(r'\d+', val_str)
            if m:
                base_chastity = int(m.group(0))
                base_chastity = max(0, min(100, base_chastity))
        except Exception as e:
            print(f"LLM Chastity Check Error: {e}")

    return base_chastity

def determine_fixed_status(client, user_input):
    stats = {}
    job_text = str(user_input.get("Job", "")).strip()

    # 1. ガード値(Chastity) - 職業ベースの基本値を決める
    # ※これは「建前上のガード」として使う
    base_chastity = determine_chastity_from_job(client, job_text)
    stats["Chastity"] = base_chastity

    # 2. 3大ステータス 【修正: 完全ランダム抽選】
    # AIの推論やガード値による補正を廃止し、リストから無慈悲に選ぶ
    
    # 性欲 (Libido): ["少し拒絶", "無い", "普通", "ムッツリ", "強め", "モンスター"]
    stats["Libido"] = random.choice(LIBIDO_LIST)
    
    # 感度 (Sensitivity): ["鈍い", "普通", "感じやすい", "すごく感じやすい"]
    stats["Sensitivity"] = random.choice(SENSITIVITY_LIST)
    
    # 経験 (Experience): ["無い", "少し", "普通", "慣れ切っている"]
    # ★修正: Chastityによる上書きロジックを削除し、完全ランダムにする
    # これにより「処女のギャル」や「経験豊富な委員長」が生まれる
    stats["Experience"] = random.choice(EXPERIENCE_LIST)
    
    # (主婦などの特殊条件のみ残す場合はここに追加するが、基本はランダム優先)
    # if "人妻" in job_text: stats["Experience"] = "夫婦生活のみ"

    # 3. 隠しパラメータ (R15修正: 過激な要素は廃止)
    
    # (1) Hidden Fetish -> R15では不要なので "なし" 固定
    # fetishes = load_hidden_fetishes()
    stats["HiddenFetish"] = "なし"
    stats["HiddenFetishDesc"] = ""

    # (2) BreastTrait (乳首) -> 視覚的な描写として残しても良いが、今回は安全のため標準固定
    # nip_path = os.path.join(BASE_DIR, "assets", "pure_body_traits.json")
    stats["BreastTraitId"] = "Normal"
    stats["BreastTraitDesc"] = "一般的な色と形状"

    # (3) VaginaTrait (膣形状) -> R15では完全に不要（描写事故の元）
    # vag_path = os.path.join(BASE_DIR, "assets", "pure_lip_shapes.json")
    stats["VaginaTraitId"] = "Normal"
    stats["VaginaTraitDesc"] = ""  # 空文字にして描写させない
    stats["VaginaTraitNote"] = "" 

    return stats

def append_visual_tags(client, current_tags, user_addition_jp):
    if not user_addition_jp:
        return current_tags

    prompt = f"""
    You are an AI art prompt assistant.
    Current Tags: {current_tags}
    User Addition (Japanese): {user_addition_jp}

    Task:
    1. Translate the user's Japanese addition into high-quality Stable Diffusion English tags.
    2. Append them to the Current Tags.
    3. Return ONLY the merged tag string.
    """
    try:
        new_tags = client.generate_text(prompt).strip()
        new_tags = new_tags.replace("```", "")
        return new_tags
    except:
        return current_tags

# ==========================================
# 3. Image Generation Logic (ComfyUI)
# ==========================================
def select_workflow_file(is_r18: bool, is_both: bool) -> str:
    """状況に応じたワークフローファイル名を選択する"""
    assets_dir = os.path.join(BASE_DIR, "assets")
    
    # ファイル名の決定
    if is_both:
        if is_r18:
            filename = "workflow_both_r18.json"
        else:
            filename = "workflow_both_sfw.json"
    else:
        if is_r18:
            filename = "workflow_t2i_r18.json"
        else:
            filename = "workflow_t2i_sfw.json"
            
    # 1. assetsフォルダ内を探索
    full_path_assets = os.path.join(assets_dir, filename)
    if os.path.exists(full_path_assets):
        return full_path_assets

    # 2. ルート直下を探索 (EXE用)
    root_path = os.path.join(BASE_DIR, filename)
    if os.path.exists(root_path):
        return root_path
        
    # フォールバック
    print(f"⚠️ Workflow file not found: {filename}. Using fallback.")
    defaults = ["workflow_t2i.json", "workflow_api_blue.json"]
    
    for d in defaults:
        p_assets = os.path.join(assets_dir, d)
        if os.path.exists(p_assets): return p_assets
        p_root = os.path.join(BASE_DIR, d)
        if os.path.exists(p_root): return p_root
            
    return ""

def send_to_comfyui(generated_tags, force_single=False, is_r18=False, is_both=False):
    """
    ComfyUIにタグを送信し、生成された画像のバイナリデータを返す。
    体験版モードの場合は固定画像を返す。
    """
    # 体験版モード: 固定画像を返す
    if IS_DEMO_MODE:
        demo_image_path = os.path.join(BASE_DIR, "assets", "demo_images", "default.png")
        if os.path.exists(demo_image_path):
            try:
                with open(demo_image_path, "rb") as f:
                    image_data = f.read()
                return {"status": "success", "image_data": image_data, "debug_prompt": "[体験版] 固定画像を使用"}
            except Exception as e:
                return {"status": "error", "message": f"体験版画像読み込みエラー: {e}"}
        else:
            # 画像が存在しない場合はエラーを返す（後で画像を配置する必要がある）
            return {"status": "error", "message": "体験版画像が見つかりません: assets/demo_images/default.png"}
    
    seed_value = random.randint(1, 999999999999999)

    try:
        actual_both = is_both and (not force_single)
        workflow_path = select_workflow_file(is_r18, actual_both)
        
        if not workflow_path:
             return {"status": "error", "message": f"Workflow not found in {BASE_DIR}"}
             
        with open(workflow_path, "r", encoding="utf-8") as f:
            prompt_workflow = json.load(f)
            
        # 2. Inject Seed (Node 3)
        if "3" in prompt_workflow and "inputs" in prompt_workflow["3"]:
            prompt_workflow["3"]["inputs"]["seed"] = seed_value
            
        # 3. Inject Positive Prompt (Node 6)
        if "6" in prompt_workflow and "inputs" in prompt_workflow["6"]:
             header = FIXED_POSITIVE_HEADER
             if is_r18:
                 header += R18_ADDITIONAL_TAGS
             
             final_prompt = header
             main_tags = generated_tags
             
             scene_party = st.session_state.get("scene_party", {})
             if force_single:
                 has_sub = False
             else:
                 has_sub = scene_party.get("sub", False) if isinstance(scene_party, dict) else False

             if has_sub:
                 sub_h = st.session_state.get("chat_sub_heroine")
                 if sub_h and hasattr(sub_h, "appearance"):
                     sub_add = f", second girl: ({sub_h.appearance}:1.5), detailed {sub_h.name}, completely different from first girl"
                     main_tags += sub_add + ", two completely distinct girls, no blending, separate identities"

             if has_sub:
                 final_tags = "two distinct girls with different features, " + main_tags
                 final_tags = final_tags.replace("1girl,", "two girls,").replace("solo,", "").replace("unknown hair,", "").replace("unknown eyes,", "").replace("unknown,", "")
             else:
                 final_tags = main_tags
             
             is_r18 = st.session_state.get("is_r18_scene", False)
             main_h = st.session_state.get("chat_heroine")
             
             if has_sub:
                 sub_h = st.session_state.get("chat_sub_heroine")
                 main_prompt_part = ""
                 if main_h and hasattr(main_h, "appearance"):
                     main_prompt_part = f"first girl: ({main_h.appearance}:1.5), detailed {main_h.name}"
                 
                 sub_prompt_part = ""
                 if sub_h and hasattr(sub_h, "appearance"):
                     sub_prompt_part = f"second girl: ({sub_h.appearance}:1.5), detailed {sub_h.name}"
                 
                 character_details = f"two distinct girls, {main_prompt_part} BREAK {sub_prompt_part}, two separate characters, "
             else:
                 character_details = ""
                 # もしDNAタグ(visual_tags)がmain.pyから来ていない場合の保険として、
                 # visual_tags属性があれば足すくらいにしておく（今回はmain.pyで完結させるので空でOK）
                 if main_h and hasattr(main_h, "visual_tags") and main_h.visual_tags:
                     pass 

             # base_prompt も "looking at viewer" だけにして、ポーズ指定を消す
             base_prompt = "looking at viewer" 
             
             final_prompt += f", {character_details}{base_prompt}, {final_tags}"
             final_prompt = final_prompt.replace("unknown hair,", "").replace("unknown eyes,", "").replace("unknown,", "").strip()

             if is_r18:
                 # Blue Pencil向け：光と湯気による検閲（謎の光）
                 holy_light_tags = ", (censor light:1.3), (bright white light:1.2), lens flare, glowing light, steam"
                 final_prompt += f", NSFW {holy_light_tags}"

             prompt_workflow["6"]["inputs"]["text"] = final_prompt
             
             # ★ NEW: Erotic Unlock Check (Stat-based)
             # Chastity <= 20 & Reason <= 20 -> Unlock R15 Limit Erotic Tags
             is_erotic_unlocked = False
             if main_h:
                 chas = int(getattr(main_h, "chastity", 50))
                 reas = int(getattr(main_h, "reason", 100))
                 if chas <= 20 and reas <= 20:
                     is_erotic_unlocked = True
                     
                     # --- Context Aware Erotic Tags ---
                     current_hist = st.session_state.get("chat_history", [])
                     recent_text = " ".join([str(msg.get("parts", [""])[0]) for msg in current_hist[-5:]])
                     
                     # Base Erotic Tags
                     unlock_tags = ", partially nude, bare breasts, bare ass, deep cleavage, sideboob, sweaty glossy skin, aroused blushing face"
                     
                     # Action: Hug
                     if any(k in recent_text for k in ["抱き", "ぎゅっ"]):
                         unlock_tags += ", hugging, embracing"
                     
                     # Action: Kiss
                     if any(k in recent_text for k in ["キス", "唇", "接吻"]):
                         unlock_tags += ", kissing, close face, saliva"

                     # Sexual Acts (Non-Explicit/Implied)
                     if any(k in recent_text for k in ["手", "コキ", "撫で", "シゴ"]):
                         unlock_tags += ", handjob focus, holding blurred rod, saliva on hands, gentle stroking, motion blur hands"
                     elif any(k in recent_text for k in ["口", "舐め", "フェラ", "奉仕"]):
                         unlock_tags += ", open mouth, tongue out extended, saliva threads dripping, upward aroused gaze, cheek bulge"
                     elif any(k in recent_text for k in ["おっぱい", "挟", "パイ", "胸"]):
                         unlock_tags += ", paizuri, breasts squeezing tightly, deep overflowing cleavage, sweaty glossy boobs, deformed breasts"
                     elif any(k in recent_text for k in ["挿入", "入", "繋が", "中", "奥"]):
                         unlock_tags += ", intimate connected bodies hide genitals"
                         if "正常位" in recent_text: unlock_tags += ", missionary closeup embrace, face to face, legs wrapped around waist"
                         elif "騎乗" in recent_text: unlock_tags += ", cowgirl position, waist blur motion, breasts bouncing, riding motion"
                         elif "後背" in recent_text or "バック" in recent_text: unlock_tags += ", doggy style from behind, bare ass focus, arched back, grabbing hips"
                         elif "立位" in recent_text: unlock_tags += ", standing sex, wall pin embrace, legs wrapped, lifting carry"
                         
                     prompt_workflow["6"]["inputs"]["text"] += unlock_tags

        # 4. Negative Prompt (Node 7)
        if "7" in prompt_workflow and "inputs" in prompt_workflow["7"]:
            final_negative = FIXED_NEGATIVE_PROMPT
            final_negative += ", blended hairstyle, mixed hair color, mixed hair length, same hairstyle, hair fusion, unknown hair, unknown eyes, unknown features, blended characters, mixed hairstyle, same eyes, fusion character, identical girls, ambiguous appearance, low detail face, solo, 1girl, standing portrait, clothed if explicit"
            
            # ★ Logic Update for Erotic Unlock
            if is_erotic_unlocked:
                # Unlock mode: Allow nudity but block genitalia strictly
                final_negative += ", explicit genitalia, visible penis, vagina, pussy, pubic hair"
            elif not st.session_state.get("is_r18_scene", False):
                # Normal Daily: No erotic elements
                final_negative += ", nude, penis, explicit, sex"
            else:
                # R18 Scene: Allow erotic but censor genitalia (Steam/Light)
                final_negative += ", (uncensored:1.2), (detailed genitals:1.2), internal view"
            
            prompt_workflow["7"]["inputs"]["text"] = final_negative
        
    except Exception as e:
        return {"status": "error", "message": f"Workflow Load Error: {e}"}

    try:
        # 送信
        p = {"prompt": prompt_workflow}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request(f"{COMFY_URL}/prompt", data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as response:
            res_json = json.loads(response.read())
            prompt_id = res_json['prompt_id']

        # 待機 (ポーリング)
        while True:
            try:
                with urllib.request.urlopen(f"{COMFY_URL}/history/{prompt_id}") as res:
                    history = json.loads(res.read())
                    if prompt_id in history:
                        break
            except:
                pass
            time.sleep(1)

        # 画像取得
        history_data = history[prompt_id]
        outputs = history_data['outputs']
        if '9' in outputs and 'images' in outputs['9']:
            img_info = outputs['9']['images'][0]
            qs = urllib.parse.urlencode({'filename': img_info['filename'], 'subfolder': img_info['subfolder'], 'type': img_info['type']})
            with urllib.request.urlopen(f"{COMFY_URL}/view?{qs}") as img_res:
                return {"status": "success", "image_data": img_res.read(), "debug_prompt": final_prompt}
        else:
            return {"status": "error", "message": "画像が見つかりません"}

    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# 4. Text Generation Logic
# ==========================================
def generate_attribute_text(attribute_key):
    """ボタンを押した時に単語を一つ生成する (Legacy support for Gacha)"""
    client = get_gemini_client()
    defaults = {
        "Job": ["学生", "OL", "アイドル", "メイド", "スパイ"],
        "Personality": ["ツンデレ", "ヤンデレ", "清楚", "小悪魔"],
        "Body Type": ["スレンダー", "グラマラス", "小柄", "長身"],
        "Tone": ["タメ口", "敬語", "お嬢様言葉"],
        "Fetish": ["匂いフェチ", "マゾヒスト", "サディスト"]
    }
    
    if not client: 
        return random.choice(defaults.get(attribute_key, ["普通"]))

    prompt = f"""
    Provide one unique and interesting Japanese word/phrase for "{attribute_key}" suitable for an anime heroine.
    Output ONLY the word.
    """
    try:
        text = client.generate_text(prompt).strip().replace('"', '').replace("'", "")
        return text
    except:
        return random.choice(defaults.get(attribute_key, ["エラー"]))


def generate_all_texts(client, input_data, status_data):
    """
    入力データ + 3大ステータス(性欲・経験・感度) を元に執筆する。
    ★修正: AIの出力漏れに対応する頑丈設計
    """
    prompt = f"""
    You are a professional scenario writer for a "Seinen" visual novel.
    
    【Data】
    Name: {input_data.get('Name')} / Age: 18+ (Visual: {input_data.get('Visual Age')}) / Job: {input_data.get('Job')}
    Personality: {input_data.get('Personality')} / Tone: {input_data.get('Tone')}
    Appearance (Raw): {input_data.get('Appearance')}

    【Sensibility Params (CRITICAL)】
    Libido: {status_data['Libido']}
    Experience: {status_data['Experience']}
    Sensitivity: {status_data['Sensitivity']}

    【Tasks (Output in Japanese)】
    1. **Main Profile (Blue Box):** Write a self-introduction (Monologue).
       - **LENGTH:** **300 to 350 characters.** (Very dense and detailed).
       - **Perspective:** First Person ("I"). Let her speak in her own words.
       - Strictly reflect her "Tone" and personality.

    2. **Visual Detail (Green Box):** Describe her appearance.
       - **LENGTH:** **250 to 300 characters.**
       - **Requirement:** **MUST include her Bust Size (e.g., G-cup) explicitly.**
       - Describe hair, eyes, outfit, and body shape in detail.

    3. **Hidden Nature (Pink Box - The Secret):** - **LENGTH:** **Under 250 characters.**
       - **Perspective:** Third Person (Objective explanation/Analysis).
       - **Style:** Clear and descriptive. Do NOT use overly abstract/weird metaphors. Write naturally based on her character.
       - **Task:** Explain her sexual nature by reflecting Libido, Sensitivity, and Experience parameters.
       - **R15 CONSTRAINT:** Describe her heat, instincts, and reactions vividly, but **DO NOT describe explicit penetration.**

    4. **Image Prompt (English):** Visual tags only.
       - **Expression**: Include a specific facial expression tag.

    【Output Format (JSON Only)】
    {{
        "main_profile": "...",
        "visual_detail": "...",
        "sexual_profile": "...",
        "image_tags": "..."
    }}
    """

    try:
        txt = client.generate_text(prompt)
        # JSON抽出 (エラー回避ロジック付き)
        match = re.search(r'\{.*\}', txt, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            
            # ★ 安全策：キーが欠けていてもエラーにならないようにデフォルト値を合成する
            defaults = {
                "main_profile": "（プロフィールの生成に失敗しました）",
                "visual_detail": "（詳細データの生成に失敗しました）",
                "sexual_profile": "（裏データの生成に失敗しました）",
                "image_tags": "1girl, solo"
            }
            # 足りないキーがあればデフォルト値で埋める
            for k, v in defaults.items():
                if k not in data:
                    data[k] = v
            
            return data
        else:
            raise ValueError("JSON not found")
            
    except Exception as e:
        return {
            "main_profile": f"生成に失敗しました: {e}", 
            "visual_detail": "データなし",
            "sexual_profile": "データなし", 
            "image_tags": "1girl, error"
        }

def adapt_character_to_world(client, full_data, world_mode):
    """
    Apply World View Adjustment Filter.
    Adapts the character data (profile, job, appearance, etc.) to fit the specified world_mode.
    """
    if world_mode == "現代":
        return full_data

    prompt = f"""
    You are an AI character adaptation assistant.

    Task:
    Adapt the following character profile to fit the specified world setting.
    This is NOT a redesign. It is a translation of expressions.

    Rules:
    - Keep personality, core traits, and overall vibe unchanged.
    - Do NOT invent a new character.
    - Only rephrase elements that conflict with the world setting.
    - Prioritize metaphorical or stylistic conversion over literal replacement.
    - For "image_tags", update the English tags to match any visual changes (e.g. "suit" -> "robe" if job changed).

    World Mode:
    {world_mode}

    Input Character Data (JSON):
    {json.dumps(full_data, ensure_ascii=False, indent=2)}

    Output:
    Return the adapted character data in the SAME JSON structure.
    """

    try:
        txt = client.generate_text(prompt)
        match = re.search(r'\{.*\}', txt, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        else:
            return full_data
    except Exception as e:
        print(f"Adaptation Error: {e}")
        return full_data

# ==========================================
# 5. Location Logic Functions
# ==========================================

def normalize_location_display_name(text: str) -> str:
    """LLMが返したdisplay_nameをUI用に整形する"""
    if not text: return ""
    text = text.replace("\n", " ").replace("\r", " ").strip()
    if len(text) > 32: text = text[:32]
    return text

def get_location_air(location_state: dict) -> str:
    """current_location から場所の空気文（air）を取得する"""
    if not location_state: return ""
    base_id = location_state.get("base_id")
    if base_id in LOCATION_DATA:
        return (LOCATION_DATA[base_id].get("air") or "").strip()
    return ""

def get_location_air_prompt_string(location_state: dict) -> str:
    air = get_location_air(location_state)
    if air: return f"現在の場所の前提: {air}"
    return ""

def get_default_location_state() -> dict:
    return {"display_name": "自宅", "base_id": "01_HOME", "category": LOC_CAT_REST}

def ensure_location_state(session_state_like) -> None:
    if "current_location" not in session_state_like:
        session_state_like["current_location"] = get_default_location_state()

def judge_location_from_user_text(client, user_text: str) -> dict:
    """ユーザー発言から場所を推定する"""
    if not user_text or not user_text.strip():
        return {
            "base_id": "01_HOME", "category": LOC_CAT_REST, "display_name": "自宅", "move": False
        }

    candidates = []
    for k, v in LOCATION_DATA.items():
        candidates.append(f"- {k} (Default: {v['fallback_display_name']}, Cat: {v['category']})")
    candidates_str = "\n".join(candidates)

    prompt = f"""
You are a system analyzing user input for a text adventure game.
Determine the location, category, and display name implied by the user's text.

User Input: "{user_text}"

Candidate Location IDs:
{candidates_str}

Output JSON ONLY.
Format:
{{
  "base_id": "09_PRIVATE",
  "category": "EROS",
  "display_name": "個室居酒屋",
  "move": true
}}
"""
    try:
        response = client.generate_json(prompt)
        if not isinstance(response, dict):
            if isinstance(response, str):
                 match = re.search(r'\{.*\}', response, re.DOTALL)
                 if match: response = json.loads(match.group(0))
                 else: raise ValueError("Response is not a valid JSON dict")
        
        base_id = response.get("base_id")
        if base_id not in LOCATION_DATA:
             return {
                "base_id": "01_HOME", "category": LOC_CAT_REST,
                "display_name": normalize_location_display_name(response.get("display_name", "自宅")),
                "move": response.get("move", False)
            }

        display_name = normalize_location_display_name(response.get("display_name", ""))
        if not display_name:
            display_name = LOCATION_DATA[base_id]["fallback_display_name"]
            
        return {
            "base_id": base_id, "category": LOCATION_DATA[base_id]["category"],
            "display_name": display_name, "move": response.get("move", False)
        }

    except Exception as e:
        print(f"Location Switch Error: {e}")
        return { "base_id": "01_HOME", "category": LOC_CAT_REST, "display_name": "自宅", "move": False }