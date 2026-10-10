"""Reel 12: "Hockey motion design BY AI" – Handyaufnahme eines Laptops im Neon-Zimmer, auf dem eine
minimalistische Hockey-Motion-Design-Animation läuft (nach dem viralen "Motion design by AI, 1 prompt"-Format).

Ablauf (16 s): Prompt-Leiste -> Klick, Eisfläche -> Prompt "Show me what AI can do with hockey" ->
Schuss-Menü (Snipe / top shelf) -> Positions-Schalter (Goalie) -> Kufen-Spuren liefern "Skate" ->
Licht verwischt das Wort zum Puck -> Puck fällt maßstabsgetreu auf den Bullypunkt (Puck 3 Zoll,
Punkt 12 Zoll) -> Eis-Spray wird "Shoot" -> "Score" -> Torlampe leuchtet rot -> FOLLOW FOR MORE ->
Wortmarke @bladesandpucks.
Fakten: NHL-Regel 13.1 (Puck 3 Zoll Durchmesser, 1 Zoll dick), Regel 1.9 (Bullypunkt Mitte: blau,
12 Zoll), Regel 1.5 (rote Mittellinie), Regel 4.1 (rotes Torlicht).
Aufruf: python3 reel12_ai_motion.py  ->  reel12_ai_motion.mp4
"""
import math
import os
import random
import subprocess
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

import pov_audio as pa
import pov_room as room
import screen_fx as fx
from pov_room import ifont, draw_hud, draw_cursor
from screen_fx import (SW, SH, CHAR, ICE, ORANGE, WHITE, c01, lerp, e_out, e_in, e_io, e_expo, e_back, spring,
                       layer, put, fade, mblur, glow, blob, edge_vignette, text_layer, text_width)

FPS = 30
DUR = 16.0
HERE = os.path.dirname(os.path.abspath(__file__))
OVERLAY = ["Hockey motion design", "BY AI"]
PROMPT = "Show me what AI can do with hockey"
PLACEHOLDER = "Hey, can you help....."
FROST = (224, 229, 235)
ICEFIELD = (234, 240, 245)
ICE_DEEP = (30, 110, 215)
GOAL_RED = (235, 45, 40)
WARMWHITE = (245, 232, 218)
NEARBLACK = (6, 5, 10)
BAR = dict(cx=SW / 2, cy=430, w=1240, h=230)
CHIP = (466, 487)                         # Modell-Chip in Inhaltskoordinaten
PILL = dict(cx=SW / 2, cy=620, w=900, h=110)
LABELS = ["Forward", "Defense", "Goalie"]
WORD_SIZE = 96
PUCK_W, PUCK_T = 123, 41                  # 3 : 1 wie ein echter Puck (3 x 1 Zoll)
SPOT_W = PUCK_W * 4                       # Bullypunkt 12 Zoll = 4 x Puckbreite
Y_PUCK0, Y_FLOOR = 0.28 * SH, 0.645 * SH


# ================================================================= virtuelle Kamera (x' = x*sc + o)
def cam_apply(im, sc, ox, oy):
    if abs(sc - 1) < 1e-3 and abs(ox) < 0.3 and abs(oy) < 0.3:
        return im
    box = (-ox / sc, -oy / sc, (SW - ox) / sc, (SH - oy) / sc)
    return im.transform((SW, SH), Image.EXTENT, box, Image.BICUBIC)


def keyed(t, keys):
    """Lineare Interpolation über (zeit, (sc, ox, oy), easing)-Schlüssel."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0, _), (t1, v1, ez) in zip(keys, keys[1:]):
        if t <= t1:
            p = ez((t - t0) / (t1 - t0))
            return tuple(lerp(a, b, p) for a, b in zip(v0, v1))
    return keys[-1][1]


def pivot_cam(sc, src, dst):
    return (sc, dst[0] - src[0] * sc, dst[1] - src[1] * sc)


CAM_PROMPT = [
    (2.35, (1.0, 0.0, 0.0), e_io),
    (3.30, (1.10, SW / 2 * -0.10 - 64, SH / 2 * -0.10 - 20), lambda x: 0.5 - 0.5 * math.cos(math.pi * c01(x))),
    (3.55, pivot_cam(1.45, CHIP, (0.45 * SW, 0.40 * SH)), e_io),
    (4.40, tuple(a + b for a, b in zip(pivot_cam(1.45, CHIP, (0.45 * SW, 0.40 * SH)), (0, 24, -10))), lambda x: x),
]


def cam_at(t):
    return keyed(t, CAM_PROMPT)


def to_screen(pt, cam):
    sc, ox, oy = cam
    return pt[0] * sc + ox, pt[1] * sc + oy


# ================================================================= Prompt-Leiste
def bar_layer(text, ink, t, fill_w=None, fill_h=None, radius=None, fill_col=FROST, fill_a=1.0, content_a=1.0,
              caret=False, shimmer=None, chip="Shot"):
    """Prompt-Leiste: Füllung frei skalierbar (für Zoom/Verschluss), Inhalt an der Endposition."""
    cx, cy, w, h = BAR["cx"], BAR["cy"], BAR["w"], BAR["h"]
    fw, fh = fill_w or w, fill_h or h
    rad = h * 0.22 if radius is None else radius
    lay = layer()
    if fill_a > 0.01:
        if content_a > 0.5 and fw <= w + 1:
            sh = layer()
            ImageDraw.Draw(sh).rounded_rectangle((cx - fw / 2, cy - fh / 2 + 14, cx + fw / 2, cy + fh / 2 + 14), radius=rad,
                                                 fill=(0, 0, 0, int(100 * fill_a)))
            lay.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)))
        d = ImageDraw.Draw(lay)
        d.rounded_rectangle((cx - fw / 2, cy - fh / 2, cx + fw / 2, cy + fh / 2), radius=rad, fill=fill_col + (int(240 * fill_a),))
        if fw <= w + 1:
            d.line((cx - fw / 2 + rad, cy - fh / 2 + 1, cx + fw / 2 - rad, cy - fh / 2 + 1), fill=(255, 255, 255, int(120 * fill_a)), width=2)
    if content_a > 0.01:
        c = layer()
        d = ImageDraw.Draw(c)
        x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
        f = ifont(450, 46)
        d.text((x0 + 56, y0 + 66), text, font=f, fill=ink + (255,), anchor="lm")
        if caret and int(t * 2) % 2 == 0:
            xc = x0 + 60 + f.getlength(text)
            d.rectangle((xc, y0 + 42, xc + 3, y0 + 90), fill=(30, 32, 38, 255))
        iy, ic = y1 - 58, (70, 76, 88, 255)
        x = x0 + 62
        d.line((x - 14, iy, x + 14, iy), fill=ic, width=4)
        d.line((x, iy - 14, x, iy + 14), fill=ic, width=4)
        x += 64
        d.ellipse((x - 16, iy - 16, x + 16, iy + 16), outline=ic, width=3)
        d.line((x - 16, iy, x + 16, iy), fill=ic, width=2)
        d.ellipse((x - 7, iy - 16, x + 7, iy + 16), outline=ic, width=2)
        x += 64
        d.rounded_rectangle((x - 16, iy - 14, x + 16, iy + 14), radius=5, outline=ic, width=3)
        d.ellipse((x - 8, iy - 7, x - 2, iy - 1), fill=ic)
        d.polygon([(x - 12, iy + 10), (x - 2, iy + 1), (x + 4, iy + 6), (x + 12, iy - 4), (x + 12, iy + 10)], fill=ic)
        # Chip "Shot"
        fc = ifont(600, 30)
        cw = fc.getlength(chip) + 64
        d.rounded_rectangle((CHIP[0] - cw / 2, iy - 24, CHIP[0] + cw / 2, iy + 24), radius=24, fill=(206, 212, 220, 255))
        d.text((CHIP[0] - 12, iy), chip, font=fc, fill=(60, 66, 76, 255), anchor="mm")
        vx = CHIP[0] + cw / 2 - 24
        d.polygon([(vx - 8, iy - 4), (vx + 8, iy - 4), (vx, iy + 6)], fill=(60, 66, 76, 255))
        # rechts: Punkt, Mikro, Senden
        bx = x1 - 64
        d.ellipse((bx - 30, iy - 30, bx + 30, iy + 30), fill=(34, 36, 42, 255))
        d.line((bx, iy + 14, bx, iy - 13), fill=(240, 242, 245, 255), width=5)
        d.line((bx - 12, iy - 1, bx, iy - 14), fill=(240, 242, 245, 255), width=5)
        d.line((bx + 12, iy - 1, bx, iy - 14), fill=(240, 242, 245, 255), width=5)
        mx = bx - 74
        d.rounded_rectangle((mx - 8, iy - 18, mx + 8, iy + 6), radius=8, fill=ic)
        d.arc((mx - 14, iy - 8, mx + 14, iy + 16), 0, 180, fill=ic, width=3)
        d.line((mx, iy + 16, mx, iy + 22), fill=ic, width=3)
        d.ellipse((mx - 66, iy - 7, mx - 52, iy + 7), fill=(120, 126, 136, 255))
        if shimmer is not None and 0 < shimmer < 1:
            band = layer()
            sx = lerp(x0 - 100, x0 + 160 + f.getlength(text), shimmer)
            ImageDraw.Draw(band).polygon([(sx - 50, y0 + 20), (sx + 20, y0 + 20), (sx - 10, y0 + 110), (sx - 80, y0 + 110)],
                                         fill=(150, 225, 255, 255))
            band = band.filter(ImageFilter.GaussianBlur(14))
            txt_mask = layer()
            ImageDraw.Draw(txt_mask).text((x0 + 56, y0 + 66), text, font=f, fill=(255, 255, 255, 255), anchor="lm")
            band.putalpha(ImageChops.multiply(band.getchannel("A"), txt_mask.getchannel("A")))
            c.alpha_composite(band)
        lay.alpha_composite(fade(c, content_a))
    return lay


def menu_layer(t):
    """Schuss-Menü unter dem Chip (Inhaltskoordinaten)."""
    if t < 3.55:
        return None
    p = e_expo((t - 3.55) / 0.13)
    lay = layer()
    d = ImageDraw.Draw(lay)
    w, row = 330, 64
    top = CHIP[1] + 34
    rows = ["Wrist shot", "Slap shot", "Snipe"]
    n_vis = 3 if t >= 3.95 else 2
    h = row * n_vis + 20
    sc = lerp(0.85, 1.0, p)
    x0, x1 = CHIP[0] - w * sc / 2 + 40, CHIP[0] + w * sc / 2 + 40
    d.rounded_rectangle((x0, top, x1, top + h * sc), radius=18, fill=(214, 220, 228, int(245 * p)))
    hover = 0 if 3.75 <= t < 3.87 else 1 if 3.87 <= t < 4.0 else 2 if t >= 4.0 else None
    f = ifont(500, 30)
    for i, label in enumerate(rows[:n_vis]):
        ry = top + 10 + row * (i + 0.5)
        off = 0.0
        a = p
        if i == 2:
            q = c01((t - 3.95) / 0.1)
            off, a = 6 * (1 - q), p * q
        if hover == i:
            col = (186, 194, 205) if (i == 2 and t >= 4.03) else (200, 207, 216)
            d.rounded_rectangle((x0 + 8, ry - row / 2 + 4 + off, x1 - 8, ry + row / 2 - 4 + off), radius=12, fill=col + (int(255 * a),))
        d.text((x0 + 26, ry + off), label, font=f, fill=(48, 54, 64, int(255 * a)), anchor="lm")
        if i == 2:
            fb = ifont(650, 20)
            bw = fb.getlength("top shelf") + 26
            bx = x0 + 32 + f.getlength(label)
            d.rounded_rectangle((bx, ry - 16 + off, bx + bw, ry + 16 + off), radius=16, fill=ORANGE + (int(255 * a),))
            d.text((bx + bw / 2, ry + off), "top shelf", font=fb, fill=(40, 22, 8, int(255 * a)), anchor="mm")
    return lay


def prompt_scene(t):
    """Prompt-Leiste mit Text, Menü und Kamera (2.35–4.67)."""
    if t < 2.55:
        txt, ink = PLACEHOLDER, (128, 134, 144)
    elif t < 2.65:
        n = int(len(PLACEHOLDER) * (1 - (t - 2.55) / 0.1))
        txt, ink = PLACEHOLDER[:max(0, n)], (128, 134, 144)
    else:
        n = min(len(PROMPT), int((t - 2.65) / 0.45 * len(PROMPT)) + 1)
        txt, ink = PROMPT[:n], (30, 32, 38)
    shimmer = c01((t - 3.12) / 0.16) if t < 3.3 else None
    lay = bar_layer(txt, ink, t, caret=t >= 2.55, shimmer=shimmer)
    mn = menu_layer(t)
    if mn:
        lay.alpha_composite(mn)
    return lay


# ================================================================= Segment-Schalter
def pill_layer(knob_pos, sc=1.0, ox=0.0, oy=0.0, macro=0.0, blue=0.0, label_x=0.0, track_a=1.0, labels_a=1.0):
    """Schalter Forward | Defense | Goalie; Geometrie direkt in Bildschirmkoordinaten (scharf bei Zoom)."""
    cx, cy, w, h = PILL["cx"] * sc + ox, PILL["cy"] * sc + oy, PILL["w"] * sc, PILL["h"] * sc
    lay = layer()
    x0, y0 = cx - w / 2, cy - h / 2
    seg = w / 3
    if track_a > 0.01:
        tl = layer()
        td = ImageDraw.Draw(tl)
        dark, frost = (60, 62, 70), (212, 216, 222)
        tc = tuple(int(lerp(a, b, macro)) for a, b in zip(dark, frost))
        td.rounded_rectangle((x0, y0, x0 + w, y0 + h), radius=h / 2, fill=tc + (int(225 + 30 * macro),))
        td.line((x0 + h / 2, y0 + 1, x0 + w - h / 2, y0 + 1), fill=(255, 255, 255, 40), width=max(1, int(sc)))
        if blue > 0:
            kx = x0 + seg * (knob_pos + 0.5)
            grad = layer()
            gd = ImageDraw.Draw(grad)
            fade_w = 0.40 * SW
            steps = 48
            for k in range(steps):
                u = k / steps
                xa = kx - fade_w * (1 - u)
                col = tuple(int(lerp(a, b, u)) for a, b in zip(tc, ICE_DEEP))
                gd.rectangle((xa, y0, xa + fade_w / steps + 2, y0 + h), fill=col + (int(255 * blue),))
            gd.rectangle((kx, y0, x0 + w, y0 + h), fill=ICE_DEEP + (int(255 * blue),))
            mk = Image.new("L", (SW, SH), 0)
            ImageDraw.Draw(mk).rounded_rectangle((x0, y0, x0 + w, y0 + h), radius=h / 2, fill=255)
            grad.putalpha(ImageChops.multiply(grad.getchannel("A"), mk))
            tl.alpha_composite(grad)
        lay.alpha_composite(fade(tl, track_a))
    # Beschriftungen
    f = ifont(600, max(6, int(h * 0.3)))
    if labels_a > 0.01:
        ld = ImageDraw.Draw(lay)
        for i, lb in enumerate(LABELS):
            lx = x0 + seg * (i + 0.5) + label_x
            if i == 2 and macro > 0.5:
                for ddx, ddy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                    ld.text((lx + ddx * sc / 3, cy + ddy * sc / 3), lb, font=f, fill=(30, 32, 38, int(255 * labels_a)), anchor="mm")
            ld.text((lx, cy), lb, font=f, fill=(240, 242, 245, int(220 * labels_a)), anchor="mm")
    return lay


def knob_layer(knob_pos, sc, ox, oy, blue_k, shrink=1.0, dx=0.0, alpha=1.0):
    cx, cy, w, h = PILL["cx"] * sc + ox, PILL["cy"] * sc + oy, PILL["w"] * sc, PILL["h"] * sc
    seg = w / 3
    kx = cx - w / 2 + seg * (knob_pos + 0.5) + dx
    kw, kh = (seg - 16 * sc) * shrink, (h - 16 * sc) * shrink
    lay = layer()
    k = layer()
    kd = ImageDraw.Draw(k)
    top_c = tuple(int(lerp(a, b, blue_k)) for a, b in zip((232, 234, 238), (150, 222, 255)))
    bot_c = tuple(int(lerp(a, b, blue_k)) for a, b in zip((218, 221, 226), ICE))
    steps = 24
    for i in range(steps):
        u = i / steps
        col = tuple(int(lerp(a, b, u)) for a, b in zip(top_c, bot_c))
        kd.rectangle((kx - kw / 2, cy - kh / 2 + kh * u, kx + kw / 2, cy - kh / 2 + kh * (u + 1 / steps) + 1), fill=col + (255,))
    mk = Image.new("L", (SW, SH), 0)
    ImageDraw.Draw(mk).rounded_rectangle((kx - kw / 2, cy - kh / 2, kx + kw / 2, cy + kh / 2), radius=kh / 2, fill=255)
    k.putalpha(ImageChops.multiply(k.getchannel("A"), mk))
    if blue_k > 0.05:
        ImageDraw.Draw(k).rounded_rectangle((kx - kw / 2, cy - kh / 2, kx + kw / 2, cy + kh / 2), radius=kh / 2,
                                            outline=(35, 150, 235, int(255 * blue_k)), width=max(1, int(3 * sc / 2)))
    halo = layer()
    ImageDraw.Draw(halo).rounded_rectangle((kx - kw / 2, cy - kh / 2, kx + kw / 2, cy + kh / 2), radius=kh / 2,
                                           fill=tuple(int(lerp(a, b, blue_k)) for a, b in zip((255, 255, 255), ICE)) + (255,))
    glow(lay, halo, 24 * max(1.0, sc / 2), 0.35 + 0.15 * blue_k, keep=False)
    lay.alpha_composite(k)
    # Beschriftung auf dem Knopf
    f = ifont(int(lerp(600, 700, blue_k)), max(6, int(h * 0.3 * shrink)))
    d = ImageDraw.Draw(lay)
    lab_old, lab_new = "Defense", "Goalie"
    q = c01((blue_k - 0.25) / 0.5)
    if q < 1:
        d.text((kx, cy), lab_old, font=f, fill=(40, 44, 52, int(255 * (1 - q))), anchor="mm")
    if q > 0:
        d.text((kx, cy), lab_new, font=f, fill=(255, 255, 255, int(255 * q)), anchor="mm")
    return fade(lay, alpha)


def pill_scene(t):
    """4.40–6.30: Schalter steigt auf, Punch-in, Knopf gleitet zu Goalie, Kamerafahrt, Ausflug nach links."""
    if t < 4.67:
        q = e_io((t - 4.40) / 0.27)
        oy = lerp(1.30 * SH - PILL["cy"], 0, q)
        lay = pill_layer(1, oy=oy)
        lay.alpha_composite(knob_layer(1, 1.0, 0, oy, 0.0))
        return lay
    if t < 5.10:
        tt_ = t - 4.67
        oy = -0.012 * SH * math.exp(-tt_ * 9) * math.sin(tt_ * 24) - 0.01 * SH * c01(tt_ / 0.43)
        ox = 0.01 * SW * c01(tt_ / 0.43)
        lay = pill_layer(1, ox=ox, oy=oy)
        lay.alpha_composite(knob_layer(1, 1.0, ox, oy, 0.0))
        return lay
    base = (1.0, 0.01 * SW, -0.01 * SH)
    piv = (PILL["cx"] + PILL["w"] / 3 + 70, PILL["cy"])
    macro_cam = pivot_cam(3.0, piv, (0.45 * SW, 0.50 * SH))
    q = e_in(c01((t - 5.10) / 0.07), 2)
    sc, ox, oy = (lerp(a, b, q) for a, b in zip(base, macro_cam))
    if t >= 5.45:                                       # Kamerafahrt: Inhalt wandert nach links
        ox -= 0.25 * SW * c01((t - 5.45) / 0.6) ** 1.1
    slide = c01((t - 5.17) / 0.28)
    knob = 1 + e_back(slide, 0.9) if t >= 5.17 else 1.0
    blue_k = c01((slide - 0.3) / 0.6)
    exit_p = c01((t - 6.05) / 0.12)
    track_a = 1 - exit_p
    lay = pill_layer(knob, sc, ox, oy, macro=q, blue=blue_k, track_a=track_a, labels_a=track_a)
    shrink = lerp(1.0, 0.55, e_in(exit_p, 2))
    dx = -1.3 * SW * e_in(c01((t - 6.17) / 0.13), 2)
    lay.alpha_composite(knob_layer(knob, sc, ox, oy, blue_k, shrink=shrink, dx=dx))
    return lay


# ================================================================= Kufen-Spuren, Wörter, Puck
_RIB = None


def ribbon_paths():
    global _RIB
    if _RIB is None:
        a = fx.bezier((1.05 * SW, -0.05 * SH), (0.92 * SW, 0.12 * SH), (0.86 * SW, 0.36 * SH), (0.70 * SW, 0.44 * SH), 140)
        line = np.stack([np.linspace(0.70 * SW, -0.10 * SW, 120), np.full(120, 0.44 * SH)], 1)
        pa_ = np.concatenate([a, line[1:]])
        _RIB = (pa_, pa_ + np.array([0.03 * SW, 0.07 * SH]))
    return _RIB


def ribbons(base, t):
    A, B = ribbon_paths()
    for k, P in enumerate((A, B)):
        tt_ = t - 6.10 - k * 0.067
        if tt_ <= 0:
            continue
        head = 0.62 * e_expo(tt_ / 0.30) + 0.38 * c01((tt_ - 0.30) / 0.45)
        tail = max(0.0, head - 0.40) + 0.6 * c01((tt_ - 0.45) / 0.3)
        tail = min(tail, head)
        fx.ribbon(base, P, head, tail, col=ORANGE, hot=(255, 224, 190), width=7, double=12, glow_r=18)
        if k == 0 and tt_ < 0.36:
            seg = np.diff(P, axis=0)
            L = np.concatenate([[0], np.cumsum(np.hypot(seg[:, 0], seg[:, 1]))])
            L /= L[-1]
            hx, hy = P[min(len(P) - 1, int(np.searchsorted(L, head)))]
            spray_blob(base, hx, hy, 1.0, seed=int(tt_ * 30))


def spray_blob(base, x, y, a, seed=0):
    fx.blob(base, x, y, 34, 34, (255, 255, 255), 0.8 * a)
    rng = random.Random(seed)
    d = ImageDraw.Draw(base)
    for _ in range(14):
        px, py, r = x + rng.uniform(-30, 30), y + rng.uniform(-22, 22), rng.uniform(1.5, 3.5)
        d.ellipse((px - r, py - r, px + r, py + r), fill=(255, 255, 255, int(200 * a)))


def word(txt, x, y, a=1.0, size=WORD_SIZE, col=WHITE):
    return text_layer(txt, size, 650, col, 0, cx=x, cy=y, alpha=a)


def squeeze(lay, sx, sy, cx, cy):
    big = lay.resize((max(1, int(SW * sx)), max(1, int(SH * sy))), Image.BILINEAR)
    out = layer()
    put(out, big, cx - cx * sx, cy - cy * sy)
    return out


def puck_layer(x, y, sx=1.0, sy=1.0, a=1.0, scale=1.0):
    """Puck in 3/4-Ansicht, Unterkante bei y (Mitte x). Maße 3:1 wie ein echter Puck."""
    w, tk = PUCK_W * scale * sx, PUCK_T * scale * sy
    eh = w * 0.22
    lay = layer()
    halo = layer()
    ImageDraw.Draw(halo).ellipse((x - w * 0.8, y - tk - eh * 2, x + w * 0.8, y + eh), fill=ICE + (255,))
    glow(lay, halo, 26, 0.25, keep=False)
    d = ImageDraw.Draw(lay)
    d.ellipse((x - w / 2, y - eh, x + w / 2, y + eh * 0.0 + eh), fill=(14, 14, 16, 255))
    d.rectangle((x - w / 2, y - tk, x + w / 2, y), fill=(14, 14, 16, 255))
    d.ellipse((x - w / 2, y - tk - eh, x + w / 2, y - tk + eh), fill=(28, 28, 32, 255))
    d.arc((x - w / 2, y - tk - eh, x + w / 2, y - tk + eh), 180, 360, fill=(235, 240, 245, 220), width=2)
    d.arc((x - w / 2, y - tk - eh, x + w / 2, y - tk + eh), 0, 180, fill=(120, 130, 140, 120), width=1)
    return fade(lay, a)


def floor_layer(p_in, p_out=0.0):
    """Bullypunkt (blau, 4x Puckbreite) auf der roten Mittellinie, perspektivisch flach."""
    sx = e_out(p_in, 3) * (1 - e_in(p_out, 2))
    if sx <= 0.01:
        return None
    lay = layer()
    d = ImageDraw.Draw(lay)
    cx, cy = SW / 2, Y_FLOOR + 8
    lw = 0.56 * SW * sx
    steps = 40
    for k in range(steps):
        u = k / steps
        a = math.sin(math.pi * u) ** 0.6
        d.rectangle((cx - lw / 2 + lw * u, cy - 4, cx - lw / 2 + lw * (u + 1 / steps) + 1, cy + 4), fill=(215, 40, 55, int(255 * a)))
    sw_, sh_ = SPOT_W * sx, 50 * sx
    spot = layer()
    ImageDraw.Draw(spot).ellipse((cx - sw_ / 2, cy - sh_ / 2, cx + sw_ / 2, cy + sh_ / 2), fill=(35, 110, 235, 255))
    glow(lay, spot, 22, 0.35)
    return lay


def arcs(base, t):
    for k, x0 in enumerate((0.30 * SW, 0.70 * SW)):
        sgn = 1 if k == 0 else -1
        P = fx.bezier((x0, 1.05 * SH), (x0 + sgn * 10, 0.7 * SH), (x0 + sgn * 50, 0.3 * SH), (x0 + sgn * 80, -0.08 * SH), 120)
        tt_ = t - 7.45
        head = c01(tt_ / 0.2)
        tail = c01((tt_ - 0.08) / 0.2)
        fx.ribbon(base, P, head, tail, col=ICE, hot=(200, 240, 255), width=4, double=10, glow_r=14)


def spray(base, t, n=60, seed=8):
    tt_ = t - 8.13
    if tt_ < 0 or tt_ > 0.5:
        return
    rng = random.Random(seed)
    d = ImageDraw.Draw(base)
    for _ in range(n):
        ang = math.radians(rng.uniform(-150, -30))
        sp = rng.uniform(0.35, 0.9) * SH
        r = rng.uniform(1.5, 4.0)
        col = (240, 248, 255) if rng.random() < 0.5 else ICE
        x = SW / 2 + math.cos(ang) * sp * tt_
        y = Y_FLOOR + math.sin(ang) * sp * tt_ + 0.5 * 1.5 * SH * tt_ * tt_
        a = c01(1 - tt_ / 0.35)
        if a > 0:
            d.ellipse((x - r, y - r, x + r, y + r), fill=col + (int(255 * a),))


def shoot_letters(t, y):
    txt = "Shoot"
    f = ifont(650, WORD_SIZE)
    widths = [f.getlength(ch) for ch in txt]
    x = SW / 2 - sum(widths) / 2
    lay = layer()
    d = ImageDraw.Draw(lay)
    rng = random.Random(3)
    for i, ch in enumerate(txt):
        tau = t - 8.20 - 0.05 * i
        sx0, sy0 = SW / 2 + rng.uniform(-160, 160), Y_FLOOR - rng.uniform(150, 320)
        cx = x + widths[i] / 2
        x += widths[i]
        if tau < 0:
            continue
        if tau < 0.15:
            p = e_out(tau / 0.15, 3)
            px, py = lerp(sx0, cx, p), lerp(sy0, y, p)
        else:
            u = tau - 0.15
            px, py = cx, y - 0.035 * SH * abs(math.sin(2 * math.pi / 0.32 * u)) * math.exp(-9 * u)
        d.text((px, py), ch, font=f, fill=WHITE + (int(255 * c01(tau / 0.06)),), anchor="mm")
    return lay


def band_mask(lay, y0, y1, soft=10):
    mk = Image.new("L", (SW, SH), 0)
    ImageDraw.Draw(mk).rectangle((0, y0, SW, y1), fill=255)
    mk = mk.filter(ImageFilter.GaussianBlur(soft))
    lay.putalpha(ImageChops.multiply(lay.getchannel("A"), mk))
    return lay


# ================================================================= Torlampe, Burst, CTA
LAMP_R = 140


def lamp_icon(d, cx, cy, s, col, lit=0.0):
    """Torlampe: Kuppel auf Sockel, drei Strahlen darüber."""
    w, h = 54 * s, 42 * s
    by = cy + 22 * s
    dome = (cx - w / 2, by - h, cx + w / 2, by + h)
    if lit > 0:
        fill = tuple(int(lerp(a, b, lit)) for a, b in zip(CHAR, GOAL_RED))
        d.pieslice(dome, 180, 360, fill=fill + (255,))
        d.ellipse((cx - w * 0.18, by - h * 0.75, cx + w * 0.05, by - h * 0.45), fill=(255, 150, 110, int(255 * lit)))
    d.arc(dome, 180, 360, fill=col, width=max(2, int(4 * s)))
    d.rounded_rectangle((cx - w / 2 - 6 * s, by, cx + w / 2 + 6 * s, by + 12 * s), radius=4 * s, fill=col)
    ray = col if lit < 0.5 else ORANGE + (255,)
    for ang in (-45, 0, 45):
        a = math.radians(ang - 90)
        r0, r1 = h + 12 * s, h + 28 * s
        d.line((cx + math.cos(a) * r0, by + math.sin(a) * r0, cx + math.cos(a) * r1, by + math.sin(a) * r1), fill=ray, width=max(2, int(4 * s)))


def lamp_layer(cx, cy, ring_p, lit=0.0, alpha=1.0, ring_glow=0.0):
    lay = layer()
    d = ImageDraw.Draw(lay)
    if lit > 0:
        g = layer()
        ImageDraw.Draw(g).ellipse((cx - 80, cy - 50, cx + 80, cy + 64), fill=(255, 90, 50, 255))
        glow(lay, g, 40, 0.6 * lit, keep=False)
    if ring_p > 0:
        rl = layer()
        ImageDraw.Draw(rl).arc((cx - LAMP_R, cy - LAMP_R, cx + LAMP_R, cy + LAMP_R), -90, -90 + 360 * c01(ring_p),
                               fill=WHITE + (255,), width=5)
        if ring_glow > 0:
            glow(lay, rl, 30, ring_glow)
        else:
            lay.alpha_composite(rl)
    lamp_icon(d, cx, cy, 1.6, WHITE + (255,), lit)
    return fade(lay, alpha)


_CONE = None


def beams(base, t, alpha):
    global _CONE
    if _CONE is None:
        _CONE = np.arctan2(fx._YY - SH / 2, fx._XX - SW / 2)
    rot = math.radians(450) * t
    a1 = np.cos(_CONE - rot)
    m_ = (np.clip((a1 - math.cos(math.radians(13))) / 0.04, 0, 1) + np.clip((-a1 - math.cos(math.radians(13))) / 0.04, 0, 1))
    lay = np.zeros((SH, SW, 4), np.float32)
    lay[..., :3] = ORANGE
    lay[..., 3] = m_ * 0.22 * alpha * 255
    base.alpha_composite(Image.fromarray(lay.astype(np.uint8), "RGBA").filter(ImageFilter.GaussianBlur(6)))


def mini_puck(d, x, y, s):
    w, tk = 54 * s, 18 * s
    eh = w * 0.22
    d.ellipse((x - w / 2, y - eh, x + w / 2, y + eh), fill=(200, 205, 212, 255))
    d.rectangle((x - w / 2, y - tk, x + w / 2, y), fill=(200, 205, 212, 255))
    d.ellipse((x - w / 2, y - tk - eh, x + w / 2, y - tk + eh), fill=(245, 248, 250, 255))


PUCK_ANGLES = [18, 64, 118, 160, 205, 252, 318]
LOCK_X = 0.31 * SW
LABEL_X = LOCK_X + 140 + 50
CTA = "FOLLOW FOR MORE"


def burst_bg(t):
    """Warmer Rot-Verlauf, der diagonal von links oben hereinwischt."""
    q = c01((t - 10.20) / 0.12)
    out = 1 - c01((t - 10.75) / 0.25)
    diag = (fx._XX / SW + fx._YY / SH) / 2
    edge = np.clip((q * 1.6 - diag) / 0.3, 0, 1) * out
    tl = np.array([150, 28, 22], np.float32)
    mid = np.array([64, 34, 40], np.float32)
    br = np.array([30, 22, 28], np.float32)
    g = np.clip(diag[..., None] * 2, 0, 1)
    col = np.where(diag[..., None] < 0.5, tl + (mid - tl) * g, mid + (br - mid) * np.clip(g - 1, 0, 1))
    arr = np.dstack([col, edge * 255])
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")


# ================================================================= Wortmarke
MARK = "@bladesandpucks"
MARK_SIZE = 76


def wordmark(t):
    lay = layer()
    if t < 13.05:
        return lay
    tt_ = t - 13.05
    f = ifont(650, MARK_SIZE)
    widths = [f.getlength(ch) for ch in MARK]
    total = sum(widths)
    sc = lerp(1.6, 1.0, e_out(c01(tt_ / 0.95), 3))
    inner = layer()
    d = ImageDraw.Draw(inner)
    x = SW / 2 - total / 2
    n = len(MARK)
    for i, ch in enumerate(MARK):
        cx = x + widths[i] / 2
        x += widths[i]
        book = i in (0, n - 1)
        land = 0.0 if book else 0.07 + 0.055 * (i - 1)
        if book:
            cool = c01((tt_ - 0.65) / 0.35)
            col = tuple(int(lerp(a, b, cool)) for a, b in zip(ORANGE, WARMWHITE))
            if tt_ < 0.25:
                k = 1 - tt_ / 0.25
                for j in range(6):
                    yy = SH / 2 - 30 + j * 12
                    sc_col = ORANGE if j % 2 else ICE
                    d.line((cx - 50, yy, cx + 50, yy), fill=sc_col + (int(150 * k),), width=2)
                    d.text((cx - 4 * k, SH / 2), ch, font=f, fill=(255, 60, 60, int(120 * k)), anchor="mm")
                    d.text((cx + 4 * k, SH / 2), ch, font=f, fill=(60, 160, 255, int(120 * k)), anchor="mm")
            d.text((cx, SH / 2), ch, font=f, fill=col + (255,), anchor="mm")
            continue
        tau = tt_ - land
        if tau < -0.22:
            continue
        for ghost, ga in ((0.066, 0.10), (0.033, 0.20), (0.0, 1.0)):
            u = c01((tau - ghost + 0.22) / 0.22)
            if u <= 0:
                continue
            yy = SH / 2 - 0.12 * SH * (1 - e_back(u, 0.5))
            rot = -25 * (1 - e_out(u, 3))
            cool = c01((tau - ghost) / 0.25)
            col = tuple(int(lerp(a, b, cool)) for a, b in zip(ORANGE, WARMWHITE))
            if ghost == 0.0:
                al = 255
            else:
                al = int(255 * ga) if u < 1 else 0
            if al <= 0:
                continue
            gl = Image.new("RGBA", (int(widths[i]) + 60, MARK_SIZE + 60), (0, 0, 0, 0))
            ImageDraw.Draw(gl).text((gl.width / 2, gl.height / 2), ch, font=f, fill=col + (al,), anchor="mm")
            if abs(rot) > 0.5:
                gl = gl.rotate(rot, resample=Image.BICUBIC)
            put(inner, gl, cx - gl.width / 2, yy - gl.height / 2)
    return squeeze(inner, sc, sc, SW / 2, SH / 2) if abs(sc - 1) > 0.002 else inner


# ================================================================= Bildschirminhalt
def hud_alpha(t):
    return c01((t - 0.25) / 0.15) * (1 - c01((t - 5.80) / 0.2))


CURSOR_KEYS = [(0.0, (0.64 * SW, 0.72 * SH)), (0.10, (0.64 * SW, 0.72 * SH)), (0.90, (0.50 * SW, 0.62 * SH)),
               (1.40, (0.50 * SW, 0.62 * SH)), (1.72, (SW / 2, SH - 169)), (3.28, (SW / 2, SH - 169))]


def cursor_pos(t):
    if t >= 3.28:
        cam = cam_at(t)
        chip = to_screen((CHIP[0], CHIP[1]), cam_at(3.55))
        if t < 3.52:
            p = e_io((t - 3.28) / 0.24)
            a = (SW / 2, SH - 169)
            return lerp(a[0], chip[0], p), lerp(a[1], chip[1], p)
        rows_y = [CHIP[1] + 34 + 10 + 64 * (i + 0.5) for i in range(3)]
        tgt = None
        for t0, i in ((3.75, 0), (3.87, 1), (4.0, 2)):
            if t >= t0 - 0.1:
                tgt = (CHIP[0] + 40, rows_y[i])
        if tgt is None:
            return to_screen((CHIP[0], CHIP[1]), cam)
        return to_screen(tgt, cam)
    for (t0, a), (t1, b) in zip(CURSOR_KEYS, CURSOR_KEYS[1:]):
        if t <= t1:
            p = e_io((t - t0) / max(1e-6, t1 - t0))
            return lerp(a[0], b[0], p), lerp(a[1], b[1], p)
    return CURSOR_KEYS[-1][1]


CLICKS = [1.00, 1.80, 3.55, 4.03]


def chrome(img, t):
    a = hud_alpha(t)
    if a > 0.01:
        draw_hud(img, max(0.0, t - 1.97), 14, a, playing=t >= 1.80, cy=SH - 150)
    if t < 6.0:
        x, y = cursor_pos(t)
        dip = any(0 <= t - c < 0.07 for c in CLICKS)
        ca = 1 - c01((t - 5.80) / 0.2)
        if ca > 0.02:
            cl = layer()
            draw_cursor(cl, x, y, 1.9 * (0.92 if dip else 1.0))
            img.alpha_composite(fade(cl, ca))


def content(t):
    """Motion-Design-Inhalt (ohne Player/Mauszeiger)."""
    # ---- Hook: Prompt-Leiste mit Platzhalter, blaue Ränder, Zoom-Explosion
    if t < 1.37:
        img = fx.bg()
        v = e_out(c01((t - 1.0) / 0.25), 2)
        glow_a = lerp(0.10, 0.35, v)
        fx.blob(img, BAR["cx"], BAR["cy"], lerp(0.45, 0.6, v) * SW, lerp(0.45, 0.6, v) * SW * 0.6, (255, 255, 255), glow_a * 0.6)
        edge_vignette(img, (30, 120, 240), 0.85 * v)
        if t < 1.30:
            img.alpha_composite(bar_layer(PLACEHOLDER, (128, 134, 144), t, shimmer=c01((t - 1.05) / 0.23) if t > 1.05 else None))
        else:
            q = c01((t - 1.30) / 0.07)
            s_ = math.exp(math.log(12) * q ** 1.6)
            img.alpha_composite(bar_layer(PLACEHOLDER, (128, 134, 144), t, fill_w=BAR["w"] * s_, fill_h=BAR["h"] * s_,
                                          radius=BAR["h"] * 0.22 * s_, content_a=1 - c01(q * 2)))
        return img
    # ---- frische Eisfläche
    if t < 1.95:
        q = c01((t - 1.37) / 0.05)
        col = tuple(int(lerp(a, b, q)) for a, b in zip(FROST, ICEFIELD))
        arr = np.empty((SH, SW, 4), np.float32)
        arr[..., :3] = np.array(col, np.float32) * (1 - 0.04 * fx._YY[..., None] / SH)
        sheen = np.exp(-(((fx._XX - 0.7 * fx._YY) - (0.3 + 0.02 * (t - 1.37)) * SW) / 120) ** 2) * 6
        arr[..., :3] += sheen[..., None]
        arr[..., 3] = 255
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    # ---- Verschluss zurück zur Leiste, Tippen, Menü, Whip
    if t < 4.67:
        img = fx.bg()
        cam = cam_at(t)
        if t < 2.65:
            vg = 1 - c01((t - 2.35) / 0.3)
            fx.blob(img, BAR["cx"], BAR["cy"], 0.6 * SW, 0.36 * SW, (255, 255, 255), 0.3 * vg * 0.6)
            edge_vignette(img, (30, 120, 240), 0.8 * vg)
        if t >= 4.03:
            gy = lerp(1.45, 1.30, e_out(c01((t - 4.03) / 0.30), 3)) * SH
            ry = 0.60 * SH
            if t > 4.40:
                w_ = e_io((t - 4.40) / 0.27)
                gy, ry = lerp(1.30, 1.18, w_) * SH, lerp(0.60, 0.30, w_) * SH
            fx.blob(img, SW / 2, gy, 0.95 * SW, ry, (30, 120, 255), 0.85 * c01((t - 4.03) / 0.3))
        if t < 2.08:                                       # Verschluss
            q = e_in(c01((t - 1.95) / 0.13), 3)
            top, bot = lerp(0, BAR["cy"] - BAR["h"] / 2, q), lerp(SH, BAR["cy"] + BAR["h"] / 2, q)
            lay = layer()
            ImageDraw.Draw(lay).rectangle((0, top, SW, bot), fill=ICEFIELD + (255,))
            img.alpha_composite(mblur(lay, 0, 30 * (1 - q) + 10))
            return img
        if t < 2.35:
            q = e_expo(c01((t - 2.08) / 0.22))
            w_ = lerp(SW, BAR["w"], q)
            col = tuple(int(lerp(a, b, q)) for a, b in zip(ICEFIELD, FROST))
            ca = c01((t - 2.18) / 0.10)
            lay = bar_layer(PLACEHOLDER, (128, 134, 144), t, fill_w=w_, radius=BAR["h"] * 0.22 * q, fill_col=col, content_a=ca,
                            shimmer=c01((t - 2.12) / 0.23))
            img.alpha_composite(lay)
            return img
        lay = cam_apply(prompt_scene(t), *cam)
        if t >= 4.40:                                      # vertikaler Whip
            q = e_io((t - 4.40) / 0.27)
            moved = layer()
            put(moved, lay, 0, -1.30 * SH * q)
            lay = moved
            img.alpha_composite(lay)
            img.alpha_composite(pill_scene(t))
            return img
        img.alpha_composite(lay)
        return img
    # ---- Schalter
    if t < 6.30:
        img = fx.bg()
        if t < 5.07:
            fx.blob(img, SW / 2, 1.18 * SH, 0.95 * SW, 0.30 * SH, (30, 120, 255), 0.85 * (1 - c01((t - 4.67) / 0.4)))
        img.alpha_composite(pill_scene(t))
        if t >= 6.05:
            ribbons(img, t)
        return img
    # ---- Kufen-Spuren liefern "Skate", Lichtfleck, Puck
    img = fx.bg()
    if t < 6.95:
        ribbons(img, t)
    if t < 7.40:
        if t < 6.45:
            return img
        p = e_expo((t - 6.45) / 0.40)
        x = lerp(0.66 * SW, SW / 2, p)
        y = 0.47 * SH
        if t >= 7.0:
            bx = lerp(1.35, -0.35, (t - 7.0) / 0.4) * SW
            fx.blob(img, bx, y, 0.42 * SW, 0.36 * SW, ICE, 0.75)
        wl = word("Skate", x, y, c01((t - 6.40) / 0.1))
        if t < 6.50:
            wl = wl.filter(ImageFilter.GaussianBlur(8 * (1 - c01((t - 6.40) / 0.1))))
        if 7.0 <= t:
            over = max(0.0, 1 - abs((lerp(1.35, -0.35, (t - 7.0) / 0.4) * SW - x) / (0.3 * SW)))
            if over > 0:
                glow(img, wl, 20, 0.6 * over, keep=False)
        if t >= 7.22:
            k = c01((t - 7.22) / 0.18)
            wl = mblur(wl, -60 * k, 0)
            wl = squeeze(wl, lerp(1, 0.15, e_in(k, 2)), lerp(1, 0.6, k), x, y)
            wl = fade(wl, 1 - k)
            bx, by = x, lerp(y, Y_PUCK0 - PUCK_T, e_io(k))
            fx.blob(img, bx, by, 40 + 20 * k, 40 + 20 * k, (255, 255, 255), 0.8 * k)
        img.alpha_composite(wl)
        return img
    if t < 8.13:
        fl = floor_layer(c01((t - 7.42) / 0.10))
        if fl:
            img.alpha_composite(fl)
        arcs(img, t)
        if t < 7.53:
            q = c01((t - 7.40) / 0.13)
            fx.blob(img, SW / 2, Y_PUCK0 - PUCK_T, 60, 60, (255, 255, 255), 0.8 * (1 - q))
            img.alpha_composite(puck_layer(SW / 2, Y_PUCK0, a=q))
            return img
        if t < 7.80:
            q = e_io((t - 7.50) / 0.30)
            bob = 3 * math.sin((t - 7.5) * 18)
            img.alpha_composite(puck_layer(SW / 2, Y_PUCK0 + bob, scale=lerp(1.0, 0.92, q)))
            return img
        tau = c01((t - 7.80) / 0.33)
        y = lerp(Y_PUCK0, Y_FLOOR, tau * tau)
        img.alpha_composite(puck_layer(SW / 2, y, sx=1 - 0.08 * tau * tau, sy=1 + 0.25 * tau * tau, scale=0.92))
        return img
    # ---- Aufprall, Spray, "Shoot" -> "Score"
    if t < 8.95:
        y_w = 0.48 * SH
        gl_a = c01((t - 8.13) / 0.15) * (1 - c01((t - 8.70) / 0.35))
        fx.blob(img, SW / 2 + 0.03 * SW * c01((t - 8.7) / 0.35), y_w - 0.03 * SH * c01((t - 8.7) / 0.35),
                0.22 * SW * 1.4, 0.16 * SH * 1.4, (55, 90, 220), 0.7 * gl_a)
        fl = floor_layer(1.0, c01((t - 8.13) / 0.27))
        if fl:
            img.alpha_composite(fl)
        bloom_a = 0.5 * (1 - c01((t - 8.13) / 0.3))
        if bloom_a > 0:
            fx.blob(img, SW / 2, Y_FLOOR, 0.10 * SW, 0.10 * SW, (255, 255, 255), bloom_a)
        tau = t - 8.13
        if tau < 0.2:
            sq = math.exp(-tau * 14) * math.cos(tau * 40)
            img.alpha_composite(puck_layer(SW / 2, Y_FLOOR, sx=1 + 0.15 * sq, sy=1 - 0.30 * sq, a=1 - c01(tau / 0.2), scale=0.92))
        spray(img, t)
        if t < 8.60:
            img.alpha_composite(shoot_letters(t, y_w))
        else:
            q = e_expo((t - 8.62) / 0.2)
            a = band_mask(word("Shoot", SW / 2, y_w - 0.06 * SH * q, 1 - q), y_w - 0.07 * SH, y_w + 0.07 * SH)
            b = band_mask(word("Score", SW / 2, y_w + 0.06 * SH * (1 - q), q), y_w - 0.07 * SH, y_w + 0.07 * SH)
            img.alpha_composite(a)
            img.alpha_composite(b)
        return img
    # ---- "Score" schwebt hoch und verlässt das Bild, Torlampe steigt auf
    if t < 10.20:
        if t < 9.83:
            yy = 0.48 * SH - 0.08 * SH * c01((t - 8.95) / 0.6) - 0.62 * SH * e_in(c01((t - 9.55) / 0.28), 3)
            tw = text_width("Score", WORD_SIZE, 650)
            fx.blob(img, SW / 2, yy, tw * 0.8, WORD_SIZE * 1.1, (255, 255, 255), 0.28)
            img.alpha_composite(word("Score", SW / 2, yy))
        if t >= 9.80:
            yy = lerp(1.10 * SH, 0.50 * SH, e_expo((t - 9.80) / 0.20))
            img.alpha_composite(lamp_layer(SW / 2, yy, e_io((t - 9.98) / 0.15)))
        return img
    # ---- Torlicht-Burst
    if t < 10.75:
        img.alpha_composite(burst_bg(t))
        beams(img, t, 1.0)
        d = ImageDraw.Draw(img)
        for k, ang in enumerate(PUCK_ANGLES):
            tau = t - 10.24 - 0.03 * k
            if tau < 0:
                continue
            s_ = e_back(tau / 0.17, 2.0) * 1.15
            rr = 1.0 + 0.06 * c01(tau / 0.5) + (0.1 if k % 2 else -0.08)
            px = SW / 2 + math.cos(math.radians(ang)) * 0.30 * SW * rr
            py = SH / 2 + math.sin(math.radians(ang)) * 0.32 * SH * rr
            mini_puck(d, px, py, s_)
        pulse = c01((t - 10.20) / 0.1) * 0.8 if t < 10.30 else lerp(0.8, 0.4, c01((t - 10.30) / 0.1))
        img.alpha_composite(lamp_layer(SW / 2, SH / 2, 1.0, lit=c01((t - 10.20) / 0.06), ring_glow=pulse))
        return img
    # ---- CTA: Lampe + FOLLOW FOR MORE
    if t < 13.05:
        if t < 11.0:
            img.alpha_composite(burst_bg(t))
            beams(img, t, 1 - c01((t - 10.75) / 0.25))
        if 11.05 <= t < 12.20:
            bx = lerp(0.80, 0.20, (t - 11.05) / 1.1) * SW
            for by in (0.43 * SH, 0.57 * SH):
                fx.blob(img, bx, by, 0.10 * SW, 0.10 * SW, ICE, 0.45)
        lx = lerp(SW / 2, LOCK_X, e_out(c01((t - 10.75) / 0.25), 3))
        lit = lerp(1.0, 0.55, c01((t - 10.75) / 0.4))
        ring_a = 0.55 if 11.40 <= t < 11.45 else 1.0
        lam = lamp_layer(lx, SH / 2, 1.0, lit=lit, ring_glow=0.0)
        if 13.0 <= t < 13.034:                               # Ein-Frame-Glitch
            arr = np.asarray(lam).copy()
            arr[..., 0] = np.roll(arr[..., 0], 4, 1)
            arr[..., 2] = np.roll(arr[..., 2], -4, 1)
            lam = Image.fromarray(arr, "RGBA")
            lam = squeeze(lam, 1, 1, 0, 0)
            moved = layer()
            put(moved, lam, 4, 0)
            lam = moved
        img.alpha_composite(fade(lam, ring_a))
        pa_ = e_expo((t - 10.85) / 0.2)
        passing = 0.0
        if 11.05 <= t < 12.20:
            bx = lerp(0.80, 0.20, (t - 11.05) / 1.1) * SW
            passing = max(0.0, 1 - abs(bx - (LABEL_X + 220)) / (0.15 * SW))
        col = tuple(int(lerp(a, b, passing)) for a, b in zip((225, 228, 232), (252, 252, 254)))
        lab = layer()
        ImageDraw.Draw(lab)
        tw = text_width(CTA, 48, 550, 3)
        lab = text_layer(CTA, 48, int(lerp(550, 700, passing)), col, 3, cx=LABEL_X + tw / 2 + 0.03 * SW * (1 - pa_), cy=SH / 2 + 2, alpha=pa_)
        img.alpha_composite(lab)
        return img
    # ---- Schwarz, Wortmarke
    img = Image.new("RGBA", (SW, SH), NEARBLACK + (255,))
    img.alpha_composite(wordmark(t))
    return img


def screen(t):
    img = content(t)
    chrome(img, t)
    return img


# ================================================================= Rendering
FAST = [(1.28, 1.40), (1.95, 2.32), (4.38, 4.70), (5.08, 5.47), (6.05, 6.50), (7.20, 7.42), (7.78, 8.20),
        (8.60, 8.85), (9.50, 10.05), (10.18, 10.32)]
OV = None


def render_frame(i):
    global OV
    if OV is None:
        OV = room.overlay_text(OVERLAY)
    t = i / FPS
    if any(a <= t < b for a, b in FAST):
        acc = None
        for dt in np.linspace(-1 / 120, 1 / 120, 6):
            arr = np.asarray(screen(max(0.0, t + dt)).convert("RGB")).astype(np.float32)
            acc = arr if acc is None else acc + arr
        scr = Image.fromarray(np.clip(acc / 6, 0, 255).astype(np.uint8))
    else:
        scr = screen(t).convert("RGB")
    return room.compose(scr, t, OV, seed=i).tobytes()


# ================================================================= Ton
def make_audio(path):
    mx = pa.Mix(DUR, seed=12)
    T = mx.t
    for c in CLICKS:
        mx.put(mx.room, mx.click(), c, 0.9)
    # Soundtrack der Animation (aus den Laptop-Lautsprechern)
    x = T(13.4)
    pad = mx.pad([330.0, 660.0, 990.0, 1320.0], 13.4, vol=0.22, attack=0.4, release=0.9)
    mx.put(mx.lap, pad, 1.97)
    mx.put(mx.lap, mx.pad([130.8, 261.6], 1.2, vol=0.25, attack=0.3, release=0.6), 4.03)
    mx.put(mx.lap, mx.pad([130.8, 261.6], 1.3, vol=0.22, attack=0.4, release=0.7), 11.05)
    mx.put(mx.lap, mx.whoosh(0.3, 0.25), 1.98)
    mx.put(mx.lap, mx.chime(880.0, vol=0.35), 3.55)
    mx.put(mx.lap, mx.whoosh(0.2, 0.45, rise=False), 4.44)
    mx.put(mx.lap, mx.pop(1400, 0.12), 5.12)
    zx = T(0.2)
    mx.put(mx.lap, mx.whoosh(0.2, 0.15), 5.2)
    mx.put(mx.lap, mx.pop(900, 0.15), 5.42)
    mx.put(mx.lap, mx.chime(1046.5, vol=0.18), 5.50)
    carve = mx.whoosh(0.35, 0.5, rise=False) * (0.7 + 0.3 * np.sign(np.sin(2 * np.pi * 40 * T(0.35))))
    mx.put(mx.lap, carve, 6.08)
    mx.put(mx.lap, mx.pluck(784.0, vol=0.28), 6.80)
    mx.put(mx.lap, mx.whoosh(0.3, 0.25), 7.05)
    mx.put(mx.lap, mx.pop(2000, 0.08), 7.98)
    tk = T(0.06)
    tock = np.sin(2 * np.pi * 180 * tk) * np.exp(-tk * 33) * 0.7 + mx.rng.standard_normal(len(tk)) * np.exp(-tk * 500) * 0.3
    mx.put(mx.lap, tock, 8.13)
    for k in range(18):
        mx.put(mx.lap, mx.click() * 0.25, 8.16 + mx.rng.uniform(0, 0.35))
    for k, f in enumerate((659.3, 784.0, 880.0, 1046.5, 1174.7)):
        mx.put(mx.lap, mx.pluck(f, vol=0.16), 8.35 + 0.05 * k)
    mx.put(mx.lap, mx.chime(784.0, vol=0.3) + np.pad(mx.chime(1568.0, vol=0.08), (0, 0)), 8.84)
    mx.put(mx.lap, mx.whoosh(0.33, 0.25), 9.50)
    mx.put(mx.lap, mx.whoosh(0.2, 0.3), 9.82)
    mx.put(mx.lap, mx.pop(1600, 0.12), 10.13)
    mx.put(mx.lap, mx.pop(700, 0.3), 10.24)
    mx.put(mx.lap, mx.pop(800, 0.25), 10.54)
    hx = T(0.5)
    horn = sum(2 * ((hx * f) % 1) - 1 for f in (220.0, 329.6)) / 2
    horn = np.convolve(horn, np.ones(40) / 40, mode="same") * np.minimum(hx / 0.05, 1) * np.clip((0.5 - hx) / 0.15, 0, 1) * 0.12
    mx.put(mx.lap, horn, 10.22)
    mx.put(mx.lap, mx.pop(1500, 0.08), 11.40)
    mx.put(mx.lap, mx.shimmer(0.4, 0.4), 12.80)
    mx.put(mx.lap, mx.thud(0.5), 13.05)
    for k in range(13):
        mx.put(mx.lap, mx.click() * 0.12, 13.12 + 0.055 * k + 0.2)
    mx.render(path, lap_gain=1.0, room_gain=0.6, target_peak=0.45)


def main():
    os.chdir(HERE)
    make_audio("audio_aimotion.wav")
    nf = int(DUR * FPS)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{room.W}x{room.H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_aimotion.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "21",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart",
           "reel12_ai_motion.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(4) as pool:
        for k, buf in enumerate(pool.imap(render_frame, range(nf), chunksize=2)):
            proc.stdin.write(buf)
            if k % 60 == 0:
                print(f"{k}/{nf}", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.frombytes("RGB", (room.W, room.H), render_frame(int(5.6 * FPS))).save("reel12_thumbnail.jpg", quality=92)
    print("fertig: reel12_ai_motion.mp4")


if __name__ == "__main__":
    main()
