"""Helm-Konzept für den Frankfurter EC Eisteufel: Bauer Re-Akt 85, Design "Devil Line" (clean).

Idee: Ein einziger Akzent – zwei schmale Hörner-Linien laufen von der Stirn über die Seiten nach hinten
(von oben gesehen ergeben sie die Hörner des Vereinslogos). Hinten das Vereinslogo, an den Seiten die Nummer.
Farben aus dem Vereinslogo (brand/gameday/devil_cut.png): Rot #D64E4D, Weiß, Schwarz.
Zwei Varianten: BLACKOUT (schwarze Schale) und WHITE ICE (weiße Schale).
Stilisierte Helmansichten (Seite/hinten/oben) als Konzeptblatt – die Druckteile passt die Folierung an ihre
Re-Akt-85-Schablone an.
Aufruf: python3 helmet_eisteufel.py [NUMMER] -> helmet_eisteufel_konzept.png
"""
import math
import os
import sys

import cairocffi as cairo
import numpy as np
from PIL import Image

import reel15_puck as R15

HERE = os.path.dirname(os.path.abspath(__file__))
SS = 2                                   # Supersampling
W, H = 1600, 1880
RED = (214, 78, 77)
NUMBER = sys.argv[1] if len(sys.argv) > 1 else "00"

VARIANTS = [
    {"name": "BLACKOUT", "shell": (24, 25, 29), "shell_hi": (70, 72, 80), "edge": (8, 8, 10), "horn": RED,
     "pin": (245, 246, 248), "num": (245, 246, 248), "num_edge": RED, "text": (245, 246, 248), "vent": (6, 6, 8)},
    {"name": "WHITE ICE", "shell": (238, 240, 243), "shell_hi": (255, 255, 255), "edge": (150, 154, 162),
     "horn": (22, 23, 27), "pin": RED, "num": (22, 23, 27), "num_edge": RED, "text": (22, 23, 27),
     "vent": (40, 42, 48)},
]


def rgb(c, a=1.0):
    return c[0] / 255, c[1] / 255, c[2] / 255, a


def bez(p0, p1, p2, p3, n=40):
    t = np.linspace(0, 1, n)[:, None]
    return ((1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3)


def path_pts(segs):
    """segs: Startpunkt + Liste kubischer Segmente (c1, c2, p)."""
    pts = [np.array(segs[0], float)]
    cur = np.array(segs[0], float)
    for c1, c2, p in segs[1:]:
        b = bez(cur, np.array(c1, float), np.array(c2, float), np.array(p, float))
        pts.extend(b[1:])
        cur = np.array(p, float)
    return np.array(pts)


# ---------------- Helmformen (lokale Koordinaten)
SIDE = path_pts([(40, 300),
                 ((30, 250), (38, 170), (92, 112)),
                 ((170, 32), (380, 8), (482, 58)),
                 ((562, 96), (600, 190), (592, 268)),
                 ((586, 312), (562, 338), (522, 340)),
                 ((492, 341), (468, 324), (454, 302)),
                 ((442, 284), (420, 276), (398, 278)),
                 ((362, 282), (338, 300), (298, 304)),
                 ((220, 310), (120, 308), (40, 300))])
BACK = path_pts([(48, 318),
                 ((24, 250), (18, 150), (60, 82)),
                 ((110, 10), (290, 10), (340, 82)),
                 ((382, 150), (376, 250), (352, 318)),
                 ((300, 336), (250, 312), (200, 312)),
                 ((150, 312), (100, 336), (48, 318))])
TOP_RX, TOP_RY = 128, 170


def poly(ctx, pts, ox, oy, s):
    ctx.move_to(ox + pts[0][0] * s, oy + pts[0][1] * s)
    for p in pts[1:]:
        ctx.line_to(ox + p[0] * s, oy + p[1] * s)
    ctx.close_path()


def shade_shell(ctx, v, x0, y0, x1, y1):
    """Schale mit Glanz oben links und dunklerer Unterkante (matter Look)."""
    g = cairo.LinearGradient(0, y0, 0, y1)
    g.add_color_stop_rgba(0, *rgb(v["shell_hi"]))
    g.add_color_stop_rgba(0.35, *rgb(v["shell"]))
    g.add_color_stop_rgba(1, *rgb(tuple(int(c * 0.82) for c in v["shell"])))
    ctx.set_source(g)
    ctx.fill_preserve()
    rg = cairo.RadialGradient(x0 + (x1 - x0) * 0.35, y0 + (y1 - y0) * 0.22, 0,
                              x0 + (x1 - x0) * 0.35, y0 + (y1 - y0) * 0.22, (x1 - x0) * 0.6)
    rg.add_color_stop_rgba(0, 1, 1, 1, 0.16)
    rg.add_color_stop_rgba(1, 1, 1, 1, 0.0)
    ctx.set_source(rg)
    ctx.fill_preserve()


def horn_poly(center, w0, tip_curl=0.0):
    """Hornform: Mittellinie mit nach hinten abnehmender Breite."""
    c = center
    d = np.gradient(c, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    n = np.stack([-d[:, 1], d[:, 0]], 1)
    t = np.linspace(0, 1, len(c))[:, None]
    w = w0 * (1 - t) ** 0.85 + 0.6
    return np.concatenate([c + n * w / 2, (c - n * w / 2)[::-1]])


def draw_side(ctx, v, ox, oy, s):
    poly(ctx, SIDE, ox, oy, s)
    ctx.save()
    ctx.clip_preserve()
    shade_shell(ctx, v, ox + 30 * s, oy + 10 * s, ox + 600 * s, oy + 370 * s)
    ctx.new_path()
    # Hörner-Linie + feine Begleitlinie
    hc = bez(np.array([96.0, 150.0]), np.array([210.0, 84.0]), np.array([392.0, 86.0]), np.array([532.0, 168.0]), 80)
    poly(ctx, horn_poly(hc, 30), ox, oy, s)
    ctx.set_source_rgba(*rgb(v["horn"]))
    ctx.fill()
    pc = bez(np.array([118.0, 182.0]), np.array([226.0, 124.0]), np.array([380.0, 126.0]), np.array([500.0, 186.0]), 80)
    poly(ctx, horn_poly(pc, 7), ox, oy, s)
    ctx.set_source_rgba(*rgb(v["pin"]))
    ctx.fill()
    # Naht der zweiteiligen Schale, Lüftungsschlitze, Ohröffnung, Visierschraube
    ctx.set_source_rgba(*rgb(v["edge"], 0.55))
    ctx.set_line_width(2.2 * s)
    ctx.move_to(ox + 438 * s, oy + 44 * s)
    ctx.curve_to(ox + 452 * s, oy + 140 * s, ox + 462 * s, oy + 240 * s, ox + 446 * s, oy + 336 * s)
    ctx.stroke()
    for (x, y, ang, ln) in ((178, 52, -0.32, 52), (262, 33, -0.08, 56), (346, 36, 0.12, 52), (512, 104, 0.75, 40)):
        ctx.save()
        ctx.translate(ox + x * s, oy + y * s)
        ctx.rotate(ang)
        ctx.rectangle(-ln / 2 * s, -5 * s, ln * s, 10 * s)
        ctx.restore()
        ctx.set_source_rgba(*rgb(v["vent"], 0.92))
        ctx.fill()
    ctx.arc(ox + 92 * s, oy + 226 * s, 9 * s, 0, 2 * math.pi)
    ctx.set_source_rgba(0.55, 0.57, 0.6, 1)
    ctx.fill()
    ctx.restore()
    poly(ctx, SIDE, ox, oy, s)
    ctx.set_source_rgba(*rgb(v["edge"]))
    ctx.set_line_width(3 * s)
    ctx.stroke()
    ear = path_pts([(318, 262), ((318, 236), (436, 232), (440, 262)), ((446, 300), (428, 344), (382, 350)),
                    ((340, 354), (316, 318), (318, 262))])
    poly(ctx, ear, ox, oy, s)                                 # Ohrschutz (schwarzes Kunststoffteil)
    ctx.set_source_rgba(*rgb((34, 36, 41)))
    ctx.fill_preserve()
    ctx.set_source_rgba(0, 0, 0, 0.6)
    ctx.set_line_width(2 * s)
    ctx.stroke()
    for k in range(3):
        ctx.arc(ox + (360 + k * 20) * s, oy + 300 * s, 5 * s, 0, 2 * math.pi)
        ctx.set_source_rgba(0.06, 0.06, 0.07, 1)
        ctx.fill()


def draw_back(ctx, v, ox, oy, s):
    poly(ctx, BACK, ox, oy, s)
    ctx.save()
    ctx.clip_preserve()
    shade_shell(ctx, v, ox + 18 * s, oy + 10 * s, ox + 382 * s, oy + 330 * s)
    ctx.new_path()
    for x in (150, 250):
        ctx.rectangle(ox + (x - 26) * s, oy + 46 * s, 52 * s, 10 * s)
        ctx.set_source_rgba(*rgb(v["vent"], 0.92))
        ctx.fill()
    ctx.restore()
    poly(ctx, BACK, ox, oy, s)
    ctx.set_source_rgba(*rgb(v["edge"]))
    ctx.set_line_width(3 * s)
    ctx.stroke()


def draw_top(ctx, v, ox, oy, s):
    cx, cy = ox + TOP_RX * s, oy + TOP_RY * s
    ctx.save()
    ctx.translate(cx, cy)
    ctx.scale(TOP_RX * s, TOP_RY * s)
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.restore()
    ctx.save()
    ctx.clip_preserve()
    shade_shell(ctx, v, cx - TOP_RX * s, cy - TOP_RY * s, cx + TOP_RX * s, cy + TOP_RY * s)
    ctx.new_path()
    for sgn in (-1, 1):                                       # von oben: die Hörner des Logos
        c = bez(np.array([sgn * 16.0, -150.0]), np.array([sgn * 52.0, -118.0]),
                np.array([sgn * 112.0, -40.0]), np.array([sgn * 118.0, 70.0]), 60)
        pts = horn_poly(c, 28) + np.array([TOP_RX, TOP_RY])
        poly(ctx, pts, ox, oy, s)
        ctx.set_source_rgba(*rgb(v["horn"]))
        ctx.fill()
        c2 = bez(np.array([sgn * 34.0, -128.0]), np.array([sgn * 64.0, -96.0]),
                 np.array([sgn * 96.0, -36.0]), np.array([sgn * 98.0, 50.0]), 60)
        poly(ctx, horn_poly(c2, 6) + np.array([TOP_RX, TOP_RY]), ox, oy, s)
        ctx.set_source_rgba(*rgb(v["pin"]))
        ctx.fill()
    for (x, y) in ((-34, -60), (34, -60), (-46, 10), (46, 10), (0, 96)):
        ctx.rectangle(cx + (x - 8) * s, cy + (y - 26) * s, 16 * s, 52 * s)
        ctx.set_source_rgba(*rgb(v["vent"], 0.92))
        ctx.fill()
    ctx.restore()
    ctx.save()
    ctx.translate(cx, cy)
    ctx.scale(TOP_RX * s, TOP_RY * s)
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.restore()
    ctx.set_source_rgba(*rgb(v["edge"]))
    ctx.set_line_width(3 * s)
    ctx.stroke()


def text(img, txt, size, wght, col, cx, cy, track=0.0, anchor="c"):
    im = R15.line_img(txt, int(size * SS), wght, col, track=track * SS, cache=False)
    x = cx * SS - (im.width / 2 if anchor == "c" else 20)
    img.alpha_composite(im, (int(x), int(cy * SS - im.height / 2)))


def outlined_number(img, num, size, col, edge, cx, cy):
    base = R15.line_img(num, int(size * SS), 900, col, cache=False)
    ring = R15.line_img(num, int(size * SS), 900, edge, cache=False)
    x, y = int(cx * SS - base.width / 2), int(cy * SS - base.height / 2)
    r = int(3 * SS)
    for dx, dy in ((r, 0), (-r, 0), (0, r), (0, -r), (r, r), (-r, -r), (r, -r), (-r, r)):
        img.alpha_composite(ring, (x + dx, y + dy))
    img.alpha_composite(base, (x, y))


def main():
    logo = Image.open(os.path.join(HERE, "brand", "gameday", "devil_cut.png")).convert("RGBA")
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W * SS, H * SS)
    ctx = cairo.Context(surf)
    g = cairo.LinearGradient(0, 0, 0, H * SS)
    g.add_color_stop_rgba(0, *rgb((242, 243, 246)))
    g.add_color_stop_rgba(1, *rgb((226, 229, 234)))
    ctx.set_source(g)
    ctx.paint()
    rows = [300, 1020]
    layout = []
    for v, y0 in zip(VARIANTS, rows):
        sx, sy, ss_ = 60, y0 + 60, 1.25                      # Seitenansicht
        bx, by, bs = 860, y0 + 120, 0.92                     # Rückansicht
        tx, ty, ts = 1270, y0 + 60, 1.0                      # Draufsicht
        draw_side(ctx, v, sx * SS, sy * SS, ss_ * SS)
        draw_back(ctx, v, bx * SS, by * SS, bs * SS)
        draw_top(ctx, v, tx * SS, ty * SS, ts * SS)
        layout.append((v, y0, (sx, sy, ss_), (bx, by, bs), (tx, ty, ts)))
        ctx.set_source_rgba(0, 0, 0, 0.08)
        ctx.set_line_width(2 * SS)
        ctx.move_to(60 * SS, (y0 + 600) * SS)
        ctx.line_to((W - 60) * SS, (y0 + 600) * SS)
        ctx.stroke()
    surf.flush()
    a = np.frombuffer(surf.get_data(), np.uint8).reshape(H * SS, W * SS, 4)
    img = Image.fromarray(a[..., [2, 1, 0, 3]].copy(), "RGBA")
    ink, grey = (20, 21, 26), (110, 114, 124)
    text(img, "EISTEUFEL FRANKFURT", 64, 900, ink, 60, 110, track=4, anchor="l")
    text(img, "HELMDESIGN  ·  BAUER RE-AKT 85  ·  KONZEPT „DEVIL LINE“", 26, 700, RED, 60, 175, track=5, anchor="l")
    text(img, "Ein Akzent: zwei Hörner-Linien von der Stirn nach hinten – von oben die Hörner aus dem Logo.",
         24, 500, grey, 60, 222, anchor="l")
    for v, y0, (sx, sy, ss_), (bx, by, bs), (tx, ty, ts) in layout:
        text(img, f"VARIANTE {'A' if v is VARIANTS[0] else 'B'}  ·  {v['name']}", 30, 850, ink, 60, y0 + 20, track=5,
             anchor="l")
        # Nummer an der Seite
        outlined_number(img, NUMBER, 92 * ss_ / 1.25, v["num"], v["num_edge"], sx + 522 * ss_, sy + 252 * ss_)
        # Logo + Schrift hinten
        lh = int(150 * bs * SS)
        lg = logo.resize((int(logo.width * lh / logo.height), lh), Image.LANCZOS)
        img.alpha_composite(lg, (int((bx + 200 * bs) * SS - lg.width / 2), int((by + 92 * bs) * SS)))
        text(img, "EISTEUFEL", 30 * bs, 900, v["text"], bx + 200 * bs, by + 262 * bs, track=6)
        text(img, "FRANKFURT  ·  EST. 1984", 15 * bs, 800, RED, bx + 200 * bs, by + 290 * bs, track=4)
        for lbl, x, y in (("SEITE", sx + 320 * ss_, sy + 400 * ss_), ("HINTEN", bx + 200 * bs, by + 380 * bs),
                          ("OBEN", tx + TOP_RX * ts, ty + 2 * TOP_RY * ts + 40)):
            text(img, lbl, 20, 800, grey, x, y, track=6)
    sw_y = H - 120
    for i, (col, name) in enumerate((((214, 78, 77), "ROT  #D64E4D"), ((24, 25, 29), "SCHWARZ MATT"),
                                     ((240, 241, 244), "WEISS"))):
        x = 60 + i * 330
        sw = Image.new("RGBA", (56 * SS, 56 * SS), col + (255,))
        img.alpha_composite(sw, (x * SS, (sw_y - 28) * SS))
        text(img, name, 22, 800, ink, x + 76, sw_y, track=3, anchor="l")
    text(img, f"Nummer {NUMBER} = Platzhalter  ·  Folie matt, Linien + Logo glänzend  ·  Druckteile passt die Folierung "
         "an ihre Re-Akt-85-Schablone an", 19, 600, grey, W / 2, H - 42, track=1)
    out = img.resize((W, H), Image.LANCZOS).convert("RGB")
    path = os.path.join(HERE, "helmet_eisteufel_konzept.png")
    out.save(path, optimize=True)
    print("gespeichert:", path)


if __name__ == "__main__":
    main()
