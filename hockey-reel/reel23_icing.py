"""Reel 23: NHL RULES EXPLAINED – PART 2: ICING (3D-Erklärvideo mit Voiceover, ~15,6 s, weißer Studio-Look).

Fakten: Icing = Puck aus der eigenen Hälfte (hinter der roten Mittellinie) über die gegnerische Torlinie, ohne
Berührung. Folge: Bully im Drittel der Mannschaft, die geict hat; sie darf nicht wechseln (seit 2005–06).
Hybrid-Icing seit 2013–14: Linienrichter entscheidet bei den Bullypunkten – Verteidiger vorne = Icing,
Angreifer vorne = weiter. In Unterzahl ist Icing erlaubt.
Stimme: Piper "Ryan" (lokal, tts_piper.py), Sätze einzeln, 1,1x.
Aufruf: python3 reel23_icing.py -> reel23_icing.mp4
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
from reel15_puck import (W, H, FPS, SPP, KSUB, SHUTTER, c01, smooth, sio, e_out, e_in, lerp, sph, blend_up, line_img,
                         reveal, put, proj, projected, px_per_in, stroke_poly, surface, surf_rgba, over, GOAL_X)
from reel22_trapezoid import fill_poly, token, puck_marker, whistle_ring, slam
from reel18_dangle import vignette

HERE = R15.HERE
INK, ORANGE = R15.INK, R15.ORANGE
RED = (225, 30, 40)
GREEN = (30, 160, 80)
BLUE = (40, 110, 210)
HALO = (255, 255, 255)
UP = np.array([0.0, 1.0, 0.0])
TEMPO = 1.1

# ================================================================= Timeline aus dem Voiceover
VO_KEYS = ["q", "half", "past", "call", "zone", "race", "def", "att", "pk", "cta"]
VO_PREFIX = "reel23"                 # voice/<prefix>_<key>.wav (reel23k = Kokoro-Stimme)
VO_START = {"q": 0.10, "half": 1.35, "past": 2.65, "call": 4.12, "zone": 4.75, "race": 7.05, "def": 9.42,
            "att": 10.85, "pk": 12.2, "cta": 13.5}
with open(os.path.join(HERE, "voice", "reel23_timing.json")) as f:
    VO_DUR = {k: v / TEMPO for k, v in json.load(f).items()}
DUR = 15.6

T_SHOT1 = 1.42                      # Schuss aus der eigenen Hälfte
T_LINE1 = 3.95                      # Puck über der Torlinie
T_WH1 = 4.1                         # Pfiff
T_BACK0, T_BACK1 = 4.8, 5.6         # Puck zurück zum Bullypunkt
T_REW0, T_REW1 = 6.75, 7.0
T_SHOT2 = 7.15
T_DOTS_D = 10.0                     # Verteidiger erreicht die Punkte (Icing) – auf "Icing" im VO
T_REW2, T_REW3 = 10.55, 10.77
T_DOTS_A = 11.58                    # Angreifer zuerst (weiter) – auf "Play on"
T_SHOT3 = 12.25
X0 = np.array([-450.0, 0.5, -60.0])
END = np.array([1172.0, 0.5, 90.0])
DOT_OWN = np.array([-828.0, 0.5, -264.0])
DOT_LINE = 828.0


def slide(t0, t1, a, b, t):
    """Puck mit Abbremsung von a nach b."""
    u = c01((t - t0) / (t1 - t0))
    return a + (b - a) * (1 - (1 - u) ** 1.7)


def puck_at(t):
    if t < T_SHOT1:
        return X0.copy()
    if t < T_BACK0:
        return slide(T_SHOT1, T_WH1 + 0.25, X0, END, t)
    if t < T_REW0:
        u = sio((t - T_BACK0) / (T_BACK1 - T_BACK0))
        p = END + (DOT_OWN - END) * u
        p[1] = 0.5 + 60 * math.sin(math.pi * u)                    # Bogen zurück
        return p
    if t < T_SHOT2:
        return X0.copy()
    if t < T_REW2:
        return slide(T_SHOT2, T_DOTS_D + 0.7, X0, END, t)
    if t < T_REW3:
        return X0.copy()
    if t < T_SHOT3 - 0.3:
        return slide(T_REW3 + 0.05, T_DOTS_A + 0.9, X0, END + np.array([0, 0, -40.0]), t)
    if t < 13.4:
        return slide(T_SHOT3, 13.35, X0, END, t)
    return np.array([1080.0, 0.5, 0.0])


def racers(t):
    """(Verteidiger, Angreifer) für die Hybrid-Icing-Szenen."""
    if T_REW1 <= t < T_REW2:                                        # Verteidiger gewinnt
        d0, d1 = np.array([620.0, 0.1, 160.0]), np.array([DOT_LINE + 30, 0.1, 120.0])
        a0, a1 = np.array([500.0, 0.1, -140.0]), np.array([DOT_LINE - 60, 0.1, -60.0])
        u = c01((t - 8.0) / (T_DOTS_D + 0.25 - 8.0))
        return d0 + (d1 - d0) * sio(u), a0 + (a1 - a0) * sio(u)
    if T_REW3 <= t < T_SHOT3 - 0.3:                                 # Angreifer gewinnt
        d0, d1 = np.array([560.0, 0.1, 160.0]), np.array([DOT_LINE - 70, 0.1, 110.0])
        a0, a1 = np.array([600.0, 0.1, -140.0]), np.array([DOT_LINE + 70, 0.1, -40.0])
        u = c01((t - T_REW3) / (T_DOTS_A + 0.3 - T_REW3))
        return d0 + (d1 - d0) * sio(u), a0 + (a1 - a0) * sio(u)
    return None


# ================================================================= Kamera
TOP_T = np.array([150.0, 0.0, 0.0])
TOP_H = 5000.0
T_CRANE0, T_CRANE1 = 1.65, 3.0      # Hook -> Draufsicht
T_END0, T_END1 = 13.45, 14.35       # Draufsicht -> Schlussbild
HOOK_P0 = np.array([-2000.0, 1300.0, -260.0])
HOOK_P1 = np.array([-1850.0, 1210.0, -120.0])
HOOK_TGT = np.array([420.0, 0.0, 0.0])
END_POS = np.array([-2250.0, 1150.0, 0.0])
END_TGT = np.array([720.0, 0.0, 0.0])


def top_target(t):
    """Draufsicht schwenkt fürs Bully kurz ins eigene Drittel (und mit dem Rewind zurück)."""
    return TOP_T - np.array([450.0, 0.0, 0.0]) * (sio(smooth(T_BACK0, T_BACK1, t)) - sio(smooth(T_REW0, T_REW1, t)))


def hook_cam(t):
    u = e_out(c01(t / T_CRANE0), 2)
    return HOOK_P0 + (HOOK_P1 - HOOK_P0) * u, HOOK_TGT, UP, 38.0


def crane(p0, t0, f0, s):
    """Schräge 3D-Ansicht (s=0) -> Draufsicht (s=1), Bild-oben bleibt +x."""
    tgt = t0 + (TOP_T - t0) * s
    r0 = float(np.linalg.norm(p0 - t0))
    r = math.exp(lerp(math.log(r0), math.log(TOP_H), s))
    d0 = (p0 - t0) / r0
    d = d0 + (np.array([0.0, 1.0, 0.0]) - d0) * s
    d /= np.linalg.norm(d)
    el = math.degrees(math.asin(max(-1.0, min(1.0, d[1]))))
    return tgt + d * r, tgt, blend_up(min(el, 89.9)), lerp(f0, 30.0, s)


def cam(t):
    if t < T_CRANE0:                                                 # schräg von hinten über die ganze Eisfläche
        return hook_cam(t)
    if t < T_CRANE1:
        p0, t0, _, f0 = hook_cam(T_CRANE0)
        return crane(p0, t0, f0, sio((t - T_CRANE0) / (T_CRANE1 - T_CRANE0)))
    if t < T_END0:
        tt_ = top_target(t)
        return tt_ + np.array([-0.5, TOP_H, 0.0]), tt_, blend_up(89.9), 30.0
    if t < T_END1:                                                   # zurück in die Schräge
        return crane(END_POS, END_TGT, 36.0, 1 - sio((t - T_END0) / (T_END1 - T_END0)))
    u = (t - T_END1) / (DUR - T_END1)
    return END_POS + np.array([90.0, -40.0, 0.0]) * u, END_TGT, UP, 36.0


def cam_row_at(t):
    pos, tgt, up, fov = cam(t)
    r, u, f = P3.look_at(pos, tgt, up)
    return P3.cam_row(pos, r, u, f, fov), float(np.linalg.norm(tgt - pos))


def seg(t):
    return 0.0, DUR


def render3d(t, fidx):
    lo, hi = seg(t)
    cams, lens, pk = np.zeros((KSUB, 13)), np.zeros((KSUB, 2)), np.zeros((KSUB, 7))
    for j in range(KSUB):
        tk = min(max(t + ((j + 0.5) / KSUB - 0.5) * SHUTTER, lo), hi - 1e-4)
        row, focus = cam_row_at(tk)
        cams[j], lens[j] = row, (0.0, focus)
        p = puck_at(tk)
        pk[j] = (p[0], p[1], p[2], R18.G.THETA0 + 8 * tk, 1.0, 0.0, tk)
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, SPP, fidx + 23, cams, lens, pk, R15.logo_tex(), base, puck, cov)
    return P3.tonemap(base), P3.tonemap(puck), cov


# ================================================================= Overlays
def draw_nets(row):
    """Beide Tore (das zweite gespiegelt)."""
    back, front = R15.draw_net(row, -1.0, False), R15.draw_net(row, -1.0, True)
    s, ctx = surface()
    mesh, fw_, fr_ = R15.net_lines(-1.0)
    for pl in mesh:
        q = pl.copy()
        q[:, 0] = -q[:, 0]
        xy, z = proj(row, q)
        if (z > 2).all():
            stroke_poly(ctx, xy, (96, 106, 122), 0.7, float(np.clip(0.45 * px_per_in(row, z.mean()), 0.8, 2.6)))
    for pl in fw_ + fr_:
        q = pl.copy()
        q[:, 0] = -q[:, 0]
        xy, z = proj(row, q)
        if (z > 2).all():
            col = (236, 238, 242) if pl is fw_[0] else R15.POST_RED
            stroke_poly(ctx, xy, col, 1.0, float(np.clip(2.3 * px_per_in(row, z.mean()), 1.5, 40)))
    return back, front, s


def line_glow(ctx, row, x, col, a, width_in=12):
    if a <= 0:
        return
    bz = R22.board_z(abs(x)) - 4
    zs = np.linspace(-bz, bz, 60)
    pts = np.stack([np.full_like(zs, x), np.full_like(zs, 0.08), zs], 1)
    xy, z = proj(row, pts)
    if (z < 3).any():
        return
    w = float(np.clip(px_per_in(row, z.mean()) * width_in, 3, 30))
    stroke_poly(ctx, xy, col, 0.25 * a, w * 4)
    stroke_poly(ctx, xy, col, 0.95 * a, w)


def half_shade(ctx, row, a):
    if a <= 0:
        return
    pts = []
    for x in np.linspace(-R22.END_X, 0, 30):
        pts.append((x, R22.board_z(abs(x))))
    for x in np.linspace(0, -R22.END_X, 30):
        pts.append((x, -R22.board_z(abs(x))))
    xy, z = proj(row, R22.poly3(pts))
    fill_poly(ctx, xy, ORANGE, 0.16 * a)


def dots_line(ctx, row, a):
    if a <= 0:
        return
    pts = np.array([[DOT_LINE, 0.08, z] for z in np.linspace(-300, 300, 40)])
    xy, _ = proj(row, pts)
    ctx.set_dash([18, 14])
    stroke_poly(ctx, xy, INK, 0.85 * a, 5)
    ctx.set_dash([])
    for z in (-264.0, 264.0):
        p, _ = projected(row, np.array([DOT_LINE, 0.08, z]))
        ctx.set_source_rgba(ORANGE[0] / 255, ORANGE[1] / 255, ORANGE[2] / 255, a)
        ctx.arc(p[0], p[1], 16 + 4 * math.sin(time.time() * 0), 0, 2 * math.pi)
        ctx.stroke()


def trail(ctx, row, t, t0):
    if t <= t0 + 0.02:
        return
    ts = np.linspace(t0, t, 40)
    pts = np.array([puck_at(x) for x in ts])
    pts[:, 1] = 0.1
    xy, z = proj(row, pts)
    if (z < 3).any():
        return
    stroke_poly(ctx, xy, ORANGE, 0.18, 22)
    stroke_poly(ctx, xy, ORANGE, 0.85, 7)


def path_hint(ctx, row, t, a):
    """Gestrichelter Weg vom Puck über die gegnerische Torlinie (Hook)."""
    if a <= 0:
        return
    pts = np.array([X0 + (END - X0) * u for u in np.linspace(0, 1, 40)])
    pts[:, 1] = 0.1
    xy, z = proj(row, pts)
    if (z < 3).any():
        return
    ctx.set_dash([22, 16], -t * 90)
    stroke_poly(ctx, xy, ORANGE, 0.9 * a, 6)
    ctx.set_dash([])
    tip, _ = projected(row, END)
    prev, _ = projected(row, END - (END - X0) / np.linalg.norm(END - X0) * 60)
    d = (tip - prev) / (np.linalg.norm(tip - prev) + 1e-9)
    nrm = np.array([-d[1], d[0]])
    tri = np.array([tip + d * 14, tip - d * 22 + nrm * 18, tip - d * 22 - nrm * 18])
    fill_poly(ctx, tri, ORANGE, 0.9 * a)


def label_at(L, row, p, txt, col, dy, a, size=40):
    if a <= 0:
        return
    xy, z = projected(row, p)
    im = line_img(txt, size, 850, col, track=4)
    reveal(L, im, min(max(xy[0], 40 + im.width / 2), W - 40 - im.width / 2), xy[1] + dy, a)


def texts(L, t, row):
    A = VO_START
    if t < 1.65:
        for txt, cy, size in (("WHAT IS", 330, 130), ("ICING?", 480, 190)):
            put(L, R18.word_img(txt, size, INK, HALO), W / 2 - R18.word_img(txt, size, INK, HALO).width / 2,
                cy - R18.word_img(txt, size, INK, HALO).height / 2)
        reveal(L, line_img("NHL RULES EXPLAINED  ·  PART 2", 34, 800, ORANGE, track=8), W / 2, 220, 1.0,
               smooth(1.45, 1.65, t))
    if 3.0 <= t < T_REW0:
        fade = 1 - smooth(T_WH1 - 0.05, T_WH1 + 0.1, t)
        label_at(L, row, np.array([-560.0, 0, 0]), "OWN HALF", ORANGE, 0, smooth(3.0, 3.2, t) * fade, 52)
        label_at(L, row, np.array([GOAL_X, 0, -250.0]), "GOAL LINE", RED, 46, smooth(3.4, 3.6, t) * fade, 40)
    slam(L, "ICING.", 210, RED, W / 2, 960, t, T_WH1 + 0.03, T_BACK0 + 0.1, 1.9)
    if T_BACK0 + 0.2 <= t < T_REW0:
        label_at(L, row, DOT_OWN, "FACEOFF IN YOUR ZONE", INK, 90, smooth(T_BACK1 - 0.2, T_BACK1, t), 40)
        slam(L, "NO LINE CHANGE", 92, RED, W / 2, 960, t, A["zone"] + 1.15, T_REW0)
    if T_REW0 <= t < T_REW1 or T_REW2 <= t < T_REW3:
        reveal(L, line_img("<<  REWIND", 60, 900, INK, track=10), W / 2, 960, 1.0)
    if T_REW1 <= t < T_REW2:
        if t < T_DOTS_D:
            slam(L, "SINCE 2013–14:", 70, INK, W / 2, 900, t, A["race"] + 0.1)
            slam(L, "RACE TO THE DOTS", 96, ORANGE, W / 2, 1000, t, A["race"] + 1.25)
        slam(L, "ICING.", 190, RED, W / 2, 1000, t, T_DOTS_D + 0.02, T_REW2)
    if T_REW1 + 0.6 <= t < T_SHOT3 - 0.3:
        rc = racers(t)
        if rc:
            d, a_ = rc
            for p, s_, col in ((d, "D", BLUE), (a_, "A", ORANGE)):
                xy, _ = projected(row, p)
                gi = line_img(s_, 30, 900, INK)
                put(L, gi, xy[0] - gi.width / 2, xy[1] - gi.height / 2)
    if T_REW3 <= t < T_SHOT3 - 0.3:
        slam(L, "PLAY ON.", 170, GREEN, W / 2, 1000, t, T_DOTS_A + 0.02, T_SHOT3 - 0.3)
    if T_SHOT3 - 0.3 <= t < T_END0:
        slam(L, "SHORT-HANDED?", 104, INK, W / 2, 900, t, A["pk"])
        slam(L, "ICING ALLOWED.", 104, GREEN, W / 2, 1040, t, A["pk"] + 0.6)
    if t >= T_END0:
        slam(L, "WHICH RULE", 120, INK, W / 2, 330, t, A["cta"])
        slam(L, "SHOULD I EXPLAIN", 92, INK, W / 2, 455, t, A["cta"] + 0.25)
        slam(L, "NEXT?", 150, ORANGE, W / 2, 580, t, A["cta"] + 0.5)
        if t >= A["cta"] + 0.8:
            reveal(L, line_img("COMMENT BELOW  ·  FOLLOW FOR PART 3", 34, 800, INK, track=6), W / 2, 700,
                   c01((t - A["cta"] - 0.8) / 0.25))


# ================================================================= Bild
def compose(t, fidx):
    base, puck, cov = render3d(t, fidx)
    row, _ = cam_row_at(t)
    top = T_CRANE1 <= t < T_END0
    lo_s, lo_c = surface()
    if t < T_SHOT1 + 0.1:
        path_hint(lo_c, row, t, smooth(0.25, 0.5, t) * (1 - smooth(T_SHOT1 - 0.05, T_SHOT1 + 0.1, t)))
    if 1.3 <= t < T_REW0:
        half_shade(lo_c, row, smooth(VO_START["half"], VO_START["half"] + 0.3, t) * (1 - smooth(4.6, 4.8, t)))
        line_glow(lo_c, row, 0.0, RED, smooth(VO_START["half"], VO_START["half"] + 0.3, t) * (1 - smooth(4.6, 4.8, t)))
        line_glow(lo_c, row, GOAL_X, RED, smooth(VO_START["past"], VO_START["past"] + 0.3, t) * (1 - smooth(4.6, 4.8, t)), 4)
    if T_REW1 <= t < T_SHOT3 - 0.3:
        dots_line(lo_c, row, smooth(VO_START["race"] + 0.6, VO_START["race"] + 0.9, t))
    if T_SHOT1 < t < T_BACK0:
        trail(lo_c, row, t, T_SHOT1)
    if T_SHOT2 < t < T_REW2:
        trail(lo_c, row, t, T_SHOT2)
    if T_REW3 < t < T_SHOT3 - 0.3:
        trail(lo_c, row, t, T_REW3 + 0.05)
    if T_SHOT3 < t < T_END0:
        trail(lo_c, row, t, T_SHOT3)
    img = over(base, *surf_rgba(lo_s))
    nb, nf, n2 = draw_nets(row)
    img = over(img, *surf_rgba(nb))
    img = over(img, *surf_rgba(n2))
    pa = cov[..., None]
    img = img * (1 - pa) + puck * pa
    img = over(img, *surf_rgba(nf))
    hi_s, hi_c = surface()
    if top:
        puck_marker(hi_c, row, puck_at(t), t)
        rc = racers(t) if t >= T_REW1 + 0.6 else None
        if rc:
            token(hi_c, row, rc[0], BLUE, 34)
            token(hi_c, row, rc[1], ORANGE, 34)
        whistle_ring(hi_c, row, puck_at(T_WH1), t, T_WH1, RED)
        if racers(T_DOTS_D - 0.01):
            whistle_ring(hi_c, row, racers(T_DOTS_D - 0.01)[0], t, T_DOTS_D, RED)
        if racers(T_DOTS_A - 0.01):
            whistle_ring(hi_c, row, racers(T_DOTS_A - 0.01)[1], t, T_DOTS_A, GREEN)
        if T_BACK1 <= t < T_REW0:
            whistle_ring(hi_c, row, DOT_OWN, t, T_BACK1, ORANGE)
    elif t < T_CRANE1:
        puck_marker(hi_c, row, puck_at(t), t)
    img = over(img, *surf_rgba(hi_s))
    for tw in (T_WH1, T_DOTS_D):
        if tw <= t < tw + 0.3:
            a = 0.2 * (1 - (t - tw) / 0.3)
            img = img * (1 - a) + np.array([1.0, 0.1, 0.12], np.float32) * a
    if T_REW0 <= t < T_REW1 or T_REW2 <= t < T_REW3:
        rng = np.random.default_rng(int(t * 1000))
        img = img * 0.92 + 0.04
        for _ in range(7):
            y0, hh = int(rng.uniform(0, H - 40)), int(rng.uniform(6, 34))
            img[y0:y0 + hh] = np.roll(img[y0:y0 + hh], int(rng.uniform(-45, 45)), 1)
        img[::4] *= 0.93
    img = np.clip(img, 0, 1)
    pil = Image.fromarray((img * 255).astype(np.uint8)).convert("RGBA")
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    texts(L, t, row)
    pil.alpha_composite(L)
    arr = np.asarray(pil.convert("RGB")).astype(np.float32) / 255
    lc = min([t - c for c in (T_WH1, T_DOTS_D, T_DOTS_A) if t >= c] + [t + 0.5])
    zp = 1 + 0.035 * math.exp(-lc * 14)
    if zp > 1.002:
        im2 = Image.fromarray((arr * 255).astype(np.uint8))
        w2, h2 = W / zp, H / zp
        im2 = im2.transform((W, H), Image.EXTENT, ((W - w2) / 2, (H - h2) / 2, (W + w2) / 2, (H + h2) / 2), Image.BILINEAR)
        arr = np.asarray(im2).astype(np.float32) / 255
    arr = arr * (0.55 + 0.45 * vignette())
    arr += np.random.default_rng(fidx).normal(0, 0.008, arr.shape[:2])[..., None]
    return (np.clip(arr, 0, 1) * 255).astype(np.uint8)


# ================================================================= Ton: Musik + Voiceover
SR = 44100


def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(23)
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

    def slapshot(vol=1.0):
        x = tt(0.3)
        return np.tanh((np.sin(2 * np.pi * np.cumsum(300 * (1 + 2 * np.exp(-x * 90))) / SR) * np.exp(-x * 20)
                        + hp(noise(0.3), 2) * np.exp(-x * 70) * 1.3) * 1.6) * vol

    def slide_sfx(dur, vol=0.3):
        x = tt(dur)
        return hp(lp(noise(dur), 3), 20) * np.exp(-x * 1.5) * vol

    def rewind(dur=0.25, vol=0.6):
        x = tt(dur)
        f = 900 + 2400 * (x / dur) ** 1.5
        return np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.25 * lp(noise(dur), 3) * vol

    def ding(vol=0.4):
        x = tt(0.9)
        return (np.sin(2 * np.pi * 1318.5 * x) + 0.6 * np.sin(2 * np.pi * 1760 * x) * (x > 0.09)) * np.exp(-x * 5) * vol

    roots = [55.0, 43.65, 49.0, 41.2]
    mel = [880.0, 1046.5, 1318.5, 1046.5, 987.8, 880.0, 784.0, 659.25]
    for k8 in range(int(DUR / (B / 2))):
        tb = k8 * B / 2
        b = k8 / 2
        pos = b % 4
        if T_REW0 <= tb < T_REW1 or T_REW2 <= tb < T_REW3 or tb > DUR - 0.5:
            continue
        if pos in (0.0, 2.5):
            put_(mus, kick(), tb)
        if pos in (1.0, 3.0):
            put_(mus, clap(), tb)
        put_(mus, hat(0.12 if k8 % 2 == 0 else 0.07), tb, pan=0.3)
        if pos == 0.0:
            put_(mus, b808(roots[int(b // 4) % 4], 2.3 * B), tb)
        put_(mus, bell(mel[k8 % 8]), tb, pan=-0.2)
    for ts in (T_SHOT1, T_SHOT2, T_REW3 + 0.05, T_SHOT3):
        put_(sfx, slapshot(0.9), ts)
        put_(sfx, slide_sfx(1.6, 0.25), ts + 0.05)
    for tw in (T_WH1, T_DOTS_D):
        put_(sfx, whistle(0.7, 0.55), tw)
        put_(sfx, stamp(1.0), tw + 0.03)
    put_(sfx, ding(0.5), T_DOTS_A)
    put_(sfx, stamp(0.6), T_DOTS_A)
    put_(sfx, ding(0.4), VO_START["pk"] + 0.6)
    for r0, r1 in ((T_REW0, T_REW1), (T_REW2, T_REW3)):
        put_(sfx, rewind(r1 - r0, 0.7), r0)
    put_(sfx, stamp(0.5), VO_START["zone"] + 1.15)
    put_(sfx, rewind(0.5, 0.25)[::-1].copy(), T_END0)                 # Whoosh in die Schlussfahrt
    put_(sfx, stamp(0.7), VO_START["cta"] + 0.5)
    # Voiceover
    voice = np.zeros(n)
    for k in VO_KEYS:
        tmp = os.path.join(HERE, f"_vo_{k}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "voice", f"{VO_PREFIX}_{k}.wav"),
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
    duck = 1 - 0.6 * np.clip(venv / 0.06, 0, 1)
    mus /= np.max(np.abs(mus)) + 1e-9
    sfx /= np.max(np.abs(sfx)) + 1e-9
    mix = mus * 0.5 * duck[:, None] + sfx * 0.55 + voice[:, None] * 1.0
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
    for k in VO_KEYS:                                                # Sätze dürfen sich nicht überlappen
        nxt = VO_KEYS[VO_KEYS.index(k) + 1] if k != VO_KEYS[-1] else None
        if nxt and VO_START[k] + VO_DUR[k] > VO_START[nxt]:
            print(f"Warnung: Satz {k} überlappt {nxt} ({VO_START[k] + VO_DUR[k]:.2f} > {VO_START[nxt]:.2f})")
    make_audio("audio_icing.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_icing.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
           "-ar", "44100", "-shortest", "-movflags", "+faststart", "reel23_icing.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(0.8, 9999)).save("reel23_thumbnail.jpg", quality=92)
    print("fertig: reel23_icing.mp4")


if __name__ == "__main__":
    main()
