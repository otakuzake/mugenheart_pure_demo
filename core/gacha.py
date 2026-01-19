import json
import random
import os
import re

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

def load_json(filename):
    path = os.path.join(ASSETS_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return []

def pick_random(data):
    """
    Robust random picker for both List and Dict (with numeric keys) types.
    """
    if isinstance(data, list):
        if not data: return None
        return random.choice(data)
    elif isinstance(data, dict):
        # Filter keys that are strings of integers "1", "2"...
        valid_keys = [k for k in data.keys() if k.isdigit()]
        if not valid_keys: return None
        return data[random.choice(valid_keys)]
    return str(data)

def pick_tone(tones_data):
    """
    Parses complex tones.json structure.
    """
    try:
        # 1. Pick Main Type (1-8)
        main_type_data = pick_random(tones_data)
        if not main_type_data or not isinstance(main_type_data, dict):
            return "標準語"
            
        about_type = main_type_data.get("about-type", "")
        
        # 2. Pick Sub Type (A-E)
        sub_keys = [k for k in main_type_data.keys() if len(k) == 1 and k.isupper()]
        if not sub_keys:
             return about_type
             
        sub_key = random.choice(sub_keys)
        sub_data = main_type_data[sub_key]
        
        type_desc = sub_data.get("type", "")
        features = sub_data.get("Features", [])
        feature_str = "、".join(features) if isinstance(features, list) else str(features)
        
        return f"{about_type} ({type_desc}) - 特徴: {feature_str}"
    except Exception as e:
        print(f"Tone Parsing Error: {e}")
        return "標準語"

def refine_job_name(raw_job):
    """
    Parses job strings like 'Job (Option A / Option B)' and picks one.
    """
    if not isinstance(raw_job, str): return str(raw_job)

    # 1. Extract content inside parentheses
    match = re.search(r'[（\(](.*?)[）\)]', raw_job)
    if match:
        inner_text = match.group(1)
        # Split by delimiters
        options = re.split(r'[・／/]', inner_text)
        # Clean and filter
        options = [opt.strip().replace("など", "") for opt in options if opt.strip()]
        
        if options:
            return random.choice(options)
    
    # 2. If no parentheses but has delimiters (e.g. "Cafe / Waitress")
    if "/" in raw_job or "・" in raw_job:
         options = re.split(r'[・／/]', raw_job)
         clean_opts = [opt.strip().replace("など", "") for opt in options if opt.strip()]
         if clean_opts:
             return random.choice(clean_opts)

    return raw_job

def spin():
    """
    Performs a random gacha spin to generate character data.
    """
    # Load all lists (Enhanced)
    jobs_data = load_json("jobs.json")
    pers_data = load_json("personalities.json")
    tones_data = load_json("tones.json")
    dial_data = load_json("dialects.json")
    # New assets
    vagina_data = load_json("hidden_vaginal_traits.json")
    breast_data = load_json("hidden_breast_traits.json")
    fetish_data = load_json("hidden_fetishes.json")
    
    # Old assets fallback (if needed, though we use new ones primarily)
    bg_data = load_json("body_genitals.json")

    # Spin!
    raw_job = pick_random(jobs_data) or "大学生"
    job = refine_job_name(raw_job)
    personality = pick_random(pers_data) or "普通"
    
    # [Logic: Mix Dialect + Tone]
    dialect = pick_random(dial_data)
    if not dialect or dialect == "なし" or dialect == "None": 
        dialect = "標準語"
        
    base_tone = pick_tone(tones_data)
    mixed_tone = f"{dialect}で、{base_tone}"

    # Body Gacha Fallback (for body_tags mixing if needed, or simple desc)
    body_list = bg_data.get("body", [])
    if not body_list: body_list = [{"desc": "普通", "tags": ""}]
    body = random.choice(body_list)

    # Ensure "breasts" list exists and assign to variable 'breast'
    breasts_list = bg_data.get("breasts", [])
    if breasts_list:
        breast = random.choice(breasts_list)
    else:
        breast = {"desc": "C", "tags": ""}
    
    # Construct Profile
    character_data = {
        "Job": job,
        "Personality": personality,
        "Tone": mixed_tone,
        "Dialect": dialect,
        "Name": "Unknown",
        "Visual Age": str(random.randint(18, 26)),
        
        # New Hidden IDs -> EMPTY (Decided at confirm phase)
        "vagina_id": "",
        "vagina_desc": "",
        "breast_id": "",
        "breast_desc": "",
        
        # Keep compatible keys for display/prompt
        "breast_desc_display": "", # Alias
        "body_desc": body["desc"],
        "body_tags": body["tags"], # Only body tags, breast tags might be inferred from ID later or prompt
        "secret_fetish": "",
        "secret_fetish_desc": "",
        
        # [Aliases for Input Handler]
        "Body": body["desc"],
        "Cup": breast["desc"]
    }
    
    return character_data
