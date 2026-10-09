# =====================================================================
#  Instagram Reels Agent — SETTINGS (sirf yahi file badalni hai)
#  Secrets (token, API keys) yahan NAHI likhne — GitHub Secrets mein daalo.
# =====================================================================

# ---------------------------------------------------------------------
# 1) POSTING SCHEDULE
# ---------------------------------------------------------------------
TIMEZONE = "Asia/Kolkata"
POSTS_PER_DAY = 10            # roz kitni reels (Instagram API limit: 24 ghante mein 50)
DAY_START = "05:30"           # pehli reel lagbhag is time
DAY_END = "22:30"             # aakhri reel lagbhag is time
JITTER_MINUTES = 12           # har slot ko ±12 min aage-peeche (robot jaisa fix time na lage)
MAX_LATE_MINUTES = 120        # koi slot isse zyada late ho gaya to skip (ek saath dher na lage)
CAMPAIGN_END = ""             # "2026-11-10" likho to us din ke baad posting band. "" = kabhi band nahi
PAUSED = True                 # ⚠ Setup + test ke baad False karo = GO LIVE. (True = automatic posting band)

# ---------------------------------------------------------------------
# 2) REEL VIDEO
# ---------------------------------------------------------------------
REEL_SECONDS = 30             # 15 se 90 ke beech (API 90 sec se lambi reel nahi leta)
MANTRA_ART_SHARE = 0.10       # 10% reels bina photo ke (ghoomta mandala + ॐ) — variety ke liye
BOTTOM_LINES = [              # neeche wali chhoti line (rotate hoti hai). {jaikara} = bhagwan ka jaikara
    "रोज़ भक्ति के लिए फ़ॉलो करें",
    "पूरा भजन सुनने के लिए ऑडियो पर टैप करें",
    "कमेंट में लिखें — {jaikara}",
    "अपनों को भेजें, सबका दिन मंगलमय हो",
]

# ---------------------------------------------------------------------
# 3) LOGIN + GAANA (AUDIO)
# ---------------------------------------------------------------------
# LOGIN_TYPE:
#   "instagram" = Instagram Login — Facebook account/Page ki zarurat NAHI  (tumhare liye abhi yahi)
#   "facebook"  = Facebook Login — Instagram FB Page se juda ho tab; library gaana sirf isi mein lagta hai
LOGIN_TYPE = "instagram"
# AUDIO_MODE:
#   "mp3"     = music/ folder ki MP3 ka sabse jandaar 30 sec hissa video mein judta hai
#   "library" = Instagram music library se official gaana attach (sirf LOGIN_TYPE = "facebook")
AUDIO_MODE = "mp3"
FALLBACK_TO_MP3 = True        # (library mode) attach fail ho aur MP3 ho to MP3 wali reel
ARTIST_NAME = ""              # (library mode) find-songs isse filter karta hai
TOKEN_REFRESH_DAYS = 20       # (instagram login) token har 20 din mein apne aap naya — GH_PAT secret chahiye

# ---------------------------------------------------------------------
# 4) CAPTION
# ---------------------------------------------------------------------
CAPTION_STYLE = "hindi"       # "hindi" (देवनागरी) ya "hinglish"
USE_CLAUDE = True             # ANTHROPIC_API_KEY ho to Claude caption likhega, warna ready templates
CLAUDE_MODEL = "claude-haiku-5-5"   # sasta + tez; behtar likhai chahiye to "claude-sonnet-5-5"
MAX_HASHTAGS = 5              # Instagram ab ek post pe 5 hashtag hi allow karta hai
COMMON_HASHTAGS = ["#bhakti", "#bhajan", "#devotional", "#omnamohbhagwate"]

# ---------------------------------------------------------------------
# 5) NOTIFICATIONS (Telegram — optional, X agent wala bot hi chalega)
# ---------------------------------------------------------------------
NOTIFY_ON_ERROR = True
NOTIFY_ON_SUCCESS = False     # 10-15 reels/din pe har baar message aayega — chaho to True karo
DAILY_SUMMARY_AT = "22:45"    # raat ko din ka hisaab (kitni post hui). "" = band

# ---------------------------------------------------------------------
# 6) BHAGWAN — photos ka folder, mantra, jaikara, hashtags, rang
#    photos/<key>/ mein us bhagwan ki photos daalo (jaise photos/shiv/1.jpg)
# ---------------------------------------------------------------------
DEITIES = {
    "shiv": {
        "name": "भगवान शिव", "jaikara": "हर हर महादेव",
        "mantras": ["ॐ नमः शिवाय", "हर हर महादेव", "बम बम भोले", "जय भोलेनाथ"],
        "keywords": ["shiv", "shiva", "shankar", "mahadev", "bhole", "bholenath", "shambhu", "rudra", "neelkanth", "शिव", "महादेव", "भोले"],
        "hashtags": ["#mahadev", "#harharmahadev", "#shiv"],
        "theme": {"glow": "#7fb2ff", "bg": "#1f2a5c", "particles": ["#cfe2ff", "#ffd27a", "#ffffff"]},
    },
    "radha": {
        "name": "श्री राधा रानी", "jaikara": "राधे राधे",
        "mantras": ["राधे राधे", "जय श्री राधे", "श्री राधा रानी की जय", "राधे कृष्ण", "बरसाने वाली राधे"],
        "keywords": ["radha", "radhe", "radharani", "radhika", "kishori", "barsana", "shriji", "राधा", "राधे", "किशोरी"],
        "hashtags": ["#radherani", "#radheradhe", "#radhakrishna"],
        "theme": {"glow": "#ff8fc8", "bg": "#5c1a3e", "particles": ["#ffd27a", "#ffb3d9", "#fff1c9"]},
    },
    "krishna": {
        "name": "श्री कृष्ण", "jaikara": "जय श्री कृष्ण",
        "mantras": ["जय श्री कृष्ण", "हरे कृष्ण हरे कृष्ण", "ॐ नमो भगवते वासुदेवाय", "गोविंद बोलो हरि गोपाल बोलो"],
        "keywords": ["krishna", "krishn", "shyam", "govind", "gopal", "kanha", "kanhaiya", "murli", "banke", "कृष्ण", "श्याम"],
        "hashtags": ["#radheradhe", "#krishna", "#harekrishna"],
        "theme": {"glow": "#ffb85c", "bg": "#0f4b5c", "particles": ["#ffd27a", "#9fe8e0", "#fff1c9"]},
    },
    "khatushyam": {
        "name": "खाटू श्याम जी", "jaikara": "जय श्री श्याम",
        "mantras": ["जय श्री श्याम", "हारे का सहारा", "श्याम बाबा की जय"],
        "keywords": ["khatu", "baba shyam", "shyam baba", "sanware", "sawariya", "khatushyam", "खाटू", "श्याम बाबा"],
        "hashtags": ["#khatushyam", "#jaishreeshyam", "#shyambaba"],
        "theme": {"glow": "#ffb347", "bg": "#5c1d4a", "particles": ["#ffd27a", "#ffb04a", "#fff1c9"]},
    },
    "ram": {
        "name": "प्रभु श्री राम", "jaikara": "जय श्री राम",
        "mantras": ["जय श्री राम", "श्री राम जय राम जय जय राम", "सिया राम"],
        "keywords": ["ram", "raam", "siyaram", "siya ram", "raghu", "raghupati", "ayodhya", "ramayan", "राम"],
        "hashtags": ["#jaishreeram", "#ram", "#siyaram"],
        "theme": {"glow": "#ffa63d", "bg": "#7a2a0e", "particles": ["#ffd27a", "#ff9a3c", "#fff1c9"]},
    },
    "hanuman": {
        "name": "हनुमान जी", "jaikara": "जय बजरंगबली",
        "mantras": ["जय बजरंगबली", "जय हनुमान", "संकट मोचन हनुमान"],
        "keywords": ["hanuman", "bajrang", "bajrangbali", "balaji", "maruti", "anjani", "sankat mochan", "हनुमान", "बजरंग", "बालाजी"],
        "hashtags": ["#hanuman", "#jaibajrangbali", "#balaji"],
        "theme": {"glow": "#ff8a3d", "bg": "#7a1d0e", "particles": ["#ffb04a", "#ff7a2e", "#ffe0a8"]},
    },
    "ganesh": {
        "name": "श्री गणेश", "jaikara": "गणपति बप्पा मोरया",
        "mantras": ["गणपति बप्पा मोरया", "ॐ गं गणपतये नमः", "जय श्री गणेश"],
        "keywords": ["ganesh", "ganpati", "ganapati", "vinayak", "gajanan", "lambodar", "गणेश", "गणपति"],
        "hashtags": ["#ganpatibappamorya", "#ganesh", "#ganpati"],
        "theme": {"glow": "#ffb347", "bg": "#7a3a0e", "particles": ["#ffd27a", "#ff9a3c", "#fff1c9"]},
    },
    "durga": {
        "name": "माँ दुर्गा", "jaikara": "जय माता दी",
        "mantras": ["जय माता दी", "जय माँ दुर्गा", "जय अम्बे गौरी"],
        "keywords": ["durga", "mata", "maa", "ambe", "sherawali", "jagdambe", "bhawani", "kali", "navratri", "devi", "दुर्गा", "माता", "अम्बे"],
        "hashtags": ["#jaimatadi", "#durgamaa", "#navratri"],
        "theme": {"glow": "#ff6b5c", "bg": "#6e0f1a", "particles": ["#ffb04a", "#ff7a6b", "#ffe0a8"]},
    },
    "vishnu": {
        "name": "भगवान विष्णु", "jaikara": "ॐ नमो नारायणाय",
        "mantras": ["ॐ नमो नारायणाय", "ॐ नमो भगवते वासुदेवाय", "जय श्री हरि"],
        "keywords": ["vishnu", "narayan", "narayana", "hari", "vasudev", "satyanarayan", "विष्णु", "नारायण", "हरि"],
        "hashtags": ["#vishnu", "#narayan", "#omnamonarayanaya"],
        "theme": {"glow": "#ffd36b", "bg": "#123a6e", "particles": ["#ffe28a", "#cfe2ff", "#fff1c9"]},
    },
    "lakshmi": {
        "name": "माँ लक्ष्मी", "jaikara": "जय माँ लक्ष्मी",
        "mantras": ["जय माँ लक्ष्मी", "ॐ श्रीं महालक्ष्म्यै नमः", "शुभ लाभ"],
        "keywords": ["lakshmi", "laxmi", "mahalakshmi", "लक्ष्मी"],
        "hashtags": ["#lakshmi", "#mahalakshmi", "#diwali"],
        "theme": {"glow": "#ffcf4d", "bg": "#7a0e3a", "particles": ["#ffe28a", "#ffd27a", "#fff1c9"]},
    },
    "sai": {
        "name": "साईं बाबा", "jaikara": "ॐ साईं राम",
        "mantras": ["ॐ साईं राम", "सबका मालिक एक", "जय साईं राम"],
        "keywords": ["sai", "saibaba", "shirdi", "साईं"],
        "hashtags": ["#saibaba", "#omsairam", "#shirdi"],
        "theme": {"glow": "#ffc46b", "bg": "#5c3a12", "particles": ["#ffd27a", "#fff1c9", "#ffb04a"]},
    },
    "general": {
        "name": "भगवान", "jaikara": "हरि ॐ",
        "mantras": ["ॐ नमो भगवते", "हरि ॐ", "सर्वे भवन्तु सुखिनः", "ॐ शांति"],
        "keywords": ["om", "bhajan", "aarti", "mantra", "prarthana", "ॐ"],
        "hashtags": ["#om", "#mantra", "#spiritual"],
        "theme": {"glow": "#ffb347", "bg": "#7a1d0e", "particles": ["#ffd27a", "#ffb04a", "#fff1c9"]},
    },
}

# Kisi bhagwan ka photo folder khaali ho to pehle in folders se photo lo (phir general)
PHOTO_FALLBACK = {"krishna": ["radha"], "radha": ["krishna"], "khatushyam": ["krishna", "radha"]}

# Hafte ke din ka bhagwan (0=Somvar ... 6=Ravivar). Us din ~40% reels inhi ki hongi.
DAY_DEITY = {
    0: ["shiv"],
    1: ["hanuman"],
    2: ["ganesh", "krishna", "radha"],
    3: ["vishnu", "sai", "krishna"],
    4: ["durga", "lakshmi", "khatushyam"],
    5: ["hanuman", "shiv"],
    6: ["ram", "general"],
}
DAY_DEITY_SHARE = 0.40

# ---------------------------------------------------------------------
# Advanced (chhedne ki zarurat nahi)
# ---------------------------------------------------------------------
GRAPH_VERSION = "v25.0"
REEL_FPS = 30
THUMB_OFFSET_MS = 2500        # cover frame: 2.5 sec pe (tab tak mantra dikh jaata hai)
SHARE_TO_FEED = True          # reel profile grid mein bhi dikhe
