"""3D-Trikot + Hockeyhose als "aufgeblasene" Silhouetten (Flat-Lay, schwebend) für mesh3d (reel37).

Keine Körper: nur Kleidung. Front/Rückseite als Höhenfeld über der Silhouette (Dicke ~ Wurzel des Randabstands),
Farbe/Streifen/Nummer aus Bildtexturen (mesh3d.TEXTURES).
jersey_mesh(tuck)   tuck 0..1: linke Vorderseite unten wird hinter den Hosenbund gesteckt
pants_mesh()
Koordinaten in Zoll: x quer, y hoch (Hosenbund bei y = 0), z zur Kamera.
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import distance_transform_edt

import mesh3d as M3

HERE = os.path.dirname(os.path.abspath(__file__))
RES = 0.35                                                  # Gitterabstand (Zoll)
NAVY = (28, 66, 160)                                         # Trikotgrund (kräftiges Blau)
PANT = (26, 30, 48)
ORANGE = (240, 120, 30)
WHITE = (240, 240, 244)

_R = [(13.0, -6.0), (13.6, 13.0), (29.5, 6.5), (33.0, 13.5), (18.5, 24.5), (7.5, 26.5), (3.6, 25.8), (0.0, 22.5)]
JERSEY = _R + [(-x, y) for x, y in _R[-2::-1]]               # Saum bei y = -6 (hängt 6" über die Hose)
PANTS = [(-11.5, 1.0), (11.5, 1.0), (12.6, -7.0), (13.2, -16.5), (1.8, -16.5), (0.9, -8.5), (-0.9, -8.5), (-1.8, -16.5),
         (-13.2, -16.5), (-12.6, -7.0)]


def _field(poly, thick):
    _POLY["cur"] = poly
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    x0, x1, y0, y1 = min(xs) - 1, max(xs) + 1, min(ys) - 1, max(ys) + 1
    nx, ny = int((x1 - x0) / RES) + 1, int((y1 - y0) / RES) + 1
    s = 4
    im = Image.new("L", (nx * s, ny * s), 0)
    ImageDraw.Draw(im).polygon([((x - x0) / RES * s, (y1 - y) / RES * s) for x, y in poly], fill=255)
    mask = np.asarray(im.resize((nx, ny), Image.BILINEAR)) > 127
    d = distance_transform_edt(mask) * RES
    h = thick * np.sqrt(np.clip(d / 4.5, 0, 1))
    gx = x0 + np.arange(nx) * RES
    gy = y1 - np.arange(ny) * RES
    return mask, h, gx, gy, (x0, x1, y0, y1)


def _surfaces(mask, h, gx, gy, box, mat, zfun=None):
    """Vorder- und Rückseite als Dreiecksnetz; zfun(x, y, z) verformt (z. B. Einstecken)."""
    ny, nx = mask.shape
    X, Y = np.meshgrid(gx, gy)
    x0, x1, y0, y1 = box
    out = []
    for sgn in (1.0, -1.0):
        Z = h * sgn
        if zfun is not None:
            Z = zfun(X, Y, Z, sgn)
        v = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
        v[:, :2] = _snap(v[:, :2], mask.ravel())
        idx = np.arange(nx * ny).reshape(ny, nx)
        m = mask
        q = m[:-1, :-1] | m[1:, :-1] | m[:-1, 1:] | m[1:, 1:]
        a, b, c, d = idx[:-1, :-1][q], idx[:-1, 1:][q], idx[1:, :-1][q], idx[1:, 1:][q]
        if sgn > 0:
            tris = np.concatenate([np.stack([a, c, b], 1), np.stack([b, c, d], 1)])
        else:
            tris = np.concatenate([np.stack([a, b, c], 1), np.stack([b, d, c], 1)])
        uvw = np.stack([(X.ravel() - x0) / (x1 - x0), (Y.ravel() - y0) / (y1 - y0), np.zeros(nx * ny)], 1)
        out.append(M3.Mesh(v, M3.vertex_normals(v, tris), tris, M3.MAT_IDS[mat], uvw))
    return out


_POLY = {}


def _snap(xy, inside):
    """Punkte außerhalb der Silhouette auf den nächsten Randpunkt ziehen (glatte Kontur statt Treppen)."""
    poly = _POLY["cur"]
    P = np.array(poly + [poly[0]])
    out = xy.copy()
    o = ~inside
    pts = xy[o]
    best = np.full(len(pts), 1e9)
    bp = pts.copy()
    for a, b in zip(P[:-1], P[1:]):
        ab = b - a
        t = np.clip(((pts - a) @ ab) / (ab @ ab), 0, 1)
        q = a + t[:, None] * ab
        d = np.sum((pts - q) ** 2, 1)
        k = d < best
        best[k], bp[k] = d[k], q[k]
    out[o] = bp
    return out


def _font(size):
    return ImageFont.truetype(os.path.join(HERE, "fonts", "ArchivoX900.ttf"), size)


def _tex(poly, painter, px_per_in=24, base=None):
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    x0, x1, y0, y1 = min(xs) - 1, max(xs) + 1, min(ys) - 1, max(ys) + 1
    w, hh = int((x1 - x0) * px_per_in), int((y1 - y0) * px_per_in)
    im = Image.new("RGB", (w, hh), base or NAVY)
    d = ImageDraw.Draw(im)

    def P(x, y):
        return ((x - x0) * px_per_in, (y1 - y) * px_per_in)

    painter(d, P, px_per_in)
    arr = np.asarray(im).astype(np.float32) / 255
    # leichte Stoffstruktur (Mesh-Gewebe)
    yy, xx = np.mgrid[0:hh, 0:w]
    arr *= (0.965 + 0.035 * (((xx // 3) + (yy // 3)) % 2))[..., None]
    return arr


def _paint_jersey(d, P, k):
    for y0, y1, col in ((-3.6, -1.6, ORANGE), (-1.2, -0.4, WHITE)):           # Saumstreifen
        d.rectangle((*P(-20, y1), *P(20, y0)), fill=col)
    for s in (-1, 1):                                                          # Ärmelstreifen (schräg)
        for off, wdt, col in ((0.0, 2.0, ORANGE), (2.4, 0.8, WHITE)):
            a, b = np.array([29.5 * s, 6.5]), np.array([33.0 * s, 13.5])
            n = np.array([-(b - a)[1], (b - a)[0]]) / np.linalg.norm(b - a) * s
            q0, q1 = a - n * (3.5 + off), b - n * (3.5 + off)
            d.polygon([P(*(q0 - (b - a) * 0.3)), P(*(q1 + (b - a) * 0.3)), P(*(q1 + (b - a) * 0.3 - n * wdt)),
                       P(*(q0 - (b - a) * 0.3 - n * wdt))], fill=col)
    d.polygon([P(-3.6, 25.8), P(0, 22.5), P(3.6, 25.8), P(3.0, 26.6), P(0, 23.8), P(-3.0, 26.6)], fill=ORANGE)
    f = _font(int(9.5 * k))
    txt = "21"
    bb = d.textbbox((0, 0), txt, font=f, stroke_width=int(0.45 * k))
    cx, cy = P(0, 11.5)
    d.text((cx - (bb[2] - bb[0]) / 2 - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1]), txt, font=f, fill=WHITE,
           stroke_width=int(0.45 * k), stroke_fill=ORANGE)


def _paint_pants(d, P, k):
    d.rectangle((*P(-14, 1.2), *P(14, -0.6)), fill=(12, 14, 24))                # Bund
    for s in (-1, 1):
        d.polygon([P(12.0 * s, -1.0), P(12.9 * s, -16.5), P(11.4 * s, -16.5), P(10.6 * s, -1.0)], fill=ORANGE)
    d.rectangle((*P(-14, -14.8), *P(14, -16.6)), fill=(12, 14, 24))


def jersey_mesh(tuck=0.0):
    mask, h, gx, gy, box = _field(JERSEY, 2.2)

    def zf(X, Y, Z, sgn):
        Z = Z + 2.6                                                     # hängt vor der Hose
        if tuck > 0 and sgn > 0:
            side = np.clip((-X - 1.0) / 4.0, 0, 1)                      # nur die linke Seite (vom Betrachter aus)
            low = np.clip((2.5 - Y) / 4.0, 0, 1)
            Z = Z - tuck * side * low * 6.4                             # hinter den Bund schieben
        if tuck > 0 and sgn < 0:
            side = np.clip((-X - 1.0) / 4.0, 0, 1)
            low = np.clip((2.5 - Y) / 4.0, 0, 1)
            Z = Z - tuck * side * low * 2.0
        return Z

    M3.TEXTURES["kit_jersey"] = _JT
    return _surfaces(mask, h, gx, gy, box, "kit_jersey", zf)


def pants_mesh():
    mask, h, gx, gy, box = _field(PANTS, 3.0)
    M3.TEXTURES["kit_pants"] = _PT
    return _surfaces(mask, h, gx, gy, box, "kit_pants")


_JT = _tex(JERSEY, _paint_jersey)
_PT = _tex(PANTS, _paint_pants, base=PANT)
