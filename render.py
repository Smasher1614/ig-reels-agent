"""
render.py — devotional reel video banane wala engine.

Output: 1080x1920 (9:16), 30fps, H.264 MP4 — Instagram Reels ke specs ke hisaab se.

Har reel mein:
  - Bhagwan ki photo pe slow zoom/pan (Ken Burns) — portrait photo full-screen,
    landscape/square photo ek sunehre frame (card) mein, peeche blur background
  - Photo na ho to: ghoomta hua mandala + bada "ॐ" (generative style)
  - Sunehri roshni (glow) jo dheere-dheere saans leti hai
  - Upar uthte diye jaise chamakte kan (particles)
  - Upar mantra (Devanagari), neeche chhoti line (jaise "रोज़ भक्ति के लिए फ़ॉलो करें")
  - Shuru/aakhir mein fade

Audio: by default ek khamosh (silent) track lagta hai — gaana Instagram library se
attach hota hai. "mp3" mode mein tumhari MP3 ka hissa video mein jud jaata hai.
"""
from __future__ import annotations

import math
import os
import random
import shutil
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, features

W, H = 1080, 1920
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(BASE_DIR, "assets", "fonts")
FONT_TITLE = os.path.join(FONT_DIR, "YatraOne-Regular.ttf")
FONT_BODY = os.path.join(FONT_DIR, "TiroDevanagariHindi-Regular.ttf")
PHOTO_EXTS = (".jpg", ".jpeg", ".png", ".webp")

HAS_RAQM = features.check_feature("raqm")

# Text ki jagah (Instagram ka UI upar ~150px aur neeche ~400px dhak leta hai)
TOP_TEXT_Y = 270      # upar wale mantra ka center
BOTTOM_TEXT_Y = 1455  # neeche wali line ka center
CARD_CENTER_Y = 930   # landscape/square photo ke frame ka center
CARD_MAX_H = 1000


# ============================================================ helpers
def hex_rgb(value) -> tuple[int, int, int]:
    if isinstance(value, (tuple, list)):
        return tuple(int(v) for v in value[:3])
    v = value.lstrip("#")
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    layout = ImageFont.Layout.RAQM if HAS_RAQM else ImageFont.Layout.BASIC
    return ImageFont.truetype(path, size, layout_engine=layout)


def _text_w(font, text: str) -> int:
    l, _, r, _ = font.getbbox(text)
    return r - l


def _ease(u: float) -> float:
    u = min(max(u, 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * u)


_GRID = None


def _grid():
    global _GRID
    if _GRID is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        _GRID = (xx, yy)
    return _GRID


def _radial(cx, cy, rx, ry) -> np.ndarray:
    xx, yy = _grid()
    return np.exp(-(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)).astype(np.float32)


def _vignette() -> np.ndarray:
    xx, yy = _grid()
    r = np.sqrt(((xx - W / 2) / (W * 0.78)) ** 2 + ((yy - H / 2) / (H * 0.62)) ** 2)
    s = np.clip((r - 0.55) / 0.75, 0, 1)
    v = 1.0 - 0.62 * (s * s * (3 - 2 * s))
    # text padhne layak rahe isliye upar/neeche halki dark band
    top = 1.0 - 0.42 * np.clip(1.0 - yy / 560.0, 0, 1) ** 1.6
    bot = 1.0 - 0.50 * np.clip((yy - 1250.0) / 670.0, 0, 1) ** 1.4
    return (v * top * bot).astype(np.float32)


# ============================================================ text layers
class TextLayer:
    """Pre-rendered text: sunehra gradient + dark outline + bahar glow."""

    def __init__(self, text: str, font_path: str, max_size: int, min_size: int,
                 center_y: int, fill_top=(255, 236, 170), fill_bottom=(240, 170, 60),
                 glow=(255, 150, 40), glow_strength=0.85, max_width=940):
        text = " ".join(text.split())
        words = text.split(" ")
        size, lines, font = max_size, [text], _font(font_path, max_size)
        for size in range(max_size, min_size - 1, -4):
            font = _font(font_path, size)
            lines = [text]
            if _text_w(font, text) > max_width and len(words) > 1:
                best = None
                for i in range(1, len(words)):
                    a, b = " ".join(words[:i]), " ".join(words[i:])
                    m = max(_text_w(font, a), _text_w(font, b))
                    if best is None or m < best[0]:
                        best = (m, [a, b])
                lines = best[1]
            if max(_text_w(font, ln) for ln in lines) <= max_width:
                break

        line_h = int(size * 1.32)
        widest = max(_text_w(font, ln) for ln in lines)
        pad = max(10, min(int(size * 0.55), (W - widest) // 2))
        tw = min(W, widest + 2 * pad)
        th = line_h * len(lines) + 2 * pad
        mask = Image.new("L", (tw, th), 0)
        d = ImageDraw.Draw(mask)
        for i, ln in enumerate(lines):
            d.text((tw / 2, pad + line_h * (i + 0.5)), ln, font=font, fill=255, anchor="mm")

        m = np.asarray(mask, dtype=np.float32) / 255.0
        outline_px = max(3, min(size // 22, 7)) * 2 + 1
        outline = np.asarray(mask.filter(ImageFilter.MaxFilter(outline_px)), dtype=np.float32) / 255.0
        glow_m = np.asarray(mask.filter(ImageFilter.GaussianBlur(max(6, size * 0.2))), dtype=np.float32) / 255.0
        glow_m = np.clip(glow_m * 1.6, 0, 1) * glow_strength

        grad = np.linspace(0, 1, th, dtype=np.float32)[:, None, None]
        fill = np.array(fill_top, np.float32) * (1 - grad) + np.array(fill_bottom, np.float32) * grad
        fill = np.broadcast_to(fill, (th, tw, 3))
        dark = np.array((45, 12, 4), np.float32)
        glow_c = np.array(glow, np.float32)

        # parat-dar-parat: glow -> outline -> text
        a_glow = glow_m * 0.75
        rgb = glow_c * a_glow[..., None]
        alpha = a_glow.copy()
        a_out = outline * 0.85
        rgb = rgb * (1 - a_out[..., None]) + dark * a_out[..., None]
        alpha = alpha * (1 - a_out) + a_out
        rgb = rgb * (1 - m[..., None]) + fill * m[..., None]
        alpha = alpha * (1 - m) + m

        self.premult = rgb.astype(np.float32)   # already alpha-weighted
        self.alpha = alpha.astype(np.float32)
        self.x = (W - tw) // 2
        self.y = int(center_y - th / 2)
        self.w, self.h = tw, th
        self.size = size
        self.lines = lines

    def composite(self, frame: np.ndarray, strength: float):
        if strength <= 0:
            return
        y0, x0 = max(0, self.y), max(0, self.x)
        y1, x1 = min(H, self.y + self.h), min(W, self.x + self.w)
        sy, sx = y0 - self.y, x0 - self.x
        a = self.alpha[sy:sy + (y1 - y0), sx:sx + (x1 - x0)] * strength
        p = self.premult[sy:sy + (y1 - y0), sx:sx + (x1 - x0)] * strength
        reg = frame[y0:y1, x0:x1]
        reg *= (1 - a)[..., None]
        reg += p


# ============================================================ particles
class Particles:
    """Upar uthte chamakte kan (diye ki chingari jaise)."""

    def __init__(self, rng: random.Random, colors, count=70, strength=1.0):
        self.sprites = {}
        for r in (2, 3, 4, 6, 9):
            s = r * 6 + 1
            c = s // 2
            yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
            dd = np.sqrt((xx - c) ** 2 + (yy - c) ** 2)
            g = np.exp(-(dd / r) ** 2 * 1.6) + 0.35 * np.exp(-(dd / (r * 2.2)) ** 2)
            self.sprites[r] = (g / g.max()).astype(np.float32)
        cols = [np.array(hex_rgb(c), np.float32) for c in colors]
        self.p = []
        for _ in range(count):
            self.p.append(dict(
                x0=rng.uniform(0, W), y0=rng.uniform(0, H + 80),
                speed=rng.uniform(35, 120), amp=rng.uniform(8, 42),
                freq=rng.uniform(0.08, 0.32), tw=rng.uniform(0.5, 1.7),
                ph=rng.uniform(0, 6.283), ph2=rng.uniform(0, 6.283),
                inten=rng.uniform(0.35, 1.0) * strength,
                r=rng.choices([2, 3, 4, 6, 9], weights=[30, 30, 20, 12, 5])[0],
                col=rng.choice(cols),
            ))

    def draw(self, frame: np.ndarray, t: float):
        for q in self.p:
            spr = self.sprites[q["r"]]
            s = spr.shape[0]
            y = (q["y0"] - q["speed"] * t) % (H + 80) - 40
            x = q["x0"] + q["amp"] * math.sin(6.283 * q["freq"] * t + q["ph"])
            b = q["inten"] * (0.55 + 0.45 * math.sin(6.283 * q["tw"] * t + q["ph2"]))
            ix, iy = int(x) - s // 2, int(y) - s // 2
            x0, y0 = max(0, ix), max(0, iy)
            x1, y1 = min(W, ix + s), min(H, iy + s)
            if x1 <= x0 or y1 <= y0:
                continue
            sub = spr[y0 - iy:y1 - iy, x0 - ix:x1 - ix]
            frame[y0:y1, x0:x1] += sub[..., None] * (q["col"] * b)


# ============================================================ backgrounds
def _cover(img: Image.Image, w: int, h: int) -> Image.Image:
    return ImageOps.fit(img, (w, h), method=Image.LANCZOS, centering=(0.5, 0.45))


def _rounded_mask(w, h, r) -> Image.Image:
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=255)
    return m


class KenBurns:
    """Photo ke andar dheere zoom + pan (subpixel smooth)."""

    def __init__(self, img: Image.Image, out_w: int, out_h: int, rng: random.Random, zoom=0.13):
        aspect = out_w / out_h
        iw, ih = img.size
        if iw / ih > aspect:
            win_h, win_w = ih, ih * aspect
        else:
            win_w, win_h = iw, iw / aspect
        # source ko itna chhota karo ki max zoom pe ~1:1 pixel ho (fast + sharp)
        scale = min(1.0, (out_w * (1 + zoom) * 1.05) / win_w)
        if scale < 1.0:
            img = img.resize((max(1, int(iw * scale)), max(1, int(ih * scale))), Image.LANCZOS)
            iw, ih = img.size
            win_w, win_h = win_w * scale, win_h * scale
        self.img, self.out = img, (out_w, out_h)
        self.iw, self.ih, self.win_w, self.win_h = iw, ih, win_w, win_h
        zin = rng.random() < 0.6
        self.z0, self.z1 = (1.0, 1.0 + zoom) if zin else (1.0 + zoom, 1.0)
        # pan: thoda sa kisi disha mein (chehra beech mein rahe isliye halka)
        self.p0 = (rng.uniform(-0.25, 0.25), rng.uniform(-0.35, 0.05))
        self.p1 = (rng.uniform(-0.25, 0.25), rng.uniform(-0.35, 0.05))

    def frame(self, u: float) -> np.ndarray:
        e = _ease(u)
        z = self.z0 + (self.z1 - self.z0) * e
        ww, wh = self.win_w / z, self.win_h / z
        px = self.p0[0] + (self.p1[0] - self.p0[0]) * e
        py = self.p0[1] + (self.p1[1] - self.p0[1]) * e
        cx = self.iw / 2 + px * (self.iw - ww) / 2
        cy = self.ih / 2 + py * (self.ih - wh) / 2
        cx = min(max(cx, ww / 2), self.iw - ww / 2)
        cy = min(max(cy, wh / 2), self.ih - wh / 2)
        ow, oh = self.out
        data = (ww / ow, 0, cx - ww / 2, 0, wh / oh, cy - wh / 2)
        im = self.img.transform(self.out, Image.AFFINE, data, resample=Image.BILINEAR)
        return np.asarray(im, dtype=np.float32)


def _mandala(size: int, rng: random.Random) -> np.ndarray:
    S = size * 2  # 2x bana ke chhota karenge (smooth edges)
    m = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(m)
    c = S / 2
    rings = [
        (0.20, 12, 0.11, 0.035, 150),
        (0.32, 16, 0.13, 0.035, 120),
        (0.45, 24, 0.12, 0.028, 95),
        (0.58, 32, 0.10, 0.022, 70),
    ]
    off = rng.uniform(0, 1)
    for (rad, n, length, width, alpha) in rings:
        R, L, Wd = rad * S / 2, length * S / 2, width * S / 2
        for k in range(n):
            a = 2 * math.pi * (k + off * 0.5) / n
            pts = []
            for j in range(13):  # lens (patta) shape
                v = j / 12
                rr = R + (v - 0.5) * L
                ww = math.sin(math.pi * v) * Wd
                pts.append((rr, ww))
            for j in range(12, -1, -1):
                v = j / 12
                rr = R + (v - 0.5) * L
                ww = -math.sin(math.pi * v) * Wd
                pts.append((rr, ww))
            poly = [(c + p[0] * math.cos(a) - p[1] * math.sin(a),
                     c + p[0] * math.sin(a) + p[1] * math.cos(a)) for p in pts]
            d.polygon(poly, outline=alpha, width=4)
        d.ellipse((c - R - L / 1.6, c - R - L / 1.6, c + R + L / 1.6, c + R + L / 1.6),
                  outline=int(alpha * 0.6), width=3)
    for k in range(48):  # bindu ring
        a = 2 * math.pi * k / 48
        R = 0.66 * S / 2
        x, y = c + R * math.cos(a), c + R * math.sin(a)
        d.ellipse((x - 7, y - 7, x + 7, y + 7), fill=110)
    m = m.resize((size, size), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.8))
    return m


# ============================================================ main renderer
class Reel:
    def __init__(self, photo: str | None, top_text: str, bottom_text: str = "",
                 seconds: float = 30, fps: int = 30, seed: int = 0, theme: dict | None = None):
        self.rng = random.Random(seed)
        self.seconds, self.fps = float(seconds), int(fps)
        theme = theme or {}
        self.glow_col = np.array(hex_rgb(theme.get("glow", "#ffb347")), np.float32)
        pcols = theme.get("particles", ["#ffd27a", "#ffb04a", "#fff1c9"])
        self.vig = _vignette()
        self.mode = "mantra-art"
        self.kb = None
        self.card = None
        self.mandala = None

        if photo:
            img = ImageOps.exif_transpose(Image.open(photo)).convert("RGB")
            iw, ih = img.size
            if iw / ih <= 0.72:
                self.mode = "full"
                self.kb = KenBurns(img, W, H, self.rng, zoom=0.13)
                self.static = None
                glow_y = 700
            else:
                self.mode = "card"
                cw = 960
                ch = int(round(cw * ih / iw))
                ch = max(540, min(CARD_MAX_H, ch))
                self.card_box = (60, int(CARD_CENTER_Y - ch / 2), cw, ch)
                self.kb = KenBurns(img, cw, ch, self.rng, zoom=0.07)
                self.card_mask = np.asarray(_rounded_mask(cw, ch, 34), np.float32)[..., None] / 255.0
                bg = _cover(img, W // 4, H // 4).filter(ImageFilter.GaussianBlur(10)).resize((W, H), Image.BILINEAR)
                bg = np.asarray(bg, np.float32) * 0.42
                bg = bg * np.array([1.05, 0.92, 0.80], np.float32)  # garam rang
                # card ke neeche parchhai (shadow)
                x, y, cw_, ch_ = self.card_box
                sh = Image.new("L", (W, H), 0)
                ImageDraw.Draw(sh).rounded_rectangle((x + 6, y + 22, x + cw_ + 6, y + ch_ + 22), 40, fill=210)
                sh = np.asarray(sh.filter(ImageFilter.GaussianBlur(28)), np.float32) / 255.0
                self.static = bg * (1 - 0.75 * sh[..., None])
                # sunehri border
                border = Image.new("L", (W, H), 0)
                ImageDraw.Draw(border).rounded_rectangle((x - 3, y - 3, x + cw_ + 2, y + ch_ + 2), 37, outline=255, width=5)
                b = np.asarray(border, np.float32) / 255.0
                bglow = np.asarray(Image.fromarray((b * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(14)), np.float32) / 255.0
                self.border_add = (b[..., None] * np.array([235, 190, 105], np.float32)
                                   + bglow[..., None] * self.glow_col * 0.9)
                self.border_mul = 1 - b[..., None] * 0.9
                glow_y = CARD_CENTER_Y - ch / 4
        if self.mode == "mantra-art":
            bgc = hex_rgb(theme.get("bg", "#7a1d0e"))
            r = _radial(W / 2, CARD_CENTER_Y, W * 0.75, H * 0.55)
            inner = np.array(bgc, np.float32)
            outer = np.array((18, 4, 8), np.float32)
            self.static = outer + (inner - outer) * r[..., None]
            self.mandala = _mandala(1040, self.rng)
            self.om = TextLayer("ॐ", FONT_TITLE, 520, 300, CARD_CENTER_Y - 10, glow=tuple(self.glow_col),
                                glow_strength=1.0, max_width=1000)
            self.mandala_speed = self.rng.choice([-1, 1]) * self.rng.uniform(4, 8)  # degree/sec
            glow_y = CARD_CENTER_Y

        self.glow = _radial(W / 2, glow_y, W * 0.55, H * 0.30)[..., None] * self.glow_col
        self.glow_period = self.rng.uniform(3.5, 5.5)
        self.particles = Particles(self.rng, pcols, count=self.rng.randint(55, 85))
        self.top = TextLayer(top_text, FONT_TITLE, 112, 64, TOP_TEXT_Y, glow=tuple(self.glow_col)) if top_text else None
        self.bottom = TextLayer(bottom_text, FONT_BODY, 56, 38, BOTTOM_TEXT_Y,
                                fill_top=(255, 246, 225), fill_bottom=(255, 214, 150),
                                glow=(0, 0, 0), glow_strength=0.9, max_width=900) if bottom_text else None

    # -------------------------------------------------------------- one frame
    def frame(self, t: float) -> np.ndarray:
        u = t / self.seconds
        if self.mode == "full":
            f = self.kb.frame(u)
        else:
            f = self.static.copy()
            if self.mode == "card":
                x, y, cw, ch = self.card_box
                card = self.kb.frame(u)
                reg = f[y:y + ch, x:x + cw]
                reg *= (1 - self.card_mask)
                reg += card * self.card_mask
            else:  # mantra-art
                ang = self.mandala_speed * t
                m = np.asarray(self.mandala.rotate(ang, resample=Image.BILINEAR), np.float32) / 255.0
                s = m.shape[0]
                x0, y0 = (W - s) // 2, int(CARD_CENTER_Y - s / 2)
                xa, xb = max(0, x0), min(W, x0 + s)
                f[y0:y0 + s, xa:xb] += m[:, xa - x0:xb - x0, None] * (np.array([255, 196, 110], np.float32) * 0.7)

        pulse = 0.20 + 0.09 * math.sin(2 * math.pi * t / self.glow_period)
        f += self.glow * pulse
        if self.mode == "card":
            f *= self.border_mul
            f += self.border_add * (0.85 + 0.15 * math.sin(2 * math.pi * t / self.glow_period))
        if self.mode == "mantra-art":
            self.om.composite(f, 0.9 + 0.1 * math.sin(2 * math.pi * t / self.glow_period))
        self.particles.draw(f, t)
        f *= self.vig[..., None]

        if self.top:
            self.top.composite(f, _ease((t - 0.3) / 1.0))
        if self.bottom:
            self.bottom.composite(f, _ease((t - 1.0) / 1.0))

        fade = min(1.0, t / 0.6, (self.seconds - t) / 0.8)
        if fade < 1.0:
            f *= max(0.0, fade)
        np.clip(f, 0, 255, out=f)
        return f.astype(np.uint8)

    def still(self, t: float) -> Image.Image:
        return Image.fromarray(self.frame(t))


def find_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg nahi mila — GitHub Actions workflow isse install karta hai; local PC pe ffmpeg install karo.")
    return exe


def render_reel(out_path: str, photo: str | None, top_text: str, bottom_text: str = "",
                seconds: float = 30, fps: int = 30, seed: int = 0, theme: dict | None = None,
                audio_mp3: str | None = None, audio_start: float = 0.0) -> dict:
    """Poori reel MP4 banao. Return: info dict (mode, seconds, size)."""
    reel = Reel(photo, top_text, bottom_text, seconds, fps, seed, theme)
    n = int(round(seconds * fps))
    cmd = [find_ffmpeg(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-"]
    if audio_mp3:
        cmd += ["-ss", f"{audio_start:.2f}", "-t", f"{seconds:.2f}", "-i", audio_mp3]
    else:
        cmd += ["-f", "lavfi", "-t", f"{seconds:.2f}", "-i", "anullsrc=r=44100:cl=stereo"]
    cmd += ["-map", "0:v", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-profile:v", "high", "-g", str(fps * 2),
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"]
    if audio_mp3:
        cmd += ["-af", f"afade=t=in:st=0:d=0.8,afade=t=out:st={max(0.0, seconds - 1.5):.2f}:d=1.5"]
    cmd += ["-t", f"{seconds:.2f}", "-movflags", "+faststart", out_path]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for i in range(n):
            proc.stdin.write(reel.frame(i / fps).tobytes())
        proc.stdin.close()
    except BrokenPipeError:
        pass
    err = proc.stderr.read().decode("utf-8", "replace")
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg fail hua: {err[-800:]}")
    return {"mode": reel.mode, "seconds": seconds, "bytes": os.path.getsize(out_path)}


def list_photos(folder: str) -> list[str]:
    if not os.path.isdir(folder):
        return []
    return sorted(os.path.join(folder, f) for f in os.listdir(folder)
                  if f.lower().endswith(PHOTO_EXTS) and not f.startswith("."))


_HOOK_CACHE: dict = {}


def find_hook_starts(path: str, seconds: float, top: int = 3) -> list[float]:
    """Gaane ke sabse jandaar (loud/energetic) hisson ke start-second — chorus aksar yahi hota hai.
    Har reel mein in top hisson mein se ek lagta hai, taaki har baar same 30 sec na ho."""
    key = (path, os.path.getmtime(path), seconds)
    if key in _HOOK_CACHE:
        return _HOOK_CACHE[key]
    sr = 4000
    raw = subprocess.run([find_ffmpeg(), "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(sr),
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32)
    n, w = len(x) // sr, int(round(seconds))
    if n <= w + 2:
        res = [0.0]
    else:
        e = np.sqrt((x[:n * sr].reshape(n, sr) ** 2).mean(axis=1))  # har second ki loudness
        cs = np.concatenate([[0.0], np.cumsum(e)])
        win = (cs[w:] - cs[:-w]) / w                                # window [i, i+w) ki average
        lo, hi = min(5, n - w), n - w                               # pehle 5 sec (intro) chhodo
        order = np.argsort(win[lo:hi + 1])[::-1] + lo
        picks: list[int] = []
        for c in order:
            if all(abs(int(c) - p) >= w * 0.6 for p in picks):
                picks.append(int(c))
            if len(picks) >= top:
                break
        best = win[picks[0]]
        res = [float(p) for p in picks if win[p] >= 0.85 * best]
    _HOOK_CACHE[key] = res
    return res
