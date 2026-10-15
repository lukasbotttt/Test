"""Reel 27: HOCKEY GEAR EXPLAINED – WHY DO PLAYERS TAPE THEIR STICKS? (TikTok-Shop-Video, 16,6 s, mind. 15 s).

Fakten (Hockey-Ratgeber, u. a. hockeymonkey.com, hockeyanswered.com, hockeyresponse.com):
- Tape auf der Schaufel gibt Reibung/Grip am Puck und dämpft Pässe; es schützt die Schaufel vor Abrieb durch
  Eis und Puck.
- Das Tape-Ende oben am Schaft ("Knob") gibt Grip und hilft, den Schläger vom Eis aufzuheben.
- "Schwarzes Tape versteckt den Puck vor dem Torwart" ist ein verbreiteter Glaube – die meisten Goalies sagen,
  die Farbe macht für sie keinen Unterschied.
Produkt: Elite Hockey Tape (TikTok Shop; Link setzt der User in der App). Werbung als "AD" gekennzeichnet.
Bild: Schaufel/Schaft/Tape/Rolle als 3D-Gitter (mesh3d), Eis + Puck (Raytracer). Keine Spielerkörper.
Aufruf: python3 reel27_tape.py -> reel27_tape.mp4
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
import reel25_goalline as G
from reel15_puck import (W, H, FPS, SPP, KSUB, SHUTTER, c01, smooth, sio, e_out, e_in, lerp, blend_up, line_img,
                         reveal, put, proj, projected, px_per_in, stroke_poly, surface, surf_rgba, over)
from reel22_trapezoid import fill_poly, whistle_ring, slam
from reel18_dangle import vignette

HERE = R15.HERE
INK, ORANGE = R15.INK, R15.ORANGE
GREEN = (30, 160, 80)
HALO = (255, 255, 255)
TEMPO = 1.08

VO_KEYS = ["q", "grip", "protect", "knob", "myth", "cta"]
VO_START = {"q": 0.15, "grip": 2.25, "protect": 4.35, "knob": 6.6, "myth": 9.75, "cta": 13.75}
with open(os.path.join(HERE, "voice", "reel27_timing.json")) as f:
    VO_DUR = {k: v / TEMPO for k, v in json.load(f).items()}
DUR = 16.6


def word(key, t_word):
    return VO_START[key] + t_word / TEMPO


T_WRAP0, T_WRAP1 = 0.15, 2.0          # Tape wickelt sich von der Ferse zur Spitze
T_DROP0, T_DROP1 = 2.0, 2.3           # Schläger landet auf dem Eis
T_P0, T_P1 = 2.35, 2.95               # Pass kommt an
T_GRIP = word("grip", 0.12)
T_SOFT = word("grip", 1.06)
T_PROT = word("protect", 0.22)
T_ICE = word("protect", 1.30)
T_KNOB = word("knob", 0.20)
T_BGRIP = word("knob", 0.92)
T_PICK = word("knob", 2.58)
T_BLACK = word("myth", 0.12)
T_MOST = word("myth", 2.32)
T_NODIFF = word("myth", 3.08)
T_CTA = VO_START["cta"]
# Kamera-Abschnitte
T_C1, T_C2, T_C3, T_C4, T_C5 = 2.15, 4.35, 6.55, 9.55, 13.6

O = np.array([150.0, 0.0, -230.0])    # Ferse der Schaufel auf dem Eis (Welt)
X_TAPE0 = 0.9
LIFT = 6.0


# ================================================================= Geometrie (lokale Zoll, x entlang der Schaufel)
def bend(x):
    return -0.6 * np.clip((np.asarray(x, float) - 1.0) / 10.0, 0, None) ** 2


def blade_profile():
    pts = [(x, 0.15 + 0.10 * (x / 10.3) ** 2) for x in np.linspace(0.6, 10.3, 26)]
    for a in np.linspace(-90, 90, 16)[1:]:
        r = math.radians(a)
        pts.append((10.3 + 1.15 * math.cos(r), 1.6 + 1.35 * math.sin(r)))
    pts += [(x, 2.95 - 0.2 * (10.3 - x) / 8.7) for x in np.linspace(10.0, 1.6, 12)]
    pts += [(0.9, 2.95), (0.2, 2.78), (-0.25, 2.1), (-0.1, 1.0), (0.2, 0.4)]
    return np.array(pts)


PROF = blade_profile()


def offset_poly(P, d):
    n = len(P)
    out = []
    for i in range(n):
        a, b, c = P[i - 1], P[i], P[(i + 1) % n]
        e1, e2 = b - a, c - b
        n1 = np.array([e1[1], -e1[0]]) / (np.linalg.norm(e1) + 1e-9)
        n2 = np.array([e2[1], -e2[0]]) / (np.linalg.norm(e2) + 1e-9)
        nn = n1 + n2
        out.append(b + nn / (np.linalg.norm(nn) + 1e-9) * d)
    return np.array(out)


PROF_TAPE = offset_poly(PROF, 0.045)


def bent_extrude(prof, half, mat):
    m = M3.extrude(prof, -half, half, mat)
    m.v[:, 2] += bend(m.v[:, 0])
    return m


def transform(m, dy=0.0, dz=0.0):
    """lokal -> Welt (Verschiebung; uvw bleibt lokal für die Tape-Muster)."""
    out = M3.Mesh(m.v + O + np.array([0.0, dy, dz]), m.n, m.t, m.m, m.uvw)
    out.g = m.g.copy()
    return out


SHAFT_D = np.array([-math.cos(math.radians(45)), math.sin(math.radians(45)), 0.0])
S0 = np.array([0.35, 2.3, 0.0])
SHAFT_LEN = 53.0


def rrect_tube(s0, s1, hw, hh, mat, n=12, nr=28, cap_ends=True, bulge=0.0, taper=False):
    """Schaft-Stück mit abgerundet-rechteckigem Querschnitt zwischen s0 und s1 (Zoll entlang des Schafts)."""
    e1 = np.array([0.0, 0.0, 1.0])
    e2 = np.cross(SHAFT_D, e1)
    e2 /= np.linalg.norm(e2)
    verts, uvw = [], []
    ss = np.linspace(s0, s1, n)
    for k, s in enumerate(ss):
        c = S0 + SHAFT_D * s
        b = 1.0 + bulge * math.sin(math.pi * k / (n - 1))
        tz = (0.46 + 0.54 * smooth(0.0, 5.0, s)) if taper else 1.0       # Hals wird zur Schaufel hin schmal
        for j in range(nr):
            th = 2 * math.pi * j / nr
            cx, cy = math.cos(th), math.sin(th)
            px = hw * b * tz * math.copysign(abs(cx) ** 0.6, cx)
            py = hh * b * math.copysign(abs(cy) ** 0.6, cy)
            verts.append(c + e1 * px + e2 * py)
            uvw.append((s, j / nr * 3.0, 0.0))
    tris = [tuple(t) for t in M3.grid_tris(n, nr)]
    if cap_ends:
        for k, s in ((0, s0), (n - 1, s1)):
            ci = len(verts)
            verts.append(S0 + SHAFT_D * s)
            uvw.append((s, 0.0, 0.0))
            for j in range(nr):
                a_, b_ = k * nr + j, k * nr + (j + 1) % nr
                tris.append((a_, b_, ci) if k else (b_, a_, ci))
    v = np.array(verts)
    t = np.array(tris, np.int32)
    return M3.Mesh(v, M3.vertex_normals(v, t), t, M3.MAT_IDS[mat], np.array(uvw))


def stick_meshes(tape_mat, wrap_x, z_off=0.0, dy=0.0):
    out = [bent_extrude(PROF, 0.22, "carbon")]
    if wrap_x > X_TAPE0 + 0.05:
        part = G.clip_x(PROF_TAPE, X_TAPE0, wrap_x)
        if len(part) >= 3:
            out.append(bent_extrude(part, 0.34, tape_mat))
    out.append(rrect_tube(-1.2, SHAFT_LEN, 0.50, 0.36, "carbon", n=24, taper=True))
    out.append(rrect_tube(9.0, 9.7, 0.515, 0.375, "stick_red", n=3, cap_ends=False))
    out.append(rrect_tube(SHAFT_LEN - 7.5, SHAFT_LEN - 0.4, 0.56, 0.42, "tape_white", n=14, cap_ends=False))
    out.append(rrect_tube(SHAFT_LEN - 1.6, SHAFT_LEN + 0.15, 0.78, 0.64, "tape_white", n=8, bulge=0.12))
    return [transform(m, dy, z_off) for m in out]


def roll_mesh(center, ang):
    """Tape-Rolle, Achse entlang x (lokal), Mittelpunkt center (lokal)."""
    nr = 40
    a = 2 * math.pi * np.arange(nr) / nr + ang
    ring = np.stack([np.zeros(nr), np.cos(a), np.sin(a)], 1)
    hw, ro, ri = 0.47, 1.5, 0.82
    xs = np.array([-hw, 0.0, 0.0])
    xe = np.array([hw, 0.0, 0.0])
    parts = []
    for r_, mat, inward in ((ro, "tape_white", False), (ri, "core", True)):
        v = np.concatenate([center + xs + ring * r_, center + xe + ring * r_])
        nrm = np.concatenate([ring, ring]) * (-1 if inward else 1)
        tris = [(i, nr + i, (i + 1) % nr) for i in range(nr)] + [((i + 1) % nr, nr + i, nr + (i + 1) % nr) for i in range(nr)]
        uv = np.zeros((2 * nr, 3))
        uv[:, 0] = 0.3
        uv[:, 1] = np.concatenate([a, a]) * 0.4
        parts.append(M3.Mesh(v, nrm, np.array(tris, np.int32), M3.MAT_IDS[mat], uv))
    for x_, sgn in ((xs, -1.0), (xe, 1.0)):                           # Seitenflächen (Ringe)
        v = np.concatenate([center + x_ + ring * ro, center + x_ + ring * ri])
        nrm = np.tile([sgn, 0.0, 0.0], (2 * nr, 1))
        tris = [(i, (i + 1) % nr, nr + i) for i in range(nr)] + [((i + 1) % nr, nr + (i + 1) % nr, nr + i) for i in range(nr)]
        uv = np.zeros((2 * nr, 3))
        uv[:, 0] = 0.3
        parts.append(M3.Mesh(v, nrm, np.array(tris, np.int32), M3.MAT_IDS["tape_white"], uv))
    return parts


def strip_mesh(xw, blade_c, roll_c, dirn):
    """Tape-Streifen von der Rolle zur Schaufel."""
    p_b = blade_c + dirn * 1.0
    p_r = roll_c - dirn * 1.45
    hw = 0.47
    v = np.array([p_b + [-hw, 0, 0], p_b + [hw, 0, 0], p_r + [hw, 0, 0], p_r + [-hw, 0, 0]])
    nrm = np.cross(p_r - p_b, [1.0, 0, 0])
    nrm = np.tile(nrm / (np.linalg.norm(nrm) + 1e-9), (4, 1))
    uv = np.zeros((4, 3))
    uv[:, 0] = 0.3
    return M3.Mesh(v, nrm, np.array([[0, 1, 2], [0, 2, 3]], np.int32), M3.MAT_IDS["tape_white"], uv)


# ================================================================= Zustände
def wrap_x(t):
    return X_TAPE0 + (11.45 - X_TAPE0) * sio(c01((t - T_WRAP0) / (T_WRAP1 - T_WRAP0)))


def lift(t):
    if t < T_DROP0:
        return LIFT
    u = c01((t - T_DROP0) / (T_DROP1 - T_DROP0))
    return LIFT * (1 - u * u)


PUCK_REST = np.array([5.6, 0.5, float(bend(5.6)) - 0.34 - 1.5])
PUCK2_REST = PUCK_REST + np.array([0.4, 0.0, 13.0])


def puck_local(t):
    """(Position lokal, sichtbar)"""
    if t < T_P0:
        return PUCK_REST + np.array([34.0, 0, -9.0]), 0.0
    if t < T_P1:
        u = e_out((t - T_P0) / (T_P1 - T_P0), 2.4)
        return PUCK_REST + np.array([34.0, 0, -9.0]) * (1 - u), 1.0
    knock = 0.0                                               # kleine Abpraller bei "ice and pucks"
    for tk in (T_ICE, word("protect", 1.84)):
        lt = t - tk
        if 0 < lt < 0.35:
            knock = max(knock, math.sin(math.pi * lt / 0.35) * 1.2)
    return PUCK_REST + np.array([0.0, 0.0, -knock]), 1.0


# ================================================================= Kamera (lokal)
def hook_cam(t):
    ly = lift(t)
    push = e_out(c01(t / T_C1), 2)
    return (np.array([19.0, 15.0 + ly, -33.0]) + np.array([-3.0, -1.5, 5.0]) * push,
            np.array([5.0, 1.5 + ly * 0.9, 0.0]), 40.0)


def grip_cam(t):
    return np.array([15.0, 9.0, -25.0]), np.array([5.2, 1.0, -3.0]), 40.0


def protect_cam(t):
    u = sio(c01((t - T_C2) / (T_C3 - T_C2)))
    ang = math.radians(-8 - 40 * u)
    tgt = np.array([5.5, 1.2, -1.0])
    r = 21.0 - 4 * u
    return tgt + np.array([math.sin(-ang) * r * 0.55 + 4, 7.5 - 1.5 * u, -math.cos(ang) * r]), tgt, 40.0


KNOB = S0 + SHAFT_D * (SHAFT_LEN - 1.0)


def knob_cam(t):
    u = sio(c01((t - T_C3) / 1.6))
    tgt = np.array([5.2, 1.0, 0.0]) + (KNOB - np.array([5.2, 1.0, 0.0])) * u
    off = np.array([12.0, 6.0, -22.0]) + (np.array([7.0, 1.5, -13.0]) - np.array([12.0, 6.0, -22.0])) * u
    return tgt + off, tgt, 40.0


def myth_cam(t):
    u = c01((t - T_C4) / (DUR - T_C4))
    return np.array([4.0, 33.0 - 3 * u, -36.0 + 3 * u]), np.array([6.5, 2.0, 4.5]), 38.0


def blend_cam(a, b, s):
    return G.blend_cam(a, b, s)


def cam_local(t):
    segs = [(0.0, hook_cam), (T_C1, grip_cam), (T_C2, protect_cam), (T_C3, knob_cam), (T_C4, myth_cam)]
    for i in range(len(segs) - 1, -1, -1):
        t0, fn = segs[i]
        if t >= t0:
            cur = fn(t)
            if i > 0 and t < t0 + 0.55:
                prev = segs[i - 1][1](t)
                return blend_cam(prev, cur, sio((t - t0) / 0.55))
            return cur
    return segs[0][1](t)


def cam(t):
    p, g, f = cam_local(t)
    p, g = p + O, g + O
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
        p, vis = puck_local(tk)
        p = p + O
        pk[j] = (p[0], p[1], p[2], 2.4 + 3.0 * min(tk, T_P1), vis, 0.0, tk)
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, SPP, fidx + 27, cams, lens, pk, R15.logo_tex(), base, puck, cov)
    # zweiter Puck (Mythos-Szene) als eigener Render-Durchgang nur, wenn sichtbar
    if t >= T_C4 - 0.6:
        pk2 = pk.copy()
        p2 = PUCK2_REST + O
        pk2[:, 0:3] = p2
        pk2[:, 4] = 1.0
        b2 = np.zeros((H, W, 3), np.float32)
        pu2 = np.zeros((H, W, 3), np.float32)
        cv2 = np.zeros((H, W), np.float32)
        P3.render(W, H, max(2, SPP // 2), fidx + 270, cams, lens, pk2, R15.logo_tex(), b2, pu2, cv2)
        return P3.tonemap(base), P3.tonemap(puck), cov, P3.tonemap(pu2), cv2
    return P3.tonemap(base), P3.tonemap(puck), cov, None, None


# ================================================================= Overlays + Text
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


def ad_tag(L):
    im = line_img("AD", 32, 850, (255, 255, 255), track=3)
    pad = Image.new("RGBA", (im.width - 8, im.height - 22), (20, 21, 26, 190))
    put(L, pad, 74, 181)
    put(L, im, 70, 170)


def blade_glow(ctx, row, a, dy=0.0):
    if a <= 0:
        return
    P = PROF_TAPE
    pts = np.stack([P[:, 0], P[:, 1] + dy, bend(P[:, 0]) - 0.3], 1) + O
    xy, z = proj(row, np.vstack([pts, pts[:1]]))
    if (z < 1).any():
        return
    stroke_poly(ctx, xy, ORANGE, 0.25 * a, 22)
    stroke_poly(ctx, xy, ORANGE, 0.9 * a, 6)


def dashed_ring(ctx, row, p, r_px, a, t, col=ORANGE):
    if a <= 0:
        return
    xy, z = projected(row, p)
    if z <= 0:
        return
    ctx.set_source_rgba(col[0] / 255, col[1] / 255, col[2] / 255, 0.9 * a)
    ctx.set_line_width(7)
    ctx.set_dash([26, 16], -t * 60)
    ctx.arc(xy[0], xy[1], r_px + 6 * math.sin(t * 9), 0, 2 * math.pi)
    ctx.stroke()
    ctx.set_dash([])


def texts(L, t, row):
    ad_tag(L)
    if t < T_C1 + 0.1:
        k = 1 - smooth(T_C1 - 0.1, T_C1 + 0.1, t)
        two_lines(L, "WHY DO PLAYERS", "TAPE THEIR STICKS?", INK, ORANGE, 470, 600, 100, 92, k)
        reveal(L, line_img("HOCKEY GEAR EXPLAINED", 34, 800, ORANGE, track=8), W / 2, 350, 1.0,
               smooth(T_C1 - 0.15, T_C1 + 0.05, t))
    slam(L, "GRIP.", 210, ORANGE, W / 2, 440, t, T_GRIP, T_C2)
    slam(L, "SOFTER PASSES", 84, INK, W / 2, 1450, t, T_SOFT, T_C2)
    slam(L, "PROTECTION.", 150, ORANGE, W / 2, 440, t, T_PROT, T_C3)
    slam(L, "VS. ICE + PUCKS", 84, INK, W / 2, 1450, t, T_ICE, T_C3)
    slam(L, "THE KNOB", 160, ORANGE, W / 2, 440, t, T_KNOB, T_C4)
    slam(L, "BETTER GRIP", 84, INK, W / 2, 1450, t, T_BGRIP, T_PICK)
    slam(L, "EASY PICK-UP", 84, INK, W / 2, 1450, t, T_PICK, T_C4)
    if T_BLACK <= t < T_NODIFF:
        two_lines(L, "BLACK TAPE", "HIDES THE PUCK?", INK, INK, 400, 530, 120, 96, smooth(T_BLACK, T_BLACK + 0.08, t))
    slam(L, "MOST GOALIES SAY", 76, INK, W / 2, 1450, t, T_MOST, T_CTA)
    slam(L, "NO DIFFERENCE.", 130, GREEN, W / 2, 440, t, T_NODIFF, T_CTA)
    if t >= T_CTA:
        slam(L, "BLACK", 150, INK, W / 2, 420, t, T_CTA)
        slam(L, "OR WHITE?", 150, ORANGE, W / 2, 580, t, word("cta", 0.36))
        slam(L, "WHAT DO YOU USE?", 76, INK, W / 2, 1480, t, word("cta", 0.9))
        if t >= word("cta", 1.3):
            reveal(L, line_img("TAPE  ·  SHOP LINK BELOW", 34, 800, ORANGE, track=6), W / 2, 1565,
                   c01((t - word("cta", 1.3)) / 0.25))


# ================================================================= Bild
def scene_meshes(t, p_puck, vis):
    ly = lift(t)
    xw = wrap_x(t)
    meshes = stick_meshes("tape_white", xw, dy=ly)
    if t < T_WRAP1 + 0.25:                                      # Rolle kreist beim Wickeln um die Schaufel
        th = 7.5 * math.pi * c01((t - T_WRAP0) / (T_WRAP1 - T_WRAP0)) - 0.9
        dirn = np.array([0.0, math.cos(th), math.sin(th)])
        bc = np.array([xw, 1.55 + ly, float(bend(xw))])
        rc = bc + dirn * 3.2 + (np.array([0.0, 0.0, 0.0]) if t < T_WRAP1 else np.array([0.0, 30.0 * (t - T_WRAP1), 0.0]))
        if t < T_WRAP1:
            meshes += [transform(m) for m in roll_mesh(rc, th * 3.0)]
            meshes.append(transform(strip_mesh(xw, bc, rc, dirn)))
    if t >= T_C4 - 0.6:                                         # zweiter Schläger mit schwarzem Tape
        meshes += stick_meshes("tape_black", 11.45, z_off=13.0)
    if vis > 0:
        meshes.append(G.cyl_mesh(p_puck + O - np.array([0, 0.5, 0]), 1.5, 1.0, "occluder", group=1))
    if t >= T_C4 - 0.6:
        meshes.append(G.cyl_mesh(PUCK2_REST + O - np.array([0, 0.5, 0]), 1.5, 1.0, "occluder", group=1))
    return meshes


def compose(t, fidx):
    base, puck, cov, puck2, cov2 = render3d(t, fidx)
    row, _ = cam_row_at(t)
    campos = cam(t)[0]
    p_l, vis = puck_local(t)
    lo_s, lo_c = surface()
    hi_s, hi_c = surface()
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img = over(base, *surf_rgba(lo_s))
    m_rgb, m_a, shadow, _ = M3.render(scene_meshes(t, p_l, vis), row, W, H, campos,
                                      alpha_by_group=np.array([1.0, 0.0], np.float32), shadow_light=(0.04, 1.0, -0.06))
    img = img * (1 - 0.30 * shadow[..., None])
    pa = cov[..., None] * vis
    img = img * (1 - pa) + puck * pa
    if puck2 is not None:
        a2 = (cov2 * smooth(T_C4 - 0.6, T_C4 - 0.3, t))[..., None]
        img = img * (1 - a2) + puck2 * a2
    img = img * (1 - m_a[..., None]) + m_rgb
    # Markierungen
    blade_glow(hi_c, row, smooth(T_PROT - 0.05, T_PROT + 0.2, t) * (1 - smooth(T_C3 - 0.2, T_C3, t)))
    whistle_ring(hi_c, row, p_l + O, t, T_P1, ORANGE)
    for tk in (T_ICE, word("protect", 1.84)):
        whistle_ring(hi_c, row, p_l + O + np.array([0, 0, 1.5]), t, tk, ORANGE)
    dashed_ring(hi_c, row, KNOB + O, 110, smooth(T_KNOB - 0.1, T_KNOB + 0.15, t) * (1 - smooth(T_C4 - 0.2, T_C4, t)), t)
    img = over(img, *surf_rgba(hi_s))
    img = np.clip(img, 0, 1)
    pil = Image.fromarray((img * 255).astype(np.uint8)).convert("RGBA")
    texts(L, t, row)
    pil.alpha_composite(L)
    arr = np.asarray(pil.convert("RGB")).astype(np.float32) / 255
    lc = min([t - c for c in (T_DROP1, T_GRIP, T_PROT, T_KNOB, T_NODIFF, T_CTA) if t >= c] + [t + 0.5])
    zp = 1 + 0.03 * math.exp(-lc * 14)
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
    rng = np.random.default_rng(27)
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

    def tape_rip(dur, vol=0.4):
        x = tt(dur)
        crackle = (rng.random(len(x)) < 0.02) * rng.standard_normal(len(x)) * 3
        body = hp(lp(noise(dur), 3), 8)
        wob = 0.6 + 0.4 * np.sin(2 * np.pi * 7.5 * x) ** 2
        return (body * 0.6 + crackle) * wob * np.minimum(x / 0.05, 1) * np.clip((dur - x) / 0.1, 0, 1) * vol

    def clack(vol=0.7):
        x = tt(0.3)
        return (hp(noise(0.3), 2) * np.exp(-x * 70) + np.sin(2 * np.pi * 180 * x) * np.exp(-x * 30) * 0.7) * vol

    def slide(dur, vol=0.3):
        x = tt(dur)
        v = np.clip(1 - x / dur, 0, 1) ** 1.2
        return hp(lp(noise(dur), 2), 18) * v * np.minimum(x / 0.03, 1) * vol

    def tap(vol=0.6):
        x = tt(0.2)
        return (np.sin(2 * np.pi * 240 * x) * 0.7 + hp(noise(0.2), 2) * 0.4) * np.exp(-x * 40) * vol

    def whoosh(dur=0.7, vol=0.5):
        x = tt(dur)
        env = np.sin(np.pi * np.clip(x / dur, 0, 1)) ** 2
        return hp(lp(noise(dur), 6), 40) * env * vol

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
        if pos in (0.0, 2.5):
            put_(mus, kick(), tb)
        if pos in (1.0, 3.0):
            put_(mus, clap(), tb)
        put_(mus, hat(0.12 if k8 % 2 == 0 else 0.07), tb, pan=0.3)
        if pos == 0.0:
            put_(mus, b808(roots[int(b // 4) % 4], 2.3 * B), tb)
        put_(mus, bell(mel[k8 % 8]), tb, pan=-0.2)
    put_(sfx, tape_rip(T_WRAP1 - T_WRAP0, 0.45), T_WRAP0)
    put_(sfx, clack(0.8), T_DROP1)
    put_(sfx, slide(T_P1 - T_P0, 0.3), T_P0)
    put_(sfx, tap(0.7), T_P1)
    for tk in (T_ICE, word("protect", 1.84)):
        put_(sfx, tap(0.5), tk + 0.05)
    for tc in (T_C2, T_C3, T_C4):
        put_(sfx, whoosh(0.6, 0.4), tc)
    for ts in (T_GRIP, T_PROT, T_KNOB):
        put_(sfx, stamp(0.5), ts)
    put_(sfx, ding(0.45), T_NODIFF)
    put_(sfx, stamp(0.7), T_NODIFF)
    put_(sfx, stamp(0.6), T_CTA)
    voice = np.zeros(n)
    for k in VO_KEYS:
        tmp = os.path.join(HERE, f"_vo_{k}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "voice", f"reel27_{k}.wav"),
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
    make_audio("audio_tape.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_tape.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
           "-ar", "44100", "-shortest", "-movflags", "+faststart", "reel27_tape.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(1.9, 9999)).save("reel27_thumbnail.jpg", quality=92)
    print("fertig: reel27_tape.mp4")


if __name__ == "__main__":
    main()
