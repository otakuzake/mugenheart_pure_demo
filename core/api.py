import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# ==========================================
# 🔑 APIキー設定 (Simple & Direct)
# ==========================================
# main.py と同様に secrets から直接取得
if "GEMINI_API_KEY" in st.secrets:
    API_KEY = st.secrets["GEMINI_API_KEY"]
else:
    API_KEY = None
    print("【Error】secrets.toml に GEMINI_API_KEY がありません。")

# ==========================================
# 🤖 モデル設定 (Stable Version)
# ==========================================
# 最新モデルではなく、安定して動作する標準モデルを使用
MODEL_NAME = "models/gemini-3-flash-preview"

def completion(messages):
    """
    Gemini APIへリクエスト送信 (gemini-pro / Simple Text Mode)
    """
    if not API_KEY:
        return "Error: API Key (GEMINI_API_KEY) not found in secrets.toml"

    # API設定
    genai.configure(api_key=API_KEY)

    # 1. メッセージの単純結合 (Empty/Roleエラー回避のための最強策)
    # システム指示とユーザー指示を区別せず、一本のテキストにします
    full_text_parts = []
    
    # デフォルトのシステム指示
    system_instruction = "あなたは役に立つAIアシスタントです。"
    
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        
        if role == "system":
            system_instruction = content
        elif role == "user":
            if content and str(content).strip():
                full_text_parts.append(str(content))

    # ユーザー指示の結合
    user_text = "\n\n".join(full_text_parts)

    # 空っぽ対策
    if not user_text.strip():
        user_text = "（指示に従い設定を出力してください）"

    # プロンプト完成形
    final_prompt = f"【システム指示】\n{system_instruction}\n\n【ユーザー入力】\n{user_text}"

    # 2. 安全フィルター全解除 (Block None)
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: 4,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: 4,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: 4,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: 4,
    }

    # 3. 生成実行
    try:
        model = genai.GenerativeModel(
            MODEL_NAME,
            safety_settings=safety_settings
        )
        
        response = model.generate_content(final_prompt)
        return response.text

    except Exception as e:
        error_msg = str(e)
        print(f"【Gemini API Error】: {error_msg}")
        return f"Error: {error_msg}"
