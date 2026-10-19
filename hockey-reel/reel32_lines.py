"""Reel 32: "WHAT DO ALL THESE LINES MEAN?" – jede Linie auf dem Eis in 20 s (Share-/Save-Video, ~20 s).

Warum dieses Thema (Analyse 20.10.): Am meisten geteilt und mit den meisten neuen Followern liefen Erklärungen, die
Gelegenheitsfans live sehen und nicht verstehen (Icing: 10 Shares/1.000 Views, 4 Follower/1.000). Ein "Spickzettel"
für die ganze Eisfläche spricht genau diese Leute an ("send this to someone watching their first game"), wird
gespeichert und führt zu den Serien-Teilen. Hook: ganze Frage riesig ab Bild 0 auf hellem Vollbild, Linien leuchten
sofort nacheinander auf. Ende: Zahl-Frage (1–6) für Kommentare + "Save this".

Fakten (NHL Official Rules 2023–24):
- Mittellinie rot, blaue Linien teilen in drei Zonen (1.5, 1.6). Icing: Schuss aus der eigenen Hälfte über die
  gegnerische Torlinie (81.1). Abseits: Angreifer dürfen nicht vor dem Puck in die Angriffszone (83.1).
- Tor nur, wenn der Puck die Torlinie zwischen den Pfosten komplett überquert ("entirely across", 78.4).
- Alle Bullys auf einem der neun Bullypunkte (76.2).
- Torraum hellblau (1.7). Trapez hinter dem Tor (1.8): Dort (und vor der Torlinie) darf der Goalie den Puck
  spielen, außerhalb hinter der Torlinie = kleine Strafe (27.8).
Look: heller 3D-Studio-Look der Hits (puck3d + Banden/Glas/Tore aus reel28), echte 3D-Kamerafahrten, Kinetic
Typography aus reel31 (Archivo Expanded) mit weißem Halo. Keine Spieler, keine Logos.
Stimme: Kokoro "Michael" (Apache-2.0), 1,1x.
Aufruf: python3 reel32_lines.py vo | audio | prev 1.0,4.2 out.jpg | (ohne Argument: Video)
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
from scipy.ndimage import gaussian_filter

import puck3d as P3
import mesh3d as M3
import reel15_puck as R15
import reel28_emptynet as R28
import reel26_overglass as R26
import reel31_powerplay as M
from reel15_puck import W, H, FPS, c01, sio, e_out, e_in, lerp, proj, projected, px_per_in, stroke_poly, surface, \
    surf_rgba, over

HERE = R15.HERE
SPP = int(os.environ.get("SPP", "8"))
KSUB = int(os.environ.get("KSUB", "10"))
SHUTTER = 0.5 / FPS
INK = (20, 22, 30)
RED = (215, 25, 40)
BLUE = (35, 95, 205)
GREEN = (25, 150, 75)
WHITE = (255, 255, 255)
TEMPO = 1.1

# ================================================================= Timeline aus dem Voiceover
VO_LINES = [
    ("q", "What do all these lines on a hockey rink mean?"),
    ("red", "Red line: shoot it from your half past their goal line? Icing."),
    ("blue", "Blue lines: beat the puck into the zone? Offside."),
    ("goal", "Goal line: the whole puck has to cross."),
    ("dots", "Nine dots: every faceoff happens on one."),
    ("crease", "Blue paint: the goalie's crease."),
    ("trap", "And the trapezoid: the only place behind the net a goalie can play the puck."),
    ("cta", "Which one didn't you know? One to six."),
]
VO_KEYS = [k for k, _ in VO_LINES]
VO_START = {"q": 0.10, "red": 2.29, "blue": 5.32, "goal": 7.99, "dots": 10.03, "crease": 12.57, "trap": 14.12,
            "cta": 18.09}
DUR = 20.4
_K = 1.08 / TEMPO                               # Wortzeiten wurden bei 1,08x gemessen
WT = {k: [v * _K for v in vs] for k, vs in {
    "q": [0.0, 0.1, 0.18, 0.36, 0.54, 0.84, 1.1, 1.14, 1.34, 1.6],
    "red": [0.0, 0.16, 0.4, 0.66, 0.76, 0.88, 1.0, 1.16, 1.44, 1.58, 1.68, 2.34],
    "blue": [0.0, 0.12, 0.4, 0.68, 0.8, 0.96, 1.14, 1.26, 1.84],
    "goal": [0.0, 0.16, 0.46, 0.64, 0.8, 1.04, 1.24, 1.36],
    "dots": [0.0, 0.22, 0.9, 1.06, 1.34, 1.54, 1.82, 2.04],
    "crease": [0.0, 0.12, 0.34, 0.56, 0.88],
    "trap": [0.0, 0.1, 0.16, 1.1, 1.22, 1.38, 1.74, 2.04, 2.22, 2.4, 2.62, 2.86, 3.16, 3.36, 3.48],
    "cta": [0.0, 0.12, 0.26, 0.5, 0.58, 1.08, 1.18, 1.32],
}.items()}


def wt(key, i):
    return VO_START[key] + WT[key][i]


T_ICING = wt("red", 11)
T_OFF = wt("blue", 8)
T_WHOLE, T_CROSS = wt("goal", 3), wt("goal", 7)
T_TRAP_OUT = wt("trap", 12)

# ================================================================= Geometrie (Zoll; x = Länge, z = Breite, Fernende +x oben)
GOAL_X, END_X = 1068.0, 1200.0
GL_Z = 174.0 + math.sqrt(336.0 ** 2 - (336.0 - 132.0) ** 2)     # Torlinie endet an der Eckrundung
DOTS = [(0.0, 0.0)] + [(sx * 240.0, sz * 264.0) for sx in (-1, 1) for sz in (-1, 1)] + \
       [(sx * 828.0, sz * 264.0) for sx in (-1, 1) for sz in (-1, 1)]
TRAP_SIDES = [[(GOAL_X * sx, 132.0 * sz), (END_X * sx, 168.0 * sz)] for sx in (-1, 1) for sz in (-1, 1)]


def P(x, z, y=0.2):
    return np.array([x, y, z], float)


def seg_pts(a, b, n=24, y=0.2):
    return np.array([[lerp(a[0], b[0], u), y, lerp(a[1], b[1], u)] for u in np.linspace(0, 1, n)])


def crease_pts(sx=1):
    ang = math.asin(48.0 / 72.0)
    arc = [(GOAL_X * sx - sx * 72.0 * math.cos(a), 72.0 * math.sin(a)) for a in np.linspace(-ang, ang, 30)]
    return np.array([[x, 0.2, z] for x, z in [(GOAL_X * sx, -48.0)] + arc + [(GOAL_X * sx, 48.0)]])


# ================================================================= Kamera
FULL = (np.array([-1316.0, 4050.0, 0.0]), np.array([60.0, 0.0, 0.0]), 36.0)
SHOTS = [                                        # (Start der Fahrt, Ende der Fahrt, Einstellung)
    (-1.0, 0.0, FULL),
    (VO_START["red"] - 0.25, VO_START["red"] + 0.35, (np.array([-1150.0, 3450.0, 0.0]), np.array([250.0, 0, 0]), 36.0)),
    (VO_START["blue"] - 0.25, VO_START["blue"] + 0.4, (np.array([-260.0, 1750.0, 0.0]), np.array([430.0, 0, 0]), 38.0)),
    (VO_START["goal"] - 0.3, VO_START["goal"] + 0.4, (np.array([872.0, 88.0, -28.0]), np.array([1076.0, 12.0, 0.0]), 44.0)),
    (VO_START["dots"] - 0.3, VO_START["dots"] + 0.35, (np.array([-1316.0, 4150.0, 0.0]), np.array([60.0, 0, 0]), 36.0)),
    (VO_START["crease"] - 0.3, VO_START["crease"] + 0.35, (np.array([760.0, 700.0, 0.0]), np.array([1040.0, 0, 0]), 36.0)),
    (VO_START["trap"] - 0.25, VO_START["trap"] + 0.4, (np.array([880.0, 820.0, 0.0]), np.array([1125.0, 0, 0]), 42.0)),
    (VO_START["cta"] - 0.3, VO_START["cta"] + 0.45, FULL),
]


def drift(shot, u):
    """Langsames Heranfahren innerhalb einer Einstellung (u = Sekunden seit Ankunft)."""
    p, g, f = shot
    k = 1 - 0.035 * (1 - math.exp(-u / 3.0))
    return g + (p - g) * k, g, f


def cam(t):
    i = max(k for k, (a, _, _) in enumerate(SHOTS) if t >= a or k == 0)
    a, b, shot = SHOTS[i]
    if t < b and i > 0:
        pa = SHOTS[i - 1]
        prev = drift(pa[2], a - pa[1])
        s = sio((t - a) / (b - a))
        p, g, f = R28.blend_cam(prev, drift(shot, 0.0), s)
    else:
        p, g, f = drift(shot, t - b)
    return p, g, np.array([0.0, 1.0, 0.0]), f


def cam_row_at(t):
    pos, tgt, up, fov = cam(t)
    r, u, f = P3.look_at(pos, tgt, up)
    return P3.cam_row(pos, r, u, f, fov), float(np.linalg.norm(tgt - pos))


# ================================================================= Puck
def puck_state(t):
    """(Position, sichtbar)"""
    r0, r1 = wt("red", 2), wt("red", 10)                        # Icing: aus eigener Hälfte übers Eis
    if r0 - 0.1 <= t < VO_START["blue"] - 0.2:
        u = e_out(c01((t - r0 - 0.25) / (r1 - r0)), 2)
        a, b = np.array([-560.0, 0.5, -140.0]), np.array([1125.0, 0.5, 150.0])
        return a + (b - a) * u, 1.0
    if VO_START["blue"] - 0.2 <= t < VO_START["goal"] - 0.3:      # Abseits: Puck kommt zu spät
        u = e_out(c01((t - wt("blue", 4)) / 1.4), 2)
        return np.array([lerp(60.0, 360.0, u), 0.5, lerp(80.0, 40.0, u)]), 1.0
    if VO_START["goal"] - 0.3 <= t < VO_START["dots"] - 0.3:      # halb auf der Linie -> komplett drüber
        u = e_out(c01((t - T_CROSS + 0.05) / 0.35), 3)
        return np.array([lerp(GOAL_X, GOAL_X + 3.6, u), 0.5, 0.0]), 1.0
    if VO_START["trap"] - 0.25 <= t < VO_START["cta"] - 0.3:      # Trapez: drinnen ok -> Ecke = Strafe
        u = sio(c01((t - T_TRAP_OUT + 0.35) / 0.55))
        return np.array([lerp(1150.0, 1150.0, u), 0.5, lerp(70.0, 330.0, u)]), 1.0
    return np.array([0.0, -50.0, 0.0]), 0.0


def render3d(t, fidx):
    cams, lens, pk = np.zeros((KSUB, 13)), np.zeros((KSUB, 2)), np.zeros((KSUB, 7))
    for j in range(KSUB):
        tk = t + ((j + 0.5) / KSUB - 0.5) * SHUTTER
        row, focus = cam_row_at(tk)
        cams[j], lens[j] = row, (0.0, focus)
        p, vis = puck_state(tk)
        pk[j] = (p[0], p[1], p[2], 0.7 + 5.0 * tk, vis, 0.0, tk)
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, SPP, fidx + 32, cams, lens, pk, R15.logo_tex(), base, puck, cov)
    return P3.tonemap(base), P3.tonemap(puck), cov


# ================================================================= Overlays auf dem Eis
def poly_ok(row, pts):
    xy, z = proj(row, pts)
    return (xy, z) if (z > 3).all() else (None, None)


def paint_trapezoids(ctx, row):
    """Trapez-Linien fehlen in der Eis-Textur -> hier aufs Eis malen (2 Zoll breit, Regel 1.8)."""
    for a, b in TRAP_SIDES:
        xy, z = poly_ok(row, seg_pts(a, b, 8, 0.05))
        if xy is None:
            continue
        w = float(np.clip(px_per_in(row, z.mean()) * 2.0, 0.8, 8))
        stroke_poly(ctx, xy, (184, 18, 26), 0.85, w)


def glow_line(ctx, row, pts, col, a, w=6.0):
    if a <= 0.01:
        return
    xy, z = poly_ok(row, pts)
    if xy is None:
        return
    for mult, al in ((5.0, 0.10), (2.6, 0.22), (1.0, 1.0)):
        stroke_poly(ctx, xy, col, al * a, w * mult)


def fill_poly(ctx, row, pts, col, a):
    if a <= 0.01:
        return
    xy, z = poly_ok(row, pts)
    if xy is None:
        return
    ctx.set_source_rgba(col[0] / 255, col[1] / 255, col[2] / 255, a)
    ctx.move_to(*xy[0])
    for q in xy[1:]:
        ctx.line_to(*q)
    ctx.close_path()
    ctx.fill()


def ring_at(ctx, row, p, col, a, r_in, w=5.0):
    if a <= 0.01:
        return
    xy, z = poly_ok(row, p + R28.CIRC * r_in)
    if xy is None:
        return
    stroke_poly(ctx, xy, col, a, w)


def pulse(t, t0, dur=0.7):
    """0 -> 1 -> sanft auf 0.45 (Linie bleibt markiert)."""
    if t < t0:
        return 0.0
    u = t - t0
    return c01(u / 0.12) * (0.45 + 0.55 * math.exp(-u / dur))


def scene_end(key):
    i = VO_KEYS.index(key)
    return VO_START[VO_KEYS[i + 1]] - 0.25 if i + 1 < len(VO_KEYS) else DUR


def highlights(ctx, row, t):
    # Hook: alle Linien leuchten ab Bild 0 nacheinander auf
    if t < VO_START["red"]:
        seq = [0.0, 0.22, 0.44, 0.66, 0.88, 1.1]
        def hk(i):
            u = t - seq[i] + 0.1
            return c01(u / 0.1) * (0.35 + 0.65 * math.exp(-max(u, 0) / 0.45)) * (1 - c01((t - 2.0) / 0.3))
        glow_line(ctx, row, seg_pts((0, -500), (0, 500)), RED, hk(0), 5)
        for x in (-300, 300):
            glow_line(ctx, row, seg_pts((x, -500), (x, 500)), BLUE, hk(1), 5)
        for sx in (-1, 1):
            glow_line(ctx, row, seg_pts((GOAL_X * sx, -GL_Z), (GOAL_X * sx, GL_Z)), RED, hk(2), 3)
            fill_poly(ctx, row, crease_pts(sx), (90, 160, 240), 0.5 * hk(4))
            for a, b in TRAP_SIDES:
                glow_line(ctx, row, seg_pts(a, b, 8), RED, hk(5), 3)
        for x, z in DOTS:
            ring_at(ctx, row, P(x, z), RED if x else BLUE, hk(3), 26, 4)
    # 1 Rote Linie + Icing-Weg
    if VO_START["red"] - 0.2 <= t < scene_end("red") + 0.2:
        a = pulse(t, VO_START["red"]) * (1 - c01((t - scene_end("red")) / 0.25))
        glow_line(ctx, row, seg_pts((0, -500), (0, 500)), RED, a, 6)
        p, vis = puck_state(t)
        if vis and t > wt("red", 2):
            pts = np.array([[-560.0, 0.3, -140.0], p + [0, -0.2, 0]])
            R28.path_line(ctx, row, seg_pts((pts[0][0], pts[0][2]), (pts[1][0], pts[1][2]), 30, 0.3), RED,
                          0.9 * (1 - c01((t - scene_end("red")) / 0.25)), 5, [18, 14], t)
            M_ = R28  # Puck-Markierung (Ring), damit der 3-Zoll-Puck in der Totale sichtbar ist
            ring_at(ctx, row, p - [0, 0.3, 0], INK, 0.9, 26, 4)
        fl = pulse(t, T_ICING - 0.05, 0.4) * (1 - c01((t - scene_end("red")) / 0.25))
        glow_line(ctx, row, seg_pts((GOAL_X, -GL_Z), (GOAL_X, GL_Z)), RED, fl, 5)
    # 2 Blaue Linien + Abseits
    if VO_START["blue"] - 0.2 <= t < scene_end("blue") + 0.2:
        a = pulse(t, VO_START["blue"]) * (1 - c01((t - scene_end("blue")) / 0.25))
        for x in (-300, 300):
            glow_line(ctx, row, seg_pts((x, -500), (x, 500)), BLUE, a, 7)
        u = e_out(c01((t - wt("blue", 2)) / 0.9), 2)
        att = P(lerp(140.0, 470.0, u), lerp(-60.0, -30.0, u))
        cr = R28.disc(ctx, row, att, BLUE, a * c01((t - VO_START["blue"] - 0.1) / 0.2), r_in=24.0)
        R28.pulse_ring(ctx, cr, RED, t, T_OFF - 0.05, 0.7)
        p, vis = puck_state(t)
        if vis:
            ring_at(ctx, row, p - [0, 0.3, 0], INK, 0.8, 14, 3)
    # 3 Torlinie (Makro)
    if VO_START["goal"] - 0.2 <= t < scene_end("goal") + 0.2:
        a = pulse(t, VO_START["goal"] + 0.1) * (1 - c01((t - scene_end("goal")) / 0.25))
        glow_line(ctx, row, seg_pts((GOAL_X, -40), (GOAL_X, 40), 40, 0.15), RED, a * 0.9, 4)
    # 4 Neun Bullypunkte
    if VO_START["dots"] - 0.2 <= t < scene_end("dots") + 0.2:
        out = 1 - c01((t - scene_end("dots")) / 0.25)
        for i, (x, z) in enumerate(DOTS_ORDER):
            t0 = VO_START["dots"] + 0.05 + 0.075 * i
            a = pulse(t, t0, 0.5) * out
            ring_at(ctx, row, P(x, z), INK, a, 30, 5)
            li = t - t0
            if 0 <= li < 0.6:
                ring_at(ctx, row, P(x, z), INK, 0.8 * (1 - li / 0.6), 30 + 90 * e_out(li / 0.6), 3)
    # 5 Torraum
    if VO_START["crease"] - 0.2 <= t < scene_end("crease") + 0.2:
        a = pulse(t, VO_START["crease"] + 0.05) * (1 - c01((t - scene_end("crease")) / 0.25))
        fill_poly(ctx, row, crease_pts(1), (60, 140, 245), 0.55 * a)
        glow_line(ctx, row, crease_pts(1), BLUE, a, 4)
    # 6 Trapez
    if VO_START["trap"] - 0.2 <= t < DUR:
        a = pulse(t, wt("trap", 2)) * (1 - c01((t - scene_end("trap")) / 0.3))
        for sx in (1,):
            for sz in (-1, 1):
                glow_line(ctx, row, seg_pts((GOAL_X * sx, 132.0 * sz), (END_X * sx, 168.0 * sz), 10), RED, a, 5)
        inside = [(GOAL_X, -132.0), (END_X, -168.0), (END_X, 168.0), (GOAL_X, 132.0)]
        fill_poly(ctx, row, np.array([[x, 0.1, z] for x, z in inside]), GREEN, 0.20 * a)
        p, vis = puck_state(t)
        if vis and t < scene_end("trap"):
            ok = p[2] < 168.0
            ring_at(ctx, row, p - [0, 0.3, 0], GREEN if ok else RED, 0.95, 9, 4)


DOTS_ORDER = sorted(DOTS, key=lambda d: (-d[0], d[1]))          # von oben nach unten aufploppen

# ================================================================= Abzeichen 1–6 (bleiben stehen -> Spickzettel)
BADGES = [(1, P(0, -440), "red"), (2, P(300, -440), "blue"), (3, P(GOAL_X, -300), "goal"),
          (4, P(-240, -330), "dots"), (5, P(GOAL_X - 95, 0), "crease"), (6, P(1150, 235), "trap")]
_BADGE = {}


def badge_spr(n):
    if n not in _BADGE:
        from PIL import ImageDraw
        s = 3
        r = 30
        im = Image.new("RGBA", (2 * r * s + 8 * s, 2 * r * s + 8 * s), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        c = r * s + 4 * s
        d.ellipse((c - r * s + 3 * s, c - r * s + 6 * s, c + r * s + 3 * s, c + r * s + 6 * s), fill=(0, 0, 0, 50))
        d.ellipse((c - r * s, c - r * s, c + r * s, c + r * s), fill=INK + (255,), outline=WHITE + (255,), width=4 * s)
        im = im.resize((im.width // s, im.height // s), Image.LANCZOS)
        tx = M.text_spr(str(n), "x9", 34, WHITE)
        im.alpha_composite(tx.img, (int(im.width / 2 - tx.ax), int(im.height / 2 - 2 - tx.ay)))
        _BADGE[n] = M.Spr(im, im.width / 2, im.height / 2)
    return _BADGE[n]


def badges(img, row, t):
    for n, p, key in BADGES:
        t0 = VO_START[key] + 0.15
        if t < t0:
            continue
        xy, z = projected(row, p)
        if z <= 3 or not (-40 < xy[0] < W + 40 and -40 < xy[1] < H + 40):
            continue
        s = 0.6 + 0.4 * M.back((t - t0) / 0.35, 2.0)
        if t >= VO_START["cta"]:                                      # am Ende nacheinander nachpulsen
            u = t - (VO_START["cta"] + 0.5 + 0.12 * n)
            s *= 1 + 0.25 * math.exp(-u * 6) * (u > 0)
        M.draw(img, badge_spr(n), xy[0], xy[1], 1.0, s)


# ================================================================= Schrift mit weißem Halo (helles Eis)
_HALO = {}


def halo(spr, sigma=9):
    k = id(spr)
    if k not in _HALO:
        pad = int(sigma * 3)
        a = np.pad(spr.arr[..., 3], pad)
        g = np.clip(gaussian_filter(a, sigma) * 2.2, 0, 1) * 0.92
        arr = np.repeat(g[..., None], 4, -1).astype(np.float32)
        _HALO[k] = (arr, spr.ax + pad, spr.ay + pad)
    return _HALO[k]


def fit(words, fk, size, maxw=960, track=0.02):
    """Schriftgröße so verkleinern, dass die Zeile in maxw Pixel passt."""
    while size > 24:
        w = sum(M.text_spr(t, fk, size, c, track).tw for t, c in words) + 0.32 * size * (len(words) - 1)
        if w <= maxw:
            return size
        size -= 4
    return size


class HLine(M.KLine):
    """KLine aus reel31, aber mit weißem Halo hinter jedem Wort (lesbar auf hellem Eis und Banden)."""

    def __init__(self, words, fk, size, cx, cy, times, t_out, track=0.02, space=0.32, glow=0.55, maxw=960):
        super().__init__(words, fk, fit(words, fk, size, maxw, track), cx, cy, times, t_out, track, space, glow)

    def render(self, dst, t):
        if self.t_out is not None and t > self.t_out + 0.25:
            return
        for i, spr in enumerate(self.sprs):
            if t < self.times[i]:
                continue
            x, y, a, s = self.state(t, i)
            x0, y0, _, _ = self.state(t - M.SHUT, i)
            h, hx, hy = halo(spr)
            M.blit(dst, h, x - hx, y - hy, a * 0.9)
            M.draw(dst, spr, x, y, a, s, x0, y0)


def slam(img, txt, size, col, cx, cy, t, t0, t1):
    """Ergebniswort knallt rein (groß -> normal), mit Halo."""
    if not (t0 <= t < t1 + 0.2):
        return
    p = (t - t0) / 0.28
    s = lerp(1.6, 1.0, M.back(p, 1.4))
    a = c01(p * 3) * (1 - c01((t - t1) / 0.2))
    spr = M.text_spr(txt, "x9", size, col, 0.02)
    h, hx, hy = halo(spr, 12)
    sc = h if abs(s - 1) < 0.01 else None
    if sc is not None:
        M.blit(img, h, cx - hx, cy - hy, a)
    else:
        hi = Image.fromarray((h * 255).astype(np.uint8), "RGBA")
        hi = hi.resize((max(1, int(hi.width * s)), max(1, int(hi.height * s))), Image.BILINEAR)
        M.blit(img, M.to_spr(hi), cx - hx * s, cy - hy * s, a)
    M.draw(img, spr, cx, cy, a, s)


def title(img, t, key, num, name, col, sub=None):
    """Kopfzeile je Linie: '1/6' + Name (+ optional Unterzeile)."""
    t0, t1 = VO_START[key] - 0.05, scene_end(key)
    if not (t0 <= t < t1 + 0.3):
        return
    HLine([(f"{num} / 6", INK)], "in6", 38, 540, 218, [t0], t1, track=0, glow=0).render(img, t)
    HLine([(w, col) for w in name.split()], "x9", 100, 540, 310, [t0 + 0.04 * i for i in range(len(name.split()))],
          t1 + 0.03, glow=0).render(img, t)
    if sub:
        HLine([(sub, INK)], "in6", 44, 540, 400, [t0 + 0.25], t1 + 0.05, track=0, glow=0).render(img, t)


def typography(img, t):
    # Hook: ganze Frage ab Bild 0
    hook = [[("WHAT", INK), ("DO", INK), ("ALL", INK)], [("THESE", INK), ("LINES", RED)], [("MEAN?", INK)]]
    for i, ln in enumerate(hook):
        HLine(ln, "x9", 118, 540, 300 + i * 136, [-0.6] * len(ln), VO_START["red"] - 0.3 + 0.03 * i,
              glow=0).render(img, t)
    title(img, t, "red", 1, "RED LINE", RED, "Center ice")
    slam(img, "ICING", 150, RED, 540, 1000, t, T_ICING - 0.03, scene_end("red"))
    title(img, t, "blue", 2, "BLUE LINES", BLUE, "They make the zones")
    slam(img, "OFFSIDE", 132, BLUE, 540, 1030, t, T_OFF - 0.03, scene_end("blue"))
    title(img, t, "goal", 3, "GOAL LINE", RED, "The WHOLE puck must cross")
    slam(img, "NO GOAL", 128, RED, 540, 1390, t, T_WHOLE - 0.05, T_CROSS)
    slam(img, "GOAL", 160, GREEN, 540, 1390, t, T_CROSS + 0.3, scene_end("goal"))
    title(img, t, "dots", 4, "9 FACEOFF DOTS", INK, "Every faceoff starts on one")
    title(img, t, "crease", 5, "THE CREASE", BLUE, "The goalie's blue paint")
    title(img, t, "trap", 6, "TRAPEZOID", RED, "Goalie may play it in here")
    slam(img, "OK", 140, GREEN, 540, 1060, t, wt("trap", 4), T_TRAP_OUT + 0.15)
    slam(img, "2 MIN", 140, RED, 540, 1060, t, T_TRAP_OUT + 0.45, scene_end("trap"))
    # Ende: Spickzettel + Frage
    c0 = VO_START["cta"] - 0.05
    HLine([("SAVE", RED), ("THIS", RED), ("FOR", INK), ("YOUR", INK), ("NEXT", INK), ("GAME", INK)], "x9", 46, 540,
          214, [c0 + 0.6 + 0.05 * i for i in range(6)], None, glow=0).render(img, t)
    HLine([("WHICH", INK), ("ONE", INK), ("DIDN'T", INK)], "x9", 96, 540, 1180, [c0, c0 + 0.12, c0 + 0.24], None,
          glow=0).render(img, t)
    HLine([("YOU", INK), ("KNOW?", INK)], "x9", 96, 540, 1296, [c0 + 0.5, c0 + 0.6], None, glow=0).render(img, t)
    HLine([("COMMENT", INK), ("1–6", RED)], "x9", 70, 540, 1410, [wt("cta", 5) - 0.05, wt("cta", 5) + 0.1], None,
          glow=0).render(img, t)


# ================================================================= Bild
_VIG = None


def vignette():
    global _VIG
    if _VIG is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = ((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H * 0.48) / (H * 0.7)) ** 2
        _VIG = (1 - 0.22 * np.clip(d, 0, 1.4))[..., None].astype(np.float32)
    return _VIG


def compose(t, fidx=0):
    base, puck, cov = render3d(t, fidx)
    row, _ = cam_row_at(t)
    campos = cam(t)[0]
    p, vis = puck_state(t)
    lo_s, lo_c = surface()
    paint_trapezoids(lo_c, row)
    R28.draw_net_lines(lo_c, row)
    R28.glass_edges(lo_c, row)
    img = over(base, *surf_rgba(lo_s))
    meshes = R28.BOARDS + R28.FRAMES
    if vis > 0:
        import reel25_goalline as G
        meshes = meshes + [G.cyl_mesh(p - np.array([0, 0.5, 0]), 1.5, 1.0, "occluder", group=1)]
    m_rgb, m_a, shadow, plane_a = M3.render(meshes, row, W, H, campos, alpha_by_group=np.array([1.0, 0.0], np.float32),
                                            extra_planes=[(R28.GLASS_ALL, 1.0)], shadow_light=(0.02, 1.0, -0.03))
    img = img * (1 - 0.15 * shadow[..., None])
    hi_s, hi_c = surface()
    highlights(hi_c, row, t)
    img = over(img, *surf_rgba(hi_s))                                # Markierungen liegen unter Puck/Banden
    pa = cov[..., None]
    img = img * (1 - pa) + puck * pa
    img = img * (1 - m_a[..., None]) + m_rgb
    k = (0.30 * plane_a)[..., None]
    img = img * (1 - k) + np.array([0.70, 0.82, 0.94], np.float32) * k
    img = img + (R26.glass_streaks() * plane_a * 0.10)[..., None]
    img = (img * vignette()).astype(np.float32)
    badges(img, row, t)
    typography(img, t)
    img += np.random.default_rng(fidx).normal(0, 0.006, (H, W))[..., None].astype(np.float32)
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


# ================================================================= Ton
SR = 44100


def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(32)
    mus = np.zeros((n, 2))
    sfx = np.zeros((n, 2))
    B = 60 / 118

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
        x = tt(0.4)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(48 + 130 * np.exp(-x * 30)) / SR) * np.exp(-x * 8) * 2.2) * vol

    def clap(vol=0.5):
        x = tt(0.25)
        return hp(noise(0.25), 3) * np.exp(-x * 22) * vol

    def hat(vol=0.08):
        return hp(noise(0.04), 1) * np.exp(-tt(0.04) * 140) * vol

    def pluck(freq, vol=0.1):
        x = tt(0.5)
        return (np.sin(2 * np.pi * freq * x) + 0.3 * np.sin(4 * np.pi * freq * x) * np.exp(-x * 10)) * \
            np.exp(-x * 7) * np.minimum(x / 0.004, 1) * vol

    def sub(freq, dur):
        x = tt(dur)
        return np.tanh(np.sin(2 * np.pi * freq * x) * 2) * np.minimum(x / 0.01, 1) * np.exp(-x * 1.3) * 0.7

    def whoosh(dur=0.5, vol=0.4):
        x = tt(dur)
        return hp(lp(noise(dur), 5), 30) * np.sin(np.pi * x / dur) ** 2 * vol

    def pop(vol=0.4, f=900):
        x = tt(0.09)
        return np.sin(2 * np.pi * np.cumsum(f * (1 + 1.5 * np.exp(-x * 60))) / SR) * np.exp(-x * 45) * vol

    def hit(vol=0.8):
        x = tt(0.5)
        return np.tanh((hp(noise(0.5), 2) * np.exp(-x * 30) + np.sin(2 * np.pi * 70 * x) * np.exp(-x * 10)) * 2) * vol

    def slap(vol=0.7):
        x = tt(0.18)
        return np.tanh((hp(noise(0.18), 1) * np.exp(-x * 60) * 1.4 + np.sin(2 * np.pi * 180 * x) * np.exp(-x * 40))
                       * 2) * vol

    def ding(vol=0.3, f=1318.5):
        x = tt(0.9)
        return (np.sin(2 * np.pi * f * x) + 0.4 * np.sin(2 * np.pi * f * 2 * x)) * np.exp(-x * 5) * vol

    def buzz(vol=0.3):
        x = tt(0.22)
        return lp(np.sign(np.sin(2 * np.pi * 140 * x)), 8) * np.exp(-x * 6) * vol

    chords = [(220.0, 277.18, 329.63), (246.94, 293.66, 369.99), (185.0, 220.0, 277.18), (196.0, 246.94, 293.66)]
    arp = [0, 2, 1, 2, 0, 2, 1, 2]
    for k8 in range(int(DUR / (B / 2))):
        tb = k8 * B / 2
        b = k8 / 2
        if tb > DUR - 0.5:
            continue
        ch = chords[int(b // 4) % 4]
        if b % 1 == 0:
            put_(mus, kick(0.7), tb)
        if b % 2 == 1:
            put_(mus, clap(0.35), tb)
        put_(mus, hat(0.07 if k8 % 2 else 0.1), tb, pan=0.3)
        put_(mus, pluck(ch[arp[k8 % 8]] * 2, 0.08), tb, pan=0.4 * math.sin(k8))
        if b % 4 == 0:
            put_(mus, sub(ch[0] / 4, 4 * B), tb)
    for i in range(6):                                                 # Hook: Linien leuchten auf
        put_(sfx, pop(0.25, 700 + 120 * i), 0.22 * i)
    for key in ("red", "blue", "goal", "dots", "crease", "trap", "cta"):
        put_(sfx, whoosh(0.26, 0.22), VO_START[key] - 0.3)            # kurz: nicht über dem Satzende davor
        put_(sfx, pop(0.25, 950), VO_START[key] - 0.1)                  # Abzeichen (nicht auf dem Wort)
    put_(sfx, slap(0.7), wt("red", 2) + 0.25)
    put_(sfx, buzz(0.3), T_ICING + 0.62)                                # erst nach dem Wort "icing"
    put_(sfx, hit(0.5), T_OFF + 0.4)
    put_(sfx, buzz(0.25), T_WHOLE + 0.05)
    put_(sfx, ding(0.35), T_CROSS + 0.3)
    for i in range(9):
        put_(sfx, pop(0.22, 800 + 60 * i), VO_START["dots"] + 0.05 + 0.075 * i)
    put_(sfx, ding(0.25, 1046.5), wt("trap", 4))
    put_(sfx, buzz(0.3), T_TRAP_OUT + 0.45)
    for i in range(6):
        put_(sfx, pop(0.2, 900 + 80 * i), VO_START["cta"] + 0.5 + 0.12 * (i + 1))
    voice = np.zeros(n)
    for k in VO_KEYS:
        tmp = os.path.join(HERE, f"_vo_{k}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "voice", f"reel32_{k}.wav"),
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
    duck = 1 - 0.82 * np.clip(venv / 0.06, 0, 1)
    sduck = 1 - 0.5 * np.clip(venv / 0.06, 0, 1)
    mus /= np.max(np.abs(mus)) + 1e-9
    sfx /= np.max(np.abs(sfx)) + 1e-9
    mix = mus * 0.32 * duck[:, None] + sfx * 0.45 * sduck[:, None] + voice[:, None] * 1.0
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
    tts_kokoro.synth(VO_LINES, os.path.join(HERE, "voice", "reel32"), speed=1.2)


def check_vo():
    with open(os.path.join(HERE, "voice", "reel32_timing.json")) as f:
        vo_dur = {k: v / TEMPO for k, v in json.load(f).items()}
    for i, k in enumerate(VO_KEYS):
        nxt = VO_START[VO_KEYS[i + 1]] if i + 1 < len(VO_KEYS) else DUR - 0.2
        if VO_START[k] + vo_dur[k] > nxt + 0.3:
            print(f"Warnung: Satz {k} zu lang ({VO_START[k] + vo_dur[k]:.2f} > {nxt:.2f})")


def remux():
    os.chdir(HERE)
    make_audio("audio_lines.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "reel32_lines.mp4", "-i", "audio_lines.wav", "-map", "0:v",
                    "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
                    "-ar", "44100", "-shortest", "-movflags", "+faststart", "_tmp_lines.mp4"], check=True)
    os.replace("_tmp_lines.mp4", "reel32_lines.mp4")


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
    make_audio("audio_lines.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_lines.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
           "-ar", "44100", "-shortest", "-movflags", "+faststart", "reel32_lines.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(0.5, 9999)).save("reel32_thumbnail.jpg", quality=92)
    print("fertig: reel32_lines.mp4")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "vo":
        make_voice()
    elif len(sys.argv) > 1 and sys.argv[1] == "audio":
        remux()
    elif len(sys.argv) > 1 and sys.argv[1] == "prev":
        preview(sys.argv[2].split(","), sys.argv[3])
    else:
        main()
