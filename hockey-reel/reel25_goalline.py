"""Reel 25: NHL RULES EXPLAINED – PART 3: IS THIS A GOAL? (Torlinie, 3D-Erklärvideo mit Voiceover, 12,9 s).

Fakten (NHL-Regel 78.4): Ein Tor zählt nur, wenn der Puck zwischen den Pfosten und unter der Latte KOMPLETT über die
rote Torlinie geht ("entirely across a red line the width of the diameter of the goal posts") – der ganze Puck muss
die ganze Linie überqueren. Torlinie 2 Zoll breit, Puck 3 Zoll Durchmesser.
Videobeweis: Ohne eindeutigen Beweis bleibt die Entscheidung auf dem Eis ("the Referees' call on the ice stands",
NHL Situation Room).
Torlinie im Renderer: x = 1067–1069, Hinterkante (Torseite) = 1069. Pfosten-Innenkante bei z = ±36.
Look: Eis + Puck (Raytracer), Torgestänge (mesh3d), Netz (Vektor) – bewusst ohne Spieler.
Stimme: Kokoro "Michael" (tts_kokoro.py, Apache-2.0), Sätze einzeln, 1,08x.
Ende spult zurück an den Anfang -> letztes Bild = erstes Bild (Loop).
Aufruf: python3 reel25_goalline.py -> reel25_goalline.mp4
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
import mesh3d as M3
from reel15_puck import (W, H, FPS, SPP, KSUB, SHUTTER, c01, smooth, sio, e_out, e_in, lerp, blend_up, line_img,
                         reveal, put, proj, projected, px_per_in, stroke_poly, surface, surf_rgba, over, GOAL_X)
from reel22_trapezoid import fill_poly, whistle_ring, slam
from reel18_dangle import vignette

HERE = R15.HERE
INK, ORANGE = R15.INK, R15.ORANGE
RED = (225, 30, 40)
GREEN = (30, 160, 80)
HALO = (255, 255, 255)
TEMPO = 1.08

# ================================================================= Timeline aus dem Voiceover
VO_KEYS = ["q", "rule", "no", "yes", "view", "cta"]
VO_START = {"q": 0.15, "rule": 1.75, "no": 4.05, "yes": 6.0, "view": 7.95, "cta": 11.3}
with open(os.path.join(HERE, "voice", "reel25_timing.json")) as f:
    VO_DUR = {k: v / TEMPO for k, v in json.load(f).items()}
DUR = 12.9


def word(key, t_word):
    """Zeitpunkt eines Worts im Mix (Wortzeit im Roh-WAV laut Spracherkennung)."""
    return VO_START[key] + t_word / TEMPO


T_STOP = 0.95                          # Puck bleibt auf der Linie liegen
T_UP0, T_UP1 = 1.35, 2.1               # Hook -> Kranfahrt in die Draufsicht
T_PUCKW = word("rule", 0.22)           # "whole puck"
T_LINEW = word("rule", 1.60)           # "whole line"
T_IN0, T_IN1 = 3.85, 4.65              # Fahrt in die Overhead-Nahaufnahme
T_TOUCH = word("no", 0.20)             # "touching"
T_NO = word("no", 1.26)                # "no goal"
T_NUDGE0, T_NUDGE1 = word("yes", 0.05), word("yes", 0.62)
T_GOAL = word("yes", 0.74)             # "goal!"
T_SNOW = 7.7                           # Schneewolke verdeckt den Puck
T_CALL = word("view", 1.22)            # "the call on the ice"
T_STANDS = word("view", 1.90)          # "stands"
T_REW0, T_REW1 = 10.45, 11.2           # Rücklauf an den Anfang

GL_BACK = GOAL_X + 1.0                 # Hinterkante der Torlinie (Torseite)
PR = 1.1875                            # Pfostenradius (2 3/8 Zoll Durchmesser)
PZ = -8.0
START = np.array([1056.0, 0.5, -26.0])     # Puck rutscht schräg aufs Tor zu (im ersten Bild schon sichtbar)
HOOK_X = 1070.2                        # Puck liegt noch 0,3 Zoll auf der Linie
OVER_X = 1071.0                        # komplett drüber (0,5 Zoll Luft)
TH0 = float(os.environ.get("TH0", "2.2"))


def ease(t, a, b):
    return sio(c01((t - a) / (b - a)))


def scene_t(t):
    """Szenenzeit: läuft normal, spult am Ende schnell an den Anfang zurück."""
    if t < T_REW0:
        return t
    if t < T_REW1:
        return T_REW0 * (1 - sio((t - T_REW0) / (T_REW1 - T_REW0)))
    return 0.0


# ================================================================= Puck
def slide_frac(s):
    return e_out(c01(s / T_STOP), 2.2)


def puck_at(s):
    if s < T_STOP:
        return START + (np.array([HOOK_X, 0.5, PZ]) - START) * slide_frac(s)
    return np.array([HOOK_X + (OVER_X - HOOK_X) * ease(s, T_NUDGE0, T_NUDGE1), 0.5, PZ])


def puck_rot(s):
    return TH0 - 2.4 * (1 - slide_frac(s)) + 0.12 * ease(s, T_NUDGE0, T_NUDGE1)


# ================================================================= Kamera
HOOK_POS = np.array([float(v) for v in os.environ.get("HOOK_POS", "1052,15,-66").split(",")])
HOOK_TGT = np.array([float(v) for v in os.environ.get("HOOK_TGT", "1069,7,-6").split(",")])
HOOK_FOV = float(os.environ.get("HOOK_FOV", "40"))
HOOK_PUSH = np.array([5.0, -1.0, 3.0])
WIDE_T = np.array([1064.0, 0.0, 0.0])
WIDE_P = WIDE_T + np.array([-80.0, 230.0, 0.0])      # schräg von vorn: Latte verdeckt die Linie nicht
CLOSE_T = np.array([GL_BACK + 0.35, 0.0, PZ])
CLOSE_P = np.array([GL_BACK, 21.0, PZ])          # genau über der Hinterkante: Kante steht im Bild senkrecht zur Linie


def hook_cam(s):
    return HOOK_POS + HOOK_PUSH * e_out(c01(s / T_UP0), 2), HOOK_TGT, HOOK_FOV


def wide_cam(s):
    return WIDE_P + np.array([4.0, -10.0, 0.0]) * c01((s - T_UP1) / 2.0), WIDE_T, 36.0


def close_cam(s):
    k = 1 + 0.07 * sio(c01((s - T_IN1) / 5.5))
    return CLOSE_T + (CLOSE_P - CLOSE_T) * k, CLOSE_T, 36.0


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


def cam(s):
    """(pos, tgt, up, fov) zur Szenenzeit s."""
    if s < T_UP0:
        p, g, f = hook_cam(s)
    elif s < T_UP1:
        p, g, f = blend_cam(hook_cam(T_UP0), wide_cam(s), sio((s - T_UP0) / (T_UP1 - T_UP0)))
    elif s < T_IN0:
        p, g, f = wide_cam(s)
    elif s < T_IN1:
        u = (s - T_IN0) / (T_IN1 - T_IN0)
        p, g, f = blend_cam(wide_cam(s), close_cam(s), e_in(u, 2) * 0.35 + e_out(u, 3) * 0.65)
    else:
        p, g, f = close_cam(s)
    d = (p - g) / np.linalg.norm(p - g)
    el = math.degrees(math.asin(max(-1.0, min(1.0, d[1]))))
    return p, g, blend_up(min(el, 89.9)), f


def cam_row_at(s):
    pos, tgt, up, fov = cam(s)
    r, u, f = P3.look_at(pos, tgt, up)
    return P3.cam_row(pos, r, u, f, fov), float(np.linalg.norm(tgt - pos))


def seg(t):
    """Bewegungsunschärfe nicht über den Rücklauf hinweg."""
    for a, b in ((0.0, T_REW0), (T_REW0, T_REW1), (T_REW1, DUR)):
        if a <= t < b:
            return a, b
    return 0.0, DUR


def render3d(t, fidx):
    lo, hi = seg(t)
    cams, lens, pk = np.zeros((KSUB, 13)), np.zeros((KSUB, 2)), np.zeros((KSUB, 7))
    for j in range(KSUB):
        tk = min(max(t + ((j + 0.5) / KSUB - 0.5) * SHUTTER, lo), hi - 1e-4)
        sk = scene_t(tk)
        row, focus = cam_row_at(sk)
        cams[j], lens[j] = row, (0.0, focus)
        p = puck_at(sk)
        pk[j] = (p[0], p[1], p[2], puck_rot(sk), 1.0, 0.0, sk)
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, SPP, fidx + 25, cams, lens, pk, R15.logo_tex(), base, puck, cov)
    return P3.tonemap(base), P3.tonemap(puck), cov


# ================================================================= Tor: Gestänge (mesh3d) + Netz (Vektor)
def sphere_mesh(c, r, mat, nu=14, nv=28):
    th = np.linspace(0, math.pi, nu)
    ph = 2 * math.pi * np.arange(nv) / nv
    n = np.stack([np.outer(np.sin(th), np.cos(ph)), np.outer(np.cos(th), np.ones(nv)),
                  np.outer(np.sin(th), np.sin(ph))], -1).reshape(-1, 3)
    return M3.Mesh(c + r * n, n, M3.grid_tris(nu, nv), M3.MAT_IDS[mat])


def cyl_mesh(c, r, h, mat, nr=48, group=0):
    """Geschlossener Zylinder (Puck-Form) mit flachen Deckeln."""
    a = 2 * math.pi * np.arange(nr) / nr
    ring = np.stack([np.cos(a), np.zeros(nr), np.sin(a)], 1)
    up = np.array([0.0, 1.0, 0.0])
    v = np.concatenate([c + r * ring, c + r * ring + up * h, c + r * ring, c + r * ring + up * h,
                        [c], [c + up * h]])
    n = np.concatenate([ring, ring, np.tile(-up, (nr, 1)), np.tile(up, (nr, 1)), [-up], [up]])
    tris = [(i, nr + i, (i + 1) % nr) for i in range(nr)] + [((i + 1) % nr, nr + i, nr + (i + 1) % nr) for i in range(nr)]
    cb, ct = 4 * nr, 4 * nr + 1
    tris += [(cb, 2 * nr + (i + 1) % nr, 2 * nr + i) for i in range(nr)]
    tris += [(ct, 3 * nr + i, 3 * nr + (i + 1) % nr) for i in range(nr)]
    return M3.Mesh(v, n, np.array(tris, np.int32), M3.MAT_IDS[mat], group=group)


def frame_meshes():
    red = M3.MAT_IDS["post_red"]
    white = M3.MAT_IDS["frame_white"]
    zc, yc = 36.0 + PR, 48.0 + PR
    out = []
    for sz in (-1.0, 1.0):
        pts = np.array([[GOAL_X, y, sz * zc] for y in np.linspace(-0.5, yc, 14)])
        out.append(M3.tube_along(pts, np.full(len(pts), PR), lambda u: red, nr=32))
        out.append(sphere_mesh(np.array([GOAL_X, yc, sz * zc]), PR, "post_red"))
    pts = np.array([[GOAL_X, yc, z] for z in np.linspace(-zc, zc, 30)])
    out.append(M3.tube_along(pts, np.full(len(pts), PR), lambda u: red, nr=32))
    phi = np.linspace(0, math.pi, 48)
    base = np.stack([GOAL_X + 40 * np.sin(phi), np.full_like(phi, 0.9), -zc * np.cos(phi)], 1)
    out.append(M3.tube_along(base, np.full(len(base), 0.9), lambda u: white, nr=16))
    top = np.stack([GOAL_X + 20 * np.sin(phi), np.full_like(phi, yc), -zc * np.cos(phi)], 1)
    out.append(M3.tube_along(top, np.full(len(top), 0.55), lambda u: white, nr=12))
    return out


FRAME = frame_meshes()
NET = R15.net_lines(-1.0)[0]


def draw_net_lines(ctx, row, a):
    if a <= 0:
        return
    for pl in NET:
        xy, z = proj(row, pl)
        if (z < 2).any():
            continue
        wdt = float(np.clip(0.4 * px_per_in(row, z.mean()), 0.8, 3.0))
        stroke_poly(ctx, xy, (112, 120, 136), 0.55 * a, wdt)


# ================================================================= Overlays
def clip_x(poly, x0, x1):
    """Polygon (N,2: x,z) auf x0 <= x <= x1 beschneiden (Sutherland-Hodgman)."""
    def half(pts, inside, cut):
        out = []
        for i in range(len(pts)):
            a, b = pts[i - 1], pts[i]
            ia, ib = inside(a), inside(b)
            if ib:
                if not ia:
                    out.append(cut(a, b))
                out.append(b)
            elif ia:
                out.append(cut(a, b))
        return out

    def cutx(xv):
        return lambda a, b: a + (b - a) * ((xv - a[0]) / (b[0] - a[0]))

    pts = [np.asarray(p, float) for p in poly]
    pts = half(pts, lambda p: p[0] >= x0, cutx(x0))
    if pts:
        pts = half(pts, lambda p: p[0] <= x1, cutx(x1))
    return np.array(pts)


def overlap_fill(ctx, row, p, a):
    """Teil des Pucks, der noch auf der Linie liegt (auf der Puck-Oberseite)."""
    if a <= 0:
        return
    th = np.linspace(0, 2 * math.pi, 120, endpoint=False)
    circ = np.stack([p[0] + 1.5 * np.cos(th), p[2] + 1.5 * np.sin(th)], 1)
    part = clip_x(circ, GOAL_X - 1.0, GL_BACK)
    if len(part) < 3:
        return
    pts = np.stack([part[:, 0], np.full(len(part), 1.0), part[:, 1]], 1)
    xy, z = proj(row, pts)
    if (z < 1).any():
        return
    fill_poly(ctx, xy, RED, 0.62 * a)
    stroke_poly(ctx, np.vstack([xy, xy[:1]]), (255, 255, 255), 0.9 * a, 3)


def edge_line(ctx, row, y, z0, z1, col, a, t):
    """Gestrichelte Hinterkante der Torlinie."""
    if a <= 0:
        return
    zs = np.linspace(z0, z1, 40)
    xy, z = proj(row, np.stack([np.full_like(zs, GL_BACK), np.full_like(zs, y), zs], 1))
    if (z < 1).any():
        return
    ctx.set_dash([26, 14], -t * 60)
    stroke_poly(ctx, xy, col, 0.95 * a, 6, R15.cairo.LINE_CAP_BUTT)
    ctx.set_dash([])


def line_glow(ctx, row, a):
    """Torlinie zwischen den Pfosten leuchtet."""
    if a <= 0:
        return
    zs = np.linspace(-36.0, 36.0, 50)
    xy, z = proj(row, np.stack([np.full_like(zs, GOAL_X), np.full_like(zs, 0.12), zs], 1))
    if (z < 3).any():
        return
    w = float(np.clip(px_per_in(row, z.mean()) * 2.0, 3.0, 40))
    stroke_poly(ctx, xy, ORANGE, 0.22 * a, w * 2.2)
    stroke_poly(ctx, xy, ORANGE, 0.9 * a, w)


def gap_band(ctx, row, p, a):
    """Luft zwischen Linie und Puck (liegt unter dem Puck, sichtbar bleibt nur der Spalt)."""
    if a <= 0:
        return
    pts = np.array([[GL_BACK, 0.1, p[2] - 0.8], [p[0], 0.1, p[2] - 0.8], [p[0], 0.1, p[2] + 0.8],
                    [GL_BACK, 0.1, p[2] + 0.8]])
    xy, z = proj(row, pts)
    if (z < 1).any():
        return
    fill_poly(ctx, xy, GREEN, 0.85 * a)


def dashed_ring(ctx, row, p, r_in, a, t, col=ORANGE):
    if a <= 0:
        return
    xy, z = projected(row, p)
    if z <= 0:
        return
    r = px_per_in(row, z) * r_in + 6 * math.sin(t * 9)
    ctx.set_source_rgba(col[0] / 255, col[1] / 255, col[2] / 255, 0.9 * a)
    ctx.set_line_width(7)
    ctx.set_dash([26, 16], -t * 60)
    ctx.arc(xy[0], xy[1], r, 0, 2 * math.pi)
    ctx.stroke()
    ctx.set_dash([])


# ---------------- Schneewolke (verdeckt den Puck im Videobeweis)
_rng = np.random.default_rng(25)
NS = 5200
SN_C = np.array([GL_BACK + 1.0, 0.0, PZ + 0.5])
SN_FIN = SN_C + np.stack([_rng.normal(0, 1.5, NS), 0.1 + np.abs(_rng.normal(0, 0.5, NS)),
                          _rng.normal(0, 1.9, NS)], 1)
SN_FIN[:, 1] -= SN_C[1]
SN_D = _rng.uniform(16, 34, NS)
SN_T0 = T_SNOW + _rng.uniform(0, 0.25, NS)
SN_K = _rng.uniform(5.0, 9.0, NS)
SN_R = _rng.uniform(0.018, 0.07, NS)
SN_SH = _rng.uniform(0.84, 1.0, NS)
SN_DIR = np.array([0.08, 0.0, 1.0]) / np.linalg.norm([0.08, 0.0, 1.0])


def snow(ctx, row, s):
    live = s >= SN_T0
    if not live.any():
        return
    dt = s - SN_T0[live]
    q = np.exp(-SN_K[live] * dt)
    pts = SN_FIN[live] - SN_DIR[None, :] * (SN_D[live] * q)[:, None]
    pts[:, 1] += 3.0 * q * (1 - q) * 4
    xy, z = proj(row, pts)
    r = px_per_in(row, z) * SN_R[live]
    sh = SN_SH[live]
    cover = smooth(T_SNOW + 0.1, T_SNOW + 0.55, s)
    cxy, cz = projected(row, SN_C)
    if cz > 0 and cover > 0:                                    # weicher Nebel unter den Flocken
        rr = px_per_in(row, cz) * 5.0
        g = R15.cairo.RadialGradient(cxy[0], cxy[1], 0, cxy[0], cxy[1], rr)
        g.add_color_stop_rgba(0, 0.97, 0.98, 1.0, 0.99 * cover)
        g.add_color_stop_rgba(0.55, 0.96, 0.97, 1.0, 0.985 * cover)
        g.add_color_stop_rgba(1, 0.95, 0.97, 1.0, 0.0)
        ctx.set_source(g)
        ctx.arc(cxy[0], cxy[1], rr, 0, 2 * math.pi)
        ctx.fill()
    for i in range(len(r)):
        if z[i] <= 1:
            continue
        ctx.set_source_rgba(0.62, 0.68, 0.78, 0.22)
        ctx.arc(xy[i, 0] + r[i] * 0.25, xy[i, 1] + r[i] * 0.3, r[i] * 1.05, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgba(sh[i] * 0.98, sh[i] * 0.99, min(1.0, sh[i] * 1.02), 0.92)
        ctx.arc(xy[i, 0], xy[i, 1], r[i], 0, 2 * math.pi)
        ctx.fill()


def review_ui(L, ctx, t, s):
    if t >= T_REW1:
        a = smooth(T_REW1, T_REW1 + 0.15, t)
    elif t >= T_REW0:
        a = 0.0
    else:
        a = (1 - smooth(T_UP0, T_UP0 + 0.2, s)) if s < T_IN0 else smooth(T_IN1 - 0.15, T_IN1 + 0.1, s)
    if a <= 0:
        return
    m, ln = 70, 70
    ctx.set_source_rgba(INK[0] / 255, INK[1] / 255, INK[2] / 255, 0.75 * a)
    ctx.set_line_width(5)
    for (x, y, dx, dy) in ((m, 200, 1, 1), (W - m, 200, -1, 1), (m, 1560, 1, -1), (W - m, 1560, -1, -1)):
        ctx.move_to(x, y + dy * ln)
        ctx.line_to(x, y)
        ctx.line_to(x + dx * ln, y)
        ctx.stroke()
    blink = 1.0 if (t * 2) % 1 < 0.6 else 0.25
    ctx.set_source_rgba(RED[0] / 255, RED[1] / 255, RED[2] / 255, a * blink)
    ctx.arc(m + 34, 252, 10, 0, 2 * math.pi)
    ctx.fill()
    reveal(L, line_img("VIDEO REVIEW", 34, 850, INK, track=6), m + 58, 252, a, 0.0, anchor="l")
    if T_SNOW + 0.3 <= s and t < T_REW0:
        reveal(L, line_img("NO CLEAR VIEW", 30, 850, RED, track=3), W - m - 10, 252, a * blink, 0.0, anchor="r")
    else:
        tc = f"00:0{int(2 + s * 0.25)}:{int((s * 30) % 60):02d}"
        reveal(L, line_img(tc, 30, 700, INK, track=2), W - m - 10, 252, a, 0.0, anchor="r")


# ================================================================= Texte
def label_at(L, row, p, txt, col, dx, dy, a, size=40):
    if a <= 0:
        return
    xy, z = projected(row, p)
    if z <= 0:
        return
    im = line_img(txt, size, 850, col, track=4)
    reveal(L, im, min(max(xy[0] + dx, 40 + im.width / 2), W - 40 - im.width / 2), xy[1] + dy, a)


def two_lines(L, a_txt, b_txt, col_a, col_b, ya, yb, size_a, size_b, k):
    for txt, cy, size, col in ((a_txt, ya, size_a, col_a), (b_txt, yb, size_b, col_b)):
        im = R18.word_img(txt, size, col, HALO)
        if k < 1:
            im = im.copy()
            im.putalpha(im.getchannel("A").point(lambda v: int(v * k)))
        put(L, im, W / 2 - im.width / 2, cy - im.height / 2)


def texts(L, t, s, row):
    A = VO_START
    if t < T_UP0 + 0.1:                                             # Hook
        k = 1 - smooth(T_UP0 - 0.1, T_UP0 + 0.1, t)
        two_lines(L, "IS THIS", "A GOAL?", INK, RED, 480, 640, 140, 178, k)
        reveal(L, line_img("NHL RULES EXPLAINED  ·  PART 3", 34, 800, ORANGE, track=8), W / 2, 360, 1.0,
               smooth(T_UP0 - 0.15, T_UP0 + 0.05, t))
    if t >= T_REW0:
        if t < T_REW1:
            reveal(L, line_img("<<  REWIND", 60, 900, INK, track=10), W / 2, 560, 1.0)
        else:
            slam(L, "DID YOU", 120, INK, W / 2, 450, t, A["cta"])
            slam(L, "GET IT RIGHT?", 120, ORANGE, W / 2, 590, t, A["cta"] + 0.2)
            if t >= A["cta"] + 0.5:
                reveal(L, line_img("COMMENT BELOW  ·  FOLLOW FOR PART 4", 34, 800, INK, track=6), W / 2, 1420,
                       c01((t - A["cta"] - 0.5) / 0.25))
        return
    if T_UP1 - 0.25 <= t < T_IN0 + 0.1:                             # Draufsicht
        fade = 1 - smooth(T_IN0 - 0.15, T_IN0 + 0.1, t)
        label_at(L, row, puck_at(s) + np.array([-9.5, 0, 0]), "WHOLE PUCK", ORANGE, 0, 0,
                 smooth(T_PUCKW, T_PUCKW + 0.2, t) * fade, 44)
        label_at(L, row, np.array([GOAL_X, 0, 16.0]), "WHOLE LINE", ORANGE, 0, -54,
                 smooth(T_LINEW, T_LINEW + 0.2, t) * fade, 44)
    slam(L, "STILL TOUCHING", 84, INK, W / 2, 1450, t, T_TOUCH + 0.35, T_NUDGE0)
    slam(L, "NO GOAL.", 180, RED, W / 2, 440, t, T_NO, T_NUDGE0 + 0.05)
    slam(L, "100% OVER", 84, INK, W / 2, 1450, t, word("yes", 0.44), T_SNOW + 0.2)
    slam(L, "GOAL!", 210, GREEN, W / 2, 430, t, T_GOAL, T_SNOW + 0.25)
    if A["view"] <= t < T_CALL:
        two_lines(L, "NO CLEAR", "REPLAY?", INK, INK, 420, 560, 120, 120, smooth(A["view"], A["view"] + 0.08, t))
    slam(L, "CALL ON THE ICE", 84, INK, W / 2, 1450, t, T_CALL, T_REW0)
    slam(L, "STANDS.", 190, ORANGE, W / 2, 440, t, T_STANDS, T_REW0)


# ================================================================= Bild
_GL = None


def goal_light():
    """Rotes Torlicht von oben (Maske)."""
    global _GL
    if _GL is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.sqrt(((xx - W / 2) / (W * 0.9)) ** 2 + ((yy + 120) / (H * 0.55)) ** 2)
        _GL = np.clip(1 - d, 0, 1) ** 1.6
    return _GL


def compose(t, fidx):
    s = scene_t(t)
    base, puck, cov = render3d(t, fidx)
    row, _ = cam_row_at(s)
    campos = cam(s)[0]
    p = puck_at(s)
    lo_s, lo_c = surface()
    hi_s, hi_c = surface()
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    frame_a = 1 - smooth(T_IN0, T_IN0 + 0.45, s)
    draw_net_lines(lo_c, row, frame_a)
    if s < T_IN0 + 0.2:                                         # Draufsicht: Linie leuchtet bei "whole line"
        line_glow(lo_c, row, smooth(T_LINEW - 0.05, T_LINEW + 0.2, s) * (1 - smooth(T_IN0 - 0.1, T_IN0 + 0.2, s)))
    gap_band(lo_c, row, p, smooth(T_NUDGE1 - 0.1, T_NUDGE1 + 0.1, s) * (1 - smooth(T_SNOW + 0.1, T_SNOW + 0.3, s)))
    img = over(base, *surf_rgba(lo_s))
    meshes = (FRAME if frame_a > 0 else []) + [cyl_mesh(p - np.array([0, 0.5, 0]), 1.5, 1.0, "occluder", group=1)]
    m_rgb, m_a, shadow, _ = M3.render(meshes, row, W, H, campos, alpha_by_group=np.array([frame_a, 0.0], np.float32),
                                      shadow_light=(0.02, 1.0, -0.03))
    img = img * (1 - 0.15 * frame_a * shadow[..., None])
    pa = cov[..., None]
    img = img * (1 - pa) + puck * pa
    img = img * (1 - m_a[..., None]) + m_rgb
    # Oberste Ebene: Markierungen, Schnee, Videobeweis-Rahmen
    if t < T_REW0:
        dashed_ring(hi_c, row, p + np.array([0, 0.5, 0]), 4.2, smooth(T_STOP, T_STOP + 0.15, s) *
                    (1 - smooth(T_UP0 - 0.1, T_UP0 + 0.1, s)), t)
        dashed_ring(hi_c, row, p + np.array([0, 0.5, 0]), 5.0, smooth(T_PUCKW - 0.05, T_PUCKW + 0.15, s) *
                    (1 - smooth(T_IN0 - 0.15, T_IN0 + 0.1, s)), t)
        touch_a = smooth(T_TOUCH + 0.3, T_TOUCH + 0.5, s) * (1 - smooth(T_NUDGE0, T_NUDGE0 + 0.2, s))
        edge_line(hi_c, row, 1.02, PZ - 7.0, PZ + 7.0, INK, smooth(T_TOUCH + 0.2, T_TOUCH + 0.4, s) *
                  (1 - smooth(T_SNOW, T_SNOW + 0.3, s)), t)
        overlap_fill(hi_c, row, p, touch_a)
        whistle_ring(hi_c, row, np.array([GL_BACK - 0.15, 1.0, PZ]), t, T_NO, RED)
        whistle_ring(hi_c, row, p + np.array([0, 0.5, 0]), t, T_GOAL, GREEN)
    snow(hi_c, row, s)
    review_ui(L, hi_c, t, s)
    img = over(img, *surf_rgba(hi_s))
    if T_GOAL <= t < T_GOAL + 1.6:                              # Torlicht pulsiert
        lt = t - T_GOAL
        a = 0.5 * (0.55 + 0.45 * math.cos(2 * math.pi * 2.6 * lt)) * math.exp(-lt * 1.3) * c01(lt / 0.05)
        k = (goal_light() * a)[..., None]
        img = img * (1 - k) + np.array([1.0, 0.12, 0.1], np.float32) * k
    if T_NO <= t < T_NO + 0.3:
        a = 0.18 * (1 - (t - T_NO) / 0.3)
        img = img * (1 - a) + np.array([1.0, 0.1, 0.12], np.float32) * a
    if T_REW0 <= t < T_REW1:
        rng = np.random.default_rng(int(t * 1000))
        img = img * 0.92 + 0.04
        for _ in range(7):
            y0, hh = int(rng.uniform(0, H - 40)), int(rng.uniform(6, 34))
            img[y0:y0 + hh] = np.roll(img[y0:y0 + hh], int(rng.uniform(-45, 45)), 1)
        img[::4] *= 0.93
    elif s < T_UP0 + 0.1 or s >= T_IN1 - 0.1:                   # leichte Scanlines im Videobeweis
        img[::3] *= 0.975
    img = np.clip(img, 0, 1)
    pil = Image.fromarray((img * 255).astype(np.uint8)).convert("RGBA")
    texts(L, t, s, row)
    pil.alpha_composite(L)
    arr = np.asarray(pil.convert("RGB")).astype(np.float32) / 255
    lc = min([t - c for c in (T_NO, T_GOAL, T_STANDS) if t >= c] + [t + 0.5])
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
    rng = np.random.default_rng(25)
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

    def stamp(vol=1.0):
        x = tt(0.9)
        f = 40 + 120 * np.exp(-x * 16)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 4) * 2.4) * vol

    def slide(dur, vol=0.3):
        x = tt(dur)
        v = np.clip(1 - x / dur, 0, 1) ** 1.2                     # Puck wird langsamer
        return hp(lp(noise(dur), 2), 18) * v * np.minimum(x / 0.03, 1) * vol

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

    def buzzer(dur=0.45, vol=0.4):
        x = tt(dur)
        sq = np.sign(np.sin(2 * np.pi * 98 * x)) + 0.6 * np.sign(np.sin(2 * np.pi * 104 * x))
        return lp(sq, 8) * np.minimum(x / 0.01, 1) * np.clip((dur - x) / 0.06, 0, 1) * vol

    def horn(dur=1.5, vol=0.4):
        x = tt(dur)
        sig = np.zeros_like(x)
        for f0, amp in ((116.5, 1.0), (146.8, 0.8), (174.6, 0.65), (233.1, 0.3)):
            ph = f0 * x + 0.004 * np.sin(2 * np.pi * 5.5 * x)
            sig += amp * (2 * (ph % 1.0) - 1)
        sig = lp(sig, 10) / 2.75
        return np.tanh(sig * 1.6) * np.minimum(x / 0.05, 1) * np.clip((dur - x) / 0.4, 0, 1) * vol

    def spray(dur=0.7, vol=0.5):
        x = tt(dur)
        return hp(lp(noise(dur), 2), 10) * np.minimum(x / 0.015, 1) * np.exp(-x * 4.5) * vol

    roots = [55.0, 43.65, 49.0, 41.2]
    mel = [880.0, 1046.5, 1318.5, 1046.5, 987.8, 880.0, 784.0, 659.25]
    for k8 in range(int(DUR / (B / 2))):
        tb = k8 * B / 2
        b = k8 / 2
        pos = b % 4
        if T_REW0 <= tb < T_REW1 or tb > DUR - 0.5:
            continue
        cu = tb < T_UP0 or T_IN1 <= tb < T_REW0                    # im Videobeweis gedämpfter Beat
        if pos in (0.0, 2.5):
            put_(mus, kick(0.7 if cu else 1.0), tb)
        if pos in (1.0, 3.0) and not cu:
            put_(mus, clap(), tb)
        put_(mus, hat(0.12 if k8 % 2 == 0 else 0.07), tb, pan=0.3)
        if pos == 0.0:
            put_(mus, b808(roots[int(b // 4) % 4], 2.3 * B), tb)
        put_(mus, bell(mel[k8 % 8]), tb, pan=-0.2)
    put_(sfx, click(0.5), 0.02)
    put_(sfx, slide(T_STOP + 0.05, 0.35), 0.0)
    put_(sfx, whoosh(T_UP1 - T_UP0 + 0.1, 0.45), T_UP0)
    put_(sfx, click(0.5), T_PUCKW)
    put_(sfx, ding(0.35), T_LINEW)
    put_(sfx, whoosh(T_IN1 - T_IN0 + 0.1, 0.5), T_IN0)
    put_(sfx, click(0.6), T_IN1)
    put_(sfx, buzzer(0.45, 0.45), T_NO)
    put_(sfx, stamp(0.8), T_NO)
    put_(sfx, slide(0.4, 0.18), T_NUDGE0)
    put_(sfx, stamp(0.7), T_GOAL)
    put_(sfx, horn(1.3, 0.55), T_GOAL + 0.12)
    put_(sfx, spray(0.7, 0.55), T_SNOW)
    put_(sfx, stamp(0.6), T_STANDS)
    put_(sfx, rewind(T_REW1 - T_REW0, 0.7), T_REW0)
    put_(sfx, stamp(0.7), VO_START["cta"] + 0.5)
    # Voiceover
    voice = np.zeros(n)
    for k in VO_KEYS:
        tmp = os.path.join(HERE, f"_vo_{k}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "voice", f"reel25_{k}.wav"),
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
    make_audio("audio_goalline.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_goalline.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
           "-ar", "44100", "-shortest", "-movflags", "+faststart", "reel25_goalline.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(1.1, 9999)).save("reel25_thumbnail.jpg", quality=92)
    print("fertig: reel25_goalline.mp4")


if __name__ == "__main__":
    main()
