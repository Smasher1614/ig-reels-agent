#!/usr/bin/env python3
"""
IG Reels Agent — "Om Namoh Bhagwate" Instagram ke liye roz devotional reels.

Kya karta hai (har slot pe, roz POSTS_PER_DAY baar):
  1. music/ (ya songs.json) se ek gaana chunta hai (hafte ke din ke bhagwan ko thoda zyada mauka)
  2. Us bhagwan ki photo pe 9:16 reel banata hai (zoom, glow, chamakte kan, mantra text)
     + gaane ka sabse jandaar 30 sec hissa (MP3 mode) — ya library gaana (Facebook Login mode)
  3. Claude se naya Hindi caption + 5 hashtag
  4. Instagram pe Reel post (Instagram Login — Facebook Page ki zarurat nahi)

Chalane ke tareeke:
  python agent.py                      -> slot due ho to 1 reel post (GitHub Actions har 20 min yahi chalata hai)
  python agent.py --now                -> abhi turant 1 reel post (test)
  python agent.py --preview 3          -> 3 reels bana ke preview/ mein — post NAHI hoga
  python agent.py --check              -> token, account, quota, gaane — sab jaancho
  python agent.py --find-songs "naam"  -> Instagram music library mein gaane dhundo
  python agent.py --find-songs "naam" --save   -> mile hue (tumhare artist naam wale) gaane songs.json mein jodo
  python agent.py --schedule           -> aaj ke slots dikhao
  python agent.py --due                -> (workflow ke liye) abhi kuch karna hai ya nahi

Settings: config.py      Gaane: songs.json      Photos: photos/<bhagwan>/
Secrets: GitHub Secrets ya .env (README dekho)
"""
from __future__ import annotations

import argparse
import base64
import collections
import datetime as dt
import hashlib
import json
import math
import os
import random
import re
import sys
import time
from zoneinfo import ZoneInfo

import config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "state.json")
SONGS_FILE = os.path.join(BASE_DIR, "songs.json")
MUSIC_DIR = os.path.join(BASE_DIR, "music")
AUDIO_EXTS = (".mp3", ".m4a", ".wav", ".aac", ".ogg",          # gaane ki audio file
              ".mp4", ".mov", ".webm", ".mkv", ".m4v")         # ya video (jaise YouTube Studio se download) — awaaz nikaal li jaati hai
PHOTOS_DIR = os.path.join(BASE_DIR, "photos")
OUT_DIR = os.path.join(BASE_DIR, "out")
PREVIEW_DIR = os.path.join(BASE_DIR, "preview")
TZ = ZoneInfo(config.TIMEZONE)
HINDI_DAYS = ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"]

# keyword se bhagwan pehchaanne ka kram (specific pehle, general baad mein)
DEITY_MATCH_ORDER = ["premanand", "sanwariya", "khatushyam", "hanuman", "ganesh", "lakshmi", "sai", "radha", "ram", "krishna",
                     "shiv", "vishnu", "durga", "general"]


class SetupError(Exception):
    """Setup/config ki galti — user ko saaf message chahiye."""


class RecentlyPosted(Exception):
    """Instagram pe abhi-abhi reel gayi hai (doosre run ne ya haath se) — ye slot chhod do, double post nahi."""


# ===================================================================== basics
def log(msg: str) -> None:
    print(f"[{now_local():%H:%M:%S}] {msg}", flush=True)


def load_dotenv(path: str = os.path.join(BASE_DIR, ".env")) -> None:
    """Local run ke liye .env padho (GitHub Actions mein Secrets aate hain)."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def env(name: str) -> str:
    return os.environ.get(name, "").strip()


def now_local() -> dt.datetime:
    fake = os.environ.get("FAKE_NOW")  # sirf testing ke liye
    if fake:
        return dt.datetime.fromisoformat(fake).replace(tzinfo=TZ)
    return dt.datetime.now(TZ)


def load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as e:
        raise SetupError(f"{os.path.basename(path)} mein JSON galti hai (line {e.lineno}): {e.msg}")


def save_json(path: str, data) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, path)


def load_state() -> dict:
    st = load_json(STATE_FILE, {})
    st.setdefault("posted", [])
    st.setdefault("skipped", [])
    st.setdefault("attempts", {})
    st.setdefault("last_used", {})
    st.setdefault("counter", 0)
    st.setdefault("captions", [])
    st.setdefault("errors", [])
    st.setdefault("summary_sent", "")
    st.setdefault("song_fail", {})
    return st


def save_state(st: dict) -> None:
    st["posted"] = st["posted"][-600:]
    st["skipped"] = st["skipped"][-300:]
    st["captions"] = st["captions"][-20:]
    st["errors"] = st["errors"][-15:]
    keep = {p["slot"] for p in st["posted"][-50:]}
    st["attempts"] = {k: v for k, v in st["attempts"].items() if k not in keep}
    if len(st["attempts"]) > 60:
        st["attempts"] = dict(list(st["attempts"].items())[-60:])
    save_json(STATE_FILE, st)


def _hhmm(s: str) -> dt.time:
    h, m = s.split(":")
    return dt.time(int(h), int(m))


def _seed(*parts) -> int:
    return int(hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)


# ===================================================================== schedule
def day_slots(day: dt.date) -> list[tuple[str, dt.datetime]]:
    """Din ke slots: har POST_WINDOWS khidki mein reels barabar faasle pe (thoda aage-peeche)."""
    windows = getattr(config, "POST_WINDOWS", None) or [(config.DAY_START, config.DAY_END, config.POSTS_PER_DAY)]
    out, i = [], 0
    for ws, we, cnt in windows:
        cnt = int(cnt)
        if cnt <= 0:
            continue
        start = dt.datetime.combine(day, _hhmm(ws), TZ)
        end = dt.datetime.combine(day, _hhmm(we), TZ)
        step = (end - start).total_seconds() / 60 / cnt
        jit = min(config.JITTER_MINUTES, step / 3)
        for k in range(cnt):
            r = random.Random(_seed(day.isoformat(), i, "slot")).uniform(-jit, jit)
            t = start + dt.timedelta(minutes=(k + 0.5) * step + r)
            out.append((f"{day.isoformat()}#{i}", t.replace(second=0, microsecond=0)))
            i += 1
    return out


def festival_today(day: dt.date) -> dict | None:
    for f in getattr(config, "FESTIVALS", []) or []:
        try:
            a, b = dt.date.fromisoformat(f["start"]), dt.date.fromisoformat(f["end"])
        except (KeyError, ValueError):
            continue
        if a <= day <= b:
            f = dict(f)
            f["day_no"] = (day - a).days + 1
            return f
    return None


def campaign_over(now: dt.datetime) -> bool:
    if not config.CAMPAIGN_END:
        return False
    return now.date() > dt.date.fromisoformat(config.CAMPAIGN_END)


def due_slot(st: dict, now: dt.datetime, mark: bool = True):
    """Abhi post karne layak sabse purana slot. Bahut late slots skip ho jaate hain."""
    if config.PAUSED or campaign_over(now):
        return None
    done = {p["slot"] for p in st["posted"]} | set(st["skipped"])
    late = dt.timedelta(minutes=config.MAX_LATE_MINUTES)
    found = None
    for day in (now.date() - dt.timedelta(days=1), now.date()):
        for key, t in day_slots(day):
            if key in done or t > now:
                continue
            if now - t > late:
                if mark:
                    st["skipped"].append(key)
                    log(f"slot {key} ({t:%H:%M}) bahut late ho gaya — skip")
                continue
            if found is None:
                found = (key, t)
    if found and st["posted"]:
        # do reels bahut paas-paas na jaayein (late run ke baad ek ke peeche ek) — agli tick tak ruko
        try:
            last = dt.datetime.fromisoformat(st["posted"][-1]["at"])
            if now - last < dt.timedelta(minutes=getattr(config, "MIN_GAP_MINUTES", 0)):
                return None
        except (KeyError, ValueError):
            pass
    return found


def summary_due(st: dict, now: dt.datetime) -> bool:
    if not config.DAILY_SUMMARY_AT or not (env("TELEGRAM_BOT_TOKEN") and env("TELEGRAM_CHAT_ID")):
        return False
    return now.time() >= _hhmm(config.DAILY_SUMMARY_AT) and st["summary_sent"] != now.date().isoformat()


# ===================================================================== songs & content
def deity_from_text(text: str) -> str:
    t = text.casefold()
    words = set(re.findall(r"[a-z]+", t))
    for key in DEITY_MATCH_ORDER:
        for kw in config.DEITIES[key]["keywords"]:
            k = kw.casefold()
            if not k.isascii() or " " in k:
                if k in t:
                    return key
            elif len(k) <= 4:
                if k in words:
                    return key
            elif any(w.startswith(k) for w in words):
                return key
    return "general"


def load_songs() -> list[dict]:
    data = load_json(SONGS_FILE, {"songs": []})
    songs = data.get("songs", data if isinstance(data, list) else [])
    out = []
    for s in songs:
        if not isinstance(s, dict) or not s.get("title") or s.get("enabled", True) is False:
            continue
        s = dict(s)
        if s.get("deity") not in config.DEITIES:
            s["deity"] = deity_from_text(s["title"])
        mp3 = s.get("mp3") or ""
        s["mp3_path"] = os.path.join(BASE_DIR, mp3) if mp3 else ""
        if s["mp3_path"] and not os.path.exists(s["mp3_path"]):
            log(f"⚠ '{s['title']}' ki MP3 nahi mili: {mp3}")
            s["mp3_path"] = ""
        out.append(s)
    # music/ (ya music/<bhagwan>/) mein padi har MP3 apne aap gaana ban jaati hai —
    # songs.json mein likhne ki zarurat nahi. File ka naam = gaane ka naam.
    known = {os.path.normpath(s["mp3_path"]) for s in out if s["mp3_path"]}
    disabled = {os.path.normpath(os.path.join(BASE_DIR, s.get("mp3") or "")) for s in songs
                if isinstance(s, dict) and s.get("enabled", True) is False and s.get("mp3")}
    if os.path.isdir(MUSIC_DIR):
        for root, _, files in os.walk(MUSIC_DIR):
            for f in sorted(files):
                path = os.path.normpath(os.path.join(root, f))
                if not f.lower().endswith(AUDIO_EXTS) or f.startswith(".") or path in known or path in disabled:
                    continue
                title = re.sub(r"[_\-]+", " ", os.path.splitext(f)[0]).strip()
                folder = os.path.basename(root)
                deity = folder if folder in config.DEITIES else deity_from_text(title)
                out.append({"title": title, "deity": deity, "audio_id": "", "mp3": os.path.relpath(path, BASE_DIR),
                            "mp3_path": path, "mp3_start": "auto"})
    return out


def library_on() -> bool:
    """Library gaana lag sakta hai? ("auto" = jahan audio_id ho aur Facebook token ho)"""
    if config.AUDIO_MODE == "library":
        return True
    return config.AUDIO_MODE == "auto" and bool(env("FB_ACCESS_TOKEN") or env("FB_PAGE_TOKEN")
                                                or config.LOGIN_TYPE == "facebook")


def usable_songs(songs: list[dict], st: dict | None = None) -> list[dict]:
    if config.AUDIO_MODE == "mp3" or not library_on():
        return [s for s in songs if s["mp3_path"]]
    bad = {aid for aid, n in ((st or {}).get("song_fail") or {}).items() if n >= 2}
    out = []
    for s in songs:
        has_mp3 = config.FALLBACK_TO_MP3 and s["mp3_path"]
        if s.get("audio_id") and str(s["audio_id"]) in bad and not has_mp3:
            continue  # do baar attach fail — jab tak audio_id theek na ho, skip
        if s.get("audio_id") or has_mp3:
            out.append(s)
    return out


def god_for(deity: str, song: dict | None = None) -> dict:
    """Section ki settings; gaane ka "mood" (songs.json) ho to us mood ki settings upar se laga do.
    Jaise Shiv section calm hai, par "josh" wale gaane (kanwar/dhol) ke liye alag mantra/lines/video speed."""
    god = dict(config.DEITIES[deity])
    mood = (song or {}).get("mood") or ""
    over = (god.get("moods") or {}).get(mood) or {}
    god.update(over)
    theme = dict(god.get("theme") or {})
    if mood in ("josh", "calm"):
        theme["calm"] = mood == "calm"
    theme.update(over.get("theme") or {})
    god["theme"] = theme
    god["mood"] = mood
    return god


def lru_pick(items: list, keyfn, st: dict, rng: random.Random):
    """Sabse kam haal-filhaal use hua item (thoda random) — repeat kam."""
    lu = st["last_used"]
    ranked = sorted(items, key=lambda x: (lu.get(keyfn(x), -1), rng.random()))
    k = max(1, len(ranked) // 3)
    return rng.choice(ranked[:k])


def photos_for(deity: str) -> list[str]:
    from render import list_photos
    ph = list_photos(os.path.join(PHOTOS_DIR, deity))
    for alt in getattr(config, "PHOTO_FALLBACK", {}).get(deity, []) + ["general"]:
        if ph or alt == deity:
            break
        ph = list_photos(os.path.join(PHOTOS_DIR, alt))
    return ph


def has_visual(deity: str) -> bool:
    return bool(photos_for(deity)) or bool(config.DEITIES.get(deity, {}).get("allow_no_photo"))


def choose_content(st: dict, now: dt.datetime, slot_key: str, songs: list[dict]) -> dict:
    rng = random.Random(_seed(slot_key, st["counter"]))
    # jis section ki ek bhi photo nahi (na fallback), uske gaane photos aane tak rukenge
    with_pics = [s for s in songs if has_visual(s["deity"])]
    songs = with_pics or songs
    day_gods = config.DAY_DEITY.get(now.weekday(), [])
    # pichhli kuch reels wale gaane abhi dobara nahi (agar aur gaane hain)
    k = min(4, max(0, len(songs) - 1))
    recent = {p["song"] for p in st["posted"][-k:]} if k else set()
    fresh = [s for s in songs if s["title"] not in recent] or songs
    # pehle section (bhagwan) chuno, phir uska gaana — taaki 17 Shiv gaane baaki sab ko na dabaa dein.
    # weight = gaano ki ginti ka square-root (jyada gaane = thoda zyada mauka) × SECTION_WEIGHT
    total = collections.Counter(s["deity"] for s in songs)
    groups: dict[str, list] = {}
    for s in fresh:
        groups.setdefault(s["deity"], []).append(s)
    cands = list(groups)
    todays = [d for d in cands if d in day_gods]
    if todays and rng.random() < config.DAY_DEITY_SHARE:
        cands = todays
    last = st["posted"][-1]["deity"] if st["posted"] else None
    weights = [math.sqrt(total[d]) * float(getattr(config, "SECTION_WEIGHT", {}).get(d, 1.0))
               * (0.5 if d == last and len(cands) > 1 else 1.0) for d in cands]
    deity_pick = rng.choices(cands, weights=weights)[0] if sum(weights) > 0 else rng.choice(cands)
    song = lru_pick(groups[deity_pick], lambda s: "song:" + s["title"], st, rng)
    deity = song["deity"]
    god = god_for(deity, song)

    photos = photos_for(deity)
    photo = None
    if photos and rng.random() >= god.get("mantra_art_share", config.MANTRA_ART_SHARE):
        photo = lru_pick(photos, lambda p: "photo:" + os.path.relpath(p, BASE_DIR), st, rng)
    mantra = lru_pick(god["mantras"], lambda m: f"mantra:{deity}:{m}", st, rng)
    lines = god.get("bottom_lines") or config.BOTTOM_LINES
    if not (library_on() and song.get("audio_id")):  # MP3 wali reel pe "Original audio" — tap karke gaana nahi milta
        lines = [b for b in lines if "ऑडियो पर टैप" not in b] or lines
    bottom = lru_pick(lines, lambda b: "bottom:" + b, st, rng).format(jaikara=god["jaikara"])
    return {
        "slot": slot_key, "song": song, "deity": deity, "god": god, "photo": photo,
        "mantra": mantra, "bottom": bottom, "seed": _seed(slot_key, "video", st["counter"]),
        "weekday": now.weekday(), "festival": festival_today(now.date()),
    }


def mark_used(st: dict, plan: dict) -> None:
    st["counter"] += 1
    c = st["counter"]
    lu = st["last_used"]
    lu["song:" + plan["song"]["title"]] = c
    if plan["photo"]:
        lu["photo:" + os.path.relpath(plan["photo"], BASE_DIR)] = c
    lu[f"mantra:{plan['deity']}:{plan['mantra']}"] = c
    god = plan.get("god") or god_for(plan["deity"], plan["song"])
    for b in god.get("bottom_lines") or config.BOTTOM_LINES:
        if b.format(jaikara=god["jaikara"]) == plan["bottom"]:
            lu["bottom:" + b] = c


# ===================================================================== captions
TEMPLATES = [
    "{jaikara} 🙏\n{day} की शुरुआत करें इस भजन के साथ — {song} 🎵\nकमेंट में लिखें: {jaikara}",
    "मन को शांति देने वाला भजन 🎶 {song}\n{name} की कृपा आप पर सदा बनी रहे 🙏\n{jaikara}",
    "{name} का नाम लो, सब काम बनेंगे ✨\n🎵 {song}\nअपनों के साथ ज़रूर शेयर करें 🙏",
    "आज {day} है — {name} को याद करें 🌼\n🎵 {song}\n{jaikara} 🙏",
    "दो पल रुकिए, आँखें बंद कीजिए और सुनिए 🎧\n{song}\n{jaikara} 🙏",
    "भक्ति में ही शक्ति है 🙏\n🎵 {song}\nकमेंट में लिखें: {jaikara}",
]
TEMPLATES_HINGLISH = [
    "{jaikara_en} 🙏\n{song} sunkar din ki shuruaat kijiye 🎵\nComment mein likhiye: {jaikara_en}",
    "Mann ko shanti dene wala bhajan 🎶 {song}\n{jaikara_en} 🙏",
    "Aaj bas do pal Bhagwan ke naam 🙏\n🎵 {song}\nApno ke saath share kijiye ✨",
]


def pick_hashtags(deity: str, rng: random.Random, tags: list | None = None) -> list[str]:
    god = list(tags or config.DEITIES[deity]["hashtags"])
    common = config.COMMON_HASHTAGS[:]
    rng.shuffle(god)
    rng.shuffle(common)
    n = max(0, int(config.MAX_HASHTAGS))
    tags = (god[:3] + common)[:n]
    seen, out = set(), []
    for t in tags:
        t = "#" + t.lstrip("#")
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def _clean_caption(text: str) -> str:
    text = re.sub(r"(?<!\S)#\S+", "", text)          # Claude hashtag na daale
    text = text.replace("**", "").strip().strip('"').strip()
    lines = [ln.rstrip() for ln in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def claude_caption(plan: dict, recent: list[str]) -> str | None:
    key = env("ANTHROPIC_API_KEY")
    if not (config.USE_CLAUDE and key):
        return None
    import requests
    god = plan.get("god") or god_for(plan["deity"], plan["song"])
    style = ("शुद्ध, सरल हिंदी (देवनागरी)" if config.CAPTION_STYLE == "hindi"
             else "Hinglish (Roman script mein Hindi)")
    system = (
        "Tum 'Om Namoh Bhagwate' naam ke Indian devotional music page ke liye Instagram Reel captions likhte ho. "
        "Page apne khud ke bhajan/mantra gaane post karta hai. Bhasha bhaktipurn, garam aur sacchi ho."
    )
    prev = "\n---\n".join(recent[-5:]) or "(abhi koi nahi)"
    fest = plan.get("festival")
    user = (
        f"Is reel ka caption likho.\n"
        f"Vishay (bhagwan/sant): {god['name']} | Jaikara: {god['jaikara']}\n"
        f"Gaana: {plan['song']['title']}\n"
        f"Din: {HINDI_DAYS[plan['weekday']]}\n"
        f"Video pe likha mantra: {plan['mantra']}\n\n"
        f"Niyam:\n"
        f"- Bhasha: {style}\n"
        f"- 2 se 4 chhoti lines, total 280 characters se kam; pehli line dil ko chhoo le\n"
        f"- Gaane ka naam ek baar 🎵 ke saath aaye\n"
        f"- Ek line comment ke liye bulaye (jaise jaikara likhne ko)\n"
        f"- 1-3 emoji theek hain; hashtag BILKUL nahi\n"
        f"- Koi chamatkar/paisa/bimari theek hone ka vaada nahi, 'share nahi kiya to...' jaisi dhamki nahi\n"
        + (f"- Is vishay ka khaas niyam: {god['caption_note']}\n" if god.get("caption_note") else "")
        + (f"- Aaj tyohaar hai: {fest['name']}" + (f" (din {fest['day_no']})" if fest.get("count_days") else "")
           + f". Caption ki aakhri line mein chhoti si shubhkamna do, jaise: \"{fest['wish']}\". "
             "Reel ke bhagwan ko tyohaar se zabardasti mat jodo.\n" if fest else "")
        + f"- Pichhle captions se alag ho:\n{prev}\n\n"
        f"Sirf caption likho, aur kuch nahi."
    )
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": config.CLAUDE_MODEL, "max_tokens": 400, "system": system,
                  "messages": [{"role": "user", "content": user}]},
            timeout=60,
        )
        if r.status_code != 200:
            log(f"Claude caption fail ({r.status_code}): {r.text[:200]} — template use hoga")
            return None
        text = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
        text = _clean_caption(text)
        return text if 10 <= len(text) <= 1500 else None
    except Exception as e:  # noqa: BLE001
        log(f"Claude caption error: {e} — template use hoga")
        return None


def make_caption(plan: dict, st: dict) -> str:
    rng = random.Random(plan["seed"] + 7)
    god = plan.get("god") or god_for(plan["deity"], plan["song"])
    text = claude_caption(plan, st["captions"])
    if not text:
        fields = dict(jaikara=god["jaikara"], name=god["name"], song=plan["song"]["title"],
                      day=HINDI_DAYS[plan["weekday"]], jaikara_en=god["jaikara"])
        pool = god.get("templates") or (TEMPLATES if config.CAPTION_STYLE == "hindi" else TEMPLATES_HINGLISH)
        recent = set(st["captions"][-3:])
        options = [t.format(**fields) for t in pool]
        fresh = [o for o in options if o not in recent] or options
        text = rng.choice(fresh)
        if plan.get("festival") and plan["festival"].get("wish") and plan["festival"]["wish"] not in text:
            text += "\n" + plan["festival"]["wish"]
    tags = pick_hashtags(plan["deity"], rng, god.get("hashtags"))
    fest = plan.get("festival")
    if fest and fest.get("hashtag") and fest["hashtag"].lower() not in [t.lower() for t in tags]:
        tags = (tags[:max(0, int(config.MAX_HASHTAGS) - 1)] + [fest["hashtag"]])[:max(1, int(config.MAX_HASHTAGS))]
    caption = text + ("\n\n" + " ".join(tags) if tags else "")
    return caption[:2150]


# ===================================================================== Instagram API
class IGError(Exception):
    def __init__(self, msg, code=None, subcode=None, raw=None):
        super().__init__(msg)
        self.code, self.subcode, self.raw = code, subcode, raw or {}

    @property
    def hint(self) -> str:
        c, s = self.code, self.subcode
        if c == 190:
            return "Token expire/galat hai — README ka 'Token banao' step dobara karo aur IG_ACCESS_TOKEN secret update karo."
        if c in (10, 200) or (c == 100 and "permission" in str(self).lower()):
            return "Permission nahi mili — token banate waqt instagram_basic + instagram_content_publish + pages_show_list tick karo."
        if c == 9 or s == 2207042:
            return "Instagram ki 24-ghante wali publishing limit poori ho gayi — POSTS_PER_DAY kam karo."
        if "audio" in str(self).lower():
            return "Gaana attach nahi hua — '--find-songs' se audio_id dobara check karo."
        return ""


class Instagram:
    def __init__(self, token: str, ig_id: str, version: str = config.GRAPH_VERSION, kind: str | None = None):
        self.kind = kind or config.LOGIN_TYPE
        ig_login = self.kind == "instagram"
        if not token or (not ig_id and not ig_login):
            raise SetupError("IG_ACCESS_TOKEN" + ("" if ig_login else " aur IG_USER_ID") +
                             " secret set nahi hai (README step 4).")
        import requests
        self.rq = requests
        self.token, self.v = token, version
        self.base = f"https://graph.{'instagram' if ig_login else 'facebook'}.com/{version}"
        self.ig_id = ig_id
        if not self.ig_id:  # Instagram Login: ID token se khud nikaal lo
            me = self.get("me", fields="user_id,username")
            self.ig_id = str(me.get("user_id") or me.get("id"))

    def _call(self, method: str, path: str, params=None, data=None, tries=3):
        url = path if path.startswith("http") else f"{self.base}/{path.lstrip('/')}"
        params = dict(params or {})
        params["access_token"] = self.token
        last = None
        for i in range(tries):
            try:
                r = self.rq.request(method, url, params=params, data=data, timeout=60)
                body = r.json() if r.content else {}
            except (self.rq.RequestException, ValueError) as e:
                last = IGError(f"network error: {e}")
                time.sleep(3 * (i + 1))
                continue
            if r.status_code < 400 and "error" not in body:
                return body
            err = body.get("error", {}) if isinstance(body, dict) else {}
            last = IGError(err.get("error_user_msg") or err.get("message") or f"HTTP {r.status_code}",
                           err.get("code"), err.get("error_subcode"), body)
            if r.status_code >= 500 or err.get("code") in (1, 2, 4, 17, 341) or err.get("is_transient"):
                time.sleep(5 * (i + 1))
                continue
            break
        raise last

    def get(self, path, **params):
        return self._call("GET", path, params=params)

    def post(self, path, **data):
        return self._call("POST", path, data=data)

    # ------------------------------------------------------------ endpoints
    def account(self):
        if self.kind == "instagram":
            return self.get("me", fields="user_id,username,name,account_type,followers_count,media_count")
        return self.get(self.ig_id, fields="id,username,name,followers_count,media_count")

    def quota(self):
        d = self.get(f"{self.ig_id}/content_publishing_limit", fields="quota_usage,config")
        row = (d.get("data") or [{}])[0]
        return row.get("quota_usage", 0), (row.get("config") or {}).get("quota_total", 50)

    def search_audio(self, query: str, pages: int = 3) -> list[dict]:
        out, nxt = [], None
        res = self.get("ig_audio", audio_type="music", user_id=self.ig_id, search_query=query)
        for _ in range(pages):
            items = res.get("audio") or res.get("data") or []
            out.extend(items)
            nxt = (res.get("paging") or {}).get("next")
            if not nxt:
                break
            res = self._call("GET", nxt)
        return out

    def audio_info(self, audio_id: str) -> dict:
        return self.get(audio_id, user_id=self.ig_id)

    def create_reel(self, caption: str, audio_id: str | None = None,
                    video_url: str | None = None) -> tuple[str, str | None]:
        """Reel container banao. video_url do to Instagram us link se video khud download karta hai
        (Instagram Login mein yahi ek tareeka hai); warna resumable upload (sirf Facebook Login)."""
        data = dict(media_type="REELS", caption=caption,
                    share_to_feed="true" if config.SHARE_TO_FEED else "false",
                    thumb_offset=str(config.THUMB_OFFSET_MS))
        if video_url:
            data["video_url"] = video_url
        else:
            data["upload_type"] = "resumable"
        if audio_id:
            # video ki apni (khamosh) awaaz 0, gaana poori awaaz mein
            data["audio_configuration"] = json.dumps({"audio_id": str(audio_id), "audio_volume": 100, "video_volume": 0})
        d = self.post(f"{self.ig_id}/media", **data)
        cid = d["id"]
        if video_url:
            return cid, None
        uri = d.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{self.v}/{cid}"
        return cid, uri

    def upload(self, uri: str, path: str) -> None:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            blob = fh.read()
        last = None
        for i in range(3):
            try:
                r = self.rq.post(uri, data=blob, timeout=300, headers={
                    "Authorization": f"OAuth {self.token}", "offset": "0", "file_size": str(size)})
                body = r.json() if r.content else {}
                if r.status_code < 400 and body.get("success", True) and "error" not in body:
                    return
                err = body.get("debug_info") or body.get("error") or body
                last = IGError(f"video upload fail: {err}")
            except self.rq.RequestException as e:
                last = IGError(f"video upload network error: {e}")
            time.sleep(5 * (i + 1))
        raise last

    def wait_ready(self, cid: str, timeout: int = 600) -> None:
        t0 = time.time()
        while True:
            d = self.get(cid, fields="status_code,status")
            code = d.get("status_code")
            if code in ("FINISHED", "PUBLISHED"):
                return
            if code in ("ERROR", "EXPIRED"):
                raise IGError(f"Instagram ne video process nahi kiya: {d.get('status')}")
            if time.time() - t0 > timeout:
                raise IGError("video processing mein bahut der lagi (10 min)")
            time.sleep(8)

    def publish(self, cid: str) -> str:
        return self.post(f"{self.ig_id}/media_publish", creation_id=cid)["id"]

    def last_post(self) -> tuple[dt.datetime | None, str]:
        """Account ki sabse nayi post ka time + link (double-post rokne ke liye)."""
        d = self.get(f"{self.ig_id}/media", fields="id,timestamp,permalink", limit=1)
        row = (d.get("data") or [{}])[0]
        ts = row.get("timestamp")
        if not ts:
            return None, ""
        return dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z"), row.get("permalink", "")

    def permalink(self, media_id: str) -> str:
        try:
            return self.get(media_id, fields="permalink").get("permalink", "")
        except IGError:
            return ""


def ig_client() -> Instagram:
    return Instagram(env("IG_ACCESS_TOKEN"), env("IG_USER_ID"))


# ===================================================================== Facebook Login (library gaana)
# Instagram Login (upar) MP3 wali reels ke liye chalta rehta hai. Library ka asli gaana sirf Facebook Login se
# lagta hai, isliye FB_ACCESS_TOKEN secret ho to bot ek doosra client bhi banata hai. state.json PUBLIC hai —
# usme kabhi token nahi, sirf Page/IG ka naam-id aur gaano ki list.
FB_GRAPH = f"https://graph.facebook.com/{config.GRAPH_VERSION}"
_FB_CACHE: dict = {}


def _fb_get(path: str, token: str, **params) -> dict:
    import requests
    if token:
        params["access_token"] = token
    r = requests.get(f"{FB_GRAPH}/{path.lstrip('/')}", params=params, timeout=60)
    body = r.json() if r.content else {}
    if r.status_code >= 400 or "error" in body:
        err = body.get("error", {}) if isinstance(body, dict) else {}
        raise IGError(err.get("error_user_msg") or err.get("message") or f"HTTP {r.status_code}",
                      err.get("code"), err.get("error_subcode"), body)
    return body


def fb_setup_due(st: dict, now: dt.datetime) -> bool:
    """Naya FB_ACCESS_TOKEN aaya hai (ya pichhli koshish fail hui thi aur 30 min ho gaye)?"""
    tok = env("FB_ACCESS_TOKEN")
    if not tok:
        return False
    fb = st.get("fb") or {}
    if fb.get("token_fp") == _fp(tok) and fb.get("ok"):
        # artist naam badla ya naye gaane aaye to library dobara dhundo
        return fb.get("artist", "") != config.ARTIST_NAME or fb.get("titles_fp") != _titles_fp()
    try:
        last = dt.datetime.fromisoformat(fb.get("tried_at", ""))
        if fb.get("token_fp") == _fp(tok) and now - last < dt.timedelta(minutes=30):
            return False
    except ValueError:
        pass
    return True


def _scan_titles() -> list[str]:
    out = []
    for s in load_songs():
        if s.get("mp3_path") and s["title"] not in out and s["deity"] != "premanand":
            out.append(s["title"])
    return out


def _titles_fp() -> str:
    return _fp("|".join(sorted(_scan_titles())))


def _norm(t: str) -> str:
    t = re.sub(r"\(.*?\)|\[.*?\]", " ", (t or "").casefold())
    return " ".join(re.findall(r"[a-z0-9\u0900-\u097f]+", t))


def _title_match(mine: str, theirs: str) -> bool:
    a, b = _norm(mine), _norm(theirs)
    return bool(a and b) and (a == b or a in b or b in a)


def fb_setup(st: dict, now: dt.datetime) -> None:
    """FB token se: lamba token, Page + Instagram account, Page token (kabhi expire nahi), aur library mein
    tumhare gaane dhundo. Sab report state.json ke "fb" mein (bina token ke)."""
    user = env("FB_ACCESS_TOKEN")
    fb = {"token_fp": _fp(user), "tried_at": now.isoformat(timespec="seconds"), "ok": False}
    st["fb"] = fb
    try:
        # 1) chhota (1-2 ghante wala) token ho to lamba (60 din) banao
        app_id, secret = env("FB_APP_ID"), env("FB_APP_SECRET")
        if app_id and secret:
            try:
                d = _fb_get("debug_token", f"{app_id}|{secret}", input_token=user).get("data", {})
                exp = d.get("expires_at") or 0
                fb["user_token_expires"] = (dt.datetime.fromtimestamp(exp, TZ).isoformat(timespec="minutes")
                                            if exp else "never")
                if exp and exp - time.time() < 2 * 86400:
                    new = _fb_get("oauth/access_token", "", grant_type="fb_exchange_token", client_id=app_id,
                                  client_secret=secret, fb_exchange_token=user).get("access_token")
                    if new:
                        user = new
                        fb["exchanged"] = True
                        if update_github_secret("FB_ACCESS_TOKEN", new):
                            os.environ["FB_ACCESS_TOKEN"] = new
                            fb["token_fp"] = _fp(new)
                            fb["user_token_expires"] = (now + dt.timedelta(days=60)).isoformat(timespec="minutes")
            except IGError as e:
                fb["exchange_error"] = str(e)[:200]
        # 2) Page + us se juda Instagram account
        pages = _fb_get("me/accounts", user, limit=50,
                        fields="name,access_token,instagram_business_account{id,username}").get("data", [])
        want = (getattr(config, "IG_USERNAME", "") or "").lstrip("@").casefold()
        with_ig = [p for p in pages if p.get("instagram_business_account")]
        pick = next((p for p in with_ig if p["instagram_business_account"].get("username", "").casefold() == want),
                    None) or (with_ig[0] if len(with_ig) == 1 else None)
        fb["pages"] = [{"name": p.get("name"), "ig": (p.get("instagram_business_account") or {}).get("username")}
                       for p in pages]
        if not pick:
            raise SetupError("Token mein koi FB Page nahi mila jo Instagram se juda ho — token banate waqt Facebook "
                             "popup mein Page aur Instagram dono tick karne the (aur pages_show_list permission).")
        iga = pick["instagram_business_account"]
        fb.update(page=pick.get("name"), ig_id=str(iga["id"]), ig_username=iga.get("username"))
        page_tok = pick.get("access_token") or ""
        # 3) kaunsa token Instagram + music search ke liye chalta hai? Page token kabhi expire nahi hota — pehle wo
        first = next((s["title"] for s in load_songs() if s.get("mp3_path")), "bhajan")
        works = None
        for kind, tok in (("page", page_tok), ("user", user)):
            if not tok:
                continue
            try:
                _fb_get(fb["ig_id"], tok, fields="username")
                _fb_get("ig_audio", tok, audio_type="music", user_id=fb["ig_id"], search_query=first)
                works = (kind, tok)
                break
            except IGError as e:
                fb[f"{kind}_token_error"] = str(e)[:200]
        if not works:
            raise SetupError("Token se Instagram/music search nahi chala — permissions check karo "
                             "(instagram_basic, instagram_content_publish, pages_show_list, pages_read_engagement).")
        fb["token_kind"] = works[0]
        if works[0] == "page":
            fb["page_token_saved"] = update_github_secret("FB_PAGE_TOKEN", works[1])
            os.environ["FB_PAGE_TOKEN"] = works[1]
        # 4) library mein tumhare gaane dhundo
        fb["library"] = library_scan(works[1], fb["ig_id"])
        fb.update(ok=True, artist=config.ARTIST_NAME, titles_fp=_titles_fp())
        n_found = sum(1 for v in fb["library"].values() if v.get("picked"))
        msg = (f"✅ Facebook juda: Page '{fb['page']}' → @{fb['ig_username']} (token: {fb['token_kind']}). "
               f"Library mein {n_found}/{len(fb['library'])} gaane tumhare naam se mile.")
        log(msg)
        telegram(msg)
    except (SetupError, IGError) as e:
        fb["error"] = str(e)[:300]
        log(f"❌ Facebook setup: {e}")
        telegram(f"❌ Facebook setup nahi hua: {e}")
    except Exception as e:  # noqa: BLE001
        fb["error"] = repr(e)[:300]
        log(f"❌ Facebook setup (anjaan): {e!r}")


def library_scan(token: str, ig_id: str) -> dict:
    """Har MP3 gaane ke naam se Instagram music library search. ARTIST_NAME ho to usi artist ka gaana
    "picked" hota hai aur songs.json mein audio_id jud jaata hai; warna sirf list (koi gaana apne aap nahi lagta)."""
    artist = (config.ARTIST_NAME or "").strip().casefold()
    out: dict = {}
    for title in _scan_titles():
        q = f"{title} {config.ARTIST_NAME}".strip() if artist else title
        try:
            res = _fb_get("ig_audio", token, audio_type="music", user_id=ig_id, search_query=q)
        except IGError as e:
            out[title] = {"error": str(e)[:120]}
            continue
        items = res.get("audio") or res.get("data") or []
        cands = []
        for a in items[:8]:
            cands.append({"audio_id": str(a.get("audio_id") or a.get("id") or ""), "title": a.get("title") or "",
                          "artist": a.get("display_artist") or "",
                          "sec": int((a.get("duration_in_ms") or 0) / 1000)})
        good = [c for c in cands if c["audio_id"] and _title_match(title, c["title"])]
        picked = next((c for c in good if artist and artist in c["artist"].casefold()), None)
        out[title] = {"candidates": good[:4] or cands[:3], "picked": picked}
    attach_library(out)
    return out


def attach_library(scan: dict) -> int:
    """"picked" gaano ka audio_id songs.json mein likho (MP3 bhi saath rehti hai — fail ho to MP3 wali reel)."""
    data = load_json(SONGS_FILE, {"songs": []})
    data.setdefault("songs", [])
    by_title = {s.get("title"): s for s in data["songs"] if isinstance(s, dict)}
    files = {s["title"]: s for s in load_songs()}
    n = 0
    for title, v in scan.items():
        c = (v or {}).get("picked")
        if not c:
            continue
        row = by_title.get(title)
        if row is None:
            src = files.get(title) or {}
            row = {"title": title, "deity": src.get("deity", ""), "mp3": src.get("mp3", ""), "mp3_start": "auto"}
            data["songs"].append(row)
            by_title[title] = row
        if str(row.get("audio_id") or "") != c["audio_id"]:
            row["audio_id"] = c["audio_id"]
            row["library_title"] = f"{c['title']} — {c['artist']}"
            n += 1
    if n:
        save_json(SONGS_FILE, data)
    return n


def fb_client(st: dict) -> "Instagram | None":
    """Library gaane wali reel ke liye Facebook Login client (setup ho chuka ho tab)."""
    if config.LOGIN_TYPE == "facebook":
        return ig_client()
    fb = st.get("fb") or {}
    if not (fb.get("ok") and fb.get("ig_id")):
        return None
    tok = env("FB_PAGE_TOKEN") if fb.get("token_kind") == "page" else env("FB_ACCESS_TOKEN")
    if not tok and fb.get("token_kind") == "page" and env("FB_ACCESS_TOKEN"):
        try:  # Page token secret mein save nahi hua — user token se abhi nikaal lo
            pages = _fb_get("me/accounts", env("FB_ACCESS_TOKEN"), limit=50,
                            fields="access_token,instagram_business_account{id}").get("data", [])
            tok = next((p.get("access_token") for p in pages
                        if str((p.get("instagram_business_account") or {}).get("id")) == fb["ig_id"]), "")
        except IGError as e:
            log(f"   Page token nahi mila: {e}")
    if not tok:
        return None
    key = (tok, fb["ig_id"])
    if key not in _FB_CACHE:
        _FB_CACHE[key] = Instagram(tok, fb["ig_id"], kind="facebook")
    return _FB_CACHE[key]


# ===================================================================== telegram
def telegram(text: str) -> None:
    tok, chat = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return
    try:
        import requests
        requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                      json={"chat_id": chat, "text": text[:3900], "disable_web_page_preview": True}, timeout=20)
    except Exception as e:  # noqa: BLE001
        log(f"Telegram message nahi gaya: {e}")


def token_days_left() -> float | None:
    """FB_APP_ID + FB_APP_SECRET ho to token kitne din aur chalega (None = pata nahi / kabhi expire nahi)."""
    if not (env("FB_APP_ID") and env("FB_APP_SECRET") and env("IG_ACCESS_TOKEN")):
        return None
    try:
        import requests
        d = requests.get(f"https://graph.facebook.com/{config.GRAPH_VERSION}/debug_token", params={
            "input_token": env("IG_ACCESS_TOKEN"),
            "access_token": f"{env('FB_APP_ID')}|{env('FB_APP_SECRET')}"}, timeout=30).json().get("data", {})
        exp = d.get("expires_at") or 0
        if not exp:
            return None
        return (exp - time.time()) / 86400
    except Exception:  # noqa: BLE001
        return None


def _fp(tok: str) -> str:
    return hashlib.sha256(tok.encode()).hexdigest()[:16]


def token_age_days(st: dict) -> float | None:
    """Ye token pehli baar kab dikha tha — usse kitne din hue (state mein sirf fingerprint, token nahi)."""
    tok = env("IG_ACCESS_TOKEN")
    if not tok:
        return None
    fp = _fp(tok)
    seen = st.get("token_seen") or {}
    if fp not in seen:
        st["token_seen"] = {fp: now_local().isoformat(timespec="seconds")}
        return 0.0
    return (now_local() - dt.datetime.fromisoformat(seen[fp])).total_seconds() / 86400


def token_refresh_due(st: dict) -> bool:
    if config.LOGIN_TYPE != "instagram" or not (env("GH_PAT") and env("GITHUB_REPOSITORY")):
        return False
    age = token_age_days(json.loads(json.dumps(st)))
    return age is not None and age >= config.TOKEN_REFRESH_DAYS


def update_github_secret(name: str, value: str) -> bool:
    """GitHub secret ko API se badlo (GH_PAT: fine-grained token, 'Secrets: Read and write')."""
    pat, repo = env("GH_PAT"), env("GITHUB_REPOSITORY")
    if not (pat and repo):
        return False
    try:
        import requests
        from nacl import encoding, public
        h = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json",
             "X-GitHub-Api-Version": "2022-11-28"}
        k = requests.get(f"https://api.github.com/repos/{repo}/actions/secrets/public-key", headers=h, timeout=30)
        k.raise_for_status()
        key = k.json()
        box = public.SealedBox(public.PublicKey(key["key"].encode(), encoding.Base64Encoder()))
        enc = base64.b64encode(box.encrypt(value.encode())).decode()
        r = requests.put(f"https://api.github.com/repos/{repo}/actions/secrets/{name}", headers=h, timeout=30,
                         json={"encrypted_value": enc, "key_id": key["key_id"]})
        return r.status_code in (201, 204)
    except Exception as e:  # noqa: BLE001
        log(f"GitHub secret update nahi hua: {e}")
        return False


def maybe_refresh_token(st: dict) -> None:
    """Instagram Login token 60 din chalta hai — har TOKEN_REFRESH_DAYS din mein naya karke secret mein daal do."""
    if config.LOGIN_TYPE != "instagram":
        return
    age = token_age_days(st)
    if age is None or age < config.TOKEN_REFRESH_DAYS:
        return
    today = now_local().date().isoformat()
    if not (env("GH_PAT") and env("GITHUB_REPOSITORY")):
        if age >= 50 and st.get("token_warned") != today:
            telegram(f"⚠ Instagram token {age:.0f} din purana hai (60 pe expire). GH_PAT secret daal do taaki "
                     f"agent khud naya kare — ya README Step 2 se naya token banao.")
            st["token_warned"] = today
        return
    try:
        import requests
        r = requests.get("https://graph.instagram.com/refresh_access_token",
                         params={"grant_type": "ig_refresh_token", "access_token": env("IG_ACCESS_TOKEN")}, timeout=30)
        new = (r.json() or {}).get("access_token")
    except Exception as e:  # noqa: BLE001
        new = None
        log(f"token refresh error: {e}")
    if new and update_github_secret("IG_ACCESS_TOKEN", new):
        os.environ["IG_ACCESS_TOKEN"] = new
        st["token_seen"] = {_fp(new): now_local().isoformat(timespec="seconds")}
        log("🔑 Instagram token naya ho gaya (agle 60 din)")
    elif st.get("token_warned") != today:
        telegram("⚠ Instagram token apne aap naya nahi ho paya — GH_PAT secret check karo (README Step 4).")
        st["token_warned"] = today


# ===================================================================== core: one reel
def render_for(plan: dict, path: str, with_mp3: bool) -> dict:
    from render import render_reel
    god = plan.get("god") or god_for(plan["deity"], plan["song"])
    song = plan["song"]
    return render_reel(
        path, plan["photo"], plan["mantra"], plan["bottom"],
        seconds=float(config.REEL_SECONDS), fps=config.REEL_FPS, seed=plan["seed"] % (2**31),
        theme=god.get("theme"),
        audio_mp3=song["mp3_path"] if with_mp3 else None,
        audio_start=audio_start_for(song, plan["seed"]) if with_mp3 else 0.0,
    )


def audio_start_for(song: dict, seed: int) -> float:
    """songs.json mein mp3_start number ho to wahi; warna gaane ka sabse jandaar hissa (hook) khud dhundo."""
    v = song.get("mp3_start", "auto")
    if isinstance(v, (int, float)) or (isinstance(v, str) and v.replace(".", "", 1).isdigit()):
        return float(v)
    from render import find_hook_starts
    # "mp3_range": [start, end] ya kai hisse [[s1, e1], [s2, e2]] — sirf in saaf hisson se (lambi video wali audio)
    rng_ = song.get("mp3_range")
    if isinstance(rng_, (list, tuple)) and rng_ and all(isinstance(r, (list, tuple)) and len(r) == 2 for r in rng_):
        ranges = [(float(a), float(b)) for a, b in rng_]
    elif isinstance(rng_, (list, tuple)) and len(rng_) == 2:
        ranges = [(float(rng_[0]), float(rng_[1]))]
    else:
        ranges = [(None, None)]
    starts = []
    for lo, hi in ranges:
        starts += find_hook_starts(song["mp3_path"], float(config.REEL_SECONDS), lo_s=lo, hi_s=hi)
    return random.Random(seed).choice(starts) if starts else 0.0


NOT_SONG_ERRORS = {-1, 1, 2, 4, 9, 10, 17, 190, 200, 341}   # -1 = upload/processing ki galti


# ===================================================================== video ko public link pe rakhna
# Instagram Login mein video seedha upload nahi hota — Instagram ek public link se khud download karta hai.
# Isliye GitHub pe hi thodi der ke liye rakhte hain (post hote hi hata dete hain).
MEDIA_TAG = "reels-media"        # GitHub Release jisme video asset rakhte hain
MEDIA_BRANCH = "reels-media"     # backup: alag branch, raw.githubusercontent.com link


def _github():
    tok, repo = env("GITHUB_TOKEN"), env("GITHUB_REPOSITORY")
    if not (tok and repo):
        raise SetupError("GITHUB_TOKEN/GITHUB_REPOSITORY nahi mile — video link sirf GitHub Actions mein banta hai.")
    import requests
    h = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    return requests, repo, h


def host_release(path: str):
    """Video ko GitHub Release asset banao → public download link."""
    rq, repo, h = _github()
    api = f"https://api.github.com/repos/{repo}"
    r = rq.get(f"{api}/releases/tags/{MEDIA_TAG}", headers=h, timeout=30)
    if r.status_code == 404:
        r = rq.post(f"{api}/releases", headers=h, timeout=30, json={
            "tag_name": MEDIA_TAG, "name": "Reels media (agent — temporary)", "prerelease": True,
            "make_latest": "false",
            "body": "Agent har reel ki video yahan kuch minute ke liye rakhta hai taaki Instagram use download "
                    "kar sake. Post hote hi file hat jaati hai. Ise delete mat karna."})
    if r.status_code >= 400:
        raise RuntimeError(f"release nahi bana: HTTP {r.status_code} {r.text[:200]}")
    rel = r.json()
    for a in rel.get("assets") or []:          # pichhli adhuri files saaf
        rq.delete(f"{api}/releases/assets/{a['id']}", headers=h, timeout=30)
    name = os.path.basename(path)
    with open(path, "rb") as fh:
        blob = fh.read()
    up = rq.post(f"https://uploads.github.com/repos/{repo}/releases/{rel['id']}/assets", params={"name": name},
                 headers={**h, "Content-Type": "video/mp4"}, data=blob, timeout=300)
    if up.status_code >= 400:
        raise RuntimeError(f"release upload fail: HTTP {up.status_code} {up.text[:200]}")
    asset = up.json()

    def cleanup():
        try:
            rq.delete(f"{api}/releases/assets/{asset['id']}", headers=h, timeout=30)
        except Exception:  # noqa: BLE001
            pass
    return asset["browser_download_url"], cleanup


def host_branch(path: str):
    """Backup: video ko ek alag branch pe push karo → raw.githubusercontent.com ka seedha link."""
    import subprocess
    import urllib.parse
    import requests
    repo = env("GITHUB_REPOSITORY")
    if not repo:
        raise SetupError("GITHUB_REPOSITORY nahi mila")
    name = os.path.basename(path)
    base = BASE_DIR

    def git(*a, inp=None):
        return subprocess.run(["git", "-C", base, *a], input=inp, capture_output=True, text=True,
                              check=True).stdout.strip()
    blob = git("hash-object", "-w", path)
    tree = git("mktree", inp=f"100644 blob {blob}\t{name}\n")
    commit = git("-c", "user.name=ig-reels-bot", "-c", "user.email=ig-reels-bot@users.noreply.github.com",
                 "commit-tree", tree, "-m", "reel video (temporary)")
    git("push", "--force", "origin", f"{commit}:refs/heads/{MEDIA_BRANCH}")
    url = f"https://raw.githubusercontent.com/{repo}/{MEDIA_BRANCH}/{urllib.parse.quote(name)}"
    for _ in range(12):  # raw link chalu hone tak ruko
        try:
            if requests.head(url, timeout=20, allow_redirects=True).status_code == 200:
                break
        except requests.RequestException:
            pass
        time.sleep(5)

    def cleanup():
        subprocess.run(["git", "-C", base, "push", "origin", f":refs/heads/{MEDIA_BRANCH}"],
                       capture_output=True, text=True)
    return url, cleanup


HOSTS = {"release": host_release, "branch": host_branch}
ACCOUNT_ERRORS = {4, 9, 10, 17, 32, 190, 200, 341, 613}   # in pe doosra link try karna bekaar


def make_container(ig: "Instagram", st: dict, path: str, caption: str, audio_id: str | None):
    """Container banao aur Instagram ke process karne tak ruko. Return: (container_id, cleanup, host)."""
    order = sorted(HOSTS, key=lambda h: h != st.get("host_ok"))   # jo pichhli baar chala wo pehle
    last = None
    for host in order:
        try:
            url, cleanup = HOSTS[host](path)
        except Exception as e:  # noqa: BLE001
            log(f"   video link ({host}) nahi bana: {e}")
            last = IGError(f"video link nahi bana ({host}): {e}", -1)
            continue
        log(f"   video link ({host}): {url}")
        try:
            cid, _ = ig.create_reel(caption, audio_id, video_url=url)
        except IGError as e:
            cleanup()
            if e.code in ACCOUNT_ERRORS or (audio_id and "audio" in str(e).lower()):
                raise                        # token/limit/gaane ki dikkat — doosra link bhi nahi chalega
            log(f"   Instagram ne {host} link nahi maana: {e}")
            e.code = e.code or -1
            last = e
            continue
        try:
            ig.wait_ready(cid)
        except IGError as e:   # Instagram is link se video nahi utha paya — doosra tareeka try karo
            cleanup()
            log(f"   Instagram ne {host} link se video nahi liya: {e}")
            e.code = e.code or -1
            last = e
            continue
        st["host_ok"] = host
        return cid, cleanup, host
    raise last or IGError("video link nahi bana", -1)


def song_problem(e: IGError) -> bool:
    """Error gaane (audio_id) ki wajah se hai, token/limit ki wajah se nahi?"""
    return e.code not in NOT_SONG_ERRORS and e.subcode != 2207042


def check_mode() -> None:
    if config.LOGIN_TYPE == "instagram" and config.AUDIO_MODE == "library" and not env("FB_ACCESS_TOKEN"):
        raise SetupError("Instagram Login mein library ka gaana attach nahi hota — config.py mein AUDIO_MODE = \"mp3\" karo "
                         "(ya FB Page jod ke LOGIN_TYPE = \"facebook\").")


def post_reel(st: dict, slot_key: str, now: dt.datetime) -> dict:
    check_mode()
    songs = usable_songs(load_songs(), st)
    if not songs:
        raise SetupError("koi gaana ready nahi — music/ folder mein MP3 daalo"
                         + (" (ya '--find-songs' se library gaane jodo)." if config.AUDIO_MODE == "library" else "."))
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"reel_{slot_key.replace('#', '_')}.mp4")
    ig = ig_client()
    gap = dt.timedelta(minutes=max(getattr(config, "MIN_GAP_MINUTES", 0), 5))
    try:   # pakka karo ki abhi-abhi koi reel nahi gayi (state purani ho to bhi double post na ho)
        last_at, last_link = ig.last_post()
        if last_at and now - last_at < gap:
            raise RecentlyPosted(f"Instagram pe {last_at.astimezone(now.tzinfo):%H:%M} baje reel gayi thi "
                                 f"({last_link}) — {slot_key} chhod raha hoon, double post nahi karunga")
    except IGError as e:
        log(f"   (pichhli post ka time nahi mila: {e} — aage badh raha hoon)")
    tried: set[str] = set()

    for attempt in range(3):  # gaana attach na ho to doosre gaane se dobara
        pool = [s for s in songs if s["title"] not in tried]
        if not pool:
            break
        plan = choose_content(st, now, f"{slot_key}~{attempt}" if attempt else slot_key, pool)
        song = plan["song"]
        tried.add(song["title"])
        caption = make_caption(plan, st)
        fbc = fb_client(st) if (library_on() and song.get("audio_id")) else None
        use_library = (fbc is not None and st["song_fail"].get(str(song.get("audio_id")), 0) < 2)
        client = fbc if use_library else ig
        log(f"🎬 {slot_key}: '{song['title']}' ({plan['deity']}) | photo: "
            f"{os.path.relpath(plan['photo'], BASE_DIR) if plan['photo'] else 'mantra-art'} | "
            f"audio: {'library' if use_library else 'mp3'}")

        t0 = time.time()
        info = render_for(plan, path, with_mp3=not use_library)
        log(f"   video bana: {info['mode']}, {info['bytes'] / 1e6:.1f} MB, {time.time() - t0:.0f}s")

        audio_used = "library" if use_library else "mp3"
        try:
            cid, cleanup, host = make_container(client, st, path, caption, song.get("audio_id") if use_library else None)
        except IGError as e:
            if not (use_library and song_problem(e)):
                raise
            aid = str(song["audio_id"])
            st["song_fail"][aid] = st["song_fail"].get(aid, 0) + 1
            if config.FALLBACK_TO_MP3 and song["mp3_path"]:
                log(f"   gaana attach nahi hua ({e}) — MP3 wali reel bana raha hoon")
                render_for(plan, path, with_mp3=True)
                client = ig
                cid, cleanup, host = make_container(ig, st, path, caption, None)
                audio_used = "mp3"
            else:
                log(f"   '{song['title']}' attach nahi hua ({e}) — doosra gaana try kar raha hoon")
                if st["song_fail"][aid] == 2 and config.NOTIFY_ON_ERROR:
                    telegram(f"⚠ Gaana '{song['title']}' (audio_id {aid}) Instagram pe attach nahi ho raha — "
                             f"ab ye skip hoga. songs.json mein audio_id check karo ya MP3 jodo.")
                continue
        try:
            media_id = client.publish(cid)
        finally:
            cleanup()
        link = client.permalink(media_id)
        log(f"   ✅ post ho gayi: {link or media_id}")
        if use_library and audio_used == "library":
            st["song_fail"].pop(str(song["audio_id"]), None)

        mark_used(st, plan)
        st["captions"].append(caption.split("\n\n#")[0])
        st["posted"].append({
            "slot": slot_key, "at": now_local().isoformat(timespec="seconds"),
            "song": song["title"], "deity": plan["deity"],
            "photo": os.path.relpath(plan["photo"], BASE_DIR) if plan["photo"] else None,
            "mantra": plan["mantra"], "audio": audio_used, "media_id": media_id, "permalink": link,
            "host": host,
        })
        try:
            os.remove(path)
        except OSError:
            pass
        if config.NOTIFY_ON_SUCCESS:
            telegram(f"✅ Reel post hui: {song['title']}\n{link}")
        return st["posted"][-1]
    raise IGError(f"{len(tried)} gaane try kiye, koi attach nahi hua: {', '.join(sorted(tried))}")


def run_once(force: bool = False) -> int:
    st = load_state()
    now = now_local()
    maybe_refresh_token(st)
    if fb_setup_due(st, now):
        fb_setup(st, now)
    if force:
        slot = (f"{now.date().isoformat()}#m{now:%H%M%S}", now)
    else:
        slot = due_slot(st, now)
    rc = 0
    if slot:
        key = slot[0]
        st["attempts"][key] = st["attempts"].get(key, 0) + 1
        try:
            post_reel(st, key, now)
        except RecentlyPosted as e:
            log(f"⏭ {e}")
            st["skipped"].append(key)
        except (SetupError, IGError) as e:
            rc = 1
            hint = getattr(e, "hint", "")
            msg = f"❌ Reel post nahi hui ({key}): {e}" + (f"\n👉 {hint}" if hint else "")
            log(msg)
            st["errors"].append({"slot": key, "at": now.isoformat(timespec="seconds"), "error": str(e)[:300]})
            if config.NOTIFY_ON_ERROR:
                telegram(msg)
            if not force and st["attempts"][key] >= 2:
                st["skipped"].append(key)
                log(f"   {key} do baar fail — ab skip")
        except Exception as e:  # noqa: BLE001 — anjaan galti: state bacha ke rakho
            rc = 1
            log(f"❌ anjaan galti: {e!r}")
            st["errors"].append({"slot": key, "at": now.isoformat(timespec="seconds"), "error": repr(e)[:300]})
            if config.NOTIFY_ON_ERROR:
                telegram(f"❌ Agent mein galti ({key}): {e!r}"[:500])
            if not force and st["attempts"][key] >= 2:
                st["skipped"].append(key)
    else:
        log("abhi koi slot due nahi")

    if summary_due(st, now):
        today = now.date().isoformat()
        posted = [p for p in st["posted"] if p["slot"].startswith(today)]
        skipped = [s for s in st["skipped"] if s.startswith(today)]
        lines = [f"📊 Aaj ka hisaab ({today}): {len(posted)}/{config.POSTS_PER_DAY} reels post hui"]
        if skipped:
            lines.append(f"⏭ skip: {len(skipped)}")
        for p in posted[-15:]:
            lines.append(f"• {p['at'][11:16]} {p['song']} ({p['audio']})")
        days = token_days_left()
        if days is not None and days < 10:
            lines.append(f"⚠ Instagram token {days:.0f} din mein expire hoga — README se naya banao!")
        telegram("\n".join(lines))
        st["summary_sent"] = today
    save_state(st)
    return rc


# ===================================================================== other commands
def cmd_due() -> int:
    st = load_state()
    now = now_local()
    ready = bool(env("IG_ACCESS_TOKEN") and (env("IG_USER_ID") or config.LOGIN_TYPE == "instagram"))
    try:
        ready = ready and bool(usable_songs(load_songs(), st))
    except SetupError:
        ready = False
    slot = due_slot(st, now, mark=False) if ready else None
    due = bool(slot) or summary_due(st, now) or token_refresh_due(st) or fb_setup_due(st, now)
    if not ready and not config.PAUSED:
        print("setup abhi poora nahi (secrets/gaane) — scheduled posting ruki hai")
    print(f"due={'true' if due else 'false'}" + (f"  (slot {slot[0]} @ {slot[1]:%H:%M})" if slot else ""))
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a") as fh:
            fh.write(f"due={'true' if due else 'false'}\n")
    return 0


def cmd_schedule() -> int:
    st = load_state()
    now = now_local()
    posted = {p["slot"]: p for p in st["posted"]}
    skipped = set(st["skipped"])
    print(f"Aaj {now:%d %b %Y} ({HINDI_DAYS[now.weekday()]}) — {config.POSTS_PER_DAY} slots, "
          f"din ke bhagwan: {', '.join(config.DAY_DEITY.get(now.weekday(), []))}")
    if config.PAUSED:
        print("⏸ PAUSED = True — posting band hai")
    for key, t in day_slots(now.date()):
        status = ("✅ " + posted[key]["song"]) if key in posted else ("⏭ skip" if key in skipped else
                                                                       ("⏳ due" if t <= now else "· baaki"))
        print(f"  {t:%H:%M}  {key}  {status}")
    return 0


def cmd_preview(n: int) -> int:
    st = load_state()
    now = now_local()
    songs = usable_songs(load_songs())
    if not songs:  # gaane abhi set nahi — demo ke liye har bhagwan ka ek nakli gaana
        from render import list_photos
        gods = [g for g in config.DEITIES if list_photos(os.path.join(PHOTOS_DIR, g))] or ["shiv", "krishna", "general"]
        songs = [{"title": f"(demo) {config.DEITIES[g]['name']} भजन", "deity": g, "mp3_path": "", "audio_id": ""} for g in gods]
        log("songs.json abhi khaali — demo gaano se preview bana raha hoon")
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    sim = json.loads(json.dumps(st))
    for i in range(n):
        key = f"preview-{now:%Y%m%d}-{i + 1}"
        plan = choose_content(sim, now, key, songs)
        caption = make_caption(plan, sim)
        path = os.path.join(PREVIEW_DIR, f"preview_{i + 1}.mp4")
        has_mp3 = bool(plan["song"].get("mp3_path")) and not (library_on() and plan["song"].get("audio_id"))
        t0 = time.time()
        info = render_for(plan, path, with_mp3=has_mp3)
        with open(path[:-4] + "_caption.txt", "w", encoding="utf-8") as fh:
            fh.write(f"Gaana: {plan['song']['title']}\nBhagwan: {plan['deity']}\n"
                     f"Photo: {os.path.relpath(plan['photo'], BASE_DIR) if plan['photo'] else 'mantra-art'}\n\n{caption}\n")
        mark_used(sim, plan)
        sim["captions"].append(caption.split("\n\n#")[0])
        log(f"preview {i + 1}: {info['mode']} | {plan['song']['title']} | {time.time() - t0:.0f}s -> {os.path.relpath(path, BASE_DIR)}")
    return 0


def cmd_check() -> int:
    from render import HAS_RAQM, find_ffmpeg
    ok = True
    print("── Setup check ──")
    print(f"• Hindi text shaping (raqm): {'✅' if HAS_RAQM else '❌ libraqm/fribidi install karo — Hindi akshar toot jaayenge'}")
    try:
        print(f"• ffmpeg: ✅ {find_ffmpeg()}")
    except RuntimeError as e:
        ok = False
        print(f"• ffmpeg: ❌ {e}")
    from render import list_photos
    counts = {g: len(list_photos(os.path.join(PHOTOS_DIR, g))) for g in config.DEITIES}
    print("• Photos: " + ", ".join(f"{g}={c}" for g, c in counts.items() if c) if any(counts.values())
          else "• Photos: ⚠ koi photo nahi — sab reels mandala-ॐ style mein banengi")
    songs = load_songs()
    use = usable_songs(songs)
    print(f"• Gaane: {len(songs)} mile (music/ + songs.json), {len(use)} post karne layak")
    by_god = {}
    for s in use:
        by_god[s["deity"]] = by_god.get(s["deity"], 0) + 1
    if by_god:
        print("   " + ", ".join(f"{g}={c}" for g, c in by_god.items()))
        waiting = [g for g in by_god if not has_visual(g)]
        if waiting:
            print(f"   ⏸ photos ka intezaar (inke gaane abhi post nahi honge): {', '.join(waiting)}")
    print(f"• Login: {config.LOGIN_TYPE} | Audio: {config.AUDIO_MODE}")
    try:
        check_mode()
    except SetupError as e:
        ok = False
        print(f"   ❌ {e}")
    print(f"• Claude caption: {'✅ key mili' if env('ANTHROPIC_API_KEY') else '⚠ ANTHROPIC_API_KEY nahi — templates use honge'}")
    print(f"• Telegram: {'✅' if env('TELEGRAM_BOT_TOKEN') and env('TELEGRAM_CHAT_ID') else '— (optional, set nahi)'}")

    try:
        ig = ig_client()
        acc = ig.account()
        print(f"• Instagram: ✅ @{acc.get('username')} ({acc.get('followers_count', '?')} followers, {acc.get('media_count', '?')} posts)")
        used, total = ig.quota()
        print(f"• Publishing limit: {used}/{total} (pichhle 24 ghante)")
        if config.POSTS_PER_DAY > total:
            ok = False
            print(f"   ❌ POSTS_PER_DAY ({config.POSTS_PER_DAY}) limit se zyada hai")
    except (SetupError, IGError) as e:
        ok = False
        print(f"• Instagram: ❌ {e}" + (f"\n   👉 {e.hint}" if getattr(e, 'hint', '') else ""))
        ig = None

    if config.LOGIN_TYPE == "instagram" and env("IG_ACCESS_TOKEN"):
        st = load_state()
        age = token_age_days(st)
        save_state(st)
        auto = env("GH_PAT") and env("GITHUB_REPOSITORY")
        print(f"• Token: ~{age:.0f} din purana (60 din pe expire) — auto-refresh: "
              + (f"✅ har {config.TOKEN_REFRESH_DAYS} din" if auto else "❌ GH_PAT secret nahi — 50 din pe Telegram yaad dilayega"))
    if config.LOGIN_TYPE == "facebook" and env("FB_APP_ID") and env("FB_APP_SECRET") and env("IG_ACCESS_TOKEN"):
        try:
            import requests
            d = requests.get(f"https://graph.facebook.com/{config.GRAPH_VERSION}/debug_token", params={
                "input_token": env("IG_ACCESS_TOKEN"),
                "access_token": f"{env('FB_APP_ID')}|{env('FB_APP_SECRET')}"}, timeout=30).json().get("data", {})
            exp = d.get("expires_at", 0)
            when = "kabhi nahi ✅" if not exp else dt.datetime.fromtimestamp(exp, TZ).strftime("%d %b %Y")
            print(f"• Token: type={d.get('type')}, expire: {when}, valid={d.get('is_valid')}")
            if exp and dt.datetime.fromtimestamp(exp, TZ) - now_local() < dt.timedelta(days=10):
                print("   ⚠ token jaldi expire hoga — README se naya banao")
        except Exception as e:  # noqa: BLE001
            print(f"• Token debug nahi hua: {e}")

    if ig and config.AUDIO_MODE == "library":
        lib = [s for s in songs if s.get("audio_id")][:20]
        if not lib:
            print("• Library gaane: ⚠ kisi gaane ka audio_id nahi — '--find-songs \"artist naam\" --save' chalao")
        for s in lib:
            try:
                a = ig.audio_info(s["audio_id"])
                print(f"   ✅ {s['title']}  →  {a.get('title')} / {a.get('display_artist')}")
            except IGError as e:
                ok = False
                print(f"   ❌ {s['title']} (audio_id {s['audio_id']}): {e}")
    fb = load_state().get("fb") or {}
    if env("FB_ACCESS_TOKEN") or fb:
        if fb.get("ok"):
            lib = fb.get("library") or {}
            print(f"• Facebook (library gaana): ✅ Page '{fb.get('page')}' → @{fb.get('ig_username')}, token={fb.get('token_kind')}, "
                  f"{sum(1 for v in lib.values() if (v or {}).get('picked'))}/{len(lib)} gaane library se")
        elif fb.get("error"):
            print(f"• Facebook (library gaana): ❌ {fb['error']}")
        else:
            print("• Facebook (library gaana): ⏳ agle run mein setup hoga")
    if env("TELEGRAM_BOT_TOKEN"):
        telegram("✅ IG Reels Agent: setup check chala. " + ("Sab theek!" if ok else "Kuch problem hai — GitHub log dekho."))
    print("── Result:", "✅ sab theek" if ok else "❌ upar ki problems theek karo")
    return 0 if ok else 1


def cmd_find_songs(query: str, save: bool) -> int:
    st = load_state()
    fbc = fb_client(st)
    if config.LOGIN_TYPE == "instagram" and not fbc:
        print("Instagram Login mein music library search nahi hota (sirf Facebook Login mein).")
        print("👉 Apne gaano ki MP3 music/ folder mein daalo — agent unhe apne aap use karega (README Step 6).")
        return 1
    ig = fbc or ig_client()
    res = ig.search_audio(query)
    artist = config.ARTIST_NAME.strip().casefold()
    if not res:
        print(f"'{query}' ke liye Instagram API ne koi gaana nahi diya.")
        print("👉 Ho sakta hai tumhare gaane third-party (API) use ke liye allowed na ho. Doosre naam/gaane ke title se try karo.")
        print("   Na mile to config.py mein AUDIO_MODE = \"mp3\" karke MP3 wala tareeka use karo (README dekho).")
        return 1
    data = load_json(SONGS_FILE, {"songs": []})
    data.setdefault("songs", [])
    have = {str(s.get("audio_id")) for s in data["songs"] if s.get("audio_id")}
    added = 0
    print(f"{'audio_id':<20} {'dur':>5}  title  —  artist")
    for a in res:
        aid = str(a.get("audio_id") or a.get("id") or "")
        title = a.get("title") or "?"
        art = a.get("display_artist") or ""
        dur = int((a.get("duration_in_ms") or 0) / 1000)
        mine = bool(artist) and artist in art.casefold()
        mark = "★" if mine else " "
        print(f"{mark}{aid:<19} {dur:>4}s  {title}  —  {art}")
        if save and mine and aid and aid not in have:
            data["songs"].append({"title": title, "deity": deity_from_text(title), "audio_id": aid,
                                  "artist": art, "mp3": "", "mp3_start": 0, "enabled": True})
            have.add(aid)
            added += 1
    if save:
        if not artist:
            print("\n⚠ --save ke liye pehle config.py mein ARTIST_NAME likho (taaki dusron ke gaane na jud jaayein).")
            return 1
        save_json(SONGS_FILE, data)
        print(f"\n✅ {added} naye gaane songs.json mein jude (★ wale). Har gaane ka 'deity' ek baar check kar lena.")
    else:
        print("\n★ = tumhare ARTIST_NAME se match. Jodne ke liye --save lagao.")
    return 0


# ===================================================================== main
def main(argv=None) -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(description="Instagram devotional reels agent")
    ap.add_argument("--now", action="store_true", help="abhi turant 1 reel post karo")
    ap.add_argument("--preview", type=int, metavar="N", help="N preview reels banao (post nahi)")
    ap.add_argument("--check", action="store_true", help="setup jaancho")
    ap.add_argument("--find-songs", metavar="QUERY", help="Instagram library mein gaane dhundo")
    ap.add_argument("--save", action="store_true", help="--find-songs ke saath: gaane songs.json mein jodo")
    ap.add_argument("--schedule", action="store_true", help="aaj ke slots dikhao")
    ap.add_argument("--due", action="store_true", help="workflow ke liye: kuch karna hai?")
    a = ap.parse_args(argv)
    try:
        if a.due:
            return cmd_due()
        if a.schedule:
            return cmd_schedule()
        if a.preview:
            return cmd_preview(a.preview)
        if a.check:
            return cmd_check()
        if a.find_songs:
            return cmd_find_songs(a.find_songs, a.save)
        return run_once(force=a.now)
    except SetupError as e:
        print(f"❌ {e}")
        return 1
    except IGError as e:
        print(f"❌ Instagram: {e}" + (f"\n👉 {e.hint}" if e.hint else ""))
        return 1


if __name__ == "__main__":
    sys.exit(main())
