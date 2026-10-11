"""Reel 18: THE DANGLE – 3D-Rekonstruktion eines echten Tors (dunkle Arena, Beat-Schnitte, 14 s).

Vorlage: Reel von @jrprospectshl – Giebelhaus (Bow Valley 17U AAA) zieht durch zwei Verteidiger
(#17, #47), lässt den Goalie in den Butterfly fallen und schiebt den Puck ins lange Eck.
Kein Original-Footage: nur der Puckweg, Gegner als Hologramm-Figuren.
  0.0–2.0   Rush übers Eis ("WATCH" / "THE HANDS." / "DEFENDER 1.")
  2.0–3.5   Zeitlupe: Dangle an #17 vorbei ("GONE.")
  3.5–4.5   #47 ("DEFENDER 2." / "GONE.")
  4.5–6.5   Goalie: Antäuschen Vorhand, Rückhand, Zeitlupe
  6.5–8.5   Kamera hinter dem Netz, Torlicht ("GOAL.")
  8.5–11.0  Replay in der Draufsicht mit Markern #17, #47, G
  11.0–14.0 "RATE THE MITTS 1–10?" + Credits
Renderer: puck3d_dark.py. Aufruf: python3 reel18_dangle.py -> reel18_dangle.mp4
"""
import math
import os
import subprocess
import time
import wave

import numpy as np
from PIL import Image, ImageFilter
from scipy.interpolate import CubicSpline

import puck3d_dark as P3
import reel15_puck as R15
import reel16_goal as G
from reel15_puck import (W, H, FPS, SPP, KSUB, SHUTTER, c01, smooth, sio, e_out, e_in, lerp, sph,
                         line_img, reveal, put, proj, projected, px_per_in, stroke_poly, partial, surface, surf_rgba,
                         over, PHI2, GOAL_X)

DUR = 14.0
HERE = R15.HERE
WHITE = (250, 250, 252)
RED = (255, 40, 50)
NEON = (255, 120, 30)
HOLO = (80, 160, 255)
GA = np.array([GOAL_X, 26.0, 0.0])
TOP_C = np.array([490.0, 0.0, 95.0])
TOP_HR = R15.TOP_H * 0.46
UP = np.array([0.0, 1.0, 0.0])

# ================================================================= Puckweg (tau = Spielzeit in s)
#        tau,   x,     z
KEYS = [(0.00, -120, 230), (0.80, 60, 215), (1.60, 300, 190), (2.30, 500, 168), (2.60, 575, 176),
        (2.80, 628, 204), (2.95, 652, 160), (3.10, 690, 100), (3.30, 742, 66), (3.45, 776, 74),
        (3.60, 806, 28), (3.80, 862, 12), (4.00, 922, 22), (4.25, 985, 28), (4.45, 1027, -24)]
T_TUCK, T_HIT = 4.45, 4.64
HIT_P = np.array([1094.0, 6.0, -24.0])
_SPL = CubicSpline([k[0] for k in KEYS], [[k[1], k[2]] for k in KEYS], bc_type="natural")
DEKES = [2.80, 2.95, 3.45, 3.60, 4.25, 4.45]
BEATEN = {"17": 2.98, "47": 3.62, "G": 4.47}


def puck_raw(tau):
    if tau < T_TUCK:
        x, z = _SPL(max(tau, 0.0))
        z += 7 * math.sin(2 * math.pi * 2.2 * tau) * (1 - smooth(2.2, 2.55, tau))   # Stickhandling
        return np.array([float(x), 0.5, float(z)])
    a = np.array([1027.0, 0.5, -24.0])
    if tau < T_HIT:                                  # Rückhand-Schieber ins lange Eck
        u = (tau - T_TUCK) / (T_HIT - T_TUCK)
        p = a + (HIT_P - a) * u
        p[1] = 0.5 + 5.5 * math.sin(math.pi / 2 * u)
        return p
    li = tau - T_HIT                                 # im Netz: fällt aufs Eis
    y = max(0.5, 6.0 - 0.5 * 386 * li ** 2)
    return np.array([HIT_P[0] - 3 * smooth(0, 0.15, li), y, HIT_P[2]])


def _spin_table():
    ts = np.arange(0, 12.0, 0.002)
    w = np.array([2.2 if t < T_TUCK else (6.0 if t < T_HIT else 3.0 * math.exp(-(t - T_HIT) * 2)) for t in ts])
    return ts, np.concatenate([[0], np.cumsum(w[:-1] * 2 * math.pi * 0.002)])


SPIN_T, SPIN_A = _spin_table()


def pstate(tau):
    return puck_raw(tau), G.THETA0 + float(np.interp(tau, SPIN_T, SPIN_A))


def fwd(tau, dt=0.03):
    v = puck_raw(min(tau, T_HIT - 0.02) + dt) - puck_raw(min(tau, T_HIT - 0.02) - dt)
    v[1] = 0
    n = np.linalg.norm(v)
    return v / n if n > 1e-6 else np.array([1.0, 0, 0])


def side(f):
    return np.array([-f[2], 0.0, f[0]])


# ================================================================= Gegner (Hologramme)
def ghost_state(name, tau):
    """Position, Höhe, Breite (z-Halbachse), Tiefe (x-Halbachse) und Zustand der Figur."""
    if name == "17":
        x = np.interp(tau, [0, 2.4, 2.8, 2.95, 3.4], [560, 630, 655, 665, 680])
        z = np.interp(tau, [0, 2.4, 2.8, 2.95, 3.4], [175, 160, 176, 194, 202])
        return np.array([x, 0.0, z]), 70.0, 15.0, 15.0
    if name == "47":
        x = np.interp(tau, [0, 3.2, 3.45, 3.6, 4.0], [720, 790, 805, 815, 832])
        z = np.interp(tau, [0, 3.2, 3.45, 3.6, 4.0], [10, 45, 62, 76, 82])
        return np.array([x, 0.0, z]), 70.0, 15.0, 15.0
    z = float(np.interp(tau, [0, 4.1, 4.3, 4.45], [8, 12, 22, 25]))   # Goalie folgt der Vorhand-Finte
    bf = smooth(4.26, 4.40, tau)                                       # Butterfly
    return np.array([GOAL_X - 26, 0.0, z]), lerp(56, 30, bf), lerp(26, 40, bf), 14.0


PROFILE = [(0.0, 0.62), (0.12, 0.58), (0.45, 0.82), (0.66, 1.0), (0.74, 0.95), (0.80, 0.5), (0.86, 0.62),
           (0.95, 0.55), (1.0, 0.3)]
GOALIE_PROFILE = [(0.0, 1.0), (0.35, 1.0), (0.55, 0.85), (0.72, 0.95), (0.82, 0.45), (0.9, 0.5), (1.0, 0.3)]


def _hull(pts):
    pts = sorted(map(tuple, pts))
    if len(pts) < 3:
        return np.array(pts)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return np.array(lo[:-1] + up[:-1])


def draw_ghost(ctx, cam, name, tau, t):
    c, hgt, rz, rx = ghost_state(name, tau)
    tb = BEATEN[name]
    li = tau - tb
    if li > 0.55:
        return
    col = HOLO if name != "G" else (150, 220, 255)
    k = 0.0 if li < 0 else e_out(c01(li / 0.5), 2)                 # 0 = steht, 1 = zerfallen
    if li >= 0:
        col = tuple(int(lerp(a, b, c01(li / 0.12))) for a, b in zip(col, RED))
    alpha = 1.0 - k
    prof = GOALIE_PROFILE if name == "G" else PROFILE
    ang = np.linspace(0, 2 * math.pi, 33)
    rings = []
    for h, r in prof:
        sc = r * (1 + 0.9 * k)
        y = h * hgt * (1 - 0.7 * k)
        rings.append(np.stack([c[0] + rx * sc * np.cos(ang), np.full_like(ang, y), c[2] + rz * sc * np.sin(ang)], 1))
    allp = np.concatenate(rings)
    xy, z = proj(cam, allp)
    if (z < 3).any():
        return
    zc = float(z.mean())
    wd = float(np.clip(0.55 * px_per_in(cam, zc), 1.2, 7))
    hull = _hull(xy)
    if len(hull) >= 3:
        ctx.set_source_rgba(col[0] / 255, col[1] / 255, col[2] / 255, 0.13 * alpha)
        ctx.move_to(*hull[0])
        for p in hull[1:]:
            ctx.line_to(*p)
        ctx.close_path()
        ctx.fill()
        stroke_poly(ctx, np.concatenate([hull, hull[:1]]), col, 0.25 * alpha, wd * 3.5)
        stroke_poly(ctx, np.concatenate([hull, hull[:1]]), col, 0.9 * alpha, wd)
    n = len(ang)
    for i, (h, _) in enumerate(prof):                                  # Ringe
        seg = xy[i * n:(i + 1) * n]
        stroke_poly(ctx, seg, col, (0.55 if i in (0, len(prof) - 1) else 0.3) * alpha, wd * 0.7)
    for j in range(0, n - 1, 4):                                       # Meridiane
        seg = xy[j::n]
        stroke_poly(ctx, seg, col, 0.22 * alpha, wd * 0.5)
    for s in range(3):                                                 # wandernde Scanlinien
        hh = ((t * 0.9 + s / 3) % 1.0)
        r = float(np.interp(hh, [p[0] for p in prof], [p[1] for p in prof]))
        ring = np.stack([c[0] + rx * r * np.cos(ang), np.full_like(ang, hh * hgt * (1 - 0.7 * k)),
                         c[2] + rz * r * np.sin(ang)], 1)
        sxy, sz = proj(cam, ring)
        if (sz > 3).all():
            stroke_poly(ctx, sxy, (230, 245, 255), 0.5 * alpha * math.sin(math.pi * hh), wd * 0.6)
    floor = np.stack([c[0] + rx * 1.8 * np.cos(ang), np.full_like(ang, 0.05), c[2] + rz * 1.8 * np.sin(ang)], 1)
    fxy, fz = proj(cam, floor)
    if (fz > 3).all():
        stroke_poly(ctx, fxy, col, 0.18 * alpha, wd * 6)
        stroke_poly(ctx, fxy, col, 0.6 * alpha, wd)
    if 0 <= li < 0.5:                                                  # Zerfall: Splitter
        r_ = G.rv(40, 300 + hash(name) % 50)
        for i in range(40):
            hh = r_[i, 0] * hgt
            a_ = r_[i, 1] * 2 * math.pi
            p0 = c + np.array([rx * math.cos(a_), hh, rz * math.sin(a_)])
            v = np.array([math.cos(a_) * (40 + 80 * r_[i, 2]), 20 + 60 * r_[i, 3], math.sin(a_) * (40 + 80 * r_[i, 2])])
            p = p0 + v * li + np.array([0, -0.5 * 300 * li * li, 0])
            sxy, sz = proj(cam, [p, p - v * 0.03])
            if (sz > 3).all():
                stroke_poly(ctx, sxy, col, 0.9 * (1 - li / 0.5), wd * 1.2)


def ghost_label(L, cam, name, tau):
    c, hgt, _, _ = ghost_state(name, tau)
    li = tau - BEATEN[name]
    if li > 0.15:
        return
    p, z = projected(cam, c + np.array([0, hgt + 14, 0]))
    if z < 8:
        return
    size = int(np.clip(px_per_in(cam, z) * 16, 26, 150))
    txt = "G" if name == "G" else "#" + name
    img = word_img(txt, size, WHITE, HOLO, cache=False)
    if li > 0:
        img.putalpha(img.getchannel("A").point(lambda v: int(v * (1 - li / 0.15))))
    put(L, img, p[0] - img.width / 2, p[1] - img.height / 2)


# ================================================================= Einstellungen (Rigs)
def rig_front(tau, u, s=1.0):
    p, _ = pstate(tau)
    f = fwd(tau)
    return p + f * (14 - 3 * u) + side(f) * 3 * s + UP * 1.4, p, UP, 42, 0.05


def rig_side(tau, u, s=1.0):
    p, _ = pstate(tau)
    f = fwd(tau)
    return p + side(f) * 14 * s + f * (-5 + 10 * u) + UP * 2.4, p + f * 2, UP, 44, 0.04


def rig_chase(tau, u):
    p, _ = pstate(tau)
    f = fwd(tau)
    return p - f * 12 + UP * 3.0 + side(f) * 2, p + f * 14 + UP * 2.0, UP, 50, 0.02


def rig_top(tau, u):
    p, _ = pstate(tau)
    f = fwd(tau)
    a = lerp(-0.35, 0.35, u)
    up = f * math.cos(a) + side(f) * math.sin(a)
    return p + UP * lerp(120, 92, u) - f * 20, p + f * 35, up, 48, 0.0


def rig_pass(name, tau, u):
    """Puck und Gegner gemeinsam im Bild: Kamera auf der anderen Seite des Puckwegs, schräg dahinter."""
    tb = BEATEN[name]
    pb = puck_raw(tb - 0.08)
    d = ghost_state(name, tb - 0.08)[0]
    f = fwd(tb - 0.25)
    dv = d - pb
    dv[1] = 0
    dv /= np.linalg.norm(dv) + 1e-9
    p, _ = pstate(tau)
    follow = (p - pb) * 0.45
    pos = pb - dv * 44 - f * 36 + UP * 15 + follow + side(f) * 8 * (u - 0.5)
    tgt = pb * 0.35 + p * 0.35 + d * 0.3 + UP * 10
    return pos, tgt, UP, 47, 0.03


def rig_goalie(tau, u):
    p, _ = pstate(tau)
    pos = np.array([lerp(872, 905, sio(u)), lerp(38, 32, u), lerp(-46, -40, u)])
    tgt = np.array([lerp(1000, 1040, sio(u)), 13.0, lerp(10, -8, sio(u))]) * 0.75 + p * 0.25
    return pos, tgt, UP, 40, 0.03


def rig_netcam(tau, u):
    p, _ = pstate(tau)
    pos = np.array([GOAL_X + 54.0, 26.0, -40.0])
    return pos, p * 0.75 + np.array([GOAL_X - 60, 14.0, 0.0]) * 0.25, UP, 50, 0.0


def rig_celebrate(tau, u):
    return sph(GA, lerp(230, 190, u), lerp(150, 205, sio(u)), lerp(12, 24, u)), GA, UP, 50, 0.0


def rig_top_replay(tau, u):
    h = TOP_HR * lerp(1.06, 1.0, u)
    return TOP_C + np.array([-0.5, h, 0]), TOP_C.copy(), np.array([1.0, 0, 0]), 30, 0.0


def rig_cta(tau, u):
    c = TOP_C + (np.array([GOAL_X - 150, 0, 0]) - TOP_C) * e_in(u, 2)
    h = TOP_HR * lerp(1.0, 0.9, e_in(u, 2))
    return c + np.array([-0.5, h, 0]), c, np.array([1.0, 0, 0]), 30, 0.0


#        v0,   v1,   tau0, tau1,  rig,                           Wort,           ab tau
SHOTS = [(0.0, 0.5, 0.40, 0.90, lambda t, u: rig_front(t, u, 1), "WATCH", None),
         (0.5, 1.0, 0.90, 1.45, lambda t, u: rig_side(t, u, 1), "THE HANDS.", None),
         (1.0, 1.5, 1.45, 2.05, rig_chase, "DEFENDER 1.", None),
         (1.5, 2.0, 2.05, 2.55, rig_top, None, None),
         (2.0, 3.5, 2.55, 3.22, lambda t, u: rig_pass("17", t, u), "GONE.", 2.97),
         (3.5, 4.0, 3.22, 3.50, rig_chase, "DEFENDER 2.", None),
         (4.0, 4.5, 3.50, 3.82, lambda t, u: rig_pass("47", t, u), "GONE.", 3.62),
         (4.5, 5.0, 3.82, 4.12, rig_chase, "GOALIE.", None),
         (5.0, 6.5, 4.12, 4.56, rig_goalie, "GONE.", 4.46),
         (6.5, 7.0, 4.56, 4.78, rig_netcam, "GOAL.", None),
         (7.0, 8.5, 4.78, 6.30, rig_celebrate, None, None),
         (8.5, 11.0, 9.0, 9.0, rig_top_replay, "REPLAY", None),
         (11.0, 14.0, 9.0, 9.0, rig_cta, None, None)]
CUTS = [s[0] for s in SHOTS[1:]]
K_NET, K_CEL, K_REP, K_CTA = 9, 10, 11, 12
SLOWMO = (4, 8)


def shot_at(t):
    for k, s in enumerate(SHOTS):
        if s[0] <= t < s[1]:
            return k
    return len(SHOTS) - 1


def tau_of(k, t):
    v0, v1, a, b = SHOTS[k][:4]
    u = c01((t - v0) / (v1 - v0))
    uu = u + 0.13 * math.sin(2 * math.pi * u) if k in SLOWMO else u
    return a + (b - a) * uu, u


def t_of_tau(k, tau):
    v0, v1, a, b = SHOTS[k][:4]
    lo, hi = v0, v1
    for _ in range(40):
        m = (lo + hi) / 2
        if tau_of(k, m)[0] < tau:
            lo = m
        else:
            hi = m
    return lo


T_GOAL = t_of_tau(K_NET, T_HIT)


def state(t, k=None):
    k = shot_at(t) if k is None else k
    tau, u = tau_of(k, t)
    pos, tgt, up, fov, ap = SHOTS[k][4](tau, u)
    p, th = pstate(tau)
    return k, tau, pos, tgt, up, fov, ap, p, th


def shake(t):
    off = np.zeros(3)
    for ts, amp in ((T_GOAL, 3.0), (2.0 + 0.62, 0.8), (5.0 + 0.9, 0.8), (0.0, 0.6)):
        lt = t - ts
        if 0 <= lt < 0.6:
            e = amp * math.exp(-lt * 8)
            off += np.array([math.sin(lt * 91), math.cos(lt * 77), math.sin(lt * 63)]) * e
    return off


def cam_row_at(t, k=None):
    k, tau, pos, tgt, up, fov, ap, p, th = state(t, k)
    pos = pos + shake(t) * (0.15 if k < K_CEL else 3.0)
    r, u_, f = P3.look_at(pos, tgt, up)
    return P3.cam_row(pos, r, u_, f, fov), ap, float(np.linalg.norm(tgt - pos)), (p, th, k, tau)


def render3d(t, fidx):
    k = shot_at(t)
    v0, v1 = SHOTS[k][:2]
    cams, lens, pk = np.zeros((KSUB, 13)), np.zeros((KSUB, 2)), np.zeros((KSUB, 7))
    for j in range(KSUB):
        tk = min(max(t + ((j + 0.5) / KSUB - 0.5) * SHUTTER, v0), v1 - 1e-4)
        row, ap, focus, (p, th, _, _) = cam_row_at(tk, k)
        cams[j], lens[j] = row, (ap, focus)
        pk[j] = (p[0], p[1], p[2], th, 1.0, 0.0, tk)
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, SPP, fidx + 18, cams, lens, pk, R15.logo_tex(), base, puck, cov)
    return P3.tonemap(base), P3.tonemap(puck), cov


# ================================================================= Netz (Einschlag unten, langes Eck)
def net_offset(p, w, t):
    tau = t - (T_HIT + 0.01)
    if tau <= 0:
        return p
    A = 11.0 * (1 - math.exp(-tau / 0.03)) * math.exp(-tau * 4.0) * math.cos(2 * math.pi * 1.7 * tau)
    d2 = np.sum((p - HIT_P - np.array([4.0, 0.0, 0.0])) ** 2, axis=-1)
    q = p.copy()
    q[..., 0] += A * np.exp(-d2 / (2 * 16.0 ** 2)) * np.maximum(w, 0.25)
    return q


R15.net_offset = net_offset


# ================================================================= Overlays
def _scratches():
    rng = np.random.default_rng(18)
    out = []
    path = [puck_raw(t) for t in np.arange(0, T_HIT, 0.02)]
    for _ in range(1500):
        c = path[rng.integers(len(path))]
        p = np.array([c[0] + rng.normal(0, 60), 0.02, c[2] + rng.normal(0, 60)])
        a = rng.uniform(-0.5, 0.5) + (0 if rng.random() < 0.7 else math.pi / 2)
        d = np.array([math.cos(a), 0, math.sin(a)]) * rng.uniform(6, 40)
        bend = np.array([-d[2], 0, d[0]]) * rng.uniform(-0.08, 0.08)
        u = np.linspace(0, 1, 6)[:, None]
        out.append((p + d * u + bend * np.sin(math.pi * u), rng.uniform(0.25, 0.6)))
    return out


SCRATCHES = _scratches()


def scratches(ctx, cam):
    pos = cam[0:3]
    if pos[1] > 300:
        return
    for pl, a in SCRATCHES:
        dist = np.linalg.norm(pl[0] - pos)
        if dist > 220:
            continue
        xy, z = proj(cam, pl)
        if (z < 0.6).any():
            continue
        wd = float(np.clip(0.05 * px_per_in(cam, z.mean()), 0.6, 3.0))
        stroke_poly(ctx, xy, (150, 175, 220), a * 0.6 * (1 - dist / 220), wd)


def neon_trail(ctx, cam, tau, k):
    if k >= K_REP or tau < 0.45:
        return
    ts = np.linspace(max(0.4, tau - 0.32), min(tau, T_HIT), 26)
    pts = np.array([puck_raw(x) for x in ts])
    pts[:, 1] = np.maximum(pts[:, 1] - 0.45, 0.03)
    xy, z = proj(cam, pts)
    if (z < 0.6).any() or len(xy) < 2:
        return
    w = float(np.clip(1.4 * px_per_in(cam, z[-1]), 4, 60))
    stroke_poly(ctx, xy, NEON, 0.18, w * 2.2)
    stroke_poly(ctx, xy, NEON, 0.55, w * 0.9)
    stroke_poly(ctx, xy, (255, 220, 170), 0.9, max(2.0, w * 0.25))


def fx(ctx, t, cam, tau, k):
    for n_, td in enumerate(DEKES):                                     # Eisspray bei jedem Haken
        if 0 <= tau - td < 0.5:
            p = puck_raw(td)
            G.spray(ctx, cam, tau, td, p + np.array([0, 0.3, 0]), -fwd(td), 60 + n_, 80, 1.1)
    if k in (K_NET, K_CEL) and tau >= T_HIT:                            # Funken am Netz
        li = tau - T_HIT
        r_ = G.rv(90, 78)
        for i in range(90):
            lt = li - r_[i, 0] * 0.05
            if lt < 0 or lt > 0.8:
                continue
            v = np.array([-(10 + r_[i, 1] * 60), 15 + r_[i, 2] * 50, (r_[i, 3] - 0.5) * 90])
            p = HIT_P + v * lt + np.array([0, -0.5 * 300 * lt * lt, 0])
            p[1] = max(p[1], 0.2)
            xy, z = proj(cam, [p, p - v * 0.02])
            if (z > 1).all():
                stroke_poly(ctx, xy, (255, 196, 70), 0.95 * (1 - lt / 0.8), 3.5)


# ---------------- Replay (Draufsicht)
def _trail():
    ts = np.linspace(0.0, T_HIT, 1200)
    pts = np.array([puck_raw(x) for x in ts])
    pts[:, 1] = 0.3
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    return pts, ts, cum / cum[-1]


TRAIL, TRAIL_T, TRAIL_F = _trail()
MARKS = [(float(np.interp(BEATEN["17"], TRAIL_T, TRAIL_F)), "17"),
         (float(np.interp(BEATEN["47"], TRAIL_T, TRAIL_F)), "47"),
         (float(np.interp(BEATEN["G"], TRAIL_T, TRAIL_F)), "G")]
REP0, REP1 = 8.65, 10.3


def replay(ctx, t, cam):
    if t < SHOTS[K_REP][0]:
        return
    fr = smooth(REP0, REP1, t)
    out = 1 - smooth(11.6, 12.0, t)
    xy, z = proj(cam, TRAIL)
    if fr <= 0 or not (z > 5).all():
        return
    ctx.push_group()
    for f_, name in MARKS:                                              # Gegner als Ringe auf dem Eis
        c, _, rz, rx = ghost_state(name, BEATEN[name] - 0.05)
        ring = np.stack([c[0] + rx * 2.2 * np.cos(PHI2), np.full_like(PHI2, 0.1), c[2] + rz * 2.2 * np.sin(PHI2)], 1)
        rxy, _ = proj(cam, ring)
        a = smooth(REP0 - 0.1, REP0 + 0.25, t)
        beat = fr >= f_
        col = RED if beat else HOLO
        stroke_poly(ctx, rxy, col, 0.25 * a, 16)
        stroke_poly(ctx, rxy, col, 0.95 * a, 4)
        if beat:
            cc = rxy.mean(0)
            q = e_out(c01((fr - f_) / 0.06), 3) * 12
            stroke_poly(ctx, np.array([cc - q, cc + q]), RED, a, 5)
            stroke_poly(ctx, np.array([cc + [q, -q], cc + [-q, q]]), RED, a, 5)
    pl = partial(xy, fr)
    stroke_poly(ctx, pl, NEON, 0.15, 34)
    stroke_poly(ctx, pl, NEON, 0.5, 14)
    stroke_poly(ctx, pl, (255, 230, 190), 1.0, 5)
    head = pl[-1]
    ctx.set_source_rgba(1, 1, 1, 1)
    ctx.arc(head[0], head[1], 9, 0, 2 * math.pi)
    ctx.fill()
    ctx.pop_group_to_source()
    ctx.paint_with_alpha(out)


def replay_labels(L, t, cam):
    if not SHOTS[K_REP][0] <= t < 11.9:
        return
    out = smooth(11.6, 11.85, t)
    a = smooth(REP0 - 0.1, REP0 + 0.25, t)
    for f_, name in MARKS:
        c, _, rz, _ = ghost_state(name, BEATEN[name] - 0.05)
        p, z = projected(cam, c + np.array([0, 0, -rz * 2.2 - 10]))
        txt = "GOALIE" if name == "G" else "#" + name
        reveal(L, line_img(txt, 40, 800, WHITE, track=2), p[0], p[1] + 44, a, out)
    fr = smooth(REP0, REP1, t)
    if fr >= 1:
        p, _ = projected(cam, HIT_P)
        reveal(L, word_img("GOAL", 60, RED, RED), p[0], p[1] - 70, smooth(REP1, REP1 + 0.15, t), out)


# ---------------- Wörter
_WORDS = {}


def word_img(txt, size, col, glow_col=NEON, cache=True):
    key = (txt, size, col, glow_col)
    if key in _WORDS and cache:
        return _WORDS[key]
    img = line_img(txt, size, 900, col, cache=cache)
    pad = 40
    sh = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
    a = Image.new("L", sh.size, 0)
    a.paste(img.getchannel("A"), (pad, pad))
    glow = Image.new("RGBA", sh.size, glow_col + (0,))
    glow.putalpha(a.filter(ImageFilter.GaussianBlur(max(4, size // 13))).point(lambda v: min(255, int(v * 1.3))))
    dark = Image.new("RGBA", sh.size, (0, 0, 0, 0))
    dark.putalpha(a.filter(ImageFilter.GaussianBlur(5)).point(lambda v: int(v * 0.6)))
    sh.alpha_composite(glow)
    sh.alpha_composite(dark, (4, 8))
    sh.alpha_composite(img, (pad, pad))
    if cache:
        _WORDS[key] = sh
    return sh


def words(L, t, k, tau):
    v0, v1, _, _, _, w, w_tau = SHOTS[k]
    if w and k < K_CTA:
        t_on = v0 if w_tau is None else t_of_tau(k, w_tau)
        if t >= t_on:
            lt = t - t_on
            size = 230 if len(w) <= 6 else (170 if len(w) <= 10 else 150)
            col = RED if w in ("GONE.", "GOAL.") else WHITE
            img = word_img(w, size, col)
            sc = (1.0 if k == 0 else lerp(1.6, 1.0, e_out(lt / 0.12, 3))) * (1 + 0.04 * lt)
            a = (1.0 if k == 0 else c01(lt / 0.05)) * (1 - smooth(v1 - 0.06, v1, t))
            if k == K_REP:
                a *= 1 - smooth(9.4, 9.6, t)
            im = img.resize((int(img.width * sc), int(img.height * sc)), Image.BILINEAR)
            if a < 1:
                im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
            y = 520 if k < K_REP else 300
            put(L, im, W / 2 - im.width / 2, y - im.height / 2)
    if k in SLOWMO:
        v0, v1 = SHOTS[k][:2]
        reveal(L, line_img("SLOW-MO", 34, 700, (200, 205, 220), track=8), W / 2, 700,
               smooth(v0 + 0.15, v0 + 0.3, t), smooth(v1 - 0.2, v1 - 0.05, t))
    if 0.5 <= t < 1.5:                                                  # kleine Zeile oben
        reveal(L, line_img("GIEBELHAUS  ·  BOW VALLEY 17U AAA", 30, 700, (200, 205, 220), track=4), W / 2, 250,
               smooth(0.5, 0.7, t), smooth(1.3, 1.45, t))
    if t >= 11.0:
        reveal(L, word_img("RATE THE MITTS", 112, WHITE), W / 2, 470, smooth(11.05, 11.25, t))
        reveal(L, word_img("1 – 10?", 230, NEON), W / 2, 670, smooth(11.2, 11.4, t))
        reveal(L, line_img("GIEBELHAUS  ·  BOW VALLEY 17U AAA", 34, 800, WHITE, track=4), W / 2, 850,
               smooth(11.4, 11.6, t))
        reveal(L, line_img("VIDEO: @JRPROSPECTSHL  ·  RECREATED IN 3D", 28, 600, (190, 196, 212), track=4), W / 2, 905,
               smooth(11.5, 11.7, t))


# ================================================================= Bild
_VIG = None


def vignette():
    global _VIG
    if _VIG is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2) * 2
        _VIG = (1 - 0.45 * np.clip(r - 0.45, 0, 1) ** 1.3)[..., None]
    return _VIG


def bloom(img):
    br = np.clip(img - 0.62, 0, None)
    small = Image.fromarray((np.clip(br, 0, 1) * 255).astype(np.uint8)).resize((W // 6, H // 6), Image.BILINEAR)
    b1 = np.asarray(small.filter(ImageFilter.GaussianBlur(3)).resize((W, H), Image.BILINEAR)).astype(np.float32) / 255
    b2 = np.asarray(small.filter(ImageFilter.GaussianBlur(10)).resize((W, H), Image.BILINEAR)).astype(np.float32) / 255
    return img + b1 * 0.7 + b2 * 0.8


def compose(t, fidx):
    base, puck, cov = render3d(t, fidx)
    row, ap, focus, (p, th, k, tau) = cam_row_at(t)
    cpos = row[0:3]
    dp = float(np.linalg.norm(p - cpos))
    sc, sctx = surface()
    scratches(sctx, row)
    img = over(base, *surf_rgba(sc))
    tr, tctx = surface()
    neon_trail(tctx, row, tau, k)
    img = over(img, *surf_rgba(tr))
    # Hologramme: hinter bzw. vor dem Puck
    gb, gbc = surface()
    gf, gfc = surface()
    if k < K_REP:
        for name in ("17", "47", "G"):
            c, hgt, _, _ = ghost_state(name, tau)
            dg = float(np.linalg.norm(c + np.array([0, hgt * 0.3, 0]) - cpos))
            draw_ghost(gbc if dg > dp else gfc, row, name, tau, t)
    show_net = k >= 7
    pa = cov[..., None]
    if show_net:
        nb, nf = R15.draw_net(row, tau, False), R15.draw_net(row, tau, True)
        b_, f_ = surf_rgba(nb), surf_rgba(nf)
        netcam = k == K_NET
        inside = p[0] > GOAL_X - 0.5
        if not netcam:
            img = over(img, *b_)
            if not inside:
                img = over(img, *f_)
        img = over(img, *surf_rgba(gb))
        img = img * (1 - pa) + puck * pa
        if netcam:
            img = over(img, *b_)
        if inside or netcam:
            img = over(img, *f_)
    else:
        img = over(img, *surf_rgba(gb))
        img = img * (1 - pa) + puck * pa
    img = over(img, *surf_rgba(gf))
    fs, ctx = surface()
    fx(ctx, t, row, tau, k)
    replay(ctx, t, row)
    img = over(img, *surf_rgba(fs))
    if k in (K_NET, K_CEL) and tau >= T_HIT:                            # Torlicht-Stroboskop
        li = tau - T_HIT
        strobe = 0.5 + 0.5 * math.cos(li * 2 * math.pi * 3.2)
        a = 0.32 * strobe * math.exp(-li * 0.6)
        img = img * (1 - a) + np.array([1.0, 0.08, 0.1], np.float32) * a
    img = bloom(img)
    lc = min([t - c for c in CUTS if t >= c] + [t + 0.5])
    if lc < 0.1:
        img = img + (1 - lc / 0.1) * 0.35
    zp = 1 + 0.07 * math.exp(-lc * 14)
    img = np.clip(img, 0, 1)
    pil = Image.fromarray((img * 255).astype(np.uint8))
    if zp > 1.002:
        w2, h2 = W / zp, H / zp
        pil = pil.transform((W, H), Image.EXTENT, ((W - w2) / 2, (H - h2) / 2, (W + w2) / 2, (H + h2) / 2), Image.BILINEAR)
    arr = np.asarray(pil).astype(np.float32) / 255
    ca = int(round(10 * math.exp(-lc * 12) + 12 * math.exp(-abs(t - T_GOAL) * 20) * (t >= T_GOAL - 0.02)))
    if ca:
        arr[..., 0] = np.roll(arr[..., 0], ca, 1)
        arr[..., 2] = np.roll(arr[..., 2], -ca, 1)
    if t > 11.0:
        arr = arr * (1 - 0.55 * smooth(11.0, 11.4, t))
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if k < K_NET:
        for name in ("17", "47", "G"):
            ghost_label(L, row, name, tau)
    words(L, t, k, tau)
    replay_labels(L, t, row)
    ta = np.asarray(L).astype(np.float32) / 255
    arr = arr * (1 - ta[..., 3:4]) + ta[..., :3] * ta[..., 3:4]
    arr = arr * vignette()
    arr += np.random.default_rng(fidx).normal(0, 0.012, arr.shape[:2])[..., None]
    return (np.clip(arr, 0, 1) * 255).astype(np.uint8)


# ================================================================= Sound (Phonk, 120 BPM)
SR = 44100


def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(18)
    mus, sfx = np.zeros(n), np.zeros(n)

    def tt(sec):
        return np.arange(int(sec * SR)) / SR

    def put_(buf, sig, at, vol=1.0):
        st = int(round(at * SR))
        if st < 0:
            sig, st = sig[-st:], 0
        e = min(n, st + len(sig))
        if st < n:
            buf[st:e] += sig[: e - st] * vol

    def lp(x, k):
        c = np.cumsum(np.concatenate([np.zeros(k), x]))
        return (c[k:] - c[:-k]) / k

    def hp(x, k):
        return x - lp(x, k)

    def noise(sec):
        return rng.standard_normal(int(sec * SR))

    def kick(vol=1.0):
        x = tt(0.35)
        f = 45 + 160 * np.exp(-x * 35)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 9) * 3.0) * vol

    def snare(vol=1.0):
        x = tt(0.3)
        return (np.sin(2 * np.pi * 185 * x) * np.exp(-x * 30) * 0.6 + hp(noise(0.3), 3) * np.exp(-x * 18)) * 0.6 * vol

    def hat(vol=0.18):
        return hp(noise(0.04), 2) * np.exp(-tt(0.04) * 120) * vol

    def bass808(freq, dur, glide=0.0):
        x = tt(dur)
        f = freq * (1 + glide * np.exp(-x * 8))
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * 2.5) * np.minimum(x / 0.005, 1) * np.exp(-x * 1.6) * 0.8

    def cowbell(freq, dur=0.25, vol=0.25):
        x = tt(dur)
        sig = np.sign(np.sin(2 * np.pi * freq * x)) + np.sign(np.sin(2 * np.pi * freq * 1.48 * x))
        return lp(sig, 3) * np.exp(-x * 14) * vol

    def whoosh(dur=0.4, vol=1.0):
        x = tt(dur)
        nz = noise(dur)
        env = np.sin(np.pi * x / dur) ** 2
        return (lp(nz, 30) * (1 - x / dur) + (lp(nz, 5) - lp(nz, 30)) * (x / dur) * 1.4) * env * 1.3 * vol

    def boom(dur=1.2, f0=45, vol=1.0):
        x = tt(dur)
        f = f0 + 110 * np.exp(-x * 14)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 3) * 2.2) * vol

    def scrape(dur=0.35, vol=0.7):
        x = tt(dur)
        return hp(noise(dur), 2) * np.exp(-x * 8) * vol

    def glitch(vol=0.6):
        x = tt(0.25)
        return np.sign(np.sin(2 * np.pi * (900 - 2400 * x) * x)) * (x * 40 % 1 < 0.5) * np.exp(-x * 12) * vol * 0.4

    def riser(dur, vol=1.0):
        x = tt(dur)
        sw = np.sin(2 * np.pi * np.cumsum(200 + 2200 * (x / dur) ** 2) / SR) * (x / dur) ** 3 * 0.15
        return (hp(noise(dur), 4) * (x / dur) ** 2 * 0.4 + sw) * vol

    def horn(dur=2.0):
        x = tt(dur)
        sig = sum(2 * ((x * f * (1 + 0.003 * np.sin(2 * np.pi * 4.5 * x))) % 1) - 1 for f in (110.0, 138.6, 164.8))
        return lp(lp(sig, 10), 6) / 3 * np.minimum(x / 0.05, 1) * np.clip((dur - x) / 0.3, 0, 1) * 0.7

    def crowd(dur, vol):
        x = tt(dur)
        return lp(noise(dur), 14) * 3 * (0.8 + 0.2 * np.sin(2 * np.pi * 0.7 * x)) * vol

    B = 0.5
    notes = [55.0, 55.0, 65.4, 49.0]
    bell = [880.0, 880.0, 1046.5, 987.8, 880.0, 784.0, 880.0, 659.3]
    for k in range(int(DUR / B)):
        tb = k * B
        if 2.0 <= tb < 3.5 or 5.0 <= tb < 6.5 or 11.0 <= tb < 12.0:
            continue
        put_(mus, kick(), tb)
        if k % 2 == 1:
            put_(mus, snare(), tb)
        for j in range(4):
            put_(mus, hat(0.2 if j % 2 == 0 else 0.12), tb + j * B / 4)
        if k % 4 == 3:
            for j in range(4):
                put_(mus, hat(0.12), tb + B / 2 + j * B / 8)
        put_(mus, bass808(notes[(k // 2) % 4], 0.48, 0.6 if k % 4 == 0 else 0.0), tb)
        put_(mus, cowbell(bell[k % 8] / 2, 0.22, 0.2), tb + 0.25)
    for s0 in (2.0, 5.0):                                                # Zeitlupen: Herzschlag + gedehnter Bass
        for hb in (0.1, 0.9):
            put_(sfx, boom(0.35, 42, 0.7), s0 + hb)
            put_(sfx, boom(0.3, 42, 0.45), s0 + hb + 0.18)
        put_(sfx, bass808(41.2, 1.5, 0.0) * 0.6, s0)
        put_(sfx, riser(0.45, 0.8), s0 + 1.05)
    for c in CUTS:
        put_(sfx, whoosh(0.22, 0.6), c - 0.12)
    for k_, w_tau in ((4, 2.97), (8, 4.46)):                             # "GONE." – Glitch + Kratzer
        tg = t_of_tau(k_, w_tau)
        put_(sfx, glitch(0.8), tg)
        put_(sfx, scrape(0.4, 0.9), tg - 0.05)
    put_(sfx, glitch(0.8), 4.0)
    for tv in (0.5, 1.0, 3.5, 4.5):
        put_(sfx, scrape(0.3, 0.6), tv)
    put_(sfx, lp(noise(0.4), 18) * np.exp(-tt(0.4) * 8) * 1.5, T_GOAL)
    put_(sfx, boom(1.8, 38, 1.3), T_GOAL)
    put_(sfx, horn(2.2), T_GOAL + 0.05)
    put_(sfx, crowd(3.0, 0.7) * np.exp(-tt(3.0) * 0.5), T_GOAL + 0.05)
    put_(sfx, riser(1.4, 0.7), 8.5)
    put_(sfx, boom(1.0, 50, 0.8), 11.0)

    mix = mus * 0.75 + sfx
    mix /= np.percentile(np.abs(mix), 99.9) + 1e-9
    mix = np.tanh(mix * 1.1)
    mix = mix / np.max(np.abs(mix)) * 0.95
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


def main():
    os.chdir(HERE)
    make_audio("audio_dangle.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_dangle.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "23",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
           "reel18_dangle.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(2.75, 9999)).save("reel18_thumbnail.jpg", quality=92)
    print("fertig: reel18_dangle.mp4")


if __name__ == "__main__":
    main()
