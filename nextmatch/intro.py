"""NEXT MATCH – Logo-Intro (Reel 1080x1920, 5 s): N und M schießen ineinander, Impact, Pfeile » snappen ein,
Glanz, Wortmarke + Tagline, Glitch-Abschaltung. Ton komplett synthetisch (keine fremden Samples).

Aufruf: python3 intro.py         -> intro/nm_intro.mp4 + intro/nm_intro_cover.jpg
        python3 intro.py prev T  -> intro/prev_T.png (Einzelbild zum Prüfen)
"""
import io
import math
import os
import subprocess
import sys
import time
import wave
from multiprocessing import Pool

import cairosvg
import cv2
import numpy as np
from PIL import Image

import logo as L
import logo_vector as V

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "intro")
W, H = 1080, 1920
FPS = 30
DUR = 5.0
SR = 48000
CX = W / 2
SYM_W = 880
SYM_CY = 830
PADB = 70

T_N0, T_HIT = 0.42, 1.0                           # N/M fliegen ein, Zusammenprall
T_C1, T_C2, T_CD = 1.12, 1.24, 0.26               # Pfeile
T_SHINE, T_SHINE_D = 1.70, 0.55                   # Glanz-Sweep
T_WIPE, T_WIPE_D = 2.10, 0.42                     # NEXT MATCH Wischer
T_STUDIO = 2.55
T_TAG, T_TAG_D = 2.95, 0.55                       # Tagline tippen
T_OUT = 4.42                                      # Glitch + Abschalten
T_OFF = 4.84

BGc = np.array(L.BG, np.float32) / 255
LIMEc = np.array(L.LIME, np.float32) / 255
WHITEc = np.array(L.WHITE, np.float32) / 255
GREYc = np.array((178, 182, 192), np.float32) / 255


def clamp01(x):
    return min(1.0, max(0.0, x))


def ease_out_expo(p):
    return 1.0 if p >= 1 else 1 - 2 ** (-10 * p)


def ease_out_back(p, s=1.9):
    p -= 1
    return p * p * ((s + 1) * p + s) + 1


def smooth(p):
    p = clamp01(p)
    return p * p * (3 - 2 * p)


# ================================================================= Assets (einmal, vor dem Fork)
def to_prem(im):
    a = np.asarray(im.convert("RGBA"), np.float32) / 255
    a[..., :3] *= a[..., 3:4]
    return a


def render_pieces():
    pieces, b = V.build_pieces()
    x0, y0, x1, y1 = b
    vb = f"{x0:.2f} {y0:.2f} {x1 - x0:.2f} {y1 - y0:.2f}"
    out = {}
    for k, p in pieces.items():
        col = L.WHITE if k in "NM" else L.LIME
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}"><path fill="{V.hexcol(col)}" '
               f'd="{V.d_attr(p)}"/></svg>')
        png = cairosvg.svg2png(bytestring=svg.encode(), output_width=SYM_W)
        out[k] = to_prem(Image.open(io.BytesIO(png)))
    # Mitte des gemeinsamen Stamms (für Impact-Punkt): rechte Kante N minus halbe Stammbreite
    a = out["N"][..., 3]
    cols = np.where(a.max(0) > 0.5)[0]
    stem_x = cols.max() - SYM_W * 0.055
    return out, stem_x


PIECES, STEM_X = render_pieces()
SYM_H = PIECES["N"].shape[0]
BAND_H = SYM_H + 2 * PADB
BAND_Y = int(SYM_CY - BAND_H / 2)
SYM_X0 = CX - SYM_W / 2
HIT_X, HIT_Y = SYM_X0 + STEM_X, SYM_CY


def text_assets():
    nm = L.shear(L.text_img("NEXT MATCH", "ArchivoX900.ttf", 200, L.WHITE, 0.02))
    nm = L.fit(nm.crop(nm.getbbox()), 700, 10 ** 4)
    letters = []
    f_size = 34
    for ch in "STUDIO":
        im = L.shear(L.text_img(ch, "ArchivoX800.ttf", f_size, L.LIME), L.SHEAR * 0.6)
        letters.append(to_prem(im.crop(im.getbbox())))
    font = L.font("JBMono700.ttf", 34)
    tag = "GAMEDAY GRAPHICS & MOTION"
    adv = font.getlength("M")
    return to_prem(nm), letters, f_size, tag, font, adv


NM_TXT, STUDIO_L, ST_SIZE, TAG, TAG_FONT, TAG_ADV = text_assets()
NM_Y = SYM_CY + SYM_H / 2 + 105
ST_Y = NM_Y + NM_TXT.shape[0] + 34
TAG_Y = ST_Y + 72


def tag_glyphs():
    from PIL import ImageDraw
    out = []
    for ch in TAG:
        im = Image.new("RGBA", (int(TAG_ADV) + 8, 48), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((4, 4), ch, font=TAG_FONT, fill=(255, 255, 255, 255))
        out.append(to_prem(im))
    return out


TAG_G = tag_glyphs()


def make_bg():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    xn, yn = xx / W, yy / H
    img = np.ones((H, W, 3), np.float32) * BGc
    img += np.exp(-(((xn - 0.78) / 0.55) ** 2 + ((yn - 0.18) / 0.32) ** 2))[..., None] * LIMEc * 0.05
    img += np.exp(-(((xn - 0.15) / 0.6) ** 2 + ((yn - 0.85) / 0.3) ** 2))[..., None] * np.array([0.2, 0.25, 0.45], np.float32) * 0.10
    spot = np.exp(-(((xx - CX) / 520) ** 2 + ((yy - SYM_CY) / 300) ** 2))[..., None] * LIMEc
    # Speedline-Koordinate senkrecht zur Kursivneigung
    u = (xx + L.SHEAR * yy) / math.sqrt(1 + L.SHEAR ** 2)
    vig = 1 - 0.55 * np.clip(((xn - 0.5) ** 2 * 1.2 + (yn - 0.5) ** 2 * 0.9) * 2.2, 0, 1)
    return img, spot.astype(np.float32), u.astype(np.float32), vig[..., None].astype(np.float32)


BG_IMG, BG_SPOT, BG_U, VIG = make_bg()

rng0 = np.random.default_rng(7)
DUST = [(rng0.uniform(0, W), rng0.uniform(0, H), rng0.uniform(8, 40), rng0.uniform(-30, -8), rng0.uniform(0.8, 2.6),
         rng0.uniform(0.12, 0.45), rng0.uniform(0, 6.28)) for _ in range(110)]
STREAKS = [(rng0.uniform(0, H), rng0.uniform(80, 420), rng0.uniform(1800, 4200), rng0.uniform(0, 3000),
            rng0.uniform(0.08, 0.32), rng0.random() < 0.45) for _ in range(46)]
SPARKS = []
for _ in range(80):
    ang = rng0.uniform(0, 2 * math.pi)
    sp = rng0.uniform(500, 2100)
    SPARKS.append((math.cos(ang) * sp * 1.25, math.sin(ang) * sp * 0.8, rng0.uniform(0.35, 0.9),
                   rng0.random() < 0.55, rng0.uniform(1.2, 2.6)))


# ================================================================= Bausteine
def over(dst, src, x, y):
    """Prämultipliziertes src (h,w,4) bei (x,y) auf dst (H,W,3/4) legen (ganzzahlig, mit Clipping)."""
    h, w = src.shape[:2]
    x, y = int(round(x)), int(round(y))
    sx0, sy0 = max(0, -x), max(0, -y)
    dx0, dy0 = max(0, x), max(0, y)
    dx1, dy1 = min(dst.shape[1], x + w), min(dst.shape[0], y + h)
    if dx1 <= dx0 or dy1 <= dy0:
        return
    s = src[sy0:sy0 + dy1 - dy0, sx0:sx0 + dx1 - dx0]
    d = dst[dy0:dy1, dx0:dx1]
    d[..., :3] = s[..., :3] + d[..., :3] * (1 - s[..., 3:4])
    if dst.shape[2] == 4:
        d[..., 3:4] = s[..., 3:4] + d[..., 3:4] * (1 - s[..., 3:4])


def shifted(src, dx, size):
    m = np.float32([[1, 0, dx], [0, 1, 0]])
    return cv2.warpAffine(src, m, size, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def piece_layer(key, offset_fn, t, shutter):
    """Einzelteil im Band mit Bewegungsunschärfe (Mittel über Teilzeitpunkte)."""
    piece = PIECES[key]
    base = np.zeros((BAND_H, W, 4), np.float32)
    over(base, piece, 0, PADB)                       # Teil an x=0, wird verschoben
    xs = [offset_fn(t - shutter * (1 - k / 6)) for k in range(7)]
    if max(xs) - min(xs) < 0.8:
        return shifted(base, SYM_X0 + xs[-1], (W, BAND_H)) if xs[-1] is not None else None
    acc = np.zeros_like(base)
    for x in xs:
        acc += shifted(base, SYM_X0 + x, (W, BAND_H))
    return acc / len(xs)


N_START, M_START = -1000, 1330                    # so gewählt, dass N und M gleichzeitig ins Bild kommen


def off_N(t):
    p = clamp01((t - T_N0) / (T_HIT - T_N0))
    x = N_START * (1 - p ** 2.2)
    if t > T_HIT:
        d = t - T_HIT
        x -= 18 * math.exp(-d * 9) * math.sin(d * 34)
    return x


def off_M(t):
    p = clamp01((t - T_N0) / (T_HIT - T_N0))
    x = M_START * (1 - p ** 2.2)
    if t > T_HIT:
        d = t - T_HIT
        x += 18 * math.exp(-d * 9) * math.sin(d * 34)
    return x


def off_C(t0):
    def f(t):
        p = clamp01((t - t0) / T_CD)
        return -1250 * (1 - ease_out_back(p, 1.6))
    return f


def symbol_band(t):
    band = np.zeros((BAND_H, W, 4), np.float32)
    sh = 0.5 / FPS
    for key, t0 in (("C1", T_C1), ("C2", T_C2)):
        if t >= t0:
            lay = piece_layer(key, off_C(t0), t, 1.0 / FPS)
            over(band, lay, 0, 0)
    if t >= T_N0:
        for key, fn in (("N", off_N), ("M", off_M)):
            lay = piece_layer(key, fn, t, sh)
            over(band, lay, 0, 0)
    # Scale-Punch beim Impact
    if t >= T_HIT:
        s = 1 + 0.07 * math.exp(-(t - T_HIT) * 7)
        m = cv2.getRotationMatrix2D((CX, BAND_H / 2), 0, s)
        band = cv2.warpAffine(band, m, (W, BAND_H), flags=cv2.INTER_LINEAR)
    return band


def blur_q(img, sigma):
    """Weichzeichnen auf Viertelauflösung (schnell), zurück auf Originalgröße."""
    h, w = img.shape[:2]
    small = cv2.resize(img, (max(1, w // 4), max(1, h // 4)), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), sigma / 4)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)


def glow_amount(t):
    if t < T_HIT:
        return 0.0
    d = t - T_HIT
    g = 0.34 + 1.1 * math.exp(-d * 5)
    g += 0.06 * math.sin(2 * math.pi * 0.7 * (t - T_HIT))
    if t > T_SHINE:
        g += 0.35 * math.exp(-((t - T_SHINE - T_SHINE_D * 0.6) / 0.2) ** 2)
    return g


def add_streak(img, t):
    """Lichtlinie am Anfang (horizontaler Neon-Strich durch die Bildmitte)."""
    if t > 0.9:
        return
    grow = ease_out_expo(clamp01((t - 0.05) / 0.35))
    fade = 1 - smooth((t - 0.45) / 0.45)
    if grow <= 0 or fade <= 0:
        return
    half = W * 0.62 * grow
    xs = np.arange(W, dtype=np.float32)
    hx = np.clip((half - np.abs(xs - CX)) / 120, 0, 1)
    ys = np.arange(-60, 61, dtype=np.float32)
    core = np.exp(-(ys / 2.2) ** 2)[:, None] * hx[None, :]
    glow = np.exp(-(ys / 22) ** 2)[:, None] * hx[None, :] * 0.35
    y0 = int(SYM_CY - 60)
    img[y0:y0 + 121] += (core[..., None] * (WHITEc * 0.7 + LIMEc * 0.3) + glow[..., None] * LIMEc) * fade * 1.4


def add_ring(layer, t):
    if t < T_HIT or t > T_HIT + 0.9:
        return
    d = t - T_HIT
    for delay, col, wmax, amp in ((0.0, LIMEc, 26, 0.9), (0.07, WHITEc, 10, 0.6)):
        dd = d - delay
        if dd <= 0:
            continue
        r = 40 + 1150 * (1 - math.exp(-dd * 5.0))
        a = math.exp(-dd * 4.2) * amp
        th = max(2, int(wmax * math.exp(-dd * 3)))
        cv2.ellipse(layer, (int(HIT_X), int(HIT_Y)), (int(r), int(r * 0.62)), 0, 0, 360,
                    tuple(float(c * a) for c in col), th, cv2.LINE_AA)


def add_sparks(layer, t):
    if t < T_HIT:
        return
    d = t - T_HIT
    for vx, vy, life, lime, wd in SPARKS:
        if d > life:
            continue
        k = 3.2
        f = (1 - math.exp(-k * d)) / k
        x, y = HIT_X + vx * f, HIT_Y + vy * f + 160 * d * d
        v = math.exp(-k * d)
        x2, y2 = x - vx * v * 0.028, y - vy * v * 0.028
        a = (1 - d / life) ** 1.3
        col = LIMEc if lime else WHITEc
        cv2.line(layer, (int(x), int(y)), (int(x2), int(y2)), tuple(float(c * a) for c in col), max(1, int(wd)), cv2.LINE_AA)


def add_dust(layer, t):
    vis = smooth((t - 0.2) / 0.6) * (1 - smooth((t - T_OUT) / 0.3))
    if vis <= 0:
        return
    for x, y, vx, vy, r, b, ph in DUST:
        px = (x + vx * t) % W
        py = (y + vy * t) % H
        a = b * vis * (0.6 + 0.4 * math.sin(t * 2.3 + ph))
        cv2.circle(layer, (int(px), int(py)), int(max(1, r)), (float(LIMEc[0] * a * 0.6 + a * 0.4),
                   float(LIMEc[1] * a * 0.6 + a * 0.4), float(LIMEc[2] * a * 0.6 + a * 0.4)), -1, cv2.LINE_AA)


def speed_factor(t):
    if t < T_HIT:
        return 0.4 + 0.6 * smooth(t / T_HIT)
    return 0.12 + 0.88 * math.exp(-(t - T_HIT) * 2.2)


def add_streaks(layer, t):
    # Geschwindigkeit integriert, damit Streifen beim Abbremsen nicht zurückspringen
    steps = np.linspace(0, t, 40)
    pos_t = float(np.trapezoid([speed_factor(s) for s in steps], steps)) if t > 0 else 0.0
    vis = smooth(t / 0.3) * (1 - smooth((t - T_OUT) / 0.3))
    for y, ln, sp, ph, b, lime in STREAKS:
        x = (ph + sp * pos_t) % (W + 900) - 450
        a = b * vis * (0.35 + 0.65 * speed_factor(t))
        ln2 = ln * (0.4 + 0.9 * speed_factor(t))
        col = LIMEc if lime else WHITEc
        for k, f in ((0, 1.0), (1, 0.5), (2, 0.22)):
            xa, xb = x - ln2 * k / 3, x - ln2 * (k + 1) / 3
            cv2.line(layer, (int(xa), int(y)), (int(xb), int(y)), tuple(float(c * a * f) for c in col), 2, cv2.LINE_AA)


def speedlines(t):
    """Feine schräge Linien im Hintergrund (Marken-Textur), gleiten nach rechts."""
    steps = np.linspace(0, t, 30)
    pos_t = float(np.trapezoid([speed_factor(s) for s in steps], steps)) if t > 0 else 0.0
    off = pos_t * 260
    fr = ((BG_U - off) / 28.4) % 1.0
    return (fr < 0.045).astype(np.float32)[..., None] * 0.03


def wordmark_layer(img, t):
    if t < T_WIPE:
        return
    h, w = NM_TXT.shape[:2]
    x0 = int(CX - w / 2)
    p = smooth((t - T_WIPE) / T_WIPE_D)
    bx = -(60 + L.SHEAR * h) + (w + 120 + L.SHEAR * h) * p   # Wischkante an der Unterkante; schräg wie die Kursive
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    edge = bx + L.SHEAR * (h - yy)
    mask = np.clip((edge - xx) / 6, 0, 1)[..., None]
    over(img, NM_TXT * mask, x0, NM_Y)
    # Lime-Wischbalken auf der Kante
    bar_a = 1 - smooth((t - T_WIPE - T_WIPE_D) / 0.18)
    if bar_a > 0:
        top, bot = NM_Y - 18, NM_Y + h + 18
        xt, xb = x0 + bx + L.SHEAR * (h + 18), x0 + bx - L.SHEAR * 18
        pts = [(xt, top), (xt + 14, top), (xb + 14, bot), (xb, bot)]
        lay = np.zeros((H, W, 3), np.float32)
        cv2.fillPoly(lay, [np.int32(pts)], tuple(float(c * bar_a) for c in LIMEc), cv2.LINE_AA)
        img += lay + blur_q(lay, 22) * 1.4


def studio_layer(img, t):
    if t < T_STUDIO:
        return
    n = len(STUDIO_L)
    widths = [g.shape[1] for g in STUDIO_L]
    for i, g in enumerate(STUDIO_L):
        p = smooth((t - T_STUDIO - i * 0.035) / 0.45)
        if p <= 0:
            continue
        track = ST_SIZE * (0.95 + 1.6 * (1 - ease_out_expo(p)))
        total = sum(widths) + track * (n - 1)
        x = CX - total / 2 + sum(widths[:i]) + track * i
        over(img, g * p, x, ST_Y)


def tagline_layer(img, t):
    if t < T_TAG:
        return
    n = len(TAG)
    shown = int(n * clamp01((t - T_TAG) / T_TAG_D))
    total = TAG_ADV * n
    x0 = CX - total / 2
    for i in range(shown):
        if TAG[i] != " ":
            over(img, TAG_G[i] * np.concatenate([GREYc, [1.0]]).astype(np.float32), x0 + i * TAG_ADV - 4, TAG_Y - 4)
    blink = shown < n or (int((t - T_TAG) * 2.4) % 2 == 0)
    if blink and t < T_OUT:
        cx = x0 + shown * TAG_ADV + 3
        cv2.rectangle(img, (int(cx), int(TAG_Y + 6)), (int(cx + TAG_ADV * 0.7), int(TAG_Y + 38)),
                      tuple(float(c) for c in LIMEc), -1)


def shine(img, band_alpha, t):
    """Diagonaler Glanz über das Symbol (nur auf/um die Buchstaben)."""
    p = (t - T_SHINE) / T_SHINE_D
    if p < 0 or p > 1:
        return
    p = smooth(p)
    xs = np.arange(W, dtype=np.float32)[None, :]
    ys = np.arange(BAND_H, dtype=np.float32)[:, None]
    pos = -200 + (W + 400) * p
    d = xs - pos - L.SHEAR * (BAND_H / 2 - ys) * 2.2
    bandm = np.exp(-(d / 38) ** 2)
    a = band_alpha
    soft = blur_q(a, 10)
    hl = (bandm * a)[..., None] * 0.55 + (bandm * soft)[..., None] * 0.45
    img[BAND_Y:BAND_Y + BAND_H] += hl * (WHITEc * 0.6 + LIMEc * 0.4)


def glitch(img, t, fi):
    if t < T_OUT:
        return img
    rng = np.random.default_rng(1000 + fi)
    d = t - T_OUT
    amt = min(1.0, d / 0.25)
    out = img.copy()
    for _ in range(int(4 + 10 * amt)):
        y = int(rng.uniform(0, H))
        hgt = int(rng.uniform(8, 90))
        dx = int(rng.uniform(-1, 1) * 140 * amt)
        out[y:y + hgt] = np.roll(img[y:y + hgt], dx, axis=1)
    k = int(6 + 22 * amt)
    out[..., 0] = np.roll(out[..., 0], k, axis=1)
    out[..., 2] = np.roll(out[..., 2], -k, axis=1)
    if rng.random() < 0.3:
        out *= 0.55
    # TV-Abschaltung: vertikal auf eine Linie, dann horizontal auf einen Punkt
    if t > T_OFF - 0.14:
        q = clamp01((t - (T_OFF - 0.14)) / 0.14)
        sy = max(0.004, (1 - q) ** 2)
        sx = 1.0 if q < 0.6 else max(0.0, 1 - (q - 0.6) / 0.4)
        m = np.float32([[sx, 0, CX * (1 - sx)], [0, sy, H / 2 * (1 - sy)]])
        out = cv2.warpAffine(out, m, (W, H), flags=cv2.INTER_LINEAR)
        out += (q > 0.5) * 0.6 * sy * 10 * np.exp(-((np.arange(H, dtype=np.float32)[:, None, None] - H / 2) / 3) ** 2)
    return out


def chroma(img, k):
    if k < 0.5:
        return img
    k = int(round(k))
    out = img.copy()
    out[..., 0] = np.roll(img[..., 0], k, axis=1)
    out[..., 2] = np.roll(img[..., 2], -k, axis=1)
    return out


def shake(t):
    amp = 0.0
    for t0, a0, k in ((T_HIT, 20, 10), (T_C1 + T_CD * 0.55, 6, 14), (T_C2 + T_CD * 0.55, 6, 14)):
        if t >= t0:
            amp += a0 * math.exp(-(t - t0) * k)
    return (amp * math.sin(t * 91.0), amp * math.cos(t * 77.0))


def compose(t, fi):
    if t >= T_OFF:
        return np.zeros((H, W, 3), np.uint8)
    intro = smooth(t / 0.35)
    img = BG_IMG * (0.25 + 0.75 * intro) + speedlines(t) * intro
    img = img + BG_SPOT * 0.06 * glow_amount(t)
    add = np.zeros((H, W, 3), np.float32)
    add_streaks(add, t)
    add_dust(add, t)
    img += add
    add_streak(img, t)
    # Symbol
    band = symbol_band(t)
    a = band[..., 3]
    g = glow_amount(t)
    if g > 0:
        af = np.zeros((H, W), np.float32)            # Glow über das ganze Bild, sonst harte Kanten am Bandrand
        af[BAND_Y:BAND_Y + BAND_H] = a
        img += blur_q(af, 26)[..., None] * LIMEc * 0.7 * g + blur_q(af, 70)[..., None] * LIMEc * 0.45 * g
    seg = img[BAND_Y:BAND_Y + BAND_H]
    seg[:] = band[..., :3] + seg * (1 - band[..., 3:4])
    shine(img, a, t)
    # Ring + Funken
    fx = np.zeros((H, W, 3), np.float32)
    add_ring(fx, t)
    add_sparks(fx, t)
    if t >= T_HIT:
        img += fx + blur_q(fx, 16) * 1.2
    # Text
    wordmark_layer(img, t)
    studio_layer(img, t)
    tagline_layer(img, t)
    # Flash
    fl = 0.0
    if t >= T_HIT:
        fl += 0.4 * math.exp(-(t - T_HIT) * 20)
    for t0 in (T_C1, T_C2):
        tl = t0 + T_CD * 0.55
        if t >= tl:
            fl += 0.1 * math.exp(-(t - tl) * 22)
    if fl > 0.003:
        img += fl * (WHITEc * 0.7 + LIMEc * 0.3)
    # Kamera
    sx, sy = shake(t)
    if abs(sx) + abs(sy) > 0.3:
        m = np.float32([[1, 0, sx], [0, 1, sy]])
        img = cv2.warpAffine(img, m, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    ca = 0.0
    if t >= T_HIT:
        ca += 12 * math.exp(-(t - T_HIT) * 9)
    img = chroma(img, ca)
    img = glitch(img, t, fi)
    # Bloom, Vignette, Korn
    img = img + blur_q(np.clip(img - 0.75, 0, None), 30) * 0.5
    img *= VIG
    grain = np.random.default_rng(fi).standard_normal((H // 2, W // 2)).astype(np.float32)
    img += cv2.resize(grain, (W, H), interpolation=cv2.INTER_NEAREST)[..., None] * 0.012
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


# ================================================================= Ton
def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(11)
    out = np.zeros((n, 2))

    def tt(sec):
        return np.arange(int(sec * SR)) / SR

    def put(sig, at, vol=1.0, pan=0.0):
        st = int(round(at * SR))
        e = min(n, st + len(sig))
        if st >= n:
            return
        gl, gr = math.cos((pan + 1) * math.pi / 4) * 1.41, math.sin((pan + 1) * math.pi / 4) * 1.41
        out[st:e, 0] += sig[: e - st] * vol * gl
        out[st:e, 1] += sig[: e - st] * vol * gr

    def lp(x, k):
        c = np.cumsum(np.concatenate([np.zeros(k), x]))
        return (c[k:] - c[:-k]) / k

    def hp(x, k):
        return x - lp(x, k)

    def noise(sec):
        return rng.standard_normal(int(sec * SR))

    def whoosh(dur, up=True):
        x = tt(dur)
        env = (x / dur) ** 2.2 if up else np.sin(np.pi * x / dur) ** 2
        sig = hp(lp(noise(dur), 5), 30)
        return sig * env

    def boom():
        x = tt(1.6)
        body = np.tanh(np.sin(2 * np.pi * np.cumsum(42 + 110 * np.exp(-x * 13)) / SR) * np.exp(-x * 2.6) * 3.2)
        crack = hp(noise(1.6), 2) * np.exp(-x * 38) * 0.9
        return body + crack

    def zip_(vol=0.5):
        x = tt(0.16)
        f = 900 + 5200 * (x / 0.16) ** 1.5
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.4 + hp(noise(0.16), 3) * 0.5) * np.sin(np.pi * x / 0.16) * vol

    def click(vol=0.4, f0=1900):
        x = tt(0.06)
        return (np.sin(2 * np.pi * f0 * x) + hp(noise(0.06), 1) * 0.4) * np.exp(-x * 110) * vol

    def glint():
        x = tt(0.9)
        f = 2600 + 3000 * x / 0.9
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.5 + 0.5 * np.sin(2 * np.pi * 22 * x)) * np.exp(-x * 4) * 0.22

    def chord(dur, freqs, vol):
        x = tt(dur)
        sig = np.zeros_like(x)
        for i, fr in enumerate(freqs):
            for det in (-0.004, 0.004):
                ph = 2 * np.pi * fr * (1 + det) * x + i
                sig += (2 * ((ph / (2 * np.pi)) % 1) - 1) * 0.5
        sig = lp(lp(sig, 14), 10)
        env = np.minimum(x / 0.01, 1) * np.exp(-x * 0.55) * np.clip((dur - x) / 0.6, 0, 1)
        return sig * env * vol

    def stutter():
        x = tt(0.36)
        gate = (np.sin(2 * np.pi * 26 * x) > 0)
        return np.sign(np.sin(2 * np.pi * 620 * x)) * gate * 0.4 + hp(noise(0.36), 1) * gate * 0.3

    def power_off():
        x = tt(0.35)
        f = 1400 * np.exp(-x * 9) + 40
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 6) * 0.55

    # Aufbau
    x = tt(1.0)
    put(lp(noise(1.0), 30) * 3 * (x / 1.0) ** 2.5 + np.sin(2 * np.pi * 38 * x) * (x / 1.0) ** 3 * 0.6, 0.0, 0.7)
    put(glint() * 0.8, 0.06, 1.0)
    put(whoosh(0.58), T_N0, 0.55, pan=-0.6)
    put(whoosh(0.58), T_N0, 0.55, pan=0.6)
    # Impact
    put(boom(), T_HIT, 1.0)
    put(click(0.7, 2600), T_HIT, 1.0)
    put(chord(3.4, (110.0, 164.81, 220.0, 246.94, 329.63), 0.22), T_HIT, 1.0)
    # Pfeile
    for t0, pan in ((T_C1, -0.25), (T_C2, 0.25)):
        put(zip_(0.55), t0, 1.0, pan)
        put(click(0.5, 1500), t0 + T_CD * 0.55, 1.0, pan)
    put(glint(), T_SHINE, 1.0, 0.3)
    put(whoosh(0.42, up=False), T_WIPE, 0.4, pan=0.2)
    put(click(0.45, 1200), T_WIPE + T_WIPE_D, 1.0)
    for i in range(len(TAG)):
        if TAG[i] != " ":
            put(click(0.16, 3000 + 300 * (i % 3)), T_TAG + T_TAG_D * i / len(TAG), 1.0, -0.4 + 0.8 * i / len(TAG))
    # Abschalten
    put(stutter(), T_OUT, 0.5)
    put(power_off(), T_OFF - 0.14, 1.0)
    # einfacher Raum (Mehrfach-Echo, gedämpft)
    wet = np.zeros_like(out)
    for dl, g in ((0.031, 0.32), (0.047, 0.28), (0.071, 0.22), (0.113, 0.16), (0.161, 0.1)):
        k = int(dl * SR)
        wet[k:, 0] += out[:-k, 1] * g
        wet[k:, 1] += out[:-k, 0] * g
    wet[:, 0], wet[:, 1] = lp(wet[:, 0], 6), lp(wet[:, 1], 6)
    mix = out + wet
    mix[int(T_OFF * SR) + int(0.3 * SR):] *= 0
    mix = np.tanh(mix / (np.max(np.abs(mix)) + 1e-9) * 1.4)
    mix *= np.clip((DUR - np.arange(n) / SR) / 0.05, 0, 1)[:, None]
    mix = mix / np.max(np.abs(mix)) * 0.95
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


def _frame(i):
    return compose(i / FPS, i).tobytes()


def main():
    os.makedirs(OUT, exist_ok=True)
    wav = os.path.join(OUT, "_intro.wav")
    make_audio(wav)
    nf = int(round(DUR * FPS))
    dst = os.path.join(OUT, "nm_intro.mp4")
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9", "-ar", "44100", "-shortest",
           "-movflags", "+faststart", dst]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    with Pool(4) as pool:
        for i, fr in enumerate(pool.imap(_frame, range(nf), chunksize=2)):
            proc.stdin.write(fr)
            if i % 30 == 0:
                print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    os.remove(wav)
    Image.fromarray(compose(4.0, 9999)).save(os.path.join(OUT, "nm_intro_cover.jpg"), quality=93)
    print("fertig:", dst)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "prev":
        os.makedirs(OUT, exist_ok=True)
        for ts in sys.argv[2:]:
            Image.fromarray(compose(float(ts), int(float(ts) * FPS))).save(os.path.join(OUT, f"prev_{ts}.png"))
    else:
        main()
