"""NEXT MATCH – Beispiel #1 als Video: Eishockey-Gameday-Ankündigung (Reel 1080x1920, ~10 s, 30 fps).

Hallenlichter gehen an, GAMEDAY knallt rein, Wappen fliegen ein, Schläger kreuzen, VS + Torhupe, Puck fällt,
Infoleiste fährt hoch, Glanz – am Ende kurze NEXT-MATCH-Endkarte. Grafik-Bausteine aus demo_gameday.py,
Ton komplett synthetisch. Schnitte liegen auf dem Beat (128 BPM).

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

import cairocffi as cairo
import cv2
import numpy as np
from PIL import Image

import demo_gameday as D
import logo as L

OUT = D.OUT
W, H = 1080, 1920
FPS = 30
SR = 48000
B = 60 / 128                                      # Beatlänge
T0 = 1.13                                         # GAMEDAY-Impact = Beat 0


def bt(n):
    return T0 + n * B


DUR = bt(16) + 1.35                               # Endkarte ~1,1 s
T_LIGHTS = (0.12, 0.38, 0.64)
T_GD = T0 - 0.18
T_PILL = bt(0.75)
T_CR = bt(2)                                      # Wappen landen
T_ST = bt(3)                                      # Schläger kreuzen
T_VS = bt(4)                                      # VS-Impact + Torhupe
T_PK = bt(5)                                      # Puck landet
T_NM = bt(5.5)
T_PN = bt(6.5)                                    # Infoleiste
T_COL = (bt(7.5), bt(8), bt(8.5))
T_TK = bt(9)
T_CRED = bt(10)
T_SHINE = bt(11)
T_OUT = bt(16)
T_END = T_OUT + 0.25

CX = 540
LX = 525                                          # Layout-Mitte (etwas links: rechts liegen die Reel-Buttons)
HOR = 930
Y_PILL, Y_GD = 300, 470
Y_CR, X_HOME, X_AWAY = 860, 262, 790
Y_VS, Y_PK = 850, 985
Y_NAME, Y_ROLE = 1085, 1122
PX0, PY0, PW, PH = 80, 1200, 870, 150
Y_TK, Y_CRED = 1420, 1478

RED = np.array(D.c01(D.RED), np.float32)
BLUE = np.array(D.c01(D.BLUE), np.float32)
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


over, over_c, text, tint, blur = D.over, D.over_c, D.text, D.tint, D.blur


def pad(a, p):
    out = np.zeros((a.shape[0] + 2 * p, a.shape[1] + 2 * p, 4), np.float32)
    out[p:p + a.shape[0], p:p + a.shape[1]] = a
    return out


def scaled(a, s):
    if abs(s - 1) < 1e-3:
        return a
    h, w = a.shape[:2]
    return cv2.resize(a, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)


def blur_q(img, sigma):
    h, w = img.shape[:2]
    small = cv2.resize(img, (max(1, w // 4), max(1, h // 4)), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), sigma / 4)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)


# ================================================================= Assets (einmal vor dem Fork)
def stick_sprite():
    """Einzelner Schläger senkrecht, Drehpunkt = Kreuzungspunkt (wie sticks_cross(540))."""
    S = 540
    length = S * 0.72
    w, h = 460, int(length + 120)
    s, c = D.surface(w, h)
    c.translate(w / 2, 30)
    D.stick_path(c, length, shaft=19, blade=150, bh=40)
    g = cairo.LinearGradient(-10, 0, 10, 0)
    g.add_color_stop_rgb(0, 0.10, 0.10, 0.12)
    g.add_color_stop_rgb(0.5, 0.32, 0.33, 0.37)
    g.add_color_stop_rgb(1, 0.08, 0.08, 0.10)
    c.set_source(g)
    c.fill()
    c.save()
    D.stick_path(c, length, shaft=19, blade=150, bh=40)
    c.clip()
    for k in range(9):
        c.rectangle(18 + k * 14, length - 20, 9, 70)
    c.set_source_rgba(0.95, 0.95, 0.97, 0.9)
    c.fill()
    c.restore()
    c.rectangle(-9.5, 0, 19, 70)
    c.set_source_rgb(0.92, 0.92, 0.94)
    c.fill()
    return D.surf_np(s), (w / 2, 30 + S * 0.42)


def bank_images(rng):
    """Drei Lichtbänke (links/mitte/rechts) als Bokeh + Spiegelung auf dem Eis."""
    banks = []
    for k, (xa, xb) in enumerate(((0, 420), (300, 780), (660, W))):
        bok = np.zeros((H, W, 3), np.float32)
        refl = np.zeros((H, W), np.float32)
        for _ in range(10):
            x, y = rng.uniform(xa, xb), rng.uniform(60, HOR - 260)
            r, b = rng.uniform(6, 24), rng.uniform(0.3, 0.95)
            cv2.circle(bok, (int(x), int(y)), int(r), (b, b * 0.95, b * 0.86), -1, cv2.LINE_AA)
            refl[HOR:, int(np.clip(x, 0, W - 1))] += b
        img = blur(bok, 6) * 0.6 + blur(bok, 34) * 0.45
        refl = cv2.GaussianBlur(refl, (0, 0), sigmaX=16, sigmaY=1)
        fall = np.exp(-np.clip(np.arange(H, dtype=np.float32) - HOR, 0, None) / 420)[:, None]
        img += (refl * fall)[..., None] * np.array((0.9, 0.9, 1.0), np.float32) * 0.33
        banks.append(img)
    return banks


def sky():
    ys = np.arange(H, dtype=np.float32)[:, None, None] / H
    xs = np.arange(W, dtype=np.float32)[None, :, None] / W
    img = np.ones((H, W, 3), np.float32) * np.array((0.03, 0.032, 0.045), np.float32)
    img += np.exp(-(((xs - 0.5) / 0.6) ** 2 + ((ys - 0.0) / 0.25) ** 2)) * RED * 0.22
    img += np.exp(-(((xs - 0.5) / 0.5) ** 2 + ((ys - HOR / H) / 0.08) ** 2)) * np.array((0.25, 0.4, 0.7), np.float32) * 0.12
    return img


def ice_tex():
    T = 2400
    tex, _ = D.ice_texture(T)
    return np.concatenate([tex, tex[-700:][::-1]], 0), T     # unten gespiegelt verlängert (für die Kamerafahrt)


rng0 = np.random.default_rng(21)
SKY = sky()
BANKS = bank_images(rng0)
TEX, TEX_T = ice_tex()
FOG = (np.clip((np.arange(H, dtype=np.float32)[:, None, None] - HOR) / 300, 0, 1) ** 1.3)
HAZE = np.array((0.05, 0.065, 0.09), np.float32)

CREST_H = D.crest_home(300)
CREST_A = D.crest_away(290)
GLOW_H = blur(pad(tint(CREST_H, D.RED), 110), 40)[..., :3]
GLOW_A = blur(pad(tint(CREST_A, D.BLUE), 110), 40)[..., :3]
SHAD_H = blur(pad(tint(CREST_H, (0, 0, 0), 0.7), 40), 10)[..., 3]
SHAD_A = blur(pad(tint(CREST_A, (0, 0, 0), 0.7), 40), 10)[..., 3]
STICK, PIVOT = stick_sprite()
STICK_F = STICK[:, ::-1].copy()
PUCK = D.puck(120)
PILL = D.pill("HAUPTRUNDE  ·  SPIELTAG 12", D.RED, D.WHITE, 22)
GD = text("GAMEDAY", "Anton.ttf", 250, D.WHITE, 0.01, k=0.16)
GD_OUT = text("GAMEDAY", "Anton.ttf", 250, D.WHITE, 0.01, stroke=3, fill=False, k=0.16)
GD_RED = tint(GD, D.RED)
VS = text("VS", "Anton.ttf", 150, D.WHITE, 0.0, k=0.16)
VS_RED = tint(VS, D.RED)
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
SPARKS = []
for _ in range(70):
    ang = rng0.uniform(0, 2 * math.pi)
    sp = rng0.uniform(500, 1900)
    SPARKS.append((math.cos(ang) * sp * 1.2, math.sin(ang) * sp * 0.8, rng0.uniform(0.35, 0.85), rng0.random() < 0.5))
DUST = [(rng0.uniform(0, W), rng0.uniform(0, HOR + 300), rng0.uniform(-12, 12), rng0.uniform(-25, -6), rng0.uniform(1, 2.6),
         rng0.uniform(0.1, 0.35), rng0.uniform(0, 6.28)) for _ in range(80)]


# ================================================================= Zeitfunktionen
def light_level(k, t):
    t0 = T_LIGHTS[k]
    if t < t0:
        return 0.0
    d = t - t0
    flick = 1.0 if d > 0.12 else (0.3 if int(d * 60) % 2 else 1.0)
    return min(1.0, 0.25 + d * 8) * flick + 0.6 * math.exp(-d * 9)


def lights(t):
    return sum(light_level(k, t) for k in range(3)) / 3


def cam_offset(t):
    """Kamerafahrt übers Eis (Texturzeilen), stark am Anfang, ruhig im Hold."""
    return 520 * math.exp(-t * 0.9)


def shake(t):
    amp = 0.0
    for t0, a0, k in ((T0, 22, 10), (T_CR, 9, 14), (T_VS, 24, 9), (T_PK, 7, 16), (T_END, 14, 12)):
        if t >= t0:
            amp += a0 * math.exp(-(t - t0) * k)
    return amp * math.sin(t * 91.0), amp * math.cos(t * 77.0)


def flash(t):
    f = 0.0
    for t0, a, k in ((T0, 0.35, 18), (T_VS, 0.45, 16), (T_END, 0.4, 14)) + tuple((tl, 0.25, 22) for tl in T_LIGHTS):
        if t >= t0:
            f += a * math.exp(-(t - t0) * k)
    return f


# ================================================================= Ebenen
def background(t):
    lv = lights(t)
    img = SKY * (0.35 + 0.65 * min(1.0, lv))
    vo = cam_offset(t)
    T = TEX_T
    src = np.float32([[0, vo], [T, vo], [T, vo + T], [0, vo + T]])
    dst = np.float32([[W / 2 - 560, HOR], [W / 2 + 560, HOR], [W / 2 + 2300, 2400], [W / 2 - 2300, 2400]])
    m = cv2.getPerspectiveTransform(src, dst)
    fl = cv2.warpPerspective(TEX, m, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    fl = fl * FOG + HAZE * (1 - FOG)
    fl *= 0.3 + 0.7 * min(1.0, lv)
    img[HOR:] = fl[HOR:]
    for k in range(3):
        lk = light_level(k, t)
        if lk > 0:
            img += BANKS[k] * lk
    img += np.exp(-((np.arange(H, dtype=np.float32) - HOR) / 6) ** 2)[:, None, None] * 0.12 * min(1.0, lv)
    return img


def add_dust(img, t):
    lay = np.zeros((H, W, 3), np.float32)
    vis = smooth((t - 0.6) / 0.8) * (1 - smooth((t - T_OUT) / 0.2))
    for x, y, vx, vy, r, b, ph in DUST:
        a = b * vis * (0.6 + 0.4 * math.sin(t * 2.1 + ph))
        cv2.circle(lay, (int((x + vx * t) % W), int((y + vy * t) % (HOR + 300))), int(r), (a, a, a * 0.95), -1, cv2.LINE_AA)
    img += lay


def gameday(img, t):
    if t < T_GD:
        return
    p = clamp01((t - T_GD) / 0.18)
    s = 1 + 1.4 * (1 - p ** 2)
    a = min(1.0, (t - T_GD) / 0.06)
    if t >= T0:
        d = t - T0
        e1, e2 = ease_out_expo(d / 0.3), ease_out_expo(d / 0.45)
        over_c(img, GD_OUT * 0.25 * e2, LX + 26 * e2, Y_GD + 22 * e2)
        over_c(img, GD_RED, LX + 12 * e1, Y_GD + 11 * e1)
    over_c(img, scaled(GD, s) * a, LX, Y_GD)
    if T_SHINE <= t <= T_SHINE + 0.6:                # Glanz
        q = smooth((t - T_SHINE) / 0.6)
        h, w = GD.shape[:2]
        xs = np.arange(w, dtype=np.float32)[None, :]
        ys = np.arange(h, dtype=np.float32)[:, None]
        band = np.exp(-((xs - (-150 + (w + 300) * q) - 0.35 * (h - ys)) / 45) ** 2)
        x0, y0 = int(LX - w / 2), int(Y_GD - h / 2)
        img[y0:y0 + h, x0:x0 + w] += (band * GD[..., 3])[..., None] * 0.5


def pill(img, t):
    if t < T_PILL - 0.3:
        return
    p = ease_out_expo((t - (T_PILL - 0.3)) / 0.35)
    h, w = PILL.shape[:2]
    m = np.clip((np.arange(w, dtype=np.float32)[None, :] - w * p * 1.1) / -20, 0, 1)[..., None]
    over_c(img, PILL * m, LX - 60 * (1 - p), Y_PILL)


def crest_x(home, t):
    p = clamp01((t - (T_CR - 0.33)) / 0.33)
    q = p ** 2.2                                     # beschleunigt rein, harter Stopp
    x_end = X_HOME if home else X_AWAY
    x_start = -260 if home else W + 260
    x = x_start + (x_end - x_start) * q
    if t > T_CR:
        d = t - T_CR
        x += (-1 if home else 1) * 14 * math.exp(-d * 9) * math.sin(d * 30)
    return x


def crests(img, t):
    if t < T_CR - 0.33:
        return
    gl = 0.55 + 0.9 * math.exp(-max(0.0, t - T_CR) * 5) if t >= T_CR else 0.4
    gl += 0.06 * math.sin(t * 4.4)
    for home, cr, glw, shd, yy in ((True, CREST_H, GLOW_H, SHAD_H, Y_CR), (False, CREST_A, GLOW_A, SHAD_A, Y_CR)):
        xs = [crest_x(home, t - k * 0.5 / FPS / 4) for k in range(5)]
        x = xs[0]
        gh, gw = glw.shape[:2]
        x0, y0 = int(x - gw / 2), int(yy - gh / 2)
        xa, ya = max(0, x0), max(0, y0)
        xb, yb = min(W, x0 + gw), min(H, y0 + gh)
        if xb > xa and yb > ya:
            img[ya:yb, xa:xb] += glw[ya - y0:yb - y0, xa - x0:xb - x0] * gl
        sh_l = np.zeros((H, W), np.float32)
        sh_h, sh_w = shd.shape
        sx0, sy0 = int(x - sh_w / 2 + 8), int(yy - sh_h / 2 + 15)
        xa, ya, xb, yb = max(0, sx0), max(0, sy0), min(W, sx0 + sh_w), min(H, sy0 + sh_h)
        if xb > xa and yb > ya:
            sh_l[ya:yb, xa:xb] = shd[ya - sy0:yb - sy0, xa - sx0:xb - sx0]
            img *= 1 - sh_l[..., None] * 0.8
        if max(xs) - min(xs) > 1:
            acc = np.zeros((H, W, 4), np.float32)
            for xx in xs:
                over_c(acc, cr, xx, yy)
            over(img, acc / len(xs), 0, 0)
        else:
            over_c(img, cr, x, yy)


def stick_angle(t):
    p = (t - (T_ST - 0.28)) / 0.28
    if p < 0:
        return None
    return 36 * ease_out_back(p, 2.2)


def sticks(img, t):
    ang = stick_angle(t)
    if ang is None:
        return
    a = min(1.0, (t - (T_ST - 0.28)) / 0.08)
    lay = np.zeros((H, W, 4), np.float32)
    for spr, sgn in ((STICK, -1), (STICK_F, 1)):
        m = cv2.getRotationMatrix2D(PIVOT, -sgn * ang, 1.0)
        m[0, 2] += CX - 15 - PIVOT[0]
        m[1, 2] += Y_VS - PIVOT[1]
        w = cv2.warpAffine(spr, m, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        over(lay, w, 0, 0)
    over(img, lay * 0.95 * a, 0, 0)


def vs(img, t):
    t0 = T_VS - 0.15
    if t < t0:
        return
    p = clamp01((t - t0) / 0.15)
    s = 1 + 2.0 * (1 - p ** 2)
    a = min(1.0, (t - t0) / 0.05)
    g = np.zeros((H, W, 4), np.float32)
    if t >= T_VS:
        over_c(g, tint(VS, D.WHITE), LX, Y_VS)
        img += blur_q(g[..., :3], 22) * (0.35 + 0.8 * math.exp(-(t - T_VS) * 6))
        e = ease_out_expo((t - T_VS) / 0.25)
        over_c(img, VS_RED, LX + 7 * e, Y_VS + 7 * e)
    over_c(img, scaled(VS, s) * a, LX, Y_VS)


def ring_sparks(img, t):
    if t < T_VS or t > T_VS + 1.0:
        return
    d = t - T_VS
    lay = np.zeros((H, W, 3), np.float32)
    for delay, col, wmax, amp in ((0.0, RED, 26, 1.0), (0.07, WHITE, 10, 0.6)):
        dd = d - delay
        if dd <= 0:
            continue
        r = 40 + 1150 * (1 - math.exp(-dd * 5.0))
        aa = math.exp(-dd * 4.2) * amp
        cv2.ellipse(lay, (int(LX), int(Y_VS)), (int(r), int(r * 0.62)), 0, 0, 360,
                    tuple(float(c * aa) for c in col), max(2, int(wmax * math.exp(-dd * 3))), cv2.LINE_AA)
    for vx, vy, life, red in SPARKS:
        if d > life:
            continue
        k = 3.2
        f = (1 - math.exp(-k * d)) / k
        x, y = LX + vx * f, Y_VS + vy * f + 160 * d * d
        v = math.exp(-k * d)
        aa = (1 - d / life) ** 1.3
        col = RED if red else WHITE
        cv2.line(lay, (int(x), int(y)), (int(x - vx * v * 0.028), int(y - vy * v * 0.028)),
                 tuple(float(c * aa) for c in col), 2, cv2.LINE_AA)
    img += lay + blur_q(lay, 16) * 1.2


def puck_y(t):
    t0 = T_PK - 0.32
    if t < t0:
        return None
    if t < T_PK:
        p = (t - t0) / 0.32
        return Y_PK - 760 * (1 - p ** 2)
    d = t - T_PK
    return Y_PK - 40 * abs(math.sin(d * math.pi / 0.2)) * math.exp(-d * 8)


def puck(img, t):
    y = puck_y(t)
    if y is None:
        return
    hgt = Y_PK - y
    sh = np.zeros((H, W), np.float32)
    sc = max(0.4, 1 - hgt / 900)
    cv2.ellipse(sh, (int(LX), int(Y_PK + 22)), (int(62 * sc), int(14 * sc)), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
    sh = blur_q(sh, 10)
    img *= 1 - (sh * 0.75 * sc)[..., None]
    over_c(img, PUCK, LX, y)


def names(img, t):
    if t < T_NM:
        return
    p = ease_out_expo((t - T_NM) / 0.4)
    for i, (tn, tr, x) in enumerate(NAMES):
        h, w = tn.shape[:2]
        xs = np.arange(w, dtype=np.float32)[None, :]
        m = np.clip((w * p * 1.15 - xs) / 20, 0, 1) if i == 0 else np.clip((xs - w * (1 - p * 1.15)) / 20, 0, 1)
        m = m[..., None]
        sh = np.zeros((H, W, 4), np.float32)
        ra = smooth((t - T_NM - 0.15) / 0.3)
        over_c(sh, tn * m, x, Y_NAME)
        over_c(sh, tr * ra, x, Y_ROLE)
        img *= 1 - np.clip(blur(sh[..., 3], 9) * 1.6, 0, 0.85)[..., None]
        over(img, sh, 0, 0)


def panel(img, t):
    if t < T_PN:
        return
    p = ease_out_expo((t - T_PN) / 0.4)
    y0 = int(PY0 + 260 * (1 - p))
    a = min(1.0, (t - T_PN) / 0.1)
    y_lo, y_hi = y0 - 10, y0 + PH + 10
    ya, yb = max(0, y_lo), min(H, y_hi)
    region = img[ya:yb].copy()
    frost = cv2.GaussianBlur(region, (0, 0), 18)
    m = PANEL_M[ya - y_lo:yb - y_lo] * a
    pan = frost * 0.55 + np.array((0.02, 0.025, 0.04), np.float32) * 0.45
    img[ya:yb] = region * (1 - m) + pan * m
    over(img, PANEL_L * a, 0, y_lo)
    for k, (tl, tv) in enumerate(COLS):
        if t < T_COL[k]:
            continue
        q = clamp01((t - T_COL[k]) / 0.22)
        cx = PX0 + PW * (k + 0.5) / 3
        over_c(img, tl * smooth(q), cx, y0 + 46)
        over_c(img, scaled(tv, 1 + 0.5 * (1 - ease_out_back(q, 1.4))) * smooth(q * 1.6), cx, y0 + 102)


def footer(img, t):
    if t >= T_TK:
        q = clamp01((t - T_TK) / 0.5)
        w = TICKET.shape[1]
        cut = int(w * q)
        if cut > 0:
            over(img, TICKET[:, :cut], PX0 - 10, Y_TK)
        if q < 1 or int(t * 3) % 2 == 0:
            cv2.rectangle(img, (int(PX0 - 6 + cut), Y_TK - 2), (int(PX0 + 4 + cut), Y_TK + TICKET.shape[0] + 2),
                          tuple(float(c) for c in RED), -1)
    if t >= T_CRED:
        a = smooth((t - T_CRED) / 0.4)
        right = PX0 + PW
        over(img, SYM_S * 0.85 * a, right - SYM_S.shape[1], Y_CRED - 4)
        over(img, CRED * a, right - SYM_S.shape[1] - 16 - CRED.shape[1], Y_CRED)


def end_card(t, fi):
    d = t - T_END
    img = np.ones((H, W, 3), np.float32) * np.array(D.c01(L.BG), np.float32)
    img += np.exp(-(((np.arange(W, dtype=np.float32)[None, :] - CX) / 520) ** 2 +
                    ((np.arange(H, dtype=np.float32)[:, None] - 860) / 340) ** 2))[..., None] * LIME * 0.07
    p = ease_out_expo(d / 0.3)
    s = 1 + 0.35 * (1 - p)
    sym = scaled(END_SYM, s)
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


def glitch(img, t, fi):
    rng = np.random.default_rng(500 + fi)
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


def chroma(img, k):
    if k < 0.5:
        return img
    k = int(round(k))
    out = img.copy()
    out[..., 0] = np.roll(img[..., 0], k, axis=1)
    out[..., 2] = np.roll(img[..., 2], -k, axis=1)
    return out


VIG = None


def vignette():
    ys = np.arange(H, dtype=np.float32)[:, None] / H - 0.5
    xs = np.arange(W, dtype=np.float32)[None, :] / W - 0.5
    return (1 - 0.5 * np.clip((xs ** 2 * 1.3 + ys ** 2) * 2.0, 0, 1))[..., None]


VIG = vignette()


def compose(t, fi):
    if t >= T_END:
        img = end_card(t, fi)
    else:
        img = background(t)
        add_dust(img, t)
        gameday(img, t)
        pill(img, t)
        sticks(img, t)
        crests(img, t)
        vs(img, t)
        ring_sparks(img, t)
        puck(img, t)
        names(img, t)
        # unten abdunkeln (Lesbarkeit Fußzeile, Reel-Caption)
        img *= 1 - 0.55 * np.clip((np.arange(H, dtype=np.float32)[:, None, None] - 1380) / 300, 0, 1)
        panel(img, t)
        footer(img, t)
        if t >= T_OUT:
            img = glitch(img, t, fi)
    img += flash(t) * (WHITE * 0.75 + RED * 0.25 if t < T_END else WHITE * 0.6 + LIME * 0.4)
    sx, sy = shake(t)
    if abs(sx) + abs(sy) > 0.3:
        m = np.float32([[1, 0, sx], [0, 1, sy]])
        img = cv2.warpAffine(img, m, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    ca = 0.0
    for t0, a in ((T0, 10), (T_VS, 14), (T_END, 10)):
        if t >= t0:
            ca += a * math.exp(-(t - t0) * 9)
    img = chroma(img, ca)
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

    def whoosh(dur=0.35, vol=0.5, up=True):
        x = tt(dur)
        env = (x / dur) ** 2 if up else np.sin(np.pi * x / dur) ** 2
        return hp(lp(noise(dur), 6), 40) * env * vol

    def riser(dur=0.6, vol=0.4):
        x = tt(dur)
        f = 250 + 3000 * (x / dur) ** 2
        return (hp(noise(dur), 2) * 0.6 + np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.25) * (x / dur) ** 2 * vol

    def clunk(vol=0.8):
        """Hallenlicht-Schütz: dumpfer Schlag + 100-Hz-Brummen."""
        x = tt(0.9)
        thump = lp(noise(0.9), 10) * 3 * np.exp(-x * 30) + np.sin(2 * np.pi * 70 * x) * np.exp(-x * 14)
        hum = (np.sin(2 * np.pi * 100 * x) + 0.4 * np.sin(2 * np.pi * 200 * x)) * np.exp(-x * 3) * 0.25
        return (thump + hum) * vol

    def clack(vol=0.7):
        x = tt(0.25)
        return (hp(noise(0.25), 2) * np.exp(-x * 60) + np.sin(2 * np.pi * 900 * x) * np.exp(-x * 45) * 0.6 +
                np.sin(2 * np.pi * 1450 * x) * np.exp(-x * 55) * 0.4) * vol

    def puck_hit(vol=0.7):
        x = tt(0.3)
        return (lp(noise(0.3), 4) * 2 * np.exp(-x * 45) + np.sin(2 * np.pi * 420 * x) * np.exp(-x * 30)) * vol

    def horn(dur=1.3, vol=0.6):
        x = tt(dur)
        sig = sum(np.sign(np.sin(2 * np.pi * f * x)) * w for f, w in ((116.5, 1.0), (146.8, 0.7), (174.6, 0.55), (233.1, 0.3)))
        env = np.minimum(x / 0.03, 1) * np.clip((dur - x) / 0.3, 0, 1)
        return lp(sig, 7) * env * vol

    def crowd(dur=3.0, vol=0.4):
        x = tt(dur)
        sig = lp(noise(dur), 10) - lp(noise(dur), 50) * 0.6
        return sig * np.minimum(x / 0.15, 1) * np.clip((dur - x) / 1.2, 0, 1) * vol * 2

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

    # Musik ab GAMEDAY-Impact bis zum Glitch
    roots = [55.0, 55.0, 43.65, 49.0]
    k8 = 0
    while bt(k8 / 2) < T_OUT - 0.02:
        tb = bt(k8 / 2)
        b = k8 / 2
        pos = b % 4
        if pos in (0.0, 1.0, 2.0, 3.0):
            put(mus, kick(1.0), tb)
        if pos in (1.0, 3.0):
            put(mus, clap(0.75), tb)
        put(mus, hat(0.12 if k8 % 2 else 0.07), tb, pan=0.3)
        if pos == 0.0:
            put(mus, sub(roots[int(b // 4) % 4], 3.6 * B), tb)
        k8 += 1
    # Intro
    for k, tl in enumerate(T_LIGHTS):
        put(sfx, clunk(0.9), tl, pan=(-0.6, 0.0, 0.6)[k])
    put(sfx, riser(0.6, 0.6), T0 - 0.6)
    put(sfx, crowd(DUR - 1.0, 0.18), 0.7)
    # Treffer auf dem Beat
    put(sfx, boom(1.0), T0)
    put(sfx, whoosh(0.3, 0.4), T_PILL - 0.3, pan=-0.5)
    put(sfx, whoosh(0.33, 0.55), T_CR - 0.33, pan=-0.7)
    put(sfx, whoosh(0.33, 0.55), T_CR - 0.33, pan=0.7)
    put(sfx, boom(0.55), T_CR)
    put(sfx, whoosh(0.28, 0.4), T_ST - 0.28)
    put(sfx, clack(0.8), T_ST)
    put(sfx, riser(0.4, 0.4), T_VS - 0.4)
    put(sfx, boom(1.0), T_VS)
    put(sfx, horn(1.4, 0.75), T_VS)
    put(sfx, crowd(2.4, 0.55), T_VS)
    put(sfx, whoosh(0.32, 0.3), T_PK - 0.32)
    put(sfx, puck_hit(0.8), T_PK)
    put(sfx, puck_hit(0.3), T_PK + 0.2)
    put(sfx, whoosh(0.4, 0.35, up=False), T_NM, pan=-0.3)
    put(sfx, whoosh(0.4, 0.45, up=False), T_PN)
    for k, tc in enumerate(T_COL):
        put(sfx, tick(0.4, 1800 + 300 * k), tc, pan=(-0.5, 0, 0.5)[k])
    for i in range(12):
        put(sfx, tick(0.12, 3200), T_TK + i * 0.042, pan=-0.3 + i * 0.05)
    put(sfx, glint(), T_SHINE, pan=0.3)
    # Abgang + Endkarte
    put(sfx, stutter(), T_OUT, 0.6)
    put(sfx, boom(0.9), T_END)
    put(sfx, chord(1.3, (110.0, 164.81, 220.0, 246.94, 329.63), 0.5), T_END)
    for i in range(10):
        put(sfx, tick(0.1, 3000), T_END + 0.4 + i * 0.04)
    mus /= np.max(np.abs(mus)) + 1e-9
    sfx /= np.max(np.abs(sfx)) + 1e-9
    mix = mus * 0.42 + sfx * 0.8
    mix = np.tanh(mix * 1.1)
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
           "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
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
    Image.fromarray(compose(T_OUT - 0.4, 99999)).save(os.path.join(OUT, "gameday_reel_cover.jpg"), quality=93)
    print("fertig:", dst)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "prev":
        for ts in sys.argv[2:]:
            Image.fromarray(compose(float(ts), int(float(ts) * FPS))).save(os.path.join(OUT, f"vprev_{ts}.png"))
    else:
        main()
