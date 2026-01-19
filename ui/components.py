import streamlit as st
import re
from PIL import Image
import os
import io
import base64
from core.language import init_manager

# Color Presets for Character Cards
MAIN_COLORS = {
    "bg": "#2a203a",  # plum
    "border": "#ff9800", # Unified to Orange (Same as Sub)
    "bar_grad": "linear-gradient(90deg, rgba(255,90,150,0.95), rgba(120,160,255,0.95))"
}

SUB_COLORS = {
    "bg": "#2a203a",  # same as main (dark plum)
    "border": "#ff9800", # Orange
    "bar_grad": "linear-gradient(90deg, rgba(255,152,0,0.95), rgba(255,193,7,0.95))"
}

def inject_custom_css():
    # --- Dynamic Background Image ---
    bg_style = ""
    # bg_path = os.path.join("assets", "ui", "hearttile.png")
    # if os.path.exists(bg_path):
    #     with open(bg_path, "rb") as f:
    #         b64 = base64.b64encode(f.read()).decode()
    #         bg_style = f"""
    #         <style>
    #         body, .stApp {{
    #             background-image: url("data:image/png;base64,{b64}") !important;
    #             background-repeat: repeat !important;
    #             background-position: top left !important;
    #             background-size: 64px !important;
    #         }}
    #         </style>
    #         """
    
    if bg_style:
        st.markdown(bg_style, unsafe_allow_html=True)

    # --- Title Screen (Game-Like) ---
    title_css = """
    <style>
    .title-bg {
      min-height: 100vh;
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 14px 0;
      background-image: url("assets/ui/top.png");
      background-size: cover;
      background-position: center;
      background-repeat: no-repeat;
    }

    .title-panel {
      width: min(760px, 92vw);
      background: rgba(20, 20, 24, 0.68);
      border: 1px solid rgba(255,255,255,0.14);
      border-radius: 18px;
      box-shadow: 0 18px 48px rgba(0,0,0,0.35);
      padding: 18px;
      backdrop-filter: blur(10px);
    }
    </style>
    """
    st.markdown(title_css, unsafe_allow_html=True)

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=M+PLUS+Rounded+1c:wght@400;500;700&display=swap');
    
    body, .stApp {
        font-family: 'M PLUS Rounded 1c', sans-serif !important;
        font-weight: 500 !important;
        color: #444444 !important;
        background: linear-gradient(180deg, #fff6fb 0%, #f4f2ff 45%, #eef6ff 100%) !important;
        overflow: hidden !important;
        /* padding-top handled by global block below */
    }

    /* ===== Global top spacing control ===== */
    html, body {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }

    .stApp {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }

    /* Streamlit main container - High Specificity to override local injects */
    body .stApp div.block-container {
        padding-top: 10px !important;
        margin-top: 0 !important;
    }

    /* Prevent extra spacing from sections */
    section.main, section.main > div {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }

    /* --- Strict Header / Toolbar Hide --- */
    header { display: none !important; }
    [data-testid="stHeader"] { display: none !important; }
    [data-testid="stToolbar"] { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    footer { visibility: hidden !important; }

    .chat-window {
        height: 70vh;
        overflow-y: auto;
        background-color: #94bce4;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .narrative {
        align-self: center;
        text-align: center;
        color: #ffffff !important;
        font-size: 0.95rem;
        background-color: rgba(0,0,0,0.1);
        padding: 8px 15px;
        border-radius: 12px;
        margin: 6px auto;
        width: 90%;
        line-height: 1.5;
    }
    .narrative em {
        font-style: italic;
        font-weight: bold;
        margin: 0 4px;
    }
    .bubble-container {
        display: flex;
        margin-bottom: 10px;
        align-items: flex-start;
    }
    .heroine-row {
        flex-direction: row;
    }
    .user-row {
        flex-direction: row-reverse;
    }
    .chat-bubble {
        padding: 10px 14px;
        border-radius: 15px;
        font-size: 0.95em;
        position: relative;
        max-width: 70%;
        line-height: 1.5;
        box-shadow: 0 1px 1px rgba(0,0,0,0.1);
    }
    .heroine-bubble {
        background-color: #ffffff;
        color: #333333;
        border-top-left-radius: 2px;
        margin-left: 8px;
    }
    .heroine-bubble::before {
        content: "◀";
        position: absolute;
        left: -10px;
        top: 10px;
        color: #ffffff;
        font-size: 12px;
    }
    .user-bubble {
        background-color: #ffccd5;
        color: #333333;
        border-top-right-radius: 2px;
        margin-right: 8px;
    }
    .user-bubble::before {
        content: "▶";
        position: absolute;
        right: -10px;
        top: 10px;
        color: #ffccd5;
        font-size: 12px;
    }
    .monologue-bubble {
        background-color: transparent;
        border: 2px solid #ffccd5;
        color: #555;
        border-radius: 15px;
        padding: 8px 12px;
        font-size: 0.9em;
        margin-right: 8px;
        max-width: 70%;
    }
    .heroine-icon {
        font-size: 24px;
        margin-top: -5px;
    }
    [data-testid="stTextInput"] input {
        background-color: #ffffff !important;
        color: #333333 !important;
        border: 2px solid #ffccd5 !important;
        border-radius: 8px;
    }
    [data-testid="stTextInput"] label {
        display: None;
    }
    .profile-card {
        background: #ffffff;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #ffc1e3;
        font-size: 0.9em;
        margin-bottom: 10px;
        color: #444;
    }
    div.stButton > button {
        background-color: #ffffff;
        border: 1px solid #ffccd5;
        color: #e91e63;
    }
    div.stButton > button:hover {
        border-color: #e91e63;
        color: #e91e63;
    }
    
    /* --- Speaker Pills --- */
    .speaker-pill {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 800;
        margin: 0 0 4px 6px; /* Just above bubble */
        border: 1px solid rgba(0,0,0,0.08);
        background: rgba(255,255,255,0.75);
        color: #333;
        white-space: nowrap;
    }
    .speaker-main { background: rgba(255,180,210,0.55); }
    .speaker-sub  { 
        background: rgba(255, 190, 120, 0.70);
        border-color: rgba(255, 150, 60, 0.55);
        color: #333;
    }
    .speaker-third { background: rgba(205,180,255,0.60); }
    
    /* --- Compact UI Spacing --- */
    .chat-window { margin-bottom: 4px !important; }
    div.stButton { margin-top: 0px !important; margin-bottom: 0px !important; }
    div[data-testid="stChatInput"] { margin-top: 4px !important; }
    
    /* --- Tight Prompt Display --- */
    .stCodeBlock { margin-top: 2px !important; }
    [data-testid="stCaptionContainer"] { margin-top: 4px !important; margin-bottom: 0px !important; }

    /* --- Subtle Edit Buttons (Strict Override) --- */
    .edit-btn-row div.stButton > button {
      background: rgba(255,255,255,0.55) !important;
      border: 1px solid rgba(0,0,0,0.08) !important;
      color: rgba(0,0,0,0.55) !important;
      border-radius: 12px !important;
      box-shadow: none !important;

      /* Fixed Sizing */
      width: 100% !important;
      min-width: 0 !important;
      height: 38px !important;
      padding: 0 !important;
      font-size: 12px !important;
      font-weight: 800 !important;
      letter-spacing: 0.08em !important;

      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
    }

    .edit-btn-row div.stButton > button:hover {
      background: rgba(255,255,255,0.75) !important;
      border-color: rgba(233, 30, 99, 0.18) !important;
      color: rgba(233, 30, 99, 0.65) !important;
    }

    .edit-btn-row div.stButton > button:disabled,
    .edit-btn-row div.stButton > button[disabled] {
      background: rgba(255,255,255,0.25) !important;
      border-color: rgba(0,0,0,0.06) !important;
      color: rgba(0,0,0,0.25) !important;
      opacity: 1 !important;
      filter: none !important;
      filter: none !important;
    }

    /* --- Title Screen (Game-Like) --- */
    .title-bg {
      min-height: 100vh;
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 14px 0;
      /* background-image set dynamically below */
      background-size: cover;
      background-position: center;
      background-repeat: no-repeat;
    }

    .title-panel {
      width: min(720px, 92vw);
      background: rgba(20, 20, 24, 0.68);
      border: 1px solid rgba(255,255,255,0.14);
      border-radius: 18px;
      box-shadow: 0 18px 48px rgba(0,0,0,0.35);
      padding: 18px 18px 16px 18px;
      backdrop-filter: blur(10px);
    }

    .title-panel h1, .title-panel h2, .title-panel h3,
    .title-panel label, .title-panel p, .title-panel span, .title-panel div {
      color: rgba(255,255,255,0.92) !important;
    }

    /* --- Global UI Refinements --- */
    .block-container {
      /* padding-top: 10px !important;  <-- Handled by global block */
      padding-bottom: 2rem !important;
      max-width: 95% !important;
    }
    
    /* Header Hide (Production Mode) */
    header { 
      visibility: hidden !important; 
      height: 0 !important;
    }
    [data-testid="stToolbar"] { 
      display: none !important; 
    }
    
    /* Scoped "Candy" Buttons */
    .action-btns div.stButton > button {
      background: linear-gradient(to bottom, #ffe6fa, #ffcce6) !important;
      border: 2px solid #ffb3d9 !important;
      border-radius: 20px !important;
      color: #d63384 !important;
      font-weight: 800 !important;
      box-shadow: 0 4px 6px rgba(255, 182, 193, 0.4) !important;
      transition: all 0.2s ease !important;
    }
    .action-btns div.stButton > button:hover {
      transform: translateY(-2px) !important;
      box-shadow: 0 6px 8px rgba(255, 182, 193, 0.6) !important;
      background: linear-gradient(to bottom, #fff0fb, #ffd9ef) !important;
    }

    /* Cute Input Fields */
    [data-testid="stTextInput"] input {
      border-radius: 15px !important;
      border: 2px solid #FECFEF !important;
      background-color: rgba(255, 255, 255, 0.9) !important;
    }
    [data-testid="stTextInput"] input:focus {
      border-color: #FF9A9E !important;
      box-shadow: 0 0 5px rgba(255, 154, 158, 0.5) !important;
      outline: none !important;
    }

    /* Pink Scrollbar */
    ::-webkit-scrollbar {
      width: 10px;
      height: 10px;
    }
    ::-webkit-scrollbar-track {
      background: #fff0f5; 
    }
    ::-webkit-scrollbar-thumb {
      background: #ffb3c1; 
      border-radius: 5px;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: #ff8fa3; 
    }


    
    </style>
    """, unsafe_allow_html=True)

def display_chat(history, heroine_icon="👩"):
    chat_html = '<div class="chat-window">'
    for msg in history:
        text = msg.get('display_text', msg['parts'][0])
        display_text = re.sub(r"<emo>.*?</emo>", "", text, flags=re.DOTALL)
        display_text = re.sub(r"(?m)^\s*[【\[].*?[】\]]\s*\d+.*$", "", display_text)
        display_text = re.sub(r"(?m)^(❤️|😈|🧠|好感度|興奮度|理性).*?$", "", display_text)
        display_text = re.sub(r"「\s*(\*\*.*?\*\*)\s*」", r"\1", display_text)

        if not display_text.strip(): continue
        
        if msg['role'] == 'user':
            clean = display_text.strip("()（）")
            if display_text.strip().startswith("(") or display_text.strip().startswith("（"):
                chat_html += f'<div class="bubble-container user-row"><div class="monologue-bubble">{clean}</div></div>'
            else:
                clean = display_text.strip("「").strip("」")
                chat_html += f'<div class="bubble-container user-row"><div class="chat-bubble user-bubble">{clean}</div></div>'
        else:
            lines = display_text.split('\n')
            for line in lines:
                p = line.strip()
                if not p: continue
                
                # Check for bubble vs narrative
                # パターン1: 「セリフ」のみ
                # パターン2: 名前「セリフ」（例: 長澤柚希「セリフ」）
                dialogue_match = False
                speaker_name_from_text = None
                dialogue_text = None
                
                # パターン2を先にチェック（名前「セリフ」）
                name_dialogue_match = re.match(r'^(.+?)「([^」]+)」$', p)
                if name_dialogue_match:
                    speaker_name_from_text = name_dialogue_match.group(1).strip()
                    dialogue_text = name_dialogue_match.group(2)
                    dialogue_match = True
                # パターン1をチェック（「セリフ」のみ）
                elif re.fullmatch(r"「[^」]+」", p) and not re.match(r"「[（(『]", p):
                    dialogue_text = p.strip("「」")
                    dialogue_match = True
                
                if dialogue_match:
                    clean = dialogue_text if dialogue_text else p.strip("「」")
                    clean = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', clean)
                    clean = clean.replace('\n', '<br>')
                    
                    # --- Speaker Pill Logic ---
                    spk = msg.get("speaker", "")
                    # テキストから抽出した名前があればそれを使用
                    display_speaker_name = speaker_name_from_text or msg.get("speaker_name", "")
                    pill = ""
                    if spk in ("main", "sub", "third") or speaker_name_from_text:
                        if not spk and speaker_name_from_text:
                            # テキストから抽出した名前の場合、mainとして扱う
                            spk = "main"
                        cls = "speaker-main" if spk=="main" else ("speaker-sub" if spk=="sub" else "speaker-third")
                        nm = display_speaker_name or ("メイン" if spk=="main" else ("サブ" if spk=="sub" else "???"))
                        pill = f"<div class='speaker-pill {cls}'>{nm}</div>"
                    
                    chat_html += f"<div class='bubble-container heroine-row'><div>{pill}<div class='chat-bubble heroine-bubble'>{clean}</div></div></div>"
                else:
                    narrative = p
                    narrative = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', narrative)
                    narrative = re.sub(r'\*(.+?)\*', r'<em>\1</em>', narrative)
                    narrative = re.sub(r'[”"]', '', narrative)
                    narrative = narrative.replace('\n', '<br>')
                    chat_html += f'<div class="narrative">{narrative}</div>'
    
    
    chat_html += '</div>'
    st.markdown(chat_html, unsafe_allow_html=True)

# --- New UI components for Left Column V2 ---

def crop_bust_shot(image_path: str, top_ratio: float = 0.0, bottom_ratio: float = 0.55):
    try:
        if not image_path or not os.path.exists(image_path):
            return None
        img = Image.open(image_path).convert("RGB")
        w, h = img.size
        top = int(h * top_ratio)
        bottom = int(h * bottom_ratio)
        bottom = max(bottom, top + 1)
        cropped = img.crop((0, top, w, bottom))
        return cropped
    except Exception:
        return None



def render_character_card(h, colors, is_active=False, show_debug=False):
    if h is None:
        return

    name = getattr(h, "name", "")
    age = getattr(h, "age", "")
    job = getattr(h, "job", "")

    bond = getattr(h, "bond_level", 0)
    try:
        bond = int(bond)
    except Exception:
        bond = 0

    love = max(0, min(int(getattr(h, "love", 0)), 100))
    lust = max(0, min(int(getattr(h, "lust", 0)), 100))
    reason = max(0, min(int(getattr(h, "reason", 0)), 100))
    possession = getattr(h, "possession", 30)
    possession = max(0, min(int(possession if possession else 30), 100))
    
    chastity = getattr(h, "chastity", 50)
    chastity = max(0, min(int(chastity if chastity is not None else 50), 100))

    # Color Variables
    CARD_BG = colors["bg"]

    # Active/Inactive共通: サブと同じ見た目に完全統一（発光・強調なし）
    CARD_BORDER = f"1px solid {colors['border']}"
    BOX_SHADOW = "0 10px 28px rgba(0,0,0,0.35)"

    INNER_BORDER = colors["border"] # Header internal border stays theme color
    BAR_GRAD = colors["bar_grad"]
    TEXT_MAIN = "#ffffff"
    TEXT_SUB = "rgba(255,255,255,0.85)"

    # Top5 (Real Data or Monitoring)
    show_monitoring = False
    if hasattr(h, "emotions_top5") and isinstance(h.emotions_top5, list) and h.emotions_top5:
        chips = h.emotions_top5
    else:
        show_monitoring = True
        chips = []

    # 言語設定を取得
    current_lang = st.session_state.get("language", "jp")
    lang_mgr = init_manager(".")
    lang_mgr.load_data(current_lang, "male_target")
    
    if show_monitoring:
        monitoring_text = lang_mgr.get("text_0161", "脳内モニタ計測中…")
        chip_html = f"<div style='font-size:12px;opacity:0.6;font-style:italic;margin-top:6px;color:{TEXT_SUB};'>{monitoring_text}</div>"
    else:
        chip_html = "".join([
            f"<span style='display:inline-block;padding:6px 10px;margin:6px 8px 0 0;"
            f"background:rgba(255,255,255,0.10);border:1px solid rgba(255,255,255,0.14);"
            f"border-radius:999px;font-size:12px;color:rgba(255,255,255,0.88);'>{k}:{v}%</span>"
            for k,v in chips
        ])

    # HTMLをインデントなしで構築してMarkdownのコードブロック化を防ぐ
    def bar_row(label, v):
        return f'<div style="display:flex;align-items:center;gap:10px;margin:10px 0;">' \
               f'<div style="width:92px;font-size:13px;color:{TEXT_SUB};white-space:nowrap;">{label}</div>' \
               f'<div style="flex:1;height:10px;background:rgba(255,255,255,0.14);border-radius:999px;overflow:hidden;">' \
               f'<div style="height:10px;width:{v}%;background:{BAR_GRAD};border-radius:999px;"></div>' \
               f'</div>' \
               f'<div style="width:40px;text-align:right;font-size:12px;color:rgba(255,255,255,0.55);">{v}%</div>' \
               f'</div>'

    # 体験版バッジの追加（多言語対応）
    from config import IS_DEMO_MODE
    demo_badge_text = lang_mgr.get("text_0182", "体験版")
    demo_badge = f'<span style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: bold; margin-left: 8px;">{demo_badge_text}</span>' if IS_DEMO_MODE else ''
    
    # 体験版: 名前の読み方を追加（長澤柚希の場合、日本語のみ）
    from config import IS_DEMO_MODE
    name_display = name
    if IS_DEMO_MODE and name == "長澤 柚希" and current_lang == "jp":
        name_display = f"{name}（{lang_mgr.get('text_0183', 'ながさわ ゆずき')}）"
    
    # ★修正ポイント: class="hero-card" と class="hero-header" を追加
    html = f'<div class="hero-card" style="background:{CARD_BG};border:{CARD_BORDER};border-radius:16px;padding:14px;box-shadow:{BOX_SHADOW};">' \
           f'<div class="hero-header" style="background:transparent;border:2px solid {INNER_BORDER};border-radius:12px;padding:10px 12px;margin-bottom:12px;">' \
           f'<div style="font-size:22px;font-weight:900;color:{TEXT_MAIN};">{name_display}{demo_badge}</div>' \
           f'<div style="font-size:12px;color:{TEXT_SUB};margin-top:4px;">{age} / {job}</div>'
            
    # [INSERTED] Relationship Status Badge
    rel_status = getattr(h, "relation_status", None)
    
    # ★修正: AIが生成した称号（relation_title）があれば、表示テキストをそれに差し替える
    display_title = rel_status
    if hasattr(h, "relation_title") and h.relation_title:
        display_title = h.relation_title

    rel_badge = ""
    if rel_status:
        # 背景色などは「rel_status」で判定（今回は固定）だが、表示は「display_title」を使う
        rel_badge = f"""<span style='
            background: linear-gradient(135deg, #ffd700 0%, #fdb931 100%);
            color: #5c4033;
            border: 1px solid #fff;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: 800;
            margin-left: 8px;
            vertical-align: middle;
            display: inline-block;
            text-shadow: none;
        '>✨ {display_title}</span>"""

    # ステータスラベルの多言語対応
    kizuna_label = lang_mgr.get("text_0154", "キズナ Lv.")
    affection_label = lang_mgr.get("text_0155", "好感度")
    excitement_label = lang_mgr.get("text_0156", "興奮度")
    possession_label = lang_mgr.get("text_0157", "独占欲")
    reason_label = lang_mgr.get("text_0158", "理性")
    guard_label = lang_mgr.get("text_0159", "ガード")
    monitor_label = lang_mgr.get("text_0160", "脳内モニタ（Top 5）")
    
    html += f'<div style="margin-top:6px;margin-bottom:8px;display:flex;align-items:center;gap:6px;font-size:13px;font-weight:800;color:#f5c542;text-shadow:0 1px 2px rgba(0,0,0,0.35);">💛 {kizuna_label}{bond}{rel_badge}</div>' \
            f'</div>' \
           f'{bar_row(f"❤️ {affection_label}", love)}' \
           f'{bar_row(f"😈 {excitement_label}", lust)}' \
           f'{bar_row(f"💘 {possession_label}", possession)}' \
           f'{bar_row(f"🧊 {reason_label}", reason)}' \
           f'{bar_row(f"🛡️ {guard_label}", chastity)}' \
           f'<div style="margin-top:12px;border-top:1px solid rgba(255,255,255,0.10);padding-top:12px;">' \
           f'<div style="font-size:14px;font-weight:800;color:{TEXT_SUB};margin-bottom:6px;">{monitor_label}</div>' \
           f'{chip_html}' \
           f'</div>' \
           f'</div>'

    st.markdown(html, unsafe_allow_html=True)

    # ---------------------------------------------------------
    # 🛠️ 開発者用データ (Developer Data)
    # ---------------------------------------------------------
    if show_debug:
        with st.expander("🛠️ 開発者用データ", expanded=False):
            # 1. 隠し性癖
            sf_name = getattr(h, "secret_fetish", "なし")
            sf_desc = getattr(h, "secret_fetish_desc", "ー")
            
            st.markdown("**隠し性癖**")
            st.caption(f"種類: {sf_name}")
            st.caption(f"説明: {sf_desc}")

            st.markdown("---")

            # 2. 乳首形状
            b_desc = getattr(h, "breast_desc", "不明")
            st.markdown("**乳首形状**")
            st.caption(f"{b_desc}")

            st.markdown("---")

            # 3. 膣形状
            v_desc = getattr(h, "vagina_desc", "不明")
            v_note = getattr(h, "vagina_note", "ー")
            
            st.markdown("**膣形状**")
            st.caption(f"種類: {v_desc}")
            st.caption(f"説明: {v_note}")
