"""Reel 40: "IN THE NHL, YOU GET A POINT FOR LOSING." – Hot Take / Debatte NHL vs. Europa (~16 s).

Kontrovers, aber fair: Fakten neutral, Urteil den Zuschauern überlassen ("NHL or Europe? Which is fairer?").
Pucks mit Wackelaugen als Figuren (wie Reel 39) vor dem echten Tor-Foto: Puck A trifft in der Verlängerung,
Puck B verliert – und bekommt trotzdem eine Punkt-Medaille. Danach Punkte-Karten NHL (2-2-1-0) und
Schweden/Finnland/Deutschland (3-2-1-0), Pointe: NHL-Spiele mit Verlängerung verteilen 3 Punkte, andere nur 2.
Fakten: siehe FACTS unten (Recherche 25.10.2026). Keine Teams/Vereine, keine Spielerkörper.
Bildnachweis: Tor-Foto Santeri Viinamäki, CC BY-SA 4.0 (Wikimedia Commons).
Stimme: Kokoro "Michael", 1,08x. Aufruf: python3 reel40_points.py vo | audio | prev 0.5,3.0 out.jpg | (Video)
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
from PIL import Image, ImageDraw, ImageFilter

import reel15_puck as R15
import reel18_dangle as R18
import reel38_quiz as Q
import reel39_goalline as G
from reel15_puck import W, H, FPS, c01, smooth, sio, e_out, line_img, put, stroke_poly, surface, surf_rgba, over
from reel22_trapezoid import slam

HERE = R15.HERE
INK, ORANGE = R15.INK, R15.ORANGE
RED = (225, 30, 40)
GREEN = (30, 160, 80)
BLUE = (40, 110, 210)
GOLD = (236, 176, 40)
TEMPO = 1.08

VO_LINES = [
    ("q", "In the NHL, you get a point for losing."),
    ("nhl", "Win: two points. Lose in overtime or a shootout? Still one."),
    ("eu", "In Sweden, Finland and Germany, a regulation win is worth three."),
    ("twist", "So in the NHL, some games are worth three points. Others, only two."),
    ("cta", "NHL or Europe? Which is fairer?"),
]
VO_KEYS = [k for k, _ in VO_LINES]
VO_START = {"q": 0.1, "nhl": 2.45, "eu": 5.9, "twist": 9.55, "cta": 13.35}
DUR = 15.9
WT = {                                           # Wortanfänge (s nach Satzbeginn, nach 1,08x), faster-whisper small.en
    "q": [0.0, 0.1, 0.2, 0.96, 1.1, 1.22, 1.28, 1.44, 1.64],
    "nhl": [0.0, 0.16, 0.38, 1.02, 1.22, 1.38, 1.74, 2.0, 2.1, 2.72, 2.88],
    "eu": [0.0, 0.1, 0.92, 1.14, 1.14, 1.9, 1.92, 2.32, 2.66, 2.84, 3.02],
    "twist": [0.0, 0.14, 0.24, 0.34, 0.96, 1.12, 1.36, 1.54, 1.68, 1.96, 2.72, 2.88, 3.2],
    "cta": [0.0, 0.16, 0.56, 0.64, 1.22, 1.36, 1.54],
}


def wt(key, i):
    return VO_START[key] + WT[key][i]


T_SHOT = 0.15                                    # Puck A rutscht ins Tor
T_GOAL = 0.95
T_MEDAL = wt("q", 6) - 0.05                      # "point": Medaille fällt
T_LAND = T_MEDAL + 0.38
T_EU3 = wt("eu", 10)                             # "three"
T_THREE = wt("twist", 8)
T_TWO = wt("twist", 12)
T_CTA = VO_START["cta"]

# ================================================================= Figuren (Zoll; Torlinie x = 0)
G.PR, G.PH_ = 3.2, 2.0                           # Figuren-Pucks etwas größer als echt
A_START, A_END = np.array([-24.0, 0.0, -24.0]), np.array([10.0, 0.0, -12.0])
B_POS = np.array([-26.0, 0.0, 14.0])
VIEW0 = (1450.0, 1800.0, 1.45)


def pos_a(t):
    u = c01((t - T_SHOT) / (T_GOAL - T_SHOT + 0.25))
    s = 1 - (1 - u) ** 2.2
    p = A_START + (A_END - A_START) * s
    if t >= T_CTA - 0.1:                                       # CTA: A steht B gegenüber
        p = np.array([-26.0, 0.0, -12.0])
    return p


def pos_b(t):
    p = B_POS.copy()
    if T_LAND <= t < T_LAND + 0.9:                             # Freudenhüpfer mit Medaille
        u = (t - T_LAND - 0.1) / 0.32
        if u > 0:
            p[1] = 3.5 * abs(math.sin(math.pi * u)) * (0.6 ** int(u))
    if t >= T_CTA - 0.1:
        p = np.array([-26.0, 0.0, 20.0])
    return p


def mood_a(t):
    if T_GOAL <= t < T_GOAL + 1.2:
        return "happy"
    if t >= T_CTA - 0.1:
        return "angry"
    return "neutral"


def mood_b(t):
    if t < T_GOAL:
        return "neutral"
    if t < T_LAND:
        return "sad"
    if t < T_LAND + 1.0:
        return "happy"
    if VO_START["eu"] <= t < VO_START["twist"]:
        return "worried"
    if t >= T_CTA - 0.1:
        return "angry"
    return "proud"


def look_at(src, dst, v):
    a, _ = Q.to_screen(src, v)
    b, _ = Q.to_screen(dst, v)
    d = b - a
    n = np.linalg.norm(d)
    return d / n * 0.6 if n > 1 else np.zeros(2)


def eyes(ctx, v, c, m, look, t, ph=0.0):
    xy, ppi = Q.to_screen(c + np.array([0.0, G.PH_ * 0.62, 0.0]), v)
    re = max(5.0, 0.62 * ppi)
    sep = 0.95 * ppi
    blink = (t + ph) % 2.7 < 0.09 and m in ("neutral", "proud")
    for sgn in (-1, 1):
        ex, ey = xy[0] + sgn * sep, xy[1]
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
        lk = look if m not in ("sad", "worried") else np.array([0.0, 0.55]) * (1 if m == "sad" else 0.3)
        if m == "worried":
            lk = np.array([0.55 * math.copysign(1, math.sin(t * 6)), 0.1])
        ctx.arc(ex + lk[0] * re * 0.5, ey + lk[1] * re * 0.5, re * 0.5, 0, 2 * math.pi)
        ctx.fill()
        lid = None
        if m == "sad" or m == "worried":                              # innen hoch
            lid = (0.55, 0.05) if sgn > 0 else (0.05, 0.55)
        elif m == "angry":                                            # innen tief
            lid = (0.05, 0.6) if sgn > 0 else (0.6, 0.05)
        elif m == "proud":
            lid = (0.3, 0.3)
        if lid:
            ctx.save()
            ctx.arc(ex, ey, re * 1.05, 0, 2 * math.pi)
            ctx.clip()
            ctx.set_source_rgba(0.06, 0.06, 0.07, 1)
            ctx.move_to(ex - re * 1.2, ey - re * lid[0])
            ctx.line_to(ex + re * 1.2, ey - re * lid[1])
            ctx.line_to(ex + re * 1.2, ey - re * 1.3)
            ctx.line_to(ex - re * 1.2, ey - re * 1.3)
            ctx.close_path()
            ctx.fill()
            ctx.restore()
    if m == "worried":                                                # Schweißtropfen
        q = ((t - VO_START["eu"]) * 0.9) % 1.0
        tx, ty = xy[0] + sep + re * 1.4, xy[1] - re * 1.2 + q * re * 2
        r_ = re * 0.38
        ctx.set_source_rgba(0.35, 0.65, 1.0, 0.95 * (1 - q))
        ctx.move_to(tx, ty - r_ * 1.8)
        ctx.curve_to(tx + r_, ty - r_ * 0.4, tx + r_, ty + r_, tx, ty + r_)
        ctx.curve_to(tx - r_, ty + r_, tx - r_, ty - r_ * 0.4, tx, ty - r_ * 1.8)
        ctx.fill()


# ================================================================= Grafiken
_IMG = {}


def medal():
    if "medal" in _IMG:
        return _IMG["medal"]
    s = 2
    d_ = 170 * s
    im = Image.new("RGBA", (d_, d_ + 70 * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon([(d_ * 0.34, 0), (d_ * 0.5, 0), (d_ * 0.44, 90 * s), (d_ * 0.3, 90 * s)], fill=(200, 30, 45, 255))
    d.polygon([(d_ * 0.5, 0), (d_ * 0.66, 0), (d_ * 0.7, 90 * s), (d_ * 0.56, 90 * s)], fill=(40, 90, 200, 255))
    y0 = 60 * s
    d.ellipse((6 * s, y0, d_ - 6 * s, y0 + d_ - 12 * s), fill=(196, 140, 20, 255))
    d.ellipse((16 * s, y0 + 10 * s, d_ - 16 * s, y0 + d_ - 22 * s), fill=GOLD + (255,), outline=(255, 226, 120, 255), width=5 * s)
    im = im.resize((170, 240), Image.LANCZOS)
    t1 = line_img("+1", 64, 900, (120, 70, 0))
    put(im, t1, 85 - t1.width / 2, 60 + 34)
    t2 = line_img("POINT", 20, 850, (120, 70, 0), track=3)
    put(im, t2, 85 - t2.width / 2, 60 + 104)
    _IMG["medal"] = im
    return im


def points_card(kind):
    """Punkte-Tabelle: kind = 'nhl' oder 'eu'."""
    if kind in _IMG:
        return _IMG[kind]
    w_, rowh = 940, 104
    rows = ([("WIN", "2"), ("OVERTIME / SHOOTOUT LOSS", "1"), ("REGULATION LOSS", "0")] if kind == "nhl" else
            [("REGULATION WIN", "3"), ("OVERTIME / SHOOTOUT WIN", "2"), ("OVERTIME / SHOOTOUT LOSS", "1"),
             ("REGULATION LOSS", "0")])
    head = "NHL" if kind == "nhl" else "SWEDEN · FINLAND · GERMANY"
    h_ = 130 + rowh * len(rows) + 24
    s = 2
    im = Image.new("RGBA", (w_ * s, h_ * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w_ * s - 1, h_ * s - 1), 34 * s, fill=(255, 255, 255, 246), outline=INK + (255,), width=5 * s)
    d.rounded_rectangle((0, 0, w_ * s - 1, 104 * s), 34 * s, fill=(INK if kind == "nhl" else BLUE) + (255,))
    d.rectangle((0, 70 * s, w_ * s - 1, 104 * s), fill=(INK if kind == "nhl" else BLUE) + (255,))
    for i in range(1, len(rows)):
        y = (130 + rowh * i - 6) * s
        d.line((36 * s, y, (w_ - 36) * s, y), fill=(220, 220, 226, 255), width=3 * s)
    im = im.resize((w_, h_), Image.LANCZOS)
    t = line_img(head, 44 if kind == "nhl" else 38, 900, (255, 255, 255), track=6)
    put(im, t, w_ / 2 - t.width / 2, 52 - t.height / 2)
    _IMG[kind] = (im, rows, rowh)
    return _IMG[kind]


def draw_card(L, kind, t, t0, row_t, t_out, hi_row=None, hi_t=None):
    if not (t0 <= t < t_out):
        return
    im, rows, rowh = points_card(kind)
    k = e_out(c01((t - t0) / 0.3), 3)
    a = 1 - smooth(t_out - 0.15, t_out, t)
    card = im.copy()
    for i, (lab, val) in enumerate(rows):
        if t < row_t[i]:
            continue
        p = e_out(c01((t - row_t[i]) / 0.25), 3)
        y = 130 + rowh * i + rowh / 2 - 10
        lt = line_img(lab, 38, 850, INK, track=2)
        if lt.width > 700:
            lt = lt.resize((700, int(lt.height * 700 / lt.width)), Image.LANCZOS)
        put(card, Q.fade_im(lt, p), 44 + (1 - p) * 40, y - lt.height / 2)
        col = {"3": GREEN, "2": INK, "1": ORANGE, "0": RED}[val]
        big = hi_row == i and hi_t is not None and t >= hi_t
        vt = line_img(val, 92 if not big else 92, 900, col)
        sc = 1 + (0.45 * math.sin(math.pi * c01((t - hi_t) / 0.35)) if big else 0)
        if sc != 1:
            vt = vt.resize((int(vt.width * sc), int(vt.height * sc)), Image.LANCZOS)
        put(card, Q.fade_im(vt, p), im.width - 70 - vt.width / 2 - 20, y - vt.height / 2)
    y_ = 900 + 60 * (1 - k)
    put(L, Q.fade_im(card, a * k), W / 2 - card.width / 2, y_ - card.height / 2)


def coins(L, t):
    """Pointe: Spiel mit Verlängerung = 3 Punkte, nach 60 Minuten = 2."""
    if not (VO_START["twist"] <= t < T_CTA - 0.1):
        return
    a = 1 - smooth(T_CTA - 0.25, T_CTA - 0.1, t)
    cols = [(W * 0.28, "REGULATION", 2, T_TWO, RED), (W * 0.72, "OVERTIME", 3, T_THREE, GREEN)]
    for cx, lab, n, tn, col in cols:
        tl = VO_START["twist"] + 0.2
        if t >= tl:
            im = line_img(lab, 40, 900, INK, track=4)
            put(L, Q.fade_im(R15.halo(im), a), cx - R15.halo(im).width / 2, 1290 - R15.halo(im).height / 2)
            put(L, Q.fade_im(im, a), cx - im.width / 2, 1290 - im.height / 2)
            sub = line_img("GAME", 30, 850, INK, track=6)
            put(L, Q.fade_im(sub, a), cx - sub.width / 2, 1340 - sub.height / 2)
        for j in range(n):                                     # Münzen stapeln
            tj = tn - 0.35 + j * 0.12
            if t < tj:
                continue
            dy = -260 * (1 - e_out(c01((t - tj) / 0.3), 2.5))
            md = medal()
            sm = md.resize((120, 170), Image.LANCZOS)
            put(L, Q.fade_im(sm, a), cx - 60 + (j - (n - 1) / 2) * 92, 1010 + dy)
        if t >= tn:
            big = line_img(f"{n} PTS", 110, 900, col)
            sc = 1 + 0.3 * math.sin(math.pi * c01((t - tn) / 0.3))
            big = big.resize((int(big.width * sc), int(big.height * sc)), Image.LANCZOS)
            put(L, Q.fade_im(R15.halo(big), a), cx - R15.halo(big).width / 2, 860 - R15.halo(big).height / 2)
            put(L, Q.fade_im(big, a), cx - big.width / 2, 860 - big.height / 2)


def texts(L, t):
    # Hook: ganzer Satz ab Bild 0
    if t < VO_START["nhl"] - 0.05:
        a = 1 - smooth(VO_START["nhl"] - 0.25, VO_START["nhl"] - 0.05, t)
        for txt, cy, size, col in (("IN THE NHL, YOU GET", 290, 92, INK), ("A POINT", 420, 150, INK),
                                   ("FOR LOSING.", 570, 140, RED)):
            im = Q.fade_im(Q.word(txt, size, col), a)
            put(L, im, W / 2 - im.width / 2, cy - im.height / 2)
    if T_GOAL - 0.05 <= t < VO_START["nhl"]:
        ch = Q.chip("OVERTIME GOAL", RED, 34)
        put(L, Q.fade_im(ch, c01((t - T_GOAL + 0.05) / 0.12) * (1 - smooth(VO_START["nhl"] - 0.2, VO_START["nhl"], t))),
            W / 2 - ch.width / 2, 700)
    # Karten
    nt = [wt("nhl", 0), wt("nhl", 3), wt("nhl", 3) + 0.35]
    draw_card(L, "nhl", t, VO_START["nhl"] - 0.05, nt, VO_START["eu"] - 0.05, 1, wt("nhl", 10))
    et = [VO_START["eu"] + 0.3, VO_START["eu"] + 0.55, VO_START["eu"] + 0.8, VO_START["eu"] + 1.05]
    draw_card(L, "eu", t, VO_START["eu"] - 0.05, et, VO_START["twist"] - 0.05, 0, T_EU3)
    if VO_START["nhl"] - 0.05 <= t < VO_START["eu"] - 0.05:
        im = Q.word("THE NHL WAY", 84, INK)
        put(L, im, W / 2 - im.width / 2, 330 - im.height / 2)
    if VO_START["eu"] - 0.05 <= t < VO_START["twist"] - 0.05:
        im = Q.word("THE EUROPEAN WAY", 84, BLUE)
        put(L, im, W / 2 - im.width / 2, 330 - im.height / 2)
    # Pointe
    if VO_START["twist"] - 0.05 <= t < T_CTA - 0.1:
        im = Q.word("SAME GAME LENGTH?", 76, INK)
        put(L, im, W / 2 - im.width / 2, 300 - im.height / 2)
        if t >= wt("twist", 4):
            im2 = Q.word("NOT THE SAME POINTS.", 70, RED)
            put(L, im2, W / 2 - im2.width / 2, 410 - im2.height / 2)
    coins(L, t)
    # CTA
    if t >= T_CTA - 0.1:
        slam(L, "NHL", 170, INK, W / 2, 280, t, T_CTA - 0.05)
        slam(L, "OR", 76, ORANGE, W / 2, 398, t, wt("cta", 2) - 0.05)
        slam(L, "EUROPE?", 150, BLUE, W / 2, 545, t, wt("cta", 3) - 0.05)
        slam(L, "WHICH IS FAIRER?", 80, INK, W / 2, 705, t, wt("cta", 4) - 0.05)
        if t >= wt("cta", 6) + 0.1:
            R15.reveal_halo(L, line_img("COMMENT BELOW", 48, 850, RED, track=8), W / 2, 805,
                            c01((t - wt("cta", 6) - 0.1) / 0.25))


def labels(L, v, t):
    """Namensschilder über den Pucks."""
    items = []
    if t < VO_START["nhl"]:
        a = c01((t - 0.2) / 0.2) * (1 - smooth(VO_START["nhl"] - 0.2, VO_START["nhl"], t))
        items = [(pos_a(t), "TEAM A", INK, a), (pos_b(t), "TEAM B", INK, a)]
        if t >= T_GOAL + 0.15:
            items = [(pos_a(t), "WINS IN OT", GREEN, a), (pos_b(t), "LOSES IN OT", RED, a)]
    if t >= T_CTA - 0.1:
        a = c01((t - T_CTA) / 0.2)
        items = [(pos_a(t), "NHL", INK, a), (pos_b(t), "EUROPE", BLUE, a)]
    for c, txt, col, a in items:
        if a <= 0:
            continue
        ch = Q.chip(txt, col, 30)
        below = c is items[-1][0] and t < VO_START["nhl"]          # B: Schild unter dem Puck (Platz für die Medaille)
        xy, ppi = Q.to_screen(c + np.array([0.0, 0.0 if below else 6.5, 0.0]), v)
        y = xy[1] + 0.9 * ppi + 10 if below else xy[1] - ch.height
        put(L, Q.fade_im(ch, a), float(np.clip(xy[0] - ch.width / 2, 20, W - 20 - ch.width)), y)


def view(t):
    v = VIEW0
    if t < 1.2:
        v = Q.lerp_v((1400.0, 1780.0, 1.3), VIEW0, sio(c01(t / 1.2)))
    if t >= T_CTA - 0.1:
        v = Q.lerp_v(VIEW0, (1350.0, 1820.0, 1.5), sio(c01((t - T_CTA) / 1.0)))
    return Q.clamp_view(*v)


def flash_wipe(img, t):
    for c in (T_GOAL, VO_START["nhl"], VO_START["eu"], VO_START["twist"], T_CTA - 0.1):
        d = t - c
        if -0.05 <= d < 0.18:
            a = (0.5 if c == T_GOAL else 0.6) * (1 - c01((d + 0.05) / 0.23))
            img = img * (1 - a) + a
    return img


# ================================================================= Bild
_BLUR = {}


def compose(t, fidx):
    G.painted_photo()
    v = view(t)
    img = Q.background(v)
    # Karten-Phase: Hintergrund weich + heller, damit die Tabellen lesbar sind
    card_a = smooth(VO_START["nhl"] - 0.1, VO_START["nhl"] + 0.2, t) * (1 - smooth(T_CTA - 0.3, T_CTA - 0.1, t))
    if card_a > 0:
        bl = cv2.GaussianBlur(img, (0, 0), 9)
        img = img * (1 - card_a) + (bl * 0.75 + 0.25) * card_a
    hi_s, hi_c = surface()
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pa, pb = pos_a(t), pos_b(t)
    show_a = t < VO_START["nhl"] + 0.2 or t >= T_CTA - 0.1
    pucks = [(pb, "b")] + ([(pa, "a")] if show_a else [])
    pucks.sort(key=lambda x: -Q.to_photo(x[0])[1])
    for c, who in pucks:
        img = G.draw_puck(img, v, c, ground=np.array([c[0], 0.0, c[2]]))
    # Rutschspur von A
    if T_SHOT <= t < T_GOAL + 0.2:
        ts_ = np.linspace(max(T_SHOT, t - 0.22), t, 10)
        pts = np.array([Q.to_screen(pos_a(x) + np.array([0, 0.7, 0]), v)[0] for x in ts_])
        if len(pts) > 1:
            stroke_poly(hi_c, pts, (255, 255, 255), 0.35, 16)
            stroke_poly(hi_c, pts, ORANGE, 0.85, 6)
    if 0 <= t - T_GOAL < 0.6:
        q = e_out((t - T_GOAL) / 0.6, 3)
        xy, ppi = Q.to_screen(pa, v)
        Q.ring(hi_c, xy, ppi * 3 * (1.2 + 4 * q), GREEN, 0.9 * (1 - q), 9 * (1 - q) + 2)
    for c, who in pucks:
        if who == "a":
            lk = look_at(c, pb, v) if t >= T_CTA - 0.1 else (np.array([0.5, -0.1]) if t < T_GOAL else np.array([0, -0.4]))
            eyes(hi_c, v, c, mood_a(t), lk, t, 0.9)
        else:
            if t < T_GOAL:
                lk = look_at(c, pa, v)
            elif t >= T_CTA - 0.1:
                lk = look_at(c, pa, v)
            elif t >= VO_START["nhl"]:
                lk = np.array([0.0, -0.6])                      # schaut zur Karte hoch
            else:
                lk = np.array([0.0, -0.3])
            eyes(hi_c, v, c, mood_b(t), lk, t)
    img = over(img, *surf_rgba(hi_s))
    img = flash_wipe(np.clip(img, 0, 1), t)
    pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
    labels(L, v, t)
    # Medaille fällt auf B
    if t >= T_MEDAL and t < VO_START["nhl"] + 0.1:
        xy, ppi = Q.to_screen(pb + np.array([0.0, G.PH_ + 4.0, 0.0]), v)
        u = c01((t - T_MEDAL) / 0.38)
        drop = -700 * (1 - u) ** 2
        bounce = -26 * abs(math.sin(math.pi * c01((t - T_LAND) / 0.25))) * (t >= T_LAND)
        md = medal()
        put(L, Q.fade_im(md, 1 - smooth(VO_START["nhl"] - 0.1, VO_START["nhl"] + 0.1, t)),
            xy[0] - md.width / 2, xy[1] - md.height + drop + bounce)
    texts(L, t)
    Q.brand(L, t)
    pil.alpha_composite(L)
    arr = np.asarray(pil.convert("RGB")).astype(np.float32) / 255
    kicks = [T_GOAL, T_LAND, T_EU3, T_THREE, T_TWO]
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
    rng = np.random.default_rng(40)
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
        if tb > DUR - 0.4:
            continue
        if pos in (0.0, 2.5) or pos == 1.5:
            put_(mus, kick(0.9), tb)
        if pos in (1.0, 3.0):
            put_(mus, clap(0.75), tb)
        put_(mus, hat(0.1 if k8 % 2 == 0 else 0.06), tb, pan=0.3)
        if pos == 0.0:
            put_(mus, sub(roots[int(b // 4) % 4], 2.6 * B), tb)
    put_(sfx, scrape(0.9, 0.5), T_SHOT)
    put_(sfx, horn(1.1, 0.45), T_GOAL)
    put_(sfx, crowd(1.6, 0.35), T_GOAL)
    put_(sfx, trombone(0.35), T_GOAL + 0.15)
    put_(sfx, whoosh(0.4, 0.35), T_MEDAL)
    put_(sfx, ding(0.55), T_LAND)
    put_(sfx, boing(0.35), T_LAND + 0.1)
    for key in ("nhl", "eu", "twist"):
        put_(sfx, whoosh(0.5, 0.35), VO_START[key] - 0.1)
    put_(sfx, pop(0.4), T_EU3)
    for j in range(3):
        put_(sfx, tick(0.4), T_THREE - 0.35 + j * 0.12)
    for j in range(2):
        put_(sfx, tick(0.4), T_TWO - 0.35 + j * 0.12)
    put_(sfx, boing(0.35), T_TWO + 0.05)
    put_(sfx, whoosh(0.5, 0.35), T_CTA - 0.1)
    put_(sfx, clack(0.5), T_CTA + 0.05)
    voice = np.zeros(n)
    for k in VO_KEYS:
        tmp = os.path.join(HERE, f"_vo_{k}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "voice", f"reel40_{k}.wav"),
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
    tts_kokoro.synth(VO_LINES, os.path.join(HERE, "voice", "reel40"), speed=1.25)


def check_vo():
    with open(os.path.join(HERE, "voice", "reel40_timing.json")) as f:
        vo_dur = {k: v / TEMPO for k, v in json.load(f).items()}
    for i, k in enumerate(VO_KEYS):
        nxt = VO_START[VO_KEYS[i + 1]] if i + 1 < len(VO_KEYS) else DUR - 0.2
        if VO_START[k] + vo_dur[k] > nxt + 0.05:
            print(f"Warnung: Satz {k} zu lang ({VO_START[k] + vo_dur[k]:.2f} > {nxt:.2f})")


def remux():
    os.chdir(HERE)
    make_audio("audio_points.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "reel40_points.mp4", "-i", "audio_points.wav",
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-af",
                    "loudnorm=I=-14:TP=-1.0:LRA=9", "-ar", "44100", "-shortest", "-movflags", "+faststart",
                    "_tmp_pt40.mp4"], check=True)
    os.replace("_tmp_pt40.mp4", "reel40_points.mp4")


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
    make_audio("audio_points.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_points.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
           "-ar", "44100", "-shortest", "-movflags", "+faststart", "reel40_points.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(0.6, 9999)).save("reel40_thumbnail.jpg", quality=92)
    print("fertig: reel40_points.mp4")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "vo":
        make_voice()
    elif len(sys.argv) > 1 and sys.argv[1] == "audio":
        remux()
    elif len(sys.argv) > 1 and sys.argv[1] == "prev":
        preview(sys.argv[2].split(","), sys.argv[3])
    else:
        main()
