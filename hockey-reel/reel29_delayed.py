"""Reel 29: NHL RULES EXPLAINED – PART 6: WHY DID THE GOALIE LEAVE IN THE 1ST PERIOD? (angezeigte Strafe, 15,9 s).

Fakten (NHL Official Rules 2023–24):
- Regel 15.1: Begeht das Team ohne Puck ein Foul, hebt der Schiedsrichter den Arm (angezeigte Strafe). Gepfiffen wird
  erst, wenn das zu bestrafende Team den Puck unter Kontrolle bringt.
- Regel 78.5 (xi): Während der angezeigten Strafe kann das bestrafte Team kein Tor erzielen – außer das andere Team
  schießt den Puck ins eigene Tor. Deshalb nimmt das gefoulte Team den Goalie für einen 6. Feldspieler raus.
- Eigentor-Beispiel: 21.03.2013 Hurricanes – Devils: Carolinas Goalie Dan Ellis fährt zur Bank, ein Pass von Jordan
  Staal rutscht ins leere Tor; gutgeschrieben wird es Devils-Goalie Martin Brodeur als letztem Devils-Spieler am Puck
  (erster Goalie mit 3 Karrieretoren; NBC Sports / Sports Illustrated, 21.03.2013).
Bilder wie Part 5 (reel28_emptynet.py): Bande, Glas, Bänke, Tore als 3D-Gitter, Eis + Puck (Raytracer), Spieler nur
als Marker; neu: Schiedsrichter-Marker (gestreift) mit erhobenem Arm und orangem Armband. Bewusst ohne Spielerkörper.
Stimme: Kokoro "Michael" (tts_kokoro.py, Apache-2.0), Sätze einzeln, 1,08x; "Brodeur" mit korrigierter Betonung.
Aufruf: python3 reel29_delayed.py vo     -> voice/reel29_*.wav
        python3 reel29_delayed.py audio  -> nur Ton neu mischen
        python3 reel29_delayed.py        -> reel29_delayed.mp4
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
from PIL import Image

import puck3d as P3
import reel15_puck as R15
import reel18_dangle as R18
import mesh3d as M3
import reel25_goalline as G
import reel26_overglass as R26
import reel28_emptynet as R28
from reel15_puck import (W, H, FPS, SPP, KSUB, SHUTTER, c01, smooth, sio, e_out, e_in, lerp, blend_up, line_img,
                         reveal, put, proj, projected, px_per_in, stroke_poly, surface, surf_rgba, over)
from reel22_trapezoid import puck_marker, whistle_ring, slam
from reel18_dangle import vignette
from reel28_emptynet import (disc, letter, pulse_ring, crease_ring, path_line, label_at, lines2, bez, drift, stick,
                             pass_, top_cam, blend_cam, A_POS, D_POS, RG_POS, PLUS_END, OWN_X, NET_IN)

HERE = R15.HERE
INK, ORANGE = R15.INK, R15.ORANGE
RED = (225, 30, 40)
BLUE = (40, 110, 210)
GREEN = (30, 160, 80)
GREY = (110, 114, 126)
GOLD = (236, 170, 20)
HALO = (255, 255, 255)
TEMPO = 1.08

# ================================================================= Timeline aus dem Voiceover
VO_LINES = [
    ("q", "Why did the goalie leave in the first period?"),
    ("arm", "See the ref's arm? Delayed penalty."),
    ("rule", "Play only stops once the other team gets the puck. So they can't score."),
    ("free", "Free extra skater with zero risk."),
    ("twist", "Unless your own pass goes in."),
    ("fact", "That goal once went to the other goalie: Martin Brodeur!"),
    ("cta", "Seen one live? Yes or no?"),
]
VO_FIXES = {"bɹˈoʊdɜː": "bɹoʊdˈɜːɹ"}           # Brodeur: broh-DUR
VO_KEYS = [k for k, _ in VO_LINES]
VO_START = {"q": 0.15, "arm": 2.15, "rule": 3.95, "free": 7.5, "twist": 9.2, "fact": 10.75, "cta": 13.45}
DUR = 15.9


def at(key, s):
    """Zeitpunkt s Sekunden nach Satzbeginn (im fertigen, 1,08x schnelleren Satz)."""
    return VO_START[key] + s


T_UP0, T_UP1 = 1.5, 2.45               # Hook am leeren Tor -> Angriffsdrittel
T_ARM = at("arm", 0.50)                # "arm"
T_DELAY = at("arm", 0.74)              # "delayed penalty"
T_BENCH = 3.2                          # Goalie auf der Bank
T_GETS = at("rule", 1.52)              # "gets the puck" – Rot wäre fast dran
T_CANT = at("rule", 2.74)              # "can't score"
T_JUMP = at("free", 0.05)              # "+1" springt aufs Eis
T_ZERO = at("free", 1.02)              # "zero risk"
T_PASS = at("twist", 0.05)             # Pass zurück an die blaue Linie …
T_OWN = 10.7                           # … rutscht ins eigene leere Tor
T_UPF0, T_UPF1 = 10.85, 11.7           # hoch auf die ganze Eisfläche
T_CREDIT = at("fact", 0.98)            # "the other goalie"
T_NAME = at("fact", 1.80)              # "Martin Brodeur"
T_DN0, T_DN1 = 13.25, 14.2             # zurück ans leere Tor (Loop)
T_CTA = VO_START["cta"]
CLOCK0 = 14 * 60 + 32                  # 1. Drittel, 14:32

# ================================================================= Marker + Puck
REF_POS = np.array([420.0, 0.0, -320.0])
OFFENDER = 1                           # roter Verteidiger D2 hat gefoult
G_P0, G_P1, G_P2 = np.array([OWN_X + 54.0, 0.0, 0.0]), np.array([-880.0, 0.0, 360.0]), np.array([-150.0, 0.0, 468.0])
PLUS_P0, PLUS_P1 = np.array([-150.0, 0.0, 470.0]), np.array([250.0, 0.0, 320.0])


def goalie_state(t):
    u = c01((t + 0.15) / (T_BENCH + 0.15))
    u = 0.5 * (u ** 1.5) + 0.5 * sio(u)
    p = bez(G_P0, G_P1, G_P2, u)
    if t > T_BENCH:
        p = p + np.array([0.0, 0.0, 70.0]) * e_in(c01((t - T_BENCH) / 0.35), 2)
    return p, 1 - smooth(T_BENCH + 0.1, T_BENCH + 0.35, t)


def plus_state(t):
    if t < T_JUMP:
        return PLUS_P0, 0.0
    u = sio(c01((t - T_JUMP) / 1.3))
    return drift(bez(PLUS_P0, PLUS_P1, PLUS_END, u), 7, t, 10.0 * u), 1.0


def attackers(t):
    A = [drift(p, k, t) for k, p in enumerate(A_POS)]
    A[2] = A[2] + np.array([0.0, 0.0, 26.0]) * sio(c01((t - T_PASS - 0.1) / 0.35))   # streckt sich – zu spät
    return A


LANE = (A_POS[3] + A_POS[2]) / 2                                       # Passweg A4 -> A3


def defenders(t):
    D = [drift(p, k + 5, t) for k, p in enumerate(D_POS)]
    k = math.sin(math.pi * c01((t - (T_GETS - 0.45)) / 0.95))          # D5 wirft sich in den Pass
    D[4] = D[4] + (LANE + np.array([40.0, 0.0, 30.0]) - D[4]) * k * 0.85
    D[0] = D[0] + np.array([40.0, 0.0, -50.0]) * sio(c01((t - 7.4) / 1.2))   # D1 jagt A1
    return D


def puck_state(t):
    A = attackers(t)
    if t < 4.6:
        return stick(A[1], A[3]), 1.0
    if t < 4.95:
        return pass_(stick(A[1], A[3]), stick(A[3], A[1]), 4.6, 4.95, t), 1.0
    if t < T_GETS - 0.22:
        return stick(A[3], A[2]), 1.0
    if t < T_GETS + 0.2:
        return pass_(stick(A[3], A[2]), stick(A[2], A[3]), T_GETS - 0.22, T_GETS + 0.2, t), 1.0
    if t < 7.0:
        return stick(A[2], A[0]), 1.0
    if t < 7.4:
        return pass_(stick(A[2], A[0]), stick(A[0], A[2]), 7.0, 7.4, t), 1.0
    if t < T_PASS:
        return stick(A[0], A[2]), 1.0
    p0 = stick(attackers(T_PASS)[0], A_POS[2])
    if t < T_OWN:
        u = c01((t - T_PASS) / (T_OWN - T_PASS))
        return p0 + (NET_IN - p0) * (1 - (1 - u) ** 1.15), 1.0
    return NET_IN, 1.0


def own_path(u1):
    p0 = stick(attackers(T_PASS)[0], A_POS[2])
    return [p0 + (NET_IN - p0) * (1 - (1 - u) ** 1.15) + [0, -0.4, 0] for u in np.linspace(0, u1, 50)]


def puck_rot(t):
    return 0.7 + 7.0 * t


# ================================================================= Kamera
MID_X, MID_H = 560.0, 3000.0
NETV_X, NETV_H = -740.0, 2900.0
FULL_X, FULL_H = 150.0, 5600.0


def hook_cam(t):
    return R28.HOOK_P0 + R28.HOOK_PUSH * e_out(c01(t / T_UP0), 2), R28.HOOK_T, R28.HOOK_FOV


def end_cam(t):
    u = c01((t - T_DN1) / (DUR - T_DN1))
    return hook_cam(T_UP0 * (1 - sio(u)))


def cam(t):
    if t < T_UP0:
        p, g, f = hook_cam(t)
    elif t < T_UP1:
        p, g, f = blend_cam(hook_cam(T_UP0), top_cam(MID_X, MID_H), sio((t - T_UP0) / (T_UP1 - T_UP0)))
    elif t < T_PASS:
        p, g, f = top_cam(MID_X + 30.0 * sio(c01((t - T_UP1) / 6.0)), MID_H)
    elif t < T_UPF0:
        s = sio(c01((t - T_PASS + 0.05) / (T_OWN - T_PASS + 0.15)))
        p, g, f = top_cam(lerp(MID_X + 30.0, NETV_X, s), lerp(MID_H, NETV_H, s) + 600 * math.sin(math.pi * s)
                          - 240 * e_out(c01((t - T_OWN) / 0.4), 3))
    elif t < T_UPF1:
        s = sio((t - T_UPF0) / (T_UPF1 - T_UPF0))
        p, g, f = top_cam(lerp(NETV_X, FULL_X, s), math.exp(lerp(math.log(NETV_H - 240), math.log(FULL_H), s)))
    elif t < T_DN0:
        p, g, f = top_cam(FULL_X, FULL_H - 80 * c01((t - T_UPF1) / 1.5))
    elif t < T_DN1:
        p, g, f = blend_cam(top_cam(FULL_X, FULL_H - 80), end_cam(T_DN1), sio((t - T_DN0) / (T_DN1 - T_DN0)))
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
    for a, b in ((0.0, T_PASS), (T_PASS, T_OWN), (T_OWN, DUR)):
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
    P3.render(W, H, SPP, fidx + 29, cams, lens, pk, R15.logo_tex(), base, puck, cov)
    return P3.tonemap(base), P3.tonemap(puck), cov


# ================================================================= Overlays
def referee(ctx, row, t, a):
    """Gestreifter Marker + Arm (unten -> oben) mit orangem Armband."""
    c_r = disc(ctx, row, drift(REF_POS, 13, t, 6.0), INK, a, r_px=(34, 64), r_in=30.0)
    if c_r is None:
        return None
    c, rp = c_r
    ctx.save()
    ctx.arc(c[0], c[1], rp * 0.9, 0, 2 * math.pi)
    ctx.clip()
    ctx.set_source_rgba(INK[0] / 255, INK[1] / 255, INK[2] / 255, a)
    for k in range(-3, 4):
        ctx.rectangle(c[0] + k * rp * 0.5 - rp * 0.12, c[1] - rp, rp * 0.24, rp * 2)
    ctx.fill()
    ctx.restore()
    wave_ = 12.0 * math.sin((t - T_ARM) * 22) * math.exp(-(t - T_ARM) * 3.5) if t >= T_ARM else 0.0
    ang = math.radians(78.0 + wave_)                                   # Arm ist schon oben (seit dem Foul)
    sh = np.array([c[0] + rp * 0.78, c[1] - rp * 0.2])
    tip = sh + np.array([math.cos(ang), -math.sin(ang)]) * rp * 1.7
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_source_rgba(1, 1, 1, a)
    ctx.set_line_width(rp * 0.55)
    ctx.move_to(*sh)
    ctx.line_to(*tip)
    ctx.stroke()
    ctx.set_source_rgba(INK[0] / 255, INK[1] / 255, INK[2] / 255, a)
    ctx.set_line_width(rp * 0.36)
    ctx.move_to(*sh)
    ctx.line_to(*tip)
    ctx.stroke()
    b0, b1 = sh + (tip - sh) * 0.42, sh + (tip - sh) * 0.62                # orange Armbinde (wie bei NHL-Refs)
    ctx.set_source_rgba(ORANGE[0] / 255, ORANGE[1] / 255, ORANGE[2] / 255, a)
    ctx.set_line_width(rp * 0.42)
    ctx.set_line_cap(cairo.LINE_CAP_BUTT)
    ctx.move_to(*b0)
    ctx.line_to(*b1)
    ctx.stroke()
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_source_rgba(INK[0] / 255, INK[1] / 255, INK[2] / 255, a)
    ctx.arc(tip[0], tip[1], rp * 0.26, 0, 2 * math.pi)
    ctx.fill()
    return c_r


def credit_line(ctx, row, rg, a, t):
    """Gepunktete Linie vom Puck im eigenen Tor zum letzten roten Spieler am Puck (Goalie)."""
    if a <= 0:
        return
    u1 = e_out(c01((t - T_UPF0 - 0.2) / 0.8), 2)
    pts = [NET_IN + (rg - NET_IN) * u + [0, 0.3, 0] for u in np.linspace(0, max(u1, 0.02), 60)]
    path_line(ctx, row, pts, GOLD, a, 7, [4, 18], t)


# ---------------- Anzeigetafel
def clock_s(t):
    return CLOCK0 - t


def scoreboard(L, t):
    sb = 1 if t >= T_OWN else 0
    hb = math.exp(-max(0.0, t - T_OWN) * 4) if t >= T_OWN else 0.0
    im = R28.bug_img(0, sb, R28.fmt(clock_s(t)), INK, 0.0, hb, period="1ST")
    sc = 1.0 + 0.07 * hb
    if sc > 1.001:
        im = im.resize((int(im.width * sc), int(im.height * sc)), Image.BILINEAR)
    put(L, im, W / 2 - im.width / 2, 205 - im.height / 2)


# ---------------- Texte
def texts(L, t, row, A, D):
    if t < T_UP0 + 0.1:
        k = 1 - smooth(T_UP0 - 0.1, T_UP0 + 0.1, t)
        lines2(L, [("WHY DID THE", 440, 120, INK), ("GOALIE LEAVE", 570, 120, INK), ("IN THE", 678, 78, INK),
                   ("1ST PERIOD?", 800, 150, RED)], k)
        reveal(L, line_img("NHL RULES EXPLAINED  ·  PART 6", 34, 800, ORANGE, track=8), W / 2, 345, 1.0,
               smooth(T_UP0 - 0.15, T_UP0 + 0.05, t))
    scoreboard(L, t)
    mid = T_UP1 - 0.3 < t < T_PASS
    if mid:
        out = 1 - smooth(T_PASS - 0.25, T_PASS, t)
        label_at(L, row, REF_POS, "REF", GREY, 0, 82, smooth(T_UP1 - 0.3, T_UP1, t) * out, 34)
        label_at(L, row, D[OFFENDER], "PENALTY", ORANGE, 0, -86, smooth(T_DELAY + 0.1, T_DELAY + 0.25, t) * out, 36)
    slam(L, "DELAYED PENALTY", 100, ORANGE, W / 2, 1450, t, T_DELAY, VO_START["rule"])
    if T_DELAY + 0.3 <= t < VO_START["rule"]:
        reveal(L, line_img("REF'S ARM UP = PENALTY COMING", 34, 800, INK, track=5), W / 2, 1545,
               c01((t - T_DELAY - 0.3) / 0.25), smooth(VO_START["rule"] - 0.2, VO_START["rule"], t))
    if VO_START["rule"] <= t < T_CANT:
        p_out = smooth(T_CANT - 0.15, T_CANT, t)
        reveal(L, line_img("PLAY ONLY STOPS WHEN", 44, 850, INK, track=6), W / 2, 1380,
               c01((t - VO_START["rule"]) / 0.25), p_out)
        if t >= at("rule", 1.1):
            im = R18.word_img("RED GETS THE PUCK", 92, RED, HALO)
            reveal(L, im, W / 2, 1480, c01((t - at("rule", 1.1)) / 0.25), p_out)
        reveal(L, line_img("NHL RULE 15.1", 26, 700, GREY, track=4), W / 2, 1600, c01((t - at("rule", 0.4)) / 0.25),
               p_out)
    if T_GETS - 0.1 < t < T_GETS + 0.7:
        p, _ = puck_state(t)
        label_at(L, row, p, "RED TOUCH = WHISTLE", RED, 0, 92, smooth(T_GETS - 0.1, T_GETS + 0.05, t)
                 * (1 - smooth(T_GETS + 0.5, T_GETS + 0.7, t)), 34)
    slam(L, "RED CAN'T SCORE.", 100, RED, W / 2, 1470, t, T_CANT, VO_START["free"])
    if VO_START["rule"] <= t < VO_START["free"] and t >= T_CANT + 0.25:
        reveal(L, line_img("NHL RULE 78.5", 26, 700, GREY, track=4), W / 2, 1580, c01((t - T_CANT - 0.25) / 0.25),
               smooth(VO_START["free"] - 0.2, VO_START["free"], t))
    pp, pa = plus_state(t)
    if T_JUMP < t < T_PASS:
        label_at(L, row, pp, "FREE EXTRA SKATER", ORANGE, -40, -86, smooth(T_JUMP, T_JUMP + 0.15, t)
                 * (1 - smooth(T_PASS - 0.3, T_PASS - 0.1, t)), 34)
    slam(L, "ZERO RISK", 160, GREEN, W / 2, 1460, t, T_ZERO, T_PASS)
    slam(L, "OWN GOAL!", 170, RED, W / 2, 700, t, T_OWN, T_CREDIT - 0.6)
    if T_CREDIT - 0.5 <= t < T_DN0:
        p_out = smooth(T_DN0 - 0.2, T_DN0, t)
        reveal(L, line_img("CREDITED TO", 44, 850, INK, track=6), W / 2, 935, c01((t - T_CREDIT + 0.5) / 0.25), p_out)
        label_at(L, row, drift(RG_POS, 11, t, 4.0), "LAST RED PLAYER ON THE PUCK", GOLD, 0, 84,
                 smooth(T_CREDIT, T_CREDIT + 0.2, t) * (1 - p_out), 30)
        if t >= T_CREDIT:
            reveal(L, R18.word_img("THE OTHER GOALIE", 96, RED, HALO), W / 2, 1025, c01((t - T_CREDIT) / 0.25), p_out)
    slam(L, "MARTIN BRODEUR", 104, INK, W / 2, 1160, t, T_NAME, T_DN0)
    if T_NAME + 0.3 <= t < T_DN0:
        reveal(L, line_img("DEVILS vs. HURRICANES  ·  MARCH 21, 2013", 28, 750, GREY, track=3), W / 2, 1248,
               c01((t - T_NAME - 0.3) / 0.25), smooth(T_DN0 - 0.2, T_DN0, t))
    if t >= T_CTA:
        slam(L, "SEEN ONE LIVE?", 110, INK, W / 2, 470, t, T_CTA)
        slam(L, "YES OR NO?", 155, ORANGE, W / 2, 630, t, at("cta", 0.9))
        if t >= at("cta", 1.2):
            reveal(L, line_img("COMMENT BELOW  ·  FOLLOW FOR PART 7", 32, 800, INK, track=6), W / 2, 1300,
                   c01((t - at("cta", 1.2)) / 0.25))


# ================================================================= Bild
def compose(t, fidx):
    base, puck, cov = render3d(t, fidx)
    row, _ = cam_row_at(t)
    campos = cam(t)[0]
    p, vis = puck_state(t)
    lo_s, lo_c = surface()
    hi_s, hi_c = surface()
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    R28.draw_net_lines(lo_c, row)
    R28.glass_edges(lo_c, row)
    img = over(base, *surf_rgba(lo_s))
    meshes = R28.BOARDS + R28.FRAMES
    if vis > 0:
        meshes = meshes + [G.cyl_mesh(p - np.array([0, 0.5, 0]), 1.5, 1.0, "occluder", group=1)]
    m_rgb, m_a, shadow, plane_a = M3.render(meshes, row, W, H, campos, alpha_by_group=np.array([1.0, 0.0], np.float32),
                                            extra_planes=[(R28.GLASS_ALL, 1.0)], shadow_light=(0.02, 1.0, -0.03))
    img = img * (1 - 0.15 * shadow[..., None])
    pa = cov[..., None]
    img = img * (1 - pa) + puck * pa
    img = img * (1 - m_a[..., None]) + m_rgb
    k = (0.30 * plane_a)[..., None]
    img = img * (1 - k) + np.array([0.70, 0.82, 0.94], np.float32) * k
    img = img + (R26.glass_streaks() * plane_a * 0.10)[..., None]

    # Markierungen auf dem Eis
    crease_ring(hi_c, row, smooth(0.25, 0.45, t) * (1 - smooth(T_UP0 - 0.2, T_UP0, t)), t)
    gp, ga = goalie_state(t)
    if t < T_BENCH + 0.35:
        us = np.linspace(0, 1, 40)
        path_line(hi_c, row, [bez(G_P0, G_P1, G_P2, u) + [0, 0.1, 0] for u in us], BLUE,
                  0.8 * smooth(0.3, 0.7, t) * (1 - smooth(T_BENCH, T_BENCH + 0.3, t)), 5, [20, 16], t)
    team_a = smooth(T_UP1 - 0.6, T_UP1, t) * (1 - smooth(T_DN0, T_DN0 + 0.3, t))
    A, D = attackers(t), defenders(t)
    cr_a = [disc(hi_c, row, q, BLUE, team_a) for q in A]
    cr_d = [disc(hi_c, row, q, RED, team_a, ring=ORANGE if (i == OFFENDER and t >= T_DELAY) else None)
            for i, q in enumerate(D)]
    rg = drift(RG_POS, 11, t, 4.0)
    gold = smooth(T_CREDIT - 0.1, T_CREDIT + 0.1, t)
    cr_rg = disc(hi_c, row, rg, RED, team_a, ring=GOLD if gold > 0.5 else None,
                 scale=1 + 0.25 * gold * (1 + 0.15 * math.sin(t * 8)))
    cr_ref = referee(hi_c, row, t, team_a)
    if T_PASS <= t < T_UPF1 + 0.3:                                          # Fehlpass ins eigene Tor
        path_line(hi_c, row, own_path(c01((t - T_PASS) / (T_OWN - T_PASS))), ORANGE,
                  1 - smooth(T_UPF1, T_UPF1 + 0.3, t), 6)
    credit_line(hi_c, row, rg, smooth(T_UPF0 + 0.1, T_UPF0 + 0.3, t) * (1 - smooth(T_DN0, T_DN0 + 0.25, t)), t)
    if T_OWN - 0.05 < t < T_DN0:
        crease_ring(hi_c, row, smooth(T_OWN, T_OWN + 0.15, t) * (1 - smooth(T_DN0 - 0.2, T_DN0, t)), t)
    pp, pa_ = plus_state(t)
    cr_p = disc(hi_c, row, pp, BLUE, pa_ * c01((t - T_JUMP) / 0.12) * (1 - smooth(T_DN0, T_DN0 + 0.3, t)),
                ring=ORANGE, scale=1 + 0.35 * math.exp(-max(0.0, t - T_JUMP) * 7))
    cr_g = disc(hi_c, row, gp, BLUE, ga, r_px=(26, 96), r_in=26.0)
    if vis > 0 and T_UP1 - 0.2 < t < T_OWN + 0.3:
        puck_marker(hi_c, row, p, t)
    pulse_ring(hi_c, cr_ref, ORANGE, t, T_ARM)
    pulse_ring(hi_c, cr_d[OFFENDER], ORANGE, t, T_DELAY + 0.05)
    pulse_ring(hi_c, cr_p, ORANGE, t, T_JUMP)
    pulse_ring(hi_c, cr_rg, GOLD, t, T_CREDIT, 0.8)
    if T_GETS - 0.2 < t < T_GETS + 0.6:                                      # Rot ist fast am Puck
        xy, z = projected(row, p)
        q = c01((t - T_GETS + 0.2) / 0.8)
        hi_c.set_source_rgba(RED[0] / 255, RED[1] / 255, RED[2] / 255, 0.9 * (1 - q))
        hi_c.set_line_width(6)
        hi_c.set_dash([14, 10], -t * 60)
        hi_c.arc(xy[0], xy[1], 44 + 30 * q, 0, 2 * math.pi)
        hi_c.stroke()
        hi_c.set_dash([])
    whistle_ring(hi_c, row, np.array([OWN_X, 20.0, 0.0]), t, T_OWN, RED)
    img = over(img, *surf_rgba(hi_s))
    if T_OWN <= t < T_OWN + 0.35:
        a = 0.22 * (1 - (t - T_OWN) / 0.35)
        img = img * (1 - a) + np.array([1.0, 0.1, 0.12], np.float32) * a
    img = np.clip(img, 0, 1)
    pil = Image.fromarray((img * 255).astype(np.uint8)).convert("RGBA")
    letter(L, cr_g, "G", BLUE, ga)
    letter(L, cr_rg, "G", RED, team_a)
    letter(L, cr_d[OFFENDER], "!", ORANGE, team_a * c01((t - T_DELAY) / 0.1), 1.0)
    letter(L, cr_p, "+1", ORANGE, pa_ * c01((t - T_JUMP) / 0.12) * (1 - smooth(T_DN0, T_DN0 + 0.3, t)), 0.8)
    texts(L, t, row, A, D)
    pil.alpha_composite(L)
    arr = np.asarray(pil.convert("RGB")).astype(np.float32) / 255
    lc = min([t - c for c in (T_DELAY, T_CANT, T_ZERO, T_OWN, T_NAME) if t >= c] + [t + 0.5])
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
    rng = np.random.default_rng(29)
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

    def chime(vol=0.4):
        out = np.zeros(int(1.2 * SR))
        for i, f in enumerate((1046.5, 1318.5, 1568.0)):
            x = tt(1.2 - 0.09 * i)
            out[int(0.09 * i * SR):][:len(x)] += np.sin(2 * np.pi * f * x) * np.exp(-x * 4) * vol
        return out

    def wahwah(vol=0.5):
        """Absteigende "Oh nein"-Posaune (Eigentor)."""
        out = []
        for f0, d in ((311.1, 0.28), (293.7, 0.28), (277.2, 0.28), (261.6, 0.8)):
            x = tt(d)
            vib = 1 + (0.025 * np.sin(2 * np.pi * 6 * x) if d > 0.5 else 0)
            ph = 2 * np.pi * np.cumsum(f0 * vib) / SR
            sig = sum(np.sin(ph * h) / h ** 1.2 for h in range(1, 7))
            env = np.minimum(x / 0.03, 1) * np.clip((d - x) / 0.08, 0, 1) * (0.55 + 0.45 * np.minimum(x / 0.12, 1))
            out.append(lp(sig, 6) * env)
        return np.tanh(np.concatenate(out) * 0.7) * vol

    roots = [55.0, 43.65, 49.0, 41.2]
    mel = [880.0, 1046.5, 1318.5, 1046.5, 987.8, 880.0, 784.0, 659.25]
    for k8 in range(int(DUR / (B / 2))):
        tb = k8 * B / 2
        b = k8 / 2
        pos = b % 4
        if tb > DUR - 0.5:
            continue
        soft = tb < T_UP0 or T_OWN <= tb < T_UPF1                       # Hook + Eigentor: nur Kick + Bass
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
        put_(sfx, skate(0.3, 0.32), 0.05 + 0.4 * k, pan=0.4)
    put_(sfx, whoosh(T_UP1 - T_UP0 + 0.1, 0.45), T_UP0)
    put_(sfx, click(0.6), T_ARM)
    put_(sfx, stamp(0.9), T_DELAY)
    put_(sfx, slap(0.45), 4.6)
    put_(sfx, slap(0.45), T_GETS - 0.22)
    put_(sfx, whoosh(0.4, 0.3), T_GETS - 0.2)
    put_(sfx, stamp(0.8), T_CANT)
    put_(sfx, slap(0.45), 7.0)
    put_(sfx, ding(0.4), T_JUMP)
    put_(sfx, stamp(0.8), T_ZERO)
    put_(sfx, ding(0.3), T_ZERO)
    put_(sfx, slap(0.7), T_PASS)
    put_(sfx, whoosh(T_OWN - T_PASS, 0.45), T_PASS)
    put_(sfx, stamp(1.0), T_OWN)
    put_(sfx, wahwah(0.55), T_OWN + 0.12)
    put_(sfx, whoosh(T_UPF1 - T_UPF0, 0.35), T_UPF0)
    put_(sfx, chime(0.45), T_CREDIT)
    put_(sfx, stamp(0.9), T_NAME)
    put_(sfx, whoosh(T_DN1 - T_DN0 + 0.1, 0.4), T_DN0)
    put_(sfx, stamp(0.7), at("cta", 0.9))
    voice = np.zeros(n)
    for k in VO_KEYS:
        tmp = os.path.join(HERE, f"_vo_{k}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "voice", f"reel29_{k}.wav"),
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
    tts_kokoro.synth(VO_LINES, os.path.join(HERE, "voice", "reel29"), speed=1.2, fixes=VO_FIXES)


def check_vo():
    with open(os.path.join(HERE, "voice", "reel29_timing.json")) as f:
        vo_dur = {k: v / TEMPO for k, v in json.load(f).items()}
    for i, k in enumerate(VO_KEYS[:-1]):
        nxt = VO_KEYS[i + 1]
        if VO_START[k] + vo_dur[k] > VO_START[nxt] + 0.35:
            print(f"Warnung: Satz {k} überlappt {nxt} ({VO_START[k] + vo_dur[k]:.2f} > {VO_START[nxt]:.2f})")


def remux():
    os.chdir(HERE)
    make_audio("audio_delayed.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "reel29_delayed.mp4", "-i", "audio_delayed.wav", "-map", "0:v",
                    "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
                    "-ar", "44100", "-shortest", "-movflags", "+faststart", "_tmp_delayed.mp4"], check=True)
    os.replace("_tmp_delayed.mp4", "reel29_delayed.mp4")


def main():
    os.chdir(HERE)
    check_vo()
    make_audio("audio_delayed.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_delayed.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
           "-ar", "44100", "-shortest", "-movflags", "+faststart", "reel29_delayed.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(0.9, 9999)).save("reel29_thumbnail.jpg", quality=92)
    print("fertig: reel29_delayed.mp4")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "vo":
        make_voice()
    elif len(sys.argv) > 1 and sys.argv[1] == "audio":
        remux()
    else:
        main()
