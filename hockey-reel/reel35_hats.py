"""Reel 35: "WHY IS THE ICE COVERED IN HATS?" – Hat-Trick-Erklärvideo im weißen Studio-Look von Reel 22 (~16 s).

Warum: Reel 22 (Trapez, weißer 3D-Studio-Look, "WHY IS THIS…?") ist der größte Hit (112k Views, 188 Follows).
Gleiches Muster: rätselhaftes Bild in Bild 0 (Eis voller Hüte), Frage als Hook, kurze Auflösung, Teaser + FOLLOW.
Löst das Versprechen aus Reel 34 ein ("Next: why do fans throw hats?").

Fakten (Recherche mit Quellen, 22.10.2026):
- Hat Trick = 3 Tore eines Spielers in einem Spiel (Merriam-Webster, NHL.com).
- Cricket 1858: H. H. Stephenson nahm 3 Wickets mit 3 Bällen hintereinander und bekam einen neuen Hut
  (NHL.com, Merriam-Webster). Das WORT ist erst ab 1865/1869 belegt -> Video sagt "it started in cricket".
- Toronto, 26.01.1946: Hutmacher Sammy Taft versprach Alex Kaleta (Chicago) einen Hut bei 3 Toren gegen Toronto,
  Kaleta traf 4-mal (Hockey Hall of Fame via NHL.com, The Hockey News, Spiel bei Hockey-Reference 6–5).
- Wer zuerst Hüte warf, ist unbekannt -> nicht behauptet.
- Teaser: Panthers "Rat Trick" (8.10.1995, Scott Mellanby) – nächstes Video.
Bilder: Bande, Glas, Tore (mesh3d), Eis + Puck (Raytracer), Hüte (hats3d.py). Keine Spieler, keine echten Logos.
Stimme: Kokoro "Michael", 1,08x. Aufruf: python3 reel35_hats.py vo | audio | prev 0.5,3.0 out.jpg | (Video)
"""
import json
import math
import os
import subprocess
import sys
import time
import wave

import numpy as np
from PIL import Image

import hats3d as HT
import mesh3d as M3
import puck3d as P3
import reel15_puck as R15
import reel18_dangle as R18
import reel26_overglass as R26
import reel28_emptynet as R28
from reel15_puck import (W, H, FPS, c01, smooth, sio, e_out, lerp, blend_up, line_img, reveal, put, projected,
                         px_per_in, surface, surf_rgba, over, GOAL_X)
from reel22_trapezoid import slam, puck_marker

HERE = R15.HERE
SPP = int(os.environ.get("SPP", "8"))
KSUB = int(os.environ.get("KSUB", "10"))
SHUTTER = 0.5 / FPS
INK, ORANGE = R15.INK, R15.ORANGE
RED = (225, 30, 40)
GREY = (110, 114, 126)
HALO = (255, 255, 255)
NAVY = (38, 35, 52)
TEMPO = 1.08

VO_LINES = [
    ("q", "Why is the ice covered in HATS?"),
    ("three", "Three goals by one player: a hat trick."),
    ("cricket", "It started in cricket: three wickets, three balls, one new hat."),
    ("toronto", "Then a Toronto hat shop promised a player a free hat for three goals. He scored four."),
    ("fans", "Now fans throw theirs."),
    ("cta", "Next: why do Florida fans throw rats? Follow."),
]
VO_KEYS = [k for k, _ in VO_LINES]
VO_START = {"q": 0.1, "three": 1.85, "cricket": 4.05, "toronto": 7.2, "fans": 12.1, "cta": 13.5}
DUR = 16.5
WT = {                                           # Wortanfänge (s nach Satzbeginn, nach 1,08x), faster-whisper
    "q": [0.0, 0.14, 0.26, 0.36, 0.54, 0.84, 1.02],
    "three": [0.0, 0.18, 0.38, 0.66, 0.82, 1.44, 1.48, 1.64],
    "cricket": [0.0, 0.06, 0.28, 0.48, 1.2, 1.3, 1.8, 1.94, 2.3, 2.52, 2.68],
    "toronto": [0.0, 0.12, 0.18, 0.36, 0.76, 0.96, 1.42, 1.56, 1.72, 1.92, 2.1, 2.32, 2.5, 2.66, 3.54, 3.56, 3.74],
    "fans": [0.0, 0.16, 0.38, 0.68],
    "cta": [0.0, 0.32, 0.4, 0.52, 0.78, 1.1, 1.38, 2.04],
}


def wt(key, i):
    return VO_START[key] + WT[key][i]


T_RW0, T_RW1 = 1.62, 2.12                       # Zurückspulen: Hüte fliegen zurück, Kran in die Draufsicht
T_UP1 = 2.3
T_G = [2.45, 2.98, 3.5]                          # die drei Tore
T_HT = wt("three", 6)                            # "hat trick"
T_DN0, T_DN1 = 3.85, 4.55                        # Draufsicht -> Nahaufnahme Held-Cap
T_CAP = wt("cricket", 8) - 0.35                  # Held-Cap fällt ("one new hat")
T_TOR = VO_START["toronto"]
T_FOUR = wt("toronto", 16)                       # "four"
T_FANS = VO_START["fans"] - 0.2                 # Hüte regnen wieder, Kamera zurück ins Hook-Bild
T_BK1 = T_FANS + 0.55
T_CTA = VO_START["cta"]

# ================================================================= Hüte
HERO_P = np.array([958.0, 0.0, 26.0])
N_HATS = 230
N_W1 = 170


def _make_hats():
    rng = np.random.default_rng(35)
    hats = []
    for i in range(N_HATS):
        kind = "cap" if rng.random() < 0.8 else "beanie"
        col = HT.COLORS[rng.integers(len(HT.COLORS))]
        col2 = "cap_white" if col != "cap_white" else "cap_red"
        # Landepunkt: dicht vor dem Tor, dünner nach außen
        r = 30 + 250 * rng.random() ** 0.75
        a = rng.uniform(-math.pi * 0.55, math.pi * 0.55)
        px, pz = 1020 - r * math.cos(a), r * math.sin(a) * 0.9
        if abs(pz) < 50 and px > 1025:                          # nicht ins Tor
            px -= 60
        side = rng.random()
        if side < 0.4:
            o = np.array([px + rng.uniform(-150, 150), rng.uniform(150, 230), -560.0])
        elif side < 0.8:
            o = np.array([px + rng.uniform(-150, 150), rng.uniform(150, 230), 560.0])
        else:
            o = np.array([1260.0, rng.uniform(170, 240), pz + rng.uniform(-150, 150)])
        flip = rng.random() < 0.18
        hats.append(dict(kind=kind, col=col, col2=col2, P=np.array([px, 0.0, pz]), O=o, flip=flip,
                         yaw=rng.uniform(0, 2 * math.pi), tf=rng.uniform(0.85, 1.25), arc=rng.uniform(30, 80),
                         axis=rng.normal(size=3), spin=rng.uniform(5, 11) * rng.choice([-1, 1]),
                         slide=rng.normal(size=2) * 9,
                         # Landezeiten: Welle 1 (Hook, zum Teil schon gelandet), Welle 2 (Fans)
                         tl1=-2.8 + 4.3 * rng.random() ** 0.8 if i < N_W1 else None,
                         tl2=T_FANS + 0.25 + 3.4 * rng.random() ** 1.6))
    return hats


HATS = _make_hats()
_LOCAL = {}


def local_mesh(h):
    key = (h["kind"], h["col"], h["col2"])
    if key not in _LOCAL:
        _LOCAL[key] = HT.hat_local(h["kind"], h["col"], h["col2"])
    return _LOCAL[key]


def rest_pose(h):
    R = HT.rot((0, 1, 0), h["yaw"])
    y = 0.0
    if h["flip"]:
        R = R @ HT.rot((1, 0, 0), math.pi)
        y = 4.0 if h["kind"] == "cap" else 6.6
    return R, y


def hat_pose(h, clock, tl):
    """-> (pos, R) oder None (noch auf der Tribüne)."""
    R0, y0 = rest_pose(h)
    P = h["P"] + np.array([0.0, y0, 0.0])
    t0 = tl - h["tf"]
    if clock < t0:
        return None
    if clock < tl:
        u = (clock - t0) / h["tf"]
        pos = h["O"] + (P - h["O"]) * u + np.array([0.0, h["arc"] * 4 * u * (1 - u), 0.0])
        R = HT.rot(h["axis"], h["spin"] * (1 - u) ** 1.3) @ R0
        return pos, R
    lt = clock - tl
    d = 1 - math.exp(-lt * 8)
    pos = P + np.array([h["slide"][0] * d, 3.5 * math.exp(-lt * 9) * abs(math.sin(lt * 26)), h["slide"][1] * d])
    wob = 0.22 * math.exp(-lt * 7) * math.sin(lt * 24)
    R = HT.rot((math.cos(h["yaw"]), 0, math.sin(h["yaw"])), wob) @ R0
    return pos, R


def hat_meshes(t):
    out = []
    if t < T_RW0:
        clock, wave_ = t, 1
    elif t < T_RW1:                                           # Zurückspulen
        clock, wave_ = T_RW0 - (T_RW0 + 3.0) * sio((t - T_RW0) / (T_RW1 - T_RW0)), 1
    elif t >= T_FANS - 1.3:
        clock, wave_ = t, 2
    else:
        clock, wave_ = None, 0
    if clock is not None:
        for h in HATS:
            tl = h["tl1"] if wave_ == 1 else h["tl2"]
            if tl is None:
                continue
            ps = hat_pose(h, clock, tl)
            if ps is None:
                continue
            out += HT.place_hat(local_mesh(h), ps[0], ps[1])
    hp = hero_pose(t)
    if hp is not None:
        out += HT.place_hat(HT.hat_local("cap", "cap_orange"), hp[0], hp[1])
    return out


def hero_pose(t):
    """Held-Cap (orange) in der Nahaufnahme: fällt bei "one new hat", liegt bis zu den Fans."""
    if not (T_CAP - 0.5 <= t < T_FANS + 0.6):
        return None
    R0 = HT.rot((0, 1, 0), -0.55)
    if t < T_CAP:
        u = c01((t - (T_CAP - 0.5)) / 0.5)
        return HERO_P + np.array([0.0, 60.0 * (1 - u * u), 0.0]), HT.rot((1, 0, 0.4), 2.2 * (1 - u) ** 1.4) @ R0
    lt = t - T_CAP
    wob = 0.2 * math.exp(-lt * 6) * math.sin(lt * 22)
    return HERO_P + np.array([0.0, 2.5 * math.exp(-lt * 9) * abs(math.sin(lt * 24)), 0.0]), HT.rot((0, 0, 1), wob) @ R0


# ================================================================= Puck: drei Tore
SHOTS = [(np.array([835.0, 0.0, -150.0]), np.array([1082.0, 1.5, 22.0])),
         (np.array([800.0, 0.0, 120.0]), np.array([1084.0, 1.5, -24.0])),
         (np.array([905.0, 0.0, -20.0]), np.array([1086.0, 1.5, 10.0]))]
SHOT_DUR = 0.26


def puck_state(t):
    for k, tg in enumerate(T_G):
        s, e = SHOTS[k]
        if tg - SHOT_DUR - 0.18 <= t < tg:
            u = c01((t - (tg - SHOT_DUR)) / SHOT_DUR)
            return s + (e - s) * (1 - (1 - u) ** 1.3) + np.array([0, 0.5, 0]), 1.0
        nxt = T_G[k + 1] - SHOT_DUR - 0.18 if k + 1 < 3 else T_DN0
        if tg <= t < nxt:
            return e + np.array([0, 0.5, 0]), 1.0
    return np.array([0.0, -50.0, 0.0]), 0.0


def shooter(t):
    """Position des Schützen-Markers (wandert von Schuss zu Schuss)."""
    pts = [SHOTS[0][0], SHOTS[1][0], SHOTS[2][0]]
    for k in range(2):
        a, b = T_G[k] + 0.05, T_G[k + 1] - SHOT_DUR - 0.18
        if t < a:
            return pts[k] - np.array([25.0, 0, 0])
        if t < b:
            return pts[k] + (pts[k + 1] - pts[k]) * sio((t - a) / (b - a)) - np.array([25.0, 0, 0])
    return pts[2] - np.array([25.0, 0, 0])


# ================================================================= Kamera
def hook_cam(t):
    p0, p1 = np.array([790.0, 44.0, 120.0]), np.array([822.0, 38.0, 100.0])
    return p0 + (p1 - p0) * e_out(c01(t / 3.0), 2), np.array([1010.0, 4.0, -8.0]), 54.0


def top_cam(t):
    return R28.top_cam(950.0 + 12 * c01((t - T_UP1) / 2.0), 1500.0, 30.0)


def hero_cam(t):
    """Blick vom Torraum aus Richtung Spielfeld: ruhiger, weißer Hintergrund hinter dem Text."""
    s = c01((t - T_DN1) / (T_FANS - T_DN1))
    a = lerp(-0.3, 0.3, sio(s))
    r = 64.0
    p = HERO_P + np.array([r * math.cos(a), 30.0 - 5 * s, r * math.sin(a)])
    return p, HERO_P + np.array([-14.0, 12.0, 0.0]), 44.0


def cam(t):
    if t < T_RW0:
        p, g, f = hook_cam(t)
    elif t < T_UP1:
        p, g, f = R28.blend_cam(hook_cam(T_RW0), top_cam(T_UP1), sio((t - T_RW0) / (T_UP1 - T_RW0)))
    elif t < T_DN0:
        p, g, f = top_cam(t)
    elif t < T_DN1:
        p, g, f = R28.blend_cam(top_cam(T_DN0), hero_cam(T_DN1), sio((t - T_DN0) / (T_DN1 - T_DN0)))
    elif t < T_FANS:
        p, g, f = hero_cam(t)
    elif t < T_BK1:
        p, g, f = R28.blend_cam(hero_cam(T_FANS), hook_cam(3.0), sio((t - T_FANS) / (T_BK1 - T_FANS)))
    else:
        u = c01((t - T_BK1) / (DUR - T_BK1))
        p, g, f = hook_cam(3.0 - 2.6 * sio(u))                 # zurück ins Anfangsbild (Loop)
    d = (p - g) / np.linalg.norm(p - g)
    el = math.degrees(math.asin(max(-1.0, min(1.0, d[1]))))
    return p, g, blend_up(min(el, 89.9)), f


def cam_row_at(t):
    pos, tgt, up, fov = cam(t)
    r, u, f = P3.look_at(pos, tgt, up)
    return P3.cam_row(pos, r, u, f, fov), float(np.linalg.norm(tgt - pos))


def render3d(t, fidx):
    cams, lens, pk = np.zeros((KSUB, 13)), np.zeros((KSUB, 2)), np.zeros((KSUB, 7))
    for j in range(KSUB):
        tk = min(max(t + ((j + 0.5) / KSUB - 0.5) * SHUTTER, 0.0), DUR - 1e-4)
        row, focus = cam_row_at(tk)
        cams[j], lens[j] = row, (0.0, focus)
        p, vis = puck_state(tk)
        pk[j] = (p[0], p[1], p[2], tk * 9.0, vis, 0.0, tk)
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, SPP, fidx + 35, cams, lens, pk, R15.logo_tex(), base, puck, cov)
    return P3.tonemap(base), P3.tonemap(puck), cov


# ================================================================= Overlays
def fade_im(im, a):
    if a >= 1:
        return im
    im = im.copy()
    im.putalpha(im.getchannel("A").point(lambda v: int(v * max(a, 0.0))))
    return im


def word(txt, size, col):
    im = R18.word_img(txt, size, col, HALO)
    if im.width > 1040:
        im = im.resize((1040, int(im.height * 1040 / im.width)), Image.LANCZOS)
    return im


_CAPICON = {}


def cap_icon(filled, size=96):
    """Kleines Cap-Symbol für den Tor-Zähler."""
    key = (filled, size)
    if key not in _CAPICON:
        from PIL import ImageDraw
        s = 4
        im = Image.new("RGBA", (size * s, int(size * 0.8) * s), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        col = ORANGE + (255,) if filled else (255, 255, 255, 235)
        w = 7 * s
        d.chord((10 * s, 8 * s, int(size * 0.72) * s, int(size * 1.1) * s), 180, 360, fill=col, outline=INK + (255,),
                width=w)
        y = int(size * 0.59) * s
        d.rounded_rectangle((int(size * 0.5) * s, y - 4 * s, (size - 4) * s, y + 9 * s), 6 * s, fill=col,
                            outline=INK + (255,), width=w)
        d.line((10 * s, y + 2 * s, int(size * 0.72) * s, y + 2 * s), fill=INK + (255,), width=w)
        _CAPICON[key] = im.resize((size, int(size * 0.8)), Image.LANCZOS)
    return _CAPICON[key]


def goal_counter(L, t):
    if not (T_UP1 - 0.3 <= t < T_DN0 + 0.1):
        return
    a = smooth(T_UP1 - 0.3, T_UP1, t) * (1 - smooth(T_DN0 - 0.15, T_DN0 + 0.1, t))
    for k in range(3):
        on = t >= T_G[k]
        im = cap_icon(on)
        sc = 1 + 0.35 * math.exp(-(t - T_G[k]) * 9) if on else 1.0
        if sc != 1:
            im = im.resize((int(im.width * sc), int(im.height * sc)), Image.BILINEAR)
        cx = W / 2 + (k - 1) * 150
        put(L, fade_im(im, a), cx - im.width / 2, 1560 - im.height / 2)


def four_counter(L, t):
    t3 = wt("toronto", 12) - 0.05
    if not (t3 <= t < T_FANS):
        return
    a = smooth(t3, t3 + 0.15, t) * (1 - smooth(T_FANS - 0.2, T_FANS, t))
    n = 4 if t >= T_FOUR else 3
    for k in range(n):
        tk = T_FOUR + 0.02 + 0.08 * k
        on = t >= tk
        im = cap_icon(on, 110)
        sc = (1 + 0.4 * math.exp(-(t - tk) * 9)) if on else 1.0
        if k == 3:
            sc *= e_out(c01((t - tk) / 0.15), 3)
        if sc <= 0.01:
            continue
        if sc != 1:
            im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.BILINEAR)
        cx = W / 2 + (k - (n - 1) / 2) * 165
        put(L, fade_im(im, a), cx - im.width / 2, 1010 - im.height / 2)


def brand(L, t):
    if t < T_RW0:
        return
    import reel33_lines_neon as N
    im = N.brand_img("bladesandpucks_lockup_transparent.png", 300).img
    key = "navy"
    if key not in _CAPICON:                                   # weiße Schrift -> Navy für den hellen Look
        arr = np.asarray(im).astype(np.float32)
        wmask = (arr[..., 0] > 200) & (arr[..., 1] > 200) & (arr[..., 2] > 200)
        arr[wmask, 0:3] = NAVY
        _CAPICON[key] = Image.fromarray(arr.astype(np.uint8), "RGBA")
    a = 0.92 * smooth(T_RW0, T_RW0 + 0.3, t)
    im = fade_im(_CAPICON[key], a)
    put(L, im, W / 2 - im.width / 2, 175 - im.height / 2)


def texts(L, t):
    # Hook: ganze Frage ab Bild 0
    if t < T_RW0 + 0.1:
        k = 1 - smooth(T_RW0 - 0.1, T_RW0 + 0.1, t)
        for txt, cy, size, col in (("WHY IS THE ICE", 330, 118, INK), ("COVERED IN", 465, 118, INK),
                                   ("HATS?", 640, 210, ORANGE)):
            im = fade_im(word(txt, size, col), k)
            put(L, im, W / 2 - im.width / 2, cy - im.height / 2)
    # 3 Tore -> Hat Trick
    if wt("three", 0) - 0.05 <= t < T_HT:
        a = smooth(wt("three", 0) - 0.05, wt("three", 0) + 0.15, t) * (1 - smooth(T_HT - 0.1, T_HT, t))
        reveal(L, line_img("3 GOALS · 1 PLAYER · 1 GAME", 46, 850, INK, track=6), W / 2, 330, a)
    slam(L, "HAT TRICK", 170, ORANGE, W / 2, 330, t, T_HT - 0.05, T_DN0 + 0.1)
    # Cricket 1858
    tc = VO_START["cricket"]
    slam(L, "1858", 190, INK, W / 2, 360, t, tc - 0.05, T_TOR - 0.05)
    slam(L, "CRICKET", 110, ORANGE, W / 2, 510, t, wt("cricket", 3) - 0.05, T_TOR - 0.05)
    for i, (txt, ti) in enumerate((("3 WICKETS", 4), ("3 BALLS", 6), ("1 NEW HAT", 8))):
        t0 = wt("cricket", ti) - 0.05
        if t0 <= t < T_TOR - 0.05:
            col = ORANGE if i == 2 else INK
            reveal(L, line_img(txt, 74, 900, col, track=4), W / 2, 760 + 105 * i, c01((t - t0) / 0.2),
                   smooth(T_TOR - 0.25, T_TOR - 0.05, t))
    # Toronto 1946
    slam(L, "TORONTO, 1946", 100, INK, W / 2, 350, t, T_TOR - 0.05, T_FANS)
    if wt("toronto", 3) - 0.05 <= t < T_FANS:
        reveal(L, line_img("HAT SHOP OWNER SAMMY TAFT", 38, 800, (70, 74, 88), track=6), W / 2, 450,
               c01((t - wt("toronto", 3) + 0.05) / 0.25), smooth(T_FANS - 0.2, T_FANS, t))
    slam(L, "FREE HAT", 130, ORANGE, W / 2, 700, t, wt("toronto", 9) - 0.05, wt("toronto", 14) - 0.1)
    slam(L, "FOR 3 GOALS", 100, INK, W / 2, 830, t, wt("toronto", 12) - 0.05, wt("toronto", 14) - 0.1)
    slam(L, "HE SCORED 4.", 130, RED, W / 2, 740, t, T_FOUR - 0.05, T_FANS)
    if T_FOUR + 0.25 <= t < T_FANS:
        reveal(L, line_img("ALEX KALETA · CHICAGO · JAN 26, 1946", 34, 800, (70, 74, 88), track=6), W / 2, 850,
               c01((t - T_FOUR - 0.25) / 0.25), smooth(T_FANS - 0.2, T_FANS, t))
    # Fans
    slam(L, "NOW FANS", 130, INK, W / 2, 360, t, VO_START["fans"] - 0.05, T_CTA - 0.05)
    slam(L, "THROW THEIRS.", 120, ORANGE, W / 2, 500, t, wt("fans", 2) - 0.05, T_CTA - 0.05)
    # CTA
    if t >= T_CTA - 0.05:
        slam(L, "NEXT:", 80, ORANGE, W / 2, 320, t, T_CTA - 0.05)
        slam(L, "WHY DO FLORIDA FANS", 84, INK, W / 2, 430, t, wt("cta", 1) - 0.05)
        slam(L, "THROW RATS?", 140, INK, W / 2, 560, t, wt("cta", 5) - 0.05)
        slam(L, "FOLLOW", 170, RED, W / 2, 1420, t, wt("cta", 7) - 0.05)
        if t >= wt("cta", 7) + 0.25:
            reveal(L, line_img("SO YOU DON'T MISS IT", 40, 850, INK, track=6), W / 2, 1540,
                   c01((t - wt("cta", 7) - 0.25) / 0.25))


def rewind_fx(img, t):
    """VHS-artiges Zurückspulen: Streifen + leichter Farbversatz."""
    if not (T_RW0 <= t < T_RW1):
        return img
    k = math.sin(math.pi * (t - T_RW0) / (T_RW1 - T_RW0))
    out = img.copy()
    sh = int(10 * k)
    if sh:
        out[..., 0] = np.roll(img[..., 0], sh, axis=1)
        out[..., 2] = np.roll(img[..., 2], -sh, axis=1)
    rng = np.random.default_rng(int(t * 1000))
    for _ in range(4):
        y, hb = int(rng.integers(0, H - 40)), int(rng.integers(6, 30))
        out[y:y + hb] = np.roll(out[y:y + hb], int(40 * k), axis=1)
    return out * (1 - 0.08 * k) + 0.08 * k


def rewind_icon(L, t):
    if not (T_RW0 <= t < T_RW1):
        return
    a = math.sin(math.pi * (t - T_RW0) / (T_RW1 - T_RW0))
    im = fade_im(line_img("<<  REWIND", 64, 900, INK, track=6), a)
    put(L, im, W / 2 - im.width / 2, 960 - im.height / 2)


# ================================================================= Bild
def compose(t, fidx):
    base, puck, cov = render3d(t, fidx)
    row, _ = cam_row_at(t)
    campos = cam(t)[0]
    p, vis = puck_state(t)
    lo_s, lo_c = surface()
    hi_s, hi_c = surface()
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    R28.draw_net_lines(lo_c, row)
    R28.glass_edges(lo_c, row)
    img = over(base, *surf_rgba(lo_s))
    meshes = R28.BOARDS + R28.FRAMES + hat_meshes(t)
    m_rgb, m_a, shadow, plane_a = M3.render(meshes, row, W, H, campos, extra_planes=[(R28.GLASS_ALL, 1.0)],
                                            shadow_light=(0.12, 1.0, -0.18))
    img = img * (1 - 0.32 * shadow[..., None])
    pa = cov[..., None]
    img = img * (1 - pa) + puck * pa
    img = img * (1 - m_a[..., None]) + m_rgb
    k = (0.30 * plane_a)[..., None]
    img = img * (1 - k) + np.array([0.70, 0.82, 0.94], np.float32) * k
    img = img + (R26.glass_streaks() * plane_a * 0.10)[..., None]

    # Draufsicht: Schütze, Schusslinien, Tor-Ringe
    ta = smooth(T_UP1 - 0.25, T_UP1, t) * (1 - smooth(T_DN0 - 0.1, T_DN0 + 0.15, t))
    if ta > 0:
        c_r = R28.disc(hi_c, row, shooter(t), ORANGE, ta, r_px=(30, 60), r_in=26.0)
        for k_, tg in enumerate(T_G):
            s, e = SHOTS[k_]
            if tg - SHOT_DUR - 0.05 <= t < tg + 0.45:
                u1 = c01((t - (tg - SHOT_DUR)) / SHOT_DUR)
                pts = [s + (e - s) * (1 - (1 - u) ** 1.3) + np.array([0, 0.3, 0]) for u in np.linspace(0, u1, 24)]
                R28.path_line(hi_c, row, pts, ORANGE, ta * (1 - smooth(tg + 0.15, tg + 0.45, t)), 6)
            gc, z = projected(row, np.array([GOAL_X + 20.0, 0.5, 0.0]))
            if z > 0:
                R28.pulse_ring(hi_c, (gc, 50.0), ORANGE, t, tg, 0.6)
        if vis > 0 and t < T_DN0:
            puck_marker(hi_c, row, p, t)
        R28.letter(L, c_r, "1", INK, ta, 0.8)
    img = over(img, *surf_rgba(hi_s))
    for t0 in T_G + [T_HT, T_CAP, T_FOUR]:
        if t0 <= t < t0 + 0.2:
            a = 0.12 * (1 - (t - t0) / 0.2)
            img = img * (1 - a) + a
    img = rewind_fx(np.clip(img, 0, 1), t)
    pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
    goal_counter(L, t)
    four_counter(L, t)
    texts(L, t)
    rewind_icon(L, t)
    brand(L, t)
    pil.alpha_composite(L)
    arr = np.asarray(pil.convert("RGB")).astype(np.float32) / 255
    lc = min([t - c for c in T_G + [T_HT, T_FOUR] if t >= c] + [t + 0.5])
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
    rng = np.random.default_rng(35)
    mus = np.zeros((n, 2))
    sfx = np.zeros((n, 2))
    B = 60 / 124

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

    def horn(dur=1.1, vol=0.5):                                  # Tor-Horn
        x = tt(dur)
        sig = sum(np.sign(np.sin(2 * np.pi * f * x)) * w for f, w in ((116.5, 1.0), (146.8, 0.7), (174.6, 0.5)))
        env = np.minimum(x / 0.04, 1) * np.clip((dur - x) / 0.25, 0, 1)
        return lp(sig, 6) * env * vol

    def crowd(dur=2.5, vol=0.4):
        x = tt(dur)
        sig = lp(noise(dur), 12) - lp(noise(dur), 60) * 0.6
        return sig * np.sin(np.pi * np.clip(x / dur, 0, 1)) ** 0.8 * vol * 2.0

    def thud(vol=0.3):
        x = tt(0.12)
        return (lp(noise(0.12), 8) * 1.5 + np.sin(2 * np.pi * 120 * x)) * np.exp(-x * 40) * vol

    def puck_hit(vol=0.7):
        x = tt(0.2)
        return (hp(noise(0.2), 2) * np.exp(-x * 60) + np.sin(2 * np.pi * 900 * x) * np.exp(-x * 50) * 0.5) * vol

    def whoosh(dur=0.4, vol=0.4):
        x = tt(dur)
        return hp(lp(noise(dur), 6), 40) * np.sin(np.pi * x / dur) ** 2 * vol

    def rewind(dur=0.5, vol=0.35):
        x = tt(dur)
        f = 300 + 2200 * (x / dur) ** 2
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * x / dur) * vol + hp(noise(dur), 3) * 0.1 * vol

    def pop(vol=0.4, f=900):
        x = tt(0.09)
        return np.sin(2 * np.pi * np.cumsum(f * (1 + 1.5 * np.exp(-x * 60))) / SR) * np.exp(-x * 45) * vol

    roots = [55.0, 55.0, 65.41, 49.0]
    for k8 in range(int(DUR / (B / 2))):
        tb = k8 * B / 2
        b = k8 / 2
        pos = b % 4
        if tb > DUR - 0.4 or T_RW0 <= tb < T_RW1:
            continue
        hook = tb < T_RW0
        if pos in (0.0, 2.5) or (pos == 1.5 and not hook):
            put_(mus, kick(0.75 if hook else 1.0), tb)
        if pos in (1.0, 3.0) and not hook:
            put_(mus, clap(0.8), tb)
        if not hook:
            put_(mus, hat(0.1 if k8 % 2 == 0 else 0.06), tb, pan=0.3)
        if pos == 0.0:
            put_(mus, sub(roots[int(b // 4) % 4], 2.6 * B), tb)
    # Hüte landen (Welle 1 + 2): leise Plops
    for h in HATS:
        for tl in (h["tl1"], h["tl2"]):
            if tl is not None and 0 <= tl < DUR and not (T_RW0 <= tl < T_FANS - 1.3):
                put_(sfx, thud(0.09), tl, pan=float(np.clip(h["P"][2] / 300, -0.8, 0.8)))
    put_(sfx, crowd(1.8, 0.35), 0.0)
    put_(sfx, rewind(T_RW1 - T_RW0, 0.4), T_RW0)
    for tg in T_G:
        put_(sfx, puck_hit(0.6), tg - SHOT_DUR)
        put_(sfx, horn(0.55, 0.32), tg)
    put_(sfx, horn(1.3, 0.45), T_HT)
    put_(sfx, crowd(2.0, 0.4), T_HT)
    put_(sfx, whoosh(0.5, 0.35), T_DN0)
    put_(sfx, thud(0.35), T_CAP)
    put_(sfx, whoosh(0.4, 0.3), T_TOR - 0.15)
    for k in range(4):
        put_(sfx, pop(0.35, 700 + 120 * k), T_FOUR + 0.02 + 0.08 * k)
    put_(sfx, whoosh(0.5, 0.35), T_FANS)
    put_(sfx, crowd(4.6, 0.55), T_FANS + 0.1)
    voice = np.zeros(n)
    for k in VO_KEYS:
        tmp = os.path.join(HERE, f"_vo_{k}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "voice", f"reel35_{k}.wav"),
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
    sduck = 1 - 0.6 * np.clip(venv / 0.06, 0, 1)
    mus /= np.max(np.abs(mus)) + 1e-9
    sfx /= np.max(np.abs(sfx)) + 1e-9
    mix = mus * 0.36 * duck[:, None] + sfx * 0.5 * sduck[:, None] + voice[:, None] * 1.0
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
    tts_kokoro.synth(VO_LINES, os.path.join(HERE, "voice", "reel35"), speed=1.25)


def check_vo():
    with open(os.path.join(HERE, "voice", "reel35_timing.json")) as f:
        vo_dur = {k: v / TEMPO for k, v in json.load(f).items()}
    for i, k in enumerate(VO_KEYS):
        nxt = VO_START[VO_KEYS[i + 1]] if i + 1 < len(VO_KEYS) else DUR - 0.2
        if VO_START[k] + vo_dur[k] > nxt + 0.3:
            print(f"Warnung: Satz {k} zu lang ({VO_START[k] + vo_dur[k]:.2f} > {nxt:.2f})")


def remux():
    os.chdir(HERE)
    make_audio("audio_hats.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "reel35_hats.mp4", "-i", "audio_hats.wav", "-map",
                    "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-af",
                    "loudnorm=I=-14:TP=-1.0:LRA=9", "-ar", "44100", "-shortest", "-movflags", "+faststart",
                    "_tmp_hats.mp4"], check=True)
    os.replace("_tmp_hats.mp4", "reel35_hats.mp4")


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
    make_audio("audio_hats.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_hats.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
           "-ar", "44100", "-shortest", "-movflags", "+faststart", "reel35_hats.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(0.9, 9999)).save("reel35_thumbnail.jpg", quality=92)
    print("fertig: reel35_hats.mp4")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "vo":
        make_voice()
    elif len(sys.argv) > 1 and sys.argv[1] == "audio":
        remux()
    elif len(sys.argv) > 1 and sys.argv[1] == "prev":
        preview(sys.argv[2].split(","), sys.argv[3])
    else:
        main()
