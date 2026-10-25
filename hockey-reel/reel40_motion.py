"""Reel 40 (Motion-Version): "IN THE NHL, YOU GET A POINT FOR LOSING." – komplett animierte Motion-Graphics (~16 s).

Gleicher Inhalt/Ton wie reel40_points.py (Stimme, Timing, Fakten), aber ohne Foto: Broadcast-Look in einer dunklen
Neon-Arena. Bausteine:
- 3D-Eisfläche als Textur (alle NHL-Markierungen, leuchtend) per Homographie in die Kamera gewarpt, Nebel/Tiefe,
  Kamera fliegt (Dolly/Orbit) und macht Whip-Pans mit Bewegungsunschärfe zwischen den Szenen.
- Arena: Banden-Kanten + Glas in 3D (leuchtend), Tribünen-Lichter als 3D-Punkte (Parallaxe), Lichtkegel vom Dach.
- Neon-Tor (3D-Drahtgitter), Puck-Figuren als 3D-Zylinder mit Spiegelung im Eis, Wackelaugen, Medaille.
- Projektionen aufs Eis ("NHL", "EUROPE", ...), Glas-Karten mit 3D-Kippung und Unschärfe dahinter, Kinetic Type,
  Chip-Stapel (Punkte pro Spiel), Versus-Split mit Blitz.
- Post: Bloom, Chromatic Aberration + Shake bei Impacts, Vignette, Korn.
Fakten (siehe reel40_points.py): NHL 2026-27 Rule 78.1/84.1 (Sieg 2, OT/SO-Niederlage 1, reguläre Niederlage 0);
SHL/Liiga/DEL 3-2-1-0 (offizielle Seiten/Tabellen 2025-26/2026-27). Keine Teams/Vereine, keine Spielerkörper.
Aufruf: python3 reel40_motion.py audio | prev 0.5,3.0 out.jpg | (Video)
"""
import math
import os
import subprocess
import sys
import time
import wave
from multiprocessing import Pool

import cairocffi as cairo
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import reel31_powerplay as M
import reel40_points as P40
from reel15_puck import put

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30
SHUT = 0.7 / FPS
TEMPO = P40.TEMPO
VO_LINES, VO_KEYS, VO_START, WT, DUR = P40.VO_LINES, P40.VO_KEYS, P40.VO_START, P40.WT, P40.DUR
wt = P40.wt

WHITE = (244, 244, 246)
RED = (255, 52, 70)
BLUE = (60, 150, 255)
ICE = (150, 215, 255)
GOLD = (255, 196, 64)
GREEN = (60, 225, 120)
ORANGE = (255, 140, 40)

# ================================================================= Timeline
T_SHOT, T_GOAL = 0.12, 0.92                      # Puck A trifft in der Verlängerung
T_MEDAL = wt("q", 6) - 0.05                      # "point": Medaille fällt auf B
T_LAND = T_MEDAL + 0.36
T_LOSE = wt("q", 8)                              # "losing"
T_TWO1 = wt("nhl", 1)                            # "two"
T_OTL = wt("nhl", 3)                             # "lose (in overtime)"
T_ONE = wt("nhl", 10)                            # "one"
T_REG = wt("eu", 6)                              # "regulation"
T_EU3 = wt("eu", 10)                             # "three"
T_THREE = wt("twist", 8)                         # "three (points)"
T_TWO = wt("twist", 12)                          # "two"
T_CTA = VO_START["cta"]
CUTS = [2.33, 5.78, 9.43, 13.23]                 # Whip-Pans zwischen den Szenen
WHIP = 0.30
SCENE_T = [0.0] + CUTS + [DUR]
IMPACTS = [T_GOAL, T_LAND, T_LOSE, T_ONE, T_EU3, T_THREE, T_TWO, T_CTA + 0.02, wt("cta", 3)]


def scene(t):
    for i in range(len(CUTS)):
        if t < CUTS[i]:
            return i
    return len(CUTS)


# ================================================================= kleine Helfer
c01, e_out, e_in, sio, lerp = M.c01, M.e_out, M.e_in, M.sio, M.lerp


def smooth(a, b, x):
    return sio((x - a) / (b - a))


def vec(*a):
    return np.array(a, np.float64)


# ================================================================= Kamera
class Cam:
    def __init__(self, pos, tgt, fov):
        self.pos = np.asarray(pos, np.float64)
        f = np.asarray(tgt, np.float64) - self.pos
        self.fwd = f / np.linalg.norm(f)
        r = np.cross(self.fwd, vec(0, 1, 0))
        self.right = r / np.linalg.norm(r)
        self.up = np.cross(self.right, self.fwd)
        self.f = (H / 2) / math.tan(math.radians(fov) / 2)
        self.R = np.stack([self.right, self.up, self.fwd])

    def cam(self, P):
        return (np.atleast_2d(P) - self.pos) @ self.R.T

    def proj(self, P):
        q = self.cam(P)
        z = q[:, 2]
        zz = np.where(np.abs(z) < 1e-6, 1e-6, z)
        return np.stack([W / 2 + self.f * q[:, 0] / zz, H / 2 - self.f * q[:, 1] / zz], 1), z

    def floor_h(self, x0, z0, ppf):
        """Homographie Texturpixel (tx, ty) -> Bildpixel für die Ebene y = 0 (x = x0 + tx/ppf, z = z0 + ty/ppf)."""
        a = self.R[:, 0] / ppf
        b = self.R[:, 2] / ppf
        c = self.R @ (vec(x0, 0, z0) - self.pos)
        Hm = np.zeros((3, 3))
        for j, col in enumerate((a, b, c)):
            Hm[0, j] = self.f * col[0] + W / 2 * col[2]
            Hm[1, j] = -self.f * col[1] + H / 2 * col[2]
            Hm[2, j] = col[2]
        return Hm

    def floor_rows(self):
        """Tiefe pro Bildzeile für die Eisebene (Kamera ohne Rollwinkel) – <= 0: kein Boden (über dem Horizont)."""
        v = np.arange(H, dtype=np.float64)
        dy = self.fwd[1] - (v - H / 2) / self.f * self.up[1]
        depth = np.where(dy < -1e-4, -self.pos[1] / np.minimum(dy, -1e-4), -1.0)
        return depth


def clip_lines(cam, P, closed=False, near=0.6):
    """3D-Polylinie an der Nahebene schneiden -> Liste von Bild-Polylinien."""
    P = np.asarray(P, np.float64)
    if closed:
        P = np.vstack([P, P[:1]])
    z = cam.cam(P)[:, 2]
    out, cur = [], []
    for i in range(len(P)):
        if z[i] >= near:
            if i > 0 and z[i - 1] < near:
                k = (near - z[i - 1]) / (z[i] - z[i - 1])
                cur.append(P[i - 1] + (P[i] - P[i - 1]) * k)
            cur.append(P[i])
        else:
            if i > 0 and z[i - 1] >= near:
                k = (near - z[i - 1]) / (z[i] - z[i - 1])
                cur.append(P[i - 1] + (P[i] - P[i - 1]) * k)
                out.append(cur)
                cur = []
    if cur:
        out.append(cur)
    res = []
    for seg in out:
        if len(seg) >= 2:
            xy, _ = cam.proj(np.array(seg))
            res.append(xy)
    return res


def key_cam(i, u):
    """Kamera der Szene i bei lokaler Zeit u (Sekunden seit Szenenbeginn)."""
    if i == 0:                                                   # Hook: tief vor dem Tor, langsamer Push
        k = sio(c01(u / 2.4))
        return Cam(vec(71.0 + 1.6 * k, 4.5 - 0.2 * k, -7.0 + 0.8 * k), vec(88.0, 2.4, -0.6), 52)
    if i == 1:                                                   # NHL: Orbit über der roten Seite
        a = math.radians(-128 + 9 * sio(c01(u / 3.5)))
        r = 46
        return Cam(vec(r * math.cos(a) * -1, 17 - 2 * sio(c01(u / 3.5)), r * math.sin(a)), vec(0, 2, 0), 56)
    if i == 2:                                                   # Europa: gegenüber, blaue Seite
        a = math.radians(52 + 9 * sio(c01(u / 3.6)))
        r = 46
        return Cam(vec(r * math.cos(a) * -1, 17 - 2 * sio(c01(u / 3.6)), r * math.sin(a)), vec(0, 2, 0), 56)
    if i == 3:                                                   # Pointe: hoch über der Mittellinie
        k = sio(c01(u / 3.8))
        return Cam(vec(0.0, 70 - 6 * k, -52 + 8 * k), vec(0, 0, -3), 60)
    k = sio(c01(u / 2.6))                                        # CTA: Bully-Punkt
    return Cam(vec(0.0, 8.5 - 0.6 * k, -27.0 + 3.0 * k), vec(0, 3.0, 0), 54)


def cam_at(t):
    i = scene(t)
    for j, c in enumerate(CUTS):
        if c - WHIP / 2 <= t < c + WHIP / 2:                     # Whip-Pan: Szene j -> j+1
            s = (t - (c - WHIP / 2)) / WHIP
            s = s * s * (3 - 2 * s)
            s = s * s * (3 - 2 * s)
            A = key_cam(j, c - WHIP / 2 - SCENE_T[j])
            B = key_cam(j + 1, 0.0)
            pos = A.pos + (B.pos - A.pos) * s
            fa, fb = A.pos + A.fwd * 40, B.pos + B.fwd * 40
            tgt = fa + (fb - fa) * s
            fov = 2 * math.degrees(math.atan((H / 2) / (A.f + (B.f - A.f) * s)))
            return Cam(pos, tgt, fov)
    return key_cam(i, t - SCENE_T[i])


def whip_amount(t):
    for c in CUTS:
        d = abs(t - c)
        if d < WHIP / 2:
            return math.sin(math.pi * (0.5 - d / WHIP)) ** 2
    return 0.0


# ================================================================= Eisfläche (Textur)
PPF = 12.0
TX0, TZ0 = -108.0, -50.0
TEX_W, TEX_H = int(216 * PPF), int(100 * PPF)
_TEX = {}


def rink_outline(n_corner=24, inset=0.0):
    """Abgerundetes Rechteck der Bande (200 x 85 ft, Eckradius 28 ft) als (x, z)-Punkte."""
    hx, hz, r = 100.0 - inset, 42.5 - inset, 28.0 - inset
    pts = []
    for cx, cz, a0 in ((hx - r, hz - r, 0), (-(hx - r), hz - r, 90), (-(hx - r), -(hz - r), 180), (hx - r, -(hz - r), 270)):
        for k in range(n_corner + 1):
            a = math.radians(a0 + 90 * k / n_corner)
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    return pts


def rink_texture():
    if "tex" in _TEX:
        return _TEX["tex"]
    ss = 2
    w, h = TEX_W * ss, TEX_H * ss

    def P(x, z):
        return ((x - TX0) * PPF * ss, (z - TZ0) * PPF * ss)

    base = Image.new("RGB", (w, h), (2, 3, 6))
    d = ImageDraw.Draw(base)
    d.polygon([P(x, z) for x, z in rink_outline()], fill=(10, 16, 28))
    em = Image.new("RGB", (w, h), (0, 0, 0))                       # leuchtende Markierungen
    e = ImageDraw.Draw(em)
    red, blue = (255, 40, 60), (40, 130, 255)

    def band(x, width, col):
        e.rectangle([P(x - width / 2, -42.5)[0], P(0, -42.5)[1], P(x + width / 2, 42.5)[0], P(0, 42.5)[1]], fill=col)

    def circle(cx, cz, r, col, width):
        x0, y0 = P(cx - r, cz - r)
        x1, y1 = P(cx + r, cz + r)
        e.ellipse([x0, y0, x1, y1], outline=col, width=int(width * PPF * ss))

    def dot(cx, cz, r, col):
        x0, y0 = P(cx - r, cz - r)
        x1, y1 = P(cx + r, cz + r)
        e.ellipse([x0, y0, x1, y1], fill=tuple(int(v * 0.45) for v in col))

    band(0, 1.0, red)
    for sx in (-1, 1):
        band(sx * 25, 1.0, blue)
        band(sx * 89, 0.25, red)
        for sz in (-1, 1):
            circle(sx * 69, sz * 22, 15, red, 0.25)
            dot(sx * 69, sz * 22, 1.0, red)
            dot(sx * 20, sz * 22, 1.0, red)
        # Torraum (Halbkreis 6 ft, vereinfacht) + Trapez
        poly = [P(sx * (89 - 6 * math.cos(math.radians(a))), 6 * math.sin(math.radians(a))) for a in np.linspace(-90, 90, 30)]
        d.polygon(poly, fill=(14, 42, 80))
        e.line(poly, fill=red, width=int(0.25 * PPF * ss))
        e.line([P(sx * 89, -11), P(sx * 100, -14)], fill=red, width=int(0.25 * PPF * ss))
        e.line([P(sx * 89, 11), P(sx * 100, 14)], fill=red, width=int(0.25 * PPF * ss))
    circle(0, 0, 15, blue, 0.25)
    dot(0, 0, 0.6, blue)
    # Bandenrand (innen) als weiße Lichtkante
    e.line([P(x, z) for x, z in rink_outline(inset=0.3)] + [P(*rink_outline(inset=0.3)[0])], fill=(200, 220, 255),
           width=int(0.5 * PPF * ss))
    base = base.resize((TEX_W, TEX_H), Image.LANCZOS)
    em = em.resize((TEX_W, TEX_H), Image.LANCZOS)
    b = np.asarray(base, np.float32) / 255
    m = np.asarray(em, np.float32) / 255
    # Eis: feine Kratzer + Rauschen
    rng = np.random.default_rng(40)
    scr = Image.new("L", (TEX_W, TEX_H), 0)
    sd = ImageDraw.Draw(scr)
    for _ in range(1400):
        x, y = rng.uniform(0, TEX_W), rng.uniform(0, TEX_H)
        a = rng.uniform(0, math.pi)
        ln = rng.uniform(20, 160)
        sd.arc([x - ln, y - ln * 0.4, x + ln, y + ln * 0.4], math.degrees(a), math.degrees(a) + rng.uniform(20, 80),
               fill=int(rng.uniform(20, 70)), width=1)
    s = np.asarray(scr, np.float32)[..., None] / 255
    b = b + s * np.array([0.05, 0.07, 0.10], np.float32) + rng.normal(0, 0.006, b.shape[:2])[..., None].astype(np.float32)
    g1 = cv2.GaussianBlur(m, (0, 0), 5)
    g2 = cv2.GaussianBlur(m, (0, 0), 18)
    tex = b + m * 1.35 + g1 * 0.9 + g2 * 0.45
    _TEX["tex"] = tex.astype(np.float32)
    return _TEX["tex"]


def render_floor(cam, tint):
    tex = rink_texture()
    Hm = cam.floor_h(TX0, TZ0, PPF)
    img = cv2.warpPerspective(tex, Hm, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                              borderValue=(0, 0, 0))
    depth = cam.floor_rows()
    vis = (depth > 0).astype(np.float32)
    fog = np.exp(-np.clip(depth, 0, None) / 140.0) * vis
    # glänzendes Eis: Lichtband am Horizont + Szenen-Tönung
    img *= fog[:, None, None].astype(np.float32)
    sheen = (np.exp(-np.clip(depth, 0, None) / 60.0) * 0 + np.exp(-((depth - 120) / 70.0) ** 2) * 0.10) * vis
    img += sheen[:, None, None].astype(np.float32) * np.array(tint, np.float32)
    return img, depth


# ================================================================= Arena: Banden, Glas, Tribünenlichter, Tor
OUT = rink_outline(12)
_STANDS = {}


def stands():
    if "p" in _STANDS:
        return _STANDS["p"]
    rng = np.random.default_rng(7)
    pts, cols, ph, sz = [], [], [], []
    base = np.array(rink_outline(10))
    cen = base.mean(0)
    for k in range(1600):
        i = rng.integers(0, len(base))
        p = base[i]
        n = p - cen
        n = n / np.linalg.norm(n)
        d = rng.uniform(8, 70)
        q = p + n * d
        y = 7 + d * 0.62 + rng.uniform(-1, 1)
        pts.append((q[0], y, q[1]))
        warm = rng.random() < 0.8
        cols.append((1.0, 0.86, 0.70) if warm else ((0.6, 0.8, 1.0) if rng.random() < 0.5 else (1.0, 0.5, 0.5)))
        ph.append(rng.uniform(0, 6.28))
        sz.append(rng.uniform(0.5, 1.4))
    # Dachstrahler
    roof = [(x, 92.0, z) for x in (-75, -45, -15, 15, 45, 75) for z in (-34, 34)]
    _STANDS["p"] = (np.array(pts), np.array(cols, np.float32), np.array(ph), np.array(sz), np.array(roof))
    return _STANDS["p"]


_DOTS = {}


def glow_dot(r):
    r = max(1, min(14, int(round(r))))
    if r not in _DOTS:
        R = r * 4 + 2
        yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
        d = np.sqrt(xx ** 2 + yy ** 2)
        core = np.clip(r * 0.6 + 0.5 - d, 0, 1)
        halo = np.exp(-(d / (r * 1.6)) ** 2) * 0.35
        _DOTS[r] = ((core + halo)[..., None], R)
    return _DOTS[r]


def draw_stands(img, cam, t, tint, amount=1.0):
    pts, cols, ph, sz, roof = stands()
    xy, z = cam.proj(pts)
    ok = (z > 2) & (xy[:, 0] > -20) & (xy[:, 0] < W + 20) & (xy[:, 1] > -20) & (xy[:, 1] < H + 20)
    flick = 0.55 + 0.45 * np.sin(t * 3.1 + ph * 3)
    flash = (np.sin(t * 9.0 + ph * 17) > 0.985).astype(np.float32) * 2.5          # Handy-/Kamerablitze
    for i in np.nonzero(ok)[0]:
        r = sz[i] * 520 / z[i]
        if r < 0.6:
            continue
        spr, R = glow_dot(r)
        a = (flick[i] * 0.5 + flash[i]) * amount
        col = cols[i] * 0.55 + np.array(tint, np.float32) * 0.45
        M.blit_add(img, spr * col, xy[i, 0] - R, xy[i, 1] - R, a)
    return img


def board_lines(cam):
    """(Polylinien, Farbe, Breite, Helligkeit) der Bande (oben/unten) und der Glaskante."""
    base = [(x, z) for x, z in OUT]
    out = []
    for y, col, wd, a in ((3.5, (235, 240, 255), 3.0, 0.95), (0.6, (255, 205, 60), 2.0, 0.55), (9.0, (140, 190, 255), 1.6, 0.35)):
        P = [(x, y, z) for x, z in base]
        for seg in clip_lines(cam, P, closed=True):
            out.append((seg, col, wd, a))
    return out


def goal_lines(cam, sx=1.0):
    """Neon-Tor an der Torlinie x = sx*89 (Rahmen rot, Netz weiß)."""
    gx = 89.0 * sx
    frame = []
    post = [(gx, 0, -3), (gx, 4, -3), (gx, 4, 3), (gx, 0, 3)]
    frame.append(post)
    base = [(gx + sx * 3.3 * math.sin(a), 0.0, -3 * math.cos(a)) for a in np.linspace(0, math.pi, 24)]
    frame.append(base)
    top = [(gx + sx * 1.6 * math.sin(a), 4.0 - 0.1 * math.sin(a), -2.9 * math.cos(a)) for a in np.linspace(0, math.pi, 18)]
    net = []
    for k in range(13):                                            # Netz: Streben zwischen Oberkante und Boden
        a = math.pi * k / 12
        p0 = (gx + sx * 1.6 * math.sin(a), 4.0, -2.9 * math.cos(a))
        p1 = (gx + sx * 3.3 * math.sin(a), 0.0, -3 * math.cos(a))
        net.append([p0, ((p0[0] + p1[0]) / 2 + sx * 0.5, 2.0, (p0[2] + p1[2]) / 2), p1])
    for y in (1.0, 2.0, 3.0):
        f = y / 4
        net.append([(gx + sx * (3.3 * (1 - f) + 1.6 * f + 0.4 * math.sin(math.pi * f)) * math.sin(a), y,
                     -(3 * (1 - f) + 2.9 * f) * math.cos(a)) for a in np.linspace(0, math.pi, 18)])
    net.append(top)
    out = []
    for P in frame:
        for seg in clip_lines(cam, P):
            out.append((seg, (255, 50, 60), 7.0, 1.0))
    for P in net:
        for seg in clip_lines(cam, P):
            out.append((seg, (225, 235, 255), 1.6, 0.45))
    return out


def stroke_layer(lines, glow=True):
    """Linien auf eine cairo-Fläche -> (rgb float, alpha) + optional Glow."""
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    c = cairo.Context(s)
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    for seg, col, wd, a in lines:
        c.set_source_rgba(col[0] / 255, col[1] / 255, col[2] / 255, a)
        c.set_line_width(wd)
        c.move_to(*seg[0])
        for p in seg[1:]:
            c.line_to(*p)
        c.stroke()
    s.flush()
    buf = np.frombuffer(s.get_data(), np.uint8).reshape(H, W, 4).astype(np.float32) / 255
    rgb = buf[..., [2, 1, 0]]
    return rgb


def add_glow(img, rgb, k1=0.9, k2=0.5):
    small = cv2.resize(rgb, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    g1 = cv2.resize(cv2.GaussianBlur(small, (0, 0), 2.0), (W, H), interpolation=cv2.INTER_LINEAR)
    g2 = cv2.resize(cv2.GaussianBlur(small, (0, 0), 7.0), (W, H), interpolation=cv2.INTER_LINEAR)
    return img + rgb + g1 * k1 + g2 * k2


# ================================================================= Lichtkegel
_BEAM = {}


def beam_spr():
    if "b" not in _BEAM:
        w, h = 520, 2100
        im = Image.new("L", (w, h), 0)
        ImageDraw.Draw(im).polygon([(w / 2 - 22, 0), (w / 2 + 22, 0), (w, h), (0, h)], fill=255)
        m = cv2.GaussianBlur(np.asarray(im, np.float32) / 255, (0, 0), 28)
        fall = np.linspace(1.0, 0.0, h, dtype=np.float32)[:, None] ** 1.4
        _BEAM["b"] = (m * fall)[..., None]
    return _BEAM["b"]


def beams(img, t, tint, k=1.0):
    b = beam_spr()
    h, w = b.shape[:2]
    for i, (x0, sp, ph) in enumerate(((180, 0.6, 0.0), (540, 0.45, 2.0), (900, 0.55, 4.1))):
        ang = 13 * math.sin(t * sp + ph)
        rot = cv2.warpAffine(b, cv2.getRotationMatrix2D((w / 2, 0), ang, 1.0), (w, h))
        a = (0.10 + 0.04 * math.sin(t * 1.7 + ph)) * k
        M.blit_add(img, rot[..., None] * np.array(tint, np.float32), x0 - w / 2, -60, a)
    return img


# ================================================================= Licht pro Szene
# (Key-Licht-Farbe, Rim-Farbe, Tönung der Umgebung)
LOOK = [
    dict(key=(1.0, 0.95, 0.9), rim=(0.55, 0.8, 1.0), tint=(0.55, 0.75, 1.0), grade=(1.0, 1.0, 1.05)),
    dict(key=(1.0, 0.55, 0.55), rim=(1.0, 0.35, 0.45), tint=(1.0, 0.35, 0.4), grade=(1.12, 0.86, 0.9)),
    dict(key=(0.6, 0.8, 1.0), rim=(0.35, 0.65, 1.0), tint=(0.35, 0.6, 1.0), grade=(0.84, 0.96, 1.2)),
    dict(key=(1.0, 0.9, 0.7), rim=(1.0, 0.8, 0.4), tint=(1.0, 0.8, 0.45), grade=(1.06, 1.0, 0.92)),
    dict(key=(1.0, 0.9, 0.9), rim=(0.8, 0.5, 1.0), tint=(0.75, 0.5, 1.0), grade=(1.0, 0.95, 1.08)),
]


def look_at_t(t):
    i = scene(t)
    L = LOOK[i]
    for c in CUTS:                                             # weich überblenden im Whip
        if c - WHIP / 2 <= t < c + WHIP / 2:
            j = CUTS.index(c)
            s = sio((t - c + WHIP / 2) / WHIP)
            A, B = LOOK[j], LOOK[j + 1]
            return {k: tuple(a + (b - a) * s for a, b in zip(A[k], B[k])) for k in A}
    return L


# ================================================================= Puck-Figuren
PR, PHT = 0.85, 0.55                             # Figuren-Puck (ft)
LDIR = np.array([-0.5, 0.75, -0.45])
LDIR /= np.linalg.norm(LDIR)


def draw_puck(img, cam, c, lk, alpha=1.0, mirror=False):
    n = 72
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ring = np.stack([np.cos(a) * PR, np.zeros(n), np.sin(a) * PR], 1)
    yt = -PHT if mirror else PHT
    bot = c + ring
    top = c + ring + np.array([0, yt, 0])
    pb, zb = cam.proj(bot)
    pt, zt = cam.proj(top)
    if (zb < 0.6).any() or (zt < 0.6).any():
        return img
    allp = np.vstack([pb, pt])
    x0, y0 = np.floor(allp.min(0)).astype(int) - 8
    x1, y1 = np.ceil(allp.max(0)).astype(int) + 8
    if x1 < 0 or y1 < 0 or x0 >= W or y0 >= H or x1 - x0 > 1400:
        return img
    ss = 3
    pw, ph = (x1 - x0) * ss, (y1 - y0) * ss
    col = np.zeros((ph, pw, 3), np.float32)
    al = np.zeros((ph, pw), np.float32)

    def S(p):
        return np.round((np.asarray(p) - [x0, y0]) * ss * 16).astype(np.int32)

    key = np.array(lk["key"], np.float32)
    rim = np.array(lk["rim"], np.float32)
    vd = cam.pos - c
    vd /= np.linalg.norm(vd)
    for i in range(n):
        j = (i + 1) % n
        am = (a[i] + a[j]) / 2 if j else (a[i] + 2 * np.pi) / 2
        nrm = np.array([math.cos(am), 0.0, math.sin(am)])
        if np.dot(nrm, cam.pos - (c + nrm * PR)) <= 0:
            continue
        lam = max(0.0, float(np.dot(nrm, LDIR)))
        fres = (1 - abs(float(np.dot(nrm, vd)))) ** 2.2
        cc = 0.025 + key * (lam ** 1.6) * 0.42 + rim * fres * 0.95
        quad = np.array([S(pb[i]), S(pb[j]), S(pt[j]), S(pt[i])])
        cv2.fillConvexPoly(col, quad, tuple(float(v) for v in cc), lineType=cv2.LINE_AA, shift=4)
        cv2.fillConvexPoly(al, quad, 1.0, lineType=cv2.LINE_AA, shift=4)
    if (cam.pos[1] > c[1] + PHT) != mirror:                      # Deckel sichtbar
        lid = S(pt)
        cv2.fillPoly(col, [lid], (0.055, 0.058, 0.07), lineType=cv2.LINE_AA, shift=4)
        cv2.fillPoly(al, [lid], 1.0, lineType=cv2.LINE_AA, shift=4)
        hl = np.zeros((ph, pw), np.float32)
        ctr = np.mean(pt, 0)
        off = (pt[n // 8] - ctr) * 0.35
        cv2.ellipse(hl, (int((ctr[0] + off[0] - x0) * ss), int((ctr[1] + off[1] - y0) * ss)),
                    (int(np.ptp(pt[:, 0]) * ss * 0.28), int(max(2, np.ptp(pt[:, 1]) * ss * 0.22))), 0, 0, 360, 1.0, -1)
        hl = cv2.GaussianBlur(hl, (0, 0), 6 * ss / 3)
        col += hl[..., None] * key * 0.16
        cv2.polylines(col, [lid], True, tuple(float(v) for v in (0.25 + rim * 0.5)), thickness=2 * ss // 2,
                      lineType=cv2.LINE_AA, shift=4)
    col = cv2.resize(col, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA)
    al = cv2.resize(al, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA) * alpha
    if mirror:                                                   # Spiegelung: nach unten ausblenden
        fade = np.linspace(1.0, 0.0, y1 - y0, dtype=np.float32)[:, None] ** 1.5
        al *= fade * 0.32
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    sc = col[ya - y0:yb - y0, xa - x0:xb - x0]
    sa = al[ya - y0:yb - y0, xa - x0:xb - x0, None]
    img[ya:yb, xa:xb] = img[ya:yb, xa:xb] * (1 - sa) + sc * sa
    return img


def eye_anchor(cam, c):
    """Bildposition + Radius der Augen (Seite zur Kamera)."""
    d = cam.pos - c
    d[1] = 0
    d /= np.linalg.norm(d)
    r = np.cross(vec(0, 1, 0), d)
    ctr = c + d * PR * 0.96 + vec(0, PHT * 0.5, 0)
    (pl, pr_), z = cam.proj(np.array([ctr - r * 0.3, ctr + r * 0.3]))
    re = cam.f * 0.2 / max(z[0], 0.1)
    return pl, pr_, re


def eyes(ctx, cam, c, m, look, t, ph=0.0):
    pl, pr_, re = eye_anchor(cam, c)
    if pl[0] > pr_[0]:
        pl, pr_ = pr_, pl
    blink = (t + ph + 1.3) % 2.7 < 0.09 and m in ("neutral", "proud")
    for sgn, (ex, ey) in ((-1, pl), (1, pr_)):
        if m == "happy":
            ctx.set_source_rgba(1, 1, 1, 1)
            ctx.set_line_width(max(2.0, re * 0.34))
            ctx.arc(ex, ey + re * 0.35, re * 0.75, math.pi * 1.15, math.pi * 1.85)
            ctx.stroke()
            continue
        ctx.set_source_rgba(1, 1, 1, 1)
        ctx.arc(ex, ey, re, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgba(0.06, 0.06, 0.08, 1)
        ctx.set_line_width(max(1.2, re * 0.1))
        ctx.arc(ex, ey, re, 0, 2 * math.pi)
        ctx.stroke()
        if blink:
            ctx.arc(ex, ey, re * 1.02, 0, 2 * math.pi)
            ctx.fill()
            continue
        lk = np.asarray(look, float)
        if m == "sad":
            lk = np.array([0.0, 0.55])
        if m == "worried":
            lk = np.array([0.55 * math.copysign(1, math.sin(t * 6)), 0.1])
        ctx.arc(ex + lk[0] * re * 0.5, ey + lk[1] * re * 0.5, re * 0.5, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgba(1, 1, 1, 0.9)                         # Glanzpunkt
        ctx.arc(ex + lk[0] * re * 0.5 - re * 0.18, ey + lk[1] * re * 0.5 - re * 0.18, re * 0.13, 0, 2 * math.pi)
        ctx.fill()
        lid = None
        if m in ("sad", "worried"):
            lid = (0.55, 0.05) if sgn > 0 else (0.05, 0.55)
        elif m == "angry":
            lid = (0.05, 0.62) if sgn > 0 else (0.62, 0.05)
        elif m == "proud":
            lid = (0.32, 0.32)
        if lid:
            ctx.save()
            ctx.arc(ex, ey, re * 1.06, 0, 2 * math.pi)
            ctx.clip()
            ctx.set_source_rgba(0.05, 0.05, 0.06, 1)
            ctx.move_to(ex - re * 1.2, ey - re * lid[0])
            ctx.line_to(ex + re * 1.2, ey - re * lid[1])
            ctx.line_to(ex + re * 1.2, ey - re * 1.3)
            ctx.line_to(ex - re * 1.2, ey - re * 1.3)
            ctx.close_path()
            ctx.fill()
            ctx.restore()
    if m == "worried":                                            # Schweißtropfen
        q = (t * 0.9) % 1.0
        tx, ty = pr_[0] + re * 1.5, pr_[1] - re * 1.3 + q * re * 2.2
        r_ = re * 0.4
        ctx.set_source_rgba(0.4, 0.75, 1.0, 0.95 * (1 - q))
        ctx.move_to(tx, ty - r_ * 1.8)
        ctx.curve_to(tx + r_, ty - r_ * 0.4, tx + r_, ty + r_, tx, ty + r_)
        ctx.curve_to(tx - r_, ty + r_, tx - r_, ty - r_ * 0.4, tx, ty - r_ * 1.8)
        ctx.fill()


# ================================================================= Medaille, Chips, Funken
_SPR = {}


def medal_img():
    if "medal" in _SPR:
        return _SPR["medal"]
    s = 3
    w_, h_ = 200, 300
    im = Image.new("RGBA", (w_ * s, h_ * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon([(62 * s, 0), (100 * s, 0), (92 * s, 120 * s), (54 * s, 120 * s)], fill=(210, 30, 50, 255))
    d.polygon([(100 * s, 0), (138 * s, 0), (146 * s, 120 * s), (108 * s, 120 * s)], fill=(30, 90, 220, 255))
    cy = 200 * s
    for r, colr in ((96, (150, 98, 10)), (90, (226, 160, 30)), (78, (255, 206, 70)), (70, (240, 178, 40))):
        d.ellipse((100 * s - r * s, cy - r * s, 100 * s + r * s, cy + r * s), fill=colr + (255,))
    im = im.resize((w_, h_), Image.LANCZOS)
    t1 = M.text_spr("+1", "x9", 66, (120, 66, 0))
    im.alpha_composite(t1.img, (int(100 - t1.ax), int(192 - t1.ay)))
    t2 = M.text_spr("POINT", "x8", 18, (120, 66, 0), 0.12)
    im.alpha_composite(t2.img, (int(100 - t2.ax), int(240 - t2.ay)))
    arr = np.asarray(im, np.float32) / 255                       # Glanz oben links
    yy, xx = np.mgrid[0:h_, 0:w_].astype(np.float32)
    sh = np.exp(-(((xx - 70) / 40) ** 2 + ((yy - 160) / 26) ** 2)) * 0.5
    arr[..., :3] = np.clip(arr[..., :3] + sh[..., None] * arr[..., 3:4], 0, 1)
    _SPR["medal"] = M.Spr(Image.fromarray((arr * 255).astype(np.uint8), "RGBA"), 100, 200)
    return _SPR["medal"]


def chip_img(rx=118, ry=40, th=30):
    key = ("chip", rx, ry, th)
    if key in _SPR:
        return _SPR[key]
    s = 3
    w_, h_ = 2 * rx + 8, 2 * ry + th + 8
    im = Image.new("RGBA", (w_ * s, h_ * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = w_ * s / 2, (ry + 4) * s
    d.rectangle((cx - rx * s, cy, cx + rx * s, cy + th * s), fill=(176, 116, 14, 255))
    d.ellipse((cx - rx * s, cy + th * s - ry * s, cx + rx * s, cy + th * s + ry * s), fill=(150, 96, 10, 255))
    for k in range(10):                                           # Kanten-Rillen
        xx = cx - rx * s + (2 * rx * s) * (k + 0.5) / 10
        d.line((xx, cy + 4 * s, xx, cy + th * s + 2 * s), fill=(220, 160, 40, 255), width=3 * s)
    d.ellipse((cx - rx * s, cy - ry * s, cx + rx * s, cy + ry * s), fill=(255, 205, 72, 255))
    d.ellipse((cx - rx * 0.78 * s, cy - ry * 0.78 * s, cx + rx * 0.78 * s, cy + ry * 0.78 * s), outline=(200, 140, 20, 255),
              width=3 * s)
    im = im.resize((w_, h_), Image.LANCZOS)
    t1 = M.text_spr("+1", "x9", 46, (130, 76, 0))
    tim = t1.img.resize((t1.img.width, int(t1.img.height * ry / rx * 1.5)), Image.LANCZOS)
    im.alpha_composite(tim, (int(w_ / 2 - t1.ax), int(ry + 4 - t1.ay * ry / rx * 1.5)))
    _SPR[key] = M.Spr(im, w_ / 2, ry + 4)
    return _SPR[key]


def sparks(img, x, y, t, t0, n=18, col=GOLD, seed=0, spd=520, life=0.6):
    if not (t0 <= t < t0 + life):
        return
    rng = np.random.default_rng(seed)
    u = t - t0
    for k in range(n):
        a = rng.uniform(math.pi * 1.05, math.pi * 1.95) if spd > 0 else rng.uniform(0, 2 * math.pi)
        v = rng.uniform(0.4, 1.0) * abs(spd)
        px = x + math.cos(a) * v * u
        py = y + math.sin(a) * v * u + 900 * u * u
        spr, R = glow_dot(2.4 * (1 - u / life) + 1)
        M.blit_add(img, spr * (np.array(col, np.float32) / 255), px - R, py - R, 1.4 * (1 - u / life))


# ================================================================= Glas-Karten
ROWS = {
    "nhl": [("WIN", "2"), ("OVERTIME / SHOOTOUT LOSS", "1"), ("REGULATION LOSS", "0")],
    "eu": [("REGULATION WIN", "3"), ("OVERTIME / SHOOTOUT WIN", "2"), ("OVERTIME / SHOOTOUT LOSS", "1"),
           ("REGULATION LOSS", "0")],
}
CARD_W = 940
ROW_H = 112


def card_base(kind):
    key = ("cardbase", kind)
    if key in _SPR:
        return _SPR[key]
    rows = ROWS[kind]
    h_ = 132 + ROW_H * len(rows) + 26
    s = 2
    im = Image.new("RGBA", (CARD_W * s, h_ * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, CARD_W * s - 1, h_ * s - 1), 38 * s, fill=(12, 14, 22, 150))
    head = Image.new("RGBA", (CARD_W * s, 104 * s), (0, 0, 0, 0))
    g = np.zeros((104 * s, CARD_W * s, 4), np.uint8)
    c0, c1 = ((230, 30, 60), (150, 20, 120)) if kind == "nhl" else ((30, 110, 255), (20, 200, 230))
    xs = np.linspace(0, 1, CARD_W * s)[None, :, None]
    g[..., :3] = (np.array(c0) * (1 - xs) + np.array(c1) * xs).astype(np.uint8)
    g[..., 3] = 235
    head = Image.fromarray(g, "RGBA")
    mask = Image.new("L", (CARD_W * s, h_ * s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, CARD_W * s - 1, h_ * s - 1), 38 * s, fill=255)
    hm = mask.crop((0, 0, CARD_W * s, 104 * s))
    im.paste(head, (0, 0), hm)
    for i in range(1, len(rows)):
        y = (132 + ROW_H * i - 6) * s
        d.line((40 * s, y, (CARD_W - 40) * s, y), fill=(255, 255, 255, 40), width=2 * s)
    d.rounded_rectangle((0, 0, CARD_W * s - 1, h_ * s - 1), 38 * s, outline=(255, 255, 255, 90), width=3 * s)
    im = im.resize((CARD_W, h_), Image.LANCZOS)
    title = "NHL" if kind == "nhl" else "SWEDEN · FINLAND · GERMANY"
    tt = M.text_spr(title, "x9", 46 if kind == "nhl" else 36, WHITE, 0.08)
    im.alpha_composite(tt.img, (int(CARD_W / 2 - tt.ax), int(52 - tt.ay)))
    cov = mask.resize((CARD_W, h_), Image.LANCZOS)
    _SPR[key] = (im, cov)
    return _SPR[key]


def card_frame(kind, t, row_t, val_t, hi):
    """Karteninhalt zur Zeit t: Zeilen erscheinen (row_t), Werte rollen ein (val_t), Hervorhebung hi=(Zeile, Zeit)."""
    base, cov = card_base(kind)
    im = base.copy()
    for i, (lab, val) in enumerate(ROWS[kind]):
        if t < row_t[i]:
            continue
        p = e_out(c01((t - row_t[i]) / 0.28), 3)
        yc = 132 + ROW_H * i + ROW_H / 2 - 12
        if hi and hi[0] == i and t >= hi[1]:                        # Hervorhebungs-Balken
            q = e_out(c01((t - hi[1]) / 0.3), 3)
            bw = int((CARD_W - 40) * q) + 1
            g = np.zeros((ROW_H - 14, bw, 4), np.uint8)
            g[..., :3] = ORANGE if kind == "nhl" else (60, 200, 255)
            g[..., 3] = np.linspace(150, 20, bw)[None, :].astype(np.uint8)
            im.alpha_composite(Image.fromarray(g, "RGBA"), (20, int(yc - (ROW_H - 14) / 2)))
        lt = M.text_spr(lab, "x8", 34, WHITE, 0.03)
        sc = min(1.0, 640 / lt.tw)
        li = lt.img if sc >= 1 else lt.img.resize((int(lt.img.width * sc), int(lt.img.height * sc)), Image.LANCZOS)
        li = li.copy()
        li.putalpha(li.getchannel("A").point(lambda v: int(v * p)))
        im.alpha_composite(li, (int(50 + (1 - p) * 60 - (lt.ax - lt.tw / 2) * sc), int(yc - lt.ay * sc)))
        vx = CARD_W - 92
        if t >= val_t[i]:                                          # Wert rollt von unten ein
            q = e_out(c01((t - val_t[i]) / 0.22), 3)
            colv = {"3": GREEN, "2": WHITE, "1": ORANGE, "0": RED}[val]
            vt = M.text_spr(val, "x9", 104, colv)
            pop = 1.0 + 0.35 * math.sin(math.pi * c01((t - val_t[i]) / 0.3)) if (hi and hi[0] == i) else 1.0
            vi = vt.img if abs(pop - 1) < 0.01 else vt.img.resize((int(vt.img.width * pop), int(vt.img.height * pop)), Image.LANCZOS)
            row = Image.new("RGBA", (vi.width, ROW_H + 40), (0, 0, 0, 0))
            oy = int((ROW_H + 40) / 2 - vt.ay * pop + (1 - q) * ROW_H * 0.85)
            put(row, vi, 0, oy)
            im.alpha_composite(row, (int(vx - vt.ax * pop), int(yc - (ROW_H + 40) / 2)))
        elif t >= row_t[i] + 0.12:                                 # Platzhalter "?"
            qm = M.text_spr("?", "x9", 84, (120, 125, 140))
            im.alpha_composite(qm.img, (int(vx - qm.ax), int(yc - qm.ay)))
    return im, cov


def glass_card(img, blur, kind, t, t_in, t_out, row_t, val_t, hi, cy=900):
    if not (t_in <= t < t_out + 0.25):
        return img
    p = e_out(c01((t - t_in) / 0.45), 3)
    q = e_in(c01((t - t_out) / 0.25), 2)
    yaw = (1 - p) * 72 - q * 60 + 5 * math.sin(t * 1.3)
    pitch = 6 * math.sin(t * 0.9 + 1) + (1 - p) * 12
    content, cov = card_frame(kind, t, row_t, val_t, hi)
    s = 0.92 + 0.08 * p
    im_c, (ax, ay) = M.tilt(content.resize((int(content.width * s), int(content.height * s)), Image.BICUBIC), yaw, pitch)
    im_m, _ = M.tilt(cov.convert("RGBA").resize((int(cov.width * s), int(cov.height * s)), Image.BICUBIC), yaw, pitch)
    a = p * (1 - q)
    x0, y0 = int(W / 2 - ax), int(cy - ay)
    m = np.asarray(im_m, np.float32)[..., 0] / 255 * a
    hh, ww = m.shape
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + ww), min(H, y0 + hh)
    if xb > xa and yb > ya:
        mm = m[ya - y0:yb - y0, xa - x0:xb - x0, None]
        img[ya:yb, xa:xb] = img[ya:yb, xa:xb] * (1 - mm * 0.9) + (blur[ya:yb, xa:xb] * 0.55 + 0.02) * mm * 0.9
    arr = M.to_spr(im_c)
    M.blit(img, arr, x0, y0, a)
    # Lichtkante, die über die Karte wandert
    sw = ((t - t_in) * 0.9) % 2.2 - 0.6
    if 0 <= sw <= 1 and a > 0.5:
        yy, xx = np.mgrid[0:hh, 0:ww].astype(np.float32)
        band = np.exp(-(((xx / ww - sw) + (yy / hh) * 0.35) / 0.05) ** 2) * 0.22 * m
        sub = img[max(0, y0):max(0, y0) + hh, max(0, x0):max(0, x0) + ww]
        b = band[max(0, -y0):max(0, -y0) + sub.shape[0], max(0, -x0):max(0, -x0) + sub.shape[1]]
        sub += b[..., None]
    return img


# ================================================================= Projektion aufs Eis
def floor_project(img, cam, spr_img, center, width_ft, intensity, reveal=1.0, t=0.0):
    """RGBA-Bild (PIL) flach aufs Eis legen, lesbar aus Kamerasicht, additiv mit Glow."""
    if intensity <= 0.01:
        return img
    f = cam.fwd.copy()
    f[1] = 0
    f /= np.linalg.norm(f)
    rgt = np.array([-f[2], 0, f[0]])
    w_, h_ = spr_img.size
    s = width_ft / w_
    O = np.asarray(center, float)
    # Textpixel (px, py) -> Welt (x, z): O + (px - w/2) s * rgt + (py - h/2) s * (-f)
    A = np.array([[s * rgt[0], -s * f[0], O[0] - s * (w_ / 2) * rgt[0] + s * (h_ / 2) * f[0]],
                  [s * rgt[2], -s * f[2], O[2] - s * (w_ / 2) * rgt[2] + s * (h_ / 2) * f[2]],
                  [0, 0, 1.0]])
    Hw = cam.floor_h(0.0, 0.0, 1.0)
    Ht = Hw @ A
    arr = np.asarray(spr_img, np.float32) / 255
    rgb = arr[..., :3] * arr[..., 3:4]
    if reveal < 1:                                              # Scan-Reveal von nah nach fern
        cut = int(h_ * (1 - reveal))
        rgb[:cut] = 0
        edge = np.zeros_like(rgb[:, :, 0])
        e0 = max(0, cut - 6)
        edge[e0:cut + 6] = 1.0
        rgb += edge[..., None] * arr[..., 3:4] * 0.0 + edge[..., None] * 0.6 * (arr[..., 3:4] > 0)
    out = cv2.warpPerspective(rgb, Ht, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    flick = 0.85 + 0.15 * math.sin(t * 40) * math.sin(t * 13)
    img += out * intensity * flick
    small = cv2.resize(out, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    img += cv2.resize(cv2.GaussianBlur(small, (0, 0), 4), (W, H)) * intensity * 0.8
    return img


def proj_text(lines):
    """Mehrzeiliger Projektionstext als PIL-RGBA."""
    key = ("proj",) + tuple(lines)
    if key in _SPR:
        return _SPR[key]
    sprs = [M.text_spr(txt, "x9", size, col, 0.04) for txt, size, col in lines]
    w_ = int(max(s.img.width for s in sprs)) + 20
    h_ = int(sum(s.img.height * 0.82 for s in sprs)) + 40
    im = Image.new("RGBA", (w_, h_), (0, 0, 0, 0))
    y = 20
    for s in sprs:
        im.alpha_composite(s.img, (int(w_ / 2 - s.ax), int(y)))
        y += s.img.height * 0.82
    _SPR[key] = im
    return im


# ================================================================= Kinetic Typography
_FIT = {}


def fit_size(txt, size, maxw=1000, fk="x9", track=0.02):
    s = M.text_spr(txt, fk, size, WHITE, track)
    return size if s.tw <= maxw else int(size * maxw / s.tw)


def fit_spr(txt, size, col, maxw=1000, fk="x9", track=0.02):
    key = (txt, size, col, maxw, fk, track)
    if key not in _FIT:
        _FIT[key] = M.text_spr(txt, fk, fit_size(txt, size, maxw, fk, track), col, track)
    return _FIT[key]


_OUTL = {}


def outline_spr(txt, size, col, width=3, fk="x9", track=0.02):
    key = (txt, size, col, width, fk, track)
    if key in _OUTL:
        return _OUTL[key]
    base = M.text_spr(txt, fk, size, col, track)
    f = M.font(fk, size)
    im = Image.new("RGBA", base.img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pad = int(size * 0.35) + 4
    if track:
        x = pad
        for ch in txt:
            d.text((x, pad), ch, font=f, fill=(0, 0, 0, 0), stroke_width=width, stroke_fill=col + (255,))
            x += f.getlength(ch) + track * size
    else:
        d.text((pad, pad), txt, font=f, fill=(0, 0, 0, 0), stroke_width=width, stroke_fill=col + (255,))
    _OUTL[key] = M.Spr(im, base.ax, base.ay, base.tw)
    return _OUTL[key]


def slam(img, spr, x, y, t, t0, t1=None, s0=1.7, glow=0.0, echo=None, drift=0.0):
    """Wort knallt rein (Skalierung + Bewegungsunschärfe), optional Outline-Echo und Ausblenden."""
    if t < t0 or (t1 is not None and t >= t1 + 0.2):
        return
    p = (t - t0) / 0.17
    s = 1 + (s0 - 1) * (1 - e_out(p, 3))
    s *= 1 + 0.05 * math.sin(math.pi * c01((t - t0 - 0.17) / 0.22))
    a = c01(p * 2.2)
    yy = y
    if t1 is not None and t > t1:
        q = (t - t1) / 0.2
        a *= 1 - c01(q)
        yy = y - e_in(q, 2) * 80
    x = x + drift * (t - t0)
    if p < 1:
        for k, aa in ((1.12, 0.25), (1.05, 0.35)):
            M.draw(img, spr, x, yy, a * aa, s * k)
    M.draw(img, spr, x, yy, a, s, glow=glow)
    if echo is not None and 0 <= t - t0 < 0.55:
        u = (t - t0) / 0.55
        M.draw(img, echo, x, yy, (1 - u) * 0.7, s * (1 + 0.45 * e_out(u, 2)))


def sweep(img, spr, x, y, s, pos, k=0.55):
    """Glanzstreifen über einen Text (additiv, nur in der Textform)."""
    arr, ax, ay = spr.scaled(s)
    h, w = arr.shape[:2]
    xx = np.arange(w, dtype=np.float32)[None, :] / w
    yy = np.arange(h, dtype=np.float32)[:, None] / h
    band = np.exp(-(((xx - pos) + yy * 0.25) / 0.07) ** 2) * arr[..., 3] * k
    M.blit_add(img, band[..., None] * np.ones(3, np.float32), x - ax, y - ay, 1.0)


def kline(img, words, y, t, times, t_out=None, gap=0.28):
    """Wortweise aufgebaute, sich neu zentrierende Zeile (words = [(text, size, col)])."""
    full = sum(M.text_spr(w, "x9", sz, col, 0.02).tw for w, sz, col in words) + sum(gap * sz for _, sz, _ in words[1:])
    if full > 980:
        k = 980 / full
        words = [(w, int(sz * k), col) for w, sz, col in words]
    sprs = [fit_spr(w, sz, col) for w, sz, col in words]
    widths = [sp.tw for sp in sprs]
    gaps = [gap * words[i][1] if i else 0 for i in range(len(words))]
    vis = [e_out(c01((t - ti) / 0.3), 3) for ti in times]
    total = sum((w + g) * v for w, g, v in zip(widths, gaps, vis))
    x = W / 2 - total / 2
    for sp, w, g, v, ti, (_, sz, col) in zip(sprs, widths, gaps, vis, times, words):
        if t < ti:
            continue
        x += g * v
        p = (t - ti) / 0.22
        a = c01(p * 2)
        yy = y + (1 - e_out(p, 3)) * sz * 0.5
        if t_out is not None and t > t_out:
            q = (t - t_out) / 0.2
            a *= 1 - c01(q)
            yy -= e_in(q, 2) * sz
        M.draw(img, sp, x + w * v / 2 + (1 - v) * w * 0.3, yy, a, 1 + (1 - e_out(p, 3)) * 0.25,
               glow=0.5 if col != WHITE else 0.0)
        x += w * v


# ================================================================= HUD
def hud(img, t):
    a = 0.95
    tag = M.tag_spr("HOT TAKE", col=RED, fg=WHITE, size=26)
    M.draw(img, tag, 60, 118, a)
    if int(t * 2.5) % 2 == 0:
        M.dot(img, 60 + tag.img.width + 22, 118 + tag.img.height / 2, 7, RED, 1.0, glow=0.8)
    lab = M.text_spr("NHL  vs  EUROPE", "m7", 26, (200, 205, 220))
    M.draw(img, lab, W - 60 - lab.tw / 2, 118 + tag.img.height / 2, a)
    for i in range(5):                                             # Fortschritt pro Szene
        x0 = 60 + i * (W - 120 + 12) / 5
        wseg = (W - 120 + 12) / 5 - 12
        M.blit(img, M.solid((255, 255, 255), int(wseg), 4, 0.18), x0, 186)
        f = c01((t - SCENE_T[i]) / (SCENE_T[i + 1] - SCENE_T[i]))
        if f > 0:
            M.blit(img, M.solid((255, 255, 255), max(1, int(wseg * f)), 4, 0.9), x0, 186)
    for (cx, cy, dx, dy) in ((40, 40, 1, 1), (W - 40, 40, -1, 1), (40, H - 40, 1, -1), (W - 40, H - 40, -1, -1)):
        M.blit(img, M.solid((255, 255, 255), 46, 3, 0.5), cx if dx > 0 else cx - 46, cy if dy > 0 else cy - 3)
        M.blit(img, M.solid((255, 255, 255), 3, 46, 0.5), cx if dx > 0 else cx - 3, cy if dy > 0 else cy - 46)


_BRAND = {}


def brand(img, t):
    if "b" not in _BRAND:
        import reel33_lines_neon as N
        bi = N.brand_img("bladesandpucks_lockup_transparent.png", 250)
        _BRAND["b"] = M.Spr(bi.img, bi.img.width / 2, bi.img.height / 2)
    M.draw(img, _BRAND["b"], W / 2, 1866, 0.85)


# ================================================================= Versus (CTA)
def lightning(rng, x0, y0, x1, y1, depth=6, rough=0.32):
    pts = [(x0, y0), (x1, y1)]
    for _ in range(depth):
        new = [pts[0]]
        for (ax_, ay_), (bx, by) in zip(pts[:-1], pts[1:]):
            mx, my = (ax_ + bx) / 2, (ay_ + by) / 2
            ln = math.hypot(bx - ax_, by - ay_)
            mx += rng.normal(0, ln * rough * 0.5)
            new += [(mx, my), (bx, by)]
        pts = new
    return pts


SPLIT = ((0.0, 380.0), (float(W), 860.0))                      # Versus-Kante: oben rot (NHL), unten blau (Europa)


def versus(img, t):
    if t < T_CTA - 0.1:
        return img
    k = e_out(c01((t - T_CTA + 0.1) / 0.3), 3)
    (x0, y0), (x1, y1) = SPLIT
    yy, xx = np.mgrid[0:H:8, 0:W:8].astype(np.float32)
    edge = y0 + (xx / W) * (y1 - y0)
    m = np.clip((yy - edge) / 70 + 0.5, 0, 1)
    m = cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]
    top = np.array([1.35, 0.5, 0.58], np.float32)
    bot = np.array([0.5, 0.78, 1.38], np.float32)
    grade = top * (1 - m) + bot * m
    img[:] = img * (1 - k + k * grade)
    rng = np.random.default_rng(int(t * 15))
    pts = lightning(rng, x0 - 20, y0 - 8, x1 + 20, y1 + 8, 7, 0.22)
    branches = []
    for j in range(3):
        i0 = int(rng.integers(20, len(pts) - 20))
        px, py = pts[i0]
        branches.append(lightning(rng, px, py, px + rng.uniform(-140, 140), py + rng.uniform(-220, 220), 5, 0.3))
    s_ = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    c = cairo.Context(s_)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    fl = 0.7 + 0.3 * math.sin(t * 53) * math.sin(t * 17)
    for poly, scale in [(pts, 1.0)] + [(b_, 0.45) for b_ in branches]:
        for wd, col, a in ((16, (0.75, 0.45, 1.0), 0.22), (6, (0.85, 0.8, 1.0), 0.65), (2.2, (1, 1, 1), 1.0)):
            c.set_source_rgba(col[0], col[1], col[2], a * k * fl * scale)
            c.set_line_width(wd * (0.6 + 0.4 * scale))
            c.move_to(*poly[0])
            for p in poly[1:]:
                c.line_to(*p)
            c.stroke()
    s_.flush()
    buf = np.frombuffer(s_.get_data(), np.uint8).reshape(H, W, 4).astype(np.float32) / 255
    return add_glow(img, buf[..., [2, 1, 0]], 1.3, 0.9)


def vs_badge(img, t):
    if t < wt("cta", 2) - 0.1:
        return
    p = (t - wt("cta", 2) + 0.1) / 0.25
    s = (1 + 0.9 * (1 - e_out(p, 3))) * (1 + 0.04 * math.sin(t * 9))
    key = "vsb"
    if key not in _SPR:
        ss = 3
        R = 92
        im = Image.new("RGBA", (2 * R * ss + 8, 2 * R * ss + 8), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        c = R * ss + 4
        d.ellipse((c - R * ss, c - R * ss, c + R * ss, c + R * ss), fill=(18, 18, 26, 255))
        d.ellipse((c - R * ss, c - R * ss, c + R * ss, c + R * ss), outline=(255, 255, 255, 255), width=6 * ss)
        d.ellipse((c - (R - 14) * ss, c - (R - 14) * ss, c + (R - 14) * ss, c + (R - 14) * ss), outline=(255, 196, 64, 255),
                  width=3 * ss)
        im = im.resize((2 * R + 3, 2 * R + 3), Image.LANCZOS)
        tv = M.text_spr("VS", "x9", 74, WHITE)
        im.alpha_composite(tv.img, (int(im.width / 2 - tv.ax), int(im.height / 2 - tv.ay)))
        _SPR[key] = M.Spr(im, im.width / 2, im.height / 2)
    M.draw(img, _SPR[key], 540, 620, c01(p * 2), s, glow=0.6)


# ================================================================= Chip-Stapel (Pointe)
STACKS = [  # (x, Anzahl, Landezeiten, Label, Unterlabel, Zahl-Zeit, Farbe)
    (270, 2, [T_TWO - 0.42, T_TWO - 0.26], "REGULATION", "60 MINUTES", T_TWO, WHITE),
    (810, 3, [T_THREE - 0.5, T_THREE - 0.34, T_THREE - 0.18], "OVERTIME", "OT / SHOOTOUT", T_THREE, GOLD),
]
STACK_Y = 1330


def chip_stacks(img, t):
    if not (VO_START["twist"] - 0.1 <= t < T_CTA + 0.1):
        return
    out = 1 - smooth(T_CTA - 0.3, T_CTA - 0.05, t)
    if out <= 0:
        return
    chip = chip_img()
    for x, n, lands, lab, sub, tn, col in STACKS:
        la = c01((t - VO_START["twist"] - 0.25) / 0.25) * out
        ls = fit_spr(lab, 46, WHITE, 470, "x8", 0.06)
        M.draw(img, ls, x, STACK_Y + 120, la)
        ss_ = M.text_spr(sub, "m7", 26, (170, 178, 196))
        M.draw(img, ss_, x, STACK_Y + 172, la)
        # Sockel-Ring
        M.ring(img, x, STACK_Y + 34, 120, 3, (255, 255, 255), 0.35 * la)
        for i in range(n):
            tl = lands[i]
            if t < tl - 0.35:
                continue
            u = c01((t - tl + 0.35) / 0.35)
            yt = STACK_Y - i * 32
            y = yt - 1100 * (1 - u) ** 2
            if t > tl:
                y = yt - 26 * abs(math.sin(math.pi * c01((t - tl) / 0.16))) * (1 - c01((t - tl) / 0.3))
            M.draw(img, chip, x, y, out)
            sparks(img, x, yt + 10, t, tl, 16, GOLD, seed=int(x + i * 7), spd=620, life=0.55)
        if t >= tn:
            big = fit_spr(f"{n} PTS", 100, col, 440)
            slam(img, big, x, STACK_Y - 300, t, tn, None, 1.6, glow=0.9 if col == GOLD else 0.4,
                 echo=outline_spr(f"{n} PTS", fit_size(f"{n} PTS", 100, 440), col, 3))


# ================================================================= Bild
def pos_a(t):
    i = scene(t)
    if i == 0:
        u = c01((t - T_SHOT) / (T_GOAL - T_SHOT + 0.18))
        s = 1 - (1 - u) ** 2.4
        p0, p1 = vec(80.0, 0, 4.0), vec(90.6, 0, 0.6)
        return p0 + (p1 - p0) * s
    if i == 4:
        return vec(3.0, 0, -9.0)
    return None


def pos_b(t):
    i = scene(t)
    if i == 0:
        p = vec(84.5, 0, -2.2)
        if T_LAND <= t < T_LAND + 0.9:
            u = (t - T_LAND - 0.08) / 0.3
            if u > 0:
                p[1] = 1.1 * abs(math.sin(math.pi * u)) * (0.55 ** int(u))
        return p
    if i == 1:
        return vec(13.2, 0, -19.8)
    if i == 2:
        return vec(-13.2, 0, 20.0)
    if i == 4:
        return vec(-3.0, 0, -9.0)
    return None


def mood_a(t):
    if T_GOAL <= t < T_GOAL + 1.2:
        return "happy"
    if t >= T_CTA - 0.1:
        return "angry"
    return "neutral"


def mood_b(t):
    if t < T_GOAL:
        return "neutral"
    if t < T_LAND:
        return "sad"
    if t < T_LAND + 0.9:
        return "happy"
    if scene(t) == 2:
        return "worried"
    if t >= T_CTA - 0.1:
        return "angry"
    return "proud"


def look_vec(cam, src, dst):
    a, _ = cam.proj(src)
    b, _ = cam.proj(dst)
    d = (b - a)[0]
    n = np.linalg.norm(d)
    return d / n * 0.6 if n > 1 else np.zeros(2)


# ================================================================= Staub/Partikel (Bildraum)
_rngp = np.random.default_rng(404)
DUST = [dict(x=float(_rngp.uniform(0, W)), y=float(_rngp.uniform(0, H)), z=float(_rngp.uniform(0.3, 1.0)),
             ph=float(_rngp.uniform(0, 6.28))) for _ in range(70)]


def particles(img, t, cam, tint):
    yaw = math.atan2(cam.fwd[0], cam.fwd[2])
    for d in DUST:
        x = (d["x"] - yaw * 900 * d["z"] + 14 * math.sin(t * 0.7 + d["ph"])) % (W + 100) - 50
        y = (d["y"] - t * 40 * d["z"] + 10 * math.cos(t * 0.5 + d["ph"])) % (H + 100) - 50
        spr, R = glow_dot(1 + 3.5 * d["z"])
        a = (0.10 + 0.25 * d["z"]) * (0.6 + 0.4 * math.sin(t * 2 + d["ph"]))
        M.blit_add(img, spr * np.array(tint, np.float32), x - R, y - R, a)


# ================================================================= Bild
_POST = {}


def bottom_shade():
    if "b" not in _POST:
        y = np.arange(H, dtype=np.float32)
        _POST["b"] = (1 - 0.55 * np.clip((y - 1560) / 300, 0, 1) ** 1.3)[:, None, None].astype(np.float32)
    return _POST["b"]


def vignette():
    if "v" not in _POST:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = ((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H * 0.48) / (H * 0.62)) ** 2
        _POST["v"] = np.clip(1 - 0.5 * r, 0.35, 1)[..., None].astype(np.float32)
    return _POST["v"]


def motion_blur(img, dx, dy):
    L = math.hypot(dx, dy)
    if L < 6:
        return img
    sm = cv2.resize(img, (W // 2, H // 2), interpolation=cv2.INTER_AREA)
    n = int(min(90, L / 2)) | 1
    k = np.zeros((n, n), np.float32)
    ang = math.atan2(dy, dx)
    c = n // 2
    for i in range(n):
        u = i - c
        x, y = int(round(c + u * math.cos(ang))), int(round(c + u * math.sin(ang)))
        k[y, x] = 1
    k /= k.sum()
    sm = cv2.filter2D(sm, -1, k)
    return cv2.resize(sm, (W, H), interpolation=cv2.INTER_LINEAR)


def blur_bg(img):
    sm = cv2.resize(img, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    return cv2.resize(cv2.GaussianBlur(sm, (0, 0), 6), (W, H), interpolation=cv2.INTER_LINEAR)


def tag(img, txt, col, x, y, a, s=1.0, fg=WHITE, size=26):
    if a <= 0.01:
        return
    sp = M.tag_spr(txt, col=col, fg=fg, size=size)
    M.draw(img, sp, x - sp.img.width * s / 2, y - sp.img.height * s / 2, a, s)


def hook_text(img, t):
    if t >= CUTS[0] + 0.05:
        return
    out = smooth(CUTS[0] - 0.2, CUTS[0] + 0.02, t)
    a = 1 - out
    dy = -out * 120
    l1 = fit_spr("IN THE NHL, YOU GET", 84, WHITE, 980)
    l2 = fit_spr("A POINT", 168, WHITE, 980)
    l3 = fit_spr("FOR LOSING.", 150, RED, 1000)
    s0 = 1.0 + 0.02 * t
    M.draw(img, l1, W / 2, 290 + dy, a, s0)
    M.draw(img, l2, W / 2, 420 + dy, a, s0, glow=0.25)
    pk = 1 + 0.16 * math.sin(math.pi * c01((t - T_LOSE) / 0.3)) if t >= T_LOSE else 1.0
    M.draw(img, l3, W / 2, 575 + dy, a, s0 * pk, glow=0.9 if t >= T_LOSE else 0.45)
    if 0.25 <= t <= 1.25:
        sweep(img, l2, W / 2, 420 + dy, s0, (t - 0.25) / 0.8 * 1.4 - 0.2)
    if T_LOSE <= t <= T_LOSE + 0.6:
        sweep(img, l3, W / 2, 575 + dy, s0 * pk, (t - T_LOSE) / 0.6 * 1.4 - 0.2, 0.8)
    if T_GOAL <= t < CUTS[0]:
        sp = fit_spr("OVERTIME GOAL", 54, WHITE, 700, "x8", 0.08)
        slam(img, sp, W / 2, 700 + dy, t, T_GOAL, None, 1.9, glow=0.0)
        M.blit(img, M.solid(RED, int(sp.tw + 60), 6, 1.0), W / 2 - (sp.tw + 60) / 2, 735 + dy, a * c01((t - T_GOAL) / 0.2))


def scene_texts(img, t):
    # NHL
    if CUTS[0] - 0.05 <= t < CUTS[1] + 0.2:
        b = VO_START["nhl"]
        kline(img, [("THE", 84, WHITE), ("NHL", 84, RED), ("WAY", 84, WHITE)], 330, t, [b - 0.05, b + 0.05, b + 0.15],
              CUTS[1] - 0.15)
    if CUTS[1] - 0.05 <= t < CUTS[2] + 0.2:
        b = VO_START["eu"]
        kline(img, [("THE", 80, WHITE), ("EUROPEAN", 80, BLUE), ("WAY", 80, WHITE)], 330, t,
              [b - 0.05, b + 0.05, b + 0.15], CUTS[2] - 0.15)
    if CUTS[2] - 0.05 <= t < CUTS[3] + 0.2:
        b = VO_START["twist"]
        kline(img, [("NOT", 90, WHITE), ("ALL", 90, WHITE), ("GAMES", 90, WHITE)], 330, t, [b, b + 0.1, b + 0.2],
              CUTS[3] - 0.15)
        kline(img, [("ARE", 90, WHITE), ("EQUAL.", 90, GOLD)], 450, t, [b + 0.4, b + 0.55], CUTS[3] - 0.15)
    # CTA
    if t >= T_CTA - 0.1:
        nhl = fit_spr("NHL", 220, WHITE, 560)
        slam(img, nhl, 330, 300, t, T_CTA - 0.05, None, 1.8, glow=0.6,
             echo=outline_spr("NHL", fit_size("NHL", 220, 560), RED, 4))
        eu = fit_spr("EUROPE", 150, WHITE, 640)
        slam(img, eu, 730, 820, t, wt("cta", 3) - 0.05, None, 1.8, glow=0.6,
             echo=outline_spr("EUROPE", fit_size("EUROPE", 150, 640), BLUE, 4))
        q = fit_spr("WHICH IS FAIRER?", 80, WHITE, 980)
        slam(img, q, W / 2, 1000, t, wt("cta", 4) - 0.05, None, 1.5, glow=0.2)
        if t >= wt("cta", 6) + 0.1:
            a = c01((t - wt("cta", 6) - 0.1) / 0.2)
            sp = fit_spr("COMMENT BELOW", 46, GOLD, 700, "x8", 0.1)
            bob = 8 * math.sin(t * 9)
            M.draw(img, sp, W / 2, 1092 + bob, a, glow=0.4)


def draw_cards(img, t):
    if not (CUTS[0] <= t < CUTS[2] + 0.3):
        return img
    blur = blur_bg(img)
    b = VO_START["nhl"]
    img = glass_card(img, blur, "nhl", t, b + 0.05, CUTS[1] - 0.2,
                     [b + 0.12, T_OTL, T_OTL + 0.45], [T_TWO1, T_ONE, T_OTL + 0.62], (1, T_ONE), cy=880)
    e = VO_START["eu"]
    img = glass_card(img, blur, "eu", t, e + 0.05, CUTS[2] - 0.2,
                     [e + 0.2, e + 0.38, e + 0.56, e + 0.74], [T_EU3, e + 0.5, e + 0.68, e + 0.86], (0, T_EU3), cy=900)
    return img


def floor_at(cam, u, v):
    d = cam.fwd + (u - W / 2) / cam.f * cam.right - (v - H / 2) / cam.f * cam.up
    return cam.pos + d * (-cam.pos[1] / d[1])


PROJ_C = {1: floor_at(key_cam(1, 1.7), 540, 1270), 2: floor_at(key_cam(2, 1.8), 540, 1300)}


def projections(img, cam, t):
    if CUTS[0] - 0.1 <= t < CUTS[1] + 0.15:
        r = c01((t - CUTS[0]) / 0.45)
        img = floor_project(img, cam, proj_text((("NHL", 300, (255, 60, 80)), ("2 · 1 · 0", 150, (255, 230, 235)))),
                            PROJ_C[1], 15, 0.6 * (1 - smooth(CUTS[1] - 0.1, CUTS[1] + 0.1, t)), r, t)
    if CUTS[1] - 0.1 <= t < CUTS[2] + 0.15:
        r = c01((t - CUTS[1]) / 0.45)
        img = floor_project(img, cam, proj_text((("EUROPE", 260, (70, 160, 255)), ("3 · 2 · 1 · 0", 150, (230, 240, 255)))),
                            PROJ_C[2], 18, 0.6 * (1 - smooth(CUTS[2] - 0.1, CUTS[2] + 0.1, t)), r, t)
    return img


def compose(t, fidx=0):
    cam = cam_at(t)
    lk = look_at_t(t)
    tint = lk["tint"]
    img, depth = render_floor(cam, tint)
    img *= np.array(lk["grade"], np.float32)
    draw_stands(img, cam, t, tint)
    gb = 1.0 + 1.6 * math.exp(-max(0.0, t - T_GOAL) * 5) * (t >= T_GOAL)
    gl = [(seg, col, wd, min(1.0, a * gb)) for seg, col, wd, a in goal_lines(cam, 1.0)]
    lines = board_lines(cam) + gl + goal_lines(cam, -1.0)
    if T_GOAL <= t < T_GOAL + 0.7:                                   # Schockwelle auf dem Eis
        u = (t - T_GOAL) / 0.7
        rr = 1.5 + 14 * e_out(u, 2)
        ring_pts = [(90.0 + rr * math.cos(a), 0.05, 0.6 + rr * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 64)]
        for seg in clip_lines(cam, ring_pts, closed=True):
            lines.append((seg, (255, 255, 255), 6 * (1 - u) + 1, 0.9 * (1 - u)))
    if T_SHOT <= t < T_GOAL + 0.25:                                  # Leuchtspur hinter Puck A
        us = np.linspace(max(T_SHOT, t - 0.28), t, 14)
        trail = [pos_a(x) + vec(0, 0.3, 0) for x in us]
        for seg in clip_lines(cam, trail):
            lines.append((seg, (120, 255, 170), 10, 0.85 * (1 - c01((t - T_GOAL) / 0.25))))
    img = add_glow(img, stroke_layer(lines))
    img = projections(img, cam, t)
    beams(img, t, tint, 1.3)
    particles(img, t, cam, tint)
    img *= bottom_shade()
    # Whip-Pan: Bewegungsunschärfe des Hintergrunds
    wa = whip_amount(t)
    if wa > 0.02:
        c0 = cam_at(t - 1 / FPS)
        p = cam.pos + cam.fwd * 30
        a_, _ = c0.proj(p)
        b_, _ = cam.proj(p)
        d = (b_ - a_)[0]
        img = motion_blur(img, d[0] * 1.2, d[1] * 1.2)
    # Puck-Figuren
    sh_s = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    sh_c = cairo.Context(sh_s)
    pucks = []
    pa, pb = pos_a(t), pos_b(t)
    if pa is not None:
        pucks.append(("a", pa))
    if pb is not None:
        pucks.append(("b", pb))
    pucks.sort(key=lambda q: -cam.cam(q[1])[0, 2])
    def plk(who):
        if t < T_CTA - 0.1:
            return lk
        col = (1.0, 0.3, 0.38) if who == "a" else (0.3, 0.6, 1.0)
        return dict(lk, rim=col, key=tuple(0.6 + 0.4 * v for v in col))

    for who, c in pucks:
        g = vec(c[0], 0, c[2])
        img = draw_puck(img, cam, g, plk(who), mirror=True)
    for who, c in pucks:
        img = draw_puck(img, cam, c, plk(who))
    for who, c in pucks:
        other = pb if who == "a" else pa
        if who == "a":
            lv = look_vec(cam, c, other) if (t >= T_CTA - 0.1 and other is not None) else np.array([0.45, -0.1])
            eyes(sh_c, cam, c, mood_a(t), lv, t, 0.9)
        else:
            if scene(t) in (1, 2):
                lv = np.array([0.0, -0.6])
            elif other is not None:
                lv = look_vec(cam, c, other)
            else:
                lv = np.zeros(2)
            eyes(sh_c, cam, c, mood_b(t), lv, t)
    sh_s.flush()
    buf = np.frombuffer(sh_s.get_data(), np.uint8).reshape(H, W, 4).astype(np.float32) / 255
    img = img * (1 - buf[..., 3:4]) + buf[..., [2, 1, 0]]
    # Medaille: fällt auf B, hängt danach an B
    if pb is not None and t >= T_MEDAL and scene(t) in (0, 1, 2):
        top, z = cam.proj(pb + vec(0, PHT + 0.05, 0))
        sz = cam.f * 0.95 / max(z[0], 0.5) / 300
        md = medal_img()
        if t < T_LAND:
            u = c01((t - T_MEDAL) / (T_LAND - T_MEDAL))
            y = top[0, 1] - 900 * (1 - u) ** 2 - md.img.height * sz * 0.2
            M.draw(img, md, top[0, 0], y, 1.0, sz * 1.15)
        else:
            bounce = -14 * abs(math.sin(math.pi * c01((t - T_LAND) / 0.22))) * (1 - c01((t - T_LAND) / 0.4))
            M.draw(img, md, top[0, 0] + 0.35 * cam.f * 0.85 / z[0], top[0, 1] + bounce + md.img.height * sz * 0.1, 1.0, sz)
            sparks(img, top[0, 0], top[0, 1], t, T_LAND, 22, GOLD, seed=5, spd=700, life=0.7)
    # Labels über den Pucks (Hook)
    if scene(t) == 0 and pa is not None and pb is not None:
        for c, txt0, txt1, col, up in ((pa, "TEAM A", "WINS IN OT", GREEN, True), (pb, "TEAM B", "LOSES IN OT", RED, False)):
            xy, z = cam.proj(vec(c[0], 0, c[2]) + vec(0, 1.6 if up else 0.0, 0))
            y = xy[0, 1] if up else xy[0, 1] + cam.f * 0.8 / z[0] + 30
            txt = txt1 if t >= T_GOAL + 0.12 else txt0
            tag(img, txt, col if t >= T_GOAL + 0.12 else (60, 64, 80), xy[0, 0], y,
                c01(t / 0.15) * (1 - smooth(CUTS[0] - 0.2, CUTS[0], t)), 1.0, WHITE, 30)
    if t >= T_CTA - 0.1 and pa is not None and pb is not None:          # Namensschilder unter den Pucks
        for c, txt, col in ((pa, "NHL", RED), (pb, "EUROPE", BLUE)):
            xy, z = cam.proj(c)
            tag(img, txt, col, xy[0, 0], xy[0, 1] + cam.f * 0.75 / z[0] + 26, c01((t - T_CTA) / 0.25), 1.0, WHITE, 30)
    img = draw_cards(img, t)
    chip_stacks(img, t)
    img = versus(img, t)
    vs_badge(img, t)
    hook_text(img, t)
    scene_texts(img, t)
    hud(img, t)
    brand(img, t)
    # Post: Bloom, Impacts (Chromatic Aberration, Shake, Blitz), Vignette, Korn
    bright = np.clip(img - 0.78, 0, None)
    sm = cv2.resize(bright, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    img += cv2.resize(cv2.GaussianBlur(sm, (0, 0), 5), (W, H)) * 0.55 + cv2.resize(cv2.GaussianBlur(sm, (0, 0), 16), (W, H)) * 0.4
    imp = max([1 - (t - ti) / 0.28 for ti in IMPACTS if 0 <= t - ti < 0.28] + [0.0])
    ca = int(round(12 * imp ** 1.5 + 16 * wa))
    if ca > 0:
        img[..., 0] = np.roll(img[..., 0], ca, axis=1)
        img[..., 2] = np.roll(img[..., 2], -ca, axis=1)
    if imp > 0:
        rng = np.random.default_rng(int(t * 1000))
        dx, dy = rng.normal(0, 9 * imp, 2)
        Mx = np.float32([[1.0 + 0.012 * imp, 0, dx - W * 0.006 * imp], [0, 1.0 + 0.012 * imp, dy - H * 0.006 * imp]])
        img = cv2.warpAffine(img, Mx, (W, H), borderMode=cv2.BORDER_REFLECT)
        img += 0.10 * imp ** 3
    if wa > 0.35:                                                   # Glitch-Streifen im Whip-Pan
        rng = np.random.default_rng(int(t * 997))
        for _ in range(7):
            y0 = int(rng.integers(0, H - 60))
            hh = int(rng.integers(8, 70))
            img[y0:y0 + hh] = np.roll(img[y0:y0 + hh], int(rng.normal(0, 70 * wa)), axis=1)
    img *= vignette()
    img += np.random.default_rng(fidx).normal(0, 0.012, (H // 2, W // 2)).repeat(2, 0).repeat(2, 1)[..., None].astype(np.float32)
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


def preview(ts, out):
    ims = [Image.fromarray(compose(float(t), int(float(t) * FPS))) for t in ts]
    cw, ch = W // 3, H // 3
    cols = min(6, len(ims))
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * ch), (40, 40, 40))
    for i, im in enumerate(ims):
        sheet.paste(im.resize((cw, ch), Image.LANCZOS), ((i % cols) * cw, (i // cols) * ch))
    sheet.save(out, quality=88)


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "prev":
    preview(sys.argv[2].split(","), sys.argv[3])


# ================================================================= Ton
SR = 44100


def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(41)
    mus = np.zeros((n, 2))
    sfx = np.zeros((n, 2))
    B = 60 / 126

    def tt(sec):
        return np.arange(int(sec * SR)) / SR

    def put_(buf, sig, at_, vol=1.0, pan=0.0):
        st = int(round(at_ * SR))
        if st >= n or st + len(sig) <= 0:
            return
        s0 = max(0, -st)
        st = max(st, 0)
        e = min(n, st + len(sig) - s0)
        gl, gr = math.cos((pan + 1) * math.pi / 4) * 1.41, math.sin((pan + 1) * math.pi / 4) * 1.41
        buf[st:e, 0] += sig[s0: s0 + e - st] * vol * gl
        buf[st:e, 1] += sig[s0: s0 + e - st] * vol * gr

    def lp(x, k):
        c = np.cumsum(np.concatenate([np.zeros(k), x]))
        return (c[k:] - c[:-k]) / k

    def hp(x, k):
        return x - lp(x, k)

    def noise(sec):
        return rng.standard_normal(int(sec * SR))

    def kick(vol=1.0):
        x = tt(0.45)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(42 + 160 * np.exp(-x * 34)) / SR) * np.exp(-x * 7) * 3.0) * vol

    def clap(vol=1.0):
        x = tt(0.3)
        return hp(noise(0.3), 2) * (np.exp(-x * 30) + 0.5 * np.exp(-np.abs(x - 0.012) * 300)) * 0.8 * vol

    def hat(vol=0.1):
        return hp(noise(0.04), 1) * np.exp(-tt(0.04) * 150) * vol

    def sub(freq, dur):
        x = tt(dur)
        f = freq * (1 + 0.6 * np.exp(-x * 9))
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * 2.6) * np.minimum(x / 0.004, 1) * np.exp(-x * 1.1) * 0.85

    def horn(dur=1.1, vol=0.5):
        x = tt(dur)
        sig = sum(np.sign(np.sin(2 * np.pi * f * x)) * w for f, w in ((116.5, 1.0), (146.8, 0.7), (174.6, 0.5)))
        env = np.minimum(x / 0.04, 1) * np.clip((dur - x) / 0.25, 0, 1)
        return lp(sig, 6) * env * vol

    def crowd(dur=2.5, vol=0.4):
        x = tt(dur)
        sig = lp(noise(dur), 12) - lp(noise(dur), 60) * 0.6
        return sig * np.sin(np.pi * np.clip(x / dur, 0, 1)) ** 0.8 * vol * 2.0

    def clack(vol=0.7):
        x = tt(0.18)
        return (hp(noise(0.18), 2) * np.exp(-x * 70) + np.sin(2 * np.pi * 1300 * x) * np.exp(-x * 60) * 0.6) * vol

    def thud(vol=0.7):
        x = tt(0.2)
        return (lp(noise(0.2), 8) * 2.5 * np.exp(-x * 40) + np.sin(2 * np.pi * 180 * x) * np.exp(-x * 30)) * vol

    def swish(vol=0.5):
        x = tt(0.5)
        return hp(lp(noise(0.5), 3), 12) * np.exp(-x * 7) * np.minimum(x / 0.01, 1) * vol

    def whoosh(dur=0.35, vol=0.4):
        x = tt(dur)
        return hp(lp(noise(dur), 6), 40) * np.sin(np.pi * x / dur) ** 2 * vol

    def pop(vol=0.4):
        x = tt(0.12)
        return np.sin(2 * np.pi * np.cumsum(500 + 900 * np.exp(-x * 40)) / SR) * np.exp(-x * 35) * vol

    def tick(vol=0.3):
        x = tt(0.05)
        return np.sin(2 * np.pi * 2200 * x) * np.exp(-x * 120) * vol

    def buzz(dur=0.5, vol=0.5):
        x = tt(dur)
        sig = np.sign(np.sin(2 * np.pi * 110 * x)) + 0.6 * np.sign(np.sin(2 * np.pi * 116 * x))
        return lp(sig, 4) * np.minimum(x / 0.01, 1) * np.clip((dur - x) / 0.05, 0, 1) * vol

    def ding(vol=0.5):
        x = tt(0.9)
        return (np.sin(2 * np.pi * 1318.5 * x) + 0.6 * np.sin(2 * np.pi * 1975.5 * x)) * np.exp(-x * 4) * vol

    def boing(vol=0.4):
        x = tt(0.45)
        f = 220 + 260 * np.exp(-x * 9) * (1 + 0.35 * np.sin(2 * np.pi * 14 * x))
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 7) * vol

    def trombone(vol=0.5):
        """Traurige Posaune: wah wah wah waaah."""
        out = np.zeros(int(1.35 * SR))
        for j, (f0, d) in enumerate(((233.1, 0.22), (220.0, 0.22), (207.7, 0.22), (196.0, 0.55))):
            x = tt(d)
            vib = 1 + (0.025 * np.sin(2 * np.pi * 6 * x) if j == 3 else 0)
            ph_ = 2 * np.pi * np.cumsum(f0 * vib) / SR
            sig = sum(np.sin(ph_ * h) / h ** 0.9 for h in range(1, 8))
            env = np.minimum(x / 0.03, 1) * np.clip((d - x) / 0.05, 0, 1)
            st = int(sum((0.24, 0.24, 0.24)[:j]) * SR)
            out[st:st + len(x)] += lp(sig, 5) * env
        return out * vol / 3

    def blower(vol=0.4):
        x = tt(0.8)
        f = 420 + 380 * np.clip(x / 0.25, 0, 1)
        sig = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.6 + np.sin(2 * np.pi * np.cumsum(f * 2) / SR) * 0.3
        return lp(sig, 6) * np.minimum(x / 0.02, 1) * np.clip((0.8 - x) / 0.15, 0, 1) * vol

    def scrape(dur=1.05, vol=0.4):
        x = tt(dur)
        env = np.minimum(x / 0.03, 1) * (1 - x / dur) ** 1.5
        return hp(lp(noise(dur), 4), 25) * env * vol

    def riser(dur=0.45, vol=0.35):
        x = tt(dur)
        f = 300 + 3200 * (x / dur) ** 2
        return (hp(noise(dur), 2) * 0.6 + np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.25) * (x / dur) ** 2 * vol

    def glitch(vol=0.25):
        x = tt(0.12)
        return np.sign(np.sin(2 * np.pi * 1800 * x)) * (np.sin(2 * np.pi * 35 * x) > 0) * np.exp(-x * 25) * vol

    def boom(vol=0.8):
        x = tt(0.8)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(48 + 90 * np.exp(-x * 14)) / SR) * np.exp(-x * 4.5) * 3) * vol

    def crackle(dur=1.5, vol=0.25):
        x = tt(dur)
        sig = hp(noise(dur), 1) * (rng.random(len(x)) < 0.02) * 4 + hp(noise(dur), 3) * 0.15
        return sig * np.minimum(x / 0.05, 1) * np.clip((dur - x) / 0.3, 0, 1) * vol

    def clink(vol=0.35, f0=2400):
        x = tt(0.3)
        return (np.sin(2 * np.pi * f0 * x) + 0.6 * np.sin(2 * np.pi * f0 * 1.51 * x)) * np.exp(-x * 18) * vol

    roots = [55.0, 55.0, 65.41, 49.0]
    for k8 in range(int(DUR / (B / 2))):
        tb = k8 * B / 2
        b = k8 / 2
        pos = b % 4
        if tb > DUR - 0.4:
            continue
        if pos in (0.0, 2.5) or pos == 1.5:
            put_(mus, kick(0.95), tb)
        if pos in (1.0, 3.0):
            put_(mus, clap(0.8), tb)
        put_(mus, hat(0.11 if k8 % 2 == 0 else 0.07), tb, pan=0.3)
        if pos == 0.0:
            put_(mus, sub(roots[int(b // 4) % 4], 2.6 * B), tb)
    put_(sfx, scrape(0.8, 0.45), T_SHOT)
    put_(sfx, horn(1.1, 0.45), T_GOAL)
    put_(sfx, crowd(1.6, 0.35), T_GOAL)
    put_(sfx, boom(0.6), T_GOAL)
    put_(sfx, trombone(0.32), T_GOAL + 0.18)
    put_(sfx, whoosh(0.4, 0.35), T_MEDAL)
    put_(sfx, ding(0.55), T_LAND)
    put_(sfx, boing(0.3), T_LAND + 0.1)
    for c in CUTS:                                       # Whip-Pans
        put_(sfx, riser(0.42, 0.3), c - 0.45)
        put_(sfx, whoosh(0.45, 0.5), c - 0.18)
        put_(sfx, glitch(0.2), c - 0.03)
        put_(sfx, glitch(0.15), c + 0.05)
    for ti in (T_ONE, T_EU3):
        put_(sfx, boom(0.45), ti)
        put_(sfx, pop(0.35), ti)
    for x_, n_, lands, *_ in STACKS:
        for j, tl in enumerate(lands):
            put_(sfx, clink(0.4, 2200 + 260 * j), tl, pan=-0.4 if x_ < W / 2 else 0.4)
    put_(sfx, boom(0.55), T_THREE)
    put_(sfx, boom(0.45), T_TWO)
    put_(sfx, boom(0.8), T_CTA)
    put_(sfx, crackle(2.4, 0.3), T_CTA)
    put_(sfx, boom(0.5), wt("cta", 3))
    voice = np.zeros(n)
    for k in VO_KEYS:
        tmp = os.path.join(HERE, f"_vo_{k}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "voice", f"reel40_{k}.wav"),
                        "-af", f"atempo={TEMPO}", "-ar", str(SR), "-ac", "1", tmp], check=True)
        with wave.open(tmp) as w:
            v = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        os.remove(tmp)
        st = int(VO_START[k] * SR)
        e = min(n, st + len(v))
        voice[st:e] += v[: e - st]
    voice /= np.max(np.abs(voice)) + 1e-9
    k = int(0.08 * SR)
    venv = np.convolve(np.abs(voice), np.ones(k) / k, mode="same")
    duck = 1 - 0.75 * np.clip(venv / 0.06, 0, 1)
    sduck = 1 - 0.45 * np.clip(venv / 0.06, 0, 1)
    mus /= np.max(np.abs(mus)) + 1e-9
    sfx /= np.max(np.abs(sfx)) + 1e-9
    mix = mus * 0.36 * duck[:, None] + sfx * 0.55 * sduck[:, None] + voice[:, None] * 1.0
    mix = np.tanh(mix * 1.05)
    mix *= np.clip((DUR - np.arange(n) / SR) / 0.3, 0, 1)[:, None]
    mix = mix / np.max(np.abs(mix)) * 0.95
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())




def make_voice():
    P40.make_voice()


def _frame(i):
    return compose(i / FPS, i).tobytes()


def main():
    os.chdir(HERE)
    make_audio("audio_points_motion.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_points_motion.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "17",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
           "-ar", "44100", "-shortest", "-movflags", "+faststart", "reel40_motion.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    with Pool(4) as pool:
        for i, fr in enumerate(pool.imap(_frame, range(nf), chunksize=4)):
            proc.stdin.write(fr)
            if i % 30 == 0:
                print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(1.95, 9999)).save("reel40_motion_thumbnail.jpg", quality=92)
    print("fertig: reel40_motion.mp4")


def remux():
    os.chdir(HERE)
    make_audio("audio_points_motion.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "reel40_motion.mp4", "-i", "audio_points_motion.wav",
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-af",
                    "loudnorm=I=-14:TP=-1.0:LRA=9", "-ar", "44100", "-shortest", "-movflags", "+faststart",
                    "_tmp_pm.mp4"], check=True)
    os.replace("_tmp_pm.mp4", "reel40_motion.mp4")


if __name__ == "__main__" and (len(sys.argv) == 1 or sys.argv[1] != "prev"):
    if len(sys.argv) > 1 and sys.argv[1] == "audio":
        remux()
    else:
        main()
