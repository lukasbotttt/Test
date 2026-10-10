"""Reel 9: "POV: you make smooth animations for hockey" – im Stil von @__mcvisuals__ (Opal Spec Ad).

Aufbau wie das Vorbild: Text-Bubble oben, Monitor mit After-Effects-Oberfläche (Viewer + lila Timeline),
darunter Schreibtisch im lila Licht. Im Viewer läuft eine cleane, dunkle UI-Animation zu Wayne Gretzky.
Fakten (NHL-Karriere): 894 Tore, 1.963 Assists, 2.857 Punkte; Tore pro Saison 1979/80–1998/99;
Rekordsaison 1981/82 mit 92 Toren; 4 Stanley Cups, 9 Hart Trophies, 10 Art Ross Trophies.
Aufruf: python3 reel9_pov.py  ->  reel9_pov.mp4
"""
import math
import os
import random
import subprocess
import wave

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

import make_hockey_reel as m
from make_hockey_reel import font, clamp, puck

W, H, FPS = 1080, 1920, 30
CW, CH = 1280, 720                       # Größe der Komposition im Viewer
DUR = 12.0
HERE = m.HERE
GOALS = [51, 55, 92, 71, 87, 73, 52, 62, 40, 54, 40, 41, 31, 16, 38, 11, 23, 25, 23, 9]
BLUE = (70, 200, 255)
ORANGE = (255, 150, 70)
TXT = (235, 235, 240)
DIM = (120, 120, 130)
VIEW = (120, 575, 960, 1048)             # Viewer-Rechteck im Endbild (x0, y0, x1, y1)
rnd = random.Random(3)


# ---------------------------------------------------------------- Easing
def ease(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def ease_out(t, p=3):
    t = clamp(t)
    return 1 - (1 - t) ** p


def ease_back(t, s=1.4):
    t = clamp(t) - 1
    return t * t * ((s + 1) * t + s) + 1


# ---------------------------------------------------------------- Text (clean, ohne Kontur)
def ctext(img, xy, txt, size, fill=TXT, weight="SemiBold", anchor="mm", alpha=1.0):
    if alpha <= 0.01:
        return
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(xy, txt, font=font(weight, size), fill=fill + (int(255 * alpha),), anchor=anchor)
    img.alpha_composite(layer)


def glow(img, layer, radius=18, strength=1.0):
    """Leuchten: weichgezeichnete Kopie per 'screen' auf das Bild legen, dann das Original drüber."""
    g = layer.filter(ImageFilter.GaussianBlur(radius))
    if strength != 1.0:
        g.putalpha(g.getchannel("A").point(lambda v: int(min(255, v * strength))))
    base = img.convert("RGB")
    lit = Image.alpha_composite(Image.new("RGBA", img.size, (0, 0, 0, 255)), g).convert("RGB")
    img.paste(ImageChops.screen(base, lit).convert("RGBA"))
    img.alpha_composite(layer)


# ---------------------------------------------------------------- Icons
def icon(d, kind, cx, cy, s, col):
    c = col + (255,)
    if kind == "puck":
        d.ellipse((cx - 11 * s, cy - 2 * s, cx + 11 * s, cy + 8 * s), fill=c)
        d.ellipse((cx - 11 * s, cy - 8 * s, cx + 11 * s, cy + 2 * s), fill=c)
    elif kind == "stick":
        d.line((cx - 8 * s, cy - 11 * s, cx + 2 * s, cy + 7 * s), fill=c, width=max(2, int(4 * s)))
        d.line((cx + 1 * s, cy + 8 * s, cx + 12 * s, cy + 8 * s), fill=c, width=max(2, int(5 * s)))
    elif kind == "star":
        pts = []
        for k in range(10):
            r = 11 * s if k % 2 == 0 else 4.6 * s
            a = -math.pi / 2 + k * math.pi / 5
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
        d.polygon(pts, fill=c)
    elif kind == "cup":
        d.ellipse((cx - 14 * s, cy - 20 * s, cx + 14 * s, cy - 12 * s), fill=c)
        d.polygon([(cx - 14 * s, cy - 16 * s), (cx + 14 * s, cy - 16 * s), (cx + 6 * s, cy - 2 * s), (cx - 6 * s, cy - 2 * s)], fill=c)
        d.rectangle((cx - 5 * s, cy - 2 * s, cx + 5 * s, cy + 4 * s), fill=c)
        for k, wdt in enumerate((9, 11, 13)):
            d.rectangle((cx - wdt * s, cy + (4 + k * 6) * s, cx + wdt * s, cy + (9 + k * 6) * s), fill=c)


def pill(img, cx, cy, kind, value, label, scale=1.0, alpha=1.0, arc=1.0):
    """Abgerundete Pille mit Icon + Zahl (wie im Vorbild), Label darunter, heller Bogen oben rechts."""
    if scale <= 0.02 or alpha <= 0.02:
        return
    w, h = 210 * scale, 92 * scale
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    a = int(255 * alpha)
    d.rounded_rectangle((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), radius=h / 2,
                        fill=(26, 26, 30, a), outline=(85, 85, 95, a), width=max(1, int(2 * scale)))
    if arc > 0:  # heller Glanzbogen
        d.arc((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2 + h * 0.6), 200, 200 + 140 * arc,
              fill=(230, 230, 240, a), width=max(2, int(4 * scale)))
    icon(d, kind, cx - w / 2 + 48 * scale, cy, 1.15 * scale, (215, 215, 225))
    d.text((cx - w / 2 + 80 * scale, cy), value, font=font("Medium", int(44 * scale)), fill=TXT + (a,), anchor="lm")
    img.alpha_composite(layer)
    ctext(img, (cx, cy + h / 2 + 34 * scale), label, int(24 * scale), DIM, "Medium", alpha=alpha)


# ---------------------------------------------------------------- Komposition (Viewer-Inhalt)
VIGN = None


def comp_bg():
    global VIGN
    if VIGN is None:
        yy, xx = np.mgrid[0:CH, 0:CW].astype(np.float32)
        r = np.sqrt(((xx - CW / 2) / CW) ** 2 + ((yy - CH * 0.45) / CH) ** 2)
        v = np.clip(30 - r * 38, 6, 30)
        VIGN = Image.fromarray(np.stack([v, v, v * 1.05], -1).astype(np.uint8)).convert("RGBA")
    return VIGN.copy()


TEXT99 = None


def particles_99():
    global TEXT99
    if TEXT99 is None:
        mask = Image.new("L", (CW, CH), 0)
        ImageDraw.Draw(mask).text((CW / 2, CH / 2), "99", font=font("Bold", 300), fill=255, anchor="mm")
        ys, xs = np.nonzero(np.asarray(mask)[::4, ::4] > 128)
        pts = list(zip(xs * 4, ys * 4))
        rr = random.Random(9)
        rr.shuffle(pts)
        TEXT99 = [(x, y, rr.uniform(-1, 1), rr.uniform(-1, 1), rr.uniform(0.6, 1.4)) for x, y in pts[:1600]]
    return TEXT99


def scene_bars(img, t):
    """0–2.4 s: Tore pro Saison als Balken, Rekordsaison leuchtet."""
    d = ImageDraw.Draw(img)
    n = len(GOALS)
    x0, x1, base, top = 150, 1130, 560, 230
    bw = (x1 - x0) / n * 0.62
    out = ease(clamp((t - 2.05) / 0.35))  # Balken fallen am Ende zusammen
    # Raster + Durchschnittslinie
    for k in range(4):
        y = base - (top - base) * -k / 3 * -1
        d.line((x0 - 20, base - k * (base - top) / 3, x1 + 10, base - k * (base - top) / 3), fill=(40, 40, 46), width=1)
    avg_y = base - (sum(GOALS) / n) / 92 * (base - top)
    for xx in range(x0 - 20, x1 + 10, 18):
        d.line((xx, avg_y, xx + 9, avg_y), fill=(150, 150, 160), width=2)
    ctext(img, (x1 + 50, avg_y), "avg", 26, (110, 110, 120), "Medium")
    hl = Image.new("RGBA", img.size, (0, 0, 0, 0))
    for i, g in enumerate(GOALS):
        p = ease_out((t - 0.15 - i * 0.035) / 0.6) * (1 - out)
        if p <= 0:
            continue
        h = g / 92 * (base - top) * p
        cx = x0 + (i + 0.5) * (x1 - x0) / n
        box = (cx - bw / 2, base - h, cx + bw / 2, base)
        if i == 2:  # 1981/82: 92 Tore
            hd = ImageDraw.Draw(hl)
            for k in range(int(h)):
                f = k / max(h, 1)
                col = tuple(int(BLUE[j] + (ORANGE[j] - BLUE[j]) * f) for j in range(3))
                hd.line((box[0], base - h + k, box[2], base - h + k), fill=col + (255,))
        else:
            d.rectangle(box, fill=(58, 58, 64))
            d.rectangle((box[0], box[1], box[2], box[1] + 4), fill=(85, 85, 92))
        if i % 5 == 0:
            ctext(img, (cx, base + 30), f"'{(79 + i) % 100:02d}", 20, (95, 95, 105), "Medium", alpha=1 - out)
    glow(img, hl, 22, 1.6)
    n_goals = int(894 * ease_out((t - 0.2) / 1.6))
    ctext(img, (x1, 105), f"{n_goals}", 74, TXT, "Light", anchor="rm", alpha=1 - out)
    ctext(img, (x1, 160), "career goals · Wayne Gretzky", 26, DIM, "Medium", anchor="rm", alpha=1 - out)
    if t > 1.2:
        a = ease((t - 1.2) / 0.3) * (1 - out)
        cx = x0 + 2.5 * (x1 - x0) / n
        ctext(img, (cx, top - 34), "92 · 1981–82", 26, ORANGE, "SemiBold", alpha=a)


def scene_pills(img, t):
    """2.4–5.9 s: Pillen erscheinen, dann 'Points'-Score mit Klammer (wie 'Score 40▲')."""
    lt = t - 2.4
    spread = ease(clamp((lt - 0.7) / 0.5))
    rise = ease(clamp((lt - 1.9) / 0.5))
    cy = 380 + 110 * rise
    data = [("puck", 894, "Goals"), ("stick", 1963, "Assists"), ("star", 2857, "Points")]
    for i, (kind, val, lab) in enumerate(data):
        if i == 0:
            sc = ease_back(lt / 0.45)
            cx = CW / 2 - 320 * spread
        else:
            # kommen erst hinter der ersten Pille hervor, wenn genug Platz ist
            p = ease_out((lt - 0.95 - (i - 1) * 0.1) / 0.4)
            if p <= 0:
                continue
            sc = 0.7 + 0.3 * p
            cx = CW / 2 + (i - 1) * 320 * spread
        shown = int(val * ease_out((lt - 0.2 - i * 0.25) / 1.1))
        pill(img, cx, cy, kind, f"{shown:,}", lab, scale=sc, alpha=clamp(sc * 1.4), arc=ease((lt - 0.3) / 0.8))
    if rise > 0:
        d = ImageDraw.Draw(img)
        a = int(255 * rise)
        yb = cy - 105
        d.line((CW / 2 - 320, yb + 20, CW / 2 - 320, yb), fill=(200, 200, 210, a), width=3)
        d.line((CW / 2 + 320, yb + 20, CW / 2 + 320, yb), fill=(200, 200, 210, a), width=3)
        d.line((CW / 2 - 320, yb, CW / 2 + 320, yb), fill=(200, 200, 210, a), width=3)
        d.line((CW / 2, yb, CW / 2, yb - 22), fill=(200, 200, 210, a), width=3)
        pts = int(2857 * ease_out((lt - 2.0) / 1.0))
        ctext(img, (CW / 2, 165), "Points", 34, (170, 170, 180), "Medium", alpha=rise)
        ctext(img, (CW / 2 - 18, 245), f"{pts:,}", 96, TXT, "Light", alpha=rise)
        tri_x = CW / 2 + 140
        d.polygon([(tri_x - 13, 262), (tri_x + 13, 262), (tri_x, 240)], fill=(220, 220, 230, a))


def scene_99(img, t):
    """5.9–7.9 s: '99' leuchtet, zerfällt in Partikel, Pokal mit rotem Glühen erscheint."""
    lt = t - 5.9
    burst = ease_out(clamp((lt - 0.7) / 0.9), 2)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if lt < 0.75:
        a = ease(lt / 0.35)
        d.text((CW / 2, CH / 2), "99", font=font("Bold", 300), fill=(240, 240, 245, int(255 * a)), anchor="mm")
    else:
        for x, y, vx, vy, sp in particles_99():
            dx = (x - CW / 2) * 0.9 + vx * 220
            dy = (y - CH / 2) * 0.6 + vy * 160 - 60
            px, py = x + dx * burst * sp, y + dy * burst * sp
            a = int(255 * clamp(1 - burst * 1.1))
            if a > 0:
                r = 2.2 - burst
                d.ellipse((px - r, py - r, px + r, py + r), fill=(235, 235, 245, a))
    glow(img, layer, 14, 1.2)
    if lt > 1.0:
        p = ease_back((lt - 1.0) / 0.45)
        red = Image.new("RGBA", img.size, (0, 0, 0, 0))
        rd = ImageDraw.Draw(red)
        s = 120 * p
        rd.rounded_rectangle((CW / 2 - s, CH / 2 - s, CW / 2 + s, CH / 2 + s), radius=40 * p, outline=(255, 40, 50, 255), width=6)
        glow(img, red, 30, 1.4)
        d2 = ImageDraw.Draw(img)
        d2.rounded_rectangle((CW / 2 - s * 0.82, CH / 2 - s * 0.82, CW / 2 + s * 0.82, CH / 2 + s * 0.82),
                             radius=34 * p, fill=(34, 34, 38, 255))
        icon(d2, "cup", CW / 2, CH / 2 + 4, 2.6 * p, (240, 240, 245))
        ctext(img, (CW / 2, CH / 2 + 180), "4× Stanley Cup", 36, TXT, "SemiBold", alpha=ease((lt - 1.3) / 0.4))


def scene_list(img, t):
    """7.9–9.6 s: Karte mit Trophäen-Liste, Schalter klappen auf 'an' (wie 'Blocked Apps')."""
    lt = t - 7.9
    d = ImageDraw.Draw(img)
    card_p = ease_out(lt / 0.5)
    y0 = 150 + (1 - card_p) * 40
    a = int(255 * card_p)
    d.rounded_rectangle((CW / 2 - 300, y0, CW / 2 + 300, y0 + 420), radius=36, fill=(24, 24, 28, a), outline=(60, 60, 68, a), width=2)
    ctext(img, (CW / 2 - 250, y0 + 55), "Trophy Case", 34, TXT, "SemiBold", anchor="lm", alpha=card_p)
    items = [("cup", "Stanley Cup", "×4"), ("star", "Hart Trophy (MVP)", "×9"), ("puck", "Art Ross (Top Scorer)", "×10")]
    for i, (kind, lab, cnt) in enumerate(items):
        p = ease_out((lt - 0.3 - i * 0.2) / 0.4)
        if p <= 0:
            continue
        y = y0 + 140 + i * 95
        x_off = (1 - p) * 60
        icon(d, kind, CW / 2 - 235 + x_off, y, 1.2, (210, 210, 220))
        ctext(img, (CW / 2 - 200 + x_off, y), lab, 30, TXT, "Medium", anchor="lm", alpha=p)
        ctext(img, (CW / 2 + 140 + x_off, y), cnt, 30, DIM, "SemiBold", anchor="lm", alpha=p)
        on = ease((lt - 0.7 - i * 0.2) / 0.3)
        tx = CW / 2 + 215
        col = tuple(int(70 + (BLUE[j] - 70) * on) for j in range(3))
        d.rounded_rectangle((tx, y - 18, tx + 64, y + 18), radius=18, fill=col + (int(255 * p),))
        kx = tx + 18 + 28 * on
        d.ellipse((kx - 14, y - 14, kx + 14, y + 14), fill=(245, 245, 250, int(255 * p)))


def scene_button(img, t):
    """9.6–10.5 s: 'Play'-Button wird gedrückt, Lichtstreif läuft drüber."""
    lt = t - 9.6
    d = ImageDraw.Draw(img)
    press = 1 - 0.08 * math.sin(math.pi * clamp((lt - 0.35) / 0.25))
    w, h = 520 * press, 96 * press
    a = int(255 * ease(lt / 0.3))
    d.rounded_rectangle((CW / 2 - w / 2, CH / 2 - h / 2, CW / 2 + w / 2, CH / 2 + h / 2), radius=h / 2,
                        fill=(52, 52, 60, a), outline=(110, 110, 125, a), width=2)
    sweep = clamp((lt - 0.45) / 0.4)
    if 0 < sweep < 1:
        sx = CW / 2 - w / 2 + w * sweep
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).rectangle((sx - 30, CH / 2 - h / 2, sx + 30, CH / 2 + h / 2), fill=(255, 255, 255, 90))
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12)))
    d.polygon([(CW / 2 - 60, CH / 2 - 14), (CW / 2 - 60, CH / 2 + 14), (CW / 2 - 38, CH / 2)], fill=(235, 235, 240, a))
    ctext(img, (CW / 2 + 10, CH / 2), "Play", 34, TXT, "Medium", alpha=a / 255)


def scene_logo(img, t):
    """10.5–12 s: Wortmarke 'The Great One', danach Abblende."""
    lt = t - 10.5
    a = ease(lt / 0.5) * (1 - ease((lt - 1.05) / 0.4))
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((CW / 2, CH / 2), "The Great One", font=font("SemiBold", 92),
                               fill=(245, 245, 250, int(255 * a)), anchor="mm")
    blur = (1 - ease(lt / 0.5)) * 8
    if blur > 0.3:
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
    glow(img, layer, 10, 0.6)


def comp_frame(t):
    img = comp_bg()
    if t < 2.4:
        scene_bars(img, t)
    elif t < 5.9:
        scene_pills(img, t)
    elif t < 7.9:
        scene_99(img, t)
    elif t < 9.6:
        scene_list(img, t)
    elif t < 10.5:
        scene_button(img, t)
    else:
        scene_logo(img, t)
    # weiche Szenenblende (kurzer Dip ins Schwarze)
    for b in (2.4, 5.9, 7.9, 9.6, 10.5):
        k = abs(t - b)
        if k < 0.12:
            img.alpha_composite(Image.new("RGBA", img.size, (0, 0, 0, int(200 * (1 - k / 0.12)))))
    return img


# ---------------------------------------------------------------- Umgebung: Wand, Monitor (After Effects), Schreibtisch
def build_static():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    # Wand oben (hell, lila Schimmer)
    wall = np.stack([232 - yy * 0.02, 230 - yy * 0.02, 242 - yy * 0.01], -1)
    wall += (np.exp(-((xx - W) / 500) ** 2 - ((yy - 300) / 400) ** 2) * np.array([-20, -25, 5]))[..., None].squeeze() if False else 0
    img.paste(Image.fromarray(np.clip(wall, 0, 255).astype(np.uint8)), (0, 0))
    d = ImageDraw.Draw(img)
    # Wand hinter dem Monitor (hell, rechts lila angestrahlt) + Tischplatte (hellgrau, lila Licht von rechts)
    yy2, xx2 = np.mgrid[1300:H, 0:W].astype(np.float32)
    light = np.exp(-((xx2 - W * 0.95) / 520) ** 2)
    wall2 = np.stack([200 - 60 * light, 196 - 70 * light, 222 + 25 * light], -1)
    grain = np.random.default_rng(1).normal(0, 3.5, wall2.shape[:2])[..., None]
    wall2 = wall2 + grain
    desk_top = 1500
    on_desk = yy2 >= desk_top
    depth = np.clip((yy2 - desk_top) / (H - desk_top), 0, 1)
    desk = np.stack([150 - 40 * depth - 50 * light, 144 - 40 * depth - 60 * light, 160 - 30 * depth + 50 * light], -1)
    desk = desk * (0.85 + 0.15 * np.exp(-((xx2 - W * 0.35) / 700) ** 2))[..., None]
    mix = np.where(on_desk[..., None], desk, wall2)
    img.paste(Image.fromarray(np.clip(mix, 0, 255).astype(np.uint8)), (0, 1300))
    d.rectangle((0, desk_top - 4, W, desk_top + 6), fill=(190, 185, 205))   # Tischkante (Lichtkante)
    # Monitor-Standfuß
    d.rectangle((W / 2 + 120, 1300, W / 2 + 165, desk_top + 30), fill=(205, 205, 212))
    d.rounded_rectangle((W / 2 + 40, desk_top + 20, W / 2 + 245, desk_top + 48), radius=10, fill=(190, 190, 198))
    # Monitorgehäuse + After-Effects-Oberfläche
    d.rectangle((-10, 400, W + 10, 1312), fill=(14, 14, 16))
    ui = (34, 34, 38)
    d.rectangle((0, 410, W, 1300), fill=ui)
    d.rectangle((0, 410, W, 432), fill=(24, 24, 27))           # Menüleiste
    for k, wtxt in enumerate(("Layer", "Effect", "Animation", "View", "Window", "Help")):
        d.text((18 + k * 82, 421), wtxt, font=font("Medium", 15), fill=(190, 190, 195), anchor="lm")
    d.text((W / 2, 444), "Adobe After Effects  –  /Projects/bladesandpucks/gretzky_concept.aep *", font=font("Medium", 13),
           fill=(150, 150, 158), anchor="mm")
    d.rectangle((0, 456, W, 486), fill=(30, 30, 34))           # Werkzeugleiste
    for k in range(14):
        d.rounded_rectangle((16 + k * 34, 462, 38 + k * 34, 480), radius=4, fill=(70, 70, 78))
    for k, wtxt in enumerate(("Default", "Review", "Learn")):
        d.text((W - 250 + k * 85, 471), wtxt, font=font("Medium", 14), fill=(160, 160, 168), anchor="lm")
    d.rectangle((0, 490, 100, 1060), fill=(28, 28, 31))        # linkes Panel
    d.rectangle((980, 490, W, 1060), fill=(28, 28, 31))        # rechtes Panel
    for k in range(26):
        d.rectangle((990, 520 + k * 20, 990 + rnd.randint(40, 80), 528 + k * 20), fill=(60, 60, 66))
    d.text((112, 508), "Composition  Gretzky Spec Ad", font=font("Medium", 14), fill=(170, 170, 178), anchor="lm")
    d.rectangle((VIEW[0] - 2, VIEW[1] - 2, VIEW[2] + 2, VIEW[3] + 2), fill=(10, 10, 11))
    d.rectangle((100, 1052, 980, 1072), fill=(26, 26, 29))     # Viewer-Fußleiste
    for k, wtxt in enumerate(("50%", "Half", "0:00:04:12", "Draft 3D", "Active Camera", "1 View")):
        d.text((120 + k * 140, 1062), wtxt, font=font("Medium", 13), fill=(150, 150, 158), anchor="lm")
    # Timeline
    d.rectangle((0, 1080, W, 1300), fill=(29, 29, 33))
    d.rectangle((0, 1080, 300, 1300), fill=(31, 31, 35))
    for k in range(10):
        y = 1118 + k * 18
        d.rectangle((14, y, 26, y + 10), fill=(70, 70, 78))
        d.text((40, y + 5), ["Gretzky_Bars", "Null 12", "Pill_Goals", "Pill_Assists", "Pill_Points", "Score",
                             "99_Particles", "Trophy_Card", "Play_Btn", "Wordmark"][k],
               font=font("Medium", 12), fill=(165, 165, 172), anchor="lm")
    d.rectangle((300, 1086, W, 1104), fill=(36, 36, 40))       # Zeitlineal
    for k in range(12):
        x = 310 + k * 64
        d.line((x, 1094, x, 1104), fill=(110, 110, 118))
        d.text((x + 2, 1092), f"{k:02d}s", font=font("Medium", 10), fill=(120, 120, 128), anchor="lm")
    colors = [(150, 140, 235), (125, 115, 220), (170, 160, 240), (140, 130, 228)]
    for k in range(10):
        y = 1116 + k * 18
        x0 = 300 + rnd.randint(0, 260)
        d.rectangle((x0, y, min(W, x0 + rnd.randint(300, 700)), y + 13), fill=colors[k % 4])
    # Pucks auf dem Schreibtisch (leicht unscharf = Tiefenschärfe)
    props = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(props)
    for (px, py, pw) in ((230, 1690, 230), (520, 1760, 300), (850, 1660, 190)):
        pd.ellipse((px - pw * 0.62, py + pw * 0.05, px + pw * 0.62, py + pw * 0.32), fill=(30, 25, 50, 120))  # Schatten
    props = props.filter(ImageFilter.GaussianBlur(14))
    for (px, py, pw) in ((230, 1690, 230), (520, 1760, 300), (850, 1660, 190)):
        pk = puck(pw)
        props.alpha_composite(pk, (int(px - pk.width / 2), int(py - pk.height / 2)))
    img.alpha_composite(props.filter(ImageFilter.GaussianBlur(1.6)))
    # lila Licht von rechts auf der unteren Bildhälfte
    rim = np.zeros((H - 1300, W, 4), np.uint8)
    xs = np.arange(W, dtype=np.float32)
    rim[..., 0], rim[..., 1], rim[..., 2] = 110, 70, 255
    rim[..., 3] = (np.exp(-((xs - W) / 420) ** 2) * 70).astype(np.uint8)[None, :]
    img.alpha_composite(Image.fromarray(rim, "RGBA"), (0, 1300))
    return img


def caption(img):
    f = font("ExtraBold", 46)
    lines = ["POV: you make smooth", "animations for hockey"]
    widths = [f.getlength(s) for s in lines]
    bw, bh = max(widths) + 48, 2 * 56 + 30
    x0, y0 = W / 2 - bw / 2, 250
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), radius=18, fill=(255, 255, 255, 255))
    for k, s in enumerate(lines):
        d.text((W / 2, y0 + 15 + 28 + k * 56), s, font=f, fill=(10, 10, 12), anchor="mm")


STATIC = None


def frame(t):
    global STATIC
    if STATIC is None:
        STATIC = build_static()
    img = STATIC.copy()
    d = ImageDraw.Draw(img)
    # Playhead in der Timeline
    px = 300 + (W - 300) * t / DUR
    d.rectangle((300, 1086, px, 1092), fill=(90, 160, 255))
    d.line((px, 1086, px, 1300), fill=(90, 160, 255), width=2)
    d.polygon([(px - 6, 1086), (px + 6, 1086), (px, 1095)], fill=(90, 160, 255))
    # Viewer-Inhalt
    comp = comp_frame(t).convert("RGB").resize((VIEW[2] - VIEW[0], VIEW[3] - VIEW[1]), Image.LANCZOS)
    comp = comp.filter(ImageFilter.GaussianBlur(0.5))  # abgefilmter Bildschirm
    img.paste(comp, (VIEW[0], VIEW[1]))
    # Bildschirm-Spiegelung
    glare = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glare).polygon([(0, 410), (420, 410), (180, 1300), (0, 1300)], fill=(255, 255, 255, 8))
    img.alpha_composite(glare)
    caption(img)
    # Handkamera: leichtes Schweben + Zoom
    z = 1.035 + 0.01 * math.sin(t * 0.7)
    dx = math.sin(t * 1.3) * 5 + math.sin(t * 3.1) * 1.5
    dy = math.cos(t * 1.1) * 4
    big = img.resize((int(W * z), int(H * z)), Image.BILINEAR)
    ox = int((big.width - W) / 2 + dx)
    oy = int((big.height - H) / 2 + dy)
    out = big.crop((ox, oy, ox + W, oy + H)).convert("RGB")
    # Körnung
    arr = np.asarray(out).astype(np.int16)
    arr += np.random.default_rng(int(t * 1000)).integers(-5, 6, arr.shape[:2])[..., None]
    return np.clip(arr, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- Sound: ruhiger, cleaner Beat + UI-Sounds
SR = 44100


def make_audio(path):
    n = int(DUR * SR)
    out = np.zeros(n)
    rng = np.random.default_rng(5)

    def add(sig, at, vol=1.0):
        s = int(at * SR)
        e = min(n, s + len(sig))
        if 0 <= s < n:
            out[s:e] += sig[: e - s] * vol

    def tt(sec):
        return np.arange(int(sec * SR)) / SR

    # Pad-Akkorde (weich)
    chords = [(220.0, 277.18, 329.63), (196.0, 246.94, 293.66), (174.61, 220.0, 261.63), (196.0, 246.94, 329.63)]
    for k, ch in enumerate(chords):
        t = tt(3.0)
        env = np.minimum(t / 0.6, 1) * np.minimum((3.0 - t) / 0.6, 1)
        sig = sum(np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t) for f in ch) * env * 0.05
        add(sig, k * 3.0)
    # leiser Beat
    beat = 60 / 100
    kt = tt(0.25)
    kick = np.sin(2 * np.pi * (45 + 90 * np.exp(-kt * 30)) * kt) * np.exp(-kt * 12)
    ht = tt(0.04)
    hat = np.diff(rng.standard_normal(len(ht)), prepend=0) * np.exp(-ht * 90) * 0.08
    k = 0
    while k * beat < DUR - 0.6:
        add(kick, k * beat, 0.35)
        add(hat, k * beat + beat / 2)
        k += 1
    # UI-Klicks / Blips
    bt = tt(0.12)
    blip = np.sin(2 * np.pi * 1600 * bt) * np.exp(-bt * 45) * 0.18
    for at in (2.45, 3.2, 3.35, 4.35, 8.25, 8.45, 8.65, 9.95):
        add(blip, at)
    # Whoosh bei Szenenwechseln
    wt = tt(0.5)
    wn = rng.standard_normal(len(wt))
    whoosh = np.convolve(wn, np.ones(40) / 40, mode="same") * np.sin(np.pi * wt / wt[-1]) ** 2 * 0.5
    for at in (2.15, 5.65, 7.65, 9.35, 10.25):
        add(whoosh, at)
    # Partikel-Zerfall
    st = tt(0.9)
    shimmer = rng.standard_normal(len(st)) * np.exp(-st * 4) * 0.12
    add(shimmer - np.convolve(shimmer, np.ones(6) / 6, mode="same"), 6.6)
    fade = np.clip((DUR - np.arange(n) / SR) / 0.8, 0, 1)
    out *= fade
    out /= max(1e-6, np.max(np.abs(out))) * 1.15
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((out * 32767).astype(np.int16).tobytes())


def main():
    os.chdir(HERE)
    make_audio("audio_pov.wav")
    nf = int(DUR * FPS)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_pov.wav", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", "reel9_pov.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(nf):
        proc.stdin.write(frame(i / FPS).tobytes())
    proc.stdin.close()
    proc.wait()
    Image.fromarray(frame(4.9)).save("reel9_thumbnail.jpg", quality=92)
    print("fertig: reel9_pov.mp4")


if __name__ == "__main__":
    main()
