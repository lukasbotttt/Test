"""Cinematisches Motion-Video: der perfekte Golfschwung (1080x1920, 30 fps).

Ein prozedural animierter Golfer (3D-Skelett, Schwung in der Schwungebene, IK für Arme/Beine)
steht als Gegenlicht-Silhouette vor einer Golden-Hour-Sonne. Kamera-Fahrten, Bullet-Time am
Umkehrpunkt, Super-Zeitlupe im Treffmoment, Ballflug mit Tracer, Bloom, Lichtstrahlen, Korn.

Aufruf: python3 swing_cinematic.py  ->  swing_cinematic.mp4 (+ swing_thumbnail.jpg)
        python3 swing_cinematic.py --preview 4.2 9.9  ->  einzelne Frames als PNG
"""
import math
import subprocess
import sys
import wave
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
HERE = Path(__file__).resolve().parent
ANTON = str(HERE.parent / "hockey-reel" / "fonts" / "Anton.ttf")
INTER = "/usr/share/fonts/opentype/inter/Inter-{}.otf"

# Szenen (Sekunden)
A0, B0, E0, F0, G0, H0, END = 0.0, 3.0, 9.4, 11.6, 15.6, 18.6, 21.8
DURATION = END
T_IMPACT = 1.13


# ---------------------------------------------------------------- Mathe-Helfer
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def smooth(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def ease_out(t):
    return 1 - (1 - clamp(t)) ** 3


def norm(v):
    return v / np.linalg.norm(v)


def rot(v, axis, ang):
    """Rodrigues-Rotation von v um axis (Einheitsvektor) um ang (rad)."""
    c, s = math.cos(ang), math.sin(ang)
    return v * c + np.cross(axis, v) * s + axis * np.dot(axis, v) * (1 - c)


def pchip(keys):
    """Monotone kubische Interpolation (Fritsch-Carlson) über [(t, v), ...]; außerhalb konstant."""
    xs = np.array([k[0] for k in keys], float)
    ys = np.array([k[1] for k in keys], float)
    h = np.diff(xs)
    d = np.diff(ys) / h
    m = np.zeros_like(ys)
    for i in range(1, len(ys) - 1):
        if d[i - 1] * d[i] > 0:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])

    def f(t):
        if t <= xs[0]:
            return ys[0]
        if t >= xs[-1]:
            return ys[-1]
        i = int(np.searchsorted(xs, t) - 1)
        s = (t - xs[i]) / h[i]
        h00, h10 = 2 * s**3 - 3 * s**2 + 1, s**3 - 2 * s**2 + s
        h01, h11 = -2 * s**3 + 3 * s**2, s**3 - s**2
        return h00 * ys[i] + h10 * h[i] * m[i] + h01 * ys[i + 1] + h11 * h[i] * m[i + 1]

    return f


# ---------------------------------------------------------------- Schwung-Kinematik
# Zeit T in echten Sekunden: 0 = Rückschwung beginnt, 0.85 = Top, 1.13 = Treffmoment, 1.8 = Finish
HAND_ANG = pchip([(0, 0), (0.3, 38), (0.6, 100), (0.85, 132), (0.93, 128), (1.0, 100), (1.07, 52),
                  (1.13, 0), (1.2, -55), (1.35, -115), (1.55, -150), (1.8, -160)])
HINGE = pchip([(0, 0), (0.3, 12), (0.6, 78), (0.85, 112), (0.95, 116), (1.03, 100), (1.08, 58),
               (1.13, 0), (1.2, -40), (1.35, -95), (1.55, -125), (1.8, -132)])
HIP_ROT = pchip([(0, 0), (0.85, 45), (0.98, 25), (1.13, -40), (1.4, -80), (1.8, -92)])
SHO_ROT = pchip([(0, 0), (0.85, 95), (1.0, 62), (1.13, -12), (1.4, -85), (1.8, -110)])
P_SHIFT = pchip([(0, 0), (0.85, -0.03), (1.13, 0.07), (1.8, 0.14)])
TILT = pchip([(0, 33), (1.13, 31), (1.5, 18), (1.8, 8)])
SIDE = pchip([(0, 0), (0.85, 3), (1.13, -10), (1.5, -14), (1.8, -10)])
HEEL = pchip([(1.13, 0), (1.4, 0.07), (1.8, 0.13)])
GAZE = pchip([(1.18, 0), (1.5, 1)])

X, Y, Z = np.eye(3)
BALL_R = 0.0214
BALL0 = np.array([0.10, 0.045, 1.15])
P0 = np.array([0.0, 0.88, -0.06])
SPINE_LEN = 0.52
TOE0 = norm(np.array([0.08, 0.0, 1.0]))
FACE_OFF = 0.05  # Hosel -> Schlagflächen-Mitte entlang Spitze
_s0 = P0 + SPINE_LEN * np.array([0, math.cos(math.radians(33)), math.sin(math.radians(33))])
CH = _s0 + np.array([0.0, -0.05, 0.05])  # Zentrum der Handkreisbahn
HOSEL0 = BALL0 - X * BALL_R - TOE0 * FACE_OFF
PA = norm(HOSEL0 - CH)
PB = norm(-X - np.dot(-X, PA) * PA)
PN = norm(np.cross(PA, PB))
R_HAND = 0.62
L_CLUB = np.linalg.norm(HOSEL0 - CH) - R_HAND


def plane_dir(deg):
    a = math.radians(deg)
    return math.cos(a) * PA + math.sin(a) * PB


def club(T):
    """Hände, Hosel, Schaftrichtung und Kopf-Orientierung (Spitze, Fläche, oben)."""
    ph, dl = HAND_ANG(T), HINGE(T)
    hands = CH + R_HAND * plane_dir(ph)
    sd = plane_dir(ph + dl)
    hosel = hands + L_CLUB * sd
    ang = math.radians(ph + dl)
    toe = rot(TOE0, PN, ang)
    face = rot(X, PN, ang)
    up = rot(Y, PN, ang)
    return hands, hosel, sd, toe, face, up


def face_center(T):
    _, hosel, _, toe, _, _ = club(T)
    return hosel + toe * FACE_OFF


def two_bone(root, end, l1, l2, pole):
    v = end - root
    d = np.linalg.norm(v)
    dr = v / d
    if d >= l1 + l2 - 1e-4:
        return root + dr * l1
    a1 = (l1 * l1 + d * d - l2 * l2) / (2 * d)
    hh = math.sqrt(max(l1 * l1 - a1 * a1, 0))
    perp = norm(pole - np.dot(pole, dr) * dr)
    return root + dr * a1 + perp * hh


def pose(T):
    """Liefert Zeichen-Primitive des Golfers: Liste von (art, punkte, breite_m)."""
    hip, sho = math.radians(HIP_ROT(T)), math.radians(SHO_ROT(T))
    tilt, side = math.radians(TILT(T)), math.radians(SIDE(T))
    P = P0 + X * P_SHIFT(T)
    sp = norm(np.array([math.sin(side), math.cos(tilt), math.sin(tilt)]))
    S = P + SPINE_LEN * sp
    lat_s = rot(X, sp, -sho)
    lat_h = rot(X, Y, -hip)
    lsh, tsh = S + lat_s * 0.20, S - lat_s * 0.20
    lhp, thp = P + lat_h * 0.11, P - lat_h * 0.11

    hands, hosel, sd, toe, face, up = club(T)
    lhand, thand = hands - sd * 0.02, hands + sd * 0.06
    lelb = two_bone(lsh, lhand, 0.31, 0.30, -sp + lat_s * 0.3)
    telb = two_bone(tsh, thand, 0.31, 0.30, -sp - lat_s * 0.3)

    heel = HEEL(T)
    lfoot_toe, lfoot_heel = np.array([0.33, 0.0, 0.17]), np.array([0.25, 0.0, -0.06])
    tfoot_toe = np.array([-0.27, 0.0, 0.18])
    tfoot_heel = np.array([-0.24 + heel * 0.9, heel, -0.03])
    lank = np.array([0.26, 0.08, -0.02])
    tank = tfoot_heel + np.array([0.0, 0.08, 0.03]) + X * heel * 0.3
    lknee = two_bone(lhp, lank, 0.46, 0.44, Z + X * 0.25)
    tknee = two_bone(thp, tank, 0.46, 0.44, Z - X * 0.1 + X * heel * 4)

    neck = S + sp * 0.07
    hd = norm(sp + Y * 0.45)
    head = S + hd * 0.25
    g = GAZE(T)
    look = norm((1 - g) * (BALL0 - head) + g * np.array([1.0, 0.25, 0.1]))
    brim = head + look * 0.09 + hd * 0.04

    prims = [
        ("poly", [lhp, thp, tsh, lsh], 0.10),
        ("cap", [P + sp * 0.05, S - sp * 0.06], 0.22),
        ("cap", [S - sp * 0.16 + lat_s * 0.07, S - sp * 0.16 - lat_s * 0.07], 0.26),
        ("cap", [lhp, thp], 0.20),
        ("cap", [lsh, tsh], 0.13),
        ("cap", [neck, head], 0.11),
        ("disc", [head], 0.20),
        ("cap", [head + hd * 0.05, brim], 0.07),
        ("cap", [lhp, lknee], 0.17), ("cap", [lknee, lank], 0.12),
        ("cap", [thp, tknee], 0.17), ("cap", [tknee, tank], 0.12),
        ("cap", [lfoot_heel, lfoot_toe], 0.09), ("cap", [tfoot_heel, tfoot_toe], 0.09),
        ("cap", [lsh, lelb], 0.10), ("cap", [lelb, lhand], 0.085),
        ("cap", [tsh, telb], 0.10), ("cap", [telb, thand], 0.085),
        ("disc", [hands], 0.10),
    ]
    return prims


def club_prims(T):
    hands, hosel, sd, toe, face, up = club(T)
    prims = [("cap", [hands - sd * 0.06, hands + sd * 0.24], 0.024),
             ("cap", [hands, hosel], 0.011)]
    # Driverkopf als konvexe Hülle eines abgeflachten Ellipsoids
    c = hosel + toe * 0.058 - face * 0.05 + up * 0.012
    pts = []
    for a in np.linspace(0, 2 * math.pi, 28, endpoint=False):
        for b in (-1.1, -0.55, 0.0, 0.55, 1.1):
            r = math.cos(b)
            pts.append(c + toe * 0.062 * r * math.cos(a) + face * 0.052 * r * math.sin(a)
                       + up * 0.03 * math.sin(b))
    pts.append(hosel - sd * 0.02)
    prims.append(("hull", pts, 0.0))
    return prims


# ---------------------------------------------------------------- Ballflug
def simulate_flight():
    v = 74.7 * np.array([math.cos(math.radians(10.9)), math.sin(math.radians(10.9)), 0.0])
    p = BALL0.copy()
    kd, kl, dt = 0.0047, 0.0032, 0.004
    out = [(0.0, p.copy())]
    t = 0.0
    while p[1] > 0 and t < 12:
        sp = np.linalg.norm(v)
        lift_dir = norm(np.cross(Z, v)) * -1 if False else norm(np.array([-v[1], v[0], 0.0]))
        acc = -kd * sp * v + kl * sp * sp * lift_dir + np.array([0, -9.81, 0])
        v = v + acc * dt
        p = p + v * dt
        t += dt
        out.append((t, p.copy()))
    ts = np.array([o[0] for o in out])
    ps = np.array([o[1] for o in out])
    return ts, ps


FLIGHT_T, FLIGHT_P = simulate_flight()
CARRY = FLIGHT_P[-1, 0] - BALL0[0]


def ball_pos(tb):
    if tb <= 0:
        return BALL0.copy()
    i = min(np.searchsorted(FLIGHT_T, tb), len(FLIGHT_T) - 1)
    return FLIGHT_P[i]


# ---------------------------------------------------------------- Kamera
class Cam:
    def __init__(self, pos, target, fov):
        self.pos = np.asarray(pos, float)
        self.fw = norm(np.asarray(target, float) - self.pos)
        self.right = norm(np.cross(self.fw, Y))
        self.up = np.cross(self.right, self.fw)
        self.f = (H / 2) / math.tan(math.radians(fov) / 2)

    def project(self, p):
        d = np.asarray(p) - self.pos
        z = max(np.dot(d, self.fw), 1e-3)
        return (W / 2 + self.f * np.dot(d, self.right) / z,
                H / 2 - self.f * np.dot(d, self.up) / z, z)

    def sun(self, yaw, elev):
        hf = norm(np.array([self.fw[0], 0, self.fw[2]]))
        d = rot(hf, Y, math.radians(-yaw))
        e = math.radians(elev)
        return norm(d * math.cos(e) + Y * math.sin(e))


# ---------------------------------------------------------------- Himmel & Boden (linear RGB)
HORIZON = np.array([1.0, 0.50, 0.22])
MID = np.array([0.36, 0.17, 0.24])
ZENITH = np.array([0.025, 0.03, 0.085])
SUNCOL = np.array([1.0, 0.72, 0.42])


def sky(dirs, S):
    e = np.clip(dirs[:, 1], 0, 1)[:, None]
    k1 = np.clip(e / 0.12, 0, 1) ** 0.7
    k2 = np.clip((e - 0.08) / 0.35, 0, 1) ** 0.7
    col = HORIZON * (1 - k1) + MID * k1
    col = col * (1 - k2) + ZENITH * k2
    c = np.clip(dirs @ S, -1, 1)[:, None]
    col = col + SUNCOL * (np.exp((c - 1) * 900) * 2.0 + np.exp((c - 1) * 60) * 0.45
                          + np.exp((c - 1) * 6) * 0.16)
    disk = np.clip((c - math.cos(math.radians(1.05))) / 0.00004, 0, 1)
    col = col + disk * np.array([6.0, 5.0, 3.6])
    # feine Wolkenschlieren
    az = np.arctan2(dirs[:, 0], -dirs[:, 2])[:, None]
    band = np.sin(e * 140 + np.sin(az * 9) * 1.5) * np.sin(az * 31 + e * 40)
    clouds = np.clip(band - 0.55, 0, 1) * np.exp(-e * 14) * (e > 0.015)
    col = col + clouds * (SUNCOL * 0.6 + np.exp((c - 1) * 8) * 0.8)
    return col


def background(cam, S, scale=2):
    w, h = W // scale, H // scale
    xs = (np.arange(w) + 0.5) * scale - W / 2
    ys = H / 2 - (np.arange(h) + 0.5) * scale
    gx, gy = np.meshgrid(xs, ys)
    dirs = (cam.fw[None, None] * cam.f + cam.right[None, None] * gx[..., None]
            + cam.up[None, None] * gy[..., None]).reshape(-1, 3)
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
    col = sky(dirs, S)
    e = dirs[:, 1]
    gnd = e < 0
    if gnd.any():
        d = dirs[gnd]
        t = cam.pos[1] / np.maximum(-d[:, 1], 1e-5)
        t = np.minimum(t, 5000)
        p = cam.pos[None] + d * t[:, None]
        stripe = 0.5 + 0.5 * np.tanh(np.sin(p[:, 2] * math.pi / 6.0) * 4)
        base = np.array([0.030, 0.052, 0.020]) * (0.75 + 0.5 * stripe)[:, None]
        r = d * np.array([1, -1, 1])
        rc = np.clip(r @ S, -1, 1)[:, None]
        base = base + SUNCOL * (np.exp((rc - 1) * 70) * 0.9 + np.exp((rc - 1) * 8) * 0.12)
        hz = d.copy()
        hz[:, 1] = 0.001
        hz /= np.linalg.norm(hz, axis=1, keepdims=True)
        fog = sky(hz, S)
        k = (1 - np.exp(-t / 260))[:, None]
        col[gnd] = base * (1 - k) + fog * k
    # Baumreihe am Horizont
    az = np.arctan2(dirs[:, 0], -dirs[:, 2])
    ht = (0.016 + 0.007 * np.sin(az * 5 + 1) + 0.004 * np.sin(az * 17 + 2)
          + 0.004 * np.abs(np.sin(az * 47)) + 0.003 * np.abs(np.sin(az * 131 + 0.5)))
    tree = (e > -0.003) & (e < ht)
    if tree.any():
        hz = dirs[tree].copy()
        hz[:, 1] = 0.0
        hz /= np.linalg.norm(hz, axis=1, keepdims=True)
        fog = sky(hz, S)
        col[tree] = np.array([0.04, 0.025, 0.05]) * 0.35 + fog * 0.55
    img = col.reshape(h, w, 3).astype(np.float32)
    return img


def _box(a, r, axis):
    if r < 1:
        return a
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis, dtype=np.float32)
    n = a.shape[axis]
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return (hi - lo) / (2 * r + 1)


def gblur(a, sigma):
    """Gauß-Näherung über drei Box-Filter (float-Arrays, beliebige Kanäle)."""
    if sigma <= 0.3:
        return a
    r = max(int(round(sigma * 0.93)), 1)
    for _ in range(3):
        a = _box(_box(a, r, 0), r, 1)
    return a


def resize_f(arr, w, h):
    out = np.empty((h, w) + arr.shape[2:], np.float32)
    if arr.ndim == 2:
        return np.asarray(Image.fromarray(arr.astype(np.float32), "F").resize((w, h), Image.BILINEAR))
    for c in range(arr.shape[2]):
        out[..., c] = np.asarray(Image.fromarray(arr[..., c].astype(np.float32), "F").resize(
            (w, h), Image.BILINEAR))
    return out


def upscale(arr, blur=0.0):
    """Lineares RGB float (halbe Auflösung) -> volle Auflösung + optionale Tiefenunschärfe."""
    return resize_f(gblur(arr, blur / 2), W, H)


# ---------------------------------------------------------------- Silhouette mit Randlicht
def convex_hull(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


SS = 2  # Supersampling


def draw_prims(draw, cam, prims, ox, oy, val=255):
    for kind, pts, wm in prims:
        pr = [cam.project(p) for p in pts]
        xy = [((x - ox) * SS, (y - oy) * SS) for x, y, _ in pr]
        if kind == "cap":
            (x0, y0), (x1, y1) = xy
            z = (pr[0][2] + pr[1][2]) / 2
            wpx = max(wm * cam.f / z * SS, 1.2)
            draw.line([xy[0], xy[1]], fill=val, width=int(round(wpx)))
            for (x, y), zz in ((xy[0], pr[0][2]), (xy[1], pr[1][2])):
                r = wm * cam.f / zz * SS / 2
                if r > 0.8:
                    draw.ellipse([x - r, y - r, x + r, y + r], fill=val)
        elif kind == "disc":
            (x, y), z = xy[0], pr[0][2]
            r = wm * cam.f / z * SS / 2
            draw.ellipse([x - r, y - r, x + r, y + r], fill=val)
        elif kind == "poly":
            draw.polygon(xy, fill=val)
        elif kind == "hull":
            hull = convex_hull([(round(x, 2), round(y, 2)) for x, y in xy])
            if len(hull) >= 3:
                draw.polygon(hull, fill=val)


def prim_bbox(cam, prim_sets, margin=60):
    xs, ys = [], []
    for prims in prim_sets:
        for _, pts, wm in prims:
            for p in pts:
                x, y, z = cam.project(p)
                r = wm * cam.f / z
                xs += [x - r, x + r]
                ys += [y - r, y + r]
    if not xs:
        return None
    x0, x1 = int(max(min(xs) - margin, -margin)), int(min(max(xs) + margin, W + margin))
    y0, y1 = int(max(min(ys) - margin, -margin)), int(min(max(ys) + margin, H + margin))
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1


def silhouette(frame, cam, S, layers, rim_w=4.0, rim_gain=1.0):
    """layers: Liste von (prims, alpha) – alpha <1 für Bewegungsunschärfe-Kopien."""
    box = prim_bbox(cam, [p for p, _ in layers])
    if box is None:
        return None
    x0, y0, x1, y1 = box
    cw, chh = x1 - x0, y1 - y0
    acc = np.zeros((chh, cw), np.float32)
    for prims, a in layers:
        im = Image.new("L", (cw * SS, chh * SS), 0)
        draw_prims(ImageDraw.Draw(im), cam, prims, x0, y0)
        m = np.asarray(im.reduce(SS), np.float32) / 255.0
        acc = np.maximum(acc, m * a)
    m = acc
    # Lichtrichtung auf dem Bildschirm
    d = np.array([np.dot(S, cam.right), -np.dot(S, cam.up)])
    back = clamp(np.dot(S, cam.fw) * 1.2 + 0.25)
    if np.linalg.norm(d) < 1e-3:
        d = np.array([0.0, -1.0])
    d = d / np.linalg.norm(d)
    rims = np.zeros_like(m)
    for k in (rim_w * 0.5, rim_w):
        dx, dy = int(round(d[0] * k)), int(round(d[1] * k))
        sh = np.roll(m, (-dy, -dx), axis=(0, 1))
        rims = np.maximum(rims, m * (1 - sh))
    rim_img = Image.fromarray((rims * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))
    rim = np.asarray(rim_img, np.float32) / 255.0
    glow = np.asarray(Image.fromarray((rims * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(rim_w * 2.5)), np.float32) / 255.0
    # in Frame einsetzen
    fx0, fy0 = max(x0, 0), max(y0, 0)
    fx1, fy1 = min(x1, W), min(y1, H)
    if fx1 <= fx0 or fy1 <= fy0:
        return None
    sl = (slice(fy0 - y0, fy1 - y0), slice(fx0 - x0, fx1 - x0))
    reg = frame[fy0:fy1, fx0:fx1]
    mm = m[sl][..., None]
    body = np.array([0.010, 0.009, 0.012]) + (1 - back) * np.array([0.03, 0.022, 0.018])
    reg[:] = reg * (1 - mm) + body * mm
    g = back * rim_gain
    reg += (rim[sl][..., None] * mm * 3.2 * g + glow[sl][..., None] * 0.35 * g) * SUNCOL
    return m, box


# ---------------------------------------------------------------- Ball
_FIB = None


def fib_points(n=330):
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n)
    th = math.pi * (1 + 5**0.5) * i
    return np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], 1)


def draw_ball(frame, cam, S, p, spin=0.0, squash=0.0, vel2d=None):
    global _FIB
    x, y, z = cam.project(p)
    if z < 0.05:
        return
    r = BALL_R * cam.f / z
    if r < 2.5:
        # winziger Ball: nur leuchtender Punkt
        rr = 6
        xs, ys = np.meshgrid(np.arange(-rr, rr + 1), np.arange(-rr, rr + 1))
        g = np.exp(-(xs**2 + ys**2) / (2 * max(r, 0.8) ** 2))[..., None]
        _blit_add(frame, g * np.array([2.2, 2.0, 1.7]), int(x) - rr, int(y) - rr)
        return
    R = int(r * 1.6) + 3
    xs, ys = np.meshgrid(np.arange(-R, R + 1) + (x - int(x)) * -1, np.arange(-R, R + 1) + (y - int(y)) * -1)
    sx, sy = 1 + squash * -0.25, 1 + squash * 0.18
    nx, ny = xs / (r * sx), -ys / (r * sy)
    rr2 = nx**2 + ny**2
    inside = rr2 < 1
    cov = np.clip((1 - np.sqrt(rr2)) * r * 1.0 + 0.5, 0, 1)
    nz = np.sqrt(np.clip(1 - rr2, 0, 1))
    L = np.array([np.dot(S, cam.right), np.dot(S, cam.up), -np.dot(S, cam.fw)])
    diff = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
    fresnel = (1 - nz) ** 3
    shade = 0.16 + 0.22 * np.clip(ny, 0, 1) + diff * 3.0 + fresnel * 0.6
    if r > 14:
        if _FIB is None:
            _FIB = fib_points()
        c, s = math.cos(spin), math.sin(spin)
        n = np.stack([nx, ny, nz], -1)[inside]
        n_r = np.stack([n[:, 0], c * n[:, 1] - s * n[:, 2], s * n[:, 1] + c * n[:, 2]], 1)
        dots = n_r @ _FIB.T
        dimp = np.clip((dots.max(1) - 0.985) / 0.015, 0, 1)
        dm = np.zeros_like(shade)
        dm[inside] = dimp
        shade = shade * (1 - 0.45 * dm * (0.3 + diff)) + dm * 0.02
    col = shade[..., None] * np.array([0.95, 0.92, 0.88])
    a = (cov * inside)[..., None]
    x0, y0 = int(x) - R, int(y) - R
    _blit_over(frame, col, a, x0, y0)


def _clip_region(arr, x0, y0):
    h, w = arr.shape[:2]
    fx0, fy0, fx1, fy1 = max(x0, 0), max(y0, 0), min(x0 + w, W), min(y0 + h, H)
    if fx1 <= fx0 or fy1 <= fy0:
        return None
    return (slice(fy0, fy1), slice(fx0, fx1)), (slice(fy0 - y0, fy1 - y0), slice(fx0 - x0, fx1 - x0))


def _blit_add(frame, arr, x0, y0):
    r = _clip_region(arr, x0, y0)
    if r:
        frame[r[0]] += arr[r[1]]


def _blit_over(frame, col, a, x0, y0):
    r = _clip_region(col, x0, y0)
    if r:
        frame[r[0]] = frame[r[0]] * (1 - a[r[1]]) + col[r[1]] * a[r[1]]


# ---------------------------------------------------------------- Linien / Glow
def glow_line(frame, pts, color, width=3, glow=14, alpha=None):
    """Polylinie (Bildschirmkoordinaten) additiv mit Kern und Leuchten."""
    if len(pts) < 2:
        return
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    pad = glow * 3 + width
    x0, y0 = int(max(min(xs) - pad, 0)), int(max(min(ys) - pad, 0))
    x1, y1 = int(min(max(xs) + pad, W)), int(min(max(ys) + pad, H))
    if x1 <= x0 or y1 <= y0:
        return
    im = Image.new("L", ((x1 - x0) * 2, (y1 - y0) * 2), 0)
    dr = ImageDraw.Draw(im)
    n = len(pts)
    for i in range(n - 1):
        a = 1.0 if alpha is None else alpha[i]
        if a <= 0.01:
            continue
        dr.line([((pts[i][0] - x0) * 2, (pts[i][1] - y0) * 2),
                 ((pts[i + 1][0] - x0) * 2, (pts[i + 1][1] - y0) * 2)],
                fill=int(255 * a), width=max(int(width * 2), 1))
    im = im.reduce(2)
    core = np.asarray(im, np.float32) / 255
    g = np.asarray(im.filter(ImageFilter.GaussianBlur(glow)), np.float32) / 255
    frame[y0:y1, x0:x1] += (core[..., None] * 2.2 + g[..., None] * 2.5) * color


# ---------------------------------------------------------------- Post-Processing
_rng_grain = np.random.default_rng(3)
_GRAIN = [_rng_grain.normal(0, 1, (H // 2, W // 2)).astype(np.float32) for _ in range(6)]
_yy, _xx = np.mgrid[0:H, 0:W]
_VIGN = (1 - 0.55 * (((_xx - W / 2) / (W * 0.75)) ** 2 + ((_yy - H / 2) / (H * 0.62)) ** 2)).clip(0.25, 1)
_VIGN = _VIGN.astype(np.float32)[..., None]


def god_rays(frame, cam, S, strength):
    sx, sy, sz = cam.project(cam.pos + S * 1000)
    if np.dot(S, cam.fw) <= 0.05 or strength <= 0:
        return
    q = 6
    small = np.asarray(Image.fromarray(np.clip(frame * 40, 0, 255).astype(np.uint8)).resize(
        (W // q, H // q), Image.BILINEAR), np.float32) / 40
    lum = small.mean(-1)
    bright = np.clip(lum - 0.9, 0, 4)
    h, w = bright.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = sx / q, sy / q
    acc = np.zeros_like(bright)
    n = 28
    for i in range(n):
        s = 1 - i / n * 0.85
        px = np.clip(cx + (xx - cx) * s, 0, w - 1).astype(np.int32)
        py = np.clip(cy + (yy - cy) * s, 0, h - 1).astype(np.int32)
        acc += bright[py, px] * (1 - i / n)
    acc = gblur(acc / n, 2.5)
    rays = np.asarray(Image.fromarray(acc.astype(np.float32), "F").resize((W, H), Image.BILINEAR))
    frame += rays[..., None] * SUNCOL * strength * 1.4


def bloom(frame):
    small = frame[::4, ::4]
    br = np.clip(small - 0.85, 0, 8)
    out = np.zeros_like(frame)
    for rad, wgt in ((4, 0.5), (14, 0.35), (40, 0.3)):
        out += resize_f(gblur(br, rad / 4), W, H) * wgt
    frame += out


def grade(frame, i, exposure=1.0, fade=1.0):
    x = frame * exposure * _VIGN
    # ACES-ähnliche Tonkurve
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    x = np.clip((x * (a * x + b)) / (x * (c * x + d) + e), 0, 1)
    x = x ** (1 / 2.2)
    # Teal-Orange: Schatten leicht blaugrün, Lichter warm
    lum = x.mean(-1, keepdims=True)
    x = x + (1 - lum) ** 3 * np.array([-0.012, 0.018, 0.035]) * 1.6
    x = x * fade
    g = _GRAIN[i % len(_GRAIN)]
    g = np.repeat(np.repeat(g, 2, 0), 2, 1)[..., None]
    x = x + g * 0.018 * (0.5 + 0.5 * (1 - lum))
    return np.clip(x * 255 + 0.5, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- Text
_fonts = {}


def font(path, size):
    key = (path, size)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(path, size)
    return _fonts[key]


def text(img, s, cx, cy, size, fnt=ANTON, color=(255, 255, 255), alpha=1.0, track=0, anchor="mm",
         glow=0):
    if alpha <= 0.01:
        return
    f = font(fnt, size)
    # Laufweite manuell
    widths = [f.getlength(ch) for ch in s]
    total = sum(widths) + track * (len(s) - 1)
    pad = 40 + glow * 3
    hgt = int(size * 1.6)
    layer = Image.new("L", (int(total) + pad * 2, hgt + pad * 2), 0)
    dr = ImageDraw.Draw(layer)
    x = pad
    for ch, wch in zip(s, widths):
        dr.text((x, pad + hgt / 2), ch, font=f, fill=255, anchor="lm")
        x += wch + track
    if anchor == "mm":
        ox, oy = int(cx - layer.width / 2), int(cy - layer.height / 2)
    else:  # "lm"
        ox, oy = int(cx - pad), int(cy - layer.height / 2)
    a = np.asarray(layer, np.float32) / 255 * alpha
    reg = _clip_region(a, ox, oy)
    if reg is None:
        return
    fr, ar = reg
    if glow:
        gl = np.asarray(layer.filter(ImageFilter.GaussianBlur(glow)), np.float32) / 255 * alpha * 0.8
        img[fr] = np.clip(img[fr] + gl[ar][..., None] * np.array([255, 170, 90]) * 0.7, 0, 255)
    sh = gblur(a, size * 0.12)[ar][..., None]
    img[fr] = img[fr] * (1 - 0.55 * np.clip(sh * 1.6, 0, 1))
    aa = a[ar][..., None]
    img[fr] = img[fr] * (1 - aa) + np.array(color, np.float32) * aa


def fade_io(t, a, b, fi=0.35, fo=0.35):
    return clamp((t - a) / fi) * clamp((b - t) / fo)


GOLD = (255, 196, 120)


def label(img, t, a, b, num, title, sub=None, y=1330):
    al = fade_io(t, a, b, 0.4, 0.35)
    if al <= 0:
        return
    slide = (1 - ease_out((t - a) / 0.6)) * 40
    text(img, num, 90 - slide * 0.5, y - 70, 40, INTER.format("SemiBold"), GOLD, al, track=6, anchor="lm")
    img[int(y - 40):int(y - 37), 90:90 + int(70 * ease_out((t - a) / 0.7))] = \
        img[int(y - 40):int(y - 37), 90:90 + int(70 * ease_out((t - a) / 0.7))] * (1 - al) + np.array(GOLD) * al
    text(img, title, 90 + slide, y + 10, 104, ANTON, (255, 255, 255), al, track=4, anchor="lm")
    if sub:
        text(img, sub, 92 + slide * 1.5, y + 100, 40, INTER.format("Medium"), (235, 225, 210),
             al * 0.92, track=1, anchor="lm")


def stat(img, t, a, b, key, val, y, x=90):
    al = fade_io(t, a, b, 0.3, 0.3)
    if al <= 0:
        return
    text(img, key, x, y, 32, INTER.format("Medium"), (230, 215, 195), al * 0.85, track=5, anchor="lm")
    text(img, val, x, y + 58, 74, ANTON, (255, 255, 255), al, track=2, anchor="lm")


# ---------------------------------------------------------------- Shot-Definitionen
def orbit_cam(ang, rad, hgt, target, fov):
    a = math.radians(ang)
    pos = np.array([target[0] + math.sin(a) * rad, hgt, target[2] + math.cos(a) * rad])
    return Cam(pos, target, fov)


# Szene B-D: Zeit -> (T, Kamerawinkel)
BD_T = pchip([(0.0, -0.6), (1.0, 0.0), (3.6, 0.85), (4.6, 0.885), (5.5, 1.0), (6.4, 1.118)])
BD_ANG = pchip([(0.0, -6), (3.6, 14), (4.6, -95), (6.4, -112)])
E_T = pchip([(0.0, 1.112), (0.5, 1.126), (1.5, 1.1335), (2.2, 1.155)])
TAU_IMP = next(k / 1000 for k in range(2200) if E_T(k / 1000) >= T_IMPACT)


def state(t):
    """Alles, was einen Frame beschreibt."""
    s = {"t": t, "trace": None, "rays": 1.0, "dof": 1.2, "rim": 4.0, "blades": False, "fx": None}
    if t < B0:
        tau = t - A0
        z = 15.5 - 3.0 * smooth(tau / 3.0)
        cam = Cam([0.45, 0.7, z], [0.0, 1.25, 0.0], 21)
        s.update(T=-1.0, cam=cam, sun=(2.0, 1.6), tau=tau, shot="A", dof=1.6, rim=3.0)
    elif t < E0:
        tau = t - B0
        T = BD_T(tau)
        cam = orbit_cam(BD_ANG(tau), 4.4, 1.05, np.array([0.0, 0.98, 0.35]), 37)
        s.update(T=T, cam=cam, sun=(16.0, 3.0), tau=tau, shot="B", rim=4.5)
        if tau > 1.0:
            s["trace"] = (0.0, T, 1.0)
    elif t < F0:
        tau = t - E0
        T = E_T(tau)
        tgt = BALL0 + np.array([0.0, 0.035, 0.0]) + np.array([0.08, 0.03, 0]) * smooth((tau - 1.3) / 0.9)
        cam = Cam(BALL0 + np.array([-0.55, 0.05, 0.92 - 0.08 * tau]), tgt, 30)
        s.update(T=T, cam=cam, sun=(7.0, 1.8), tau=tau, shot="E", dof=2.6, rim=6.0, blades=True,
                 rays=1.0)
    elif t < G0:
        tau = t - F0
        T = 1.16 + tau * 0.9
        tb = (1.16 - T_IMPACT) + tau * 1.55
        bp = ball_pos(tb)
        look = np.array([60.0, 2.0 + 10 * smooth(tau / 3.0), BALL0[2] + 0.2])
        cam = Cam([-4.3 - 0.5 * tau, 1.25, BALL0[2] - 0.3], look, 42)
        s.update(T=T, cam=cam, sun=(-14.0, 3.0), tau=tau, shot="F", tb=tb, ball=bp, dof=1.0, rim=3.5)
    else:
        tau = t - G0
        cam = orbit_cam(22 + 9 * tau / 6.2, 3.3 - 0.25 * smooth(tau / 3.0), 0.42,
                        np.array([0.05, 1.12, 0.25]), 42)
        s.update(T=1.8 + 0.02 * math.sin(tau), cam=cam, sun=(-13.0, 2.6), tau=tau, shot="G", rim=4.5)
        s["trace"] = (0.0, 1.8 * smooth((tau - 0.4) / 1.8), clamp(1 - (tau - 3.4) / 1.0))
    return s


# ---------------------------------------------------------------- Rendering
BLADES = None


def make_blades():
    rng = np.random.default_rng(11)
    out = []
    for _ in range(1400):
        x = BALL0[0] + rng.uniform(-0.35, 0.4)
        z = BALL0[2] + rng.uniform(-0.35, 0.3)
        h = rng.uniform(0.006, 0.014)
        lean = rng.normal(0, 0.003, 2)
        out.append((np.array([x, 0, z]), np.array([x + lean[0], h, z + lean[1]])))
    return out


def tee_prims(T):
    if T < T_IMPACT + 0.002:
        base = np.array([BALL0[0], 0.0, BALL0[2]])
        top = np.array([BALL0[0], BALL0[1] - BALL_R, BALL0[2]])
        return [("cap", [base, top], 0.006), ("cap", [top - Y * 0.003, top], 0.012)]
    dt = T - T_IMPACT
    base = np.array([BALL0[0] + dt * 2.0, max(0.0, dt * 1.2 - 4.9 * dt * dt), BALL0[2]])
    ang = dt * 40
    dirv = norm(np.array([math.sin(ang), math.cos(ang), 0]))
    top = base + dirv * 0.024
    return [("cap", [base, top], 0.006), ("cap", [top - dirv * 0.003, top], 0.012)]


def particles(frame, cam, T):
    """Grasstückchen & Staub nach dem Treffmoment."""
    dt = T - T_IMPACT
    if dt <= 0:
        return
    rng = np.random.default_rng(5)
    n = 70
    v = np.stack([rng.uniform(0.5, 9, n), rng.uniform(0.3, 4, n), rng.normal(0, 1.4, n)], 1)
    p = BALL0 - Y * 0.04 + v * dt + np.array([0, -4.9, 0]) * dt * dt
    for k in range(n):
        x, y, z = cam.project(p[k])
        if not (0 <= x < W and 0 <= y < H) or z < 0.05:
            continue
        r = max(0.004 * cam.f / z * (0.4 + (k % 5) * 0.15), 1.0)
        rr = int(r * 3) + 2
        xs, ys = np.meshgrid(np.arange(-rr, rr + 1), np.arange(-rr, rr + 1))
        g = np.exp(-(xs**2 + ys**2) / (2 * r * r))[..., None]
        col = np.array([1.2, 0.8, 0.45]) if k % 3 else np.array([0.35, 0.45, 0.12])
        _blit_add(frame, g * col * 0.9, int(x) - rr, int(y) - rr)


def render(i):
    t = i / FPS
    st = state(t)
    cam, T = st["cam"], st["T"]
    S = cam.sun(*st["sun"])
    frame = upscale(background(cam, S), st["dof"])

    # Schwungbahn (Schlagkopf) als goldene Linie
    if st["trace"]:
        ta, tb_, al = st["trace"]
        if tb_ > ta + 0.01 and al > 0:
            ts = np.linspace(ta, tb_, 240)
            pts = [cam.project(face_center(x))[:2] for x in ts]
            alpha = [al * (0.25 + 0.75 * k / len(ts)) for k in range(len(ts))]
            glow_line(frame, pts, np.array([1.0, 0.62, 0.28]) * 0.55, 2.2, 9, alpha)

    ball_before = st["shot"] != "F"
    flying = T > T_IMPACT
    if st["shot"] == "F":
        bp = st["ball"]
    else:
        bp = ball_pos((T - T_IMPACT) * 1.0) if flying else BALL0

    # Bewegungsunschärfe: Schlägerkopien über das Belichtungsintervall
    dT = abs(state(t + 1 / FPS)["T"] - T) * 0.6 if t + 1 / FPS < DURATION else 0
    clubs = [(club_prims(T) + tee_prims(T), 1.0)]
    nb = int(min(max(dT / 0.004, 0), 14))
    for k in range(1, nb + 1):
        tt = T - dT * k / (nb + 1)
        clubs.append((club_prims(tt), (1 - k / (nb + 1)) * 0.75))

    if st["blades"]:
        # Nahaufnahme: Tiefenstaffelung Körper -> Gras hinten -> Ball -> Schläger -> Gras vorn
        global BLADES
        if BLADES is None:
            BLADES = make_blades()
        silhouette(frame, cam, S, [(pose(T), 1.0)], st["rim"], 0.6)
        back = [("cap", [a, b], 0.0012) for a, b in BLADES if a[2] <= BALL0[2] + 0.02]
        silhouette(frame, cam, S, [(back, 1.0)], 2.0, 0.35)
        if not flying:
            draw_ball(frame, cam, S, bp)
        silhouette(frame, cam, S, clubs, st["rim"])
        if flying:
            sq = math.exp(-((T - T_IMPACT) / 0.0012) ** 2) if T - T_IMPACT < 0.004 else 0
            draw_ball(frame, cam, S, bp, spin=(T - T_IMPACT) * 280, squash=sq)
        front = [("cap", [a, b], 0.0012) for a, b in BLADES if a[2] > BALL0[2] + 0.02]
        silhouette(frame, cam, S, [(front, 1.0)], 2.0, 0.35)
    else:
        if ball_before and not flying:
            draw_ball(frame, cam, S, bp)
        silhouette(frame, cam, S, [(pose(T) + clubs[0][0], 1.0)] + clubs[1:], st["rim"])
        if ball_before and flying:
            draw_ball(frame, cam, S, bp, spin=(T - T_IMPACT) * 280)
    if st["blades"]:
        particles(frame, cam, T)
        dt = T - T_IMPACT
        if 0 < dt < 0.02:  # Schockwelle & Blitz
            x, y, _ = cam.project(BALL0)
            rad = 40 + dt * 26000
            pts = [(x + math.cos(a) * rad, y + math.sin(a) * rad * 0.35)
                   for a in np.linspace(0, 2 * math.pi, 90)]
            glow_line(frame, pts, np.array([1.0, 0.8, 0.6]) * 0.6 * (1 - dt / 0.02), 2, 10)
        if dt > 0:
            frame += np.float32(1.6 * math.exp(-(st["tau"] - TAU_IMP) / 0.07))

    if st["shot"] == "F":
        tb = st["tb"]
        ts = FLIGHT_T[FLIGHT_T <= tb]
        if len(ts) > 2:
            idx = np.linspace(0, len(ts) - 1, min(len(ts), 160)).astype(int)
            pts = [cam.project(FLIGHT_P[k])[:2] for k in idx]
            alpha = [0.15 + 0.85 * (k / len(idx)) for k in range(len(idx))]
            glow_line(frame, pts, np.array([1.0, 0.62, 0.32]) * 1.1, 3.0, 12, alpha)
        draw_ball(frame, cam, S, st["ball"])

    god_rays(frame, cam, S, st["rays"])
    bloom(frame)

    fade = 1.0
    if t < 0.8:
        fade = smooth(t / 0.8)
    if t > H0:
        fade = 1 - 0.78 * smooth((t - H0) / 0.9)
    if t > END - 0.6:
        fade *= clamp((END - t) / 0.6)
    img = grade(frame, i, 1.0, fade).astype(np.float32)
    overlays(img, st)
    return img.astype(np.uint8)


def overlays(img, st):
    t, tau, shot = st["t"], st["tau"], st["shot"]
    if shot == "A":
        al = fade_io(tau, 0.6, 3.0, 0.8, 0.45)
        sp = 8 + 10 * tau
        text(img, "DER PERFEKTE", W / 2, 470, 50, INTER.format("Medium"), (240, 225, 205), al, track=sp)
        text(img, "SCHWUNG", W / 2, 600, 210, ANTON, (255, 255, 255), al, track=6 + 3 * tau, glow=18)
        text(img, "IN ZEITLUPE", W / 2, 745, 34, INTER.format("Medium"), GOLD, al * 0.95,
             track=sp * 0.9)
    elif shot == "B":
        label(img, tau, 0.25, 1.15, "01", "ADRESSE", "Stabile Basis. Ruhiger Kopf.")
        label(img, tau, 1.35, 3.45, "02", "AUSHOLEN", "Breit und langsam zurück.")
        label(img, tau, 3.55, 4.6, "03", "TOP", "90° Schulterdrehung")
        label(img, tau, 4.75, 6.6, "04", "ÜBERGANG", "Hüfte zuerst. Winkel halten.")
    elif shot == "E":
        label(img, tau, 0.05, 2.4, "05", "TREFFMOMENT", "Kontakt: 0,0004 Sekunden", y=1320)
        stat(img, tau, 0.9, 2.4, "SCHLÄGERKOPF", "182 KM/H", 330)
        stat(img, tau, 1.25, 2.4, "BALL", "269 KM/H", 480)
    elif shot == "F":
        stat(img, tau, 0.3, 4.2, "ABFLUGWINKEL", "10,9°", 300)
        stat(img, tau, 0.6, 4.2, "BACKSPIN", "2.686 U/MIN", 450)
        carry = min(max(st["ball"][0] - BALL0[0], 0), CARRY)
        stat(img, tau, 0.9, 4.2, "CARRY", f"{carry:.0f} M", 600)
    elif shot == "G":
        label(img, tau, 0.4, 2.9, "06", "FINISH", "Balance halten. Zum Ziel zeigen.")
        if tau > 3.0:
            a = fade_io(tau, 3.1, 7.0, 0.6, 0.6)
            text(img, "TEMPO", W / 2, 620, 46, INTER.format("Medium"), GOLD, a, track=18)
            text(img, "3 : 1", W / 2, 760, 220, ANTON, (255, 255, 255), a, track=8, glow=16)
            for k, line in enumerate(["Langsam ausholen.", "Explosiv durchschwingen.",
                                      "Im Gleichgewicht enden."]):
                al = fade_io(tau, 3.6 + k * 0.35, 7.0, 0.5, 0.6)
                text(img, line, W / 2, 960 + k * 66, 44, INTER.format("Medium"), (240, 230, 215),
                     al, track=1)
            al = fade_io(tau, 4.8, 7.0, 0.6, 0.6)
            text(img, "DER PERFEKTE SCHWUNG", W / 2, 1260, 34, INTER.format("SemiBold"), GOLD,
                 al * 0.9, track=10)


# ---------------------------------------------------------------- Audio
SR = 44100


def bandnoise(n, lo, hi, rng):
    x = rng.standard_normal(n)
    f = np.fft.rfft(x)
    fr = np.fft.rfftfreq(n, 1 / SR)
    f[(fr < lo) | (fr > hi)] = 0
    y = np.fft.irfft(f, n)
    return y / (np.abs(y).max() + 1e-9)


def sweep_noise(n, f0, f1, rng, bw=0.5):
    """Rauschen mit gleitendem Bandpass (Overlap-Add)."""
    blk = 4096
    hop = blk // 2
    out = np.zeros(n + blk)
    win = np.hanning(blk)
    fr = np.fft.rfftfreq(blk, 1 / SR)
    for s in range(0, n, hop):
        k = s / max(n - 1, 1)
        fc = f0 * (f1 / f0) ** k
        g = np.exp(-0.5 * (np.log(np.maximum(fr, 1) / fc) / bw) ** 2)
        seg = np.fft.irfft(np.fft.rfft(rng.standard_normal(blk) * win) * g, blk)
        out[s:s + blk] += seg * win
    out = out[:n]
    return out / (np.abs(out).max() + 1e-9)


def conv(x, ir):
    n = len(x) + len(ir)
    m = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)[:len(x)]


def make_audio(path):
    n = int(DURATION * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(2)
    L = np.zeros(n)
    Rr = np.zeros(n)

    def add(sig, at, gain=1.0, pan=0.0):
        s = int(at * SR)
        e = min(n, s + len(sig))
        if s < n and e > s:
            L[s:e] += sig[:e - s] * gain * (1 - pan) ** 0.5
            Rr[s:e] += sig[:e - s] * gain * (1 + pan) ** 0.5

    def env(a, b, fi, fo):
        return np.clip((t - a) / fi, 0, 1) * np.clip((b - t) / fo, 0, 1)

    # Wind / Atmosphäre
    wind = bandnoise(n, 80, 900, rng) * (0.5 + 0.5 * np.sin(t * 0.7) ** 2)
    add(wind * 0.05 * (1 - 0.8 * env(E0 + 0.3, F0, 0.2, 0.1)), 0)

    # Vögel zu Beginn
    for k, at in enumerate([0.6, 1.25, 1.4, 2.3, 16.3, 16.45, 17.6]):
        dur = 0.12
        tt = np.arange(int(dur * SR)) / SR
        f = 3400 + 900 * np.sin(tt * 60) + k * 120
        chirp = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / dur) ** 2
        add(chirp, at, 0.025, pan=0.6 if k % 2 else -0.5)

    # Flächen-Pad (Akkorde, langsame Schwellung)
    def pad(freqs, a, b, gain):
        e = env(a, b, 1.2, 1.2)
        sig = np.zeros(n)
        for fq in freqs:
            for det in (-0.12, 0.0, 0.13):
                sig += np.sin(2 * np.pi * (fq + det) * t + rng.uniform(0, 6))
        sig *= (0.7 + 0.3 * np.sin(t * 0.9))
        add(sig * e / len(freqs) / 3, 0, gain)

    pad([73.42, 110.0, 146.83, 174.61, 220.0], 0.0, 4.4, 0.20)       # Dm
    pad([58.27, 116.54, 146.83, 174.61, 233.08], 3.6, 9.25, 0.20)     # Bb
    pad([87.31, 130.81, 174.61, 220.0, 261.63], F0 - 0.1, G0 + 0.8, 0.22)  # F
    pad([73.42, 110.0, 146.83, 185.0, 220.0, 293.66], G0 + 0.2, END, 0.22)  # D-Dur

    # Riser vor dem Treffmoment
    rs, re_ = 6.6, 9.85
    m = int((re_ - rs) * SR)
    tr = np.arange(m) / SR
    riser = sweep_noise(m, 300, 6000, rng, 0.35) * (tr / tr[-1]) ** 2.2
    tone = np.sin(2 * np.pi * np.cumsum(110 * 2 ** (tr / tr[-1] * 2.0)) / SR) * (tr / tr[-1]) ** 2
    add(riser * 0.20 + tone * 0.06, rs)

    # Schwung-Whoosh (Zeitlupe, tief)
    m = int(2.2 * SR)
    tw = np.arange(m) / SR
    wh = sweep_noise(m, 120, 700, rng, 0.4) * np.sin(np.pi * tw / tw[-1]) ** 2
    add(wh, B0 + 4.5, 0.25, pan=-0.3)

    # Treffmoment: Stille, dann Klick + Sub + Hall
    imp = E0 + 0.95
    gap = (t > imp - 0.35) & (t < imp)
    L[gap] *= 0.12
    Rr[gap] *= 0.12
    tc = np.arange(int(0.05 * SR)) / SR
    click = rng.standard_normal(len(tc)) * np.exp(-tc * 260) + np.sin(2 * np.pi * 3200 * tc) * np.exp(-tc * 120)
    tb = np.arange(int(2.5 * SR)) / SR
    boom = np.sin(2 * np.pi * (38 + 90 * np.exp(-tb * 18)) * tb) * np.exp(-tb * 2.2)
    ir = rng.standard_normal(int(2.8 * SR)) * np.exp(-np.arange(int(2.8 * SR)) / SR * 2.4)
    hit = np.zeros(int(3.0 * SR))
    hit[:len(click)] += click * 0.9
    hit[:len(boom)] += boom * 0.9
    tail = conv(hit, ir)
    tail /= np.abs(tail).max()
    add(hit, imp, 0.85)
    add(tail, imp, 0.35)

    # Ballflug: hohes, fallendes Pfeifen
    m = int(3.8 * SR)
    tf = np.arange(m) / SR
    fl = sweep_noise(m, 4500, 1200, rng, 0.25) * np.exp(-tf * 0.8) * np.clip(tf / 0.05, 0, 1)
    add(fl, F0 + 0.05, 0.12, pan=0.2)
    add(boom[:int(1.5 * SR)] * 0.6, F0, 0.4)
    add(boom * 0.7, G0, 0.35)
    add(boom * 0.8, G0 + 3.05, 0.45)

    # Sanfte Melodie im Finale
    for k, (fq, at) in enumerate([(587.33, G0 + 3.2), (739.99, G0 + 3.55), (880.0, G0 + 3.9),
                                  (1174.66, G0 + 4.6)]):
        tt = np.arange(int(2.5 * SR)) / SR
        note = (np.sin(2 * np.pi * fq * tt) + 0.3 * np.sin(2 * np.pi * fq * 2 * tt)) * np.exp(-tt * 1.8)
        add(note, at, 0.06, pan=-0.3 + 0.2 * k)

    out = np.stack([L, Rr], 1)
    fade = np.clip(t / 0.5, 0, 1) * np.clip((DURATION - t) / 1.2, 0, 1)
    out *= fade[:, None]
    out /= np.abs(out).max() * 1.12
    pcm = (out * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ---------------------------------------------------------------- main
def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--preview":
        for s in sys.argv[2:]:
            tt = float(s)
            Image.fromarray(render(int(round(tt * FPS)))).save(HERE / f"preview_{tt:05.2f}.png")
        return
    audio = HERE / "audio_swing.wav"
    make_audio(audio)
    n_frames = int(DURATION * FPS)
    out = HERE / "swing_cinematic.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(audio),
           "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool() as pool:
        for k, fr in enumerate(pool.imap(render, range(n_frames), chunksize=2)):
            proc.stdin.write(fr.tobytes())
            if k % 60 == 0:
                print(f"{k}/{n_frames}", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(render(int(10.3 * FPS))).save(HERE / "swing_thumbnail.jpg", quality=92)
    print(f"fertig: {out}  (Carry {CARRY:.0f} m)")


if __name__ == "__main__":
    main()
