"""Reel 16: THE PERFECT GOAL – 3D-Motion-Video, ein Spielzug in einer einzigen Kamerafahrt (22 s, Loop).

Ablauf:
  0.0–1.3   Bully: Puck knallt auf den Mittelpunkt ("WATCH THIS PUCK.")
  1.3–5.0   THE DANGLE: drei Haken im Zickzack, Eisspray bei jedem Richtungswechsel
  5.0–8.4   THE SAUCER: Puck fliegt rotierend durch die Luft, Zeitlupe, Kamera umkreist ihn
  8.4–10.6  THE ONE-TIMER: Peitschenschwenk, Schuss
  10.6–13.2 TOP SHELF: Einschlag oben im Netz, Torlicht, Kamerawackeln
  13.2–17.8 THE REPLAY: Kranfahrt in die Draufsicht, der Spielzug zeichnet sich als Linie aufs Eis
  17.8–22.0 Sturzflug zurück, "RATE THIS GOAL 1–10" – Loop (Puck fällt wieder auf den Punkt)
Nutzt puck3d.py (Raytracer) und Bausteine aus reel15_puck.py.
Aufruf: python3 reel16_goal.py  ->  reel16_goal.mp4
"""
import math
import os
import subprocess
import time
import wave

import numpy as np
from PIL import Image, ImageDraw

import puck3d as P3
import reel15_puck as R
from reel15_puck import (W, H, FPS, SPP, KSUB, SHUTTER, INK, ORANGE, GREY, c01, smooth, sio, smoother, e_out, e_in,
                         lerp, sph, blend_up, hermite, line_img, reveal, reveal_halo, put, proj, projected,
                         px_per_in, stroke_poly, partial, surface, surf_rgba, over, PHI2, GOAL_X)

DUR = 22.0
HERE = R.HERE
P0 = np.array([-40.0, 0.0, -60.0])                  # Start auf freiem Eis im Mittelkreis
T0 = P0 + np.array([0.0, 0.5, 0.0])
THETA0 = -2.48
T_LAND, G_EFF = 0.25, 35.2
GA = np.array([GOAL_X, 26.0, 0.0])
T_SHOT, T_HIT = 8.9, 10.6
HIT_P = np.array([1086.0, 40.0, -20.0])
SHOT_A = np.array([775.0, 0.5, 168.0])
TOP_C, TOP_H = R.TOP_C, R.TOP_H
T_CRANE, T_TOP, T_DIVE = 13.2, 17.2, 17.8


# ================================================================= Puckweg
def puck_raw(t):
    """Position ohne Fall/Loop-Behandlung."""
    if t < 1.3:
        return T0.copy()
    if t < 5.0:                                   # Dangle
        u = (t - 1.3) / 3.7
        x = P0[0] + (640 - P0[0]) * u ** 1.4
        z = P0[2] * (1 - u) + 34 * math.sin(3 * math.pi * u) * smooth(0, 0.08, u)
        return np.array([x, 0.5, z])
    if t < 8.4:                                   # Saucer (Zeitlupe in der Mitte)
        u = (t - 5.0) / 3.4
        p = u + 0.13 * math.sin(2 * math.pi * u)
        return np.array([640 + 120 * p, 0.5 + 10 * math.sin(math.pi * p), 170 * p])
    if t < T_SHOT:                                # annehmen
        u = (t - 8.4) / 0.5
        return np.array([760 + 15 * e_out(u, 2), 0.5, 170 - 2 * e_out(u, 2)])
    if t < T_HIT:                                 # One-Timer
        u = (t - T_SHOT) / (T_HIT - T_SHOT)
        q = 1 - (1 - u) ** 1.6
        p = SHOT_A + (HIT_P - SHOT_A) * q
        p[1] = 0.5 + 39.5 * q
        return p
    tau = t - T_HIT                               # im Netz: fällt herunter
    y = max(0.5, 40.0 - 0.5 * 386 * max(0.0, tau - 0.05) ** 2)
    return np.array([HIT_P[0] - 2 * smooth(0, 0.2, tau), y, HIT_P[2]])


def _spin_table():
    ts = np.arange(0, DUR + 0.01, 0.002)
    w = np.array([0.0 if t < 1.3 else (2.0 if t < 5.0 else (7.0 if t < 8.4 else (1.0 if t < T_SHOT else
                  (10.0 if t < T_HIT else 3.0 * math.exp(-(t - T_HIT) * 2))))) for t in ts]) * 2 * math.pi
    return ts, np.concatenate([[0], np.cumsum(w[:-1] * 0.002)])


SPIN_T, SPIN_A = _spin_table()


def puck_state(t):
    t = t % DUR
    if t >= DUR - 0.4 or t < T_LAND + 0.2:        # Fall auf den Bully-Punkt (Loop-Naht)
        tl = t - DUR if t >= DUR - 0.4 else t
        if tl < T_LAND:
            y = 0.5 + 0.5 * G_EFF * (T_LAND - tl) ** 2
        else:
            y = 0.5 + 0.18 * math.sin(math.pi * c01((tl - T_LAND) / 0.14))
        return np.array([P0[0], y, P0[2]]), THETA0, 1.0
    if 16.0 <= t < DUR - 0.4:
        return np.array([0.0, 300.0, 0.0]), THETA0, 0.0
    return puck_raw(t), THETA0 + float(np.interp(t, SPIN_T, SPIN_A)), 1.0


# ================================================================= Kamera
KT = np.array([0.0, 1.2, 1.8, 3.4, 4.9, 5.6, 7.0, 8.4, 8.9, 9.6, 10.6, T_CRANE])
KEYS = {"r": [11, 9.5, 9, 10, 9, 12, 10, 12, 14, 30, 170, 160],
        "az": [192, 200, 155, 120, 200, 250, 340, 390, 509, 512, 545, 550],
        "el": [9, 12, 6, 9, 5, -25, 28, 12, 8, 6, 3, 5],
        "fov": [34, 34, 42, 44, 44, 40, 40, 42, 46, 50, 50, 50],
        "ap": [0.15, 0.15, 0.06, 0.04, 0.04, 0.06, 0.06, 0.04, 0.03, 0.0, 0.0, 0.0]}
SHAKES = [(T_SHOT, 1.6), (T_HIT, 3.5), (T_LAND, 0.25)]


def anchor(t):
    p, _, _ = puck_state(t)
    if t < 1.3:
        p = T0.copy()
    w = smooth(9.4, 10.5, t)
    return p * (1 - w) + GA * w


def _f0():
    a = anchor(T_CRANE)
    r = KEYS["r"][-1]
    pos = sph(a, r, KEYS["az"][-1], KEYS["el"][-1])
    d = pos - GA
    rr = float(np.linalg.norm(d))
    return rr, math.degrees(math.asin(d[1] / rr)), math.degrees(math.atan2(d[2], d[0])) % 360


F_R0, F_EL0, F_AZ0 = _f0()


def camera(t):
    t = t % DUR
    if t < T_CRANE:
        k = {n: hermite(t, KT, v) for n, v in KEYS.items()}
        a = anchor(t)
        pos = sph(a, k["r"], k["az"], k["el"])
        return pos, a, np.array([0.0, 1.0, 0.0]), k["fov"], k["ap"], k["r"]
    if t < T_TOP:                                  # Kranfahrt
        x = (t - T_CRANE) / (T_TOP - T_CRANE)
        tgt = GA + (TOP_C - GA) * sio(x)
        r = math.exp(lerp(math.log(F_R0), math.log(TOP_H), smoother(x)))
        el = lerp(F_EL0, 89.9, sio(x) * 0.35 + smoother(x) * 0.65)
        return sph(tgt, r, F_AZ0, el), tgt, blend_up(el), lerp(50.0, 30.0, sio(x)), 0.0, r
    if t < T_DIVE:
        return sph(TOP_C, TOP_H, F_AZ0, 89.9), TOP_C.copy(), blend_up(89.9), 30.0, 0.0, TOP_H
    x = (t - T_DIVE) / (DUR - T_DIVE)              # Sturzflug
    tgt = TOP_C + (T0 - TOP_C) * smooth(0.0, 0.7, x)
    r = math.exp(lerp(math.log(TOP_H), math.log(11.0), smoother(x)))
    el = lerp(89.9, 9.0, smooth(0.25, 1.0, x))
    az_end = 192.0
    while az_end - F_AZ0 > 180:
        az_end -= 360
    while az_end - F_AZ0 < -180:
        az_end += 360
    az = lerp(F_AZ0, az_end, smooth(0.2, 1.0, x))
    ap = 0.15 * smooth(60.0, 11.0, r)
    return sph(tgt, r, az, el), tgt, blend_up(el), lerp(30.0, 34.0, smoother(x)), ap, r


def cam_row(t):
    pos, tgt, up, fov, ap, focus = camera(t)
    tt = t % DUR
    for ts, amp in SHAKES:
        lt = tt - ts
        if 0 <= lt < 0.5:
            e = amp * math.exp(-lt * 9)
            off = np.array([math.sin(lt * 91), math.cos(lt * 77), math.sin(lt * 63 + 1)]) * e * max(1.0, focus / 40)
            pos = pos + off * 0.15
    r, u, f = P3.look_at(pos, tgt, up)
    return P3.cam_row(pos, r, u, f, fov), ap, focus


def render3d(t, fidx):
    cams, lens, pk = np.zeros((KSUB, 13)), np.zeros((KSUB, 2)), np.zeros((KSUB, 7))
    for k in range(KSUB):
        tk = t + ((k + 0.5) / KSUB - 0.5) * SHUTTER
        row, ap, focus = cam_row(tk)
        cams[k], lens[k] = row, (ap, focus)
        pos, th, vis = puck_state(tk)
        pk[k] = (pos[0], pos[1], pos[2], th, vis, 0.0, tk)
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, SPP, fidx + 1, cams, lens, pk, R.logo_tex(), base, puck, cov)
    return P3.tonemap(base), P3.tonemap(puck), cov


# ================================================================= Netz (Einschlag oben)
def net_offset(p, w, t):
    tau = t - (T_HIT + 0.02)
    if tau <= 0:
        return p
    A = 13.0 * (1 - math.exp(-tau / 0.03)) * math.exp(-tau * 4.0) * math.cos(2 * math.pi * 1.7 * tau)
    d2 = np.sum((p - HIT_P - np.array([8.0, 0.0, 0.0])) ** 2, axis=-1)
    q = p.copy()
    q[..., 0] += A * np.exp(-d2 / (2 * 18.0 ** 2)) * np.maximum(w, 0.25)
    return q


R.net_offset = net_offset


# ================================================================= Kufen-Kratzer
def _scratches():
    rng = np.random.default_rng(5)
    out = []
    path = [puck_raw(t) for t in np.arange(1.3, T_HIT, 0.02)]
    for _ in range(1400):
        c = path[rng.integers(len(path))]
        p = np.array([c[0] + rng.normal(0, 60), 0.02, c[2] + rng.normal(0, 60)])
        a = rng.uniform(-0.5, 0.5) + (0 if rng.random() < 0.7 else math.pi / 2)
        L = rng.uniform(6, 40)
        d = np.array([math.cos(a), 0, math.sin(a)]) * L
        bend = np.array([-d[2], 0, d[0]]) * rng.uniform(-0.08, 0.08)
        u = np.linspace(0, 1, 6)[:, None]
        out.append((p + d * u + bend * np.sin(math.pi * u), rng.uniform(0.25, 0.6)))
    return out


SCRATCHES = _scratches()


def draw_scratches(ctx, cam):
    pos = cam[0:3]
    if pos[1] > 300:
        return
    for pl, a in SCRATCHES:
        dist = np.linalg.norm(pl[0] - pos)
        if dist > 260:
            continue
        xy, z = proj(cam, pl)
        if (z < 0.6).any():
            continue
        w = float(np.clip(0.05 * px_per_in(cam, z.mean()), 0.6, 3.0))
        stroke_poly(ctx, xy, (150, 160, 176), a * (1 - dist / 260), w)


# ================================================================= Effekte
def rv(n, seed):
    return np.random.default_rng(seed).random((n, 6))


DEKES = [1.3 + 3.7 * u for u in (1 / 6, 1 / 2, 5 / 6)]


def spray(ctx, cam, t, t0, origin, back, seed, n=70, power=1.0):
    li = t - t0
    if not 0 <= li < 0.7:
        return
    r_ = rv(n, seed)
    side = np.cross(back, [0, 1, 0])
    for k in range(n):
        lt = li - r_[k, 0] * 0.08
        if lt < 0 or lt > 0.55:
            continue
        v = back * (20 + r_[k, 1] * 50) * power + side * (r_[k, 2] - 0.5) * 50 + np.array([0, 15 + r_[k, 3] * 40, 0]) * power
        p = origin + v * lt + np.array([0, -0.5 * 386 * lt * lt, 0])
        if p[1] < 0:
            continue
        xy, z = proj(cam, [p, p - v * 0.012])
        if (z < 0.5).any():
            continue
        stroke_poly(ctx, xy, (140, 160, 188), 0.85 * (1 - lt / 0.55), 2.0 + r_[k, 4] * 2.4)


def ring_on_ice(ctx, cam, c, r, col, alpha, width):
    ring = np.stack([c[0] + r * np.cos(PHI2), np.full_like(PHI2, 0.05), c[2] + r * np.sin(PHI2)], 1)
    xy, z = proj(cam, ring)
    if (z > 1).all():
        stroke_poly(ctx, xy, col, alpha, width)


def fx_scene(ctx, t, cam):
    # Aufprall beim Bully
    li = t - T_LAND
    if 0 <= li < 0.45:
        q = e_out(li / 0.45, 3)
        ring_on_ice(ctx, cam, P0, 1.8 + 3.2 * q, ORANGE, 0.9 * (1 - q), 3.0)
    # Haken: Eisspray entgegen der Bewegung
    for k, td in enumerate(DEKES):
        if 0 <= t - td < 0.7:
            p = puck_raw(td)
            v = puck_raw(td + 0.02) - puck_raw(td - 0.02)
            v[1] = 0
            v /= np.linalg.norm(v) + 1e-9
            spray(ctx, cam, t, td, p + np.array([0, 0.3, 0]), -v, 30 + k, 60, 0.9)
    # Abheben zum Saucer
    if 4.95 <= t < 5.7:
        spray(ctx, cam, t, 4.95, puck_raw(4.95), np.array([-0.6, 0, -0.8]), 41, 50, 0.7)
    # One-Timer: Schwung, Ringe, Spray
    if T_SHOT - 0.14 < t < T_SHOT + 0.7:
        pp, zp = projected(cam, SHOT_A)
        if zp > 0.5:
            lt = t - (T_SHOT - 0.14)
            if lt < 0.3:
                pts = np.array([[pp[0] + 620, pp[1] + 420], [pp[0] + 300, pp[1] + 260], [pp[0] + 60, pp[1] + 40]])
                a_, b_ = c01(lt / 0.14), c01((lt - 0.12) / 0.16)
                seg = []
                for i in range(25):
                    u = lerp(b_, a_, i / 24)
                    seg.append((1 - u) ** 2 * pts[0] + 2 * (1 - u) * u * pts[1] + u * u * pts[2])
                stroke_poly(ctx, np.array(seg), ORANGE, 1 - b_, 18 * (1 - b_ * 0.7))
            li = t - T_SHOT
            if 0 <= li < 0.45:
                q = e_out(li / 0.45, 3)
                for col, rmax, wdt in ((ORANGE, 360, 8), (INK, 230, 3)):
                    ctx.set_source_rgba(col[0] / 255, col[1] / 255, col[2] / 255, (1 - q) * 0.9)
                    ctx.set_line_width(wdt * (1 - q) + 1)
                    ctx.arc(pp[0], pp[1], 30 + rmax * q, 0, 2 * math.pi)
                    ctx.stroke()
        d = HIT_P - SHOT_A
        d[1] = 0
        d /= np.linalg.norm(d)
        spray(ctx, cam, t, T_SHOT, SHOT_A, -d, 52, 90, 1.1)
    # Tor: Torlicht, Ring, Funken
    li = t - T_HIT
    if 0 <= li < 2.2:
        pg, zg = projected(cam, np.array([GOAL_X + 30, 80.0, 0.0]))
        if zg > 1:
            import cairocffi as cairo
            pulse = sum(math.exp(-((li - k * 0.4) / 0.12) ** 2) for k in range(5))
            rr = 300 * (0.7 + 0.3 * pulse)
            g = cairo.RadialGradient(pg[0], pg[1], 0, pg[0], pg[1], rr)
            g.add_color_stop_rgba(0, 1.0, 0.25, 0.12, 0.6 * pulse)
            g.add_color_stop_rgba(1, 1.0, 0.25, 0.12, 0)
            ctx.set_source(g)
            ctx.arc(pg[0], pg[1], rr, 0, 2 * math.pi)
            ctx.fill()
        if li < 0.9:
            q = e_out(li / 0.9, 3)
            ring_on_ice(ctx, cam, np.array([GOAL_X, 0, 0]), 40 + 160 * q, ORANGE, 0.85 * (1 - q), 5.0)
        if li < 0.8:
            r_ = rv(60, 77)
            for k in range(60):
                lt = li - r_[k, 0] * 0.05
                if lt < 0 or lt > 0.7:
                    continue
                v = np.array([-(10 + r_[k, 1] * 40), 20 + r_[k, 2] * 40, (r_[k, 3] - 0.5) * 70])
                p = HIT_P + v * lt + np.array([0, -0.5 * 300 * lt * lt, 0])
                xy, z = proj(cam, [p, p - v * 0.015])
                if (z > 1).all():
                    stroke_poly(ctx, xy, (255, 196, 70), 0.9 * (1 - lt / 0.7), 3.0)


# ---------------- Replay-Linie in der Draufsicht
def _trail():
    ts = np.arange(1.3, T_HIT + 0.001, 0.01)
    pts = np.array([puck_raw(t) for t in ts])
    pts[:, 1] = 0.3
    return np.concatenate([[[P0[0], 0.3, P0[2]]], pts])


TRAIL = _trail()
MARKS = [(0.0, "DROP", 1), (0.37, "DANGLE", -1), (0.63, "SAUCER", -1), (0.82, "ONE-TIMER", 1), (1.0, "GOAL", 1)]


def trail_frac(t):
    return smooth(14.4, 16.8, t)


def annotations(ctx, t, cam):
    if 13.6 < t < 18.3:
        out = 1 - smooth(17.85, 18.25, t)
        fr = trail_frac(t)
        xy, z = proj(cam, TRAIL)
        if fr > 0 and (z > 5).all():
            ctx.push_group()
            pl = partial(xy, fr)
            stroke_poly(ctx, pl, ORANGE, 0.25, 22.0)
            stroke_poly(ctx, pl, ORANGE, 1.0, 6.0)
            head = pl[-1]
            ctx.set_source_rgba(1, 1, 1, 1)
            ctx.arc(head[0], head[1], 7, 0, 2 * math.pi)
            ctx.fill()
            for f_, _, _ in MARKS:
                if fr >= f_ - 0.001:
                    idx = min(len(xy) - 1, int(f_ * (len(xy) - 1)))
                    k = e_out(c01((fr - f_) / 0.06), 2)
                    ctx.set_source_rgba(INK[0] / 255, INK[1] / 255, INK[2] / 255, 1)
                    ctx.arc(xy[idx][0], xy[idx][1], 11 * k, 0, 2 * math.pi)
                    ctx.fill()
                    ctx.set_source_rgba(ORANGE[0] / 255, ORANGE[1] / 255, ORANGE[2] / 255, 1)
                    ctx.arc(xy[idx][0], xy[idx][1], 5 * k, 0, 2 * math.pi)
                    ctx.fill()
            ctx.pop_group_to_source()
            ctx.paint_with_alpha(out)


def mark_labels(L, t, cam):
    if not 13.6 < t < 18.3:
        return
    out = smooth(17.85, 18.25, t)
    fr = trail_frac(t)
    xy, z = proj(cam, TRAIL)
    if not (z > 5).all():
        return
    for f_, txt, side in MARKS:
        if fr >= f_ - 0.001:
            idx = min(len(xy) - 1, int(f_ * (len(xy) - 1)))
            p = xy[idx]
            img = line_img(txt, 30, 800, INK, track=2)
            right = side > 0
            x = p[0] + 24 if right else p[0] - 24
            reveal(L, img, x, p[1], smooth(0, 0.08, fr - f_ + 0.001), out, "l" if right else "r")


# ================================================================= Text
def headline(L, t, a, b, txt, size=104, col=INK, lab=None, y=382):
    ex = smooth(b - 0.25, b, t)
    p = smooth(a, a + 0.3, t)
    if lab:
        reveal(L, line_img(lab, 30, 650, ORANGE, track=6), W / 2, y - 92, smooth(a - 0.05, a + 0.2, t), ex)
    reveal(L, line_img(txt, size, 900, col), W / 2, y, p, ex)


def texts(L, t):
    loop_in = smooth(DUR - 0.55, DUR - 0.2, t) if t > DUR - 1 else 1.0
    if t < 1.5 or t > DUR - 0.6:
        ex = smooth(1.1, 1.35, t) if t < 2 else 0.0
        reveal_halo(L, line_img("WATCH THIS PUCK.", 96, 900, INK), W / 2, 382, loop_in, ex)
    if 1.3 < t < 5.1:
        headline(L, t, 1.4, 4.95, "THE DANGLE", lab="01")
    if 5.0 < t < 8.5:
        headline(L, t, 5.1, 8.4, "THE SAUCER", lab="02")
        reveal(L, line_img("SLOW-MO  ·  4×", 30, 650, GREY, track=4), W / 2, 478, smooth(5.6, 5.9, t), smooth(8.0, 8.3, t))
    if 8.4 < t < 10.8:
        headline(L, t, 8.5, 10.7, "THE ONE-TIMER", size=96, lab="03")
    if 10.6 < t < 13.4:
        headline(L, t, 10.68, 13.3, "TOP SHELF.", size=150, col=ORANGE, lab="04")
    if 13.8 < t < 18.3:
        headline(L, t, 14.0, 18.2, "THE REPLAY", size=96, y=338)
    if 18.3 < t < DUR - 0.5:
        ex = smooth(DUR - 0.95, DUR - 0.65, t)
        reveal(L, line_img("RATE THIS GOAL", 104, 900, INK), W / 2, 382, smooth(18.4, 18.7, t), ex)
        reveal(L, line_img("1 – 10?", 150, 900, ORANGE), W / 2, 520, smooth(18.55, 18.85, t), ex)
        reveal(L, line_img("COMMENT YOUR SCORE", 40, 700, GREY, 3), W / 2, 640, smooth(18.8, 19.1, t), ex)
        if 19.1 < t < DUR - 0.7:
            y = 690 + abs(math.sin((t - 19.1) * 6)) * 14
            ImageDraw.Draw(L).polygon([(W / 2 - 18, y), (W / 2 + 18, y), (W / 2, y + 22)],
                                      fill=ORANGE + (int(255 * (1 - ex)),))


# ================================================================= Bild
def compose(t, fidx):
    base, puck, cov = render3d(t, fidx)
    row, ap, focus = cam_row(t)
    sc, sctx = surface()
    draw_scratches(sctx, row)
    img = over(base, *surf_rgba(sc))
    pa = cov[..., None]
    ppos, _, pvis = puck_state(t)
    puck_inside = ppos[0] > GOAL_X - 0.5 and pvis > 0
    front = None
    if 8.0 < t < 17.5 or ap > 0:
        nb, nf = R.draw_net(row, t, False), R.draw_net(row, t, True)
        _, zg = projected(row, GA)
        if zg > 1:
            fade = 1 - smooth(350, 2600, zg) if row[1] < 400 else 1.0
            sig = float(min(40.0, ap * abs(1 / zg - 1 / focus) * (H / 2) / row[12] * 0.5)) if ap > 0.005 else 0.0
            lays = []
            for s_ in (nb, nf):
                rgb, a = surf_rgba(s_)
                if sig > 0.8:
                    from PIL import ImageFilter
                    pil = Image.fromarray((np.concatenate([rgb, a], -1) * 255).astype(np.uint8), "RGBA")
                    arr = np.asarray(pil.filter(ImageFilter.GaussianBlur(sig))).astype(np.float32) / 255
                    rgb, a = arr[..., :3], arr[..., 3:4]
                lays.append((rgb * fade, a * fade))
            img = over(img, *lays[0])
            front = lays[1]
            if not puck_inside:
                img = over(img, *front)
    img = img * (1 - pa) + puck * pa
    if front is not None and puck_inside:
        img = over(img, *front)
    fs, ctx = surface()
    fx_scene(ctx, t, row)
    img = over(img, *surf_rgba(fs))
    an, actx = surface()
    annotations(actx, t, row)
    img = over(img, *surf_rgba(an))
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    texts(L, t)
    mark_labels(L, t, row)
    wm = R.watermark()
    L.alpha_composite(wm, (W - 50 - wm.width, 206))
    ta = np.asarray(L).astype(np.float32) / 255
    img = img * (1 - ta[..., 3:4]) + ta[..., :3] * ta[..., 3:4]
    img = img * R.VIG
    img += np.random.default_rng(fidx).normal(0, 0.006, img.shape[:2])[..., None]
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


# ================================================================= Sound
SR = 44100


def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(16)
    music, sfx = np.zeros(n), np.zeros(n)

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
        x = tt(0.4)
        f = 48 + 120 * np.exp(-x * 30)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 8) * 2.0) * 0.9 * vol

    def clap():
        x = tt(0.25)
        nz = hp(noise(0.25), 6)
        out = np.zeros(len(x))
        for off, dec in ((0, 70), (0.01, 70), (0.02, 18)):
            st = int(off * SR)
            out[st:] += nz[: len(x) - st] * np.exp(-x[: len(x) - st] * dec)
        return lp(out, 2) * 0.45

    def hat(vol=0.2, open_=False):
        d_ = 0.22 if open_ else 0.05
        return hp(noise(d_), 2) * np.exp(-tt(d_) * (16 if open_ else 110)) * vol

    def bass(freq, dur):
        x = tt(dur)
        return np.tanh(np.sin(2 * np.pi * freq * x) * 2.2) * 0.55 * np.minimum(x / 0.01, 1) * np.clip((dur - x) / 0.05, 0, 1)

    def pad(freqs, dur, vol=0.12):
        x = tt(dur)
        sig = sum(np.sin(2 * np.pi * f * x + np.sin(2 * np.pi * 0.3 * x) * 0.3) for f in freqs) / len(freqs)
        return sig * np.minimum(x / 0.5, 1) * np.clip((dur - x) / 0.5, 0, 1) * vol

    def pluck(freq, dur=0.5, vol=0.2):
        x = tt(dur)
        return (np.sin(2 * np.pi * freq * x) + 0.3 * np.sin(4 * np.pi * freq * x) * np.exp(-x * 12)) * np.exp(-x * 7) * vol

    def whoosh(dur=0.5, vol=1.0, down=False):
        x = tt(dur)
        nz = noise(dur)
        env = np.sin(np.pi * x / dur) ** 2
        lo, hi = lp(nz, 40), lp(nz, 6) - lp(nz, 40)
        mv = 1 - x / dur if down else x / dur
        return (lo * (1 - mv) + hi * mv * 1.3) * env * 1.2 * vol

    def riser(dur, vol=1.0):
        x = tt(dur)
        sw = np.sin(2 * np.pi * np.cumsum(300 + 1800 * (x / dur) ** 2) / SR) * (x / dur) ** 3 * 0.12
        return (hp(noise(dur), 4) * (x / dur) ** 2 * 0.35 + sw) * vol

    def thud(f0=150, vol=0.8):
        x = tt(0.25)
        f = f0 * (1 + 0.8 * np.exp(-x * 60))
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 26) + hp(noise(0.25), 3) * np.exp(-x * 120) * 0.4) * vol

    def scrape(dur=0.4, vol=0.6):
        x = tt(dur)
        return hp(noise(dur), 2) * np.exp(-x * 7) * (0.6 + 0.4 * np.sin(2 * np.pi * 37 * x)) * vol

    def crack(vol=1.0):
        x = tt(0.5)
        body = np.sin(2 * np.pi * np.cumsum(220 * (1 + 2 * np.exp(-x * 80))) / SR) * np.exp(-x * 18)
        return np.tanh((body * 0.8 + hp(noise(0.5), 2) * np.exp(-x * 70) * 1.2) * 1.6) * vol

    def boom(dur=1.6, f0=50, vol=1.0):
        x = tt(dur)
        f = f0 + 90 * np.exp(-x * 12)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 2.6) * 1.8) * vol

    def horn(dur=1.6):
        x = tt(dur)
        sig = sum(2 * ((x * f * (1 + 0.003 * np.sin(2 * np.pi * 4.5 * x))) % 1) - 1 for f in (110.0, 138.6, 164.8))
        return lp(lp(sig, 10), 6) / 3 * np.minimum(x / 0.05, 1) * np.clip((dur - x) / 0.3, 0, 1) * 0.65

    def crowd(dur, vol):
        x = tt(dur)
        return lp(noise(dur), 14) * 3 * (0.8 + 0.2 * np.sin(2 * np.pi * 0.7 * x)) * vol

    def heartbeat(at):
        for k, off in enumerate((0.0, 0.18)):
            put_(sfx, boom(0.35, 45, 0.5 - 0.15 * k), at + off)

    ROOT = [55.0, 55.0, 43.65, 49.0]
    beat = 0.5
    for k in range(int(DUR / beat)):
        tb = k * beat
        full = (1.3 <= tb < 5.0) or (T_SHOT <= tb < T_CRANE + 1.0)
        light = T_CRANE + 1.0 <= tb < DUR - 0.5
        if full:
            put_(music, kick(), tb)
            if k % 2 == 1:
                put_(music, clap(), tb)
            put_(music, hat(0.22, True), tb + 0.25)
            for j in (0.125, 0.375):
                put_(music, hat(0.12), tb + j)
            put_(music, bass(ROOT[(k // 4) % 4], 0.22), tb + 0.25)
        elif light:
            put_(music, hat(0.14), tb)
            put_(music, hat(0.08), tb + 0.25)
            if k % 2 == 0:
                put_(music, kick(0.45), tb)
        elif tb < 1.3:
            put_(music, hat(0.1), tb)
    put_(music, pad([110, 164.8, 220, 261.6], 3.6, 0.13), 5.0)             # Zeitlupe
    put_(music, pad([98, 146.8, 196, 246.9], 4.6, 0.11), T_CRANE)
    put_(music, pad([110, 164.8, 220, 329.6], 4.2, 0.12), T_DIVE)
    for tb, f in ((14.4, 523.3), (15.0, 659.3), (15.6, 784.0), (16.2, 880.0), (19.0, 659.3), (19.5, 784.0), (20.0, 659.3)):
        put_(music, pluck(f, 0.6, 0.16), tb)

    put_(sfx, whoosh(0.3, 0.5, down=True), T_LAND - 0.25)
    put_(sfx, thud(140, 1.0), T_LAND)
    put_(sfx, boom(0.8, 55, 0.5), T_LAND)
    put_(sfx, riser(1.0, 0.6), 0.3)
    for td in DEKES:
        put_(sfx, scrape(0.45, 0.7), td - 0.02)
        put_(sfx, whoosh(0.3, 0.6), td - 0.15)
    put_(sfx, scrape(0.3, 0.6), 4.95)
    put_(sfx, whoosh(0.6, 0.8), 4.9)
    for hb in (5.6, 6.6, 7.6):
        heartbeat(hb)
    put_(sfx, lp(noise(3.0), 30) * np.sin(np.pi * tt(3.0) / 3.0) * 0.5, 5.2)  # gedehnte Luft
    put_(sfx, thud(170, 0.7), 8.42)
    put_(sfx, whoosh(0.5, 1.0), 8.4)
    put_(sfx, riser(0.4, 0.7), 8.5)
    put_(sfx, crack(1.1), T_SHOT)
    put_(sfx, boom(1.4, 46, 0.9), T_SHOT)
    put_(sfx, hp(noise(1.6), 3) * np.exp(-tt(1.6) * 1.5) * 0.06, T_SHOT + 0.05)
    put_(sfx, lp(noise(0.4), 20) * np.exp(-tt(0.4) * 9) * 1.3, T_HIT)
    put_(sfx, boom(1.6, 42, 1.1), T_HIT)
    put_(sfx, horn(1.8), T_HIT + 0.05)
    put_(sfx, crowd(2.6, 0.5) * np.exp(-tt(2.6) * 0.8), T_HIT + 0.05)
    put_(sfx, riser(1.4, 0.6), T_CRANE - 0.3)
    put_(sfx, lp(noise(2.4), 3) * np.sin(np.pi * tt(2.4) / 2.4) * 0.05, 14.4)   # Linie zeichnet
    for _, _, _ in MARKS:
        pass
    for f_ in (0.0, 0.37, 0.63, 0.82, 1.0):
        put_(sfx, thud(1400, 0.10), 14.4 + 2.4 * (f_ ** 1.0) * 1.0)
        put_(sfx, pluck(1046.5, 0.3, 0.12), 14.4 + 2.4 * f_)
    put_(sfx, whoosh(3.0, 0.75, down=True), T_DIVE + 0.1)

    mix = music * 0.7 + sfx * 0.9
    mix /= np.percentile(np.abs(mix), 99.95) + 1e-9
    mix = np.tanh(mix * 0.9)
    mix = mix / np.max(np.abs(mix)) * 0.94
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


def main():
    os.chdir(HERE)
    make_audio("audio_goal.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_goal.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "19",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
           "reel16_goal.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(10.9, 9999)).save("reel16_thumbnail.jpg", quality=92)
    print("fertig: reel16_goal.mp4")


if __name__ == "__main__":
    main()
