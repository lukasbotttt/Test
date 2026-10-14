"""Reel 26: NHL RULES EXPLAINED – PART 4: WHY IS THIS 2 MINUTES? (Puck über das Glas, 3D-Erklärvideo, 13,3 s).

Fakten (NHL-Regel 63.2, Delay of Game): Schießt oder schlägt ein Spieler den Puck aus seinem eigenen Drittel direkt
(ohne Abfälschung) aus der Spielfläche, gibt es 2 Minuten – außer dort, wo kein Glas ist (Spielerbänke). Die Strafe
ist automatisch, Absicht spielt keine Rolle. Seit 2016–17 zählt, wo der Puck beim Schuss ist. Berührt der Puck
vorher Glas, Bande, Spieler oder Schläger, gibt es keine Strafe.
Bilder: Bande (weiß, gelbe Fußleiste) + Glasscheiben + Spielerbank ohne Glas als 3D-Gitter (mesh3d), Eis + Puck
(Raytracer), Spieler nur als Marker ("D"). Bewusst ohne Spielerkörper.
Stimme: Kokoro "Michael" (tts_kokoro.py, Apache-2.0), Sätze einzeln, 1,08x.
Aufruf: python3 reel26_overglass.py -> reel26_overglass.mp4
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
import mesh3d as M3
import reel25_goalline as G
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
TEMPO = 1.08

# ================================================================= Timeline aus dem Voiceover
VO_KEYS = ["q", "rule", "pen", "glass", "bench", "cta"]
VO_START = {"q": 0.15, "rule": 1.85, "pen": 3.95, "glass": 5.95, "bench": 8.45, "cta": 10.95}
with open(os.path.join(HERE, "voice", "reel26_timing.json")) as f:
    VO_DUR = {k: v / TEMPO for k, v in json.load(f).items()}
DUR = 13.3


def word(key, t_word):
    return VO_START[key] + t_word / TEMPO


T_UP0, T_UP1 = 1.45, 2.25              # Hook (Zeitlupe am Glas) -> Übersicht
T_ZONE = word("rule", 0.40)            # "own zone"
T_L1 = 3.0                             # Szene 1: Schuss direkt über das Glas
D1 = 0.40
T_PEN = VO_START["pen"]                # "Penalty"
T_EVEN = word("pen", 0.26)
T_DIVE0, T_DIVE1 = 5.4, 6.0            # zurück ans Glas
T_L2 = 6.05                            # Szene 2: erst ans Glas, dann drüber
T_HIT = T_L2 + 0.30
T_NO1 = word("glass", 1.20)
T_PAN0, T_PAN1 = 7.75, 8.4             # Schwenk zur Spielerbank
T_L3 = 8.5                             # Szene 3: über die Bank
D3 = 0.5
T_NO2 = word("bench", 0.98)
T_BACK0, T_BACK1 = 10.3, 10.95         # zurück zum Anfangsbild (Loop)

# ================================================================= Geometrie (Zoll)
BH, GH = 42.0, 72.0                    # Bande, Glas darüber
GTOP = BH + GH
SZ = 510.0                             # Seitenbande (Innenkante)
BENCHES = [(-260.0, -40.0), (40.0, 260.0)]
ZONE_X = -306.0                        # Grenze des eigenen Drittels (blaue Linie, linke Hälfte)


def wall_path():
    """Innenkante der Bande: +z-Seite bis zur Mitte, Ecke, Stirnseite, Ecke, -z-Seite."""
    pts = [(x, SZ) for x in np.linspace(420.0, -864.0, 44)]
    for a in np.linspace(90, 180, 22)[1:]:
        r = math.radians(a)
        pts.append((-864.0 + 336.0 * math.cos(r), 174.0 + 336.0 * math.sin(r)))
    pts += [(-1200.0, z) for z in np.linspace(174.0, -174.0, 12)[1:]]
    for a in np.linspace(180, 270, 22)[1:]:
        r = math.radians(a)
        pts.append((-864.0 + 336.0 * math.cos(r), -174.0 + 336.0 * math.sin(r)))
    pts += [(x, -SZ) for x in np.linspace(-864.0, 420.0, 44)[1:]]
    return np.array(pts)


WALL = wall_path()


def inward(pts):
    t = np.gradient(pts, axis=0)
    n = np.stack([-t[:, 1], t[:, 0]], 1)
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    flip = (n * (-pts)).sum(1) < 0
    n[flip] *= -1
    return n


WALL_N = inward(WALL)


def strip(p_bot, p_top, normal, mat):
    """Senkrechter Streifen entlang einer Linie (p_bot/p_top: N x 3)."""
    n_ = len(p_bot)
    v = np.concatenate([p_bot, p_top])
    nn = np.concatenate([normal, normal])
    tris = [(i, n_ + i, i + 1) for i in range(n_ - 1)] + [(i + 1, n_ + i, n_ + i + 1) for i in range(n_ - 1)]
    return M3.Mesh(v, nn, np.array(tris, np.int32), M3.MAT_IDS[mat])


def box_mesh(x0, x1, y0, y1, z0, z1, mat):
    c = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                  [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]])
    faces = [((0, 1, 2, 3), (0, 0, -1)), ((5, 4, 7, 6), (0, 0, 1)), ((4, 0, 3, 7), (-1, 0, 0)),
             ((1, 5, 6, 2), (1, 0, 0)), ((3, 2, 6, 7), (0, 1, 0)), ((4, 5, 1, 0), (0, -1, 0))]
    v, n, t = [], [], []
    for idx, nor in faces:
        b = len(v)
        v += [c[i] for i in idx]
        n += [nor] * 4
        t += [(b, b + 1, b + 2), (b, b + 2, b + 3)]
    return M3.Mesh(np.array(v, float), np.array(n, float), np.array(t, np.int32), M3.MAT_IDS[mat])


def boards_meshes():
    xz = WALL
    n2 = WALL_N
    n3 = np.stack([n2[:, 0], np.zeros(len(n2)), n2[:, 1]], 1)
    p = np.stack([xz[:, 0], np.zeros(len(xz)), xz[:, 1]], 1)
    out = [strip(p, p + [0, BH, 0], n3, "board_white")]                       # Innenseite
    k0 = p + n3 * 0.12
    out.append(strip(k0, k0 + [0, 9.0, 0], n3, "kick_yellow"))                 # gelbe Fußleiste
    top_in, top_out = p + [0, BH, 0], p + [0, BH, 0] - n3 * 5.0
    out.append(strip(top_in, top_out, np.tile([0.0, 1.0, 0.0], (len(p), 1)), "board_white"))
    rail = p + [0, BH + 0.6, 0] - n3 * 2.5
    out.append(M3.tube_along(rail, np.full(len(rail), 1.3), lambda u: M3.MAT_IDS["rail"], nr=10))
    for x0, x1 in BENCHES:                                                     # Spielerbänke hinter der Bande
        out.append(box_mesh(x0 + 12, x1 - 12, 0.0, 17.0, SZ + 22, SZ + 40, "bench_seat"))
        wall_pts = np.array([[x, 0.0, SZ + 62] for x in np.linspace(x0, x1, 8)])
        out.append(strip(wall_pts, wall_pts + [0, BH, 0], np.tile([0.0, 0.0, -1.0], (8, 1)), "board_white"))
        for xs in (x0, x1):
            side = np.array([[xs, 0.0, z] for z in np.linspace(SZ + 4, SZ + 62, 4)])
            out.append(strip(side, side + [0, BH, 0], np.tile([1.0 if xs == x0 else -1.0, 0.0, 0.0], (4, 1)),
                             "board_white"))
    return out


def in_bench(x, z):
    return z > 0 and any(a <= x <= b for a, b in BENCHES)


def glass_panels():
    """Glasscheiben (Viereck je Scheibe) – keine Scheiben vor den Spielerbänken."""
    out = []
    pts = WALL
    seg = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    marks = np.arange(0, seg[-1], 60.0)
    xs = np.interp(marks, seg, pts[:, 0])
    zs = np.interp(marks, seg, pts[:, 1])
    nx = np.interp(marks, seg, WALL_N[:, 0])
    nz = np.interp(marks, seg, WALL_N[:, 1])
    for i in range(len(marks) - 1):
        a = np.array([xs[i] - nx[i] * 1.5, BH, zs[i] - nz[i] * 1.5])
        b = np.array([xs[i + 1] - nx[i + 1] * 1.5, BH, zs[i + 1] - nz[i + 1] * 1.5])
        if in_bench((a[0] + b[0]) / 2, (a[2] + b[2]) / 2):
            continue
        out.append(np.array([a, b, b + [0, GH, 0], a + [0, GH, 0]]))
    for x0, x1 in BENCHES:                                                     # Glas hinter den Bänken
        out.append(np.array([[x0, BH, SZ + 62], [x1, BH, SZ + 62], [x1, GTOP, SZ + 62], [x0, GTOP, SZ + 62]]))
    return out


def mirror_x(mesh):
    m = M3.Mesh(mesh.v * [-1, 1, 1], mesh.n * [-1, 1, 1], mesh.t, mesh.m, mesh.uvw)
    m.g = mesh.g.copy()
    return m


BOARDS = boards_meshes()
GLASS = glass_panels()
GLASS_ALL = np.concatenate(GLASS)
GOAL_FRAME = [mirror_x(m) for m in G.FRAME]                                    # eigenes Tor bei x = -1068
NET = [pl * [-1, 1, 1] for pl in R15.net_lines(-1.0)[0]]


# ================================================================= Puck
def arc(a, b, apex, u):
    p = a + (b - a) * u
    p[1] += 4 * apex * u * (1 - u)
    return p


def bez(p0, p1, p2, u):
    return (1 - u) ** 2 * p0 + 2 * (1 - u) * u * p1 + u * u * p2


L1, E1, APEX1 = np.array([-735.0, 0.5, 420.0]), np.array([-712.0, 30.0, 640.0]), 140.0
L2, C2, H2 = np.array([-735.0, 0.5, 432.0]), np.array([-731.0, 74.0, 470.0]), np.array([-728.0, 96.0, 508.3])
B2c, T2 = np.array([-726.0, 132.0, 507.0]), np.array([-724.0, 128.0, 522.0])
C2c, E2 = np.array([-722.0, 132.0, 548.0]), np.array([-720.0, 50.0, 600.0])
L3, E3, APEX3 = np.array([-360.0, 0.5, 400.0]), np.array([-190.0, 17.5, 538.0]), 70.0


def s1(u):
    return arc(L1, E1, APEX1, u)


def s2(tl):
    """Szene 2 nach lokaler Zeit (s): ans Glas (0–0.3), am Glas hoch und drüber (0.3–0.55), dahinter runter."""
    if tl < 0.30:
        return bez(L2, C2, H2, e_in(tl / 0.30, 1.15))
    if tl < 0.55:
        return bez(H2, B2c, T2, (tl - 0.30) / 0.25)
    return bez(T2, C2c, E2, min((tl - 0.55) / 0.35, 1.0))


def puck_state(t):
    """(Position, sichtbar)"""
    if t < T_UP0:                                                     # Hook: Zeitlupe über dem Glas
        return s1(0.18 + 0.40 * t / T_UP0), 1.0
    if t < T_UP0 + 0.45:
        return s1(0.58 + 0.42 * (t - T_UP0) / 0.45), 1.0
    if t < 2.35:
        return L1, 0.0
    if t < T_DIVE0:                                                   # Übersicht: Schuss in Echtzeit
        u = c01((t - T_L1) / D1)
        return s1(u), (1.0 if u < 1 else 0.0)
    if t < T_L2:
        return L2, (1.0 if t >= T_DIVE1 - 0.2 else 0.0)
    if t < T_PAN0:
        tl = t - T_L2
        return s2(tl), (1.0 if tl < 0.95 else 0.0)
    if t < T_L3:
        return L3, (1.0 if t >= T_PAN1 - 0.1 else 0.0)
    if t < T_BACK0 + 0.3:
        u = c01((t - T_L3) / D3)
        return arc(L3, E3, APEX3, u), 1.0
    return L1, 0.0


def puck_rot(t):
    return 1.3 + 9.0 * t


# ================================================================= Kamera
GLASS_TGT = np.array([float(v) for v in os.environ.get("GTGT", "-726,150,500").split(",")])
CLOSE_OFF = np.array([float(v) for v in os.environ.get("COFF", "-230,90,-150").split(",")])
HOOK_PUSH = np.array([10.0, 2.0, 14.0])
BENCH_TGT = np.array([-206.0, 130.0, 500.0])
OV_POS = np.array([-1580.0, 640.0, 120.0])
OV_TGT = np.array([-560.0, 0.0, 430.0])
CLOSE_FOV, OV_FOV = float(os.environ.get("CFOV", "38")), 38.0


def hook_cam(t):
    return GLASS_TGT + CLOSE_OFF + HOOK_PUSH * e_out(c01(t / T_UP0), 2), GLASS_TGT, CLOSE_FOV


def glass_cam(t):
    return GLASS_TGT + CLOSE_OFF + HOOK_PUSH * 0.6, GLASS_TGT, CLOSE_FOV


def bench_cam(t):
    return BENCH_TGT + CLOSE_OFF + HOOK_PUSH * 0.6 + np.array([6.0, 0, 6.0]) * c01((t - T_PAN1) / 2.0), BENCH_TGT, CLOSE_FOV


def ov_cam(t):
    return OV_POS + np.array([60.0, -30.0, 0.0]) * c01((t - T_UP1) / 3.2), OV_TGT, OV_FOV


def blend_cam(a, b, s):
    pa, ta, fa = a
    pb, tb, fb = b
    tgt = ta + (tb - ta) * s
    ra, rb = float(np.linalg.norm(pa - ta)), float(np.linalg.norm(pb - tb))
    r = math.exp(lerp(math.log(ra), math.log(rb), s))
    da, db = (pa - ta) / ra, (pb - tb) / rb
    d = da + (db - da) * s
    d /= np.linalg.norm(d)
    return tgt + d * r, tgt, fa + (fb - fa) * s


def slide_cam(a, b, s):
    return a[0] + (b[0] - a[0]) * s, a[1] + (b[1] - a[1]) * s, a[2] + (b[2] - a[2]) * s


def cam(t):
    if t < T_UP0:
        p, g, f = hook_cam(t)
    elif t < T_UP1:
        p, g, f = blend_cam(hook_cam(T_UP0), ov_cam(t), sio((t - T_UP0) / (T_UP1 - T_UP0)))
    elif t < T_DIVE0:
        p, g, f = ov_cam(t)
    elif t < T_DIVE1:
        u = (t - T_DIVE0) / (T_DIVE1 - T_DIVE0)
        p, g, f = blend_cam(ov_cam(t), glass_cam(t), e_in(u, 2) * 0.35 + e_out(u, 3) * 0.65)
    elif t < T_PAN0:
        p, g, f = glass_cam(t)
    elif t < T_PAN1:
        p, g, f = slide_cam(glass_cam(t), bench_cam(t), sio((t - T_PAN0) / (T_PAN1 - T_PAN0)))
    elif t < T_BACK0:
        p, g, f = bench_cam(t)
    elif t < T_BACK1:
        p, g, f = slide_cam(bench_cam(t), hook_cam(0.0), sio((t - T_BACK0) / (T_BACK1 - T_BACK0)))
    else:
        p, g, f = hook_cam(0.0)
    d = (p - g) / np.linalg.norm(p - g)
    el = math.degrees(math.asin(max(-1.0, min(1.0, d[1]))))
    return p, g, blend_up(min(el, 89.9)), f


def cam_row_at(t):
    pos, tgt, up, fov = cam(t)
    r, u, f = P3.look_at(pos, tgt, up)
    return P3.cam_row(pos, r, u, f, fov), float(np.linalg.norm(tgt - pos))


def seg(t):
    for a, b in ((0.0, T_UP0 + 0.45), (T_UP0 + 0.45, T_DIVE1 - 0.2), (T_DIVE1 - 0.2, T_PAN1 - 0.1),
                 (T_PAN1 - 0.1, T_BACK0 + 0.3), (T_BACK0 + 0.3, DUR)):
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
        p, vis = puck_state(tk)
        pk[j] = (p[0], p[1], p[2], puck_rot(tk), vis, 0.0, tk)
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, SPP, fidx + 26, cams, lens, pk, R15.logo_tex(), base, puck, cov)
    return P3.tonemap(base), P3.tonemap(puck), cov


# ================================================================= Overlays
def draw_net_lines(ctx, row):
    for pl in NET:
        xy, z = proj(row, pl)
        if (z < 2).any():
            continue
        stroke_poly(ctx, xy, (112, 120, 136), 0.55, float(np.clip(0.4 * px_per_in(row, z.mean()), 0.8, 3.0)))


def glass_edges(ctx, row):
    """Kanten und Fugen der Glasscheiben."""
    for q in GLASS:
        xy, z = proj(row, q)
        if (z < 3).any():
            continue
        w = float(np.clip(px_per_in(row, z.mean()) * 0.8, 0.8, 5))
        stroke_poly(ctx, xy[[0, 3]], (190, 198, 210), 0.65, w)
        stroke_poly(ctx, xy[[2, 3]], (250, 252, 255), 0.95, w * 1.6)
        stroke_poly(ctx, xy[[2, 3]], (170, 180, 196), 0.5, w * 0.5)


def zone_shade(ctx, row, a):
    if a <= 0:
        return
    pts = [(ZONE_X, SZ)] + [(x, z) for x, z in WALL if x < ZONE_X] + [(ZONE_X, -SZ)]
    xy, z = proj(row, R22.poly3(pts, 0.08))
    if (z < 3).any():
        return
    fill_poly(ctx, xy, BLUE, 0.13 * a)


def line_glow(ctx, row, x, col, a):
    if a <= 0:
        return
    zs = np.linspace(-SZ + 2, SZ - 2, 60)
    xy, z = proj(row, np.stack([np.full_like(zs, x), np.full_like(zs, 0.12), zs], 1))
    if (z < 3).any():
        return
    w = float(np.clip(px_per_in(row, z.mean()) * 12, 3, 26))
    stroke_poly(ctx, xy, col, 0.25 * a, w * 3)
    stroke_poly(ctx, xy, col, 0.9 * a, w)


def trail(ctx, row, pts, a=1.0):
    if len(pts) < 2 or a <= 0:
        return
    xy, z = proj(row, np.asarray(pts))
    if (z < 3).any():
        return
    stroke_poly(ctx, xy, ORANGE, 0.2 * a, 20)
    stroke_poly(ctx, xy, ORANGE, 0.85 * a, 6)


def path_trail(t):
    """Bisher geflogene Strecke der aktuellen Szene (für die orange Spur)."""
    if T_UP1 <= t < T_DIVE0 and t > T_L1:
        u1 = c01((t - T_L1) / D1)
        return [s1(u) for u in np.linspace(0, u1, 30)], 1 - smooth(T_DIVE0 - 0.4, T_DIVE0, t)
    if T_L2 < t < T_PAN0:
        tl = min(t - T_L2, 0.9)
        return [s2(x) for x in np.linspace(0, tl, 40)], 1 - smooth(T_PAN0 - 0.3, T_PAN0, t)
    if T_L3 < t < T_BACK0:
        u1 = c01((t - T_L3) / D3)
        return [arc(L3, E3, APEX3, u) for u in np.linspace(0, u1, 30)], 1 - smooth(T_BACK0 - 0.3, T_BACK0, t)
    if t < T_UP0:
        return [s1(u) for u in np.linspace(0.0, 0.18 + 0.40 * t / T_UP0, 30)], 1 - smooth(T_UP0 - 0.2, T_UP0, t)
    return [], 0.0


def dashed_ring(ctx, row, p, r_in, a, t, col=ORANGE, min_px=0):
    if a <= 0:
        return
    xy, z = projected(row, p)
    if z <= 0:
        return
    r = max(px_per_in(row, z) * r_in, min_px) + 6 * math.sin(t * 9)
    ctx.set_source_rgba(col[0] / 255, col[1] / 255, col[2] / 255, 0.9 * a)
    ctx.set_line_width(7)
    ctx.set_dash([26, 16], -t * 60)
    ctx.arc(xy[0], xy[1], r, 0, 2 * math.pi)
    ctx.stroke()
    ctx.set_dash([])


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


def texts(L, t, row):
    A = VO_START
    if t < T_UP0 + 0.1:
        k = 1 - smooth(T_UP0 - 0.1, T_UP0 + 0.1, t)
        two_lines(L, "WHY IS THIS", "2 MINUTES?", INK, RED, 480, 640, 140, 178, k)
        reveal(L, line_img("NHL RULES EXPLAINED  ·  PART 4", 34, 800, ORANGE, track=8), W / 2, 360, 1.0,
               smooth(T_UP0 - 0.15, T_UP0 + 0.05, t))
    if T_UP1 - 0.2 <= t < T_DIVE0:
        fade = 1 - smooth(T_DIVE0 - 0.25, T_DIVE0, t)
        label_at(L, row, np.array([-800.0, 0, -60.0]), "OWN ZONE", BLUE, 0, 0,
                 smooth(T_ZONE, T_ZONE + 0.2, t) * fade * (1 - smooth(T_EVEN - 0.15, T_EVEN, t)), 46)
    slam(L, "2:00", 250, RED, W / 2, 470, t, T_PEN, T_DIVE0 + 0.05)
    if T_PEN + 0.15 <= t < T_DIVE0:
        reveal(L, line_img("DELAY OF GAME", 44, 850, INK, track=8), W / 2, 610, c01((t - T_PEN - 0.15) / 0.2),
               smooth(T_DIVE0 - 0.15, T_DIVE0, t))
    slam(L, "EVEN BY ACCIDENT", 84, INK, W / 2, 1450, t, T_EVEN, T_DIVE0)
    if T_HIT <= t < T_PAN0:
        label_at(L, row, H2, "OFF THE GLASS", ORANGE, -40, -90,
                 smooth(T_HIT, T_HIT + 0.15, t) * (1 - smooth(T_PAN0 - 0.2, T_PAN0, t)), 44)
    slam(L, "NO PENALTY.", 160, GREEN, W / 2, 440, t, T_NO1, T_PAN0)
    if T_PAN1 - 0.1 <= t < T_BACK0:
        label_at(L, row, np.array([-150.0, BH + 30, SZ]), "NO GLASS", ORANGE, 0, 0,
                 smooth(word("bench", 0.2), word("bench", 0.4), t) * (1 - smooth(T_BACK0 - 0.2, T_BACK0, t)), 44)
    slam(L, "OVER THE BENCH", 84, INK, W / 2, 1450, t, word("bench", 0.34), T_BACK0)
    slam(L, "NO PENALTY.", 160, GREEN, W / 2, 440, t, T_NO2, T_BACK0)
    if t >= A["cta"]:
        slam(L, "FAIR RULE", 120, INK, W / 2, 450, t, A["cta"])
        slam(L, "OR TOO HARSH?", 120, ORANGE, W / 2, 590, t, A["cta"] + 0.35)
        if t >= A["cta"] + 0.7:
            reveal(L, line_img("COMMENT BELOW  ·  FOLLOW FOR PART 5", 34, 800, INK, track=6), W / 2, 1420,
                   c01((t - A["cta"] - 0.7) / 0.25))


# ================================================================= Bild
_GS = None


def glass_streaks():
    """Diagonale Spiegelstreifen (Bildraum) für die Glasflächen."""
    global _GS
    if _GS is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = (xx * 0.8 + yy * 0.45) / 140.0
        _GS = (np.clip(np.sin(d) * 1.6 - 0.9, 0, 1) + np.clip(np.sin(d * 0.37 + 1.3) * 1.4 - 1.0, 0, 1) * 0.6)
    return _GS


def compose(t, fidx):
    base, puck, cov = render3d(t, fidx)
    row, _ = cam_row_at(t)
    campos = cam(t)[0]
    p, vis = puck_state(t)
    lo_s, lo_c = surface()
    hi_s, hi_c = surface()
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ov = T_UP0 + 0.3 < t < T_DIVE0 + 0.3
    if ov:
        zone_shade(lo_c, row, smooth(T_ZONE - 0.05, T_ZONE + 0.25, t))
        line_glow(lo_c, row, -300.0, LINE_BLUE, smooth(T_ZONE - 0.05, T_ZONE + 0.25, t) * 0.8)
        draw_net_lines(lo_c, row)
    glass_edges(lo_c, row)
    img = over(base, *surf_rgba(lo_s))
    meshes = BOARDS + (GOAL_FRAME if ov else [])
    if vis > 0:
        meshes = meshes + [G.cyl_mesh(p - np.array([0, 0.5, 0]), 1.5, 1.0, "occluder", group=1)]
    m_rgb, m_a, shadow, plane_a = M3.render(meshes, row, W, H, campos, alpha_by_group=np.array([1.0, 0.0], np.float32),
                                            extra_planes=[(GLASS_ALL, 1.0)], shadow_light=(0.02, 1.0, -0.03))
    img = img * (1 - 0.15 * shadow[..., None])
    pa = cov[..., None]
    img = img * (1 - pa) + puck * pa
    img = img * (1 - m_a[..., None]) + m_rgb
    k = (0.30 * plane_a)[..., None]                                        # Glas: bläulich + Spiegelstreifen
    img = img * (1 - k) + np.array([0.70, 0.82, 0.94], np.float32) * k
    img = img + (glass_streaks() * plane_a * 0.10)[..., None]
    # Markierungen
    pts, ta = path_trail(t)
    trail(hi_c, row, pts, ta)
    if ov and T_UP1 - 0.1 < t < T_DIVE0:
        tok_a = smooth(T_UP1 - 0.1, T_UP1 + 0.15, t) * (1 - smooth(T_DIVE0 - 0.25, T_DIVE0, t))
        token(hi_c, row, L1 + np.array([-30.0, 0, -22.0]), BLUE, 30, tok_a)
        if vis > 0:
            puck_marker(hi_c, row, p, t)
        whistle_ring(hi_c, row, s1(0.42), t, T_L1 + 0.5 * D1, RED)
    if t < T_UP0:
        dashed_ring(hi_c, row, p, 6.0, smooth(0.15, 0.35, t) * (1 - smooth(T_UP0 - 0.15, T_UP0, t)), t)
    if T_DIVE1 - 0.2 < t < T_PAN0 or T_PAN1 - 0.1 < t < T_BACK0:
        lp = L2 if t < T_PAN0 else L3
        tok_a = smooth(T_DIVE1 - 0.2, T_DIVE1, t) if t < T_PAN0 else smooth(T_PAN1 - 0.1, T_PAN1 + 0.1, t)
        tok_a *= (1 - smooth(T_PAN0 - 0.2, T_PAN0, t)) if t < T_PAN0 else (1 - smooth(T_BACK0 - 0.2, T_BACK0, t))
        token(hi_c, row, lp + np.array([-26.0, 0, -18.0]), BLUE, 22, tok_a)
    whistle_ring(hi_c, row, H2, t, T_HIT, ORANGE)
    whistle_ring(hi_c, row, T2, t, T_NO1, GREEN)
    whistle_ring(hi_c, row, E3, t, T_NO2, GREEN)
    img = over(img, *surf_rgba(hi_s))
    if T_PEN <= t < T_PEN + 0.3:
        a = 0.2 * (1 - (t - T_PEN) / 0.3)
        img = img * (1 - a) + np.array([1.0, 0.1, 0.12], np.float32) * a
    img = np.clip(img, 0, 1)
    pil = Image.fromarray((img * 255).astype(np.uint8)).convert("RGBA")
    # "D"-Buchstaben auf den Markern
    if ov and T_UP1 - 0.1 < t < T_DIVE0 - 0.25:
        xy, z = projected(row, L1 + np.array([-30.0, 0, -22.0]))
        if z > 0:
            gi = line_img("D", 28, 900, BLUE)
            put(L, gi, xy[0] - gi.width / 2, xy[1] - gi.height / 2)
    texts(L, t, row)
    pil.alpha_composite(L)
    arr = np.asarray(pil.convert("RGB")).astype(np.float32) / 255
    lc = min([t - c for c in (T_PEN, T_NO1, T_NO2) if t >= c] + [t + 0.5])
    zp = 1 + 0.035 * math.exp(-lc * 14)
    if zp > 1.002:
        im2 = Image.fromarray((arr * 255).astype(np.uint8))
        w2, h2 = W / zp, H / zp
        im2 = im2.transform((W, H), Image.EXTENT, ((W - w2) / 2, (H - h2) / 2, (W + w2) / 2, (H + h2) / 2), Image.BILINEAR)
        arr = np.asarray(im2).astype(np.float32) / 255
    arr = arr * (0.55 + 0.45 * vignette())
    arr += np.random.default_rng(fidx).normal(0, 0.008, arr.shape[:2])[..., None]
    return (np.clip(arr, 0, 1) * 255).astype(np.uint8)


# ================================================================= Ton
SR = 44100


def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(26)
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

    def slap(vol=0.6):
        x = tt(0.25)
        return (hp(noise(0.25), 2) * np.exp(-x * 60) * 0.8 + np.sin(2 * np.pi * 120 * x) * np.exp(-x * 25) * 0.6) * vol

    def thunk(vol=0.7):
        x = tt(0.6)
        body = np.sin(2 * np.pi * 85 * x) * np.exp(-x * 14)
        rattle = lp(hp(noise(0.6), 30), 3) * np.exp(-x * 9) * 0.5
        return np.tanh((body + rattle) * 2.0) * vol

    def knock(vol=0.5):
        x = tt(0.3)
        return (np.sin(2 * np.pi * 330 * x) * 0.6 + np.sin(2 * np.pi * 510 * x) * 0.4) * np.exp(-x * 28) * vol

    def whoosh(dur=0.7, vol=0.5):
        x = tt(dur)
        env = np.sin(np.pi * np.clip(x / dur, 0, 1)) ** 2
        return hp(lp(noise(dur), 6), 40) * env * vol

    def slowmo(dur=1.4, vol=0.4):
        x = tt(dur)
        env = np.sin(np.pi * np.clip(x / dur, 0, 1)) ** 1.5
        return lp(noise(dur), 40) * env * vol * 3.0

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
        if tb > DUR - 0.5:
            continue
        soft = tb < T_UP0                                              # Zeitlupe: nur Kick + Bass
        if pos in (0.0, 2.5):
            put_(mus, kick(0.7 if soft else 1.0), tb)
        if pos in (1.0, 3.0) and not soft:
            put_(mus, clap(), tb)
        if not soft:
            put_(mus, hat(0.12 if k8 % 2 == 0 else 0.07), tb, pan=0.3)
        if pos == 0.0:
            put_(mus, b808(roots[int(b // 4) % 4], 2.3 * B), tb)
        put_(mus, bell(mel[k8 % 8]), tb, pan=-0.2)
    put_(sfx, slowmo(T_UP0, 0.5), 0.0)
    put_(sfx, whoosh(T_UP1 - T_UP0 + 0.1, 0.45), T_UP0)
    put_(sfx, click(0.5), T_ZONE)
    put_(sfx, slap(0.7), T_L1)
    put_(sfx, whoosh(0.4, 0.35), T_L1 + 0.05)
    put_(sfx, whistle(0.7, 0.55), T_L1 + 0.5)
    put_(sfx, stamp(1.0), T_PEN)
    put_(sfx, whoosh(T_DIVE1 - T_DIVE0 + 0.1, 0.5), T_DIVE0)
    put_(sfx, slap(0.6), T_L2)
    put_(sfx, thunk(0.8), T_HIT)
    put_(sfx, ding(0.45), T_NO1)
    put_(sfx, stamp(0.5), T_NO1)
    put_(sfx, whoosh(T_PAN1 - T_PAN0 + 0.1, 0.5), T_PAN0)
    put_(sfx, slap(0.6), T_L3)
    put_(sfx, knock(0.6), T_L3 + D3)
    put_(sfx, ding(0.45), T_NO2)
    put_(sfx, stamp(0.5), T_NO2)
    put_(sfx, whoosh(T_BACK1 - T_BACK0 + 0.1, 0.45), T_BACK0)
    put_(sfx, stamp(0.7), VO_START["cta"] + 0.35)
    voice = np.zeros(n)
    for k in VO_KEYS:
        tmp = os.path.join(HERE, f"_vo_{k}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "voice", f"reel26_{k}.wav"),
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
    duck = 1 - 0.72 * np.clip(venv / 0.06, 0, 1)
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
    for i, k in enumerate(VO_KEYS[:-1]):
        nxt = VO_KEYS[i + 1]
        if VO_START[k] + VO_DUR[k] > VO_START[nxt] + 0.35:
            print(f"Warnung: Satz {k} überlappt {nxt} ({VO_START[k] + VO_DUR[k]:.2f} > {VO_START[nxt]:.2f})")
    make_audio("audio_overglass.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_overglass.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
           "-ar", "44100", "-shortest", "-movflags", "+faststart", "reel26_overglass.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(0.8, 9999)).save("reel26_thumbnail.jpg", quality=92)
    print("fertig: reel26_overglass.mp4")


if __name__ == "__main__":
    main()
