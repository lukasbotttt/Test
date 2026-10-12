"""Reel 22: WHY IS THIS BEHIND EVERY NHL NET? – 3D-Erklärvideo zur Trapez-Regel (13,5 s, weißer Studio-Look).

Fakten (NHL-Regel, seit 2005–06): Hinter der Torlinie darf der Goalie den Puck nur im Trapez spielen; außerhalb
= 2 Minuten (Delay of Game). Spitzname "Brodeur Rule" (Martin Brodeurs Puckspiel gilt als Auslöser).
Trapez: an der Torlinie 8 ft neben jedem Pfosten (seit 2014), an der Bande 28 ft breit.
  0.0–1.6   Tiefe 3D-Kamera hinter dem Tor, Trapez glüht: "WHY IS THIS / BEHIND EVERY NHL NET?"
  1.6–3.4   Kranfahrt in die Draufsicht: "THE TRAPEZOID" / "NHL RULE SINCE 2005–06"
  3.4–6.6   Szenario A: Puck läuft in die Ecke, Goalie spielt ihn außerhalb -> Pfiff, "2 MIN"
  6.6–6.95  Zurückspulen
  6.95–9.6  Szenario B: Puck hinter dem Tor im Trapez -> "LEGAL", Pass
  9.6–11.3  3D: "NICKNAMED / THE BRODEUR RULE"
  11.3–13.5 "SHOULD THE NHL REMOVE IT?" YES / NO
Renderer: puck3d.py. Aufruf: python3 reel22_trapezoid.py -> reel22_trapezoid.mp4
"""
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
from reel15_puck import (W, H, FPS, SPP, KSUB, SHUTTER, c01, smooth, sio, e_out, e_in, e_back, lerp, line_img,
                         reveal, put, proj, projected, px_per_in, stroke_poly, partial, surface, surf_rgba, over, GOAL_X)
from reel18_dangle import word_img, vignette

DUR = 13.5
HERE = R15.HERE
INK = R15.INK
ORANGE = R15.ORANGE
RED = (225, 30, 40)
GREEN = (30, 160, 80)
HALO = (255, 255, 255)
UP = np.array([0.0, 1.0, 0.0])
SIDE = -1.0                                         # Ecke für die Szenarien (z-Vorzeichen)

# ================================================================= Geometrie (Zoll)
END_X, HALF_Z, CORNER = 1200.0, 510.0, 336.0
CX, CZ = END_X - CORNER, HALF_Z - CORNER            # Mittelpunkt der Eckrundung (864, 174)
TRAP = [(GOAL_X, -132.0), (END_X, -168.0), (END_X, 168.0), (GOAL_X, 132.0)]


def board_z(x):
    """|z| der Bande bei x (Ende der Eisfläche, inkl. Rundung)."""
    if x <= CX:
        return HALF_Z
    dx = min(x - CX, CORNER)
    return CZ + math.sqrt(max(CORNER ** 2 - dx ** 2, 0.0))


def poly3(pts2, y=0.06):
    return np.array([[x, y, z] for x, z in pts2])


def trap_poly():
    return poly3(TRAP + [TRAP[0]])


def outside_zone(side):
    """Fläche hinter der Torlinie außerhalb des Trapezes (eine Seite)."""
    pts = [(GOAL_X, side * 132.0)]
    for x in np.linspace(GOAL_X, END_X, 24):
        pts.append((x, side * board_z(x)))
    pts += [(END_X, side * 168.0), (GOAL_X, side * 132.0)]
    return poly3(pts)


def rim_path(stop_s, side):
    """Puck an der Bande entlang: Seitenbande -> Eckrundung -> Stirnbande. s = Bogenlänge (Zoll)."""
    r = CORNER - 9
    pts = []
    for x in np.linspace(700, CX, 20):
        pts.append((x, side * (CZ + r)))
    for a in np.linspace(math.pi / 2, 0, 40):
        pts.append((CX + r * math.cos(a), side * (CZ + r * math.sin(a))))
    for zz in np.linspace(CZ, -60, 30):
        pts.append((CX + r, side * zz))
    pts = np.array(pts)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    return pts, cum


RIM_PTS, RIM_CUM = rim_path(0, SIDE)


def rim_at(s):
    x = np.interp(s, RIM_CUM, RIM_PTS[:, 0])
    z = np.interp(s, RIM_CUM, RIM_PTS[:, 1])
    return np.array([x, 0.5, z])


def corner_s(angle_deg):
    """Bogenlänge bis zum Winkel in der Eckrundung (90° = Anfang, 0° = Stirnbande)."""
    r = CORNER - 9
    return float(np.linalg.norm(np.diff(RIM_PTS[:20], axis=0), axis=1).sum()) + r * math.radians(90 - angle_deg)


S_A = corner_s(38)                                  # Ecke, außerhalb des Trapezes
S_B = RIM_CUM[-1] - 40                              # an der Stirnbande hinter dem Tor, im Trapez
T_A0, T_A1 = 3.55, 4.75                             # Puck läuft (A)
T_G0, T_G1 = 4.15, 5.05                             # Goalie fährt raus (A)
T_WHISTLE = 5.08
T_REW0, T_REW1 = 6.6, 6.95
T_B0, T_B1 = 7.0, 8.3
T_GB0, T_GB1 = 7.55, 8.45
T_LEGAL = 8.5
T_PASS0, T_PASS1 = 8.95, 9.5
GOALIE_HOME = np.array([GOAL_X - 22, 0.0, 0.0])


def decel(u):
    return 1 - (1 - c01(u)) ** 2.2


def puck_scn(t):
    """Puckposition in den Szenarien (Draufsicht)."""
    if t < T_REW0:
        return rim_at(S_A * decel((t - T_A0) / (T_A1 - T_A0))) if t >= T_A0 else rim_at(0)
    if t < T_REW1:                                   # zurückspulen
        u = (t - T_REW0) / (T_REW1 - T_REW0)
        return rim_at(S_A * (1 - e_in(u, 2)))
    if t < T_PASS0:
        return rim_at(S_B * decel((t - T_B0) / (T_B1 - T_B0))) if t >= T_B0 else rim_at(0)
    u = e_out((t - T_PASS0) / (T_PASS1 - T_PASS0), 2)
    a = rim_at(S_B)
    b = np.array([860.0, 0.5, SIDE * 380.0])
    return a + (b - a) * u


def goalie_scn(t):
    tgt_a = rim_at(S_A) + np.array([-24.0, 0, -SIDE * 22.0])
    if t < T_REW0:
        u = sio((t - T_G0) / (T_G1 - T_G0))
        return GOALIE_HOME + (tgt_a - GOALIE_HOME) * u
    if t < T_REW1:
        u = (t - T_REW0) / (T_REW1 - T_REW0)
        return tgt_a + (GOALIE_HOME - tgt_a) * e_in(u, 2)
    tgt_b = rim_at(S_B) + np.array([-26.0, 0, -SIDE * 6.0])
    via = np.array([GOAL_X + 30.0, 0.0, SIDE * 70.0])
    u = sio((t - T_GB0) / (T_GB1 - T_GB0))
    if u < 0.5:                                       # um den Pfosten herum
        return GOALIE_HOME + (via - GOALIE_HOME) * (u * 2)
    return via + (tgt_b - via) * ((u - 0.5) * 2)


# ================================================================= Kamera
TOP_T = np.array([1055.0, 0.0, SIDE * 120.0])
TOP_H = 2000.0


def hook_cam(t, side=1.0, mirror=False):
    u = c01(t / 1.6)
    zs = 230.0 if not mirror else -230.0
    pos = np.array([lerp(860.0, 885.0, u), lerp(165.0, 150.0, u), lerp(zs, zs * 0.8, u)])
    tgt = np.array([1130.0, 0.0, -zs * 0.05])
    return pos, tgt, UP, 46.0


def top_up():
    return np.array([0.0, 0.0, 1.0])


def cam(t):
    if t < 1.6:
        return hook_cam(t)
    if t < 3.4:                                       # Kranfahrt mit Drehung
        s = (t - 1.6) / 1.8
        p0, t0, _, f0 = hook_cam(1.6)
        p1 = TOP_T + np.array([0.01, TOP_H, 0.0])
        r0 = np.linalg.norm(p0 - t0)
        r = math.exp(lerp(math.log(r0), math.log(TOP_H), sio(s)))
        tgt = t0 + (TOP_T - t0) * sio(s)
        d0 = (p0 - t0) / r0
        d1 = np.array([0.0, 1.0, 0.0])
        d = d0 + (d1 - d0) * sio(s)
        d /= np.linalg.norm(d)
        pos = tgt + d * r
        phi = math.pi / 2 * smooth(0.35, 1.0, s)
        tilt_up = np.array([1.0, 0.0, 0.0])
        up = UP * (1 - smooth(0.3, 0.8, s)) + (tilt_up * math.cos(phi) + top_up() * math.sin(phi)) * smooth(0.3, 0.8, s)
        return pos, tgt, up / np.linalg.norm(up), lerp(f0, 30.0, sio(s))
    if t < 9.6:
        return TOP_T + np.array([0.01, TOP_H, 0.0]), TOP_T, top_up(), 30.0
    u = (t - 9.6) / (DUR - 9.6)
    pos = np.array([lerp(870.0, 900.0, u), lerp(160.0, 145.0, u), lerp(-250.0, -190.0, u)])
    return pos, np.array([1110.0, 38.0, 15.0]), UP, 46.0


def puck_vis(t):
    if t < 3.4:
        return np.array([1180.0, 0.5, -20.0]), 0.0, 1.0       # Puck liegt im Trapez (Hook)
    if t < 9.6:
        return puck_scn(t), 2.0 * t, 1.0
    return np.array([1170.0, 0.5, 30.0]), 0.3 * t, 1.0


CUTS = [9.6]


def seg(t):
    return (0.0, 9.6) if t < 9.6 else (9.6, DUR)


def cam_row_at(t):
    pos, tgt, up, fov = cam(t)
    r, u, f = P3.look_at(pos, tgt, up)
    return P3.cam_row(pos, r, u, f, fov), float(np.linalg.norm(tgt - pos))


def render3d(t, fidx):
    lo, hi = seg(t)
    cams, lens, pk = np.zeros((KSUB, 13)), np.zeros((KSUB, 2)), np.zeros((KSUB, 7))
    for j in range(KSUB):
        tk = min(max(t + ((j + 0.5) / KSUB - 0.5) * SHUTTER, lo), hi - 1e-4)
        row, focus = cam_row_at(tk)
        cams[j], lens[j] = row, (0.0, focus)
        p, th, vis = puck_vis(tk)
        pk[j] = (p[0], p[1], p[2], R18.G.THETA0 + th, vis, 0.0, tk)
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, SPP, fidx + 22, cams, lens, pk, R15.logo_tex(), base, puck, cov)
    return P3.tonemap(base), P3.tonemap(puck), cov


# ================================================================= Overlays
def fill_poly(ctx, xy, col, a):
    ctx.set_source_rgba(col[0] / 255, col[1] / 255, col[2] / 255, a)
    ctx.move_to(*xy[0])
    for p in xy[1:]:
        ctx.line_to(*p)
    ctx.close_path()
    ctx.fill()


def boards3d(ctx, cam_row):
    """Bande + Glas am Ende der Eisfläche (nur in den tiefen 3D-Einstellungen)."""
    xs = np.linspace(700, END_X, 40)
    for side in (1.0, -1.0):
        outline = [(x, side * board_z(x)) for x in xs]
        outline += [(END_X, side * z) for z in np.linspace(CZ, 0, 12)]
        b = poly3(outline, 0.0)
        top = b + np.array([0, 42.0, 0])
        glass = b + np.array([0, 110.0, 0])
        for i in range(len(b) - 1):
            quad = np.array([b[i], b[i + 1], top[i + 1], top[i]])
            xy, z = proj(cam_row, quad)
            if (z < 3).any():
                continue
            fill_poly(ctx, xy, (238, 239, 242), 1.0)
            kick = np.array([b[i], b[i + 1], b[i + 1] + [0, 9, 0], b[i] + [0, 9, 0]])
            kxy, _ = proj(cam_row, kick)
            fill_poly(ctx, kxy, (232, 196, 40), 1.0)
            gq = np.array([top[i], top[i + 1], glass[i + 1], glass[i]])
            gxy, _ = proj(cam_row, gq)
            fill_poly(ctx, gxy, (225, 232, 238), 0.55)
        txy, z = proj(cam_row, top)
        if (z > 3).all():
            stroke_poly(ctx, txy, (205, 208, 214), 1.0, 5)


def trapezoid(ctx, cam_row, t, scene):
    pulse = 0.5 + 0.5 * math.sin(t * 7)
    xy, z = proj(cam_row, trap_poly())
    if (z < 3).any():
        return
    a_fill = 0.0
    if scene == "hook":
        a_fill = 0.18 + 0.12 * pulse
    elif scene == "top":
        a_fill = 0.22
    else:
        a_fill = 0.2 + 0.08 * pulse
    fill_poly(ctx, xy, ORANGE, a_fill)
    w = float(np.clip(px_per_in(cam_row, float(z.mean())) * 3.5, 3, 10))
    stroke_poly(ctx, xy, ORANGE, 0.25, w * 4)
    stroke_poly(ctx, xy, ORANGE, 1.0, w)


def no_zones(ctx, cam_row, a):
    if a <= 0:
        return
    for side in (1.0, -1.0):
        xy, z = proj(cam_row, outside_zone(side))
        if (z < 3).any():
            continue
        fill_poly(ctx, xy, RED, 0.28 * a)
        stroke_poly(ctx, xy, RED, 0.8 * a, 4)


def arrow(ctx, cam_row, t):
    """Handgezeichneter Pfeil von der Frage auf das Trapez (Hook)."""
    p = c01((t - 0.05) / 0.3) if t > 0.02 else 1.0
    out = 1 - smooth(1.45, 1.6, t)
    if p <= 0 or out <= 0:
        return
    tip, z = projected(cam_row, np.array([1150.0, 0.06, -135.0]))
    a = np.array([W * 0.70, 650.0])
    c = np.array([W * 0.92, (a[1] + tip[1]) / 2])
    pts = np.array([(1 - u) ** 2 * a + 2 * (1 - u) * u * c + u * u * tip for u in np.linspace(0, p, 30)])
    stroke_poly(ctx, pts, HALO, 0.9 * out, 20)
    stroke_poly(ctx, pts, ORANGE, out, 10)
    if p > 0.95:
        d = pts[-1] - pts[-3]
        d /= np.linalg.norm(d) + 1e-6
        n = np.array([-d[1], d[0]])
        head = np.array([pts[-1] - d * 34 + n * 22, pts[-1], pts[-1] - d * 34 - n * 22])
        stroke_poly(ctx, head, HALO, 0.9 * out, 20)
        stroke_poly(ctx, head, ORANGE, out, 10)


def token(ctx, cam_row, p, col, r_in, a=1.0):
    xy, z = projected(cam_row, p)
    if z <= 0:
        return None
    r = px_per_in(cam_row, z) * r_in
    ctx.set_source_rgba(0, 0, 0, 0.12 * a)
    ctx.arc(xy[0] + 3, xy[1] + 5, r + 2, 0, 2 * math.pi)
    ctx.fill()
    ctx.set_source_rgba(1, 1, 1, a)
    ctx.arc(xy[0], xy[1], r, 0, 2 * math.pi)
    ctx.fill()
    ctx.set_source_rgba(col[0] / 255, col[1] / 255, col[2] / 255, a)
    ctx.set_line_width(max(3, r * 0.18))
    ctx.arc(xy[0], xy[1], r, 0, 2 * math.pi)
    ctx.stroke()
    return xy, r


def puck_marker(ctx, cam_row, p, t):
    xy, z = projected(cam_row, p)
    if z <= 0:
        return
    r = 26 + 3 * math.sin(t * 9)
    ctx.set_source_rgba(INK[0] / 255, INK[1] / 255, INK[2] / 255, 0.85)
    ctx.set_line_width(3)
    for k in range(4):
        a0 = k * math.pi / 2 + 0.35
        ctx.arc(xy[0], xy[1], r, a0, a0 + 0.9)
        ctx.stroke()


def trail2d(ctx, cam_row, fn, t, span=0.35):
    ts = np.linspace(max(0.0, t - span), t, 18)
    pts = np.array([fn(x) for x in ts])
    xy, z = proj(cam_row, pts)
    if (z < 3).any():
        return
    stroke_poly(ctx, xy, ORANGE, 0.18, 22)
    stroke_poly(ctx, xy, ORANGE, 0.7, 7)


def whistle_ring(ctx, cam_row, p, t, t0, col):
    li = t - t0
    if not 0 <= li < 0.6:
        return
    xy, z = projected(cam_row, p)
    q = e_out(li / 0.6, 3)
    ctx.set_source_rgba(col[0] / 255, col[1] / 255, col[2] / 255, 0.9 * (1 - q))
    ctx.set_line_width(10 * (1 - q) + 2)
    ctx.arc(xy[0], xy[1], 30 + 240 * q, 0, 2 * math.pi)
    ctx.stroke()


# ---------------- Text
def slam(L, txt, size, col, cx, cy, t, t0, t1=None, s0=1.6, glow=HALO):
    lt = t - t0
    if lt < 0 or (t1 is not None and t >= t1):
        return
    a = c01(lt / 0.05) * (1 - (smooth(t1 - 0.1, t1, t) if t1 else 0))
    sc = lerp(s0, 1.0, e_out(lt / 0.13, 3))
    im = word_img(txt, size, col, glow)
    im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.BILINEAR)
    if a < 1:
        im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    put(L, im, cx - im.width / 2, cy - im.height / 2)


def texts(L, t, cam_row):
    # Hook
    if t < 1.6:
        a = 1.0
        for txt, cy, size in (("WHY IS THIS", 330, 128), ("BEHIND EVERY", 470, 104), ("NHL NET?", 590, 128)):
            im = word_img(txt, size, INK, HALO)
            put(L, im, W / 2 - im.width / 2, cy - im.height / 2)
    # Titel in der Draufsicht
    slam(L, "THE TRAPEZOID", 118, ORANGE, W / 2, 300, t, 2.75, T_A0 - 0.05)
    if 2.95 <= t < T_A0:
        reveal(L, line_img("NHL RULE SINCE 2005–06", 36, 800, INK, track=8), W / 2, 400, smooth(2.95, 3.15, t),
               smooth(T_A0 - 0.15, T_A0, t))
    # Szenario A
    if T_A0 <= t < T_REW0:
        reveal(L, line_img("GOALIE PLAYS IT OUTSIDE…", 54, 850, INK, track=3), W / 2, 300, smooth(T_A0, T_A0 + 0.2, t),
               smooth(T_WHISTLE - 0.1, T_WHISTLE, t))
    slam(L, "2 MIN", 230, RED, W / 2, 360, t, T_WHISTLE + 0.05, T_REW0, 1.9)
    if T_WHISTLE + 0.25 <= t < T_REW0:
        reveal(L, line_img("DELAY OF GAME", 48, 850, RED, track=10), W / 2, 500, smooth(T_WHISTLE + 0.25, T_WHISTLE + 0.45, t),
               smooth(T_REW0 - 0.1, T_REW0, t))
    # Rewind
    if T_REW0 <= t < T_REW1:
        reveal(L, line_img("<<  REWIND", 60, 900, INK, track=10), W / 2, 330, 1.0)
    # Szenario B
    if T_REW1 <= t < T_LEGAL:
        reveal(L, line_img("…OR INSIDE THE TRAPEZOID", 54, 850, INK, track=3), W / 2, 300, smooth(T_REW1, T_REW1 + 0.2, t),
               smooth(T_LEGAL - 0.1, T_LEGAL, t))
    slam(L, "LEGAL.", 200, GREEN, W / 2, 360, t, T_LEGAL, 9.6, 1.8)
    # Brodeur
    slam(L, "NICKNAMED", 96, INK, W / 2, 330, t, 9.7, 11.3)
    slam(L, "THE BRODEUR", 128, ORANGE, W / 2, 460, t, 9.85, 11.3)
    slam(L, "RULE", 150, ORANGE, W / 2, 590, t, 10.0, 11.3)
    # CTA
    slam(L, "SHOULD THE NHL", 104, INK, W / 2, 330, t, 11.35)
    slam(L, "REMOVE IT?", 150, INK, W / 2, 465, t, 11.5)
    slam(L, "YES", 150, GREEN, W * 0.3, 640, t, 11.9)
    slam(L, "NO", 150, RED, W * 0.7, 640, t, 12.05)
    if t >= 12.15:
        reveal(L, line_img("/", 130, 300, INK), W / 2, 640, c01((t - 12.15) / 0.15))
        reveal(L, line_img("COMMENT YES OR NO", 38, 800, ORANGE, track=8), W / 2, 770, c01((t - 12.3) / 0.25))


# ================================================================= Bild
def compose(t, fidx):
    base, puck, cov = render3d(t, fidx)
    row, _ = cam_row_at(t)
    scene = "hook" if t < 1.6 else ("crane" if t < 3.4 else ("top" if t < 9.6 else "end"))
    lo_s, lo_c = surface()
    if scene in ("hook", "end", "crane"):
        if scene != "crane" or t < 2.4:
            boards3d(lo_c, row)
    trapezoid(lo_c, row, t, scene)
    if scene == "top":
        hl = smooth(T_WHISTLE, T_WHISTLE + 0.1, t) * (1 - smooth(T_REW0 - 0.1, T_REW0, t))
        no_zones(lo_c, row, hl)
        if T_A0 <= t < T_PASS1 + 0.3:
            trail2d(lo_c, row, puck_scn, t)
    img = over(base, *surf_rgba(lo_s))
    nb, nf = R15.draw_net(row, -1.0, False), R15.draw_net(row, -1.0, True)
    img = over(img, *surf_rgba(nb))
    pa = cov[..., None]
    img = img * (1 - pa) + puck * pa
    img = over(img, *surf_rgba(nf))
    hi_s, hi_c = surface()
    if scene == "top":
        g = goalie_scn(t)
        token(hi_c, row, g + np.array([0, 0.1, 0]), ORANGE, 20)
        puck_marker(hi_c, row, puck_scn(t), t)
        whistle_ring(hi_c, row, puck_scn(T_WHISTLE), t, T_WHISTLE, RED)
        whistle_ring(hi_c, row, puck_scn(T_LEGAL), t, T_LEGAL, GREEN)
    if scene in ("hook", "end"):
        puck_marker(hi_c, row, puck_vis(t)[0], t)
    if scene == "hook":
        arrow(hi_c, row, t)
    img = over(img, *surf_rgba(hi_s))
    if scene == "top" and T_WHISTLE <= t < T_WHISTLE + 0.35:            # roter Blitz beim Pfiff
        a = 0.22 * (1 - (t - T_WHISTLE) / 0.35)
        img = img * (1 - a) + np.array([1.0, 0.1, 0.12], np.float32) * a
    if T_REW0 <= t < T_REW1:                                              # VHS-Rücklauf
        rng = np.random.default_rng(int(t * 1000))
        img = img * 0.92 + 0.04
        for _ in range(7):
            y0, hh = int(rng.uniform(0, H - 40)), int(rng.uniform(6, 34))
            img[y0:y0 + hh] = np.roll(img[y0:y0 + hh], int(rng.uniform(-45, 45)), 1)
        img[::4] *= 0.93
    img = np.clip(img, 0, 1)
    pil = Image.fromarray((img * 255).astype(np.uint8)).convert("RGBA")
    if scene == "top":                                                    # Goalie-"G" auf dem Token
        xy, z = projected(row, goalie_scn(t))
        gi = line_img("G", 30, 900, INK)
        put(pil, gi, xy[0] - gi.width / 2, xy[1] - gi.height / 2)
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    texts(L, t, row)
    pil.alpha_composite(L)
    arr = np.asarray(pil.convert("RGB")).astype(np.float32) / 255
    lc = min([t - c for c in CUTS + [T_WHISTLE, T_LEGAL] if t >= c] + [t + 0.5])
    zp = 1 + 0.04 * math.exp(-lc * 14)
    if zp > 1.002:
        im2 = Image.fromarray((arr * 255).astype(np.uint8))
        w2, h2 = W / zp, H / zp
        im2 = im2.transform((W, H), Image.EXTENT, ((W - w2) / 2, (H - h2) / 2, (W + w2) / 2, (H + h2) / 2), Image.BILINEAR)
        arr = np.asarray(im2).astype(np.float32) / 255
    arr = arr * (0.55 + 0.45 * vignette())
    arr += np.random.default_rng(fidx).normal(0, 0.008, arr.shape[:2])[..., None]
    return (np.clip(arr, 0, 1) * 255).astype(np.uint8)


# ================================================================= Sound (Trap, 140 BPM)
SR = 44100


def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(22)
    L_, R_ = np.zeros(n), np.zeros(n)
    B = 60 / 140

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

    def kick(vol=1.0):
        x = tt(0.35)
        f = 46 + 180 * np.exp(-x * 38)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 9) * 3.0 + hp(noise(0.35), 2) * np.exp(-x * 400) * 0.5) * vol

    def clap(vol=1.0):
        x = tt(0.3)
        env = sum((x >= d) * np.exp(-np.maximum(x - d, 0) * 70) for d in (0.0, 0.01, 0.021))
        return hp(lp(noise(0.3), 2), 6) * (env * 0.45 + np.exp(-x * 13) * 0.55) * 0.8 * vol

    def hat(vol=0.14):
        return hp(noise(0.04), 1) * np.exp(-tt(0.04) * 150) * vol

    def b808(freq, dur, glide=0.5):
        x = tt(dur)
        f = freq * (1 + glide * np.exp(-x * 10))
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * 2.4) * np.minimum(x / 0.003, 1) * np.exp(-x * 1.3) * 0.8

    def bell(freq, dur=0.5, vol=0.1):
        x = tt(dur)
        return np.sin(2 * np.pi * freq * x + np.sin(2 * np.pi * freq * 3.5 * x) * 2 * np.exp(-x * 6)) * np.exp(-x * 5) * vol

    def whoosh(dur=0.35, vol=1.0):
        x = tt(dur)
        nz = noise(dur)
        env = np.exp(-((x / dur - 0.55) ** 2) * 16)
        kx = 36 - 30 * (x / dur)
        return sum(lp(nz, kk) * np.exp(-((kx - kk) ** 2) / 60) for kk in (36, 18, 8, 4)) * env * 1.6 * vol

    def whistle(dur=0.6, vol=0.5):
        x = tt(dur)
        trill = 1 + 0.5 * (np.sin(2 * np.pi * 32 * x) > 0)
        sig = np.sin(2 * np.pi * np.cumsum(np.full_like(x, 2900.0) + 120 * np.sin(2 * np.pi * 32 * x)) / SR)
        return sig * trill * 0.5 * np.minimum(x / 0.02, 1) * np.clip((dur - x) / 0.08, 0, 1) * vol

    def stamp(vol=1.0):
        x = tt(0.9)
        f = 40 + 120 * np.exp(-x * 16)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 4) * 2.4) * vol

    def ding(vol=0.4):
        x = tt(0.9)
        return (np.sin(2 * np.pi * 1318.5 * x) + 0.6 * np.sin(2 * np.pi * 1760 * x) * (x > 0.09)) * np.exp(-x * 5) * vol

    def rewind(dur=0.35, vol=0.6):
        x = tt(dur)
        f = 900 + 2400 * (x / dur) ** 1.5
        return np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.25 * lp(noise(dur), 3) * vol + hp(noise(dur), 2) * 0.15 * vol

    def scrape(dur=0.4, vol=0.6):
        x = tt(dur)
        return hp(noise(dur), 2) * np.exp(-x * 6) * vol

    roots = [55.0, 43.65, 49.0, 41.2]
    mel = [880.0, 1046.5, 1318.5, 1046.5, 987.8, 880.0, 784.0, 659.25]
    for k8 in range(int(DUR / (B / 2))):
        tb = k8 * B / 2
        b = k8 / 2
        pos = b % 4
        quiet = (T_REW0 <= tb < T_REW1 + 0.05) or tb >= 13.0
        if not quiet:
            if pos in (0.0, 2.5):
                put_(kick(), tb)
            if pos in (1.0, 3.0):
                put_(clap(), tb)
            put_(hat(0.14 if k8 % 2 == 0 else 0.09), tb, pan=0.3)
            if pos == 3.5:
                for j in range(1, 4):
                    put_(hat(0.08), tb + j * B / 6, pan=0.3)
            if pos == 0.0:
                put_(b808(roots[int(b // 4) % 4], 2.3 * B), tb)
        put_(bell(mel[k8 % 8], 0.5, 0.06), tb, pan=-0.2)
    put_(stamp(0.9), 0.0)
    put_(whoosh(0.6, 0.8), 1.7)
    put_(stamp(0.6), 2.75)
    put_(scrape(0.5, 0.5), T_A0)
    put_(scrape(0.4, 0.4), T_G0 + 0.2, pan=0.3)
    put_(whistle(0.7, 0.6), T_WHISTLE)
    put_(stamp(1.1), T_WHISTLE + 0.05)
    put_(rewind(T_REW1 - T_REW0, 0.7), T_REW0)
    put_(scrape(0.5, 0.5), T_B0)
    put_(ding(0.5), T_LEGAL)
    put_(stamp(0.7), T_LEGAL)
    put_(whoosh(0.35, 0.6), T_PASS0)
    put_(whoosh(0.4, 0.7), 9.5)
    for t0 in (9.7, 9.85, 10.0, 11.35, 11.5, 11.9, 12.05):
        put_(stamp(0.55), t0)
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
    make_audio("audio_trapezoid.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_trapezoid.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
           "reel22_trapezoid.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(0.8, 9999)).save("reel22_thumbnail.jpg", quality=92)
    print("fertig: reel22_trapezoid.mp4")


if __name__ == "__main__":
    main()
