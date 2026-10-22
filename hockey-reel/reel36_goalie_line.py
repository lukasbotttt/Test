"""Reel 36: "WHY CAN'T THE GOALIE TOUCH THE PUCK HERE?" – Mittellinien-Regel für Goalies (weißer Studio-Look, ~12 s).

Muster wie Reel 22 (Trapez, größter Hit): Goalie-Einschränkung als Rätsel-Hook, Szenario A (Strafe), Rückspulen,
Szenario B (legal), Frage + FOLLOW. Allgemeine Regel, keine Teams/Vereine.
Fakten (Recherche 22.10.2026):
- NHL Rule 27.7: Spielt der Goalie hinter der roten Mittellinie den Puck (oder checkt), gibt es eine kleine Strafe.
  Entscheidend ist die Position des PUCKS. Über die Linie fahren ist nicht verboten -> Video sagt "can't play the puck".
  IIHF: gleiche Regel (27.6). Strafe sitzt ein Mitspieler ab (27.1) -> Video sagt nichts von Strafbank.
- Aus der eigenen Hälfte darf er schießen; NHL.com (2.10.2026): 18 NHL-Goalies wurden 21 Tore gutgeschrieben.
Bilder: Bande, Glas, Tore (mesh3d), Eis + Puck (Raytracer), Goalie als Marker "G". Keine Spielerkörper.
Stimme: Kokoro "Michael", 1,08x. Aufruf: python3 reel36_goalie_line.py vo | audio | prev 0.5,3.0 out.jpg | (Video)
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

import mesh3d as M3
import puck3d as P3
import reel15_puck as R15
import reel18_dangle as R18
import reel26_overglass as R26
import reel28_emptynet as R28
from reel15_puck import (W, H, FPS, c01, smooth, sio, e_out, e_in, lerp, blend_up, line_img, reveal, put, proj,
                         projected, stroke_poly, surface, surf_rgba, over, GOAL_X)
from reel22_trapezoid import slam, puck_marker, fill_poly, board_z, whistle_ring

HERE = R15.HERE
SPP = int(os.environ.get("SPP", "8"))
KSUB = int(os.environ.get("KSUB", "10"))
SHUTTER = 0.5 / FPS
INK, ORANGE = R15.INK, R15.ORANGE
RED = (225, 30, 40)
GREEN = (30, 160, 80)
BLUE = (40, 110, 210)
HALO = (255, 255, 255)
NAVY = (38, 35, 52)
TEMPO = 1.08

VO_LINES = [
    ("q", "Why can't the goalie touch the puck HERE?"),
    ("rule", "Past the center red line, a goalie can't play the puck. Two-minute penalty."),
    ("twist", "From his own half? He can shoot, and even score."),
    ("cta", "Should that change? Follow for more rules."),
]
VO_KEYS = [k for k, _ in VO_LINES]
VO_START = {"q": 0.1, "rule": 2.05, "twist": 6.15, "cta": 9.6}
DUR = 12.6
WT = {                                           # Wortanfänge (s nach Satzbeginn, nach 1,08x), faster-whisper
    "q": [0.0, 0.12, 0.42, 0.44, 0.6, 0.92, 1.1, 1.24],
    "rule": [0.0, 0.14, 0.3, 0.48, 0.68, 1.24, 1.26, 1.44, 1.84, 2.0, 2.12, 2.76, 3.08],
    "twist": [0.0, 0.1, 0.22, 0.36, 1.0, 1.1, 1.2, 1.42, 1.64, 1.8],
    "cta": [0.0, 0.12, 0.26, 0.94, 1.2, 1.42, 1.58],
}


def wt(key, i):
    return VO_START[key] + WT[key][i]


T_UP0, T_UP1 = 1.95, 2.55                        # Hook -> Draufsicht
T_LINE = wt("rule", 2)                           # "center red line": Linie glüht
T_GO = 2.35                                      # Goalie fährt los
T_TOUCH = wt("rule", 8)                          # "play" – Goalie spielt den Puck hinter der Linie
T_WH = T_TOUCH + 0.22                            # Pfiff
T_2MIN = wt("rule", 11) - 0.05                   # "two-minute"
T_RW0, T_RW1 = 5.55, 6.0                         # Rückspulen
T_SHOT = wt("twist", 6)                          # "shoot"
T_GOAL = wt("twist", 9) + 0.05                   # "score"
T_DN0, T_DN1 = 9.3, 10.0                        # zurück in die 3D-Einstellung (Loop)
T_CTA = VO_START["cta"]

# ================================================================= Positionen (Zoll; eigenes Tor bei x = -1068)
CREASE = np.array([-1030.0, 0.0, 0.0])
PUCK_A = np.array([42.0, 0.5, 150.0])           # Puck knapp hinter der Mittellinie
PASS_A = np.array([-330.0, 0.5, -190.0])         # Goalie passt zurück
G_A1 = np.array([22.0, 0.0, 136.0])              # Goalie am Puck
G_B = np.array([-690.0, 0.0, -70.0])             # Goalie in der eigenen Hälfte
NET_B = np.array([GOAL_X + 20.0, 1.5, 8.0])      # leeres Tor gegenüber


def bez(p0, p1, p2, u):
    return (1 - u) ** 2 * p0 + 2 * (1 - u) * u * p1 + u * u * p2


def goalie_a(t):
    u = c01((t - T_GO) / (T_TOUCH - T_GO))
    u = 0.35 * u ** 1.5 + 0.65 * sio(u)
    return bez(CREASE, np.array([-560.0, 0.0, 300.0]), G_A1, u)


def goalie_state(t):
    """Position des Goalies (G)."""
    if t < T_GO:
        return CREASE + np.array([6 * math.sin(t * 2), 0, 4 * math.cos(t * 1.7)]) * (t > 0.1)
    if t < T_RW0:
        p = goalie_a(min(t, T_TOUCH))
        if t > T_TOUCH:                                          # gleitet nach dem Spielen aus
            p = p + np.array([22.0, 0.0, 10.0]) * e_out(c01((t - T_TOUCH) / 0.6), 2)
        return p
    if t < T_RW1:                                                # Rückspulen
        s = sio((t - T_RW0) / (T_RW1 - T_RW0))
        a = goalie_a(T_TOUCH) + np.array([22.0, 0.0, 10.0])
        return a + (G_B - a) * s
    return G_B + np.array([8.0, 0.0, 3.0]) * c01((t - T_RW1) / 1.2)


def puck_state(t):
    """(Position, sichtbar)"""
    if t < T_TOUCH:
        return PUCK_A, 1.0
    if t < T_RW0:
        u = c01((t - T_TOUCH) / 0.55)
        return PUCK_A + (PASS_A - PUCK_A) * (1 - (1 - u) ** 1.4), 1.0
    if t < T_RW1:
        s = sio((t - T_RW0) / (T_RW1 - T_RW0))
        return PASS_A + (G_B + np.array([30.0, 0.5, 16.0]) - PASS_A) * s, 1.0
    stick = G_B + np.array([30.0, 0.5, 16.0])
    if t < T_SHOT:
        return stick, 1.0
    if t < T_GOAL:
        u = c01((t - T_SHOT) / (T_GOAL - T_SHOT))
        return stick + (NET_B - stick) * (1 - (1 - u) ** 1.25), 1.0
    return NET_B, 1.0


# ================================================================= Kamera
def hook_cam(t):
    p0, p1 = PUCK_A + np.array([-128.0, 44.0, 52.0]), PUCK_A + np.array([-104.0, 36.0, 42.0])
    return p0 + (p1 - p0) * e_out(c01(t / 2.0), 2), PUCK_A + np.array([4.0, -6.0, 0.0]), 42.0


def top_a(t):
    return R28.top_cam(-170.0, 4300.0, 30.0)


def top_b(t):
    return R28.top_cam(40.0, 5050.0, 30.0)


def cam(t):
    if t < T_UP0:
        p, g, f = hook_cam(t)
    elif t < T_UP1:
        p, g, f = R28.blend_cam(hook_cam(T_UP0), top_a(T_UP1), sio((t - T_UP0) / (T_UP1 - T_UP0)))
    elif t < T_RW0:
        p, g, f = top_a(t)
    elif t < T_RW1 + 0.2:
        p, g, f = R28.blend_cam(top_a(T_RW0), top_b(T_RW1 + 0.2), sio((t - T_RW0) / (T_RW1 + 0.2 - T_RW0)))
    elif t < T_DN0:
        p, g, f = top_b(t)
    elif t < T_DN1:
        p, g, f = R28.blend_cam(top_b(T_DN0), hook_cam(0.6), sio((t - T_DN0) / (T_DN1 - T_DN0)))
    else:
        p, g, f = hook_cam(0.6 - 0.5 * sio(c01((t - T_DN1) / (DUR - T_DN1))))
    d = (p - g) / np.linalg.norm(p - g)
    el = math.degrees(math.asin(max(-1.0, min(1.0, d[1]))))
    return p, g, blend_up(min(el, 89.9)), f


def cam_row_at(t):
    pos, tgt, up, fov = cam(t)
    r, u, f = P3.look_at(pos, tgt, up)
    return P3.cam_row(pos, r, u, f, fov), float(np.linalg.norm(tgt - pos))


def seg(t):
    for a, b in ((0.0, T_RW0), (T_RW0, T_RW1), (T_RW1, DUR)):
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
        pk[j] = (p[0], p[1], p[2], 1.3 + 6.0 * tk, vis, 0.0, tk)
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, SPP, fidx + 36, cams, lens, pk, R15.logo_tex(), base, puck, cov)
    return P3.tonemap(base), P3.tonemap(puck), cov


# ================================================================= Overlays
def half_poly(side=1.0):
    """Hälfte der Eisfläche hinter der Mittellinie (x > 0), mit Eckrundung."""
    xs = np.linspace(0.0, 1200.0, 60)
    top = [(x, 0.08, board_z(x)) for x in xs]
    bot = [(x, 0.08, -board_z(x)) for x in xs[::-1]]
    return np.array([(side * x, y, z) for x, y, z in top + bot])


HALF = half_poly()


def clip_proj(row, pts, closed=True, near=2.0):
    """Polygon/Linie an der Kameraebene abschneiden (Sutherland-Hodgman), dann projizieren."""
    _, z = proj(row, pts)
    out = []
    n = len(pts)
    for i in range(n if closed else n - 1):
        a, b = pts[i], pts[(i + 1) % n]
        za, zb = z[i], z[(i + 1) % n]
        if za >= near:
            out.append(a)
        if (za >= near) != (zb >= near):
            out.append(a + (b - a) * (near + 0.01 - za) / (zb - za))
    if not closed and z[-1] >= near:
        out.append(pts[-1])
    if len(out) < 2:
        return None
    xy, _ = proj(row, np.array(out))
    return xy


def red_zone(ctx, row, a, t):
    if a <= 0:
        return
    xy = clip_proj(row, HALF)                            # Hook-Nahaufnahme: Teile hinter der Kamera abschneiden
    if xy is None or len(xy) < 3:
        return
    pulse = 0.5 + 0.5 * math.sin(t * 7)
    fill_poly(ctx, xy, RED, a * (0.16 + 0.06 * pulse))


def line_glow(ctx, row, a):
    if a <= 0:
        return
    pts = np.array([(0.0, 0.12, z) for z in np.linspace(-505, 505, 40)])
    xy = clip_proj(row, pts, closed=False)
    if xy is None:
        return
    stroke_poly(ctx, xy, RED, 0.25 * a, 46)
    stroke_poly(ctx, xy, RED, 0.5 * a, 22)
    stroke_poly(ctx, xy, (255, 120, 120), 0.9 * a, 6)


def goalie_marker(hi_c, L, row, t):
    p = goalie_state(t)
    c_r = R28.disc(hi_c, row, p, BLUE, 1.0, r_px=(40, 80), r_in=34.0, ring=ORANGE)
    R28.letter(L, c_r, "G", BLUE, 1.0, 0.95)
    return c_r


def path(hi_c, row, t):
    if T_GO <= t < T_TOUCH + 0.4:                                       # Weg des Goalies
        us = np.linspace(0, c01((t - T_GO) / (T_TOUCH - T_GO)), 30)
        pts = [goalie_a(T_GO + u * (T_TOUCH - T_GO)) + np.array([0, 0.1, 0]) for u in us]
        R28.path_line(hi_c, row, pts, BLUE, 0.7 * (1 - smooth(T_TOUCH, T_TOUCH + 0.4, t)), 5, [20, 16], t)
    if T_SHOT - 0.05 <= t < T_GOAL + 0.6:                               # Schuss übers ganze Eis
        stick = G_B + np.array([30.0, 0.5, 16.0])
        u1 = c01((t - T_SHOT) / (T_GOAL - T_SHOT))
        pts = [stick + (NET_B - stick) * (1 - (1 - u) ** 1.25) for u in np.linspace(0, u1, 40)]
        R28.path_line(hi_c, row, pts, ORANGE, 1 - smooth(T_GOAL + 0.2, T_GOAL + 0.6, t), 7)


def word(txt, size, col):
    im = R18.word_img(txt, size, col, HALO)
    if im.width > 1040:
        im = im.resize((1040, int(im.height * 1040 / im.width)), Image.LANCZOS)
    return im


def fade_im(im, a):
    if a >= 1:
        return im
    im = im.copy()
    im.putalpha(im.getchannel("A").point(lambda v: int(v * max(a, 0.0))))
    return im


_NAVY = {}


def brand(L, t):
    if t < T_UP0:
        return
    if "lock" not in _NAVY:
        import reel33_lines_neon as N
        im = N.brand_img("bladesandpucks_lockup_transparent.png", 280).img
        arr = np.asarray(im).astype(np.float32)
        wm = (arr[..., 0] > 200) & (arr[..., 1] > 200) & (arr[..., 2] > 200)
        arr[wm, 0:3] = NAVY
        _NAVY["lock"] = Image.fromarray(arr.astype(np.uint8), "RGBA")
    im = fade_im(_NAVY["lock"], 0.92 * smooth(T_UP0, T_UP0 + 0.3, t) * (1 - smooth(T_DN0 - 0.2, T_DN0, t)))
    put(L, im, W / 2 - im.width / 2, 1830 - im.height / 2)


def here_arrow(ctx, row, t, a):
    """Pfeil vom Hook-Text auf den Puck."""
    if a <= 0:
        return
    xy, z = projected(row, PUCK_A + np.array([0, 3.0, 0]))
    if z <= 0:
        return
    sx, sy = 700.0, 680.0
    ex, ey = xy[0] + 10, xy[1] - 34
    k = e_out(c01((t - 0.25) / 0.35), 3)
    ex, ey = sx + (ex - sx) * k, sy + (ey - sy) * k
    ctx.set_source_rgba(ORANGE[0] / 255, ORANGE[1] / 255, ORANGE[2] / 255, a)
    ctx.set_line_width(9)
    ctx.move_to(sx, sy)
    ctx.curve_to(sx + 40, sy + 80, ex + 30, ey - 90, ex, ey)
    ctx.stroke()
    if k > 0.95:
        ang = math.atan2(90.0, -30.0)
        for s in (-1, 1):
            ctx.move_to(ex, ey)
            ctx.line_to(ex - 36 * math.cos(ang + s * 0.5), ey - 36 * math.sin(ang + s * 0.5))
        ctx.stroke()


def texts(L, t):
    # Hook: ganze Frage ab Bild 0
    if t < T_UP0 + 0.1:
        k = 1 - smooth(T_UP0 - 0.1, T_UP0 + 0.1, t)
        for txt, cy, size, col in (("WHY CAN'T THE GOALIE", 300, 92, INK), ("TOUCH THE PUCK", 420, 112, INK),
                                   ("HERE?", 580, 190, RED)):
            im = fade_im(word(txt, size, col), k)
            put(L, im, W / 2 - im.width / 2, cy - im.height / 2)
    # Regel
    if T_UP1 - 0.1 <= t < T_WH:
        reveal(L, line_img("PAST THE CENTER RED LINE…", 52, 850, INK, track=3), W / 2, 300,
               smooth(T_UP1 - 0.1, T_UP1 + 0.1, t), smooth(T_WH - 0.1, T_WH, t))
    if wt("rule", 6) - 0.05 <= t < T_WH:
        reveal(L, line_img("…NO PUCK FOR THE GOALIE", 52, 850, RED, track=3), W / 2, 380,
               c01((t - wt("rule", 6) + 0.05) / 0.2), smooth(T_WH - 0.1, T_WH, t))
    slam(L, "2 MIN", 230, RED, W / 2, 330, t, T_2MIN, T_RW0, 1.9)
    if T_2MIN + 0.25 <= t < T_RW0:
        reveal(L, line_img("MINOR PENALTY · NHL RULE 27.7", 40, 850, RED, track=6), W / 2, 470,
               smooth(T_2MIN + 0.25, T_2MIN + 0.45, t), smooth(T_RW0 - 0.1, T_RW0, t))
    if T_RW0 <= t < T_RW1:
        reveal(L, line_img("<<  REWIND", 60, 900, INK, track=10), W / 2, 330, 1.0)
    # Szenario B
    if T_RW1 <= t < T_GOAL:
        reveal(L, line_img("FROM HIS OWN HALF?", 60, 900, INK, track=3), W / 2, 760,
               smooth(T_RW1, T_RW1 + 0.2, t), smooth(T_GOAL - 0.1, T_GOAL, t))
    slam(L, "GOAL!", 210, ORANGE, W / 2, 900, t, T_GOAL, T_DN0, 1.9)
    slam(L, "LEGAL.", 130, GREEN, W / 2, 1060, t, T_GOAL + 0.25, T_DN0, 1.7)
    if T_GOAL + 0.45 <= t < T_DN0:
        reveal(L, line_img("ONLY 18 NHL GOALIES HAVE BEEN", 34, 850, INK, track=5), W / 2, 1170,
               smooth(T_GOAL + 0.45, T_GOAL + 0.65, t), smooth(T_DN0 - 0.1, T_DN0, t))
        reveal(L, line_img("CREDITED WITH A GOAL", 34, 850, INK, track=5), W / 2, 1220,
               smooth(T_GOAL + 0.55, T_GOAL + 0.75, t), smooth(T_DN0 - 0.1, T_DN0, t))
    # CTA
    slam(L, "SHOULD THAT", 110, INK, W / 2, 300, t, T_CTA - 0.05)
    slam(L, "CHANGE?", 160, INK, W / 2, 440, t, wt("cta", 2) - 0.05)
    slam(L, "YES", 140, GREEN, W * 0.3, 600, t, wt("cta", 2) + 0.2)
    slam(L, "NO", 140, RED, W * 0.7, 600, t, wt("cta", 2) + 0.35)
    if t >= wt("cta", 2) + 0.45:
        reveal(L, line_img("/", 120, 300, INK), W / 2, 600, c01((t - wt("cta", 2) - 0.45) / 0.15))
    slam(L, "FOLLOW", 160, RED, W / 2, 1420, t, wt("cta", 3) - 0.05)
    if t >= wt("cta", 4):
        reveal(L, line_img("FOR MORE RULES", 44, 850, INK, track=8), W / 2, 1540, c01((t - wt("cta", 4)) / 0.25))


def rewind_fx(img, t):
    if not (T_RW0 <= t < T_RW1):
        return img
    k = math.sin(math.pi * (t - T_RW0) / (T_RW1 - T_RW0))
    out = img.copy()
    sh = int(10 * k)
    if sh:
        out[..., 0] = np.roll(img[..., 0], sh, axis=1)
        out[..., 2] = np.roll(img[..., 2], -sh, axis=1)
    rng = np.random.default_rng(int(t * 1000))
    for _ in range(4):
        y, hb = int(rng.integers(0, H - 40)), int(rng.integers(6, 30))
        out[y:y + hb] = np.roll(out[y:y + hb], int(40 * k), axis=1)
    return out * (1 - 0.08 * k) + 0.08 * k


# ================================================================= Bild
def compose(t, fidx):
    base, puck, cov = render3d(t, fidx)
    row, _ = cam_row_at(t)
    campos = cam(t)[0]
    p, vis = puck_state(t)
    lo_s, lo_c = surface()
    hi_s, hi_c = surface()
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # rote Zone + glühende Mittellinie (unter Bande/Toren)
    za = (1 - smooth(T_UP0 - 0.1, T_UP0 + 0.2, t)) + smooth(T_LINE - 0.1, T_LINE + 0.2, t) * (1 - smooth(T_RW0, T_RW0 + 0.2, t))
    za = max(za, 0.0) + (smooth(T_DN1, T_DN1 + 0.3, t) if t >= T_DN1 else 0.0)
    red_zone(lo_c, row, min(za, 1.0) * (1.6 if T_WH <= t < T_RW0 else 1.0), t)
    la = max(1 - smooth(T_UP0, T_UP0 + 0.3, t), smooth(T_LINE - 0.05, T_LINE + 0.15, t) * (1 - smooth(T_RW0, T_RW0 + 0.2, t)),
             smooth(T_DN1, T_DN1 + 0.3, t))
    line_glow(lo_c, row, la)
    R28.draw_net_lines(lo_c, row)
    R28.glass_edges(lo_c, row)
    img = over(base, *surf_rgba(lo_s))
    meshes = R28.BOARDS + R28.FRAMES
    if vis > 0:
        import reel25_goalline as G25
        meshes = meshes + [G25.cyl_mesh(p - np.array([0, 0.5, 0]), 1.5, 1.0, "occluder", group=1)]
    m_rgb, m_a, shadow, plane_a = M3.render(meshes, row, W, H, campos, alpha_by_group=np.array([1.0, 0.0], np.float32),
                                            extra_planes=[(R28.GLASS_ALL, 1.0)], shadow_light=(0.02, 1.0, -0.03))
    img = img * (1 - 0.15 * shadow[..., None])
    pa = cov[..., None]
    img = img * (1 - pa) + puck * pa
    img = img * (1 - m_a[..., None]) + m_rgb
    k = (0.30 * plane_a)[..., None]
    img = img * (1 - k) + np.array([0.70, 0.82, 0.94], np.float32) * k
    img = img + (R26.glass_streaks() * plane_a * 0.10)[..., None]
    # Marker, Wege, Puck-Ring
    path(hi_c, row, t)
    c_r = goalie_marker(hi_c, L, row, t)
    if vis > 0:
        puck_marker(hi_c, row, p, t)
    whistle_ring(hi_c, row, PUCK_A + np.array([0, 0.5, 0]), t, T_WH, RED)
    R28.pulse_ring(hi_c, c_r, ORANGE, t, T_TOUCH, 0.5)
    gc, z = projected(row, NET_B)
    if z > 0:
        R28.pulse_ring(hi_c, (gc, 40.0), ORANGE, t, T_GOAL, 0.7)
    here_arrow(hi_c, row, t, 1 - smooth(T_UP0 - 0.2, T_UP0, t))
    img = over(img, *surf_rgba(hi_s))
    for t0 in (T_WH, T_2MIN, T_GOAL):
        if t0 <= t < t0 + 0.2:
            a = 0.12 * (1 - (t - t0) / 0.2)
            img = img * (1 - a) + a
    img = rewind_fx(np.clip(img, 0, 1), t)
    pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
    texts(L, t)
    brand(L, t)
    pil.alpha_composite(L)
    arr = np.asarray(pil.convert("RGB")).astype(np.float32) / 255
    lc = min([t - c for c in (T_WH, T_2MIN, T_GOAL) if t >= c] + [t + 0.5])
    zp = 1 + 0.035 * math.exp(-lc * 12)
    if zp > 1.002:
        im2 = Image.fromarray((arr * 255).astype(np.uint8))
        w2, h2 = W / zp, H / zp
        im2 = im2.transform((W, H), Image.EXTENT, ((W - w2) / 2, (H - h2) / 2, (W + w2) / 2, (H + h2) / 2),
                            Image.BILINEAR)
        arr = np.asarray(im2).astype(np.float32) / 255
    arr = arr * R18.vignette()
    return (np.clip(arr, 0, 1) * 255).astype(np.uint8)


# ================================================================= Ton
SR = 44100


def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(36)
    mus = np.zeros((n, 2))
    sfx = np.zeros((n, 2))
    B = 60 / 124

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
        return np.tanh(np.sin(2 * np.pi * np.cumsum(42 + 160 * np.exp(-x * 34)) / SR) * np.exp(-x * 7) * 3.0) * vol

    def clap(vol=1.0):
        x = tt(0.3)
        return hp(noise(0.3), 2) * (np.exp(-x * 30) + 0.5 * np.exp(-np.abs(x - 0.012) * 300)) * 0.8 * vol

    def hat(vol=0.1):
        return hp(noise(0.04), 1) * np.exp(-tt(0.04) * 150) * vol

    def sub(freq, dur):
        x = tt(dur)
        f = freq * (1 + 0.6 * np.exp(-x * 9))
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * 2.6) * np.minimum(x / 0.004, 1) * np.exp(-x * 1.1) * 0.85

    def whistle(dur=0.55, vol=0.5):
        x = tt(dur)
        f = 2900 + 120 * np.sin(2 * np.pi * 34 * x)
        env = np.minimum(x / 0.02, 1) * np.clip((dur - x) / 0.08, 0, 1)
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.25 * hp(noise(dur), 2)) * env * vol

    def horn(dur=1.1, vol=0.5):
        x = tt(dur)
        sig = sum(np.sign(np.sin(2 * np.pi * f * x)) * w for f, w in ((116.5, 1.0), (146.8, 0.7), (174.6, 0.5)))
        env = np.minimum(x / 0.04, 1) * np.clip((dur - x) / 0.25, 0, 1)
        return lp(sig, 6) * env * vol

    def crowd(dur=2.5, vol=0.4):
        x = tt(dur)
        sig = lp(noise(dur), 12) - lp(noise(dur), 60) * 0.6
        return sig * np.sin(np.pi * np.clip(x / dur, 0, 1)) ** 0.8 * vol * 2.0

    def puck_hit(vol=0.7):
        x = tt(0.2)
        return (hp(noise(0.2), 2) * np.exp(-x * 60) + np.sin(2 * np.pi * 900 * x) * np.exp(-x * 50) * 0.5) * vol

    def skate(dur=1.2, vol=0.2):
        x = tt(dur)
        return hp(lp(noise(dur), 3), 30) * (0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 2.2 * x))) * np.sin(np.pi * x / dur) * vol

    def whoosh(dur=0.4, vol=0.4):
        x = tt(dur)
        return hp(lp(noise(dur), 6), 40) * np.sin(np.pi * x / dur) ** 2 * vol

    def rewind(dur=0.5, vol=0.35):
        x = tt(dur)
        f = 300 + 2200 * (x / dur) ** 2
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * x / dur) * vol + hp(noise(dur), 3) * 0.1 * vol

    def boom(vol=0.8):
        x = tt(0.8)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(55 + 90 * np.exp(-x * 12)) / SR) * np.exp(-x * 4) * 3) * vol

    roots = [55.0, 55.0, 65.41, 49.0]
    for k8 in range(int(DUR / (B / 2))):
        tb = k8 * B / 2
        b = k8 / 2
        pos = b % 4
        if tb > DUR - 0.4 or T_RW0 <= tb < T_RW1:
            continue
        hook = tb < T_UP0
        if pos in (0.0, 2.5) or (pos == 1.5 and not hook):
            put_(mus, kick(0.75 if hook else 1.0), tb)
        if pos in (1.0, 3.0) and not hook:
            put_(mus, clap(0.8), tb)
        if not hook:
            put_(mus, hat(0.1 if k8 % 2 == 0 else 0.06), tb, pan=0.3)
        if pos == 0.0:
            put_(mus, sub(roots[int(b // 4) % 4], 2.6 * B), tb)
    put_(sfx, whoosh(0.5, 0.35), T_UP0)
    put_(sfx, skate(T_TOUCH - T_GO, 0.25), T_GO)
    put_(sfx, puck_hit(0.6), T_TOUCH)
    put_(sfx, whistle(0.6, 0.55), T_WH)
    put_(sfx, boom(0.8), T_2MIN)
    put_(sfx, rewind(T_RW1 - T_RW0, 0.4), T_RW0)
    put_(sfx, puck_hit(0.8), T_SHOT)
    put_(sfx, horn(1.2, 0.45), T_GOAL)
    put_(sfx, crowd(2.0, 0.45), T_GOAL)
    put_(sfx, whoosh(0.5, 0.35), T_DN0)
    voice = np.zeros(n)
    for k in VO_KEYS:
        tmp = os.path.join(HERE, f"_vo_{k}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "voice", f"reel36_{k}.wav"),
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
    duck = 1 - 0.75 * np.clip(venv / 0.06, 0, 1)
    sduck = 1 - 0.55 * np.clip(venv / 0.06, 0, 1)
    mus /= np.max(np.abs(mus)) + 1e-9
    sfx /= np.max(np.abs(sfx)) + 1e-9
    mix = mus * 0.36 * duck[:, None] + sfx * 0.5 * sduck[:, None] + voice[:, None] * 1.0
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
    tts_kokoro.synth(VO_LINES, os.path.join(HERE, "voice", "reel36"), speed=1.25)


def check_vo():
    with open(os.path.join(HERE, "voice", "reel36_timing.json")) as f:
        vo_dur = {k: v / TEMPO for k, v in json.load(f).items()}
    for i, k in enumerate(VO_KEYS):
        nxt = VO_START[VO_KEYS[i + 1]] if i + 1 < len(VO_KEYS) else DUR - 0.2
        if VO_START[k] + vo_dur[k] > nxt + 0.3:
            print(f"Warnung: Satz {k} zu lang ({VO_START[k] + vo_dur[k]:.2f} > {nxt:.2f})")


def remux():
    os.chdir(HERE)
    make_audio("audio_goalie_line.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "reel36_goalie_line.mp4", "-i", "audio_goalie_line.wav",
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-af",
                    "loudnorm=I=-14:TP=-1.0:LRA=9", "-ar", "44100", "-shortest", "-movflags", "+faststart",
                    "_tmp_gl.mp4"], check=True)
    os.replace("_tmp_gl.mp4", "reel36_goalie_line.mp4")


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
    make_audio("audio_goalie_line.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_goalie_line.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
           "-ar", "44100", "-shortest", "-movflags", "+faststart", "reel36_goalie_line.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(0.9, 9999)).save("reel36_thumbnail.jpg", quality=92)
    print("fertig: reel36_goalie_line.mp4")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "vo":
        make_voice()
    elif len(sys.argv) > 1 and sys.argv[1] == "audio":
        remux()
    elif len(sys.argv) > 1 and sys.argv[1] == "prev":
        preview(sys.argv[2].split(","), sys.argv[3])
    else:
        main()
