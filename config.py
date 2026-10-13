# =====================================================================
#  Instagram Reels Agent — SETTINGS (sirf yahi file badalni hai)
#  Secrets (token, API keys) yahan NAHI likhne — GitHub Secrets mein daalo.
# =====================================================================

# ---------------------------------------------------------------------
# 1) POSTING SCHEDULE
# ---------------------------------------------------------------------
TIMEZONE = "Asia/Kolkata"
# Kab-kab post ho (IST): (shuru, khatam, kitni reels). Reels in khidkiyon mein barabar faasle pe lagti hain.
#  - Subah: puja/aarti ka time — bhakti wale log subah sabse pehle bhajan dekhte hain
#  - Dopahar: lunch + India ka afternoon engagement peak (2-5 PM)
#  - Shaam: sandhya aarti + Reels ka prime time (6-9 PM) — sabse zyada reels yahin
# Instagram Insights → Followers → "Most active times" dekh ke inhe badal sakte ho.
POST_WINDOWS = [
    ("05:45", "08:45", 3),
    ("12:30", "16:30", 2),
    ("18:00", "22:30", 5),
]
POSTS_PER_DAY = sum(c for _, _, c in POST_WINDOWS)   # roz kitni reels (apne aap — upar ki ginti ka jod)
JITTER_MINUTES = 12           # har slot ko ±12 min aage-peeche (robot jaisa fix time na lage)
MAX_LATE_MINUTES = 120        # koi slot isse zyada late ho gaya to skip (ek saath dher na lage)
MIN_GAP_MINUTES = 35          # do reels ke beech kam se kam itna faasla
CAMPAIGN_END = ""             # "2026-11-10" likho to us din ke baad posting band. "" = kabhi band nahi
PAUSED = False                # 🚀 LIVE. True karo to automatic posting turant band

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

# Tyohaar: in dino caption mein chhoti si shubhkamna + tyohaar ka hashtag (har bhagwan ki reel mein)
FESTIVALS = [
    {"name": "नवरात्रि", "start": "2026-10-11", "end": "2026-10-19", "hashtag": "#navratri",
     "wish": "नवरात्रि की हार्दिक शुभकामनाएं 🙏", "count_days": True},
    {"name": "दशहरा", "start": "2026-10-20", "end": "2026-10-20", "hashtag": "#dussehra",
     "wish": "विजयादशमी की हार्दिक शुभकामनाएं 🙏"},
    {"name": "शरद पूर्णिमा", "start": "2026-10-25", "end": "2026-10-25", "hashtag": "#sharadpurnima",
     "wish": "शरद पूर्णिमा की शुभकामनाएं 🌕"},
    {"name": "धनतेरस", "start": "2026-11-06", "end": "2026-11-06", "hashtag": "#dhanteras",
     "wish": "धनतेरस की शुभकामनाएं 🪔"},
    {"name": "दीपावली", "start": "2026-11-08", "end": "2026-11-08", "hashtag": "#diwali",
     "wish": "दीपावली की हार्दिक शुभकामनाएं 🪔"},
]

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
        "name": "भगवान शिव", "jaikara": "ॐ नमः शिवाय",
        "mantras": ["ॐ नमः शिवाय", "शिवोहम्", "शिव शम्भो", "ॐ महादेवाय नमः", "हर हर महादेव"],
        "keywords": ["shiv", "shiva", "shankar", "mahadev", "bhole", "bholenath", "shambhu", "rudra", "neelkanth", "shivoham",
                     "kailash", "शिव", "महादेव", "भोले", "शिवोहम"],
        "hashtags": ["#mahadev", "#omnamahshivay", "#shiv", "#shivmeditation"],
        "theme": {"glow": "#7fb2ff", "bg": "#1f2a5c", "particles": ["#cfe2ff", "#ffd27a", "#ffffff"], "calm": True},
        # Shiv ji ke bhajan ekdum shaant/dhyaan wale hain
        "bottom_lines": [
            "आँखें बंद करें और बस सुनें",
            "रोज़ भक्ति के लिए फ़ॉलो करें",
            "कमेंट में लिखें — ॐ नमः शिवाय",
            "मन को शांति दे — अपनों को भेजें",
        ],
        "caption_note": ("Ye bhajan ekdum shaant, dhyaan (meditation) wala hai. Caption bhi shaant, sukoon aur dhyaan ka ho — "
                         "'Bam Bam', josh ya chillane wala tone NAHI. Headphone lagake, aankhein band karke sunne ka bhaav ho. "
                         "Gaane ke naam mein Saavan/Sawan ho to bhi ye mat likho ki abhi saavan ka mahina chal raha hai."),
        # songs.json mein kisi gaane pe "mood": "josh" likho to ye settings lagengi (kanwar/dhol wale gaane)
        "moods": {
            "josh": {
                "jaikara": "हर हर महादेव",
                "mantras": ["हर हर महादेव", "बम बम भोले", "जय भोलेनाथ", "जय शिव शंकर"],
                "bottom_lines": [
                    "कमेंट में लिखें — हर हर महादेव",
                    "रोज़ भक्ति के लिए फ़ॉलो करें",
                    "पूरा भजन सुनने के लिए ऑडियो पर टैप करें",
                    "भोले के भक्तों को भेजें",
                ],
                "hashtags": ["#harharmahadev", "#bambambhole", "#mahadev", "#bholenath"],
                "caption_note": ("Ye joshila Shiv bhajan hai (dhol/kanwar wala). Caption mein utsah aur bhakti ho — "
                                 "'Har Har Mahadev', 'Bam Bam Bhole' jaisa jaikara. Gaane ke naam mein Saavan/Sawan ho "
                                 "to bhi ye mat likho ki abhi saavan ka mahina chal raha hai."),
                "templates": [
                    "हर हर महादेव 🔱\nभोले के भक्तों, आवाज़ ऊँची करो! 🙌\n🎵 {song}\nकमेंट में लिखें: हर हर महादेव",
                    "बम बम भोले 🔱\n🎵 {song}\nपूरा भजन सुनें और अपनों को भेजें 🙏",
                    "आज {day} — भोलेनाथ के नाम 🔱\n🎵 {song}\nजय भोलेनाथ 🙏",
                ],
            },
        },
        "templates": [
            "ॐ नमः शिवाय 🙏\nआँखें बंद करें, साँस धीमी करें… और बस सुनें 🎧\n🎵 {song}",
            "शिव में ही शांति है 🌙\n🎵 {song}\nकमेंट में लिखें: ॐ नमः शिवाय",
            "आज {day} — कुछ पल महादेव के साथ 🕉️\n🎵 {song}\nमन शांत हो तो अपनों को भी भेजें 🙏",
        ],
    },
    "premanand": {
        "name": "पूज्य श्री प्रेमानंद जी महाराज", "jaikara": "राधा राधा",
        "mantras": ["राधा राधा", "श्री राधा", "जय जय श्री राधे", "राधा नाम जप"],
        # "Radha Naam Jap" bhajan isi section mein aata hai (naam mein "naam jap" ho to)
        "keywords": ["premanand", "naam jap", "naam jaap", "naamjap", "प्रेमानंद", "नाम जप"],
        "hashtags": ["#premanandjimaharaj", "#radharadha", "#vrindavan"],
        "theme": {"glow": "#ffc83d", "bg": "#6b4a00", "particles": ["#ffe28a", "#ffd27a", "#fff1c9"]},
        "mantra_art_share": 0,    # har reel mein Maharaj ji ki photo (bina photo wali mandala reel nahi)
        # Caption likhte waqt Claude ke liye niyam (asli sant hain — unke naam se jhootha quote nahi)
        "caption_note": ("Ye reel Vrindavan ke sant Pujya Shri Premanand Ji Maharaj ki tasveeron par hai, bhajan 'Radha Naam Jap' hai. "
                         "Aadar se 'Pujya Maharaj Ji' likho. Unke naam se koi vachan/quote MAT likho (unhone kuch kaha aisa mat dikhao), "
                         "aur aisa mat likho ki ye page unka official page hai. Radha naam jap ki mahima aur bhakti par likho."),
        "templates": [
            "राधा राधा 🙏\nपूज्य महाराज जी के चरणों में कोटि-कोटि प्रणाम 🌼\n🎵 {song}\nकमेंट में लिखें: राधा राधा",
            "हर साँस में राधा नाम 🙏\n🎵 {song}\nदो पल आँखें बंद करें और साथ में जपें — राधा राधा",
            "आज {day} है — राधा नाम जप से दिन की शुरुआत करें 🌸\n🎵 {song}\nअपनों को भेजें 🙏",
        ],
    },
    "sanwariya": {
        "name": "श्री सांवलिया सेठ", "jaikara": "जय श्री सांवलिया सेठ",
        "mantras": ["जय श्री सांवलिया सेठ", "सांवरिया सेठ की जय", "मेरे सांवरिया", "जय श्री कृष्ण"],
        "keywords": ["sanwariya", "sanwriya", "sanwaliya", "sawariya", "saawariya", "sanware", "mandaphia",
                     "सांवलिया", "सांवरिया", "साँवरिया"],
        "hashtags": ["#sanwariyaseth", "#sanwaliyaseth", "#jaishrikrishna"],
        "theme": {"glow": "#ffcf5c", "bg": "#1f2f6b", "particles": ["#ffe28a", "#ffd27a", "#cfe2ff"]},
        "caption_note": ("Ye bhajan Shri Sanwaliya Seth ji (Mandaphia, Chittorgarh — Shri Krishna ka roop) ke hain. "
                         "Bharose, apnapan aur bhakti ka bhaav ho. Dhan/business badhne ya mannat poori hone ka vaada MAT karo."),
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
        "mantras": ["जय श्री श्याम", "हारे का सहारा बाबा श्याम हमारा", "श्याम बाबा की जय", "जय खाटू श्याम", "लखदातार की जय"],
        "keywords": ["khatu", "baba shyam", "shyam baba", "khatushyam", "hare ka sahara", "haare ka sahara",
                     "shyam dhani", "lakhdatar", "barbarik", "खाटू", "श्याम बाबा", "हारे का सहारा"],
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
    2: ["ganesh", "krishna", "radha", "sanwariya"],
    3: ["vishnu", "sai", "krishna"],
    4: ["durga", "lakshmi", "khatushyam"],
    5: ["hanuman", "shiv"],
    6: ["ram", "general"],
}
DAY_DEITY_SHARE = 0.40

# Kis section ki reels kitni baar (1.0 = normal, 2.0 = dugni, 0 = band). Khaali = sab barabar niyam se.
# Jaise Maharaj ji ki reels zyada chahiye: {"premanand": 2.0}
SECTION_WEIGHT = {}

# ---------------------------------------------------------------------
# Advanced (chhedne ki zarurat nahi)
# ---------------------------------------------------------------------
GRAPH_VERSION = "v25.0"
REEL_FPS = 30
THUMB_OFFSET_MS = 2500        # cover frame: 2.5 sec pe (tab tak mantra dikh jaata hai)
SHARE_TO_FEED = True          # reel profile grid mein bhi dikhe
