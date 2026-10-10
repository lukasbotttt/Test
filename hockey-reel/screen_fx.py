"""Bausteine für minimalistisches Motion Design im Keynote-Stil (Bildschirminhalt, 1600x1000).

Alles arbeitet auf RGBA-Ebenen in Bildschirmauflösung. Farben als Quell-Werte (vor dem
"Abfilmen" durch pov_room.filmed_screen).
"""
import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from pov_room import SCR_W, SCR_H, ifont

SW, SH = SCR_W, SCR_H
CHAR = (22, 20, 26)          # Grundfläche (Anthrazit mit Violettstich)
IVORY = (240, 236, 226)
GREIGE = (232, 226, 214)
INDIGO = (60, 80, 255)
AZURE = (40, 130, 255)
PERI_IN, PERI_RIM, TRACK = (150, 175, 255), (90, 105, 255), (70, 80, 220)
TEAL, TEAL_HOT = (70, 230, 205), (190, 255, 245)
VIOLET = (100, 95, 235)
CYAN = (90, 200, 255)
RED = (255, 52, 64)
ICE = (64, 196, 255)
ORANGE = (255, 146, 60)
WHITE = (246, 246, 250)


# ================================================================= Easing
def c01(x):
    return max(0.0, min(1.0, x))


def lerp(a, b, t):
    return a + (b - a) * t


def e_out(t, p=4):
    return 1 - (1 - c01(t)) ** p


def e_in(t, p=3):
    return c01(t) ** p


def e_io(t):
    t = c01(t)
    return 16 * t ** 5 if t < 0.5 else 1 - (-2 * t + 2) ** 5 / 2


def e_expo(t):
    """Schnell rein, lange auslaufen (90 % nach ~1/3 der Zeit)."""
    t = c01(t)
    return 1.0 if t >= 1 else 1 - 2 ** (-10 * t)


def e_back(t, s=1.4):
    t = c01(t) - 1
    return t * t * ((s + 1) * t + s) + 1


def spring(t, freq=4.5, damp=5.5):
    """Gedämpfte Feder 0 -> 1 mit Überschwingen."""
    if t <= 0:
        return 0.0
    return 1 - math.exp(-damp * t) * math.cos(2 * math.pi * freq * t)


# ================================================================= Ebenen-Helfer
def layer(w=SW, h=SH):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def put(base, im, x, y):
    x, y = int(round(x)), int(round(y))
    sx, sy = max(0, -x), max(0, -y)
    ex, ey = min(im.width, base.width - x), min(im.height, base.height - y)
    if sx < ex and sy < ey:
        base.alpha_composite(im.crop((sx, sy, ex, ey)), (x + sx, y + sy))


def fade(im, a):
    if a >= 0.999:
        return im
    im = im.copy()
    im.putalpha(im.getchannel("A").point(lambda v: int(v * max(0.0, a))))
    return im


def mblur(im, dx, dy):
    """Richtungs-Bewegungsunschärfe (Länge in px)."""
    n = int(min(48, max(abs(dx), abs(dy)) / 3))
    if n < 2:
        return im
    arr = np.asarray(im).astype(np.float32)
    pre = arr.copy()
    pre[..., :3] *= pre[..., 3:4] / 255
    acc = np.zeros_like(pre)
    for k in range(n):
        f = k / (n - 1) - 0.5
        acc += np.roll(np.roll(pre, int(round(dx * f)), axis=1), int(round(dy * f)), axis=0)
    acc /= n
    a = acc[..., 3:4]
    rgb = acc[..., :3] / np.maximum(a / 255, 1e-4)
    return Image.fromarray(np.clip(np.concatenate([rgb, a], -1), 0, 255).astype(np.uint8), "RGBA")


def transform_layer(im, sc=1.0, cx=SW / 2, cy=SH / 2, dx=0.0, dy=0.0):
    """Ebene um (cx, cy) skalieren und verschieben (virtuelle Kamera)."""
    if abs(sc - 1) < 1e-3 and abs(dx) < 0.5 and abs(dy) < 0.5:
        return im
    w2, h2 = im.width / sc, im.height / sc
    x0 = cx - cx / sc - dx / sc
    y0 = cy - cy / sc - dy / sc
    return im.transform(im.size, Image.EXTENT, (x0, y0, x0 + w2, y0 + h2), Image.BILINEAR)


def glow(base, lay, radius=30, strength=1.0, keep=True):
    """Weiches Leuchten (Viertelauflösung, additiv-ähnlich per screen)."""
    w, h = lay.size
    small = lay.resize((w // 4, h // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(float(radius) / 4))
    g = np.asarray(small.resize((w, h), Image.BILINEAR)).astype(np.float32)
    add = g[..., :3] * np.clip(g[..., 3:4] / 255 * strength, 0, 1)
    b = np.asarray(base).astype(np.float32)
    ba = b[..., 3:4] / 255
    pre = b[..., :3] * ba
    pre = 255 - (255 - pre) * (255 - np.clip(add, 0, 255)) / 255
    ga = np.clip(g[..., 3:4] / 255 * strength, 0, 1)
    na = 1 - (1 - ba) * (1 - ga)
    out = np.concatenate([pre / np.maximum(na, 1e-4), na * 255], -1)
    base.paste(Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA"))
    if keep:
        base.alpha_composite(lay)


_YY, _XX = np.mgrid[0:SH, 0:SW].astype(np.float32)


def blob(base, cx, cy, rx, ry, col, alpha=1.0):
    """Großer, sehr weicher Gauß-Lichtfleck (Lichtfigur)."""
    if alpha <= 0.005:
        return
    g = np.exp(-(((_XX - cx) / rx) ** 2 + ((_YY - cy) / ry) ** 2) * 1.6) * alpha
    lay = np.zeros((SH, SW, 4), np.float32)
    lay[..., :3] = col
    lay[..., 3] = np.clip(g, 0, 1) * 255
    base.alpha_composite(Image.fromarray(lay.astype(np.uint8), "RGBA"))


def edge_vignette(base, col, alpha):
    if alpha <= 0.005:
        return
    d = np.minimum(np.minimum(_XX, SW - _XX) / SW, np.minimum(_YY, SH - _YY) / SH * 1.6)
    g = np.exp(-d * 9) * alpha
    lay = np.zeros((SH, SW, 4), np.float32)
    lay[..., :3] = col
    lay[..., 3] = np.clip(g, 0, 1) * 255
    base.alpha_composite(Image.fromarray(lay.astype(np.uint8), "RGBA"))


def bg(col=CHAR):
    """Grundfläche mit sanftem Verlauf (Mitte etwas heller)."""
    r = np.sqrt(((_XX - SW / 2) / SW) ** 2 + ((_YY - SH * 0.45) / SH) ** 2)
    k = (1.12 - 0.3 * np.clip(r, 0, 1))[..., None]
    arr = np.clip(np.array(col, np.float32) * k, 0, 255)
    return Image.fromarray(np.dstack([arr, np.full((SH, SW), 255, np.float32)]).astype(np.uint8), "RGBA")


# ================================================================= Text
def text_layer(txt, size, weight=600, col=WHITE, tracking=0.0, cx=SW / 2, cy=SH / 2, alpha=1.0, per_letter=None):
    """Text Buchstabe für Buchstabe; per_letter(i, n) -> (dx, dy, alpha, scale)."""
    lay = layer()
    d = ImageDraw.Draw(lay)
    f = ifont(weight, size)
    widths = [f.getlength(ch) for ch in txt]
    total = sum(widths) + tracking * (len(txt) - 1)
    x = cx - total / 2
    for i, ch in enumerate(txt):
        dx, dy, a, sc = 0.0, 0.0, alpha, 1.0
        if per_letter:
            dx, dy, a, sc = per_letter(i, len(txt))
            a *= alpha
        if a > 0.01 and ch != " ":
            if abs(sc - 1) > 0.02:
                fs = ifont(weight, max(4, int(size * sc)))
                d.text((x + widths[i] / 2 + dx, cy + dy), ch, font=fs, fill=col + (int(255 * c01(a)),), anchor="mm")
            else:
                d.text((x + widths[i] / 2 + dx, cy + dy), ch, font=f, fill=col + (int(255 * c01(a)),), anchor="mm")
        x += widths[i] + tracking
    return lay


def text_width(txt, size, weight=600, tracking=0.0):
    f = ifont(weight, size)
    return sum(f.getlength(ch) for ch in txt) + tracking * (len(txt) - 1)


# ================================================================= UI: Prompt-Leiste
def prompt_bar(text, caret=True, t=0.0, cx=SW / 2, cy=SH * 0.43, w=1240, h=230, alpha=1.0, chip="AI", fill=GREIGE,
               shimmer=None):
    """Generische KI-Eingabeleiste (abgerundet, hell) mit Text, Icon-Reihe, Modell-Chip und Senden-Knopf."""
    lay = layer()
    d = ImageDraw.Draw(lay)
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    sh = layer()
    ImageDraw.Draw(sh).rounded_rectangle((x0, y0 + 14, x1, y1 + 14), radius=h * 0.22, fill=(0, 0, 0, 110))
    lay.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)))
    d.rounded_rectangle((x0, y0, x1, y1), radius=h * 0.22, fill=fill + (236,))
    ink = (58, 54, 52)
    f = ifont(450, 46)
    d.text((x0 + 56, y0 + 66), text, font=f, fill=ink + (255,), anchor="lm")
    if caret and int(t * 2.2) % 2 == 0:
        cxr = x0 + 60 + f.getlength(text)
        d.rectangle((cxr, y0 + 40, cxr + 3, y0 + 92), fill=ink + (255,))
    # Icon-Reihe unten links
    iy = y1 - 58
    ic = (92, 88, 84, 255)
    x = x0 + 62
    d.line((x - 14, iy, x + 14, iy), fill=ic, width=4)
    d.line((x, iy - 14, x, iy + 14), fill=ic, width=4)
    x += 66
    d.ellipse((x - 16, iy - 16, x + 16, iy + 16), outline=ic, width=3)
    d.line((x - 16, iy, x + 16, iy), fill=ic, width=2)
    d.ellipse((x - 7, iy - 16, x + 7, iy + 16), outline=ic, width=2)
    x += 66
    d.rounded_rectangle((x - 16, iy - 14, x + 16, iy + 14), radius=5, outline=ic, width=3)
    d.ellipse((x - 8, iy - 6, x - 2, iy), fill=ic)
    d.polygon([(x - 12, iy + 10), (x - 2, iy + 1), (x + 4, iy + 6), (x + 12, iy - 4), (x + 12, iy + 10)], fill=ic)
    x += 70
    fc = ifont(550, 30)
    d.text((x - 10, iy), chip, font=fc, fill=ic, anchor="lm")
    d.polygon([(x + fc.getlength(chip), iy - 4), (x + fc.getlength(chip) + 14, iy - 4), (x + fc.getlength(chip) + 7, iy + 5)], fill=ic)
    # Senden-Knopf rechts
    bx = x1 - 64
    d.ellipse((bx - 30, iy - 30, bx + 30, iy + 30), fill=(40, 38, 36, 255))
    d.line((bx, iy + 14, bx, iy - 13), fill=(240, 236, 228, 255), width=5)
    d.line((bx - 12, iy - 2, bx, iy - 14), fill=(240, 236, 228, 255), width=5)
    d.line((bx + 12, iy - 2, bx, iy - 14), fill=(240, 236, 228, 255), width=5)
    mx = bx - 74
    d.rounded_rectangle((mx - 8, iy - 18, mx + 8, iy + 6), radius=8, fill=ic)
    d.arc((mx - 14, iy - 8, mx + 14, iy + 16), 0, 180, fill=ic, width=3)
    d.line((mx, iy + 16, mx, iy + 22), fill=ic, width=3)
    if shimmer is not None and 0 < shimmer < 1:
        band = layer()
        sx = lerp(x0 - 200, x1 + 200, shimmer)
        ImageDraw.Draw(band).polygon([(sx - 60, y0), (sx + 30, y0), (sx - 10, y1), (sx - 100, y1)], fill=TEAL_HOT + (150,))
        band = band.filter(ImageFilter.GaussianBlur(20))
        bm = Image.new("L", (SW, SH), 0)
        ImageDraw.Draw(bm).rounded_rectangle((x0, y0, x1, y1), radius=h * 0.22, fill=255)
        band.putalpha(ImageChops.multiply(band.getchannel("A"), bm))
        lay.alpha_composite(band)
    return fade(lay, alpha)


def dropdown(items, sel, cx, top, w=360, row_h=74, alpha=1.0, open_p=1.0, badge=None, fill=GREIGE):
    """Menü unter dem Modell-Chip; items = Liste von Texten; sel = Index der Markierung (oder None)."""
    lay = layer()
    d = ImageDraw.Draw(lay)
    h = row_h * len(items) + 24
    sc = lerp(0.85, 1.0, e_out(open_p, 3))
    hh = h * sc
    x0, x1 = cx - w * sc / 2, cx + w * sc / 2
    d.rounded_rectangle((x0, top, x1, top + hh), radius=22, fill=fill + (int(240 * c01(open_p * 1.5)),))
    f = ifont(500, int(32 * sc))
    for i, it in enumerate(items):
        ry = top + 12 * sc + row_h * sc * (i + 0.5)
        if sel == i:
            d.rounded_rectangle((x0 + 10, ry - row_h * sc / 2 + 4, x1 - 10, ry + row_h * sc / 2 - 4), radius=14, fill=(206, 199, 186, 255))
        d.text((x0 + 30 * sc, ry), it, font=f, fill=(58, 54, 52, int(255 * c01(open_p * 1.5))), anchor="lm")
        if badge and badge[0] == i:
            bw = ifont(600, 22).getlength(badge[1]) + 24
            bx = x0 + 34 * sc + f.getlength(it) + 14
            d.rounded_rectangle((bx, ry - 16, bx + bw, ry + 16), radius=16, fill=TEAL + (255,))
            d.text((bx + bw / 2, ry), badge[1], font=ifont(600, 22), fill=(10, 40, 36, 255), anchor="mm")
    return fade(lay, alpha)


# ================================================================= Segment-Schalter
def segmented(labels, knob_pos, cx, cy, w=760, h=110, knob_col=None, track_fill=None, blue_fill=0.0, alpha=1.0):
    """Kapsel mit Optionen; knob_pos = Position des Schiebers in Options-Einheiten (0..n-1, auch Zwischenwerte)."""
    lay = layer()
    d = ImageDraw.Draw(lay)
    n = len(labels)
    x0, y0 = cx - w / 2, cy - h / 2
    d.rounded_rectangle((x0, y0, x0 + w, y0 + h), radius=h / 2, fill=(track_fill or (60, 60, 66)) + (230,))
    seg = w / n
    if blue_fill > 0:
        bw = seg * (knob_pos + 1) * blue_fill
        grad = layer()
        gd = ImageDraw.Draw(grad)
        steps = 40
        for k in range(steps):
            a = k / steps
            col = tuple(int(lerp(c0, c1, a)) for c0, c1 in zip((60, 60, 66), TRACK))
            gd.rectangle((x0 + bw * a, y0, x0 + bw * (a + 1 / steps) + 1, y0 + h), fill=col + (255,))
        mk = Image.new("L", (SW, SH), 0)
        ImageDraw.Draw(mk).rounded_rectangle((x0, y0, x0 + w, y0 + h), radius=h / 2, fill=255)
        grad.putalpha(ImageChops.multiply(grad.getchannel("A"), mk))
        lay.alpha_composite(grad)
    kx = x0 + seg * (knob_pos + 0.5)
    kc = knob_col or (225, 226, 232)
    knob = layer()
    ImageDraw.Draw(knob).rounded_rectangle((kx - seg / 2 + 8, y0 + 8, kx + seg / 2 - 8, y0 + h - 8), radius=(h - 16) / 2, fill=kc + (255,))
    glow(lay, knob, 30, 0.6)
    f = ifont(600, int(h * 0.3))
    for i, lb in enumerate(labels):
        on = abs(knob_pos - i) < 0.5
        col = (24, 24, 30) if on and sum(kc) > 500 else WHITE
        d2 = ImageDraw.Draw(lay)
        d2.text((x0 + seg * (i + 0.5), cy), lb, font=f, fill=col + (255,), anchor="mm")
    return fade(lay, alpha)


# ================================================================= Bänder / Linien
def bezier(p0, p1, p2, p3, n=120):
    ts = np.linspace(0, 1, n)[:, None]
    p0, p1, p2, p3 = (np.array(p, float) for p in (p0, p1, p2, p3))
    return (1 - ts) ** 3 * p0 + 3 * (1 - ts) ** 2 * ts * p1 + 3 * (1 - ts) * ts ** 2 * p2 + ts ** 3 * p3


def ribbon(base, pts, head, tail, col=TEAL, hot=TEAL_HOT, width=10, double=18, glow_r=26):
    """Doppel-Band entlang pts; sichtbar zwischen tail..head (0..1 der Pfadlänge), verjüngt am Ende."""
    if head <= tail:
        return
    seg = np.diff(pts, axis=0)
    L = np.concatenate([[0], np.cumsum(np.hypot(seg[:, 0], seg[:, 1]))])
    L /= L[-1]
    sel = (L >= tail) & (L <= head)
    idx = np.flatnonzero(sel)
    if len(idx) < 2:
        return
    P = pts[idx]
    nrm = np.gradient(P, axis=0)
    nrm = np.stack([-nrm[:, 1], nrm[:, 0]], 1)
    nrm /= np.maximum(np.hypot(nrm[:, 0], nrm[:, 1])[:, None], 1e-6)
    lay = layer()
    d = ImageDraw.Draw(lay)
    m = len(P)
    for off in (-double / 2, double / 2):
        Q = P + nrm * off
        for k in range(m - 1):
            u = k / max(1, m - 2)
            wdt = max(1, int(width * (0.25 + 0.75 * u)))
            d.line([tuple(Q[k]), tuple(Q[k + 1])], fill=col + (int(255 * (0.3 + 0.7 * u)),), width=wdt)
            if u > 0.55:
                d.line([tuple(Q[k]), tuple(Q[k + 1])], fill=hot + (int(255 * (u - 0.55) / 0.45),), width=max(1, wdt // 3))
    glow(base, lay, glow_r, 0.9)


# ================================================================= Icon im Ring, Partikel
def ring_icon(draw_icon, cx, cy, r, ring_p=1.0, alpha=1.0, col=WHITE, width=5):
    lay = layer()
    d = ImageDraw.Draw(lay)
    if ring_p > 0:
        d.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * c01(ring_p), fill=col + (255,), width=width)
    draw_icon(d, cx, cy, r * 0.62, col + (255,))
    return fade(lay, alpha)
