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
Bilder: Bande, Glas, Tore (mesh3d), Eis (Raytracer) als Standbild-Hintergrund; davor das echte Löwen-Frankfurt-
Heimtrikot 2026/27 (ohne Sponsoren, kit_clean.py) als Stoff mit Falten-Licht und Wehen (cloth2d.py) + Hose. Kein Körper.
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

import cloth2d as C
import mesh3d as M3
import puck3d as P3
import reel15_puck as R15
import reel18_dangle as R18
import reel26_overglass as R26
import reel28_emptynet as R28
from reel15_puck import W, H, FPS, c01, smooth, sio, e_out, lerp, line_img, reveal, put, surface, surf_rgba, over
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

KIT_C = np.array([880.0, 40.0, 0.0])             # Bezugspunkt der Kamera für den Hintergrund
KX0, KY0 = (W - C.CW) // 2, 640                  # Trikot-Arbeitsfläche auf dem Bildschirm


# ================================================================= Trikot
def tuck_amount(t):
    if t < T_UNTUCK:
        return 1.0
    if t < T_RETUCK:
        return 1 - e_out(c01((t - T_UNTUCK) / 0.35), 3)
    return e_out(c01((t - T_RETUCK) / 0.4), 3)


def kit_offset(t):
    """Schweben + kleiner Hüpfer bei den Aktionen (Bildschirm-Pixel)."""
    y = 7.0 * math.sin(t * 1.7)
    for t0 in (T_UNTUCK, T_RETUCK, T_2MIN):
        if t0 <= t < t0 + 0.4:
            y -= 16.0 * math.sin(math.pi * (t - t0) / 0.4)
    return KX0, KY0 + y


def kit_yaw(t):
    return 0.10 * math.sin(t * 0.8 + 0.4)


_AN = {"tuck": (C.CX - 230, C.WAIST - 10), "waist": (C.CX - 220, C.WAIST + 30)}   # Trikot-Koordinaten


def anchor(t, name):
    ox, oy = kit_offset(t)
    ax, ay = _AN[name]
    return ox + ax, oy + ay


# ================================================================= Hintergrund (Standbild, einmal gerendert)
_BG = {}


def bg_plate():
    if "img" in _BG:
        return _BG["img"]
    pos, tgt = KIT_C + np.array([-166.0, 4.0, 10.0]), KIT_C + np.array([0.0, 19.0, 0.0])
    r, u, f = P3.look_at(pos, tgt, np.array([0.0, 1.0, 0.0]))
    row = P3.cam_row(pos, r, u, f, 44.0)
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, int(os.environ.get("BGSPP", "32")), 37, row[None], np.array([[0.0, 166.0]]),
              np.array([[0.0, -50.0, 0.0, 0.0, 0.0, 0.0, 0.0]]), R15.logo_tex(), base, puck, cov)
    img = P3.tonemap(base)
    lo_s, lo_c = surface()
    R28.draw_net_lines(lo_c, row)
    R28.glass_edges(lo_c, row)
    img = over(img, *surf_rgba(lo_s))
    m_rgb, m_a, shadow, plane_a = M3.render(R28.BOARDS + R28.FRAMES, row, W, H, pos,
                                            extra_planes=[(R28.GLASS_ALL, 1.0)], shadow_light=(0.15, 1.0, 0.1))
    img = img * (1 - 0.2 * shadow[..., None])
    img = img * (1 - m_a[..., None]) + m_rgb
    k = (0.30 * plane_a)[..., None]
    img = img * (1 - k) + np.array([0.70, 0.82, 0.94], np.float32) * k
    img = img + (R26.glass_streaks() * plane_a * 0.10)[..., None]
    _BG["img"] = np.clip(img, 0, 1).astype(np.float32)
    return _BG["img"]


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


def ring_at(ctx, t, name, rx, ry, col, a, dash=True, dy=0.0):
    """Kreis um eine Stelle am Trikot (Bildschirm-Pixel)."""
    if a <= 0:
        return
    x, y = anchor(t, name)
    ctx.set_source_rgba(col[0] / 255, col[1] / 255, col[2] / 255, a)
    ctx.set_line_width(10)
    if dash:
        ctx.set_dash([28, 18], -t * 60)
    ctx.save()
    ctx.translate(x, y + dy)
    ctx.scale(rx, ry)
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.restore()
    ctx.stroke()
    ctx.set_dash([])


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


def card(L, lines, cx, cy, a, size=58):
    """Weiße Karte mit Textzeilen (lesbar auch über dem dunklen Trikot)."""
    if a <= 0:
        return
    from PIL import ImageDraw
    ims = [line_img(txt, size, 900, col, track=3) for txt, col in lines]
    w = max(im.width for im in ims) + 70
    h = sum(im.height for im in ims) + 18 * (len(ims) - 1) + 44
    im = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((24, 30, 20 + w, 26 + h), 24, fill=(0, 0, 0, 60))
    d.rounded_rectangle((20, 20, 20 + w, 20 + h), 24, fill=(255, 255, 255, 240))
    y = 42
    for t_im in ims:
        im.alpha_composite(t_im, (int(20 + (w - t_im.width) / 2), int(y)))
        y += t_im.height + 18
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
    put(L, im, W / 2 - im.width / 2, 1862 - im.height / 2)


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
        card(L, [("PROTECTIVE GEAR", INK)] + ([("= UNDER THE UNIFORM", ORANGE)] if t >= T_UNDER - 0.05 else []),
             W / 2, 330, a)
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
        card(L, [("FOR MORE RULES", INK)], W / 2, 1600, c01((t - wt("cta", 6)) / 0.25), size=40)


def marks(ctx, t):
    # rote Markierung am eingesteckten Teil (Hook, Strafe, Ende)
    tuck_a = max(1 - smooth(VO_START["rule"] - 0.3, VO_START["rule"], t),
                 smooth(T_RETUCK + 0.3, T_RETUCK + 0.5, t) * (1 - smooth(T_2MIN - 0.1, T_2MIN + 0.1, t)),
                 smooth(T_CTA + 0.1, T_CTA + 0.4, t))
    ring_at(ctx, t, "tuck", 170, 95, RED, 0.95 * tuck_a)
    if t < VO_START["rule"]:
        x, y = anchor(t, "tuck")
        arrow(ctx, 300.0, 690.0, x - 40, y - 90, RED, 1 - smooth(VO_START["rule"] - 0.3, VO_START["rule"], t),
              e_out(c01((t - 0.2) / 0.4), 3))
    # Polster am Bund (Ausrüstung) bei "Protective gear"
    ga = smooth(T_GEAR - 0.05, T_GEAR + 0.2, t) * (1 - smooth(T_UNTUCK - 0.2, T_UNTUCK + 0.1, t))
    ring_at(ctx, t, "waist", 175, 60, ORANGE, 0.95 * ga, dash=False)
    # grüner Kreis beim Rausziehen
    ok = smooth(T_UNTUCK + 0.1, T_UNTUCK + 0.3, t) * (1 - smooth(T_RETUCK - 0.2, T_RETUCK, t))
    ring_at(ctx, t, "tuck", 170, 95, GREEN, 0.9 * ok, dash=False, dy=40)


# ================================================================= Bild
def zoom_state(t):
    """Nahaufnahme auf den Bund bei "Protective gear": (Faktor, Mittelpunkt der Ansicht)."""
    c0, c1 = T_GEAR - 0.25, T_GEAR + 0.35
    d0, d1 = T_UNTUCK - 0.5, T_UNTUCK + 0.1
    k = sio(c01((t - c0) / (c1 - c0))) * (1 - sio(c01((t - d0) / (d1 - d0))))
    ax, ay = anchor(t, "waist")
    z = 1 + 0.75 * k
    cx = lerp(W / 2, ax + 60, k)
    cy = lerp(H / 2, ay - 230, k)
    return z, cx, cy


def compose(t, fidx):
    img = bg_plate().copy()
    # weicher Schatten auf dem Eis
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ox, oy = kit_offset(t)
    sh = np.exp(-(((xx - 540) / 330) ** 2 + ((yy - 1790 - 0.3 * (oy - KY0)) / 34) ** 2))
    img = img * (1 - 0.26 * sh[..., None])
    kit, _ = C.frame(t, tuck_amount(t), kit_yaw(t))
    x0, y0 = int(round(ox)), int(round(oy))
    hh, ww = kit.shape[:2]
    ya, yb = max(0, y0), min(H, y0 + hh)
    seg = img[ya:yb, x0:x0 + ww]
    k = kit[ya - y0:yb - y0, :, :]
    seg[:] = seg * (1 - k[..., 3:4]) + k[..., :3] * k[..., 3:4]
    hi_s, hi_c = surface()
    marks(hi_c, t)
    img = over(img, *surf_rgba(hi_s))
    for t0, col in ((T_UNTUCK, (1, 1, 1)), (T_WARN, (1, 0.95, 0.7)), (T_2MIN, (1, 0.85, 0.85))):
        if t0 <= t < t0 + 0.2:
            a = 0.14 * (1 - (t - t0) / 0.2)
            img = img * (1 - a) + np.array(col, np.float32) * a
    pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    lc = min([t - c for c in (T_UNTUCK, T_WARN, T_2MIN, T_BACK) if t >= c] + [t + 0.5])
    z, cx, cy = zoom_state(t)
    z *= 1 + 0.035 * math.exp(-lc * 12) + 0.02 * t / DUR
    if z > 1.002:
        w2, h2 = W / z, H / z
        pil = pil.transform((W, H), Image.EXTENT, (cx - w2 / 2, cy - h2 / 2, cx + w2 / 2, cy + h2 / 2), Image.BICUBIC)
    pil = pil.convert("RGBA")
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    texts(L, t)
    brand(L, t)
    pil.alpha_composite(L)
    arr = np.asarray(pil.convert("RGB")).astype(np.float32) / 255
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
