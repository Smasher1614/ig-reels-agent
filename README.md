# 🙏 Om Namoh Bhagwate — Instagram Reels Agent

Roz automatic devotional reels: **tumhari bhagwan ki photos + tumhare apne gaane + Hindi caption**.
GitHub Actions pe free chalta hai — laptop band ho tab bhi.
**Facebook account/Page ki zarurat nahi** (Instagram Login use hota hai).

---

## Ye kya karta hai

Har slot pe (default: roz 10 baar, subah 5:30 se raat 10:30 tak):

1. **Gaana chunta hai** — `music/` folder ki MP3s mein se, rotate karke (pichhli 4 reels wala gaana dobara nahi). Hafte ke din ke bhagwan ko thoda zyada mauka (Somvar = Shiv, Mangal = Hanuman, …)
2. **Gaane ka sabse jandaar 30 sec hissa** (chorus/hook) khud dhundta hai — har reel mein alag-alag hook
3. **Video banata hai** (1080×1920):
   - **Lambi (portrait) photo** → full screen, dheere zoom/pan
   - **Chaukor/chaudi photo** → sunehre frame mein, peeche blur background
   - **~10% reels bina photo** → ghoomta mandala + bada ॐ (variety ke liye)
   - Upar mantra (जैसे *ॐ नमः शिवाय*), sunehri saans leti roshni, upar uthte chamakte kan, neeche chhoti line
4. **Caption** — Claude naya Hindi caption likhta hai + 5 hashtag (Instagram ab 5 se zyada nahi leta)
5. **Post** — Instagram pe Reel
6. **Token khud naya karta hai** (har 20 din) — tumhe 60 din baad dobara setup nahi karna
7. Kuch galat ho to **Telegram pe message**, raat ko din ka hisaab

---

## ⚠ Ek imaandaar baat — 10-15 reels/din

- **Technically theek hai:** Instagram API 24 ghante mein 50 reels tak allow karta hai.
- **Reach ka risk:** Instagram baar-baar milta-julta content ki reach kam karta hai. 20 photos aur 10 gaano se 300 reels/mahina banengi to bahut si ek jaisi lagengi.
- **Meri salah:** pehla hafta `POSTS_PER_DAY = 5`, Insights mein reach per reel dekho, phir badhao. 10/din ke liye **100+ alag photos** aur **15-20+ gaane** rakho.

---

## Setup (ek baar, ~45 min)

### Step 1 — Instagram account

- Account **Creator ya Business** hona chahiye: Instagram app → Settings → *Account type and tools* → *Switch to professional account*
- Account **Public** ho
- Facebook Page jodne ki **zarurat nahi**

### Step 2 — Meta app aur token (Instagram Login)

1. <https://developers.facebook.com> pe login karo → developer account banao (pehli baar ho to)
   - Tumhara FB sirf ads ke liye restricted hai to developer account aam taur pe ban jaata hai. Agar ye bhi block ho → neeche **"Developer account na bane to"** dekho
2. **My Apps → Create App** → naam (jaise `ONB Reels`) + email
3. Use case mein **"Manage messaging & content on Instagram"** chuno → Create
4. App dashboard → **Instagram → API setup with Instagram login**
5. **Generate access tokens** wale hisse mein **Add account** → Om Namoh Bhagwate ke Instagram se login → Allow
   - Agar "tester invite" maange: App roles → Roles → **Instagram Testers** mein apna username add karo, phir Instagram app → Settings → *Website permissions* → *Apps and websites* → **Tester invites** → Accept. Phir dobara *Add account*
6. Account ke saamne **Generate token** → token copy karo (ye 60 din chalta hai — agent khud naya karta rahega)

> Dashboard Business Verification jaisa kuch maange to mujhe batao — us hisaab se rasta nikaalenge.

### Step 3 — GitHub repo

1. GitHub → **New repository** → naam `ig-reels-agent` → **Public** (public pe Actions free hai; secrets phir bhi chhupe rehte hain)
2. Repo page pe *uploading an existing file* → is folder ki **saari files aur folders** drag-drop karo (`.github` folder bhi!) → *Commit changes*

### Step 4 — Secrets daalo

Repo → **Settings → Secrets and variables → Actions → New repository secret**

| Naam | Kya daalna hai | Zaruri? |
|---|---|---|
| `IG_ACCESS_TOKEN` | Step 2 ka token | ✅ |
| `GH_PAT` | GitHub token (neeche dekho) — isse agent Instagram token khud naya karta hai | ✅ (warna har 60 din manual) |
| `ANTHROPIC_API_KEY` | Claude API key (X agent wali chalegi) | caption ke liye |
| `TELEGRAM_BOT_TOKEN` | X agent wala Telegram bot token | optional |
| `TELEGRAM_CHAT_ID` | X agent wala chat ID | optional |

**GH_PAT kaise banaye:**
GitHub → profile photo → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**
- Expiration: 1 year
- Repository access: **Only select repositories** → `ig-reels-agent`
- Permissions → Repository permissions → **Secrets: Read and write**
- *Generate token* → copy → `GH_PAT` secret mein daalo

### Step 5 — Photos daalo

`photos/` mein har bhagwan ka folder hai:

`premanand` · `radha` · `shiv` · `krishna` · `khatushyam` · `ram` · `hanuman` · `ganesh` · `durga` · `vishnu` · `lakshmi` · `sai` · `general`

- GitHub pe folder kholo (jaise `photos/shiv`) → *Add file → Upload files*
- **Lambi (9:16 / portrait) photo sabse achhi** — full screen dikhti hai
- `general` mein mandir, diya, ॐ jaisi photos — jis bhagwan ka folder khaali ho uske gaane ke saath ye lagti hain
- Apni banayi (ya AI se khud banayi) photos use karo — doosre channels ki watermark wali photos se reach aur copyright dono ka risk

### Step 6 — Gaane (MP3) daalo

`music/` folder mein MP3 upload karo. Bhagwan ke hisaab se folder bana sakte ho — `music/shiv/`, `music/krishna/` … (GitHub pe *Add file → Upload files* → naam mein `shiv/` likh ke folder ban jaata hai)

- **File ka naam = gaane ka naam** (caption mein yahi aayega), jaise `Om Namah Shivay Dhun.mp3`
- **Premanand Ji Maharaj** wali reels ke liye bhajan ka naam `Radha Naam Jap.mp3` rakho — naam mein "naam jap" hai to wo apne aap Maharaj ji ki photos ke saath lagega
- MP3 nahi hai? **Video file bhi chalegi** (`.mp4`, `.webm`, `.mov`) — jaise YouTube Studio → Content → apni video ke ⋮ → *Download*. Agent video se awaaz khud nikaal leta hai
- `songs.json` chhedne ki zarurat **nahi** — agent music/ ki har MP3 khud utha leta hai
- Folder ke bina daali to agent naam se bhagwan pehchaanta hai (Shiv/Mahadev/Bhole → shiv, Radhe/Shyam → krishna …)
- Gaane ka **sabse jandaar 30 sec** agent khud chunta hai. Kisi gaane ka start khud fix karna ho to `songs.json` mein likho:
  ```json
  {"title": "Om Namah Shivay Dhun", "deity": "shiv", "mp3": "music/shiv/Om Namah Shivay Dhun.mp3", "mp3_start": 42}
  ```

> ⚠ **Public repo** mein MP3 koi bhi download kar sakta hai. Ye theek na lage to poora gaana mat daalo — sirf chorus ka 60-90 sec hissa daalo.
>
> **Copyright:** gaane TuneCore se Meta pe registered hain. TuneCore ke mutabik wo sirf monetize karta hai, block nahi — agar Instagram kabhi reel mute kare to wo Meta ki audio policy se hoga. Pehli test reel (Step 7 `now`) se pata chal jaayega.

### Step 7 — Check → Preview → Test post

**Actions** tab → (pehli baar *enable workflows* aaye to dabao) → left mein **IG Reels Agent** → **Run workflow**, mode chuno:

| mode | kya hota hai |
|---|---|
| `check` | sab jaanchta hai: token, account, limit, photos, gaane, token auto-refresh |
| `preview` | 3 reels banata hai, **post nahi** — run page ke neeche **Artifacts → preview-reels** se zip download karke dekho (caption bhi saath mein) |
| `now` | **abhi 1 reel post** — Instagram pe dekho awaaz theek hai, mute to nahi hui |
| `schedule` | aaj ke slots aur kaunse post hue |

### Step 8 — 🚀 GO LIVE

`config.py` → `PAUSED = False` → Commit.

Bas! Ab har 20 min agent check karega aur roz `POSTS_PER_DAY` reels apne aap jayengi.

---

## Settings (config.py)

| Kya badalna hai | Setting |
|---|---|
| Roz kitni reels | `POSTS_PER_DAY` |
| Pehli / aakhri reel ka time | `DAY_START`, `DAY_END` |
| Reel kitne second ki | `REEL_SECONDS` (15-90) |
| Turant band | `PAUSED = True` |
| Ek mahine baad apne aap band | `CAMPAIGN_END = "2026-11-10"` |
| Bina photo wali (mandala) reels kitni | `MANTRA_ART_SHARE` |
| Neeche wali line | `BOTTOM_LINES` |
| Caption Hindi ya Hinglish | `CAPTION_STYLE` |
| Har post pe Telegram message | `NOTIFY_ON_SUCCESS = True` |
| Mantra, jaikara, hashtag, rang | `DEITIES` |

---

## Kuch galat ho to

| Dikkat | Kya karein |
|---|---|
| Actions mein ❌ laal run | Run kholo → *Agent chalao* step ke aakhri lines mein Hinglish mein wajah + 👉 upay likha hoga |
| `Token expire/galat` (code 190) | Step 2 se naya token → `IG_ACCESS_TOKEN` secret update. `GH_PAT` daala hai to dobara nahi hoga |
| `koi gaana ready nahi` | Step 6 — music/ mein MP3 daalo |
| Reel mute ho gayi | Meta ki audio policy — us gaane ka chhota/doosra hissa try karo, ya TuneCore support se poochho |
| Publishing limit | `POSTS_PER_DAY` kam karo |
| Reels time pe nahi aa rahi | GitHub ka schedule kabhi 10-20 min late hota hai — normal. 2 ghante se zyada late slot skip hota hai (ek saath dher na lage) |
| Kuch bhi post nahi ho raha | `PAUSED = False` hai? Secrets daale? `check` mode chalao |

---

## Developer account na bane to

Agar restricted FB ki wajah se developers.facebook.com pe developer account hi nahi ban raha:
- **Account Quality** (facebook.com/accountquality) se restriction pe *Request review* karo — purani restriction kabhi-kabhi hat jaati hai
- Ya koi bharosemand saathi (jiska FB theek ho) app bana ke tumhe **Instagram Tester** add kare — token phir bhi tumhare Instagram se banega

## Baad mein FB theek ho jaaye to (Instagram library ka gaana)

FB Page juda ho to reel pe **tumhare official gaane ka naam** (Instagram library se) lag sakta hai — reach ke liye ye best hai:
1. Instagram ko FB Page se jodo
2. `config.py`: `LOGIN_TYPE = "facebook"`, `AUDIO_MODE = "library"`, `ARTIST_NAME = "..."`
3. Graph API Explorer se Page token (permissions: `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`, `business_management`) → secrets `IG_ACCESS_TOKEN` + `IG_USER_ID`
4. Actions → mode `find-songs` (query = artist naam, save ✅) → gaane `songs.json` mein jud jaayenge

Is waqt mujhse poochh lena — detail mein step bata dunga.

---

## Kharcha

- **GitHub Actions:** public repo pe free
- **Instagram API:** free
- **Claude captions:** Haiku model — lagbhag ₹10-15/mahina
- **Telegram:** free

---

## Files

| File | Kaam |
|---|---|
| `config.py` | saari settings |
| `music/` | tumhare gaane (MP3) |
| `photos/<bhagwan>/` | photos |
| `songs.json` | (optional) gaane ka start fix karna / library mode |
| `agent.py` | dimaag — schedule, gaana/photo chunna, caption, Instagram post, token refresh |
| `render.py` | video banane wala engine + hook finder |
| `state.json` | agent ki yaaddasht (kya post hua) — apne aap banti hai, chhedo mat |
| `assets/fonts/` | Hindi fonts (Yatra One, Tiro Devanagari Hindi — SIL Open Font License) |
| `.github/workflows/reels.yml` | har 20 min chalne wala schedule |

Local PC pe chalana ho (optional): Python 3.11+, ffmpeg install karo, `.env` file mein secrets likho, phir `pip install -r requirements.txt` aur `python agent.py --check`.
