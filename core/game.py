import random
import re

from core.models import SKILL_DEFINITIONS

# ==========================================
# Prompt Construction
# ==========================================
def generate_image_prompt(h):
    # Simplified prompt builder using the new 'visual_tags'
    base = "masterpiece, best quality, highres, anime style, 1girl, solo, cowboy shot"
    
    # Use h['visual_tags'] if available, otherwise fallback
    visuals = h.get('visual_tags', "")
    if not visuals and h.get('hair_color', "unknown") != "unknown":
         visuals = f"{h.get('hair_color')} hair, {h.get('hair_style')}, {h.get('eye_color')} eyes, {h.get('outfit')}"
         
    p_prompt = "blush, shy"
    pers = h['personality']
    if "ツンデレ" in pers or "強気" in pers:
        p_prompt = random.choice(["arms crossed, looking away, blushing", "pout, angry face"])
    elif "元気" in pers or "活発" in pers:
        p_prompt = random.choice(["peace sign, big smile, open mouth", "leaning forward, winking"])
    elif "大人" in pers or "お姉さん" in pers:
        p_prompt = random.choice(["hands on cheek, ara ara, seductive smile", "finger on lips"])
    
    angle = random.choice(["slightly from above", "from side", "dutch angle", "straight on"])
    prompt = f"{base}, {visuals}, {h['bust']} cup, {p_prompt}, {angle}, beautiful eyes, detailed face"
    return prompt

def construct_system_prompt(h, current_love, current_lust, current_reason, is_skill_active=False, active_skill_data=None):
    prompt = f"""
    あなたは恋愛ゲームのヒロイン「{h['name']}」です。
    以下の設定と現在のステータスになりきって対話してください。

    **【現在のステータス】**
    - ❤️ 好感度: {current_love}%
    - 😈 興奮度: {current_lust}%
    - 🧠 理性: {current_reason}%

    **【キャラクター設定】**
    - {h['age']}歳 / {h['job']} / {h['personality']}
    - 身体特徴: {h['body_desc']} ({h['bust']}カップ)
    - 性器特徴: {h['genital_desc']}
    - 経験: {h['experience_desc']}
    - 彼との関係: {h['backstory']}
    - 口調: {h.get('style', h.get('speaking_style', '標準語'))}
    - 感情パラメーター(25種): 喜び, 期待, 羞恥, 官能, 欲望, etc...
    
    **【隠し要素 (プレイヤーには秘密)】**
    - 隠し性癖: {h['trait']}
    (※この性癖は、好感度MAX・興奮MAX・理性0(崩壊)の状態になった時のみ、発露させてください。それまでは隠し通してください。)

    **【描写フォーマット】**
    1. **セリフ:** 実際に口に出す言葉のみ、鍵括弧「」で囲む。
    2. **地の文:** 鍵括弧の外に書く。
    3. **心の声:** () または（）で囲む。
    4. **強調:** 重要な単語は **アスタリスク2つ** で囲んで太字にする（鍵括弧は不要）。
    """
    
    # スキル継続中の追加指示
    skill_instruction = ""
    if is_skill_active and active_skill_data:
        data = active_skill_data
        skill_instruction = f"""
        \n**【⚠️ 重要：現在特殊スキルが発動中です】**
        現在の状態: {data.get('during', '')}
        この設定を維持し、解除されるまで通常の状態には戻らないでください。
        """
        prompt += skill_instruction

    prompt += """
    **【出力ルール (絶対厳守)】**
    1. **ステータス数値や感情分析を、会話本文には絶対に書かないでください。** 会話の没入感を損ないます。
    2. レスポンスの**末尾**に、必ず以下のXMLタグ形式のみを使って内部データを出力してください。
    
    (Output Template):
    「(ここにセリフと描写)」
    <emo>
    【喜び】80【期待】50【羞恥】30
    </emo>
    """
    return prompt

# ==========================================
# Game State Logic
# ==========================================
def update_status_from_emotions(heroine, text):
    """Parses <emo> tags and updates heroine status in-place."""
    try:
        # 1. Try finding <emo> tags first
        match = re.search(r"<emo>(.*?)</emo>", text, re.DOTALL)
        if match:
            emo_str = match.group(1)
        else:
            # Fallback: Look for the pattern at the end of text if tag is missing
            emo_str = text 

        # Parse items like 【喜び】80 or [喜び:80] or 喜び: 80
        items = re.findall(r"[【\[](.*?)[】\]][:：]?\s*(\d+)", emo_str)
        
        # If standard brackets failed, try simplified pattern "Name: Number" at end of line
        if not items:
             items = re.findall(r"(?:\n|^)\s*([^\s:0-9]+)[:：]\s*(\d+)", emo_str)

        if items:
            # Merge New Emotions
            if 'emotions' not in heroine:
                 heroine['emotions'] = {}
            
            # Filter and update
            for name, val in items:
                if len(name) < 10: 
                    heroine['emotions'][name] = int(val)
            
            current_emos = heroine['emotions']

            # 1. Love (好感度)
            love_keywords = ["愛情", "信頼", "共感", "満足", "幸福", "好意", "喜び", "感謝", "安心", "期待"]
            love_score = sum([current_emos.get(k, 0) for k in love_keywords])
            # Scaling: Divide sum by 3.5
            heroine['love'] = min(100, max(0, int(love_score / 3.5)))

            # 2. Lust (興奮度)
            lust_keywords = ["官能", "欲望", "衝動", "陶酔", "興奮", "発情", "快感"]
            lust_score = sum([current_emos.get(k, 0) for k in lust_keywords])
            # Scaling: Divide sum by 3.0
            heroine['lust'] = min(100, max(0, int(lust_score / 3.0)))

            # 3. Reason (理性)
            # 興奮度に応じて減少し、羞恥心で少し回復する計算
            shame = current_emos.get("羞恥", 0)
            base = 100
            erosion = heroine['lust'] 
            resistance = int(shame * 0.5)
            heroine['reason'] = min(100, max(0, base - erosion + resistance))
            
            return True # Updated
            
    except Exception as e:
        print(f"Emotion Parse Error: {e}")
    return False # Not updated
