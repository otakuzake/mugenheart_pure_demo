import json
import random
import os
import re
import ast
from core import gacha

# --- 1. 定数・設定 ---

# ★貴方が決めた正真正銘のテーマリスト (全63種)
THEME_LIST = [
    "猫", "時間", "嘘・秘密", "炎", "水", "鏡", "旅人・冒険家", "科学者", "太陽", "祭り", 
    "アイドル", "ヒーロー", "秩序", "混沌", "空", "海", "砂漠", "音楽", "沈黙", "王侯・貴族", 
    "人形", "夢", "勇気", "希望", "ダンス", "月", "花", "図書館", "天使", "影", 
    "姉御", "魔法", "夜", "二面性", "誘惑・魔性", "機械", "孤独", "犬", "母性・守護", "妹", 
    "生意気", "臆病", "騎士", "蝶", "ドジ・ハプニング", "お調子者", "純粋", "ギャル", "メイド", "スポーツ", 
    "トリックスター", "氷", "雪", "巫女", "探偵", "怪盗", "宝石", "隠れ家", "宇宙", "森", 
    "委員長", "天然", "探求"
]

ASSET_PATHS = {
    "Job": "assets/jobs.json",
    "Personality": "assets/personalities.json",
    "Tone": "assets/tones.json"
}

# --- 2. アセット読み込み関数 (Safe Loader) ---
def load_asset_list(key):
    """
    指定されたJSONファイルからリストを読み込む。
    """
    path = ASSET_PATHS.get(key)
    default_values = ["普通"]
    
    if not path or not os.path.exists(path):
        return default_values

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                values = []
                for k, v in data.items():
                    if isinstance(v, str):
                        values.append(v)
                    elif isinstance(v, dict) and "name" in v:
                        values.append(v["name"])
                return values if values else default_values
            return default_values
    except:
        return default_values

# --- 3. ガチャ・連想生成ロジック (The Successful Logic) ---

def generate_profile_from_themes(gemini_client, world_mode="現代", world_detail=""):
    """
    テーマリストから2つ選び、連想ロジックでプロフィールを生成する。
    world_mode: "現代", "ファンタジー", "SF"
    world_detail: 追加の自由記述ルール
    戻り値: (テーマ名文字列, プロフィール辞書)
    """
    # 1. テーマ選出
    if len(THEME_LIST) < 2:
        themes = ["光", "闇"]
    else:
        themes = random.sample(THEME_LIST, 2)
        
    theme_str = f"{themes[0]} × {themes[1]}"

    # --- Helper Functions (Local Definition) ---
    def sanitize_job_text(job_text: str, themes: list[str]) -> str:
        if not job_text:
            return ""
        t = str(job_text).strip()

        # remove parentheses content (both JP and EN)
        t = re.sub(r"[（\(].*?[）\)]", "", t).strip()

        # remove theme words if present
        for th in (themes or []):
            if th:
                t = t.replace(th, "")
        # normalize spaces
        t = re.sub(r"\s{2,}", " ", t).strip()
        t = t.replace("　", " ").strip()
        return t

    def fallback_adapt_job(base_job: str, world_mode: str) -> str:
        bj = (base_job or "").strip()
        if not bj:
            return ""

        if world_mode == "ファンタジー":
            table = {
                "家庭教師": "個人指南役",
                "学生": "見習い",
                "OL": "ギルド事務官",
                "受付嬢": "ギルド受付",
                "医師": "治癒師",
                "看護師見習い": "癒し手見習い",
                "研究所職員": "魔導研究員",
            }
            return table.get(bj, bj)

        if world_mode == "SF":
            table = {
                "家庭教師": "パーソナルチューター",
                "学生": "訓練生",
                "OL": "メガコープ職員",
                "受付嬢": "セキュリティ受付",
                "医師": "メディカルオフィサー",
                "看護師見習い": "メディカルアシスタント",
                "研究所職員": "研究セクション職員",
            }
            return table.get(bj, bj)

        return bj
    
    # --- [New] Get Fixed Data from Gacha ---
    gacha_data = gacha.spin()
    base_job = gacha_data.get("Job", "学生")
    forced_tone = gacha_data.get("Tone", "普通")
    forced_pers = gacha_data.get("Personality", "普通")
    forced_body = gacha_data.get("Body", "普通")
    forced_cup = gacha_data.get("Cup", "普通")

    # APIがない場合のダミー返却
    if not gemini_client:
        dummy_data = {
            "Name": "テスト花子",
            "Visual Age": "18",
            "Job": base_job,
            "Appearance": f"テーマ『{theme_str}』風の服装",
            "Personality": forced_pers,
            "Hobby": f"テーマ『{theme_str}』に関連する趣味",
            "Tone": forced_tone
        }
        dummy_data.update(gacha_data)
        return theme_str, dummy_data
 
    # World Rule Definition
    if world_mode == "ファンタジー":
        world_rule = f"""
        World Setting: **High Fantasy** (dungeons, dragons, magic, kingdoms, guilds). Steampunk is allowed.
        Forbidden: modern Japan, office jobs, convenience stores, smartphones, real-world modern institutions.
        Name must be fantasy-style (non-Japanese is OK, Katakana preferred).
        
        **JOB ADAPTATION RULE:**
        The Base Job is "{base_job}". You MUST ADAPT this job to the Fantasy world.
        (e.g. "OL" -> "Guild Receptionist", "Student" -> "Magic Apprentice", "Nurse" -> "Healer", "Idol" -> "Songstress/Bard")
        
        Job must be fantasy role adapted from "{base_job}".
        Outfit and items must fit fantasy/steampunk.
 
        Additional World Rules:
        {world_detail}
        """
    elif world_mode == "SF":
        world_rule = f"""
        World Setting: **Sci-Fi / Future World** (cyberpunk, space colonies, mecha, dystopia, mega-corporations).
 
        IMPORTANT OUTPUT RULES:
        - Output language MUST be Japanese.
        - Do NOT output English sentences.
        - Names, job titles, and descriptions must be written in Japanese (katakana or kanji is allowed for sci-fi style).
        - English words may be used ONLY as proper nouns if absolutely necessary, but the surrounding text must be Japanese.
 
        Forbidden:
        - Full English output.
        - English-only descriptions.
        - Medieval kingdoms, fantasy magic systems.
 
        **JOB ADAPTATION RULE:**
        The Base Job is "{base_job}". You MUST ADAPT this job to the Sci-Fi world.
        (e.g. "OL" -> "Mega-Corp Clerk", "Student" -> "Pilot Trainee", "Police" -> "Security Droid Handler")
 
        Job must be future role adapted from "{base_job}".
        Outfit and items must fit sci-fi.
 
        Additional World Rules:
        {world_detail}
        """
    else:
        world_rule = f"""
        World Setting: **Modern-like Earth** (fictional). Contemporary life is allowed.
        Name should be normal Japanese name.
        
        **JOB RULE:**
        The Base Job is "{base_job}". Since this is a modern setting, use it as is or slightly refine it to match the theme.
        
        Outfit and items must fit modern.
 
        Additional World Rules:
        {world_detail}
        
        Important: If World Mode is Modern-like, output Job exactly as Base Job with no changes.
        """
 
    # Priority Block Construction
    priority_block = ""
    if world_detail:
        priority_block = f"""
    【Top Priority World Rules】
    {world_detail}
    - These rules override any default genre assumptions.
    - Do NOT introduce elements that contradict these rules.
        """
 
    # 言語設定を取得
    import streamlit as st
    current_lang = st.session_state.get("language", "jp")
    
    # AI生成プロンプト (強化版・World Mode対応・言語対応)
    if current_lang == "zh-CN" or current_lang == "zh-TW":
        # Chinese version (Simplified/Traditional)
        if current_lang == "zh-CN":
            prompt = f"""
    您是一位創意角色設計師。
    
    **重要：您必須用中文輸出所有字段。姓名、讀音、外觀、愛好、職業——一切都必須是中文。**
    
    【任務】
    基於兩個主題和固定屬性的「化學反應」生成角色概念。
    
    主題: **『{theme_str}』**
    
    {priority_block}

    {world_rule}
    
    【固定屬性（基礎）】
    1. **基礎職業:** {base_job}（參見職業適應規則）
    2. **語調:** {forced_tone}（她的性格符合此）
    3. **性格:** {forced_pers}
    4. **身體:** {forced_body}, {forced_cup}
    
    【「外觀」的關鍵規則】
    1. **無換行:** 將描述輸出為單個連續段落。不要使用項目符號。允許使用「，」或「 」等分隔符。
    2. **無數字身高:** 不要寫具體數字如「165cm」。使用形容詞如「高挑」「嬌小」或「苗條」。
    3. **整合身體和罩杯:** 您必須自然地將「{forced_body}」和「{forced_cup}」融入句子流程。
       - 錯誤: "體型：{forced_body}。罩杯：{forced_cup}。"
       - 正確: "〜，擁有{forced_body}的柔軟肢體，胸前{forced_cup}突出。服裝是〜"
    4. **無推理:** 不要解釋「為什麼」選擇這些特徵。直接輸出描述。

    【輸出要求】
    * **姓名:** 角色姓名（中文姓名，姓和名）。
    * **讀音:** 拼音讀音（可以與姓名相同或發音指南）。
    * **外觀:** 中文描述文本。整合體型、罩杯大小（{forced_cup}）、髮型和服裝的單個段落。
    * **愛好:** 中文的具體愛好或行為原則。
    * **職業:** 最終適應的職業名稱（中文）。
      - 「職業」字段必須僅是純角色名稱。
      - 不要添加主題詞、暱稱、括號、引號或任何裝飾性後綴/前綴。
      - 示例: "家庭教師"（正確），"家庭教師（冰之怪盜）"（錯誤）。
      - 如果世界模式是現代類，完全按照基礎職業輸出，不變更。
      - 如果世界模式是奇幻/科幻，適應職業措辭以適應世界但保持含義。無主題。
    * 僅輸出JSON。
    * 所有字段用中文輸出。
    
    【輸出格式（僅JSON）】
    {{
        "Name": "...",
        "Reading": "...",
        "Appearance": "...",
        "Hobby": "...",
        "Job": "..."
    }}
    """
        else:  # zh-TW
            prompt = f"""
    您是一位創意角色設計師。
    
    **重要：您必須用繁體中文輸出所有字段。姓名、讀音、外觀、愛好、職業——一切都必須是繁體中文。**
    
    【任務】
    基於兩個主題和固定屬性的「化學反應」生成角色概念。
    
    主題: **『{theme_str}』**
    
    {priority_block}

    {world_rule}
    
    【固定屬性（基礎）】
    1. **基礎職業:** {base_job}（參見職業適應規則）
    2. **語調:** {forced_tone}（她的性格符合此）
    3. **性格:** {forced_pers}
    4. **身體:** {forced_body}, {forced_cup}
    
    【「外觀」的關鍵規則】
    1. **無換行:** 將描述輸出為單個連續段落。不要使用項目符號。允許使用「，」或「 」等分隔符。
    2. **無數字身高:** 不要寫具體數字如「165cm」。使用形容詞如「高挑」「嬌小」或「苗條」。
    3. **整合身體和罩杯:** 您必須自然地將「{forced_body}」和「{forced_cup}」融入句子流程。
       - 錯誤: "體型：{forced_body}。罩杯：{forced_cup}。"
       - 正確: "〜，擁有{forced_body}的柔軟肢體，胸前{forced_cup}突出。服裝是〜"
    4. **無推理:** 不要解釋「為什麼」選擇這些特徵。直接輸出描述。

    【輸出要求】
    * **姓名:** 角色姓名（繁體中文姓名，姓和名）。
    * **讀音:** 拼音讀音（可以與姓名相同或發音指南）。
    * **外觀:** 繁體中文描述文本。整合體型、罩杯大小（{forced_cup}）、髮型和服裝的單個段落。
    * **愛好:** 繁體中文的具體愛好或行為原則。
    * **職業:** 最終適應的職業名稱（繁體中文）。
      - 「職業」字段必須僅是純角色名稱。
      - 不要添加主題詞、暱稱、括號、引號或任何裝飾性後綴/前綴。
      - 示例: "家庭教師"（正確），"家庭教師（冰之怪盜）"（錯誤）。
      - 如果世界模式是現代類，完全按照基礎職業輸出，不變更。
      - 如果世界模式是奇幻/科幻，適應職業措辭以適應世界但保持含義。無主題。
    * 僅輸出JSON。
    * 所有字段用繁體中文輸出。
    
    【輸出格式（僅JSON）】
    {{
        "Name": "...",
        "Reading": "...",
        "Appearance": "...",
        "Hobby": "...",
        "Job": "..."
    }}
    """
    elif current_lang == "en":
        prompt = f"""
    You are a creative character designer.
    
    **CRITICAL: You MUST output ALL fields in English. Name, Reading, Appearance, Hobby, Job - everything must be in English.**
    
    【Task】
    Generate a character concept based on the "Chemical Reaction" of two themes and FIXED attributes.
    
    Themes: **『{theme_str}』**
    
    {priority_block}

    {world_rule}
    
    【FIXED ATTRIBUTES (BASE)】
    1. **Base Job:** {base_job} (See Job Adaptation Rule)
    2. **Tone:** {forced_tone} (Her personality matches this)
    3. **Personality:** {forced_pers}
    4. **Body:** {forced_body}, {forced_cup}
    
    【CRITICAL RULES FOR "Appearance"】
    1. **NO LINE BREAKS:** Output the description as a SINGLE continuous paragraph. Do NOT use bullet points. Separators like "," or " " are allowed.
    2. **NO NUMERIC HEIGHT:** Do NOT write specific numbers like "165cm". Use adjectives like "Tall", "Petite", or "Slender".
    3. **INTEGRATE BODY & CUP:** You MUST naturally include "{forced_body}" and "{forced_cup}" in the sentence flow.
       - BAD: "Body type: {forced_body}. Cup size: {forced_cup}."
       - GOOD: "With a {forced_body} frame and soft limbs, her {forced_cup} breasts stand out. Her outfit is..."
    4. **NO REASONING:** Do NOT explain "why" you chose these features. Output the description directly.

    【Output Requirements】
    * **Name:** Character Name (English name, first and last name).
    * **Reading:** Phonetic reading (can be same as name or pronunciation guide).
    * **Appearance:** Descriptive text in English. A single paragraph integrating Body Type, Cup Size ({forced_cup}), Hair, and Outfit.
    * **Hobby:** A specific hobby or behavior principle in English.
    * **Job:** The final adapted job name in English.
      - The "Job" field MUST be a plain role name only.
      - DO NOT add theme words, nicknames, parentheses, quotes, or any decorative suffix/prefix.
      - Examples: "Tutor" (OK), "Tutor (Ice Thief)" (NG).
      - If World Mode is Modern-like, output Job exactly as Base Job with no changes.
      - If World Mode is Fantasy/SF, adapt job wording to fit world but keep meaning. No themes.
    * Output JSON ONLY.
    * Output ALL fields in English.
    
    【Output Format (JSON Only)】
    {{
        "Name": "...",
        "Reading": "...",
        "Appearance": "...",
        "Hobby": "...",
        "Job": "..."
    }}
    """
    else:
        # Japanese version (original)
        prompt = f"""
    You are a creative character designer.
    
    【Task】
    Generate a character concept based on the "Chemical Reaction" of two themes and FIXED attributes.
    
    Themes: **『{theme_str}』**
    
    {priority_block}

    {world_rule}
    
    【FIXED ATTRIBUTES (BASE)】
    1. **Base Job:** {base_job} (See Job Adaptation Rule)
    2. **Tone:** {forced_tone} (Her personality matches this)
    3. **Personality:** {forced_pers}
    4. **Body:** {forced_body}, {forced_cup}
    
    【CRITICAL RULES FOR "Appearance"】
    1. **NO LINE BREAKS:** Output the description as a SINGLE continuous paragraph. Do NOT use bullet points. Separators like "、" or " " are allowed.
    2. **NO NUMERIC HEIGHT:** Do NOT write specific numbers like "165cm". Use adjectives like "Tall" (長身), "Petite" (小柄), or "Slender" (スラリとした).
    3. **INTEGRATE BODY & CUP:** You MUST naturally include "{forced_body}" and "{forced_cup}" in the sentence flow.
       - BAD: "体型・{forced_body}。カップ・{forced_cup}。"
       - GOOD: "〜、{forced_body}で柔らかな肢体を持ち、胸元には{forced_cup}が主張している。服装は〜"
    4. **NO REASONING:** Do NOT explain "why" you chose these features. Output the description directly.

    【Output Requirements】
    * **Name:** Character Name (Kanji or Katakana).
    * **Reading:** Reading in Katakana or Hiragana.
    * **Appearance:** Descriptive text. A single paragraph integrating Body Type, Cup Size ({forced_cup}), Hair, and Outfit.
    * **Hobby:** A specific hobby or behavior principle.
    * **Job:** The final adapted job name.
      - The "Job" field MUST be a plain role name only.
      - DO NOT add theme words, nicknames, parentheses, quotes, or any decorative suffix/prefix.
      - Examples: "家庭教師" (OK), "家庭教師（氷の怪盗）" (NG).
      - If World Mode is Modern-like, output Job exactly as Base Job with no changes.
      - If World Mode is Fantasy/SF, adapt job wording to fit world but keep meaning. No themes.
    * Output JSON ONLY.
    * Output ALL fields in Japanese.
    
    【Output Format (JSON Only)】
    {{
        "Name": "...",
        "Reading": "...",
        "Appearance": "...",
        "Hobby": "...",
        "Job": "..."
    }}
    """
    
    try:
        txt = gemini_client.generate_text(prompt)
        # JSONクリーニング
        txt = re.sub(r'```json', '', txt)
        txt = re.sub(r'```', '', txt).strip()
        start = txt.find('{')
        end = txt.rfind('}') + 1
        data = json.loads(txt[start:end])
        
        # 名前とふりがなを結合
        name_kanji = data.get("Name", "名称不明")
        name_reading = data.get("Reading", "")
        # ファンタジー/SFなどで読みがそのままNameの場合もあるので柔軟に
        full_name = f"{name_kanji} ({name_reading})" if name_reading and name_reading != name_kanji else name_kanji
        
        # AIが適応させた職業を取得
        ai_adapted_job = data.get("Job", base_job)

        # Decide final job safely (NO theme mixing)
        if world_mode == "現代":
            final_job = (base_job or "").strip()
        else:
            cand = sanitize_job_text(ai_adapted_job, themes)
            # reject if empty or still contains theme-ish artifacts
            bad = (not cand)
            if not bad:
                for th in themes:
                    if th and th in cand:
                        bad = True
                        break
            if ("（" in cand) or ("）" in cand) or ("(" in cand) or (")" in cand):
                bad = True

            final_job = fallback_adapt_job(base_job, world_mode) if bad else cand

        # 結合データ
        profile_data = {
            "Name": full_name, 
            "Visual Age": str(random.randint(18, 26)),
            "Job": final_job, # Final Safely Decided Job
            "Appearance": data.get("Appearance", "特徴なし"),
            "Personality": forced_pers, # Force Gacha Result
            "Hobby": data.get("Hobby", "特になし"),
            "Tone": forced_tone # Force Gacha Result
        }
        
        # Merge Hidden Traits from Gacha
        profile_data.update(gacha_data)
        # Ensure Name/Age generated by AI (or fallback) are kept over Gacha placeholders
        profile_data["Name"] = full_name
        profile_data["Job"] = final_job 
        
        return theme_str, profile_data

    except Exception as e:
        # エラー時のフォールバックデータ
        # 変数名が間違っていた箇所を修正 (selected_job -> base_job など)
        error_data = {
            "Name": "生成エラー子",
            "Visual Age": "20",
            "Job": base_job if 'base_job' in locals() else "不明",
            "Appearance": "生成に失敗しました（性的コンテンツ規制などの可能性があります）",
            "Personality": forced_pers if 'forced_pers' in locals() else "普通",
            "Hobby": "なし",
            "Tone": forced_tone if 'forced_tone' in locals() else "普通",
            "Error": str(e)
        }
        # エラー時も gacha_data の基本情報は混ぜておく
        if 'gacha_data' in locals():
            error_data.update(gacha_data)

        return theme_str, error_data

# --- 4. 単発ガチャ機能 ---
def generate_attribute_text(attribute_key, gemini_client=None):
    """
    単発ガチャ用。ボタンを押した時に単語を一つ生成する。
    """
    defaults = {
        "Name": ["佐藤 花子", "田中 美咲", "鈴木 愛", "高橋 凛"],
        "Job": ["学生", "OL", "アイドル", "メイド", "スパイ"],
        "Personality": ["ツンデレ", "ヤンデレ", "清楚", "小悪魔"],
        "Body Type": ["スレンダー", "グラマラス", "小柄", "長身"],
        "Appearance": ["黒髪ロング", "金髪ショート", "制服姿", "眼鏡っ娘"],
        "Tone": ["タメ口", "敬語", "お嬢様言葉"],
        "Fetish": ["匂いフェチ", "マゾヒスト", "サディスト"],
        "Hobby": ["カフェ巡り", "読書", "ゲーム", "散歩"]
    }
    
    # 対応するキーがなければ汎用リストを使う
    fallback_list = defaults.get(attribute_key, ["普通"])
    
    if not gemini_client: 
        return random.choice(fallback_list)

    # 単発用プロンプト
    prompt = f"""
    Provide one unique and interesting Japanese word/phrase for anime heroine's "{attribute_key}".
    Output ONLY the word. (e.g. if Name, output "綾波レイ" etc)
    """
    try:
        text = gemini_client.generate_text(prompt).strip().replace('"', '').replace("'", "")
        return text
    except:
        return random.choice(fallback_list)

# --- 5. キャラ検索ロジック ---
def search_character_profile(name, gemini_client, world_detail=""):
    """
    既存キャラ名を元にプロフィールを生成する。
    戻り値: プロフィール辞書 (main.pyのsession_stateとキーを一致させる)
    """
    if not gemini_client:
        return {}

    # AIへの命令を日本語で記述し、自然に日本語出力を促す（強制終了回避）
    prompt = f"""
    あなたはアニメ・ゲームに詳しいキャラクターデータベースです。
    以下のキャラクターを分析し、設定を出力してください。
    
    対象: **『{name}』**

    【重要：世界観ルール（最優先）】
    {world_detail}
    - もし世界観ルール（水着指定や中世設定など）がある場合、
      対象キャラの衣装や職業を、その世界観に合わせて **「再解釈・翻案」** してください。
    - 例: 中世ファンタジーなら「スーツ→ローブ」「銃→杖」に置換。
    - 例: 水着世界なら「制服→水着」に置換。
    
    【指示】
    以下の情報を推測し、JSON形式で出力してください。
    不明な場合はイメージで補完してください。
    
    1. **Name:** フルネーム（読み仮名も分かる範囲で。例: 綾波 レイ (あやなみ れい)）
    2. **Visual Age:** 見た目年齢（数値文字列）
    3. **Job:** 職業や役割
    4. **Appearance:** 外見の特徴（髪型、髪色、服装、体型やスタイルなど具体的・描写的に）
    5. **Personality:** 性格を表すキーワードや短い文章
    6. **Tone:** 口調や話し方の特徴
    7. **Hobby:** 趣味、習慣、または行動原理
    
    【Output Format (JSON Only)】
    {{
        "Name": "...",
        "Visual Age": "...",
        "Job": "...",
        "Appearance": "...",
        "Personality": "...",
        "Tone": "...",
        "Hobby": "..."
    }}
    """
    
    try:
        txt = gemini_client.generate_text(prompt)
        
        # デバッグ用にコンソールに出力してもよいが、ここでは処理に集中
        if not txt:
            raise ValueError("AIからの応答が空でした。")

        # JSON部分を正規表現で強力に抽出
        match = re.search(r'\{.*\}', txt, re.DOTALL)
        if match:
            json_str = match.group(0)
            data = json.loads(json_str)
            return data
        else:
            # JSONが見つからない場合は、テキスト全体を解析しようとせずエラー扱いにする
            raise ValueError("JSON形式が見つかりませんでした。")

    except Exception as e:
        # エラー発生時はクラッシュさせず、エラー情報を入れた辞書を返す
        return {
            "Name": f"{name} (検索失敗)",
            "Visual Age": "??",
            "Job": "データ取得エラー",
            "Appearance": f"エラーが発生しました: {str(e)}",
            "Personality": "不明",
            "Tone": "不明",
            "Hobby": "再試行してください"
        }

# --- 6. 場所判定ロジック (Location System) ---
def classify_location(user_text, gemini_client):
    """
    ユーザー入力から「現在の場所」を判定し、Base_IDとDisplay_nameを返す。
    gemini_client: main.py から渡される GeminiClient インスタンス
    """
    # 定義済みBase_IDリスト
    BASE_LOCATIONS = [
        {"base_id": "01_HOME", "category": "REST", "name": "自宅"},
        {"base_id": "02_NATURE", "category": "REST", "name": "自然・公園"},
        {"base_id": "03_CITY", "category": "SOCIAL", "name": "街中・都市"},
        {"base_id": "04_DINING", "category": "SOCIAL", "name": "飲食店・カフェ"},
        {"base_id": "05_WORK", "category": "SOCIAL", "name": "職場・学校"},
        {"base_id": "06_EVENT", "category": "SOCIAL", "name": "イベント・施設"},
        {"base_id": "07_TRANSIT", "category": "DANGER", "name": "移動中・乗り物"},
        {"base_id": "08_DUNGEON", "category": "DANGER", "name": "危険地帯・ダンジョン"},
        {"base_id": "09_PRIVATE", "category": "EROS", "name": "個室・ホテル"},
        {"base_id": "10_BED", "category": "EROS", "name": "ベッド・寝室"}
    ]

    # デフォルト（判定失敗時）
    fallback = {"base_id": "01_HOME", "category": "REST", "display_name": "", "move": False}

    if not user_text or not gemini_client:
        return fallback

    # LLMへのプロンプト
    prompt = f"""
    Analyze the user's text and classify the current location.
    
    User Text: "{user_text}"
    
    Target Base Locations:
    1. 01_HOME (Rest, Home)
    2. 02_NATURE (Park, Forest, Sea)
    3. 03_CITY (City, Street, Shopping)
    4. 04_DINING (Cafe, Restaurant, Bar)
    5. 05_WORK (School, Office)
    6. 06_EVENT (Event, Gym, Cinema)
    7. 07_TRANSIT (Train, Car, Moving)
    8. 08_DUNGEON (Dangerous Place, Ruins)
    9. 09_PRIVATE (Private Room, Hotel, Karaoke Box)
    10. 10_BED (Bed, Futon, Intimate Space)

    Rules:
    - If the user explicitly suggests sticking to the current place, or no movement is implied, set "move": false.
    - If the user implies going somewhere or being somewhere new, set "move": true and select the best Base_ID.
    - "display_name": The specific location name inferred from the text (e.g., "Living Room", "Starbucks", "Tokyo Station").
      - If no specific name is found, use an empty string "".
      - Output Japanese for display_name.
    
    Output JSON ONLY:
    {{
        "base_id": "...",
        "category": "...",
        "display_name": "...",
        "move": true/false
    }}
    """

    try:
        txt = gemini_client.generate_text(prompt)
        # JSON抽出
        match = re.search(r'\{.*\}', txt, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            # Validate Base_ID
            bid = data.get("base_id", "")
            found = next((x for x in BASE_LOCATIONS if x["base_id"] == bid), None)
            
            if found:
                return {
                    "base_id": found["base_id"],
                    "category": found["category"],
                    "display_name": data.get("display_name", ""),
                    "move": data.get("move", False)
                }
            else:
                return fallback
        else:
            return fallback

    except Exception:
        return fallback