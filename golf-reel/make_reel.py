"""Erzeugt ein TikTok-Reel (1080x1920, 30 fps) mit 3 Golf-Fakten.

Aufruf: python3 make_reel.py  ->  golf_reel.mp4
"""
import math
import random
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
YELLOW = (255, 214, 0)
WHITE = (255, 255, 255)
RED = (235, 40, 50)

# Szenen: (Start, Ende) in Sekunden
SCENES = [(0.0, 3.0), (3.0, 8.6), (8.6, 14.6), (14.6, 20.2), (20.2, 24.0)]
DURATION = SCENES[-1][1]
random.seed(7)


# ---------------------------------------------------------------- helpers
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out_cubic(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_out_back(t, s=1.9):
    t = clamp(t)
    t -= 1
    return t * t * ((s + 1) * t + s) + 1


def ease_in_out(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


_font_cache = {}


def font(size):
    if size not in _font_cache:
        _font_cache[size] = ImageFont.truetype(FONT, size)
    return _font_cache[size]


_text_cache = {}


def text_img(txt, size, color=WHITE, stroke=None):
    """Rendert Text mit schwarzer Kontur + Schatten als RGBA-Bild."""
    key = (txt, size, color)
    if key in _text_cache:
        return _text_cache[key]
    stroke = stroke if stroke is not None else max(4, size // 11)
    f = font(size)
    l, t, r, b = f.getbbox(txt, stroke_width=stroke)
    pad = 30
    w, h = r - l + pad * 2, b - t + pad * 2
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((pad - l + 6, pad - t + 10), txt, font=f,
                                fill=(0, 0, 0, 150), stroke_width=stroke,
                                stroke_fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(8))
    d = ImageDraw.Draw(shadow)
    d.text((pad - l, pad - t), txt, font=f, fill=color + (255,),
           stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
    _text_cache[key] = shadow
    return shadow


def paste_center(frame, img, cx, cy, scale=1.0, alpha=1.0, angle=0.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    if scale != 1.0:
        img = img.resize((max(1, int(img.width * scale)),
                          max(1, int(img.height * scale))), Image.BILINEAR)
    if angle:
        img = img.rotate(angle, resample=Image.BICUBIC, expand=True)
    if alpha < 1.0:
        a = img.getchannel("A").point(lambda v: int(v * alpha))
        img = img.copy()
        img.putalpha(a)
    frame.alpha_composite(img, (int(cx - img.width / 2), int(cy - img.height / 2)))


def pop_text(frame, txt, size, color, cx, cy, t_local, delay=0.0, dur=0.35, wobble=0.0):
    p = (t_local - delay) / dur
    if p <= 0:
        return
    s = ease_out_back(p)
    paste_center(frame, text_img(txt, size, color), cx, cy, scale=s,
                 alpha=clamp(p * 3), angle=wobble)


def fit_size(txt, max_size, max_w=940):
    size = max_size
    while size > 30 and font(size).getlength(txt) + size // 5 > max_w:
        size -= 4
    return size


# ---------------------------------------------------------------- backgrounds
def gradient(top, bottom):
    y = np.linspace(0, 1, H)[:, None, None]
    arr = np.array(top)[None, None, :] * (1 - y) + np.array(bottom)[None, None, :] * y
    return np.repeat(arr, W, axis=1)


def fairway_bg():
    arr = gradient((18, 120, 60), (6, 60, 30))
    # Mähstreifen (diagonal)
    yy, xx = np.mgrid[0:H, 0:W]
    stripes = ((xx + yy * 0.6) // 150) % 2
    arr = arr * (1 + 0.07 * stripes[..., None])
    # Vignette
    cx, cy = W / 2, H / 2
    r = np.sqrt(((xx - cx) / W) ** 2 + ((yy - cy) / H) ** 2)
    arr = arr * (1 - 0.55 * np.clip(r - 0.25, 0, 1))[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")


def space_bg():
    arr = gradient((8, 10, 35), (25, 15, 60))
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")


BG_FAIRWAY = fairway_bg()
BG_SPACE = space_bg()
STARS = [(random.randint(0, W), random.randint(0, H), random.uniform(1, 3.5),
          random.uniform(0, 6.28)) for _ in range(220)]

# ---------------------------------------------------------------- golf ball
N_DIMPLES = 336
_g = math.pi * (3 - math.sqrt(5))
DIMPLES = []
for i in range(N_DIMPLES):
    y = 1 - (i + 0.5) / N_DIMPLES * 2
    rr = math.sqrt(1 - y * y)
    DIMPLES.append((math.cos(_g * i) * rr, y, math.sin(_g * i) * rr))

_shade_cache = {}


def ball_shading(size):
    if size not in _shade_cache:
        yy, xx = np.mgrid[0:size, 0:size]
        c = size / 2
        nx, ny = (xx - c) / c, (yy - c) / c
        d = np.sqrt(nx ** 2 + ny ** 2)
        lx, ly = nx + 0.35, ny + 0.4  # Lichtquelle oben links
        light = np.clip(1.05 - 0.3 * np.sqrt(lx ** 2 + ly ** 2), 0.6, 1.0)
        rim = np.clip((d - 0.85) / 0.15, 0, 1) * 0.2
        val = np.clip(light - rim, 0, 1)
        _shade_cache[size] = val
    return _shade_cache[size]


def golf_ball(diam, rot=0.0, tilt=0.35):
    """Golfball mit 336 Dellen, gedreht um rot (Rad)."""
    ss = 2
    size = int(diam * ss)
    img = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, size - 1, size - 1), fill=245)
    c = size / 2
    rd = size * 0.04
    ca, sa = math.cos(rot), math.sin(rot)
    ct, st = math.cos(tilt), math.sin(tilt)
    for x, y, z in DIMPLES:
        x, z = x * ca + z * sa, -x * sa + z * ca
        y, z = y * ct - z * st, y * st + z * ct
        if z <= 0.12:
            continue
        px, py = c + x * c * 0.97, c + y * c * 0.97
        rx = rd * (0.35 + 0.65 * z)
        shade = int(212 + 22 * z)
        d.ellipse((px - rd, py - rx, px + rd, py + rx) if abs(y) > abs(x) else
                  (px - rx, py - rd, px + rx, py + rd), fill=shade)
    base = np.asarray(img, dtype=np.float32) / 255.0
    val = base * ball_shading(size)
    rgb = np.stack([val * 255, val * 255, val * 252], -1).astype(np.uint8)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((1, 1, size - 2, size - 2), fill=255)
    out = Image.fromarray(rgb).convert("RGBA")
    out.putalpha(mask)
    return out.resize((int(diam), int(diam)), Image.LANCZOS)


def ball_shadow(frame, cx, cy, w, alpha=0.35):
    sh = Image.new("RGBA", (int(w * 1.6), int(w * 0.5)), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((0, 0, sh.width - 1, sh.height - 1),
                               fill=(0, 0, 0, int(255 * alpha)))
    sh = sh.filter(ImageFilter.GaussianBlur(10))
    frame.alpha_composite(sh, (int(cx - sh.width / 2), int(cy - sh.height / 2)))


# ---------------------------------------------------------------- UI elements
def pill(frame, txt, cy, t_local):
    p = ease_out_back(t_local / 0.3)
    if p <= 0:
        return
    f = font(44)
    tw = f.getlength(txt)
    w, h = int(tw + 80), 86
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=43, fill=YELLOW + (255,))
    d.text((40, h / 2), txt, font=f, fill=(20, 20, 20), anchor="lm")
    paste_center(frame, img, W / 2, cy, scale=p)


def progress(frame, t):
    p = t / DURATION
    d = ImageDraw.Draw(frame)
    d.rectangle((0, H - 12, W, H), fill=(0, 0, 0, 120))
    d.rectangle((0, H - 12, int(W * p), H), fill=YELLOW + (255,))


def flash(frame, t_local):
    a = clamp(1 - t_local / 0.18)
    if a > 0:
        ov = Image.new("RGBA", (W, H), (255, 255, 255, int(200 * a)))
        frame.alpha_composite(ov)


def confetti(frame, t_local, origin, seed):
    if t_local < 0 or t_local > 2.2:
        return
    rnd = random.Random(seed)
    d = ImageDraw.Draw(frame)
    cols = [YELLOW, WHITE, RED, (60, 200, 255), (120, 255, 120)]
    for _ in range(70):
        ang = rnd.uniform(-math.pi, 0)
        sp = rnd.uniform(500, 1500)
        vx, vy = math.cos(ang) * sp, math.sin(ang) * sp
        x = origin[0] + vx * t_local
        y = origin[1] + vy * t_local + 1400 * t_local ** 2
        s = rnd.uniform(9, 18)
        a = int(255 * clamp(1 - t_local / 2.2))
        col = rnd.choice(cols) + (a,)
        rot = t_local * rnd.uniform(4, 12)
        dx, dy = math.cos(rot) * s, math.sin(rot) * s * 0.5
        d.polygon([(x - dx, y - dy), (x + dy, y - dx), (x + dx, y + dy), (x - dy, y + dx)],
                  fill=col)


# ---------------------------------------------------------------- scenes
def scene_hook(frame, t):
    # Ball fällt von oben und springt
    g = 4200
    y0, floor = -200, 1250
    tt = t
    t_hit = math.sqrt(2 * (floor - y0) / g)
    if tt < t_hit:
        y = y0 + 0.5 * g * tt * tt
    else:
        v = g * t_hit * 0.45
        tb = tt - t_hit
        hop = v * tb - 0.5 * g * tb * tb
        if hop < 0:
            v2 = v * 0.4
            tb2 = tb - 2 * v / g
            hop = max(0, v2 * tb2 - 0.5 * g * tb2 * tb2)
        y = floor - hop
    ball_shadow(frame, W / 2, floor + 135, 230, 0.4)
    paste_center(frame, golf_ball(260, rot=t * 3), W / 2, y)

    w = math.sin(t * 7) * 1.5
    pop_text(frame, "99% WISSEN", 110, WHITE, W / 2, 470, t, 0.1, wobble=w)
    pop_text(frame, "DAS NICHT", 110, WHITE, W / 2, 600, t, 0.35, wobble=-w)
    pop_text(frame, "ÜBER GOLF", 130, YELLOW, W / 2, 760, t, 0.6, wobble=w)
    if t > 1.4:
        pop_text(frame, "Bis zum Ende schauen!", 52, WHITE, W / 2, 1560, t, 1.4)


def count_up(t, start, dur, target):
    return int(target * ease_out_cubic((t - start) / dur))


def scene_dimples(frame, t):
    flash(frame, t)
    pill(frame, "FAKT 1 / 3", 330, t)
    pop_text(frame, "Ein Golfball hat", 70, WHITE, W / 2, 470, t, 0.15)
    zoom = 1 + 0.06 * math.sin(t * 2)
    s = ease_out_back((t - 0.2) / 0.5)
    if s > 0:
        paste_center(frame, golf_ball(560, rot=t * 0.9), W / 2, 900, scale=s * zoom)
    n = count_up(t, 0.6, 1.6, 336)
    if t > 0.6:
        paste_center(frame, text_img(f"{n}", 170, YELLOW), W / 2, 1290,
                     scale=1 + (0.15 if 2.2 < t < 2.35 else 0))
    pop_text(frame, "DELLEN", 90, WHITE, W / 2, 1440, t, 2.1)
    if t > 3.0:
        # Unteres Infokärtchen
        p = ease_out_cubic((t - 3.0) / 0.4)
        y = 1610 + (1 - p) * 300
        paste_center(frame, text_img("Ohne Dellen fliegt er nur", 52, WHITE), W / 2, y, alpha=p)
        paste_center(frame, text_img("etwa HALB so weit!", 64, YELLOW), W / 2, y + 85, alpha=p)


def flag(frame, x, y_ground, t, h=520):
    d = ImageDraw.Draw(frame)
    d.line((x, y_ground, x, y_ground - h), fill=(240, 240, 240, 255), width=12)
    pts_top, pts_bot = [], []
    for i in range(13):
        u = i / 12
        wave_ = math.sin(t * 7 - u * 5) * 18 * u
        pts_top.append((x + 6 + u * 230, y_ground - h + wave_))
        pts_bot.append((x + 6 + u * 230, y_ground - h + 140 - u * 50 + wave_))
    d.polygon(pts_top + pts_bot[::-1], fill=RED + (255,))


def scene_hole(frame, t):
    flash(frame, t)
    pill(frame, "FAKT 2 / 3", 330, t)
    pop_text(frame, "Chance auf ein", 66, WHITE, W / 2, 460, t, 0.1)
    pop_text(frame, "HOLE-IN-ONE:", 96, YELLOW, W / 2, 570, t, 0.3)

    # Grün
    green = Image.new("RGBA", (W + 400, 520), (0, 0, 0, 0))
    gd = ImageDraw.Draw(green)
    gd.ellipse((0, 0, green.width - 1, green.height - 1), fill=(40, 170, 80, 255))
    green = green.filter(ImageFilter.GaussianBlur(3))
    frame.alpha_composite(green, (-200, 960))
    hx, hy = 690, 1210
    d = ImageDraw.Draw(frame)
    d.ellipse((hx - 85, hy - 30, hx + 85, hy + 30), fill=(10, 25, 12, 255))
    d.ellipse((hx - 85, hy - 30, hx + 85, hy + 22), outline=(230, 230, 230, 255), width=5)
    flag(frame, hx, hy, t)

    # Ball rollt ins Loch
    t_in = 2.3
    if t < t_in:
        p = ease_in_out(clamp((t - 0.5) / (t_in - 0.5)))
        bx = -120 + (hx - -120) * p
        by = hy + 40 - 25 * p
        ball_shadow(frame, bx + 10, by + 50, 90, 0.3)
        paste_center(frame, golf_ball(110, rot=-p * 14), bx, by)
    elif t < t_in + 0.25:
        p = (t - t_in) / 0.25
        paste_center(frame, golf_ball(110, rot=0), hx, hy + 5 + 40 * p, scale=1 - 0.6 * p,
                     alpha=1 - p)
    confetti(frame, t - t_in - 0.15, (hx, hy - 20), 11)

    if t > t_in + 0.15:
        lt = t - t_in - 0.15
        shake = math.sin(lt * 60) * 8 * clamp(1 - lt / 0.4)
        pop_text(frame, "1 zu 12.500", 150, WHITE, W / 2 + shake, 1460, lt, 0, 0.4)
        pop_text(frame, "(als Amateur)", 50, WHITE, W / 2, 1590, lt, 0.4)


def moon_img():
    size = 1500
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, size - 1, size - 1), fill=(185, 185, 195, 255))
    rnd = random.Random(3)
    for _ in range(40):
        r = rnd.uniform(25, 110)
        a = rnd.uniform(0, 6.28)
        dist = rnd.uniform(0, size / 2 - r - 10)
        x, y = size / 2 + math.cos(a) * dist, size / 2 + math.sin(a) * dist
        d.ellipse((x - r, y - r * 0.8, x + r, y + r * 0.8), fill=(150, 150, 160, 255))
        d.ellipse((x - r * 0.8, y - r * 0.6, x + r * 0.9, y + r * 0.75), fill=(165, 165, 175, 255))
    glow = Image.new("RGBA", (size + 200, size + 200), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((60, 60, size + 140, size + 140), fill=(200, 200, 255, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    glow.alpha_composite(img, (100, 100))
    return glow


MOON = moon_img()


def scene_moon(frame, t):
    frame.paste(BG_SPACE)
    d = ImageDraw.Draw(frame)
    for x, y, r, ph in STARS:
        a = int(140 + 115 * math.sin(t * 3 + ph))
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, a))
    rise = ease_out_cubic(t / 0.9)
    frame.alpha_composite(MOON, (int(W / 2 - MOON.width / 2), int(1330 + (1 - rise) * 500)))
    flash(frame, t)
    pill(frame, "FAKT 3 / 3", 330, t)
    pop_text(frame, "Golf wurde schon", 70, WHITE, W / 2, 470, t, 0.2)
    pop_text(frame, "AUF DEM MOND", 108, YELLOW, W / 2, 590, t, 0.45)
    pop_text(frame, "gespielt!", 70, WHITE, W / 2, 705, t, 0.7)

    # Ball fliegt in Zeitlupe (Mond-Schwerkraft)
    t0 = 1.1
    if t > t0:
        lt = t - t0
        x0, y0 = 120, 1380
        vx, vy, g = 260, -190, 85
        trail = []
        for k in range(18):
            tk = max(0, lt - k * 0.06)
            trail.append((x0 + vx * tk, y0 + vy * tk + 0.5 * g * tk * tk))
        for k, (x, y) in enumerate(reversed(trail)):
            r = 4 + k * 0.8
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 12 + k * 7))
        bx, by = trail[0]
        paste_center(frame, golf_ball(80, rot=lt * 2), bx, by)

    if t > 2.6:
        pop_text(frame, "Alan Shepard, 1971", 58, WHITE, W / 2, 870, t, 2.6)
        pop_text(frame, "Apollo 14", 50, YELLOW, W / 2, 950, t, 2.85)


def scene_cta(frame, t):
    flash(frame, t)
    w = math.sin(t * 6) * 2
    pop_text(frame, "WELCHER FAKT", 104, WHITE, W / 2, 500, t, 0.05, wobble=w)
    pop_text(frame, "HAT DICH", 104, WHITE, W / 2, 630, t, 0.2, wobble=-w)
    pop_text(frame, "ÜBERRASCHT?", 112, YELLOW, W / 2, 770, t, 0.35, wobble=w)
    bob = math.sin(t * 5) * 18
    if t > 0.2:
        paste_center(frame, golf_ball(240, rot=t * 2.5), W / 2, 1060 + bob,
                     scale=ease_out_back((t - 0.2) / 0.5))
    pop_text(frame, "Schreib's in die", 58, WHITE, W / 2, 1330, t, 0.8)
    pop_text(frame, "Kommentare!", 74, YELLOW, W / 2, 1415, t, 1.0)
    pop_text(frame, "+ Folgen für Teil 2", 58, WHITE, W / 2, 1560, t, 1.5)


SCENE_FUNCS = [scene_hook, scene_dimples, scene_hole, scene_moon, scene_cta]


def render_frame(i):
    t = i / FPS
    frame = BG_FAIRWAY.copy()
    for (a, b), fn in zip(SCENES, SCENE_FUNCS):
        if a <= t < b:
            fn(frame, t - a)
            break
    progress(frame, t)
    return frame.convert("RGB")


# ---------------------------------------------------------------- audio
SR = 44100


def make_audio(path):
    n = int(DURATION * SR)
    out = np.zeros(n)
    t = np.arange(n) / SR
    bpm = 120
    beat = 60 / bpm
    rng = np.random.default_rng(1)

    def add(sig, at):
        s = int(at * SR)
        e = min(n, s + len(sig))
        if s < n:
            out[s:e] += sig[: e - s]

    # Kick
    kt = np.arange(int(0.35 * SR)) / SR
    kick = np.sin(2 * np.pi * (50 + 120 * np.exp(-kt * 30)) * kt) * np.exp(-kt * 9)
    # Hi-Hat
    ht = np.arange(int(0.06 * SR)) / SR
    hat = rng.standard_normal(len(ht))
    hat = np.diff(hat, prepend=0) * np.exp(-ht * 70) * 0.25
    # Clap
    ct = np.arange(int(0.2 * SR)) / SR
    clap = rng.standard_normal(len(ct)) * np.exp(-ct * 25) * 0.35

    bass_notes = [55.0, 55.0, 65.41, 49.0]  # A, A, C, G
    k = 0
    while k * beat < DURATION:
        at = k * beat
        add(kick * 0.9, at)
        add(hat, at + beat / 2)
        if k % 2 == 1:
            add(clap, at)
        note = bass_notes[(k // 4) % 4]
        bt = np.arange(int(beat * SR)) / SR
        add(np.sin(2 * np.pi * note * bt) * np.exp(-bt * 3) * 0.35, at)
        # Plucks
        if k % 2 == 0:
            pt = np.arange(int(0.3 * SR)) / SR
            f = note * 4 * (1.5 if k % 8 == 4 else 1)
            add(np.sign(np.sin(2 * np.pi * f * pt)) * np.exp(-pt * 14) * 0.06, at + beat * 0.75)
        k += 1

    # Whoosh bei Szenenwechsel
    wt = np.arange(int(0.45 * SR)) / SR
    noise = rng.standard_normal(len(wt))
    env = np.sin(np.pi * wt / wt[-1]) ** 2
    whoosh = np.convolve(noise, np.ones(30) / 30, mode="same") * env * 0.9
    for a, _ in SCENES[1:]:
        add(whoosh, a - 0.3)

    # "Plopp" ins Loch + Ding
    pt = np.arange(int(0.25 * SR)) / SR
    plop = np.sin(2 * np.pi * (300 - 500 * pt) * pt) * np.exp(-pt * 20) * 0.8
    add(plop, SCENES[2][0] + 2.3)
    dt = np.arange(int(1.0 * SR)) / SR
    ding = (np.sin(2 * np.pi * 1318.5 * dt) + 0.5 * np.sin(2 * np.pi * 1975.5 * dt)) * np.exp(-dt * 4) * 0.25
    for at in (SCENES[1][0] + 2.2, SCENES[2][0] + 2.45, SCENES[3][0] + 0.45):
        add(ding, at)

    # Fade-out
    fade = np.clip((DURATION - t) / 0.6, 0, 1)
    out *= fade
    out /= np.max(np.abs(out)) * 1.1
    pcm = (out * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ---------------------------------------------------------------- main
def main():
    make_audio("audio.wav")
    n_frames = int(DURATION * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", "audio.wav",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
           "golf_reel.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n_frames):
        proc.stdin.write(render_frame(i).tobytes())
        if i % 60 == 0:
            print(f"{i}/{n_frames}", flush=True)
    proc.stdin.close()
    proc.wait()
    render_frame(int(1.8 * FPS)).save("thumbnail.jpg", quality=92)
    print("fertig: golf_reel.mp4")


if __name__ == "__main__":
    main()
