"""Reel 24: NHL RULES EXPLAINED – PART 3: OFFSIDE (3D-Erklärvideo mit Voiceover, 15,6 s, weißer Studio-Look).

Fakten (NHL-Regel 83.1): Der Puck muss die blaue Linie komplett überqueren, bevor ein Angreifer mit BEIDEN
Schlittschuhen komplett darüber ist – sonst Abseits. Es zählen nur die Schlittschuhe, nicht der Schläger.
Onside ist, wer mit einem Schlittschuh die Linie berührt oder auf seiner Seite ist, wenn der Puck die Linie
komplett überquert. Seit Januar 2021 (Interpretation der NHL): Ein Schlittschuh in der Luft gilt als onside,
solange er die Ebene über der Vorderkante der Linie noch nicht durchbrochen hat.
Blaue Linie im Renderer: x = 294–306 (12 Zoll), Vorderkante zur Angriffszone = 306.
Stimme: Kokoro "Michael" (tts_kokoro.py, Apache-2.0), Sätze einzeln, 1,08x.
Aufruf: python3 reel24_offside.py -> reel24_offside.mp4
"""
import json
import math
import os
import subprocess
import time
import wave

import numpy as np
from PIL import Image

import puck3d as P3
import reel15_puck as R15
import reel18_dangle as R18
import reel22_trapezoid as R22
from reel15_puck import (W, H, FPS, SPP, KSUB, SHUTTER, c01, smooth, sio, e_out, e_in, lerp, blend_up, line_img,
                         reveal, put, proj, projected, px_per_in, stroke_poly, surface, surf_rgba, over, GOAL_X)
from reel22_trapezoid import fill_poly, token, puck_marker, whistle_ring, slam
from reel18_dangle import vignette

HERE = R15.HERE
INK, ORANGE = R15.INK, R15.ORANGE
RED = (225, 30, 40)
GREEN = (30, 160, 80)
BLUE = (40, 110, 210)
LINE_BLUE = (40, 95, 200)
HALO = (255, 255, 255)
UP = np.array([0.0, 1.0, 0.0])
TEMPO = 1.08

# ================================================================= Timeline aus dem Voiceover
VO_KEYS = ["q", "puck", "skates", "call", "stick", "line", "air", "cta"]
VO_START = {"q": 0.10, "puck": 1.45, "skates": 3.35, "call": 4.82, "stick": 6.25, "line": 8.05, "air": 9.75,
            "cta": 13.4}
with open(os.path.join(HERE, "voice", "reel24_timing.json")) as f:
    VO_DUR = {k: v / TEMPO for k, v in json.load(f).items()}
DUR = 15.6


def word(key, t_word):
    """Zeitpunkt eines Worts im Mix (Wortzeit im Roh-WAV laut Spracherkennung)."""
    return VO_START[key] + t_word / TEMPO


T_PUCK1 = word("puck", 1.04)          # "first" – Puck überquert die Linie (legal)
T_REW0, T_REW1 = 3.02, 3.3
T_IN2 = word("skates", 0.60)          # "in" – Angreifer 2 komplett in der Zone
T_PUCK2 = 4.78                        # Puck überquert die Linie -> Pfiff
T_DIVE0, T_DIVE1 = 5.45, 6.2          # Sturzflug in die Nahaufnahme (Videobeweis)
T_ONLY = word("stick", 1.06)          # "only skates"
T_V3 = 7.85                           # Schlittschuh rutscht auf die Linie
T_ON1 = word("line", 1.22)            # "onside"
T_V4 = 9.6                            # Schlittschuh hebt ab
T_PLANE = word("air", 1.30)           # "a skate in the air"
T_ON2 = word("air", 2.64)             # "onside"
T_OUT0, T_OUT1 = 13.05, 13.45         # Weißblitz, Schnitt zurück in die Gesamtansicht
T_CUT = 13.25
LEAD = 306.0                          # Vorderkante der blauen Linie
SQ_X = 380.0
SPEED1, SPEED2 = 300.0, 240.0


# ================================================================= Szene: Positionen
def frz(t, t_stop, dur=0.3):
    """Zeit, die nach dem Pfiff weich anhält."""
    if t <= t_stop:
        return t
    u = min(t - t_stop, dur)
    return t_stop + u - u * u / (2 * dur)


def rew(t):
    """Im Rewind läuft Szene 1 schnell rückwärts."""
    if T_REW0 <= t < T_REW1:
        return T_REW0 - (T_REW0 - 1.5) * (t - T_REW0) / (T_REW1 - T_REW0)
    return t


def puck_top(t):
    t = max(rew(t), 1.5)
    if t < T_REW1:                                            # Szene 1: Puck zuerst (legal)
        s = t - 1.5
        return np.array([LEAD + 1.5 - SPEED1 * (T_PUCK1 - 1.5) + SPEED1 * s, 0.5, -90 + 10 * s])
    s = frz(t, T_PUCK2 + 0.03) - T_PUCK2                      # Szene 2: Abseits
    return np.array([LEAD + 1.5 + SPEED2 * s, 0.5, -90 + 8 * s])


def players_top(t):
    """(A1, A2, D1, D2) in der Draufsicht."""
    t = max(rew(t), 1.5)
    if t < T_REW1:
        s = t - 1.5
        p = puck_top(t)
        a1 = p + np.array([-34.0, 0, -26.0])
        a2 = np.array([LEAD + 20 - 280 * (T_PUCK1 + 0.17 - 1.5) + 280 * s, 0, 140 - 6 * s])
        d1 = np.array([560 + 50 * s, 0, -170 + 10 * s])
        d2 = np.array([590 + 45 * s, 0, 175 - 8 * s])
        return a1, a2, d1, d2
    tf = frz(t, T_PUCK2 + 0.03)
    p = puck_top(t)
    a1 = p + np.array([-34.0, 0, -26.0])
    a2 = np.array([LEAD + 14 + 300 * (tf - T_IN2), 0, 140 - 12 * (tf - T_IN2)])
    s = tf - T_REW1
    d1 = np.array([560 + 45 * s, 0, -170 + 10 * s])
    d2 = np.array([590 + 40 * s, 0, 175 - 8 * s])
    return a1, a2, d1, d2


# Nahaufnahme: klassische Videobeweis-Kamera an der Bande, Blick entlang der blauen Linie (Zone rechts)
CU_Z = 120.0
CU_TGT = np.array([LEAD + 1.0, 8.0, CU_Z])
CU_POS = np.array([LEAD - 40.0, 38.0, CU_Z + 158.0])
NEAR_Z, FAR_Z = CU_Z + 7.0, CU_Z - 7.0
PUCK_Z = CU_Z + 26.0


def ease(t, a, b):
    return sio(c01((t - a) / (b - a)))


def skates_cu(t):
    """[(x-mitte, z, lift)] für den kamerafernen und den kameranahen Schlittschuh (Fahrtrichtung +x)."""
    far_x, near_x, lift = 325.0, 312.5, 0.0
    near_x += (302.0 - near_x) * ease(t, T_V3, T_V3 + 0.55)       # Variante 3: zurück auf die Linie
    u4 = ease(t, T_V4, T_V4 + 0.6)                                 # Variante 4: hebt über der Linie ab
    near_x += (300.0 - near_x) * u4
    lift = 4.5 * u4
    return [(far_x, FAR_Z, 0.0), (near_x, NEAR_Z, lift)]


def puck_cu(t):
    if t < T_V3:
        return np.array([258.0 + 26 * e_out(c01((t - T_DIVE0) / 2.4), 2), 0.5, PUCK_Z])
    if t < T_V4:
        return np.array([284.0 + (LEAD + 3.5 - 284.0) * ease(t, T_V3 + 0.2, T_ON1 - 0.05), 0.5, PUCK_Z])
    return np.array([286.0 + (LEAD + 3.5 - 286.0) * ease(t, T_PLANE - 0.3, T_ON2 - 0.05), 0.5, PUCK_Z])


def in_cu(t):
    return T_DIVE0 + 0.35 <= t < T_CUT


def puck_at(t):
    if t < T_DIVE0 + 0.35:
        return puck_top(t)
    if t < T_CUT:
        return puck_cu(t)
    return np.array([LEAD + 160.0, 0.5, -40.0])


# ================================================================= Kamera
TOP_T = np.array([SQ_X, 0.0, 0.0])
TOP_H = 3300.0
T_CRANE0, T_CRANE1 = 1.45, 2.2
HERO_P0 = np.array([-1450.0, 1150.0, -330.0])
HERO_P1 = np.array([-1320.0, 1060.0, -200.0])
HERO_TGT = np.array([520.0, 0.0, 0.0])
END_POS = np.array([-1400.0, 1080.0, 260.0])
END_TGT = np.array([620.0, 0.0, 0.0])


def hook_cam(t):
    u = e_out(c01(t / T_CRANE0), 2)
    return HERO_P0 + (HERO_P1 - HERO_P0) * u, HERO_TGT, 38.0


def top_cam(t):
    return TOP_T + np.array([-0.5, TOP_H, 0.0]), TOP_T, 30.0


def blend_cam(a, b, s):
    """Kamerafahrt zwischen zwei Einstellungen (Abstand logarithmisch, Richtung über die Kugel)."""
    pa, ta, fa = a
    pb, tb, fb = b
    tgt = ta + (tb - ta) * s
    ra, rb = float(np.linalg.norm(pa - ta)), float(np.linalg.norm(pb - tb))
    r = math.exp(lerp(math.log(ra), math.log(rb), s))
    da, db = (pa - ta) / ra, (pb - tb) / rb
    d = da + (db - da) * s
    d /= np.linalg.norm(d)
    return tgt + d * r, tgt, fa + (fb - fa) * s


def cam(t):
    """(pos, tgt, up, fov)"""
    if t < T_CRANE0:
        p, g, f = hook_cam(t)
    elif t < T_CRANE1:
        p, g, f = blend_cam(hook_cam(T_CRANE0), top_cam(t), sio((t - T_CRANE0) / (T_CRANE1 - T_CRANE0)))
    elif t < T_DIVE0:
        p, g, f = top_cam(t)
    elif t < T_DIVE1:
        s = (t - T_DIVE0) / (T_DIVE1 - T_DIVE0)
        p, g, f = blend_cam(top_cam(t), (CU_POS, CU_TGT, 36.0), e_in(s, 2) * 0.35 + e_out(s, 3) * 0.65)
    elif t < T_OUT0:
        u = (t - T_DIVE1) / (T_OUT0 - T_DIVE1)              # langsame Fahrt in der Nahaufnahme
        p, g, f = CU_POS + np.array([10.0, -6.0, 14.0]) * u, CU_TGT, 36.0
    elif t < T_CUT:
        p, g, f = CU_POS + np.array([10.0, -6.0, 14.0]), CU_TGT, 36.0
    else:
        u = (t - T_CUT) / (DUR - T_CUT)
        p, g, f = END_POS + np.array([-160.0, 120.0, -60.0]) * (1 - e_out(u, 3)), END_TGT, 36.0
    d = (p - g) / np.linalg.norm(p - g)
    el = math.degrees(math.asin(max(-1.0, min(1.0, d[1]))))
    return p, g, blend_up(min(el, 89.9)), f


def cam_row_at(t):
    pos, tgt, up, fov = cam(t)
    r, u, f = P3.look_at(pos, tgt, up)
    return P3.cam_row(pos, r, u, f, fov), float(np.linalg.norm(tgt - pos))


def seg(t):
    """Bewegungsunschärfe nicht über Schnitte hinweg (Puck springt beim Rewind)."""
    for a, b in ((0.0, T_REW0), (T_REW0, T_REW1), (T_REW1, T_DIVE0 + 0.35), (T_DIVE0 + 0.35, T_CUT), (T_CUT, DUR)):
        if a <= t < b:
            return a, b
    return 0.0, DUR


def render3d(t, fidx):
    lo, hi = seg(t)
    cams, lens, pk = np.zeros((KSUB, 13)), np.zeros((KSUB, 2)), np.zeros((KSUB, 7))
    for j in range(KSUB):
        tk = min(max(t + ((j + 0.5) / KSUB - 0.5) * SHUTTER, lo), hi - 1e-4)
        row, focus = cam_row_at(tk)
        cams[j], lens[j] = row, (0.0, focus)
        p = puck_at(tk)
        pk[j] = (p[0], p[1], p[2], R18.G.THETA0 + 6 * tk, 1.0, 0.0, tk)
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, SPP, fidx + 24, cams, lens, pk, R15.logo_tex(), base, puck, cov)
    return P3.tonemap(base), P3.tonemap(puck), cov


# ================================================================= Overlays: Draufsicht
def line_band(ctx, row, x0, x1, col, a, zr=None):
    """Fläche zwischen x0 und x1 über die ganze Breite (oder zr)."""
    if a <= 0:
        return
    za, zb = zr if zr else (-R22.board_z(abs(x0)) + 2, R22.board_z(abs(x0)) - 2)
    pts = np.array([[x0, 0.1, za], [x1, 0.1, za], [x1, 0.1, zb], [x0, 0.1, zb]])
    xy, z = proj(row, pts)
    if (z < 3).any():
        return
    fill_poly(ctx, xy, col, a)


def edge_glow(ctx, row, x, col, a, zr=None, width_in=2.5):
    if a <= 0:
        return
    za, zb = zr if zr else (-R22.board_z(abs(x)) + 2, R22.board_z(abs(x)) - 2)
    zs = np.linspace(za, zb, 50)
    pts = np.stack([np.full_like(zs, x), np.full_like(zs, 0.12), zs], 1)
    xy, z = proj(row, pts)
    if (z < 3).any():
        return
    w = float(np.clip(px_per_in(row, z.mean()) * width_in, 2.5, 26))
    stroke_poly(ctx, xy, col, 0.25 * a, w * 4)
    stroke_poly(ctx, xy, col, 0.95 * a, w)


def zone_shade(ctx, row, a):
    if a <= 0:
        return
    pts = [(x, R22.board_z(x)) for x in np.linspace(LEAD, R22.END_X, 30)]
    pts += [(x, -R22.board_z(x)) for x in np.linspace(R22.END_X, LEAD, 30)]
    xy, z = proj(row, R22.poly3(pts))
    if (z < 3).any():
        return
    fill_poly(ctx, xy, BLUE, 0.10 * a)


def dash_arrow(ctx, row, pts, t, col, a):
    if a <= 0:
        return
    pts = np.asarray(pts, float)
    xy, z = proj(row, pts)
    if (z < 3).any():
        return
    ctx.set_dash([22, 16], -t * 90)
    stroke_poly(ctx, xy, col, 0.9 * a, 6)
    ctx.set_dash([])
    d = xy[-1] - xy[-2]
    d /= np.linalg.norm(d) + 1e-9
    n = np.array([-d[1], d[0]])
    tip = xy[-1]
    fill_poly(ctx, np.array([tip + d * 14, tip - d * 22 + n * 18, tip - d * 22 - n * 18]), col, 0.9 * a)


def trail(ctx, row, t, t0, fn):
    if t <= t0 + 0.02:
        return
    ts = np.linspace(t0, t, 40)
    pts = np.array([fn(x) for x in ts])
    pts[:, 1] = 0.1
    xy, z = proj(row, pts)
    if (z < 3).any():
        return
    stroke_poly(ctx, xy, ORANGE, 0.18, 22)
    stroke_poly(ctx, xy, ORANGE, 0.85, 7)


def letter_tokens(L, row, items):
    for p, s_, col in items:
        xy, z = projected(row, p)
        if z <= 0:
            continue
        gi = line_img(s_, 28, 900, col)
        put(L, gi, xy[0] - gi.width / 2, xy[1] - gi.height / 2)


# ================================================================= Overlays: Nahaufnahme (Schlittschuhe)
LIGHT = np.array([0.35, 1.0, -0.45])
LIGHT /= np.linalg.norm(LIGHT)
BOOT = (30, 31, 37)
HOLDER = (236, 236, 240)
STEEL = (168, 174, 186)
SOCK = ORANGE


# Seitenprofile (u nach vorn, y nach oben), Zoll
BOOT_P = np.array([(5.4, 3.0), (5.9, 3.6), (5.8, 4.4), (5.0, 5.1), (2.2, 6.0), (0.8, 7.6), (0.4, 10.6),
                   (-3.4, 10.8), (-3.9, 9.2), (-4.7, 6.4), (-4.9, 4.2), (-4.5, 3.0)])
HOLDER_P = np.array([(-4.4, 3.0), (5.1, 3.0), (4.5, 1.0), (-3.9, 1.0)])
BLADE_P = np.array([(-4.9, 0.25), (-5.6, 0.75), (-4.9, 1.05), (5.1, 1.05), (5.8, 0.7), (5.3, 0.1), (-4.2, 0.0)])


def extrude(profile, cx, cz, lift, width):
    """Profil (u, y) entlang z extrudieren -> (Seitenflächen, Kappe vorn, Kappe hinten)."""
    z0, z1 = cz - width / 2, cz + width / 2
    P = [(cx + u, lift + y) for u, y in profile]
    n = len(P)
    faces = []
    for i in range(n):
        (xa, ya), (xb, yb) = P[i], P[(i + 1) % n]
        faces.append(np.array([[xa, ya, z0], [xb, yb, z0], [xb, yb, z1], [xa, ya, z1]]))
    cap1 = np.array([[x, y, z1] for x, y in P])
    cap0 = np.array([[x, y, z0] for x, y in P][::-1])
    return faces + [cap1, cap0]


def skate_faces(cx, cz, lift):
    """(Flächen, Streifen): Streifen werden nach dem Bein gezeichnet."""
    out, bands = [], []
    for prof, wd, col in ((BLADE_P, 0.3, STEEL), (HOLDER_P, 1.1, HOLDER), (BOOT_P, 3.8, BOOT)):
        out += [(f, col) for f in extrude(prof, cx, cz, lift, wd)]
    # Unterschenkel mit Stutzen (Zylinder) + weißer Streifen
    lx, ly = cx - 1.6, lift + 10.6
    for y0, y1, r, col, dst in ((ly, ly + 60.0, 2.9, SOCK, out), (ly + 5.0, ly + 7.5, 2.9, (246, 246, 246), bands)):
        ring = [(lx + r * math.cos(q), cz + r * math.sin(q)) for q in np.linspace(0, 2 * math.pi, 29)[:-1]]
        for i in range(len(ring)):
            (xa, za), (xb, zb) = ring[i], ring[(i + 1) % len(ring)]
            dst.append((np.array([[xa, y0, za], [xb, y0, zb], [xb, y1, zb], [xa, y1, za]]), col))
    return out, bands


def shade(face, col, campos):
    n = np.cross(face[1] - face[0], face[2] - face[0])
    nn = np.linalg.norm(n)
    if nn < 1e-9:
        return None
    n /= nn
    ctr = face.mean(0)
    if np.dot(n, campos - ctr) < 0:                              # Rückseite
        return None
    k = 0.66 + 0.4 * max(0.0, float(np.dot(n, LIGHT)))
    return tuple(int(min(255, ch * k)) for ch in col)


def draw_skates(ctx, row, t, campos):
    sk = skates_cu(t)
    for cx, cz, lift in sk:                                         # Schatten
        q = np.array([[cx - 5.6, 0.05, cz - 2.2], [cx + 5.8, 0.05, cz - 2.2], [cx + 5.8, 0.05, cz + 2.2],
                      [cx - 5.6, 0.05, cz + 2.2]])
        q[:, 0] += lift * 0.3
        xy, z = proj(row, q)
        if (z > 1).all():
            fill_poly(ctx, xy, (20, 24, 34), 0.22 / (1 + lift * 0.15))
    order = sorted(sk, key=lambda s_: -abs(s_[1] - campos[2]))      # ferner Schlittschuh zuerst
    for cx, cz, lift in order:
        faces, bands = skate_faces(cx, cz, lift)
        faces.sort(key=lambda fc: -float(np.linalg.norm(fc[0].mean(0) - campos)))
        for f, col in faces + bands:
            sc = shade(f, col, campos)
            if sc is None:
                continue
            xy, z = proj(row, f)
            if (z < 1).any():
                continue
            fill_poly(ctx, xy, sc, 1.0)
            ctx.set_source_rgba(sc[0] / 255, sc[1] / 255, sc[2] / 255, 1.0)    # Nähte schließen
            ctx.set_line_width(1.2)
            ctx.move_to(*xy[0])
            for q in xy[1:]:
                ctx.line_to(*q)
            ctx.close_path()
            ctx.stroke()


STICK_Z = FAR_Z - 9.0


def draw_stick(ctx, row, a):
    if a <= 0:
        return
    blade = np.array([[281.0, 0.1, STICK_Z], [293.0, 0.1, STICK_Z], [293.0, 3.0, STICK_Z], [281.5, 3.4, STICK_Z]])
    xy, z = proj(row, blade)
    if (z > 1).all():
        fill_poly(ctx, xy, (22, 22, 26), a)
    shaft = np.array([[292.0, 2.0, STICK_Z], [313.0, 44.0, CU_Z - 3.0]])
    xy, z = proj(row, shaft)
    if (z > 1).all():
        stroke_poly(ctx, xy, (40, 40, 46), a, float(np.clip(px_per_in(row, z.mean()) * 1.2, 3, 40)))


def plane_wall(ctx, row, a):
    if a <= 0:
        return
    z0, z1 = CU_Z - 24.0, CU_Z + 34.0
    h = 22.0 * e_out(a, 3)
    q = np.array([[LEAD, 0.1, z0], [LEAD, 0.1, z1], [LEAD, h, z1], [LEAD, h, z0]])
    xy, z = proj(row, q)
    if (z < 1).any():
        return
    fill_poly(ctx, xy, LINE_BLUE, 0.15 * a)
    stroke_poly(ctx, xy[1:3], LINE_BLUE, 0.85 * a, 4)
    stroke_poly(ctx, xy[2:4], LINE_BLUE, 0.85 * a, 4)


def review_ui(L, ctx, t):
    a = smooth(T_DIVE1 - 0.15, T_DIVE1 + 0.1, t) * (1 - smooth(T_OUT0, T_OUT0 + 0.25, t))
    if a <= 0:
        return
    m, ln = 70, 70
    ctx.set_source_rgba(INK[0] / 255, INK[1] / 255, INK[2] / 255, 0.75 * a)
    ctx.set_line_width(5)
    for (x, y, dx, dy) in ((m, 300, 1, 1), (W - m, 300, -1, 1), (m, 1560, 1, -1), (W - m, 1560, -1, -1)):
        ctx.move_to(x, y + dy * ln)
        ctx.line_to(x, y)
        ctx.line_to(x + dx * ln, y)
        ctx.stroke()
    blink = 1.0 if (t * 2) % 1 < 0.6 else 0.25
    ctx.set_source_rgba(RED[0] / 255, RED[1] / 255, RED[2] / 255, a * blink)
    ctx.arc(m + 34, 352, 10, 0, 2 * math.pi)
    ctx.fill()
    reveal(L, line_img("VIDEO REVIEW", 34, 850, INK, track=6), m + 58, 352, a, 0.0, anchor="l")
    tc = f"00:0{int(4 + (t - T_DIVE1) * 0.25)}:{int((t * 30) % 60):02d}"
    reveal(L, line_img(tc, 30, 700, INK, track=2), W - m - 10, 352, a, 0.0, anchor="r")


# ================================================================= Texte
def label_at(L, row, p, txt, col, dx, dy, a, size=40):
    if a <= 0:
        return
    xy, z = projected(row, p)
    if z <= 0:
        return
    im = line_img(txt, size, 850, col, track=4)
    reveal(L, im, min(max(xy[0] + dx, 40 + im.width / 2), W - 40 - im.width / 2), xy[1] + dy, a)


def texts(L, t, row):
    A = VO_START
    if t < T_CRANE0 + 0.1:
        for txt, cy, size in (("WHAT IS", 330, 130), ("OFFSIDE?", 480, 178)):
            im = R18.word_img(txt, size, INK, HALO)
            put(L, im, W / 2 - im.width / 2, cy - im.height / 2)
        reveal(L, line_img("NHL RULES EXPLAINED  ·  PART 3", 34, 800, ORANGE, track=8), W / 2, 220, 1.0,
               smooth(T_CRANE0 - 0.15, T_CRANE0 + 0.05, t))
    top = T_CRANE1 - 0.2 <= t < T_DIVE0
    if top:
        fade = 1 - smooth(T_DIVE0 - 0.25, T_DIVE0, t)
        label_at(L, row, np.array([LEAD, 0, -R22.board_z(LEAD) + 120]), "BLUE LINE", LINE_BLUE, 0, -46,
                 smooth(T_CRANE1, T_CRANE1 + 0.2, t) * fade, 38)
        label_at(L, row, np.array([1000.0, 0, 0]), "THEIR ZONE", BLUE, 0, 0,
                 smooth(T_CRANE1 + 0.1, T_CRANE1 + 0.3, t) * fade * (1 - smooth(T_REW0 - 0.1, T_REW0, t)), 44)
    slam(L, "PUCK FIRST.", 120, GREEN, W / 2, 560, t, T_PUCK1 + 0.02, T_REW0)
    if T_REW0 <= t < T_REW1:
        reveal(L, line_img("<<  REWIND", 60, 900, INK, track=10), W / 2, 560, 1.0)
    slam(L, "OFFSIDE.", 190, RED, W / 2, 470, t, T_PUCK2 + 0.03, T_DIVE0 + 0.1)
    # Nahaufnahme
    if T_DIVE1 - 0.05 <= t < T_OUT0:
        slam(L, "OFFSIDE.", 120, RED, W / 2, 470, t, T_DIVE1 - 0.05, T_V3 + 0.1, s0=1.0)
        slam(L, "STICK DOESN'T COUNT", 64, INK, W / 2, 1420, t, A["stick"] + 0.1, T_ONLY)
        slam(L, "ONLY SKATES.", 104, INK, W / 2, 1420, t, T_ONLY, T_V3 + 0.1)
        slam(L, "ON THE LINE", 64, INK, W / 2, 1420, t, T_V3 + 0.55, T_ON1)
        slam(L, "ONSIDE.", 150, GREEN, W / 2, 470, t, T_ON1, T_V4 + 0.1)
        slam(L, "SINCE 2021:", 64, INK, W / 2, 1360, t, A["air"] + 0.05, T_OUT0)
        slam(L, "SKATE IN THE AIR", 76, INK, W / 2, 1450, t, T_PLANE, T_OUT0)
        slam(L, "ONSIDE.", 150, GREEN, W / 2, 470, t, T_ON2, T_OUT0)
    if t >= T_CUT:
        slam(L, "WHICH RULE", 120, INK, W / 2, 330, t, A["cta"])
        slam(L, "SHOULD I EXPLAIN", 92, INK, W / 2, 455, t, A["cta"] + 0.25)
        slam(L, "NEXT?", 150, ORANGE, W / 2, 580, t, A["cta"] + 0.5)
        if t >= A["cta"] + 0.8:
            reveal(L, line_img("COMMENT BELOW  ·  FOLLOW FOR PART 4", 34, 800, INK, track=6), W / 2, 700,
                   c01((t - A["cta"] - 0.8) / 0.25))


# ================================================================= Bild
def compose(t, fidx):
    base, puck, cov = render3d(t, fidx)
    row, _ = cam_row_at(t)
    campos = cam(t)[0]
    lo_s, lo_c = surface()
    hi_s, hi_c = surface()
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cu = in_cu(t)
    if not cu:
        zone_shade(lo_c, row, smooth(VO_START["puck"] + 0.2, VO_START["puck"] + 0.5, t))
        edge_glow(lo_c, row, LEAD, LINE_BLUE, smooth(VO_START["puck"], VO_START["puck"] + 0.3, t) * 0.9)
        if t < T_CRANE1:
            a1, a2, _, _ = players_top(1.5)
            dash_arrow(lo_c, row, [a2 + np.array([0, 0.1, 0]), np.array([LEAD + 160, 0.1, 130])], t, ORANGE,
                       smooth(0.2, 0.5, t) * (1 - smooth(1.3, 1.5, t)))
        if 1.5 < t < T_REW0:
            trail(lo_c, row, t, 1.5, puck_top)
        if T_REW1 < t < T_DIVE0:
            trail(lo_c, row, t, T_REW1, puck_top)
        a1, a2, d1, d2 = players_top(max(t, 1.5) if t < T_REW0 else t)
        tok_a = 1 - smooth(T_DIVE0, T_DIVE0 + 0.25, t)
        for p, col in ((d1, BLUE), (d2, BLUE), (a1, ORANGE), (a2, ORANGE)):
            token(hi_c, row, p, col, 30, tok_a)
        if tok_a > 0.5:
            letter_tokens(L, row, [(d1, "D", BLUE), (d2, "D", BLUE), (a1, "A", ORANGE), (a2, "A", ORANGE)])
        puck_marker(hi_c, row, puck_at(t), t)
        whistle_ring(hi_c, row, puck_top(T_PUCK1), t, T_PUCK1, GREEN)
        whistle_ring(hi_c, row, players_top(T_PUCK2)[1], t, T_PUCK2 + 0.03, RED)
        if T_PUCK2 < t < T_DIVE0 + 0.3:                         # Abseits-Spieler markieren
            xy, z = projected(row, a2)
            if z > 0:
                r = px_per_in(row, z) * 46
                hi_c.set_source_rgba(RED[0] / 255, RED[1] / 255, RED[2] / 255, 0.9 * tok_a)
                hi_c.set_line_width(6)
                hi_c.arc(xy[0], xy[1], r, 0, 2 * math.pi)
                hi_c.stroke()
    else:
        zr = (CU_Z - 40.0, CU_Z + 60.0)
        edge_glow(lo_c, row, LEAD, LINE_BLUE, 0.8, zr, 0.45)
        if t >= T_V3:                                           # Kontakt mit der Linie
            on = smooth(T_V3 + 0.45, T_V3 + 0.6, t) * (1 - smooth(T_V4, T_V4 + 0.2, t))
            line_band(lo_c, row, 294.0, LEAD, GREEN, 0.35 * on, (NEAR_Z - 3.0, NEAR_Z + 3.0))
        draw_stick(lo_c, row, smooth(VO_START["stick"] - 0.1, VO_START["stick"] + 0.15, t) * (1 - smooth(T_V3 - 0.2, T_V3, t)))
        if VO_START["stick"] + 0.1 <= t < T_V3:                 # Schläger durchgestrichen
            xy, z = projected(row, np.array([287.0, 1.7, STICK_Z]))
            if z > 0:
                k = c01((t - VO_START["stick"] - 0.15) / 0.2)
                hi_c.set_source_rgba(RED[0] / 255, RED[1] / 255, RED[2] / 255, 0.95)
                hi_c.set_line_width(9)
                for sgn in (1, -1):
                    hi_c.move_to(xy[0] - 46 * k, xy[1] - sgn * 46 * k)
                    hi_c.line_to(xy[0] + 46 * k, xy[1] + sgn * 46 * k)
                    hi_c.stroke()
        draw_skates(lo_c, row, t, campos)                       # Puck liegt näher an der Kamera
        plane_wall(hi_c, row, smooth(T_PLANE - 0.2, T_PLANE + 0.3, t))
        for tw, p in ((T_ON1, np.array([302.0, 1.0, NEAR_Z])), (T_ON2, np.array([300.0, 5.5, NEAR_Z]))):
            whistle_ring(hi_c, row, p, t, tw, GREEN)
        review_ui(L, hi_c, t)
    img = over(base, *surf_rgba(lo_s))
    pa = cov[..., None]
    img = img * (1 - pa) + puck * pa
    img = over(img, *surf_rgba(hi_s))
    if T_PUCK2 + 0.03 <= t < T_PUCK2 + 0.33:
        a = 0.2 * (1 - (t - T_PUCK2 - 0.03) / 0.3)
        img = img * (1 - a) + np.array([1.0, 0.1, 0.12], np.float32) * a
    if T_REW0 <= t < T_REW1:
        rng = np.random.default_rng(int(t * 1000))
        img = img * 0.92 + 0.04
        for _ in range(7):
            y0, hh = int(rng.uniform(0, H - 40)), int(rng.uniform(6, 34))
            img[y0:y0 + hh] = np.roll(img[y0:y0 + hh], int(rng.uniform(-45, 45)), 1)
        img[::4] *= 0.93
    if cu and T_DIVE1 <= t < T_OUT0:                            # leichte Scanlines im Videobeweis
        img[::3] *= 0.975
    wf = smooth(T_OUT0, T_CUT, t) * (1 - smooth(T_CUT, T_OUT1, t))  # Weißblitz
    if wf > 0:
        img = img * (1 - wf) + wf
    img = np.clip(img, 0, 1)
    pil = Image.fromarray((img * 255).astype(np.uint8)).convert("RGBA")
    texts(L, t, row)
    pil.alpha_composite(L)
    arr = np.asarray(pil.convert("RGB")).astype(np.float32) / 255
    lc = min([t - c for c in (T_PUCK2 + 0.03, T_DIVE1, T_ON1, T_ON2) if t >= c] + [t + 0.5])
    zp = 1 + 0.035 * math.exp(-lc * 14)
    if zp > 1.002:
        im2 = Image.fromarray((arr * 255).astype(np.uint8))
        w2, h2 = W / zp, H / zp
        im2 = im2.transform((W, H), Image.EXTENT, ((W - w2) / 2, (H - h2) / 2, (W + w2) / 2, (H + h2) / 2), Image.BILINEAR)
        arr = np.asarray(im2).astype(np.float32) / 255
    arr = arr * (0.55 + 0.45 * vignette())
    arr += np.random.default_rng(fidx).normal(0, 0.008, arr.shape[:2])[..., None]
    return (np.clip(arr, 0, 1) * 255).astype(np.uint8)


# ================================================================= Ton: Musik + Voiceover
SR = 44100


def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(24)
    mus = np.zeros((n, 2))
    sfx = np.zeros((n, 2))
    B = 60 / 140

    def tt(sec):
        return np.arange(int(sec * SR)) / SR

    def put_(buf, sig, at, vol=1.0, pan=0.0):
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
        x = tt(0.35)
        f = 46 + 180 * np.exp(-x * 38)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 9) * 3.0) * vol

    def clap(vol=1.0):
        x = tt(0.3)
        env = sum((x >= d) * np.exp(-np.maximum(x - d, 0) * 70) for d in (0.0, 0.01, 0.021))
        return hp(lp(noise(0.3), 2), 6) * (env * 0.45 + np.exp(-x * 13) * 0.55) * 0.8 * vol

    def hat(vol=0.12):
        return hp(noise(0.04), 1) * np.exp(-tt(0.04) * 150) * vol

    def b808(freq, dur):
        x = tt(dur)
        f = freq * (1 + 0.5 * np.exp(-x * 10))
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * 2.4) * np.minimum(x / 0.003, 1) * np.exp(-x * 1.3) * 0.8

    def bell(freq, dur=0.5, vol=0.06):
        x = tt(dur)
        return np.sin(2 * np.pi * freq * x + np.sin(2 * np.pi * freq * 3.5 * x) * 2 * np.exp(-x * 6)) * np.exp(-x * 5) * vol

    def whistle(dur=0.6, vol=0.5):
        x = tt(dur)
        sig = np.sin(2 * np.pi * np.cumsum(np.full_like(x, 2900.0) + 120 * np.sin(2 * np.pi * 32 * x)) / SR)
        return sig * (1 + 0.5 * (np.sin(2 * np.pi * 32 * x) > 0)) * 0.5 * np.minimum(x / 0.02, 1) * np.clip((dur - x) / 0.08, 0, 1) * vol

    def stamp(vol=1.0):
        x = tt(0.9)
        f = 40 + 120 * np.exp(-x * 16)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 4) * 2.4) * vol

    def skate_sfx(dur, vol=0.3):
        x = tt(dur)
        strides = 0.5 + 0.5 * np.sin(2 * np.pi * 2.6 * x) ** 2
        return hp(lp(noise(dur), 2), 12) * strides * np.minimum(x / 0.1, 1) * np.clip((dur - x) / 0.2, 0, 1) * vol

    def rewind(dur=0.25, vol=0.6):
        x = tt(dur)
        f = 900 + 2400 * (x / dur) ** 1.5
        return np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.25 * lp(noise(dur), 3) * vol

    def whoosh(dur=0.7, vol=0.5):
        x = tt(dur)
        env = np.sin(np.pi * np.clip(x / dur, 0, 1)) ** 2
        return hp(lp(noise(dur), 6), 40) * env * vol

    def click(vol=0.5):
        x = tt(0.08)
        return hp(noise(0.08), 1) * np.exp(-x * 120) * vol

    def ding(vol=0.4):
        x = tt(0.9)
        return (np.sin(2 * np.pi * 1318.5 * x) + 0.6 * np.sin(2 * np.pi * 1760 * x) * (x > 0.09)) * np.exp(-x * 5) * vol

    roots = [55.0, 43.65, 49.0, 41.2]
    mel = [880.0, 1046.5, 1318.5, 1046.5, 987.8, 880.0, 784.0, 659.25]
    for k8 in range(int(DUR / (B / 2))):
        tb = k8 * B / 2
        b = k8 / 2
        pos = b % 4
        if T_REW0 <= tb < T_REW1 or tb > DUR - 0.5:
            continue
        cu = T_DIVE1 <= tb < T_OUT0                     # im Videobeweis gedämpfter Beat
        if pos in (0.0, 2.5):
            put_(mus, kick(0.7 if cu else 1.0), tb)
        if pos in (1.0, 3.0) and not cu:
            put_(mus, clap(), tb)
        put_(mus, hat(0.12 if k8 % 2 == 0 else 0.07), tb, pan=0.3)
        if pos == 0.0:
            put_(mus, b808(roots[int(b // 4) % 4], 2.3 * B), tb)
        put_(mus, bell(mel[k8 % 8]), tb, pan=-0.2)
    put_(sfx, skate_sfx(1.5, 0.22), 1.5)
    put_(sfx, skate_sfx(1.5, 0.22), T_REW1)
    put_(sfx, ding(0.45), T_PUCK1)
    put_(sfx, rewind(T_REW1 - T_REW0, 0.7), T_REW0)
    put_(sfx, whistle(0.7, 0.55), T_PUCK2)
    put_(sfx, stamp(1.0), T_PUCK2 + 0.03)
    put_(sfx, whoosh(T_DIVE1 - T_DIVE0 + 0.1, 0.5), T_DIVE0)
    put_(sfx, click(0.6), T_DIVE1)
    put_(sfx, stamp(0.5), T_ONLY)
    put_(sfx, ding(0.5), T_ON1)
    put_(sfx, stamp(0.4), T_ON1)
    put_(sfx, ding(0.5), T_ON2)
    put_(sfx, stamp(0.4), T_ON2)
    put_(sfx, whoosh(T_OUT1 - T_OUT0, 0.4), T_OUT0)
    put_(sfx, stamp(0.7), VO_START["cta"] + 0.5)
    # Voiceover
    voice = np.zeros(n)
    for k in VO_KEYS:
        tmp = os.path.join(HERE, f"_vo_{k}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "voice", f"reel24_{k}.wav"),
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
    duck = 1 - 0.72 * np.clip(venv / 0.06, 0, 1)                     # Stimme klar vor dem Beat
    mus /= np.max(np.abs(mus)) + 1e-9
    sfx /= np.max(np.abs(sfx)) + 1e-9
    mix = mus * 0.42 * duck[:, None] + sfx * 0.5 + voice[:, None] * 1.0
    mix = np.tanh(mix * 1.05)
    mix *= np.clip((DUR - np.arange(n) / SR) / 0.3, 0, 1)[:, None]
    mix = mix / np.max(np.abs(mix)) * 0.95
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


def main():
    os.chdir(HERE)
    for i, k in enumerate(VO_KEYS[:-1]):                             # Sätze dürfen sich nicht überlappen
        nxt = VO_KEYS[i + 1]
        if VO_START[k] + VO_DUR[k] > VO_START[nxt] + 0.35:            # Roh-WAVs enden mit ~0,4 s Stille
            print(f"Warnung: Satz {k} überlappt {nxt} ({VO_START[k] + VO_DUR[k]:.2f} > {VO_START[nxt]:.2f})")
    make_audio("audio_offside.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_offside.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
           "-ar", "44100", "-shortest", "-movflags", "+faststart", "reel24_offside.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(0.8, 9999)).save("reel24_thumbnail.jpg", quality=92)
    print("fertig: reel24_offside.mp4")


if __name__ == "__main__":
    main()
