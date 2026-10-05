"""TikTok-Reel (1080x1920, 30 fps): 3 Hockey-Fakten für @bladesandpucks.

Aufruf: python3 make_hockey_reel.py  ->  hockey_reel.mp4
Format orientiert sich am erfolgreichsten Video des Accounts
(Frage am Ende -> Kommentare).
"""
import math
import os
import random
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
HERE = os.path.dirname(os.path.abspath(__file__))
ANTON = os.path.join(HERE, "fonts", "Anton.ttf")
MONT = os.path.join(HERE, "fonts", "Montserrat.ttf")
ICE = (80, 205, 255)
WHITE = (255, 255, 255)
RED = (235, 35, 50)
GREY = (175, 185, 200)

SCENES = [(0.0, 2.8), (2.8, 7.8), (7.8, 13.0), (13.0, 19.0), (19.0, 23.0)]
DURATION = SCENES[-1][1]
random.seed(4)


# ---------------------------------------------------------------- helpers
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out_cubic(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_out_back(t, s=1.8):
    t = clamp(t) - 1
    return t * t * ((s + 1) * t + s) + 1


def ease_in_out(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


_fonts = {}


def font(kind, size):
    key = (kind, size)
    if key not in _fonts:
        if kind == "anton":
            _fonts[key] = ImageFont.truetype(ANTON, size)
        else:
            f = ImageFont.truetype(MONT, size)
            f.set_variation_by_name(kind)  # z.B. "ExtraBold", "Black"
            _fonts[key] = f
    return _fonts[key]


_texts = {}


def text_img(txt, size, color=WHITE, kind="anton", max_w=960, plain=False):
    key = (txt, size, color, kind, plain)
    if key in _texts:
        return _texts[key]
    while size > 24 and font(kind, size).getlength(txt) > max_w:
        size -= 4
    f = font(kind, size)
    stroke = max(3, size // 22)
    l, t, r, b = f.getbbox(txt, stroke_width=stroke)
    pad = 36
    img = Image.new("RGBA", (r - l + 2 * pad, b - t + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((pad - l + 4, pad - t + 10), txt, font=f, fill=(0, 0, 0, 170),
                             stroke_width=stroke, stroke_fill=(0, 0, 0, 170))
    img = img.filter(ImageFilter.GaussianBlur(9))
    if color == ICE:  # leichter Glow für Akzentwörter
        glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).text((pad - l, pad - t), txt, font=f, fill=ICE + (150,))
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(14)))
    if plain:
        img = Image.new("RGBA", img.size, (0, 0, 0, 0))
        stroke = 0
    ImageDraw.Draw(img).text((pad - l, pad - t), txt, font=f, fill=color + (255,),
                             stroke_width=stroke, stroke_fill=(5, 10, 25, 255))
    _texts[key] = img
    return img


def paste_center(frame, img, cx, cy, scale=1.0, alpha=1.0, angle=0.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    if abs(scale - 1.0) > 1e-3:
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))),
                         Image.BILINEAR)
    if angle:
        img = img.rotate(angle, resample=Image.BICUBIC, expand=True)
    if alpha < 1.0:
        img = img.copy()
        img.putalpha(img.getchannel("A").point(lambda v: int(v * alpha)))
    frame.alpha_composite(img, (int(cx - img.width / 2), int(cy - img.height / 2)))


def pop(frame, txt, size, color, cx, cy, t, delay=0.0, kind="anton", dur=0.32, angle=0.0):
    p = (t - delay) / dur
    if p > 0:
        paste_center(frame, text_img(txt, size, color, kind), cx, cy,
                     scale=ease_out_back(p), alpha=clamp(p * 3), angle=angle)


def slide_up(frame, txt, size, color, cx, cy, t, delay, kind="ExtraBold"):
    p = ease_out_cubic((t - delay) / 0.4)
    if p > 0:
        paste_center(frame, text_img(txt, size, color, kind), cx, cy + (1 - p) * 120, alpha=p)


# ---------------------------------------------------------------- background
def arena_bg():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    v = yy / H
    arr = np.stack([10 + 6 * v, 20 + 10 * v, 45 + 15 * v], -1)
    # Spotlight von oben
    spot = np.exp(-(((xx - W / 2) / 620) ** 2 + ((yy - 250) / 1100) ** 2))
    arr += spot[..., None] * np.array([25, 45, 70])
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
    # Rink-Markierungen (dezent)
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.rectangle((0, 1150, W, 1172), fill=RED + (45,))
    d.rectangle((0, 560, W, 590), fill=(40, 90, 255, 40))
    d.rectangle((0, 1735, W, 1765), fill=(40, 90, 255, 40))
    d.ellipse((W / 2 - 330, 1161 - 330, W / 2 + 330, 1161 + 330), outline=(40, 90, 255, 40), width=10)
    rnd = random.Random(9)
    for _ in range(160):  # Kufen-Kratzer im Eis
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        ln, a = rnd.uniform(80, 420), rnd.uniform(-0.5, 0.5)
        d.line((x, y, x + math.cos(a) * ln, y + math.sin(a) * ln),
               fill=(200, 230, 255, rnd.randint(8, 22)), width=rnd.choice((1, 2)))
    img.alpha_composite(ov.filter(ImageFilter.GaussianBlur(1.2)))
    # Vignette
    r = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2)
    vig = (np.clip((r - 0.3) * 1.6, 0, 0.75) * 255).astype(np.uint8)
    black = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    black.putalpha(Image.fromarray(vig))
    img.alpha_composite(black)
    return img


BG = arena_bg()


# ---------------------------------------------------------------- puck
_pucks = {}


def puck(w, tilt=0.38):
    key = (int(w), tilt)
    if key in _pucks:
        return _pucks[key]
    ss = 3
    pw = int(w * ss)
    ph = int(pw * tilt)
    thick = int(pw * 0.26)
    img = Image.new("RGBA", (pw + 4, ph + thick + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Seite mit Riffelung
    d.ellipse((2, thick + 2, pw + 2, thick + ph + 2), fill=(14, 14, 16, 255))
    d.rectangle((2, ph / 2 + 2, pw + 2, ph / 2 + thick + 2), fill=(14, 14, 16, 255))
    for i in range(1, 46):
        x = 2 + pw / 2 - math.cos(i / 46 * math.pi) * pw / 2
        d.line((x, ph / 2 + thick * 0.18 + 2, x, ph / 2 + thick * 0.82 + 2), fill=(38, 38, 42, 255), width=ss * 2)
    # Oberseite
    d.ellipse((2, 2, pw + 2, ph + 2), fill=(30, 30, 34, 255))
    d.ellipse((pw * 0.08, ph * 0.1, pw * 0.92, ph * 0.9), outline=(48, 48, 54, 255), width=ss * 3)
    # Glanzkante
    d.arc((2, 2, pw + 2, ph + 2), 200, 330, fill=(110, 115, 125, 255), width=ss * 3)
    img = img.resize((img.width // ss, img.height // ss), Image.LANCZOS)
    _pucks[key] = img
    return img


def shadow(frame, cx, cy, w, alpha=0.5):
    sh = Image.new("RGBA", (int(w * 1.3), int(w * 0.4)), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((0, 0, sh.width - 1, sh.height - 1), fill=(0, 0, 0, int(255 * alpha)))
    sh = sh.filter(ImageFilter.GaussianBlur(14))
    frame.alpha_composite(sh, (int(cx - sh.width / 2), int(cy - sh.height / 2)))


def speed_lines(frame, x_tail, x_head, cy, spread, alpha=1.0, seed=0):
    rnd = random.Random(seed)
    d = ImageDraw.Draw(frame)
    for _ in range(14):
        dy = rnd.uniform(-spread, spread)
        start = x_tail + rnd.uniform(0, (x_head - x_tail) * 0.5)
        d.line((start, cy + dy, x_head - 40, cy + dy),
               fill=(200, 235, 255, int(rnd.uniform(60, 160) * alpha)), width=rnd.choice((3, 4, 6)))


def ice_spray(frame, t, x, y, seed):
    if not 0 <= t <= 0.9:
        return
    rnd = random.Random(seed)
    d = ImageDraw.Draw(frame)
    for _ in range(60):
        ang = rnd.uniform(-math.pi * 0.95, -math.pi * 0.35)
        sp = rnd.uniform(250, 900)
        px = x + math.cos(ang) * sp * t
        py = y + math.sin(ang) * sp * t + 900 * t * t
        r = rnd.uniform(2, 6)
        a = int(230 * (1 - t / 0.9))
        d.ellipse((px - r, py - r, px + r, py + r), fill=(225, 245, 255, a))


# ---------------------------------------------------------------- UI
def pill(frame, txt, cy, t):
    p = ease_out_back(t / 0.3)
    if p <= 0:
        return
    f = font("Black", 42)
    tw = f.getlength(txt)
    w, h = int(tw + 84), 84
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=42, fill=ICE + (255,))
    d.text((w / 2, h / 2), txt, font=f, fill=(8, 18, 40), anchor="mm")
    paste_center(frame, img, W / 2, cy, scale=p)


def progress(frame, t):
    d = ImageDraw.Draw(frame)
    d.rectangle((0, H - 12, W, H), fill=(0, 0, 0, 140))
    d.rectangle((0, H - 12, int(W * t / DURATION), H), fill=ICE + (255,))


def flash(frame, t):
    a = clamp(1 - t / 0.16)
    if a > 0:
        frame.alpha_composite(Image.new("RGBA", (W, H), (220, 245, 255, int(190 * a))))


def snowflake(d, x, y, r, a):
    for k in range(3):
        ang = k * math.pi / 3 + a
        dx, dy = math.cos(ang) * r, math.sin(ang) * r
        d.line((x - dx, y - dy, x + dx, y + dy), fill=(220, 245, 255, 200), width=3)


# ---------------------------------------------------------------- scenes
def scene_hook(frame, t):
    # Puck schießt rein, stoppt mit Eisspray
    stop = 0.45
    tx, ty = W / 2, 1250
    p = ease_out_cubic(t / stop)
    x = -300 + (tx + 300) * p
    if t < stop + 0.1:
        speed_lines(frame, x - 700, x, ty, 40, alpha=clamp(1 - t / (stop + 0.1)), seed=1)
    shadow(frame, x, ty + 70, 330)
    paste_center(frame, puck(320), x, ty)
    ice_spray(frame, t - stop + 0.1, tx + 140, ty + 40, 5)

    shake = math.sin(t * 70) * 10 * clamp(1 - (t - stop) / 0.3) if t > stop else 0
    pop(frame, "99% OF FANS", 170, WHITE, W / 2 + shake, 430, t, 0.05)
    pop(frame, "DON'T KNOW", 170, WHITE, W / 2 - shake, 620, t, 0.3)
    pop(frame, "THESE 3 FACTS", 150, ICE, W / 2, 800, t, 0.55)
    slide_up(frame, "Watch till the end", 52, WHITE, W / 2, 1560, t, 1.3)


def scene_frozen(frame, t):
    d = ImageDraw.Draw(frame)
    rnd = random.Random(2)
    for _ in range(45):  # Schneeflocken
        x0, sp, r, ph = rnd.uniform(0, W), rnd.uniform(90, 220), rnd.uniform(8, 20), rnd.uniform(0, 6)
        y = (rnd.uniform(0, H) + sp * t) % H
        snowflake(d, x0 + math.sin(t * 1.5 + ph) * 30, y, r, t + ph)
    flash(frame, t)
    pill(frame, "FACT 1 / 3", 330, t)
    pop(frame, "NHL PUCKS ARE", 110, WHITE, W / 2, 470, t, 0.15)
    s = 1 + 0.04 * math.sin(t * 8) if t > 0.9 else 1
    pop(frame, "FROZEN", 230, ICE, W / 2, 640, t, 0.45, angle=-3 * s)
    pop(frame, "BEFORE EVERY GAME", 92, WHITE, W / 2, 810, t, 0.8)

    # Puck mit Frost
    bob = math.sin(t * 2.4) * 14
    pk = puck(430).copy()
    frost = clamp((t - 0.9) / 1.6)
    if frost > 0:
        rnd2 = np.random.default_rng(3)
        noise = rnd2.random((pk.height, pk.width))
        mask = np.asarray(pk.getchannel("A"), dtype=np.float32) / 255
        a = (np.clip(noise * 1.4 - (1 - frost) * 1.2, 0, 1) * mask * 150).astype(np.uint8)
        fr = Image.new("RGBA", pk.size, (215, 240, 255, 0))
        fr.putalpha(Image.fromarray(a))
        pk.alpha_composite(fr.filter(ImageFilter.GaussianBlur(1)))
    shadow(frame, W / 2, 1210 + 80, 440, 0.45)
    paste_center(frame, pk, W / 2, 1110 + bob, scale=ease_out_back((t - 0.3) / 0.5))

    slide_up(frame, "so they slide faster", 58, WHITE, W / 2, 1420, t, 2.5)
    slide_up(frame, "& don't bounce", 68, ICE, W / 2, 1500, t, 2.75, kind="Black")


def gauge(frame, cx, cy, r, frac):
    d = ImageDraw.Draw(frame)
    box = (cx - r, cy - r, cx + r, cy + r)
    d.arc(box, 150, 390, fill=(255, 255, 255, 40), width=34)
    end = 150 + 240 * frac
    if frac > 0:
        col = tuple(int(ICE[i] + (RED[i] - ICE[i]) * clamp((frac - 0.6) / 0.4)) for i in range(3))
        d.arc(box, 150, end, fill=col + (255,), width=34)
    for k in range(13):
        a = math.radians(150 + 240 * k / 12)
        r1, r2 = r - 50, r - 70 if k % 3 else r - 90
        d.line((cx + math.cos(a) * r1, cy + math.sin(a) * r1, cx + math.cos(a) * r2, cy + math.sin(a) * r2),
               fill=(255, 255, 255, 140), width=5)
    a = math.radians(end)
    d.line((cx + math.cos(a) * (r - 140), cy + math.sin(a) * (r - 140),
            cx + math.cos(a) * (r - 55), cy + math.sin(a) * (r - 55)), fill=RED + (255,), width=12)


def scene_speed(frame, t):
    flash(frame, t)
    pill(frame, "FACT 2 / 3", 330, t)
    pop(frame, "HARDEST SHOT", 130, WHITE, W / 2, 470, t, 0.1)
    pop(frame, "EVER RECORDED", 100, WHITE, W / 2, 610, t, 0.3)

    fill = ease_in_out((t - 0.5) / 1.6)
    jitter = math.sin(t * 90) * 0.006 if 1.8 < t < 2.4 else 0
    gauge(frame, W / 2, 1000, 350, clamp(fill * 0.97 + jitter))
    val = 108.8 * fill
    big = 1 + (0.12 * clamp(1 - (t - 2.1) / 0.25) if t > 2.1 else 0)
    paste_center(frame, text_img(f"{val:.1f}", 150, WHITE if fill < 1 else ICE), W / 2, 1040, scale=big)
    paste_center(frame, text_img("MPH", 58, GREY, "Black"), W / 2, 1160)

    # Puck fliegt durchs Bild, wenn der Wert erreicht ist
    if 2.1 < t < 2.7:
        p = (t - 2.1) / 0.6
        x = -200 + (W + 400) * p
        speed_lines(frame, x - 900, x, 1330, 30, seed=7)
        paste_center(frame, puck(150), x, 1330)
    slide_up(frame, "(175 km/h)", 56, GREY, W / 2, 1400, t, 2.5)
    slide_up(frame, "ZDENO CHARA · 2012", 70, ICE, W / 2, 1490, t, 2.8, kind="Black")


def scene_gretzky(frame, t):
    flash(frame, t)
    pill(frame, "FACT 3 / 3", 330, t)
    pop(frame, "GRETZKY'S ASSISTS", 120, WHITE, W / 2, 470, t, 0.1)
    pop(frame, "ALONE BEAT EVERYONE'S", 92, WHITE, W / 2, 600, t, 0.35)
    pop(frame, "TOTAL POINTS", 160, ICE, W / 2, 750, t, 0.6)

    d = ImageDraw.Draw(frame)
    x0, maxw, bh = 90, 900, 110
    bars = [("GRETZKY · ASSISTS ONLY", 1963, ICE, 980),
            ("#2 ALL-TIME POINTS · JÁGR", 1921, GREY, 1220)]
    for i, (label, val, col, y) in enumerate(bars):
        p = ease_out_cubic((t - 1.0 - i * 0.25) / 1.5)
        if p <= 0:
            continue
        lab = text_img(label, 44, WHITE, "ExtraBold")
        frame.alpha_composite(lab, (x0 - 36, int(y - 95)))
        d.rounded_rectangle((x0, y, x0 + maxw, y + bh), radius=18, fill=(255, 255, 255, 25))
        wbar = max(20, maxw * val / 1963 * p)
        d.rounded_rectangle((x0, y, x0 + wbar, y + bh), radius=18, fill=col + (255,))
        num = text_img(f"{int(val * p):,}", 72, (8, 18, 40), "Black", plain=True) if wbar > 300 else text_img(f"{int(val * p):,}", 72, WHITE, "Black")
        frame.alpha_composite(num, (int(x0 + max(wbar - num.width + 20, 0)), int(y + bh / 2 - num.height / 2)))

    slide_up(frame, "Even with ZERO goals,", 56, WHITE, W / 2, 1450, t, 3.2)
    slide_up(frame, "he'd still be #1 all-time.", 62, ICE, W / 2, 1530, t, 3.45, kind="Black")


def goal_light(frame, t):
    on = (int(t * 6) % 2 == 0) and t < 1.6
    if not on:
        return
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(ov).rectangle((0, 0, W, H), outline=RED + (200,), width=60)
    frame.alpha_composite(ov.filter(ImageFilter.GaussianBlur(40)))


def scene_cta(frame, t):
    flash(frame, t)
    goal_light(frame, t)
    pop(frame, "WHO'S THE MOST", 130, WHITE, W / 2, 470, t, 0.05)
    pop(frame, "UNDERRATED", 200, ICE, W / 2, 650, t, 0.25, angle=math.sin(t * 5) * 1.5)
    pop(frame, "PLAYER EVER?", 140, WHITE, W / 2, 830, t, 0.45)
    if t > 0.5:
        shadow(frame, W / 2, 1120, 260, 0.4)
        paste_center(frame, puck(240), W / 2, 1060 + math.sin(t * 5) * 14,
                     scale=ease_out_back((t - 0.5) / 0.4))
    slide_up(frame, "Drop a name in the comments", 54, WHITE, W / 2, 1300, t, 0.9)
    if t > 1.1:  # hüpfender Pfeil
        d = ImageDraw.Draw(frame)
        y = 1390 + abs(math.sin(t * 6)) * 30
        d.polygon([(W / 2 - 40, y), (W / 2 + 40, y), (W / 2, y + 50)], fill=ICE + (255,))
    slide_up(frame, "+ FOLLOW FOR PART 2", 64, ICE, W / 2, 1540, t, 1.5, kind="Black")


SCENE_FUNCS = [scene_hook, scene_frozen, scene_speed, scene_gretzky, scene_cta]


def render_frame(i):
    t = i / FPS
    frame = BG.copy()
    for (a, b), fn in zip(SCENES, SCENE_FUNCS):
        if a <= t < b:
            lt = t - a
            fn(frame, lt)
            if a > 0 and lt < 0.15:  # Zoom-Punch beim Szenenwechsel
                z = 1 + 0.07 * (1 - lt / 0.15)
                big = frame.resize((int(W * z), int(H * z)), Image.BILINEAR)
                ox, oy = (big.width - W) // 2, (big.height - H) // 2
                frame = big.crop((ox, oy, ox + W, oy + H))
            break
    progress(frame, t)
    return frame.convert("RGB")


# ---------------------------------------------------------------- audio
SR = 44100


def lowpass(x, n):
    return np.convolve(x, np.ones(n) / n, mode="same")


def make_audio(path):
    n = int(DURATION * SR)
    out = np.zeros(n)
    rng = np.random.default_rng(2)

    def add(sig, at, vol=1.0):
        s = int(at * SR)
        e = min(n, s + len(sig))
        if 0 <= s < n:
            out[s:e] += sig[: e - s] * vol

    def tt(sec):
        return np.arange(int(sec * SR)) / SR

    beat = 60 / 128
    kt = tt(0.3)
    kick = np.sin(2 * np.pi * (45 + 140 * np.exp(-kt * 35)) * kt) * np.exp(-kt * 10)
    ht = tt(0.05)
    hat = np.diff(rng.standard_normal(len(ht)), prepend=0) * np.exp(-ht * 80) * 0.22
    ct = tt(0.18)
    clap = lowpass(rng.standard_normal(len(ct)), 3) * np.exp(-ct * 22) * 0.4
    notes = [41.2, 41.2, 49.0, 36.7]  # E, E, G, D
    k = 0
    while k * beat < DURATION - 0.3:
        at = k * beat
        add(kick, at, 0.95)
        add(hat, at + beat / 2)
        if k % 2:
            add(clap, at)
        f = notes[(k // 4) % 4]
        bt = tt(beat)
        saw = 2 * ((f * bt) % 1) - 1
        add(lowpass(saw, 40) * np.exp(-bt * 2.5) * 0.5, at)
        k += 1

    # Whoosh zu jedem Szenenwechsel
    wt = tt(0.4)
    whoosh = lowpass(rng.standard_normal(len(wt)), 25) * np.sin(np.pi * wt / wt[-1]) ** 2
    for a, _ in SCENES[1:]:
        add(whoosh, a - 0.28, 1.0)

    # Schlagschuss (Slap) + Eiskratzen im Hook
    st = tt(0.25)
    slap = (rng.standard_normal(len(st)) * np.exp(-st * 60) + np.sin(2 * np.pi * 90 * st) * np.exp(-st * 25)) * 0.9
    add(slap, 0.0)
    sc = tt(0.5)
    scrape = (rng.standard_normal(len(sc)) - lowpass(rng.standard_normal(len(sc)), 8)) * np.exp(-sc * 5) * 0.35
    add(scrape, 0.42)
    add(slap, SCENES[2][0] + 2.1, 0.8)

    # Publikum jubelt bei 108.8
    cr = tt(2.2)
    crowd = lowpass(rng.standard_normal(len(cr)), 12) * np.minimum(cr / 0.25, 1) * np.exp(-np.maximum(cr - 0.6, 0) * 2)
    add(crowd * 1.2, SCENES[2][0] + 2.1)

    # Ding bei Zahlen
    dt = tt(0.9)
    ding = (np.sin(2 * np.pi * 1318.5 * dt) + 0.5 * np.sin(2 * np.pi * 1975.5 * dt)) * np.exp(-dt * 4.5) * 0.22
    for at in (SCENES[1][0] + 0.45, SCENES[3][0] + 2.5):
        add(ding, at)

    # Torhupe zum CTA
    ht2 = tt(1.5)
    env = np.minimum(ht2 / 0.05, 1) * np.clip((1.5 - ht2) / 0.3, 0, 1)
    horn = sum(2 * ((f * ht2) % 1) - 1 for f in (110, 138.6, 164.8))
    add(lowpass(horn, 12) * env * 0.28, SCENES[4][0])

    fade = np.clip((DURATION - np.arange(n) / SR) / 0.6, 0, 1)
    out *= fade
    out /= np.max(np.abs(out)) * 1.1
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((out * 32767).astype(np.int16).tobytes())


def main():
    os.chdir(HERE)
    make_audio("audio.wav")
    nf = int(DURATION * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", "audio.wav", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
           "-movflags", "+faststart", "hockey_reel.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(nf):
        proc.stdin.write(render_frame(i).tobytes())
        if i % 90 == 0:
            print(f"{i}/{nf}", flush=True)
    proc.stdin.close()
    proc.wait()
    render_frame(int(1.9 * FPS)).save("thumbnail.jpg", quality=92)
    print("fertig: hockey_reel.mp4")


if __name__ == "__main__":
    main()
