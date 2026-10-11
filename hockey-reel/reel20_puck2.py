"""Reel 20: THE PUCK pt. 2 – Brand-Motion-Design (Apple-/Spotify-Brand-Stil), 140 BPM, 33 Beats (14,1 s).

Stilvorlage: schnelle Beat-Schnitte, Kreis-Raster, riesige angeschnittene Typo mit hochgestellten Labels,
Farbflächen, Motion-Blur-Ball als Übergang, Karaoke-Zeilen, glühendes Wort, Logo-Reveal.
Farben: Schwarz / Weiß / Bladesandpucks-Orange. Reine 2D-Grafik (cairo + PIL), Musik selbst synthetisiert (Trap, 140 BPM).
Fakten: Puck aus vulkanisiertem Gummi, vor Spielen gefroren (weniger Springen).
Aufruf: python3 reel20_puck2.py -> reel20_puck2.mp4 + reel20_thumbnail.jpg
"""
import math
import os
import subprocess
import time
import wave

import cairocffi as cairo
import numpy as np
from PIL import Image, ImageFilter

import reel15_puck as R15
from reel15_puck import c01, smooth, e_out, e_in, e_back, lerp, ifont

W, H, FPS = 1080, 1920, 30
BPM = 140
B = 60.0 / BPM
NBEATS = 33
DUR = NBEATS * B
HERE = R15.HERE
BLACK = (10, 10, 12)
WHITE = (247, 247, 245)
OR = (255, 140, 50)
DIM = (120, 120, 126)


# ================================================================= Bausteine
def new_ctx(bg):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    c = cairo.Context(s)
    c.set_source_rgb(*[v / 255 for v in bg])
    c.paint()
    return s, c


def to_pil(s):
    s.flush()
    return Image.frombuffer("RGBA", (W, H), bytes(s.get_data()), "raw", "BGRa", 0, 1).copy()


def rgb(c, col, a=1.0):
    c.set_source_rgba(col[0] / 255, col[1] / 255, col[2] / 255, a)


def circle(c, x, y, r, col, fill=True, lw=8, a=1.0):
    if r <= 0:
        return
    rgb(c, col, a)
    c.arc(x, y, r, 0, 2 * math.pi)
    if fill:
        c.fill()
    else:
        c.set_line_width(lw)
        c.stroke()


def rect(c, x, y, w, h, col, a=1.0):
    rgb(c, col, a)
    c.rectangle(x, y, w, h)
    c.fill()


def streak(img, path, s0, s1, r, col, n=48):
    """Ball mit Bewegungsunschärfe entlang path(s); Kopf bei s1."""
    s, c = new_ctx((0, 0, 0))
    c.set_operator(cairo.OPERATOR_CLEAR)
    c.paint()
    c.set_operator(cairo.OPERATOR_OVER)
    for i in range(n):
        q = i / (n - 1)
        x, y = path(lerp(s0, s1, q))
        circle(c, x, y, r * (0.55 + 0.45 * q), col, a=0.06 + 0.5 * q ** 3)
    x, y = path(s1)
    circle(c, x, y, r, col)
    lay = to_pil(s).filter(ImageFilter.GaussianBlur(2.2))
    img.alpha_composite(lay)


def text_img(txt, size, wght, col):
    return R15.line_img(txt, size, wght, col)


def paste_c(img, im, cx, cy, a=1.0):
    if a <= 0:
        return
    if a < 1:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    R15.put(img, im, cx - im.width / 2, cy - im.height / 2)


def paste_l(img, im, x, cy, a=1.0):
    paste_c(img, im, x + im.width / 2, cy, a)


def sup_text(img, txt, sup, size, x, cy, col, sup_col=None, wght=700, a=1.0):
    """Text mit hochgestelltem Label; gibt die Breite zurück."""
    t = text_img(txt, size, wght, col)
    paste_l(img, t, x, cy, a)
    w = t.width
    if sup:
        s = text_img(sup, int(size * 0.36), 600, sup_col or col)
        paste_l(img, s, x + w + 6, cy - size * 0.33, a)
        w += 6 + s.width
    return w


def masked_reveal(img, im, x, cy, p, direction="up"):
    """Zeile gleitet maskiert herein."""
    if p <= 0:
        return
    box = Image.new("RGBA", (im.width, im.height + 16), (0, 0, 0, 0))
    off = (1 - e_out(p, 4)) * (im.height + 16)
    R15.put(box, im, 0, 8 + (off if direction == "up" else -off))
    R15.put(img, box, x, cy - im.height / 2 - 8)


_MARK = {}


def mark(size, dark=False):
    key = (size, dark)
    if key not in _MARK:
        m = Image.open(os.path.join(HERE, "brand", "bladesandpucks_mark_transparent.png")).convert("RGBA")
        m = m.crop(m.getbbox())
        if dark:                                        # weiße Flächen -> Schwarz, Orange bleibt
            a = np.asarray(m).astype(np.int16).copy()
            sat = a[..., :3].max(-1) - a[..., :3].min(-1)
            wh = sat < 40
            a[wh, 0], a[wh, 1], a[wh, 2] = BLACK
            m = Image.fromarray(a.astype(np.uint8), "RGBA")
        s = size / m.height
        _MARK[key] = m.resize((int(m.width * s), size), Image.LANCZOS)
    return _MARK[key]


def eighth_pulse(t, k=6.0):
    return math.exp(-((t % (B / 2)) / (B / 2)) * k)


def beat_pulse(t, k=5.0):
    return math.exp(-((t % B) / B) * k)


# ================================================================= Szenen (lt = Zeit seit Szenenstart)
def grid(c, spacing, ang, scale, fn):
    cx, cy = W / 2, H / 2
    ca, sa = math.cos(ang), math.sin(ang)
    n = int(1400 / (spacing * scale)) + 2
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            gx, gy = i * spacing * scale, j * spacing * scale
            x, y = cx + gx * ca - gy * sa, cy + gx * sa + gy * ca
            if -200 < x < W + 200 and -200 < y < H + 200:
                fn(c, i, j, x, y)


def sc_dots(t, lt, u):
    s, c = new_ctx(WHITE)
    pul = eighth_pulse(t)
    off = lt * 60

    def f(c, i, j, x, y):
        if i == 0 and j == 0:
            return
        circle(c, x - off * 0.5, y - off, 58 * (1 + 0.14 * pul * ((i + j) % 2)), BLACK)
    grid(c, 168, 0.0, 1.0, f)
    circle(c, W / 2, H / 2, 64 + 6 * pul, BLACK)
    img = to_pil(s)
    paste_c(img, mark(78), W / 2, H / 2, smooth(0.35 * B, 0.6 * B, lt))
    lab = text_img("THE PUCK  pt. 2", 36, 750, BLACK)
    s2, c2 = new_ctx(BLACK)
    c2.set_operator(cairo.OPERATOR_CLEAR)
    c2.paint()
    c2.set_operator(cairo.OPERATOR_OVER)
    pw, ph = lab.width + 64, lab.height + 34
    rgb(c2, WHITE)
    c2.new_sub_path()
    for (ax, ay, a0) in ((W / 2 + pw / 2 - ph / 2, 300, -math.pi / 2), (W / 2 - pw / 2 + ph / 2, 300, math.pi / 2)):
        c2.arc(ax, ay, ph / 2, a0, a0 + math.pi)
    c2.close_path()
    c2.fill()
    img.alpha_composite(to_pil(s2))
    paste_c(img, lab, W / 2, 300)
    return img


def sc_rings(t, lt, u):
    s, c = new_ctx(BLACK)
    k = int(lt / B)
    ang = math.radians(9) * (k + e_out(c01((lt - k * B) / 0.18), 3))

    def f(c, i, j, x, y):
        if i == 0 and j == 0:
            return
        circle(c, x, y, 60, WHITE, fill=False, lw=9)
    grid(c, 168, ang, 1.0, f)
    circle(c, W / 2, H / 2, 60, WHITE, fill=False, lw=9)
    img = to_pil(s)
    sc = e_back(c01(lt / 0.2), 2.2)
    if sc > 0.02:
        paste_c(img, mark(max(4, int(66 * sc))), W / 2, H / 2)
    return img


def sc_checker(t, lt, u):
    s, c = new_ctx(BLACK)
    k8 = int(lt / (B / 2))
    zoom = lerp(1.25, 1.4, u)

    def f(c, i, j, x, y):
        if i == 0 and j == 0:
            return
        filled = (i + j + k8) % 2 == 0
        circle(c, x, y, 60 * zoom, WHITE, fill=filled, lw=9 * zoom)
    grid(c, 168, math.radians(18), zoom, f)
    circle(c, W / 2, H / 2, 60 * zoom, WHITE, fill=False, lw=9 * zoom)
    img = to_pil(s)
    paste_c(img, mark(int(66 * zoom)), W / 2, H / 2)
    return img


def sc_pop(t, lt, u):
    s, c = new_ctx(BLACK)
    q = c01((lt - B) / B)                                # zweiter Beat: alles schrumpft, Mitte wächst

    def f(c, i, j, x, y):
        if i == 0 and j == 0:
            return
        r = 68 * (1 + 0.1 * beat_pulse(t)) * (1 - e_in(q, 2))
        circle(c, x, y, r, WHITE)
    grid(c, 168, math.radians(18), 1.4, f)
    rc = lerp(84, 260, e_in(q, 3))
    circle(c, W / 2, H / 2, rc, WHITE)
    img = to_pil(s)
    paste_c(img, mark(int(rc * 1.1), dark=True), W / 2, H / 2)
    return img


def sc_logo(t, lt, u):
    img = to_pil(new_ctx(BLACK)[0])
    q = e_out(c01((lt - B * 0.9) / 0.35), 4)
    word = text_img("bladesandpucks", 76, 800, WHITE)
    m = mark(124)
    total = m.width + 34 + word.width
    mx = lerp(W / 2, W / 2 - total / 2 + m.width / 2, q)
    sc = e_back(c01(lt / 0.22), 2.0)
    paste_c(img, m.resize((max(2, int(m.width * sc)), max(2, int(m.height * sc)))), mx, H / 2)
    if q > 0:
        x0 = mx + m.width / 2 + 34
        vis = int(word.width * q)
        if vis > 2:
            paste_l(img, word.crop((0, 0, vis, word.height)), x0, H / 2 + 6, c01(q * 1.5))
    return img


def sc_orange_word(t, lt, u):
    s, c = new_ctx(BLACK)
    wipe = e_out(c01(lt / 0.2), 4)
    rect(c, W * (1 - wipe), 0, W * wipe + 1, H, OR)
    img = to_pil(s)
    paste_c(img, text_img("Puck", 110, 700, BLACK), W / 2 - 40, H / 2, c01((lt - 0.12) / 0.1))

    def path(sv):
        return (lerp(W + 120, W / 2 + 190, sv) + 160 * math.sin(math.pi * sv) * 0.6,
                H / 2 + 260 * (1 - sv) ** 2 - 120 * math.sin(math.pi * sv))
    p = e_out(c01((lt - 0.1) / (B * 1.3)), 3)
    if p > 0:
        streak(img, path, max(0.0, p - lerp(0.45, 0.0, p)), p, 34, BLACK)
    return img


def giant_scene(lt, u, shift0, shift1, hi):
    img = to_pil(new_ctx(WHITE)[0])
    top = Image.new("RGBA", (W, 980), BLACK + (255,))
    img.alpha_composite(top)
    g = text_img("PUCK", 760, 850, WHITE)
    x = lerp(shift0, shift1, e_out(u, 2))
    R15.put(img, g, x, 490 - g.height / 2)
    if hi:                                                 # "CK" in Orange
        pu = ifont(760, 850).getlength("PU")
        ck = g.crop((int(pu), 0, g.width, g.height))
        a = np.asarray(ck).copy()
        a[..., 0], a[..., 1], a[..., 2] = OR
        R15.put(img, Image.fromarray(a, "RGBA"), x + pu, 490 - g.height / 2)
    s, c = new_ctx(BLACK)
    c.set_operator(cairo.OPERATOR_CLEAR)
    c.paint()
    c.set_operator(cairo.OPERATOR_OVER)
    sq = e_out(c01(lt / 0.16), 3)
    rect(c, 560, 700 + 420 * (1 - sq), 520, 520 * sq, OR)
    img.alpha_composite(to_pil(s))
    if sq > 0.9:
        sup_text(img, "Orange", "(1)", 34, 760, 960, BLACK)
    sup_text(img, "Black", "(2)", 34, 70, 1180, BLACK, a=c01((lt - 0.1) / 0.1))
    sup_text(img, "White", "(3)", 34, 70, 940, WHITE, a=c01((lt - 0.05) / 0.1))
    return img


def sc_giant1(t, lt, u):
    return giant_scene(lt, u, 120, -520, False)


def sc_giant2(t, lt, u):
    return giant_scene(lt, u, -640, -1200, True)


def sc_for(t, lt, u):
    img = to_pil(new_ctx(WHITE)[0])
    q = c01(lt / (B * 0.9))
    if q < 1:
        g = text_img("for", 900, 800, BLACK)
        sc = lerp(1.0, 0.25, e_in(q, 2))
        gi = g.resize((int(g.width * sc), int(g.height * sc)), Image.BILINEAR)
        if q > 0.4:
            gi = gi.filter(ImageFilter.GaussianBlur((q - 0.4) * 30))
        paste_c(img, gi, W / 2 + 80 * q, H / 2, 1 - smooth(0.8, 1.0, q))
    if lt > B * 0.85:
        p = c01((lt - B * 0.85) / 0.22)
        line = text_img("Hockey for everyone", 70, 700, BLACK)
        masked_reveal(img, line, W / 2 - line.width / 2, H / 2, p)
        s, c = new_ctx(BLACK)
        c.set_operator(cairo.OPERATOR_CLEAR)
        c.paint()
        c.set_operator(cairo.OPERATOR_OVER)
        circle(c, W / 2 + line.width / 2 + 60 + 20 * math.sin(lt * 9), H / 2 - 80 + 30 * math.cos(lt * 7), 11, OR)
        img.alpha_composite(to_pil(s))
    return img


def sc_lace(t, lt, u):
    img = to_pil(new_ctx(BLACK)[0])
    split = lerp(1080, 980, e_out(u, 3))
    img.alpha_composite(Image.new("RGBA", (W, int(split)), WHITE + (255,)))
    line = text_img("Lace up your", 70, 700, BLACK)
    masked_reveal(img, line, W / 2 - line.width / 2, split - 70, c01(lt / 0.22))

    def path(sv):
        return lerp(-80, W / 2 - 40, sv), split + 260 - 120 * math.sin(math.pi * sv * 0.8)
    p = e_out(c01((lt - 0.15) / (B * 1.4)), 3)
    if p > 0:
        streak(img, path, max(0.0, p - lerp(0.5, 0.0, p)), p, 30, WHITE)
    return img


def sc_fav(t, lt, u):
    img = to_pil(new_ctx(BLACK)[0])
    line = text_img("Favorite shot...", 72, 700, WHITE)
    masked_reveal(img, line, W / 2 - line.width / 2 + 40, H / 2, c01(lt / 0.2))

    def path(sv):
        return (lerp(-60, W / 2 - line.width / 2 - 40, sv),
                H / 2 + 380 * (1 - sv) ** 1.5 - 60 * math.sin(math.pi * sv))
    p = e_out(c01((lt - 0.05) / (B * 1.2)), 3)
    if p > 0:
        streak(img, path, max(0.0, p - lerp(0.55, 0.0, p)), p, 28, WHITE)
    return img


def spec_scene(lt, title, sub, giant):
    s, c = new_ctx(WHITE)
    wipe = e_out(c01(lt / 0.18), 4)
    rect(c, W - (W - 470) * wipe, 0, (W - 470) * wipe + 1, H, OR)
    img = to_pil(s)
    paste_c(img, text_img(title, 64, 600, BLACK), 235, H / 2 - 30)
    paste_c(img, text_img(sub, 30, 500, DIM), 235, H / 2 + 34)
    g = text_img(giant, 820, 850, BLACK)
    x = 470 + lerp(140, 30, e_out(c01(lt / B), 3))
    R15.put(img, g, x, H / 2 + 120 - g.height / 2)
    return img


def sc_rubber(t, lt, u):
    return spec_scene(lt, "Rubber", "Vulcanized", "Pu")


def sc_frozen(t, lt, u):
    return spec_scene(lt, "Frozen", "before games", "ck")


LYRICS = [(["Snap,", "slap,", "wrist,", "backhand"], "(pick one)"),
          (["Dangle,", "deke,", "toe", "drag"], "(like a pro)"),
          (["Tape,", "blade,", "ice,", "bar down"], "(ping)"),
          (["Puck,", "puck,", "puck,", "puck"], "(bring it)")]


def sc_lyrics(t, lt, u):
    big = Image.new("RGBA", (W, H), BLACK + (255,))
    k = min(15, int(lt / (B / 2)))
    cur_line = k // 4
    size, gap = 72, 112
    zoom = lerp(1.02, 1.12, e_in(u, 1.5))
    yc = H / 2 + (1.5 - lerp(0, 3, (lt / (8 * B)))) * gap * 0.55
    for li, (words_, sup) in enumerate(LYRICS):
        y = yc + (li - 1.5) * gap
        x = 64
        a = 1.0 if li <= cur_line else 0.45
        for wi, wd in enumerate(words_):
            idx = li * 4 + wi
            col = OR if idx == k else WHITE
            im = text_img(wd, size, 750, col)
            paste_l(big, im, x, y, a)
            x += im.width + 18
        s = text_img(sup, 24, 600, WHITE)
        paste_l(big, s, x - 6, y - size * 0.34, a)
    if zoom > 1.001:
        w2, h2 = W / zoom, H / zoom
        cy = lerp(H / 2, yc + (cur_line - 1.5) * gap, 0.6)
        x0 = 0
        y0 = min(max(cy - h2 / 2, 0), H - h2)
        big = big.transform((W, H), Image.EXTENT, (x0, y0, x0 + w2, y0 + h2), Image.BICUBIC)
    return big


def sc_glow(t, lt, u):
    img = to_pil(new_ctx(BLACK)[0])
    g = text_img("puck", 150, 700, OR)
    pad = 120
    a = Image.new("L", (g.width + 2 * pad, g.height + 2 * pad), 0)
    a.paste(g.getchannel("A"), (pad, pad))
    glow = Image.new("RGBA", a.size, OR + (0,))
    glow.putalpha(a.filter(ImageFilter.GaussianBlur(40)).point(lambda v: min(255, int(v * 2.2))))
    halo = Image.new("RGBA", a.size, (255, 255, 255, 0))
    halo.putalpha(a.filter(ImageFilter.GaussianBlur(90)).point(lambda v: int(v * 0.35)))
    sc = lerp(0.94, 1.04, u)
    for layer_ in (halo, glow):
        li = layer_.resize((int(layer_.width * sc), int(layer_.height * sc)), Image.BILINEAR)
        paste_c(img, li, W / 2, H / 2, c01(lt / 0.12))
    gi = g.resize((int(g.width * sc), int(g.height * sc)), Image.BILINEAR)
    paste_c(img, gi, W / 2, H / 2, c01(lt / 0.12))
    return img


def sc_end(t, lt, u):
    img = to_pil(new_ctx(WHITE)[0])
    q = e_out(c01((lt - B) / 0.35), 4)
    word = text_img("bladesandpucks", 76, 800, BLACK)
    m = mark(124, dark=True)
    total = m.width + 34 + word.width
    mx = lerp(W / 2, W / 2 - total / 2 + m.width / 2, q)
    sc = e_back(c01(lt / 0.22), 2.0)
    paste_c(img, m.resize((max(2, int(m.width * sc)), max(2, int(m.height * sc)))), mx, H / 2)
    if q > 0:
        vis = int(word.width * q)
        if vis > 2:
            paste_l(img, word.crop((0, 0, vis, word.height)), mx + m.width / 2 + 34, H / 2 + 6, c01(q * 1.5))
    lab = text_img("THE PUCK  pt. 2", 34, 700, DIM)
    masked_reveal(img, lab, W / 2 - lab.width / 2, H / 2 + 170, c01((lt - B * 1.3) / 0.25))
    return img


SCENES = [(0, 2, sc_dots), (2, 4, sc_rings), (4, 6, sc_checker), (6, 8, sc_pop), (8, 10, sc_logo),
          (10, 12, sc_orange_word), (12, 13, sc_giant1), (13, 14, sc_giant2), (14, 16, sc_for),
          (16, 18, sc_lace), (18, 20, sc_fav), (20, 21, sc_rubber), (21, 22, sc_frozen),
          (22, 30, sc_lyrics), (30, 31, sc_glow), (31, 33, sc_end)]


def compose(t):
    bt = t / B
    for b0, b1, fn in SCENES:
        if b0 <= bt < b1 or (fn is sc_end and bt >= b0):
            lt = t - b0 * B
            img = fn(t, lt, c01(lt / ((b1 - b0) * B)))
            break
    zp = 1 + 0.035 * math.exp(-lt * 16)                     # Zoom-Punch auf jedem Schnitt
    if zp > 1.002:
        w2, h2 = W / zp, H / zp
        img = img.transform((W, H), Image.EXTENT, ((W - w2) / 2, (H - h2) / 2, (W + w2) / 2, (H + h2) / 2),
                            Image.BILINEAR)
    arr = np.asarray(img.convert("RGB")).astype(np.float32) / 255
    arr += np.random.default_rng(int(t * 1000)).normal(0, 0.008, arr.shape[:2])[..., None]
    return (np.clip(arr, 0, 1) * 255).astype(np.uint8)


# ================================================================= Musik (Trap, 140 BPM, a-Moll)
SR = 44100


def make_audio(path):
    n = int(DUR * SR) + SR // 2
    rng = np.random.default_rng(20)
    mus, sfx = np.zeros(n), np.zeros(n)

    def tt(sec):
        return np.arange(int(sec * SR)) / SR

    def put_(buf, sig, at, vol=1.0):
        st = int(round(at * SR))
        e = min(n, st + len(sig))
        if 0 <= st < n:
            buf[st:e] += sig[: e - st] * vol

    def lp(x, k):
        c = np.cumsum(np.concatenate([np.zeros(k), x]))
        return (c[k:] - c[:-k]) / k

    def hp(x, k):
        return x - lp(x, k)

    def noise(sec):
        return rng.standard_normal(int(sec * SR))

    def kick(vol=1.0):
        x = tt(0.3)
        f = 48 + 170 * np.exp(-x * 40)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 10) * 3.2) * vol

    def clap(vol=1.0):
        x = tt(0.25)
        env = sum(np.exp(-np.maximum(x - d, 0) * 60) * (x >= d) for d in (0.0, 0.01, 0.022))
        return hp(noise(0.25), 3) * (env * 0.5 + np.exp(-x * 14) * 0.5) * 0.7 * vol

    def hat(vol=0.16):
        return hp(noise(0.035), 2) * np.exp(-tt(0.035) * 140) * vol

    def b808(freq, dur, glide=0.0, f_to=None):
        x = tt(dur)
        f = freq * (1 + glide * np.exp(-x * 9))
        if f_to:
            f = f + (f_to - freq) * np.clip((x - dur * 0.55) / (dur * 0.35), 0, 1)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * 2.2) * np.minimum(x / 0.004, 1) * np.exp(-x * 1.4) * 0.85

    def bell(freq, dur=0.5, vol=0.2):
        x = tt(dur)
        sig = np.sin(2 * np.pi * freq * x) + 0.45 * np.sin(2 * np.pi * freq * 2.76 * x) * np.exp(-x * 9) + \
            0.25 * np.sin(2 * np.pi * freq * 5.4 * x) * np.exp(-x * 20)
        return sig * np.exp(-x * 5.5) * np.minimum(x / 0.002, 1) * vol

    def blip(freq=2200, vol=0.12):
        x = tt(0.05)
        return np.sin(2 * np.pi * freq * x) * np.exp(-x * 90) * vol

    def whoosh(dur=0.35, vol=1.0):
        x = tt(dur)
        nz = noise(dur)
        env = np.sin(np.pi * x / dur) ** 2
        return (lp(nz, 26) * (1 - x / dur) + (lp(nz, 5) - lp(nz, 26)) * (x / dur) * 1.4) * env * 1.2 * vol

    def riser(dur, vol=1.0):
        x = tt(dur)
        sw = np.sin(2 * np.pi * np.cumsum(300 + 2600 * (x / dur) ** 2) / SR) * (x / dur) ** 3 * 0.15
        return (hp(noise(dur), 4) * (x / dur) ** 2 * 0.35 + sw) * vol

    def impact(vol=1.0):
        x = tt(1.2)
        f = 40 + 120 * np.exp(-x * 16)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 3) * 2.4) * vol

    A, C, D, E, G = 55.0, 65.41, 73.42, 82.41, 49.0
    roots = [A, A, F_ := 43.65, G]                           # a – a – F – G (je 1 Takt)
    arp = [440.0, 523.25, 659.25, 523.25, 440.0, 659.25, 587.33, 523.25]
    drums_off = lambda b: (6.0 <= b < 8.0) or (14.0 <= b < 14.5) or (b >= 30.0)
    for k8 in range(NBEATS * 2):
        b = k8 / 2
        tb = b * B
        bar = int(b // 4)
        pos = b % 4
        if not drums_off(b):
            if pos in (0.0, 2.5) or (bar % 2 == 1 and pos == 3.5):
                put_(mus, kick(), tb)
            if pos in (1.0, 3.0):
                put_(mus, clap(), tb)
            put_(mus, hat(0.17 if k8 % 2 == 0 else 0.11), tb)
            if pos == 3.5 or (22 <= b < 30 and pos == 1.5):          # Hi-Hat-Rolls
                for j in range(1, 4):
                    put_(mus, hat(0.1), tb + j * B / 6)
            if pos == 0.0:
                r = roots[bar % 4]
                put_(mus, b808(r, B * 2.4, 0.5, r * (1.5 if bar % 2 else 1.0)), tb)
            if pos == 2.5:
                put_(mus, b808(roots[bar % 4], B * 1.4, 0.3), tb)
        if b < 30:
            put_(mus, bell(arp[k8 % 8] * (0.5 if 8 <= b < 22 else 1.0), 0.45, 0.13), tb)
    for b in np.arange(4, 6, 0.5):                           # UI-Klicks beim Umschalten der Kreise
        put_(sfx, blip(2400 if int(b * 2) % 2 else 1800), b * B)
    put_(sfx, riser(2 * B, 0.9), 6 * B)
    put_(sfx, impact(1.2), 8 * B)
    for b in (10.05, 16.1, 18.05):
        put_(sfx, whoosh(0.4, 0.9), b * B)
    for b in (2, 4, 6, 12, 13, 14, 20, 21, 22):
        put_(sfx, whoosh(0.18, 0.4), b * B - 0.09)
    put_(sfx, riser(B, 0.7), 29 * B)
    put_(sfx, impact(0.9), 30 * B)
    put_(sfx, bell(880.0, 1.6, 0.35) + bell(1318.5, 1.6, 0.2), 30 * B)
    put_(sfx, impact(1.1), 31 * B)
    put_(sfx, bell(440.0, 2.0, 0.3) + bell(659.25, 2.0, 0.22), 31 * B)
    put_(mus, b808(A, 2.4, 0.6), 31 * B)

    mix = mus * 0.8 + sfx
    mix /= np.percentile(np.abs(mix), 99.9) + 1e-9
    mix = np.tanh(mix * 1.1)
    mix *= np.clip((DUR + 0.3 - np.arange(n) / SR) / 0.5, 0, 1)
    mix = mix / np.max(np.abs(mix)) * 0.95
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


def main():
    os.chdir(HERE)
    make_audio("audio_puck2.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_puck2.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
           "reel20_puck2.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS).tobytes())
        if i % 60 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(12.6 * B)).save("reel20_thumbnail.jpg", quality=92)
    print("fertig: reel20_puck2.mp4")


if __name__ == "__main__":
    main()
