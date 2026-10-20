"""Reel 33: "WHAT DO ALL THESE LINES MEAN?" – Neuauflage im "Blackout Arena"-Look mit Branding (~21 s).

Inhalt, Fakten, Voiceover, Timing, Kamerafahrten und Puck-Demos aus reel32_lines.py (dort auch die Regel-Belege).
Neu (User fand reel32 zu blass/unanschaulich):
- Dunkle Arena in Markenfarben (Navy #262334, Orange #FF923C): das 3D-Bild wird pro Pixel über die Eisebene
  abgedunkelt, Spotlicht-Kegel folgen der Station. Alle Markierungen werden als leuchtende Neon-LEDs neu gezeichnet
  (scharfe Linie + zwei Glow-Stufen) und schalten sich im Hook nacheinander ein.
- Anschaulicher: Zonen eingefärbt, Puck mit Kometenschweif, Pfeile, große Neon-Ergebniswörter.
- Branding: Logo-Lockup oben, orangefarbene Zahl-Chips, Endkarte mit Logo und "Follow"-Zeile.
Aufruf: python3 reel33_lines_neon.py audio | prev 1.0,4.2 out.jpg | (ohne Argument: Video)
"""
import math
import os
import subprocess
import sys
import time

import cairocffi as cairo
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, zoom

import mesh3d as M3
import reel15_puck as R15
import reel26_overglass as R26
import reel28_emptynet as R28
import reel31_powerplay as M
import reel32_lines as L
from reel15_puck import W, H, FPS, c01, sio, e_out, lerp, proj, px_per_in, surface, surf_rgba, over

HERE = R15.HERE
NAVY = (38, 35, 52)
ORANGE = (255, 146, 60)
WHITE = (246, 246, 250)
NEON_R = (255, 58, 72)
NEON_B = (70, 150, 255)
NEON_G = (60, 230, 130)
VO_START, wt, scene_end = L.VO_START, L.wt, L.scene_end
GOAL_X, END_X, GL_Z = L.GOAL_X, L.END_X, L.GL_Z
DUR = 21.3
L.DUR = DUR                                       # Ton (L.make_audio) läuft bis zur Endkarte
T_END = 19.95                                     # Endkarte mit Logo
L.T_TRAP_OUT = wt("trap", 6)                      # Puck verlässt das Trapez bei "behind" (2 MIN gut lesbar)
_puck_state_32 = L.puck_state


def _puck_state(t):
    """Wie reel32, aber in der Trapez-Szene bleibt der Puck im Bild (Ecke knapp außerhalb des Trapezes)."""
    if VO_START["trap"] - 0.25 <= t < VO_START["cta"] - 0.3:
        u = sio(c01((t - L.T_TRAP_OUT + 0.1) / 0.5))
        return np.array([lerp(1150.0, 1160.0, u), 0.5, lerp(70.0, 182.0, u)]), 1.0
    return _puck_state_32(t)


L.puck_state = _puck_state
_a, _b, _ = L.SHOTS[6]                           # Trapez-Einstellung etwas weiter, damit die Ecke im Bild ist
L.SHOTS[6] = (_a, _b, (np.array([860.0, 800.0, 0.0]), np.array([1125.0, 0.0, 20.0]), 50.0))


# ================================================================= Licht: Eis abdunkeln + Spotlicht-Kegel
def ice_hits(row):
    pos, r, u, f, tanh = row[0:3], row[3:6], row[6:9], row[9:12], row[12]
    sx = ((np.arange(W) + 0.5) / W * 2 - 1) * tanh * W / H
    sy = (1 - (np.arange(H) + 0.5) / H * 2) * tanh
    d = f[None, None, :] + sx[None, :, None] * r[None, None, :] + sy[:, None, None] * u[None, None, :]
    dy = d[..., 1]
    tt = np.where(dy < -1e-6, -pos[1] / np.minimum(dy, -1e-6), np.inf)
    hx = pos[0] + tt * d[..., 0]
    hz = pos[2] + tt * d[..., 2]
    qx, qz = np.abs(hx) - (1200 - 336), np.abs(hz) - (510 - 336)
    sd = np.hypot(np.maximum(qx, 0), np.maximum(qz, 0)) + np.minimum(np.maximum(qx, qz), 0) - 336
    on_ice = np.isfinite(tt) & (sd < 0)
    return hx, hz, on_ice


def pools(t):
    """Spotlicht-Kegel (x, z, Radius, Stärke) je Station, weich überblendet."""
    sets = [(0.0, [(0, 0, 900, 0.55)]),
            (VO_START["red"], [(0, 0, 420, 0.9), (700, 0, 520, 0.5)]),
            (VO_START["blue"], [(330, 0, 380, 1.0)]),
            (VO_START["goal"], [(1068, 0, 110, 1.3)]),
            (VO_START["dots"], [(0, 0, 900, 0.6)]),
            (VO_START["crease"], [(1040, 0, 160, 1.2)]),
            (VO_START["trap"], [(1130, 0, 200, 1.1)]),
            (VO_START["cta"], [(0, 0, 1000, 0.7)])]
    out = []
    for i, (t0, ps) in enumerate(sets):
        a = c01((t - t0 + 0.3) / 0.5) if i else 1.0
        b = 1 - c01((t - sets[i + 1][0] + 0.3) / 0.5) if i + 1 < len(sets) else 1.0
        w = a * b
        if w > 0.01:
            out += [(x, z, r, s * w) for x, z, r, s in ps]
    return out


def light_map(row, t):
    hx, hz, on_ice = ice_hits(row)
    lm = np.full((H, W), 0.42, np.float32)
    for x, z, r, s in pools(t):
        lm += s * np.exp(-((hx - x) ** 2 + (hz - z) ** 2) / (2 * r * r)).astype(np.float32)
    lm = np.where(on_ice, lm, 0.30 + 0.25 * np.clip(lm - 0.42, 0, 1))
    return lm[..., None].astype(np.float32)


ICE_TINT = np.array([0.26, 0.29, 0.50], np.float32)


# ================================================================= Neon
def vis_runs(row, pts):
    """Polylinie in sichtbare Stücke teilen (Punkte hinter der Kamera fallen weg)."""
    xy, z = proj(row, pts)
    runs, cur = [], []
    for p, zz in zip(xy, z):
        if zz > 3 and abs(p[0]) < 6 * W and abs(p[1]) < 6 * H:
            cur.append(p)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return [np.array(rn) for rn in runs if len(rn) > 1]


def neon(ctx, row, pts, col, a, w=4.0, dash=None, t=0.0):
    if a <= 0.01:
        return
    for rn in vis_runs(row, pts):
        if dash:
            ctx.set_dash(dash, -t * 90)
        R15.stroke_poly(ctx, rn, col, min(1.0, a), w)
        ctx.set_dash([])


def neon_fill(ctx, row, pts, col, a):
    if a <= 0.01:
        return
    xy, z = proj(row, pts)
    if (z <= 3).any():
        return
    ctx.set_source_rgba(col[0] / 255, col[1] / 255, col[2] / 255, min(1.0, a))
    ctx.move_to(*xy[0])
    for q in xy[1:]:
        ctx.line_to(*q)
    ctx.close_path()
    ctx.fill()


def circle_pts(x, z, r, n=72):
    return np.array([[x + r * math.cos(a), 0.2, z + r * math.sin(a)] for a in np.linspace(0, 2 * math.pi, n)])


def rink_outline():
    pts = []
    for cx, cz, a0 in ((864, 174, 0), (-864, 174, 90), (-864, -174, 180), (864, -174, 270)):
        for a in np.linspace(math.radians(a0), math.radians(a0 + 90), 16):
            pts.append([cx + 336 * math.cos(a), 0.2, cz + 336 * math.sin(a)])
    pts.append(pts[0])
    return np.array(pts)


RINK_OUT = rink_outline()


def switch(t, t0):
    """LED-Einschalten mit kurzem Flackern."""
    u = t - t0
    if u < 0:
        return 0.0
    if u < 0.16:
        return [0.9, 0.2, 1.0, 0.4, 1.0, 1.0, 1.0, 1.0][int(u / 0.02)]
    return 1.0


def focus_level(t, key, t0=None):
    """1 -> Station aktiv (hell + Puls), sonst gedimmt."""
    t0 = VO_START[key] if t0 is None else t0
    if t < t0 - 0.1 or t > scene_end(key) + 0.25:
        return 0.0
    u = t - t0
    return c01((u + 0.1) / 0.15) * (1 - c01((t - scene_end(key)) / 0.25)) * (1.0 + 0.6 * math.exp(-max(u, 0) / 0.35))


def markings(ctx, row, t):
    """Alle Linien als Neon. Grundhelligkeit nach dem Hook 0.30, aktive Station hell."""
    on = [switch(t, -0.12 + 0.12 * i) for i in range(8)]      # Hook: nacheinander einschalten (Bild 0 schon an)
    in_hook = t < VO_START["red"]
    base = lambda k: on[k] * (1.0 if in_hook else 0.30)
    cta = c01((t - VO_START["cta"] - 0.2) / 0.5)              # am Ende alles wieder hell
    lvl = lambda key: max(focus_level(t, key), 0.75 * cta)
    neon(ctx, row, RINK_OUT, (190, 200, 230), on[0] * (0.7 if in_hook else 0.45), 2.5)
    neon(ctx, row, L.seg_pts((0, -505), (0, 505), 40), NEON_R, base(1) + lvl("red"), 6)
    for x in (-300, 300):
        neon(ctx, row, L.seg_pts((x, -505), (x, 505), 40), NEON_B, base(2) + lvl("blue"), 6)
    for sx in (-1, 1):
        neon(ctx, row, L.seg_pts((GOAL_X * sx, -GL_Z), (GOAL_X * sx, GL_Z), 40), NEON_R,
             base(3) + (lvl("goal") if sx > 0 else 0.75 * cta) + 0.9 * L.pulse(t, L.T_ICING - 0.05, 0.4) *
             (t < scene_end("red") + 0.2) * (sx > 0), 3)
        cr = L.crease_pts(sx)
        neon(ctx, row, cr, NEON_B, base(5) + lvl("crease"), 3)
        neon_fill(ctx, row, cr, NEON_B, 0.10 * (base(5) + 0.8 * lvl("crease")))
        for a, b in L.TRAP_SIDES:
            if (a[0] > 0) == (sx > 0):
                neon(ctx, row, L.seg_pts(a, b, 10), NEON_R, base(6) + (lvl("trap") if sx > 0 else 0.75 * cta), 3)
    neon(ctx, row, circle_pts(0, 0, 180), NEON_B, base(4) * 0.8, 2.5)
    for sx in (-1, 1):
        for sz in (-1, 1):
            neon(ctx, row, circle_pts(828 * sx, 264 * sz, 180), NEON_R, base(4) * 0.8, 2.5)
    for i, (x, z) in enumerate(L.DOTS_ORDER):
        t0 = VO_START["dots"] + 0.05 + 0.075 * i
        a = base(7) + lvl("dots") * c01((t - t0) / 0.08) + 0.75 * cta
        neon_fill(ctx, row, circle_pts(x, z, 12, 24), NEON_B if x == 0 else NEON_R, min(1.0, a))
        li = t - t0
        if 0 <= li < 0.6 and focus_level(t, "dots") > 0:
            neon(ctx, row, circle_pts(x, z, 30 + 110 * e_out(li / 0.6), 36), WHITE, 0.9 * (1 - li / 0.6), 3)


def demos(ctx, row, t, fill):
    """Anschauliche Demos je Station (auf eigener Fläche, mit Glow)."""
    # 1 Icing: eigene Hälfte eingefärbt, Puck mit Kometenschweif übers ganze Eis
    a = focus_level(t, "red")
    if a > 0:
        neon_fill(fill, row, np.array([[-1190, 0.1, -500], [0, 0.1, -500], [0, 0.1, 500], [-1190, 0.1, 500]]),
                  ORANGE, 0.10 * min(a, 1))
        p, vis = L.puck_state(t)
        if vis and t > wt("red", 2):
            tail = [L.puck_state(t - k * 0.02)[0] for k in range(14)]
            tail = np.array([q + [0, -0.3, 0] for q in tail if q[1] > 0])
            if len(tail) > 1:
                neon(ctx, row, tail, ORANGE, 0.9, 10)
            neon(ctx, row, L.seg_pts((-560, -140), (p[0], p[2]), 30, 0.3), ORANGE, 0.55, 3, [16, 14], t)
            neon_fill(ctx, row, circle_pts(p[0], p[2], 16, 24), WHITE, 1.0)
            neon(ctx, row, circle_pts(p[0], p[2], 30, 30), ORANGE, 0.9, 3)
    # 2 Abseits: Angriffszone eingefärbt, Angreifer vor dem Puck über der Linie
    a = focus_level(t, "blue")
    if a > 0:
        neon_fill(fill, row, np.array([[300, 0.1, -505], [1150, 0.1, -505], [1150, 0.1, 505], [300, 0.1, 505]]),
                  ORANGE, 0.12 * min(a, 1))
        u = e_out(c01((t - wt("blue", 2)) / 0.9), 2)
        ax_, az = lerp(140.0, 470.0, u), lerp(-60.0, -30.0, u)
        neon_fill(ctx, row, circle_pts(ax_, az, 22, 30), WHITE, 0.95 * min(a, 1))
        neon(ctx, row, circle_pts(ax_, az, 30, 30), NEON_R if t > L.T_OFF - 0.05 else WHITE, min(a, 1), 4)
        p, vis = L.puck_state(t)
        if vis:
            neon_fill(ctx, row, circle_pts(p[0], p[2], 10, 20), WHITE, 1.0)
            neon(ctx, row, circle_pts(p[0], p[2], 18, 24), ORANGE, 0.9, 3)
    # 6 Trapez: innen grün = erlaubt, Puck-Ring grün -> rot
    a = focus_level(t, "trap")
    if a > 0:
        inside = np.array([[GOAL_X, 0.1, -132.0], [END_X, 0.1, -168.0], [END_X, 0.1, 168.0], [GOAL_X, 0.1, 132.0]])
        neon_fill(fill, row, inside, NEON_G, 0.16 * min(a, 1))
        p, vis = L.puck_state(t)
        if vis:
            ok = p[2] < 132.0 + (p[0] - GOAL_X) / (END_X - GOAL_X) * 36.0
            neon(ctx, row, circle_pts(p[0], p[2], 9, 24), NEON_G if ok else NEON_R, 1.0, 4)


def glow_add(img, surf, k_sharp=1.0, k_glow=1.0):
    rgb, a = surf_rgba(surf)
    small = zoom(rgb, (0.25, 0.25, 1), order=1)
    g1 = np.stack([gaussian_filter(small[..., c], 2.0) for c in range(3)], -1)
    g2 = np.stack([gaussian_filter(small[..., c], 7.0) for c in range(3)], -1)
    glow = zoom(g1 * 1.4 + g2 * 1.2, (H / small.shape[0], W / small.shape[1], 1), order=1)
    return img + rgb * k_sharp + glow[:H, :W] * k_glow


# ================================================================= Branding
_BR = {}


def brand_img(name, width):
    key = (name, width)
    if key not in _BR:
        im = Image.open(os.path.join(HERE, "brand", name)).convert("RGBA")
        bb = im.getbbox()
        im = im.crop(bb)
        im = im.resize((width, int(im.height * width / im.width)), Image.LANCZOS)
        _BR[key] = M.Spr(im, im.width / 2, im.height / 2)
    return _BR[key]


def brand_bug(img, t):
    a = 0.92 * (1 - c01((t - T_END) / 0.25))
    draw = brand_img("bladesandpucks_lockup_transparent.png", 300)
    M.draw(img, draw, 540, 168, a)


def end_card(img, t):
    if t < T_END:
        return
    p = c01((t - T_END) / 0.35)
    img *= 1 - 0.72 * e_out(p)
    img += np.array(NAVY, np.float32) / 255 * 0.72 * e_out(p)
    mk = brand_img("bladesandpucks_mark_transparent.png", 300)
    M.draw(img, mk, 540, 760 + 40 * (1 - e_out(p)), p, 0.9 + 0.1 * M.back(p, 1.6))
    q = c01((t - T_END - 0.2) / 0.3)
    NLine([("BLADES", WHITE), ("&", ORANGE), ("PUCKS", WHITE)], "x9", 84, 540, 1010 + 30 * (1 - e_out(q)),
          [T_END + 0.2] * 3, None).render(img, t)
    hd = M.text_spr("@bladesandpucks", "in6", 40, (200, 200, 214))
    M.draw(img, hd, 540, 1075, q * 0.9)
    NLine([("FOLLOW", ORANGE), ("FOR", WHITE), ("1", WHITE), ("NHL", WHITE), ("RULE", WHITE), ("A", WHITE),
           ("DAY", WHITE)], "x9", 44, 540, 1170, [T_END + 0.4 + 0.04 * i for i in range(7)], None).render(img, t)


# ================================================================= Schrift (weiß/orange auf dunkel)
_SH = {}


def shadow(spr, sigma=10):
    k = id(spr)
    if k not in _SH:
        pad = int(sigma * 3)
        a = np.pad(spr.arr[..., 3], pad)
        g = np.clip(gaussian_filter(a, sigma) * 1.6, 0, 1) * 0.75
        arr = np.zeros(g.shape + (4,), np.float32)
        arr[..., :3] = g[..., None] * np.array(NAVY, np.float32) / 255 * 0.4
        arr[..., 3] = g
        _SH[k] = (arr, spr.ax + pad, spr.ay + pad)
    return _SH[k]


GLOW_COLS = (ORANGE, NEON_R, NEON_B, NEON_G)


class NLine(M.KLine):
    def __init__(self, words, fk, size, cx, cy, times, t_out, track=0.02, space=0.32, maxw=960):
        super().__init__(words, fk, L.fit(words, fk, size, maxw, track), cx, cy, times, t_out, track, space, 0.0)

    def render(self, dst, t):
        if self.t_out is not None and t > self.t_out + 0.25:
            return
        for i, spr in enumerate(self.sprs):
            if t < self.times[i]:
                continue
            x, y, a, s = self.state(t, i)
            x0, y0, _, _ = self.state(t - M.SHUT, i)
            sh, hx, hy = shadow(spr)
            M.blit(dst, sh, x - hx, y - hy + 4, a * 0.9)
            M.draw(dst, spr, x, y, a, s, x0, y0, glow=0.7 if self.cols[i] in GLOW_COLS else 0.0)


def chip(img, txt, cx, cy, a, s=1.0):
    M.draw(img, M.tag_spr(txt, ORANGE, NAVY, 30), cx - M.tag_spr(txt, ORANGE, NAVY, 30).img.width / 2 * s,
           cy - M.tag_spr(txt, ORANGE, NAVY, 30).img.height / 2 * s, a, s)


def title(img, t, key, num, name, col, sub):
    t0, t1 = VO_START[key] - 0.05, scene_end(key)
    if not (t0 <= t < t1 + 0.3):
        return
    p = c01((t - t0) / 0.25)
    chip(img, f"{num} / 6", 540, 262, p * (1 - c01((t - t1) / 0.2)), 0.8 + 0.2 * M.back(p, 1.6))
    NLine([(w, col) for w in name.split()], "x9", 104, 540, 352, [t0 + 0.04 * i for i in range(len(name.split()))],
          t1 + 0.03).render(img, t)
    NLine([(sub, WHITE)], "in6", 44, 540, 440, [t0 + 0.25], t1 + 0.05, track=0).render(img, t)


def slam(img, txt, size, col, cx, cy, t, t0, t1):
    if not (t0 <= t < t1 + 0.2):
        return
    p = (t - t0) / 0.28
    s = lerp(1.6, 1.0, M.back(p, 1.4))
    a = c01(p * 3) * (1 - c01((t - t1) / 0.2))
    spr = M.text_spr(txt, "x9", L.fit([(txt, col)], "x9", size, 980), col, 0.02)
    sh, hx, hy = shadow(spr, 14)
    M.blit(img, sh, cx - hx, cy - hy + 6, a)
    M.draw(img, spr, cx, cy, a, s, glow=1.1)


def typography(img, t):
    hook = [[("WHAT", WHITE), ("DO", WHITE), ("ALL", WHITE)], [("THESE", WHITE), ("LINES", ORANGE)],
            [("MEAN?", WHITE)]]
    for i, ln in enumerate(hook):
        NLine(ln, "x9", 118, 540, 340 + i * 132, [-0.6] * len(ln), VO_START["red"] - 0.3 + 0.03 * i).render(img, t)
    title(img, t, "red", 1, "RED LINE", NEON_R, "Splits the ice in half")
    slam(img, "ICING", 170, NEON_R, 540, 1040, t, L.T_ICING - 0.03, scene_end("red"))
    title(img, t, "blue", 2, "BLUE LINES", NEON_B, "They make the 3 zones")
    slam(img, "OFFSIDE", 150, NEON_R, 540, 1080, t, L.T_OFF - 0.03, scene_end("blue"))
    title(img, t, "goal", 3, "GOAL LINE", NEON_R, "The WHOLE puck must cross")
    slam(img, "NO GOAL", 140, NEON_R, 540, 1390, t, L.T_WHOLE - 0.05, L.T_CROSS)
    slam(img, "GOAL!", 170, NEON_G, 540, 1390, t, L.T_CROSS + 0.3, scene_end("goal"))
    title(img, t, "dots", 4, "9 FACEOFF DOTS", WHITE, "Every faceoff starts on one")
    title(img, t, "crease", 5, "THE CREASE", NEON_B, "The goalie's blue paint")
    title(img, t, "trap", 6, "TRAPEZOID", NEON_R, "Goalie may play it in here")
    slam(img, "OK", 160, NEON_G, 540, 1330, t, wt("trap", 4), L.T_TRAP_OUT + 0.15)
    slam(img, "2 MIN", 160, NEON_R, 540, 1330, t, L.T_TRAP_OUT + 0.45, scene_end("trap"))
    c0 = VO_START["cta"] - 0.05
    out = T_END - 0.1
    NLine([("SAVE", ORANGE), ("THIS", ORANGE), ("FOR", WHITE), ("YOUR", WHITE), ("NEXT", WHITE), ("GAME", WHITE)],
          "x9", 46, 540, 262, [c0 + 0.6 + 0.05 * i for i in range(6)], out).render(img, t)
    NLine([("WHICH", WHITE), ("ONE", WHITE), ("DIDN'T", WHITE)], "x9", 96, 540, 1180, [c0, c0 + 0.12, c0 + 0.24],
          out).render(img, t)
    NLine([("YOU", WHITE), ("KNOW?", WHITE)], "x9", 96, 540, 1296, [c0 + 0.5, c0 + 0.6], out).render(img, t)
    NLine([("COMMENT", WHITE), ("1–6", ORANGE)], "x9", 70, 540, 1410, [wt("cta", 5) - 0.05, wt("cta", 5) + 0.1],
          out).render(img, t)


# ================================================================= Abzeichen in Markenfarbe
_BADGE = {}


def badge_spr(n):
    if n not in _BADGE:
        from PIL import ImageDraw
        s, r = 3, 32
        im = Image.new("RGBA", (2 * r * s + 8 * s, 2 * r * s + 8 * s), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        c = r * s + 4 * s
        d.ellipse((c - r * s, c - r * s, c + r * s, c + r * s), fill=ORANGE + (255,), outline=WHITE + (255,),
                  width=3 * s)
        im = im.resize((im.width // s, im.height // s), Image.LANCZOS)
        tx = M.text_spr(str(n), "x9", 36, NAVY)
        im.alpha_composite(tx.img, (int(im.width / 2 - tx.ax), int(im.height / 2 - 2 - tx.ay)))
        _BADGE[n] = M.Spr(im, im.width / 2, im.height / 2)
    return _BADGE[n]


def badges(img, row, t):
    if t > T_END:
        return
    for n, p, key in L.BADGES:
        t0 = VO_START[key] + 0.15
        if t < t0:
            continue
        xy, z = R15.projected(row, p)
        if z <= 3 or not (-40 < xy[0] < W + 40 and -40 < xy[1] < H + 40):
            continue
        s = 0.6 + 0.4 * M.back((t - t0) / 0.35, 2.0)
        if t >= VO_START["cta"]:
            u = t - (VO_START["cta"] + 0.5 + 0.12 * n)
            s *= 1 + 0.3 * math.exp(-u * 6) * (u > 0)
        M.draw(img, badge_spr(n), xy[0], xy[1], 1.0, s)


# ================================================================= Bild
_VIG = None


def vignette():
    global _VIG
    if _VIG is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = ((xx - W / 2) / (W * 0.7)) ** 2 + ((yy - H * 0.5) / (H * 0.62)) ** 2
        _VIG = (1 - 0.45 * np.clip(d, 0, 1.3))[..., None].astype(np.float32)
    return _VIG


def compose(t, fidx=0):
    base, puck, cov = L.render3d(t, fidx)
    row, _ = L.cam_row_at(t)
    campos = L.cam(t)[0]
    p, vis = L.puck_state(t)
    lm = light_map(row, t)
    img = base * ICE_TINT * lm                                      # Eis dunkel, Spotlicht-Kegel
    lo_s, lo_c = surface()
    R28.draw_net_lines(lo_c, row)
    img = over(img, *surf_rgba(lo_s))
    fill_s, fill_c = surface()
    em_s, em_c = surface()
    markings(em_c, row, t)
    demos(em_c, row, t, fill_c)
    img = over(img, *surf_rgba(fill_s))
    img = glow_add(img, em_s)
    meshes = R28.BOARDS + R28.FRAMES
    if vis > 0:
        import reel25_goalline as G
        meshes = meshes + [G.cyl_mesh(p - np.array([0, 0.5, 0]), 1.5, 1.0, "occluder", group=1)]
    m_rgb, m_a, shadow_, plane_a = M3.render(meshes, row, W, H, campos, alpha_by_group=np.array([1.0, 0.0], np.float32),
                                             extra_planes=[(R28.GLASS_ALL, 1.0)], shadow_light=(0.02, 1.0, -0.03))
    pa = cov[..., None]
    img = img * (1 - pa) + puck * pa * (0.55 + 0.45 * np.clip(lm, 0, 1.6))
    img = img * (1 - m_a[..., None]) + m_rgb * np.array([0.42, 0.42, 0.55], np.float32) * np.clip(lm * 1.3, 0.3, 1.4)
    k = (0.22 * plane_a)[..., None]
    img = img * (1 - k) + np.array([0.20, 0.24, 0.40], np.float32) * k
    img = img + (R26.glass_streaks() * plane_a * 0.06)[..., None]
    img = (img * vignette()).astype(np.float32)
    badges(img, row, t)
    typography(img, t)
    brand_bug(img, t)
    end_card(img, t)
    img += np.random.default_rng(fidx).normal(0, 0.007, (H, W))[..., None].astype(np.float32)
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


# ================================================================= Ausgabe
def remux():
    os.chdir(HERE)
    L.make_audio("audio_lines_neon.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "reel33_lines_neon.mp4", "-i", "audio_lines_neon.wav", "-map",
                    "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-af",
                    "loudnorm=I=-14:TP=-1.0:LRA=9", "-ar", "44100", "-shortest", "-movflags", "+faststart",
                    "_tmp_neon.mp4"], check=True)
    os.replace("_tmp_neon.mp4", "reel33_lines_neon.mp4")


def preview(ts, out):
    ims = [Image.fromarray(compose(float(t), int(float(t) * FPS))) for t in ts]
    cw, ch = W // 3, H // 3
    cols = min(6, len(ims))
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * ch), (40, 40, 40))
    for i, im in enumerate(ims):
        sheet.paste(im.resize((cw, ch), Image.LANCZOS), ((i % cols) * cw, (i // cols) * ch))
    sheet.save(out, quality=88)


def main():
    os.chdir(HERE)
    L.make_audio("audio_lines_neon.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_lines_neon.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "17",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
           "-ar", "44100", "-shortest", "-movflags", "+faststart", "reel33_lines_neon.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(0.8, 9999)).save("reel33_thumbnail.jpg", quality=92)
    print("fertig: reel33_lines_neon.mp4")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "audio":
        remux()
    elif len(sys.argv) > 1 and sys.argv[1] == "prev":
        preview(sys.argv[2].split(","), sys.argv[3])
    else:
        main()
