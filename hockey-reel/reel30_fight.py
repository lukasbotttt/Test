"""Reel 30: NHL RULES EXPLAINED – PART 7: WHY IS FIGHTING ALLOWED? (neuer "Fight Night"-Look, 14,8 s).

Fakten (NHL Official Rules 2023–24):
- Regel 46.14: Wer kämpft, bekommt eine große Strafe (Major); Regel 20.1: Major = 5 Minuten. Kein Platzverweis.
- Regel 46.11: Der Anstifter ("instigator") bekommt zusätzlich 2 Minuten (instigating minor) und eine 10-Minuten-
  Disziplinarstrafe -> 2 + 5 + 10 = 17 Strafminuten.
- IIHF-Regelbuch Art. 46.1 (gilt international, z. B. Olympia/WM): "Fighting is not part of international ice
  hockey's DNA" – Major + automatische Spieldauer-Disziplinarstrafe (Game Misconduct) = Platzverweis.
Look: dunkle Arena mit Spotlicht (Licht wird pro Pixel auf der Eisebene berechnet), 3D-Handschuhe fallen aufs Eis,
Spieler als glänzende 3D-Chips, Strafbänke mit Türen, Glas und LED-Uhren. Bewusst ohne Spielerkörper.
Stimme: Kokoro "Michael" (tts_kokoro.py, Apache-2.0), Sätze einzeln, 1,08x.
Aufruf: python3 reel30_fight.py vo     -> voice/reel30_*.wav
        python3 reel30_fight.py audio  -> nur Ton neu mischen
        python3 reel30_fight.py        -> reel30_fight.mp4
"""
import json
import math
import os
import subprocess
import sys
import time
import wave

import cairocffi as cairo
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import gaussian_filter

import puck3d as P3
import reel15_puck as R15
import reel18_dangle as R18
import mesh3d as M3
import reel25_goalline as G
import reel26_overglass as R26
import reel28_emptynet as R28
from reel15_puck import (W, H, FPS, SPP, KSUB, SHUTTER, c01, smooth, sio, e_out, e_in, lerp, line_img, reveal, put,
                         proj, projected, px_per_in, stroke_poly, surface, surf_rgba, over)
from reel22_trapezoid import slam
from reel28_emptynet import blend_cam

HERE = R15.HERE
WHITE = (255, 255, 255)
RED = (235, 40, 50)
BLUE = (60, 130, 255)
ORANGE = (255, 120, 30)
GREEN = (40, 200, 110)
GREY = (150, 156, 170)
LED = (255, 52, 40)
TEMPO = 1.08

# ================================================================= Timeline aus dem Voiceover
VO_LINES = [
    ("q", "Why is fighting allowed in the NHL?"),
    ("twist", "Technically, it isn't. It's a five-minute major."),
    ("box", "But nobody gets thrown out. Both sit, then play on."),
    ("intl", "In international hockey? Automatic ejection."),
    ("inst", "And if you start it: seventeen minutes in the box."),
    ("cta", "Should the NHL ban fighting? Yes or no?"),
]
VO_KEYS = [k for k, _ in VO_LINES]
VO_START = {"q": 0.15, "twist": 1.85, "box": 4.1, "intl": 6.85, "inst": 9.25, "cta": 11.6}
DUR = 14.8


def at(key, s):
    """Zeitpunkt s Sekunden nach Satzbeginn (im fertigen, 1,08x schnelleren Satz)."""
    return VO_START[key] + s


T_UP0, T_UP1 = 1.75, 2.5               # Hook -> über der Mitte
T_ISNT = at("twist", 0.56)             # "it isn't"
T_MAJOR = at("twist", 1.30)            # "five-minute major"
T_BX0, T_BX1 = 3.95, 4.75              # Flug zu den Strafbänken
T_GO = 4.3                             # Chips fahren in die Boxen
T_IN = 5.35
T_SIT = at("box", 1.46)                # "both sit" -> Uhren laufen
T_PLAY = at("box", 2.19)               # "play on" -> zurück aufs Eis
T_INTL = VO_START["intl"]
T_EJECT = at("intl", 1.24)             # "automatic ejection"
T_REW = VO_START["inst"]               # Rückspulen in die Boxen
T_START = at("inst", 0.28)             # "start it"
T_17 = at("inst", 0.98)                # "seventeen minutes"
T_EN0, T_EN1 = 11.45, 12.3             # zurück in die Mitte
T_CTA = VO_START["cta"]

# ================================================================= Geometrie (Zoll)
BH, GH, SZ = R26.BH, R26.GH, R26.SZ
BOX_X = (-105.0, 105.0)                # Strafbank Blau (links), Rot (rechts)
DOOR_HALF = 27.0
BZ0, BZ1 = -SZ - 2.0, -SZ - 70.0       # Boxtiefe hinter der Bande
BOX_WALLS = (-175.0, -35.0, 35.0, 175.0)


def side_pieces():
    """Bande auf der Strafbank-Seite (z = -SZ) mit Lücken für die Türen."""
    edges = [-864.0]
    for bx in BOX_X:
        edges += [bx - DOOR_HALF, bx + DOOR_HALF]
    edges.append(864.0)
    return [np.array([(x, -SZ) for x in np.arange(a, b + 0.1, 6.0)]) for a, b in zip(edges[::2], edges[1::2])]


def rest_wall():
    """Rest der Bande (R28.WALL ohne die gerade Strafbank-Seite)."""
    wl = R28.WALL
    keep = ~((wl[:, 1] < -SZ + 0.5) & (np.abs(wl[:, 0]) < 863.0))
    idx = np.flatnonzero(~keep)
    a, b = idx[0], idx[-1]
    return [wl[: a], wl[b + 1:]]


def board_strip(pts, normal=None):
    p = np.stack([pts[:, 0], np.zeros(len(pts)), pts[:, 1]], 1)
    if normal is None:
        n2 = R26.inward(pts)
        n3 = np.stack([n2[:, 0], np.zeros(len(n2)), n2[:, 1]], 1)
    else:
        n3 = np.tile(normal, (len(pts), 1))
    out = [R26.strip(p, p + [0, BH, 0], n3, "board_white")]
    k0 = p + n3 * 0.12
    out.append(R26.strip(k0, k0 + [0, 9.0, 0], n3, "kick_yellow"))
    out.append(R26.strip(p + [0, BH, 0], p + [0, BH, 0] - n3 * 5.0, np.tile([0.0, 1.0, 0.0], (len(p), 1)), "board_white"))
    return out


def glass_along(pts, normal):
    out = []
    seg_ = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    marks = np.append(np.arange(0, seg_[-1], 60.0), seg_[-1])
    xs, zs = np.interp(marks, seg_, pts[:, 0]), np.interp(marks, seg_, pts[:, 1])
    for i in range(len(marks) - 1):
        if marks[i + 1] - marks[i] < 1.0:
            continue
        a = np.array([xs[i] - normal[0] * 1.5, BH, zs[i] - normal[2] * 1.5])
        b = np.array([xs[i + 1] - normal[0] * 1.5, BH, zs[i + 1] - normal[2] * 1.5])
        out.append(np.array([a, b, b + [0, GH, 0], a + [0, GH, 0]]))
    return out


def arena():
    meshes, glass = [], []
    for pts in rest_wall():
        meshes += board_strip(pts)
    for pts in side_pieces():
        meshes += board_strip(pts, np.array([0.0, 0.0, 1.0]))
        glass += glass_along(pts, np.array([0.0, 0.0, 1.0]))
    for x0, x1 in R26.BENCHES:                                           # Spielerbänke (ohne Glas davor)
        meshes.append(R26.box_mesh(x0 + 12, x1 - 12, 0.0, 17.0, SZ + 22, SZ + 40, "bench_seat"))
    # Strafbänke: Boden, Rückwand, Trennwände, Sitzbänke, Glas
    meshes.append(R26.box_mesh(BOX_WALLS[0], BOX_WALLS[-1], -0.4, 0.15, BZ1, BZ0, "box_floor"))
    back = np.array([[x, 0.0, BZ1] for x in np.linspace(BOX_WALLS[0], BOX_WALLS[-1], 12)])
    meshes.append(R26.strip(back, back + [0, BH, 0], np.tile([0.0, 0.0, 1.0], (12, 1)), "board_white"))
    glass.append(np.array([[BOX_WALLS[0], BH, BZ1], [BOX_WALLS[-1], BH, BZ1], [BOX_WALLS[-1], BH + GH, BZ1],
                           [BOX_WALLS[0], BH + GH, BZ1]]))
    for xw in BOX_WALLS:
        side = np.array([[xw, 0.0, z] for z in np.linspace(BZ0, BZ1, 5)])
        meshes.append(R26.strip(side, side + [0, BH, 0], np.tile([1.0, 0.0, 0.0], (5, 1)), "board_white"))
        glass.append(np.array([[xw, BH, BZ0], [xw, BH, BZ1], [xw, BH + GH, BZ1], [xw, BH + GH, BZ0]]))
    for x0, x1 in ((BOX_WALLS[0], BOX_WALLS[1]), (BOX_WALLS[2], BOX_WALLS[3])):
        meshes.append(R26.box_mesh(x0 + 10, x1 - 10, 0.0, 17.0, BZ1 + 2, BZ1 + 20, "bench_seat"))
    return meshes, glass


ARENA, GLASS = arena()
GLASS_ALL = np.concatenate(GLASS)


# ================================================================= 3D-Handschuh
GLOVE_SCALE = 1.45


def glove_local():
    nu, nr = 64, 28
    us = np.linspace(0.0, 14.0, nu)
    verts, uvw = [], []
    for u in us:
        if u < 4.8:
            hh, hw = 3.0 + 0.25 * (4.8 - u) / 4.8, 2.95
        elif u < 9.0:
            s = (u - 4.8) / 4.2
            hh, hw = lerp(3.0, 2.45, s), lerp(2.95, 2.7, s)
        else:
            hh, hw = 2.25 + 0.45 * abs(math.sin(math.pi * (u - 9.0) / 1.25)), 2.65
        e = 14.0 - u
        k = math.sqrt(max(0.0, 1 - max(0.0, 1 - e / 1.2) ** 2)) if e < 1.2 else 1.0
        k0 = math.sqrt(max(0.0, 1 - max(0.0, 1 - u / 0.35) ** 2)) if u < 0.35 else 1.0
        k = max(min(k, 0.6 + 0.4 * k0), 0.08)
        for j in range(nr):
            th = 2 * math.pi * j / nr
            c, s = math.cos(th), math.sin(th)
            w = hw * k * math.copysign(abs(c) ** 0.7, c)
            y = hh + hh * (0.55 + 0.45 * k) * math.copysign(abs(s) ** 0.7, s)
            verts.append((u, y, w))
    tris = list(map(tuple, M3.grid_tris(nu, nr)))
    tris += M3.cap(verts, (nu - 1) * nr, nr, (14.0, 2.4, 0.0))
    tris += [(t[1], t[0], t[2]) for t in M3.cap(verts, 0, nr, (0.0, 3.0, 0.0))]
    v = np.array(verts)
    t = np.array(tris, np.int32)
    hand = M3.Mesh(v, M3.vertex_normals(v, t), t, 0, v.copy())
    thumb = M3.tube_along([(5.6, 2.2, 2.6), (7.8, 2.6, 3.4), (9.8, 2.4, 3.3), (10.9, 2.1, 2.8)],
                          [1.25, 1.2, 1.05, 0.8], lambda s: 0, nr=16)
    thumb.uvw = thumb.v.copy()
    m = M3.merge([hand, thumb])
    m.v = (m.v - np.array([7.0, 2.5, 0.0])) * GLOVE_SCALE                    # Mitte in den Ursprung, größer (gut lesbar)
    return m


GLOVE = glove_local()


def rot(ax, a):
    c, s = math.cos(a), math.sin(a)
    if ax == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if ax == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


# (Material, Landeplatz, Richtung, Landezeit, Startdrehung)
GLOVES = [("glove_blue", (-36.0, 20.0), 0.6, 0.40, (1.9, 2.6, 0.7)),
          ("glove_red", (32.0, -22.0), 2.4, 0.58, (-2.2, 1.7, -1.1)),
          ("glove_blue", (-14.0, -34.0), -0.9, 0.80, (2.6, -1.9, 0.9)),
          ("glove_red", (22.0, 30.0), 1.4, 1.02, (-1.6, -2.4, 1.3))]


def glove_mesh(i, t):
    mat, (lx, lz), head, tl, (a0, b0, c0) = GLOVES[i]
    t0 = tl - 0.75
    s = c01((t - t0) / (tl - t0))
    q = 1 - e_out(s, 2.2)
    R = rot("y", head + b0 * q) @ rot("z", a0 * q) @ rot("x", c0 * q)
    if t > tl:
        lt = t - tl
        R = R @ rot("z", 0.22 * math.exp(-lt * 7) * math.sin(lt * 26)) @ rot("x", 0.12 * math.exp(-lt * 7) * math.sin(lt * 21))
    v = GLOVE.v @ R.T
    n = GLOVE.n @ R.T
    y_floor = -v[:, 1].min()
    if t < tl:
        y = lerp(38.0, y_floor, s * s)
    else:
        lt = t - tl
        y = y_floor + 3.2 * math.exp(-lt * 7) * abs(math.sin(lt * 15))
    drift = np.array([lx, 0.0, lz]) * (1 - 0.18 * q) + np.array([lx, 0.0, lz]) * 0.05 * c01((t - tl) / 0.6)
    m = M3.Mesh(v + np.array([drift[0], y, drift[2]]), n, GLOVE.t, M3.MAT_IDS[mat], GLOVE.uvw)
    return m


# ================================================================= Spieler-Chips
CHIP_R = 14.0


def chip_meshes(p, team, a=1.0):
    if a <= 0.02:
        return []
    mat = "chip_blue" if team == 0 else "chip_red"
    base = G.cyl_mesh(np.array([p[0], 0.0, p[2]]), CHIP_R, 3.0, mat, nr=56)
    top = G.cyl_mesh(np.array([p[0], 3.0, p[2]]), CHIP_R * 0.74, 0.35, "chip_top", nr=56)
    return [base, top]


def door(bx):
    return np.array([bx, 0.0, -SZ + 40.0])


def seat(bx):
    return np.array([bx, 0.0, BZ1 + 32.0])


def fight_pos(t, team):
    th = 4.05 + 1.25 * t                                                # Blau steht beim Abgang links
    r = 70.0 - 18.0 * sum(math.exp(-((t - tp) / 0.09) ** 2) for tp in (1.25, 1.55, 1.9, 2.25))
    ang = th + (0.0 if team == 0 else math.pi)
    return np.array([r * math.cos(ang), 0.0, r * math.sin(ang)])


def chip_state(t, team):
    """(Position, Deckkraft) – Team 0 = Blau (Anstifter), 1 = Rot."""
    bx = BOX_X[team]
    if t < T_GO:
        return fight_pos(t, team), 1.0
    p_go = fight_pos(T_GO, team)
    if t < T_IN:
        u = sio(c01((t - T_GO) / (T_IN - T_GO)))
        q = R28.bez(p_go, door(bx) + [0, 0, 30.0], door(bx), min(u * 1.35, 1.0))
        if u > 0.74:
            q = door(bx) + (seat(bx) - door(bx)) * sio((u - 0.74) / 0.26)
        return q, 1.0
    if t < T_PLAY:
        return seat(bx), 1.0
    out = door(bx) + np.array([0.0, 0.0, 70.0])
    if t < T_EJECT:
        u = sio(c01((t - T_PLAY) / 0.55))
        return seat(bx) + (out - seat(bx)) * u, 1.0
    if t < T_REW:
        u = e_in(c01((t - T_EJECT - 0.15) / 0.8), 2)
        side = np.array([-1.0 if team == 0 else 1.0, 0.0, 0.25]) * 420.0
        return out + side * u, 1 - smooth(T_EJECT + 0.55, T_EJECT + 0.95, t)
    if t < T_EN0:
        return seat(bx), smooth(T_REW, T_REW + 0.2, t)
    return seat(bx), 1 - smooth(T_EN0, T_EN0 + 0.2, t)


# ================================================================= Kamera
def hook_cam(t):
    p0, p1 = np.array([-84.0, 44.0, 156.0]), np.array([-70.0, 39.0, 132.0])
    return p0 + (p1 - p0) * e_out(c01(t / T_UP0), 2), np.array([0.0, 4.0, -8.0]), 46.0


def top_cam(t):
    return np.array([-210.0, 290.0, 330.0]) + np.array([20.0, -10.0, -20.0]) * c01((t - T_UP1) / 1.5), \
        np.array([0.0, 0.0, -15.0]), 40.0


def box_cam(t):
    s = c01((t - T_BX1) / (T_EN0 - T_BX1))
    return np.array([0.0, 470.0, -20.0]) + np.array([0.0, -30.0, -25.0]) * sio(s), np.array([0.0, 10.0, -505.0]), 50.0


def end_cam(t):
    u = c01((t - T_EN1) / (DUR - T_EN1))
    return hook_cam(T_UP0 * (1 - sio(u)) + 0.0)


def cam(t):
    if t < T_UP0:
        p, g, f = hook_cam(t)
    elif t < T_UP1:
        p, g, f = blend_cam(hook_cam(T_UP0), top_cam(T_UP1), sio((t - T_UP0) / (T_UP1 - T_UP0)))
    elif t < T_BX0:
        p, g, f = top_cam(t)
    elif t < T_BX1:
        p, g, f = blend_cam(top_cam(T_BX0), box_cam(T_BX1), sio((t - T_BX0) / (T_BX1 - T_BX0)))
    elif t < T_EN0:
        p, g, f = box_cam(t)
    elif t < T_EN1:
        p, g, f = blend_cam(box_cam(T_EN0), end_cam(T_EN1), sio((t - T_EN0) / (T_EN1 - T_EN0)))
    else:
        p, g, f = end_cam(t)
    return p, g, np.array([0.0, 1.0, 0.0]), f


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
        pk[j] = (0.0, -50.0, 0.0, 0.0, 0.0, 0.0, tk)                    # kein Puck in diesem Video
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, SPP, fidx + 30, cams, lens, pk, R15.logo_tex(), base, puck, cov)
    return P3.tonemap(base)


# ================================================================= Licht (dunkle Arena + Spots)
_NDC = None


def ice_hit(row):
    """Schnittpunkt jedes Pixelstrahls mit der Eisebene (x, z) + Maske (Strahl trifft das Eis)."""
    global _NDC
    if _NDC is None:
        xs = (np.arange(W) + 0.5) / W * 2 - 1
        ys = 1 - (np.arange(H) + 0.5) / H * 2
        _NDC = np.meshgrid(xs.astype(np.float32), ys.astype(np.float32))
    nx, ny = _NDC
    pos, r, u, f, tanh = row[0:3], row[3:6], row[6:9], row[9:12], row[12]
    asp = W / H
    d = f[None, None, :] + nx[..., None] * (tanh * asp) * r[None, None, :] + ny[..., None] * tanh * u[None, None, :]
    dy = d[..., 1]
    hit = dy < -1e-4
    tt = np.where(hit, -pos[1] / np.where(hit, dy, -1.0), 0.0)
    return pos[0] + tt * d[..., 0], pos[2] + tt * d[..., 2], hit


def spots(t):
    """[(x, z, Radius, Stärke, Farbe)]"""
    center = 1.0 - 0.75 * smooth(T_BX0, T_BX1, t) + 0.75 * smooth(T_EN0, T_EN1, t)
    boxl = smooth(T_BX0 + 0.2, T_BX1 + 0.2, t) * (1 - smooth(T_EN0, T_EN1, t))
    out = [(0.0, -25.0, 150.0, 0.95 * center, (1.0, 0.97, 0.92))]
    for bx in BOX_X:
        out.append((bx, BZ1 + 32.0, 110.0, 0.95 * boxl, (1.0, 0.95, 0.88)))
    out.append((0.0, -SZ + 60.0, 230.0, 0.42 * boxl, (0.85, 0.9, 1.0)))
    for team in (0, 1):
        p, a = chip_state(t, team)
        col = (0.25, 0.45, 1.0) if team == 0 else (1.0, 0.18, 0.2)
        out.append((p[0], p[2], 34.0, 0.55 * a, col))
    return out


def light_map(row, t, mesh_a=None, mesh_pos=None):
    x, z, hit = ice_hit(row)
    if mesh_a is not None:                                              # Gitter: Licht am echten Ort
        k = np.clip(mesh_a, 0, 1)
        safe = np.where(k[..., None] > 0.01, mesh_pos / np.maximum(k, 1e-3)[..., None], 0.0)
        x = x * (1 - k) + safe[..., 0] * k
        z = z * (1 - k) + safe[..., 2] * k
        hit = np.maximum(hit.astype(np.float32), k)
    amb = np.array([0.055, 0.065, 0.105], np.float32)
    L = np.broadcast_to(amb, (H, W, 3)).copy()
    haze = np.zeros((H, W), np.float32)
    for sx, sz, rad, k, col in spots(t):
        if k <= 0.01:
            continue
        g = np.exp(-(((x - sx) ** 2 + (z - sz) ** 2) / (rad * rad))).astype(np.float32) * hit
        L += g[..., None] * (k * np.array(col, np.float32))
        haze += g * k
    return L, haze


# ================================================================= Overlays
_LEDS = {}


def led_img(txt, col=LED, size=74):
    key = (txt, col, size)
    if key not in _LEDS:
        t_im = line_img(txt, size, 900, col)
        pad = 26
        w, h = t_im.width + 2 * pad, t_im.height + 2 * pad
        im = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((20, 20, 20 + w, 20 + h), 18, fill=(8, 9, 12, 235), outline=(60, 64, 74, 255), width=3)
        glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
        glow.alpha_composite(t_im, (20 + pad, 20 + pad))
        glow = glow.filter(ImageFilter.GaussianBlur(9))
        im.alpha_composite(glow)
        im.alpha_composite(glow)
        im.alpha_composite(t_im, (20 + pad, 20 + pad))
        _LEDS[key] = im
    return _LEDS[key]


def fmt(sec):
    s = int(math.ceil(max(sec, 0.0) - 1e-6))
    return f"{s // 60}:{s % 60:02d}"


def box_clock(t, team):
    """(Text, Farbe) der LED-Uhr über der Box oder None."""
    if t < T_SIT - 0.1 or t >= T_EN0 + 0.2:
        return None
    if t < T_PLAY:
        return fmt(300.0 - 300.0 * c01((t - T_SIT - 0.15) / (T_PLAY - T_SIT - 0.2))), LED
    if t < T_INTL + 0.3:
        return "0:00", LED
    if t < T_REW:
        return ("EJECTED", LED) if t >= T_EJECT else ("IIHF", (120, 170, 255))
    if team == 1:
        return "5:00", LED
    if t < T_17:
        return fmt(min(1020.0, 120.0 + 300.0 * c01((t - T_START) / 0.3) + 600.0 * c01((t - T_START - 0.35) / 0.3))), LED
    return "17:00", ORANGE


def draw_clocks(L, row, t):
    for team, bx in enumerate(BOX_X):
        c = box_clock(t, team)
        if c is None:
            continue
        xy, z = projected(row, np.array([bx, BH + GH + 26.0, BZ1]))
        if z <= 0:
            continue
        im = led_img(*c)
        a = smooth(T_SIT - 0.1, T_SIT + 0.05, t) * (1 - smooth(T_EN0, T_EN0 + 0.2, t))
        if a < 1:
            im = im.copy()
            im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
        put(L, im, xy[0] - im.width / 2, xy[1] - im.height / 2)


def ring2d(ctx, xy, r, col, a, w=6):
    if a <= 0:
        return
    ctx.set_source_rgba(col[0] / 255, col[1] / 255, col[2] / 255, a)
    ctx.set_line_width(w)
    ctx.arc(xy[0], xy[1], r, 0, 2 * math.pi)
    ctx.stroke()


def impact(ctx, row, t):
    """Weiße Schlag-Blitze zwischen den Chips."""
    for tp in (1.25, 1.55, 1.9, 2.25):
        li = t - tp
        if not 0 <= li < 0.35:
            continue
        p = (fight_pos(tp, 0) + fight_pos(tp, 1)) / 2 + np.array([0, 18.0, 0])
        xy, z = projected(row, p)
        if z <= 0:
            continue
        q = e_out(li / 0.35, 3)
        k = px_per_in(row, z)
        ctx.set_source_rgba(1, 1, 1, 0.9 * (1 - q))
        ctx.set_line_width(5)
        for j in range(10):
            a = j * math.pi / 5 + tp * 3
            r0, r1 = k * (8 + 24 * q), k * (16 + 44 * q)
            ctx.move_to(xy[0] + math.cos(a) * r0, xy[1] + math.sin(a) * r0)
            ctx.line_to(xy[0] + math.cos(a) * r1, xy[1] + math.sin(a) * r1)
        ctx.stroke()


def tag(L, xy, txt, col, a, size=34):
    if a <= 0:
        return
    im = line_img(txt, size, 850, col, track=4)
    reveal(L, im, min(max(xy[0], 40 + im.width / 2), W - 40 - im.width / 2), xy[1], a)


def word(txt, size, col, glow):
    return R18.word_img(txt, size, col, glow)


def texts(L, t, row):
    if t < T_UP0 + 0.1:
        k = 1 - smooth(T_UP0 - 0.1, T_UP0 + 0.1, t)
        for txt, cy, size, col, gl in (("WHY IS", 400, 120, WHITE, (90, 110, 160)),
                                       ("FIGHTING", 540, 170, WHITE, (90, 110, 160)),
                                       ("ALLOWED?", 705, 160, RED, (160, 20, 30))):
            im = word(txt, size, col, gl)
            if k < 1:
                im = im.copy()
                im.putalpha(im.getchannel("A").point(lambda v: int(v * k)))
            put(L, im, W / 2 - im.width / 2, cy - im.height / 2)
        reveal(L, line_img("NHL RULES EXPLAINED  ·  PART 7", 34, 800, ORANGE, track=8), W / 2, 285, 1.0,
               smooth(T_UP0 - 0.15, T_UP0 + 0.05, t))
    slam(L, "IT ISN'T.", 190, WHITE, W / 2, 520, t, T_ISNT, T_MAJOR - 0.05, glow=(90, 110, 160))
    slam(L, "5:00", 300, RED, W / 2, 520, t, T_MAJOR, T_BX0 + 0.1, glow=(160, 20, 30))
    if T_MAJOR + 0.25 <= t < T_BX0 + 0.1:
        reveal(L, line_img("MAJOR PENALTY  ·  NHL RULE 46", 38, 850, WHITE, track=6), W / 2, 700,
               c01((t - T_MAJOR - 0.25) / 0.25), smooth(T_BX0 - 0.1, T_BX0 + 0.1, t))
    slam(L, "NOBODY GETS EJECTED", 76, WHITE, W / 2, 1480, t, at("box", 0.24), T_SIT - 0.05, glow=(90, 110, 160))
    if T_SIT <= t < T_INTL:
        reveal(L, line_img("SIT 5 MIN  ·  THEN PLAY ON", 44, 850, WHITE, track=6), W / 2, 1480,
               c01((t - T_SIT) / 0.25), smooth(T_INTL - 0.2, T_INTL, t))
    if T_INTL <= t < T_REW:
        p_out = smooth(T_REW - 0.2, T_REW, t)
        reveal(L, line_img("INTERNATIONAL HOCKEY", 46, 850, (150, 190, 255), track=6), W / 2, 1390,
               c01((t - T_INTL) / 0.25), p_out)
        if t >= T_EJECT + 0.3:
            reveal(L, line_img("IIHF RULE 46.1  ·  OLYMPICS & WORLDS", 28, 750, GREY, track=4), W / 2, 1585,
                   c01((t - T_EJECT - 0.3) / 0.25), p_out)
    slam(L, "AUTOMATIC EJECTION", 82, RED, W / 2, 1485, t, T_EJECT, T_REW, glow=(160, 20, 30))
    if T_REW <= t < T_EN0:
        bxy, z = projected(row, np.array([BOX_X[0], BH + GH + 26.0, BZ1]))
        tag(L, (bxy[0], bxy[1] + 88), "STARTED IT", ORANGE, smooth(T_START, T_START + 0.15, t)
            * (1 - smooth(T_EN0 - 0.2, T_EN0, t)), 36)
        for i, (txt, tt) in enumerate((("+2  INSTIGATOR", T_START + 0.05), ("+5  FIGHTING", T_START + 0.35),
                                       ("+10  MISCONDUCT", T_START + 0.65))):
            a = smooth(tt, tt + 0.12, t) * (1 - smooth(T_17 - 0.05, T_17 + 0.1, t))
            tag(L, (W / 2, 1300 + i * 62), txt, WHITE, a, 40)
    slam(L, "17 MINUTES", 150, ORANGE, W / 2, 1460, t, T_17, T_EN0, glow=(170, 70, 10))
    if T_17 + 0.3 <= t < T_EN0:
        reveal(L, line_img("FOR THE INSTIGATOR  ·  NHL RULE 46.11", 30, 750, GREY, track=4), W / 2, 1585,
               c01((t - T_17 - 0.3) / 0.25), smooth(T_EN0 - 0.2, T_EN0, t))
    if t >= T_CTA:
        slam(L, "SHOULD THE NHL", 108, WHITE, W / 2, 420, t, T_CTA, glow=(90, 110, 160))
        slam(L, "BAN FIGHTING?", 120, RED, W / 2, 560, t, at("cta", 0.43), glow=(160, 20, 30))
        slam(L, "YES OR NO?", 150, ORANGE, W / 2, 1420, t, at("cta", 1.72), glow=(170, 70, 10))
        if t >= at("cta", 2.0):
            reveal(L, line_img("COMMENT BELOW  ·  FOLLOW FOR PART 8", 32, 800, WHITE, track=6), W / 2, 1560,
                   c01((t - at("cta", 2.0)) / 0.25))


# ================================================================= Bild
_VIG = None


def vignette():
    global _VIG
    if _VIG is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H * 0.55) / H) ** 2) * 2
        _VIG = (1 - 0.6 * np.clip(r - 0.35, 0, 1) ** 1.4)[..., None]
    return _VIG


def compose(t, fidx):
    base = render3d(t, fidx)
    row, _ = cam_row_at(t)
    campos = cam(t)[0]
    lo_s, lo_c = surface()
    hi_s, hi_c = surface()
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img = over(base, *surf_rgba(lo_s))
    meshes = ARENA + [glove_mesh(i, t) for i in range(len(GLOVES))]
    for team in (0, 1):
        p, a = chip_state(t, team)
        if a > 0.5:
            meshes += chip_meshes(p, team)
    m_rgb, m_a, shadow, plane_a, m_pos = M3.render(meshes, row, W, H, campos, extra_planes=[(GLASS_ALL, 1.0)],
                                                   shadow_light=(0.03, 1.0, 0.05), want_pos=True)
    img = img * (1 - 0.45 * shadow[..., None])
    img = img * (1 - m_a[..., None]) + m_rgb
    k = (0.22 * plane_a)[..., None]
    img = img * (1 - k) + np.array([0.70, 0.82, 0.94], np.float32) * k
    # Arena-Licht
    Lm, haze = light_map(row, t, m_a, m_pos)
    img = img * Lm
    img = img + (R26.glass_streaks() * plane_a * 0.05)[..., None]
    hz = gaussian_filter(haze[::4, ::4], 18)
    hz = np.asarray(Image.fromarray((np.clip(hz, 0, 2) * 120).astype(np.uint8)).resize((W, H), Image.BILINEAR),
                    np.float32) / 120
    img = img + hz[..., None] * np.array([0.05, 0.055, 0.07], np.float32)
    # Markierungen
    impact(hi_c, row, t)
    for team in (0, 1):
        p, a = chip_state(t, team)
        xy, z = projected(row, p + np.array([0, 3.0, 0]))
        if z <= 0:
            continue
        kpx = px_per_in(row, z)
        if t < T_GO + 0.1:
            ring2d(hi_c, xy, kpx * CHIP_R * 1.35, BLUE if team == 0 else RED, 0.5 * a * smooth(0.2, 0.5, t), 4)
        if T_EJECT <= t < T_REW:                                            # rotes X über den Chips
            q = smooth(T_EJECT, T_EJECT + 0.12, t) * a
            r = max(kpx * CHIP_R * 0.8, 16)
            hi_c.set_source_rgba(RED[0] / 255, RED[1] / 255, RED[2] / 255, q)
            hi_c.set_line_width(9)
            hi_c.move_to(xy[0] - r, xy[1] - r)
            hi_c.line_to(xy[0] + r, xy[1] + r)
            hi_c.move_to(xy[0] + r, xy[1] - r)
            hi_c.line_to(xy[0] - r, xy[1] + r)
            hi_c.stroke()
    if T_ISNT <= t < T_ISNT + 0.6:                                          # Pfiff
        xy, z = projected(row, np.array([0.0, 10.0, 0.0]))
        q = e_out((t - T_ISNT) / 0.6, 3)
        ring2d(hi_c, xy, 40 + 300 * q, WHITE, 0.8 * (1 - q), 10 * (1 - q) + 2)
    if T_START <= t < T_START + 0.6:
        xy, z = projected(row, seat(BOX_X[0]) + [0, 3.0, 0])
        q = e_out((t - T_START) / 0.6, 3)
        ring2d(hi_c, xy, 30 + 160 * q, ORANGE, 0.9 * (1 - q), 8 * (1 - q) + 2)
    img = over(img, *surf_rgba(hi_s))
    for t0, col in ((T_MAJOR, (1.0, 0.1, 0.12)), (T_EJECT, (1.0, 0.1, 0.12)), (T_17, (1.0, 0.45, 0.1))):
        if t0 <= t < t0 + 0.3:
            a = 0.16 * (1 - (t - t0) / 0.3)
            img = img * (1 - a) + np.array(col, np.float32) * a
    img = np.clip(img, 0, 1)
    pil = Image.fromarray((img * 255).astype(np.uint8)).convert("RGBA")
    draw_clocks(L, row, t)
    texts(L, t, row)
    pil.alpha_composite(L)
    arr = np.asarray(pil.convert("RGB")).astype(np.float32) / 255
    lc = min([t - c for c in (T_ISNT, T_MAJOR, T_EJECT, T_17) if t >= c] + [t + 0.5])
    zp = 1 + 0.04 * math.exp(-lc * 14)
    if zp > 1.002:
        im2 = Image.fromarray((arr * 255).astype(np.uint8))
        w2, h2 = W / zp, H / zp
        im2 = im2.transform((W, H), Image.EXTENT, ((W - w2) / 2, (H - h2) / 2, (W + w2) / 2, (H + h2) / 2), Image.BILINEAR)
        arr = np.asarray(im2).astype(np.float32) / 255
    arr = arr * vignette()
    arr += np.random.default_rng(fidx).normal(0, 0.012, arr.shape[:2])[..., None]
    return (np.clip(arr, 0, 1) * 255).astype(np.uint8)


# ================================================================= Ton
SR = 44100


def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(30)
    mus = np.zeros((n, 2))
    sfx = np.zeros((n, 2))
    B = 60 / 132

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
        f = 42 + 160 * np.exp(-x * 34)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 7) * 3.2) * vol

    def snare(vol=1.0):
        x = tt(0.35)
        return (hp(noise(0.35), 3) * np.exp(-x * 16) * 0.7 + np.sin(2 * np.pi * 185 * x) * np.exp(-x * 22) * 0.5) * vol

    def hat(vol=0.1):
        return hp(noise(0.04), 1) * np.exp(-tt(0.04) * 150) * vol

    def sub(freq, dur):
        x = tt(dur)
        f = freq * (1 + 0.6 * np.exp(-x * 9))
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * 2.6) * np.minimum(x / 0.004, 1) * np.exp(-x * 1.1) * 0.85

    def stab(freq, dur=0.6, vol=0.08):
        x = tt(dur)
        sig = sum(np.sin(2 * np.pi * freq * m * x + 0.3 * np.sin(2 * np.pi * 3 * x)) / m for m in (1, 2, 3, 4))
        return lp(sig, 3) * np.exp(-x * 4.5) * vol

    def stamp(vol=1.0):
        x = tt(0.9)
        f = 38 + 110 * np.exp(-x * 16)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 4) * 2.6) * vol

    def thud(vol=0.7):
        x = tt(0.4)
        body = np.sin(2 * np.pi * np.cumsum(70 + 60 * np.exp(-x * 30)) / SR) * np.exp(-x * 18)
        return np.tanh((body + lp(noise(0.4), 8) * np.exp(-x * 25) * 0.6) * 2.0) * vol

    def punch(vol=0.6):
        x = tt(0.25)
        return np.tanh((hp(lp(noise(0.25), 3), 20) * np.exp(-x * 35) + np.sin(2 * np.pi * 90 * x) * np.exp(-x * 20))
                       * 2.2) * vol

    def crowd(dur=2.5, vol=0.4):
        x = tt(dur)
        sig = lp(noise(dur), 12) - lp(noise(dur), 60) * 0.6
        env = np.sin(np.pi * np.clip(x / dur, 0, 1)) ** 0.8
        return sig * env * vol * 2.0

    def whistle(dur=0.6, vol=0.5):
        x = tt(dur)
        sig = np.sin(2 * np.pi * np.cumsum(np.full_like(x, 2900.0) + 120 * np.sin(2 * np.pi * 32 * x)) / SR)
        return sig * (1 + 0.5 * (np.sin(2 * np.pi * 32 * x) > 0)) * 0.5 * np.minimum(x / 0.02, 1) * np.clip((dur - x) / 0.08, 0, 1) * vol

    def whoosh(dur=0.7, vol=0.5):
        x = tt(dur)
        env = np.sin(np.pi * np.clip(x / dur, 0, 1)) ** 2
        return hp(lp(noise(dur), 6), 40) * env * vol

    def tick(vol=0.3):
        x = tt(0.03)
        return np.sin(2 * np.pi * 2200 * x) * np.exp(-x * 220) * vol

    def door_clack(vol=0.5):
        x = tt(0.3)
        return (np.sin(2 * np.pi * 240 * x) * 0.6 + hp(noise(0.3), 4) * 0.5) * np.exp(-x * 30) * vol

    def buzzer(dur=0.7, vol=0.4):
        x = tt(dur)
        sig = np.sign(np.sin(2 * np.pi * 110 * x)) * 0.5 + np.sign(np.sin(2 * np.pi * 116.5 * x)) * 0.5
        return lp(sig, 6) * np.minimum(x / 0.01, 1) * np.clip((dur - x) / 0.05, 0, 1) * vol

    def rewind(dur=0.4, vol=0.4):
        x = tt(dur)
        f = 1800 - 1400 * (x / dur)
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.4 + hp(lp(noise(dur), 4), 30) * 0.6) * np.sin(np.pi * x / dur) * vol

    def chime(vol=0.4):
        out = np.zeros(int(1.2 * SR))
        for i, f in enumerate((783.99, 1046.5, 1318.5)):
            x = tt(1.2 - 0.08 * i)
            out[int(0.08 * i * SR):][:len(x)] += np.sin(2 * np.pi * f * x) * np.exp(-x * 4) * vol
        return out

    roots = [41.2, 41.2, 49.0, 36.7]                                     # dunkles e-Moll
    for k8 in range(int(DUR / (B / 2))):
        tb = k8 * B / 2
        b = k8 / 2
        pos = b % 4
        if tb > DUR - 0.4:
            continue
        hook = tb < T_UP0
        if pos in (0.0, 2.5) or (pos == 1.5 and not hook):
            put_(mus, kick(0.75 if hook else 1.0), tb)
        if pos in (1.0, 3.0) and not hook:
            put_(mus, snare(0.9), tb)
        if not hook:
            put_(mus, hat(0.1 if k8 % 2 == 0 else 0.06), tb, pan=0.3)
        if pos == 0.0:
            put_(mus, sub(roots[int(b // 4) % 4], 2.6 * B), tb)
            put_(mus, stab(roots[int(b // 4) % 4] * 8, 0.8, 0.07), tb, pan=-0.2)
    for i, g in enumerate(GLOVES):                                        # Handschuhe fallen aufs Eis
        put_(sfx, thud(0.75), g[3], pan=-0.3 + 0.2 * i)
    put_(sfx, crowd(3.0, 0.35), 0.0)
    for tp in (1.25, 1.55, 1.9, 2.25):
        put_(sfx, punch(0.55), tp - 0.03)
    put_(sfx, whoosh(T_UP1 - T_UP0 + 0.1, 0.4), T_UP0)
    put_(sfx, whistle(0.7, 0.55), T_ISNT - 0.05)
    put_(sfx, stamp(1.0), T_MAJOR)
    put_(sfx, whoosh(T_BX1 - T_BX0 + 0.1, 0.45), T_BX0)
    put_(sfx, door_clack(0.6), T_IN - 0.25)
    put_(sfx, door_clack(0.5), T_IN - 0.15, pan=0.3)
    for k in range(int((T_PLAY - T_SIT) / 0.06)):
        put_(sfx, tick(0.18), T_SIT + 0.1 + 0.06 * k)
    put_(sfx, door_clack(0.5), T_PLAY)
    put_(sfx, buzzer(0.7, 0.4), T_EJECT)
    put_(sfx, stamp(0.9), T_EJECT)
    put_(sfx, rewind(0.4, 0.4), T_REW)
    for i in range(3):
        put_(sfx, tick(0.4), T_START + 0.05 + 0.3 * i)
    put_(sfx, stamp(1.0), T_17)
    put_(sfx, chime(0.35), T_17)
    put_(sfx, whoosh(T_EN1 - T_EN0 + 0.1, 0.4), T_EN0)
    put_(sfx, stamp(0.8), at("cta", 1.72))
    voice = np.zeros(n)
    for k in VO_KEYS:
        tmp = os.path.join(HERE, f"_vo_{k}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "voice", f"reel30_{k}.wav"),
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
    sduck = 1 - 0.5 * np.clip(venv / 0.06, 0, 1)
    mus /= np.max(np.abs(mus)) + 1e-9
    sfx /= np.max(np.abs(sfx)) + 1e-9
    mix = mus * 0.42 * duck[:, None] + sfx * 0.5 * sduck[:, None] + voice[:, None] * 1.0
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
    tts_kokoro.synth(VO_LINES, os.path.join(HERE, "voice", "reel30"), speed=1.2)


def check_vo():
    with open(os.path.join(HERE, "voice", "reel30_timing.json")) as f:
        vo_dur = {k: v / TEMPO for k, v in json.load(f).items()}
    for i, k in enumerate(VO_KEYS[:-1]):
        nxt = VO_KEYS[i + 1]
        if VO_START[k] + vo_dur[k] > VO_START[nxt] + 0.35:
            print(f"Warnung: Satz {k} überlappt {nxt} ({VO_START[k] + vo_dur[k]:.2f} > {VO_START[nxt]:.2f})")


def remux():
    os.chdir(HERE)
    make_audio("audio_fight.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "reel30_fight.mp4", "-i", "audio_fight.wav", "-map", "0:v",
                    "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
                    "-ar", "44100", "-shortest", "-movflags", "+faststart", "_tmp_fight.mp4"], check=True)
    os.replace("_tmp_fight.mp4", "reel30_fight.mp4")


def main():
    os.chdir(HERE)
    check_vo()
    make_audio("audio_fight.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_fight.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "19",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
           "-ar", "44100", "-shortest", "-movflags", "+faststart", "reel30_fight.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(1.0, 9999)).save("reel30_thumbnail.jpg", quality=92)
    print("fertig: reel30_fight.mp4")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "vo":
        make_voice()
    elif len(sys.argv) > 1 and sys.argv[1] == "audio":
        remux()
    else:
        main()
