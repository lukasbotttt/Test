"""Reel 34: "WHY DO DETROIT FANS THROW OCTOPUSES ON THE ICE?" – Hockey-Kultur im dunklen Arena-Look (~17 s).

Warum: Part 7 (dunkler 3D-Arena-Look) hatte die beste Retention der Serie (1 s 83 %, Ende 43 %, 21,8k Views).
Neugier-Thema für Gelegenheitsfans + Teilen ("Wusstest du das?"), Hook: 3D-Krake klatscht in Bild 0 aufs Eis.
Fakten: siehe FACTS unten (Faktencheck mit Quellen).
Look: Arena-Bauten, Spotlicht und LED-Tafeln aus reel30_fight.py, 3D-Krake aus octopus3d.py.
Stimme: Kokoro "Michael", 1,08x. Aufruf: python3 reel34_octopus.py vo | audio | prev 1.0,4.2 out.jpg | (Video)
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
from scipy.ndimage import gaussian_filter

import mesh3d as M3
import octopus3d as O
import puck3d as P3
import reel15_puck as R15
import reel26_overglass as R26
import reel28_emptynet as R28
import reel30_fight as F
from reel15_puck import W, H, FPS, c01, smooth, sio, e_out, e_in, lerp, line_img, reveal, put, projected, px_per_in, \
    surface, surf_rgba, over
from reel22_trapezoid import slam

HERE = R15.HERE
SPP = int(os.environ.get("SPP", "8"))
KSUB = int(os.environ.get("KSUB", "10"))
SHUTTER = 0.5 / FPS
WHITE = (255, 255, 255)
RED = (235, 40, 50)
ORANGE = (255, 146, 60)
GOLD = (255, 200, 70)
GREY = (150, 156, 170)
LED = (255, 52, 40)
TEMPO = 1.08

VO_LINES = [
    ("q", "Why is THIS on the rink?"),
    ("born", "Detroit, nineteen fifty-two, Stanley Cup Final."),
    ("arms", "Eight arms, for the eight wins it took to win the Cup."),
    ("won", "Detroit won all eight."),
    ("today", "Today you would need sixteen. Two octopuses."),
    ("cta", "Next: why do fans throw hats? Follow so you don't miss it."),
]
VO_KEYS = [k for k, _ in VO_LINES]
VO_START = {"q": 0.1, "born": 1.5, "arms": 4.15, "won": 6.75, "today": 8.05, "cta": 10.6}
DUR = 14.1
WT = {                                           # Wortanfänge (s nach Satzbeginn, nach 1,08x), faster-whisper
    "q": [0.0, 0.16, 0.34, 0.48, 0.7, 0.8],
    "born": [0.0, 0.26, 1.1, 1.66, 2.0],
    "arms": [0.0, 0.16, 0.44, 0.86, 0.94, 1.14, 1.36, 1.52, 1.66, 1.82, 1.96, 2.1],
    "won": [0.0, 0.24, 0.5, 0.66],
    "today": [0.0, 0.18, 0.38, 0.48, 0.62, 1.42, 1.54],
    "cta": [0.0, 0.22, 0.4, 0.52, 0.72, 1.08, 1.9, 1.96, 2.22, 2.34, 2.52, 2.64],
}


def at(key, s):
    return VO_START[key] + s


def wt(key, i):
    return VO_START[key] + WT[key][i]


T_LAND = 0.42                                    # Krake 1 landet
T_UP0, T_UP1 = 1.4, 2.1                          # Hook -> Draufsicht
T_ARMS = wt("arms", 0)                           # Nummern 1–8 an den Armen
T_WON = VO_START["won"]
T_CUP = wt("won", 3) + 0.2
T_LAND2 = wt("today", 4) + 0.05                  # zweite Krake bei "sixteen"
T_CTA = VO_START["cta"]
C1 = (0.0, 0.0)
C2 = (66.0, -40.0)
SCALE = 1.35


# ================================================================= Kraken
def octo_state(t, which):
    """(center_xz, y0, s, wob, heading, t_phase, sichtbar)"""
    tl = T_LAND if which == 0 else T_LAND2
    c = C1 if which == 0 else C2
    head = 0.5 if which == 0 else -1.1
    if which == 1 and t < tl - 0.6:
        return None
    if t < tl:
        u = c01((t - (tl - 0.62)) / 0.62)
        y0 = lerp(34.0, 0.0, u * u)
        return c, y0, 0.0, 0.0, head + 0.8 * (1 - u), 0.0
    lt = t - tl
    s = e_out(c01(lt / 0.3), 2)
    wob = math.exp(-lt * 3.2)
    return c, 0.0, s, wob, head, lt


def octo_meshes(t):
    out = []
    for which in (0, 1):
        st = octo_state(t, which)
        if st is None:
            continue
        c, y0, s, wob, head, ph = st
        out += O.octopus_mesh(c, y0, s, wob, head, SCALE, ph)
    return out


def tips(t, which):
    st = octo_state(t, which)
    if st is None:
        return None
    c, y0, s, wob, head, ph = st
    return O.tip_positions(c, y0, s, wob, head, SCALE, ph)


# ================================================================= Kamera
def hook_cam(t):
    p0, p1 = np.array([-62.0, 40.0, 128.0]), np.array([-54.0, 34.0, 108.0])
    return p0 + (p1 - p0) * e_out(c01(t / T_UP0), 2), np.array([0.0, 7.0, 0.0]), 46.0


def top_cam(t):
    s = c01((t - T_UP1) / 4.0)
    return np.array([-28.0, 175.0, 92.0]) + np.array([4.0, -16.0, -6.0]) * sio(s), np.array([2.0, 0.0, -24.0]), 44.0


def wide_cam(t):
    s = c01((t - (T_WON - 0.2)) / 3.0)
    return np.array([-40.0, 215.0, 150.0]) + np.array([6.0, -12.0, -8.0]) * sio(s), np.array([30.0, 0.0, -20.0]), 46.0


def end_cam(t):
    s = c01((t - T_CTA) / 3.0)
    return np.array([-70.0, 52.0, 150.0]) + np.array([8.0, -4.0, -14.0]) * sio(s), np.array([28.0, 8.0, -18.0]), 50.0


def cam(t):
    if t < T_UP0:
        p, g, f = hook_cam(t)
    elif t < T_UP1:
        p, g, f = R28.blend_cam(hook_cam(T_UP0), top_cam(T_UP1), sio((t - T_UP0) / (T_UP1 - T_UP0)))
    elif t < T_WON - 0.25:
        p, g, f = top_cam(t)
    elif t < T_WON + 0.45:
        p, g, f = R28.blend_cam(top_cam(T_WON - 0.25), wide_cam(T_WON + 0.45),
                                sio((t - T_WON + 0.25) / 0.7))
    elif t < T_CTA - 0.3:
        p, g, f = wide_cam(t)
    elif t < T_CTA + 0.5:
        p, g, f = R28.blend_cam(wide_cam(T_CTA - 0.3), end_cam(T_CTA + 0.5), sio((t - T_CTA + 0.3) / 0.8))
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
        pk[j] = (0.0, -50.0, 0.0, 0.0, 0.0, 0.0, tk)
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, SPP, fidx + 34, cams, lens, pk, R15.logo_tex(), base, puck, cov)
    return P3.tonemap(base)


# ================================================================= Licht
def spots(t):
    out = [(C1[0], C1[1], 105.0, 0.62, (1.0, 0.96, 0.9))]
    k2 = smooth(T_LAND2 - 0.5, T_LAND2 - 0.1, t)
    if k2 > 0:
        out.append((C2[0], C2[1], 95.0, 0.6 * k2, (1.0, 0.96, 0.9)))
    flash = math.exp(-max(0.0, t - T_LAND) * 6) * (t >= T_LAND)
    out.append((C1[0], C1[1], 70.0, 0.6 * flash, (1.0, 0.5, 0.55)))
    cup = smooth(T_CUP - 0.05, T_CUP + 0.15, t) * (1 - smooth(T_LAND2 - 0.6, T_LAND2 - 0.2, t))
    if cup > 0:
        out.append((C1[0], C1[1], 180.0, 0.35 * cup, (1.0, 0.8, 0.35)))
    return out


def light_map(row, t, mesh_a, mesh_pos):
    x, z, hit = F.ice_hit(row)
    k = np.clip(mesh_a, 0, 1)
    safe = np.where(k[..., None] > 0.01, mesh_pos / np.maximum(k, 1e-3)[..., None], 0.0)
    x = x * (1 - k) + safe[..., 0] * k
    z = z * (1 - k) + safe[..., 2] * k
    hit = np.maximum(hit.astype(np.float32), k)
    amb = np.array([0.055, 0.065, 0.105], np.float32)
    L = np.broadcast_to(amb, (H, W, 3)).copy()
    haze = np.zeros((H, W), np.float32)
    for sx, sz, rad, kk, col in spots(t):
        if kk <= 0.01:
            continue
        g = np.exp(-(((x - sx) ** 2 + (z - sz) ** 2) / (rad * rad))).astype(np.float32) * hit
        L += g[..., None] * (kk * np.array(col, np.float32))
        haze += g * kk
    return L, haze


# ================================================================= Overlays
_BADGE = {}


def badge_img(n, col=ORANGE, size=46):
    key = (n, col, size)
    if key not in _BADGE:
        from PIL import ImageDraw
        s = 3
        r = size // 2 + 6
        im = Image.new("RGBA", ((2 * r + 10) * s, (2 * r + 10) * s), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        c = (r + 5) * s
        d.ellipse((c - r * s, c - r * s, c + r * s, c + r * s), fill=col + (255,), outline=(255, 255, 255, 255),
                  width=3 * s)
        im = im.resize((im.width // s, im.height // s), Image.LANCZOS)
        tx = line_img(str(n), size, 900, (20, 20, 28))
        im.alpha_composite(tx, (int(im.width / 2 - tx.width / 2), int(im.height / 2 - tx.height / 2) + 1))
        _BADGE[key] = im
    return _BADGE[key]


def arm_numbers(L, row, t):
    """Nummern 1–8 (bzw. 1–16) an den Armspitzen."""
    if t < T_ARMS - 0.05 or t >= T_CTA - 0.2:
        return
    fade = 1 - smooth(T_CTA - 0.45, T_CTA - 0.2, t)
    tp = tips(t, 0)
    for k in range(8):
        t0 = T_ARMS + 0.05 + 0.13 * k
        if t < t0:
            continue
        xy, z = projected(row, tp[k] + [0, 2.0, 0])
        if z <= 0:
            continue
        s = 0.5 + 0.5 * e_out((t - t0) / 0.18, 3) + 0.3 * math.exp(-(t - t0) * 9)
        im = badge_img(k + 1)
        im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BILINEAR)
        if fade < 1:
            im.putalpha(im.getchannel("A").point(lambda v: int(v * fade)))
        put(L, im, xy[0] - im.width / 2, xy[1] - im.height / 2)
    tp2 = tips(t, 1)
    if tp2 is not None and t >= T_LAND2:
        for k in range(8):
            t0 = T_LAND2 + 0.2 + 0.06 * k
            if t < t0:
                continue
            xy, z = projected(row, tp2[k] + [0, 2.0, 0])
            if z <= 0:
                continue
            s = 0.5 + 0.5 * e_out((t - t0) / 0.18, 3)
            im = badge_img(k + 9, GOLD, 40)
            im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BILINEAR)
            if fade < 1:
                im.putalpha(im.getchannel("A").point(lambda v: int(v * fade)))
            put(L, im, xy[0] - im.width / 2, xy[1] - im.height / 2)


def led(L, txt, col, cx, cy, a, size=74):
    if a <= 0:
        return
    im = F.led_img(txt, col, size)
    if a < 1:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    put(L, im, cx - im.width / 2, cy - im.height / 2)


def word(txt, size, col, gl):
    return F.word(txt, size, col, gl)


def texts(L, t, row):
    blue_gl, red_gl, or_gl = (90, 110, 160), (160, 20, 30), (170, 70, 10)
    if t < T_UP0 + 0.1:                                              # Hook: ganze Frage ab Bild 0
        k = 1 - smooth(T_UP0 - 0.1, T_UP0 + 0.1, t)
        for txt, cy, size, col, gl in (("WHY IS THIS", 360, 140, WHITE, blue_gl),
                                       ("ON THE RINK?", 530, 140, RED, red_gl)):
            im = word(txt, size, col, gl)
            if im.width > 1000:
                im = im.resize((1000, int(im.height * 1000 / im.width)), Image.LANCZOS)
            if k < 1:
                im = im.copy()
                im.putalpha(im.getchannel("A").point(lambda v: int(v * k)))
            put(L, im, W / 2 - im.width / 2, cy - im.height / 2)
    # 1952 – Herkunft
    tb = VO_START["born"]
    if tb - 0.05 <= t < T_ARMS:
        a = smooth(tb - 0.05, tb + 0.15, t) * (1 - smooth(T_ARMS - 0.2, T_ARMS, t))
        led(L, "1952", LED, W / 2, 330, a, 120)
        if t >= wt("born", 2) - 0.05:
            reveal(L, line_img("STANLEY CUP FINAL", 54, 850, WHITE, track=6), W / 2, 470,
                   c01((t - wt("born", 2) + 0.05) / 0.25), smooth(T_ARMS - 0.2, T_ARMS, t))
            reveal(L, line_img("PETE & JERRY CUSIMANO · DETROIT OLYMPIA", 30, 750, GREY, track=6), W / 2, 540,
                   c01((t - wt("born", 2) - 0.25) / 0.25), smooth(T_ARMS - 0.2, T_ARMS, t))
    # 8 Arme = 8 Siege
    slam(L, "8 ARMS", 150, ORANGE, W / 2, 360, t, wt("arms", 1) - 0.05, T_WON, glow=or_gl)
    slam(L, "= 8 WINS", 130, WHITE, W / 2, 510, t, wt("arms", 5) - 0.05, T_WON, glow=blue_gl)
    if wt("arms", 9) <= t < T_WON:
        reveal(L, line_img("2 ROUNDS · BEST OF 7 · BACK THEN", 34, 800, GREY, track=6), W / 2, 620,
               c01((t - wt("arms", 9)) / 0.25), smooth(T_WON - 0.2, T_WON, t))
    T_WEND = VO_START["today"] + 0.45             # 8–0 / Stanley Cup länger stehen lassen
    # Detroit gewinnt alle 8
    if T_WON - 0.05 <= t < T_WEND:
        a = smooth(T_WON - 0.05, T_WON + 0.15, t) * (1 - smooth(T_WEND - 0.2, T_WEND, t))
        led(L, "SEMIS  4–0", LED, 295, 1520, a * smooth(wt("won", 1), wt("won", 1) + 0.12, t), 60)
        led(L, "FINAL  4–0", LED, 785, 1520, a * smooth(wt("won", 3), wt("won", 3) + 0.12, t), 60)
    slam(L, "8–0", 210, WHITE, W / 2, 370, t, wt("won", 2) - 0.05, T_WEND, glow=blue_gl)
    slam(L, "STANLEY CUP", 118, GOLD, W / 2, 540, t, T_CUP - 0.05, T_WEND, glow=or_gl)
    # Heute 16
    slam(L, "TODAY: 16 WINS", 104, WHITE, W / 2, 370, t, wt("today", 4) - 0.05, T_CTA, glow=blue_gl)
    slam(L, "= 2 OCTOPUSES", 104, RED, W / 2, 500, t, wt("today", 5) - 0.05, T_CTA, glow=red_gl)
    if wt("today", 6) + 0.3 <= t < T_CTA:
        reveal(L, line_img("4 ROUNDS · BEST OF 7", 34, 800, GREY, track=6), W / 2, 600,
               c01((t - wt("today", 6) - 0.3) / 0.25), smooth(T_CTA - 0.2, T_CTA, t))
    # Frage
    if t >= T_CTA:
        slam(L, "NEXT:", 80, ORANGE, W / 2, 330, t, T_CTA, glow=or_gl)
        slam(L, "WHY DO FANS", 110, WHITE, W / 2, 450, t, wt("cta", 1) - 0.05, glow=blue_gl)
        slam(L, "THROW HATS?", 130, WHITE, W / 2, 590, t, wt("cta", 4) - 0.05, glow=blue_gl)
        slam(L, "FOLLOW", 170, RED, W / 2, 1380, t, wt("cta", 6) - 0.05, glow=red_gl)
        if t >= wt("cta", 7) + 0.2:
            reveal(L, line_img("SO YOU DON'T MISS IT", 40, 850, WHITE, track=6), W / 2, 1500,
                   c01((t - wt("cta", 7) - 0.2) / 0.25))


def splash(ctx, row, t):
    """Aufprall-Ring + Spritzer bei der Landung."""
    for tl, c in ((T_LAND, C1), (T_LAND2, C2)):
        li = t - tl
        if not 0 <= li < 0.5:
            continue
        xy, z = projected(row, np.array([c[0], 0.5, c[1]]))
        if z <= 0:
            continue
        q = e_out(li / 0.5, 3)
        k = px_per_in(row, z)
        F.ring2d(ctx, xy, k * (20 + 70 * q), (255, 255, 255), 0.8 * (1 - q), 7 * (1 - q) + 2)
        ctx.set_source_rgba(1, 1, 1, 0.85 * (1 - q))
        ctx.set_line_width(5)
        for j in range(12):
            a = j * math.pi / 6 + 0.3
            r0, r1 = k * (18 + 40 * q), k * (26 + 70 * q)
            ctx.move_to(xy[0] + math.cos(a) * r0, xy[1] + math.sin(a) * r0 * 0.6)
            ctx.line_to(xy[0] + math.cos(a) * r1, xy[1] + math.sin(a) * r1 * 0.6)
        ctx.stroke()


def brand(L, t):
    """Logo-Lockup oben (nach der Hook) wie in den neuen Videos."""
    if t < T_UP0:
        return
    import reel33_lines_neon as N
    sp = N.brand_img("bladesandpucks_lockup_transparent.png", 300)
    a = 0.92 * smooth(T_UP0, T_UP0 + 0.3, t)
    im = sp.img
    if a < 1:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    put(L, im, W / 2 - im.width / 2, 175 - im.height / 2)


# ================================================================= Bild
def compose(t, fidx):
    base = render3d(t, fidx)
    row, _ = cam_row_at(t)
    campos = cam(t)[0]
    lo_s, lo_c = surface()
    hi_s, hi_c = surface()
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img = over(base, *surf_rgba(lo_s))
    meshes = F.ARENA + octo_meshes(t)
    m_rgb, m_a, shadow, plane_a, m_pos = M3.render(meshes, row, W, H, campos, extra_planes=[(F.GLASS_ALL, 1.0)],
                                                   shadow_light=(0.03, 1.0, 0.05), want_pos=True)
    img = img * (1 - 0.5 * shadow[..., None])
    img = img * (1 - m_a[..., None]) + m_rgb
    k = (0.22 * plane_a)[..., None]
    img = img * (1 - k) + np.array([0.70, 0.82, 0.94], np.float32) * k
    Lm, haze = light_map(row, t, m_a, m_pos)
    img = img * Lm
    img = img + (R26.glass_streaks() * plane_a * 0.05)[..., None]
    hz = gaussian_filter(haze[::4, ::4], 18)
    hz = np.asarray(Image.fromarray((np.clip(hz, 0, 2) * 120).astype(np.uint8)).resize((W, H), Image.BILINEAR),
                    np.float32) / 120
    img = img + hz[..., None] * np.array([0.05, 0.055, 0.07], np.float32)
    splash(hi_c, row, t)
    img = over(img, *surf_rgba(hi_s))
    for t0, col in ((T_LAND, (1.0, 1.0, 1.0)), (T_CUP, (1.0, 0.8, 0.3)), (T_LAND2, (1.0, 1.0, 1.0))):
        if t0 <= t < t0 + 0.25:
            a = 0.14 * (1 - (t - t0) / 0.25)
            img = img * (1 - a) + np.array(col, np.float32) * a
    img = np.clip(img, 0, 1)
    pil = Image.fromarray((img * 255).astype(np.uint8)).convert("RGBA")
    arm_numbers(L, row, t)
    texts(L, t, row)
    brand(L, t)
    pil.alpha_composite(L)
    arr = np.asarray(pil.convert("RGB")).astype(np.float32) / 255
    lc = min([t - c for c in (T_LAND, T_CUP, T_LAND2) if t >= c] + [t + 0.5])
    zp = 1 + 0.045 * math.exp(-lc * 12)
    if zp > 1.002:
        im2 = Image.fromarray((arr * 255).astype(np.uint8))
        w2, h2 = W / zp, H / zp
        im2 = im2.transform((W, H), Image.EXTENT, ((W - w2) / 2, (H - h2) / 2, (W + w2) / 2, (H + h2) / 2),
                            Image.BILINEAR)
        arr = np.asarray(im2).astype(np.float32) / 255
    arr = arr * F.vignette()
    arr += np.random.default_rng(fidx).normal(0, 0.012, arr.shape[:2])[..., None]
    return (np.clip(arr, 0, 1) * 255).astype(np.uint8)


# ================================================================= Ton
SR = 44100


def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(34)
    mus = np.zeros((n, 2))
    sfx = np.zeros((n, 2))
    B = 60 / 126

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

    def snare(vol=1.0):
        x = tt(0.35)
        return (hp(noise(0.35), 3) * np.exp(-x * 16) * 0.7 + np.sin(2 * np.pi * 185 * x) * np.exp(-x * 22) * 0.5) * vol

    def hat(vol=0.1):
        return hp(noise(0.04), 1) * np.exp(-tt(0.04) * 150) * vol

    def sub(freq, dur):
        x = tt(dur)
        f = freq * (1 + 0.6 * np.exp(-x * 9))
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * 2.6) * np.minimum(x / 0.004, 1) * np.exp(-x * 1.1) * 0.85

    def organ(freq, dur, vol=0.12):
        x = tt(dur)
        sig = sum(np.sin(2 * np.pi * freq * m * x) / m for m in (1, 2, 3, 4, 6))
        env = np.minimum(x / 0.02, 1) * np.clip((dur - x) / 0.05, 0, 1)
        return lp(sig, 2) * env * vol

    def splat(vol=0.9):
        x = tt(0.5)
        wet = lp(noise(0.5), 3) * np.exp(-x * 14)
        body = np.sin(2 * np.pi * np.cumsum(90 + 120 * np.exp(-x * 25)) / SR) * np.exp(-x * 12)
        return np.tanh((wet * 1.2 + body) * 2.0) * vol

    def crowd(dur=2.5, vol=0.4):
        x = tt(dur)
        sig = lp(noise(dur), 12) - lp(noise(dur), 60) * 0.6
        return sig * np.sin(np.pi * np.clip(x / dur, 0, 1)) ** 0.8 * vol * 2.0

    def pop(vol=0.4, f=900):
        x = tt(0.09)
        return np.sin(2 * np.pi * np.cumsum(f * (1 + 1.5 * np.exp(-x * 60))) / SR) * np.exp(-x * 45) * vol

    def whoosh(dur=0.4, vol=0.4):
        x = tt(dur)
        return hp(lp(noise(dur), 6), 40) * np.sin(np.pi * x / dur) ** 2 * vol

    def fall(dur=0.6, vol=0.3):
        x = tt(dur)
        f = 1400 - 900 * (x / dur)
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.3 + hp(lp(noise(dur), 5), 30) * 0.7) * (x / dur) ** 1.5 * vol

    roots = [55.0, 55.0, 65.41, 49.0]
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
            put_(mus, snare(0.85), tb)
        if not hook:
            put_(mus, hat(0.1 if k8 % 2 == 0 else 0.06), tb, pan=0.3)
        if pos == 0.0:
            put_(mus, sub(roots[int(b // 4) % 4], 2.6 * B), tb)
    put_(sfx, fall(0.45, 0.3), T_LAND - 0.45)
    put_(sfx, splat(1.0), T_LAND)
    put_(sfx, crowd(2.6, 0.4), T_LAND + 0.05)
    put_(sfx, whoosh(0.5, 0.35), T_UP0)
    for k in range(8):
        put_(sfx, pop(0.35, 700 + 70 * k), T_ARMS + 0.05 + 0.13 * k)
    put_(sfx, whoosh(0.5, 0.35), T_WON - 0.25)
    for i, f in enumerate((392.0, 523.25, 659.25, 783.99)):            # Stadion-Orgel zum Cup
        put_(sfx, organ(f, 0.22 if i < 3 else 0.6, 0.14), T_CUP + 0.12 * i)
    put_(sfx, crowd(2.2, 0.45), T_CUP)
    put_(sfx, fall(0.45, 0.3), T_LAND2 - 0.45)
    put_(sfx, splat(0.9), T_LAND2)
    for k in range(8):
        put_(sfx, pop(0.3, 1000 + 50 * k), T_LAND2 + 0.2 + 0.06 * k)
    put_(sfx, whoosh(0.4, 0.3), T_CTA - 0.3)
    voice = np.zeros(n)
    for k in VO_KEYS:
        tmp = os.path.join(HERE, f"_vo_{k}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "voice", f"reel34_{k}.wav"),
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
    mix = mus * 0.38 * duck[:, None] + sfx * 0.5 * sduck[:, None] + voice[:, None] * 1.0
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
    tts_kokoro.synth(VO_LINES, os.path.join(HERE, "voice", "reel34"), speed=1.2)


def check_vo():
    with open(os.path.join(HERE, "voice", "reel34_timing.json")) as f:
        vo_dur = {k: v / TEMPO for k, v in json.load(f).items()}
    for i, k in enumerate(VO_KEYS):
        nxt = VO_START[VO_KEYS[i + 1]] if i + 1 < len(VO_KEYS) else DUR - 0.2
        if VO_START[k] + vo_dur[k] > nxt + 0.3:
            print(f"Warnung: Satz {k} zu lang ({VO_START[k] + vo_dur[k]:.2f} > {nxt:.2f})")


def remux():
    os.chdir(HERE)
    make_audio("audio_octopus.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "reel34_octopus.mp4", "-i", "audio_octopus.wav", "-map",
                    "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-af",
                    "loudnorm=I=-14:TP=-1.0:LRA=9", "-ar", "44100", "-shortest", "-movflags", "+faststart",
                    "_tmp_octo.mp4"], check=True)
    os.replace("_tmp_octo.mp4", "reel34_octopus.mp4")


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
    make_audio("audio_octopus.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_octopus.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
           "-ar", "44100", "-shortest", "-movflags", "+faststart", "reel34_octopus.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(0.15, 9999)).save("reel34_thumbnail.jpg", quality=92)
    print("fertig: reel34_octopus.mp4")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "vo":
        make_voice()
    elif len(sys.argv) > 1 and sys.argv[1] == "audio":
        remux()
    elif len(sys.argv) > 1 and sys.argv[1] == "prev":
        preview(sys.argv[2].split(","), sys.argv[3])
    else:
        main()
