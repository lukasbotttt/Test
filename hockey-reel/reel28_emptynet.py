"""Reel 28: NHL RULES EXPLAINED – PART 5: WHY DID THE GOALIE LEAVE THE NET? (Empty Net, 3D-Erklärvideo, 15,8 s).

Fakten:
- Liegt ein Team spät hinten, holt es den Goalie für einen zusätzlichen Feldspieler vom Eis ("extra attacker",
  6 gegen 5). Risiko: Tor ins leere Netz (Empty-Net-Goal).
- Asness & Brown (2018), "Pulling the Goalie: Hockey and Investment Implications" (SSRN 3132563, Daten NHL 2015–16):
  bei einem Tor Rückstand ab 5:40 Restzeit ("The crossover point comes at 5:40 remaining"), bei zwei Toren ab 11:40;
  üblich war damals die letzte Minute ("not the 1+ minute mark common in the NHL").
- Später möglich: NHL-Regel 25 / Tabelle 12 (zugesprochenes Tor bei leerem Netz), Regel 15.1 + 78.5 (xi)
  (Goalie raus bei angezeigter Strafe).
Bilder: Bande, Glas, Spielerbank und beide Tore als 3D-Gitter (mesh3d), Eis + Puck (Raytracer), Spieler nur als
Marker ("G" = Goalie, "+1" = zusätzlicher Feldspieler). Bewusst ohne Spielerkörper.
Stimme: Kokoro "Michael" (tts_kokoro.py, Apache-2.0), Sätze einzeln, 1,08x.
Aufruf: python3 reel28_emptynet.py vo   -> voice/reel28_*.wav
        python3 reel28_emptynet.py audio -> nur Ton neu mischen
        python3 reel28_emptynet.py      -> reel28_emptynet.mp4
"""
import json
import math
import os
import subprocess
import sys
import time
import wave

import numpy as np
from PIL import Image, ImageDraw

import puck3d as P3
import reel15_puck as R15
import reel18_dangle as R18
import mesh3d as M3
import reel25_goalline as G
import reel26_overglass as R26
from reel15_puck import (W, H, FPS, SPP, KSUB, SHUTTER, c01, smooth, sio, e_out, e_in, lerp, blend_up, line_img,
                         reveal, put, proj, projected, px_per_in, stroke_poly, surface, surf_rgba, over)
from reel22_trapezoid import fill_poly, puck_marker, whistle_ring, slam
from reel18_dangle import vignette

HERE = R15.HERE
INK, ORANGE = R15.INK, R15.ORANGE
RED = (225, 30, 40)
BLUE = (40, 110, 210)
GREY = (110, 114, 126)
HALO = (255, 255, 255)
TEMPO = 1.08

# ================================================================= Timeline aus dem Voiceover
VO_LINES = [
    ("q", "Why did the goalie just leave the net?"),
    ("down", "His team is down one goal, two minutes left."),
    ("six", "He goes to the bench, and an extra skater jumps on. Six against five."),
    ("risk", "The catch? Lose the puck, and it's an empty-net goal."),
    ("math", "But one study says: pull him with almost six minutes left!"),
    ("cta", "When would YOU pull him?"),
]
VO_KEYS = [k for k, _ in VO_LINES]
VO_START = {"q": 0.15, "down": 1.85, "six": 4.35, "risk": 8.15, "math": 10.75, "cta": 13.75}
DUR = 15.8


def load_vo_dur():
    with open(os.path.join(HERE, "voice", "reel28_timing.json")) as f:
        return {k: v / TEMPO for k, v in json.load(f).items()}


def at(key, s):
    """Zeitpunkt s Sekunden nach Satzbeginn (im fertigen, 1,08x schnelleren Satz)."""
    return VO_START[key] + s


T_UP0, T_UP1 = 1.55, 2.85              # Hook am leeren Tor -> Draufsicht
T_GOALW = at("down", 1.0)              # "one goal"
T_CLOCK = at("down", 1.58)             # "two minutes"
T_BENCH = at("six", 0.52)              # Goalie an der Bank
T_JUMP = at("six", 1.80)               # "+1" springt aufs Eis
T_OFF0, T_OFF1 = 5.55, 7.25            # Schwenk ins Angriffsdrittel
T_SIX = at("six", 2.81)                # "Six"
T_FIVE = at("six", 3.33)               # "five"
T_LOSE = at("risk", 0.40)              # "lose the puck" – Pass abgefangen
T_SHOT = T_LOSE + 0.22
T_GOAL = at("risk", 1.62)              # Puck im leeren Tor ("empty-net")
T_DN0, T_DN1 = 10.4, 11.35             # zurück ans leere Tor
T_SAYS = at("math", 0.62)              # "says" -> Rückspulen
T_PULL = at("math", 1.22)              # "pull him"
T_540 = at("math", 1.76)               # "six minutes" -> 5:40
T_CTA = VO_START["cta"]

# ================================================================= Geometrie (Zoll)
BH, GH = R26.BH, R26.GH
SZ = R26.SZ
BENCHES = R26.BENCHES                  # eigene Bank = BENCHES[0] (im 3. Drittel neben dem eigenen Tor)
OWN_X = -G.GOAL_X                      # eigenes Tor (leer) bei x = -1068
NET_IN = np.array([OWN_X - 22.0, 0.5, 4.0])


def wall_path():
    """Innenkante der Bande, ganze Eisfläche (geschlossen)."""
    pts = [(x, SZ) for x in np.linspace(864.0, -864.0, 60)]
    for cx, cz, a0, a1 in ((-864.0, 174.0, 90, 180), (-864.0, -174.0, 180, 270), (864.0, -174.0, 270, 360),
                           (864.0, 174.0, 0, 90)):
        seg_ = []
        for a in np.linspace(a0, a1, 22)[1:]:
            r = math.radians(a)
            seg_.append((cx + 336.0 * math.cos(r), cz + 336.0 * math.sin(r)))
        pts += seg_
        if a1 == 180:
            pts += [(-1200.0, z) for z in np.linspace(174.0, -174.0, 12)[1:]]
        elif a1 == 270:
            pts += [(x, -SZ) for x in np.linspace(-864.0, 864.0, 60)[1:]]
        elif a1 == 360:
            pts += [(1200.0, z) for z in np.linspace(-174.0, 174.0, 12)[1:]]
    return np.array(pts)


WALL = wall_path()
WALL_N = R26.inward(WALL)


def boards_meshes():
    p = np.stack([WALL[:, 0], np.zeros(len(WALL)), WALL[:, 1]], 1)
    n3 = np.stack([WALL_N[:, 0], np.zeros(len(WALL_N)), WALL_N[:, 1]], 1)
    out = [R26.strip(p, p + [0, BH, 0], n3, "board_white")]
    k0 = p + n3 * 0.12
    out.append(R26.strip(k0, k0 + [0, 9.0, 0], n3, "kick_yellow"))
    out.append(R26.strip(p + [0, BH, 0], p + [0, BH, 0] - n3 * 5.0, np.tile([0.0, 1.0, 0.0], (len(p), 1)),
                         "board_white"))
    rail = p + [0, BH + 0.6, 0] - n3 * 2.5
    out.append(M3.tube_along(rail, np.full(len(rail), 1.3), lambda u: M3.MAT_IDS["rail"], nr=10))
    for x0, x1 in BENCHES:
        out.append(R26.box_mesh(x0 + 12, x1 - 12, 0.0, 17.0, SZ + 22, SZ + 40, "bench_seat"))
        wp = np.array([[x, 0.0, SZ + 62] for x in np.linspace(x0, x1, 8)])
        out.append(R26.strip(wp, wp + [0, BH, 0], np.tile([0.0, 0.0, -1.0], (8, 1)), "board_white"))
        for xs in (x0, x1):
            side = np.array([[xs, 0.0, z] for z in np.linspace(SZ + 4, SZ + 62, 4)])
            out.append(R26.strip(side, side + [0, BH, 0], np.tile([1.0 if xs == x0 else -1.0, 0.0, 0.0], (4, 1)),
                                 "board_white"))
    return out


def glass_panels():
    out = []
    seg_ = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(WALL, axis=0), axis=1))])
    marks = np.arange(0, seg_[-1], 60.0)
    xs, zs = np.interp(marks, seg_, WALL[:, 0]), np.interp(marks, seg_, WALL[:, 1])
    nx, nz = np.interp(marks, seg_, WALL_N[:, 0]), np.interp(marks, seg_, WALL_N[:, 1])
    for i in range(len(marks) - 1):
        a = np.array([xs[i] - nx[i] * 1.5, BH, zs[i] - nz[i] * 1.5])
        b = np.array([xs[i + 1] - nx[i + 1] * 1.5, BH, zs[i + 1] - nz[i + 1] * 1.5])
        if R26.in_bench((a[0] + b[0]) / 2, (a[2] + b[2]) / 2):
            continue
        out.append(np.array([a, b, b + [0, GH, 0], a + [0, GH, 0]]))
    for x0, x1 in BENCHES:
        out.append(np.array([[x0, BH, SZ + 62], [x1, BH, SZ + 62], [x1, BH + GH, SZ + 62], [x0, BH + GH, SZ + 62]]))
    return out


BOARDS = boards_meshes()
GLASS = glass_panels()
GLASS_ALL = np.concatenate(GLASS)
FRAMES = G.FRAME + [R26.mirror_x(m) for m in G.FRAME]
NET_MESH = R15.net_lines(-1.0)[0]
NETS = NET_MESH + [pl * [-1, 1, 1] for pl in NET_MESH]

# ================================================================= Marker (Spieler) + Puck
A_POS = [np.array(v) for v in ((985.0, 0.0, -300.0), (870.0, 0.0, 255.0), (530.0, 0.0, -270.0),
                               (505.0, 0.0, 215.0), (1000.0, 0.0, 40.0))]
D_POS = [np.array(v) for v in ((935.0, 0.0, -205.0), (905.0, 0.0, 175.0), (775.0, 0.0, -140.0),
                               (760.0, 0.0, 120.0), (690.0, 0.0, 125.0))]
RG_POS = np.array([1048.0, 0.0, 0.0])                    # gegnerischer Goalie
PLUS_END = np.array([725.0, 0.0, -40.0])                 # "+1" im Slot
INTER = A_POS[3] + (PLUS_END - A_POS[3]) * 0.55          # hier wird der Pass abgefangen
G_P0, G_P1, G_P2 = np.array([OWN_X + 54.0, 0.0, 0.0]), np.array([-880.0, 0.0, 360.0]), np.array([-150.0, 0.0, 468.0])
PLUS_P0, PLUS_P1 = np.array([-150.0, 0.0, 470.0]), np.array([300.0, 0.0, 300.0])


def bez(p0, p1, p2, u):
    return (1 - u) ** 2 * p0 + 2 * (1 - u) * u * p1 + u * u * p2


def drift(p, k, t, amp=12.0):
    return p + np.array([amp * math.sin(1.3 * t + 1.7 * k), 0.0, amp * math.cos(1.1 * t + 2.3 * k)])


def goalie_state(t):
    """(Position, Deckkraft) des eigenen Goalies."""
    if t < T_SAYS - 0.15:
        u = c01((t + 0.15) / (T_BENCH + 0.15))
        u = 0.5 * (u ** 1.6) + 0.5 * sio(u)
        p = bez(G_P0, G_P1, G_P2, u)
        if t > T_BENCH:                                                  # durch die Tür auf die Bank
            p = p + np.array([0.0, 0.0, 70.0]) * e_in(c01((t - T_BENCH) / 0.35), 2)
        return p, 1 - smooth(T_BENCH + 0.1, T_BENCH + 0.35, t)
    u = 0.6 * c01((t - T_540) / 3.8) ** 1.4                             # Rückspulen: wieder im Tor, geht erneut
    return bez(G_P0, G_P1, G_P2, u), smooth(T_SAYS - 0.15, T_SAYS + 0.15, t)


def plus_state(t):
    if t < T_JUMP:
        return PLUS_P0, 0.0
    u = sio(c01((t - T_JUMP) / 1.25))
    p = bez(PLUS_P0, PLUS_P1, PLUS_END, u)
    return drift(p, 7, t, 10.0 * u), 1 - smooth(T_DN0, T_DN0 + 0.3, t)


def attackers(t):
    return [drift(p, k, t) for k, p in enumerate(A_POS)]


def defenders(t):
    out = [drift(p, k + 5, t) for k, p in enumerate(D_POS)]
    s = sio(c01((t - (T_LOSE - 0.45)) / 0.45))                          # D5 läuft in den Pass
    out[4] = out[4] + (INTER + np.array([4.0, 0.0, 10.0]) - out[4]) * s
    return out


def stick(p, toward):
    d = toward - p
    d[1] = 0.0
    return p + d / (np.linalg.norm(d) + 1e-9) * 22.0 + np.array([0.0, 0.5, 0.0])


def pass_(a, b, t0, t1, t):
    u = c01((t - t0) / (t1 - t0))
    return a + (b - a) * (1 - (1 - u) ** 1.4)


def puck_state(t):
    """(Position, sichtbar)"""
    A = attackers(t)
    if t < 6.25:
        return stick(A[0], A[2]), 1.0
    if t < 6.6:
        return pass_(stick(A[0], A[2]), stick(A[2], A[0]), 6.25, 6.6, t), 1.0
    if t < 7.35:
        return stick(A[2], A[3]), 1.0
    if t < 7.7:
        return pass_(stick(A[2], A[3]), stick(A[3], A[2]), 7.35, 7.7, t), 1.0
    if t < T_LOSE - 0.32:
        return stick(A[3], PLUS_END), 1.0
    if t < T_LOSE:
        return pass_(stick(A[3], PLUS_END), INTER + np.array([0, 0.5, 0]), T_LOSE - 0.32, T_LOSE, t), 1.0
    if t < T_SHOT:
        return INTER + np.array([0, 0.5, 0]), 1.0
    if t < T_DN0:
        u = c01((t - T_SHOT) / (T_GOAL - T_SHOT))
        p0 = INTER + np.array([0, 0.5, 0])
        return p0 + (NET_IN - p0) * (1 - (1 - u) ** 1.25), 1.0
    return NET_IN, 0.0


def puck_rot(t):
    return 1.3 + 7.0 * t


# ================================================================= Kamera
HOOK_P0 = np.array([float(v) for v in os.environ.get("HPOS", "-1185,345,-40").split(",")])
HOOK_T = np.array([float(v) for v in os.environ.get("HTGT", "-930,0,30").split(",")])
HOOK_FOV = float(os.environ.get("HFOV", "46"))
HOOK_PUSH = np.array([18.0, -8.0, 4.0])
FULL_X, FULL_H = -60.0, 4800.0
OFF_X, OFF_H = 700.0, 2750.0
NETV_X, NETV_H = -740.0, 2900.0


def hook_cam(t):
    return HOOK_P0 + HOOK_PUSH * e_out(c01(t / T_UP0), 2), HOOK_T, HOOK_FOV


def top_cam(x, h, fov=30.0):
    return np.array([x - 0.02 * h, h, 0.0]), np.array([x, 0.0, 0.0]), fov


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


def end_cam(t):
    """Am leeren Tor nach dem Rückweg: gleitet zurück ins Anfangsbild (Loop)."""
    u = c01((t - T_DN1) / (DUR - T_DN1))
    return hook_cam(T_UP0 * (1 - sio(u)))


def cam(t):
    if t < T_UP0:
        p, g, f = hook_cam(t)
    elif t < T_UP1:
        p, g, f = blend_cam(hook_cam(T_UP0), top_cam(FULL_X, FULL_H), sio((t - T_UP0) / (T_UP1 - T_UP0)))
    elif t < T_OFF0:
        p, g, f = top_cam(FULL_X, FULL_H)
    elif t < T_SHOT:
        s = sio(c01((t - T_OFF0) / (T_OFF1 - T_OFF0)))
        p, g, f = top_cam(lerp(FULL_X, OFF_X, s), math.exp(lerp(math.log(FULL_H), math.log(OFF_H), s)))
    elif t < T_DN0:
        s = sio(c01((t - T_SHOT + 0.05) / (T_GOAL - T_SHOT + 0.15)))
        hh = lerp(OFF_H, NETV_H, s) + 500 * math.sin(math.pi * s)
        p, g, f = top_cam(lerp(OFF_X, NETV_X, s), hh - 260 * e_out(c01((t - T_GOAL) / 0.5), 3))
    elif t < T_DN1:
        p, g, f = blend_cam(top_cam(NETV_X, NETV_H - 260), end_cam(T_DN1), sio((t - T_DN0) / (T_DN1 - T_DN0)))
    else:
        p, g, f = end_cam(t)
    d = (p - g) / np.linalg.norm(p - g)
    el = math.degrees(math.asin(max(-1.0, min(1.0, d[1]))))
    return p, g, blend_up(min(el, 89.9)), f


def cam_row_at(t):
    pos, tgt, up, fov = cam(t)
    r, u, f = P3.look_at(pos, tgt, up)
    return P3.cam_row(pos, r, u, f, fov), float(np.linalg.norm(tgt - pos))


def seg(t):
    for a, b in ((0.0, T_LOSE), (T_LOSE, T_SHOT), (T_SHOT, T_DN0), (T_DN0, DUR)):
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
    P3.render(W, H, SPP, fidx + 28, cams, lens, pk, R15.logo_tex(), base, puck, cov)
    return P3.tonemap(base), P3.tonemap(puck), cov


# ================================================================= Overlays
def draw_net_lines(ctx, row):
    for pl in NETS:
        xy, z = proj(row, pl)
        if (z < 2).any():
            continue
        stroke_poly(ctx, xy, (112, 120, 136), 0.55, float(np.clip(0.4 * px_per_in(row, z.mean()), 0.8, 3.0)))


def glass_edges(ctx, row):
    for q in GLASS:
        xy, z = proj(row, q)
        if (z < 3).any():
            continue
        w = float(np.clip(px_per_in(row, z.mean()) * 0.8, 0.8, 5))
        stroke_poly(ctx, xy[[0, 3]], (190, 198, 210), 0.65, w)
        stroke_poly(ctx, xy[[2, 3]], (250, 252, 255), 0.95, w * 1.6)
        stroke_poly(ctx, xy[[2, 3]], (170, 180, 196), 0.5, w * 0.5)


CIRC = np.stack([np.cos(np.linspace(0, 2 * math.pi, 49)), np.zeros(49), np.sin(np.linspace(0, 2 * math.pi, 49))], 1)


def disc(ctx, row, p, col, a=1.0, r_px=(24, 64), r_in=30.0, ring=None, scale=1.0):
    """Spielermarker als Scheibe auf dem Eis (perspektivisch), Pixelgröße begrenzt. Gibt (Mitte, Radius px) zurück."""
    if a <= 0:
        return None
    c, z = projected(row, p + np.array([0, 0.2, 0]))
    if z <= 2:
        return None
    k = px_per_in(row, z)
    r = float(np.clip(k * r_in, *r_px)) / k * scale
    xy, zz = proj(row, p + np.array([0, 0.2, 0]) + CIRC * r)
    if (zz < 2).any():
        return None
    ctx.set_source_rgba(0, 0, 0, 0.13 * a)
    ctx.move_to(*(xy[0] + [3, 6]))
    for q in xy[1:]:
        ctx.line_to(*(q + [3, 6]))
    ctx.close_path()
    ctx.fill()
    ctx.set_source_rgba(1, 1, 1, a)
    ctx.move_to(*xy[0])
    for q in xy[1:]:
        ctx.line_to(*q)
    ctx.close_path()
    ctx.fill_preserve()
    rc = ring or col
    rp = r * k
    ctx.set_source_rgba(rc[0] / 255, rc[1] / 255, rc[2] / 255, a)
    ctx.set_line_width(max(3.0, rp * 0.2))
    ctx.stroke()
    return c, rp


def letter(L, c_r, txt, col, a=1.0, k=0.95):
    if c_r is None or a <= 0:
        return
    c, rp = c_r
    im = line_img(txt, max(10, int(rp * k)), 900, col)
    if a < 1:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    put(L, im, c[0] - im.width / 2, c[1] - im.height / 2)


def pulse_ring(ctx, c_r, col, t, t0, dur=0.6):
    if c_r is None:
        return
    li = t - t0
    if not 0 <= li < dur:
        return
    c, rp = c_r
    q = e_out(li / dur, 3)
    ctx.set_source_rgba(col[0] / 255, col[1] / 255, col[2] / 255, 0.9 * (1 - q))
    ctx.set_line_width(8 * (1 - q) + 2)
    ctx.arc(c[0], c[1], rp * (1.2 + 2.2 * q), 0, 2 * math.pi)
    ctx.stroke()


def badge(L, c_r, n, col, a):
    if c_r is None or a <= 0:
        return
    c, rp = c_r
    im = R18.word_img(str(n), 54, col, HALO)
    if a < 1:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    put(L, im, c[0] - im.width / 2, c[1] - rp - 34 - im.height / 2)


def crease_ring(ctx, row, a, t):
    if a <= 0:
        return
    pts = np.array([OWN_X + 42.0, 0.15, 0.0]) + CIRC * [52.0, 0, 64.0]
    xy, z = proj(row, pts)
    if (z < 2).any():
        return
    ctx.set_source_rgba(ORANGE[0] / 255, ORANGE[1] / 255, ORANGE[2] / 255, 0.95 * a)
    ctx.set_line_width(8)
    ctx.set_dash([28, 18], -t * 70)
    ctx.move_to(*xy[0])
    for q in xy[1:]:
        ctx.line_to(*q)
    ctx.stroke()
    ctx.set_dash([])


def path_line(ctx, row, pts, col, a, width=6, dash=None, t=0.0):
    if a <= 0 or len(pts) < 2:
        return
    xy, z = proj(row, np.asarray(pts))
    if (z < 3).any():
        return
    if dash:
        ctx.set_dash(dash, -t * 80)
    stroke_poly(ctx, xy, col, 0.2 * a, width * 3.2)
    stroke_poly(ctx, xy, col, 0.9 * a, width)
    ctx.set_dash([])


def label_at(L, row, p, txt, col, dx, dy, a, size=40):
    if a <= 0:
        return
    xy, z = projected(row, p)
    if z <= 0:
        return
    im = line_img(txt, size, 850, col, track=4)
    reveal(L, im, min(max(xy[0] + dx, 40 + im.width / 2), W - 40 - im.width / 2), xy[1] + dy, a)


# ---------------- Anzeigetafel
def clock_s(t):
    if t < T_CLOCK:
        return 120.0
    if t < T_SAYS:
        return 120.0 - min(t, T_DN0) + T_CLOCK
    u = e_in(c01((t - T_SAYS) / (T_540 - T_SAYS)), 2)
    c0 = 120.0 - T_DN0 + T_CLOCK
    return c0 + (340.0 - c0) * u if t < T_540 else 340.0 - max(0.0, t - T_540)


def fmt(sec):
    s = int(math.ceil(sec - 1e-6))
    return f"{s // 60}:{s % 60:02d}"


_BUG = {}


def bug_img(sa, sb, clock, ccol, ha, hb, period="3RD"):
    key = (sa, sb, clock, ccol, round(ha, 2), round(hb, 2), period)
    if key in _BUG:
        return _BUG[key]
    w, h = 640, 118
    im = Image.new("RGBA", (w + 40, h + 50), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((24, 30, 20 + w, 26 + h), 30, fill=(0, 0, 0, 34))
    d.rounded_rectangle((20, 20, 20 + w, 20 + h), 30, fill=(255, 255, 255, 250), outline=(214, 218, 226, 255), width=3)
    for i, (num, col, hl) in enumerate(((sa, BLUE, ha), (sb, RED, hb))):
        x0 = 44 + i * 150
        grow = int(8 * hl)
        d.rounded_rectangle((x0 - grow, 36 - grow, x0 + 104 + grow, 122 + grow), 22, fill=col + (255,))
        n_im = line_img(str(num), 66, 900, (255, 255, 255))
        im.alpha_composite(n_im, (x0 + 52 - n_im.width // 2, 79 - n_im.height // 2))
    c_im = line_img(":", 54, 900, INK)
    im.alpha_composite(c_im, (44 + 127 - c_im.width // 2, 76 - c_im.height // 2))
    d.line((368, 44, 368, 114), fill=(214, 218, 226, 255), width=3)
    p_im = line_img(period, 30, 800, GREY, track=3)
    im.alpha_composite(p_im, (392, 79 - p_im.height // 2))
    k_im = line_img(clock, 64, 900, ccol)
    im.alpha_composite(k_im, (636 - k_im.width, 79 - k_im.height // 2))
    _BUG[key] = im
    return im


def scoreboard(L, t):
    a = smooth(at("down", 0.25), at("down", 0.5), t)
    if a <= 0:
        return
    sb = 3 if T_GOAL <= t < T_SAYS else 2
    hb = math.exp(-max(0.0, t - T_GOAL) * 5) if T_GOAL <= t < T_SAYS else 0.0
    ha = math.exp(-max(0.0, t - T_GOALW) * 5) if t >= T_GOALW else 0.0
    if T_540 <= t:
        ccol = ORANGE
    else:
        ccol = INK
    im = bug_img(1, sb, fmt(clock_s(t)), ccol, ha, hb)
    pc = math.exp(-max(0.0, t - T_CLOCK) * 6) if t >= T_CLOCK else 0.0
    pc += math.exp(-max(0.0, t - T_540) * 6) if t >= T_540 else 0.0
    sc = 1.0 + 0.06 * pc
    if sc > 1.001:
        im = im.resize((int(im.width * sc), int(im.height * sc)), Image.BILINEAR)
    reveal(L, im, W / 2, 205, a)


# ---------------- Texte
def lines2(L, rows, k):
    for txt, cy, size, col in rows:
        im = R18.word_img(txt, size, col, HALO)
        if k < 1:
            im = im.copy()
            im.putalpha(im.getchannel("A").point(lambda v: int(v * k)))
        put(L, im, W / 2 - im.width / 2, cy - im.height / 2)


def texts(L, t, row):
    if t < T_UP0 + 0.1:
        k = 1 - smooth(T_UP0 - 0.1, T_UP0 + 0.1, t)
        lines2(L, [("WHY DID THE", 470, 128, INK), ("GOALIE LEAVE", 610, 128, INK), ("THE NET?", 770, 178, RED)], k)
        reveal(L, line_img("NHL RULES EXPLAINED  ·  PART 5", 34, 800, ORANGE, track=8), W / 2, 350, 1.0,
               smooth(T_UP0 - 0.15, T_UP0 + 0.05, t))
    scoreboard(L, t)
    gp, ga = goalie_state(t)
    if T_UP1 - 0.3 < t < T_BENCH:
        label_at(L, row, gp, "GOALIE", BLUE, 0, -70, smooth(T_UP1 - 0.3, T_UP1, t) * (1 - smooth(T_BENCH - 0.3, T_BENCH - 0.1, t)), 38)
    if T_BENCH - 0.1 < t < T_OFF0 + 0.4:
        label_at(L, row, np.array([-150.0, 0, 380.0]), "BENCH", INK, 0, 0,
                 smooth(T_BENCH - 0.1, T_BENCH + 0.1, t) * (1 - smooth(T_OFF0, T_OFF0 + 0.3, t)), 40)
    pp, pa = plus_state(t)
    if T_JUMP < t < T_SIX:
        label_at(L, row, pp, "EXTRA SKATER", ORANGE, 0, -84, smooth(T_JUMP, T_JUMP + 0.15, t) * (1 - smooth(T_SIX - 0.2, T_SIX, t)), 36)
    slam(L, "6", 260, BLUE, W / 2 - 230, 1460, t, T_SIX, T_LOSE)
    slam(L, "VS", 110, INK, W / 2, 1480, t, T_FIVE - 0.12, T_LOSE)
    slam(L, "5", 260, RED, W / 2 + 230, 1460, t, T_FIVE, T_LOSE)
    if T_LOSE <= t < T_GOAL:
        label_at(L, row, INTER, "TURNOVER", RED, 0, 100, smooth(T_LOSE, T_LOSE + 0.12, t) * (1 - smooth(T_GOAL - 0.2, T_GOAL, t)), 40)
    slam(L, "EMPTY NET", 150, RED, W / 2, 640, t, T_GOAL, T_DN0 + 0.2)
    slam(L, "GOAL.", 200, RED, W / 2, 800, t, T_GOAL + 0.18, T_DN0 + 0.2)
    if T_SAYS - 0.1 <= t < T_CTA:
        p_out = smooth(T_CTA - 0.2, T_CTA, t)
        reveal(L, line_img("ONE STUDY SAYS:", 48, 850, INK, track=6), W / 2, 400, c01((t - T_SAYS + 0.1) / 0.25), p_out)
        if t >= T_PULL:
            reveal(L, line_img("PULL HIM WITH", 48, 850, INK, track=6), W / 2, 478, c01((t - T_PULL) / 0.25), p_out)
        if t >= T_540 + 0.25:
            reveal(L, line_img("LEFT  ·  DOWN BY ONE GOAL", 44, 850, INK, track=5), W / 2, 820,
                   c01((t - T_540 - 0.25) / 0.25), p_out)
            reveal(L, line_img("ASNESS & BROWN (2018), NHL DATA 2015–16", 26, 700, GREY, track=3), W / 2, 885,
                   c01((t - T_540 - 0.35) / 0.25), p_out)
    slam(L, "5:40", 270, ORANGE, W / 2, 650, t, T_540, T_CTA)
    if t >= T_CTA:
        slam(L, "WHEN WOULD YOU", 112, INK, W / 2, 470, t, T_CTA)
        slam(L, "PULL HIM?", 170, ORANGE, W / 2, 630, t, at("cta", 0.5))
        if t >= at("cta", 0.9):
            reveal(L, line_img("COMMENT YOUR TIME  ·  FOLLOW FOR PART 6", 32, 800, INK, track=6), W / 2, 1300,
                   c01((t - at("cta", 0.9)) / 0.25))


# ================================================================= Bild
def compose(t, fidx):
    base, puck, cov = render3d(t, fidx)
    row, _ = cam_row_at(t)
    campos = cam(t)[0]
    p, vis = puck_state(t)
    lo_s, lo_c = surface()
    hi_s, hi_c = surface()
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_net_lines(lo_c, row)
    glass_edges(lo_c, row)
    img = over(base, *surf_rgba(lo_s))
    meshes = BOARDS + FRAMES
    if vis > 0:
        meshes = meshes + [G.cyl_mesh(p - np.array([0, 0.5, 0]), 1.5, 1.0, "occluder", group=1)]
    m_rgb, m_a, shadow, plane_a = M3.render(meshes, row, W, H, campos, alpha_by_group=np.array([1.0, 0.0], np.float32),
                                            extra_planes=[(GLASS_ALL, 1.0)], shadow_light=(0.02, 1.0, -0.03))
    img = img * (1 - 0.15 * shadow[..., None])
    pa = cov[..., None]
    img = img * (1 - pa) + puck * pa
    img = img * (1 - m_a[..., None]) + m_rgb
    k = (0.30 * plane_a)[..., None]
    img = img * (1 - k) + np.array([0.70, 0.82, 0.94], np.float32) * k
    img = img + (R26.glass_streaks() * plane_a * 0.10)[..., None]

    # Markierungen auf dem Eis
    crease_ring(hi_c, row, smooth(0.25, 0.45, t) * (1 - smooth(T_UP0 - 0.2, T_UP0, t)), t)
    crease_ring(hi_c, row, smooth(T_GOAL, T_GOAL + 0.15, t) * (1 - smooth(T_DN0 + 0.1, T_DN0 + 0.3, t)), t)
    gp, ga = goalie_state(t)
    if t < T_BENCH + 0.35:                                                   # Weg des Goalies
        us = np.linspace(0, 1, 40)
        path_line(hi_c, row, [bez(G_P0, G_P1, G_P2, u) + [0, 0.1, 0] for u in us], BLUE,
                  0.8 * smooth(0.4, 0.8, t) * (1 - smooth(T_BENCH, T_BENCH + 0.3, t)), 5, [20, 16], t)
    team_a = smooth(T_UP1 - 0.6, T_UP1, t) * (1 - smooth(T_DN0, T_DN0 + 0.3, t))
    A, D = attackers(t), defenders(t)
    cr_a, cr_d = [], []
    for q in A:
        cr_a.append(disc(hi_c, row, q, BLUE, team_a))
    for q in D:
        cr_d.append(disc(hi_c, row, q, RED, team_a))
    cr_rg = disc(hi_c, row, drift(RG_POS, 11, t, 4.0), RED, team_a)
    if T_LOSE - 0.32 <= t < T_GOAL + 0.4:                                   # Pass + Schuss
        if t < T_SHOT:
            path_line(hi_c, row, [stick(A[3], PLUS_END), PLUS_END + [0, 0.1, 0]], BLUE,
                      0.6 * (1 - smooth(T_LOSE, T_LOSE + 0.2, t)), 4, [16, 14], t)
        else:
            u1 = c01((t - T_SHOT) / (T_GOAL - T_SHOT))
            p0 = INTER + np.array([0, 0.5, 0])
            pts = [p0 + (NET_IN - p0) * (1 - (1 - u) ** 1.25) for u in np.linspace(0, u1, 40)]
            path_line(hi_c, row, pts, ORANGE, 1 - smooth(T_GOAL + 0.1, T_GOAL + 0.4, t), 6)
    pp, pa_ = plus_state(t)
    cr_p = disc(hi_c, row, pp, BLUE, pa_ * c01((t - T_JUMP) / 0.12), ring=ORANGE,
                scale=1 + 0.35 * math.exp(-max(0.0, t - T_JUMP) * 7))
    cr_g = disc(hi_c, row, gp, BLUE, ga, r_px=(26, 96), r_in=26.0)
    if vis > 0 and T_UP1 - 0.2 < t < T_GOAL + 0.3:
        puck_marker(hi_c, row, p, t)
    pulse_ring(hi_c, cr_g, BLUE, t, T_BENCH - 0.05)
    pulse_ring(hi_c, cr_p, ORANGE, t, T_JUMP)
    for i, c_r in enumerate(cr_a + [cr_p]):
        pulse_ring(hi_c, c_r, BLUE, t, T_SIX - 0.05 + 0.05 * i, 0.45)
    for i, c_r in enumerate(cr_d):
        pulse_ring(hi_c, c_r, RED, t, T_FIVE - 0.05 + 0.05 * i, 0.45)
    pulse_ring(hi_c, cr_d[4], RED, t, T_LOSE)
    if T_GOAL - 0.02 < t < T_GOAL + 0.6:
        xy, z = projected(row, np.array([OWN_X, 20.0, 0.0]))
        whistle_ring(hi_c, row, np.array([OWN_X, 20.0, 0.0]), t, T_GOAL, RED)
    img = over(img, *surf_rgba(hi_s))
    if T_GOAL <= t < T_GOAL + 0.35:
        a = 0.24 * (1 - (t - T_GOAL) / 0.35)
        img = img * (1 - a) + np.array([1.0, 0.1, 0.12], np.float32) * a
    img = np.clip(img, 0, 1)
    pil = Image.fromarray((img * 255).astype(np.uint8)).convert("RGBA")
    letter(L, cr_g, "G", BLUE, ga)
    letter(L, cr_rg, "G", RED, team_a)
    letter(L, cr_p, "+1", ORANGE, pa_ * c01((t - T_JUMP) / 0.12), 0.8)
    na = (1 - smooth(T_LOSE - 0.15, T_LOSE, t))
    for i, c_r in enumerate(cr_a + [cr_p]):
        badge(L, c_r, i + 1, BLUE, c01((t - T_SIX - 0.05 * i) / 0.08) * na)
    for i, c_r in enumerate(cr_d):
        badge(L, c_r, i + 1, RED, c01((t - T_FIVE - 0.05 * i) / 0.08) * na)
    texts(L, t, row)
    pil.alpha_composite(L)
    arr = np.asarray(pil.convert("RGB")).astype(np.float32) / 255
    lc = min([t - c for c in (T_SIX, T_GOAL, T_540) if t >= c] + [t + 0.5])
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
    rng = np.random.default_rng(28)
    mus = np.zeros((n, 2))
    sfx = np.zeros((n, 2))
    B = 60 / 140

    def tt(sec):
        return np.arange(int(sec * SR)) / SR

    def put_(buf, sig, at_, vol=1.0, pan=0.0):
        st = int(round(at_ * SR))
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

    def slap(vol=0.6):
        x = tt(0.25)
        return (hp(noise(0.25), 2) * np.exp(-x * 60) * 0.8 + np.sin(2 * np.pi * 120 * x) * np.exp(-x * 25) * 0.6) * vol

    def tick(vol=0.3):
        x = tt(0.03)
        return np.sin(2 * np.pi * 2400 * x) * np.exp(-x * 220) * vol

    def whoosh(dur=0.7, vol=0.5):
        x = tt(dur)
        env = np.sin(np.pi * np.clip(x / dur, 0, 1)) ** 2
        return hp(lp(noise(dur), 6), 40) * env * vol

    def skate(dur=0.32, vol=0.3):
        x = tt(dur)
        env = np.sin(np.pi * np.clip(x / dur, 0, 1)) ** 1.5
        return hp(noise(dur), 3) * env * vol

    def click(vol=0.5):
        x = tt(0.08)
        return hp(noise(0.08), 1) * np.exp(-x * 120) * vol

    def ding(vol=0.4):
        x = tt(0.9)
        return (np.sin(2 * np.pi * 1318.5 * x) + 0.6 * np.sin(2 * np.pi * 1760 * x) * (x > 0.09)) * np.exp(-x * 5) * vol

    def horn(dur=1.6, vol=0.6):
        x = tt(dur)
        sig = np.zeros_like(x)
        for f0 in (155.6, 196.0, 233.1):
            ph = 2 * np.pi * f0 * x + 0.03 * np.sin(2 * np.pi * 5.5 * x)
            sig += sum(np.sin(ph * h) / h for h in range(1, 9))
        env = np.minimum(x / 0.05, 1) * np.clip((dur - x) / 0.35, 0, 1)
        return np.tanh(lp(sig, 4) * 0.6) * env * vol

    def rewind(dur=1.0, vol=0.4):
        x = tt(dur)
        f = 300 + 1500 * (x / dur) ** 2
        tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.6 + 0.4 * np.sin(2 * np.pi * 18 * x))
        env = np.sin(np.pi * np.clip(x / dur, 0, 1)) ** 1.2
        return (tone * 0.4 + hp(lp(noise(dur), 4), 30) * 0.6) * env * vol

    roots = [55.0, 43.65, 49.0, 41.2]
    mel = [880.0, 1046.5, 1318.5, 1046.5, 987.8, 880.0, 784.0, 659.25]
    for k8 in range(int(DUR / (B / 2))):
        tb = k8 * B / 2
        b = k8 / 2
        pos = b % 4
        if tb > DUR - 0.5:
            continue
        soft = tb < T_UP0 or T_SAYS <= tb < T_540                     # Hook + Rückspulen: nur Kick + Bass
        if pos in (0.0, 2.5):
            put_(mus, kick(0.7 if soft else 1.0), tb)
        if pos in (1.0, 3.0) and not soft:
            put_(mus, clap(), tb)
        if not soft:
            put_(mus, hat(0.12 if k8 % 2 == 0 else 0.07), tb, pan=0.3)
        if pos == 0.0:
            put_(mus, b808(roots[int(b // 4) % 4], 2.3 * B), tb)
        put_(mus, bell(mel[k8 % 8]), tb, pan=-0.2)
    for k in range(5):                                                     # Goalie fährt zur Bank
        put_(sfx, skate(0.3, 0.32), 0.05 + 0.42 * k, pan=0.4)
    put_(sfx, whoosh(T_UP1 - T_UP0 + 0.1, 0.45), T_UP0)
    put_(sfx, click(0.5), T_GOALW)
    put_(sfx, tick(0.5), T_CLOCK)
    put_(sfx, stamp(0.5), T_CLOCK)
    put_(sfx, click(0.6), T_BENCH)
    put_(sfx, ding(0.4), T_JUMP)
    put_(sfx, whoosh(T_OFF1 - T_OFF0, 0.35), T_OFF0)
    put_(sfx, slap(0.45), 6.25)
    put_(sfx, slap(0.45), 7.35)
    put_(sfx, stamp(0.9), T_SIX)
    put_(sfx, stamp(0.7), T_FIVE)
    put_(sfx, slap(0.4), T_LOSE - 0.32)
    put_(sfx, click(0.7), T_LOSE)
    put_(sfx, slap(0.8), T_SHOT)
    put_(sfx, whoosh(T_GOAL - T_SHOT, 0.5), T_SHOT)
    put_(sfx, horn(1.7, 0.6), at("risk", 2.3))                    # Hupe erst nach "goal" (sonst verdeckt sie den Satz)
    put_(sfx, stamp(1.0), T_GOAL)
    put_(sfx, whoosh(T_DN1 - T_DN0 + 0.1, 0.45), T_DN0)
    put_(sfx, rewind(T_540 - T_SAYS, 0.45), T_SAYS)
    put_(sfx, stamp(1.0), T_540)
    put_(sfx, ding(0.45), T_540)
    for k in range(3):
        put_(sfx, skate(0.3, 0.25), T_540 + 0.2 + 0.42 * k, pan=0.4)
    put_(sfx, stamp(0.7), at("cta", 0.5))
    voice = np.zeros(n)
    for k in VO_KEYS:
        tmp = os.path.join(HERE, f"_vo_{k}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "voice", f"reel28_{k}.wav"),
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
    sduck = 1 - 0.5 * np.clip(venv / 0.06, 0, 1)
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
    tts_kokoro.synth(VO_LINES, os.path.join(HERE, "voice", "reel28"), speed=1.2)


def remux():
    """Nur den Ton neu mischen und auf das fertige Bild legen."""
    os.chdir(HERE)
    make_audio("audio_emptynet.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "reel28_emptynet.mp4", "-i", "audio_emptynet.wav", "-map", "0:v",
                    "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
                    "-ar", "44100", "-shortest", "-movflags", "+faststart", "_tmp_emptynet.mp4"], check=True)
    os.replace("_tmp_emptynet.mp4", "reel28_emptynet.mp4")


def main():
    os.chdir(HERE)
    vo_dur = load_vo_dur()
    for i, k in enumerate(VO_KEYS[:-1]):
        nxt = VO_KEYS[i + 1]
        if VO_START[k] + vo_dur[k] > VO_START[nxt] + 0.35:
            print(f"Warnung: Satz {k} überlappt {nxt} ({VO_START[k] + vo_dur[k]:.2f} > {VO_START[nxt]:.2f})")
    make_audio("audio_emptynet.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_emptynet.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
           "-ar", "44100", "-shortest", "-movflags", "+faststart", "reel28_emptynet.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(0.9, 9999)).save("reel28_thumbnail.jpg", quality=92)
    print("fertig: reel28_emptynet.mp4")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "vo":
        make_voice()
    elif len(sys.argv) > 1 and sys.argv[1] == "audio":
        remux()
    else:
        main()
