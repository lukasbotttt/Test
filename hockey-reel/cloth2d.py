"""2.5D-Stoff-Renderer (reel37): echtes Trikot-Design als Stoff mit Falten-Licht, Wehen und Einstecken in die Hose.

Trikot: kit/loewen_home_clean.png (Löwen Frankfurt Heim 2026/27, ohne Sponsoren, siehe kit_clean.py).
Hose: selbst gezeichnet (schwarz, orange Paspel, gesteppte Polster).
frame(t, tuck, yaw) -> (RGBA float-Bild in Arbeitsauflösung, Ankerpunkte)
Koordinaten: Arbeitsauflösung = Trikot-Textur * SCALE; Ursprung oben links am Trikot.
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import distance_transform_edt, gaussian_filter, map_coordinates

HERE = os.path.dirname(os.path.abspath(__file__))
SCALE = 0.55
ORANGE = (240, 104, 20)

# ----------------------------------------------------------------- Trikot laden
_src = Image.open(os.path.join(HERE, "kit", "loewen_home_clean.png")).convert("RGBA")
TW, TH = int(_src.width * SCALE), int(_src.height * SCALE)
JERSEY = np.asarray(_src.resize((TW, TH), Image.LANCZOS)).astype(np.float32) / 255
WAIST = 1250 * SCALE                       # Oberkante Hosenbund (y in Trikot-Koordinaten)
TORSO = (350 * SCALE, 1250 * SCALE)        # x-Bereich Rumpf
CX = 800 * SCALE                           # Mitte


def _height_map():
    """Faltenrelief (Höhe) über dem Trikot: Rumpfwölbung, Saum-Drapierung, Achselfalten, Ellbogenfalten."""
    yy, xx = np.mgrid[0:TH, 0:TW].astype(np.float32)
    u, v = xx / TW, yy / TH
    torso = ((u > 0.21) & (u < 0.79)).astype(np.float32)
    torso = gaussian_filter(torso, 12)
    h = -1.1 * ((u - 0.5) / 0.30) ** 2 * torso                                      # Wölbung
    hem = np.clip((v - 0.58) / 0.42, 0, 1) ** 1.3
    h += 0.42 * np.sin(u * 2 * math.pi * 4.6 + 0.9 * np.sin(v * 7.0)) * hem * torso  # Drapierung zum Saum
    for ax, s in ((0.235, 1.0), (0.765, -1.0)):                                    # Achselfalten
        dx, dy = u - ax, v - 0.40
        d = np.sqrt(dx * dx + dy * dy)
        ang = np.arctan2(dy, dx * s)
        h += 0.30 * np.sin(d * 46.0 - ang * 2.6) * np.exp(-d * 7.0) * torso
    sleeve = 1 - torso
    h += 0.45 * np.sin(v * 58.0 + u * 9.0) * np.exp(-((v - 0.64) / 0.09) ** 2) * sleeve   # Ellbogen
    h += 0.25 * np.sin(v * 20.0 - u * 30.0) * sleeve * np.clip((v - 0.2) / 0.6, 0, 1)
    rng = np.random.default_rng(37)
    h += gaussian_filter(rng.normal(0, 1, (TH, TW)).astype(np.float32), 26) * 3.5      # unregelmäßig
    return h


def _shade(h, alpha, k=26.0, light=(-0.45, -0.55, 0.70)):
    gy, gx = np.gradient(gaussian_filter(h, 2.0))
    n = np.stack([-gx * k, -gy * k, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    L = np.array(light, np.float32)
    L /= np.linalg.norm(L)
    diff = np.clip((n * L).sum(-1), 0, 1)
    Hh = L + np.array([0, 0, 1.0], np.float32)
    Hh /= np.linalg.norm(Hh)
    spec = np.clip((n * Hh).sum(-1), 0, 1) ** 24
    edge = distance_transform_edt(alpha > 0.5)                     # Volumen: Ränder etwas dunkler
    ao = 0.80 + 0.20 * np.clip(edge / 22.0, 0, 1)
    return (0.58 + 0.62 * diff) * ao, spec


_JH = _height_map()
J_SHADE, J_SPEC = _shade(_JH, JERSEY[..., 3])


# ----------------------------------------------------------------- Hose zeichnen
def _pants():
    w, hgt = int(1000 * SCALE), int(640 * SCALE)
    s = 3
    im = Image.new("RGBA", (w * s, hgt * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    def P(x, y):                                               # x relativ zur Mitte, y ab Bund (Trikot-Pixel)
        return ((x * SCALE + w / 2) * s, y * SCALE * s)

    leg = [(-480, 0), (480, 0), (505, 120), (515, 330), (500, 610), (70, 610), (52, 360), (0, 330), (-52, 360),
           (-70, 610), (-500, 610), (-515, 330), (-505, 120)]
    d.polygon([P(*p) for p in leg], fill=(28, 28, 31, 255))
    d.polygon([P(-480, 0), P(480, 0), P(488, 58), P(-488, 58)], fill=(18, 18, 20, 255))          # Bund
    for sx in (-1, 1):                                                                          # Paspel
        d.line([P(sx * 508, 90), P(sx * 515, 330), P(sx * 503, 600)], fill=ORANGE + (255,), width=int(9 * SCALE * s))
        d.line([P(sx * 470, 90), P(sx * 478, 330), P(sx * 466, 600)], fill=ORANGE + (255,), width=int(4 * SCALE * s))
    for y in (190, 330, 470):                                                                   # Steppnähte
        d.line([P(-500, y), P(-80, y + 20)], fill=(16, 16, 18, 255), width=int(5 * SCALE * s))
        d.line([P(80, y + 20), P(500, y)], fill=(16, 16, 18, 255), width=int(5 * SCALE * s))
    for x in (-300, -150, 150, 300):                                                            # Gürtelschlaufen
        d.rectangle((*P(x - 14, -4), *P(x + 14, 62)), fill=(40, 40, 44, 255))
    im = im.resize((w, hgt), Image.LANCZOS)
    arr = np.asarray(im).astype(np.float32) / 255
    yy, xx = np.mgrid[0:hgt, 0:w].astype(np.float32)
    u, v = xx / w, yy / hgt
    h = np.zeros((hgt, w), np.float32)
    for c in (0.27, 0.73):                                                                      # zwei Beine
        h += -1.2 * ((u - c) / 0.25) ** 2
    for y in (190, 330, 470):
        h += 0.35 * np.exp(-((yy - (y + 10) * SCALE) / (14 * SCALE)) ** 2)                     # Polster-Wülste
    h = np.maximum(h, -2.0)
    sh, sp = _shade(h * 2.0, arr[..., 3], k=18.0)
    arr[..., :3] = np.clip(arr[..., :3] * sh[..., None] + sp[..., None] * 0.18, 0, 1)
    return arr


PANTS = _pants()
PW, PH = PANTS.shape[1], PANTS.shape[0]
PANTS_X0 = CX - PW / 2                      # Position in Trikot-Koordinaten
PANTS_Y0 = WAIST

# Arbeitsfläche: Trikot + Hose darunter
CW = TW
CH = int(max(TH, PANTS_Y0 + PH)) + 4


def _warp(img, dx, dy):
    """img an (x - dx, y - dy) abtasten (kleine Verschiebungen, Kanäle einzeln)."""
    hgt, w = img.shape[:2]
    yy, xx = np.mgrid[0:hgt, 0:w].astype(np.float32)
    cy, cx = yy - dy, xx - dx
    out = np.empty_like(img)
    for c in range(img.shape[2]):
        out[..., c] = map_coordinates(img[..., c], [cy, cx], order=1, mode="constant", cval=0.0)
    return out


def frame(t, tuck=0.0, yaw=0.0):
    """-> RGBA (CH, CW, 4) mit Licht, Wehen und Einstecken; dazu Ankerpunkte (Trikot-Koordinaten)."""
    yy, xx = np.mgrid[0:TH, 0:TW].astype(np.float32)
    u, v = xx / TW, yy / TH
    sleeve_w = np.clip((np.abs(u - 0.5) - 0.27) / 0.2, 0, 1)
    # Wehen: Ärmel schwingen, Saum wellt sich
    dx = 9.0 * np.sin(2 * math.pi * 0.55 * t + v * 3.2) * sleeve_w * np.clip(v * 1.4, 0, 1)
    dx += 5.0 * np.sin(2 * math.pi * 0.42 * t + u * 4.0) * np.clip((v - 0.5) * 2, 0, 1)
    dy = 3.0 * np.sin(2 * math.pi * 0.5 * t + u * 6.5) * np.clip(v - 0.45, 0, 1) * 2
    dy += 4.0 * np.sin(2 * math.pi * 0.55 * t + 1.3) * sleeve_w
    # Drehung um die Hochachse (leichte Perspektive)
    dx += (xx - CX) * (math.cos(yaw) - 1)
    dy += (yy - TH * 0.45) * (xx - CX) / TW * math.sin(yaw) * 0.12
    # Einstecken (linke Seite vom Betrachter): Stoff wird nach unten in den Bund gezogen
    left = np.clip((CX + 30 - xx) / 90.0, 0, 1) * np.clip((xx - TORSO[0] + 20) / 30.0, 0, 1)
    band = np.clip((yy - (WAIST - 150)) / 150.0, 0, 1)
    dy += tuck * 26.0 * left * band ** 1.4
    jr = _warp(np.dstack([JERSEY, J_SHADE[..., None], J_SPEC[..., None]]), dx, dy)
    rgb, a, sh, sp = jr[..., :3], jr[..., 3], jr[..., 4], jr[..., 5]
    # Bausch-Falten über dem Bund
    bunch = tuck * left * np.exp(-((yy - (WAIST - 40)) / 45.0) ** 2)
    sh = sh * (1 - 0.32 * bunch * (0.5 + 0.5 * np.sin(yy * 0.55 + xx * 0.05)))
    sp = sp + 0.25 * bunch * np.clip(np.sin(yy * 0.55 + xx * 0.05 + 1.2), 0, 1) ** 4
    shade_yaw = 1 + 0.22 * math.sin(yaw) * (u - 0.5) * 2
    rgb = np.clip(rgb * (sh * shade_yaw)[..., None] + sp[..., None] * 0.35, 0, 1)
    # unterhalb des Bundes auf der linken Seite: im Hosenbund verschwunden
    xb = CX - 20 + np.clip(yy - WAIST, 0, None) * 0.9                       # diagonale Kante: rechts hängt raus
    hide = tuck * np.clip((xb - xx) / 2.0 + 0.5, 0, 1) * np.clip((yy - WAIST - 2) / 4.0, 0, 1)
    a = a * (1 - hide)
    # Hose (dahinter), leicht mitschwingend
    canvas = np.zeros((CH, CW, 4), np.float32)
    px0 = int(round(PANTS_X0 + 3 * math.sin(2 * math.pi * 0.42 * t)))
    py0 = int(round(PANTS_Y0))
    pc = PANTS.copy()
    # Schatten des Trikots auf der Hose
    jsh = np.zeros((CH, CW), np.float32)
    jsh[:TH, :TW] = a
    jsh = gaussian_filter(np.roll(jsh, 10, axis=0), 9)
    pc_sh = jsh[py0:py0 + PH, px0:px0 + PW]
    pc[..., :3] *= (1 - 0.55 * pc_sh[:pc.shape[0], :pc.shape[1]])[..., None]
    # dunkle Kante, wo der Stoff im Bund steckt
    tuck_edge = np.zeros((PH, PW), np.float32)
    tl = tuck * np.clip((CX - 6 - (np.arange(PW) + px0)) / 30.0, 0, 1)[None, :]
    tuck_edge += tl * np.exp(-(np.arange(PH)[:, None] / 10.0) ** 2)
    pc[..., :3] *= (1 - 0.0 * tuck_edge)[..., None]
    canvas[py0:py0 + PH, px0:px0 + PW] = pc
    jl = np.zeros((CH, CW, 4), np.float32)
    jl[:TH, :TW, :3] = rgb
    jl[:TH, :TW, 3] = a
    out = canvas.copy()
    al = jl[..., 3:4]
    out[..., :3] = canvas[..., :3] * canvas[..., 3:4] * (1 - al) + jl[..., :3] * al
    out[..., 3:4] = canvas[..., 3:4] * (1 - al) + al
    out[..., :3] = np.where(out[..., 3:4] > 1e-4, out[..., :3] / np.maximum(out[..., 3:4], 1e-4), 0)
    # Bund liegt auf dem eingesteckten Stoff: schmaler Schatten direkt unter der Kante
    yb = int(WAIST)
    lane = tuck * np.clip((CX - 6 - np.arange(CW)) / 30.0, 0, 1) * (np.arange(CW) > TORSO[0] - 10)
    for k, f in ((0, 0.55), (1, 0.62), (2, 0.72), (3, 0.82), (4, 0.9)):
        out[yb + 6 + k, :, :3] *= (1 - (1 - f) * lane)[:, None]
    # Hosenbund liegt auf dem eingesteckten Stoff (linke Seite)
    if tuck > 0:
        bh = int(34 * SCALE * 1.6)
        xs = np.arange(CW)
        lanew = np.clip((CX - 20 - xs) / 3.0 + 0.5, 0, 1) * tuck
        band_src = np.zeros((bh, CW, 4), np.float32)
        band_src[:, px0:px0 + PW] = pc[:bh]
        ab = band_src[..., 3] * lanew[None, :]
        seg = out[py0:py0 + bh]
        seg[..., :3] = seg[..., :3] * (1 - ab[..., None]) + band_src[..., :3] * ab[..., None]
        seg[..., 3] = np.maximum(seg[..., 3], ab)
    anchors = {"tuck": (CX - 230, WAIST - 10), "waist": (CX - 220, WAIST + 30), "chest": (CX, 400)}
    return out, anchors
