"""Reel 10: Studio-Version von "POV: you make smooth animations for hockey".

Ablauf (15 s, loopbar):
  0.0–0.5   POV: Monitor mit After Effects, Komposition (9:16) klein im Viewer
  0.5–1.4   Kamera fliegt in den Bildschirm (mit Bewegungsunschärfe) -> Vollbild
  1.4–13.6  Vollbild-Motion-Design zu Wayne Gretzky (6 Szenen)
  13.6–14.6 Kamera zieht zurück auf den Monitor, 14.6–15.0 POV (Loop-Punkt)
Szenen: Titel + rollender Zähler 894 | 3D-Balken Tore/Saison | Karten Goals/Assists/Points |
        "99" -> Partikel -> Stanley Cup | Trophäen | Wortmarke "THE GREAT ONE".
Fakten: 894 Tore, 1.963 Assists, 2.857 Punkte (NHL-Rekord), 92 Tore 1981/82, 4 Stanley Cups,
        9 Hart Trophies, 10 Art Ross Trophies, Nr. 99 ligaweit gesperrt (2000).
Aufruf: python3 reel10_studio.py  ->  reel10_studio.mp4
"""
import math
import os
import random
import subprocess
import sys
import wave
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

import make_hockey_reel as m
import reel9_pov as pov
from make_hockey_reel import font, clamp

W, H, FPS, DUR = 1080, 1920, 30, 15.4
HERE = m.HERE
BLUE = (64, 196, 255)
ORANGE = (255, 146, 60)
RED = (255, 52, 64)
WHITE = (245, 246, 250)
DIM = (128, 132, 145)
GOALS = [51, 55, 92, 71, 87, 73, 52, 62, 40, 54, 40, 41, 31, 16, 38, 11, 23, 25, 23, 9]
COMP_IN_VIEW = (407, 575, 673, 1048)   # 9:16-Komposition im Viewer des POV-Bildes (x0,y0,x1,y1)


# ================================================================= Easing
def c01(x):
    return max(0.0, min(1.0, x))


def e_io(t):          # ease in-out quint (snappy, "studio")
    t = c01(t)
    return 16 * t ** 5 if t < 0.5 else 1 - (-2 * t + 2) ** 5 / 2


def e_out(t, p=4):
    t = c01(t)
    return 1 - (1 - t) ** p


def e_in(t, p=3):
    return c01(t) ** p


def e_back(t, s=1.6):
    t = c01(t) - 1
    return t * t * ((s + 1) * t + s) + 1


def lerp(a, b, t):
    return a + (b - a) * t


# ================================================================= Grundbausteine
def layer():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def glow_onto(base, lay, radius=24, strength=1.0, keep=True):
    """Schnelles Leuchten: Blur auf 1/4 Auflösung, per screen auf base, dann Ebene drüber."""
    small = lay.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(radius / 4))
    g = small.resize((W, H), Image.BILINEAR)
    arr = np.asarray(g).astype(np.float32)
    ga = np.clip(arr[..., 3:4] / 255 * strength, 0, 1)
    add = np.clip(arr[..., :3] * ga, 0, 255)                     # Glow (vormultipliziert)
    b = np.asarray(base).astype(np.float32)
    ba = b[..., 3:4] / 255
    pre = b[..., :3] * ba                                         # Basis vormultipliziert
    pre = 255 - (255 - pre) * (255 - add) / 255                   # 'screen'
    na = 1 - (1 - ba) * (1 - ga)                                  # neue Deckkraft (auch auf transparenten Ebenen)
    rgb = pre / np.maximum(na, 1e-4)
    out = np.concatenate([rgb, na * 255], -1)
    base.paste(Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA"))
    if keep:
        base.alpha_composite(lay)


def text_size(txt, size, weight, tracking=0):
    f = font(weight, size)
    return sum(f.getlength(ch) for ch in txt) + tracking * (len(txt) - 1)


def tracked(lay, txt, cx, cy, size, weight="ExtraBold", color=WHITE, tracking=0, alpha=1.0,
            per_letter=None, anchor_x="center"):
    """Text Buchstabe für Buchstabe (Laufweite + individuelle Animation pro Buchstabe)."""
    f = font(weight, size)
    total = text_size(txt, size, weight, tracking)
    x = cx - total / 2 if anchor_x == "center" else cx
    d = ImageDraw.Draw(lay)
    n = len(txt)
    for i, ch in enumerate(txt):
        dx, dy, a = 0, 0, alpha
        if per_letter:
            dx, dy, a = per_letter(i, n)
            a *= alpha
        if a > 0.01 and ch != " ":
            d.text((x + dx, cy + dy), ch, font=f, fill=color + (int(255 * c01(a)),), anchor="lm")
        x += f.getlength(ch) + tracking
    return total


def masked(lay, box):
    """Alles außerhalb von box (x0,y0,x1,y1) unsichtbar machen (Masken-Reveal)."""
    m_ = Image.new("L", lay.size, 0)
    ImageDraw.Draw(m_).rectangle(box, fill=255)
    lay.putalpha(ImageChops.multiply(lay.getchannel("A"), m_))
    return lay


def light_sweep(lay, pos, width=120, angle=0.35, strength=0.85):
    """Diagonaler Lichtstreifen über die sichtbaren Pixel von lay (pos 0..1)."""
    if not 0 < pos < 1:
        return
    yy, xx = np.mgrid[0:H:2, 0:W:2].astype(np.float32)
    center = lerp(-300, W + 300, pos)
    dist = (xx + yy * angle) - (center + 540 * angle)
    band = np.exp(-(dist / width) ** 2) * strength
    band = Image.fromarray((band * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)
    a = lay.getchannel("A")
    hl = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    hl.putalpha(ImageChops.multiply(a, band))
    lay.alpha_composite(hl)


def vblur(img, amount):
    """Vertikale Bewegungsunschärfe (für rollende Ziffern)."""
    k = int(amount)
    if k < 2:
        return img
    arr = np.asarray(img).astype(np.float32)
    pad = np.pad(arr, ((k, k), (0, 0), (0, 0)), mode="edge")
    cs = np.cumsum(pad, axis=0)
    out = (cs[2 * k:] - cs[:-2 * k]) / (2 * k)
    out = out[: arr.shape[0]]
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")


def odometer(lay, text, cx, cy, size, prog, weight="Black", color=WHITE, stagger=0.12, spins=2):
    """Rollender Zähler: jede Ziffer dreht (spins) Runden und rastet auf ihrem Zielwert ein."""
    f = font(weight, size)
    dw = f.getlength("0")
    widths = [dw if ch.isdigit() else f.getlength(ch) for ch in text]
    total = sum(widths)
    x = cx - total / 2
    ch_h = int(size * 1.15)
    digits = [i for i, ch in enumerate(text) if ch.isdigit()]
    for i, ch in enumerate(text):
        w = widths[i]
        if ch.isdigit():
            k = digits.index(i)
            p = e_out(c01(prog * (1 + stagger * len(digits)) - k * stagger), 3)
            target = int(ch) + 10 * spins
            v = target * p
            base = int(math.floor(v))
            frac = v - base
            speed = 0 if p >= 1 else (1 - p) ** 2 * target * 3
            cell = Image.new("RGBA", (int(w) + 8, ch_h * 3), (0, 0, 0, 0))
            cd = ImageDraw.Draw(cell)
            for j, dv in enumerate((base - 1, base, base + 1)):
                cd.text((cell.width / 2, ch_h * (j + 0.5) - frac * ch_h),
                        str(dv % 10), font=f, fill=color + (255,), anchor="mm")
            cell = cell.crop((0, ch_h, cell.width, ch_h * 2))
            cell = vblur(cell, min(40, speed))
            # Ein-/Ausblenden an den Kanten der Zelle (Rollen-Optik)
            fade = np.linspace(0, 1, ch_h)
            fade = np.minimum(np.minimum(fade / 0.18, (1 - fade) / 0.18), 1)
            a = np.asarray(cell.getchannel("A")).astype(np.float32) * fade[:, None]
            cell.putalpha(Image.fromarray(a.astype(np.uint8)))
            lay.alpha_composite(cell, (int(x + w / 2 - cell.width / 2), int(cy - ch_h / 2)))
        else:
            ImageDraw.Draw(lay).text((x + w / 2, cy), ch, font=f, fill=color + (int(255 * c01(prog * 3)),), anchor="mm")
        x += w
    return total


def gradient_text(lay, txt, cx, cy, size, weight, top, mid, bot, tracking=0, alpha=1.0):
    """Chrom-Text: Text als Maske, gefüllt mit vertikalem Verlauf."""
    mask_l = layer()
    tracked(mask_l, txt, cx, cy, size, weight, (255, 255, 255), tracking)
    bbox = mask_l.getbbox()
    if not bbox:
        return
    y0, y1 = bbox[1], bbox[3]
    ys = np.linspace(0, 1, y1 - y0)[:, None]
    cols = np.where(ys < 0.5, np.array(top) + (np.array(mid) - np.array(top)) * ys * 2,
                    np.array(mid) + (np.array(bot) - np.array(mid)) * (ys - 0.5) * 2)
    grad = np.zeros((H, W, 4), np.uint8)
    grad[y0:y1, :, :3] = cols[:, None, :].astype(np.uint8)
    a = np.asarray(mask_l.getchannel("A")).astype(np.float32) * alpha
    grad[..., 3] = a.astype(np.uint8)
    lay.alpha_composite(Image.fromarray(grad, "RGBA"))


# ================================================================= Icons (groß, sauber)
def draw_icon(d, kind, cx, cy, s, col):
    c = col + (255,) if len(col) == 3 else col
    if kind == "puck":
        d.ellipse((cx - 22 * s, cy - 2 * s, cx + 22 * s, cy + 14 * s), fill=c)
        d.rectangle((cx - 22 * s, cy - 6 * s, cx + 22 * s, cy + 6 * s), fill=c)
        d.ellipse((cx - 22 * s, cy - 14 * s, cx + 22 * s, cy + 2 * s), fill=(255, 255, 255, 60))
    elif kind == "stick":
        d.line((cx - 14 * s, cy - 22 * s, cx + 4 * s, cy + 14 * s), fill=c, width=int(7 * s))
        d.rounded_rectangle((cx + 0 * s, cy + 10 * s, cx + 24 * s, cy + 20 * s), radius=4 * s, fill=c)
    elif kind == "star":
        pts = []
        for k in range(10):
            r = 22 * s if k % 2 == 0 else 9 * s
            a = -math.pi / 2 + k * math.pi / 5
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
        d.polygon(pts, fill=c)
    elif kind == "cup":
        d.ellipse((cx - 30 * s, cy - 44 * s, cx + 30 * s, cy - 28 * s), fill=c)
        d.polygon([(cx - 30 * s, cy - 36 * s), (cx + 30 * s, cy - 36 * s), (cx + 12 * s, cy - 6 * s), (cx - 12 * s, cy - 6 * s)], fill=c)
        d.rectangle((cx - 10 * s, cy - 6 * s, cx + 10 * s, cy + 6 * s), fill=c)
        for k, wdt in enumerate((18, 22, 26, 30)):
            d.rounded_rectangle((cx - wdt * s, cy + (6 + k * 11) * s, cx + wdt * s, cy + (15 + k * 11) * s), radius=2 * s, fill=c)


# ================================================================= Hintergrund
_BG = None
_DOTS = None


def background(t, cam=(0.0, 0.0)):
    global _BG, _DOTS
    if _BG is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H * 0.42) / H) ** 2 * 0.6)
        base = np.clip(1 - r * 1.6, 0, 1)
        rgb = np.stack([6 + 10 * base, 8 + 14 * base, 14 + 30 * base], -1)
        _BG = Image.fromarray(rgb.astype(np.uint8)).convert("RGBA")
        _DOTS = Image.new("RGBA", (W + 120, H + 120), (0, 0, 0, 0))
        dd = ImageDraw.Draw(_DOTS)
        for y in range(0, H + 120, 60):
            for x in range(0, W + 120, 60):
                dd.ellipse((x - 1.6, y - 1.6, x + 1.6, y + 1.6), fill=(150, 170, 220, 26))
    img = _BG.copy()
    ox = int(60 + cam[0] + math.sin(t * 0.4) * 20) % 60
    oy = int(60 + cam[1] - t * 12) % 60
    img.alpha_composite(_DOTS.crop((ox, oy, ox + W, oy + H)))
    return img


# ================================================================= Szenen (lt = lokale Zeit)
def sc_title(lt):
    L = layer()
    d = ImageDraw.Draw(L)
    line_w = 760 * e_io((lt - 0.15) / 0.6)
    y_line = 700
    if line_w > 2:
        d.rectangle((W / 2 - line_w / 2, y_line - 1.5, W / 2 + line_w / 2, y_line + 1.5), fill=WHITE + (255,))
    # Name steigt aus der Linie auf
    up = layer()
    tracked(up, "WAYNE GRETZKY", W / 2, y_line - 52, 72, "ExtraBold", WHITE, 14,
            per_letter=lambda i, n: (0, 90 * (1 - e_out((lt - 0.45 - i * 0.03) / 0.55)), 1))
    L.alpha_composite(masked(up, (0, 0, W, y_line - 4)))
    down = layer()
    tracked(down, "THE GREAT ONE", W / 2, y_line + 42, 34, "SemiBold", BLUE, 16,
            per_letter=lambda i, n: (0, -60 * (1 - e_out((lt - 0.8 - i * 0.025) / 0.5)), 1))
    L.alpha_composite(masked(down, (0, y_line + 4, W, H)))
    # Riesiger rollender Zähler
    if lt > 1.1:
        num = layer()
        odometer(num, "894", W / 2, 1040, 360, c01((lt - 1.1) / 1.35), "Black", WHITE)
        light_sweep(num, c01((lt - 2.55) / 0.55))
        L.alpha_composite(num)
        lab = layer()
        tracked(lab, "NHL GOALS", W / 2, 1265, 40, "Bold", DIM, 20,
                per_letter=lambda i, n: (0, 0, e_out((lt - 2.2 - i * 0.03) / 0.3)))
        L.alpha_composite(lab)
    return L


def project(x, y, z, cam):
    yaw, camz, camy, f, cx, cy = cam
    xr = x * math.cos(yaw) + z * math.sin(yaw)
    zr = -x * math.sin(yaw) + z * math.cos(yaw)
    zc = zr + camz
    return cx + f * xr / zc, cy - f * (y - camy) / zc, zc


def sc_bars(lt):
    L = layer()
    d = ImageDraw.Draw(L)
    cam = (lerp(0.62, 0.42, e_io(lt / 3.2)), lerp(10.5, 8.6, e_io(lt / 3.2)), 3.4, 980, 470, 1200)
    out = e_in(c01((lt - 2.75) / 0.35), 2)
    # Bodenraster
    for gx in np.arange(-4, 6.01, 1.0):
        a = project(gx, 0, -2, cam)
        b = project(gx, 0, 22, cam)
        d.line((a[0], a[1], b[0], b[1]), fill=(80, 110, 170, 40), width=1)
    for gz in np.arange(-2, 22.01, 2.0):
        a = project(-4, 0, gz, cam)
        b = project(6, 0, gz, cam)
        d.line((a[0], a[1], b[0], b[1]), fill=(80, 110, 170, 40), width=1)
    bars = []
    for i, g in enumerate(GOALS):
        x0 = -2.2 + i * 0.36
        z0 = -1.0 + i * 1.05
        p = e_out((lt - 0.15 - i * 0.045) / 0.7) * (1 - out)
        h = g / 92 * 6.4 * p
        bars.append((z0, i, x0, h))
    hl = layer()
    hd = ImageDraw.Draw(hl)
    top_pt = None
    for z0, i, x0, h in sorted(bars, reverse=True):     # hinten zuerst
        if h <= 0.01:
            continue
        w, dz = 0.55, 0.55
        P = lambda x, y, z: project(x, y, z, cam)[:2]
        fl, fr = P(x0, 0, z0), P(x0 + w, 0, z0)
        tl, tr = P(x0, h, z0), P(x0 + w, h, z0)
        br_, tbr = P(x0 + w, 0, z0 + dz), P(x0 + w, h, z0 + dz)
        tbl = P(x0, h, z0 + dz)
        if i == 2:
            # Rekordbalken: Verlauf blau -> orange + Glow
            steps = 40
            for k in range(steps):
                a0, a1 = k / steps, (k + 1) / steps
                col = tuple(int(lerp(BLUE[j], ORANGE[j], a0)) for j in range(3))
                q = [(lerp(tl[0], fl[0], a0), lerp(tl[1], fl[1], a0)), (lerp(tr[0], fr[0], a0), lerp(tr[1], fr[1], a0)),
                     (lerp(tr[0], fr[0], a1), lerp(tr[1], fr[1], a1)), (lerp(tl[0], fl[0], a1), lerp(tl[1], fl[1], a1))]
                hd.polygon(q, fill=col + (255,))
            hd.polygon([tr, tbr, br_, fr], fill=(30, 90, 140, 255))
            hd.polygon([tl, tr, tbr, tbl], fill=(190, 235, 255, 255))
            top_pt = ((tl[0] + tr[0]) / 2, tl[1])
        else:
            shade = 40 + int(30 * (1 - i / 20))
            d.polygon([tr, tbr, br_, fr], fill=(shade - 18, shade - 16, shade - 10, 255))
            d.polygon([tl, tr, fr, fl], fill=(shade + 10, shade + 12, shade + 18, 255))
            d.polygon([tl, tr, tbr, tbl], fill=(shade + 45, shade + 48, shade + 58, 255))
    glow_onto(L, hl, 40, 1.4)
    # Callout
    if top_pt and lt > 1.0:
        p = e_io((lt - 1.0) / 0.5) * (1 - out)
        ex, ey = top_pt[0] + 120, top_pt[1] - 210
        mx, my = lerp(top_pt[0], ex, p), lerp(top_pt[1], ey, p)
        d.line((top_pt[0], top_pt[1] - 8, mx, my), fill=WHITE + (int(255 * p),), width=3)
        d.ellipse((top_pt[0] - 7, top_pt[1] - 15, top_pt[0] + 7, top_pt[1] - 1), fill=WHITE + (int(255 * p),))
        if lt > 1.35:
            lab = layer()
            tracked(lab, "1981–82", ex + 20, ey - 92, 36, "SemiBold", ORANGE, 8, anchor_x="left",
                    per_letter=lambda i, n: (0, 0, e_out((lt - 1.35 - i * 0.03) / 0.3)))
            odometer(lab, "92", ex + 115, ey - 10, 150, c01((lt - 1.4) / 0.8), "Black", WHITE)
            tracked(lab, "GOALS · ONE SEASON", ex + 20, ey + 82, 30, "Bold", DIM, 8, anchor_x="left",
                    per_letter=lambda i, n: (0, 0, e_out((lt - 1.7 - i * 0.02) / 0.3)))
            lab.putalpha(lab.getchannel("A").point(lambda v: int(v * (1 - out))))
            L.alpha_composite(lab)
    head = layer()
    tracked(head, "GOALS PER SEASON", W / 2, 330, 40, "Bold", WHITE, 18,
            per_letter=lambda i, n: (0, 40 * (1 - e_out((lt - 0.1 - i * 0.02) / 0.4)), e_out((lt - 0.1 - i * 0.02) / 0.4) * (1 - out)))
    L.alpha_composite(masked(head, (0, 280, W, 372)))
    return L


CARDS = [("puck", "GOALS", "894"), ("stick", "ASSISTS", "1,963"), ("star", "POINTS", "2,857")]


def sc_cards(lt):
    L = layer()
    out = e_in(c01((lt - 2.5) / 0.3), 2)
    for k, (ic, lab, val) in enumerate(CARDS):
        p = e_out((lt - 0.05 - k * 0.16) / 0.55)
        if p <= 0:
            continue
        cy = 640 + k * 250 - out * (300 + k * 60)
        sc = lerp(0.75, 1.0, p)
        card = Image.new("RGBA", (880, 210), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        hi = k == 2 and lt > 1.55
        hp = e_out((lt - 1.55) / 0.4) if hi else 0
        border = tuple(int(lerp(70, BLUE[j], hp)) for j in range(3))
        cd.rounded_rectangle((2, 2, 877, 207), radius=40, fill=(16, 17, 22, 255), outline=border + (255,), width=3)
        cd.ellipse((40, 45, 160, 165), fill=(30, 32, 40, 255))
        draw_icon(cd, ic, 100, 105, 1.25, (225, 228, 238))
        tracked(card, lab, 200, 70, 30, "Bold", DIM, 10, anchor_x="left")
        num = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        odometer(num, val, 380 + 0, 300, 112, c01((lt - 0.25 - k * 0.16) / 1.1), "Black", WHITE)
        bb = num.getbbox()
        if bb:
            numc = num.crop((bb[0], 300 - 70, bb[2], 300 + 70))
            card.alpha_composite(numc, (200, 70))
        if hi:
            tag = Image.new("RGBA", card.size, (0, 0, 0, 0))
            tracked(tag, "NHL RECORD", 860 - text_size("NHL RECORD", 26, "ExtraBold", 6) - 30, 70, 26, "ExtraBold", BLUE, 6,
                    anchor_x="left", alpha=hp)
            card.alpha_composite(tag)
        cw, ch = int(880 * sc), int(210 * sc)
        card = card.resize((cw, ch), Image.BILINEAR)
        blur = (1 - p) * 10 + out * 8
        if blur > 0.5:
            card = card.filter(ImageFilter.GaussianBlur(blur))
        a = p * (1 - out)
        card.putalpha(card.getchannel("A").point(lambda v: int(v * a)))
        if hi:
            gl = layer()
            gl.alpha_composite(card, (int(W / 2 - cw / 2), int(cy - ch / 2)))
            glow_onto(L, gl, 50, 0.9 * hp)
        else:
            L.alpha_composite(card, (int(W / 2 - cw / 2), int(cy - ch / 2)))
    head = layer()
    tracked(head, "CAREER", W / 2, 400, 40, "Bold", WHITE, 22,
            per_letter=lambda i, n: (0, 40 * (1 - e_out((lt - i * 0.03) / 0.4)), e_out((lt - i * 0.03) / 0.4) * (1 - out)))
    L.alpha_composite(masked(head, (0, 350, W, 445)))
    return L


def chrome_cup(alpha):
    """Stanley-Cup-Silhouette mit Chrom-Verlauf und feiner Kontur."""
    mask_l = layer()
    draw_icon(ImageDraw.Draw(mask_l), "cup", W / 2, 960, 8.2, (255, 255, 255))
    a = np.asarray(mask_l.getchannel("A")).astype(np.float32)
    ys = np.arange(H, dtype=np.float32)[:, None]
    xs = np.arange(W, dtype=np.float32)[None, :]
    band = 0.5 + 0.5 * np.cos((xs - W / 2) / 70.0)          # senkrechte Glanzstreifen
    v = 150 + 90 * band - 0.03 * (ys - 600)
    rgb = np.stack([v, v + 4, v + 14], -1)
    out = np.dstack([np.clip(rgb, 0, 255), a * alpha]).astype(np.uint8)
    cup = Image.fromarray(out, "RGBA")
    edge = mask_l.filter(ImageFilter.FIND_EDGES)
    edge.putalpha(edge.getchannel("A").point(lambda v_: int(min(255, v_ * 2) * alpha)))
    cup.alpha_composite(edge)
    return cup


_PART = None


def particle_sets():
    global _PART
    if _PART is None:
        rng = np.random.default_rng(7)
        m1 = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m1).text((W / 2, 900), "99", font=font("Black", 640), fill=255, anchor="mm")
        m2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw_icon(ImageDraw.Draw(m2), "cup", W / 2, 960, 8.2, (255, 255, 255))
        a1 = np.argwhere(np.asarray(m1)[::3, ::3] > 128) * 3
        a2 = np.argwhere(np.asarray(m2.getchannel("A"))[::3, ::3] > 128) * 3
        n = 2600
        p1 = a1[rng.choice(len(a1), n)][:, ::-1].astype(np.float32)
        p2 = a2[rng.choice(len(a2), n)][:, ::-1].astype(np.float32)
        # grob nach Höhe sortieren -> weniger Chaos, schönere Wirbel
        p1 = p1[np.argsort(p1[:, 1] + rng.normal(0, 60, n))]
        p2 = p2[np.argsort(p2[:, 1] + rng.normal(0, 60, n))]
        _PART = (p1, p2, rng.uniform(0.7, 1.3, n), rng.uniform(-1, 1, n))
    return _PART


def sc_99(lt):
    L = layer()
    p1, p2, spd, side = particle_sets()
    t_burst, t_form = 0.75, 1.75
    if lt < t_burst + 0.05:
        a = e_out(lt / 0.35)
        sc_ = lerp(1.25, 1.0, e_out(lt / 0.6))
        chrome = layer()
        gradient_text(chrome, "99", W / 2, 900, int(640 * sc_), "Black", (255, 255, 255), (130, 140, 160), (245, 248, 255), alpha=a)
        light_sweep(chrome, c01((lt - 0.2) / 0.5))
        glow_onto(L, chrome, 30, 0.5)
    if lt >= t_burst:
        e = e_io(c01((lt - t_burst) / (t_form - t_burst)) * 0.999)
        center = np.array([W / 2, 930], np.float32)
        lp = p1 + (p2 - p1) * e
        theta = math.sin(math.pi * e) * 2.4
        rel = lp - center
        rot = np.stack([rel[:, 0] * math.cos(theta) - rel[:, 1] * math.sin(theta),
                        rel[:, 0] * math.sin(theta) + rel[:, 1] * math.cos(theta)], -1)
        expand = 1 + 0.55 * math.sin(math.pi * e) * spd
        pos = center + rot * expand[:, None]
        pos[:, 0] += side * 90 * math.sin(math.pi * e)
        fade_out = 1 - e_out(c01((lt - t_form - 0.15) / 0.4))
        pl = layer()
        pd = ImageDraw.Draw(pl)
        mixc = math.sin(math.pi * e)
        col = tuple(int(lerp(WHITE[j], BLUE[j], mixc)) for j in range(3))
        r = 2.6
        for x, y in pos:
            pd.ellipse((x - r, y - r, x + r, y + r), fill=col + (int(235 * fade_out),))
        glow_onto(L, pl, 18, 1.3)
        if lt > t_form - 0.1:
            cp = e_out((lt - t_form + 0.1) / 0.45)
            cup = chrome_cup(cp)
            light_sweep(cup, c01((lt - t_form - 0.1) / 0.6))
            red = layer()
            ImageDraw.Draw(red).ellipse((W / 2 - 330, 600, W / 2 + 330, 1330), fill=RED + (int(170 * cp),))
            glow_onto(L, red, 180, 3.2, keep=False)
            glow_onto(L, cup, 40, 0.5)
            lab = layer()
            odometer(lab, "4", W / 2 - 190, 1490, 150, c01((lt - t_form) / 0.6), "Black", WHITE)
            tracked(lab, "× STANLEY CUP", W / 2 - 120, 1490, 60, "ExtraBold", WHITE, 6, anchor_x="left",
                    per_letter=lambda i, n: (0, 0, e_out((lt - t_form - 0.15 - i * 0.03) / 0.3)))
            L.alpha_composite(lab)
    return L


TROPHIES = [("9×", "HART TROPHIES", "LEAGUE MVP"), ("10×", "ART ROSS", "SCORING TITLES"), ("#99", "RETIRED", "BY THE ENTIRE NHL")]


def sc_trophies(lt):
    L = layer()
    d = ImageDraw.Draw(L)
    out = e_in(c01((lt - 1.75) / 0.25), 2)
    head = layer()
    tracked(head, "TROPHY CASE", W / 2, 520, 40, "Bold", WHITE, 22,
            per_letter=lambda i, n: (0, 40 * (1 - e_out((lt - i * 0.03) / 0.4)), e_out((lt - i * 0.03) / 0.4)))
    L.alpha_composite(masked(head, (0, 470, W, 565)))
    for k, (big, l1, l2) in enumerate(TROPHIES):
        y = 760 + k * 250
        lp = e_io((lt - 0.1 - k * 0.15) / 0.5)
        d.rectangle((90, y - 110, 90 + 900 * lp, y - 108), fill=(70, 80, 100, 255))
        row = layer()
        tracked(row, big, 100, y, 150, "Black", BLUE if k != 2 else ORANGE, 0, anchor_x="left",
                per_letter=lambda i, n: (0, 170 * (1 - e_out((lt - 0.25 - k * 0.15 - i * 0.04) / 0.5)), 1))
        masked(row, (0, y - 105, W, y + 90))
        tracked(row, l1, 470, y - 22, 46, "ExtraBold", WHITE, 4, anchor_x="left",
                per_letter=lambda i, n: (0, 0, e_out((lt - 0.4 - k * 0.15 - i * 0.02) / 0.3)))
        tracked(row, l2, 470, y + 32, 28, "SemiBold", DIM, 6, anchor_x="left",
                per_letter=lambda i, n: (0, 0, e_out((lt - 0.55 - k * 0.15 - i * 0.015) / 0.3)))
        L.alpha_composite(row)
    if out > 0:
        L.putalpha(L.getchannel("A").point(lambda v: int(v * (1 - out))))
    return L


def sc_end(lt):
    L = layer()
    wipe = e_io(lt / 0.7)
    word = layer()
    tracked(word, "THE GREAT ONE", W / 2, 900, 112, "Black", WHITE, 4)
    light_sweep(word, c01((lt - 0.6) / 0.7))
    tot = text_size("THE GREAT ONE", 112, "Black", 4)
    x0 = W / 2 - tot / 2 - 10
    masked(word, (0, 0, x0 + (tot + 20) * wipe, H))
    glow_onto(L, word, 30, 0.45)
    d = ImageDraw.Draw(L)
    if wipe < 1:
        xw = x0 + (tot + 20) * wipe
        d.rectangle((xw - 2, 820, xw + 2, 980), fill=BLUE + (255,))
    lw = 300 * e_io((lt - 0.5) / 0.5)
    d.rectangle((W / 2 - lw / 2, 1000, W / 2 + lw / 2, 1003), fill=BLUE + (255,))
    sub = layer()
    tracked(sub, "@BLADESANDPUCKS", W / 2, 1060, 30, "SemiBold", DIM, 12,
            per_letter=lambda i, n: (0, 0, e_out((lt - 0.8 - i * 0.02) / 0.3)))
    L.alpha_composite(sub)
    return L


SCENES = [(0.0, 3.2, sc_title), (3.2, 6.4, sc_bars), (6.4, 9.2, sc_cards),
          (9.2, 11.6, sc_99), (11.6, 13.6, sc_trophies), (13.6, 16.0, sc_end)]
XF = 0.28   # Überblendzeit (Zoom-through)


def comp(t):
    img = background(t)
    for a, b, fn in SCENES:
        if a - XF <= t < b + XF:
            lt = t - a
            L = fn(max(0.0, lt))
            # Zoom-through: raus = größer + blasser, rein = aus etwas kleiner
            s, al = 1.0, 1.0
            if t > b - XF and b < DUR:
                q = e_in(c01((t - (b - XF)) / (2 * XF)), 2)
                s, al = 1 + 0.35 * q, 1 - q
            if t < a + XF and a > 0:
                q = e_out(c01((t - (a - XF)) / (2 * XF)), 3)
                s, al = 0.86 + 0.14 * q, q
            if al <= 0.01:
                continue
            if abs(s - 1) > 0.002:
                big = L.resize((int(W * s), int(H * s)), Image.BILINEAR)
                if s > 1:
                    ox, oy = (big.width - W) // 2, (big.height - H) // 2
                    L = big.crop((ox, oy, ox + W, oy + H))
                else:
                    L2 = layer()
                    L2.alpha_composite(big, ((W - big.width) // 2, (H - big.height) // 2))
                    L = L2
            if al < 1:
                L.putalpha(L.getchannel("A").point(lambda v: int(v * al)))
            img.alpha_composite(L)
    return img


# ================================================================= POV-Rahmen + Kamerafahrt
_POVSTATIC = None


def pov_frame(t, comp_img):
    global _POVSTATIC
    if _POVSTATIC is None:
        _POVSTATIC = pov.build_static()
    img = _POVSTATIC.copy()
    d = ImageDraw.Draw(img)
    px = 300 + (W - 300) * t / DUR
    d.rectangle((300, 1086, px, 1092), fill=(90, 160, 255))
    d.line((px, 1086, px, 1300), fill=(90, 160, 255), width=2)
    d.polygon([(px - 6, 1086), (px + 6, 1086), (px, 1095)], fill=(90, 160, 255))
    v = pov.VIEW
    d.rectangle(v, fill=(44, 44, 48))          # Pasteboard
    x0, y0, x1, y1 = COMP_IN_VIEW
    img.paste(comp_img.convert("RGB").resize((x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0))
    glare = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glare).polygon([(0, 410), (420, 410), (180, 1300), (0, 1300)], fill=(255, 255, 255, 8))
    img.alpha_composite(glare)
    pov.caption(img)
    return img


def zoom_amount(t):
    if t < 0.5:
        return 0.0
    if t < 1.4:
        return e_io((t - 0.5) / 0.9)
    if t < 14.15:
        return 1.0
    if t < 15.0:
        return 1 - e_io((t - 14.15) / 0.85)
    return 0.0


def render_t(t):
    c = comp(t)
    z = zoom_amount(t)
    if z >= 0.999:
        out = c.convert("RGB")
    else:
        pv = pov_frame(t, c)
        # Handkamera nur in der POV-Totale
        hz = 1.03 + 0.008 * math.sin(t * 0.7)
        hx = math.sin(t * 1.3) * 5 * (1 - z)
        hy = math.cos(t * 1.1) * 4 * (1 - z)
        full = (W / 2 - W / (2 * hz) + hx, H / 2 - H / (2 * hz) + hy, W / 2 + W / (2 * hz) + hx, H / 2 + H / (2 * hz) + hy)
        r = tuple(lerp(full[i], COMP_IN_VIEW[i], z) for i in range(4))
        sc = W / (r[2] - r[0])
        out = pv.transform((W, H), Image.EXTENT, r, Image.BILINEAR).convert("RGBA")
        # native (scharfe) Komposition an die richtige Stelle legen
        cx0 = (COMP_IN_VIEW[0] - r[0]) * sc
        cy0 = (COMP_IN_VIEW[1] - r[1]) * sc
        cw = (COMP_IN_VIEW[2] - COMP_IN_VIEW[0]) * sc
        ch = (COMP_IN_VIEW[3] - COMP_IN_VIEW[1]) * sc
        if cw > 300:
            out.paste(c.resize((int(round(cw)), int(round(ch))), Image.BILINEAR).convert("RGBA"), (int(round(cx0)), int(round(cy0))))
        out = out.convert("RGB")
    return out


def is_fast(t):
    if 0.5 < t < 1.45 or 14.1 < t < 15.05:
        return True
    return any(abs(t - b) < XF for b in (3.2, 6.4, 9.2, 11.6, 13.6))


def render_frame(i):
    t = i / FPS
    if is_fast(t):
        acc = None
        for dt in (-1 / 90, 0, 1 / 90):     # 3 Unterbilder = Bewegungsunschärfe
            a = np.asarray(render_t(max(0, t + dt))).astype(np.float32)
            acc = a if acc is None else acc + a
        arr = acc / 3
    else:
        arr = np.asarray(render_t(t)).astype(np.float32)
    # Körnung + Vignette
    rng = np.random.default_rng(i)
    arr += rng.normal(0, 3.2, arr.shape[:2])[..., None]
    return np.clip(arr, 0, 255).astype(np.uint8).tobytes()


# ================================================================= Sounddesign
SR = 44100


def make_audio(path):
    n = int(DUR * SR)
    out = np.zeros(n)
    rng = np.random.default_rng(11)

    def add(sig, at, vol=1.0):
        s = int(at * SR)
        e = min(n, s + len(sig))
        if 0 <= s < n:
            out[s:e] += sig[: e - s] * vol

    def tt(sec):
        return np.arange(int(sec * SR)) / SR

    # Riser in den Bildschirm
    rt = tt(1.4)
    riser = rng.standard_normal(len(rt))
    riser = np.convolve(riser, np.ones(20) / 20, mode="same") * (rt / 1.4) ** 2.5 * 0.6
    riser += np.sin(2 * np.pi * (200 + 900 * (rt / 1.4) ** 2) * rt) * (rt / 1.4) ** 3 * 0.12
    add(riser, 0.0)
    # Sub-Drop / Impact beim Eintauchen
    it = tt(1.2)
    impact = np.sin(2 * np.pi * (32 + 70 * np.exp(-it * 9)) * it) * np.exp(-it * 2.6) * 0.9
    impact += rng.standard_normal(len(it)) * np.exp(-it * 30) * 0.35
    add(impact, 1.4)
    add(impact * 0.55, 10.95)  # Pokal formt sich
    # Beat (110 bpm) ab dem Eintauchen
    beat = 60 / 110
    kt = tt(0.3)
    kick = np.sin(2 * np.pi * (42 + 120 * np.exp(-kt * 32)) * kt) * np.exp(-kt * 9)
    ht = tt(0.05)
    hat = np.diff(rng.standard_normal(len(ht)), prepend=0) * np.exp(-ht * 80) * 0.12
    ct = tt(0.2)
    clap = np.convolve(rng.standard_normal(len(ct)), np.ones(3) / 3, mode="same") * np.exp(-ct * 24) * 0.25
    bass_notes = [55.0, 55.0, 43.65, 49.0]
    k, t0 = 0, 1.4
    while t0 + k * beat < 14.6:
        at = t0 + k * beat
        add(kick, at, 0.8)
        add(hat, at + beat / 2)
        if k % 2:
            add(clap, at)
        f = bass_notes[(k // 4) % 4]
        bt = tt(beat)
        saw = 2 * ((f * bt) % 1) - 1
        add(np.convolve(saw, np.ones(30) / 30, mode="same") * np.exp(-bt * 2) * 0.35, at)
        k += 1
    # Whooshes an den Übergängen + beim Rauszoomen
    wt = tt(0.55)
    wn = np.convolve(rng.standard_normal(len(wt)), np.ones(35) / 35, mode="same")
    whoosh = wn * np.sin(np.pi * wt / wt[-1]) ** 2 * 0.9
    for at in (2.95, 6.15, 8.95, 11.35, 13.35, 14.15):
        add(whoosh, at)
    # Ticks beim Hochzählen
    tk = tt(0.02)
    tick = np.sin(2 * np.pi * 3200 * tk) * np.exp(-tk * 300) * 0.12
    for start, dur, cnt in ((1.1, 1.35, 22), (4.6, 0.8, 12), (6.65, 1.1, 16), (10.95, 0.6, 6)):
        for j in range(cnt):
            add(tick, start + dur * (j / cnt) ** 0.6)
    # Partikel-Schimmer
    st = tt(1.1)
    sh = rng.standard_normal(len(st))
    sh = (sh - np.convolve(sh, np.ones(5) / 5, mode="same")) * np.sin(np.pi * st / st[-1]) * 0.18
    add(sh, 9.95)
    # Pad unter allem
    pt = tt(DUR)
    pad = sum(np.sin(2 * np.pi * f * pt) for f in (110, 164.81, 220, 277.18)) * 0.025
    out += pad * np.minimum(pt / 1.0, 1)
    fade = np.clip((DUR - np.arange(n) / SR) / 0.5, 0, 1)
    out *= fade
    out /= max(1e-6, np.max(np.abs(out))) * 1.1
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((out * 32767).astype(np.int16).tobytes())


def main():
    os.chdir(HERE)
    make_audio("audio_studio.wav")
    nf = int(DUR * FPS)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_studio.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
           "reel10_studio.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(4) as pool:
        for k, buf in enumerate(pool.imap(render_frame, range(nf), chunksize=4)):
            proc.stdin.write(buf)
            if k % 60 == 0:
                print(f"{k}/{nf}", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.frombytes("RGB", (W, H), render_frame(int(5.2 * FPS))).save("reel10_thumbnail.jpg", quality=92)
    print("fertig: reel10_studio.mp4")


if __name__ == "__main__":
    main()
