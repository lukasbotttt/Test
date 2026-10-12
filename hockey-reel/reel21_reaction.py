"""Reel 21: 0.44 SECONDS – Torwart-Perspektive, wie wenig Zeit ein Goalie hat (12,5 s, weißer Studio-Look).

Rechnung: Blaue Linie -> Torlinie = 64 ft (NHL-Spielfeld), 100 mph = 146,7 ft/s -> 64 / 146,7 = 0,436 s.
Menschliche Reaktionszeit auf einen Sehreiz ≈ 0,25 s (Näherungswert, "≈" im Bild) -> bleiben ≈ 0,19 s zum Bewegen.
  0.0–1.04  POV durch das Maskengitter, Puck an der blauen Linie ("YOU'RE THE GOALIE."), Schuss in Echtzeit
  1.04–2.6  Kamera hinter dem Tor: Einschlag, Torlicht, "THAT WAS / 0.44 SECONDS."
  2.6–8.0   Replay 12x langsamer aus der POV: Timer, Balken REACT / MOVE
  8.0–9.6   Draufsicht: 64 FT, 100 MPH
  9.6–12.5  Puck direkt vor der Maske: "COULD YOU SAVE IT?" YES / NO
Renderer: puck3d.py. Aufruf: python3 reel21_reaction.py -> reel21_reaction.mp4
"""
import math
import os
import subprocess
import time
import wave

import cairocffi as cairo
import numpy as np
from PIL import Image, ImageFilter

import puck3d as P3
import reel15_puck as R15
import reel18_dangle as R18
from reel15_puck import (W, H, FPS, SPP, KSUB, SHUTTER, c01, smooth, sio, e_out, e_in, lerp, sph, line_img, reveal,
                         put, proj, projected, px_per_in, stroke_poly, partial, surface, surf_rgba, over, GOAL_X)
from reel18_dangle import word_img, vignette, bloom

DUR = 12.5
HERE = R15.HERE
WHITE = (250, 250, 252)
INK = R15.INK
RED = (225, 30, 40)
NEON = R15.ORANGE
HALO = (255, 255, 255)
UP = np.array([0.0, 1.0, 0.0])

# ================================================================= Schuss
S = np.array([300.0, 0.5, 70.0])                 # blaue Linie (64 ft vor der Torlinie)
HIT = np.array([1089.0, 30.0, 22.0])             # Netz, Fanghand-Seite oben
V = 1760.0                                       # 100 mph in Zoll/s
T_FLIGHT = float(np.linalg.norm(HIT - S)) / V    # bis zum Netz
T_LINE = (GOAL_X - S[0]) / (HIT[0] - S[0]) * T_FLIGHT   # bis zur Torlinie = 0,436 s
EYE = np.array([1040.0, 40.0, 0.0])
LOOK = np.array([640.0, -8.0, 30.0])
T_SHOT = 0.6                                     # Abschuss in der Echtzeit-Szene
FREEZE_P = EYE + np.array([-21.0, -1.0, 0.0])    # Schlussbild: Puck direkt vor der Maske
REP0, REP1, SLOW = 2.6, 8.0, 12.0                # Replay: 12x langsamer


def puck_at(g):
    """g = Spielzeit seit dem Abschuss (s)."""
    if g <= 0:
        return S.copy()
    if g < T_FLIGHT:
        return S + (HIT - S) * (g / T_FLIGHT)
    li = g - T_FLIGHT
    y = max(0.5, HIT[1] - 0.5 * 386 * max(0.0, li - 0.04) ** 2)
    return np.array([HIT[0] + 3 * smooth(0, 0.12, li), y, HIT[2]])


def spin_at(g):
    return R18.G.THETA0 + (0.0 if g <= 0 else 6.0 * 2 * math.pi * min(g, T_FLIGHT) + 3 * max(0.0, g - T_FLIGHT))


def game_time(t):
    """Spielzeit g für die Videozeit t (je Szene)."""
    if t < 2.6:
        return t - T_SHOT
    if t < REP1:
        return min(T_FLIGHT + 0.02, (t - REP0 - 0.15) / SLOW)
    if t < 9.6:
        return T_FLIGHT + 0.3
    return None


# ================================================================= Kameras
def breathe(t, amp=0.25):
    return np.array([math.sin(t * 1.3) * amp, math.sin(t * 2.1 + 1) * amp * 0.6, math.sin(t * 0.9 + 2) * amp])


def shot(t):
    """-> Kamera (pos, ziel, up, fov, blende), Puck (pos, drehung, sichtbar), Szene"""
    if t < 1.04:                                                       # A: POV Echtzeit
        g = t - T_SHOT
        kick = np.zeros(3)
        if 0 < g < 0.6:
            kick = np.array([0, 0, -1.0]) * 2.5 * math.exp(-max(0.0, g - T_LINE) * 9) * (g > T_LINE)
        pos = EYE + breathe(t) + kick
        return (pos, LOOK, UP, 50, 0.0), (puck_at(g), spin_at(g), 1.0), "pov"
    if t < 2.6:                                                        # B: hinter dem Tor
        u = (t - 1.04) / 1.56
        g = t - T_SHOT
        pos = np.array([GOAL_X + 60.0 + 10 * u, 34.0 - 6 * u, 46.0 - 14 * u])
        tgt = np.array([GOAL_X - 30.0, 22.0, 6.0])
        return (pos, tgt, UP, 48, 0.0), (puck_at(g), spin_at(g), 1.0), "net"
    if t < REP1:                                                       # C: Replay POV
        g = game_time(t)
        u = (t - REP0) / (REP1 - REP0)
        pos = EYE + breathe(t, 0.15) + np.array([0, 0, 0])
        return (pos, LOOK, UP, lerp(50, 46, sio(u)), 0.0), (puck_at(g), spin_at(g), 1.0), "replay"
    if t < 9.6:                                                        # D: Draufsicht
        u = (t - REP1) / 1.6
        c = np.array([lerp(640.0, 690.0, u), 0.0, 20.0])
        h = lerp(1650.0, 1500.0, sio(u))
        return (c + np.array([-0.5, h, 0]), c, np.array([1.0, 0, 0]), 30, 0.0), (puck_at(T_FLIGHT + 0.3), 0.0, 1.0), "top"
    u = (t - 9.6) / (DUR - 9.6)                                         # E: Puck vor der Maske
    p = FREEZE_P
    pos = EYE + breathe(t, 0.12) + np.array([lerp(0.0, 3.0, sio(u)), 0, 0])
    return (pos, p + np.array([-40.0, -5.0, 0.0]), UP, 50, 0.03), (p, R18.G.THETA0 + 0.5 * (t - 9.6), 1.0), "freeze"


SCENE_CUTS = [1.04, 2.6, REP1, 9.6]


def seg_bounds(t):
    cuts = [0.0] + SCENE_CUTS + [DUR]
    for a, b in zip(cuts[:-1], cuts[1:]):
        if a <= t < b:
            return a, b
    return cuts[-2], DUR


def cam_row_at(t):
    (pos, tgt, up, fov, ap), pk, sc = shot(t)
    r, u_, f = P3.look_at(pos, tgt, up)
    return P3.cam_row(pos, r, u_, f, fov), ap, float(np.linalg.norm(tgt - pos)), pk, sc


def render3d(t, fidx, shutter):
    lo, hi = seg_bounds(t)
    cams, lens, pk = np.zeros((KSUB, 13)), np.zeros((KSUB, 2)), np.zeros((KSUB, 7))
    for j in range(KSUB):
        tk = min(max(t + ((j + 0.5) / KSUB - 0.5) * shutter, lo), hi - 1e-4)
        row, ap, focus, (p, th, vis), _ = cam_row_at(tk)
        cams[j], lens[j] = row, (ap, focus)
        pk[j] = (p[0], p[1], p[2], th, vis, 0.0, tk)
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, SPP, fidx + 21, cams, lens, pk, R15.logo_tex(), base, puck, cov)
    return P3.tonemap(base), P3.tonemap(puck), cov


# ================================================================= Netz-Einschlag
def net_offset(p, w, t):
    tau = t - (T_FLIGHT + 0.01)
    if tau <= 0:
        return p
    A = 12.0 * (1 - math.exp(-tau / 0.03)) * math.exp(-tau * 4.0) * math.cos(2 * math.pi * 1.7 * tau)
    d2 = np.sum((p - HIT - np.array([4.0, 0.0, 0.0])) ** 2, axis=-1)
    q = p.copy()
    q[..., 0] += A * np.exp(-d2 / (2 * 16.0 ** 2)) * np.maximum(w, 0.25)
    return q


R15.net_offset = net_offset


# ================================================================= Overlays
def _rink_lines():
    """Spielfeldmarkierungen als 3D-Polylinien (Breite in Zoll, Farbe)."""
    out = []
    zs = np.linspace(-500, 500, 120)
    for x, col, wd in ((300.0, (40, 110, 210), 12), (0.0, (205, 35, 45), 12), (-300.0, (40, 110, 210), 12)):
        out.append((np.stack([np.full_like(zs, x), np.full_like(zs, 0.05), zs], 1), col, wd))
    ph = np.linspace(0, 2 * math.pi, 90)
    for cx, cz, r, col in ((828, 264, 180, (205, 35, 45)), (828, -264, 180, (205, 35, 45)), (0, 0, 180, (40, 110, 210)),
                           (-828, 264, 180, (205, 35, 45)), (-828, -264, 180, (205, 35, 45))):
        out.append((np.stack([cx + r * np.cos(ph), np.full_like(ph, 0.05), cz + r * np.sin(ph)], 1), col, 2.5))
    for cx, cz in ((240, 264), (240, -264), (-240, 264), (-240, -264), (828, 264), (828, -264)):
        out.append((np.stack([cx + 12 * np.cos(ph), np.full_like(ph, 0.05), cz + 12 * np.sin(ph)], 1), (205, 35, 45), 12))
    rng = np.random.default_rng(21)
    for _ in range(900):                                             # Kufenspuren
        c = np.array([rng.uniform(250, 1050), 0.03, rng.normal(0, 110)])
        a = rng.uniform(-0.6, 0.6) + (0 if rng.random() < 0.7 else math.pi / 2)
        d = np.array([math.cos(a), 0, math.sin(a)]) * rng.uniform(10, 60)
        u = np.linspace(0, 1, 6)[:, None]
        bend = np.array([-d[2], 0, d[0]]) * rng.uniform(-0.08, 0.08)
        out.append((c + d * u + bend * np.sin(math.pi * u), (150, 160, 176), -rng.uniform(0.3, 0.6)))
    return out


RINK = _rink_lines()


def rink_overlay(ctx, cam):
    pos = cam[0:3]
    for pts, col, wd in RINK:
        xy, z = proj(cam, pts)
        ok = z > 4
        if ok.sum() < 2:
            continue
        if wd < 0:                                                    # Kratzer: dünn, mit Entfernung ausblenden
            dist = float(np.linalg.norm(pts[0] - pos))
            if dist > 400 or not ok.all():
                continue
            stroke_poly(ctx, xy, col, -wd * (1 - dist / 400), float(np.clip(0.06 * px_per_in(cam, z.mean()), 0.6, 2.5)))
            continue
        segs, cur = [], []
        for p_, k in zip(xy, ok):
            if k:
                cur.append(p_)
            elif len(cur) > 1:
                segs.append(cur)
                cur = []
            else:
                cur = []
        if len(cur) > 1:
            segs.append(cur)
        for sg in segs:
            sg = np.array(sg)
            zz = float(np.median(z[ok]))
            stroke_poly(ctx, sg, col, 0.9, float(np.clip(wd * px_per_in(cam, zz) * 0.35, 1.0, 40)))


def mask_cage():
    """Unscharfes Gitter der Goalie-Maske + dunkler Maskenrand (POV)."""
    s, c = surface()
    c.set_source_rgba(0.05, 0.05, 0.06, 1)
    for x in (0.27, 0.73):
        c.rectangle(W * x - 26, H * 0.75, 52, H * 0.3)
    c.fill()
    for y, a in ((0.80, 1.0), (0.93, 1.0)):
        c.rectangle(-50, H * y - 24, W + 100, 48)
    c.fill()
    c.set_source_rgba(0.05, 0.05, 0.06, 1)
    c.rectangle(W * 0.5 - 22, H * 0.80, 44, H * 0.3)
    c.fill()
    img = Image.frombuffer("RGBA", (W, H), bytes(s.get_data()), "raw", "BGRa", 0, 1).copy()
    img = img.filter(ImageFilter.GaussianBlur(16))
    edge = Image.new("L", (W, H), 0)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H * 0.42) / (H * 0.62)) ** 2)
    ea = (np.clip((r - 0.82) / 0.25, 0, 1) * 235).astype(np.uint8)
    rim = Image.new("RGBA", (W, H), (6, 6, 8, 0))
    rim.putalpha(Image.fromarray(ea).filter(ImageFilter.GaussianBlur(30)))
    img.alpha_composite(rim)
    hl = np.zeros((H, W, 4), np.uint8)                              # schwacher Glanz auf den Stäben
    hl[..., :3] = 120
    return img, Image.fromarray(hl)


_CAGE = None


def cage():
    global _CAGE
    if _CAGE is None:
        _CAGE = mask_cage()[0]
    return _CAGE


def reticle(ctx, cam, p, a, t):
    xy, z = projected(cam, p)
    if z <= 0 or a <= 0:
        return
    r = 46 + 6 * math.sin(t * 8)
    ctx.set_source_rgba(1, 0.47, 0.12, a)
    ctx.set_line_width(4)
    for k in range(4):
        a0 = k * math.pi / 2 + 0.3
        ctx.arc(xy[0], xy[1], r, a0, a0 + 0.95)
        ctx.stroke()


def trail(ctx, cam, g, g_span=0.06, wmul=1.0):
    if g <= 0.005:
        return
    gs = np.linspace(max(0.0, g - g_span), min(g, T_FLIGHT), 22)
    pts = np.array([puck_at(x) for x in gs])
    xy, z = proj(cam, pts)
    if (z < 2).any():
        return
    w = float(np.clip(1.2 * px_per_in(cam, z[-1]), 3, 70)) * wmul
    stroke_poly(ctx, xy, NEON, 0.18, w * 2.4)
    stroke_poly(ctx, xy, NEON, 0.55, w)
    stroke_poly(ctx, xy, (255, 225, 180), 0.9, max(2.0, w * 0.28))


def topview(ctx, cam, t):
    u = c01((t - REP1 - 0.1) / 0.9)
    pts = np.array([puck_at(x) for x in np.linspace(0, T_FLIGHT, 60)])
    pts[:, 1] = 0.3
    xy, z = proj(cam, pts)
    pl = partial(xy, u)
    stroke_poly(ctx, pl, NEON, 0.18, 30)
    stroke_poly(ctx, pl, NEON, 0.6, 12)
    stroke_poly(ctx, pl, (255, 230, 190), 1.0, 4)
    # Maßlinie 64 ft (blaue Linie -> Torlinie), seitlich versetzt
    a = np.array([300.0, 0.3, -150.0])
    b = np.array([GOAL_X, 0.3, -150.0])
    q = e_out(c01((t - REP1 - 0.3) / 0.6), 3)
    (pa, pb), _ = proj(cam, [a, b])
    c_ = (pa + pb) / 2
    stroke_poly(ctx, np.array([c_ + (pa - c_) * q, c_ + (pb - c_) * q]), INK, 0.95, 4)
    if q > 0.95:
        for p in (pa, pb):
            d = (pb - pa) / (np.linalg.norm(pb - pa) + 1e-6)
            n = np.array([-d[1], d[0]])
            stroke_poly(ctx, np.array([p - n * 18, p + n * 18]), INK, 0.95, 4)


def topview_labels(L, cam, t):
    a = np.array([684.0, 0.3, -150.0])
    pa, _ = projected(cam, a)
    reveal(L, line_img("64 FT", 64, 900, INK, track=4), pa[0] + 80, pa[1], smooth(REP1 + 0.7, REP1 + 0.9, t),
           smooth(9.45, 9.6, t))
    m = puck_at(T_FLIGHT * 0.5)
    pm, _ = projected(cam, np.array([m[0], 0.3, m[2]]))
    reveal(L, line_img("100 MPH", 56, 900, NEON, track=4), min(pm[0] + 150, W - 150), pm[1], smooth(REP1 + 0.9, REP1 + 1.1, t),
           smooth(9.45, 9.6, t))


# ---------------- Timer + Balken (Replay)
REACT = 0.25


def timer_ui(L, ctxs, t):
    g = max(0.0, min(T_LINE, game_time(t)))
    a = smooth(REP0 + 0.05, REP0 + 0.3, t) * (1 - smooth(REP1 - 0.15, REP1, t))
    if a <= 0:
        return
    big = line_img(f"{g:0.3f}", 150, 300, INK, cache=False)
    s_ = line_img("s", 60, 400, R15.GREY, cache=False)
    reveal(L, big, W / 2 - 20, 430, a)
    reveal(L, s_, W / 2 + big.width / 2 + 6, 460, a)
    reveal(L, line_img("REPLAY · 12× SLOWER", 30, 700, R15.GREY, track=8), W / 2, 300, a)
    # Balken
    x0, x1, y = 120, W - 120, 1260
    xr = x0 + (x1 - x0) * REACT / T_LINE
    ctx = ctxs
    ctx.set_source_rgba(0.06, 0.07, 0.09, 0.15 * a)
    ctx.rectangle(x0, y - 9, x1 - x0, 18)
    ctx.fill()
    fill = x0 + (x1 - x0) * g / T_LINE
    ctx.set_source_rgba(1, 0.47, 0.12, a)
    ctx.rectangle(x0, y - 9, min(fill, xr) - x0, 18)
    ctx.fill()
    if fill > xr:
        ctx.set_source_rgba(1, 0.16, 0.2, a)
        ctx.rectangle(xr, y - 9, fill - xr, 18)
        ctx.fill()
    ctx.set_source_rgba(0.06, 0.07, 0.09, 0.9 * a)
    ctx.rectangle(xr - 2, y - 26, 4, 52)
    ctx.fill()
    reveal(L, line_img("REACT ≈ 0.25 s", 34, 750, NEON, track=2), (x0 + xr) / 2, y - 52, a)
    reveal(L, line_img("MOVE 0.19 s", 34, 750, RED, track=2), (xr + x1) / 2, y - 52, a)


def replay_words(L, t):
    g = game_time(t)
    if g is None:
        return
    items = [(0.02, 0.22, "SHOT FROM THE", "BLUE LINE.", INK), (0.25, 0.33, "YOU JUST", "SAW IT.", INK),
             (0.33, 0.43, "NOW", "MOVE.", NEON), (T_LINE, 9.0, "GOAL.", None, RED)]
    for g0, g1, l1, l2, col in items:
        if g0 <= g < g1:
            t0 = REP0 + 0.15 + g0 * SLOW
            lt = t - t0
            sc = lerp(1.5, 1.0, e_out(lt / 0.12, 3))
            for txt, cy, size in ((l1, 640, 110 if l2 else 200), (l2, 760, 150)):
                if not txt:
                    continue
                im = word_img(txt, size, col if txt == l2 or not l2 else INK, HALO)
                im = im.resize((int(im.width * sc), int(im.height * sc)), Image.BILINEAR)
                put(L, im, W / 2 - im.width / 2, cy - im.height / 2)


def words(L, t, cam):
    if t < 1.04:
        a = 1.0 if t < 0.55 else 1 - smooth(0.55, 0.62, t)
        if a > 0:
            for txt, cy, size in (("YOU'RE", 400, 130), ("THE GOALIE.", 540, 150)):
                im = word_img(txt, size, INK, HALO).copy()
                im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
                put(L, im, W / 2 - im.width / 2, cy - im.height / 2)
            reveal(L, line_img("WATCH THE PUCK", 36, 750, NEON, track=10), W / 2, 660, 1.0, smooth(0.55, 0.62, t))
    if 1.2 <= t < 2.6:
        for txt, cy, t0, size, col in (("THAT WAS", 560, 1.25, 120, WHITE), ("0.44", 760, 1.5, 300, WHITE),
                                       ("SECONDS.", 940, 1.62, 130, WHITE)):  # auf Torlicht-Rot: weiß
            if t >= t0:
                lt = t - t0
                sc = lerp(1.6, 1.0, e_out(lt / 0.12, 3))
                im = word_img(txt, size, col, RED)
                im = im.resize((int(im.width * sc), int(im.height * sc)), Image.BILINEAR)
                a = c01(lt / 0.05) * (1 - smooth(2.5, 2.6, t))
                im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
                put(L, im, W / 2 - im.width / 2, cy - im.height / 2)
    if t >= 9.6:
        lt = t - 9.6
        for txt, cy, t0, size, col, gl in (("COULD YOU", 290, 0.1, 130, INK, HALO), ("SAVE IT?", 425, 0.25, 170, INK, HALO),
                                           ("YES", 1170, 0.7, 160, (30, 150, 70), HALO), ("NO", 1170, 0.85, 160, RED, HALO)):
            if lt >= t0:
                l2 = lt - t0
                sc = lerp(1.6, 1.0, e_out(l2 / 0.12, 3))
                im = word_img(txt, size, col, gl)
                im = im.resize((int(im.width * sc), int(im.height * sc)), Image.BILINEAR)
                im.putalpha(im.getchannel("A").point(lambda v: int(v * c01(l2 / 0.05))))
                cx = W / 2 if txt not in ("YES", "NO") else (W * 0.3 if txt == "YES" else W * 0.7)
                put(L, im, cx - im.width / 2, cy - im.height / 2)
        if lt > 0.95:
            reveal(L, line_img("/", 130, 300, INK), W / 2, 1170, c01((lt - 0.95) / 0.15))
            reveal(L, line_img("COMMENT YES OR NO", 38, 800, NEON, track=8), W / 2, 1300,
                   c01((lt - 1.1) / 0.25))


def watermark(L, t):
    reveal(L, line_img("@bladesandpucks", 28, 600, (190, 192, 200), track=2), W / 2, 1540, 1.0)


# ================================================================= Bild
def compose(t, fidx):
    (pos, tgt, up, fov, ap), (p, th, vis), sc = shot(t)
    shutter = SHUTTER * (0.35 if sc == "replay" else 1.0)
    base, puck, cov = render3d(t, fidx, shutter)
    row, _, _, _, _ = cam_row_at(t)
    g = t - T_SHOT if sc in ("pov", "net") else (game_time(t) if sc == "replay" else T_FLIGHT)
    tr, tctx = surface()
    if sc in ("pov", "replay", "freeze"):
        rink_overlay(tctx, row)
    if sc in ("pov", "replay") and g is not None and 0 < g < T_FLIGHT:
        trail(tctx, row, g, 0.05 if sc == "pov" else 0.03)
    if sc == "freeze":
        d = (S - FREEZE_P) / np.linalg.norm(S - FREEZE_P)
        pts = np.array([FREEZE_P + d * k for k in np.linspace(90, 1.5, 24)])
        xy, z = proj(row, pts)
        if (z > 1).all():
            stroke_poly(tctx, xy, NEON, 0.18, 70)
            stroke_poly(tctx, xy, NEON, 0.55, 26)
            stroke_poly(tctx, xy, (255, 225, 180), 0.9, 7)
    img = over(base, *surf_rgba(tr))
    pa = cov[..., None]
    if sc in ("net", "top"):
        nb, nf = R15.draw_net(row, g, False), R15.draw_net(row, g, True)
        b_, f_ = surf_rgba(nb), surf_rgba(nf)
        if sc == "net":
            img = img * (1 - pa) + puck * pa
            img = over(img, *b_)
            img = over(img, *f_)
        else:
            img = over(img, *b_)
            img = over(img, *f_)
            img = img * (1 - pa) + puck * pa
    else:
        img = img * (1 - pa) + puck * pa
    fs, fctx = surface()
    if sc == "pov":
        reticle(fctx, row, p, 1 - smooth(T_SHOT - 0.02, T_SHOT + 0.06, t), t)
    if sc == "top":
        topview(fctx, row, t)
    if sc == "replay":
        _, zp_ = projected(row, p)
        size_px = px_per_in(row, zp_) * 3 if zp_ > 0 else 999
        reticle(fctx, row, p, smooth(REP0, REP0 + 0.3, t) * (1 - c01((size_px - 30) / 30)), t)
    img = over(img, *surf_rgba(fs))
    if sc == "net" and g >= T_FLIGHT:                                       # Torlicht
        li = g - T_FLIGHT
        strobe = 0.5 + 0.5 * math.cos(li * 2 * math.pi * 3.2)
        a = 0.34 * strobe * math.exp(-li * 0.9)
        img = img * (1 - a) + np.array([1.0, 0.08, 0.1], np.float32) * a
    if sc == "net":
        img = bloom(img * 0.9)
    lc = min([t - c for c in SCENE_CUTS if t >= c] + [t + 0.5])
    if lc < 0.08:
        img = img + (1 - lc / 0.08) * 0.3
    hit_flash = sc == "pov" and 0 <= t - (T_SHOT + T_LINE) < 0.1
    if hit_flash:
        img = img + 0.25 * (1 - (t - T_SHOT - T_LINE) / 0.1)
    img = np.clip(img, 0, 1)
    pil = Image.fromarray((img * 255).astype(np.uint8)).convert("RGBA")
    if sc in ("pov", "replay", "freeze"):
        pil.alpha_composite(cage())
    if sc == "replay":
        s2, c2 = surface()
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    words(L, t, row)
    if sc == "replay":
        timer_ui(L, c2, t)
        replay_words(L, t)
        pil.alpha_composite(Image.frombuffer("RGBA", (W, H), bytes(s2.get_data()), "raw", "BGRa", 0, 1).copy())
    if sc == "top":
        topview_labels(L, row, t)
    pil.alpha_composite(L)
    arr = np.asarray(pil.convert("RGB")).astype(np.float32) / 255
    zp = 1 + 0.05 * math.exp(-lc * 14)
    if zp > 1.002:
        im2 = Image.fromarray((arr * 255).astype(np.uint8))
        w2, h2 = W / zp, H / zp
        im2 = im2.transform((W, H), Image.EXTENT, ((W - w2) / 2, (H - h2) / 2, (W + w2) / 2, (H + h2) / 2), Image.BILINEAR)
        arr = np.asarray(im2).astype(np.float32) / 255
    arr = arr * vignette()
    arr += np.random.default_rng(fidx).normal(0, 0.012, arr.shape[:2])[..., None]
    return (np.clip(arr, 0, 1) * 255).astype(np.uint8)


# ================================================================= Sound
SR = 44100


def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(21)
    L_, R_ = np.zeros(n), np.zeros(n)

    def tt(sec):
        return np.arange(int(sec * SR)) / SR

    def put_(sig, at, vol=1.0, pan=0.0):
        st = int(round(at * SR))
        if st >= n:
            return
        if st < 0:
            sig, st = sig[-st:], 0
        e = min(n, st + len(sig))
        gl, gr = math.cos((pan + 1) * math.pi / 4) * 1.41, math.sin((pan + 1) * math.pi / 4) * 1.41
        L_[st:e] += sig[: e - st] * vol * gl
        R_[st:e] += sig[: e - st] * vol * gr

    def lp(x, k):
        c = np.cumsum(np.concatenate([np.zeros(k), x]))
        return (c[k:] - c[:-k]) / k

    def hp(x, k):
        return x - lp(x, k)

    def noise(sec):
        return rng.standard_normal(int(sec * SR))

    def thump(vol=1.0, f0=48):
        x = tt(0.35)
        f = f0 + 60 * np.exp(-x * 30)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 12) * 2.5) * vol

    def heartbeat(at, vol=1.0):
        put_(thump(vol), at)
        put_(thump(vol * 0.6, 44), at + 0.2)

    def crack(vol=1.0):
        x = tt(0.4)
        body = np.sin(2 * np.pi * np.cumsum(260 * (1 + 2 * np.exp(-x * 80))) / SR) * np.exp(-x * 18)
        return np.tanh((body + hp(noise(0.4), 2) * np.exp(-x * 60) * 1.4) * 1.8) * vol

    def whoosh(dur=0.35, vol=1.0, slow=1.0):
        x = tt(dur)
        nz = noise(dur)
        env = np.exp(-((x / dur - 0.7) ** 2) * 14)
        k = (36 * slow - 30 * slow * (x / dur) ** 2)
        out = sum(lp(nz, kk) * np.exp(-((k - kk) ** 2) / 60) for kk in (36, 18, 8, 4))
        return out * env * 1.8 * vol

    def boom(dur=1.6, f0=38, vol=1.0):
        x = tt(dur)
        f = f0 + 120 * np.exp(-x * 14)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 2.4) * 2.4) * vol

    def horn(dur=1.6):
        x = tt(dur)
        sig = sum(2 * ((x * f * (1 + 0.003 * np.sin(2 * np.pi * 4.5 * x))) % 1) - 1 for f in (110.0, 138.6, 164.8))
        return lp(lp(sig, 10), 6) / 3 * np.minimum(x / 0.05, 1) * np.clip((dur - x) / 0.3, 0, 1) * 0.7

    def crowd(dur, vol):
        x = tt(dur)
        return lp(noise(dur), 14) * 3 * (0.8 + 0.2 * np.sin(2 * np.pi * 0.7 * x)) * vol

    def drone(dur, f, vol):
        x = tt(dur)
        sig = sum(np.sin(2 * np.pi * f * k * x + k) / k for k in (1, 2, 3)) + lp(noise(dur), 200) * 2
        return sig * np.minimum(x / 0.5, 1) * np.clip((dur - x) / 0.4, 0, 1) * vol

    def tick(vol=0.25, f=2400):
        x = tt(0.04)
        return np.sin(2 * np.pi * f * x) * np.exp(-x * 120) * vol

    def riser(dur, vol=1.0):
        x = tt(dur)
        return (hp(noise(dur), 3) * (x / dur) ** 2.5 * 0.35 + np.sin(2 * np.pi * np.cumsum(200 + 2200 * (x / dur) ** 2) / SR) * (x / dur) ** 3 * 0.15) * vol

    # A: Spannung, Abschuss, Vorbeiflug
    put_(drone(1.2, 55, 0.18), 0.0)
    heartbeat(0.0, 0.9)
    put_(crowd(1.0, 0.12), 0.0)
    put_(crack(1.2), T_SHOT)
    put_(whoosh(0.32, 1.3), T_SHOT + T_LINE - 0.24, pan=-0.7)
    # B: Netz, Torlicht
    put_(lp(noise(0.4), 18) * np.exp(-tt(0.4) * 8) * 1.4, T_SHOT + T_FLIGHT)
    put_(boom(1.8, 36, 1.2), 1.04)
    put_(horn(1.5), 1.08)
    put_(crowd(1.6, 0.6) * np.exp(-tt(1.6) * 0.8), 1.08)
    for t0 in (1.25, 1.5, 1.62):
        put_(thump(0.8, 60), t0)
    # C: Replay – gedehnte Klänge, Herzschlag, Ticks im Spieltakt (alle 0,02 s Spielzeit)
    put_(drone(REP1 - REP0, 41, 0.28), REP0)
    for hb in np.arange(REP0 + 0.2, REP1 - 0.3, 0.9):
        heartbeat(hb, 0.8)
    for k in range(int(T_LINE / 0.02) + 1):
        put_(tick(0.18 if k % 5 else 0.3, 2400 if k % 5 else 3000), REP0 + 0.15 + k * 0.02 * SLOW)
    put_(boom(1.2, 50, 0.6), REP0 + 0.15 + REACT * SLOW)
    put_(riser(1.2, 0.6), REP0 + 0.15 + T_LINE * SLOW - 1.2)
    put_(whoosh(1.2, 1.2, 1.0), REP0 + 0.15 + T_LINE * SLOW - 0.9, pan=-0.6)
    put_(boom(1.8, 34, 1.1), REP0 + 0.15 + T_LINE * SLOW)
    # D/E
    put_(whoosh(0.3, 0.7), REP1 - 0.1)
    put_(boom(1.4, 46, 0.8), 9.6)
    for k, t0 in enumerate((9.7, 9.85, 10.3, 10.45)):
        put_(thump(0.7, 58 + 8 * k), t0)
    put_(drone(DUR - 9.6, 55, 0.15), 9.6)
    for hb in (10.6, 11.5):
        heartbeat(hb, 0.6)
    mix = np.stack([L_, R_], 1)
    mix /= np.percentile(np.abs(mix), 99.9) + 1e-9
    mix = np.tanh(mix * 1.1)
    mix *= np.clip((DUR - np.arange(n) / SR) / 0.4, 0, 1)[:, None]
    mix = mix / np.max(np.abs(mix)) * 0.95
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


def main():
    os.chdir(HERE)
    make_audio("audio_reaction.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_reaction.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "22",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
           "reel21_reaction.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(1.7, 9999)).save("reel21_thumbnail.jpg", quality=92)
    print("fertig: reel21_reaction.mp4")


if __name__ == "__main__":
    main()
