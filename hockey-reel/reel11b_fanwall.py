"""Reel 11b: FAN WALL #1 – Spektakel-Version (Brad Marchand für @mrnobbbe).

Ablauf (16 s, Schnittraster 0,4 s = 150 BPM halbe Zeit):
  0.0–1.0   Hook: Kommentar-Karte + Stempel "REQUEST ACCEPTED"
  1.0–4.4   Arena: rotierender 3D-Videowürfel, Suchscheinwerfer, FAN WALL #1 -> @name -> 63,
            Pyro-Drop bei 3.4 ("Number sixty-three!")
  4.4–5.0   Kameraflug in den Würfel
  5.0–8.2   Spieler-Reveal: Freisteller, Riesen-63, Lauftext, Lichtstrahlen ("Brad Marchand!")
  8.2–10.6  Draft: Zähler 1 -> 71 mit Draft-Board (70 Picks vor ihm)
  10.6–13.0 2x Stanley Cup: Feuerwerk + Konfetti ("Two-time Stanley Cup champion!")
  13.0–16.0 Zurück in die Arena: WHO'S NEXT? + Call-to-Action
Stimme: vidIQ-Voiceover (Adam) mit Hallen-Hall. Foto: Lisa Gansky, CC BY-SA 2.0 (Wikimedia Commons),
Freisteller: prep_marchand_cut.py.
Aufruf: python3 reel11b_fanwall.py  ->  reel11b_fanwall.mp4
"""
import math
import os
import random
import subprocess
import wave
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter
from scipy.signal import fftconvolve

import make_hockey_reel as m
import reel3_cup_day as r3
import reel10_studio as s
import reel11_fanwall as r11
from make_hockey_reel import font
from reel10_studio import (W, H, BLUE, ORANGE, RED, WHITE, DIM, c01, e_io, e_out, e_in, e_back, lerp,
                           layer, glow_onto, tracked, masked, light_sweep, gradient_text, chrome_cup)

FPS = 30
DUR = 16.0
HERE = m.HERE
NAME = "mrnobbbe"
COMMENT = "Do Brad Marchand"
GOLD = (255, 196, 70)
ICEW = (220, 232, 255)
CREDIT = "Photo: Lisa Gansky / CC BY-SA 2.0"
r3.VOICE = os.path.join(HERE, "voice", "reel11b.mp3")
VOICE_AT = [1.3, 3.45, 5.02, 10.72]       # Ladies and gentlemen / Number 63 / Brad Marchand / 2x champion
IMPACTS = [(0.55, 1.0), (3.4, 1.0), (5.0, 1.3), (9.4, 0.8), (10.8, 0.9), (13.0, 0.5)]
Q = 4
QW, QH = W // Q, H // Q
QYY, QXX = np.mgrid[0:QH, 0:QW].astype(np.float32)


# ================================================================= Grundbausteine
def qcanvas():
    return np.zeros((QH, QW, 3), np.float32)


def to_arr(img, addq=None):
    arr = np.asarray(img.convert("RGB")).astype(np.float32)
    if addq is not None:
        up = Image.fromarray(np.clip(addq, 0, 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)
        arr += np.asarray(up).astype(np.float32)
    return arr


def add_light(img, addq):
    """Additives Licht (Viertelauflösung) in ein Bild einrechnen – hinter später darübergelegte Ebenen."""
    up = Image.fromarray(np.clip(addq, 0, 255).astype(np.uint8)).resize((W, H), Image.BILINEAR).convert("RGBA")
    addq[:] = 0
    return ImageChops.add(img, up)


def zoom_arr(arr, z):
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    if z >= 1:
        w2, h2 = W / z, H / z
        im = im.transform((W, H), Image.EXTENT, ((W - w2) / 2, (H - h2) / 2, (W + w2) / 2, (H + h2) / 2), Image.BILINEAR)
    else:
        small = im.resize((int(W * z), int(H * z)), Image.BILINEAR)
        im = Image.new("RGB", (W, H), (6, 8, 14))
        im.paste(small, ((W - small.width) // 2, (H - small.height) // 2))
    return np.asarray(im).astype(np.float32)


def put_img(lay, im, x, y):
    """alpha_composite, das auch über die Ränder hinaus platzieren darf."""
    x, y = int(x), int(y)
    sx, sy = max(0, -x), max(0, -y)
    ex, ey = min(im.width, lay.width - x), min(im.height, lay.height - y)
    if sx >= ex or sy >= ey:
        return
    lay.alpha_composite(im.crop((sx, sy, ex, ey)), (x + sx, y + sy))


def scale_layer(lay, sc, cx, cy):
    """Ebene um (cx, cy) skalieren."""
    if abs(sc - 1) < 0.003:
        return lay
    big = lay.resize((max(1, int(W * sc)), max(1, int(H * sc))), Image.BILINEAR)
    out = layer()
    put_img(out, big, cx - cx * sc, cy - cy * sc)
    return out


def fade_layer(lay, a):
    if a >= 0.999:
        return lay
    lay.putalpha(lay.getchannel("A").point(lambda v: int(v * max(0.0, a))))
    return lay


def ring(d, cx, cy, lt, dur=0.45, rmax=800, col=WHITE, width=14):
    if not 0 <= lt < dur:
        return
    p = lt / dur
    r = 40 + rmax * e_out(p, 3)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col + (int(230 * (1 - p) ** 1.5),),
              width=max(2, int(width * (1 - p))))


def beams(addq, t, specs, gain=1.0):
    """Suchscheinwerfer als additives Licht (Viertelauflösung)."""
    for bx, by, sp, ph, amp, base, col, wdt, strength in specs:
        ang = base + math.sin(t * sp + ph) * amp
        L = 700
        tip = (bx + math.sin(ang) * L, by + math.cos(ang) * L)
        nx, ny = math.cos(ang) * wdt, -math.sin(ang) * wdt
        mk = Image.new("L", (QW, QH), 0)
        ImageDraw.Draw(mk).polygon([(bx - 2, by), (bx + 2, by), (tip[0] + nx, tip[1] + ny), (tip[0] - nx, tip[1] - ny)], fill=255)
        a = np.asarray(mk.filter(ImageFilter.GaussianBlur(4))).astype(np.float32) / 255
        fall = np.exp(-np.sqrt((QXX - bx) ** 2 + (QYY - by) ** 2) / 420)
        addq += (a * fall)[..., None] * np.array(col, np.float32) * strength * gain


TOP_BEAMS = [(30, -6, 0.8, 0.0, 0.35, 0.28, BLUE, 42, 0.30), (100, -6, 0.6, 1.7, 0.40, -0.10, ICEW, 34, 0.22),
             (170, -6, 0.7, 3.1, 0.40, 0.10, ICEW, 34, 0.22), (240, -6, 0.9, 4.2, 0.35, -0.28, BLUE, 42, 0.30)]
LOW_BEAMS = [(0, QH + 6, 0.5, 0.3, 0.25, math.pi - 0.45, BLUE, 46, 0.22),
             (QW, QH + 6, 0.55, 2.0, 0.25, math.pi + 0.45, BLUE, 46, 0.22)]
DROP_BEAMS = [(60, QH + 6, 1.6, 0.0, 0.35, math.pi - 0.3, ORANGE, 40, 0.35),
              (QW - 60, QH + 6, 1.4, 1.0, 0.35, math.pi + 0.3, ORANGE, 40, 0.35)]


def flare(addq, x, y, strength, col=(120, 200, 255)):
    qx, qy = x / Q, y / Q
    streak = np.exp(-((QYY - qy) / 1.3) ** 2) * np.exp(-np.abs(QXX - qx) / 110)
    core = np.exp(-((QXX - qx) ** 2 + (QYY - qy) ** 2) / 80)
    addq += (streak[..., None] * np.array(col, np.float32) + core[..., None] * 255) * strength


_RAYGRID = {}


def rays(addq, lt, cx, cy, strength, col=BLUE):
    key = (cx, cy)
    if key not in _RAYGRID:
        _RAYGRID[key] = (np.arctan2(QYY - cy / Q, QXX - cx / Q), np.sqrt((QXX - cx / Q) ** 2 + (QYY - cy / Q) ** 2))
    ang, r = _RAYGRID[key]
    v = (0.5 + 0.5 * np.cos(ang * 11 + lt * 0.45)) ** 6 * np.exp(-r / 190) * (1 - np.exp(-r / 12))
    addq += v[..., None] * np.array(col, np.float32) * strength


def sparks(d, lt, emitters, seed, n=60, spread=0.55, speed=(700, 1500), grav=2200, life=(0.5, 1.1),
           window=0.5, col=(255, 214, 150), width=3):
    rng = random.Random(seed)
    for ox, oy in emitters:
        for _ in range(n):
            t0, ang = rng.uniform(0, window), -math.pi / 2 + rng.uniform(-spread, spread)
            sp, lf = rng.uniform(*speed), rng.uniform(*life)
            tau = lt - t0
            if tau < 0 or tau > lf:
                continue
            vx, vy = math.cos(ang) * sp, math.sin(ang) * sp
            x1, y1 = ox + vx * tau, oy + vy * tau + 0.5 * grav * tau * tau
            u = max(0.0, tau - 0.035)
            x0, y0 = ox + vx * u, oy + vy * u + 0.5 * grav * u * u
            d.line((x0, y0, x1, y1), fill=col + (int(255 * (1 - tau / lf) ** 0.7),), width=width)


def embers(d, lt, seed=9, n=60):
    rng = random.Random(seed)
    for _ in range(n):
        x0, y0, vy = rng.uniform(0, W), rng.uniform(300, H + 300), rng.uniform(60, 190)
        sw, ph, r = rng.uniform(10, 40), rng.uniform(0, 6.28), rng.uniform(1.5, 4.2)
        col = rng.choice((BLUE, ORANGE, WHITE))
        y, x = y0 - vy * lt, x0 + math.sin(lt * 1.5 + ph) * sw
        a = int(170 * (0.5 + 0.5 * math.sin(lt * 4 + ph)))
        d.ellipse((x - r, y - r, x + r, y + r), fill=col + (a,))


CONF_COLS = [BLUE, ORANGE, WHITE, GOLD, (255, 80, 110)]


def confetti(d, lt, n=140, seed=5, speed=1.0):
    rng = random.Random(seed)
    for _ in range(n):
        x0, y0, vy = rng.uniform(-40, W + 40), rng.uniform(-1000, -40), rng.uniform(300, 540) * speed
        sw, fr, ph = rng.uniform(20, 60), rng.uniform(1.5, 3.5), rng.uniform(0, 6.28)
        rot, rs, flip = rng.uniform(0, 6.28), rng.uniform(-6, 6), rng.uniform(5, 11)
        col, w_, h_ = rng.choice(CONF_COLS), rng.uniform(12, 20), rng.uniform(22, 34)
        y = y0 + vy * lt
        if y < -60 or y > H + 60:
            continue
        x = x0 + math.sin(lt * fr + ph) * sw
        a, fl = rot + rs * lt, math.cos(lt * flip + ph)
        hw, hh = w_ / 2, h_ / 2 * max(0.08, abs(fl))
        ca, sa = math.cos(a), math.sin(a)
        pts = [(x + ca * px - sa * py, y + sa * px + ca * py) for px, py in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]
        sh = 1.0 if fl > 0 else 0.62
        d.polygon(pts, fill=tuple(int(c * sh) for c in col) + (255,))


# ================================================================= LED-Würfel (echtes 3D)
LED_W, LED_H = 200, 112
FACE_W, TOP_B, SCR_H, BOT_B = 800, 56, 448, 84
FACE_H = TOP_B + SCR_H + BOT_B
HALF = FACE_W / 2
FOCAL = 1500
TICKER = "  FAN WALL  •  BLADESANDPUCKS  •  COMMENT YOUR PLAYER  •"
_DOT = {}


def led_text(img, xy, txt, size, col, weight="Black", alpha=1.0):
    ImageDraw.Draw(img).text(xy, txt, font=font(weight, size), fill=tuple(int(c * alpha) for c in col), anchor="mm")


def fit(txt, weight, size, maxw):
    while size > 10 and font(weight, size).getlength(txt) > maxw:
        size -= 1
    return size


def led_arena(ta):
    """LED-Inhalt während der Arena-Szene (ta = Zeit seit 1.0 s)."""
    img = Image.new("RGB", (LED_W, LED_H), (0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = LED_W / 2, LED_H / 2
    if ta < 1.0:
        led_text(img, (cx, cy - 10), "FAN WALL", 36, WHITE)
        led_text(img, (cx, cy + 28), "#1", 22, BLUE)
        d.rectangle((LED_W * e_io((ta - 0.1) / 0.45), 0, LED_W, LED_H), fill=(0, 0, 0))
        if ta > 0.55 and int(ta * 8) % 2 == 0:
            d.rectangle((2, 2, LED_W - 3, LED_H - 3), outline=BLUE)
    elif ta < 2.4:
        lt = ta - 1.0
        led_text(img, (cx, cy - 24), "REQUESTED BY", 18, (200, 205, 215), "ExtraBold", e_out(lt / 0.25))
        name = "@" + NAME.upper()
        f = font("Black", fit(name, "Black", 30, LED_W - 16))
        x = cx - f.getlength(name) / 2
        for i, ch in enumerate(name):
            p = c01((lt - 0.2 - i * 0.045) / 0.12)
            if p > 0:
                d.text((x, cy + 14), ch, font=f, fill=tuple(int(lerp(255, c, p)) for c in ORANGE), anchor="lm")
            x += f.getlength(ch)
    else:
        lt = ta - 2.4
        led_text(img, (cx, cy - 36), "NUMBER", 16, WHITE, alpha=e_out(lt / 0.2))
        col = BLUE if int(lt * 7.5) % 2 == 1 else WHITE
        led_text(img, (cx, cy + 12), "63", 86, col, alpha=e_out((lt - 0.03) / 0.12))
    return img


def led_next(tg):
    img = Image.new("RGB", (LED_W, LED_H), (0, 0, 0))
    led_text(img, (LED_W / 2, 17), "FAN WALL #2", 15, BLUE, "ExtraBold")
    led_text(img, (LED_W / 2, 50), "WHO'S", 34, WHITE)
    led_text(img, (LED_W / 2, 89), "NEXT?", 38, ORANGE if int(tg * 3) % 2 == 0 else WHITE)
    return img


def led_screen_img(led_img, cell):
    w, h = LED_W * cell, LED_H * cell
    if cell not in _DOT:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        dx, dy = (xx % cell) - (cell - 1) / 2, (yy % cell) - (cell - 1) / 2
        _DOT[cell] = np.clip(cell * 0.55 - np.sqrt(dx * dx + dy * dy), 0, 1)[..., None]
    big = np.asarray(led_img.resize((w, h), Image.NEAREST)).astype(np.float32)
    out = big * _DOT[cell] * 1.2 + big * 0.12 + 5
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).convert("RGBA")


def face_texture(t, led_img, hi=False):
    k = 2 if hi else 1
    tex = Image.new("RGBA", (FACE_W * k, FACE_H * k), (22, 24, 32, 255))
    d = ImageDraw.Draw(tex)
    for i in range(16):
        on = (int(t * 10) + i) % 4 != 0
        cx = (25 + i * 50) * k
        d.ellipse((cx - 6 * k, 22 * k, cx + 6 * k, 34 * k), fill=(255, 220, 120, 255) if on else (70, 60, 36, 255))
    tex.paste(led_screen_img(led_img, 4 * k), (0, TOP_B * k))
    f = font("ExtraBold", 34)
    unit = f.getlength(TICKER)
    band = Image.new("RGB", (FACE_W, BOT_B - 16), (0, 0, 0))
    ImageDraw.Draw(band).text((-((t * 170) % unit), (BOT_B - 16) / 2), TICKER * 3, font=f, fill=ORANGE, anchor="lm")
    if hi:
        band = band.resize((band.width * 2, band.height * 2), Image.BILINEAR)
    tex.paste(band, (0, (TOP_B + SCR_H + 8) * k))
    return tex


def persp_coeffs(dst, src):
    A, B = [], []
    for (x, y), (X, Y) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -X * x, -X * y])
        B.append(X)
        A.append([0, 0, 0, x, y, 1, -Y * x, -Y * y])
        B.append(Y)
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()


def draw_cube(lay, t, led_img, Zc, yaw, cy, Yc=-520.0, hi=False):
    """Vierseitiger Videowürfel, perspektivisch projiziert (Kamera im Ursprung, Blick +z)."""
    py = cy - FOCAL * Yc / Zc

    def P(x, y, z):
        return (W / 2 + FOCAL * x / z, py + FOCAL * y / z)

    hh = FACE_H / 2
    faces, bottom, tops = [], [], []
    for k in range(4):
        th = yaw + k * math.pi / 2
        nx, nz = math.sin(th), -math.cos(th)
        tx, tz = math.cos(th), math.sin(th)
        fx, fz = HALF * nx, Zc + HALF * nz
        bottom.append(P(fx - HALF * tx, Yc + hh, fz - HALF * tz))
        tops.append(P(fx - HALF * tx, Yc - hh, fz - HALF * tz))
        vis = -(nx * fx + nz * fz)
        if vis <= 0:
            continue
        c3 = [(fx - HALF * tx, Yc - hh, fz - HALF * tz), (fx + HALF * tx, Yc - hh, fz + HALF * tz),
              (fx + HALF * tx, Yc + hh, fz + HALF * tz), (fx - HALF * tx, Yc + hh, fz - HALF * tz)]
        if min(c[2] for c in c3) < 25:
            continue
        faces.append((fz, vis / math.sqrt(fx * fx + Yc * Yc + fz * fz), [P(*c) for c in c3]))
    d = ImageDraw.Draw(lay)
    for x, y in tops:                                   # Seile zum Hallendach
        d.line((x, y, x + (x - W / 2) * 0.12, -20), fill=(58, 64, 80, 255), width=3)
    if Yc + hh < -5:
        d.polygon(bottom, fill=(15, 16, 22, 255), outline=(46, 50, 66, 255))
    tex = face_texture(t, led_img, hi)
    for fz, cosv, quad in sorted(faces, key=lambda f_: -f_[0]):
        pw = max(math.dist(quad[0], quad[1]), math.dist(quad[3], quad[2]))
        sc = pw / tex.width * 1.15
        src = tex if sc > 0.9 else tex.resize((max(8, int(tex.width * sc)), max(8, int(tex.height * sc))), Image.BOX)
        shade = 0.3 + 0.7 * c01(cosv) ** 0.6
        if shade < 0.99:
            src = Image.blend(src, Image.new("RGBA", src.size, (0, 0, 0, 255)), 1 - shade)
        sw, sh = src.size
        coeffs = persp_coeffs(quad, [(0, 0), (sw, 0), (sw, sh), (0, sh)])
        lay.alpha_composite(src.transform((W, H), Image.PERSPECTIVE, coeffs, Image.BILINEAR))


def arena_frame(t, tilt, Zc, yaw, cy, led_img, Yc=-520.0, beam_gain=1.0):
    bg = r11.arena_static()
    oy = int(380 * tilt)
    img = bg.crop((0, oy, W, oy + H)).copy()
    addq = qcanvas()
    beams(addq, t, TOP_BEAMS, beam_gain)
    beams(addq, t, LOW_BEAMS, beam_gain)
    img = add_light(img, addq)
    cube = layer()
    draw_cube(cube, t, led_img, Zc, yaw, cy, Yc, hi=Zc < 1150)
    glow_onto(img, cube, 90, 0.5)
    d = ImageDraw.Draw(img)
    for x, y, ph in r11._CROWD:                         # Handyblitze im Publikum
        if math.sin(t * 9 + ph * 7) > 0.96:
            yy = y - oy
            d.ellipse((x - 5, yy - 5, x + 5, yy + 5), fill=(255, 255, 255, 235))
    return img, addq


PYRO_X = [0.09, 0.35, 0.65, 0.91]
_NOISE = None


def noise_tex():
    global _NOISE
    if _NOISE is None:
        rng = np.random.default_rng(7)
        acc = np.zeros((256, 256), np.float32)
        for k, amp in ((8, 1.0), (16, 0.5), (32, 0.25), (64, 0.12)):
            g = np.tile(rng.standard_normal((k, k)).astype(np.float32), (3, 3))
            acc += np.asarray(Image.fromarray(g).resize((768, 768), Image.BICUBIC))[256:512, 256:512] * amp
        _NOISE = (acc - acc.min()) / (acc.max() - acc.min())
    return _NOISE


def pyro(addq, lt):
    """Flammensäulen vom Eis (additiv, Viertelauflösung). Liefert die Spitzen für Funken."""
    if lt < 0 or lt > 1.3:
        return []
    N = noise_tex()
    hgt = QH * 0.46 * e_out(lt / 0.14, 3) * (1 - 0.3 * c01((lt - 0.55) / 0.6))
    fade = 1 - c01((lt - 0.75) / 0.55)
    out = np.zeros((QH, QW), np.float32)
    dy = QH - QYY
    rel = dy / max(hgt, 1.0)
    for k, fx in enumerate(PYRO_X):
        cx = fx * QW
        col = np.exp(-((QXX - cx) / (8 + 7 * rel)) ** 2) * (dy > 0)
        n = N[((QYY * 1.5 + lt * 260 + k * 53).astype(int)) % 256, ((QXX * 1.5 + k * 71).astype(int)) % 256]
        hm = np.clip(1 - rel + (n - 0.5) * 0.9, 0, 1)
        out = np.maximum(out, col * hm * (0.55 + 0.7 * n))
    v = out * fade * 1.35
    rgb = np.stack([np.clip(v * 2.3, 0, 1), np.clip(v * 1.6 - 0.32, 0, 1), np.clip(v * 1.5 - 0.95, 0, 1)], -1)
    addq += rgb * 255
    return [(fx * W, H - hgt * Q * 0.9) for fx in PYRO_X]


# ================================================================= Szene A: Hook
_HOOK = None
_CARD = None
_STAMP = None


def hook_static():
    global _HOOK
    if _HOOK is None:
        a = r11.arena_static().crop((0, 380, W, 380 + H)).convert("RGB")
        small = a.resize((QW, QH), Image.BILINEAR).filter(ImageFilter.GaussianBlur(2.5))
        small = Image.blend(small, Image.new("RGB", small.size, (0, 0, 0)), 0.3)
        _HOOK = small.resize((W, H), Image.BILINEAR).convert("RGBA")
    return _HOOK


def comment_card():
    global _CARD
    if _CARD is None:
        S = 1.45
        w, h = int(700 * S), int(190 * S)
        c = Image.new("RGBA", (w + 80, h + 80), (0, 0, 0, 0))
        sh = Image.new("L", c.size, 0)
        ImageDraw.Draw(sh).rounded_rectangle((40, 58, 40 + w, 58 + h), radius=int(34 * S), fill=150)
        c.putalpha(sh.filter(ImageFilter.GaussianBlur(18)))
        d = ImageDraw.Draw(c)
        d.rounded_rectangle((40, 40, 40 + w, 40 + h), radius=int(34 * S), fill=(238, 239, 243, 255))
        ox, oy = 40, 40
        d.ellipse((ox + 28 * S, oy + 38 * S, ox + 128 * S, oy + 138 * S), fill=(60, 140, 220, 255))
        d.text((ox + 78 * S, oy + 88 * S), NAME[0].upper(), font=font("Black", int(52 * S)), fill=(255, 255, 255), anchor="mm")
        d.text((ox + 152 * S, oy + 58 * S), NAME, font=font("SemiBold", int(30 * S)), fill=(92, 92, 104), anchor="lm")
        d.text((ox + 152 * S, oy + 112 * S), COMMENT, font=font("ExtraBold", fit(COMMENT, "ExtraBold", int(50 * S), w - 160 * S - 30)),
               fill=(18, 18, 22), anchor="lm")
        d.text((ox + 152 * S, oy + 158 * S), "Reply", font=font("SemiBold", int(24 * S)), fill=(150, 150, 160), anchor="lm")
        _CARD = c
    return _CARD


def stamp_img():
    global _STAMP
    if _STAMP is None:
        w, h = 660, 250
        st = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(st)
        col = (238, 40, 54)
        d.rounded_rectangle((6, 6, w - 7, h - 7), radius=26, outline=col + (255,), width=12)
        d.rounded_rectangle((28, 28, w - 29, h - 29), radius=16, outline=col + (255,), width=4)
        tracked(st, "REQUEST", w / 2, 80, 50, "Black", col, 14)
        size = 104
        while s.text_size("ACCEPTED", size, "Black", 4) > w - 90:
            size -= 2
        tracked(st, "ACCEPTED", w / 2, 160, size, "Black", col, 4)
        rng = np.random.default_rng(3)
        holes = (rng.random((h // 3, w // 3)) > 0.9).astype(np.uint8) * 255
        hm = np.asarray(Image.fromarray(holes).resize((w, h), Image.NEAREST).filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32)
        a = np.asarray(st.getchannel("A")).astype(np.float32) * (1 - hm / 255 * 0.85)
        st.putalpha(Image.fromarray(a.astype(np.uint8)))
        _STAMP = st.rotate(9, resample=Image.BICUBIC, expand=True)
    return _STAMP


STAMP_C = (W / 2 + 120, 1035)


def hook(t):
    img = hook_static().copy()
    addq = qcanvas()
    beams(addq, t + 2.0, TOP_BEAMS, 0.8)
    img = add_light(img, addq)
    L = layer()
    tracked(L, "YOU ASKED.", W / 2, 560, 112, "Black", WHITE, 2,
            per_letter=lambda i, n: (0, -70 * (1 - e_out((t + 0.3 - i * 0.03) / 0.22)), c01((t + 0.3 - i * 0.03) / 0.1)))
    # Kommentar-Karte fliegt von unten herein
    p = e_out((t + 0.1) / 0.38, 3)
    card = comment_card()
    rot = lerp(-14, 0, p)
    sc = lerp(0.72, 1.0, p)
    cimg = card.rotate(rot, resample=Image.BICUBIC, expand=True)
    cimg = cimg.resize((int(cimg.width * sc), int(cimg.height * sc)), Image.BILINEAR)
    cy = lerp(1750, 880, p)
    put_img(L, cimg, W / 2 - cimg.width / 2, cy - cimg.height / 2)
    # Stempel knallt drauf
    ps = (t - 0.42) / 0.13
    d = ImageDraw.Draw(L)
    if ps > 0:
        stp = stamp_img()
        sc_ = lerp(2.8, 1.0, e_in(min(ps, 1.0), 2))
        if t > 0.55:
            sc_ *= 1 + 0.04 * math.exp(-(t - 0.55) * 12) * math.sin((t - 0.55) * 45)
        si = stp.resize((int(stp.width * sc_), int(stp.height * sc_)), Image.BILINEAR)
        put_img(L, fade_layer(si, c01(ps * 2.5)), STAMP_C[0] - si.width / 2, STAMP_C[1] - si.height / 2)
        ring(d, STAMP_C[0], STAMP_C[1], t - 0.55, 0.45, 760, WHITE, 16)
        sparks(d, t - 0.55, [STAMP_C], 3, n=36, spread=2.8, speed=(500, 1300), grav=900, life=(0.25, 0.5),
               window=0.02, col=(255, 230, 225), width=4)
    txt = layer()
    tracked(txt, "WE DELIVERED.", W / 2, 1360, 96, "Black", WHITE, 2,
            per_letter=lambda i, n: (0, 60 * (1 - e_out((t - 0.62 - i * 0.025) / 0.22)), c01((t - 0.62 - i * 0.025) / 0.1)))
    lw = 560 * e_io((t - 0.75) / 0.3)
    if lw > 2:
        ImageDraw.Draw(txt).rectangle((W / 2 - lw / 2, 1432, W / 2 + lw / 2, 1440), fill=ORANGE + (255,))
    glow_onto(L, txt, 26, 0.6)
    img.alpha_composite(L)
    return img, addq


# ================================================================= Szene B/C/G: Arena
def arena_B(t):
    ta = max(0.0, t - 1.0)
    tilt = 1 - e_io(ta / 0.9)
    Zc = lerp(2300, 1550, e_io(c01(ta / 3.4)))
    yaw = lerp(-0.5, -0.12, e_io(c01(ta / 3.4)))
    cy = 600 - 1000 * tilt
    drop = t - 3.4
    gain = 1.0 + (1.3 * math.exp(-drop * 2.5) if drop >= 0 else 0)
    img, addq = arena_frame(t, tilt, Zc, yaw, cy, led_arena(ta), beam_gain=gain)
    if drop >= 0:
        beams(addq, t, DROP_BEAMS, math.exp(-drop * 1.5))
        tips = pyro(addq, drop)
        sp = layer()
        if tips:
            sparks(ImageDraw.Draw(sp), drop, tips, 11, n=26, spread=0.5, speed=(500, 1100), window=0.7)
        img.alpha_composite(sp)
        r11.goal_beacons(img, drop)
    return img, addq


def arena_C(t):
    tc = c01((t - 4.4) / 0.6)
    Zc = lerp(1550, 465, e_in(tc, 2.4))
    yaw = lerp(-0.12, 0.0, e_io(tc))
    cy = lerp(600, 960, e_io(tc))
    Yc = lerp(-520, 0, e_io(tc))
    return arena_frame(t, 0.0, Zc, yaw, cy, led_arena(t - 1.0), Yc=Yc)


def sc_cta(t):
    tg = t - 13.0
    q = e_out(c01(tg / 1.1), 3)
    Zc = lerp(640, 2250, q) + 250 * e_io(c01((tg - 1.1) / 1.9))
    yaw = lerp(0.0, 0.42, e_io(c01(tg / 3.0)))
    cy = lerp(960, 560, e_io(c01(tg / 0.9)))
    Yc = lerp(0, -520, q)
    img, addq = arena_frame(t, 0.0, Zc, yaw, cy, led_next(tg), Yc=Yc)
    fx = layer()
    fd = ImageDraw.Draw(fx)
    sparks(fd, tg - 0.25, [(70, H + 10), (W - 70, H + 10)], 21, n=70, spread=0.22, speed=(1300, 1900),
           life=(0.6, 1.0), window=2.0)
    confetti(fd, tg + 1.2, n=70, seed=8, speed=0.8)
    img.alpha_composite(fx)
    L = layer()
    head = layer()
    tracked(head, "REQUESTED BY", W / 2, 1060, 36, "Bold", (170, 178, 195), 18,
            per_letter=lambda i, n: (0, 34 * (1 - e_out((tg - 0.45 - i * 0.02) / 0.3)), e_out((tg - 0.45 - i * 0.02) / 0.3)))
    L.alpha_composite(masked(head, (0, 1015, W, 1105)))
    name = layer()
    tracked(name, "@" + NAME, W / 2, 1150, 92, "Black", WHITE, 2,
            per_letter=lambda i, n: (0, 0, e_out((tg - 0.6 - i * 0.03) / 0.22)))
    light_sweep(name, c01((tg - 1.0) / 0.6))
    glow_onto(L, name, 30, 0.55)
    lw = 520 * e_io((tg - 0.8) / 0.4)
    if lw > 2:
        ImageDraw.Draw(L).rectangle((W / 2 - lw / 2, 1222, W / 2 + lw / 2, 1226), fill=BLUE + (255,))
    cta = layer()
    tracked(cta, "COMMENT YOUR PLAYER", W / 2, 1320, fit("COMMENT YOUR PLAYER", "Black", 70, 840), "Black", ORANGE, 3,
            per_letter=lambda i, n: (0, 30 * (1 - e_out((tg - 1.0 - i * 0.015) / 0.25)), e_out((tg - 1.0 - i * 0.015) / 0.2)))
    if tg > 1.4:
        y = 1395 + abs(math.sin(tg * 6)) * 24
        ImageDraw.Draw(cta).polygon([(W / 2 - 38, y), (W / 2 + 38, y), (W / 2, y + 48)], fill=ORANGE + (255,))
    glow_onto(L, cta, 30, 0.7)
    img.alpha_composite(L)
    return img, addq


# ================================================================= Szene D: Spieler
_PL = None
_63 = None
_ROWS = None
_NAMEIMG = None
PL_TOP, PL_CX = 600, W / 2 + 30


def player_assets():
    global _PL
    if _PL is None:
        cut = Image.open(os.path.join(HERE, "photos", "marchand_cut.png")).convert("RGBA")
        hgt = 1450
        cut = cut.resize((int(cut.width * hgt / cut.height), hgt), Image.LANCZOS)
        arr = np.asarray(cut).astype(np.float32)
        ys = np.arange(hgt, dtype=np.float32)[:, None]
        fade = np.clip((hgt - 40 - ys) / 360, 0, 1)
        rgb = ((arr[..., :3] - 128) * 1.12 + 128) * np.array([0.96, 1.0, 1.06]) * (0.35 + 0.65 * fade[..., None])
        a = arr[..., 3] * fade
        graded = Image.fromarray(np.dstack([np.clip(rgb, 0, 255), a]).astype(np.uint8), "RGBA")
        al = Image.fromarray(a.astype(np.uint8))
        rim_a = ImageChops.subtract(al, al.filter(ImageFilter.MinFilter(9))).filter(ImageFilter.GaussianBlur(1.6))
        rim_a = np.asarray(rim_a).astype(np.float32) * np.clip(1.15 - ys / hgt, 0, 1)
        rim = Image.new("RGBA", cut.size, (200, 238, 255, 0))
        rim.putalpha(Image.fromarray(np.clip(rim_a * 1.3, 0, 255).astype(np.uint8)))
        halo = Image.new("RGBA", cut.size, BLUE + (0,))
        halo.putalpha(al.resize((cut.width // 4, hgt // 4)).filter(ImageFilter.GaussianBlur(14)).resize(cut.size, Image.BILINEAR)
                      .point(lambda v: int(v * 0.75)))
        _PL = (graded, rim, halo)
    return _PL


def big63():
    global _63
    if _63 is None:
        f = font("anton", 1000)
        lay = Image.new("L", (1400, 1500), 0)
        ImageDraw.Draw(lay).text((700, 750), "63", font=f, fill=255, anchor="mm")
        lay = lay.crop(lay.getbbox())
        sc = 880 / lay.height
        lay = lay.resize((int(lay.width * sc), 880), Image.LANCZOS)
        ys = np.linspace(0, 1, lay.height)[:, None, None]
        top, bot = np.array([120, 215, 255]), np.array([18, 50, 128])
        rgb = np.broadcast_to(top + (bot - top) * ys, (lay.height, lay.width, 3))
        a = np.asarray(lay).astype(np.float32) * 0.9
        _63 = Image.fromarray(np.dstack([rgb, a]).astype(np.uint8), "RGBA")
    return _63


def name_rows():
    global _ROWS
    if _ROWS is None:
        f = font("anton", 200)
        unit = "MARCHAND   "
        uw = f.getlength(unit)
        strip = Image.new("RGBA", (int(uw * 4), 250), (0, 0, 0, 0))
        d = ImageDraw.Draw(strip)
        for k in range(4):
            d.text((k * uw, 125), unit, font=f, fill=(0, 0, 0, 0), stroke_width=3, stroke_fill=(150, 205, 255, 255), anchor="lm")
        _ROWS = (strip, uw)
    return _ROWS


def name_img():
    global _NAMEIMG
    if _NAMEIMG is None:
        size = fit("MARCHAND", "anton", 250, 930)
        lay = layer()
        ImageDraw.Draw(lay).text((W / 2, 420), "MARCHAND", font=font("anton", size), fill=WHITE + (255,), anchor="mm")
        _NAMEIMG = lay
    return _NAMEIMG


def sc_player(lt, t):
    img = s.background(t)
    addq = qcanvas()
    rays(addq, lt, W / 2, 760, 0.55 * e_out(lt / 0.3))
    img = add_light(img, addq)
    if lt < 0.7:
        flare(addq, W / 2 - 80, 760, 0.9 * (1 - lt / 0.7) ** 2)
    # Lauftext-Reihen hinter dem Spieler
    strip, uw = name_rows()
    rows = layer()
    for k, y in enumerate((640, 900, 1160)):
        off = (uw * 0.37 * k + (lt * 140 if k % 2 == 0 else -lt * 140)) % uw
        rows.alpha_composite(strip.crop((int(off), 0, int(off) + W, 250)), (0, y - 125))
    img.alpha_composite(fade_layer(rows, 0.32 * e_out(lt / 0.4)))
    graded, rim, halo = player_assets()
    # Riesen-63
    n63 = big63()
    s63 = lerp(1.5, 1.0, e_out(lt / 0.35, 3)) * (1 + 0.02 * lt)
    i63 = n63.resize((int(n63.width * s63), int(n63.height * s63)), Image.BILINEAR)
    put_img(img, fade_layer(i63, e_out(lt / 0.25)), W / 2 - i63.width / 2, 860 - i63.height / 2)
    # Spieler: Slam + langsamer Push-in
    sp = lerp(1.22, 1.0, e_out(lt / 0.22, 3)) * (1 + 0.05 * e_io(c01(lt / 3.2)))
    pw, ph = int(graded.width * sp), int(graded.height * sp)
    x0, y0 = int(PL_CX - pw / 2), int(PL_TOP - (sp - 1) * 300)
    pl = layer()
    for im_ in (halo, graded, rim):
        put_img(pl, im_.resize((pw, ph), Image.BILINEAR), x0, y0)
    img.alpha_composite(fade_layer(pl, c01(lt / 0.06)))
    # Glut-Partikel
    fx = layer()
    embers(ImageDraw.Draw(fx), lt)
    img.alpha_composite(fx)
    # Name
    L = layer()
    tracked(L, "BRAD", W / 2, 268, 62, "ExtraBold", WHITE, 34,
            per_letter=lambda i, n: (0, 40 * (1 - e_out((lt - 0.2 - i * 0.04) / 0.3)), e_out((lt - 0.2 - i * 0.04) / 0.3)))
    nm = name_img().copy()
    light_sweep(nm, c01((lt - 0.7) / 0.55))
    nm = scale_layer(nm, lerp(1.45, 1.0, e_out(lt / 0.2, 3)), W / 2, 420)
    glow_onto(L, fade_layer(nm, c01(lt / 0.08)), 30, 0.28)
    if lt > 0.85:
        p = e_back((lt - 0.85) / 0.35)
        tag = layer()
        td = ImageDraw.Draw(tag)
        w_, h_ = 400 * p, 76 * p
        td.rounded_rectangle((W / 2 - w_ / 2, 556 - h_ / 2, W / 2 + w_ / 2, 556 + h_ / 2), radius=h_ / 2, fill=ORANGE + (255,))
        if p > 0.4:
            tracked(tag, '"THE RAT"', W / 2, 556, int(40 * min(1, p)), "Black", (20, 16, 14), 6)
        L.alpha_composite(tag)
    tracked(L, CREDIT, W / 2, H - 70, 24, "SemiBold", (150, 155, 168), 1, alpha=0.9)
    img.alpha_composite(L)
    d = ImageDraw.Draw(img)
    ring(d, W / 2, 760, lt, 0.5, 950, ICEW, 18)
    return img, addq


# ================================================================= Szene E: Draft
TILE_W, TILE_H, GAP = 84, 42, 8
GRID_X0 = (W - (10 * TILE_W + 9 * GAP)) / 2
GRID_Y0 = 905


def draft_count(lt):
    p = c01((lt - 0.2) / 1.0)
    return 71 if p >= 1 else 1 + int(70 * (1 - (1 - p) ** 2.6))


def lit_time(i):
    return 0.2 + 1 - (1 - (i + 1) / 70) ** (1 / 2.6)


def sc_draft(lt, t):
    img = s.background(t)
    addq = qcanvas()
    landed = lt >= 1.2
    n = draft_count(lt)
    L = layer()
    head = layer()
    tracked(head, "DRAFTED", W / 2, 300, 46, "Bold", DIM, 24,
            per_letter=lambda i, k: (0, 40 * (1 - e_out((lt - i * 0.03) / 0.35)), e_out((lt - i * 0.03) / 0.35)))
    L.alpha_composite(masked(head, (0, 250, W, 350)))
    tracked(L, "2006 · ROUND 3", W / 2, 372, 34, "Bold", BLUE, 10, alpha=e_out((lt - 0.3) / 0.3))
    # Zähler
    num = layer()
    nd = ImageDraw.Draw(num)
    f = font("Black", 400)
    col = ORANGE if landed and lt < 1.5 else WHITE
    nx = W / 2 - 40
    nd.text((nx, 650), str(n), font=f, fill=col + (255,), anchor="mm")
    speed = (draft_count(lt + 0.03) - n) / 0.03
    if speed > 4:
        num = s.vblur(num, min(36, speed * 0.5))
    if landed:
        pst = e_back((lt - 1.2) / 0.25)
        if pst > 0.05:
            sup = layer()
            tracked(sup, "ST", nx + f.getlength("71") / 2 + 12, 520, int(110 * min(1.2, pst)), "Black", col, 0, anchor_x="left")
            num.alpha_composite(sup)
        num = scale_layer(num, 1 + 0.22 * math.exp(-(lt - 1.2) * 11), nx, 650)
    glow_onto(L, num, 34, 0.75 if landed else 0.3)
    # Draft-Board: 70 Picks vor ihm
    d = ImageDraw.Draw(L)
    tf = font("Bold", 20)
    for i in range(70):
        r_, c_ = divmod(i, 10)
        x0, y0 = GRID_X0 + c_ * (TILE_W + GAP), GRID_Y0 + r_ * (TILE_H + GAP)
        ap = e_out((lt - 0.05 - (r_ + c_) * 0.012) / 0.25)
        if ap <= 0:
            continue
        if n > i + 1:
            fl = math.exp(-max(0.0, lt - lit_time(i)) * 10)
            if landed:
                fl = max(fl, 0.5 * math.exp(-(lt - 1.2) * 4))
            fill = tuple(int(lerp(c0, c1, fl)) for c0, c1 in zip((46, 58, 82), BLUE)) + (int(255 * ap),)
            tc = (205, 214, 232)
        else:
            fill, tc = (18, 24, 38, int(210 * ap)), (70, 80, 102)
        d.rounded_rectangle((x0, y0, x0 + TILE_W, y0 + TILE_H), radius=6, fill=fill)
        d.text((x0 + TILE_W / 2, y0 + TILE_H / 2), str(i + 1), font=tf, fill=tc + (int(255 * ap),), anchor="mm")
    if landed:
        tracked(L, "70 PLAYERS PICKED BEFORE HIM", W / 2, 1312, 34, "Bold", WHITE, 4,
                per_letter=lambda i, k: (0, 0, e_out((lt - 1.3 - i * 0.012) / 0.2)))
    if lt > 1.55:
        p = e_back((lt - 1.55) / 0.35)
        tag = layer()
        td = ImageDraw.Draw(tag)
        w_, h_ = 620 * p, 96 * p
        td.rounded_rectangle((W / 2 - w_ / 2, 1430 - h_ / 2, W / 2 + w_ / 2, 1430 + h_ / 2), radius=h_ / 2, outline=ORANGE + (255,), width=5)
        if p > 0.3:
            tracked(tag, "NOBODY SAW IT COMING", W / 2, 1430, int(36 * min(1, p)), "ExtraBold", ORANGE, 4)
        glow_onto(L, tag, 30, 0.8)
    img.alpha_composite(L)
    d = ImageDraw.Draw(img)
    ring(d, nx, 650, lt - 1.2, 0.45, 820, ORANGE, 16)
    if landed and lt < 1.7:
        flare(addq, nx, 650, 0.8 * (1 - (lt - 1.2) / 0.5))
    return img, addq


# ================================================================= Szene F: 2x Stanley Cup
FW = [(0.15, 250, 560, GOLD), (0.4, 830, 470, ICEW), (0.7, 540, 300, BLUE), (1.05, 300, 820, ORANGE),
      (1.35, 790, 760, GOLD), (1.7, 540, 520, ICEW), (2.0, 230, 400, BLUE)]
_CUP = None


def fireworks(d, lt, seed=31):
    for k, (t0, x, y, col) in enumerate(FW):
        tau = lt - t0
        if tau < 0 or tau > 1.5:
            continue
        rng = random.Random(seed + k)
        if tau < 0.1:
            r = 16 + 40 * (1 - tau / 0.1)
            d.ellipse((x - r, y - r, x + r, y + r), fill=col + (int(150 * (1 - tau / 0.1)),))
        for i in range(64):
            ang, sp, tw = i / 64 * 2 * math.pi + rng.uniform(-0.06, 0.06), rng.uniform(330, 480), rng.random()
            kk = (1 - math.exp(-2.6 * tau)) / 2.6
            k0 = (1 - math.exp(-2.6 * max(0.0, tau - 0.07))) / 2.6
            x1, y1 = x + math.cos(ang) * sp * kk, y + math.sin(ang) * sp * kk + 140 * tau * tau
            x0, y0 = x + math.cos(ang) * sp * k0, y + math.sin(ang) * sp * k0 + 140 * max(0.0, tau - 0.07) ** 2
            a = (1 - tau / 1.5) ** 1.4
            if tau > 0.7 and tw > 0.5 and (int(lt * 30) + i) % 3 == 0:
                a *= 0.2
            d.line((x0, y0, x1, y1), fill=col + (int(255 * a),), width=3)


def cup_img():
    global _CUP
    if _CUP is None:
        c = chrome_cup(1.0)
        sc = 0.52
        c = c.resize((int(W * sc), int(H * sc)), Image.BILINEAR)
        _CUP = (c, sc)
    return _CUP


def sc_cups(lt, t):
    img = s.background(t)
    addq = qcanvas()
    rays(addq, lt + 3, W / 2, 1050, 0.35 * e_out(lt / 0.4), GOLD)
    img = add_light(img, addq)
    fw = layer()
    fireworks(ImageDraw.Draw(fw), lt)
    glow_onto(img, fw, 18, 1.1)
    L = layer()
    head = layer()
    tracked(head, "STANLEY CUP CHAMPION", W / 2, 300, 44, "Bold", WHITE, 12,
            per_letter=lambda i, n: (0, 40 * (1 - e_out((lt - i * 0.02) / 0.4)), e_out((lt - i * 0.02) / 0.4)))
    L.alpha_composite(masked(head, (0, 250, W, 350)))
    # "2x" in Gold, knallt bei 10.8
    if lt > 0.12:
        big = layer()
        gradient_text(big, "2×", W / 2, 600, 330, "Black", (255, 240, 190), GOLD, (190, 110, 30))
        big = scale_layer(big, lerp(1.9, 1.0, e_in(c01((lt - 0.12) / 0.08), 2)) * (1 + 0.1 * math.exp(-(lt - 0.2) * 10) if lt > 0.2 else 1), W / 2, 600)
        light_sweep(big, c01((lt - 0.6) / 0.6))
        glow_onto(L, fade_layer(big, c01((lt - 0.12) / 0.05)), 40, 0.75)
    # zwei Pokale steigen auf
    cup, csc = cup_img()
    gl = layer()
    gd = ImageDraw.Draw(gl)
    for k, (year, team, cx, colg) in enumerate((("2011", "BOSTON", W / 2 - 225, BLUE), ("2025", "FLORIDA", W / 2 + 225, RED))):
        p = e_out((lt - 0.3 - k * 0.2) / 0.5, 3)
        if p <= 0:
            continue
        gd.ellipse((cx - 160, 860, cx + 160, 1220), fill=colg + (int(140 * p),))
    glow_onto(img, gl, 170, 1.8, keep=False)
    for k, (year, team, cx) in enumerate((("2011", "BOSTON", W / 2 - 225), ("2025", "FLORIDA", W / 2 + 225))):
        p = e_out((lt - 0.3 - k * 0.2) / 0.5, 3)
        if p <= 0:
            continue
        cy = 1040 + 260 * (1 - p)
        put_img(L, fade_layer(cup.copy(), p), cx - W * csc / 2, cy - 960 * csc)
        tracked(L, year, cx, 1325, 92, "Black", WHITE, 0, alpha=e_out((lt - 0.55 - k * 0.2) / 0.25))
        tracked(L, team, cx, 1398, 30, "Bold", DIM, 10, alpha=e_out((lt - 0.7 - k * 0.2) / 0.25))
    cf = layer()
    confetti(ImageDraw.Draw(cf), lt - 0.15)
    L.alpha_composite(cf)
    img.alpha_composite(L)
    d = ImageDraw.Draw(img)
    ring(d, W / 2, 600, lt - 0.2, 0.45, 900, GOLD, 16)
    return img, addq


# ================================================================= Zusammenbau
STUDIO = [(5.0, 8.2, sc_player), (8.2, 10.6, sc_draft), (10.6, 13.0, sc_cups)]
XF = 0.16


def studio_at(t):
    out = None
    for a, b, fn in STUDIO:
        if a - XF <= t < b + XF and not (a == 5.0 and t < a) and not (b == 13.0 and t >= b):
            arr = to_arr(*fn(max(0.0, t - a), t))
            al, z = 1.0, 1.0
            if t > b - XF and b < 13.0:
                q = e_in(c01((t - (b - XF)) / (2 * XF)), 2)
                z, al = 1 + 0.4 * q, 1 - q
            if t < a + XF and a > 5.0:
                q = e_out(c01((t - (a - XF)) / (2 * XF)), 3)
                z, al = 0.85 + 0.15 * q, q
            if abs(z - 1) > 0.003:
                arr = zoom_arr(arr, z)
            out = arr * al if out is None else out + arr * al
    return out


def white(arr, w):
    return arr * (1 - w) + np.array([225, 240, 255], np.float32) * w if w > 0 else arr


def scene_at(t):
    if t < 0.88:
        return to_arr(*hook(t))
    if t < 1.1:                                         # Whip nach oben in die Arena
        p = e_in(c01((t - 0.88) / 0.22), 2)
        a, b = to_arr(*hook(t)), to_arr(*arena_B(t))
        sh = int(p * H)
        out = np.empty_like(a)
        out[:H - sh] = a[sh:]
        out[H - sh:] = b[:sh]
        return out
    if t < 4.4:
        return to_arr(*arena_B(t))
    if t < 5.0:
        return white(to_arr(*arena_C(t)), e_in(c01((t - 4.84) / 0.16), 2))
    if t < 13.0:
        arr = studio_at(t)
        if t < 5.25:
            arr = white(arr, 1 - e_out((t - 5.0) / 0.25, 2))
        if t > 12.86:                                   # Zoom in den Pokal-Screen -> Arena
            q = e_in(c01((t - 12.86) / 0.14), 2)
            arr = white(zoom_arr(arr, 1 + 0.5 * q), q)
        return arr
    arr = to_arr(*sc_cta(t))
    return white(arr, 1 - e_out((t - 13.0) / 0.3, 2)) if t < 13.3 else arr


# ================================================================= Nachbearbeitung
_VIG = None


def vignette():
    global _VIG
    if _VIG is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2) * 2
        _VIG = (1 - 0.42 * np.clip(r - 0.55, 0, 1) ** 1.3)[..., None]
    return _VIG


def bloom(arr):
    lum = arr.max(axis=2)
    br = arr * np.clip((lum - 190) / 65, 0, 1)[..., None]
    small = br.reshape(H // 8, 8, W // 8, 8, 3).mean(axis=(1, 3))
    im = Image.fromarray(np.clip(small, 0, 255).astype(np.uint8))
    b1 = np.asarray(im.filter(ImageFilter.GaussianBlur(3)).resize((W, H), Image.BILINEAR)).astype(np.float32)
    b2 = np.asarray(im.filter(ImageFilter.GaussianBlur(10)).resize((W, H), Image.BILINEAR)).astype(np.float32)
    return arr + b1 * 0.38 + b2 * 0.36


def impact_env(t):
    return max([amp * math.exp(-(t - ti) * 10) for ti, amp in IMPACTS if t >= ti] + [0.0])


def shake(t):
    dx = dy = 0.0
    for k, (ti, amp) in enumerate(IMPACTS):
        lt = t - ti
        if 0 <= lt < 0.45:
            e = amp * 30 * math.exp(-lt * 9)
            dx += math.sin(lt * 97 + k) * e
            dy += math.cos(lt * 83 + 2 * k) * e
    return dx, dy


def post(arr, t, i):
    arr = bloom(arr)
    dx, dy = shake(t)
    if abs(dx) + abs(dy) > 0.5:
        im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        z = 1.05
        w2, h2 = W / z, H / z
        box = ((W - w2) / 2 + dx, (H - h2) / 2 + dy, (W + w2) / 2 + dx, (H + h2) / 2 + dy)
        arr = np.asarray(im.transform((W, H), Image.EXTENT, box, Image.BILINEAR)).astype(np.float32)
    k = int(round(9 * impact_env(t)))
    if k:
        arr[..., 0] = np.roll(arr[..., 0], k, 1)
        arr[..., 2] = np.roll(arr[..., 2], -k, 1)
    arr = arr * vignette()
    arr += np.random.default_rng(i).normal(0, 2.4, arr.shape[:2])[..., None]
    return np.clip(arr, 0, 255).astype(np.uint8)


FAST = [(0.0, 0.3, 3), (0.42, 0.6, 3), (0.88, 1.12, 3), (4.4, 5.0, 7), (5.0, 5.12, 3), (8.04, 8.36, 3),
        (10.44, 10.76, 3), (10.76, 10.85, 3), (12.86, 13.15, 3)]


def render_frame(i):
    t = i / FPS
    sub = next((k for a, b, k in FAST if a <= t < b), 1)
    if sub > 1:
        dts = np.linspace(-1 / 60, 1 / 60, sub) if sub > 3 else (-1 / 90, 0, 1 / 90)
        arr = sum(scene_at(max(0.0, min(DUR - 1e-3, t + dt))) for dt in dts) / sub
    else:
        arr = scene_at(t)
    return post(arr, t, i).tobytes()


# ================================================================= Sound
SR = 44100


def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(11)
    music, sfx, vox = np.zeros(n), np.zeros(n), np.zeros(n)

    def tt(sec):
        return np.arange(int(sec * SR)) / SR

    def put(buf, sig, at, vol=1.0):
        st = int(round(at * SR))
        if st < 0:
            sig, st = sig[-st:], 0
        e = min(n, st + len(sig))
        if st < n:
            buf[st:e] += sig[: e - st] * vol

    def lp(x, k):
        if k <= 1:
            return x
        c = np.cumsum(np.concatenate([np.zeros(k), x]))
        return (c[k:] - c[:-k]) / k

    def hp(x, k):
        return x - lp(x, k)

    def noise(sec):
        return rng.standard_normal(int(sec * SR))

    def kick():
        x = tt(0.45)
        f = 46 + 110 * np.exp(-x * 28)
        body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 7.5)
        return np.tanh((body + noise(0.45) * np.exp(-x * 400) * 0.3) * 2.2) * 0.9

    def clap():
        x = tt(0.3)
        out = np.zeros(len(x))
        nz = hp(noise(0.3), 6)
        for off, dec in ((0, 60), (0.011, 60), (0.022, 16)):
            st = int(off * SR)
            out[st:] += nz[: len(x) - st] * np.exp(-x[: len(x) - st] * dec)
        return lp(out, 2) * 0.55

    def hat(open_=False):
        d_ = 0.25 if open_ else 0.06
        x = tt(d_)
        return hp(noise(d_), 3) * np.exp(-x * (18 if open_ else 90)) * 0.22

    def sub(freq, dur):
        x = tt(dur)
        f = freq * (1 + 0.6 * np.exp(-x * 40))
        env = np.minimum(x / 0.005, 1) * np.clip((dur - x) / 0.06, 0, 1) * np.exp(-x * 1.2)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * 2.5) * env * 0.7

    def saws(freqs, dur, det=(-0.006, 0.0, 0.006)):
        x = tt(dur)
        sig = sum(2 * ((x * f * (1 + dd)) % 1) - 1 for f in freqs for dd in det)
        return lp(lp(sig, 7), 5) / (len(freqs) * len(det)), x

    def stab(freqs, dur=0.9, vol=0.9):
        sig, x = saws(freqs, dur)
        return sig * np.minimum(x / 0.008, 1) * np.exp(-x * 3.0) * vol

    def pad(freqs, dur, vol=0.18):
        sig, x = saws(freqs, dur)
        sig = lp(sig, 14)
        return sig * np.minimum(x / 0.25, 1) * np.clip((dur - x) / 0.25, 0, 1) * vol

    def boom(dur=2.0, f0=55, vol=1.0):
        x = tt(dur)
        f = f0 + 140 * np.exp(-x * 14)
        body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 2.2)
        tail = lp(noise(dur), 30) * np.exp(-x * 2.8) * 0.8
        hit = hp(noise(dur), 4) * np.exp(-x * 30) * 0.5
        return np.tanh((body + tail + hit) * 1.6) * 0.9 * vol

    def whoosh(dur=0.45, vol=1.0):
        x = tt(dur)
        nz = noise(dur)
        env = np.sin(np.pi * x / dur) ** 2
        lo, hi = lp(nz, 40), lp(nz, 8) - lp(nz, 40)
        mv = x / dur
        return (lo * (1 - mv) + hi * mv * 1.4) * env * 1.4 * vol

    def riser(dur, vol=1.0):
        x = tt(dur)
        sweep = np.sin(2 * np.pi * np.cumsum(200 + 1400 * (x / dur) ** 2) / SR) * (x / dur) ** 3 * 0.18
        return (hp(noise(dur), 5) * (x / dur) ** 2 * 0.5 + sweep) * vol

    def crash(vol=0.25):
        x = tt(1.6)
        return hp(noise(1.6), 2) * np.exp(-x * 2.6) * vol

    def horn(dur=1.6):
        x = tt(dur)
        sig = sum(2 * ((x * f * (1 + 0.003 * np.sin(2 * np.pi * 4.5 * x))) % 1) - 1 for f in (110.0, 138.6, 164.8))
        sig = lp(lp(sig, 10), 6)
        return sig / 3 * np.minimum(x / 0.06, 1) * np.clip((dur - x) / 0.35, 0, 1) * 0.75

    def crowd(dur, vol):
        x = tt(dur)
        a = lp(noise(dur), 14) * 3
        mod = 0.75 + 0.25 * np.sin(2 * np.pi * 0.7 * x + 1) * np.sin(2 * np.pi * 0.23 * x)
        return a * mod * vol

    def crackle(dur, density=140, vol=0.35):
        x = np.zeros(int(dur * SR))
        for _ in range(int(dur * density)):
            p = int(rng.integers(0, len(x) - 300))
            amp = rng.uniform(0.2, 1) * np.exp(-p / SR * 1.5)
            x[p:p + 200] += hp(rng.standard_normal(200), 2) * np.exp(-np.arange(200) / 25) * amp
        return x * vol

    FM = [174.6, 207.7, 261.6, 349.2]
    DB = [138.6, 174.6, 207.7, 277.2]
    EB = [155.6, 196.0, 233.1, 311.1]
    AB = [207.7, 261.6, 311.1, 415.3]
    ROOT = [87.3, 87.3, 69.3, 77.8]
    CHORD = [FM, FM, DB, EB]

    # ---------- Beat (Achtel = 0.2 s), gefiltert bis zum Drop bei 3.4
    drums, drums_f, bass = np.zeros(n), np.zeros(n), np.zeros(n)
    k8 = 0
    tp = 1.8
    while tp < 15.39:
        pos, bar = k8 % 8, (k8 - 8) // 8           # Takt 0 beginnt beim Drop (3.4)
        gap = 4.6 <= tp < 5.0
        tgt = drums_f if tp < 3.4 else drums
        if not gap:
            if pos in (0, 5):
                put(tgt, kick(), tp, 0.95)
            if pos == 4:
                put(tgt, clap(), tp, 0.85)
            put(tgt, hat(), tp, 0.8 if pos % 2 == 0 else 0.5)
            if pos in (6, 7) and bar % 2 == 1 and tp >= 3.4:
                for j in (1, 2):
                    put(drums, hat(), tp + j * 0.2 / 3, 0.45)
            if pos == 7 and bar % 4 == 3:
                put(drums, hat(True), tp, 0.6)
            if tp >= 3.4 and pos in (0, 5):
                put(bass, sub(ROOT[bar % 4], 0.95 if pos == 0 else 0.55), tp)
        tp = round(tp + 0.2, 4)
        k8 += 1
    music += drums + lp(drums_f, 22) * 1.6 + bass * 0.9
    # Flächen ab dem Spieler-Reveal
    for b in range(7):
        st = 5.0 + b * 1.6
        if st < 15.4:
            put(music, pad(CHORD[(b + 1) % 4], min(1.6, 15.9 - st) + 0.05), st)
    for at, ch in ((3.4, FM), (5.0, FM), (8.2, DB), (9.4, EB), (10.8, FM), (13.0, AB), (15.4, FM)):
        put(music, stab(ch, 1.4 if at == 15.4 else 0.9), at)
    put(music, sub(87.3, 0.6), 15.4, 1.0)

    # ---------- Effekte
    put(sfx, whoosh(0.38, 0.9), 0.0)
    put(sfx, whoosh(0.16, 0.7), 0.4)
    put(sfx, boom(1.2, 70, 0.9), 0.55)
    put(sfx, hp(noise(0.06), 2) * np.exp(-tt(0.06) * 60) * 0.9, 0.55)
    put(sfx, whoosh(0.3, 1.0), 0.86)
    put(sfx, crowd(3.6, 0.35) * np.clip(np.arange(int(3.6 * SR)) / SR / 0.6, 0, 1), 1.0)
    put(sfx, riser(1.6, 0.8), 1.8)
    put(sfx, boom(2.0, 50, 1.0), 3.4)
    put(sfx, horn(1.6), 3.42)
    fire_x = tt(1.3)
    put(sfx, lp(noise(1.3), 6) * np.minimum(fire_x / 0.03, 1) * np.exp(-fire_x * 1.8) * 0.9, 3.4)
    put(sfx, crowd(1.8, 0.9) * np.exp(-tt(1.8) * 0.9), 3.4)
    put(sfx, crackle(1.0, 120, 0.3), 3.5)
    put(sfx, crash(0.3), 3.4)
    put(sfx, riser(0.6, 1.1), 4.4)
    put(sfx, boom(0.6, 60, 0.8)[::-1] * 0.7, 4.4)
    put(sfx, boom(2.2, 45, 1.15), 5.0)
    put(sfx, crash(0.3), 5.0)
    put(sfx, whoosh(0.32, 1.0), 8.04)
    put(sfx, crash(0.18), 8.2)
    tick_x = tt(0.02)
    tick = np.sin(2 * np.pi * 3000 * tick_x) * np.exp(-tick_x * 300) * 0.16
    prev = draft_count(0.0)
    for j in range(1, 1400):
        lt = j / 1000
        c = draft_count(lt)
        if c != prev:
            put(sfx, tick, 8.2 + lt)
            prev = c
    put(sfx, boom(1.4, 60, 0.8), 9.4)
    put(sfx, whoosh(0.32, 1.0), 10.44)
    put(sfx, crash(0.25), 10.6)
    put(sfx, boom(1.6, 50, 1.0), 10.8)
    for t0, *_ in FW:
        put(sfx, boom(0.7, 75, 0.35), 10.6 + t0)
        put(sfx, crackle(1.0, 90, 0.22), 10.6 + t0 + 0.25)
    put(sfx, whoosh(0.3, 1.0), 12.82)
    put(sfx, boom(1.2, 60, 0.6), 13.0)
    put(sfx, horn(1.3), 13.05)
    put(sfx, crowd(3.0, 0.7) * np.clip((16.0 - 13.0 - tt(3.0)) / 0.8, 0, 1), 13.0)
    put(sfx, crackle(2.2, 60, 0.18), 13.3)
    put(sfx, boom(0.9, 55, 0.7), 15.4)

    # ---------- Stadionsprecher mit Hallen-Hall
    v = r3.load_voice()
    segs = r3.speech_segments(v)
    assert len(segs) == 4, segs
    for (a, b), at in zip(segs, VOICE_AT):
        clip = v[max(0, int((a - 0.04) * SR)): int((b + 0.15) * SR)].astype(np.float64)
        ramp = np.minimum(np.arange(len(clip)) / (0.01 * SR), 1) * np.minimum((len(clip) - np.arange(len(clip))) / (0.03 * SR), 1)
        put(vox, clip * ramp, at)
    vox = hp(vox, 130)
    vox = np.tanh(vox * 2.2) / 1.6
    irl = int(1.6 * SR)
    ix = np.arange(irl) / SR
    ir = lp(rng.standard_normal(irl), 3) * np.exp(-ix * 3.4)
    ir[: int(0.02 * SR)] *= np.linspace(0, 1, int(0.02 * SR))
    ir /= np.sqrt(np.sum(ir ** 2))
    wet = fftconvolve(vox, ir)[:n]
    slap = np.zeros(n)
    dl = int(0.11 * SR)
    slap[dl:] = vox[:-dl]
    vox_out = vox + wet * 0.3 + slap * 0.18
    env = lp(np.abs(vox), 2200)
    duck = 1 - 0.5 * np.clip(env / (env.max() * 0.25 + 1e-9), 0, 1)

    mix = music * 0.6 * duck + sfx * 0.75 + vox_out * 1.25
    mix /= np.percentile(np.abs(mix), 99.95) + 1e-9
    mix = np.tanh(mix * 0.95)
    mix *= np.clip((DUR - np.arange(n) / SR) / 0.5, 0, 1)
    mix = mix / np.max(np.abs(mix)) * 0.95
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


def main():
    os.chdir(HERE)
    make_audio("audio_fanwall2.wav")
    nf = int(DUR * FPS)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_fanwall2.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "21",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
           "reel11b_fanwall.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(4) as pool:
        for k, buf in enumerate(pool.imap(render_frame, range(nf), chunksize=2)):
            proc.stdin.write(buf)
            if k % 60 == 0:
                print(f"{k}/{nf}", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.frombytes("RGB", (W, H), render_frame(int(5.6 * FPS))).save("reel11b_thumbnail.jpg", quality=92)
    print("fertig: reel11b_fanwall.mp4")


if __name__ == "__main__":
    main()
