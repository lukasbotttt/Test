"""Reel 12: "I asked AI to animate hockey" – Handyaufnahme eines Laptops im Neon-Zimmer, auf dem eine
minimalistische Hockey-Motion-Design-Animation läuft (nach dem viralen "Motion design by AI, 1 prompt"-Format).

Ablauf (13.4 s, Ende = Anfang für einen nahtlosen Loop):
  0.00 Prompt-Leiste, Klick auf Play -> 0.60 Eisfläche mit Mittellinie, Bullypunkt und Mittelkreis
  1.15 Leiste formt sich neu, Prompt "Show me what AI can do with hockey" wird getippt
  2.75 Schuss-Menü (Snipe / top shelf) -> 3.50 Whip zum Schalter Goalie | Defense | Forward
  4.32 Knopf gleitet zu Forward -> 5.15 Kufen-Spuren liefern "Skate" -> 6.05 Licht verwischt es zum Puck
  6.80 Puck fällt auf den Bullypunkt (maßstabsgetreu: 3 Zoll Puck, 12 Zoll Punkt, 12 Zoll Linie)
  7.50 Eis-Spray -> "Shoot" -> "Score" -> 9.45 Torlicht (rot, Hupe) -> 10.3 COMMENT YOUR POSITION
  11.45 Wortmarke @bladesandpucks -> 12.75 fällt zurück in die Prompt-Leiste (Loop)
Fakten: NHL-Regeln 13.1 (Puck 3 Zoll Durchmesser, 1 Zoll dick), 1.9 (Bullypunkt Mitte blau, 12 Zoll;
Mittelkreis 15 Fuß Radius), 1.5 (rote Mittellinie, 12 Zoll breit), 4.1 (rotes Torlicht).
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
from screen_fx import (SW, SH, ICE, ORANGE, WHITE, c01, lerp, e_out, e_in, e_io, e_expo, e_back,
                       layer, put, fade, mblur, glow, edge_vignette, text_layer, text_width)

FPS = 30
DUR = 13.4
room.LOOP = DUR
HERE = os.path.dirname(os.path.abspath(__file__))
OVERLAY = ["I asked AI to animate hockey", "WAIT FOR THE GOAL LIGHT"]
PROMPT = "Show me what AI can do with hockey"
PLACEHOLDER = "Hey, can you help....."
BG = (38, 35, 52)
FROST = (224, 229, 235)
ICEFIELD = (238, 243, 247)
KNOB_TOP, KNOB_BOT, KNOB_RIM = (80, 165, 240), (30, 127, 216), (18, 96, 185)
WARMWHITE = (245, 232, 218)
NEARBLACK = (0, 0, 0)
BAR = dict(cx=SW / 2, cy=430, w=1240, h=230)
CHIP = (466, 487)                         # Modell-Chip in Inhaltskoordinaten
PILL = dict(cx=SW / 2, cy=620, w=960, h=120)
LABELS = ["Goalie", "Defense", "Forward"]
WORD_SIZE = 104
SQUASH = 5.0                              # Blickwinkel ~11.5°: Kreise erscheinen 5:1 gestaucht
PUCK_W = 150                              # Puck 3 Zoll
PUCK_T = PUCK_W / 3 * 0.98                # 1 Zoll dick
SPOT_W = PUCK_W * 4                       # Bullypunkt 12 Zoll = 4 x Puck
Y_PUCK0, Y_FLOOR = 0.30 * SH, 0.66 * SH
T_PLAY = 0.35


def bg():
    return fx.bg(BG)


# ================================================================= virtuelle Kamera (x' = x*sc + o)
def cam_apply(im, sc, ox, oy):
    if abs(sc - 1) < 1e-3 and abs(ox) < 0.3 and abs(oy) < 0.3:
        return im
    box = (-ox / sc, -oy / sc, (SW - ox) / sc, (SH - oy) / sc)
    return im.transform((SW, SH), Image.EXTENT, box, Image.BICUBIC)


def pivot_cam(sc, src, dst):
    return (sc, dst[0] - src[0] * sc, dst[1] - src[1] * sc)


def keyed(t, keys):
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0, _), (t1, v1, ez) in zip(keys, keys[1:]):
        if t <= t1:
            p = ez((t - t0) / (t1 - t0))
            return tuple(lerp(a, b, p) for a, b in zip(v0, v1))
    return keys[-1][1]


CHIP_CAM = pivot_cam(1.3, CHIP, (0.40 * SW, 0.42 * SH))      # Leiste bleibt rechts im Bild (Senden sichtbar)
CAM_PROMPT = [
    (1.45, (1.0, 0.0, 0.0), e_io),
    (2.35, pivot_cam(1.08, (SW / 2, SH / 2), (SW / 2 - 30, SH / 2 - 10)), e_io),
    (2.70, CHIP_CAM, e_io),
    (3.50, (CHIP_CAM[0], CHIP_CAM[1] + 20, CHIP_CAM[2] - 8), lambda x: x),
]


def cam_at(t):
    return keyed(t, CAM_PROMPT)


# ================================================================= Prompt-Leiste
def bar_layer(text, ink, t, fill_w=None, fill_h=None, radius=None, fill_col=FROST, fill_a=1.0, content_a=1.0,
              caret=False, shimmer=None, chip="Shot", scale=1.0):
    """Prompt-Leiste: Füllung frei skalierbar (Zoom/Verschluss), Inhalt an der Endposition."""
    cx, cy, w, h = BAR["cx"], BAR["cy"], BAR["w"], BAR["h"]
    fw, fh = fill_w or w, fill_h or h
    rad = h * 0.22 if radius is None else radius
    lay = layer()
    if fill_a > 0.01:
        if fw <= w + 1:
            sh = layer()
            ImageDraw.Draw(sh).rounded_rectangle((cx - fw / 2, cy - fh / 2 + 14, cx + fw / 2, cy + fh / 2 + 14), radius=rad,
                                                 fill=(0, 0, 0, int(100 * fill_a * c01(content_a * 2))))
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
        fc = ifont(600, 30)
        cw = fc.getlength(chip) + 64
        d.rounded_rectangle((CHIP[0] - 48, iy - 24, CHIP[0] - 48 + cw, iy + 24), radius=24, fill=(206, 212, 220, 255))
        d.text((CHIP[0] - 48 + 24, iy), chip, font=fc, fill=(60, 66, 76, 255), anchor="lm")
        vx = CHIP[0] - 48 + cw - 24
        d.polygon([(vx - 8, iy - 4), (vx + 8, iy - 4), (vx, iy + 6)], fill=(60, 66, 76, 255))
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
            mk = layer()
            ImageDraw.Draw(mk).text((x0 + 56, y0 + 66), text, font=f, fill=(255, 255, 255, 255), anchor="lm")
            band.putalpha(ImageChops.multiply(band.getchannel("A"), mk.getchannel("A")))
            c.alpha_composite(band)
        lay.alpha_composite(fade(c, content_a))
    if abs(scale - 1) > 1e-3:
        big = lay.resize((int(SW * scale), int(SH * scale)), Image.BILINEAR)
        lay = layer()
        put(lay, big, cx - cx * scale, cy - cy * scale)
    return lay


def rest_state(glow_a=0.10):
    """Ruhezustand (erstes und letztes Bild): Leiste mit Platzhalter auf dunklem Grund."""
    img = bg()
    fx.blob(img, BAR["cx"], BAR["cy"], 0.45 * SW, 0.27 * SW, (255, 255, 255), glow_a * 0.6)
    img.alpha_composite(bar_layer(PLACEHOLDER, (128, 134, 144), 0.0))
    return img


# Tippen: 34 Zeichen in 0.85 s mit leicht unregelmäßigem Anschlag
_rk = random.Random(5)
_iv = [1 + _rk.uniform(-0.3, 0.3) for _ in PROMPT]
KEY_T = list(np.cumsum(_iv) / sum(_iv) * 0.85 + 1.45 - 0.85 / len(PROMPT))
MENU_TOP = CHIP[1] + 34
MENU_ROWS = ["Wrist shot", "Slap shot", "Snipe"]
MENU_X0 = CHIP[0] - 48
ROW_H = 70


def row_y(i):
    return MENU_TOP + 10 + ROW_H * (i + 0.5)


def menu_layer(t):
    if t < 2.75 or t >= 3.40:
        return None
    p = e_expo((t - 2.75) / 0.13)
    close = c01((t - 3.28) / 0.1)
    lay = layer()
    d = ImageDraw.Draw(lay)
    w = 380
    h = ROW_H * 3 + 20
    sc = lerp(0.85, 1.0, p) * lerp(1.0, 0.92, close)
    a = p * (1 - close)
    x0 = MENU_X0
    d.rounded_rectangle((x0, MENU_TOP, x0 + w * sc, MENU_TOP + h * sc), radius=18, fill=(214, 220, 228, int(245 * a)))
    hover = 0 if 2.90 <= t < 3.00 else 1 if 3.00 <= t < 3.12 else 2 if t >= 3.12 else None
    f = ifont(500, 34)
    fb = ifont(650, 30)
    for i, label in enumerate(MENU_ROWS):
        ry = MENU_TOP + (10 + ROW_H * (i + 0.5)) * sc
        if hover == i:
            col = (186, 194, 205) if (i == 2 and t >= 3.22) else (200, 207, 216)
            d.rounded_rectangle((x0 + 8, ry - ROW_H * sc / 2 + 4, x0 + w * sc - 8, ry + ROW_H * sc / 2 - 4), radius=12, fill=col + (int(255 * a),))
        d.text((x0 + 26, ry), label, font=f, fill=(48, 54, 64, int(255 * a)), anchor="lm")
        if i == 2:
            bw = fb.getlength("top shelf") + 30
            bx = x0 + 40 + f.getlength(label)
            d.rounded_rectangle((bx, ry - 20, bx + bw, ry + 20), radius=20, fill=ORANGE + (int(255 * a),))
            d.text((bx + bw / 2, ry), "top shelf", font=fb, fill=(40, 22, 8, int(255 * a)), anchor="mm")
    return lay


POINTER = [(2.45, (BAR["cx"] + 260, BAR["cy"] + 40)), (2.70, (CHIP[0] - 10, CHIP[1] + 6)), (2.86, (CHIP[0] - 10, CHIP[1] + 6)),
           (2.92, (MENU_X0 + 70, row_y(0))), (3.02, (MENU_X0 + 70, row_y(1))), (3.14, (MENU_X0 + 70, row_y(2))),
           (3.40, (MENU_X0 + 70, row_y(2)))]


def pointer_pos(t):
    for (t0, a), (t1, b) in zip(POINTER, POINTER[1:]):
        if t <= t1:
            p = e_io((t - t0) / (t1 - t0))
            return lerp(a[0], b[0], p), lerp(a[1], b[1], p)
    return POINTER[-1][1]


def prompt_scene(t):
    """Leiste mit Tippen, Menü und Zeiger in Inhaltskoordinaten (1.45–3.77)."""
    if t < KEY_T[0]:
        txt, ink = PLACEHOLDER, (128, 134, 144)
    else:
        n = sum(1 for k in KEY_T if k <= t)
        txt, ink = PROMPT[:n], (30, 32, 38)
    shimmer = c01((t - 2.35) / 0.15) if 2.35 <= t < 2.5 else None
    chip = "Snipe" if t >= 3.22 else "Shot"
    lay = bar_layer(txt, ink, t, caret=t >= KEY_T[0], shimmer=shimmer, chip=chip)
    mn = menu_layer(t)
    if mn:
        lay.alpha_composite(mn)
    if 2.45 <= t < 3.45:
        x, y = pointer_pos(t)
        dip = any(0 <= t - c < 0.07 for c in (2.75, 3.22))
        cl = layer()
        draw_cursor(cl, x, y, 1.6 * (0.92 if dip else 1.0))
        lay.alpha_composite(fade(cl, c01((t - 2.45) / 0.06) * (1 - c01((t - 3.32) / 0.1))))
    return lay


# ================================================================= Eisfläche (Hook)
_ICE = None


def ice_sheet():
    """Mittelzone von oben: rote Mittellinie, blauer Bullypunkt und Mittelkreis, Kufen-Kratzer (maßstabsgetreu)."""
    global _ICE
    if _ICE is None:
        img = Image.new("RGBA", (SW, SH), ICEFIELD + (255,))
        lay = layer()
        d = ImageDraw.Draw(lay)
        rng = random.Random(11)
        for _ in range(34):
            cx, cy = rng.uniform(-300, SW + 300), rng.uniform(-300, SH + 300)
            r = rng.uniform(300, 1100)
            a0 = rng.uniform(0, 360)
            d.arc((cx - r, cy - r, cx + r, cy + r), a0, a0 + rng.uniform(15, 50), fill=(150, 165, 180, rng.randint(20, 32)),
                  width=rng.choice((1, 2, 2, 3)))
        R = 0.34 * SH                         # Mittelkreis: 15 Fuß Radius
        line_w = R * 12 / 180                 # Mittellinie 12 Zoll
        spot_r = R * 6 / 180                  # Bullypunkt 12 Zoll Durchmesser
        cx, cy = SW / 2, SH / 2
        d.rectangle((cx - line_w / 2, 0, cx + line_w / 2, SH), fill=(215, 40, 55, 92))
        d.ellipse((cx - R, cy - R, cx + R, cy + R), outline=(35, 110, 235, 92), width=max(2, int(R * 2 / 180)))
        d.ellipse((cx - spot_r, cy - spot_r, cx + spot_r, cy + spot_r), fill=(35, 110, 235, 110))
        img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(0.6)))
        arr = np.asarray(img).astype(np.float32)
        arr[..., :3] *= (1 - 0.04 * fx._YY[..., None] / SH)
        _ICE = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    return _ICE


# ================================================================= Segment-Schalter
def pill_geom(sc, ox, oy):
    return PILL["cx"] * sc + ox, PILL["cy"] * sc + oy, PILL["w"] * sc, PILL["h"] * sc


def pill_layer(sc=1.0, ox=0.0, oy=0.0, blue=0.0, knob_pos=1.0, track_a=1.0):
    cx, cy, w, h = pill_geom(sc, ox, oy)
    lay = layer()
    x0, y0 = cx - w / 2, cy - h / 2
    seg = w / 3
    if track_a <= 0.01:
        return lay
    tl = layer()
    td = ImageDraw.Draw(tl)
    td.rounded_rectangle((x0, y0, x0 + w, y0 + h), radius=h / 2, fill=(62, 64, 74, 235))
    td.line((x0 + h / 2, y0 + 1, x0 + w - h / 2, y0 + 1), fill=(255, 255, 255, 40), width=max(1, int(sc)))
    if blue > 0:
        kx = x0 + seg * (knob_pos + 0.5)
        grad = layer()
        gd = ImageDraw.Draw(grad)
        fw = 0.45 * w
        steps = 48
        for k in range(steps):
            u = k / steps
            xa = kx - fw * (1 - u)
            col = tuple(int(lerp(a, b, u)) for a, b in zip((62, 64, 74), (24, 90, 190)))
            gd.rectangle((xa, y0, xa + fw / steps + 2, y0 + h), fill=col + (int(255 * blue),))
        gd.rectangle((kx, y0, x0 + w, y0 + h), fill=(24, 90, 190, int(255 * blue)))
        mk = Image.new("L", (SW, SH), 0)
        ImageDraw.Draw(mk).rounded_rectangle((x0, y0, x0 + w, y0 + h), radius=h / 2, fill=255)
        grad.putalpha(ImageChops.multiply(grad.getchannel("A"), mk))
        tl.alpha_composite(grad)
    f = ifont(600, max(6, int(h * 0.3)))
    d = ImageDraw.Draw(tl)
    for i, lb in enumerate(LABELS):
        d.text((x0 + seg * (i + 0.5), cy), lb, font=f, fill=(240, 242, 245, 220), anchor="mm")
    lay.alpha_composite(fade(tl, track_a))
    return lay


def knob_layer(knob_pos, sc, ox, oy, slide, shrink=1.0, dx=0.0, alpha=1.0):
    cx, cy, w, h = pill_geom(sc, ox, oy)
    seg = w / 3
    kx = cx - w / 2 + seg * (knob_pos + 0.5) + dx
    kw, kh = (seg - 16 * sc) * shrink, (h - 16 * sc) * shrink
    blue = c01((slide - 0.25) / 0.6)
    lay = layer()
    k = layer()
    kd = ImageDraw.Draw(k)
    top_c = tuple(int(lerp(a, b, blue)) for a, b in zip((236, 238, 242), KNOB_TOP))
    bot_c = tuple(int(lerp(a, b, blue)) for a, b in zip((218, 221, 226), KNOB_BOT))
    steps = 24
    for i in range(steps):
        u = i / steps
        col = tuple(int(lerp(a, b, u)) for a, b in zip(top_c, bot_c))
        kd.rectangle((kx - kw / 2, cy - kh / 2 + kh * u, kx + kw / 2, cy - kh / 2 + kh * (u + 1 / steps) + 1), fill=col + (255,))
    mk = Image.new("L", (SW, SH), 0)
    ImageDraw.Draw(mk).rounded_rectangle((kx - kw / 2, cy - kh / 2, kx + kw / 2, cy + kh / 2), radius=kh / 2, fill=255)
    k.putalpha(ImageChops.multiply(k.getchannel("A"), mk))
    if blue > 0.05:
        kd = ImageDraw.Draw(k)
        kd.rounded_rectangle((kx - kw / 2, cy - kh / 2, kx + kw / 2, cy + kh / 2), radius=kh / 2,
                             outline=KNOB_RIM + (int(255 * blue),), width=max(1, int(2 * sc)))
        kd.line((kx - kw / 2 + kh / 2, cy - kh / 2 + 2 * sc, kx + kw / 2 - kh / 2, cy - kh / 2 + 2 * sc),
                fill=(150, 210, 255, int(200 * blue)), width=max(1, int(2 * sc)))
    halo = layer()
    ImageDraw.Draw(halo).rounded_rectangle((kx - kw / 2, cy - kh / 2, kx + kw / 2, cy + kh / 2), radius=kh / 2,
                                           fill=tuple(int(lerp(a, b, blue)) for a, b in zip((255, 255, 255), ICE)) + (255,))
    glow(lay, halo, 24 * max(1.0, sc / 2), 0.35 + 0.2 * blue, keep=False)
    lay.alpha_composite(k)
    f = ifont(int(lerp(600, 700, blue)), max(6, int(h * 0.3 * shrink)))
    d = ImageDraw.Draw(lay)
    a_old = 1 - c01((slide - 0.2) / 0.2)
    a_new = c01((slide - 0.45) / 0.2)
    if a_old > 0.01:
        d.text((kx, cy), "Defense", font=f, fill=(40, 44, 52, int(255 * a_old)), anchor="mm")
    if a_new > 0.01:
        d.text((kx, cy), "Forward", font=f, fill=(255, 255, 255, int(255 * a_new)), anchor="mm")
    return fade(lay, alpha)


PUNCH_SC = 2.2
PIVOT = (PILL["cx"] + PILL["w"] / 6, PILL["cy"])             # zwischen Defense und Forward


def pill_scene(t):
    """3.50–5.30: Schalter steigt auf, Punch-in, Knopf gleitet zu Forward, Kamerafahrt, Ausflug nach links."""
    if t < 3.77:
        q = e_io((t - 3.50) / 0.27)
        oy = lerp(1.30 * SH - PILL["cy"], 0, q)
        lay = pill_layer(oy=oy)
        lay.alpha_composite(knob_layer(1, 1.0, 0, oy, 0.0))
        return lay
    if t < 4.25:
        tt_ = t - 3.77
        oy = -0.012 * SH * math.exp(-tt_ * 9) * math.sin(tt_ * 24)
        lay = pill_layer(oy=oy)
        lay.alpha_composite(knob_layer(1, 1.0, 0, oy, 0.0))
        return lay
    q = e_in(c01((t - 4.25) / 0.07), 2)
    tgt = pivot_cam(PUNCH_SC, PIVOT, (0.50 * SW, 0.50 * SH))
    sc, ox, oy = (lerp(a, b, q) for a, b in zip((1.0, 0.0, 0.0), tgt))
    slide = c01((t - 4.32) / 0.30)
    sp = e_io(slide)
    knob = 1 + sp
    ox -= 0.5 * sp * (PILL["w"] / 3) * sc                       # Kamera folgt dem Knopf zur Hälfte
    if t >= 4.62:                                               # Kamerafahrt: Inhalt wandert nach links
        ox -= 0.18 * SW * c01((t - 4.62) / 0.5)
    exit_p = c01((t - 5.10) / 0.12)
    lay = pill_layer(sc, ox, oy, blue=c01((slide - 0.25) / 0.6), knob_pos=knob, track_a=1 - exit_p)
    shrink = lerp(1.0, 0.55, e_in(exit_p, 2))
    dx = -1.5 * SW * e_in(c01((t - 5.17) / 0.13), 2)
    lay.alpha_composite(knob_layer(knob, sc, ox, oy, slide, shrink=shrink, dx=dx))
    return lay


# ================================================================= Kufen-Spuren, Wort, Puck
WORD_Y = 0.475 * SH
SKATE_W = text_width("Skate", WORD_SIZE, 650)
WORD_X0 = SW / 2 - SKATE_W / 2
_RIB = None


def ribbon_paths():
    global _RIB
    if _RIB is None:
        out = []
        for dx, y in ((0.0, 0.415 * SH), (0.03 * SW, 0.535 * SH)):
            a = fx.bezier((1.05 * SW + dx, -0.05 * SH), (0.92 * SW + dx, 0.12 * SH), (0.86 * SW + dx, y - 0.08 * SH), (0.72 * SW + dx, y), 140)
            line = np.stack([np.linspace(0.72 * SW + dx, WORD_X0 - 26, 140), np.full(140, y)], 1)
            out.append(np.concatenate([a, line[1:]]))
        _RIB = out
    return _RIB


def head_point(P, head):
    seg = np.diff(P, axis=0)
    L = np.concatenate([[0], np.cumsum(np.hypot(seg[:, 0], seg[:, 1]))])
    L /= L[-1]
    return P[min(len(P) - 1, int(np.searchsorted(L, head)))]


def rib_head(t, k):
    return e_out(c01((t - 5.15 - k * 0.05) / 0.45), 4)


def rib_tail(t, k):
    lead = e_out(c01((t - 5.27 - k * 0.05) / 0.45), 4)
    return min(rib_head(t, k), lead + 0.6 * c01((t - 5.62) / 0.30))


def ribbons(base, t):
    for k, P in enumerate(ribbon_paths()):
        h, tl = rib_head(t, k), rib_tail(t, k)
        if h > tl + 0.002:
            fx.ribbon(base, P, h, tl, col=ORANGE, hot=(255, 224, 190), width=12, double=18, glow_r=26)
        if k == 0 and 0 < h < 0.97:
            hx, hy = head_point(P, h)
            fx.blob(base, hx, hy, 30, 30, (255, 255, 255), 0.75)


def word(txt, x, y, a=1.0, size=WORD_SIZE, col=WHITE):
    return text_layer(txt, size, 650, col, 0, cx=x, cy=y, alpha=a)


def squeeze(lay, sx, sy, cx, cy):
    big = lay.resize((max(1, int(SW * sx)), max(1, int(SH * sy))), Image.BILINEAR)
    out = layer()
    put(out, big, cx - cx * sx, cy - cy * sy)
    return out


def puck_layer(x, y, sx=1.0, sy=1.0, a=1.0):
    """Puck in 3/4-Ansicht (gleicher Blickwinkel wie der Bullypunkt); y = Mitte der Unterseite."""
    w = PUCK_W * sx
    tk = PUCK_T * sy
    eh = w / SQUASH / 2
    lay = layer()
    halo = layer()
    ImageDraw.Draw(halo).ellipse((x - w * 0.9, y - tk - eh * 3, x + w * 0.9, y + eh * 2), fill=(255, 255, 255, 255))
    glow(lay, halo, 40, 0.25, keep=False)
    d = ImageDraw.Draw(lay)
    d.ellipse((x - w / 2, y - eh, x + w / 2, y + eh), fill=(16, 16, 19, 255))
    d.rectangle((x - w / 2, y - tk, x + w / 2, y), fill=(16, 16, 19, 255))
    d.ellipse((x - w / 2, y - tk - eh, x + w / 2, y - tk + eh), fill=(32, 32, 37, 255))
    d.ellipse((x - w / 2, y - tk - eh, x + w / 2, y - tk + eh), outline=(184, 194, 208, 230), width=3)
    d.line((x - w / 2 + 1, y - tk, x - w / 2 + 1, y), fill=(120, 130, 145, 200), width=2)
    d.line((x + w / 2 - 1, y - tk, x + w / 2 - 1, y), fill=(120, 130, 145, 200), width=2)
    d.ellipse((x - w * 0.22, y - tk - eh * 0.7, x - w * 0.02, y - tk - eh * 0.1), fill=(230, 236, 245, 120))
    return fade(lay, a)


def floor_layer(p_in, p_out=0.0):
    """Mittellinie (12 Zoll, rot) mit Bullypunkt (12 Zoll, blau) im gleichen Blickwinkel wie der Puck."""
    sx = e_out(p_in, 3) * (1 - e_in(p_out, 2))
    if sx <= 0.01:
        return None
    lay = layer()
    d = ImageDraw.Draw(lay)
    cx, cy = SW / 2, Y_FLOOR
    band_h = SPOT_W / SQUASH
    lw = 0.62 * SW * sx
    steps = 50
    for k in range(steps):
        u = k / steps
        a = c01(math.sin(math.pi * u) * 1.6) ** 1.5
        d.rectangle((cx - lw / 2 + lw * u, cy - band_h / 2, cx - lw / 2 + lw * (u + 1 / steps) + 1, cy + band_h / 2),
                    fill=(205, 38, 52, int(235 * a)))
    sw_, sh_ = SPOT_W * sx, band_h * sx
    spot = layer()
    ImageDraw.Draw(spot).ellipse((cx - sw_ / 2, cy - sh_ / 2, cx + sw_ / 2, cy + sh_ / 2), fill=(35, 110, 235, 255))
    glow(lay, spot, 22, 0.35)
    return lay


def spotlight(base, a):
    if a > 0.01:
        fx.blob(base, SW / 2, Y_FLOOR - 120, 0.30 * SW, 0.32 * SH, (205, 215, 235), 0.22 * a)


def speed_lines(base, y, a):
    d = ImageDraw.Draw(base)
    for dx, ln in ((-34, 60), (0, 90), (34, 50)):
        d.line((SW / 2 + dx, y - PUCK_T - 30 - ln, SW / 2 + dx, y - PUCK_T - 30), fill=(230, 238, 250, int(80 * a)), width=3)


def spray(base, t):
    tt_ = t - 7.50
    if tt_ < 0 or tt_ > 0.45:
        return
    rng = random.Random(8)
    d = ImageDraw.Draw(base)
    for _ in range(46):
        side = rng.choice((-1, 1))
        vx = side * rng.uniform(300, 520)
        vy = -rng.uniform(140, 260)
        r = rng.uniform(2.5, 6)
        col = (240, 248, 255) if rng.random() < 0.6 else ICE
        x = SW / 2 + side * PUCK_W * 0.45 + vx * tt_
        y = Y_FLOOR + vy * tt_ + 0.5 * 1300 * tt_ * tt_
        a = c01(1 - tt_ / 0.4)
        d.ellipse((x - r, y - r, x + r, y + r), fill=col + (int(255 * a),))


def shoot_letters(t, y):
    txt = "Shoot"
    f = ifont(650, WORD_SIZE)
    widths = [f.getlength(ch) for ch in txt]
    x = SW / 2 - sum(widths) / 2
    lay = layer()
    d = ImageDraw.Draw(lay)
    for i, ch in enumerate(txt):
        cx = x + widths[i] / 2
        x += widths[i]
        tau = t - 7.55 - 0.03 * i
        if tau < 0:
            continue
        p = e_back(tau / 0.27, 1.7)
        d.text((cx, y - 46 * (1 - p)), ch, font=f, fill=WHITE + (int(255 * c01(tau / 0.06)),), anchor="mm")
    return lay


def band_mask(lay, y0, y1, soft=10):
    mk = Image.new("L", (SW, SH), 0)
    ImageDraw.Draw(mk).rectangle((0, y0, SW, y1), fill=255)
    mk = mk.filter(ImageFilter.GaussianBlur(soft))
    lay.putalpha(ImageChops.multiply(lay.getchannel("A"), mk))
    return lay


# ================================================================= Torlampe, Burst, CTA
LAMP_R = 182
LAMP_S = 2.08


def lamp_icon(d, cx, cy, s, col, lit=0.0):
    w, h = 54 * s, 42 * s
    by = cy + 22 * s
    dome = (cx - w / 2, by - h, cx + w / 2, by + h)
    if lit > 0:
        fill = tuple(int(lerp(a, b, lit)) for a, b in zip(BG, (240, 40, 36)))
        d.pieslice(dome, 180, 360, fill=fill + (255,))
        d.ellipse((cx - w * 0.18, by - h * 0.75, cx + w * 0.05, by - h * 0.45), fill=(255, 160, 120, int(255 * lit)))
    d.arc(dome, 180, 360, fill=col, width=max(2, int(4 * s)))
    d.rounded_rectangle((cx - w / 2 - 6 * s, by, cx + w / 2 + 6 * s, by + 12 * s), radius=4 * s, fill=col)
    ray = col if lit < 0.5 else ORANGE + (255,)
    for ang in (-45, 0, 45):
        a = math.radians(ang - 90)
        r0, r1 = h + 12 * s, h + 28 * s
        d.line((cx + math.cos(a) * r0, by + math.sin(a) * r0, cx + math.cos(a) * r1, by + math.sin(a) * r1), fill=ray, width=max(2, int(4 * s)))


def lamp_layer(cx, cy, ring_p, lit=0.0, alpha=1.0, ring_glow=0.0):
    lay = layer()
    if lit > 0:
        g = layer()
        ImageDraw.Draw(g).ellipse((cx - 110, cy - 70, cx + 110, cy + 90), fill=(255, 80, 50, 255))
        glow(lay, g, 50, 0.7 * lit, keep=False)
    if ring_p > 0:
        rl = layer()
        ImageDraw.Draw(rl).arc((cx - LAMP_R, cy - LAMP_R, cx + LAMP_R, cy + LAMP_R), -90, -90 + 360 * c01(ring_p), fill=WHITE + (255,), width=6)
        if ring_glow > 0:
            glow(lay, rl, 34, ring_glow)
        else:
            lay.alpha_composite(rl)
    lamp_icon(ImageDraw.Draw(lay), cx, cy, LAMP_S, WHITE + (255,), lit)
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
    lay[..., :3] = (255, 170, 90)
    lay[..., 3] = m_ * 0.28 * alpha * 255
    base.alpha_composite(Image.fromarray(lay.astype(np.uint8), "RGBA").filter(ImageFilter.GaussianBlur(6)))


def black_puck(d, x, y, s, a=1.0):
    w, tk = 70 * s, 70 * s / 3
    eh = w / SQUASH / 2 * 1.6
    al = int(255 * a)
    d.ellipse((x - w / 2 + 4, y + 6 - eh, x + w / 2 + 4, y + 6 + eh), fill=(0, 0, 0, int(90 * a)))
    d.ellipse((x - w / 2, y - eh, x + w / 2, y + eh), fill=(18, 18, 22, al))
    d.rectangle((x - w / 2, y - tk, x + w / 2, y), fill=(18, 18, 22, al))
    d.ellipse((x - w / 2, y - tk - eh, x + w / 2, y - tk + eh), fill=(40, 40, 46, al))
    d.ellipse((x - w / 2, y - tk - eh, x + w / 2, y - tk + eh), outline=(200, 205, 214, al), width=2)


PUCK_ANGLES = [18, 64, 118, 160, 205, 252, 318]
CTA = "COMMENT YOUR POSITION"
CTA_SIZE = 56
CTA_W = text_width(CTA, CTA_SIZE, 650, 3)
LOCK_X = SW / 2 - (2 * LAMP_R + 56 + CTA_W) / 2 + LAMP_R
LABEL_X = LOCK_X + LAMP_R + 56


def burst_bg(t):
    q = c01((t - 9.45) / 0.10)
    out = 1 - c01((t - 10.20) / 0.25)
    diag = (fx._XX / SW + fx._YY / SH) / 2
    edge = np.clip((q * 1.6 - diag) / 0.3, 0, 1) * out
    tl = np.array([240, 40, 34], np.float32)
    mid = np.array([150, 28, 36], np.float32)
    br = np.array([70, 18, 26], np.float32)
    g = np.clip(diag[..., None] * 2, 0, 2)
    col = np.where(diag[..., None] < 0.5, tl + (mid - tl) * g, mid + (br - mid) * np.clip(g - 1, 0, 1))
    strobe = 1 + 0.35 * math.exp(-max(0.0, t - 9.45) * 18) + (0.3 * math.exp(-(t - 9.80) * 18) if t >= 9.80 else 0)
    arr = np.dstack([np.clip(col * strobe, 0, 255), edge * 255])
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


# ================================================================= Wortmarke
MARK = "@bladesandpucks"
MARK_SIZE = 84
T_MARK = 11.45


def wordmark(t, scale_extra=1.0, alpha=1.0):
    lay = layer()
    tt_ = t - T_MARK
    if tt_ < 0:
        return lay
    f = ifont(650, MARK_SIZE)
    widths = [f.getlength(ch) for ch in MARK]
    total = sum(widths)
    sc = lerp(1.3, 1.0, e_out(c01(tt_ / 0.8), 3)) * (1 + 0.03 * c01((tt_ - 0.8) / 0.5)) * scale_extra
    inner = layer()
    x = SW / 2 - total / 2
    for i, ch in enumerate(MARK):
        cx = x + widths[i] / 2
        x += widths[i]
        tau = tt_ - 0.04 * i
        if tau < 0:
            continue
        for ghost, ga in ((0.066, 0.12), (0.033, 0.22), (0.0, 1.0)):
            u = c01((tau - ghost) / 0.22)
            if u <= 0:
                continue
            if ghost > 0 and u >= 1:
                continue
            yy = SH / 2 - 0.10 * SH * (1 - e_back(u, 0.5))
            rot = -25 * (1 - e_out(u, 3))
            cool = c01((tau - ghost - 0.22) / 0.25)
            col = tuple(int(lerp(a, b, cool)) for a, b in zip(ORANGE, WARMWHITE))
            gl = Image.new("RGBA", (int(widths[i]) + 60, MARK_SIZE + 60), (0, 0, 0, 0))
            ImageDraw.Draw(gl).text((gl.width / 2, gl.height / 2), ch, font=f, fill=col + (int(255 * ga),), anchor="mm")
            if abs(rot) > 0.5:
                gl = gl.rotate(rot, resample=Image.BICUBIC)
            put(inner, gl, cx - gl.width / 2, yy - gl.height / 2)
    out = squeeze(inner, sc, sc, SW / 2, SH / 2) if abs(sc - 1) > 0.002 else inner
    return fade(out, alpha)


# ================================================================= Bildschirminhalt
def hud_alpha(t):
    return c01(t / 0.12) * (1 - c01((t - 3.10) / 0.2))


def os_cursor(t):
    p = e_io(c01((t - 0.02) / 0.30))
    x = lerp(0.62 * SW, SW / 2 + 4, p)
    y = lerp(0.74 * SH, SH - 167, p)
    return x, y, c01(t / 0.05) * (1 - c01((t - 0.90) / 0.2))


def chrome(img, t):
    a = hud_alpha(t)
    if a > 0.01:
        draw_hud(img, max(0.0, t - T_PLAY), 13, a, playing=t >= T_PLAY, cy=SH - 150)
    x, y, ca = os_cursor(t)
    if ca > 0.02:
        cl = layer()
        draw_cursor(cl, x, y, 1.9 * (0.92 if 0 <= t - T_PLAY < 0.07 else 1.0))
        img.alpha_composite(fade(cl, ca))


def content(t):
    # ---- Ruhebild, Klick auf Play, blaue Ränder, Zoom-Explosion
    if t < 0.60:
        if t < T_PLAY:
            return rest_state()
        img = bg()
        v = e_out(c01((t - T_PLAY) / 0.15), 2)
        fx.blob(img, BAR["cx"], BAR["cy"], lerp(0.45, 0.6, v) * SW, lerp(0.27, 0.36, v) * SW, (255, 255, 255), lerp(0.10, 0.35, v) * 0.6)
        edge_vignette(img, (30, 120, 240), 0.85 * v)
        if t < 0.52:
            img.alpha_composite(bar_layer(PLACEHOLDER, (128, 134, 144), t, shimmer=c01((t - 0.36) / 0.16)))
        else:
            q = c01((t - 0.52) / 0.08)
            s_ = math.exp(math.log(12) * q ** 1.6)
            img.alpha_composite(bar_layer(PLACEHOLDER, (128, 134, 144), t, fill_w=BAR["w"] * s_, fill_h=BAR["h"] * s_,
                                          radius=BAR["h"] * 0.22 * s_, content_a=1 - c01(q * 2)))
        return img
    # ---- Eisfläche mit Mittelzone (Hockey sofort sichtbar)
    if t < 1.15:
        ice = ice_sheet()
        q = c01((t - 0.60) / 0.06)
        base = Image.new("RGBA", (SW, SH), FROST + (255,))
        out = Image.blend(base, ice, q)
        z = 1.0 + 0.04 * c01((t - 0.60) / 0.55)
        return cam_apply(out, *pivot_cam(z, (SW / 2, SH / 2), (SW / 2, SH / 2)))
    # ---- Verschluss zurück zur Leiste, Tippen, Menü, Whip
    if t < 3.77:
        img = bg()
        if t < 1.75:
            vg = 1 - c01((t - 1.45) / 0.3)
            fx.blob(img, BAR["cx"], BAR["cy"], 0.6 * SW, 0.36 * SW, (255, 255, 255), 0.3 * vg * 0.6)
            edge_vignette(img, (30, 120, 240), 0.8 * vg)
        if t >= 3.22:
            gy = lerp(1.45, 1.30, e_out(c01((t - 3.22) / 0.28), 3)) * SH
            ry = 0.60 * SH
            if t > 3.50:
                w_ = e_io((t - 3.50) / 0.27)
                gy, ry = lerp(1.30, 1.18, w_) * SH, lerp(0.60, 0.30, w_) * SH
            fx.blob(img, SW / 2, gy, 0.95 * SW, ry, (30, 120, 255), 0.85 * c01((t - 3.22) / 0.28))
        if t < 1.28:
            q = e_in(c01((t - 1.15) / 0.13), 3)
            top, bot = lerp(0, BAR["cy"] - BAR["h"] / 2, q), lerp(SH, BAR["cy"] + BAR["h"] / 2, q)
            ice = ice_sheet().crop((0, int(top), SW, int(bot)))
            lay = layer()
            lay.alpha_composite(ice.resize((SW, max(1, int(bot - top)))), (0, int(top)))
            img.alpha_composite(mblur(lay, 0, 30 * (1 - q) + 10))
            return img
        if t < 1.45:
            q = e_expo(c01((t - 1.28) / 0.17))
            w_ = lerp(SW, BAR["w"], q)
            col = tuple(int(lerp(a, b, q)) for a, b in zip(ICEFIELD, FROST))
            ca = c01((t - 1.33) / 0.08)
            img.alpha_composite(bar_layer(PLACEHOLDER, (128, 134, 144), t, fill_w=w_, radius=BAR["h"] * 0.22 * q, fill_col=col,
                                          content_a=ca, shimmer=c01((t - 1.30) / 0.15)))
            return img
        lay = cam_apply(prompt_scene(t), *cam_at(t))
        if t >= 3.50:
            q = e_io((t - 3.50) / 0.27)
            moved = layer()
            put(moved, lay, 0, -1.30 * SH * q)
            img.alpha_composite(moved)
            img.alpha_composite(pill_scene(t))
            return img
        img.alpha_composite(lay)
        return img
    # ---- Schalter
    if t < 5.32:
        img = bg()
        if t < 4.17:
            fx.blob(img, SW / 2, 1.18 * SH, 0.95 * SW, 0.30 * SH, (30, 120, 255), 0.85 * (1 - c01((t - 3.77) / 0.4)))
        if t >= 5.15:
            ribbons(img, t)
        img.alpha_composite(pill_scene(t))
        return img
    img = bg()
    # ---- Kufen-Spuren liefern "Skate", Lichtfleck verwischt es zum Puck
    if t < 6.45:
        if t < 6.0:
            ribbons(img, t)
        x, y = SW / 2, WORD_Y
        wl = word("Skate", x, y)
        hx = head_point(ribbon_paths()[0], rib_head(t, 0))[0]
        if rib_head(t, 0) < 0.999:                               # Wort erscheint hinter dem Kopf der Spur
            mk = Image.new("L", (SW, SH), 0)
            ImageDraw.Draw(mk).rectangle((hx + 10, 0, SW, SH), fill=255)
            mk = mk.filter(ImageFilter.GaussianBlur(8))
            wl.putalpha(ImageChops.multiply(wl.getchannel("A"), mk))
        if t >= 6.05:
            bxp = lerp(1.35, -0.35, (t - 6.05) / 0.4) * SW
            fx.blob(img, bxp, y, 0.42 * SW, 0.36 * SW, ICE, 0.75)
            over = max(0.0, 1 - abs(bxp - x) / (0.3 * SW))
            if over > 0:
                glow(img, wl, 20, 0.6 * over, keep=False)
        if t >= 6.22:
            k = c01((t - 6.22) / 0.2)
            wl = mblur(wl, -70 * k, 0)
            wl = squeeze(wl, lerp(1, 0.15, e_in(k, 2)), lerp(1, 0.5, k), x, y)
            wl = fade(wl, 1 - e_in(k, 2))
            by = lerp(y, Y_PUCK0 - PUCK_T / 2, e_io(c01((t - 6.30) / 0.15)))
            fx.blob(img, x, by, 40 + 20 * k, 40 + 20 * k, (255, 255, 255), 0.85 * k)
        img.alpha_composite(wl)
        return img
    # ---- Puck formt sich, schwebt, fällt, liegt maßstabsgetreu auf dem Bullypunkt
    if t < 7.50:
        spotlight(img, c01((t - 6.44) / 0.15))
        fl = floor_layer(c01((t - 6.44) / 0.10))
        if fl:
            img.alpha_composite(fl)
        if t < 6.55:
            q = c01((t - 6.45) / 0.10)
            fx.blob(img, SW / 2, Y_PUCK0 - PUCK_T / 2, 60, 60, (255, 255, 255), 0.85 * (1 - q))
            img.alpha_composite(puck_layer(SW / 2, Y_PUCK0, a=q))
            return img
        if t < 6.80:
            bob = -6 * math.sin(math.pi * c01((t - 6.55) / 0.25))
            img.alpha_composite(puck_layer(SW / 2, Y_PUCK0 + bob))
            return img
        if t < 7.10:
            tau = c01((t - 6.80) / 0.30)
            y = lerp(Y_PUCK0, Y_FLOOR, tau * tau)
            speed_lines(img, y, tau)
            img.alpha_composite(puck_layer(SW / 2, y, sx=1 - 0.05 * tau * tau, sy=1 + 0.12 * tau * tau))
            return img
        tau = t - 7.10
        sq = math.exp(-tau * 22) * math.cos(tau * 45) if tau < 0.12 else 0.0
        img.alpha_composite(puck_layer(SW / 2, Y_FLOOR, sx=1 + 0.08 * sq, sy=1 - 0.20 * sq))
        return img
    # ---- Spray, "Shoot" -> "Score"
    if t < 8.97:
        y_w = WORD_Y
        gl_a = c01((t - 7.50) / 0.15) * (1 - c01((t - 8.52) / 0.35))
        fx.blob(img, SW / 2, y_w, 0.31 * SW, 0.22 * SH, (55, 90, 220), 0.7 * gl_a)
        spotlight(img, 1 - c01((t - 7.55) / 0.25))
        fl = floor_layer(1.0, c01((t - 7.58) / 0.22))
        if fl:
            img.alpha_composite(fl)
        spray(img, t)
        if t < 7.72:
            img.alpha_composite(puck_layer(SW / 2, Y_FLOOR, a=1 - c01((t - 7.52) / 0.2)))
        if t < 8.40:
            img.alpha_composite(shoot_letters(t, y_w))
        else:
            q = e_expo((t - 8.40) / 0.12)
            a = band_mask(word("Shoot", SW / 2, y_w - 0.06 * SH * q, 1 - q), y_w - 0.075 * SH, y_w + 0.075 * SH)
            b = band_mask(word("Score", SW / 2, y_w + 0.06 * SH * (1 - q), q), y_w - 0.075 * SH, y_w + 0.075 * SH)
            if t >= 8.52:
                tw = text_width("Score", WORD_SIZE, 650)
                fx.blob(img, SW / 2, y_w, tw * 0.8, WORD_SIZE * 1.1, (255, 255, 255), 0.28 * c01((t - 8.52) / 0.1))
            img.alpha_composite(a)
            img.alpha_composite(b)
        return img
    # ---- "Score" verlässt das Bild nach oben, Torlampe steigt auf, Ring zeichnet sich
    if t < 9.45:
        if t < 9.20:
            yy = WORD_Y - 0.03 * SH - 0.62 * SH * e_in(c01((t - 8.97) / 0.23), 3)
            tw = text_width("Score", WORD_SIZE, 650)
            fx.blob(img, SW / 2, yy, tw * 0.8, WORD_SIZE * 1.1, (255, 255, 255), 0.28)
            img.alpha_composite(word("Score", SW / 2, yy))
        if t >= 9.00:
            yy = lerp(1.15 * SH, 0.50 * SH, e_expo((t - 9.00) / 0.20))
            img.alpha_composite(lamp_layer(SW / 2, yy, e_io((t - 9.12) / 0.33)))
        return img
    # ---- Torlicht: Rot, Strobe, Lichtkegel, Pucks fliegen
    if t < 10.30:
        img.alpha_composite(burst_bg(t))
        beams(img, t, 1.0 - c01((t - 10.15) / 0.15))
        d = ImageDraw.Draw(img)
        for k, ang in enumerate(PUCK_ANGLES):
            tau = t - 9.48 - 0.025 * k
            if tau < 0:
                continue
            s_ = e_back(tau / 0.15, 2.0) * 1.3 * lerp(1.0, 0.6, c01((t - 10.10) / 0.2))
            r = lerp(60, 420, e_out(tau / 0.6, 3)) + 30 * tau
            px = SW / 2 + math.cos(math.radians(ang + 20 * tau)) * r * 1.45
            py = SH / 2 + math.sin(math.radians(ang + 20 * tau)) * r
            black_puck(d, px, py, s_, 1 - c01((t - 10.10) / 0.2))
        pulse = 0.8 * c01((t - 9.45) / 0.08) if t < 9.6 else lerp(0.8, 0.4, c01((t - 9.6) / 0.2))
        img.alpha_composite(lamp_layer(SW / 2, SH / 2, 1.0, lit=c01((t - 9.45) / 0.05), ring_glow=pulse))
        return img
    # ---- CTA: Lampe + COMMENT YOUR POSITION
    if t < T_MARK:
        if t < 10.45:
            img.alpha_composite(burst_bg(t))
        if 10.55 <= t:
            bxp = lerp(0.85, 0.15, (t - 10.55) / 0.9) * SW
            for by in (0.43 * SH, 0.57 * SH):
                fx.blob(img, bxp, by, 0.10 * SW, 0.10 * SW, ICE, 0.4)
        lx = lerp(SW / 2, LOCK_X, e_out(c01((t - 10.30) / 0.25), 3))
        img.alpha_composite(lamp_layer(lx, SH / 2, 1.0, lit=lerp(1.0, 0.6, c01((t - 10.30) / 0.4))))
        pa_ = e_expo((t - 10.40) / 0.2)
        img.alpha_composite(text_layer(CTA, CTA_SIZE, 650, (238, 240, 244), 3, cx=LABEL_X + CTA_W / 2 + 0.03 * SW * (1 - pa_),
                                       cy=SH / 2 + 2, alpha=pa_))
        return img
    # ---- Wortmarke, dann zurück in die Prompt-Leiste (Loop)
    if t < 12.75:
        img = Image.new("RGBA", (SW, SH), NEARBLACK + (255,))
        img.alpha_composite(wordmark(t))
        return img
    if t >= 13.25:
        return rest_state()
    q = c01((t - 12.75) / 0.5)
    blk = Image.new("RGBA", (SW, SH), NEARBLACK + (255,))
    bga = e_io(c01((t - 12.80) / 0.30))
    img = Image.blend(blk, bg(), bga)
    fx.blob(img, BAR["cx"], BAR["cy"], 0.45 * SW, 0.27 * SW, (255, 255, 255), 0.06 * bga)
    img.alpha_composite(wordmark(t, scale_extra=lerp(1.0, 0.55, e_in(q, 2)), alpha=1 - e_in(c01(q / 0.6), 2)))
    ba = e_out(c01((t - 12.95) / 0.30), 3)
    if ba > 0:
        bar = bar_layer(PLACEHOLDER, (128, 134, 144), t, scale=lerp(0.94, 1.0, ba))
        img.alpha_composite(fade(bar, ba))
    return img


def screen(t):
    img = content(t)
    chrome(img, t)
    return img


# ================================================================= Rendering
FAST = [(0.50, 0.62, 24), (1.15, 1.45, 12), (3.48, 3.80, 32), (4.23, 4.34, 24), (4.32, 4.64, 24), (5.10, 5.34, 24),
        (5.34, 5.62, 8), (6.20, 6.47, 12), (6.78, 7.14, 16), (7.50, 7.86, 8), (8.38, 8.55, 12), (8.95, 9.24, 24),
        (9.44, 9.56, 8), (10.28, 10.60, 8), (12.75, 13.25, 6)]
OV = None


def render_frame(i):
    global OV
    if OV is None:
        OV = room.overlay_text(OVERLAY)
    t = i / FPS
    n = max([k for a, b, k in FAST if a <= t < b] + [1])
    if n > 1:
        acc = None
        for dt in np.linspace(-1 / 120, 1 / 120, n):
            arr = np.asarray(screen(max(0.0, min(DUR - 1e-3, float(t + dt)))).convert("RGB")).astype(np.float32)
            acc = arr if acc is None else acc + arr
        scr = Image.fromarray(np.clip(acc / n, 0, 255).astype(np.uint8))
    else:
        scr = screen(t).convert("RGB")
    return room.compose(scr, t, OV, seed=i).tobytes()


# ================================================================= Ton
def make_audio(path):
    mx = pa.Mix(DUR, seed=12)
    T = mx.t
    mx.put(mx.room, mx.click(), T_PLAY, 0.9)
    # Soundtrack der Animation (Laptop-Lautsprecher); leiser Grundton läuft über die Loop-Naht
    n = mx.n
    x = np.arange(n) / pa.SR
    pad = np.zeros(n)
    rng = np.random.default_rng(3)
    for f in (330.0, 660.0, 990.0, 1320.0):
        for det in (-0.003, 0.0, 0.003):
            pad += np.sin(2 * np.pi * f * (1 + det) * x + rng.uniform(0, 6.28)) / (1 + (f > 400) * 1.5)
    pad /= 12
    lvl = np.interp(x, [0, T_PLAY, T_PLAY + 0.4, 11.4, 12.9, DUR], [0.06, 0.06, 0.22, 0.22, 0.06, 0.06])
    duck = 1 - 0.5 * np.clip((x - 9.45) / 0.05, 0, 1) * np.clip((10.6 - x) / 0.3, 0, 1)
    mx.lap += pad * lvl * duck
    mx.put(mx.lap, mx.pad([130.8, 261.6], 1.2, vol=0.25, attack=0.3, release=0.6), 3.22)
    mx.put(mx.lap, mx.pad([130.8, 261.6], 1.0, vol=0.2, attack=0.3, release=0.6), 10.55)
    mx.put(mx.lap, mx.whoosh(0.2, 0.3), 0.40)
    mx.put(mx.lap, mx.whoosh(0.16, 0.45), 0.50)
    ice_x = T(0.55)
    mx.put(mx.lap, mx.whoosh(0.55, 0.12) * (0.7 + 0.3 * np.sin(2 * np.pi * 11 * ice_x)), 0.62)
    mx.put(mx.lap, mx.whoosh(0.25, 0.3, rise=False), 1.15)
    for k in KEY_T:
        mx.put(mx.lap, mx.click() * 0.08, k)
    mx.put(mx.lap, mx.pop(1800, 0.08), 2.75)
    mx.put(mx.lap, mx.chime(880.0, vol=0.35), 2.76)
    mx.put(mx.lap, mx.pop(1800, 0.08), 3.22)
    mx.put(mx.lap, mx.whoosh(0.22, 0.45, rise=False), 3.52)
    mx.put(mx.lap, mx.pop(1400, 0.12), 4.25)
    mx.put(mx.lap, mx.whoosh(0.28, 0.15), 4.32)
    mx.put(mx.lap, mx.pop(900, 0.15), 4.62)
    mx.put(mx.lap, mx.chime(1046.5, vol=0.18), 4.66)
    carve = mx.whoosh(0.4, 0.55, rise=False) * (0.7 + 0.3 * np.sign(np.sin(2 * np.pi * 40 * T(0.4))))
    mx.put(mx.lap, carve, 5.15)
    mx.put(mx.lap, mx.pluck(784.0, vol=0.28), 5.62)
    mx.put(mx.lap, mx.whoosh(0.32, 0.28), 6.05)
    mx.put(mx.lap, mx.pop(2000, 0.08), 6.78)
    tk = T(0.07)
    tock = np.sin(2 * np.pi * 180 * tk) * np.exp(-tk * 33) * 0.8 + mx.rng.standard_normal(len(tk)) * np.exp(-tk * 500) * 0.35
    mx.put(mx.lap, tock, 7.10)
    for k in range(16):
        mx.put(mx.lap, mx.click() * 0.22, 7.52 + mx.rng.uniform(0, 0.35))
    for k, f in enumerate((659.3, 784.0, 880.0, 1046.5, 1174.7)):
        mx.put(mx.lap, mx.pluck(f, vol=0.16), 7.62 + 0.03 * k)
    mx.put(mx.lap, mx.chime(784.0, vol=0.3) + mx.chime(1568.0, vol=0.08), 8.42)
    mx.put(mx.lap, mx.whoosh(0.25, 0.28), 8.96)
    mx.put(mx.lap, mx.pop(1600, 0.12), 9.43)
    # Torhupe (synthetisch) + Strobe-Pops
    hx = T(1.15)
    horn = sum(2 * ((hx * f * (1 + 0.002 * np.sin(2 * np.pi * 5 * hx))) % 1) - 1 for f in (110.0, 165.0, 220.0, 221.5)) / 4
    horn = np.convolve(horn, np.ones(12) / 12, mode="same")
    horn *= np.minimum(hx / 0.06, 1) * np.clip((1.15 - hx) / 0.25, 0, 1) * 0.75
    mx.put(mx.lap, horn, 9.45)
    mx.put(mx.lap, mx.thud(0.6), 9.45)
    mx.put(mx.lap, mx.pop(700, 0.3), 9.47)
    mx.put(mx.lap, mx.pop(800, 0.25), 9.80)
    mx.put(mx.lap, mx.whoosh(0.25, 0.2), 10.28)
    mx.put(mx.lap, mx.pop(1500, 0.08), 10.42)
    mx.put(mx.lap, mx.shimmer(0.4, 0.35), 11.10)
    mx.put(mx.lap, mx.thud(0.45), T_MARK)
    for k in range(len(MARK)):
        mx.put(mx.lap, mx.click() * 0.1, T_MARK + 0.04 * k + 0.2)
    mx.put(mx.lap, mx.whoosh(0.4, 0.2, rise=False), 12.78)
    mx.render(path, lap_gain=1.0, room_gain=0.6, target_peak=0.5)


def main():
    os.chdir(HERE)
    make_audio("audio_aimotion.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{room.W}x{room.H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_aimotion.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "22",
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
    Image.frombytes("RGB", (room.W, room.H), render_frame(int(9.6 * FPS))).save("reel12_thumbnail.jpg", quality=92)
    print("fertig: reel12_ai_motion.mp4")


if __name__ == "__main__":
    main()
