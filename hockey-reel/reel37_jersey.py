"""Reel 37: "WHY IS THIS A PENALTY IN THE NHL?" – eingestecktes Trikot (weißer Studio-Look, ~15,8 s).

Warum: Trend-Thema der Saison 2026-27 (NHL setzt die Regel wieder durch, Preseason-Strafe am 24.9.2026 ging viral),
absurd + sofort verständlich -> Shares/Kommentare. Muster der Hits: rätselhaftes Objekt + "Why is THIS…?" in Bild 0.
Allgemeine Regel, keine Teams/Spieler.
Fakten (Recherche 23.10.2026):
- NHL Rule 9.5 (2026-27): Schutzausrüstung (außer Handschuhe, Helm, Halsschutz, Goalie-Schienen) muss UNTER der
  Uniform getragen werden (Regelbuch-PDF media.nhl.com).
- Durchsetzung 2026-27 (Friedman/Sportsnet, berichtet von AP/TSN, theScore, THN, Daily Faceoff): Trikot muss zu
  Beginn jedes Shifts draußen sein; erst Verwarnung, danach 2-Minuten-Strafe.
- Letzte Strafen dafür 2013 (AP/TSN); im Sept. 2026 wieder gepfiffen (Preseason, 2-Min-Strafe).
Bilder: Bande, Glas, Tore (mesh3d), Eis (Raytracer), Trikot + Hose als schwebende Kleidung (kit3d.py), kein Körper.
Stimme: Kokoro "Michael", 1,08x. Aufruf: python3 reel37_jersey.py vo | audio | prev 0.5,3.0 out.jpg | (Video)
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

import hats3d as HT
import kit3d as K
import mesh3d as M3
import puck3d as P3
import reel15_puck as R15
import reel18_dangle as R18
import reel26_overglass as R26
import reel28_emptynet as R28
from reel15_puck import (W, H, FPS, c01, smooth, sio, e_out, lerp, blend_up, line_img, reveal, put, projected,
                         px_per_in, surface, surf_rgba, over)
from reel22_trapezoid import slam

HERE = R15.HERE
SPP = int(os.environ.get("SPP", "8"))
KSUB = int(os.environ.get("KSUB", "6"))
SHUTTER = 0.5 / FPS
INK, ORANGE = R15.INK, R15.ORANGE
RED = (225, 30, 40)
GREEN = (30, 160, 80)
YELLOW = (235, 180, 0)
HALO = (255, 255, 255)
NAVY = (38, 35, 52)
TEMPO = 1.08

VO_LINES = [
    ("q", "Why is THIS a penalty in the NHL?"),
    ("rule", "Protective gear has to be worn under the uniform. So every shift starts with the jersey untucked."),
    ("pen", "Tucked anyway? First, a warning. Then, two minutes."),
    ("hist", "It hadn't been called since twenty thirteen. This season, it's back."),
    ("cta", "Should this be a penalty? Follow for more rules."),
]
VO_KEYS = [k for k, _ in VO_LINES]
VO_START = {"q": 0.1, "rule": 2.1, "pen": 7.25, "hist": 9.7, "cta": 12.95}
DUR = 15.8
WT = {                                           # Wortanfänge (s nach Satzbeginn, nach 1,08x), faster-whisper
    "q": [0.0, 0.14, 0.26, 0.36, 0.44, 0.72, 0.98, 1.08],
    "rule": [0.0, 0.34, 0.6, 0.9, 1.06, 1.16, 1.42, 1.58, 1.74, 2.62, 2.72, 2.94, 3.22, 3.6, 3.84, 3.94, 4.1],
    "pen": [0.0, 0.12, 0.74, 0.9, 1.04, 1.54, 1.62, 1.82],
    "hist": [0.0, 0.08, 0.3, 0.4, 0.64, 0.88, 1.88, 2.06, 2.38, 2.68],
    "cta": [0.0, 0.12, 0.26, 0.4, 0.46, 1.12, 1.3, 1.56, 1.72],
}


def wt(key, i):
    return VO_START[key] + WT[key][i]


T_GEAR = wt("rule", 1)                           # "gear": Polster am Bund leuchtet
T_UNDER = wt("rule", 6)                          # "under the uniform"
T_UNTUCK = wt("rule", 16) - 0.1                  # "untucked": Trikot rutscht raus
T_RETUCK = VO_START["pen"] - 0.05                # "Tucked anyway?"
T_WARN = wt("pen", 4) - 0.05                     # "warning"
T_2MIN = wt("pen", 6) - 0.05                     # "two minutes"
T_2013 = wt("hist", 5) - 0.05
T_BACK = wt("hist", 7) - 0.05
T_CTA = VO_START["cta"]

KIT_C = np.array([880.0, 40.0, 0.0])             # schwebt vor dem Tor über dem Eis
YAW0 = -math.pi / 2                              # Vorderseite zeigt zur Kamera (-x)


# ================================================================= Kleidung
def tuck_amount(t):
    if t < T_UNTUCK:
        return 1.0
    if t < T_RETUCK:
        return 1 - e_out(c01((t - T_UNTUCK) / 0.35), 3)
    return e_out(c01((t - T_RETUCK) / 0.4), 3)


def kit_pose(t):
    yaw = YAW0 + 0.16 * math.sin(t * 0.8 + 0.4)
    bob = np.array([0.0, 1.4 * math.sin(t * 1.7), 0.0])
    pop = 0.0
    for t0 in (T_UNTUCK, T_RETUCK, T_2MIN):
        if t0 <= t < t0 + 0.4:
            pop += 2.5 * math.sin(math.pi * (t - t0) / 0.4)
    return KIT_C + bob + np.array([0.0, pop, 0.0]), HT.rot((0, 1, 0), yaw)


_PANTS = None


def kit_meshes(t):
    global _PANTS
    if _PANTS is None:
        _PANTS = K.pants_mesh()
    c, R = kit_pose(t)
    tk = round(tuck_amount(t), 3)
    return HT.place_hat(_PANTS, c, R) + HT.place_hat(K.jersey_mesh(tk), c, R)


def kit_point(t, local):
    c, R = kit_pose(t)
    return c + R @ np.asarray(local, float)


# ================================================================= Kamera
def wide_cam(t):
    s = c01(t / DUR)
    p = KIT_C + np.array([-166.0 + 12 * s, 4.0, 22.0 - 28 * s])
    return p, KIT_C + np.array([0.0, 19.0, 0.0]), 44.0


def close_cam(t):
    """Nahaufnahme auf Bund/Polster bei "Protective gear"."""
    return KIT_C + np.array([-100.0, 0.0, -16.0]), KIT_C + np.array([0.0, 15.0, -4.0]), 40.0


def cam(t):
    c0, c1 = T_GEAR - 0.25, T_GEAR + 0.4
    d0, d1 = T_UNTUCK - 0.55, T_UNTUCK + 0.15
    if t < c0:
        p, g, f = wide_cam(t)
    elif t < c1:
        p, g, f = R28.blend_cam(wide_cam(c0), close_cam(c1), sio((t - c0) / (c1 - c0)))
    elif t < d0:
        p, g, f = close_cam(t)
    elif t < d1:
        p, g, f = R28.blend_cam(close_cam(d0), wide_cam(d1), sio((t - d0) / (d1 - d0)))
    else:
        p, g, f = wide_cam(t)
    for t0, amp in ((T_2MIN, 2.2), (T_UNTUCK, 0.8)):
        lt = t - t0
        if 0 <= lt < 0.5:
            e = amp * math.exp(-lt * 9)
            p = p + np.array([math.sin(lt * 83), math.cos(lt * 71), math.sin(lt * 59)]) * e
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
        pk[j] = (0.0, -50.0, 0.0, 0.0, 0.0, 0.0, tk)
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, SPP, fidx + 37, cams, lens, pk, R15.logo_tex(), base, puck, cov)
    return P3.tonemap(base)


# ================================================================= Overlays
def fade_im(im, a):
    if a >= 1:
        return im
    im = im.copy()
    im.putalpha(im.getchannel("A").point(lambda v: int(v * max(a, 0.0))))
    return im


def word(txt, size, col):
    im = R18.word_img(txt, size, col, HALO)
    if im.width > 1040:
        im = im.resize((1040, int(im.height * 1040 / im.width)), Image.LANCZOS)
    return im


def ring_at(ctx, row, t, local, rx, ry, col, a, dash=True):
    """Gestrichelter Kreis um eine Stelle am Trikot (in Pixeln, perspektivisch skaliert)."""
    if a <= 0:
        return
    p = kit_point(t, local)
    xy, z = projected(row, p)
    if z <= 0:
        return
    k = px_per_in(row, z)
    ctx.set_source_rgba(col[0] / 255, col[1] / 255, col[2] / 255, a)
    ctx.set_line_width(9)
    if dash:
        ctx.set_dash([26, 16], -t * 60)
    ctx.save()
    ctx.translate(xy[0], xy[1])
    ctx.scale(rx * k, ry * k)
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.restore()
    ctx.stroke()
    ctx.set_dash([])
    return xy, k


def arrow(ctx, sx, sy, ex, ey, col, a, k=1.0):
    if a <= 0 or k <= 0:
        return
    ex, ey = sx + (ex - sx) * k, sy + (ey - sy) * k
    ctx.set_source_rgba(col[0] / 255, col[1] / 255, col[2] / 255, a)
    ctx.set_line_width(10)
    ctx.move_to(sx, sy)
    ctx.curve_to(sx - 70, sy + 90, ex - 60, ey - 120, ex, ey)
    ctx.stroke()
    if k > 0.95:
        ang = math.atan2(120.0, 60.0)
        for s in (-1, 1):
            ctx.move_to(ex, ey)
            ctx.line_to(ex - 40 * math.cos(ang + s * 0.5), ey - 40 * math.sin(ang + s * 0.5))
        ctx.stroke()


def badge(L, txt, col, cx, cy, t, t0, t1, size=90, txt_col=(255, 255, 255)):
    """Farbige Karte (Verwarnung / Strafe), slammt rein."""
    if not (t0 <= t < t1):
        return
    from PIL import ImageDraw
    lt = t - t0
    sc = lerp(1.5, 1.0, e_out(c01(lt / 0.14), 3))
    a = c01(lt / 0.05) * (1 - smooth(t1 - 0.12, t1, t))
    tx = line_img(txt, size, 900, txt_col, track=2)
    w, h = tx.width + 80, tx.height + 46
    im = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((24, 28, 20 + w, 24 + h), 22, fill=(0, 0, 0, 70))
    d.rounded_rectangle((20, 20, 20 + w, 20 + h), 22, fill=col + (255,))
    im.alpha_composite(tx, (int(20 + (w - tx.width) / 2), int(20 + (h - tx.height) / 2)))
    im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.BILINEAR)
    put(L, fade_im(im, a), cx - im.width / 2, cy - im.height / 2)


_NAVY = {}


def brand(L, t):
    if t < 1.9:
        return
    if "lock" not in _NAVY:
        import reel33_lines_neon as N
        im = N.brand_img("bladesandpucks_lockup_transparent.png", 280).img
        arr = np.asarray(im).astype(np.float32)
        wm = (arr[..., 0] > 200) & (arr[..., 1] > 200) & (arr[..., 2] > 200)
        arr[wm, 0:3] = NAVY
        _NAVY["lock"] = Image.fromarray(arr.astype(np.uint8), "RGBA")
    im = fade_im(_NAVY["lock"], 0.92 * smooth(1.9, 2.2, t))
    put(L, im, W / 2 - im.width / 2, 1830 - im.height / 2)


def texts(L, t):
    # Hook: ganze Frage ab Bild 0
    if t < VO_START["rule"]:
        k = 1 - smooth(VO_START["rule"] - 0.2, VO_START["rule"], t)
        for txt, cy, size, col in (("WHY IS THIS", 300, 128, INK), ("A PENALTY", 445, 150, RED),
                                   ("IN THE NHL?", 590, 118, INK)):
            put(L, fade_im(word(txt, size, col), k), W / 2 - word(txt, size, col).width / 2,
                cy - word(txt, size, col).height / 2)
    # Regel
    if T_GEAR - 0.1 <= t < T_UNTUCK - 0.1:
        a = smooth(T_GEAR - 0.1, T_GEAR + 0.1, t) * (1 - smooth(T_UNTUCK - 0.3, T_UNTUCK - 0.1, t))
        reveal(L, line_img("PROTECTIVE GEAR", 64, 900, INK, track=3), W / 2, 300, a)
        if t >= T_UNDER - 0.05:
            reveal(L, line_img("= UNDER THE UNIFORM", 64, 900, ORANGE, track=3), W / 2, 385,
                   a * c01((t - T_UNDER + 0.05) / 0.2))
    if T_UNTUCK - 0.1 <= t < T_RETUCK:
        slam(L, "EVERY SHIFT:", 90, INK, W / 2, 300, t, T_UNTUCK - 0.1, T_RETUCK)
        slam(L, "UNTUCKED.", 150, GREEN, W / 2, 430, t, T_UNTUCK, T_RETUCK)
    # Strafe
    if T_RETUCK <= t < T_WARN:
        reveal(L, line_img("TUCKED ANYWAY?", 76, 900, INK, track=3), W / 2, 330, smooth(T_RETUCK, T_RETUCK + 0.15, t),
               smooth(T_WARN - 0.1, T_WARN, t))
    badge(L, "1ST: WARNING", YELLOW, W / 2, 330, t, T_WARN, VO_START["hist"] - 0.05, 70, INK)
    slam(L, "2 MIN", 220, RED, W / 2, 490, t, T_2MIN, VO_START["hist"] - 0.05, 1.9)
    # Geschichte
    slam(L, "LAST CALLED:", 80, INK, W / 2, 300, t, wt("hist", 3) - 0.05, T_CTA - 0.05)
    slam(L, "2013", 170, (120, 124, 136), W / 2, 420, t, T_2013, T_CTA - 0.05)
    slam(L, "2026: IT'S BACK.", 112, ORANGE, W / 2, 600, t, T_BACK, T_CTA - 0.05)
    # CTA
    slam(L, "SHOULD THIS BE", 100, INK, W / 2, 290, t, T_CTA - 0.05)
    slam(L, "A PENALTY?", 140, RED, W / 2, 420, t, wt("cta", 4) - 0.05)
    slam(L, "YES", 130, GREEN, W * 0.3, 570, t, wt("cta", 4) + 0.25)
    slam(L, "NO", 130, RED, W * 0.7, 570, t, wt("cta", 4) + 0.38)
    if t >= wt("cta", 4) + 0.48:
        reveal(L, line_img("/", 110, 300, INK), W / 2, 570, c01((t - wt("cta", 4) - 0.48) / 0.15))
    slam(L, "FOLLOW", 150, RED, W / 2, 1480, t, wt("cta", 5) - 0.05)
    if t >= wt("cta", 6):
        reveal(L, line_img("FOR MORE RULES", 42, 850, INK, track=8), W / 2, 1590, c01((t - wt("cta", 6)) / 0.25))


def marks(ctx, row, t):
    # rote Markierung am eingesteckten Teil (Hook, Strafe, Ende)
    tuck_a = max(1 - smooth(VO_START["rule"] - 0.3, VO_START["rule"], t),
                 smooth(T_RETUCK + 0.3, T_RETUCK + 0.5, t) * (1 - smooth(T_2MIN - 0.1, T_2MIN + 0.1, t)),
                 smooth(T_CTA + 0.1, T_CTA + 0.4, t))
    ring_at(ctx, row, t, (-8.0, -1.5, 3.0), 9.5, 6.5, RED, 0.95 * tuck_a)
    if t < VO_START["rule"]:
        p = kit_point(t, (-8.0, 5.0, 3.0))
        xy, z = projected(row, p)
        if z > 0:
            arrow(ctx, 330.0, 700.0, xy[0] - 20, xy[1] - 30, RED, 1 - smooth(VO_START["rule"] - 0.3, VO_START["rule"], t),
                  e_out(c01((t - 0.2) / 0.4), 3))
    # Polster am Bund (Ausrüstung) leuchtet bei "Protective gear"
    ga = smooth(T_GEAR - 0.05, T_GEAR + 0.2, t) * (1 - smooth(T_UNTUCK - 0.2, T_UNTUCK + 0.1, t))
    ring_at(ctx, row, t, (-7.0, 0.0, 3.5), 7.5, 4.0, ORANGE, 0.95 * ga, dash=False)
    # grüner Haken beim Rausziehen
    ok = smooth(T_UNTUCK + 0.1, T_UNTUCK + 0.3, t) * (1 - smooth(T_RETUCK - 0.2, T_RETUCK, t))
    ring_at(ctx, row, t, (-8.0, -2.5, 3.0), 9.5, 6.5, GREEN, 0.9 * ok, dash=False)


# ================================================================= Bild
FRONT_LIGHT = np.array([-0.60, 0.80, 0.30])                  # von der Kameraseite (-x) und oben
FRONT_LIGHT /= np.linalg.norm(FRONT_LIGHT)


def compose(t, fidx):
    base = render3d(t, fidx)
    row, _ = cam_row_at(t)
    campos = cam(t)[0]
    lo_s, lo_c = surface()
    hi_s, hi_c = surface()
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    R28.draw_net_lines(lo_c, row)
    R28.glass_edges(lo_c, row)
    img = over(base, *surf_rgba(lo_s))
    old = M3.LIGHT
    M3.LIGHT = FRONT_LIGHT                                    # Kleidung von vorn-oben beleuchten
    m_rgb, m_a, shadow, plane_a = M3.render(R28.BOARDS + R28.FRAMES + kit_meshes(t), row, W, H, campos,
                                            extra_planes=[(R28.GLASS_ALL, 1.0)], shadow_light=(0.15, 1.0, 0.1))
    M3.LIGHT = old
    img = img * (1 - 0.28 * shadow[..., None])
    img = img * (1 - m_a[..., None]) + m_rgb
    k = (0.30 * plane_a)[..., None]
    img = img * (1 - k) + np.array([0.70, 0.82, 0.94], np.float32) * k
    img = img + (R26.glass_streaks() * plane_a * 0.10)[..., None]
    marks(hi_c, row, t)
    img = over(img, *surf_rgba(hi_s))
    for t0, col in ((T_UNTUCK, (1, 1, 1)), (T_WARN, (1, 0.95, 0.7)), (T_2MIN, (1, 0.85, 0.85))):
        if t0 <= t < t0 + 0.2:
            a = 0.14 * (1 - (t - t0) / 0.2)
            img = img * (1 - a) + np.array(col, np.float32) * a
    pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
    texts(L, t)
    brand(L, t)
    pil.alpha_composite(L)
    arr = np.asarray(pil.convert("RGB")).astype(np.float32) / 255
    lc = min([t - c for c in (T_UNTUCK, T_WARN, T_2MIN, T_BACK) if t >= c] + [t + 0.5])
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
    rng = np.random.default_rng(37)
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

    def swish(dur=0.35, vol=0.4):                                   # Stoff
        x = tt(dur)
        return hp(lp(noise(dur), 2), 12) * np.sin(np.pi * x / dur) ** 1.5 * vol

    def whoosh(dur=0.4, vol=0.4):
        x = tt(dur)
        return hp(lp(noise(dur), 6), 40) * np.sin(np.pi * x / dur) ** 2 * vol

    def boom(vol=0.8):
        x = tt(0.8)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(55 + 90 * np.exp(-x * 12)) / SR) * np.exp(-x * 4) * 3) * vol

    def ding(vol=0.4, f=1320):
        x = tt(0.6)
        return (np.sin(2 * np.pi * f * x) + 0.4 * np.sin(2 * np.pi * f * 2.01 * x)) * np.exp(-x * 7) * vol

    def buzz(dur=0.35, vol=0.4):
        x = tt(dur)
        return np.sign(np.sin(2 * np.pi * 220 * x)) * lp(np.ones(len(x)), 1) * np.clip((dur - x) / 0.05, 0, 1) * vol

    roots = [55.0, 55.0, 65.41, 49.0]
    for k8 in range(int(DUR / (B / 2))):
        tb = k8 * B / 2
        b = k8 / 2
        pos = b % 4
        if tb > DUR - 0.4:
            continue
        hook = tb < VO_START["rule"]
        if pos in (0.0, 2.5) or (pos == 1.5 and not hook):
            put_(mus, kick(0.75 if hook else 1.0), tb)
        if pos in (1.0, 3.0) and not hook:
            put_(mus, clap(0.8), tb)
        if not hook:
            put_(mus, hat(0.1 if k8 % 2 == 0 else 0.06), tb, pan=0.3)
        if pos == 0.0:
            put_(mus, sub(roots[int(b // 4) % 4], 2.6 * B), tb)
    put_(sfx, whistle(0.45, 0.4), 0.05)
    put_(sfx, whoosh(0.45, 0.3), T_GEAR - 0.25)
    put_(sfx, swish(0.35, 0.5), T_UNTUCK)
    put_(sfx, ding(0.35), T_UNTUCK + 0.15)
    put_(sfx, swish(0.35, 0.5), T_RETUCK)
    put_(sfx, whistle(0.5, 0.5), T_WARN)
    put_(sfx, boom(0.8), T_2MIN)
    put_(sfx, buzz(0.3, 0.25), T_2013)
    put_(sfx, whoosh(0.4, 0.3), T_BACK - 0.15)
    put_(sfx, whoosh(0.5, 0.35), T_CTA - 0.2)
    voice = np.zeros(n)
    for k in VO_KEYS:
        tmp = os.path.join(HERE, f"_vo_{k}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "voice", f"reel37_{k}.wav"),
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
    tts_kokoro.synth(VO_LINES, os.path.join(HERE, "voice", "reel37"), speed=1.25)


def check_vo():
    with open(os.path.join(HERE, "voice", "reel37_timing.json")) as f:
        vo_dur = {k: v / TEMPO for k, v in json.load(f).items()}
    for i, k in enumerate(VO_KEYS):
        nxt = VO_START[VO_KEYS[i + 1]] if i + 1 < len(VO_KEYS) else DUR - 0.2
        if VO_START[k] + vo_dur[k] > nxt + 0.3:
            print(f"Warnung: Satz {k} zu lang ({VO_START[k] + vo_dur[k]:.2f} > {nxt:.2f})")


def remux():
    os.chdir(HERE)
    make_audio("audio_jersey.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "reel37_jersey.mp4", "-i", "audio_jersey.wav",
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-af",
                    "loudnorm=I=-14:TP=-1.0:LRA=9", "-ar", "44100", "-shortest", "-movflags", "+faststart",
                    "_tmp_js.mp4"], check=True)
    os.replace("_tmp_js.mp4", "reel37_jersey.mp4")


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
    make_audio("audio_jersey.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_jersey.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
           "-ar", "44100", "-shortest", "-movflags", "+faststart", "reel37_jersey.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(0.9, 9999)).save("reel37_thumbnail.jpg", quality=92)
    print("fertig: reel37_jersey.mp4")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "vo":
        make_voice()
    elif len(sys.argv) > 1 and sys.argv[1] == "audio":
        remux()
    elif len(sys.argv) > 1 and sys.argv[1] == "prev":
        preview(sys.argv[2].split(","), sys.argv[3])
    else:
        main()
