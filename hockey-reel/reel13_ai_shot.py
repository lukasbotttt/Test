"""Reel 13: "I asked AI to animate hockey pt 2" – der härteste Schuss der NHL-Geschichte als Ratespiel.

Gleiches Format wie Reel 12 (gefilmter Laptop im Neon-Zimmer, Loop: letztes Bild = erstes Bild).
Ablauf (13.4 s):
  0.00 Prompt-Leiste, Play -> 0.60 Angriffszone von oben (maßstabsgetreu, 19.5 px pro Fuß): ein Puck fliegt mit
       echter Rekordgeschwindigkeit von der blauen Linie ins Tor (64 ft in 0.40 s)
  1.20 Leiste formt sich neu, Prompt "Show me the hardest shot in NHL history" (Kamera folgt dem Cursor)
  2.72 Senden -> die Leiste wird zur Timer-Spur, Ziffern drehen sich ("GUESS THE SPEED"), rasten ein,
       stoppen bei 108.5 (Shea Weber 2015), ticken weiter auf 108.8 -> Schloss zu, Torlicht (6.10)
  6.95 Zdeno Chara · 2012 -> 8.30 Schalter NHL | AHL: 109.2 Martin Frk · 2020
  9.80 WHO BREAKS 108.8? COMMENT A NAME -> 11.30 Wortmarke -> 12.60 zurück in die Prompt-Leiste
Fakten (geprüft, Quellen u. a. NHL.com): Chara 108.8 mph (175.1 km/h), 28.1.2012, NHL All-Star Skills,
Ottawa – weiterhin NHL-Rekord (Stand 10/2026). Weber 108.5 mph 2015 (am nächsten dran). AHL: Martin Frk
109.2 mph, 26.1.2020, AHL All-Star Skills. 108.8 mph = 159.6 ft/s -> blaue Linie bis Torlinie (64 ft) 0.40 s.
Aufruf: python3 reel13_ai_shot.py  ->  reel13_ai_shot.mp4
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
import reel10_studio as studio
import reel12_ai_motion as p1
import screen_fx as fx
from pov_room import ifont, draw_cursor
from screen_fx import (SW, SH, ICE, ORANGE, WHITE, c01, lerp, e_out, e_in, e_io, e_expo, e_back,
                       layer, put, fade, mblur, glow, edge_vignette, text_layer, text_width)
from reel12_ai_motion import (BG, FROST, ICEFIELD, BAR, WARMWHITE, KNOB_TOP, KNOB_BOT, KNOB_RIM, T_PLAY,
                              bg, cam_apply, bar_layer, rest_state, squeeze, band_mask, beams, black_puck, PUCK_ANGLES)

FPS = 30
DUR = 13.4
room.LOOP = DUR
HERE = os.path.dirname(os.path.abspath(__file__))
OVERLAY = ["I asked AI to animate hockey pt 2", "GUESS BEFORE IT LOCKS"]
PROMPT = "Show me the hardest shot in NHL history"
PLACEHOLDER = p1.PLACEHOLDER
GREYTXT = (186, 196, 210)

# ================================================================= Angriffszone von oben (19.5 px pro Fuß)
PX_FT = 19.5
BLUE_X = 0.10 * SW
GOAL_X = BLUE_X + 64 * PX_FT                 # Torlinie 64 ft hinter der blauen Linie
NET_Y = 0.505 * SH
PUCK_A, PUCK_B = (BLUE_X, 0.56 * SH), (GOAL_X - 8, NET_Y)
T_SHOT0, T_SHOT1 = 0.66, 1.06                 # 64 ft bei 108.8 mph = 0.40 s
_ZONE = None


def zone_sheet():
    global _ZONE
    if _ZONE is None:
        img = Image.new("RGBA", (SW, SH), ICEFIELD + (255,))
        lay = layer()
        d = ImageDraw.Draw(lay)
        rng = random.Random(23)
        for _ in range(34):
            cx, cy = rng.uniform(-300, SW + 300), rng.uniform(-300, SH + 300)
            r = rng.uniform(300, 1100)
            a0 = rng.uniform(0, 360)
            d.arc((cx - r, cy - r, cx + r, cy + r), a0, a0 + rng.uniform(15, 50), fill=(150, 165, 180, rng.randint(20, 32)),
                  width=rng.choice((1, 2, 2, 3)))
        red = (215, 40, 55)
        # Bullykreise (15 ft Radius) 20 ft vor der Torlinie, 22 ft neben der Mitte; Punkte 2 ft
        for sy in (-1, 1):
            cx, cy = GOAL_X - 20 * PX_FT, NET_Y + sy * 22 * PX_FT
            R = 15 * PX_FT
            d.ellipse((cx - R, cy - R, cx + R, cy + R), outline=red + (130,), width=3)
            d.ellipse((cx - PX_FT, cy - PX_FT, cx + PX_FT, cy + PX_FT), fill=red + (150,))
        # blaue Linie (12 Zoll), Torlinie (2 Zoll)
        d.rectangle((BLUE_X - PX_FT / 2, 0, BLUE_X + PX_FT / 2, SH), fill=(35, 110, 235, 160))
        d.rectangle((GOAL_X - 2, 0, GOAL_X + 2, SH), fill=red + (200,))
        # Torraum (6 ft Radius)
        cr = 6 * PX_FT
        d.pieslice((GOAL_X - cr, NET_Y - cr, GOAL_X + cr, NET_Y + cr), 90, 270, fill=(150, 200, 245, 120), outline=red + (200,), width=3)
        img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(0.6)))
        arr = np.asarray(img).astype(np.float32)
        arr[..., :3] *= (1 - 0.04 * fx._YY[..., None] / SH)
        _ZONE = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    return _ZONE


def net_layer(bulge=0.0):
    """Tor von oben: 6 ft breit, 40 Zoll tief, Netz beult beim Einschlag nach hinten aus."""
    lay = layer()
    d = ImageDraw.Draw(lay)
    half, depth = 3 * PX_FT, 40 / 12 * PX_FT
    x0 = GOAL_X
    back = x0 + depth + 26 * bulge
    pts = [(x0, NET_Y - half), (x0 + depth * 0.8, NET_Y - half * 0.9), (back, NET_Y), (x0 + depth * 0.8, NET_Y + half * 0.9), (x0, NET_Y + half)]
    d.polygon(pts, fill=(255, 255, 255, 90))
    for k in range(1, 7):
        u = k / 7
        d.line((x0, NET_Y - half + 2 * half * u, lerp(x0 + depth * 0.8, back, 1 - abs(u - 0.5) * 2), NET_Y - half * 0.9 + 1.8 * half * 0.9 * u),
               fill=(150, 160, 175, 150), width=1)
    d.line(pts, fill=(215, 40, 55, 255), width=6)
    return lay


def hook_frame(t):
    """0.60–1.20: Zone, Ausholen, Puck fliegt mit Rekordtempo ins Tor."""
    img = zone_sheet().copy()
    hit = t >= T_SHOT1
    bulge = math.exp(-(t - T_SHOT1) * 9) * math.sin((t - T_SHOT1) * 30) if hit else 0.0
    img.alpha_composite(net_layer(max(0.0, bulge)))
    d = ImageDraw.Draw(img)
    if t < T_SHOT0:
        k = c01((t - 0.62) / 0.04)
        if k > 0:
            fx.blob(img, PUCK_A[0], PUCK_A[1], 50, 50, (255, 255, 255), 0.9 * k)
        x, y = PUCK_A
    elif not hit:
        u = (t - T_SHOT0) / (T_SHOT1 - T_SHOT0)
        x, y = lerp(PUCK_A[0], PUCK_B[0], u), lerp(PUCK_A[1], PUCK_B[1], u)
        tr = layer()
        td = ImageDraw.Draw(tr)
        L = min(280, (x - PUCK_A[0]))
        dx, dy = PUCK_B[0] - PUCK_A[0], PUCK_B[1] - PUCK_A[1]
        n = math.hypot(dx, dy)
        ux, uy = dx / n, dy / n
        for k in range(24):
            a, b = k / 24, (k + 1) / 24
            td.line((x - ux * L * (1 - a), y - uy * L * (1 - a), x - ux * L * (1 - b), y - uy * L * (1 - b)),
                    fill=(110, 190, 255, int(220 * a)), width=max(2, int(14 * a)))
        glow(img, tr, 16, 0.8)
    else:
        x, y = PUCK_B[0] + 14, PUCK_B[1]
    if not hit or t < T_SHOT1 + 0.05:
        r = 14
        d.ellipse((x - r, y - r, x + r, y + r), fill=(22, 22, 26, 255), outline=(205, 214, 228, 255), width=3)
    tau = t - T_SHOT1
    if hit and tau < 0.25:
        fx.blob(img, GOAL_X + 20, NET_Y, 90, 90, (255, 255, 255), 0.8 * (1 - tau / 0.25))
        rng = random.Random(4)
        for _ in range(18):
            ang = rng.uniform(-math.pi * 0.85, math.pi * 0.85) + math.pi
            sp = rng.uniform(250, 600)
            px, py = GOAL_X + math.cos(ang) * sp * tau, NET_Y + math.sin(ang) * sp * tau
            rr = rng.uniform(2, 5)
            d.ellipse((px - rr, py - rr, px + rr, py + rr), fill=(240, 248, 255, int(255 * (1 - tau / 0.25))))
    if t < T_SHOT0 + 0.1:
        tau0 = t - 0.62
        if 0 <= tau0 < 0.2:
            rng = random.Random(9)
            for _ in range(14):
                ang = rng.uniform(0, 2 * math.pi)
                sp = rng.uniform(120, 300)
                px, py = PUCK_A[0] + math.cos(ang) * sp * tau0, PUCK_A[1] + math.sin(ang) * sp * tau0
                d.ellipse((px - 3, py - 3, px + 3, py + 3), fill=(240, 248, 255, int(255 * (1 - tau0 / 0.2))))
    z = 1.0 + 0.04 * c01((t - 0.60) / 0.60)
    return cam_apply(img, *p1.pivot_cam(z, (SW / 2, SH / 2), (SW / 2, SH / 2)))


# ================================================================= Prompt: Tippen mit Kamera, Senden
_rk = random.Random(7)
_iv = [1 + _rk.uniform(-0.3, 0.3) for _ in PROMPT]
KEY_T = list(np.cumsum(_iv) / sum(_iv) * 1.0 + 1.52 - 1.0 / len(PROMPT))
TXT_X0 = BAR["cx"] - BAR["w"] / 2 + 56
SEND = (BAR["cx"] + BAR["w"] / 2 - 64, BAR["cy"] + BAR["h"] / 2 - 58)


def typed(t):
    if t < KEY_T[0]:
        return PLACEHOLDER, (128, 134, 144)
    return PROMPT[:sum(1 for k in KEY_T if k <= t)], (30, 32, 38)


def prompt_cam(t):
    """Nah ran an den Text (1.6x), Kamera folgt dem Cursor, dann zurück."""
    txt, _ = typed(t)
    caret_x = TXT_X0 + 4 + ifont(450, 46).getlength(txt if t >= KEY_T[0] else "")
    z = 1.0 + 0.6 * e_io((t - 1.50) / 0.22) - 0.6 * e_io((t - 2.56) / 0.12)
    ox_l = 0.07 * SW - TXT_X0 * z                                  # Textanfang links im Bild
    ox_c = 0.66 * SW - caret_x * z                                 # Cursor höchstens bei 66 %
    ox = min(ox_l, ox_c)
    oy = 0.46 * SH - BAR["cy"] * z
    if z <= 1.001:
        return 1.0, 0.0, 0.0
    k = c01((z - 1.0) / 0.6)
    return z, ox * k, oy * k


def send_button(lay, t):
    """Senden-Knopf wird beim Klick eisblau und springt kurz auf."""
    if t < 2.72:
        return
    p = e_back(c01((t - 2.72) / 0.18), 2.0)
    s = lerp(1.0, 1.12, p) if t < 2.86 else lerp(1.12, 1.0, e_out((t - 2.86) / 0.1))
    d = ImageDraw.Draw(lay)
    bx, iy = SEND
    r = 30 * s
    d.ellipse((bx - r, iy - r, bx + r, iy + r), fill=ICE + (255,))
    d.line((bx, iy + 14 * s, bx, iy - 13 * s), fill=(255, 255, 255, 255), width=5)
    d.line((bx - 12 * s, iy - 1 * s, bx, iy - 14 * s), fill=(255, 255, 255, 255), width=5)
    d.line((bx + 12 * s, iy - 1 * s, bx, iy - 14 * s), fill=(255, 255, 255, 255), width=5)


def prompt_scene(t):
    txt, ink = typed(t)
    sh = c01((t - 2.72) / 0.14) if 2.72 <= t < 2.86 else None
    lay = bar_layer(txt, ink, t, caret=t >= KEY_T[0] and t < 2.72, shimmer=sh)
    send_button(lay, t)
    if 2.56 <= t < 2.95:
        p = e_io((t - 2.58) / 0.12)
        x, y = lerp(0.70 * SW, SEND[0] - 6, p), lerp(0.50 * SH, SEND[1] + 4, p)
        cl = layer()
        draw_cursor(cl, x, y, 1.6 * (0.92 if 0 <= t - 2.72 < 0.07 else 1.0))
        lay.alpha_composite(fade(cl, c01((t - 2.56) / 0.05) * (1 - c01((t - 2.85) / 0.08))))
    return lay


# ================================================================= Zahlen-Walze, Timer-Spur, Schloss
NUM_F = ifont(700, 300)
CELL_W = max(NUM_F.getlength(str(k)) for k in range(10)) + 6
DOT_W = NUM_F.getlength(".") + 10
UNIT = "mph"
UNIT_F = ifont(500, 120)
GROUP_W = 4 * CELL_W + DOT_W + 34 + UNIT_F.getlength(UNIT)
NUM_CY = 0.46 * SH
CELL_H = 330
TRACK_Y, TRACK_X0, TRACK_X1 = 0.80 * SH, BAR["cx"] - 448, BAR["cx"] + 448
LOCK_POS = (TRACK_X1 + 64, TRACK_Y)
RATE = 115.0                                  # Ziffern pro Sekunde beim Drehen


def spin_pos(t, t0, lock_t, final, ticks=()):
    """Walzenposition einer Ziffer: dreht ab t0, rastet bei lock_t weich auf 'final' ein, danach Einzelschritte."""
    if t < t0:
        return 0.0, 0.0
    a = RATE * (lock_t - t0)
    if t < lock_t:
        return RATE * (t - t0), RATE
    target = a + ((final - a) % 10) + 10
    u = c01((t - lock_t) / 0.32)
    pos = a + (target - a) * e_out(u, 3)
    speed = (target - a) * 3 * (1 - u) ** 2 / 0.32
    for tk, steps in ticks:
        if t >= tk:
            q = e_out(c01((t - tk) / 0.09), 3)
            pos += steps * q
            speed += steps * 3 * (1 - c01((t - tk) / 0.09)) ** 2 / 0.09 if t < tk + 0.09 else 0
    return pos, speed


def number_layer(cells, color=WHITE, unit_a=1.0, alpha=1.0):
    """cells: Liste aus (pos, speed) für 4 Ziffern; Komma-Punkt zwischen 3. und 4."""
    lay = layer()
    x = SW / 2 - GROUP_W / 2
    for i, (pos, speed) in enumerate(cells):
        if i == 3:
            ImageDraw.Draw(lay).text((x + DOT_W / 2, NUM_CY), ".", font=NUM_F, fill=color + (255,), anchor="mm")
            x += DOT_W
        cell = Image.new("RGBA", (int(CELL_W) + 4, CELL_H * 3), (0, 0, 0, 0))
        cd = ImageDraw.Draw(cell)
        base = math.floor(pos)
        frac = pos - base
        for j in range(-1, 2):
            dgt = int((base + j) % 10)
            cy = CELL_H * 1.5 + (j - frac) * -CELL_H
            cd.text((cell.width / 2, cy), str(dgt), font=NUM_F, fill=color + (255,), anchor="mm")
        if speed > 3:
            cell = studio.vblur(cell, min(70, speed * 0.9))
        win = cell.crop((0, int(CELL_H * 1.5 - CELL_H / 2), cell.width, int(CELL_H * 1.5 + CELL_H / 2)))
        mk = Image.new("L", win.size, 0)
        md = ImageDraw.Draw(mk)
        for yy in range(win.height):
            e = min(yy, win.height - 1 - yy) / 40
            md.line((0, yy, win.width, yy), fill=int(255 * c01(e)))
        win.putalpha(ImageChops.multiply(win.getchannel("A"), mk))
        put(lay, win, x, NUM_CY - CELL_H / 2)
        x += CELL_W
    if unit_a > 0.01:
        ImageDraw.Draw(lay).text((x + 34, NUM_CY + 60), UNIT, font=UNIT_F, fill=GREYTXT + (int(255 * unit_a),), anchor="ls")
    return fade(lay, alpha)


# Einraste-Plan: 1 (3.80), 0 (4.30), 8 (4.80), Zehntel stoppt bei 5 (5.05, steht ~0.4 s), dann 6/7/8 (5.78/5.88/6.00)
LOCKS = [(3.10, 3.80, 1, ()), (3.13, 4.30, 0, ()), (3.16, 4.80, 8, ()), (3.19, 5.05, 5, ((5.78, 1), (5.88, 1), (6.00, 1)))]
T_LOCK = 6.10


def guess_cells(t):
    return [spin_pos(t, a, b, f, tk) for a, b, f, tk in LOCKS]


def static_cells(digits):
    return [(float(dg), 0.0) for dg in digits]


def reroll_cells(t, t0):
    """108.8 -> 109.2 (Einer 8->9, Zehntel 8->12)."""
    out = []
    for i, (a, b) in enumerate(((1, 1), (0, 0), (8, 9), (8, 12))):
        u = e_out(c01((t - t0 - 0.05 * i) / 0.35), 3)
        out.append((a + (b - a) * u, (b - a) * 3 * (1 - c01((t - t0 - 0.05 * i) / 0.35)) ** 2 / 0.35 if a != b else 0.0))
    return out


def padlock(d, cx, cy, s, closed, col=WHITE, jitter=0.0):
    """Vorhängeschloss: Bügel offen (seitlich angehoben) oder geschlossen."""
    c = col + (255,)
    cx += jitter
    bw, bh = 64 * s, 52 * s
    d.rounded_rectangle((cx - bw / 2, cy - bh / 2 + 10 * s, cx + bw / 2, cy + bh / 2 + 10 * s), radius=9 * s, fill=c)
    d.ellipse((cx - 6 * s, cy + 4 * s, cx + 6 * s, cy + 16 * s), fill=BG + (255,))
    lift = (1 - closed) * 20 * s
    r = 22 * s
    top = cy - bh / 2 + 10 * s
    d.arc((cx - r, top - r * 2 - lift + 4 * s, cx + r, top + 4 * s - lift), 180, 360, fill=c, width=max(2, int(8 * s)))
    d.line((cx + r - 4 * s, top - r - lift + 4 * s, cx + r - 4 * s, top + 2 * s - (lift if closed < 1 else 0)), fill=c, width=max(2, int(8 * s)))
    d.line((cx - r + 4 * s, top - r - lift + 4 * s, cx - r + 4 * s, top - lift + 2 * s), fill=c, width=max(2, int(8 * s)))


def timer_track(base, t, a=1.0):
    if a <= 0.01:
        return
    lay = layer()
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle((TRACK_X0, TRACK_Y - 7, TRACK_X1, TRACK_Y + 7), radius=7, fill=(62, 64, 74, 255))
    u = c01((t - 3.30) / 2.78)
    p = 0.85 * u + 0.15 * u ** 3
    hx = lerp(TRACK_X0, TRACK_X1, p)
    if p > 0:
        rib = layer()
        rd = ImageDraw.Draw(rib)
        rd.rounded_rectangle((TRACK_X0, TRACK_Y - 7, hx, TRACK_Y + 7), radius=7, fill=ORANGE + (255,))
        rd.rounded_rectangle((max(TRACK_X0, hx - 60), TRACK_Y - 4, hx, TRACK_Y + 4), radius=4, fill=(255, 224, 190, 255))
        glow(lay, rib, 18, 0.9)
        if p < 1:
            fx.blob(lay, hx, TRACK_Y, 22, 22, (255, 255, 255), 0.9)
    closed = e_out(c01((t - T_LOCK) / 0.06), 2)
    jit = 2 * math.sin(t * 90) if 5.30 <= t < 5.70 else 0.0
    padlock(ImageDraw.Draw(lay), LOCK_POS[0], LOCK_POS[1] - 6, 0.85, closed, jitter=jit)
    base.alpha_composite(fade(lay, a))


# ================================================================= Name-Zeilen, Schalter NHL | AHL
NAME_Y = 0.70 * SH
NAME_F = ifont(650, 104)
PILL_F = ifont(650, 90)


def name_line(name, year, t0, alpha=1.0, y=NAME_Y, t=0.0):
    """Name (Buchstaben fallen ein) + oranger Jahres-Pill rechts daneben."""
    lay = layer()
    nw = sum(NAME_F.getlength(ch) for ch in name)
    pw = PILL_F.getlength(year) + 80
    total = nw + 40 + pw
    x = SW / 2 - total / 2
    d = ImageDraw.Draw(lay)
    for i, ch in enumerate(name):
        w = NAME_F.getlength(ch)
        tau = t - t0 - 0.03 * i
        if tau >= 0:
            u = c01(tau / 0.24)
            yy = y - 46 * (1 - e_back(u, 1.7))
            cool = c01((tau - 0.1) / 0.25)
            col = tuple(int(lerp(a, b, cool)) for a, b in zip(ORANGE, WHITE))
            d.text((x + w / 2, yy), ch, font=NAME_F, fill=col + (int(255 * c01(tau / 0.06)),), anchor="mm")
        x += w
    p = e_back(c01((t - t0 - 0.30) / 0.2), 1.6)
    if p > 0:
        px0 = x + 40
        cx = px0 + pw / 2
        hw, hh = pw / 2 * p, 65 * p
        d.rounded_rectangle((cx - hw, y - hh, cx + hw, y + hh), radius=hh, fill=ORANGE + (255,))
        if p > 0.5:
            d.text((cx, y + 2), year, font=ifont(650, max(8, int(90 * min(1, p)))), fill=(40, 22, 8, 255), anchor="mm")
    return fade(lay, alpha)


TOG = dict(cx=SW / 2, cy=0.15 * SH, w=736, h=150)


def league_toggle(t, oy=0.0):
    """Schalter NHL | AHL; Knopf gleitet bei 8.65 nach AHL."""
    cx, cy, w, h = TOG["cx"], TOG["cy"] + oy, TOG["w"], TOG["h"]
    lay = layer()
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), radius=h / 2, fill=(62, 64, 74, 235))
    seg = w / 2
    slide = e_io(c01((t - 8.65) / 0.30))
    kx = cx - w / 2 + seg * (0.5 + slide)
    kw, kh = seg - 16, h - 16
    k = layer()
    kd = ImageDraw.Draw(k)
    for i in range(24):
        u = i / 24
        col = tuple(int(lerp(a, b, u)) for a, b in zip(KNOB_TOP, KNOB_BOT))
        kd.rectangle((kx - kw / 2, cy - kh / 2 + kh * u, kx + kw / 2, cy - kh / 2 + kh * (u + 1 / 24) + 1), fill=col + (255,))
    mk = Image.new("L", (SW, SH), 0)
    ImageDraw.Draw(mk).rounded_rectangle((kx - kw / 2, cy - kh / 2, kx + kw / 2, cy + kh / 2), radius=kh / 2, fill=255)
    k.putalpha(ImageChops.multiply(k.getchannel("A"), mk))
    ImageDraw.Draw(k).rounded_rectangle((kx - kw / 2, cy - kh / 2, kx + kw / 2, cy + kh / 2), radius=kh / 2, outline=KNOB_RIM + (255,), width=2)
    halo = layer()
    ImageDraw.Draw(halo).rounded_rectangle((kx - kw / 2, cy - kh / 2, kx + kw / 2, cy + kh / 2), radius=kh / 2, fill=ICE + (255,))
    glow(lay, halo, 24, 0.45, keep=False)
    lay.alpha_composite(k)
    f = ifont(650, 90)
    for i, lb in enumerate(("NHL", "AHL")):
        on = (1 - slide) if i == 0 else slide
        col = tuple(int(lerp(a, b, on)) for a, b in zip((200, 204, 212), (255, 255, 255)))
        ImageDraw.Draw(lay).text((cx - w / 2 + seg * (i + 0.5), cy + 3), lb, font=f, fill=col + (255,), anchor="mm")
    return lay


# ================================================================= Torlicht (Part-1-Signatur), CTA, Wortmarke
def burst_bg(t, t0):
    q = c01((t - t0) / 0.10)
    out = 1 - c01((t - (t0 + 0.70)) / 0.25)
    diag = (fx._XX / SW + fx._YY / SH) / 2
    edge = np.clip((q * 1.6 - diag) / 0.3, 0, 1) * out
    tl, mid, br = np.array([240, 40, 34], np.float32), np.array([150, 28, 36], np.float32), np.array([70, 18, 26], np.float32)
    g = np.clip(diag[..., None] * 2, 0, 2)
    col = np.where(diag[..., None] < 0.5, tl + (mid - tl) * g, mid + (br - mid) * np.clip(g - 1, 0, 1))
    strobe = 1 + 0.35 * math.exp(-max(0.0, t - t0) * 18) + (0.3 * math.exp(-(t - t0 - 0.35) * 18) if t >= t0 + 0.35 else 0)
    return Image.fromarray(np.dstack([np.clip(col * strobe, 0, 255), edge * 255]).astype(np.uint8), "RGBA")


CTA1, CTA2 = "WHO BREAKS 108.8?", "COMMENT A NAME"
MARK = "@bladesandpucks"
MARK_SIZE = 96
T_MARK = 11.30


def wordmark(t, scale_extra=1.0, alpha=1.0):
    lay = layer()
    tt_ = t - T_MARK
    if tt_ < 0:
        return lay
    f = ifont(650, MARK_SIZE)
    widths = [f.getlength(ch) for ch in MARK]
    sc = lerp(1.3, 1.0, e_out(c01(tt_ / 0.8), 3)) * (1 + 0.03 * c01((tt_ - 0.8) / 0.5)) * scale_extra
    inner = layer()
    x = SW / 2 - sum(widths) / 2
    for i, ch in enumerate(MARK):
        cx = x + widths[i] / 2
        x += widths[i]
        tau = tt_ - 0.04 * i
        if tau < 0:
            continue
        for ghost, ga in ((0.066, 0.12), (0.033, 0.22), (0.0, 1.0)):
            u = c01((tau - ghost) / 0.22)
            if u <= 0 or (ghost > 0 and u >= 1):
                continue
            yy = SH / 2 - 0.10 * SH * (1 - e_back(u, 0.5))
            rot = -25 * (1 - e_out(u, 3))
            cool = c01((tau - ghost - 0.22) / 0.25)
            col = tuple(int(lerp(a, b, cool)) for a, b in zip(ORANGE, WARMWHITE))
            gl = Image.new("RGBA", (int(widths[i]) + 70, MARK_SIZE + 70), (0, 0, 0, 0))
            ImageDraw.Draw(gl).text((gl.width / 2, gl.height / 2), ch, font=f, fill=col + (int(255 * ga),), anchor="mm")
            if abs(rot) > 0.5:
                gl = gl.rotate(rot, resample=Image.BICUBIC)
            put(inner, gl, cx - gl.width / 2, yy - gl.height / 2)
    out = squeeze(inner, sc, sc, SW / 2, SH / 2) if abs(sc - 1) > 0.002 else inner
    return fade(out, alpha)


# ================================================================= Bildschirminhalt
def content(t):
    # ---- Ruhebild, Play, Zoom-Explosion (wie Part 1)
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
            col = tuple(int(lerp(a, b, c01((t - 0.56) / 0.04))) for a, b in zip(FROST, ICEFIELD))
            img.alpha_composite(bar_layer(PLACEHOLDER, (128, 134, 144), t, fill_w=BAR["w"] * s_, fill_h=BAR["h"] * s_,
                                          radius=BAR["h"] * 0.22 * s_, fill_col=col, content_a=1 - c01(q * 2)))
        return img
    # ---- Hook: Schuss mit echter Rekordgeschwindigkeit
    if t < 1.20:
        out = hook_frame(t)
        q = c01((t - 0.60) / 0.05)
        if q < 1:
            out = Image.blend(Image.new("RGBA", (SW, SH), ICEFIELD + (255,)), out, q)
        return out
    img = bg()
    # ---- Verschluss zurück zur Leiste
    if t < 1.50:
        vg = 1.0
        fx.blob(img, BAR["cx"], BAR["cy"], 0.6 * SW, 0.36 * SW, (255, 255, 255), 0.3 * vg * 0.6)
        edge_vignette(img, (30, 120, 240), 0.8 * vg)
        if t < 1.33:
            q = e_in(c01((t - 1.20) / 0.13), 3)
            top, bot = lerp(0, BAR["cy"] - BAR["h"] / 2, q), lerp(SH, BAR["cy"] + BAR["h"] / 2, q)
            src = hook_frame(1.19).crop((0, int(top), SW, int(bot)))
            lay = layer()
            lay.alpha_composite(src.resize((SW, max(1, int(bot - top)))), (0, int(top)))
            img.alpha_composite(mblur(lay, 0, 30 * (1 - q) + 10))
            return img
        q = e_expo(c01((t - 1.33) / 0.17))
        w_ = lerp(SW, BAR["w"], q)
        col = tuple(int(lerp(a, b, q)) for a, b in zip(ICEFIELD, FROST))
        img.alpha_composite(bar_layer(PLACEHOLDER, (128, 134, 144), t, fill_w=w_, radius=BAR["h"] * 0.22 * q, fill_col=col,
                                      content_a=c01((t - 1.38) / 0.08), shimmer=c01((t - 1.35) / 0.15)))
        return img
    # ---- Tippen (nah), Senden, Leiste wird zur Timer-Spur
    if t < 3.30:
        if t < 1.80:
            vg = 1 - c01((t - 1.50) / 0.3)
            fx.blob(img, BAR["cx"], BAR["cy"], 0.6 * SW, 0.36 * SW, (255, 255, 255), 0.18 * vg)
            edge_vignette(img, (30, 120, 240), 0.8 * vg)
        if t < 2.86:
            img.alpha_composite(cam_apply(prompt_scene(t), *prompt_cam(t)))
            return img
        q = e_expo(c01((t - 2.86) / 0.24))
        fx.blob(img, SW / 2, NUM_CY, 0.36 * SW, 0.26 * SH, (30, 120, 255), 0.35 * q)
        cy, h = lerp(BAR["cy"], TRACK_Y, q), lerp(BAR["h"], 14, q)
        w_ = lerp(BAR["w"], TRACK_X1 - TRACK_X0, q)
        col = tuple(int(lerp(a, b, q)) for a, b in zip(FROST, (62, 64, 74)))
        lay = layer()
        ImageDraw.Draw(lay).rounded_rectangle((SW / 2 - w_ / 2, cy - h / 2, SW / 2 + w_ / 2, cy + h / 2), radius=lerp(BAR["h"] * 0.22, 7, q),
                                              fill=col + (240,))
        txt, ink = typed(t)
        lay.alpha_composite(fade(bar_layer(txt, ink, t, fill_a=0.0), 1 - c01((t - 2.86) / 0.1)))
        img.alpha_composite(lay)
        timer_track(img, t, c01((t - 3.05) / 0.2))
        lab = text_layer("GUESS THE SPEED", 64, 650, GREYTXT, 10, cx=SW / 2, cy=0.17 * SH, alpha=c01((t - 2.95) / 0.2))
        img.alpha_composite(lab)
        if t >= 3.00:
            cells = guess_cells(t)
            num = number_layer(cells, unit_a=c01((t - 3.10) / 0.15))
            drop = 1 - e_back(c01((t - 3.00) / 0.25), 1.7)
            moved = layer()
            put(moved, num, 0, -0.2 * SH * drop)
            img.alpha_composite(fade(moved, c01((t - 3.00) / 0.08)))
        return img
    # ---- Ratespiel bis zum Einrasten, dann Torlicht
    if t < 6.95:
        locked = t >= T_LOCK
        if locked:
            img.alpha_composite(burst_bg(t, T_LOCK))
            beams(img, t, 1.0 - c01((t - 6.75) / 0.15))
            d = ImageDraw.Draw(img)
            for k, ang in enumerate(PUCK_ANGLES):
                tau = t - T_LOCK - 0.03 - 0.025 * k
                if tau < 0:
                    continue
                s_ = e_back(tau / 0.15, 2.0) * 1.3 * lerp(1.0, 0.6, c01((t - 6.65) / 0.2))
                r = lerp(60, 420, e_out(tau / 0.6, 3)) + 30 * tau
                px = SW / 2 + math.cos(math.radians(ang + 20 * tau)) * r * 1.45
                py = NUM_CY + math.sin(math.radians(ang + 20 * tau)) * r
                black_puck(d, px, py, s_, 1 - c01((t - 6.65) / 0.2))
        else:
            fx.blob(img, SW / 2, NUM_CY, 0.36 * SW, 0.26 * SH, (30, 120, 255), 0.35)
        timer_track(img, t, 1 - c01((t - 6.15) / 0.15))
        lab_y = 0.17 * SH - 0.4 * SH * e_in(c01((t - T_LOCK) / 0.15), 2)
        img.alpha_composite(text_layer("GUESS THE SPEED", 64, 650, GREYTXT, 10, cx=SW / 2, cy=lab_y))
        cells = guess_cells(t) if not locked else static_cells((1, 0, 8, 8))
        col = WHITE
        num = number_layer(cells, color=col)
        if locked:
            k = math.exp(-(t - T_LOCK) * 9)
            num = squeeze(num, 1 + 0.06 * k, 1 + 0.06 * k, SW / 2, NUM_CY)
            glow(img, num, 34, 0.7)
            rp = e_back(c01((t - 6.25) / 0.2), 1.6)
            if rp > 0:
                pl = layer()
                pd = ImageDraw.Draw(pl)
                pw, ph = 440 * rp, 88 * rp
                pd.rounded_rectangle((SW / 2 - pw / 2, 0.73 * SH - ph / 2, SW / 2 + pw / 2, 0.73 * SH + ph / 2), radius=ph / 2,
                                     fill=(255, 255, 255, 235))
                if rp > 0.5:
                    pd.text((SW / 2, 0.73 * SH + 1), "NHL RECORD", font=ifont(700, int(54 * min(1, rp))), fill=(150, 20, 24, 255), anchor="mm")
                img.alpha_composite(pl)
        else:
            img.alpha_composite(num)
        return img
    # ---- Wer? Chara 2012, dann NHL | AHL
    if t < 9.80:
        rec = c01((t - 6.95) / 0.30)
        if t < 7.10:
            img.alpha_composite(burst_bg(t, T_LOCK))
        fx.blob(img, SW / 2, 0.40 * SH, 0.36 * SW, 0.26 * SH, (30, 120, 255), 0.30 * e_io(rec))
        twist = t >= 8.30
        cells = static_cells((1, 0, 8, 8)) if t < 8.75 else reroll_cells(t, 8.75)
        orange = c01((t - 8.80) / 0.25)
        col = tuple(int(lerp(a, b, orange)) for a, b in zip(WHITE, ORANGE))
        num = number_layer(cells, color=col)
        s_ = lerp(1.0, 0.86, e_io(rec))
        num = squeeze(num, s_, s_, SW / 2, NUM_CY)
        moved = layer()
        put(moved, num, 0, lerp(0, -0.06 * SH, e_io(rec)) + (0.06 * SH * e_io(c01((t - 8.30) / 0.3)) if twist else 0))
        img.alpha_composite(moved)
        yb = NAME_Y + 0.06 * SH * e_io(c01((t - 8.30) / 0.3))
        if t < 8.85:
            img.alpha_composite(name_line("Zdeno Chara", "2012", 7.05, y=yb, t=t))
        else:
            q = e_expo(c01((t - 8.85) / 0.14))
            a = band_mask(name_line("Zdeno Chara", "2012", -10, 1 - q, y=yb - 0.07 * SH * q, t=t), yb - 0.09 * SH, yb + 0.09 * SH)
            b = band_mask(name_line("Martin Frk", "2020", -10, q, y=yb + 0.07 * SH * (1 - q), t=t), yb - 0.09 * SH, yb + 0.09 * SH)
            img.alpha_composite(a)
            img.alpha_composite(b)
        if twist:
            oy = lerp(1.30 * SH - TOG["cy"], 0, e_io(c01((t - 8.30) / 0.27)))
            oy += -0.012 * SH * math.exp(-(t - 8.57) * 9) * math.sin((t - 8.57) * 24) if t > 8.57 else 0
            img.alpha_composite(league_toggle(t, oy))
        return img
    # ---- CTA: WHO BREAKS 108.8? COMMENT A NAME
    if t < T_MARK:
        q = e_in(c01((t - 9.80) / 0.15), 2)
        if q < 1:
            grp = layer()
            num = number_layer(reroll_cells(t, 8.75), color=ORANGE)
            num = squeeze(num, 0.86, 0.86, SW / 2, NUM_CY)
            put(grp, num, 0, 0)
            grp.alpha_composite(name_line("Martin Frk", "2020", -10, y=NAME_Y + 0.06 * SH, t=t))
            grp.alpha_composite(league_toggle(t))
            img.alpha_composite(fade(squeeze(grp, lerp(1, 0.6, q), lerp(1, 0.6, q), SW / 2, SH / 2), 1 - q))
        if t >= 10.10:
            bxp = lerp(0.85, 0.15, (t - 10.10) / 1.0) * SW
            for by in (0.43 * SH, 0.57 * SH):
                fx.blob(img, bxp, by, 0.10 * SW, 0.10 * SW, ICE, 0.4)
        p = e_out(c01((t - 9.92) / 0.25), 3)
        if p > 0:
            lay = layer()
            d = ImageDraw.Draw(lay)
            rc = (SW / 2, 0.25 * SH)
            R = 110
            d.arc((rc[0] - R, rc[1] - R, rc[0] + R, rc[1] + R), -90, -90 + 360 * e_io(c01((t - 9.92) / 0.3)), fill=WHITE + (255,), width=6)
            padlock(d, rc[0], rc[1] - 4, 1.35, 1 - e_back(c01((t - 10.45) / 0.2), 2.0))
            img.alpha_composite(fade(lay, p))
            l1 = text_layer(CTA1, 100, 700, (238, 240, 244), 2, cx=SW / 2 + 0.03 * SW * (1 - e_expo((t - 10.00) / 0.2)), cy=0.53 * SH,
                            alpha=e_expo((t - 10.00) / 0.2))
            img.alpha_composite(l1)
            pp = e_back(c01((t - 10.10) / 0.22), 1.6)
            if pp > 0:
                pl = layer()
                pd = ImageDraw.Draw(pl)
                pw = (ifont(650, 90).getlength(CTA2) + 120) * pp
                ph = 140 * pp
                pd.rounded_rectangle((SW / 2 - pw / 2, 0.74 * SH - ph / 2, SW / 2 + pw / 2, 0.74 * SH + ph / 2), radius=ph / 2, fill=ORANGE + (255,))
                if pp > 0.5:
                    pd.text((SW / 2, 0.74 * SH + 3), CTA2, font=ifont(650, max(8, int(90 * min(1, pp)))), fill=(40, 22, 8, 255), anchor="mm")
                glow(img, pl, 26, 0.5)
        return img
    # ---- Wortmarke, Loop zurück in die Leiste
    if t < 12.60:
        img = Image.new("RGBA", (SW, SH), (0, 0, 0, 255))
        img.alpha_composite(wordmark(t))
        return img
    if t >= 13.10:
        return rest_state()
    q = c01((t - 12.60) / 0.5)
    bga = e_io(c01((t - 12.65) / 0.30))
    img = Image.blend(Image.new("RGBA", (SW, SH), (0, 0, 0, 255)), bg(), bga)
    fx.blob(img, BAR["cx"], BAR["cy"], 0.45 * SW, 0.27 * SW, (255, 255, 255), 0.06 * bga)
    img.alpha_composite(wordmark(t, scale_extra=lerp(1.0, 0.55, e_in(q, 2)), alpha=1 - e_in(c01(q / 0.6), 2)))
    ba = e_out(c01((t - 12.80) / 0.30), 3)
    if ba > 0:
        img.alpha_composite(fade(bar_layer(PLACEHOLDER, (128, 134, 144), t, scale=lerp(0.94, 1.0, ba)), ba))
    return img


def screen(t):
    img = content(t)
    p1.chrome(img, t)
    return img


# ================================================================= Rendering
FAST = [(0.50, 0.62, 24), (0.62, 1.12, 16), (1.20, 1.50, 12), (1.50, 1.74, 12), (2.54, 2.72, 16), (2.86, 3.30, 8),
        (6.08, 6.30, 8), (6.95, 7.30, 12), (8.30, 8.60, 24), (8.62, 9.12, 12), (9.78, 10.05, 12), (12.60, 13.10, 6)]
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
    mx = pa.Mix(DUR, seed=21)
    T = mx.t
    mx.put(mx.room, mx.click(), T_PLAY, 0.9)
    n = mx.n
    x = np.arange(n) / pa.SR
    pad = np.zeros(n)
    rng = np.random.default_rng(5)
    for f in (293.7, 587.3, 880.0, 1174.7):
        for det in (-0.003, 0.0, 0.003):
            pad += np.sin(2 * np.pi * f * (1 + det) * x + rng.uniform(0, 6.28)) / (1 + (f > 400) * 1.5)
    pad /= 12
    lvl = np.interp(x, [0, T_PLAY, T_PLAY + 0.4, 3.2, 5.3, 5.7, 6.1, 11.2, 12.7, DUR],
                    [0.06, 0.06, 0.2, 0.2, 0.26, 0.12, 0.2, 0.2, 0.06, 0.06])
    duck = 1 - 0.5 * np.clip((x - 6.10) / 0.05, 0, 1) * np.clip((7.2 - x) / 0.3, 0, 1)
    mx.lap += pad * lvl * duck
    mx.put(mx.lap, mx.whoosh(0.2, 0.3), 0.40)
    mx.put(mx.lap, mx.whoosh(0.16, 0.45), 0.50)
    # Schlagschuss: Knall beim Treffen, Puck-Zischen, Einschlag im Netz
    ck = T(0.08)
    crack = (mx.rng.standard_normal(len(ck)) * np.exp(-ck * 90) + np.sin(2 * np.pi * 900 * ck) * np.exp(-ck * 60) * 0.6) * 0.9
    mx.put(mx.lap, crack, 0.64)
    mx.put(mx.lap, mx.whoosh(0.42, 0.5, rise=True), 0.64)
    mx.put(mx.lap, mx.thud(0.6), T_SHOT1)
    mx.put(mx.lap, mx.whoosh(0.3, 0.25, rise=False), T_SHOT1 + 0.02)
    mx.put(mx.lap, mx.whoosh(0.25, 0.3, rise=False), 1.20)
    for k in KEY_T:
        mx.put(mx.lap, mx.click() * 0.08, k)
    mx.put(mx.lap, mx.pop(1800, 0.1), 2.72)
    mx.put(mx.lap, mx.chime(880.0, vol=0.3), 2.73)
    mx.put(mx.lap, mx.whoosh(0.3, 0.25), 2.86)
    # Walzen-Ticken: Dichte folgt der Drehgeschwindigkeit, Einrast-Klicks
    tick = mx.click() * 0.10
    tt = 3.10
    while tt < 6.05:
        live = sum(1 for a, b, f, tk in LOCKS if a <= tt < b + 0.3)
        if live:
            mx.put(mx.lap, tick * (0.5 + 0.15 * live), tt)
        tt += 1 / (18 + 6 * live)
    for a, b, f, tk in LOCKS:
        mx.put(mx.lap, mx.pop(1300, 0.18), b + 0.3)
        for tkt, _ in tk:
            mx.put(mx.lap, mx.pop(1500, 0.16), tkt)
    mx.put(mx.lap, mx.pluck(659.3, vol=0.2), 5.62)
    # Schloss zu + Torlicht + Hupe
    mx.put(mx.lap, mx.click() * 0.8, T_LOCK)
    hx = T(1.15)
    horn = sum(2 * ((hx * f * (1 + 0.002 * np.sin(2 * np.pi * 5 * hx))) % 1) - 1 for f in (110.0, 165.0, 220.0, 221.5)) / 4
    horn = np.convolve(horn, np.ones(12) / 12, mode="same") * np.minimum(hx / 0.06, 1) * np.clip((1.15 - hx) / 0.25, 0, 1) * 0.75
    mx.put(mx.lap, horn, T_LOCK)
    mx.put(mx.lap, mx.thud(0.6), T_LOCK)
    mx.put(mx.lap, mx.pop(700, 0.3), T_LOCK + 0.02)
    mx.put(mx.lap, mx.pop(800, 0.25), T_LOCK + 0.35)
    mx.put(mx.lap, mx.whoosh(0.3, 0.25), 6.95)
    for k, f in enumerate((659.3, 784.0, 880.0, 1046.5)):
        mx.put(mx.lap, mx.pluck(f, vol=0.12), 7.08 + 0.09 * k)
    mx.put(mx.lap, mx.whoosh(0.22, 0.4, rise=False), 8.30)
    mx.put(mx.lap, mx.whoosh(0.28, 0.15), 8.65)
    mx.put(mx.lap, mx.chime(1046.5, vol=0.25), 8.80)
    mx.put(mx.lap, mx.whoosh(0.25, 0.25), 9.80)
    mx.put(mx.lap, mx.pop(1500, 0.12), 10.45)
    mx.put(mx.lap, mx.pad([130.8, 261.6], 1.0, vol=0.2, attack=0.3, release=0.6), 10.1)
    mx.put(mx.lap, mx.shimmer(0.4, 0.35), 10.95)
    mx.put(mx.lap, mx.thud(0.45), T_MARK)
    for k in range(len(MARK)):
        mx.put(mx.lap, mx.click() * 0.1, T_MARK + 0.04 * k + 0.2)
    mx.put(mx.lap, mx.whoosh(0.4, 0.2, rise=False), 12.63)
    mx.render(path, lap_gain=1.0, room_gain=0.6, target_peak=0.5)


def main():
    os.chdir(HERE)
    make_audio("audio_aishot.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{room.W}x{room.H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_aishot.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "22",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart",
           "reel13_ai_shot.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(4) as pool:
        for k, buf in enumerate(pool.imap(render_frame, range(nf), chunksize=2)):
            proc.stdin.write(buf)
            if k % 60 == 0:
                print(f"{k}/{nf}", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.frombytes("RGB", (room.W, room.H), render_frame(int(6.3 * FPS))).save("reel13_thumbnail.jpg", quality=92)
    print("fertig: reel13_ai_shot.mp4")


if __name__ == "__main__":
    main()
