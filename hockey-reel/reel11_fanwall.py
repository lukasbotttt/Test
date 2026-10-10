"""Reel 11: FAN WALL #1 – Zuschauer-Wunsch auf dem Arena-Videowürfel + Spieler-Animation.

Template: NAMES / COMMENT / PLAYER oben anpassen (Namen aus den Kommentaren, eigene ausgenommen).
Ablauf (14 s):
  0.0–4.8  Arena mit Jumbotron (LED-Optik): FAN WALL #1 -> REQUESTED BY -> @name -> NEXT UP: Spieler,
           dazu der Kommentar als TikTok-Antwort-Sticker, Torlicht + Hupe
  4.8–5.6  Kamera fliegt in den Videowürfel
  5.6–14.0 Studio-Animation zum Spieler, Abspann "Requested by @name"
Fakten Brad Marchand: Nr. 63, Draft 2006 an Position 71 (Runde 3, Boston), Stanley Cup 2011 (Boston)
und 2025 (Florida), Bruins-Kapitän ab 2023, Spitzname "The Rat".
Aufruf: python3 reel11_fanwall.py  ->  reel11_fanwall.mp4
"""
import math
import os
import random
import subprocess
import wave
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import make_hockey_reel as m
import reel10_studio as s
from make_hockey_reel import font
from reel10_studio import (W, H, BLUE, ORANGE, RED, WHITE, DIM, c01, e_io, e_out, e_in, e_back, lerp,
                           layer, glow_onto, tracked, masked, light_sweep, odometer, draw_icon, chrome_cup)

FPS = 30
DUR = 14.0
HERE = m.HERE
NAMES = ["mrnobbbe"]                       # Kommentator(en) – Fan Wall
COMMENT = ("mrnobbbe", "Do Brad Marchand")  # Kommentar für den Antwort-Sticker
PLAYER = "BRAD MARCHAND"
JUMBO = (140, 420, 940, 870)               # Frontfläche des Videowürfels (x0, y0, x1, y1)
LED_W, LED_H = 200, 112                    # LED-Auflösung des Screens
rnd = random.Random(4)


# ================================================================= LED-Screen
_DOTMASK = None


def led_dotmask():
    global _DOTMASK
    if _DOTMASK is None:
        w, h = JUMBO[2] - JUMBO[0], JUMBO[3] - JUMBO[1]
        cell_x, cell_y = w / LED_W, h / LED_H
        mk = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(mk)
        r = min(cell_x, cell_y) * 0.42
        for j in range(LED_H):
            for i in range(LED_W):
                cx, cy = (i + 0.5) * cell_x, (j + 0.5) * cell_y
                d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
        _DOTMASK = np.asarray(mk).astype(np.float32)[..., None] / 255
    return _DOTMASK


def led_text(img, xy, txt, size, col, weight="Black", anchor="mm", alpha=1.0):
    ImageDraw.Draw(img).text(xy, txt, font=font(weight, size), fill=tuple(int(c * alpha) for c in col), anchor=anchor)


def led_content(t):
    """Inhalt des Videowürfels in LED-Auflösung."""
    img = Image.new("RGB", (LED_W, LED_H), (0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = LED_W / 2, LED_H / 2
    if t < 1.3:
        wipe = e_io(t / 0.5)
        led_text(img, (cx, cy - 8), "FAN WALL", 34, WHITE)
        led_text(img, (cx, cy + 26), "#1", 18, BLUE, "Black")
        d.rectangle((LED_W * wipe, 0, LED_W, LED_H), fill=(0, 0, 0))
        if int(t * 8) % 2 == 0 and t > 0.5:
            d.rectangle((2, 2, LED_W - 3, LED_H - 3), outline=BLUE)
    elif t < 2.3:
        lt = t - 1.3
        led_text(img, (cx, cy - 6), "REQUESTED BY", 22, (200, 205, 215), "ExtraBold", alpha=e_out(lt / 0.3))
        for k in range(3):
            if (int(lt * 6) + k) % 3 == 0:
                d.ellipse((cx - 20 + k * 20 - 3, cy + 22, cx - 20 + k * 20 + 3, cy + 28), fill=BLUE)
    elif t < 3.6:
        lt = t - 2.3
        name = "@" + NAMES[0].upper()
        size = 30
        while size > 12 and sum(font("Black", size).getlength(ch) for ch in name) > LED_W - 16:
            size -= 2
        f = font("Black", size)
        total = sum(f.getlength(ch) for ch in name)
        x = cx - total / 2
        for i, ch in enumerate(name):
            p = c01((lt - i * 0.05) / 0.12)
            if p > 0:
                col = tuple(int(lerp(255, c, p)) for c in ORANGE) if p < 1 else ORANGE
                d.text((x, cy - 4), ch, font=f, fill=col, anchor="lm")
            x += f.getlength(ch)
        led_text(img, (cx, cy + 30), "THANK YOU!", 14, WHITE, "ExtraBold", alpha=e_out((lt - 0.7) / 0.3))
    else:
        lt = t - 3.6
        flash = int(lt * 6) % 2 == 0
        led_text(img, (cx, cy - 26), "NEXT UP", 16, RED if flash else WHITE, "Black")
        first, last = PLAYER.split(" ", 1)
        led_text(img, (cx, cy + 2), first, 22, WHITE, "Black", alpha=e_out(lt / 0.2))
        led_text(img, (cx, cy + 30), last, 30, BLUE, "Black", alpha=e_out((lt - 0.1) / 0.2))
    return img


def led_screen(t):
    w, h = JUMBO[2] - JUMBO[0], JUMBO[3] - JUMBO[1]
    c = led_content(t).resize((w, h), Image.NEAREST)
    arr = np.asarray(c).astype(np.float32) * led_dotmask() * 1.15 + 6
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")


# ================================================================= Arena
_ARENA = None
_CROWD = None


def arena_static():
    global _ARENA, _CROWD
    if _ARENA is None:
        yy, xx = np.mgrid[0:H + 400, 0:W].astype(np.float32)
        v = np.clip(1 - np.abs(yy - 700) / 1500, 0, 1)
        rgb = np.stack([4 + 10 * v, 6 + 14 * v, 12 + 32 * v], -1)
        img = Image.fromarray(rgb.astype(np.uint8)).convert("RGBA")
        d = ImageDraw.Draw(img)
        # Dachträger
        for k in range(-3, 12):
            d.line((k * 140, 0, 540 + (k - 4) * 40, 330), fill=(40, 46, 60, 255), width=3)
        d.line((0, 120, W, 120), fill=(40, 46, 60, 255), width=4)
        d.line((0, 260, W, 260), fill=(36, 42, 56, 255), width=3)
        # Seile zum Würfel
        for x in (260, 820):
            d.line((x, 0, x, JUMBO[1] - 40), fill=(60, 66, 80, 255), width=4)
        # Tribünen + Publikum (unten)
        crowd = Image.new("RGBA", (W, H + 400), (0, 0, 0, 0))
        cd = ImageDraw.Draw(crowd)
        for row in range(14):
            y = 1500 + row * 46
            shade = 18 + row * 3
            cd.rectangle((0, y - 20, W, y + 26), fill=(shade, shade + 2, shade + 10, 255))
            for k in range(28):
                x = k * 40 + rnd.uniform(-8, 8) + (row % 2) * 20
                rr = 14 + row * 0.6
                cd.ellipse((x - rr, y - rr - 10, x + rr, y + rr - 10), fill=(10, 12, 18, 255))
                cd.rounded_rectangle((x - rr * 1.4, y + rr - 12, x + rr * 1.4, y + 30), radius=8, fill=(10, 12, 18, 255))
        img.alpha_composite(crowd.filter(ImageFilter.GaussianBlur(1.5)))
        _ARENA = img
        _CROWD = [(rnd.uniform(0, W), rnd.uniform(1480, 2150), rnd.uniform(0, 6.28)) for _ in range(70)]
    return _ARENA


def jumbotron_frame(lay, t):
    d = ImageDraw.Draw(lay)
    x0, y0, x1, y1 = JUMBO
    # Seitenflächen (perspektivisch)
    d.polygon([(x0 - 70, y0 + 30), (x0, y0), (x0, y1), (x0 - 70, y1 - 30)], fill=(20, 22, 30, 255))
    d.polygon([(x1 + 70, y0 + 30), (x1, y0), (x1, y1), (x1 + 70, y1 - 30)], fill=(20, 22, 30, 255))
    for k in range(6):
        yy = y0 + 60 + k * 60
        d.line((x0 - 60, yy + 20 - k * 2, x0 - 10, yy), fill=(40, 90, 140, 120), width=3)
        d.line((x1 + 10, yy, x1 + 60, yy + 20 - k * 2), fill=(40, 90, 140, 120), width=3)
    # Rahmen oben/unten mit Lichtern
    d.rectangle((x0 - 74, y0 - 46, x1 + 74, y0), fill=(26, 28, 36, 255))
    d.rectangle((x0 - 74, y1, x1 + 74, y1 + 70), fill=(26, 28, 36, 255))
    for k in range(18):
        on = (int(t * 10) + k) % 4 != 0
        cx = x0 - 50 + k * 51
        col = (255, 220, 120, 255) if on else (80, 70, 40, 255)
        d.ellipse((cx - 5, y0 - 28, cx + 5, y0 - 18), fill=col)
    # Laufband unter dem Würfel
    band = Image.new("RGBA", (x1 - x0 + 148, 50), (0, 0, 0, 255))
    msg = "  FAN WALL  •  BLADESANDPUCKS  •  COMMENT YOUR PLAYER  •" * 3
    ImageDraw.Draw(band).text((-(t * 160) % 900, 25), msg, font=font("ExtraBold", 26), fill=ORANGE + (255,), anchor="lm")
    lay.alpha_composite(band, (x0 - 74, y1 + 10))


def spotlights(lay, t):
    for k, (bx, sp, ph) in enumerate(((180, 0.7, 0.0), (900, 0.6, 1.7), (540, 0.9, 3.1))):
        ang = math.sin(t * sp + ph) * 0.45
        top = (bx, 60)
        length = 2000
        w = 220
        tip = (bx + math.sin(ang) * length, 60 + math.cos(ang) * length)
        nx, ny = math.cos(ang) * w, -math.sin(ang) * w
        beam = layer()
        ImageDraw.Draw(beam).polygon([top, (tip[0] - nx, tip[1] - ny), (tip[0] + nx, tip[1] + ny)], fill=(140, 180, 255, 26))
        lay.alpha_composite(beam.filter(ImageFilter.GaussianBlur(30)))


def comment_sticker(lay, lt):
    """TikTok-Antwort-Sticker: 'Antwort auf @name' + Kommentar."""
    p = e_back(lt / 0.4)
    if p <= 0:
        return
    user, text = COMMENT
    card = Image.new("RGBA", (700, 170), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle((0, 0, 699, 169), radius=26, fill=(255, 255, 255, 255))
    cd.ellipse((26, 30, 106, 110), fill=(60, 140, 220, 255))
    cd.text((66, 70), user[0].upper(), font=font("Black", 44), fill=(255, 255, 255), anchor="mm")
    cd.text((128, 50), f"Reply to {user}'s comment", font=font("SemiBold", 28), fill=(120, 120, 128), anchor="lm")
    cd.text((128, 104), text, font=font("ExtraBold", 44), fill=(18, 18, 22), anchor="lm")
    w, h = int(700 * p), int(170 * p)
    if w > 10:
        card = card.resize((w, h), Image.BILINEAR)
        lay.alpha_composite(card, (int(W / 2 - w / 2), int(1250 - h / 2)))


def goal_beacons(lay, lt):
    if lt <= 0:
        return
    on = int(lt * 6) % 2 == 0
    if not on:
        return
    gl = layer()
    gd = ImageDraw.Draw(gl)
    for x in (60, W - 60):
        gd.ellipse((x - 60, 330, x + 60, 450), fill=RED + (255,))
    glow_onto(lay, gl, 160, 1.6)


def arena(t):
    tilt = 1 - e_io(t / 1.0)
    img = arena_static().crop((0, int(380 * tilt), W, int(380 * tilt) + H)).copy()
    spotlights(img, t)
    jl = layer()
    jumbotron_frame(jl, t)
    jl.alpha_composite(led_screen(t), (JUMBO[0], JUMBO[1]))
    glow = layer()
    glow.alpha_composite(led_screen(t), (JUMBO[0], JUMBO[1]))
    glow_onto(jl, glow, 60, 0.55, keep=False)
    off = int(-380 * tilt)
    shifted = layer()
    shifted.alpha_composite(jl, (0, off))
    img.alpha_composite(shifted)
    # Handyblitze im Publikum
    fl = ImageDraw.Draw(img)
    for x, y, ph in _CROWD:
        if math.sin(t * 9 + ph * 7) > 0.97:
            yy = y - 380 * tilt
            fl.ellipse((x - 5, yy - 5, x + 5, yy + 5), fill=(255, 255, 255, 230))
    if t > 2.3:
        comment_sticker(img, t - 2.3)
    goal_beacons(img, t - 3.6)
    return img


# ================================================================= Spieler-Animation (Studio-Stil)
def sc_name(lt):
    L = layer()
    d = ImageDraw.Draw(L)
    y_line = 760
    lw = 780 * e_io((lt - 0.05) / 0.5)
    if lw > 2:
        d.rectangle((W / 2 - lw / 2, y_line - 1.5, W / 2 + lw / 2, y_line + 1.5), fill=WHITE + (255,))
    up = layer()
    tracked(up, PLAYER, W / 2, y_line - 55, 80, "ExtraBold", WHITE, 10,
            per_letter=lambda i, n: (0, 100 * (1 - e_out((lt - 0.25 - i * 0.03) / 0.5)), 1))
    L.alpha_composite(masked(up, (0, 0, W, y_line - 4)))
    down = layer()
    tracked(down, '"THE RAT"', W / 2, y_line + 48, 40, "ExtraBold", ORANGE, 14,
            per_letter=lambda i, n: (0, -70 * (1 - e_out((lt - 0.55 - i * 0.03) / 0.45)), 1))
    L.alpha_composite(masked(down, (0, y_line + 4, W, H)))
    if lt > 0.8:
        num = layer()
        tracked(num, "#", W / 2 - 230, 1120, 200, "Black", BLUE, 0, anchor_x="left", alpha=e_out((lt - 0.8) / 0.3))
        odometer(num, "63", W / 2 + 60, 1120, 330, c01((lt - 0.8) / 1.0), "Black", WHITE)
        light_sweep(num, c01((lt - 1.7) / 0.5))
        L.alpha_composite(num)
    return L


def sc_draft(lt):
    L = layer()
    head = layer()
    tracked(head, "DRAFTED", W / 2, 520, 44, "Bold", DIM, 22,
            per_letter=lambda i, n: (0, 40 * (1 - e_out((lt - i * 0.03) / 0.4)), e_out((lt - i * 0.03) / 0.4)))
    L.alpha_composite(masked(head, (0, 465, W, 570)))
    num = layer()
    odometer(num, "71", W / 2 - 60, 860, 400, c01((lt - 0.15) / 1.0), "Black", WHITE)
    tracked(num, "ST", W / 2 + 180, 760, 90, "Black", WHITE, 0, anchor_x="left", alpha=e_out((lt - 0.9) / 0.3))
    light_sweep(num, c01((lt - 1.1) / 0.5))
    L.alpha_composite(num)
    sub = layer()
    tracked(sub, "OVERALL · 2006 · ROUND 3", W / 2, 1110, 36, "Bold", BLUE, 8,
            per_letter=lambda i, n: (0, 0, e_out((lt - 0.7 - i * 0.02) / 0.3)))
    L.alpha_composite(sub)
    if lt > 1.3:
        p = e_back((lt - 1.3) / 0.4)
        tag = layer()
        td = ImageDraw.Draw(tag)
        w, h = 560 * p, 100 * p
        td.rounded_rectangle((W / 2 - w / 2, 1300 - h / 2, W / 2 + w / 2, 1300 + h / 2), radius=h / 2, outline=ORANGE + (255,), width=4)
        if p > 0.3:
            tracked(tag, "NOBODY SAW IT COMING", W / 2, 1300, int(34 * min(1, p)), "ExtraBold", ORANGE, 4)
        glow_onto(L, tag, 30, 0.8)
    return L


def sc_cups(lt):
    L = layer()
    head = layer()
    tracked(head, "STANLEY CUP CHAMPION", W / 2, 470, 44, "Bold", WHITE, 12,
            per_letter=lambda i, n: (0, 40 * (1 - e_out((lt - i * 0.02) / 0.4)), e_out((lt - i * 0.02) / 0.4)))
    L.alpha_composite(masked(head, (0, 415, W, 520)))
    for k, (year, team, cx) in enumerate((("2011", "BOSTON", W / 2 - 230), ("2025", "FLORIDA", W / 2 + 230))):
        p = e_out((lt - 0.2 - k * 0.35) / 0.5)
        if p <= 0:
            continue
        cup = chrome_cup(p)
        sc_ = 0.55
        cw, ch = int(W * sc_), int(H * sc_)
        cup_s = cup.resize((cw, ch), Image.BILINEAR)
        red = layer()
        ImageDraw.Draw(red).ellipse((cx - 170, 640, cx + 170, 1080), fill=(RED if k == 1 else BLUE) + (int(150 * p),))
        glow_onto(L, red, 180, 2.0, keep=False)
        L.alpha_composite(cup_s, (int(cx - cw / 2), int(860 - ch * 960 / H)))
        num = layer()
        odometer(num, year, cx, 1240, 110, c01((lt - 0.4 - k * 0.35) / 0.9), "Black", WHITE, stagger=0.08, spins=1)
        tracked(num, team, cx, 1340, 32, "Bold", DIM, 10, alpha=e_out((lt - 0.9 - k * 0.35) / 0.3))
        L.alpha_composite(num)
    if lt > 1.6:
        big = layer()
        tracked(big, "2×", W / 2, 1530, 120, "Black", ORANGE, 0, alpha=e_out((lt - 1.6) / 0.3))
        glow_onto(L, big, 30, 0.6)
    return L


def sc_credit(lt):
    L = layer()
    d = ImageDraw.Draw(L)
    head = layer()
    tracked(head, "REQUESTED BY", W / 2, 700, 40, "Bold", DIM, 20,
            per_letter=lambda i, n: (0, 40 * (1 - e_out((lt - i * 0.03) / 0.4)), e_out((lt - i * 0.03) / 0.4)))
    L.alpha_composite(masked(head, (0, 650, W, 750)))
    name = layer()
    tracked(name, "@" + NAMES[0], W / 2, 830, 96, "Black", WHITE, 2,
            per_letter=lambda i, n: (0, 0, e_out((lt - 0.3 - i * 0.04) / 0.25)))
    light_sweep(name, c01((lt - 0.9) / 0.6))
    glow_onto(L, name, 30, 0.5)
    lw = 520 * e_io((lt - 0.6) / 0.5)
    d.rectangle((W / 2 - lw / 2, 920, W / 2 + lw / 2, 923), fill=BLUE + (255,))
    cta = layer()
    tracked(cta, "WANT YOUR NAME ON THE WALL?", W / 2, 1040, 40, "ExtraBold", WHITE, 4,
            per_letter=lambda i, n: (0, 0, e_out((lt - 1.0 - i * 0.015) / 0.3)))
    tracked(cta, "COMMENT YOUR PLAYER", W / 2, 1110, 52, "Black", ORANGE, 4,
            per_letter=lambda i, n: (0, 0, e_out((lt - 1.3 - i * 0.02) / 0.3)))
    L.alpha_composite(cta)
    if lt > 1.6:
        y = 1210 + abs(math.sin(lt * 6)) * 26
        d.polygon([(W / 2 - 40, y), (W / 2 + 40, y), (W / 2, y + 52)], fill=ORANGE + (255,))
    return L


SCENES = [(5.6, 7.9, sc_name), (7.9, 10.0, sc_draft), (10.0, 12.2, sc_cups), (12.2, 14.5, sc_credit)]
XF = 0.25


def studio(t):
    img = s.background(t)
    for a, b, fn in SCENES:
        if a - XF <= t < b + XF:
            L = fn(max(0.0, t - a))
            sc_, al = 1.0, 1.0
            if t > b - XF and b < DUR:
                q = e_in(c01((t - (b - XF)) / (2 * XF)), 2)
                sc_, al = 1 + 0.35 * q, 1 - q
            if t < a + XF and a > 5.7:
                q = e_out(c01((t - (a - XF)) / (2 * XF)), 3)
                sc_, al = 0.86 + 0.14 * q, q
            if al <= 0.01:
                continue
            if abs(sc_ - 1) > 0.002:
                big = L.resize((int(W * sc_), int(H * sc_)), Image.BILINEAR)
                if sc_ > 1:
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


# ================================================================= Gesamtbild + Kamera
def render_t(t):
    if t < 4.8:
        return arena(t).convert("RGB")
    if t < 5.6:
        # Flug in den Videowürfel: Zoom auf die Screenmitte, dann Blitz
        z = e_in((t - 4.8) / 0.8, 3)
        a = arena(min(t, 4.79))
        cx, cy = (JUMBO[0] + JUMBO[2]) / 2, (JUMBO[1] + JUMBO[3]) / 2
        sc_ = 1 + 7 * z
        wv, hv = W / sc_, H / sc_
        out = a.transform((W, H), Image.EXTENT, (cx - wv / 2, cy - hv / 2, cx + wv / 2, cy + hv / 2), Image.BILINEAR)
        fl = c01((t - 5.25) / 0.35)
        if fl > 0:
            st = studio(5.6).convert("RGBA")
            out = Image.blend(out.convert("RGBA"), Image.new("RGBA", (W, H), (220, 240, 255, 255)), min(1, fl * 1.6))
            if fl > 0.6:
                out = Image.blend(out, st, (fl - 0.6) / 0.4)
        return out.convert("RGB")
    return studio(t).convert("RGB")


def is_fast(t):
    return 4.8 < t < 5.65 or any(abs(t - b) < XF for b in (7.9, 10.0, 12.2))


def render_frame(i):
    t = i / FPS
    if is_fast(t):
        acc = sum(np.asarray(render_t(max(0, t + dt))).astype(np.float32) for dt in (-1 / 90, 0, 1 / 90)) / 3
    else:
        acc = np.asarray(render_t(t)).astype(np.float32)
    acc += np.random.default_rng(i).normal(0, 3.0, acc.shape[:2])[..., None]
    return np.clip(acc, 0, 255).astype(np.uint8).tobytes()


# ================================================================= Sound: Arena + Studio
SR = 44100


def make_audio(path):
    n = int(DUR * SR)
    out = np.zeros(n)
    rng = np.random.default_rng(21)

    def add(sig, at, vol=1.0):
        st = int(at * SR)
        e = min(n, st + len(sig))
        if 0 <= st < n:
            out[st:e] += sig[: e - st] * vol

    def tt(sec):
        return np.arange(int(sec * SR)) / SR

    def lp(x, k):
        return np.convolve(x, np.ones(k) / k, mode="same")

    # Publikum (gefiltertes Rauschen mit Wellen), bis zum Flug in den Würfel
    ct = tt(5.6)
    crowd = lp(rng.standard_normal(len(ct)), 25) * (0.25 + 0.15 * np.sin(ct * 1.3)) * np.clip((5.6 - ct) / 0.5, 0, 1)
    add(crowd * 1.4, 0.0)
    # Orgel "Charge!" (G C E G – E G)
    def organ(f, d):
        x = tt(d)
        sig = sum(np.sin(2 * np.pi * f * h * x) / h for h in (1, 2, 3, 4))
        return sig * np.minimum(x / 0.02, 1) * np.clip((d - x) / 0.04, 0, 1) * 0.12
    seq = [(392, 0.16), (523.25, 0.16), (659.25, 0.16), (783.99, 0.32), (659.25, 0.14), (783.99, 0.5)]
    at = 0.25
    for f, d in seq:
        add(organ(f, d), at)
        at += d + 0.03
    # LED-Blips bei Namen
    bt = tt(0.08)
    blip = np.sin(2 * np.pi * 1800 * bt) * np.exp(-bt * 50) * 0.15
    for k in range(len("@" + NAMES[0])):
        add(blip, 2.3 + k * 0.05)
    # Torhupe + Jubel bei NEXT UP
    ht = tt(1.4)
    horn = sum(2 * ((f * ht) % 1) - 1 for f in (110, 138.6, 164.8))
    add(lp(horn, 12) * np.minimum(ht / 0.05, 1) * np.clip((1.4 - ht) / 0.3, 0, 1) * 0.3, 3.6)
    cheer = lp(rng.standard_normal(len(ht)), 10) * np.minimum(ht / 0.2, 1) * np.exp(-ht * 0.8) * 0.9
    add(cheer, 3.65)
    # Riser + Impact beim Flug in den Würfel
    rt = tt(0.8)
    add(lp(rng.standard_normal(len(rt)), 15) * (rt / 0.8) ** 2.5 * 0.7, 4.8)
    it = tt(1.0)
    add(np.sin(2 * np.pi * (32 + 70 * np.exp(-it * 9)) * it) * np.exp(-it * 2.6) * 0.9, 5.6)
    # Studio-Beat
    beat = 60 / 110
    kt = tt(0.3)
    kick = np.sin(2 * np.pi * (42 + 120 * np.exp(-kt * 32)) * kt) * np.exp(-kt * 9)
    hh = tt(0.05)
    hat = np.diff(rng.standard_normal(len(hh)), prepend=0) * np.exp(-hh * 80) * 0.12
    k = 0
    while 5.6 + k * beat < DUR - 0.4:
        add(kick, 5.6 + k * beat, 0.8)
        add(hat, 5.6 + k * beat + beat / 2)
        k += 1
    wt = tt(0.5)
    whoosh = lp(rng.standard_normal(len(wt)), 35) * np.sin(np.pi * wt / wt[-1]) ** 2 * 0.9
    for a in (7.65, 9.75, 11.95):
        add(whoosh, a)
    tk = tt(0.02)
    tick = np.sin(2 * np.pi * 3200 * tk) * np.exp(-tk * 300) * 0.12
    for start, d, cnt in ((6.4, 1.0, 12), (8.05, 1.0, 14), (10.4, 0.9, 10)):
        for j in range(cnt):
            add(tick, start + d * (j / cnt) ** 0.6)
    fade = np.clip((DUR - np.arange(n) / SR) / 0.6, 0, 1)
    out *= fade
    out /= max(1e-6, np.max(np.abs(out))) * 1.1
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((out * 32767).astype(np.int16).tobytes())


def main():
    os.chdir(HERE)
    make_audio("audio_fanwall.wav")
    nf = int(DUR * FPS)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_fanwall.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "23",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
           "reel11_fanwall.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(4) as pool:
        for k, buf in enumerate(pool.imap(render_frame, range(nf), chunksize=4)):
            proc.stdin.write(buf)
            if k % 60 == 0:
                print(f"{k}/{nf}", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.frombytes("RGB", (W, H), render_frame(int(3.0 * FPS))).save("reel11_thumbnail.jpg", quality=92)
    print("fertig: reel11_fanwall.mp4")


if __name__ == "__main__":
    main()
