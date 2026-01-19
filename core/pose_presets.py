# core/pose_presets.py

CLOTHING = {
    "default": "",
    "nude": "nude, nipples, pussy, navel, no clothes, uncensored",
    "underwear": "underwear, lingerie, bra, panties",
    "half_dressed": "clothes lift, shirt lift, showing panties, messy clothes, undressing",
    "bikini": "bikini, swimsuit",
}

POSES = {
    # Basic
    "normal": "upper body, standing, looking at viewer",
    "close_up": "close up, face focus, looking at viewer",
    "kiss": "kissing, close up, cheek to cheek, profile, tongue, saliva, side view",
    "hug": "hugging, embrace, body contact, upper body",
    "sleeping": "sleeping, lying in bed, closed eyes, peaceful",
    "undressing": "undressing, holding clothes, half naked, embarrassing, looking at viewer",
    
    # Oral / Service (POV)
    "fellatio": "fellatio, sucking penis, penis in mouth, head bob, saliva trail, looking up, pov, high angle",
    "irrumatio": "irrumatio, deepthroat, skull fucking, penis in mouth, gagging, teary eyes, side view, pov",
    "facesitting": "facesitting, sitting on face, pussy view, thighs, low angle, pov",
    "facesitting_pov": "facesitting, pussy on face, extreme close up, pov, looking up, smothering, thighs, nose hook",
    "paizuri": "paizuri, breast smother, grabbing penis, pov, cleavage, looking down",
    "kunni": "cunnilingus, legs spread, pussy focus, looking down, pov, tongue",
    "handjob": "handjob, stroking penis, penis focus, saliva, looking at penis, pov, grip, detailed hands",
    "footjob": "footjob, soles, toes, rubbing penis, penis between feet, pov, looking down, detailed feet",
    "sumata": "sumata, femoral sex, rubbing penis on thighs, penis between thighs, no penetration, pov, looking down, friction",
    "sixty_nine": "69, sixty-nine, simultaneous oral, facesitting, sucking penis, pov, from below, mutual pleasure",

    # Sex (POV)
    "missionary": "sex, vaginal, missionary, lying on back, legs spread, looking at viewer, legs up, pov",
    "doggystyle": "sex, vaginal, doggy style, from side, side view, kneeling, ass focus, bent over, looking back",
    "cowgirl": "sex, vaginal, cowgirl position, straddling, sitting on penis, bouncing breasts, looking at viewer, low angle, pov",
    "mating_press": "sex, vaginal, mating press, legs folded, holding legs, deep penetration, pov",
    "back_standing": "sex, vaginal, standing, from behind, side view, bent over table, grabbing hips, pov",
    "standing_back": "sex, vaginal, standing, from behind, doggy style, bent over, lifting skirt, pov, grabbing waist",
    "wall_sex": "sex, vaginal, pinned against wall, lifting leg, standing, pov, deep penetration, pinning wrists",
    "spooning": "sex, vaginal, side entry, lying on side, hugging from behind, close up",
    "facesitting_sex": "facesitting, sex, reverse cowgirl, sitting on face, pussy view, pov",
    
    # Finish
    "creampie": "creampie, vaginal, leaking cum, after sex, lying, messy, pov",
    "bukkake": "bukkake, cum on face, cum on eyes, closed eyes, messy, close up",
    "facial": "cum on face, tongue out, catching cum, messy",
}

BOTH_POSES = {
    # Basic BOTH (★修正: デフォルトは顔の超ドアップ)
    "sandwich_hug": "2girls, sandwich, extreme close up, face focus, nose touching viewer, kissing viewer, approaching viewer, pov, detailed eyes, blushing, happy",
    
    "sandwich_kiss": "2girls, sandwich, kissing cheek, one kiss one hug, hugging viewer, male in middle, close up, affection",
    "arm_in_arm": "2girls, walking, arm in arm, interlocking arms, looking at viewer",
    "bed_lying": "2girls, lying in bed, sandwich, on back, looking at viewer, sheets, male in middle, pov",
    
    # Service BOTH (POV) - ★新規追加エリア★
    "w_fellatio": "2girls, double fellatio, fellatio, sucking penis, penis in mouth, looking up, saliva, high angle, pov",
    "w_paizuri": "2girls, double paizuri, breast sandwich, breast smother, penis between breasts, cleavage, pov",
    "w_handjob": "2girls, double handjob, stroking penis, saliva trail, looking at penis, detailed hands, pov",
    "w_footjob": "2girls, double footjob, four feet, rubbing penis, soles, toes, pov, looking down",
    "w_sumata": "2girls, double sumata, grinding, penis between thighs, sandwich, friction, pov, looking down",
    "w_facesitting": "2girls, double facesitting, one sitting on face, one sitting on chest, ass smother, pov, looking up",
    "face_chest": "2girls, facesitting, breast smother, pov, looking down, sensory overload",
    "harem_service": "2girls, harem, rubbing bodies, serving, worshiping penis, all over body, pov",
    
    # Sex BOTH
    "threesome_missionary": "2girls, threesome, sex, vaginal, missionary, one girl watching, holding hands, sweat",
    "threesome_doggystyle": "2girls, threesome, sex, vaginal, doggy style, from behind, other girl kissing",
    "double_penetration": "2girls, threesome, double penetration, dp, one front one back, ahegao, messy",
    "sandwich_sex": "2girls, threesome, sex, sandwich, mating press, spitroast (implied)",
    
    # Finish BOTH
    "w_bukkake": "2girls, bukkake, cum on face, cum on body, messy, semen, tongue out",
    "w_creampie": "2girls, creampie, vaginal, leaking cum, messy, lying on bed, exhausted",
}

EXPRESSIONS = {
    "smile": "smile, gentle smile, happy",
    "angry": "angry, furrowed brow, glaring",
    "sad": "sad, tearing up, gloomy",
    "shy": "heavy blush, embarrassed, shy, looking away",
    "aroused": "aroused, heavy breathing, sweaty, open mouth, drooling, heart-shaped pupils",
    "pleasure": "expression of pleasure, ecstasy, closed eyes, open mouth, sweating",
    "ahegao": "ahegao, rolling eyes, tongue out, drooling, brainless",
    "painful": "painful expression, tearing up, frowning, endurance",
    "sadistic": "sadistic smile, smirk, narrowing eyes, looking down on viewer",
    "teasing": "teasing smile, one eye closed, tongue out",
    "yandere": "yandere, empty eyes, dark smile, highlightless eyes",
    "love": "enchanted, affectionate look, gentle smile, blushing",
    "kissing": "closed eyes, passionate face",
}

# ★ポーズごとの最適化NSFWタグ (余計な部位を描画させないため)
POSE_SPECIFIC_NSFW = {
    # 口・奉仕系 (下半身の描写を避ける)
    "fellatio": "nsfw, explicit, penis, glans, saliva, penis in mouth, uncensored",
    "w_fellatio": "nsfw, explicit, penis, glans, saliva, penis in mouth, uncensored",
    "irrumatio": "nsfw, explicit, penis, glans, deepthroat, gagging, uncensored",
    "face_chest": "nsfw, explicit, breasts, nipples, penis, uncensored",
    "facesitting": "nsfw, explicit, pussy, ass, thighs, uncensored",
    "facesitting_pov": "nsfw, explicit, pussy, ass, thighs, uncensored, close up",
    "w_facesitting": "nsfw, explicit, pussy, ass, thighs, uncensored, double facesitting",
    
    # 手・足・素股 (POV強調)
    "handjob": "nsfw, explicit, penis, glans, handjob, uncensored",
    "w_handjob": "nsfw, explicit, penis, glans, handjob, uncensored",
    "footjob": "nsfw, explicit, penis, feet, soles, uncensored",
    "w_footjob": "nsfw, explicit, penis, feet, soles, uncensored, four feet",
    "sumata": "nsfw, explicit, penis, thighs, rubbing, uncensored",
    "w_sumata": "nsfw, explicit, penis, thighs, rubbing, uncensored",
    "sixty_nine": "nsfw, explicit, penis, pussy, oral, uncensored",
    "harem_service": "nsfw, explicit, penis, rubbing, uncensored",

    # 胸系
    "paizuri": "nsfw, explicit, breasts, nipples, penis, glans, cum on breasts, uncensored",
    "w_paizuri": "nsfw, explicit, breasts, nipples, penis, glans, uncensored",
    
    # 挿入系 (マンコ必須)
    "missionary": "nsfw, explicit, pussy, penis, vaginal, uncensored, pubic hair",
    "doggystyle": "nsfw, explicit, pussy, penis, vaginal, ass, uncensored",
    "cowgirl": "nsfw, explicit, pussy, penis, vaginal, nipples, uncensored",
    "mating_press": "nsfw, explicit, pussy, penis, vaginal, uncensored",
    "back_standing": "nsfw, explicit, pussy, penis, vaginal, ass, uncensored",
    "standing_back": "nsfw, explicit, pussy, penis, vaginal, ass, uncensored",
    "wall_sex": "nsfw, explicit, pussy, penis, vaginal, uncensored",
    "spooning": "nsfw, explicit, pussy, penis, vaginal, uncensored",
    "threesome_missionary": "nsfw, explicit, pussy, penis, vaginal, uncensored",
    "threesome_doggystyle": "nsfw, explicit, pussy, penis, vaginal, ass, uncensored",
    "double_penetration": "nsfw, explicit, pussy, penis, vaginal, anus, uncensored",
    "sandwich_sex": "nsfw, explicit, pussy, penis, vaginal, uncensored",
    "facesitting_sex": "nsfw, explicit, pussy, penis, vaginal, ass, uncensored",
    
    # 露出・ソフト系
    "undressing": "nsfw, nipples, panties, underwear, navel",
    "kunni": "nsfw, explicit, pussy, clitoris, saliva, uncensored",
    
    # フィニッシュ
    "creampie": "nsfw, explicit, pussy, semen, leaking cum, uncensored",
    "w_creampie": "nsfw, explicit, pussy, semen, leaking cum, uncensored",
    "bukkake": "nsfw, explicit, semen, cum on face, sticky, messy",
    "w_bukkake": "nsfw, explicit, semen, cum on face, sticky, messy",
    "facial": "nsfw, explicit, semen, cum on face, tongue out",
}

# デフォルトの強力タグ (辞書にない場合に使用)
NSFW_FORCE_TAGS = "nsfw, explicit, uncensored, nipples, pussy, penis, glans, pubic hair, detailed genitals"

# 白濁粘液被覆ver
# Blue Pencil Optimized
EJACULATION_TAGS = "bukkake, semen on face, semen on body, cum on body, sticky semen, detailed semen, aftermath, (shining skin:1.1)"