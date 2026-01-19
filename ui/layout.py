import streamlit as st
from PIL import Image
import io
import time
from . import components
from core import game, llm, comfy

def handle_input(display_text, prompt_text=None):
    if not prompt_text: prompt_text = display_text
    
    # Append User Message
    st.session_state.chat_history.append({"role": "user", "parts": [display_text]})
    
    # Construct System Prompt with current state
    h = st.session_state.heroine
    sys = game.construct_system_prompt(
        h, 
        st.session_state.heroine['love'], 
        st.session_state.heroine['lust'], 
        st.session_state.heroine['reason'],
        st.session_state.get('is_skill_active', False), 
        st.session_state.get('active_skill_data', None)
    )
    st.session_state.system_prompt = sys # Update displayed prompt if needed

    # Generate Response
    with st.spinner("Heroine is thinking..."):
         # We need to pass the history. The history in session state is [{"role":..., "parts":...}]
         # Core LLM wrapper expects this format
         full_response = llm.get_chat_response(st.session_state.chat_history, sys)
    
    # Process Response (Emotion parsing)
    if full_response:
        import re
        try:
            if game.update_status_from_emotions(st.session_state.heroine, full_response):
                st.toast("Status Updated!", icon="✅")
            else:
                 pass # No emotion tags, that's fine
        except Exception as e:
            st.toast("Warning: Parse Failed", icon="⚠️")
            print(e)
            
        st.session_state.chat_history.append({"role": "model", "parts": [full_response]})
        time.sleep(0.5)
        st.rerun()

def render_layout():
    col_left, col_center, col_right = st.columns([1, 2, 1])
    
    # ==========================
    # LEFT COLUMN
    # ==========================
    with col_left:
        if st.button("New Game 🔄", use_container_width=True):
            with st.spinner("運命の相手を探しています..."):
                h = llm.generate_heroine()
                st.session_state.heroine = h
                
                # Backstory & Stats
                bg_data = llm.generate_backstory_and_stats(h)
                h['backstory'] = bg_data['text']
                h['love'] = bg_data['stats']['love']
                h['lust'] = bg_data['stats']['lust']
                h['reason'] = bg_data['stats']['reason']
                h['location'] = bg_data.get('location', '街中')
                h['bg_tag'] = bg_data.get('bg_tag', 'city street')
                
                # Initial Prompt & Image System
                st.session_state.generated_prompt = game.generate_image_prompt(h)
                st.session_state.chat_history = []
                st.session_state.current_image_bytes = None
                
                # Initial system prompt construction
                st.session_state.system_prompt = game.construct_system_prompt(
                    h, h['love'], h['lust'], h['reason']
                )
            st.rerun()
            
        h = st.session_state.get('heroine')
        components.render_profile_card(h)
        
        if h:
            st.markdown("---")
            st.caption("🔮 装備スキル選択")
            skill_keys = list(game.SKILL_DEFINITIONS.keys())
            selected_skill_label = st.selectbox(
                "Select Skill", skill_keys, label_visibility="collapsed", key="skill_selector"
            )
            
            if selected_skill_label == "✨ 自由記述":
                custom_text = st.text_input("スキル効果を入力", value="常識改変：露出狂が常識の世界", key="custom_skill_input")
                st.session_state.active_skill_name = "特殊スキル"
                st.session_state.active_skill_effect = custom_text
            else:
                st.session_state.active_skill_name = selected_skill_label.replace("✨ ", "").replace("⏱️ ", "").replace("😈 ", "").replace("🍄 ", "")
                st.session_state.active_skill_effect = game.SKILL_DEFINITIONS[selected_skill_label] # dict or string

            st.caption("🎨 Current Prompt")
            st.code(st.session_state.get('generated_prompt', ''), language="text")

    # ==========================
    # CENTER COLUMN
    # ==========================
    with col_center:
        history = st.session_state.get('chat_history', [])
        components.render_chat_window(history)
        
        if st.session_state.get('heroine'):
            c1, c2, c3 = st.columns(3)
            
            # Button A: Love
            if c1.button("A: 優しく", use_container_width=True):
                with st.spinner("Action Generating..."):
                    action_desc = llm.generate_player_action("優しく甘いアプローチ")
                    prompt = action_desc + "\n\n【システム指示: プレイヤーのこの行動に対し、ヒロインとしての反応（セリフと感情タグ）を出力してください。好感度(Love)が上がりやすい行動です。】"
                    handle_input(action_desc, prompt)
            
            # Button B: Lust
            if c2.button("B: 攻める", use_container_width=True):
                 with st.spinner("Action Generating..."):
                    action_desc = llm.generate_player_action("強引な性的アプローチ")
                    prompt = action_desc + "\n\n【システム指示: プレイヤーのこの行動に対し、ヒロインとしての反応を出力してください。興奮度(Lust)を上げ、理性(Reason)を下げる行動です。ただし性癖に合わない場合は拒絶しても構いません。】"
                    handle_input(action_desc, prompt)
            
            # Button C: Skill
            if st.session_state.get('is_skill_active', False):
                if c3.button("C: スキル解除 (Release)", use_container_width=True, type="primary"):
                     data = st.session_state.active_skill_data
                     instruction = f"""
                     【システム指示: プレイヤーはスキルを解除しました！】
                     以下の描写を行ってください：
                     {data.get('end', '効果が解除される。')}
                     """
                     st.session_state.is_skill_active = False
                     st.session_state.active_skill_data = {}
                     handle_input("【スキル解除】", instruction)
            else:
                if c3.button("C: スキル発動 (Activate)", use_container_width=True):
                    # Prepare Skill Data
                    if st.session_state.get("active_skill_name") == "特殊スキル":
                         custom_text = st.session_state.get("active_skill_effect", "自由設定")
                         current_skill_data = {
                            "start": f"スキル『{custom_text}』が発動する。",
                            "during": f"【状態: {custom_text}】この設定に従い続けること。",
                            "end": "スキルを解除する。"
                        }
                    else:
                         # active_skill_effect should be the dictionary from definition
                         current_skill_data = st.session_state.get('active_skill_effect')
                         # fallback just in case
                         if not isinstance(current_skill_data, dict):
                             current_skill_data = game.SKILL_DEFINITIONS["⏱️ 時間停止"]

                    st.session_state.active_skill_data = current_skill_data
                    st.session_state.is_skill_active = True
                    
                    instruction = f"""
                    【システム指示: プレイヤーはスキルを発動しました！】
                    以下の描写を行ってください：
                    {current_skill_data['start']}
                    """
                    key = st.session_state.get("skill_selector", "特殊")
                    handle_input(f"【スキル発動: {key}】", instruction)

            if val := st.chat_input("メッセージ..."):
                handle_input(val)

    # ==========================
    # RIGHT COLUMN
    # ==========================
    with col_right:
        if st.session_state.get('current_image_bytes'):
            try:
                image = Image.open(io.BytesIO(st.session_state.current_image_bytes))
                st.image(image, caption="Real-time Render", use_container_width=True)
            except:
                 st.image("defogirl.webp", caption="Render Error", use_container_width=True)
        elif st.session_state.get('heroine'):
             # Try fallback image
             try:
                 st.image("defogirl.webp", caption="Waiting for Render...", use_container_width=True)
             except:
                 st.write("Waiting for Render...")
        else:
            st.empty()
        
        st.markdown("---")
        # 体験版モード: 画像生成ボタンを無効化
        from config import IS_DEMO_MODE
        if IS_DEMO_MODE:
            st.button("📸 今の画面を見る (体験版では利用できません)", type="primary", use_container_width=True, disabled=True, help="体験版では画像生成機能は利用できません")
        else:
            if st.button("📸 今の画面を見る (Generate)", type="primary", use_container_width=True):
                with st.spinner("Rendering Current Scene..."):
                    h = st.session_state.heroine
                    new_p = llm.generate_pov_prompt(h, st.session_state.chat_history)
                    st.session_state.generated_prompt = new_p
                    
                    # Call Comfy Logic
                    img_bytes = comfy.generate_image(new_p)
                    if img_bytes:
                        st.session_state.current_image_bytes = img_bytes
                    else:
                        st.toast("Image Generation Failed", icon="❌")
                    st.rerun()
