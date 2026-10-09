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
import datetime as dt
import hashlib
import json
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
DEITY_MATCH_ORDER = ["premanand", "khatushyam", "hanuman", "ganesh", "lakshmi", "sai", "radha", "ram", "krishna",
                     "shiv", "vishnu", "durga", "general"]


class SetupError(Exception):
    """Setup/config ki galti — user ko saaf message chahiye."""


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
    n = max(1, int(config.POSTS_PER_DAY))
    start = dt.datetime.combine(day, _hhmm(config.DAY_START), TZ)
    end = dt.datetime.combine(day, _hhmm(config.DAY_END), TZ)
    span = (end - start).total_seconds() / 60
    step = span / (n - 1) if n > 1 else 0
    jit = min(config.JITTER_MINUTES, step / 3) if n > 1 else config.JITTER_MINUTES
    out = []
    for i in range(n):
        r = random.Random(_seed(day.isoformat(), i, "slot")).uniform(-jit, jit)
        t = start + dt.timedelta(minutes=i * step + r)
        t = min(max(t, start - dt.timedelta(minutes=jit)), end + dt.timedelta(minutes=jit))
        out.append((f"{day.isoformat()}#{i}", t.replace(second=0, microsecond=0)))
    return out


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


def usable_songs(songs: list[dict], st: dict | None = None) -> list[dict]:
    if config.AUDIO_MODE == "mp3":
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


def choose_content(st: dict, now: dt.datetime, slot_key: str, songs: list[dict]) -> dict:
    rng = random.Random(_seed(slot_key, st["counter"]))
    day_gods = config.DAY_DEITY.get(now.weekday(), [])
    # pichhli kuch reels wale gaane abhi dobara nahi (agar aur gaane hain)
    k = min(4, max(0, len(songs) - 1))
    recent = {p["song"] for p in st["posted"][-k:]} if k else set()
    fresh = [s for s in songs if s["title"] not in recent] or songs
    day_songs = [s for s in fresh if s["deity"] in day_gods]
    pool = day_songs if day_songs and rng.random() < config.DAY_DEITY_SHARE else fresh
    song = lru_pick(pool, lambda s: "song:" + s["title"], st, rng)
    deity = song["deity"]
    god = config.DEITIES[deity]

    photos = photos_for(deity)
    photo = None
    if photos and rng.random() >= god.get("mantra_art_share", config.MANTRA_ART_SHARE):
        photo = lru_pick(photos, lambda p: "photo:" + os.path.relpath(p, BASE_DIR), st, rng)
    mantra = lru_pick(god["mantras"], lambda m: f"mantra:{deity}:{m}", st, rng)
    bottom = lru_pick(config.BOTTOM_LINES, lambda b: "bottom:" + b, st, rng).format(jaikara=god["jaikara"])
    return {
        "slot": slot_key, "song": song, "deity": deity, "photo": photo,
        "mantra": mantra, "bottom": bottom, "seed": _seed(slot_key, "video", st["counter"]),
        "weekday": now.weekday(),
    }


def mark_used(st: dict, plan: dict) -> None:
    st["counter"] += 1
    c = st["counter"]
    lu = st["last_used"]
    lu["song:" + plan["song"]["title"]] = c
    if plan["photo"]:
        lu["photo:" + os.path.relpath(plan["photo"], BASE_DIR)] = c
    lu[f"mantra:{plan['deity']}:{plan['mantra']}"] = c
    for b in config.BOTTOM_LINES:
        if b.format(jaikara=config.DEITIES[plan["deity"]]["jaikara"]) == plan["bottom"]:
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


def pick_hashtags(deity: str, rng: random.Random) -> list[str]:
    god = config.DEITIES[deity]["hashtags"][:]
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
    god = config.DEITIES[plan["deity"]]
    style = ("शुद्ध, सरल हिंदी (देवनागरी)" if config.CAPTION_STYLE == "hindi"
             else "Hinglish (Roman script mein Hindi)")
    system = (
        "Tum 'Om Namoh Bhagwate' naam ke Indian devotional music page ke liye Instagram Reel captions likhte ho. "
        "Page apne khud ke bhajan/mantra gaane post karta hai. Bhasha bhaktipurn, garam aur sacchi ho."
    )
    prev = "\n---\n".join(recent[-5:]) or "(abhi koi nahi)"
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
    god = config.DEITIES[plan["deity"]]
    text = claude_caption(plan, st["captions"])
    if not text:
        fields = dict(jaikara=god["jaikara"], name=god["name"], song=plan["song"]["title"],
                      day=HINDI_DAYS[plan["weekday"]], jaikara_en=god["jaikara"])
        pool = god.get("templates") or (TEMPLATES if config.CAPTION_STYLE == "hindi" else TEMPLATES_HINGLISH)
        recent = set(st["captions"][-3:])
        options = [t.format(**fields) for t in pool]
        fresh = [o for o in options if o not in recent] or options
        text = rng.choice(fresh)
    tags = pick_hashtags(plan["deity"], rng)
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
    def __init__(self, token: str, ig_id: str, version: str = config.GRAPH_VERSION):
        ig_login = config.LOGIN_TYPE == "instagram"
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
        if config.LOGIN_TYPE == "instagram":
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

    def create_reel(self, caption: str, audio_id: str | None = None) -> tuple[str, str]:
        data = dict(media_type="REELS", upload_type="resumable", caption=caption,
                    share_to_feed="true" if config.SHARE_TO_FEED else "false",
                    thumb_offset=str(config.THUMB_OFFSET_MS))
        if audio_id:
            # video ki apni (khamosh) awaaz 0, gaana poori awaaz mein
            data["audio_configuration"] = json.dumps({"audio_id": str(audio_id), "audio_volume": 100, "video_volume": 0})
        d = self.post(f"{self.ig_id}/media", **data)
        cid = d["id"]
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

    def permalink(self, media_id: str) -> str:
        try:
            return self.get(media_id, fields="permalink").get("permalink", "")
        except IGError:
            return ""


def ig_client() -> Instagram:
    return Instagram(env("IG_ACCESS_TOKEN"), env("IG_USER_ID"))


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
    god = config.DEITIES[plan["deity"]]
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
    starts = find_hook_starts(song["mp3_path"], float(config.REEL_SECONDS))
    return random.Random(seed).choice(starts) if starts else 0.0


NOT_SONG_ERRORS = {1, 2, 4, 9, 10, 17, 190, 200, 341}


def song_problem(e: IGError) -> bool:
    """Error gaane (audio_id) ki wajah se hai, token/limit ki wajah se nahi?"""
    return e.code not in NOT_SONG_ERRORS and e.subcode != 2207042


def check_mode() -> None:
    if config.LOGIN_TYPE == "instagram" and config.AUDIO_MODE == "library":
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
    tried: set[str] = set()

    for attempt in range(3):  # gaana attach na ho to doosre gaane se dobara
        pool = [s for s in songs if s["title"] not in tried]
        if not pool:
            break
        plan = choose_content(st, now, f"{slot_key}~{attempt}" if attempt else slot_key, pool)
        song = plan["song"]
        tried.add(song["title"])
        caption = make_caption(plan, st)
        use_library = (config.AUDIO_MODE == "library" and bool(song.get("audio_id"))
                       and st["song_fail"].get(str(song.get("audio_id")), 0) < 2)
        log(f"🎬 {slot_key}: '{song['title']}' ({plan['deity']}) | photo: "
            f"{os.path.relpath(plan['photo'], BASE_DIR) if plan['photo'] else 'mantra-art'} | "
            f"audio: {'library' if use_library else 'mp3'}")

        t0 = time.time()
        info = render_for(plan, path, with_mp3=not use_library)
        log(f"   video bana: {info['mode']}, {info['bytes'] / 1e6:.1f} MB, {time.time() - t0:.0f}s")

        audio_used = "library" if use_library else "mp3"
        try:
            cid, uri = ig.create_reel(caption, song.get("audio_id") if use_library else None)
        except IGError as e:
            if not (use_library and song_problem(e)):
                raise
            aid = str(song["audio_id"])
            st["song_fail"][aid] = st["song_fail"].get(aid, 0) + 1
            if config.FALLBACK_TO_MP3 and song["mp3_path"]:
                log(f"   gaana attach nahi hua ({e}) — MP3 wali reel bana raha hoon")
                render_for(plan, path, with_mp3=True)
                cid, uri = ig.create_reel(caption, None)
                audio_used = "mp3"
            else:
                log(f"   '{song['title']}' attach nahi hua ({e}) — doosra gaana try kar raha hoon")
                if st["song_fail"][aid] == 2 and config.NOTIFY_ON_ERROR:
                    telegram(f"⚠ Gaana '{song['title']}' (audio_id {aid}) Instagram pe attach nahi ho raha — "
                             f"ab ye skip hoga. songs.json mein audio_id check karo ya MP3 jodo.")
                continue
        ig.upload(uri, path)
        ig.wait_ready(cid)
        media_id = ig.publish(cid)
        link = ig.permalink(media_id)
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
    due = bool(slot) or summary_due(st, now) or token_refresh_due(st)
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
        has_mp3 = config.AUDIO_MODE == "mp3" and bool(plan["song"].get("mp3_path"))
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
    if env("TELEGRAM_BOT_TOKEN"):
        telegram("✅ IG Reels Agent: setup check chala. " + ("Sab theek!" if ok else "Kuch problem hai — GitHub log dekho."))
    print("── Result:", "✅ sab theek" if ok else "❌ upar ki problems theek karo")
    return 0 if ok else 1


def cmd_find_songs(query: str, save: bool) -> int:
    if config.LOGIN_TYPE == "instagram":
        print("Instagram Login mein music library search nahi hota (sirf Facebook Login mein).")
        print("👉 Apne gaano ki MP3 music/ folder mein daalo — agent unhe apne aap use karega (README Step 6).")
        return 1
    ig = ig_client()
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
