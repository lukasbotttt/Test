"""Reel 39: "QUIZ #2 – 3 PUCKS. ONLY 1 IS A GOAL." – Torlinien-Quiz mit echtem Tor-Foto (2,5D, ~15 s).

Fortsetzung von Reel 38 (Quiz-Format kam gut an). Drei Pucks rutschen nacheinander an die Torlinie, "Which one?",
Auflösung mit Nahaufnahme (Überlappung rot / Lücke grün) und Draufsicht-Grafik, FOLLOW für Teil 3.
Fakten (NHL Official Rules 2026-27): Rule 78.4 – ein Tor zählt nur, wenn der Puck ENTIRELY über die rote Linie
zwischen den Pfosten ist. Rule 1.5 – Torlinie 2 Zoll (5 cm) breit. Allgemeine Regel, keine Teams/Vereine.
Bild: Tor-Foto + kalibrierte Kamera aus Reel 38; Torlinie und Torraum werden perspektivisch korrekt ins Eis gemalt,
Pucks als 3D-Zylinder im Foto-Perspektivmodell gezeichnet. Keine Spielerkörper.
Bildnachweis: Tor-Foto Santeri Viinamäki, CC BY-SA 4.0 (Wikimedia Commons).
Stimme: Kokoro "Michael", 1,08x. Aufruf: python3 reel39_goalline.py vo | audio | prev 0.5,3.0 out.jpg | (Video)
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
import reel38_quiz as Q
from reel15_puck import W, H, FPS, c01, smooth, sio, e_out, line_img, reveal, put, stroke_poly, surface, surf_rgba, over
from reel22_trapezoid import slam

HERE = R15.HERE
INK, ORANGE = R15.INK, R15.ORANGE
RED = (225, 30, 40)
GREEN = (30, 160, 80)
TEMPO = 1.08

VO_LINES = [
    ("q", "Three pucks. Only ONE is a goal."),
    ("lock", "Which one? Lock it in."),
    ("r1", "One: half on the line. Nope."),
    ("r3", "Three: sooo close. Still touching. No goal."),
    ("r2", "Two counts! The whole puck is over the line."),
    ("cta", "Did you get it? Follow for part three."),
]
VO_KEYS = [k for k, _ in VO_LINES]
VO_START = {"q": 0.1, "lock": 4.75, "r1": 6.35, "r3": 8.4, "r2": 11.0, "cta": 13.45}
DUR = 15.75
WT = {                                           # Wortanfänge (s nach Satzbeginn, nach 1,08x), faster-whisper small.en
    "q": [0.0, 0.24, 0.74, 0.88, 1.14, 1.24, 1.36],
    "lock": [0.0, 0.2, 0.46, 0.78, 0.94],
    "r1": [0.0, 0.22, 0.42, 0.58, 0.66, 1.08],
    "r3": [0.0, 0.24, 0.56, 1.08, 1.16, 1.68, 1.82],
    "r2": [0.0, 0.14, 0.78, 0.86, 1.06, 1.26, 1.4, 1.56, 1.66],
    "cta": [0.0, 0.12, 0.24, 0.4, 0.7, 0.94, 1.18, 1.36],
}


def wt(key, i):
    return VO_START[key] + WT[key][i]


PLAY_LEN = 1.35
S = [-0.3, 1.35, 2.7]                            # Puck k rutscht an die Linie (Puck 1 schon ab Bild 0 in Bewegung)
T_BACK = S[2] + PLAY_LEN                         # Rückzoom: alle drei sichtbar
T_LOCK = VO_START["lock"] - 0.05
REVEAL = [("r1", 0), ("r3", 2), ("r2", 1)]       # Reihenfolge der Auflösung
T_NO1 = wt("r1", 5)
T_NO3 = wt("r3", 5)
T_YES = wt("r2", 1)
T_CTA = VO_START["cta"]

# ================================================================= Pucks (Zoll; Torlinie x = -1..+1, Tor bei x > 0)
LINE_HALF = 1.0                                  # Linie 2 Zoll breit, mittig unter den Pfosten
PR, PH_ = 1.5, 1.0                               # Puck: Radius, Höhe
PUCKS = [
    dict(x=0.2, z=-20.0, verdict="no"),          # halb auf der Linie
    dict(x=3.5, z=0.0, verdict="yes"),           # ganz drüber (1 Zoll Lücke)
    dict(x=2.0, z=20.0, verdict="no"),           # berührt noch die Linie (0,5 Zoll)
]
for _k, _p in enumerate(PUCKS):
    _p["start"] = np.array([-46.0, 0.0, _p["z"] - 18.0 + 10.0 * _k])


def puck_pos(k, t):
    """Weltposition (Mittelpunkt am Boden) des Pucks k zur Zeit t; None = noch nicht da."""
    if t < S[k]:
        return None
    p = PUCKS[k]
    end = np.array([p["x"], 0.0, p["z"]])
    u = c01((t - S[k]) / 1.05)
    s = 1 - (1 - u) ** 3                                       # rutscht aus
    return p["start"] + (end - p["start"]) * s


# ================================================================= Foto mit Torlinie + Torraum
def world_poly(pts):
    return np.array([Q.to_photo(np.array([x, 0.0, z]))[0] for x, z in pts], np.float32)


def painted_photo():
    if "lines" in Q._PHOTO:
        return
    img = Q.photo().astype(np.float32) / 255
    h, w = img.shape[:2]

    def mask(polys, blur=1.6):
        m = np.zeros((h, w), np.float32)
        for poly in polys:
            cv2.fillPoly(m, [np.round(poly * 4).astype(np.int32)], 1.0, lineType=cv2.LINE_AA, shift=2)
        return cv2.GaussianBlur(m, (0, 0), blur)

    lum = img.mean(axis=2, keepdims=True)
    # Torraum: 8 ft breit, 6 ft Radius (vereinfacht: gerade Seiten + Bogen), hellblau mit roter Linie
    arc = [(-math.sqrt(72 ** 2 - z ** 2), z) for z in np.linspace(-48, 48, 60)]
    crease = [(-LINE_HALF, -48.0)] + arc + [(-LINE_HALF, 48.0)]
    m_fill = mask([world_poly(crease)], 2.0)
    blue = np.array([0.55, 0.78, 0.95], np.float32)
    img = img * (1 - 0.32 * m_fill[..., None]) + lum * blue * 0.32 * m_fill[..., None] * 1.08
    outer = [(x * 1.0, z) for x, z in arc]
    inner = [(-math.sqrt(70 ** 2 - min(z * z, 70 ** 2 - 1)), z * 70 / 72) for z in np.linspace(-48, 48, 60)]
    ring_ = [(-LINE_HALF, -48.0)] + outer + [(-LINE_HALF, 48.0), (-LINE_HALF, 46.0)] + inner[::-1] + [(-LINE_HALF, -46.0)]
    m_ring = mask([world_poly(ring_)], 1.4)
    red = np.array([0.80, 0.10, 0.13], np.float32)
    img = img * (1 - 0.6 * m_ring[..., None]) + lum * red * 0.6 * m_ring[..., None] * 1.1
    # Torlinie (2 Zoll) quer übers Eis
    band = [(-LINE_HALF, -400.0), (LINE_HALF, -400.0), (LINE_HALF, 400.0), (-LINE_HALF, 400.0)]
    m_line = mask([world_poly(band)], 1.3)
    img = img * (1 - 0.85 * m_line[..., None]) + lum * red * 0.85 * m_line[..., None] * 1.1
    out = (np.clip(img, 0, 1) * 255).astype(np.uint8)
    Q._PHOTO["p"] = out
    Q._PHOTO.pop("half", None)
    Q._PHOTO["lines"] = True


# ================================================================= Puck als Zylinder in Fotoperspektive
def draw_puck(img, v, c, alpha=1.0, ground=None):
    """Puck (Mittelpunkt am Boden c) perspektivisch korrekt zeichnen, 3x überabgetastet."""
    ang = np.linspace(0, 2 * math.pi, 64, endpoint=False)
    bot = np.array([Q.to_screen(c + np.array([PR * math.cos(a), 0.0, PR * math.sin(a)]), v)[0] for a in ang])
    top = np.array([Q.to_screen(c + np.array([PR * math.cos(a), PH_, PR * math.sin(a)]), v)[0] for a in ang])
    allp = np.vstack([bot, top])
    x0, y0 = np.floor(allp.min(0)).astype(int) - 6
    x1, y1 = np.ceil(allp.max(0)).astype(int) + 6
    if x1 < 0 or y1 < 0 or x0 >= W or y0 >= H:
        return img
    ss = 3
    pw, ph = (x1 - x0) * ss, (y1 - y0) * ss
    col = np.zeros((ph, pw, 3), np.float32)
    al = np.zeros((ph, pw), np.float32)

    def P(pts):
        return np.round((pts - [x0, y0]) * ss * 4).astype(np.int32)

    hull = cv2.convexHull(P(allp).astype(np.float32)).astype(np.int32)
    cv2.fillPoly(al, [hull], 1.0, lineType=cv2.LINE_AA, shift=2)
    # Seite: dunkler Gummi mit leichtem Glanzband, Deckel etwas heller
    yy = (np.arange(ph, dtype=np.float32)[:, None] / ph)
    col[:] = (0.045 + 0.03 * np.exp(-((yy - 0.62) / 0.12) ** 2))[..., None] * np.ones(3, np.float32)
    lid = np.zeros((ph, pw), np.float32)
    cv2.fillPoly(lid, [P(top)], 1.0, lineType=cv2.LINE_AA, shift=2)
    xx = np.arange(pw, dtype=np.float32)[None, :] / pw
    lid_col = 0.075 + 0.05 * xx + 0.02 * (1 - yy)
    col = col * (1 - lid[..., None]) + lid_col[..., None] * lid[..., None]
    rim = np.zeros((ph, pw), np.float32)
    cv2.polylines(rim, [P(top)], True, 1.0, thickness=int(1.2 * ss), lineType=cv2.LINE_AA, shift=2)
    col = col + rim[..., None] * 0.22
    col = cv2.resize(col, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA)
    al = cv2.resize(al, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA) * alpha
    # Kontaktschatten
    g = c if ground is None else ground
    cxy, ppi = Q.to_screen(g, v)
    lift = math.exp(-(c[1] - g[1]) / 4.0)
    img = Q.soft_shadow(img, cxy + np.array([0, 0.25 * ppi]), 2.0 * ppi * (2 - lift), 0.6 * ppi * (2 - lift), 0.55 * alpha * lift)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    sub_c = col[ya - y0:yb - y0, xa - x0:xb - x0]
    sub_a = al[ya - y0:yb - y0, xa - x0:xb - x0, None]
    img[ya:yb, xa:xb] = img[ya:yb, xa:xb] * (1 - sub_a) + sub_c * sub_a
    return img


# ================================================================= Bildausschnitt
def puck_view(k, s=1.55, dy=0.0):
    ph, _ = Q.to_photo(np.array([PUCKS[k]["x"], 0.0, PUCKS[k]["z"]]))
    return (ph[0], ph[1] - 120 + dy, s)


def goal_view():
    ph, _ = Q.to_photo(np.array([0.0, 14.0, 4.0]))
    return (ph[0] - 40, ph[1] - 160, 0.98)


BASE = (1800.0, Q.PH_H / 2, Q.S_MIN)


def view(t):
    if t < S[1]:
        v = Q.lerp_v(BASE, puck_view(0), sio(c01((t - 0.05) / 1.0)))
    elif t < S[2]:
        v = Q.lerp_v(puck_view(0), puck_view(1), sio(c01((t - S[1]) / 0.6)))
    elif t < T_BACK:
        v = Q.lerp_v(puck_view(1), puck_view(2), sio(c01((t - S[2]) / 0.6)))
    elif t < VO_START["r1"]:
        v = Q.lerp_v(puck_view(2), goal_view(), sio(c01((t - T_BACK) / 0.7)))
    elif t < T_CTA - 0.1:
        for key, k in REVEAL[::-1]:
            if t >= VO_START[key]:
                t0 = VO_START[key]
                a = puck_view(k, 1.8, 120)
                v = (a[0], a[1], a[2] + 0.05 * (t - t0))
                break
    else:
        v = Q.lerp_v(goal_view(), BASE, sio(c01((t - T_CTA) / 1.6)))
    return Q.clamp_view(*v)


# ================================================================= Overlays
def badge_state(i, t):
    if t >= {0: T_NO1, 1: T_YES, 2: T_NO3}[i]:
        return "no" if PUCKS[i]["verdict"] == "no" else "yes"
    if S[i] <= t < S[i] + PLAY_LEN and t < T_BACK:
        return "now"
    return None


def badges_row(L, t, cy, size=104):
    xs = [W / 2 - 160, W / 2, W / 2 + 160]
    for i in range(3):
        st = badge_state(i, t)
        im = Q.num_badge(i + 1, st, size)
        pop = 1.0
        for t0 in (S[i], {0: T_NO1, 1: T_YES, 2: T_NO3}[i]):
            if 0 <= t - t0 < 0.25:
                pop = 1 + 0.25 * math.sin(math.pi * (t - t0) / 0.25)
        if pop != 1.0:
            im = im.resize((int(size * pop), int(size * pop)), Image.LANCZOS)
        put(L, im, xs[i] - im.width / 2, cy - im.height / 2)


def puck_tags(L, v, t, a):
    """Nummern über den Pucks."""
    if a <= 0:
        return
    for i in range(3):
        c = puck_pos(i, t)
        if c is None:
            continue
        xy, ppi = Q.to_screen(c + np.array([0.0, 7.0, 0.0]), v)
        st = badge_state(i, t) if t >= VO_START["r1"] else None
        im = Q.fade_im(Q.num_badge(i + 1, st, 74), a)
        put(L, im, xy[0] - im.width / 2, xy[1] - im.height / 2 - 18)
        # Stiel vom Badge zum Puck
        d = ImageDraw.Draw(L)
        top, _ = Q.to_screen(c + np.array([0.0, 1.3, 0.0]), v)
        d.line((xy[0], xy[1] + 18, top[0], top[1] - 4), fill=INK + (int(200 * a),), width=3)


def highlight(ctx, v, k, a, t):
    """Nahaufnahme-Auflösung: Linie umrandet, Überlappung rot bzw. Lücke grün."""
    if a <= 0:
        return
    p = PUCKS[k]
    zc = p["z"]
    band = np.array([Q.to_screen(np.array([x, 0.0, z]), v)[0]
                     for x, z in ((-LINE_HALF, zc - 9), (LINE_HALF, zc - 9), (LINE_HALF, zc + 9), (-LINE_HALF, zc + 9))])
    circ = np.array([Q.to_screen(np.array([p["x"] + PR * math.cos(q), 0.0, zc + PR * math.sin(q)]), v)[0]
                     for q in np.linspace(0, 2 * math.pi, 64)])
    # Hinterkante der Linie (x = +1): "die Linie endet hier"
    edge = np.array([Q.to_screen(np.array([LINE_HALF, 0.0, z]), v)[0] for z in np.linspace(zc - 14, zc + 14, 20)])
    ctx.set_dash([18, 10], -t * 40)
    stroke_poly(ctx, edge, (255, 255, 255), 0.95 * a, 5)
    ctx.set_dash([])
    if p["verdict"] == "no":
        ctx.save()
        ctx.move_to(*band[0])
        for q in band[1:]:
            ctx.line_to(*q)
        ctx.close_path()
        ctx.clip()
        ctx.move_to(*circ[0])
        for q in circ[1:]:
            ctx.line_to(*q)
        ctx.close_path()
        pulse = 0.55 + 0.25 * math.sin(t * 10)
        ctx.set_source_rgba(1.0, 0.15, 0.2, pulse * a)
        ctx.fill()
        ctx.restore()
    else:
        gap = np.array([Q.to_screen(np.array([x, 0.0, z]), v)[0]
                        for x, z in ((LINE_HALF, zc - 0.9), (p["x"] - PR + 0.05, zc - 0.9),
                                     (p["x"] - PR + 0.05, zc + 0.9), (LINE_HALF, zc + 0.9))])
        ctx.move_to(*gap[0])
        for q in gap[1:]:
            ctx.line_to(*q)
        ctx.close_path()
        ctx.set_source_rgba(0.2, 0.85, 0.4, (0.7 + 0.25 * math.sin(t * 10)) * a)
        ctx.fill()
    stroke_poly(ctx, np.vstack([circ, circ[:1]]), (255, 255, 255), 0.9 * a, 3)


_CARD = {}


def top_card(k):
    """Draufsicht: rote Linie, Puck, Tor-Seite rechts."""
    if k in _CARD:
        return _CARD[k]
    sc = 2
    w_, h_ = 600 * sc, 250 * sc
    im = Image.new("RGBA", (w_, h_), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w_ - 1, h_ - 1), 28 * sc, fill=(255, 255, 255, 245), outline=INK + (255,), width=4 * sc)
    ppi = 46 * sc
    cx = w_ / 2 - 40 * sc
    cy = h_ / 2 + 14 * sc
    d.rectangle((cx - ppi, 54 * sc, cx + ppi, h_ - 16 * sc), fill=(205, 30, 42, 255))
    p = PUCKS[k]
    px = cx + p["x"] * ppi
    d.ellipse((px - PR * ppi, cy - PR * ppi, px + PR * ppi, cy + PR * ppi), fill=(18, 18, 22, 235))
    if p["verdict"] == "yes":
        d.rectangle((cx + ppi, cy - 10 * sc, px - PR * ppi, cy + 10 * sc), fill=(40, 190, 90, 255))
    im = im.resize((600, 250), Image.LANCZOS)
    put(im, line_img("TOP VIEW", 22, 850, INK, track=6), 24, 18)
    put(im, line_img("NET  →", 22, 850, (120, 120, 130), track=4), 600 - 120, 18)
    _CARD[k] = im
    return im


def texts(L, t, v):
    # Hook
    if t < 1.25:
        a = 1 - smooth(1.05, 1.25, t)
        put(L, Q.fade_im(Q.chip("HOCKEY QUIZ #2", RED, 32), a), W / 2 - Q.chip("HOCKEY QUIZ #2", RED, 32).width / 2, 150)
        for txt, cy, size, col in (("3 PUCKS.", 320, 170, INK), ("ONLY 1 IS A GOAL.", 460, 100, RED)):
            im = Q.fade_im(Q.word(txt, size, col), a)
            put(L, im, W / 2 - im.width / 2, cy - im.height / 2)
    elif t < T_LOCK:
        im = Q.word("ONLY 1 IS A GOAL.", 70, RED)
        put(L, im, W / 2 - im.width / 2, 250 - im.height / 2)
    if 1.25 <= t < T_LOCK or VO_START["r1"] <= t < T_CTA - 0.1:
        badges_row(L, t, 380 if t < T_LOCK else 270)
    if T_LOCK <= t < VO_START["r1"]:
        slam(L, "WHICH ONE?", 150, INK, W / 2, 300, t, T_LOCK, VO_START["r1"], 1.7)
        if t >= wt("lock", 2):
            R15.reveal_halo(L, line_img("COMMENT 1, 2 OR 3", 48, 850, RED, track=6), W / 2, 440,
                            c01((t - wt("lock", 2)) / 0.25), smooth(VO_START["r1"] - 0.1, VO_START["r1"], t))
    # Auflösung
    info = {0: ("NOPE.", RED, "HALF ON THE LINE", T_NO1), 2: ("NO GOAL", RED, "SO CLOSE… STILL TOUCHING", T_NO3),
            1: ("GOAL!", GREEN, "ENTIRELY ACROSS THE LINE", T_YES)}
    for i, (key, k) in enumerate(REVEAL):
        t0 = VO_START[key]
        t1 = VO_START[REVEAL[i + 1][0]] if i + 1 < len(REVEAL) else T_CTA - 0.1
        if not (t0 <= t < t1):
            continue
        big, col, sub, ts = info[k]
        slam(L, big, 170 if k != 1 else 200, col, W / 2, 430, t, ts, t1, 1.8)
        if t >= t0 + 0.15:
            R15.reveal_halo(L, line_img(sub, 44, 850, INK, track=4), W / 2, 545, c01((t - t0 - 0.15) / 0.2),
                            smooth(t1 - 0.1, t1, t))
        if t >= ts + 0.25:
            R15.reveal_halo(L, line_img("NHL RULE 78.4", 32, 850, col, track=8), W / 2, 605, c01((t - ts - 0.25) / 0.2),
                            smooth(t1 - 0.1, t1, t))
        card = top_card(k)
        a = c01((t - t0 - 0.35) / 0.25) * (1 - smooth(t1 - 0.12, t1, t))
        if a > 0:
            y = 1420 + 30 * (1 - e_out(c01((t - t0 - 0.35) / 0.3), 3))
            put(L, Q.fade_im(card, a), W / 2 - card.width / 2, y - card.height / 2)
    # CTA
    if t >= T_CTA - 0.1:
        slam(L, "DID YOU", 120, INK, W / 2, 290, t, T_CTA - 0.05)
        slam(L, "GET IT?", 170, ORANGE, W / 2, 440, t, wt("cta", 1))
        slam(L, "FOLLOW", 160, RED, W / 2, 1300, t, wt("cta", 4) - 0.05)
        if t >= wt("cta", 5):
            R15.reveal_halo(L, line_img("FOR PART 3", 54, 850, INK, track=8), W / 2, 1420, c01((t - wt("cta", 5)) / 0.25))


def flash_wipe(img, t):
    for c in [VO_START[k] for k, _ in REVEAL] + [T_CTA - 0.1]:
        d = t - c
        if -0.05 <= d < 0.18:
            a = 0.7 * (1 - c01((d + 0.05) / 0.23))
            img = img * (1 - a) + a
    return img


# ================================================================= Comedy: Wackelaugen, Sprechblasen, Konfetti
def hop(i, t):
    """Freudensprünge von Puck 2 nach der Auflösung."""
    if PUCKS[i]["verdict"] != "yes" or not (T_YES <= t < T_YES + 1.35):
        return 0.0
    u = (t - T_YES) / 0.45
    return 4.5 * abs(math.sin(math.pi * u)) * (0.75 ** int(u))


def mood(i, t):
    if PUCKS[i]["verdict"] == "yes" and t >= T_YES:
        return "happy" if t < T_YES + 1.6 else "proud"
    if i == 0 and t >= T_NO1:
        return "sad"
    if i == 2 and t >= T_NO3:
        return "sad"
    if T_LOCK <= t < VO_START["r1"]:
        return {0: "nervous", 1: "neutral", 2: "proud"}[i]
    return "neutral"


def draw_eyes(ctx, v, i, c, t):
    xy, ppi = Q.to_screen(c + np.array([0.0, 0.62, 0.0]), v)
    re = max(4.0, 0.44 * ppi)
    m = mood(i, t)
    # Blickrichtung: beim Rutschen nach vorn, danach Nachwackeln
    look = np.array([0.0, 0.0])
    if S[i] <= t < S[i] + 1.05:
        a_, _ = Q.to_screen(puck_pos(i, t + 0.05), v)
        b_, _ = Q.to_screen(puck_pos(i, t), v)
        d = a_ - b_
        if np.linalg.norm(d) > 0.5:
            look = d / np.linalg.norm(d) * 0.55
    else:
        ts = t - (S[i] + 1.05)
        look = np.array([math.sin(ts * 22) * 0.5 * math.exp(-ts * 4), 0.15])
    if m == "nervous":
        look = np.array([0.6 * math.copysign(1, math.sin(t * 5.3)), 0.1])
    if m == "sad":
        look = np.array([0.0, 0.55])
    if m == "proud":
        look = np.array([0.25, -0.35])
    blink = (t * 1.0 + i * 0.37) % 2.6 < 0.09 and m in ("neutral", "nervous")
    for sgn in (-1, 1):
        ex, ey = xy[0] + sgn * 0.62 * ppi, xy[1]
        if m == "happy":
            ctx.set_source_rgba(1, 1, 1, 1)
            ctx.set_line_width(max(2.0, re * 0.32))
            ctx.arc(ex, ey + re * 0.35, re * 0.75, math.pi * 1.15, math.pi * 1.85)
            ctx.stroke()
            continue
        ctx.set_source_rgba(1, 1, 1, 1)
        ctx.arc(ex, ey, re, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgba(0.08, 0.08, 0.1, 1)
        ctx.set_line_width(max(1.2, re * 0.1))
        ctx.arc(ex, ey, re, 0, 2 * math.pi)
        ctx.stroke()
        if blink:
            ctx.set_source_rgba(0.06, 0.06, 0.07, 1)
            ctx.arc(ex, ey, re * 1.02, 0, 2 * math.pi)
            ctx.fill()
            continue
        ctx.arc(ex + look[0] * re * 0.5, ey + look[1] * re * 0.5, re * 0.5, 0, 2 * math.pi)
        ctx.fill()
        if m == "sad":                                            # Augenlid schräg (innen hoch)
            ctx.save()
            ctx.arc(ex, ey, re * 1.05, 0, 2 * math.pi)
            ctx.clip()
            ctx.set_source_rgba(0.06, 0.06, 0.07, 1)
            ctx.move_to(ex - re * 1.2, ey - re * (0.55 if sgn > 0 else 0.05))
            ctx.line_to(ex + re * 1.2, ey - re * (0.05 if sgn > 0 else 0.55))
            ctx.line_to(ex + re * 1.2, ey - re * 1.3)
            ctx.line_to(ex - re * 1.2, ey - re * 1.3)
            ctx.close_path()
            ctx.fill()
            ctx.restore()
        if m == "proud":                                          # halb geschlossen, lässig
            ctx.save()
            ctx.arc(ex, ey, re * 1.05, 0, 2 * math.pi)
            ctx.clip()
            ctx.set_source_rgba(0.06, 0.06, 0.07, 1)
            ctx.rectangle(ex - re * 1.2, ey - re * 1.3, re * 2.4, re * 0.95)
            ctx.fill()
            ctx.restore()
    # Träne bei Puck 3
    if i == 2 and t >= T_NO3 + 0.2:
        for j in range(3):
            q = ((t - T_NO3 - 0.2) * 1.1 + j / 3) % 1.0
            tx, ty = xy[0] + 0.62 * ppi + re * 0.5, xy[1] + re * 0.6 + q * 2.2 * ppi
            ctx.set_source_rgba(0.35, 0.65, 1.0, 0.9 * (1 - q))
            r_ = re * 0.32
            ctx.move_to(tx, ty - r_ * 1.8)
            ctx.curve_to(tx + r_, ty - r_ * 0.4, tx + r_, ty + r_, tx, ty + r_)
            ctx.curve_to(tx - r_, ty + r_, tx - r_, ty - r_ * 0.4, tx, ty - r_ * 1.8)
            ctx.fill()


_BUB = {}


def bubble_img(txt, size=32):
    key = (txt, size)
    if key in _BUB:
        return _BUB[key]
    t_ = line_img(txt, size, 850, INK, track=2)
    pw, ph = t_.width + 44, t_.height + 30
    im = Image.new("RGBA", (pw, ph + 26), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((2, 2, pw - 3, ph - 3), ph // 2, fill=(255, 255, 255, 250), outline=INK + (255,), width=4)
    cx = pw * 0.32
    d.polygon([(cx - 12, ph - 5), (cx + 12, ph - 5), (cx - 8, ph + 22)], fill=(255, 255, 255, 250))
    d.line([(cx - 12, ph - 4), (cx - 8, ph + 22), (cx + 12, ph - 4)], fill=INK + (255,), width=4)
    im.alpha_composite(t_, (22, 15))
    _BUB[key] = im
    return im


BUBBLES = [  # (Puck, Text, ab, bis, Höhe über dem Puck in Zoll, Zusatz-Pixel nach oben)
    (0, "AM I IN?", T_LOCK + 0.25, VO_START["r1"], 7.0, 70),
    (2, "I'M SO IN.", T_LOCK + 0.6, VO_START["r1"], 7.0, 70),
    (1, "...", T_LOCK + 0.95, VO_START["r1"], 7.0, 190),
    (0, "WAIT... WHAT?", T_NO1 + 0.25, VO_START["r3"] - 0.1, 3.5, 40),
    (2, "BUT I'M SO CLOSE!", wt("r3", 2), VO_START["r2"] - 0.1, 3.5, 40),
    (1, "TOLD YA.", T_YES + 0.7, T_CTA - 0.15, 3.5, 40),
]


def bubbles(L, v, t):
    for i, txt, t0, t1, hy, dy in BUBBLES:
        if not (t0 <= t < t1):
            continue
        c = puck_pos(i, t)
        if c is None:
            continue
        xy, _ = Q.to_screen(c + np.array([0.0, hy, 0.0]), v)
        im = bubble_img(txt)
        k = e_out(c01((t - t0) / 0.18), 3) * (1 + 0.12 * math.sin(math.pi * c01((t - t0) / 0.25)))
        a = 1 - smooth(t1 - 0.12, t1, t)
        if k < 0.99:
            im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
        x = float(np.clip(xy[0] - im.width * 0.32, 20, W - 20 - im.width))
        put(L, Q.fade_im(im, a), x, xy[1] - im.height - dy)


_CONF = {}


def confetti(ctx, v, t):
    if not (T_YES <= t < T_YES + 2.4):
        return
    if "p" not in _CONF:
        rng = np.random.default_rng(39)
        n = 110
        _CONF["p"] = dict(ang=rng.uniform(-2.6, -0.55, n), sp=rng.uniform(700, 1500, n), rot=rng.uniform(0, 6.3, n),
                          spin=rng.uniform(-12, 12, n), sz=rng.uniform(10, 20, n), col=rng.integers(0, 5, n),
                          dl=rng.uniform(0, 0.15, n))
    p = _CONF["p"]
    cols = [(0.93, 0.25, 0.2), (0.15, 0.7, 0.35), (0.98, 0.75, 0.1), (0.2, 0.5, 0.95), (0.95, 0.45, 0.1)]
    c = puck_pos(1, t)
    org, _ = Q.to_screen(c + np.array([0.0, 2.0, 0.0]), v)
    for j in range(len(p["ang"])):
        tt_ = t - T_YES - p["dl"][j]
        if tt_ < 0:
            continue
        x = org[0] + math.cos(p["ang"][j]) * p["sp"][j] * tt_
        y = org[1] + math.sin(p["ang"][j]) * p["sp"][j] * tt_ + 900 * tt_ * tt_
        a = 1 - c01((tt_ - 1.6) / 0.6)
        r = p["rot"][j] + p["spin"][j] * tt_
        sz = p["sz"][j]
        ctx.save()
        ctx.translate(x, y)
        ctx.rotate(r)
        cc = cols[p["col"][j]]
        ctx.set_source_rgba(cc[0], cc[1], cc[2], a)
        ctx.rectangle(-sz / 2, -sz * 0.3 * abs(math.cos(r * 1.7)) - 1, sz, sz * 0.6 * abs(math.cos(r * 1.7)) + 2)
        ctx.fill()
        ctx.restore()


# ================================================================= Bild
def compose(t, fidx):
    painted_photo()
    v = view(t)
    img = Q.background(v)
    hi_s, hi_c = surface()
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    order = sorted(range(3), key=lambda i: -Q.to_photo(np.array([PUCKS[i]["x"], 0, PUCKS[i]["z"]]))[1])
    for i in order:
        c = puck_pos(i, t)
        if c is not None:
            img = draw_puck(img, v, c + np.array([0.0, hop(i, t), 0.0]), ground=c)
    # Rutsch-Spur + Marker während des Anrutschens
    for i in range(3):
        if S[i] <= t < S[i] + 1.2:
            ts_ = np.linspace(max(S[i], t - 0.25), t, 10)
            pts = np.array([Q.to_screen(puck_pos(i, x) + np.array([0, 0.5, 0]), v)[0] for x in ts_])
            if len(pts) > 1:
                stroke_poly(hi_c, pts, (255, 255, 255), 0.35, 14)
                stroke_poly(hi_c, pts, ORANGE, 0.85, 5)
            Q.brackets(hi_c, Q.to_screen(puck_pos(i, t) + np.array([0, 0.5, 0]), v)[0], t, 40)
        if 0 <= t - (S[i] + 1.05) < 0.5:                       # Stopp-Ring
            q = e_out((t - S[i] - 1.05) / 0.5, 3)
            xy, ppi = Q.to_screen(puck_pos(i, t), v)
            Q.ring(hi_c, xy, ppi * 2 * (1.2 + 3 * q), ORANGE, 0.9 * (1 - q), 8 * (1 - q) + 2)
    for key, k in REVEAL:
        t0 = VO_START[key]
        t1 = {"r1": VO_START["r3"], "r3": VO_START["r2"], "r2": T_CTA - 0.1}[key]
        if t0 <= t < t1:
            highlight(hi_c, v, k, c01((t - t0 - 0.2) / 0.3) * (1 - smooth(t1 - 0.12, t1, t)), t)
            Q.brackets(hi_c, Q.to_screen(puck_pos(k, t) + np.array([0, 0.5, 0]), v)[0], t, 70)
    for i in range(3):                                          # Wackelaugen
        c = puck_pos(i, t)
        if c is not None:
            draw_eyes(hi_c, v, i, c + np.array([0.0, hop(i, t), 0.0]), t)
    confetti(hi_c, v, t)
    img = over(img, *surf_rgba(hi_s))
    img = flash_wipe(np.clip(img, 0, 1), t)
    pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
    tag_a = c01((t - T_BACK - 0.3) / 0.3) * (1 - smooth(VO_START["r1"] - 0.15, VO_START["r1"], t))
    puck_tags(L, v, t, tag_a)
    bubbles(L, v, t)
    texts(L, t, v)
    Q.brand(L, t)
    pil.alpha_composite(L)
    arr = np.asarray(pil.convert("RGB")).astype(np.float32) / 255
    kicks = [S[i] + 1.05 for i in range(3)] + [T_NO1, T_NO3, T_YES]
    lc = min([t - c for c in kicks if t >= c] + [t + 0.5])
    zp = 1 + 0.03 * math.exp(-lc * 12)
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
    rng = np.random.default_rng(39)
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

    def boing(vol=0.4):
        x = tt(0.45)
        f = 220 + 260 * np.exp(-x * 9) * (1 + 0.35 * np.sin(2 * np.pi * 14 * x))
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 7) * vol

    def trombone(vol=0.5):
        """Traurige Posaune: wah wah wah waaah."""
        out = np.zeros(int(1.35 * SR))
        for j, (f0, d) in enumerate(((233.1, 0.22), (220.0, 0.22), (207.7, 0.22), (196.0, 0.55))):
            x = tt(d)
            vib = 1 + (0.025 * np.sin(2 * np.pi * 6 * x) if j == 3 else 0)
            ph_ = 2 * np.pi * np.cumsum(f0 * vib) / SR
            sig = sum(np.sin(ph_ * h) / h ** 0.9 for h in range(1, 8))
            env = np.minimum(x / 0.03, 1) * np.clip((d - x) / 0.05, 0, 1)
            st = int(sum((0.24, 0.24, 0.24)[:j]) * SR)
            out[st:st + len(x)] += lp(sig, 5) * env
        return out * vol / 3

    def blower(vol=0.4):
        x = tt(0.8)
        f = 420 + 380 * np.clip(x / 0.25, 0, 1)
        sig = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.6 + np.sin(2 * np.pi * np.cumsum(f * 2) / SR) * 0.3
        return lp(sig, 6) * np.minimum(x / 0.02, 1) * np.clip((0.8 - x) / 0.15, 0, 1) * vol

    def scrape(dur=1.05, vol=0.4):
        x = tt(dur)
        env = np.minimum(x / 0.03, 1) * (1 - x / dur) ** 1.5
        return hp(lp(noise(dur), 4), 25) * env * vol

    roots = [55.0, 55.0, 65.41, 49.0]
    for k8 in range(int(DUR / (B / 2))):
        tb = k8 * B / 2
        b = k8 / 2
        pos = b % 4
        if tb > DUR - 0.4 or T_LOCK <= tb < VO_START["r1"]:
            continue
        if pos in (0.0, 2.5) or pos == 1.5:
            put_(mus, kick(0.9), tb)
        if pos in (1.0, 3.0):
            put_(mus, clap(0.75), tb)
        put_(mus, hat(0.1 if k8 % 2 == 0 else 0.06), tb, pan=0.3)
        if pos == 0.0:
            put_(mus, sub(roots[int(b // 4) % 4], 2.6 * B), tb)
    for i in range(3):                                   # Pucks rutschen an die Linie
        put_(sfx, pop(0.3), S[i] + 0.02)
        put_(sfx, scrape(1.05, 0.55), S[i] + 0.02, pan=-0.2 + 0.2 * i)
        put_(sfx, boing(0.4), S[i] + 1.05)
    put_(sfx, whoosh(0.5, 0.35), T_BACK)
    for j in range(7):                                   # Uhr ticken bei "Which one?"
        put_(sfx, tick(0.35), T_LOCK + 0.1 + j * 0.2)
    for key, k in REVEAL:
        put_(sfx, whoosh(0.5, 0.4), VO_START[key] - 0.1)
    put_(sfx, trombone(0.5), T_NO1 + 0.12)
    put_(sfx, trombone(0.5), T_NO3 + 0.12)
    put_(sfx, blower(0.4), T_YES + 0.1)
    put_(sfx, pop(0.5), T_YES)
    put_(sfx, ding(0.5), T_YES)
    put_(sfx, horn(1.3, 0.45), T_YES + 0.05)
    put_(sfx, crowd(2.4, 0.45), T_YES + 0.05)
    put_(sfx, whoosh(0.5, 0.35), T_CTA - 0.1)
    voice = np.zeros(n)
    for k in VO_KEYS:
        tmp = os.path.join(HERE, f"_vo_{k}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "voice", f"reel39_{k}.wav"),
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
    tts_kokoro.synth(VO_LINES, os.path.join(HERE, "voice", "reel39"), speed=1.25)


def check_vo():
    with open(os.path.join(HERE, "voice", "reel39_timing.json")) as f:
        vo_dur = {k: v / TEMPO for k, v in json.load(f).items()}
    for i, k in enumerate(VO_KEYS):
        nxt = VO_START[VO_KEYS[i + 1]] if i + 1 < len(VO_KEYS) else DUR - 0.2
        if VO_START[k] + vo_dur[k] > nxt + 0.05:
            print(f"Warnung: Satz {k} zu lang ({VO_START[k] + vo_dur[k]:.2f} > {nxt:.2f})")


def remux():
    os.chdir(HERE)
    make_audio("audio_goalline.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "reel39_goalline.mp4", "-i", "audio_goalline.wav",
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-af",
                    "loudnorm=I=-14:TP=-1.0:LRA=9", "-ar", "44100", "-shortest", "-movflags", "+faststart",
                    "_tmp_gl39.mp4"], check=True)
    os.replace("_tmp_gl39.mp4", "reel39_goalline.mp4")


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
    make_audio("audio_goalline.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_goalline.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
           "-ar", "44100", "-shortest", "-movflags", "+faststart", "reel39_goalline.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(0.6, 9999)).save("reel39_thumbnail.jpg", quality=92)
    print("fertig: reel39_goalline.mp4")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "vo":
        make_voice()
    elif len(sys.argv) > 1 and sys.argv[1] == "audio":
        remux()
    elif len(sys.argv) > 1 and sys.argv[1] == "prev":
        preview(sys.argv[2].split(","), sys.argv[3])
    else:
        main()
