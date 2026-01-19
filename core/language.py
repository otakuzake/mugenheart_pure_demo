import json
import os
import streamlit as st

class LanguageManager:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.lang_data = {}
        self.theme_data = {}
        self.current_lang = "jp"
        self.current_theme = "male_target" # デフォルトは男性向け（美少女）

    def load_data(self, lang="jp", theme="male_target"):
        """言語とテーマを読み込む"""
        self.current_lang = lang
        self.current_theme = theme
        
        # 1. 言語ファイルの読み込み
        lang_path = os.path.join(self.base_dir, "assets", "LANG", f"{lang}.json")
        if os.path.exists(lang_path):
            try:
                with open(lang_path, "r", encoding="utf-8") as f:
                    self.lang_data = json.load(f)
            except Exception as e:
                print(f"Error loading lang file: {e}")
                self.lang_data = {}
        else:
            self.lang_data = {}

        # 2. テーマファイル（性別設定など）の読み込み
        theme_path = os.path.join(self.base_dir, "assets", "THEME", f"{theme}.json")
        if os.path.exists(theme_path):
            try:
                with open(theme_path, "r", encoding="utf-8") as f:
                    self.theme_data = json.load(f)
            except Exception as e:
                print(f"Error loading theme file: {e}")
                self.theme_data = {}
        else:
            self.theme_data = {}

    def get(self, key, default=None):
        """辞書からテキストを取り出す"""
        # データがあればそれを返す。なければキー自体を返す（開発中の確認用）
        val = self.lang_data.get(key)
        if val is None:
            return default if default is not None else f"[{key}]"
        return val

    def get_prompt(self, key):
        """テーマ（性別など）に応じたプロンプト設定を取り出す"""
        return self.theme_data.get(key, "")

# シングルトン管理用
manager = None

def init_manager(base_path):
    global manager
    manager = LanguageManager(base_path)
    return manager
