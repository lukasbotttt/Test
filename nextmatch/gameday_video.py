"""NEXT MATCH – Beispiel #1 als Video: Eishockey-Gameday (Reel 1080x1920, ~14,5 s, 30 fps), fiktive Vereine.

Szenen (Schnitte auf dem Beat, 128 BPM):
  1 Laufschrift-Wand + GAMEDAY-Drop   2 Heimteam (3D-Wappen, Lichtstrahlen, Funken)   3 Gastteam
  4 VS-Clash (diagonaler Split, Blitz, Torhupe)   5 Info-Karten DATUM/BULLY/ARENA   6 Plakat   7 NEXT-MATCH-Endkarte
Bausteine (Wappen, Eis, Panel) aus demo_gameday.py, Ton komplett synthetisch.

Aufruf: python3 gameday_video.py          -> out/demo/gameday_reel.mp4 + gameday_reel_cover.jpg
        python3 gameday_video.py prev T…  -> out/demo/vprev_T.png
"""
import math
import os
import subprocess
import sys
import time
import wave
from multiprocessing import Pool

import cv2
import numpy as np
from PIL import Image

import demo_gameday as D
import logo as L

OUT = D.OUT
W, H = 1080, 1920
FPS = 30
SR = 48000
B = 60 / 128
T0 = 1.0                                          # Drop: GAMEDAY knallt rein (Beat 0)


def bt(n):
    return T0 + n * B


T_LIGHTS = (0.10, 0.30, 0.50)
T_PILL0, T_TEASE = bt(1), bt(2)
T_HOME, T_HL = bt(4), bt(5)                       # Schnitt Heimteam, Wappen landet
T_AWAY, T_AL = bt(8), bt(9)
T_VS = bt(12)                                     # Hälften prallen aufeinander
T_VSIN = T_VS - 0.32
T_INFO = bt(16)
T_CARDS = (bt(16), bt(18), bt(20))
T_PO = bt(22)                                     # Plakat
T_SHINE = bt(24)
T_OUT = bt(26)
T_END = T_OUT + 0.25
DUR = T_END + 1.15
WHIP = 0.11

CX, CY = 540, 960
LX = 525                                          # Layout-Mitte Plakat (rechts liegen die Reel-Buttons)
HOR = 930
Y_PILL, Y_GD = 300, 470
Y_CR, X_HOME, X_AWAY = 860, 262, 790
Y_VS = 850
Y_NAME, Y_ROLE = 1085, 1122
PX0, PY0, PW, PH = 80, 1200, 870, 150
Y_TK, Y_CRED = 1420, 1478
Y_TEAM = 760                                      # Wappenmitte in den Team-Szenen

RED = np.array(D.c01(D.RED), np.float32)
BLUE = np.array(D.c01(D.BLUE), np.float32)
YEL = np.array(D.c01(D.YELLOW), np.float32)
WHITE = np.array(D.c01(D.WHITE), np.float32)
LIME = np.array(D.c01(L.LIME), np.float32)


def clamp01(x):
    return min(1.0, max(0.0, x))


def smooth(p):
    p = clamp01(p)
    return p * p * (3 - 2 * p)


def ease_out_expo(p):
    p = clamp01(p)
    return 1.0 if p >= 1 else 1 - 2 ** (-10 * p)


def ease_out_back(p, s=1.7):
    p = clamp01(p) - 1
    return p * p * ((s + 1) * p + s) + 1


def ease_io_expo(p):
    p = clamp01(p)
    if p in (0.0, 1.0):
        return p
    return 2 ** (20 * p - 10) / 2 if p < 0.5 else (2 - 2 ** (-20 * p + 10)) / 2


over, over_c, text, tint, blur = D.over, D.over_c, D.text, D.tint, D.blur
YY = np.arange(H, dtype=np.float32)[:, None]
XX = np.arange(W, dtype=np.float32)[None, :]


def pad(a, p):
    out = np.zeros((a.shape[0] + 2 * p, a.shape[1] + 2 * p, a.shape[2]), np.float32)
    out[p:p + a.shape[0], p:p + a.shape[1]] = a
    return out


def scaled(a, s):
    if abs(s - 1) < 1e-3:
        return a
    h, w = a.shape[:2]
    return cv2.resize(a, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)


def fitw(a, maxw):
    return scaled(a, min(1.0, maxw / a.shape[1]))


def blur_q(img, sigma):
    h, w = img.shape[:2]
    small = cv2.resize(img, (max(1, w // 4), max(1, h // 4)), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), sigma / 4)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)


def add_c(img, a3, cx, cy, k=1.0):
    """Additiv zentriert einfügen, mit Clipping."""
    h, w = a3.shape[:2]
    x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if xb > xa and yb > ya:
        img[ya:yb, xa:xb] += a3[ya - y0:yb - y0, xa - x0:xb - x0] * k


def mblur(img, length, vertical):
    n = int(length)
    if n < 3:
        return img
    return cv2.blur(img, (1, n) if vertical else (n, 1))


def wipe_mask(w, p, reverse=False):
    xs = np.arange(w, dtype=np.float32)[None, :]
    m = np.clip((xs - w * (1 - p * 1.15)) / 20, 0, 1) if reverse else np.clip((w * p * 1.15 - xs) / 20, 0, 1)
    return m[..., None]


def ring(img, cx, cy, d, col, scale=1.0):
    if d < 0 or d > 0.9:
        return
    lay = np.zeros((H, W, 3), np.float32)
    for delay, c, wmax, amp in ((0.0, col, 24, 1.0), (0.07, WHITE, 9, 0.6)):
        dd = d - delay
        if dd <= 0:
            continue
        r = (40 + 1100 * (1 - math.exp(-dd * 5.0))) * scale
        aa = math.exp(-dd * 4.2) * amp
        cv2.ellipse(lay, (int(cx), int(cy)), (int(r), int(r * 0.62)), 0, 0, 360,
                    tuple(float(v * aa) for v in c), max(2, int(wmax * math.exp(-dd * 3))), cv2.LINE_AA)
    img += lay + blur_q(lay, 16) * 1.1


# ================================================================= Assets (einmal vor dem Fork)
rng0 = np.random.default_rng(21)


def strip(word, size, col, stroke, fill, gap, n):
    spr = text(word, "Anton.ttf", size, col, 0.01, stroke=stroke, fill=fill, k=0.16)
    period = spr.shape[1] + gap
    out = np.zeros((spr.shape[0], period * n, 4), np.float32)
    for i in range(n):
        over(out, spr, i * period, 0)
    return out, period


WALL_W, WALL_H = 1500, 2400
WALL_ROWS = []
for k in range(10):
    style = k % 3
    if style == 0:
        s_, per = strip("GAMEDAY", 290, D.WHITE, 3, False, 90, 6)
        alpha = 0.28
    elif style == 1:
        s_, per = strip("GAMEDAY", 290, D.RED_D, 0, True, 90, 6)
        alpha = 0.85
    else:
        s_, per = strip("GAMEDAY", 290, D.RED, 2, False, 90, 6)
        alpha = 0.45
    WALL_ROWS.append((s_ * alpha, per, 1 if k % 2 else -1, 340 + 90 * (k % 4), k * 262 - 60))


def rays_img(n=1500, count=30):
    im = np.zeros((n, n), np.float32)
    c = n / 2
    for i in range(count):
        a = i * 2 * math.pi / count + rng0.uniform(-0.04, 0.04)
        wa = math.radians(rng0.uniform(1.5, 4.0))
        pts = [(c, c), (c + math.cos(a - wa) * n, c + math.sin(a - wa) * n), (c + math.cos(a + wa) * n, c + math.sin(a + wa) * n)]
        cv2.fillPoly(im, [np.int32(pts)], float(rng0.uniform(0.4, 1.0)), cv2.LINE_AA)
    r = np.hypot(*np.meshgrid(np.arange(n) - c, np.arange(n) - c))
    im *= np.exp(-r / 330) * np.clip(r / 120, 0, 1)
    return cv2.GaussianBlur(im, (0, 0), 5).astype(np.float32)


RAYS = rays_img()


def club_bg(col, dark):
    img = np.ones((H, W, 3), np.float32) * np.array(D.c01(dark), np.float32)
    img += np.exp(-(((XX - CX) / 620) ** 2 + ((YY - Y_TEAM) / 560) ** 2))[..., None] * col * 0.55
    img += np.exp(-(((XX - CX) / 900) ** 2 + ((YY - 1900) / 380) ** 2))[..., None] * col * 0.25
    img *= (1 - 0.5 * np.clip(((XX / W - 0.5) ** 2 * 1.4 + (YY / H - 0.5) ** 2) * 2.2, 0, 1))[..., None]
    return img.astype(np.float32)


BG_HOME = club_bg(RED, (12, 2, 4))
BG_AWAY = club_bg(BLUE, (2, 6, 22))
STRIPE_U = (XX + 0.45 * YY).astype(np.float32)


def vstrip(word, size, col):
    spr = text(word, "Anton.ttf", size, col, 0.02, stroke=3, fill=False)
    spr = np.rot90(spr).copy()                     # senkrecht, von unten nach oben lesbar
    period = spr.shape[0] + 60
    n = int(math.ceil((H + period) / period)) + 1
    out = np.zeros((period * n, spr.shape[1], 4), np.float32)
    for i in range(n):
        over(out, spr, 0, i * period)
    return out, period


VSTRIP_H = vstrip("FALKENSTADT", 200, D.WHITE)
VSTRIP_A = vstrip("WOLFSRIED", 200, D.WHITE)

BIG_H = D.crest_home(500)
BIG_A = D.crest_away(490)
MID_H = D.crest_home(380)
MID_A = D.crest_away(365)
CREST_H = D.crest_home(300)
CREST_A = D.crest_away(290)
GLOW_BIG_H = blur(pad(tint(BIG_H, D.RED), 120), 46)[..., :3]
GLOW_BIG_A = blur(pad(tint(BIG_A, D.YELLOW), 120), 46)[..., :3]
GLOW_MID_H = blur(pad(tint(MID_H, D.RED), 110), 40)[..., :3]
GLOW_MID_A = blur(pad(tint(MID_A, D.BLUE), 110), 40)[..., :3]
GLOW_H = blur(pad(tint(CREST_H, D.RED), 110), 40)[..., :3]
GLOW_A = blur(pad(tint(CREST_A, D.BLUE), 110), 40)[..., :3]


def letters(word, size, col, font="ArchivoX900.ttf"):
    f = L.font(font, size)
    out, x = [], 0.0
    for ch in word:
        if ch != " ":
            out.append((text(ch, font, size, col, 0.0, k=0.14), x + f.getlength(ch) / 2))
        x += f.getlength(ch) + size * 0.04
    return out, x


NAME_H = letters("EC FALKENSTADT", 70, D.WHITE)
NAME_A = letters("ERC WOLFSRIED", 70, D.WHITE)
PILL_HT = D.pill("HEIMTEAM", D.RED, D.WHITE, 26)
PILL_GT = D.pill("GASTTEAM", D.YELLOW, (10, 20, 60), 26)
EST_H = text("EST. 1952", "ArchivoX800.ttf", 24, (230, 200, 200), 0.45)
EST_A = text("EST. 1968", "ArchivoX800.ttf", 24, (220, 225, 245), 0.45)

GD_BIG = fitw(text("GAMEDAY", "Anton.ttf", 330, D.WHITE, 0.01, k=0.16), 980)
GD_BIG_RED = tint(GD_BIG, D.RED)
GD_BIG_GLOW = blur(pad(GD_BIG_RED, 100), 40)[..., :3]
GD_BIG_OUT = fitw(text("GAMEDAY", "Anton.ttf", 330, D.WHITE, 0.01, stroke=3, fill=False, k=0.16), 980)
PILL = D.pill("HAUPTRUNDE  ·  SPIELTAG 12", D.RED, D.WHITE, 22)
PILL_BIG = D.pill("HAUPTRUNDE  ·  SPIELTAG 12", D.RED, D.WHITE, 30)
TEASE = text("FALKENSTADT  VS  WOLFSRIED", "ArchivoX800.ttf", 36, D.WHITE, 0.12, k=0.1)

VS_BIG = text("VS", "Anton.ttf", 340, D.WHITE, 0.0, k=0.16)
VS_BIG_GLOW = blur(pad(VS_BIG, 100), 30)[..., :3]
VS_NAME_H = text("EC FALKENSTADT", "ArchivoX900.ttf", 44, D.WHITE, 0.02, k=0.14)
VS_NAME_A = text("ERC WOLFSRIED", "ArchivoX900.ttf", 44, D.WHITE, 0.02, k=0.14)

CARDS = []
for lab, val in D.INFO:
    v = fitw(text(val, "Anton.ttf", 300, D.WHITE, 0.02, k=0.16), 960)
    vo = fitw(text(val, "Anton.ttf", 300, D.WHITE, 0.02, stroke=3, fill=False, k=0.16), 960)
    CARDS.append((D.pill(lab, D.RED, D.WHITE, 34), v, tint(v, D.RED), vo))

# Plakat (wie die Grafik, ohne Schläger/Puck)
GD = text("GAMEDAY", "Anton.ttf", 250, D.WHITE, 0.01, k=0.16)
GD_OUT = text("GAMEDAY", "Anton.ttf", 250, D.WHITE, 0.01, stroke=3, fill=False, k=0.16)
GD_RED = tint(GD, D.RED)
VS = text("VS", "Anton.ttf", 150, D.WHITE, 0.0, k=0.16)
VS_RED = tint(VS, D.RED)
VS_GLOW = blur(pad(VS, 80), 22)[..., :3]
SHAD_H = blur(pad(tint(CREST_H, (0, 0, 0), 0.7), 40), 10)[..., 3:4]
SHAD_A = blur(pad(tint(CREST_A, (0, 0, 0), 0.7), 40), 10)[..., 3:4]
NAMES = [(text(d["name"], "ArchivoX800.ttf", 28, D.WHITE, 0.04, k=0.1), text(r, "ArchivoX800.ttf", 18, (150, 156, 170), 0.45), x)
         for d, r, x in ((D.HOME, "HEIM", X_HOME), (D.AWAY, "GAST", X_AWAY))]
COLS = [(text(lab, "ArchivoX800.ttf", 20, (150, 156, 170), 0.3),
         text(val, "Anton.ttf", 60 if len(val) < 10 else 46, D.WHITE, 0.03, k=0.12)) for lab, val in D.INFO]
TICKET = text("TICKETS AN DER ABENDKASSE AB 18:30 UHR", "ArchivoX800.ttf", 19, (200, 204, 214), 0.12)
SYM_S = D.prem(L.fit(L.symbol_nm(120), 64, 22))
CRED = text("DESIGN: NEXT MATCH  ·  DEMO", "ArchivoX800.ttf", 14, (130, 136, 150), 0.25)
END_SYM = D.prem(L.fit(L.symbol_nm(500), 700, 260))
END_WM = text("NEXT MATCH", "ArchivoX900.ttf", 74, L.WHITE, 0.02, k=L.SHEAR)
END_CTA = text("DM FOR A FREE SAMPLE", "JBMono700.ttf", 42, L.LIME, 0.0)


def panel_masks():
    sk = 26
    s, c = D.surface(W, PH + 20)
    c.move_to(PX0 + sk, 10)
    c.line_to(PX0 + PW + sk, 10)
    c.line_to(PX0 + PW - sk, PH + 10)
    c.line_to(PX0 - sk, PH + 10)
    c.close_path()
    c.set_source_rgba(1, 1, 1, 1)
    c.fill()
    m = D.surf_np(s)[..., 3:4]
    s, c = D.surface(W, PH + 20)
    c.move_to(PX0 + sk, 10)
    c.line_to(PX0 + PW + sk, 10)
    c.set_source_rgb(*D.c01(D.RED))
    c.set_line_width(6)
    c.stroke()
    for k in (1, 2):
        xx = PX0 + PW * k / 3
        c.move_to(xx + sk * 0.6, 34)
        c.line_to(xx - sk * 0.6, PH - 14)
        c.set_source_rgba(1, 1, 1, 0.22)
        c.set_line_width(2)
        c.stroke()
    return m, D.surf_np(s)


PANEL_M, PANEL_L = panel_masks()


def bank_images():
    banks = []
    for xa, xb in ((0, 420), (300, 780), (660, W)):
        bok = np.zeros((H, W, 3), np.float32)
        refl = np.zeros((H, W), np.float32)
        for _ in range(10):
            x, y = rng0.uniform(xa, xb), rng0.uniform(60, HOR - 260)
            r, b = rng0.uniform(6, 24), rng0.uniform(0.3, 0.95)
            cv2.circle(bok, (int(x), int(y)), int(r), (b, b * 0.95, b * 0.86), -1, cv2.LINE_AA)
            refl[HOR:, int(np.clip(x, 0, W - 1))] += b
        img = blur(bok, 6) * 0.6 + blur(bok, 34) * 0.45
        refl = cv2.GaussianBlur(refl, (0, 0), sigmaX=16, sigmaY=1)
        fall = np.exp(-np.clip(np.arange(H, dtype=np.float32) - HOR, 0, None) / 420)[:, None]
        img += (refl * fall)[..., None] * np.array((0.9, 0.9, 1.0), np.float32) * 0.33
        banks.append(img.astype(np.float32))
    return banks


BANKS = bank_images()
SKY = (np.ones((H, W, 3), np.float32) * np.array((0.03, 0.032, 0.045), np.float32)
       + np.exp(-(((XX / W - 0.5) / 0.6) ** 2 + ((YY / H) / 0.25) ** 2))[..., None] * RED * 0.22
       + np.exp(-(((XX / W - 0.5) / 0.5) ** 2 + (((YY - HOR) / H) / 0.08) ** 2))[..., None]
       * np.array((0.25, 0.4, 0.7), np.float32) * 0.12).astype(np.float32)
_tex, _ = D.ice_texture(2400)
TEX = np.concatenate([_tex, _tex[-700:][::-1]], 0).astype(np.float32)
FOG = (np.clip((np.arange(H, dtype=np.float32)[:, None, None] - HOR) / 300, 0, 1) ** 1.3)
HAZE = np.array((0.05, 0.065, 0.09), np.float32)

EMBERS = [(rng0.uniform(0, W), rng0.uniform(0, H), rng0.uniform(60, 220), rng0.uniform(1.2, 3.2), rng0.uniform(0.2, 0.8),
           rng0.uniform(0, 6.28), rng0.uniform(-30, 30)) for _ in range(90)]
SPARKS = [(math.cos(a) * s * 1.2, math.sin(a) * s * 0.8, rng0.uniform(0.35, 0.85), rng0.random() < 0.5)
          for a, s in zip(rng0.uniform(0, 2 * math.pi, 80), rng0.uniform(500, 1900, 80))]
VIG = (1 - 0.5 * np.clip(((XX / W - 0.5) ** 2 * 1.3 + (YY / H - 0.5) ** 2) * 2.0, 0, 1))[..., None].astype(np.float32)


# ================================================================= gemeinsame Ebenen
def speed_int(fn, t, n=40):
    if t <= 0:
        return 0.0
    s = np.linspace(0, t, n)
    return float(np.trapezoid([fn(x) for x in s], s))


def floor(vo, bright=1.0):
    T = 2400
    src = np.float32([[0, vo], [T, vo], [T, vo + T], [0, vo + T]])
    dst = np.float32([[W / 2 - 560, HOR], [W / 2 + 560, HOR], [W / 2 + 2300, 2400], [W / 2 - 2300, 2400]])
    m = cv2.getPerspectiveTransform(src, dst)
    fl = cv2.warpPerspective(TEX, m, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return (fl * FOG + HAZE * (1 - FOG)) * bright


def arena(level, vo):
    img = SKY * (0.35 + 0.65 * level)
    img[HOR:] = floor(vo, 0.3 + 0.7 * level)[HOR:]
    for k in range(3):
        img += BANKS[k] * level
    img += np.exp(-((np.arange(H, dtype=np.float32) - HOR) / 6) ** 2)[:, None, None] * 0.12
    return img


def light_level(k, t):
    t0 = T_LIGHTS[k]
    if t < t0:
        return 0.0
    d = t - t0
    flick = 1.0 if d > 0.12 else (0.3 if int(d * 60) % 2 else 1.0)
    return min(1.0, 0.25 + d * 8) * flick + 0.6 * math.exp(-d * 9)


def embers(img, tl, col):
    lay = np.zeros((H, W, 3), np.float32)
    for x, y, vy, r, b, ph, vx in EMBERS:
        py = (y - vy * tl) % H
        px = (x + vx * tl + 18 * math.sin(tl * 1.7 + ph)) % W
        a = b * (0.6 + 0.4 * math.sin(tl * 5 + ph))
        cv2.circle(lay, (int(px), int(py)), int(r), tuple(float(v * a) for v in col), -1, cv2.LINE_AA)
    img += lay + blur_q(lay, 10) * 1.5


def flip3d(img, spr, theta, scale, cx, cy, alpha=1.0):
    """Wappen um die senkrechte Achse gedreht (Perspektive), zentriert bei (cx, cy)."""
    h, w = spr.shape[:2]
    th = math.radians(theta)
    if abs(math.cos(th)) < 0.03:
        return
    f = 1700.0
    dst = []
    for x, y in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        k = f / (f + x * math.sin(th))
        dst.append((cx + x * math.cos(th) * k * scale, cy + y * k * scale))
    m = cv2.getPerspectiveTransform(np.float32([(0, 0), (w, 0), (w, h), (0, h)]), np.float32(dst))
    warped = cv2.warpPerspective(spr, m, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    over(img, warped * alpha, 0, 0)


# ================================================================= Szene 1: Laufschrift-Wand + GAMEDAY
def wall_speed(t):
    if t < T0:
        return 0.35 + 0.65 * smooth(t / T0)
    return 0.35 + 2.4 * math.exp(-(t - T0) * 3.5)


def type_wall(t, k_alpha=1.0):
    canvas = np.zeros((WALL_H, WALL_W, 4), np.float32)
    pos = speed_int(wall_speed, t)
    for s_, per, d, sp, y in WALL_ROWS:
        off = (d * sp * pos) % per
        over(canvas, s_, -per + off - 200, y)
    m = cv2.getRotationMatrix2D((WALL_W / 2, WALL_H / 2), 8, 1.0)
    m[0, 2] -= (WALL_W - W) / 2
    m[1, 2] -= (WALL_H - H) / 2
    return cv2.warpAffine(canvas, m, (W, H), flags=cv2.INTER_LINEAR) * k_alpha


def scene_intro(t):
    lv = min(1.0, sum(light_level(k, t) for k in range(3)) / 3)
    img = np.ones((H, W, 3), np.float32) * np.array((0.02, 0.012, 0.016), np.float32)
    img += np.exp(-(((XX - CX) / 700) ** 2 + ((YY - CY) / 700) ** 2))[..., None] * RED * (0.12 + 0.3 * lv)
    wall = type_wall(t, 0.35 + 0.65 * lv)
    img = wall[..., :3] + img * (1 - wall[..., 3:4])
    for x0, sp in ((-300, 900), (1400, -700)):     # rote Lichtkegel schwenken durchs Bild
        x = x0 + sp * t
        img += np.exp(-((XX - x - 0.5 * (YY - CY)) / 120) ** 2)[..., None] * RED * 0.18 * lv
    img *= 0.45 + 0.55 * min(1.0, lv + 0.3)
    if t >= T0 - 0.16:
        p = clamp01((t - (T0 - 0.16)) / 0.16)
        s = 1 + 1.6 * (1 - p ** 2)
        a = min(1.0, (t - (T0 - 0.16)) / 0.05)
        if t >= T0:
            d = t - T0
            e1, e2 = ease_out_expo(d / 0.3), ease_out_expo(d / 0.45)
            add_c(img, GD_BIG_GLOW, CX, CY, 0.5 + 1.2 * math.exp(-d * 5))
            over_c(img, GD_BIG_OUT * 0.3 * e2, CX + 30 * e2, CY + 26 * e2)
            over_c(img, GD_BIG_RED, CX + 14 * e1, CY + 13 * e1)
        over_c(img, scaled(GD_BIG, s) * a, CX, CY)
    q = ease_out_expo((t - (T_PILL0 - 0.25)) / 0.35)
    if q > 0:
        over_c(img, PILL_BIG * wipe_mask(PILL_BIG.shape[1], q), CX - 60 * (1 - q), CY - 215)
    q = ease_out_expo((t - T_TEASE) / 0.4)
    if q > 0:
        over_c(img, TEASE * wipe_mask(TEASE.shape[1], q), CX, CY + 205)
    return img


# ================================================================= Szene 2/3: Teams
def scene_team(t, home):
    t0, tland = (T_HOME, T_HL) if home else (T_AWAY, T_AL)
    tl = t - t0
    acc = RED if home else YEL
    img = (BG_HOME if home else BG_AWAY).copy()
    img += (((STRIPE_U - 260 * tl) % 140) < 46).astype(np.float32)[..., None] * 0.035
    vs_, per = VSTRIP_H if home else VSTRIP_A
    for x, d in ((30, 1), (W - 30 - vs_.shape[1], -1)):  # senkrechte Laufschrift links/rechts
        off = (d * 140 * tl) % per
        lay = np.zeros((H, W, 4), np.float32)
        over(lay, vs_, x, -per + off)
        img = lay[..., :3] * 0.22 + img * (1 - lay[..., 3:4] * 0.22)
    land = clamp01((t - tland + 0.25) / 0.25)
    m = cv2.getRotationMatrix2D((RAYS.shape[1] / 2, RAYS.shape[0] / 2), 10 * tl, 1.0)
    r = cv2.warpAffine(RAYS, m, RAYS.shape[::-1])
    k = (0.25 + 0.75 * land) + (0.8 * math.exp(-(t - tland) * 4) if t >= tland else 0)
    add_c(img, r[..., None] * (acc * 0.55 + WHITE * 0.2), CX, Y_TEAM, k)
    embers(img, tl, acc * 0.8 + WHITE * 0.2)
    spr, glw = (BIG_H, GLOW_BIG_H) if home else (BIG_A, GLOW_BIG_A)
    p = clamp01((t - (tland - 0.42)) / 0.42)
    theta = (-1 if home else 1) * 110 * (1 - ease_out_back(p, 1.3))
    sc = 1 + 0.5 * (1 - p) ** 2
    fy = 8 * math.sin((t - tland) * 3) if t > tland else 0
    if t >= tland - 0.42:
        add_c(img, glw, CX, Y_TEAM + fy, 0.5 + 0.7 * land + (1.0 * math.exp(-(t - tland) * 5) if t >= tland else 0))
        flip3d(img, spr, theta, sc, CX, Y_TEAM + fy, min(1.0, p * 4))
    if t >= tland:
        ring(img, CX, Y_TEAM, t - tland, acc)
    lets, total = NAME_H if home else NAME_A           # Buchstaben steigen gestaffelt auf
    x0 = CX - total / 2
    for i, (spr_l, xc) in enumerate(lets):
        q = clamp01((t - (tland + 0.12 + i * 0.025)) / 0.32)
        if q > 0:
            over_c(img, spr_l * smooth(q * 1.5), x0 + xc, 1235 + 70 * (1 - ease_out_back(q, 1.6)))
    q = ease_out_expo((t - (tland + 0.05)) / 0.3)
    if q > 0:
        over_c(img, (PILL_HT if home else PILL_GT) * q, CX - 50 * (1 - q), 1128)
    q = smooth((t - (tland + 0.45)) / 0.3)
    if q > 0:
        over_c(img, (EST_H if home else EST_A) * q, CX, 1318)
    return img


# ================================================================= Szene 4: VS-Clash
LINE_Y0, LINE_Y1 = 1180, 740                      # Diagonale bei x=0 / x=W


def line_y(x):
    return LINE_Y0 + (LINE_Y1 - LINE_Y0) * x / W


def bolt(seed, n=48, amp=26):
    r = np.random.default_rng(seed)
    off = np.cumsum(r.normal(0, amp * 0.45, n))
    off -= np.linspace(off[0], off[-1], n)
    off = np.clip(off, -amp, amp)
    xs = np.linspace(-20, W + 20, n)
    nx, ny = (LINE_Y0 - LINE_Y1) / W, 1.0
    nrm = math.hypot(nx, ny)
    return np.stack([xs + off * nx / nrm, line_y(xs) + off * ny / nrm], 1)


def half_img(home, tl):
    img = (BG_HOME if home else BG_AWAY).copy() * 0.85
    img += (((STRIPE_U + (-1 if home else 1) * 300 * tl) % 120) < 40).astype(np.float32)[..., None] * 0.04
    cx, cy = (300, 640) if home else (780, 1280)
    add_c(img, GLOW_MID_H if home else GLOW_MID_A, cx, cy, 1.1)
    over_c(img, MID_H if home else MID_A, cx, cy)
    # Namen außen (über dem Heim-, unter dem Gastwappen), damit das große VS in der Mitte frei bleibt
    nx, ny = (340, 365) if home else (720, 1545)
    over_c(img, VS_NAME_H if home else VS_NAME_A, nx, ny)
    return img


def scene_vs(t):
    tl = t - T_VSIN
    q = clamp01(tl / 0.32) ** 2.2
    dx_h, dx_a = -W * (1 - q), W * (1 - q)
    if t > T_VS:
        d = t - T_VS
        wob = 16 * math.exp(-d * 9) * math.sin(d * 30)
        dx_h, dx_a = dx_h - wob, dx_a + wob
    img = scene_team(t, False) * 0.45 if t < T_VS else np.zeros((H, W, 3), np.float32)
    for home, dx in ((True, dx_h), (False, dx_a)):
        hi = half_img(home, tl)
        hi = cv2.warpAffine(hi, np.float32([[1, 0, dx], [0, 1, 0]]), (W, H), borderMode=cv2.BORDER_CONSTANT)
        if abs(dx) > 2:
            hi = mblur(hi, min(160, abs(dx) * 0.25), False)
        ly = line_y(XX - dx)
        msk = np.clip((ly - YY) / 2 + 0.5, 0, 1) if home else np.clip((YY - ly) / 2 + 0.5, 0, 1)
        if home:
            msk = msk * (XX < W + dx)
        else:
            msk = msk * (XX > dx)
        img = img * (1 - msk[..., None]) + hi * msk[..., None]
    if t >= T_VS:
        d = t - T_VS
        lay = np.zeros((H, W, 3), np.float32)
        inten = 0.55 + 0.45 * math.exp(-d * 3) + 0.15 * math.sin(d * 37)
        for j in range(2):
            pts = bolt(int(d * 15) * 7 + j, amp=30 if j == 0 else 18)
            cv2.polylines(lay, [np.int32(pts)], False, (1.0, 1.0, 1.0), 4 if j == 0 else 2, cv2.LINE_AA)
        img += lay * inten + blur_q(lay, 18) * np.array((0.8, 0.85, 1.0), np.float32) * 1.6 * inten \
            + blur_q(lay, 60) * np.array((0.6, 0.5, 1.0), np.float32) * inten
        sp = np.zeros((H, W, 3), np.float32)
        for vx, vy, life, red in SPARKS:
            if d > life:
                continue
            f = (1 - math.exp(-3.2 * d)) / 3.2
            x, y = CX + vx * f, CY + vy * f + 160 * d * d
            v = math.exp(-3.2 * d)
            aa = (1 - d / life) ** 1.3
            cv2.line(sp, (int(x), int(y)), (int(x - vx * v * 0.028), int(y - vy * v * 0.028)),
                     tuple(float(c * aa) for c in (RED if red else WHITE)), 2, cv2.LINE_AA)
        img += sp + blur_q(sp, 14)
    tv = T_VS - 0.1
    if t >= tv:
        p2 = clamp01((t - tv) / 0.1)
        s = 1 + 2.2 * (1 - p2 ** 2)
        if t >= T_VS:
            e = ease_out_expo((t - T_VS) / 0.3)
            add_c(img, VS_BIG_GLOW, CX, CY, 0.4 + 0.8 * math.exp(-(t - T_VS) * 5))
            over_c(img, tint(VS_BIG, D.RED), CX - 12 * e, CY + 10 * e)
            over_c(img, tint(VS_BIG, D.BLUE), CX + 12 * e, CY - 10 * e)
        over_c(img, scaled(VS_BIG, s) * min(1.0, (t - tv) / 0.04), CX, CY)
    return img


# ================================================================= Szene 5: Info-Karten
def scene_info(t):
    tl = t - T_INFO
    img = floor(650 - 200 * tl, 0.75)
    img[:HOR] = SKY[:HOR]
    for k in range(3):
        img += BANKS[k] * 0.8
    img *= 0.55
    img += np.exp(-((XX / 380) ** 2 + ((YY - CY) / 700) ** 2))[..., None] * RED * 0.25
    img += np.exp(-(((XX - W) / 380) ** 2 + ((YY - CY) / 700) ** 2))[..., None] * BLUE * 0.25
    k = max(i for i, tc in enumerate(T_CARDS) if t >= tc - 1e-6)
    tc = T_CARDS[k]
    pill, val, val_red, val_out = CARDS[k]
    pin = ease_out_expo((t - tc) / 0.28)
    pout = clamp01((t - (T_CARDS[k + 1] - 0.12)) / 0.12) ** 2 if k < 2 else 0.0
    x = CX + W * (1 - pin) - W * 1.2 * pout
    lay = np.zeros((H, W, 4), np.float32)
    for j, dy in enumerate((-330, 330)):             # Kontur-Echos oben/unten, laufen gegeneinander
        over_c(lay, val_out * 0.35, x + ((-1) ** j) * 90 * (t - tc), CY + dy)
    e = ease_out_expo((t - tc) / 0.35)
    over_c(lay, val_red, x + 14 * e, CY + 13 * e)
    over_c(lay, val, x, CY)
    over_c(lay, pill, CX - 40 * (1 - pin) - W * 1.2 * pout, CY - 230)
    bl = 220 * (1 - pin) if pin < 0.98 else 0.0
    bl = max(bl, 260 * pout)
    if bl > 3:
        lay = mblur(lay, bl, False)
    img = lay[..., :3] + img * (1 - lay[..., 3:4])
    ring(img, CX, CY, t - tc, RED, 0.7)
    return img


# ================================================================= Szene 6: Plakat
def scene_poster(t):
    tl = t - T_PO
    img = arena(1.0, 260 * math.exp(-tl * 1.4))
    p = clamp01(tl / 0.22)                           # GAMEDAY fällt von oben rein
    if p >= 1:
        d = tl - 0.22
        e1, e2 = ease_out_expo(d / 0.3), ease_out_expo(d / 0.45)
        over_c(img, GD_OUT * 0.25 * e2, LX + 26 * e2, Y_GD + 22 * e2)
        over_c(img, GD_RED, LX + 12 * e1, Y_GD + 11 * e1)
    lay = np.zeros((H, W, 4), np.float32)
    over_c(lay, GD, LX, Y_GD - 420 * (1 - p ** 2))
    if p < 1:
        lay = mblur(lay, 90 * (1 - p) + 20, True)
    img = lay[..., :3] + img * (1 - lay[..., 3:4])
    if T_SHINE <= t <= T_SHINE + 0.6:
        q = smooth((t - T_SHINE) / 0.6)
        h, w = GD.shape[:2]
        band = np.exp(-((np.arange(w, dtype=np.float32)[None, :] - (-150 + (w + 300) * q)
                         - 0.35 * (h - np.arange(h, dtype=np.float32)[:, None])) / 45) ** 2)
        x0, y0 = int(LX - w / 2), int(Y_GD - h / 2)
        img[y0:y0 + h, x0:x0 + w] += (band * GD[..., 3])[..., None] * 0.5
    q = ease_out_expo((tl - 0.1) / 0.35)
    if q > 0:
        over_c(img, PILL * wipe_mask(PILL.shape[1], q), LX - 60 * (1 - q), Y_PILL)
    tlc = 0.32                                        # Wappen landen
    gl = 0.55 + (0.9 * math.exp(-(tl - tlc) * 5) if tl >= tlc else 0) + 0.06 * math.sin(t * 4.4)
    for home, cr, glw, shd, xe in ((True, CREST_H, GLOW_H, SHAD_H, X_HOME), (False, CREST_A, GLOW_A, SHAD_A, X_AWAY)):
        xs = -260 if home else W + 260
        x = xs + (xe - xs) * clamp01(tl / tlc) ** 2.2
        add_c(img, glw, x, Y_CR, gl)
        sh = np.zeros((H, W, 1), np.float32)
        add_c(sh, shd, x + 8, Y_CR + 15)
        img *= 1 - sh * 0.8
        if tl < tlc:
            accl = np.zeros((H, W, 4), np.float32)
            for j in range(5):
                over_c(accl, cr, xs + (xe - xs) * clamp01((tl - j * 0.006) / tlc) ** 2.2, Y_CR)
            img = accl[..., :3] / 5 + img * (1 - accl[..., 3:4] / 5)
        else:
            over_c(img, cr, x, Y_CR)
    tv = tlc - 0.1
    if tl >= tv:
        s = 1 + 2.0 * (1 - clamp01((tl - tv) / 0.1) ** 2)
        if tl >= tlc:
            e = ease_out_expo((tl - tlc) / 0.25)
            add_c(img, VS_GLOW, LX, Y_VS, 0.35 + 0.8 * math.exp(-(tl - tlc) * 6))
            over_c(img, VS_RED, LX + 7 * e, Y_VS + 7 * e)
        over_c(img, scaled(VS, s) * min(1.0, (tl - tv) / 0.04), LX, Y_VS)
    q = ease_out_expo((tl - 0.4) / 0.4)
    if q > 0:
        for i, (tn, tr, xn) in enumerate(NAMES):
            sh = np.zeros((H, W, 4), np.float32)
            over_c(sh, tn * wipe_mask(tn.shape[1], q, reverse=(i == 1)), xn, Y_NAME)
            over_c(sh, tr * smooth((tl - 0.55) / 0.3), xn, Y_ROLE)
            img *= 1 - np.clip(blur(sh[..., 3], 9) * 1.6, 0, 0.85)[..., None]
            img = sh[..., :3] + img * (1 - sh[..., 3:4])
    img *= 1 - 0.55 * np.clip((YY[..., None] - 1380) / 300, 0, 1)
    tp = 0.45                                         # Infoleiste
    if tl >= tp:
        pp = ease_out_expo((tl - tp) / 0.4)
        y0 = int(PY0 + 260 * (1 - pp))
        a = min(1.0, (tl - tp) / 0.1)
        ya, yb = max(0, y0 - 10), min(H, y0 + PH + 10)
        region = img[ya:yb].copy()
        frost = cv2.GaussianBlur(region, (0, 0), 18)
        msk = PANEL_M[ya - (y0 - 10):yb - (y0 - 10)] * a
        img[ya:yb] = region * (1 - msk) + (frost * 0.55 + np.array((0.02, 0.025, 0.04), np.float32) * 0.45) * msk
        over(img, PANEL_L * a, 0, y0 - 10)
        for k, (tlab, tv_) in enumerate(COLS):
            qq = clamp01((tl - (0.6 + 0.08 * k)) / 0.22)
            if qq > 0:
                cx = PX0 + PW * (k + 0.5) / 3
                over_c(img, tlab * smooth(qq), cx, y0 + 46)
                over_c(img, scaled(tv_, 1 + 0.5 * (1 - ease_out_back(qq, 1.4))) * smooth(qq * 1.6), cx, y0 + 102)
    q = clamp01((tl - 0.85) / 0.45)                   # Fuß
    if q > 0:
        cut = int(TICKET.shape[1] * q)
        if cut > 0:
            over(img, TICKET[:, :cut], PX0 - 10, Y_TK)
        if q < 1 or int(t * 3) % 2 == 0:
            cv2.rectangle(img, (int(PX0 - 6 + cut), Y_TK - 2), (int(PX0 + 4 + cut), Y_TK + TICKET.shape[0] + 2),
                          tuple(float(c) for c in RED), -1)
    a = smooth((tl - 1.1) / 0.4)
    if a > 0:
        right = PX0 + PW
        over(img, SYM_S * 0.85 * a, right - SYM_S.shape[1], Y_CRED - 4)
        over(img, CRED * a, right - SYM_S.shape[1] - 16 - CRED.shape[1], Y_CRED)
    return img


# ================================================================= Endkarte
def end_card(t):
    d = t - T_END
    img = np.ones((H, W, 3), np.float32) * np.array(D.c01(L.BG), np.float32)
    img += np.exp(-(((XX - CX) / 520) ** 2 + ((YY - 860) / 340) ** 2))[..., None] * LIME * 0.07
    sym = scaled(END_SYM, 1 + 0.35 * (1 - ease_out_expo(d / 0.3)))
    g = np.zeros((H, W, 4), np.float32)
    over_c(g, tint(sym, L.LIME), CX, 860)
    img += blur_q(g[..., :3], 26) * (0.6 + 1.0 * math.exp(-d * 5)) + blur_q(g[..., :3], 70) * 0.4
    over_c(img, sym * min(1.0, d / 0.08), CX, 860)
    if d > 0.18:
        q = ease_out_expo((d - 0.18) / 0.35)
        over_c(img, END_WM * q, CX, 1065 + 30 * (1 - q))
    if d > 0.4:
        q = clamp01((d - 0.4) / 0.4)
        w = END_CTA.shape[1]
        cut = int(w * q)
        x0 = CX - w / 2
        if cut > 0:
            over(img, END_CTA[:, :cut], x0, 1160)
        if q < 1 or int(d * 3) % 2 == 0:
            cv2.rectangle(img, (int(x0 + cut + 4), 1158), (int(x0 + cut + 22), 1160 + END_CTA.shape[0]),
                          tuple(float(c) for c in LIME), -1)
    return img


# ================================================================= Schnitte + Post
SCENES = [(0.0, scene_intro), (T_HOME, lambda t: scene_team(t, True)), (T_AWAY, lambda t: scene_team(t, False)),
          (T_VSIN, scene_vs), (T_INFO, scene_info), (T_PO, scene_poster)]
WHIPS = (T_HOME, T_AWAY, T_PO)                     # senkrechte Whip-Pans; übrige Schnitte hart mit Blitz


def glitch(img, t):
    rng = np.random.default_rng(int(t * 1000))
    amt = clamp01((t - T_OUT) / 0.25)
    out = img.copy()
    for _ in range(int(5 + 12 * amt)):
        y = int(rng.uniform(0, H))
        hgt = int(rng.uniform(10, 120))
        out[y:y + hgt] = np.roll(img[y:y + hgt], int(rng.uniform(-1, 1) * 160 * amt), axis=1)
    k = int(6 + 26 * amt)
    out[..., 0] = np.roll(out[..., 0], k, axis=1)
    out[..., 2] = np.roll(out[..., 2], -k, axis=1)
    if rng.random() < 0.35:
        out *= 0.5
    return out


def render_base(t):
    if t >= T_END:
        return end_card(t)
    for tc in WHIPS:
        if abs(t - tc) < WHIP:
            j = max(i for i, (s, _) in enumerate(SCENES) if s <= tc)
            fa, fb = SCENES[j - 1][1], SCENES[j][1]
            u = (t - (tc - WHIP)) / (2 * WHIP)
            sh = ease_io_expo(u) * H
            a = cv2.warpAffine(fa(min(t, tc - 1e-3)), np.float32([[1, 0, 0], [0, 1, -sh]]), (W, H))
            b = cv2.warpAffine(fb(max(t, tc)), np.float32([[1, 0, 0], [0, 1, H - sh]]), (W, H))
            return mblur(a + b, 40 + 300 * (1 - abs(u - 0.5) * 2), True)
    idx = max(i for i, (s, _) in enumerate(SCENES) if t >= s)
    img = SCENES[idx][1](t)
    return glitch(img, t) if t >= T_OUT else img


IMPACTS = [(T0, 26, 0.45, RED), (T_HL, 16, 0.3, RED), (T_AL, 16, 0.3, YEL), (T_VS, 30, 0.6, WHITE),
           (T_CARDS[0], 10, 0.15, RED), (T_CARDS[1], 10, 0.15, WHITE), (T_CARDS[2], 10, 0.15, RED),
           (T_PO + 0.32, 16, 0.25, WHITE), (T_END, 14, 0.4, LIME)] + [(tl, 4, 0.2, WHITE) for tl in T_LIGHTS]


def compose(t, fi):
    img = render_base(t)
    fl = np.zeros(3, np.float32)
    amp = ca = 0.0
    for t0, sh, f, col in IMPACTS:
        if t >= t0:
            d = t - t0
            fl += (col * 0.3 + WHITE * 0.7) * f * math.exp(-d * 16)
            amp += sh * math.exp(-d * 10)
            ca += sh * 0.45 * math.exp(-d * 9)
    img = img + fl
    if amp > 0.3:
        m = np.float32([[1, 0, amp * math.sin(t * 91)], [0, 1, amp * math.cos(t * 77)]])
        img = cv2.warpAffine(img, m, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    if ca > 0.5:
        k = int(round(ca))
        img = img.copy()
        img[..., 0] = np.roll(img[..., 0], k, axis=1)
        img[..., 2] = np.roll(img[..., 2], -k, axis=1)
    img = img + blur_q(np.clip(img - 0.78, 0, None), 30) * 0.45
    img *= VIG
    grain = np.random.default_rng(fi).standard_normal((H // 2, W // 2)).astype(np.float32)
    img += cv2.resize(grain, (W, H), interpolation=cv2.INTER_NEAREST)[..., None] * 0.012
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


# ================================================================= Ton
def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(5)
    mus = np.zeros((n, 2))
    sfx = np.zeros((n, 2))

    def tt(sec):
        return np.arange(int(sec * SR)) / SR

    def put(buf, sig, at, vol=1.0, pan=0.0):
        st = int(round(at * SR))
        if st >= n:
            return
        e = min(n, st + len(sig))
        gl, gr = math.cos((pan + 1) * math.pi / 4) * 1.41, math.sin((pan + 1) * math.pi / 4) * 1.41
        buf[st:e, 0] += sig[: e - st] * vol * gl
        buf[st:e, 1] += sig[: e - st] * vol * gr

    def lp(x, k):
        c = np.cumsum(np.concatenate([np.zeros(k), x]))
        return (c[k:] - c[:-k]) / k

    def hp(x, k):
        return x - lp(x, k)

    def noise(sec):
        return rng.standard_normal(int(sec * SR))

    def kick(vol=1.0):
        x = tt(0.45)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(44 + 170 * np.exp(-x * 32)) / SR) * np.exp(-x * 7) * 3.0) * vol

    def clap(vol=1.0):
        x = tt(0.3)
        return hp(noise(0.3), 2) * (np.exp(-x * 28) + 0.5 * np.exp(-np.abs(x - 0.012) * 300)) * 0.8 * vol

    def snare(vol=1.0):
        x = tt(0.2)
        return (hp(noise(0.2), 2) * np.exp(-x * 30) + np.sin(2 * np.pi * 190 * x) * np.exp(-x * 25) * 0.5) * vol

    def hat(vol=0.1):
        return hp(noise(0.05), 1) * np.exp(-tt(0.05) * 140) * vol

    def sub(freq, dur):
        x = tt(dur)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(freq * (1 + 0.5 * np.exp(-x * 9))) / SR) * 2.4) * \
            np.minimum(x / 0.004, 1) * np.exp(-x * 1.4) * 0.8

    def boom(vol=1.0):
        x = tt(1.4)
        body = np.tanh(np.sin(2 * np.pi * np.cumsum(42 + 110 * np.exp(-x * 13)) / SR) * np.exp(-x * 3) * 3.2)
        return (body + hp(noise(1.4), 2) * np.exp(-x * 40) * 0.8) * vol

    def whoosh(dur=0.3, vol=0.5, up=True):
        x = tt(dur)
        env = (x / dur) ** 2 if up else np.sin(np.pi * x / dur) ** 2
        return hp(lp(noise(dur), 6), 40) * env * vol

    def riser(dur=0.6, vol=0.4):
        x = tt(dur)
        f = 250 + 3000 * (x / dur) ** 2
        return (hp(noise(dur), 2) * 0.6 + np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.25) * (x / dur) ** 2 * vol

    def clunk(vol=0.8):
        x = tt(0.9)
        thump = lp(noise(0.9), 10) * 3 * np.exp(-x * 30) + np.sin(2 * np.pi * 70 * x) * np.exp(-x * 14)
        hum = (np.sin(2 * np.pi * 100 * x) + 0.4 * np.sin(2 * np.pi * 200 * x)) * np.exp(-x * 3) * 0.25
        return (thump + hum) * vol

    def horn(dur=1.4, vol=0.6):
        x = tt(dur)
        sig = sum(np.sign(np.sin(2 * np.pi * f * x)) * w for f, w in ((116.5, 1.0), (146.8, 0.7), (174.6, 0.55), (233.1, 0.3)))
        return lp(sig, 7) * np.minimum(x / 0.03, 1) * np.clip((dur - x) / 0.3, 0, 1) * vol

    def crowd(dur=3.0, vol=0.4):
        x = tt(dur)
        sig = lp(noise(dur), 10) - lp(noise(dur), 50) * 0.6
        return sig * np.minimum(x / 0.15, 1) * np.clip((dur - x) / 1.2, 0, 1) * vol * 2

    def zap(dur=1.6, vol=0.3):
        """Elektrisches Knistern (Blitz an der VS-Kante)."""
        x = tt(dur)
        crack = hp(noise(dur), 1) * (rng.random(len(x)) < 0.03) * 3
        buzz = np.sign(np.sin(2 * np.pi * 60 * x)) * 0.15 * (0.5 + 0.5 * np.sin(2 * np.pi * 9 * x))
        return (crack + lp(buzz, 3)) * np.exp(-x * 1.6) * vol

    def tick(vol=0.25, f0=2400):
        x = tt(0.05)
        return np.sin(2 * np.pi * f0 * x) * np.exp(-x * 120) * vol

    def glint():
        x = tt(0.8)
        f = 2600 + 3000 * x / 0.8
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.5 + 0.5 * np.sin(2 * np.pi * 22 * x)) * np.exp(-x * 4) * 0.25

    def stutter():
        x = tt(0.3)
        gate = (np.sin(2 * np.pi * 26 * x) > 0)
        return np.sign(np.sin(2 * np.pi * 620 * x)) * gate * 0.35 + hp(noise(0.3), 1) * gate * 0.3

    def chord(dur, freqs, vol):
        x = tt(dur)
        sig = np.zeros_like(x)
        for i, fr in enumerate(freqs):
            for det in (-0.004, 0.004):
                ph = 2 * np.pi * fr * (1 + det) * x + i
                sig += (2 * ((ph / (2 * np.pi)) % 1) - 1) * 0.5
        return lp(lp(sig, 14), 10) * np.minimum(x / 0.01, 1) * np.exp(-x * 0.9) * vol

    # Musik: 4/4 ab dem Drop, Break mit Snare-Wirbel vor dem VS (Beat 10–12)
    roots = [55.0, 55.0, 43.65, 49.0]
    k8 = 0
    while bt(k8 / 2) < T_OUT - 0.02:
        tb, b = bt(k8 / 2), k8 / 2
        pos = b % 4
        brk = 10 <= b < 12
        if float(pos).is_integer() and not brk:
            put(mus, kick(1.0), tb)
        if pos in (1.0, 3.0) and not brk:
            put(mus, clap(0.75), tb)
        put(mus, hat(0.12 if k8 % 2 else 0.07), tb, pan=0.3)
        if pos == 0.0 and not brk:
            put(mus, sub(roots[int(b // 4) % 4], 3.6 * B), tb)
        k8 += 1
    roll_t = bt(10)
    while roll_t < T_VS - 0.01:                      # Snare-Wirbel wird schneller und lauter
        prog = (roll_t - bt(10)) / (2 * B)
        put(mus, snare(0.35 + 0.6 * prog), roll_t)
        roll_t += B / 2 if prog < 0.5 else (B / 4 if prog < 0.8 else B / 8)
    for k, tl in enumerate(T_LIGHTS):
        put(sfx, clunk(0.9), tl, pan=(-0.6, 0.0, 0.6)[k])
    put(sfx, riser(0.8, 0.6), T0 - 0.8)
    put(sfx, crowd(DUR - 1.0, 0.16), 0.7)
    put(sfx, boom(1.0), T0)
    put(sfx, whoosh(0.3, 0.35), T_PILL0 - 0.25, pan=-0.5)
    put(sfx, whoosh(0.4, 0.3, up=False), T_TEASE, pan=0.4)
    for tc, tland, pan in ((T_HOME, T_HL, -0.3), (T_AWAY, T_AL, 0.3)):
        put(sfx, whoosh(0.22, 0.7), tc - 0.2)
        put(sfx, whoosh(0.4, 0.5), tland - 0.4, pan=pan)
        put(sfx, boom(0.75), tland)
        put(sfx, crowd(1.6, 0.4), tland, pan=pan)
        for i in range(12):
            put(sfx, tick(0.06, 2600 + 80 * i), tland + 0.12 + i * 0.025)
    put(sfx, riser(0.6, 0.5), T_VS - 0.6)
    put(sfx, whoosh(0.32, 0.7), T_VSIN, pan=-0.6)
    put(sfx, whoosh(0.32, 0.7), T_VSIN, pan=0.6)
    put(sfx, boom(1.0), T_VS)
    put(sfx, horn(1.5, 0.8), T_VS)
    put(sfx, crowd(2.6, 0.6), T_VS)
    put(sfx, zap(1.8, 0.4), T_VS)
    for tc in T_CARDS:
        put(sfx, whoosh(0.2, 0.55), tc - 0.18, pan=0.5)
        put(sfx, boom(0.45), tc)
        put(sfx, clap(0.5), tc)
    put(sfx, whoosh(0.22, 0.7), T_PO - 0.2)
    put(sfx, boom(0.7), T_PO + 0.32)
    put(sfx, chord(2.4, (110.0, 164.81, 220.0, 246.94, 329.63), 0.35), T_PO + 0.32)
    for k in range(3):
        put(sfx, tick(0.35, 1800 + 300 * k), T_PO + 0.6 + 0.08 * k, pan=(-0.5, 0, 0.5)[k])
    put(sfx, glint(), T_SHINE, pan=0.3)
    put(sfx, stutter(), T_OUT, 0.6)
    put(sfx, boom(0.9), T_END)
    put(sfx, chord(1.2, (110.0, 164.81, 220.0, 246.94, 329.63), 0.5), T_END)
    for i in range(10):
        put(sfx, tick(0.1, 3000), T_END + 0.4 + i * 0.04)
    mus /= np.max(np.abs(mus)) + 1e-9
    sfx /= np.max(np.abs(sfx)) + 1e-9
    mix = np.tanh((mus * 0.42 + sfx * 0.8) * 1.1)
    mix *= np.clip((DUR - np.arange(n) / SR) / 0.25, 0, 1)[:, None]
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
    wav = os.path.join(OUT, "_gameday.wav")
    make_audio(wav)
    nf = int(round(DUR * FPS))
    dst = os.path.join(OUT, "gameday_reel.mp4")
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "slow", "-crf", "21", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=9", "-ar", "44100", "-shortest",
           "-movflags", "+faststart", dst]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    with Pool(4) as pool:
        for i, fr in enumerate(pool.imap(_frame, range(nf), chunksize=2)):
            proc.stdin.write(fr)
            if i % 60 == 0:
                print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    os.remove(wav)
    Image.fromarray(compose(T_OUT - 0.3, 99999)).save(os.path.join(OUT, "gameday_reel_cover.jpg"), quality=93)
    print("fertig:", dst)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "prev":
        for ts in sys.argv[2:]:
            Image.fromarray(compose(float(ts), int(float(ts) * FPS))).save(os.path.join(OUT, f"vprev_{ts}.png"))
    else:
        main()
