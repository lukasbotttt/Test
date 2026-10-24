"""Reel 38: "3 GOALS. ONLY 1 COUNTS." – Tor-Quiz mit echten Fotos (2,5D, ~18 s).

Format: Quiz-Hook (Zuschauer raten 1/2/3), drei Tore, "Which one?", Auflösung in Zeitlupe, FOLLOW.
Allgemeine Regeln, keine Teams/Vereine.
Fakten (NHL Official Rules 2024-25, media.nhl.com, geprüft 24.10.2026):
- Rule 80.3: Angreifer trifft den Puck oberhalb der Latte, Puck geht rein -> kein Tor (Kontaktpunkt entscheidet).
- Rule 67.6: Angreifer schlägt/lenkt den Puck mit der Hand ins Tor -> kein Tor.
- Rule 80.3 (2. Absatz): Verteidiger schlägt den Puck mit hohem Schläger ins EIGENE Tor -> Tor zählt. (IIHF 80.3 gleich.)
Bild: echtes Foto eines leeren Eishockeytors als Kulisse; die Kamera ist an den vier Rahmenecken kalibriert
(solvePnP, Brennweite geschätzt), damit Puck, Schatten und Lattenhöhe perspektivisch stimmen. Schläger, Puck und
Handschuh sind echte, freigestellte Fotos (gear_cut.py) und werden als Sprites animiert. Keine Spielerkörper.
Bildnachweis (Wikimedia Commons): Tor + Schläger + Puck: Santeri Viinamäki, CC BY-SA 4.0; Handschuh: Petey21, CC0.
Stimme: Kokoro "Michael", 1,08x. Aufruf: python3 reel38_quiz.py vo | audio | prev 0.5,3.0 out.jpg | (Video)
"""
import json
import math
import os
import subprocess
import sys
import time
import wave

import cv2
import numpy as np
from PIL import Image, ImageDraw

import reel15_puck as R15
import reel18_dangle as R18
from reel15_puck import W, H, FPS, c01, smooth, sio, e_out, line_img, reveal, put, stroke_poly, surface, surf_rgba, over
from reel22_trapezoid import slam

HERE = R15.HERE
INK, ORANGE = R15.INK, R15.ORANGE
RED = (225, 30, 40)
GREEN = (30, 160, 80)
BLUE = (40, 110, 210)
HALO = (255, 255, 255)
NAVY = (38, 35, 52)
TEMPO = 1.08

VO_LINES = [
    ("q", "Three goals. Only ONE counts."),
    ("lock", "Which one? Lock it in."),
    ("r1", "One: the attacker's stick is above the crossbar. No goal."),
    ("r2", "Two. Batted in by hand. No goal."),
    ("r3", "Three counts! A defender's high stick into his own net is a goal."),
    ("cta", "Did you get it? Follow for more rules."),
]
VO_KEYS = [k for k, _ in VO_LINES]
VO_START = {"q": 0.1, "lock": 6.0, "r1": 7.6, "r2": 10.55, "r3": 12.6, "cta": 16.0}
DUR = 18.3
WT = {                                           # Wortanfänge (s nach Satzbeginn, nach 1,08x), faster-whisper small.en
    "q": [0.0, 0.2, 0.76, 0.82, 1.06],
    "lock": [0.0, 0.2, 0.46, 0.78, 0.94],
    "r1": [0.0, 0.18, 0.32, 0.76, 0.9, 1.06, 1.24, 1.38, 2.18, 2.32],
    "r2": [0.0, 0.18, 0.5, 0.6, 0.74, 1.22, 1.42],
    "r3": [0.0, 0.24, 0.96, 1.06, 1.48, 1.66, 1.86, 2.04, 2.2, 2.38, 2.6, 2.74, 2.86],
    "cta": [0.0, 0.12, 0.24, 0.4, 0.8, 0.94, 1.16, 1.36],
}


def wt(key, i):
    return VO_START[key] + WT[key][i]


PLAY_LEN = 1.8
S = [0.15, 2.05, 3.95]                           # Start der drei Tore
T_PLAYS_END = S[2] + PLAY_LEN
T_LOCK = VO_START["lock"] - 0.1
U_HIT, U_IN = 0.95, 1.3                          # lokale Zeit: Kontakt, Puck im Tor
# Replays: u = u0 + (t - Start) * rate  (Zeitlupe)
REPLAY = {0: ("r1", 0.3, 0.47), 1: ("r2", 0.45, 0.62), 2: ("r3", 0.6, 0.5)}
T_NO1 = wt("r1", 8)                              # "No goal"
T_NO2 = wt("r2", 5)
T_YES = wt("r3", 1)                              # "counts"
T_CTA = VO_START["cta"]

# ================================================================= Foto-Kamera (an den Torpfosten kalibriert)
GEAR = os.path.join(HERE, "gear")
PH_W, PH_H = 3868, 2762
FPH = 7275.0                                     # Brennweite in Pixeln (aus den 4 Rahmenecken geschätzt)
POST_Z, BAR_Y = 37.2, 49.2                       # Rohrmitte: 6 x 4 ft Innenmaß + Rohr
CROSSBAR = BAR_Y


def _pose():
    img_pts = np.array([(1325, 1065), (1335, 1930), (2142, 1215), (2116, 2198)], np.float64)
    obj = np.array([(0, BAR_Y, -POST_Z), (0, 0, -POST_Z), (0, BAR_Y, POST_Z), (0, 0, POST_Z)], np.float64)
    K = np.array([[FPH, 0, PH_W / 2], [0, FPH, PH_H / 2], [0, 0, 1.0]])
    _, rv, tv = cv2.solvePnP(obj, img_pts, K, None, flags=cv2.SOLVEPNP_IPPE)
    return cv2.Rodrigues(rv)[0], tv.ravel()


ROT, TRA = _pose()


def to_photo(p):
    q = ROT @ np.asarray(p, float) + TRA
    return np.array([FPH * q[0] / q[2] + PH_W / 2, FPH * q[1] / q[2] + PH_H / 2]), q[2]


# ================================================================= Spielzüge (Zoll; Torlinie x = 0, Tor offen nach -x)
P = [
    dict(a=np.array([-32.0, 25.0, -5.0]), c=np.array([-12.0, 62.0, 6.0]), n=np.array([18.0, 16.0, -6.0]),
         r=np.array([24.0, 0.5, -9.0]), arc=14.0, kind="stick", spr="stick_white", flip=False,
         grip=np.array([-30.0, 42.0, -30.0]), pre=np.array([-10.0, 18.0, -4.0]), post=np.array([12.0, -14.0, -2.0]),
         far=np.array([-34.0, 30.0, -10.0]), who="ATTACKER", col=RED),
    dict(a=np.array([-60.0, 0.5, 30.0]), c=np.array([-12.0, 24.0, 10.0]), n=np.array([18.0, 9.0, 2.0]),
         r=np.array([24.0, 0.5, 0.0]), arc=10.0, kind="glove", far=np.array([-30.0, 20.0, 10.0]),
         who="ATTACKER", col=RED),
    dict(a=np.array([-50.0, 40.0, 10.0]), c=np.array([-10.0, 62.0, -12.0]), n=np.array([17.0, 21.0, 8.0]),
         r=np.array([24.0, 0.5, 10.0]), arc=24.0, kind="stick", spr="stick_black", flip=True,
         grip=np.array([14.0, 42.0, 40.0]), pre=np.array([6.0, 14.0, 12.0]), post=np.array([9.0, -12.0, 8.0]),
         far=np.array([18.0, 30.0, 26.0]), who="DEFENDER", col=BLUE),
]


def puck_at(k, u):
    p = P[k]
    if u < U_HIT:
        s = c01(u / U_HIT)
        s = 0.25 * s + 0.75 * (1 - (1 - s) ** 1.6)
        return p["a"] + (p["c"] - p["a"]) * s + np.array([0, p["arc"] * math.sin(math.pi * s) * 0.6, 0])
    if u < U_IN:
        s = (u - U_HIT) / (U_IN - U_HIT)
        return p["c"] + (p["n"] - p["c"]) * s
    s = c01((u - U_IN) / 0.25)
    q = p["n"] + (p["r"] - p["n"]) * s
    q[1] = max(0.5, p["n"][1] * (1 - s) ** 2 + 0.5 + 2.5 * math.sin(math.pi * c01((u - U_IN - 0.25) / 0.2)) * (u > U_IN + 0.25))
    return q


def hit_dir(k):
    p = P[k]
    d = p["n"] - p["c"]
    return d / np.linalg.norm(d)


def swing(k, u):
    """Versatz des Schlägerblatts/Handschuhs vom Kontaktpunkt."""
    p = P[k]
    pre = p.get("pre", np.array([-10.0, 12.0, 0.0]))
    post = p.get("post", hit_dir(k) * 14)
    if u < 0.55:
        return pre + p["far"] * (1 - sio(c01((u - 0.05) / 0.5)))
    if u < U_HIT:
        s = (u - 0.55) / (U_HIT - 0.55)
        return pre * (1 - s ** 1.8)
    s = e_out(c01((u - U_HIT) / 0.25), 2)
    out = post * s
    if u > 1.45:
        out = out + p["far"] * sio(c01((u - 1.45) / 0.35))
    return out


# ================================================================= Freisteller (echte Fotos, gear_cut.py)
SPR_PPI = 26.0                                   # Sprites werden auf 26 px/Zoll vorskaliert
_SPR = {}


def _premul(rgba):
    a = rgba[..., 3:4].astype(np.float32) / 255
    return np.dstack([rgba[..., :3].astype(np.float32) / 255 * a, a])


def stick_sprite(name, flip):
    """(RGBA vormultipliziert, Blattmitte (x, y), Schaftrichtung) – Schaft nach links oben verlängert."""
    key = (name, flip)
    if key in _SPR:
        return _SPR[key]
    im = np.asarray(Image.open(os.path.join(GEAR, name + ".png")).convert("RGBA"))
    h, w = im.shape[:2]
    al = im[..., 3] > 128
    ys = np.arange(h)

    def ctr(x):
        col = al[:, x]
        return float(ys[col].mean()) if col.any() else None

    bend = int(w * (0.47 if name == "stick_white" else 0.42))
    blade_px = w - bend
    sc = SPR_PPI * 11.0 / blade_px                # Blatt ≈ 11 Zoll
    im = cv2.resize(im, (int(w * sc), int(h * sc)), interpolation=cv2.INTER_AREA)
    h, w = im.shape[:2]
    al = im[..., 3] > 128
    ys = np.arange(h)
    x0, x1 = 3, int(w * 0.18)
    c0, c1 = ctr(x0), ctr(x1)
    d = np.array([x0 - x1, c0 - c1], float)
    d /= np.linalg.norm(d)
    # Schaft verlängern: linken Streifen entlang der Schaftrichtung wiederholen
    ext = int(SPR_PPI * 46)
    step = 12
    n = ext // step
    off_x, off_y = int(-d[0] * ext) + 10, int(-d[1] * ext) + 10
    can = np.zeros((h + off_y + 20, w + off_x + 10, 4), np.uint8)
    can[off_y:off_y + h, off_x:off_x + w] = im
    strip = im[:, 4:4 + step + 2]
    for i in range(1, n + 1):
        sx = off_x + 4 - step * i
        sy = off_y + int(round(-step * i * d[1] / d[0])) if d[0] != 0 else off_y
        if sx < 0 or sy < 0:
            break
        reg = can[sy:sy + h, sx:sx + strip.shape[1]]
        hh, ww = reg.shape[:2]
        m = strip[:hh, :ww, 3:4] > reg[..., 3:4]
        can[sy:sy + hh, sx:sx + ww] = np.where(m, strip[:hh, :ww], reg)
    xs = np.arange(int(w * 0.62), w - 2)
    bx = float(xs.mean()) + off_x
    by = float(np.mean([ctr(x) for x in xs if ctr(x) is not None])) + off_y
    spr = _premul(can)
    if flip:
        spr = spr[:, ::-1].copy()
        bx = spr.shape[1] - 1 - bx
        d = np.array([-d[0], d[1]])
    _SPR[key] = (spr, np.array([bx, by]), d)
    return _SPR[key]


def glove_sprite():
    if "glove" not in _SPR:
        im = np.asarray(Image.open(os.path.join(GEAR, "glove.png")).convert("RGBA"))[::-1, ::-1]   # Finger nach oben
        h, w = im.shape[:2]
        sc = SPR_PPI * 16.0 / h                   # Handschuh ≈ 16 Zoll lang (inkl. Stulpe)
        im = cv2.resize(np.ascontiguousarray(im), (int(w * sc), int(h * sc)), interpolation=cv2.INTER_AREA)
        _SPR["glove"] = _premul(im)
    return _SPR["glove"]


def puck_sprite():
    if "puck" not in _SPR:
        im = np.asarray(Image.open(os.path.join(GEAR, "puck.png")).convert("RGBA"))
        h, w = im.shape[:2]
        sc = SPR_PPI * 3.0 / w * 2                # doppelte Auflösung, Puck 3 Zoll
        im = cv2.resize(im, (int(w * sc), int(h * sc)), interpolation=cv2.INTER_AREA)
        _SPR["puck"] = _premul(im)
    return _SPR["puck"]


_PHOTO = {}


def photo():
    if "p" not in _PHOTO:
        im = cv2.imread(os.path.join(GEAR, "goal_clean.jpg"))[..., ::-1]
        _PHOTO["p"] = np.ascontiguousarray(im)
    return _PHOTO["p"]


# ================================================================= Zeitlinie
def state(t):
    """(Szene, Spielzug k, lokale Zeit u)"""
    for k in range(3):
        if S[k] <= t < S[k] + PLAY_LEN:
            return "play", k, t - S[k]
    if t < S[0]:
        return "play", 0, 0.0
    if t < VO_START["r1"]:
        return "lock", 2, 1.79
    for k in (2, 1, 0):
        key, u0, rate = REPLAY[k]
        if t >= VO_START[key]:
            if k == 2 and t >= T_CTA - 0.1:
                return "cta", 2, 1.79
            return "replay", k, min(u0 + (t - VO_START[key]) * rate, 1.79)
    return "lock", 2, 1.79


def puck_state(t):
    sc, k, u = state(t)
    if sc in ("lock", "cta"):
        return P[2]["r"], 0.0
    return puck_at(k, u), 1.0


# ================================================================= Bildausschnitt (digitale Kamera im Foto)
TOP_FADE = (np.clip(1 - np.arange(H, dtype=np.float32) / 760, 0, 1) ** 1.6 * 0.62)[:, None, None]
S_MIN = H / PH_H                                  # ganze Fotohöhe
BASE_V = (1880.0, PH_H / 2, S_MIN)


def clamp_view(vx, vy, s):
    s = max(s, S_MIN)
    hw, hh = W / 2 / s, H / 2 / s
    return float(np.clip(vx, hw, PH_W - hw)), float(np.clip(vy, hh, PH_H - hh)), s


def lerp_v(a, b, k):
    return tuple(a[i] + (b[i] - a[i]) * k for i in range(3))


def replay_view(k):
    ph, _ = to_photo(P[k]["c"])
    g, _ = to_photo(np.array([0.0, 30.0, 0.0]))
    dy = -170.0 if P[k]["kind"] == "stick" else 0.0
    dx = 140.0 if k == 2 else 60.0
    return (ph[0] * 0.5 + g[0] * 0.5 + dx, ph[1] * 0.5 + g[1] * 0.5 + 40 + dy, 0.86)


def view(t):
    sc, k, u = state(t)
    v_a, v_b = (1800.0, PH_H / 2, S_MIN), (1760.0, 1440.0, 0.75)
    if sc == "play":
        v = lerp_v(v_a, v_b, sio(c01(u / PLAY_LEN)))
    elif sc == "lock":
        v = lerp_v(v_b, v_a, sio(c01((t - T_PLAYS_END) / 1.2)))
    elif sc == "replay":
        tt_ = t - VO_START[REPLAY[k][0]]
        v0 = replay_view(k)
        v = (v0[0] - 10 * tt_, v0[1], v0[2] + 0.03 * tt_)
    else:
        v = lerp_v(v_a, (1780.0, 1420.0, 0.74), sio(c01((t - T_CTA) / 2.2)))
    return clamp_view(*v)


def to_screen(p, v):
    ph, d = to_photo(p)
    vx, vy, s = v
    return np.array([(ph[0] - vx) * s + W / 2, (ph[1] - vy) * s + H / 2]), FPH / d * s


def background(v):
    vx, vy, s = v
    if s < 0.9:                                   # Verkleinern ohne Aliasing: halbe Auflösung als Quelle
        src = _PHOTO.get("half")
        if src is None:
            src = _PHOTO["half"] = cv2.resize(photo(), (PH_W // 2, PH_H // 2), interpolation=cv2.INTER_AREA)
        M = np.array([[2 * s, 0, W / 2 - s * vx], [0, 2 * s, H / 2 - s * vy]], np.float32)
    else:
        src = photo()
        M = np.array([[s, 0, W / 2 - s * vx], [0, s, H / 2 - s * vy]], np.float32)
    img = cv2.warpAffine(src, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    img = img.astype(np.float32) / 255
    # Studio-Look: oben weich aufgehellt (Text), Farben leicht kühler/heller
    img = img * np.array([0.98, 1.0, 1.03], np.float32)
    img = img + (1 - img) * TOP_FADE
    return img


def blit(img, spr, M):
    """Vormultipliziertes RGBA-Sprite mit Affinmatrix M (Sprite -> Bild) aufs Bild."""
    out = cv2.warpAffine(spr, M.astype(np.float32), (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                         borderValue=(0, 0, 0, 0))
    a = out[..., 3:4]
    return img * (1 - a) + out[..., :3]


def affine(src_pt, dst_pt, scale, ang):
    c, s_ = math.cos(ang) * scale, math.sin(ang) * scale
    A = np.array([[c, -s_], [s_, c]])
    t_ = np.asarray(dst_pt) - A @ np.asarray(src_pt)
    return np.hstack([A, t_[:, None]])


def soft_shadow(img, xy, rx, ry, a):
    if a <= 0.01:
        return img
    x0, x1 = int(max(0, xy[0] - rx * 2.5)), int(min(W, xy[0] + rx * 2.5))
    y0, y1 = int(max(0, xy[1] - ry * 2.5)), int(min(H, xy[1] + ry * 2.5))
    if x1 <= x0 or y1 <= y0:
        return img
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    g = np.exp(-(((xx - xy[0]) / rx) ** 2 + ((yy - xy[1]) / ry) ** 2)) * a
    img[y0:y1, x0:x1] *= (1 - g)[..., None]
    return img


def draw_stick(img, k, u, v):
    p = P[k]
    spr, bc, d_s = stick_sprite(p["spr"], p["flip"])
    B = p["c"] + swing(k, u) - hit_dir(k) * 2.2 - np.array([0, 0.5, 0])
    T = p["c"] + p["grip"] + swing(k, u) * 0.35
    bxy, ppi = to_screen(B, v)
    txy, _ = to_screen(T, v)
    d = (txy - bxy) / (np.linalg.norm(txy - bxy) + 1e-6)
    ang = math.atan2(d[1], d[0]) - math.atan2(d_s[1], d_s[0])
    # Schatten aufs Eis
    gxy, gppi = to_screen(np.array([B[0], 0.0, B[2]]), v)
    img = soft_shadow(img, gxy, 7 * gppi, 2.2 * gppi, 0.28 * math.exp(-B[1] / 40))
    return blit(img, spr, affine(bc, bxy, ppi / SPR_PPI, ang)), txy, ppi


def draw_glove(img, k, u, v):
    p = P[k]
    spr = glove_sprite()
    G = p["c"] + swing(k, u) + np.array([-4.0, 1.0, 0.0])
    gxy, ppi = to_screen(G, v)
    flick = 0.5 * (1 - sio(c01((u - 0.6) / 0.35))) - 0.45 * e_out(c01((u - U_HIT) / 0.25), 2)
    sxy, sppi = to_screen(np.array([G[0], 0.0, G[2]]), v)
    img = soft_shadow(img, sxy, 6 * sppi, 2.0 * sppi, 0.3 * math.exp(-G[1] / 40))
    ctr = np.array([spr.shape[1] / 2, spr.shape[0] * 0.42])
    return blit(img, spr, affine(ctr, gxy, ppi / SPR_PPI, -0.25 + flick)), gxy - np.array([0, 9 * ppi]), ppi


def draw_puck(img, k, u, v, rate):
    spr = puck_sprite()
    p = puck_at(k, u)
    pxy, ppi = to_screen(p, v)
    sxy, sppi = to_screen(np.array([p[0], 0.0, p[2]]), v)
    img = soft_shadow(img, sxy, 2.0 * sppi, 0.7 * sppi, 0.45 * math.exp(-p[1] / 25))
    q, _ = to_screen(puck_at(k, max(0.0, u - rate / 60)), v)
    n = 5 if np.linalg.norm(pxy - q) > 3 else 1
    sc = ppi * 3.0 / (spr.shape[1])
    acc = np.zeros((H, W, 4), np.float32)
    for i in range(n):
        f = i / max(n - 1, 1)
        c = q + (pxy - q) * f
        M = affine((spr.shape[1] / 2, spr.shape[0] / 2), c, sc, 0.15 * math.sin(u * 7))
        acc += cv2.warpAffine(spr, M.astype(np.float32), (W, H), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0)) / n
    return img * (1 - acc[..., 3:4]) + acc[..., :3], pxy


# ================================================================= Overlays
def ring(ctx, xy, r, col, a, wd=6):
    ctx.set_source_rgba(col[0] / 255, col[1] / 255, col[2] / 255, a)
    ctx.set_line_width(wd)
    ctx.arc(float(xy[0]), float(xy[1]), r, 0, 2 * math.pi)
    ctx.stroke()


def brackets(ctx, xy, t, r=30):
    r = r + 3 * math.sin(t * 9)
    ctx.set_source_rgba(1, 1, 1, 0.95)
    ctx.set_line_width(5)
    for k_ in range(4):
        a0 = k_ * math.pi / 2 + 0.35
        ctx.arc(float(xy[0]), float(xy[1]), r, a0, a0 + 0.9)
        ctx.stroke()
    ctx.set_source_rgba(INK[0] / 255, INK[1] / 255, INK[2] / 255, 0.9)
    ctx.set_line_width(2.5)
    for k_ in range(4):
        a0 = k_ * math.pi / 2 + 0.35
        ctx.arc(float(xy[0]), float(xy[1]), r, a0, a0 + 0.9)
        ctx.stroke()


def bar_line(ctx, v, a, t):
    """Gestrichelte Linie auf Lattenhöhe, über das Tor hinaus."""
    if a <= 0:
        return
    pts = np.array([to_screen(np.array([0.0, BAR_Y, z]), v)[0] for z in np.linspace(-170, 170, 40)])
    stroke_poly(ctx, pts, (255, 255, 255), 0.5 * a, 16)
    stroke_poly(ctx, pts, ORANGE, 0.25 * a, 22)
    ctx.set_dash([26, 16], -t * 60)
    stroke_poly(ctx, pts, ORANGE, 0.95 * a, 6)
    ctx.set_dash([])
    lab = line_img("CROSSBAR HEIGHT", 26, 850, ORANGE, track=5)
    return pts, lab



def word(txt, size, col):
    im = R18.word_img(txt, size, col, HALO)
    if im.width > 1040:
        im = im.resize((1040, int(im.height * 1040 / im.width)), Image.LANCZOS)
    return im


def fade_im(im, a):
    if a >= 1:
        return im
    im = im.copy()
    im.putalpha(im.getchannel("A").point(lambda v: int(v * max(a, 0.0))))
    return im


_CHIPS = {}


def chip(txt, col, size=34, fg=(255, 255, 255)):
    key = (txt, col, size, fg)
    if key not in _CHIPS:
        t_ = line_img(txt, size, 850, fg, track=4)
        im = Image.new("RGBA", (t_.width + 44, t_.height + 26), (0, 0, 0, 0))
        ImageDraw.Draw(im).rounded_rectangle((0, 0, im.width - 1, im.height - 1), im.height // 2, fill=col + (255,))
        im.alpha_composite(t_, (22, 13))
        _CHIPS[key] = im
    return _CHIPS[key]


def num_badge(n, state_, size=118):
    """Kreis mit Nummer; state_: None (offen), 'now' (aktiv), 'no' (rot X), 'yes' (grün Haken)."""
    key = ("b", n, state_, size)
    if key in _CHIPS:
        return _CHIPS[key]
    s = 2
    im = Image.new("RGBA", (size * s, size * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fill = {None: (255, 255, 255), "now": ORANGE, "no": RED, "yes": GREEN}[state_]
    d.ellipse((6, 6, size * s - 6, size * s - 6), fill=fill + (255,), outline=INK + (255,) if state_ is None else None,
              width=8)
    im = im.resize((size, size), Image.LANCZOS)
    if state_ == "no":
        d2 = ImageDraw.Draw(im)
        q = size * 0.3
        d2.line((q, q, size - q, size - q), fill=(255, 255, 255, 255), width=int(size * 0.09))
        d2.line((q, size - q, size - q, q), fill=(255, 255, 255, 255), width=int(size * 0.09))
    elif state_ == "yes":
        d2 = ImageDraw.Draw(im)
        d2.line((size * 0.26, size * 0.52, size * 0.43, size * 0.69, size * 0.75, size * 0.33),
                fill=(255, 255, 255, 255), width=int(size * 0.1), joint="curve")
    else:
        t_ = line_img(str(n), int(size * 0.56), 900, INK if state_ is None else (255, 255, 255))
        im.alpha_composite(t_, (int(size / 2 - t_.width / 2), int(size / 2 - t_.height / 2)))
    _CHIPS[key] = im
    return im


def badges_row(L, t, cy, size=118):
    sc, k, u = state(t)
    xs = [W / 2 - 170, W / 2, W / 2 + 170]
    for i in range(3):
        st = None
        if sc == "play" and i == k:
            st = "now"
        if t >= T_NO1 and i == 0:
            st = "no"
        if t >= T_NO2 and i == 1:
            st = "no"
        if t >= T_YES and i == 2:
            st = "yes"
        im = num_badge(i + 1, st, size)
        pop = 1.0
        for t0 in ([S[i]] if i < 3 else []) + [{0: T_NO1, 1: T_NO2, 2: T_YES}[i]]:
            if 0 <= t - t0 < 0.25:
                pop = 1 + 0.25 * math.sin(math.pi * (t - t0) / 0.25)
        if pop != 1.0:
            im = im.resize((int(size * pop), int(size * pop)), Image.LANCZOS)
        put(L, im, xs[i] - im.width / 2, cy - im.height / 2)


def who_label(L, xy, k, a, ymin=560):
    if xy is None or a <= 0:
        return
    im = fade_im(chip(P[k]["who"], P[k]["col"], 32), a)
    x = float(np.clip(xy[0] - im.width / 2, 30, W - 30 - im.width))
    y = float(np.clip(xy[1] - im.height - 20, ymin, 1500))
    put(L, im, x, y)


_NAVY = {}


def brand(L, t):
    if t < 1.8:
        return
    if "lock" not in _NAVY:
        import reel33_lines_neon as N
        im = N.brand_img("bladesandpucks_lockup_transparent.png", 280).img
        arr = np.asarray(im).astype(np.float32)
        wm = (arr[..., 0] > 200) & (arr[..., 1] > 200) & (arr[..., 2] > 200)
        arr[wm, 0:3] = NAVY
        _NAVY["lock"] = Image.fromarray(arr.astype(np.uint8), "RGBA")
    im = fade_im(_NAVY["lock"], 0.92 * smooth(1.8, 2.1, t))
    put(L, im, W / 2 - im.width / 2, 1862 - im.height / 2)


def texts(L, t):
    sc, k, u = state(t)
    # Hook: ganze Aussage ab Bild 0
    if t < S[1] - 0.1:
        a = 1 - smooth(S[1] - 0.3, S[1] - 0.1, t)
        for txt, cy, size, col in (("3 GOALS.", 300, 170, INK), ("ONLY 1 COUNTS.", 450, 118, RED)):
            im = fade_im(word(txt, size, col), a)
            put(L, im, W / 2 - im.width / 2, cy - im.height / 2)
    elif t < T_LOCK:
        im = word("ONLY 1 COUNTS.", 76, RED)
        put(L, im, W / 2 - im.width / 2, 260 - im.height / 2)
    if S[1] - 0.25 <= t < T_LOCK or VO_START["r1"] <= t < T_CTA - 0.1:
        badges_row(L, t, 400 if t < T_LOCK else 290, 112)
    # Which one?
    if T_LOCK <= t < VO_START["r1"]:
        slam(L, "WHICH ONE?", 150, INK, W / 2, 330, t, T_LOCK, VO_START["r1"], 1.7)
        for i in range(3):
            t0 = wt("lock", 2) + 0.1 * i - 0.1
            if t >= t0:
                im = num_badge(i + 1, None, 190)
                pop = 1 + 0.3 * math.sin(math.pi * c01((t - t0) / 0.2))
                im = im.resize((int(190 * pop), int(190 * pop)), Image.LANCZOS)
                put(L, im, W / 2 + (i - 1) * 260 - im.width / 2, 560 - im.height / 2)
        if t >= wt("lock", 2) + 0.35:
            reveal(L, line_img("COMMENT YOUR ANSWER", 48, 850, RED, track=6), W / 2, 740,
                   c01((t - wt("lock", 2) - 0.35) / 0.25), smooth(VO_START["r1"] - 0.1, VO_START["r1"], t))
    # Auflösung
    if VO_START["r1"] <= t < VO_START["r2"]:
        R15.reveal_halo(L, line_img("REPLAY 1", 36, 850, INK, track=10), W / 2, 378, c01((t - VO_START["r1"]) / 0.2),
               smooth(VO_START["r2"] - 0.1, VO_START["r2"], t))
        slam(L, "NO GOAL", 170, RED, W / 2, 512, t, T_NO1, VO_START["r2"], 1.8)
        if t >= wt("r1", 5):
            R15.reveal_halo(L, line_img("STICK ABOVE THE CROSSBAR", 44, 850, INK, track=4), W / 2, 610,
                   c01((t - wt("r1", 5)) / 0.2), smooth(VO_START["r2"] - 0.1, VO_START["r2"], t))
        if t >= T_NO1 + 0.25:
            R15.reveal_halo(L, line_img("NHL RULE 80.3", 34, 850, RED, track=8), W / 2, 672, c01((t - T_NO1 - 0.25) / 0.2),
                   smooth(VO_START["r2"] - 0.1, VO_START["r2"], t))
    if VO_START["r2"] <= t < VO_START["r3"]:
        R15.reveal_halo(L, line_img("REPLAY 2", 36, 850, INK, track=10), W / 2, 378, c01((t - VO_START["r2"]) / 0.2),
               smooth(VO_START["r3"] - 0.1, VO_START["r3"], t))
        slam(L, "NO GOAL", 170, RED, W / 2, 512, t, T_NO2, VO_START["r3"], 1.8)
        if t >= wt("r2", 1):
            R15.reveal_halo(L, line_img("BATTED IN BY HAND", 44, 850, INK, track=4), W / 2, 610,
                   c01((t - wt("r2", 1)) / 0.2), smooth(VO_START["r3"] - 0.1, VO_START["r3"], t))
        if t >= T_NO2 + 0.25:
            R15.reveal_halo(L, line_img("NHL RULE 67.6", 34, 850, RED, track=8), W / 2, 672, c01((t - T_NO2 - 0.25) / 0.2),
                   smooth(VO_START["r3"] - 0.1, VO_START["r3"], t))
    if VO_START["r3"] <= t < T_CTA - 0.1:
        t1 = T_CTA - 0.1
        slam(L, "IT COUNTS!", 150, GREEN, W / 2, 512, t, T_YES, t1, 1.8)
        if t >= wt("r3", 3):
            R15.reveal_halo(L, line_img("DEFENDER'S HIGH STICK", 44, 850, INK, track=4), W / 2, 610,
                   c01((t - wt("r3", 3)) / 0.2), smooth(t1 - 0.1, t1, t))
        if t >= wt("r3", 6):
            R15.reveal_halo(L, line_img("INTO HIS OWN NET = GOAL", 44, 850, GREEN, track=4), W / 2, 668,
                   c01((t - wt("r3", 6)) / 0.2), smooth(t1 - 0.1, t1, t))
        if t >= T_YES + 0.3:
            R15.reveal_halo(L, line_img("NHL RULE 80.3", 34, 850, GREEN, track=8), W / 2, 730, c01((t - T_YES - 0.3) / 0.2),
                   smooth(t1 - 0.1, t1, t))
    # CTA
    if t >= T_CTA - 0.1:
        slam(L, "DID YOU", 120, INK, W / 2, 300, t, T_CTA - 0.05)
        slam(L, "GET IT?", 170, ORANGE, W / 2, 450, t, wt("cta", 1))
        slam(L, "FOLLOW", 160, RED, W / 2, 1380, t, wt("cta", 4) - 0.05)
        if t >= wt("cta", 5):
            reveal(L, line_img("FOR MORE RULES", 44, 850, INK, track=8), W / 2, 1500, c01((t - wt("cta", 5)) / 0.25))


def flash_wipe(img, t):
    """Kurzer weißer Blitz beim Wechsel zwischen den Toren/Replays."""
    for c in (S[1], S[2], VO_START["r1"], VO_START["r2"], VO_START["r3"], T_CTA - 0.1):
        d = t - c
        if -0.05 <= d < 0.18:
            a = 0.75 * (1 - c01((d + 0.05) / 0.23))
            img = img * (1 - a) + a
    return img


def replay_fx(img, t):
    sc, k, u = state(t)
    if sc != "replay":
        return img
    gray = img.mean(axis=2, keepdims=True)
    return img * 0.82 + gray * 0.18


# ================================================================= Bild
def compose(t, fidx):
    v = view(t)
    sc, k, u = state(t)
    img = background(v)
    hi_s, hi_c = surface()
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    anchor = None
    rate = 1.0 if sc != "replay" else REPLAY[k][2]
    pxy = None
    if sc in ("play", "replay") and 0.05 <= u < 1.8:
        p = puck_at(k, u)
        B = P[k]["c"] + swing(k, u)
        _, dp = to_photo(p)
        _, db = to_photo(B)
        draw_obj = draw_glove if P[k]["kind"] == "glove" else draw_stick
        if db > dp:                                               # weiter hinten zuerst
            img, anchor, _ = draw_obj(img, k, u, v)
            img, pxy = draw_puck(img, k, u, v, rate)
        else:
            img, pxy = draw_puck(img, k, u, v, rate)
            img, anchor, _ = draw_obj(img, k, u, v)
    elif sc in ("play", "replay"):
        img, pxy = draw_puck(img, k, u, v, rate)
    # Lattenhöhe in den Replays 1 und 3
    if sc == "replay" and k in (0, 2):
        a = c01((t - VO_START[REPLAY[k][0]]) / 0.3)
        res = bar_line(hi_c, v, a, t)
        if res is not None:
            pts, lab = res
            x_ = W - 40 - lab.width
            y_ = float(np.interp(x_ + lab.width / 2, pts[:, 0], pts[:, 1])) if pts[0, 0] < pts[-1, 0] else float(pts[-1, 1])
            put(L, fade_im(lab, a), x_, y_ - lab.height - 16)
    # Kontakt-Ring + Tor-Ring
    if sc in ("play", "replay"):
        for uu, col in ((U_HIT, ORANGE), (U_IN, P[k]["col"] if sc == "play" else (GREEN if k == 2 else RED))):
            du = (u - uu) / rate
            if 0 <= du < 0.5:
                xy, ppi = to_screen(puck_at(k, uu), v)
                q = e_out(du / 0.5, 3)
                ring(hi_c, xy, ppi * 3 * (1.2 + 3.5 * q), col, 0.9 * (1 - q), 8 * (1 - q) + 2)
        if pxy is not None and u < U_IN + 0.1:
            us = np.linspace(max(0.0, u - 0.3 * rate), u, 14)
            pts = np.array([to_screen(puck_at(k, x), v)[0] for x in us])
            stroke_poly(hi_c, pts, (255, 255, 255), 0.35, 12)
            stroke_poly(hi_c, pts, ORANGE, 0.85, 5)
            brackets(hi_c, pxy, t, 34)
    img = over(img, *surf_rgba(hi_s))
    img = replay_fx(np.clip(img, 0, 1), t)
    img = flash_wipe(img, t)
    pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
    if sc in ("play", "replay") and anchor is not None:
        who_label(L, anchor, k, c01((u - 0.3) / 0.15) * (1 - c01((u - 1.55) / 0.15)), 560 if sc == "play" else 760)
    texts(L, t)
    brand(L, t)
    pil.alpha_composite(L)
    arr = np.asarray(pil.convert("RGB")).astype(np.float32) / 255
    kicks = [S[i] + U_HIT for i in range(3)] + [T_NO1, T_NO2, T_YES]
    lc = min([t - c for c in kicks if t >= c] + [t + 0.5])
    zp = 1 + 0.035 * math.exp(-lc * 12)
    if zp > 1.002:
        im2 = Image.fromarray((arr * 255).astype(np.uint8))
        w2, h2 = W / zp, H / zp
        im2 = im2.transform((W, H), Image.EXTENT, ((W - w2) / 2, (H - h2) / 2, (W + w2) / 2, (H + h2) / 2),
                            Image.BILINEAR)
        arr = np.asarray(im2).astype(np.float32) / 255
    arr = arr * R18.vignette()
    return (np.clip(arr, 0, 1) * 255).astype(np.uint8)


# ================================================================= Ton
SR = 44100


def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(38)
    mus = np.zeros((n, 2))
    sfx = np.zeros((n, 2))
    B = 60 / 126

    def tt(sec):
        return np.arange(int(sec * SR)) / SR

    def put_(buf, sig, at_, vol=1.0, pan=0.0):
        st = int(round(at_ * SR))
        if st >= n or st + len(sig) <= 0:
            return
        s0 = max(0, -st)
        st = max(st, 0)
        e = min(n, st + len(sig) - s0)
        gl, gr = math.cos((pan + 1) * math.pi / 4) * 1.41, math.sin((pan + 1) * math.pi / 4) * 1.41
        buf[st:e, 0] += sig[s0: s0 + e - st] * vol * gl
        buf[st:e, 1] += sig[s0: s0 + e - st] * vol * gr

    def lp(x, k):
        c = np.cumsum(np.concatenate([np.zeros(k), x]))
        return (c[k:] - c[:-k]) / k

    def hp(x, k):
        return x - lp(x, k)

    def noise(sec):
        return rng.standard_normal(int(sec * SR))

    def kick(vol=1.0):
        x = tt(0.45)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(42 + 160 * np.exp(-x * 34)) / SR) * np.exp(-x * 7) * 3.0) * vol

    def clap(vol=1.0):
        x = tt(0.3)
        return hp(noise(0.3), 2) * (np.exp(-x * 30) + 0.5 * np.exp(-np.abs(x - 0.012) * 300)) * 0.8 * vol

    def hat(vol=0.1):
        return hp(noise(0.04), 1) * np.exp(-tt(0.04) * 150) * vol

    def sub(freq, dur):
        x = tt(dur)
        f = freq * (1 + 0.6 * np.exp(-x * 9))
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * 2.6) * np.minimum(x / 0.004, 1) * np.exp(-x * 1.1) * 0.85

    def horn(dur=1.1, vol=0.5):
        x = tt(dur)
        sig = sum(np.sign(np.sin(2 * np.pi * f * x)) * w for f, w in ((116.5, 1.0), (146.8, 0.7), (174.6, 0.5)))
        env = np.minimum(x / 0.04, 1) * np.clip((dur - x) / 0.25, 0, 1)
        return lp(sig, 6) * env * vol

    def crowd(dur=2.5, vol=0.4):
        x = tt(dur)
        sig = lp(noise(dur), 12) - lp(noise(dur), 60) * 0.6
        return sig * np.sin(np.pi * np.clip(x / dur, 0, 1)) ** 0.8 * vol * 2.0

    def clack(vol=0.7):
        x = tt(0.18)
        return (hp(noise(0.18), 2) * np.exp(-x * 70) + np.sin(2 * np.pi * 1300 * x) * np.exp(-x * 60) * 0.6) * vol

    def thud(vol=0.7):
        x = tt(0.2)
        return (lp(noise(0.2), 8) * 2.5 * np.exp(-x * 40) + np.sin(2 * np.pi * 180 * x) * np.exp(-x * 30)) * vol

    def swish(vol=0.5):
        x = tt(0.5)
        return hp(lp(noise(0.5), 3), 12) * np.exp(-x * 7) * np.minimum(x / 0.01, 1) * vol

    def whoosh(dur=0.35, vol=0.4):
        x = tt(dur)
        return hp(lp(noise(dur), 6), 40) * np.sin(np.pi * x / dur) ** 2 * vol

    def pop(vol=0.4):
        x = tt(0.12)
        return np.sin(2 * np.pi * np.cumsum(500 + 900 * np.exp(-x * 40)) / SR) * np.exp(-x * 35) * vol

    def tick(vol=0.3):
        x = tt(0.05)
        return np.sin(2 * np.pi * 2200 * x) * np.exp(-x * 120) * vol

    def buzz(dur=0.5, vol=0.5):
        x = tt(dur)
        sig = np.sign(np.sin(2 * np.pi * 110 * x)) + 0.6 * np.sign(np.sin(2 * np.pi * 116 * x))
        return lp(sig, 4) * np.minimum(x / 0.01, 1) * np.clip((dur - x) / 0.05, 0, 1) * vol

    def ding(vol=0.5):
        x = tt(0.9)
        return (np.sin(2 * np.pi * 1318.5 * x) + 0.6 * np.sin(2 * np.pi * 1975.5 * x)) * np.exp(-x * 4) * vol

    roots = [55.0, 55.0, 65.41, 49.0]
    for k8 in range(int(DUR / (B / 2))):
        tb = k8 * B / 2
        b = k8 / 2
        pos = b % 4
        if tb > DUR - 0.4:
            continue
        calm = T_LOCK <= tb < VO_START["r1"]
        if calm:
            continue
        if pos in (0.0, 2.5) or pos == 1.5:
            put_(mus, kick(0.9), tb)
        if pos in (1.0, 3.0):
            put_(mus, clap(0.75), tb)
        put_(mus, hat(0.1 if k8 % 2 == 0 else 0.06), tb, pan=0.3)
        if pos == 0.0:
            put_(mus, sub(roots[int(b // 4) % 4], 2.6 * B), tb)
    for i in range(3):                                   # die drei Tore
        put_(sfx, pop(0.35), S[i] + 0.02)
        put_(sfx, whoosh(0.4, 0.35), S[i] + 0.4)
        put_(sfx, thud(0.8) if P[i]["kind"] == "glove" else clack(0.8), S[i] + U_HIT)
        put_(sfx, swish(0.6), S[i] + U_IN)
    for j in range(8):                                   # Uhr ticken bei "Which one?"
        put_(sfx, tick(0.35), T_LOCK + 0.1 + j * 0.2)
    for k, (key, u0, rate) in REPLAY.items():            # Replays in Zeitlupe
        t0 = VO_START[key]
        put_(sfx, whoosh(0.5, 0.4), t0 - 0.1)
        put_(sfx, (thud(0.6) if P[k]["kind"] == "glove" else clack(0.6)), t0 + (U_HIT - u0) / rate)
    put_(sfx, buzz(0.5, 0.45), T_NO1)
    put_(sfx, buzz(0.5, 0.45), T_NO2)
    put_(sfx, ding(0.5), T_YES)
    put_(sfx, horn(1.3, 0.45), T_YES + 0.05)
    put_(sfx, crowd(2.4, 0.45), T_YES + 0.05)
    put_(sfx, whoosh(0.5, 0.35), T_CTA - 0.1)
    voice = np.zeros(n)
    for k in VO_KEYS:
        tmp = os.path.join(HERE, f"_vo_{k}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "voice", f"reel38_{k}.wav"),
                        "-af", f"atempo={TEMPO}", "-ar", str(SR), "-ac", "1", tmp], check=True)
        with wave.open(tmp) as w:
            v = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        os.remove(tmp)
        st = int(VO_START[k] * SR)
        e = min(n, st + len(v))
        voice[st:e] += v[: e - st]
    voice /= np.max(np.abs(voice)) + 1e-9
    k = int(0.08 * SR)
    venv = np.convolve(np.abs(voice), np.ones(k) / k, mode="same")
    duck = 1 - 0.75 * np.clip(venv / 0.06, 0, 1)
    sduck = 1 - 0.45 * np.clip(venv / 0.06, 0, 1)
    mus /= np.max(np.abs(mus)) + 1e-9
    sfx /= np.max(np.abs(sfx)) + 1e-9
    mix = mus * 0.36 * duck[:, None] + sfx * 0.55 * sduck[:, None] + voice[:, None] * 1.0
    mix = np.tanh(mix * 1.05)
    mix *= np.clip((DUR - np.arange(n) / SR) / 0.3, 0, 1)[:, None]
    mix = mix / np.max(np.abs(mix)) * 0.95
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


def make_voice():
    import tts_kokoro
    tts_kokoro.synth(VO_LINES, os.path.join(HERE, "voice", "reel38"), speed=1.25)


def check_vo():
    with open(os.path.join(HERE, "voice", "reel38_timing.json")) as f:
        vo_dur = {k: v / TEMPO for k, v in json.load(f).items()}
    for i, k in enumerate(VO_KEYS):
        nxt = VO_START[VO_KEYS[i + 1]] if i + 1 < len(VO_KEYS) else DUR - 0.2
        if VO_START[k] + vo_dur[k] > nxt + 0.05:
            print(f"Warnung: Satz {k} zu lang ({VO_START[k] + vo_dur[k]:.2f} > {nxt:.2f})")


def remux():
    os.chdir(HERE)
    make_audio("audio_quiz.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "reel38_quiz.mp4", "-i", "audio_quiz.wav",
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-af",
                    "loudnorm=I=-14:TP=-1.0:LRA=9", "-ar", "44100", "-shortest", "-movflags", "+faststart",
                    "_tmp_qz.mp4"], check=True)
    os.replace("_tmp_qz.mp4", "reel38_quiz.mp4")


def preview(ts, out):
    ims = [Image.fromarray(compose(float(t), int(float(t) * FPS))) for t in ts]
    cw, ch = W // 3, H // 3
    cols = min(6, len(ims))
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * ch), (40, 40, 40))
    for i, im in enumerate(ims):
        sheet.paste(im.resize((cw, ch), Image.LANCZOS), ((i % cols) * cw, (i // cols) * ch))
    sheet.save(out, quality=88)


def main():
    os.chdir(HERE)
    check_vo()
    make_audio("audio_quiz.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_quiz.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
           "-ar", "44100", "-shortest", "-movflags", "+faststart", "reel38_quiz.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(0.0 + S[0] + 0.85, 9999)).save("reel38_thumbnail.jpg", quality=92)
    print("fertig: reel38_quiz.mp4")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "vo":
        make_voice()
    elif len(sys.argv) > 1 and sys.argv[1] == "audio":
        remux()
    elif len(sys.argv) > 1 and sys.argv[1] == "prev":
        preview(sys.argv[2].split(","), sys.argv[3])
    else:
        main()
