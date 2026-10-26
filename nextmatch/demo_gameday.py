"""NEXT MATCH – Beispielgrafik #1: Eishockey-Gameday (Feed 1080x1350) mit zwei FIKTIVEN Vereinen.

Alles vektoriell/prozedural gezeichnet (Wappen, Schläger, Puck, Eisfläche) – keine Fotos, keine Fremdlizenzen.
Aufruf: python3 demo_gameday.py  -> out/demo/gameday_feed.png
"""
import math
import os

import cairocffi as cairo
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import logo as L

OUT = os.path.join(L.OUT, "demo")
W, H = 1080, 1350
RED = (225, 16, 30)
RED_D = (120, 6, 14)
BLACK = (14, 14, 18)
BLUE = (20, 70, 216)
YELLOW = (255, 196, 0)
WHITE = (246, 247, 250)
ICE_BLUE = (70, 140, 255)

HOME = dict(name="EC FALKENSTADT", short="ECF", est="1952", city="FALKENSTADT")
AWAY = dict(name="ERC WOLFSRIED", short="W", est="1968")
INFO = (("DATUM", "FR 30.10."), ("BULLY", "20:00"), ("ARENA", "FALKEN-ARENA"))
HOR = 600                                          # Horizont der Eisfläche


def c01(c):
    return tuple(v / 255 for v in c)


# ================================================================= Hilfen
def prem(im):
    a = np.asarray(im.convert("RGBA"), np.float32) / 255
    a[..., :3] *= a[..., 3:4]
    return a


def over(dst, src, x, y):
    h, w = src.shape[:2]
    x, y = int(round(x)), int(round(y))
    sx0, sy0 = max(0, -x), max(0, -y)
    dx0, dy0 = max(0, x), max(0, y)
    dx1, dy1 = min(dst.shape[1], x + w), min(dst.shape[0], y + h)
    if dx1 <= dx0 or dy1 <= dy0:
        return
    s = src[sy0:sy0 + dy1 - dy0, sx0:sx0 + dx1 - dx0]
    d = dst[dy0:dy1, dx0:dx1]
    d[..., :3] = s[..., :3] + d[..., :3] * (1 - s[..., 3:4])


def over_c(dst, src, cx, cy):
    over(dst, src, cx - src.shape[1] / 2, cy - src.shape[0] / 2)


def surface(w, h):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(w), int(h))
    return s, cairo.Context(s)


def surf_np(s):
    """cairo ARGB32 (prämultipliziert, BGRA) -> float RGBA prämultipliziert."""
    s.flush()
    a = np.frombuffer(s.get_data(), np.uint8).reshape(s.get_height(), s.get_width(), 4).astype(np.float32) / 255
    return a[..., [2, 1, 0, 3]].copy()


def np_pil(a):
    """prämultipliziert float RGBA -> PIL RGBA."""
    rgb = a[..., :3] / np.maximum(a[..., 3:4], 1e-6)
    out = np.concatenate([np.clip(rgb, 0, 1), a[..., 3:4]], -1)
    return Image.fromarray((out * 255).astype(np.uint8), "RGBA")


def text(txt, font, size, col, track=0.0, stroke=0, fill=True, k=0.0):
    """Text als prämultipliziertes RGBA; optional nur Kontur (fill=False) und kursiv (k)."""
    f = L.font(font, size)
    w = int(sum(f.getlength(c) for c in txt) + track * size * max(0, len(txt) - 1)) + size + 2 * stroke
    asc, desc = f.getmetrics()
    im = Image.new("RGBA", (w, asc + desc + size // 2 + 2 * stroke), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = size // 2 + stroke
    for ch in txt:
        d.text((x, size // 4 + stroke), ch, font=f, fill=(col + (255,)) if fill else (0, 0, 0, 0),
               stroke_width=stroke, stroke_fill=col + (255,))
        x += f.getlength(ch) + track * size
    im = im.crop(im.getbbox())
    if k:
        im = L.shear(im, k)
        im = im.crop(im.getbbox())
    return prem(im)


def blur(a, sigma):
    return cv2.GaussianBlur(a, (0, 0), sigma)


def tint(a, col, alpha=1.0):
    """Alpha-Maske eines Layers in Farbe col (prämultipliziert)."""
    out = np.zeros_like(a)
    out[..., 3] = a[..., 3] * alpha
    out[..., :3] = np.array(c01(col), np.float32) * out[..., 3:4]
    return out


# ================================================================= Wappen (fiktiv)
def shield_path(c, x, y, w, h):
    c.move_to(x, y + h * 0.06)
    c.line_to(x + w * 0.5, y)
    c.line_to(x + w, y + h * 0.06)
    c.line_to(x + w, y + h * 0.56)
    c.curve_to(x + w, y + h * 0.80, x + w * 0.72, y + h * 0.92, x + w * 0.5, y + h)
    c.curve_to(x + w * 0.28, y + h * 0.92, x, y + h * 0.80, x, y + h * 0.56)
    c.close_path()


def stick_path(c, length, shaft=15, blade=118, bh=30):
    """Schläger senkrecht (Griff oben bei y=0), Kelle nach rechts unten."""
    c.rectangle(-shaft / 2, 0, shaft, length)
    c.move_to(-shaft / 2, length - 6)
    c.line_to(shaft / 2, length - 6)
    c.curve_to(shaft / 2 + blade * 0.3, length + bh * 0.25, blade * 0.8, length + bh * 0.2, blade, length)
    c.line_to(blade + 6, length + bh * 0.55)
    c.curve_to(blade * 0.8, length + bh * 1.05, shaft / 2, length + bh * 1.0, -shaft / 2, length + bh * 0.62)
    c.close_path()


def crest_home(S=320):
    ss = 2
    s, c = surface(S * ss, S * 1.15 * ss)
    c.scale(ss, ss)
    w, h = S * 0.86, S * 1.05
    x0, y0 = (S - w) / 2, S * 0.04
    shield_path(c, x0, y0, w, h)
    c.set_source_rgb(*c01(RED))
    c.fill()
    shield_path(c, x0 + 12, y0 + 12, w - 24, h - 26)
    c.set_source_rgb(*c01(BLACK))
    c.fill_preserve()
    c.set_source_rgb(*c01(WHITE))
    c.set_line_width(3)
    c.stroke()
    # Kopfband
    c.save()
    shield_path(c, x0 + 12, y0 + 12, w - 24, h - 26)
    c.clip()
    c.rectangle(0, y0 + h * 0.15, S, h * 0.13)
    c.set_source_rgb(*c01(RED))
    c.fill()
    c.restore()
    img = surf_np(s)
    big = cv2.resize(img, (S, int(S * 1.15)), interpolation=cv2.INTER_AREA)
    # Texte
    t1 = text(HOME["city"], "ArchivoX800.ttf", 19, WHITE, 0.25)
    over_c(big, t1, S / 2, y0 + h * 0.215)
    mono = text(HOME["short"], "Anton.ttf", 118, WHITE, 0.02, k=0.12)
    over_c(big, tint(mono, RED), S / 2 + 6, y0 + h * 0.6 + 6)
    over_c(big, mono, S / 2, y0 + h * 0.6)
    yr = text(HOME["est"], "ArchivoX800.ttf", 22, WHITE, 0.35)
    over_c(big, yr, S / 2, y0 + h * 0.84)
    for dx in (-62, 62):
        over_c(big, star_img(9, RED), S / 2 + dx, y0 + h * 0.84)
    return big


def crest_away(S=320):
    ss = 2
    s, c = surface(S * ss, S * ss)
    c.scale(ss, ss)
    r = S * 0.48
    c.arc(S / 2, S / 2, r, 0, 2 * math.pi)
    c.set_source_rgb(*c01(BLUE))
    c.fill()
    c.arc(S / 2, S / 2, r - 7, 0, 2 * math.pi)
    c.set_source_rgb(*c01(YELLOW))
    c.set_line_width(5)
    c.stroke()
    c.arc(S / 2, S / 2, r * 0.66, 0, 2 * math.pi)
    c.set_source_rgb(*c01(YELLOW))
    c.fill()
    c.arc(S / 2, S / 2, r * 0.66 - 6, 0, 2 * math.pi)
    c.set_source_rgb(*c01(BLUE))
    c.set_line_width(3)
    c.stroke()
    img = np_pil(cv2.resize(surf_np(s), (S, S), interpolation=cv2.INTER_AREA))
    # Ringtext rundherum gleichmäßig verteilt
    f = L.font("ArchivoX800.ttf", 23)
    txt = f"ERC WOLFSRIED · EST. {AWAY['est']} · "
    R = r * 0.83
    base = sum(f.getlength(ch) for ch in txt)
    track = (2 * math.pi * R - base) / len(txt)
    L.arc_text(img, txt, f, R, -math.pi / 2, True, track)
    big = prem(img)
    mono = text(AWAY["short"], "Anton.ttf", 112, BLUE, k=0.1)
    over_c(big, mono, S / 2 + 2, S / 2 + 14)
    for dx in (-34, 0, 34):                         # drei Sterne
        star = star_img(11 if dx else 14, BLUE)
        over_c(big, star, S / 2 + dx, S / 2 - r * 0.43 - (0 if dx else 4))
    return big


def star_img(R, col):
    s, c = surface(R * 2 + 4, R * 2 + 4)
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = R if i % 2 == 0 else R * 0.45
        (c.move_to if i == 0 else c.line_to)(R + 2 + rr * math.cos(a), R + 2 + rr * math.sin(a))
    c.close_path()
    c.set_source_rgb(*c01(col))
    c.fill()
    return surf_np(s)


# ================================================================= Schläger, Puck
def sticks_cross(S=760):
    s, c = surface(S, S)
    for ang, flip in ((-36, False), (36, True)):
        c.save()
        c.translate(S / 2, S / 2)
        c.rotate(math.radians(ang))
        if flip:
            c.scale(-1, 1)
        c.translate(0, -S * 0.42)
        length = S * 0.72
        stick_path(c, length, shaft=19, blade=150, bh=40)
        g = cairo.LinearGradient(-10, 0, 10, 0)
        g.add_color_stop_rgb(0, 0.10, 0.10, 0.12)
        g.add_color_stop_rgb(0.5, 0.32, 0.33, 0.37)
        g.add_color_stop_rgb(1, 0.08, 0.08, 0.10)
        c.set_source(g)
        c.fill()
        # weißes Tape auf der Kelle, Griffband oben
        c.save()
        stick_path(c, length, shaft=19, blade=150, bh=40)
        c.clip()
        for k in range(9):
            c.rectangle(18 + k * 14, length - 20, 9, 70)
        c.set_source_rgba(0.95, 0.95, 0.97, 0.9)
        c.fill()
        c.restore()
        c.rectangle(-9.5, 0, 19, 70)
        c.set_source_rgb(0.92, 0.92, 0.94)
        c.fill()
        c.restore()
    return surf_np(s)


def puck(w=150):
    h = w * 0.62
    s, c = surface(w + 8, h + 8)
    ry = w * 0.17
    top, side = 4 + ry, w * 0.20
    c.save()
    c.translate(w / 2 + 4, 0)
    # Seite
    c.move_to(-w / 2, top)
    c.line_to(-w / 2, top + side)
    c.save()
    c.scale(1, ry / (w / 2))
    c.arc_negative(0, (top + side) / (ry / (w / 2)), w / 2, math.pi, 0)
    c.restore()
    c.line_to(w / 2, top)
    c.close_path()
    g = cairo.LinearGradient(-w / 2, 0, w / 2, 0)
    g.add_color_stop_rgb(0, 0.05, 0.05, 0.06)
    g.add_color_stop_rgb(0.35, 0.22, 0.22, 0.25)
    g.add_color_stop_rgb(1, 0.03, 0.03, 0.04)
    c.set_source(g)
    c.fill()
    # Oberseite
    c.save()
    c.scale(1, ry / (w / 2))
    c.arc(0, top / (ry / (w / 2)), w / 2, 0, 2 * math.pi)
    c.restore()
    g = cairo.LinearGradient(0, top - ry, 0, top + ry)
    g.add_color_stop_rgb(0, 0.20, 0.20, 0.23)
    g.add_color_stop_rgb(1, 0.07, 0.07, 0.08)
    c.set_source(g)
    c.fill_preserve()
    c.set_source_rgba(1, 1, 1, 0.35)
    c.set_line_width(2)
    c.stroke()
    c.restore()
    return surf_np(s)


# ================================================================= Eisfläche
def ice_texture(T=2400):
    rng = np.random.default_rng(3)
    base = np.array((0.085, 0.11, 0.15), np.float32)
    n = cv2.resize(rng.random((T // 16, T // 16)).astype(np.float32), (T, T), interpolation=cv2.INTER_CUBIC)
    img = base * (0.85 + 0.3 * n[..., None])
    sc = np.zeros((T, T), np.float32)
    for _ in range(700):                            # Kufenspuren
        x, y = rng.uniform(0, T), rng.uniform(0, T)
        a = rng.uniform(0, math.pi)
        ln, cur = rng.uniform(120, 700), rng.uniform(-0.002, 0.002)
        pts = []
        for k in range(24):
            tt = k / 23 * ln
            aa = a + cur * tt
            pts.append((x + math.cos(aa) * tt, y + math.sin(aa) * tt))
        cv2.polylines(sc, [np.int32(pts)], False, float(rng.uniform(0.04, 0.16)), 1, cv2.LINE_AA)
    img += sc[..., None] * np.array((0.75, 0.85, 1.0), np.float32)
    lay = np.zeros((T, T, 3), np.float32)
    cy = int(T * 0.50)                              # Mittellinie liegt hinter der Info-Leiste
    red, blue = c01(RED), c01(ICE_BLUE)
    cv2.rectangle(lay, (0, cy - 13), (T, cy + 13), red, -1, cv2.LINE_AA)        # rote Mittellinie
    for xx in range(0, T, 60):                                                  # Mittellinien-Muster
        cv2.rectangle(lay, (xx + 20, cy - 4), (xx + 40, cy + 4), (0.95, 0.95, 0.95), -1)
    cv2.circle(lay, (T // 2, cy), int(T * 0.19), blue, 10, cv2.LINE_AA)        # Bullykreis Mitte
    cv2.circle(lay, (T // 2, cy), 26, blue, -1, cv2.LINE_AA)
    by = int(T * 0.20)
    cv2.rectangle(lay, (0, by - 26), (T, by + 26), blue, -1, cv2.LINE_AA)      # blaue Linie
    for fx in (T // 2 - 560, T // 2 + 560):                                    # Bullypunkte neutrale Zone
        cv2.circle(lay, (fx, int(T * 0.245)), 22, red, -1, cv2.LINE_AA)
    glow = blur(lay, 10) * 0.9 + blur(lay, 40) * 0.6
    img = img * (1 - np.clip(lay.max(-1, keepdims=True), 0, 1) * 0.85) + lay * 0.85 + glow * 0.5
    return img, cy


def floor_layer():
    T = 2400
    tex, cy = ice_texture(T)
    src = np.float32([[0, 0], [T, 0], [T, T], [0, T]])
    dst = np.float32([[W / 2 - 560, HOR], [W / 2 + 560, HOR], [W / 2 + 2300, H + 900], [W / 2 - 2300, H + 900]])
    m = cv2.getPerspectiveTransform(src, dst)
    fl = cv2.warpPerspective(tex, m, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    mask = cv2.warpPerspective(np.ones((T, T), np.float32), m, (W, H))
    ys = np.arange(H, dtype=np.float32)[:, None, None]
    fog = np.clip((ys - HOR) / 260, 0, 1) ** 1.3
    haze = np.array((0.05, 0.065, 0.09), np.float32)
    fl = fl * fog + haze * (1 - fog)
    return fl, mask[..., None]


# ================================================================= Hintergrund
def background():
    rng = np.random.default_rng(9)
    ys = np.arange(H, dtype=np.float32)[:, None, None] / H
    xs = np.arange(W, dtype=np.float32)[None, :, None] / W
    img = np.ones((H, W, 3), np.float32) * np.array((0.03, 0.032, 0.045), np.float32)
    img += np.exp(-(((xs - 0.5) / 0.6) ** 2 + ((ys - 0.0) / 0.35) ** 2)) * np.array(c01(RED), np.float32) * 0.20
    img += np.exp(-(((xs - 0.5) / 0.5) ** 2 + ((ys - 0.44) / 0.12) ** 2)) * np.array((0.25, 0.4, 0.7), np.float32) * 0.12
    # Hallenlichter (Bokeh)
    bok = np.zeros((H, W, 3), np.float32)
    lights = []
    for _ in range(26):
        x, y = rng.uniform(0, W), rng.uniform(20, HOR - 150)
        r = rng.uniform(5, 22)
        b = rng.uniform(0.25, 0.9)
        cv2.circle(bok, (int(x), int(y)), int(r), (b, b * 0.95, b * 0.85), -1, cv2.LINE_AA)
        lights.append((x, b))
    img += blur(bok, 6) * 0.55 + blur(bok, 30) * 0.4
    fl, mask = floor_layer()
    img = img * (1 - mask) + fl * mask
    # Spiegelungen der Lichter auf dem Eis
    refl = np.zeros((H, W), np.float32)
    for x, b in lights:
        refl[HOR:, int(np.clip(x, 0, W - 1))] += b
    refl = cv2.GaussianBlur(refl, (0, 0), sigmaX=14, sigmaY=1)
    fall = np.exp(-np.clip(np.arange(H, dtype=np.float32) - HOR, 0, None) / 320)[:, None]
    img += (refl * fall)[..., None] * np.array((0.9, 0.9, 1.0), np.float32) * 0.35
    # Horizont-Lichtkante
    img += np.exp(-((np.arange(H, dtype=np.float32) - HOR) / 6) ** 2)[:, None, None] * 0.12
    return img


# ================================================================= Layout
def pill(txt, col_bg, col_fg, size=24):
    t = text(txt, "ArchivoX800.ttf", size, col_fg, 0.18)
    w, h = t.shape[1] + 56, t.shape[0] + 26
    sk = h * 0.32
    s, c = surface(w + sk + 4, h)
    c.move_to(sk, 0)
    c.line_to(w + sk, 0)
    c.line_to(w, h)
    c.line_to(0, h)
    c.close_path()
    c.set_source_rgb(*c01(col_bg))
    c.fill()
    out = surf_np(s)
    over_c(out, t, out.shape[1] / 2, out.shape[0] / 2)
    return out


def info_panel(img):
    x0, y0, w, h = 70, 935, W - 140, 150
    sk = 26
    region = img[y0 - 10:y0 + h + 10].copy()
    frost = cv2.GaussianBlur(region, (0, 0), 18)
    s, c = surface(W, h + 20)
    c.move_to(x0 + sk, 10)
    c.line_to(x0 + w + sk, 10)
    c.line_to(x0 + w - sk, h + 10)
    c.line_to(x0 - sk, h + 10)
    c.close_path()
    c.set_source_rgba(1, 1, 1, 1)
    c.fill()
    m = surf_np(s)[..., 3:4]
    panel = frost * 0.55 + np.array((0.02, 0.025, 0.04), np.float32) * 0.45
    img[y0 - 10:y0 + h + 10] = region * (1 - m) + panel * m
    # rote Oberkante + Trenner
    s, c = surface(W, h + 20)
    c.move_to(x0 + sk, 10)
    c.line_to(x0 + w + sk, 10)
    c.set_source_rgb(*c01(RED))
    c.set_line_width(6)
    c.stroke()
    for k in (1, 2):
        xx = x0 + w * k / 3
        c.move_to(xx + sk * 0.6, 34)
        c.line_to(xx - sk * 0.6, h - 14)
        c.set_source_rgba(1, 1, 1, 0.22)
        c.set_line_width(2)
        c.stroke()
    over(img, surf_np(s), 0, y0 - 10)
    for k, (lab, val) in enumerate(INFO):
        cx = x0 + w * (k + 0.5) / 3
        tl = text(lab, "ArchivoX800.ttf", 20, (150, 156, 170), 0.3)
        over_c(img, tl, cx, y0 + 46)
        size = 60 if len(val) < 10 else 46
        tv = text(val, "Anton.ttf", size, WHITE, 0.03, k=0.12)
        over_c(img, tv, cx, y0 + 102)


def glow_under(img, src, cx, cy, col, sigma, amt):
    g = np.zeros((H, W, 4), np.float32)
    over_c(g, tint(src, col), cx, cy)
    img += blur(g[..., :3], sigma) * amt


def compose():
    img = background()
    # Kopf
    p = pill("HAUPTRUNDE  ·  SPIELTAG 12", RED, WHITE, 22)
    over_c(img, p, W / 2, 82)
    head = text("GAMEDAY", "Anton.ttf", 250, WHITE, 0.01, k=0.16)
    hx, hy = W / 2, 250
    outl = text("GAMEDAY", "Anton.ttf", 250, WHITE, 0.01, stroke=3, fill=False, k=0.16)
    over_c(img, outl * 0.25, hx + 26, hy + 22)
    over_c(img, tint(head, RED), hx + 12, hy + 11)
    over_c(img, head, hx, hy)
    # Mitte: Schläger, Wappen, VS, Puck
    st = sticks_cross(540)
    over_c(img, st * 0.95, W / 2, 610)
    ch, ca = crest_home(300), crest_away(290)
    glow_under(img, ch, 255, 610, RED, 40, 0.9)
    glow_under(img, ca, 825, 610, BLUE, 40, 1.0)
    for cr, cx in ((ch, 255), (ca, 825)):          # Schlagschatten
        sh = np.zeros((H, W, 4), np.float32)
        over_c(sh, tint(cr, (0, 0, 0), 0.7), cx + 8, 625)
        a = blur(sh[..., 3], 10)[..., None]
        img *= 1 - a * 0.8
    over_c(img, ch, 255, 610)
    over_c(img, ca, 825, 610)
    vs = text("VS", "Anton.ttf", 150, WHITE, 0.0, k=0.16)
    glow_under(img, vs, W / 2, 600, WHITE, 22, 0.35)
    over_c(img, tint(vs, RED), W / 2 + 7, 607)
    over_c(img, vs, W / 2, 600)
    pk = puck(120)
    sh = np.zeros((H, W, 4), np.float32)
    over_c(sh, tint(pk, (0, 0, 0)), W / 2, 742)
    img *= 1 - blur(sh[..., 3], 8)[..., None] * 0.7
    over_c(img, pk, W / 2, 730)
    # Vereinsnamen
    for cx, d, role in ((255, HOME, "HEIM"), (825, AWAY, "GAST")):
        tn = text(d["name"], "ArchivoX800.ttf", 30, WHITE, 0.04, k=0.1)
        tr = text(role, "ArchivoX800.ttf", 18, (150, 156, 170), 0.45)
        sh = np.zeros((H, W, 4), np.float32)           # weicher Schatten, damit die Eislinien den Text nicht stören
        over_c(sh, tn, cx, 815)
        over_c(sh, tr, cx, 853)
        img *= 1 - np.clip(blur(sh[..., 3], 9) * 1.6, 0, 0.85)[..., None]
        over_c(img, tn, cx, 815)
        over_c(img, tr, cx, 853)
    info_panel(img)
    # Fuß (unten abdunkeln, damit der Text auf dem Eis lesbar bleibt)
    ys_ = np.arange(H, dtype=np.float32)[:, None, None]
    img *= 1 - 0.55 * np.clip((ys_ - 1110) / 160, 0, 1)
    ft = text("TICKETS AN DER ABENDKASSE AB 18:30 UHR", "ArchivoX800.ttf", 19, (200, 204, 214), 0.12)
    over(img, ft, 70, 1158)
    sym = L.fit(L.symbol_nm(120), 64, 22)
    sp = prem(sym)
    over(img, sp * 0.85, W - 70 - sp.shape[1], 1214)
    cr = text("DESIGN: NEXT MATCH  ·  DEMO", "ArchivoX800.ttf", 14, (130, 136, 150), 0.25)
    over(img, cr, W - 70 - sp.shape[1] - 16 - cr.shape[1], 1218)
    # Finish: Vignette + Korn
    ys = np.arange(H, dtype=np.float32)[:, None] / H - 0.5
    xs = np.arange(W, dtype=np.float32)[None, :] / W - 0.5
    img *= (1 - 0.5 * np.clip((xs ** 2 * 1.3 + ys ** 2) * 2.0, 0, 1))[..., None]
    img += np.random.default_rng(1).standard_normal((H, W, 1)).astype(np.float32) * 0.012
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))


def main():
    os.makedirs(OUT, exist_ok=True)
    im = compose()
    im.save(os.path.join(OUT, "gameday_feed.png"))
    print("fertig")


if __name__ == "__main__":
    main()
