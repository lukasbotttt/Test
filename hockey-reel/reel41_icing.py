"""Reel 41: HOCKEY QUIZ #3 – "3 SHOTS. ONLY 1 IS ICING." (Neon-Motion-Look wie reel40_motion.py, ~16 s)

Drei Puck-Figuren liegen an der roten Mittellinie, werden gleichzeitig übers ganze Eis geschossen, Rückspulen,
"Which one?", Auflösung mit Nahaufnahmen von oben (Berührung grün, Lücke rot), Pointe Torlinie vs. Mittellinie.
Fakten (NHL Official Rules 2026-27):
- Rule 81.1: Schießt ein gleich starkes/überlegenes Team den Puck aus der eigenen Hälfte über die gegnerische
  Torlinie -> Icing. "Gaining the line": berührt der Puck (am Schläger) die rote Mittellinie, gibt es kein Icing.
- Rule 1.5: Mittellinie 12 Zoll breit. Rule 78.4: Tor nur, wenn der Puck ENTIRELY über der Torlinie ist.
- Rule 81.5/81.6 (Berührung durch Gegner, Unterzahl) bewusst ausgeklammert: "5 ON 5", leeres Eis.
Stil-Puck: 1 ft Durchmesser (Figur), Mittellinie maßstabsgetreu 1 ft. Keine Teams/Vereine, keine Spielerkörper.
Aufruf: python3 reel41_icing.py audio | prev 0.5,3.0 out.jpg | (Video)
"""
import json
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
from PIL import Image, ImageDraw

import reel40_motion as E

M = E.M
E.PR, E.PHT = 0.5, 0.33                          # Figuren-Puck: 1 ft Durchmesser
HERE = E.HERE
W, H, FPS = E.W, E.H, E.FPS
TEMPO = 1.08
WHITE, RED, BLUE, ICE, GOLD, GREEN, ORANGE = E.WHITE, E.RED, E.BLUE, E.ICE, E.GOLD, E.GREEN, E.ORANGE
c01, e_out, e_in, sio, smooth, vec = E.c01, E.e_out, E.e_in, E.sio, E.smooth, E.vec

VO_LINES = [
    ("q", "Three shots. Only ONE is icing."),
    ("lock", "Which one?"),
    ("r1", "One touches the red line. No icing."),
    ("r3", "Three is over it. No icing."),
    ("r2", "But two never touched it. Icing!"),
    ("twist", "For a goal? The whole puck. For icing? Just a touch."),
    ("cta", "Did you get it? Follow for part four."),
]
VO_KEYS = [k for k, _ in VO_LINES]
VO_START = {"q": 0.1, "lock": 4.05, "r1": 5.35, "r3": 7.65, "r2": 9.5, "twist": 11.45, "cta": 13.95}
DUR = 16.35
WT = {                                           # Wortanfänge (s nach Satzbeginn, nach 1,08x), faster-whisper small.en
    "q": [0.0, 0.24, 0.84, 1.0, 1.24, 1.36],
    "lock": [0.0, 0.2],
    "r1": [0.0, 0.2, 0.58, 0.7, 0.84, 1.44, 1.56],
    "r3": [0.0, 0.2, 0.34, 0.6, 0.98, 1.1],
    "r2": [0.0, 0.14, 0.28, 0.5, 0.74, 1.12],
    "twist": [0.0, 0.18, 0.26, 0.42, 0.6, 0.8, 0.98, 1.2, 1.68, 1.8, 1.94],
    "cta": [0.0, 0.12, 0.22, 0.42, 0.7, 0.94, 1.18, 1.38],
}


def wt(key, i):
    return VO_START[key] + WT[key][i]


T_SHOT = [2.15, 2.25, 2.35]                      # die drei Schüsse
FLY = 1.0
T_RW0, T_RW1 = 3.45, 3.95                        # Rückspulen
T_LOCK = VO_START["lock"] - 0.05
REVEAL = [("r1", 0), ("r3", 2), ("r2", 1)]
T_V = {0: wt("r1", 5), 2: wt("r3", 4), 1: wt("r2", 5)}          # "No (icing)" / "Icing"
T_GOALC = wt("twist", 2)                         # "goal"
T_ICEC = wt("twist", 7)                          # "icing"
T_CTA = VO_START["cta"]

# ================================================================= Pucks (ft; Mittellinie x = -0.5..0.5, Angriff Richtung +x)
PUCKS = [
    dict(x=-0.75, z=-2.0, end=(98.0, -18.0), icing=False, why="TOUCHES THE RED LINE"),   # 3 Zoll auf der Linie
    dict(x=-1.25, z=0.0, end=(98.0, 9.0), icing=True, why="NEVER TOUCHED IT"),           # 3 Zoll Lücke
    dict(x=1.25, z=2.0, end=(98.0, 22.0), icing=False, why="ALREADY PAST IT"),
]


def start_pos(k):
    return vec(PUCKS[k]["x"], 0, PUCKS[k]["z"])


def fly_pos(k, u):
    p0 = start_pos(k)
    p1 = vec(PUCKS[k]["end"][0], 0, PUCKS[k]["end"][1])
    s = 1 - (1 - c01(u)) ** 2.2
    return p0 + (p1 - p0) * s


def cross_time(k):
    lo, hi = 0.0, 1.0
    for _ in range(30):
        mid = (lo + hi) / 2
        if fly_pos(k, mid)[0] < 89.0:
            lo = mid
        else:
            hi = mid
    return T_SHOT[k] + lo * FLY


T_CROSS = [cross_time(k) for k in range(3)]


def puck_pos(k, t):
    if t < T_SHOT[k]:
        return start_pos(k)
    if t < T_RW0:
        return fly_pos(k, (t - T_SHOT[k]) / FLY)
    if t < T_RW1:
        end = fly_pos(k, (T_RW0 - T_SHOT[k]) / FLY)
        s = sio((t - T_RW0) / (T_RW1 - T_RW0))
        return end + (start_pos(k) - end) * s
    return start_pos(k)


def mood(k, t):
    if t >= T_V[k]:
        return "sad" if PUCKS[k]["icing"] else "happy" if t < T_V[k] + 1.2 else "proud"
    if T_LOCK <= t < VO_START["r1"]:
        return {0: "worried", 1: "proud", 2: "neutral"}[k]
    if t >= VO_START["r1"]:
        return "worried" if k == 1 and t >= VO_START["r3"] else "neutral"
    return "neutral"


# ================================================================= Kamera
LOCK_C, LOCK_T = vec(-5.5, 14.0, 0.0), vec(0.3, 0.0, 0.0)
OVER_C, OVER_T = vec(20.0, 95.0, 0.0), vec(55.0, 0.0, 0.0)


def cam_seg(i, u):
    """Kamera-Schlüssel für Segment i bei lokaler Zeit u."""
    if i == 0:                                                   # Hook: schräg hinter den Pucks
        k = sio(c01(u / 2.1))
        return vec(-11.5 + 0.8 * k, 8.5 - 0.6 * k, 0.0), vec(2.5, 0.6, 0.0), 46.0
    if i == 1:                                                   # Schüsse: hoch in die Draufsicht der Angriffshälfte
        k = sio(c01(u / 0.5))
        p0, g0 = vec(-10.7, 7.9, 0.0), vec(2.5, 0.6, 0.0)
        return p0 + (OVER_C - p0) * k, g0 + (OVER_T - g0) * k, 46.0 + 8 * k
    if i == 2:                                                   # Rückspulen -> von oben auf die Mittellinie
        k = sio(c01(u / 0.5))
        return OVER_C + (LOCK_C - OVER_C) * k, OVER_T + (LOCK_T - OVER_T) * k, 54 - 4 * k
    if i == 3:                                                   # "Which one?"
        k = sio(c01(u / 1.4))
        return LOCK_C + vec(0.3 * k, -0.8 * k, 0.0), LOCK_T, 50.0
    if 4 <= i <= 6:                                              # Nahaufnahmen von schräg oben
        k_ = REVEAL[i - 4][1]
        p = start_pos(k_)
        d = sio(c01(u / 2.0))
        return p + vec(-0.55 + 0.1 * d, 8.4 - 0.5 * d, 0.0), p + vec(0.15, 0.0, 0.0), 44.0
    if i == 7:                                                   # Pointe: Überblick
        k = sio(c01(u / 2.4))
        return vec(-6.0, 15.5 - k, 0.0), vec(0.3, 0.0, 0.0), 52.0
    k = sio(c01(u / 2.2))                                        # CTA
    return LOCK_C + vec(-1.0 * k, 2.0 * k, 0.0), LOCK_T, 50.0


SEG_T = [0.0, T_SHOT[0], T_RW0, T_RW1, VO_START["r1"], VO_START["r3"], VO_START["r2"], VO_START["twist"], T_CTA - 0.1, DUR]
BLEND = {4: 0.32, 5: 0.32, 6: 0.32, 7: 0.4, 8: 0.4, 3: 0.0, 2: 0.0, 1: 0.0}


def seg_of(t):
    for i in range(len(SEG_T) - 1):
        if t < SEG_T[i + 1]:
            return i
    return len(SEG_T) - 2


def cam_at(t):
    i = seg_of(t)
    u = t - SEG_T[i]
    p, g, f = cam_seg(i, u)
    b = BLEND.get(i, 0.0)
    if b > 0 and u < b and i > 0:                                # Whip-Übergang vom vorigen Segment
        pp, gg, ff = cam_seg(i - 1, SEG_T[i] - SEG_T[i - 1])
        s = sio(sio(u / b))
        p, g, f = pp + (p - pp) * s, gg + (g - gg) * s, ff + (f - ff) * s
    return E.Cam(p, g, f)


def whip_amount(t):
    i = seg_of(t)
    b = BLEND.get(i, 0.0)
    u = t - SEG_T[i]
    if b > 0 and u < b and i > 0:
        return math.sin(math.pi * u / b) ** 2
    if T_RW0 <= t < T_RW1:
        return 0.6 * math.sin(math.pi * (t - T_RW0) / (T_RW1 - T_RW0))
    return 0.0


def tint_at(t):
    i = seg_of(t)
    T = {0: (0.55, 0.78, 1.0), 1: (0.5, 0.85, 1.0), 2: (0.85, 0.6, 1.0), 3: (0.55, 0.78, 1.0), 7: (1.0, 0.8, 0.45),
         8: (0.75, 0.55, 1.0)}
    if 4 <= i <= 6:
        k = REVEAL[i - 4][1]
        return (1.0, 0.4, 0.45) if (PUCKS[k]["icing"] and t >= T_V[k]) else (0.5, 0.92, 0.7) if t >= T_V[k] else (0.6, 0.8, 1.0)
    return T[i]


def look_dict(t):
    tn = tint_at(t)
    return dict(key=(1.0, 0.95, 0.92), rim=tuple(0.35 + 0.65 * v for v in tn), tint=tn)


# ================================================================= Overlays
def poly_world(cam, pts):
    xy, z = cam.proj(np.array(pts, float))
    return xy if (z > 0.3).all() else None


def fill_path(ctx, xy):
    ctx.move_to(*xy[0])
    for p in xy[1:]:
        ctx.line_to(*p)
    ctx.close_path()


def highlight(ctx, cam, k, t, a):
    """Nahaufnahme: Linie + Puck-Abdruck; Berührung grün, Lücke rot, Puck jenseits der Linie grün."""
    if a <= 0:
        return
    p = PUCKS[k]
    x, z = p["x"], p["z"]
    circ = poly_world(cam, [(x + E.PR * math.cos(q), 0.01, z + E.PR * math.sin(q)) for q in np.linspace(0, 2 * math.pi, 72)])
    edge_near = poly_world(cam, [(-0.5, 0.01, zz) for zz in np.linspace(z - 2.2, z + 2.2, 20)])
    edge_far = poly_world(cam, [(0.5, 0.01, zz) for zz in np.linspace(z - 2.2, z + 2.2, 20)])
    if circ is None or edge_near is None:
        return
    pulse = 0.6 + 0.3 * math.sin(t * 9)
    ctx.set_dash([20, 12], -t * 50)
    ctx.set_line_width(5)
    ctx.set_source_rgba(1, 1, 1, 0.95 * a)
    for e in (edge_near, edge_far):
        ctx.move_to(*e[0])
        for q in e[1:]:
            ctx.line_to(*q)
        ctx.stroke()
    ctx.set_dash([])
    if k == 0:                                                   # Überlappung Puck ∩ Linie
        band = poly_world(cam, [(-0.5, 0.01, z - 2), (0.5, 0.01, z - 2), (0.5, 0.01, z + 2), (-0.5, 0.01, z + 2)])
        ctx.save()
        fill_path(ctx, band)
        ctx.clip()
        fill_path(ctx, circ)
        ctx.set_source_rgba(0.25, 1.0, 0.5, 0.75 * pulse * a)
        ctx.fill()
        ctx.restore()
    elif k == 1:                                                 # Lücke bis zur Linie
        gap = poly_world(cam, [(x + E.PR, 0.01, z - 0.3), (-0.5, 0.01, z - 0.3), (-0.5, 0.01, z + 0.3), (x + E.PR, 0.01, z + 0.3)])
        fill_path(ctx, gap)
        ctx.set_source_rgba(1.0, 0.2, 0.3, pulse * a)
        ctx.fill()
    else:                                                        # ganz in der Angriffshälfte
        half = poly_world(cam, [(0.5, 0.01, z - 2), (4.0, 0.01, z - 2), (4.0, 0.01, z + 2), (0.5, 0.01, z + 2)])
        fill_path(ctx, half)
        ctx.set_source_rgba(0.25, 1.0, 0.5, 0.18 * a)
        ctx.fill()
    ctx.set_line_width(4)
    ctx.set_source_rgba(1, 1, 1, 0.9 * a)
    fill_path(ctx, circ)
    ctx.stroke()


def num_badge(n, st, size=84):
    key = ("nb", n, st, size)
    if key in E._SPR:
        return E._SPR[key]
    s = 3
    im = Image.new("RGBA", (size * s, size * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fill = {None: (18, 20, 30), "yes": (30, 170, 90), "no": (220, 40, 55)}[st]
    d.ellipse((4, 4, size * s - 4, size * s - 4), fill=fill + (235,), outline=(255, 255, 255, 255), width=5 * s)
    im = im.resize((size, size), Image.LANCZOS)
    if st == "no":
        d2 = ImageDraw.Draw(im)
        q = size * 0.3
        d2.line((q, q, size - q, size - q), fill=(255, 255, 255, 255), width=int(size * 0.1))
        d2.line((q, size - q, size - q, q), fill=(255, 255, 255, 255), width=int(size * 0.1))
    elif st == "yes":
        d2 = ImageDraw.Draw(im)
        d2.line((size * 0.26, size * 0.52, size * 0.43, size * 0.69, size * 0.75, size * 0.33), fill=(255, 255, 255, 255),
                width=int(size * 0.1), joint="curve")
    else:
        tt = M.text_spr(str(n), "x9", int(size * 0.5), WHITE)
        im.alpha_composite(tt.img, (int(size / 2 - tt.ax), int(size / 2 - tt.ay)))
    E._SPR[key] = M.Spr(im, size / 2, size / 2)
    return E._SPR[key]


def verdict_state(k, t):
    if t >= T_V[k]:
        return "no" if PUCKS[k]["icing"] else "yes"
    return None


def puck_badges(img, cam, t, a, lift=1.6, size=80):
    if a <= 0.01:
        return
    for k in range(3):
        c = puck_pos(k, t)
        xy, z = cam.proj(c + vec(0, lift, 0))
        if z[0] < 0.5:
            continue
        M.draw(img, num_badge(k + 1, verdict_state(k, t), size), xy[0, 0], xy[0, 1], a)


def badges_row(img, t, y, a):
    for k in range(3):
        st = verdict_state(k, t)
        sp = num_badge(k + 1, st, 96)
        pop = 1.0
        if st is not None and t - T_V[k] < 0.3:
            pop = 1 + 0.3 * math.sin(math.pi * (t - T_V[k]) / 0.3)
        M.draw(img, sp, W / 2 + (k - 1) * 150, y, a, pop)


def mini_card(kind):
    key = ("mini", kind)
    if key in E._SPR:
        return E._SPR[key]
    w_, h_ = 460, 560
    s = 2
    im = Image.new("RGBA", (w_ * s, h_ * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w_ * s - 1, h_ * s - 1), 34 * s, fill=(12, 14, 24, 170), outline=(255, 255, 255, 90),
                        width=3 * s)
    hc = (230, 40, 70) if kind == "goal" else (40, 140, 255)
    d.rounded_rectangle((0, 0, w_ * s - 1, 96 * s), 34 * s, fill=hc + (235,))
    d.rectangle((0, 60 * s, w_ * s - 1, 96 * s), fill=hc + (235,))
    # Symbol: Linie + Puck (Draufsicht)
    cx, cy = w_ * s / 2, 270 * s
    if kind == "goal":
        lw = 10 * s                                              # Torlinie: 2 Zoll
        d.rectangle((cx - 60 * s - lw / 2, cy - 120 * s, cx - 60 * s + lw / 2, cy + 120 * s), fill=(255, 50, 70, 255))
        r = 62 * s
        px = cx - 60 * s + lw / 2 + 16 * s + r
    else:
        lw = 120 * s                                             # Mittellinie: 12 Zoll
        d.rectangle((cx - 40 * s - lw / 2, cy - 120 * s, cx - 40 * s + lw / 2, cy + 120 * s), fill=(255, 50, 70, 255))
        r = 62 * s
        px = cx - 40 * s - lw / 2 - r + 22 * s                   # Puck berührt die Linie
    d.ellipse((px - r, cy - r, px + r, cy + r), fill=(20, 20, 26, 255), outline=(255, 255, 255, 255), width=4 * s)
    im = im.resize((w_, h_), Image.LANCZOS)
    t1 = M.text_spr("GOAL" if kind == "goal" else "ICING", "x9", 44, WHITE, 0.06)
    im.alpha_composite(t1.img, (int(w_ / 2 - t1.ax), int(50 - t1.ay)))
    l1 = M.text_spr("GOAL LINE" if kind == "goal" else "CENTER RED LINE", "m7", 22, (190, 196, 210))
    im.alpha_composite(l1.img, (int(w_ / 2 - l1.ax), int(132 - l1.ay)))
    l2 = E.fit_spr("WHOLE PUCK" if kind == "goal" else "JUST A TOUCH", 52, GREEN if kind != "goal" else WHITE, 400)
    im.alpha_composite(l2.img, (int(w_ / 2 - l2.ax), int(452 - l2.ay)))
    l3 = M.text_spr("MUST BE ACROSS" if kind == "goal" else "IS ENOUGH", "x8", 26, (200, 205, 220), 0.06)
    im.alpha_composite(l3.img, (int(w_ / 2 - l3.ax), int(505 - l3.ay)))
    E._SPR[key] = im
    return im


def draw_mini(img, blur, kind, cx, cy, t, t_in, t_out):
    if not (t_in <= t < t_out + 0.2):
        return
    p = e_out(c01((t - t_in) / 0.4), 3)
    q = e_in(c01((t - t_out) / 0.2), 2)
    a = p * (1 - q)
    yaw = (1 - p) * (70 if kind == "goal" else -70) + 4 * math.sin(t * 1.4 + (0 if kind == "goal" else 2))
    im = mini_card(kind)
    tim, (ax, ay) = M.tilt(im, yaw, 3 * math.sin(t * 1.1))
    arr = M.to_spr(tim)
    x0, y0 = int(cx - ax), int(cy - ay)
    hh, ww = arr.shape[:2]
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + ww), min(H, y0 + hh)
    if xb > xa and yb > ya:
        m = arr[ya - y0:yb - y0, xa - x0:xb - x0, 3:4] * a
        img[ya:yb, xa:xb] = img[ya:yb, xa:xb] * (1 - m) + blur[ya:yb, xa:xb] * 0.5 * m
    M.blit(img, arr, x0, y0, a)


def hud(img, t):
    tg = M.tag_spr("HOCKEY QUIZ #3", col=(40, 140, 255), fg=WHITE, size=26)
    M.draw(img, tg, 60, 118, 0.95)
    lab = M.text_spr("NHL RULE 81.1", "m7", 26, (200, 205, 220))
    M.draw(img, lab, W - 60 - lab.tw / 2, 118 + tg.img.height / 2, 0.95)
    segs = [0.0, T_SHOT[0], T_LOCK, VO_START["r1"], T_CTA - 0.1, DUR]
    for i in range(5):
        x0 = 60 + i * (W - 120 + 12) / 5
        wseg = (W - 120 + 12) / 5 - 12
        M.blit(img, M.solid((255, 255, 255), int(wseg), 4, 0.18), x0, 186)
        f = c01((t - segs[i]) / (segs[i + 1] - segs[i]))
        if f > 0:
            M.blit(img, M.solid((255, 255, 255), max(1, int(wseg * f)), 4, 0.9), x0, 186)
    for (cx, cy, dx, dy) in ((40, 40, 1, 1), (W - 40, 40, -1, 1), (40, H - 40, 1, -1), (W - 40, H - 40, -1, -1)):
        M.blit(img, M.solid((255, 255, 255), 46, 3, 0.5), cx if dx > 0 else cx - 46, cy if dy > 0 else cy - 3)
        M.blit(img, M.solid((255, 255, 255), 3, 46, 0.5), cx if dx > 0 else cx - 3, cy if dy > 0 else cy - 46)


def texts(img, t):
    # Hook – ganze Frage ab Bild 0
    if t < T_SHOT[0] + 0.25:
        out = smooth(T_SHOT[0] - 0.05, T_SHOT[0] + 0.25, t)
        a, dy = 1 - out, -out * 140
        l1 = E.fit_spr("3 SHOTS.", 170, WHITE, 980)
        l2 = E.fit_spr("ONLY 1 IS ICING.", 104, ICE, 1000)
        M.draw(img, l1, W / 2, 300 + dy, a, 1 + 0.02 * t, glow=0.2)
        M.draw(img, l2, W / 2, 445 + dy, a, 1 + 0.02 * t, glow=0.6)
        if 0.3 <= t <= 1.3:
            E.sweep(img, l1, W / 2, 300 + dy, 1 + 0.02 * t, (t - 0.3) / 1.0 * 1.4 - 0.2)
        E.tag(img, "5 ON 5", (60, 64, 80), W / 2, 560 + dy, a, 1.0, WHITE, 28)
    # Torlinie überquert: "ICING?"
    for k in range(3):
        if T_CROSS[k] <= t < T_RW0:
            sp = E.fit_spr("ICING?", 120, WHITE, 900)
            E.slam(img, sp, W / 2, 640, t, T_CROSS[0], None, 1.6, glow=0.5)
            break
    if T_RW0 <= t < T_RW1 + 0.1:
        sp = E.fit_spr("<< REWIND", 64, WHITE, 700, "x8", 0.08)
        if int(t * 8) % 2 == 0:
            M.draw(img, sp, W / 2, 470, 0.9)
    # Which one?
    if T_LOCK <= t < VO_START["r1"]:
        sp = E.fit_spr("WHICH ONE?", 140, WHITE, 980)
        E.slam(img, sp, W / 2, 330, t, T_LOCK, VO_START["r1"] - 0.15, 1.7, glow=0.3)
        if t >= T_LOCK + 0.3:
            sp2 = E.fit_spr("COMMENT 1, 2 OR 3", 50, GOLD, 900, "x8", 0.08)
            M.draw(img, sp2, W / 2, 455, c01((t - T_LOCK - 0.3) / 0.2) * (1 - smooth(VO_START["r1"] - 0.2, VO_START["r1"], t)),
                   glow=0.3)
    # Auflösung
    for i, (key, k) in enumerate(REVEAL):
        t0 = VO_START[key]
        t1 = VO_START[REVEAL[i + 1][0]] if i + 1 < len(REVEAL) else VO_START["twist"]
        if not (t0 - 0.05 <= t < t1):
            continue
        a = c01((t - t0) / 0.2) * (1 - smooth(t1 - 0.15, t1, t))
        badges_row(img, t, 290, a)
        sub = E.fit_spr(PUCKS[k]["why"], 50, WHITE, 960, "x8", 0.05)
        M.draw(img, sub, W / 2, 520, a * c01((t - t0 - 0.1) / 0.2))
        if t >= T_V[k]:
            big = E.fit_spr("ICING!" if PUCKS[k]["icing"] else "NO ICING", 150, RED if PUCKS[k]["icing"] else GREEN, 980)
            E.slam(img, big, W / 2, 410, t, T_V[k], t1 - 0.15, 1.8, glow=0.8,
                   echo=E.outline_spr("ICING!" if PUCKS[k]["icing"] else "NO ICING",
                                      E.fit_size("ICING!" if PUCKS[k]["icing"] else "NO ICING", 150, 980),
                                      RED if PUCKS[k]["icing"] else GREEN, 4))
            if t >= T_V[k] + 0.25:
                r = M.text_spr("NHL RULE 81.1", "m7", 26, (200, 205, 220))
                M.draw(img, r, W / 2, 585, a * c01((t - T_V[k] - 0.25) / 0.2))
    # Pointe
    if VO_START["twist"] - 0.05 <= t < T_CTA:
        b = VO_START["twist"]
        E.kline(img, [("SAME", 84, WHITE), ("RED,", 84, RED)], 320, t, [b, b + 0.12], T_CTA - 0.2)
        E.kline(img, [("DIFFERENT", 84, WHITE), ("RULE.", 84, GOLD)], 430, t, [b + 0.3, b + 0.45], T_CTA - 0.2)
    # CTA
    if t >= T_CTA - 0.1:
        E.slam(img, E.fit_spr("DID YOU GET IT?", 104, WHITE, 980), W / 2, 330, t, T_CTA - 0.05, None, 1.7, glow=0.3)
        E.slam(img, E.fit_spr("FOLLOW", 190, WHITE, 900), W / 2, 1400, t, wt("cta", 4) - 0.05, None, 1.8, glow=0.5,
               echo=E.outline_spr("FOLLOW", E.fit_size("FOLLOW", 190, 900), RED, 4))
        if t >= wt("cta", 6) - 0.05:
            sp = E.fit_spr("FOR PART 4", 70, GOLD, 800)
            E.slam(img, sp, W / 2, 1530, t, wt("cta", 6) - 0.05, None, 1.5, glow=0.4)


# ================================================================= Bild
def compose(t, fidx=0):
    cam = cam_at(t)
    lk = look_dict(t)
    tint = lk["tint"]
    img, depth = E.render_floor(cam, tint)
    img *= np.array([0.85 + 0.15 * tint[0], 0.85 + 0.15 * tint[1], 0.85 + 0.15 * tint[2]], np.float32)
    E.draw_stands(img, cam, t, tint)
    lines = E.board_lines(cam) + E.goal_lines(cam, 1.0) + E.goal_lines(cam, -1.0)
    for k in range(3):                                           # Schuss-Ringe + Leuchtspuren
        if T_SHOT[k] <= t < T_SHOT[k] + 0.5:
            u = (t - T_SHOT[k]) / 0.5
            rr = 0.6 + 4 * e_out(u, 2)
            ring = [(PUCKS[k]["x"] + rr * math.cos(q), 0.03, PUCKS[k]["z"] + rr * math.sin(q)) for q in np.linspace(0, 2 * math.pi, 48)]
            for seg in E.clip_lines(cam, ring, closed=True):
                lines.append((seg, (160, 230, 255), 6 * (1 - u) + 1, 0.9 * (1 - u)))
        if T_SHOT[k] <= t < T_RW1:
            us = np.linspace(max(T_SHOT[k], t - 0.22), t, 14)
            trail = [puck_pos(k, x) + vec(0, 0.15, 0) for x in us]
            for seg in E.clip_lines(cam, trail):
                lines.append((seg, (120, 220, 255) if t < T_RW0 else (230, 120, 255), 9, 0.9))
        if T_CROSS[k] <= t < T_CROSS[k] + 0.5:                   # Torlinie blitzt beim Überqueren
            u = (t - T_CROSS[k]) / 0.5
            z = fly_pos(k, (T_CROSS[k] - T_SHOT[k]) / FLY)[2]
            gl = [(89.0, 0.03, zz) for zz in np.linspace(z - 6, z + 6, 12)]
            for seg in E.clip_lines(cam, gl):
                lines.append((seg, (255, 255, 255), 10 * (1 - u) + 2, 1.0 - u))
    img = E.add_glow(img, E.stroke_layer(lines))
    E.beams(img, t, tint, 1.2)
    E.particles(img, t, cam, tint)
    img *= E.bottom_shade()
    wa = whip_amount(t)
    if wa > 0.02:
        c0 = cam_at(t - 1 / FPS)
        p = cam.pos + cam.fwd * 20
        a_, _ = c0.proj(p)
        b_, _ = cam.proj(p)
        d = (b_ - a_)[0]
        img = E.motion_blur(img, d[0] * 1.2, d[1] * 1.2)
    # Puck-Figuren
    order = sorted(range(3), key=lambda k: -cam.cam(puck_pos(k, t))[0, 2])
    es = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ec = cairo.Context(es)
    for k in order:
        c = puck_pos(k, t)
        if cam.cam(c)[0, 2] < 1.0:
            continue
        img = E.draw_puck(img, cam, c, lk, mirror=True)
        img = E.draw_puck(img, cam, c, lk)
        if cam.cam(c)[0, 2] < 40:
            lv = np.array([0.0, -0.5]) if T_SHOT[k] <= t < T_RW1 else np.array([0.0, 0.15])
            E.eyes(ec, cam, c, mood(k, t), lv, t, 0.2 + 0.37 * k)
    es.flush()
    eb = np.frombuffer(es.get_data(), np.uint8).reshape(H, W, 4).astype(np.float32) / 255
    img = img * (1 - eb[..., 3:4]) + eb[..., [2, 1, 0]]
    # Hervorhebung als Röntgen-Overlay über den Pucks
    hs = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    hc = cairo.Context(hs)
    for i, (key, k) in enumerate(REVEAL):
        t0 = VO_START[key]
        t1 = VO_START[REVEAL[i + 1][0]] if i + 1 < len(REVEAL) else VO_START["twist"]
        if t0 <= t < t1:
            highlight(hc, cam, k, t, c01((t - t0 - 0.25) / 0.3) * (1 - smooth(t1 - 0.12, t1, t)))
    hs.flush()
    hb = np.frombuffer(hs.get_data(), np.uint8).reshape(H, W, 4).astype(np.float32) / 255
    img = img * (1 - hb[..., 3:4]) + hb[..., [2, 1, 0]]
    for k in range(3):                                           # Funken beim Schuss
        xy, z = cam.proj(start_pos(k))
        E.sparks(img, xy[0, 0], xy[0, 1], t, T_SHOT[k], 14, (160, 230, 255), seed=k + 3, spd=600, life=0.45)
    # Nummern über den Pucks
    ba = (1 - smooth(T_SHOT[0] - 0.1, T_SHOT[0], t)) + c01((t - T_RW1) / 0.2) * (1 - smooth(VO_START["r1"] - 0.1, VO_START["r1"], t))
    puck_badges(img, cam, t, min(1.0, ba), 1.7 if t < T_SHOT[0] else 2.3, 76 if t < T_SHOT[0] else 70)
    # Pointe: Karten
    if VO_START["twist"] - 0.1 <= t < T_CTA + 0.2:
        blur = E.blur_bg(img)
        draw_mini(img, blur, "goal", 290, 1000, t, T_GOALC - 0.1, T_CTA - 0.2)
        draw_mini(img, blur, "icing", 790, 1000, t, T_ICEC - 0.1, T_CTA - 0.2)
    texts(img, t)
    hud(img, t)
    E.brand(img, t)
    # Post
    bright = np.clip(img - 0.78, 0, None)
    sm = cv2.resize(bright, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    img += cv2.resize(cv2.GaussianBlur(sm, (0, 0), 5), (W, H)) * 0.55 + cv2.resize(cv2.GaussianBlur(sm, (0, 0), 16), (W, H)) * 0.4
    impacts = T_SHOT + [T_V[k] for k in range(3)] + [T_LOCK, T_CTA, wt("cta", 4)]
    imp = max([1 - (t - ti) / 0.28 for ti in impacts if 0 <= t - ti < 0.28] + [0.0])
    rw = math.sin(math.pi * c01((t - T_RW0) / (T_RW1 - T_RW0))) if T_RW0 <= t < T_RW1 else 0.0
    ca = int(round(12 * imp ** 1.5 + 16 * wa + 10 * rw))
    if ca > 0:
        img[..., 0] = np.roll(img[..., 0], ca, axis=1)
        img[..., 2] = np.roll(img[..., 2], -ca, axis=1)
    if imp > 0:
        rng = np.random.default_rng(int(t * 1000))
        dx, dy = rng.normal(0, 9 * imp, 2)
        Mx = np.float32([[1.0 + 0.012 * imp, 0, dx - W * 0.006 * imp], [0, 1.0 + 0.012 * imp, dy - H * 0.006 * imp]])
        img = cv2.warpAffine(img, Mx, (W, H), borderMode=cv2.BORDER_REFLECT)
        img += 0.10 * imp ** 3
    if wa > 0.35 or rw > 0.2:                                    # Glitch / VHS
        rng = np.random.default_rng(int(t * 997))
        for _ in range(8):
            y0 = int(rng.integers(0, H - 60))
            hh = int(rng.integers(8, 70))
            img[y0:y0 + hh] = np.roll(img[y0:y0 + hh], int(rng.normal(0, 70 * max(wa, rw))), axis=1)
        if rw > 0.2:
            img[::4] *= 0.75
    img *= E.vignette()
    img += np.random.default_rng(fidx).normal(0, 0.012, (H // 2, W // 2)).repeat(2, 0).repeat(2, 1)[..., None].astype(np.float32)
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


def preview(ts, out):
    ims = [Image.fromarray(compose(float(t), int(float(t) * FPS))) for t in ts]
    cw, ch = W // 3, H // 3
    cols = min(6, len(ims))
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * ch), (40, 40, 40))
    for i, im in enumerate(ims):
        sheet.paste(im.resize((cw, ch), Image.LANCZOS), ((i % cols) * cw, (i // cols) * ch))
    sheet.save(out, quality=88)


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "prev":
    preview(sys.argv[2].split(","), sys.argv[3])


# ================================================================= Ton
SR = 44100


def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(42)
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

    def riser(dur=0.45, vol=0.35):
        x = tt(dur)
        f = 300 + 3200 * (x / dur) ** 2
        return (hp(noise(dur), 2) * 0.6 + np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.25) * (x / dur) ** 2 * vol

    def glitch(vol=0.25):
        x = tt(0.12)
        return np.sign(np.sin(2 * np.pi * 1800 * x)) * (np.sin(2 * np.pi * 35 * x) > 0) * np.exp(-x * 25) * vol

    def boom(vol=0.8):
        x = tt(0.8)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(48 + 90 * np.exp(-x * 14)) / SR) * np.exp(-x * 4.5) * 3) * vol

    def crackle(dur=1.5, vol=0.25):
        x = tt(dur)
        sig = hp(noise(dur), 1) * (rng.random(len(x)) < 0.02) * 4 + hp(noise(dur), 3) * 0.15
        return sig * np.minimum(x / 0.05, 1) * np.clip((dur - x) / 0.3, 0, 1) * vol

    def clink(vol=0.35, f0=2400):
        x = tt(0.3)
        return (np.sin(2 * np.pi * f0 * x) + 0.6 * np.sin(2 * np.pi * f0 * 1.51 * x)) * np.exp(-x * 18) * vol

    def riser(dur=0.45, vol=0.35):
        x = tt(dur)
        f = 300 + 3200 * (x / dur) ** 2
        return (hp(noise(dur), 2) * 0.6 + np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.25) * (x / dur) ** 2 * vol

    def glitch(vol=0.25):
        x = tt(0.12)
        return np.sign(np.sin(2 * np.pi * 1800 * x)) * (np.sin(2 * np.pi * 35 * x) > 0) * np.exp(-x * 25) * vol

    def boom(vol=0.8):
        x = tt(0.8)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(48 + 90 * np.exp(-x * 14)) / SR) * np.exp(-x * 4.5) * 3) * vol

    def rewind_s(dur=0.5, vol=0.4):
        x = tt(dur)
        f = 2600 - 2200 * (x / dur)
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.5 + hp(noise(dur), 3) * 0.3) * np.sin(np.pi * x / dur) * vol

    def whistle(dur=0.6, vol=0.5):
        x = tt(dur)
        f = 2900 + 120 * np.sin(2 * np.pi * 34 * x)
        env = np.minimum(x / 0.02, 1) * np.clip((dur - x) / 0.08, 0, 1)
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.25 * hp(noise(dur), 2)) * env * vol

    def chime(vol=0.4):
        x = tt(0.7)
        return (np.sin(2 * np.pi * 880 * x) + 0.7 * np.sin(2 * np.pi * 1318.5 * x) + 0.4 * np.sin(2 * np.pi * 1760 * x)) * np.exp(-x * 5) * vol

    roots = [55.0, 55.0, 65.41, 49.0]
    for k8 in range(int(DUR / (B / 2))):
        tb = k8 * B / 2
        b = k8 / 2
        pos = b % 4
        if tb > DUR - 0.4 or (T_RW0 <= tb < T_RW1) or (T_LOCK <= tb < VO_START["r1"]):
            continue
        if pos in (0.0, 2.5) or pos == 1.5:
            put_(mus, kick(0.95), tb)
        if pos in (1.0, 3.0):
            put_(mus, clap(0.8), tb)
        put_(mus, hat(0.11 if k8 % 2 == 0 else 0.07), tb, pan=0.3)
        if pos == 0.0:
            put_(mus, sub(roots[int(b // 4) % 4], 2.6 * B), tb)
    put_(sfx, riser(0.6, 0.3), T_SHOT[0] - 0.6)
    for k in range(3):
        put_(sfx, clack(0.9), T_SHOT[k], pan=(k - 1) * 0.4)
        put_(sfx, whoosh(0.5, 0.45), T_SHOT[k] + 0.02, pan=(k - 1) * 0.4)
        put_(sfx, pop(0.3), T_CROSS[k])
    put_(sfx, boom(0.5), T_CROSS[0])
    put_(sfx, rewind_s(T_RW1 - T_RW0, 0.45), T_RW0)
    for j in range(6):
        put_(sfx, tick(0.35), T_LOCK + 0.1 + j * 0.2)
    for key, k in REVEAL:
        put_(sfx, whoosh(0.45, 0.45), VO_START[key] - 0.15)
        put_(sfx, glitch(0.15), VO_START[key] - 0.02)
        if PUCKS[k]["icing"]:
            put_(sfx, whistle(0.65, 0.5), T_V[k] + 0.05)
            put_(sfx, boom(0.7), T_V[k])
        else:
            put_(sfx, chime(0.35), T_V[k])
    put_(sfx, whoosh(0.45, 0.4), T_GOALC - 0.12)
    put_(sfx, whoosh(0.45, 0.4), T_ICEC - 0.12)
    put_(sfx, pop(0.35), T_ICEC + 0.1)
    put_(sfx, boom(0.7), T_CTA)
    put_(sfx, boom(0.5), wt("cta", 4))
    voice = np.zeros(n)
    for k in VO_KEYS:
        tmp = os.path.join(HERE, f"_vo_{k}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "voice", f"reel41_{k}.wav"),
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
    tts_kokoro.synth(VO_LINES, os.path.join(HERE, "voice", "reel41"), speed=1.25)


def _frame(i):
    return compose(i / FPS, i).tobytes()


def main():
    os.chdir(HERE)
    make_audio("audio_icing_quiz.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_icing_quiz.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "19",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
           "-ar", "44100", "-shortest", "-movflags", "+faststart", "reel41_icing.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    with Pool(4) as pool:
        for i, fr in enumerate(pool.imap(_frame, range(nf), chunksize=4)):
            proc.stdin.write(fr)
            if i % 30 == 0:
                print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(0.6, 9999)).save("reel41_thumbnail.jpg", quality=92)
    print("fertig: reel41_icing.mp4")


def remux():
    os.chdir(HERE)
    make_audio("audio_icing_quiz.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "reel41_icing.mp4", "-i", "audio_icing_quiz.wav",
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-af",
                    "loudnorm=I=-14:TP=-1.0:LRA=9", "-ar", "44100", "-shortest", "-movflags", "+faststart",
                    "_tmp_ic.mp4"], check=True)
    os.replace("_tmp_ic.mp4", "reel41_icing.mp4")


if __name__ == "__main__" and (len(sys.argv) == 1 or sys.argv[1] != "prev"):
    if len(sys.argv) > 1 and sys.argv[1] == "audio":
        remux()
    elif len(sys.argv) > 1 and sys.argv[1] == "vo":
        make_voice()
    else:
        main()
