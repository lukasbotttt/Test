"""Reel 15: THE PUCK – cleanes 3D-Motion-Video in einer einzigen Kamerafahrt (15 s, Loop).

Ablauf:
  0.0–0.3   Puck fällt in Zeitlupe ins Bild (Loop-Naht), landet bei 0.3
  0.3–2.3   01 COLD: Frost wächst über den Puck – "EVERY NHL PUCK / IS FROZEN."
  2.3–4.6   02 SIZE: Frost verdampft, Kamera steigt, Maßlinien 3 IN / 1 IN, "SOLID RUBBER."
  4.6–5.1   Kamera schwingt hinter den Puck
  5.1–7.95  03 SPEED: Schuss, Verfolgungsfahrt, Zähler 108.8 MPH (Chara, 2012)
  7.95–9.8  04 TARGET: Tor, Netz beult aus, Maßlinien 6 FT / 4 FT
  9.8–12.2  05 ICE: Kranfahrt in die Draufsicht, Spielfeldlinien zeichnen sich, 200 x 85 FT
  12.2–15.0 Sturzflug zurück zur Startposition, "WHICH ONE DID YOU KNOW?" – Loop
3D: puck3d.py (numba-Raytracer). Vektorgrafik: cairo. Text: Inter.
Fakten: NHL-Puck 3" x 1", 5,5–6 oz, Hartgummi, vor Spielen gefroren (springt weniger);
Härtester Schuss (NHL-Rekord) 108,8 mph, Zdeno Chara, All-Star Skills 2012; Tor 6 x 4 ft; Eisfläche 200 x 85 ft.
Aufruf: python3 reel15_puck.py  ->  reel15_puck.mp4
"""
import math
import os
import subprocess
import sys
import time
import wave

import cairocffi as cairo
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import puck3d as P3

W, H, FPS = 1080, 1920, 30
DUR = 15.0
SPP = 8
KSUB = 12
SHUTTER = 0.5 / FPS
HERE = os.path.dirname(os.path.abspath(__file__))
INTER = os.path.join(HERE, "fonts", "Inter.ttf")

INK = (16, 17, 22)
ORANGE = (240, 100, 20)
ICEBLUE = (28, 126, 255)
GREY = (104, 108, 120)
POST_RED = (206, 30, 38)

HP = np.array([-60.0, 0.0, -84.0])                 # Startpunkt des Pucks (freies Eis im Mittelkreis)
T0 = HP + np.array([0.0, 0.5, 0.0])
GOAL_X = 1068.0
G2 = np.array([GOAL_X, 22.0, 0.0])
U = np.array([GOAL_X - HP[0], 0.0, -HP[2]])
U /= np.linalg.norm(U)
UPERP = np.array([-U[2], 0.0, U[0]])
THETA0 = -2.48                                     # Logo lesbar aus der Maßlinien-Perspektive
TOP_C = np.array([424.0, 0.0, 0.0])                # Draufsicht: Spielfeld unter dem Textblock
TOP_H = 6322.0
T_LAND, G_EFF = 0.14, 92.0                        # Zeitlupen-Fall (Bild 0: Puck kurz vor dem Aufprall)
T_SHOT, T_GOAL = 5.10, 7.95
T_HIT = T_GOAL + 0.04
S_STOP = 905.0


# ================================================================= Easing
def c01(x):
    return 0.0 if x < 0 else (1.0 if x > 1 else x)


def smooth(a, b, x):
    t = c01((x - a) / (b - a))
    return t * t * (3 - 2 * t)


def sio(x):
    return 0.5 - 0.5 * math.cos(math.pi * c01(x))


def smoother(x):
    x = c01(x)
    return x * x * x * (x * (6 * x - 15) + 10)


def e_out(x, p=3):
    return 1 - (1 - c01(x)) ** p


def e_in(x, p=3):
    return c01(x) ** p


def e_back(x, s=1.7):
    x = c01(x) - 1
    return x * x * ((s + 1) * x + s) + 1


def lerp(a, b, t):
    return a + (b - a) * t


def sph(T, r, az, el):
    a, e = math.radians(az), math.radians(el)
    return T + r * np.array([math.cos(e) * math.cos(a), math.sin(e), math.cos(e) * math.sin(a)])


def blend_up(el):
    w = smooth(55.0, 89.0, el)
    u = np.array([w, 1 - w, 0.0])
    return u / np.linalg.norm(u)


# ================================================================= Puck
def _shot_table():
    xs = np.linspace(0, 1, 4001)
    v = np.array([smooth(0, 0.16, x) * (1 - 0.4 * x) for x in xs])
    s = np.concatenate([[0], np.cumsum((v[1:] + v[:-1]) / 2 * np.diff(xs))])
    return xs, s / s[-1] * 1150, v[-1] / s[-1] * 1150 / (T_GOAL - T_SHOT)


SHOT_X, SHOT_S, V_END = _shot_table()


def s_puck(t):
    if t < T_SHOT:
        return 0.0
    x = (t - T_SHOT) / (T_GOAL - T_SHOT)
    if x <= 1:
        return float(np.interp(x, SHOT_X, SHOT_S))
    tau = t - T_GOAL
    v = V_END
    a = v * v / 16
    ts = v / a
    if tau < ts:
        return 1150 + v * tau - 0.5 * a * tau * tau
    return 1158 - 3 * smooth(0, 0.3, tau - ts)


def frost_at(t):
    if t < 0.32 or t > 2.75:
        return 0.0
    f = 0.88 * e_out((t - 0.32) / 0.7, 2.2)
    return f * (1 - e_in((t - 2.3) / 0.45, 2))


def puck_state(t):
    """-> (Position, Drehung, sichtbar, Frost)"""
    t = t % DUR
    if t >= 14.7 or t < T_LAND + 0.2:
        tl = t - DUR if t >= 14.7 else t
        if tl < T_LAND:
            y = 0.5 + 0.5 * G_EFF * (T_LAND - tl) ** 2
        else:
            y = 0.5 + 0.18 * math.sin(math.pi * c01((tl - T_LAND) / 0.14))
        return np.array([HP[0], y, HP[2]]), THETA0, 1.0, frost_at(t)
    if 10.9 <= t < 14.7:
        return np.array([HP[0], 300.0, HP[2]]), THETA0, 0.0, 0.0
    s = s_puck(t)
    pos = HP + U * s + np.array([0.0, 0.5, 0.0])
    spin = 0.0 if t < T_SHOT else 2 * math.pi * 5 * 2.0 * (1 - math.exp(-(t - T_SHOT) / 2.0))
    return pos, THETA0 + spin, 1.0, frost_at(t)


# ================================================================= Kamera
KT = np.array([0.0, 2.4, 3.6, 4.55, T_SHOT])
KEYS = {"r": [11.0, 9.6, 16.5, 17.5, 9.0], "az": [192.0, 199.0, 220.0, 232.0, 184.26],
        "el": [9.0, 11.0, 38.0, 50.0, 7.0], "fov": [34.0, 34.0, 34.0, 34.0, 40.0],
        "ap": [0.15, 0.15, 0.11, 0.09, 0.05]}


def hermite(t, ts, vs):
    """Kubische Hermite-Kurve mit Catmull-Rom-Tangenten, Tangente 0 an den Enden."""
    vs = np.asarray(vs, float)
    n = len(ts)
    m = np.zeros(n)
    for i in range(1, n - 1):
        m[i] = (vs[i + 1] - vs[i - 1]) / (ts[i + 1] - ts[i - 1])
    i = int(np.clip(np.searchsorted(ts, t) - 1, 0, n - 2))
    h = ts[i + 1] - ts[i]
    x = c01((t - ts[i]) / h)
    h00, h10, h01, h11 = 2 * x ** 3 - 3 * x ** 2 + 1, x ** 3 - 2 * x ** 2 + x, -2 * x ** 3 + 3 * x ** 2, x ** 3 - x ** 2
    return h00 * vs[i] + h10 * h * m[i] + h01 * vs[i + 1] + h11 * h * m[i + 1]


def _follow_table():
    dt = 1 / 1200
    ts = np.arange(T_SHOT, 9.8 + dt, dt)
    sp = np.array([s_puck(t) for t in ts])
    vp = np.gradient(sp, dt)
    lag = 8.93 + 13.0 * np.array([smooth(T_SHOT, T_SHOT + 0.7, t) for t in ts])
    dlag = np.gradient(lag, dt)
    sc = np.empty_like(ts)
    s = -8.93
    for k, t in enumerate(ts):
        sc[k] = s
        v = vp[k] - dlag[k]
        v = max(0.0, min(v, 3.0 * (S_STOP - s)))
        v += 6.0 * smooth(7.9, 8.5, t) * (1 - smooth(9.2, 9.8, t))
        s += v * dt
    return ts, sc


FOLLOW_T, FOLLOW_S = _follow_table()


def cam_follow(t):
    s = float(np.interp(t, FOLLOW_T, FOLLOW_S))
    h = 1.597 + 4.0 * smooth(T_SHOT, 6.0, t) + 21.0 * smooth(6.6, 8.0, t)
    lat = -14.0 * smooth(6.6, 8.0, t)
    pos = HP + U * s + np.array([0.0, h, 0.0]) + UPERP * lat
    ppos, _, _, _ = puck_state(t)
    look = ppos + U * 22.0 * smooth(T_SHOT, T_SHOT + 0.5, t)
    tgt = look * (1 - smooth(6.8, 7.9, t)) + G2 * smooth(6.8, 7.9, t)
    fov = 40.0 + 8.0 * smooth(T_SHOT, 6.0, t) + 2.0 * smooth(6.6, 8.0, t)
    ap = 0.05 * (1 - smooth(T_SHOT, 7.0, t))
    focus = float(np.linalg.norm(ppos - pos)) * (1 - smooth(6.8, 7.9, t)) + float(np.linalg.norm(G2 - pos)) * smooth(6.8, 7.9, t)
    return pos, tgt, np.array([0.0, 1.0, 0.0]), fov, ap, focus


_F0 = cam_follow(9.8)[0] - G2
F_R0 = float(np.linalg.norm(_F0))
F_EL0 = math.degrees(math.asin(_F0[1] / F_R0))
F_AZ0 = math.degrees(math.atan2(_F0[2], _F0[0])) % 360


def camera(t):
    """-> (pos, target, up, fov, aperture, focus)"""
    t = t % DUR
    if t < T_SHOT:
        r, az, el = hermite(t, KT, KEYS["r"]), hermite(t, KT, KEYS["az"]), hermite(t, KT, KEYS["el"])
        fov, ap = hermite(t, KT, KEYS["fov"]), hermite(t, KT, KEYS["ap"])
        return sph(T0, r, az, el), T0.copy(), np.array([0.0, 1.0, 0.0]), fov, ap, r
    if t < 9.8:
        return cam_follow(t)
    if t < 12.2:                                    # Kranfahrt in die Draufsicht
        x = (t - 9.8) / 2.4
        tgt = G2 + (TOP_C - G2) * sio(x)
        r = math.exp(lerp(math.log(F_R0), math.log(TOP_H), smoother(x)))
        el = lerp(F_EL0, 89.9, sio(x) * 0.35 + smoother(x) * 0.65)
        fov = lerp(50.0, 30.0, sio(x))
        return sph(tgt, r, F_AZ0, el), tgt, blend_up(el), fov, 0.0, r
    x = (t - 12.2) / 2.8                            # Sturzflug zurück
    tgt = TOP_C + (T0 - TOP_C) * smooth(0.0, 0.7, x)
    r = math.exp(lerp(math.log(TOP_H), math.log(11.0), smoother(x)))
    el = lerp(89.9, 9.0, smooth(0.25, 1.0, x))
    az_end = 192.0 if abs(192.0 - F_AZ0) < 180 else 192.0 + 360.0
    az = lerp(F_AZ0, az_end, smooth(0.2, 1.0, x))
    fov = lerp(30.0, 34.0, smoother(x))
    ap = 0.15 * smooth(60.0, 11.0, r)
    return sph(tgt, r, az, el), tgt, blend_up(el), fov, ap, r


def cam_row(t):
    pos, tgt, up, fov, ap, focus = camera(t)
    r, u, f = P3.look_at(pos, tgt, up)
    return P3.cam_row(pos, r, u, f, fov), ap, focus


# ================================================================= 3D-Rendern
_LOGO = None


def logo_tex():
    global _LOGO
    if _LOGO is None:
        im = Image.open(os.path.join(HERE, "brand", "bladesandpucks_mark_transparent.png")).convert("RGBA")
        _LOGO = np.ascontiguousarray(np.asarray(im.resize((256, 256), Image.LANCZOS)).astype(np.float32) / 255)
    return _LOGO


def render3d(t, fidx):
    cams = np.zeros((KSUB, 13))
    lens = np.zeros((KSUB, 2))
    pk = np.zeros((KSUB, 7))
    for k in range(KSUB):
        tk = t + ((k + 0.5) / KSUB - 0.5) * SHUTTER
        row, ap, focus = cam_row(tk)
        cams[k], lens[k] = row, (ap, focus)
        pos, th, vis, fr = puck_state(tk)
        pk[k] = (pos[0], pos[1], pos[2], th, vis, fr, tk)
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, SPP, fidx + 1, cams, lens, pk, logo_tex(), base, puck, cov)
    return P3.tonemap(base), P3.tonemap(puck), cov


# ================================================================= Vektor-Ebenen (cairo)
def surface():
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    return s, cairo.Context(s)


def surf_rgba(s):
    """cairo-Fläche -> (vormultipliziertes RGB, Alpha) als float 0..1."""
    s.flush()
    a = np.frombuffer(s.get_data(), np.uint8).reshape(H, W, 4).astype(np.float32) / 255
    return a[..., [2, 1, 0]], a[..., 3:4]


def over(dst, rgb_pm, a):
    return dst * (1 - a) + rgb_pm


def proj(cam, pts):
    xy, z = P3.project(cam, np.asarray(pts, float).reshape(-1, 3), W, H)
    return xy, z


def px_per_in(cam, z):
    return (H / 2) / (cam[12] * np.maximum(z, 1e-3))


def stroke_poly(ctx, xy, col, alpha, width, cap=cairo.LINE_CAP_ROUND):
    ctx.set_source_rgba(col[0] / 255, col[1] / 255, col[2] / 255, alpha)
    ctx.set_line_width(width)
    ctx.set_line_cap(cap)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.move_to(*xy[0])
    for p in xy[1:]:
        ctx.line_to(*p)
    ctx.stroke()


def partial(xy, frac):
    """Polylinie nur bis zum Anteil frac ihrer Länge (Draw-on)."""
    if frac >= 1:
        return xy
    seg = np.linalg.norm(np.diff(xy, axis=0), axis=1)
    L = seg.sum() * frac
    out, acc = [xy[0]], 0.0
    for i, l in enumerate(seg):
        if acc + l >= L:
            out.append(xy[i] + (xy[i + 1] - xy[i]) * ((L - acc) / max(l, 1e-6)))
            break
        out.append(xy[i + 1])
        acc += l
    return np.array(out)


# ---------------- Tornetz
PHI = np.linspace(0, math.pi, 25)


def net_offset(p, w, t):
    tau = t - T_HIT
    if tau <= 0:
        return p
    A = 9.0 * (1 - math.exp(-tau / 0.03)) * math.exp(-tau * 4.5) * math.cos(2 * math.pi * 1.8 * tau)
    d2 = np.sum((p - np.array([GOAL_X + 36, 4.0, 2.0])) ** 2, axis=-1)
    disp = A * np.exp(-d2 / (2 * 16.0 ** 2)) * w
    q = p.copy()
    q[..., 0] += disp
    return q


def net_lines(t):
    base = np.stack([GOAL_X + 40 * np.sin(PHI), np.zeros_like(PHI), -36 * np.cos(PHI)], 1)
    top = np.stack([GOAL_X + 20 * np.sin(PHI), np.full_like(PHI, 48.0), -36 * np.cos(PHI)], 1)
    mesh = []
    for v in np.linspace(0, 1, 9)[1:-1]:                       # waagrechte Maschen (Seiten + Rückwand)
        pts = base + (top - base) * v
        w = np.sin(PHI) * math.sin(math.pi * v)
        mesh.append(net_offset(pts, w, t))
    for i in range(1, len(PHI) - 1, 2):                        # senkrechte Maschen
        v = np.linspace(0, 1, 10)[:, None]
        pts = base[i] + (top[i] - base[i]) * v
        w = math.sin(PHI[i]) * np.sin(math.pi * v[:, 0])
        mesh.append(net_offset(pts, w, t))
    for z in np.linspace(-30, 30, 7):                          # Dach
        d = 20 * math.sqrt(max(0.0, 1 - (z / 36) ** 2))
        u = np.linspace(0, 1, 6)[:, None]
        pts = np.array([GOAL_X, 48.0, z]) + np.array([d, 0.0, 0.0]) * u
        mesh.append(net_offset(pts, (1 - abs(z) / 36) * np.sin(math.pi * u[:, 0]) * 0.4, t))
    frame_white = [base]
    frame_red = [np.array([[GOAL_X, 0, -36], [GOAL_X, 48, -36]], float),
                 np.array([[GOAL_X, 0, 36], [GOAL_X, 48, 36]], float),
                 np.array([[GOAL_X, 48, -36], [GOAL_X, 48, 36]], float)]
    return mesh, frame_white, frame_red


def draw_net(cam, t, front):
    s, ctx = surface()
    mesh, fw_, fr_ = net_lines(t)
    if not front:
        for pl in mesh:
            xy, z = proj(cam, pl)
            if (z < 2).any():
                continue
            wdt = float(np.clip(0.45 * px_per_in(cam, z.mean()), 0.8, 2.6))
            stroke_poly(ctx, xy, (96, 106, 122), 0.7, wdt)
        for pl in fw_:
            xy, z = proj(cam, pl)
            if (z < 2).any():
                continue
            stroke_poly(ctx, xy, (236, 238, 242), 1.0, float(np.clip(2.2 * px_per_in(cam, z.mean()), 1.2, 30)))
            stroke_poly(ctx, xy, (180, 186, 196), 0.6, float(np.clip(0.5 * px_per_in(cam, z.mean()), 0.6, 6)))
    else:
        for pl in fr_:
            xy, z = proj(cam, pl)
            if (z < 2).any():
                continue
            wdt = float(np.clip(2.375 * px_per_in(cam, z.mean()), 1.5, 60))
            stroke_poly(ctx, xy, POST_RED, 1.0, wdt)
            stroke_poly(ctx, xy - np.array([wdt * 0.18, wdt * 0.12]), (255, 120, 120), 0.45, wdt * 0.22)
    return s


# ---------------- Maßlinien
def dim_line(ctx, a, b, prog, col=ORANGE, width=4.0):
    if prog <= 0:
        return
    c = (a + b) / 2
    pa, pb = c + (a - c) * e_out(prog, 3), c + (b - c) * e_out(prog, 3)
    stroke_poly(ctx, np.array([pa, pb]), col, 1.0, width)
    d = (b - a) / (np.linalg.norm(b - a) + 1e-6)
    n = np.array([-d[1], d[0]])
    k = e_back(c01((prog - 0.75) / 0.25), 2.2)
    if k > 0:
        for p in (a, b):
            stroke_poly(ctx, np.array([p - n * 15 * k, p + n * 15 * k]), col, 1.0, width)
            ctx.arc(p[0], p[1], 6.5 * k, 0, 2 * math.pi)
            ctx.fill()


def ext_line(ctx, a, b, alpha):
    if alpha > 0:
        ctx.set_dash([6, 6])
        stroke_poly(ctx, np.array([a, b]), GREY, 0.55 * alpha, 2.0, cairo.LINE_CAP_BUTT)
        ctx.set_dash([])


# ================================================================= Text (Inter)
_FONTS = {}


def ifont(size, wght):
    key = (size, wght)
    if key not in _FONTS:
        f = ImageFont.truetype(INTER, size)
        f.set_variation_by_axes([32 if size >= 40 else 14, wght])
        _FONTS[key] = f
    return _FONTS[key]


_LINES = {}


def line_img(txt, size, wght, col, track=0.0, cache=True):
    key = (txt, size, wght, col, track)
    if key not in _LINES or not cache:
        f = ifont(size, wght)
        asc, desc = f.getmetrics()
        tw = sum(f.getlength(ch) for ch in txt) + track * (len(txt) - 1) if track else f.getlength(txt, features=["tnum"])
        im = Image.new("RGBA", (int(tw) + 40, asc + desc + 40), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        if track:
            x = 20
            for ch in txt:
                d.text((x, 20), ch, font=f, fill=col + (255,))
                x += f.getlength(ch) + track
        else:
            d.text((20, 20), txt, font=f, fill=col + (255,), features=["tnum"])
        bb = im.getbbox()
        # feste Zeilenhöhe (Ober-/Unterlänge), damit Zeilen gleich sitzen
        out = im.crop((bb[0], 20 + int(asc * 0.18), bb[2], 20 + asc + desc))
        if not cache:
            return out
        _LINES[key] = out
    return _LINES[key]


_HALO = {}


def halo(img):
    """Weicher weißer Lichthof hinter einer Textzeile."""
    key = id(img)
    if key not in _HALO:
        pad = 24
        a = Image.new("L", (img.width + 2 * pad, img.height + 2 * pad), 0)
        a.paste(img.getchannel("A"), (pad, pad))
        a = a.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(9)).point(lambda v: min(255, int(v * 2.2)))
        h_ = Image.new("RGBA", a.size, (248, 248, 250, 0))
        h_.putalpha(a)
        _HALO[key] = (h_, img)
    return _HALO[key][0]


def reveal_halo(L, img, cx, cy, p_in, p_out=0.0):
    hl = halo(img)
    reveal(L, hl, cx, cy, p_in, p_out)
    reveal(L, img, cx, cy, p_in, p_out)


def put(L, im, x, y):
    """alpha_composite mit Beschnitt an den Bildrändern."""
    x, y = int(round(x)), int(round(y))
    sx, sy = max(0, -x), max(0, -y)
    ex, ey = min(im.width, L.width - x), min(im.height, L.height - y)
    if sx < ex and sy < ey:
        L.alpha_composite(im.crop((sx, sy, ex, ey)), (x + sx, y + sy))


def reveal(L, img, cx, cy, p_in, p_out=0.0, anchor="c"):
    """Maskierte Zeile: gleitet beim Einblenden von unten herein, beim Ausblenden nach oben hinaus."""
    if p_in <= 0 or p_out >= 1:
        return
    w, h = img.size
    off = (1 - e_out(p_in, 4)) * h * 1.08 - e_in(p_out, 3) * h * 1.08
    pad = 8
    box = Image.new("RGBA", (w, h + 2 * pad), (0, 0, 0, 0))
    put(box, img, 0, pad + off)
    x0 = cx - w / 2 if anchor == "c" else (cx if anchor == "l" else cx - w)
    put(L, box, x0, cy - h / 2 - pad)


def label(L, txt, cy, p_in, p_out=0.0):
    img = line_img(txt, 30, 650, ORANGE, track=6)
    reveal(L, img, W / 2, cy, p_in, p_out)


# ================================================================= Szenen-Overlays
def projected(cam, p):
    xy, z = proj(cam, [p])
    return xy[0], z[0]


def overlays(t, cam, ap, focus):
    """Liefert Ebenen: net_back, net_front (cairo), fx (cairo), anno (cairo), text (PIL)."""
    layers = {}
    show_net = 4.6 < t < 12.6 or ap > 0                # auch unscharf im Hintergrund (Loop-Naht!)
    if show_net:
        nb, nf = draw_net(cam, t, False), draw_net(cam, t, True)
        _, zg = projected(cam, G2)
        if zg > 1:
            fade = 1 - smooth(350, 2600, zg) if cam[1] < 400 else 1.0
            sig = 0.0
            if ap > 0.005:
                sig = float(min(40.0, ap * abs(1 / zg - 1 / focus) * (H / 2) / cam[12] * 0.5))
            layers["net"] = (nb, nf, fade, sig)
    fx_s, ctx = surface()
    fx_scene(ctx, t, cam)
    layers["fx"] = fx_s
    an_s, actx = surface()
    annotations(actx, t, cam)
    layers["anno"] = an_s
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    texts(L, t)
    layers["text"] = L
    return layers


def rand_vecs(n, seed):
    return np.random.default_rng(seed).random((n, 6))


def fx_scene(ctx, t, cam):
    # Frost: kalter Dunst + Funkeln
    if 0.3 < t < 2.2:
        rv = rand_vecs(70, 7)
        for k in range(70):
            lt = (t - 0.3 - rv[k, 0] * 1.2)
            if lt < 0 or lt > 1.4:
                continue
            ang = rv[k, 1] * 2 * math.pi
            rad = 1.6 + lt * (1.2 + rv[k, 2] * 2.0)
            p = np.array([HP[0] + math.cos(ang) * rad, 0.3 + lt * (0.6 + rv[k, 3] * 1.4), HP[2] + math.sin(ang) * rad])
            xy, z = projected(cam, p)
            if z < 0.5:
                continue
            a = 0.35 * math.sin(math.pi * lt / 1.4)
            rr = (0.12 + rv[k, 4] * 0.18) * px_per_in(cam, z)
            g = cairo.RadialGradient(xy[0], xy[1], 0, xy[0], xy[1], rr)
            g.add_color_stop_rgba(0, 0.78, 0.88, 1.0, a)
            g.add_color_stop_rgba(1, 0.78, 0.88, 1.0, 0)
            ctx.set_source(g)
            ctx.arc(xy[0], xy[1], rr, 0, 2 * math.pi)
            ctx.fill()
    # Frost verdampft: Funken steigen auf
    if 2.25 < t < 3.0:
        rv = rand_vecs(48, 11)
        for k in range(48):
            lt = t - 2.25 - rv[k, 0] * 0.25
            if lt < 0 or lt > 0.5:
                continue
            ang = rv[k, 1] * 2 * math.pi
            rad = R_ * (0.4 + rv[k, 2] * 0.7) + lt * 3.0
            p = np.array([HP[0] + math.cos(ang) * rad, 1.0 + lt * (4 + rv[k, 3] * 5), HP[2] + math.sin(ang) * rad])
            xy, z = projected(cam, p)
            if z < 0.5:
                continue
            a = 1 - lt / 0.5
            s_ = (2.5 + rv[k, 4] * 3.5)
            ctx.set_source_rgba(0.35, 0.62, 1.0, 0.85 * a)
            ctx.arc(xy[0], xy[1], s_, 0, 2 * math.pi)
            ctx.fill()
    # Schuss: oranger Schwung + Aufprall-Ringe + Eisspray
    if T_SHOT - 0.14 < t < T_SHOT + 0.7:
        pp, _ = projected(cam, T0)
        lt = t - (T_SHOT - 0.14)
        if lt < 0.3:
            pts = np.array([[pp[0] - 620, pp[1] + 420], [pp[0] - 300, pp[1] + 260], [pp[0] - 60, pp[1] + 40]])
            a_ = c01(lt / 0.14)
            b_ = c01((lt - 0.12) / 0.16)
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            ctx.set_source_rgba(ORANGE[0] / 255, ORANGE[1] / 255, ORANGE[2] / 255, 1 - b_)
            ctx.set_line_width(16 * (1 - b_ * 0.7))
            n = 24
            seg = []
            for i in range(n + 1):
                u = lerp(b_, a_, i / n)
                q = (1 - u) ** 2 * pts[0] + 2 * (1 - u) * u * pts[1] + u * u * pts[2]
                seg.append(q)
            ctx.move_to(*seg[0])
            for q in seg[1:]:
                ctx.line_to(*q)
            ctx.stroke()
        li = t - T_SHOT
        if 0 <= li < 0.45:
            ppos, _, _, _ = puck_state(t)
            pq, zq = projected(cam, T0)
            for k, (col, rmax, wdt) in enumerate(((ORANGE, 330, 7), (INK, 210, 3))):
                q = e_out(li / 0.45, 3)
                ctx.set_source_rgba(col[0] / 255, col[1] / 255, col[2] / 255, (1 - q) * 0.9)
                ctx.set_line_width(wdt * (1 - q) + 1)
                ctx.arc(pq[0], pq[1], 30 + rmax * q, 0, 2 * math.pi)
                ctx.stroke()
        if 0 <= li < 0.7:
            rv = rand_vecs(90, 21)
            for k in range(90):
                lt = li - rv[k, 0] * 0.12
                if lt < 0 or lt > 0.55:
                    continue
                v = -U * (25 + rv[k, 1] * 60) + UPERP * (rv[k, 2] - 0.5) * 50 + np.array([0, 18 + rv[k, 3] * 45, 0])
                p0 = HP + np.array([0, 0.3, 0]) + U * (-1.2)
                p = p0 + v * lt + np.array([0, -0.5 * 386 * lt * lt, 0])
                if p[1] < 0:
                    continue
                pv = p - v * 0.012
                xy, z = proj(cam, [p, pv])
                if (z < 0.5).any():
                    continue
                stroke_poly(ctx, xy, (140, 160, 188), 0.85 * (1 - lt / 0.55), 2.2 + rv[k, 4] * 2.4)
    # Tor: Torlicht + Ring auf dem Eis
    li = t - T_HIT
    if 0 <= li < 1.4:
        pg, zg = projected(cam, np.array([GOAL_X + 30, 78.0, 0.0]))
        if zg > 1:
            pulse = sum(math.exp(-((li - k * 0.42) / 0.12) ** 2) for k in range(3))
            rr = 260 * (0.7 + 0.3 * pulse)
            g = cairo.RadialGradient(pg[0], pg[1], 0, pg[0], pg[1], rr)
            g.add_color_stop_rgba(0, 1.0, 0.25, 0.12, 0.55 * pulse)
            g.add_color_stop_rgba(1, 1.0, 0.25, 0.12, 0)
            ctx.set_source(g)
            ctx.arc(pg[0], pg[1], rr, 0, 2 * math.pi)
            ctx.fill()
        q = e_out(li / 0.8, 3)
        if li < 0.8:
            r = 40 + 120 * q
            ring = np.stack([GOAL_X + r * np.cos(PHI2), np.full_like(PHI2, 0.05), r * np.sin(PHI2)], 1)
            xy, z = proj(cam, ring)
            if (z > 1).all():
                stroke_poly(ctx, xy, ORANGE, 0.8 * (1 - q), 4.0)


PHI2 = np.linspace(0, 2 * math.pi, 64)
R_ = 1.5


def rink_polylines():
    lines = []
    corner = np.linspace(0, math.pi / 2, 16)
    cx, cz, rc = 1200 - 336, 510 - 336, 336
    b = []
    for sx, sz, a0 in ((1, 1, 0), (-1, 1, math.pi / 2), (-1, -1, math.pi), (1, -1, 1.5 * math.pi)):
        for a in corner:
            b.append((sx * cx + rc * math.cos(a + a0), 0, sz * cz + rc * math.sin(a + a0)))
    b.append(b[0])
    lines.append((np.array(b, float), 9.85, 0.9))
    for x0, t0 in ((0, 10.2), (300, 10.35), (-300, 10.35)):
        lines.append((np.array([[x0, 0, -510], [x0, 0, 510]], float), t0, 0.5))
    for x0 in (1068, -1068):
        lines.append((np.array([[x0, 0, -441], [x0, 0, 441]], float), 10.5, 0.45))
    ang = np.linspace(-math.pi / 2, 1.5 * math.pi, 48)
    for (x0, z0), t0 in (((0, 0), 10.55), ((828, 264), 10.7), ((828, -264), 10.75), ((-828, 264), 10.8), ((-828, -264), 10.85)):
        lines.append((np.stack([x0 + 180 * np.cos(ang), np.zeros_like(ang), z0 + 180 * np.sin(ang)], 1), t0, 0.6))
    for sx in (1, -1):
        a2 = np.linspace(-0.73, 0.73, 20)
        lines.append((np.stack([sx * (1068 - 72 * np.cos(a2)), np.zeros_like(a2), 72 * np.sin(a2)], 1), 10.95, 0.35))
    return lines


RINK_LINES = rink_polylines()


def annotations(ctx, t, cam):
    # 02 SIZE: Durchmesser + Dicke
    if 2.8 < t < 4.65:
        out = 1 - smooth(4.45, 4.62, t)
        f = cam[9:12].copy()
        rh = np.cross(f, [0, 1, 0])
        rh[1] = 0
        rh /= np.linalg.norm(rh)
        fh = f.copy()
        fh[1] = 0
        fh /= np.linalg.norm(fh)
        c = HP + np.array([0, 0.01, 0])
        a3, b3 = c - rh * 1.5, c + rh * 1.5
        fwd = -fh * 2.6
        (a, b, ea, eb), _ = proj(cam, [a3 + fwd, b3 + fwd, a3, b3])
        pr = smooth(2.85, 3.25, t)
        ext_line(ctx, ea, a, pr * out)
        ext_line(ctx, eb, b, pr * out)
        ctx.push_group()
        dim_line(ctx, a, b, pr)
        q = HP + rh * 1.5
        side = rh * 0.5
        (s0, s1, e0, e1), _ = proj(cam, [q + side, q + side + np.array([0, 1.0, 0]), q, q + np.array([0, 1.0, 0])])
        pr2 = smooth(3.35, 3.7, t)
        dim_line(ctx, s0, s1, pr2)
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(out)
        ext_line(ctx, e0, s0, pr2 * out)
        ext_line(ctx, e1, s1, pr2 * out)
    # 04 TARGET: 6 FT / 4 FT am Tor
    if 8.3 < t < 9.9:
        out = 1 - smooth(9.62, 9.85, t)
        pts = [[GOAL_X, 58, -36], [GOAL_X, 58, 36], [GOAL_X, 48, -36], [GOAL_X, 48, 36],
               [GOAL_X, 0, -48], [GOAL_X, 48, -48], [GOAL_X, 0, -36], [GOAL_X, 48, -36]]
        xy, z = proj(cam, pts)
        if (z > 1).all():
            ctx.push_group()
            dim_line(ctx, xy[0], xy[1], smooth(8.35, 8.75, t))
            dim_line(ctx, xy[4], xy[5], smooth(8.6, 9.0, t))
            ctx.pop_group_to_source()
            ctx.paint_with_alpha(out)
            ext_line(ctx, xy[2], xy[0], smooth(8.35, 8.75, t) * out)
            ext_line(ctx, xy[3], xy[1], smooth(8.35, 8.75, t) * out)
            ext_line(ctx, xy[6], xy[4], smooth(8.6, 9.0, t) * out)
            ext_line(ctx, xy[7], xy[5], smooth(8.6, 9.0, t) * out)
    # 05 ICE: Linien zeichnen sich + 200 x 85 FT
    if 9.8 < t < 12.5:
        out = 1 - smooth(12.05, 12.4, t)
        ctx.push_group()
        for pl, t0, d in RINK_LINES:
            fr = smooth(t0, t0 + d, t)
            if fr <= 0:
                continue
            xy, z = proj(cam, pl)
            if (z < 5).any():
                continue
            stroke_poly(ctx, partial(xy, fr), ORANGE, 0.95, 3.2)
        xy, z = proj(cam, [[-1200, 0, -570], [1200, 0, -570], [1250, 0, -510], [1250, 0, 510]])
        if (z > 5).all():
            dim_line(ctx, xy[0], xy[1], smooth(11.2, 11.7, t), INK, 3.5)
            dim_line(ctx, xy[2], xy[3], smooth(11.45, 11.95, t), INK, 3.5)
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(out)


def dim_labels(L, t, cam):
    """Beschriftungen der Maßlinien (PIL, folgt den 3D-Punkten)."""
    if 2.8 < t < 4.65:
        out = smooth(4.45, 4.62, t)
        f = cam[9:12].copy()
        rh = np.cross(f, [0, 1, 0])
        rh[1] = 0
        rh /= np.linalg.norm(rh)
        fh = f.copy()
        fh[1] = 0
        fh /= np.linalg.norm(fh)
        c = HP - fh * 2.6
        (p, q), _ = proj(cam, [c, HP + rh * 2.0 + np.array([0, 0.5, 0])])
        reveal(L, line_img("3 IN", 58, 900, INK), p[0], p[1] + 50, smooth(3.0, 3.25, t), out)
        reveal(L, line_img("1 IN", 58, 900, INK), q[0] + 20, q[1], smooth(3.45, 3.7, t), out, "l")
    if 8.3 < t < 9.9:
        out = smooth(9.62, 9.85, t)
        (p, q), z = proj(cam, [[GOAL_X, 58, 0], [GOAL_X, 24, -48]])
        if (z > 1).all():
            reveal(L, line_img("6 FT", 58, 900, INK), p[0], p[1] - 46, smooth(8.45, 8.7, t), out)
            a_ = smooth(8.7, 8.95, t) * (1 - out)
            if a_ > 0:
                lab = line_img("4 FT", 54, 900, INK).rotate(90, expand=True)
                lab = lab.copy()
                lab.putalpha(lab.getchannel("A").point(lambda v: int(v * a_)))
                put(L, lab, q[0] - 22 - lab.width, q[1] - lab.height / 2)
    if 11.0 < t < 12.5:
        out = smooth(12.05, 12.4, t)
        (p, q), z = proj(cam, [[0, 0, -570], [1250, 0, 0]])
        if (z > 5).all():
            a_ = smooth(11.35, 11.6, t) * (1 - out)
            if a_ > 0:
                lab = line_img("200 FT", 44, 900, INK).rotate(90, expand=True).copy()
                lab.putalpha(lab.getchannel("A").point(lambda v: int(v * a_)))
                put(L, lab, p[0] - 20 - lab.width, p[1] - lab.height / 2)
            reveal(L, line_img("85 FT", 44, 900, INK), q[0], q[1] - 40, smooth(11.6, 11.85, t), out)


def texts(L, t):
    # 01 COLD (+ Wiederholung am Ende für den Loop)
    tl = t
    loop_in = smooth(14.45, 14.85, t) if t > 14.0 else 1.0
    if t < 2.7 or t > 14.4:
        ex = smooth(2.3, 2.55, t) if t < 3 else 0.0
        reveal_halo(L, line_img("01  —  COLD", 30, 650, ORANGE, track=6), W / 2, 290, loop_in, ex)
        reveal_halo(L, line_img("EVERY NHL PUCK", 92, 900, INK), W / 2, 382, loop_in, ex)
        if t < 3:
            reveal(L, line_img("IS FROZEN.", 132, 900, ICEBLUE), W / 2, 500, smooth(0.36, 0.62, tl), smooth(2.34, 2.6, t))
            reveal(L, line_img("before every game, so it bounces less", 36, 500, GREY), W / 2, 600,
                   smooth(1.1, 1.4, t), smooth(2.3, 2.5, t))
    # 02 SIZE
    if 2.5 < t < 4.8:
        ex = smooth(4.42, 4.62, t)
        label(L, "02  —  SIZE", 290, smooth(2.55, 2.8, t), ex)
        reveal(L, line_img("SOLID RUBBER.", 100, 900, INK), W / 2, 382, smooth(2.6, 2.9, t), ex)
        reveal(L, line_img("5.5 – 6 oz, 3 inches wide", 36, 500, GREY), W / 2, 478, smooth(2.8, 3.1, t), ex)
    # 03 SPEED
    if 5.1 < t < 8.1:
        ex = smooth(7.6, 7.85, t)
        label(L, "03  —  SPEED", 290, smooth(5.15, 5.4, t), ex)
        v = 108.8 * e_out((t - 5.25) / 1.25, 3)
        ref = line_img("108.8", 220, 900, INK)
        cur = line_img(f"{v:.1f}", 220, 900, INK, cache=False)
        num = Image.new("RGBA", ref.size, (0, 0, 0, 0))
        num.alpha_composite(cur, (ref.width - cur.width, 0))
        unit = line_img("MPH", 64, 900, ORANGE)
        wtot = num.width + 18 + unit.width
        x0 = W / 2 - wtot / 2
        reveal(L, num, x0 + num.width / 2, 432, smooth(5.2, 5.45, t), ex)
        reveal(L, unit, x0 + num.width + 18 + unit.width / 2, 470, smooth(5.3, 5.55, t), ex)
        reveal(L, line_img("NHL HARDEST SHOT RECORD  ·  ZDENO CHARA, 2012", 28, 600, GREY, 2), W / 2, 566,
               smooth(5.6, 5.9, t), ex)
    # 04 TARGET
    if 8.0 < t < 9.95:
        ex = smooth(9.6, 9.82, t)
        label(L, "04  —  TARGET", 290, smooth(8.05, 8.3, t), ex)
        reveal(L, line_img("6 × 4 FEET.", 112, 900, INK), W / 2, 386, smooth(8.15, 8.45, t), ex)
        reveal(L, line_img("that's the whole net", 36, 500, GREY), W / 2, 486, smooth(8.4, 8.7, t), ex)
    # 05 ICE
    if 10.0 < t < 12.5:
        ex = smooth(12.05, 12.3, t)
        label(L, "05  —  ICE", 252, smooth(10.1, 10.35, t), ex)
        reveal(L, line_img("200 × 85 FEET", 96, 900, INK), W / 2, 338, smooth(10.2, 10.5, t), ex)
    # CTA
    if 12.3 < t < 14.6:
        ex = smooth(14.2, 14.45, t)
        reveal(L, line_img("WHICH ONE", 100, 900, INK), W / 2, 380, smooth(12.4, 12.7, t), ex)
        reveal(L, line_img("DID YOU KNOW?", 100, 900, INK), W / 2, 486, smooth(12.5, 12.8, t), ex)
        reveal(L, line_img("COMMENT 01 – 05", 44, 700, ORANGE, 3), W / 2, 590, smooth(12.75, 13.0, t), ex)
        if 13.0 < t < 14.4:
            y = 640 + abs(math.sin((t - 13.0) * 6)) * 14
            ImageDraw.Draw(L).polygon([(W / 2 - 18, y), (W / 2 + 18, y), (W / 2, y + 22)],
                                      fill=ORANGE + (int(255 * (1 - ex)),))


_WM = None


def watermark():
    global _WM
    if _WM is None:
        im = Image.open(os.path.join(HERE, "brand", "bladesandpucks_mark_dark.png")).convert("RGBA")
        im = im.crop(im.getbbox())
        s = 54 / im.height
        im = im.resize((int(im.width * s), 54), Image.LANCZOS)
        a = im.getchannel("A").point(lambda v: int(v * 0.5))
        im.putalpha(a)
        _WM = im
    return _WM


# ================================================================= Bild zusammensetzen
def compose(t, fidx):
    base, puck, cov = render3d(t, fidx)
    row, ap, focus = cam_row(t)
    lay = overlays(t, row, ap, focus)
    img = base
    pa = cov[..., None]
    netinfo = lay.get("net")
    ppos, _, pvis, _ = puck_state(t)
    puck_inside = ppos[0] > GOAL_X - 0.5 and pvis > 0
    front_rgb = None
    if netinfo:
        nb, nf, fade, sig = netinfo
        layers_rgba = []
        for s_ in (nb, nf):
            rgb, a = surf_rgba(s_)
            if sig > 0.8:
                pil = Image.fromarray(np.concatenate([rgb, a], -1).__mul__(255).astype(np.uint8), "RGBA")
                pil = pil.filter(ImageFilter.GaussianBlur(sig))
                arr = np.asarray(pil).astype(np.float32) / 255
                rgb, a = arr[..., :3], arr[..., 3:4]
            layers_rgba.append((rgb * fade, a * fade))
        img = over(img, *layers_rgba[0])
        front_rgb = layers_rgba[1]
        if not puck_inside:
            img = over(img, *front_rgb)
    img = img * (1 - pa) + puck * pa
    if front_rgb is not None and puck_inside:
        img = over(img, *front_rgb)
    img = over(img, *surf_rgba(lay["fx"]))
    img = over(img, *surf_rgba(lay["anno"]))
    L = lay["text"]
    dim_labels(L, t, row)
    wm = watermark()
    L.alpha_composite(wm, (W - 50 - wm.width, 206))
    ta = np.asarray(L).astype(np.float32) / 255
    img = img * (1 - ta[..., 3:4]) + ta[..., :3] * ta[..., 3:4]
    # leichte Vignette + feines Korn gegen Banding
    img = img * VIG
    img += np.random.default_rng(fidx).normal(0, 0.006, img.shape[:2])[..., None]
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)
VIG = (1 - 0.10 * np.clip(np.sqrt(((_xx - W / 2) / W) ** 2 + ((_yy - H / 2) / H) ** 2) * 2 - 0.6, 0, 1) ** 1.5)[..., None]
del _yy, _xx


# ================================================================= Sound
SR = 44100


def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(15)
    music, sfx = np.zeros(n), np.zeros(n)

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

    def kick(vol=1.0):
        x = tt(0.4)
        f = 48 + 120 * np.exp(-x * 30)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 8) * 2.0) * 0.9 * vol

    def clap():
        x = tt(0.25)
        nz = hp(noise(0.25), 6)
        out = np.zeros(len(x))
        for off, dec in ((0, 70), (0.01, 70), (0.02, 18)):
            st = int(off * SR)
            out[st:] += nz[: len(x) - st] * np.exp(-x[: len(x) - st] * dec)
        return lp(out, 2) * 0.45

    def hat(vol=0.2, open_=False):
        d_ = 0.22 if open_ else 0.05
        x = tt(d_)
        return hp(noise(d_), 2) * np.exp(-x * (16 if open_ else 110)) * vol

    def pulse(freq=55.0, dur=0.32, vol=0.5):
        x = tt(dur)
        return np.sin(2 * np.pi * freq * x) * np.minimum(x / 0.004, 1) * np.exp(-x * 9) * vol

    def bass(freq, dur):
        x = tt(dur)
        sig = np.tanh(np.sin(2 * np.pi * freq * x) * 2.2) * 0.55
        return sig * np.minimum(x / 0.01, 1) * np.clip((dur - x) / 0.05, 0, 1)

    def pluck(freq, dur=0.6, vol=0.25):
        x = tt(dur)
        sig = np.sin(2 * np.pi * freq * x) + 0.35 * np.sin(2 * np.pi * freq * 2 * x) * np.exp(-x * 12)
        return sig * np.exp(-x * 7) * vol

    def chime(freq, dur=1.4, vol=0.22):
        x = tt(dur)
        sig = sum(np.sin(2 * np.pi * freq * m * x) * a * np.exp(-x * d) for m, a, d in ((1, 1, 3), (2.76, 0.4, 6), (5.4, 0.2, 10)))
        return sig * vol

    def pad(freqs, dur, vol=0.12):
        x = tt(dur)
        sig = sum(np.sin(2 * np.pi * f * x + np.sin(2 * np.pi * 0.3 * x) * 0.3) for f in freqs) / len(freqs)
        return sig * np.minimum(x / 0.6, 1) * np.clip((dur - x) / 0.6, 0, 1) * vol

    def whoosh(dur=0.5, vol=1.0, down=False):
        x = tt(dur)
        nz = noise(dur)
        env = np.sin(np.pi * x / dur) ** 2
        lo, hi = lp(nz, 40), lp(nz, 6) - lp(nz, 40)
        mv = 1 - x / dur if down else x / dur
        return (lo * (1 - mv) + hi * mv * 1.3) * env * 1.2 * vol

    def riser(dur, vol=1.0):
        x = tt(dur)
        sw = np.sin(2 * np.pi * np.cumsum(300 + 1800 * (x / dur) ** 2) / SR) * (x / dur) ** 3 * 0.12
        return (hp(noise(dur), 4) * (x / dur) ** 2 * 0.35 + sw) * vol

    def thud(f0=160, vol=0.8):
        x = tt(0.25)
        f = f0 * (1 + 0.8 * np.exp(-x * 60))
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 26) + hp(noise(0.25), 3) * np.exp(-x * 120) * 0.4) * vol

    def crack(vol=1.0):
        x = tt(0.5)
        body = np.sin(2 * np.pi * np.cumsum(220 * (1 + 2 * np.exp(-x * 80))) / SR) * np.exp(-x * 18)
        snap = hp(noise(0.5), 2) * np.exp(-x * 70)
        return np.tanh((body * 0.8 + snap * 1.2) * 1.6) * vol

    def boom(dur=1.6, f0=50, vol=1.0):
        x = tt(dur)
        f = f0 + 90 * np.exp(-x * 12)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 2.6) * 1.8) * vol

    def crackle(dur, dens=160, vol=0.25, hi=True):
        x = np.zeros(int(dur * SR))
        for _ in range(int(dur * dens)):
            p = int(rng.integers(0, len(x) - 200))
            x[p:p + 160] += (hp(rng.standard_normal(160), 1) if hi else rng.standard_normal(160)) * np.exp(-np.arange(160) / 18) * rng.uniform(0.2, 1)
        return x * vol

    def sparkle(dur=0.6, vol=0.2):
        x = tt(dur)
        sig = np.zeros(len(x))
        for _ in range(40):
            f = rng.uniform(2500, 7000)
            st = int(rng.uniform(0, dur * 0.8) * SR)
            k = np.arange(len(x) - st) / SR
            sig[st:] += np.sin(2 * np.pi * f * k) * np.exp(-k * 30) * rng.uniform(0.3, 1)
        return sig / 6 * vol

    def horn(dur=1.2):
        x = tt(dur)
        sig = sum(2 * ((x * f * (1 + 0.003 * np.sin(2 * np.pi * 4.5 * x))) % 1) - 1 for f in (110.0, 138.6, 164.8))
        return lp(lp(sig, 10), 6) / 3 * np.minimum(x / 0.05, 1) * np.clip((dur - x) / 0.3, 0, 1) * 0.6

    def crowd(dur, vol):
        x = tt(dur)
        return lp(noise(dur), 14) * 3 * (0.8 + 0.2 * np.sin(2 * np.pi * 0.7 * x)) * vol

    # ---------- Musik (120 BPM, Schlag = 0.5 s)
    AM = [220.0, 261.6, 329.6, 392.0]
    ROOT = [55.0, 55.0, 43.65, 49.0]
    for k in range(30):                                  # Grundpuls über alles
        tb = k * 0.5
        sec_full = T_SHOT <= tb < 12.2
        if not sec_full:
            put(music, pulse(55.0, 0.3, 0.35), tb)
        if 1.0 <= tb < 12.2:
            for j in range(4):
                put(music, hat(0.10 if j % 2 else 0.16), tb + j * 0.125)
        if sec_full:
            put(music, kick(), tb)
            if k % 2 == 1:
                put(music, clap(), tb)
            put(music, hat(0.22, True), tb + 0.25)
            put(music, bass(ROOT[(k // 4) % 4], 0.22), tb + 0.25)
            put(music, bass(ROOT[(k // 4) % 4], 0.18), tb + 0.375)
    for tb, f in ((0.75, 659.3), (1.25, 523.3), (1.75, 784.0), (3.25, 659.3), (3.75, 880.0), (13.0, 523.3),
                  (13.5, 659.3), (14.0, 784.0), (14.5, 659.3)):
        put(music, pluck(f, 0.7, 0.18), tb)
    put(music, pad([110, 164.8, 220, 261.6], 4.8, 0.10), 0.0)
    put(music, pad([98, 146.8, 196, 246.9], 3.2, 0.10), 9.6)
    put(music, pad([110, 164.8, 220, 329.6], 3.4, 0.13), 12.0)
    put(music, pad([110, 164.8, 220, 261.6], 1.0, 0.10), 14.2)

    # ---------- Effekte
    put(sfx, whoosh(0.35, 0.5, down=True), T_LAND - 0.3)
    put(sfx, thud(150, 0.9), T_LAND)
    put(sfx, crackle(0.8, 220, 0.22), T_LAND + 0.02)
    put(sfx, chime(1318.5, 1.6, 0.16), 0.36)
    put(sfx, pulse(41.2, 0.6, 0.6), 0.36)
    put(sfx, sparkle(0.6, 0.35), 2.28)
    put(sfx, whoosh(0.5, 0.45), 2.3)
    for ti in (2.85, 3.35, 8.35, 8.6, 11.2, 11.45):
        put(sfx, thud(1400, 0.10), ti)
        put(sfx, pluck(1046.5, 0.3, 0.12), ti)
    put(sfx, riser(0.55, 0.8), 4.55)
    put(sfx, whoosh(0.5, 0.9), 4.6)
    put(sfx, crack(1.0), T_SHOT)
    put(sfx, boom(1.4, 46, 0.8), T_SHOT)
    tk = tt(0.015)
    tick = np.sin(2 * np.pi * 2600 * tk) * np.exp(-tk * 400) * 0.10
    prev = -1
    for j in range(0, 1500):
        ti = 5.25 + j / 1000
        v = int(108.8 * e_out((ti - 5.25) / 1.25, 3))
        if v != prev:
            put(sfx, tick, ti)
            prev = v
    put(sfx, hp(noise(2.8), 3) * np.exp(-tt(2.8) * 0.6) * 0.05, T_SHOT + 0.05)    # Gleiten auf dem Eis
    put(sfx, lp(noise(0.4), 20) * np.exp(-tt(0.4) * 9) * 1.2, T_HIT)               # Netz
    put(sfx, boom(1.0, 60, 0.6), T_HIT)
    put(sfx, horn(1.2), T_HIT + 0.05)
    put(sfx, crowd(1.6, 0.35) * np.exp(-tt(1.6) * 1.2), T_HIT + 0.05)
    put(sfx, riser(2.2, 0.55), 9.9)
    for pl, t0, d in RINK_LINES:
        put(sfx, lp(noise(d), 3) * np.sin(np.pi * tt(d) / d) * 0.035, t0)
    put(sfx, whoosh(2.4, 0.7, down=True), 12.25)

    mix = music * 0.7 + sfx * 0.9
    mix /= np.percentile(np.abs(mix), 99.95) + 1e-9
    mix = np.tanh(mix * 0.9)
    mix = mix / np.max(np.abs(mix)) * 0.94
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


def main():
    os.chdir(HERE)
    make_audio("audio_puck.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_puck.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "19",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
           "reel15_puck.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(0.62, 9999)).save("reel15_thumbnail.jpg", quality=92)
    print("fertig: reel15_puck.mp4")


if __name__ == "__main__":
    main()
