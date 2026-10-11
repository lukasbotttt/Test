"""Reel 20: THE PUCK pt. 2 – Brand-Motion-Design mit echtem 3D-Puck, 140 BPM, 26 Beats (11,1 s).

Stil: Apple-/Spotify-Brand-Animation (Kreis-Raster, riesige Typo mit hochgestellten Labels, Farbflächen,
Ball-Übergänge), aber der "Ball" ist der raytracte Puck aus Teil 1 (puck3d.py, echte Bewegungsunschärfe).
  0–2    Raster aus Puck-Renderings dreht sich im Takt, "THE PUCK pt. 2"
  2–4    Zoom in den mittleren Puck (Match-Cut auf 3D)
  4–8    Product-Shot: Kamera kippt aus der Draufsicht, Callouts (1) Vulcanized rubber (2) Knurled edge (3) 5.5–6 oz
  8–16   Pro Beat schießt der Puck durchs Bild und wischt die nächste Fläche frei:
         SNAP SLAP WRIST BACKHAND DANGLE DEKE TOE DRAG SNIPE
  16–20  Puck bremst in der Mitte ab: "WHICH SHOT / IS YOURS?"
  20–26  Puck fliegt ins Logo, "bladesandpucks", "THE PUCK pt. 2"
Fakten: NHL-Puck aus vulkanisiertem Gummi, geriffelte (knurled) Kante für Grip, 5,5–6 oz (NHL Rule 25).
Musik selbst synthetisiert (Trap, a-Moll, Stereo mit Hall).
Aufruf: python3 reel20_puck2.py -> reel20_puck2.mp4, reel20_puck2_ohne_ton.mp4, reel20_thumbnail.jpg
"""
import math
import os
import subprocess
import time
import wave

import cairocffi as cairo
import numpy as np
from PIL import Image, ImageFilter
from scipy.signal import fftconvolve

import puck3d as P3
import reel15_puck as R15
from reel15_puck import c01, smooth, sio, e_out, e_in, e_back, lerp, sph, blend_up

W, H, FPS = 1080, 1920, 30
BPM = 140
B = 60.0 / BPM
NBEATS = 26
DUR = NBEATS * B
HERE = R15.HERE
SPP = int(os.environ.get("SPP", "12"))
KSUB = int(os.environ.get("KSUB", "12"))
SUB2D = int(os.environ.get("SUB2D", "5"))
BLACK = (10, 10, 12)
WHITE = (247, 247, 245)
OR = (255, 140, 50)
GREY = (233, 233, 229)
DIM = (128, 128, 134)
THETA0 = R15.THETA0


def e_io(x):
    x = c01(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


# ================================================================= 2D-Bausteine
def to_pil(s):
    s.flush()
    return Image.frombuffer("RGBA", (s.get_width(), s.get_height()), bytes(s.get_data()), "raw", "BGRa", 0, 1).copy()


def clear_ctx(w=W, h=H):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    return s, cairo.Context(s)


def rgb(c, col, a=1.0):
    c.set_source_rgba(col[0] / 255, col[1] / 255, col[2] / 255, a)


def solid(col):
    return Image.new("RGBA", (W, H), col + (255,))


def headline(txt, size, col, track=-0.035, wght=850):
    return R15.line_img(txt, size, wght, col, track=size * track)


def fit_headline(txt, col, max_w=980, max_size=340):
    size = max_size
    while size > 60:
        im = headline(txt, size, col)
        if im.width <= max_w:
            return im
        size -= 10
    return headline(txt, size, col)


def paste_c(img, im, cx, cy, a=1.0):
    if a <= 0 or im is None:
        return
    if a < 1:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    R15.put(img, im, cx - im.width / 2, cy - im.height / 2)


def scaled(im, s):
    if abs(s - 1) < 1e-3:
        return im
    return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BICUBIC)


def reveal_c(img, im, cx, cy, p, p_out=0.0, a=1.0):
    """Maskierte Zeile: gleitet von unten herein, nach oben hinaus."""
    if p <= 0 or p_out >= 1:
        return
    pad = 10
    box = Image.new("RGBA", (im.width, im.height + 2 * pad), (0, 0, 0, 0))
    off = (1 - e_out(p, 5)) * (im.height + pad) - e_in(p_out, 3) * (im.height + pad)
    R15.put(box, im, 0, pad + off)
    paste_c(img, box, cx, cy, a)


def with_sup(main, sup, gap=8, rise=0.62):
    """Hängt ein hochgestelltes Label an ein Text-Bild."""
    out = Image.new("RGBA", (main.width + gap + sup.width, main.height), (0, 0, 0, 0))
    out.alpha_composite(main, (0, 0))
    out.alpha_composite(sup, (main.width + gap, max(0, int(main.height * (1 - rise) - sup.height))))
    return out


_MARK = {}


def mark(size):
    if size not in _MARK:
        m = Image.open(os.path.join(HERE, "brand", "bladesandpucks_mark_transparent.png")).convert("RGBA")
        m = m.crop(m.getbbox())
        s = size / m.height
        _MARK[size] = m.resize((int(m.width * s), size), Image.LANCZOS)
    return _MARK[size]


MARK_SLOT = (0.549, 0.595, 0.418)        # Mitte (x, y relativ) + Breite des orangen Puck-Felds im Zeichen


# ================================================================= 3D
LOGO = R15.logo_tex()


def cam_row(pos, tgt, up, fov):
    pos = np.asarray(pos, float)
    r, u, f = P3.look_at(pos, np.asarray(tgt, float), np.asarray(up, float))
    return P3.cam_row(pos, r, u, f, fov)


def render_puck(w, h, rows, lens, pk, seed, spp=None):
    base = np.zeros((h, w, 3), np.float32)
    puck = np.zeros((h, w, 3), np.float32)
    cov = np.zeros((h, w), np.float32)
    P3.render(w, h, spp or SPP, seed, np.ascontiguousarray(rows), np.ascontiguousarray(lens),
              np.ascontiguousarray(pk), LOGO, base, puck, cov)
    return P3.tonemap(puck), cov


def layer_from(puck_rgb, cov):
    rgba = np.dstack([np.clip(puck_rgb, 0, 1) * 255, np.clip(cov, 0, 1) * 255]).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def soft_shadow(lay, blur, alpha):
    sh = Image.new("RGBA", lay.size, (0, 0, 0, 0))
    sh.putalpha(lay.getchannel("A").filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * alpha)))
    return sh


# --- Draufsicht-Sprite (gleiche Kamera wie der Start des Product-Shots -> nahtloser Match-Cut)
PC = np.array([0.0, 20.0, 0.0])
R_TOP, AZ0 = 30.0, 200.0
D_MATCH = 760                                   # Puck-Durchmesser in px beim Match-Cut


def fov_for(diam_px, dist, h=H):
    return math.degrees(2 * math.atan((3.0 * h / diam_px) / 2 / dist))


def top_cam(fov):
    return cam_row(sph(PC, R_TOP, AZ0, 89.9), PC, blend_up(89.9), fov)


_SPRITE = None


def sprite():
    """Puck von oben, 720 px (Puck = 680 px), RGBA, plus weicher Schatten."""
    global _SPRITE
    if _SPRITE is None:
        n = 720
        rows = np.repeat(top_cam(fov_for(680, R_TOP, n))[None], 4, 0)
        pk = np.repeat(np.array([[PC[0], PC[1], PC[2], THETA0, 1.0, 0.0, 0.0]]), 4, 0)
        rgbp, cov = render_puck(n, n, rows, np.zeros((4, 2)), pk, 7, spp=32)
        sp = layer_from(rgbp, cov)
        _SPRITE = (sp, soft_shadow(sp, 14, 0.32))
    return _SPRITE


# ================================================================= 0–4: Puck-Raster und Zoom
SP_D = 150
SPACING = 196


def grid_frame(t):
    bt = t / B
    img = solid(WHITE)
    sp, sh = sprite()
    k = min(int(bt), 3)
    ang = 90.0 * (k + e_out(c01((bt - k) / 0.35), 4)) if bt < 4 else 360.0
    zoom = math.exp(math.log(D_MATCH / SP_D) * e_io((bt - 2) / 2)) if bt >= 2 else 1.0
    band = 1 - smooth(1.7, 2.2, bt)                  # freie Zeile für den Titel
    rs, rsh = sp.rotate(ang, Image.BICUBIC), sh.rotate(ang, Image.BICUBIC)
    push = 1 + 2.2 * e_in(c01((bt - 2.4) / 1.5), 2)      # Nachbarn fliegen vor dem Match-Cut raus
    cache = {}
    for j in range(-10, 11):
        for i in range(-6, 7):
            drift = 0.0 if (i == 0 and j == 0) else (1 if j % 2 else -1) * 30 * min(bt, 2.0)
            gx, gy = i * SPACING + drift, j * SPACING
            pz = 1.0 if (i == 0 and j == 0) else push
            x, y = W / 2 + gx * zoom * pz, H / 2 + gy * zoom * pz
            dist = math.hypot(gx, gy)
            s = 1 + 0.16 * math.exp(-((dist / 700 - (bt % 1) * 2.4) ** 2) * 10)
            if abs(gy + 490) < 200:
                s *= 1 - band
            d = SP_D * s * zoom
            if d < 4 or x < -d or x > W + d or y < -d or y > H + d:
                continue
            key = int(d)
            if key not in cache:
                f = key / 680
                cache[key] = (scaled(rs, f), scaled(rsh, f))
            a, b = cache[key]
            paste_c(img, b, x, y + 0.06 * key)
            paste_c(img, a, x, y)
    if bt < 2.3:
        p_out = c01((bt - 1.75) / 0.4)
        reveal_c(img, headline("THE PUCK", 200, BLACK), W / 2, 430, 1.0 if bt < 0.02 else c01(bt / 0.3), p_out)
        reveal_c(img, R15.line_img("pt. 2", 76, 800, OR), W / 2, 560, c01((bt - 0.25) / 0.3), p_out)
    return img


# ================================================================= 4–8: Product-Shot (3D)
CALLOUT = [(4.75, "Vulcanized rubber", "(1)"), (5.5, "Knurled edge", "(2)"), (6.25, "5.5–6 oz", "(3)")]
CALL_OUT = (7.05, 7.25)
LAUNCH = (7.25, 7.7)


def product_state(t):
    bt = t / B
    u = c01((bt - 4) / 1.15)
    el = lerp(89.9, 26.0, e_io(u))
    r = lerp(R_TOP, 21.0, e_io(u))
    az = AZ0 + 28 * c01((bt - 4) / 4) + 8 * e_io(u)
    fov = lerp(fov_for(D_MATCH, R_TOP), 25.0, e_io(u))
    pos = sph(PC, r, az, el)
    up = blend_up(el)
    lt = max(0.0, t - 4 * B)
    launch = c01((bt - LAUNCH[0]) / (LAUNCH[1] - LAUNCH[0]))
    p = PC.copy()
    p[1] += 0.35 * math.sin(lt * 2.4) * c01((bt - 4.5) * 2)
    spin = 1.1 * lt * lt / (1 + lt) + 40 * launch ** 2
    if launch > 0:                                   # Puck schießt nach rechts aus dem Bild
        p = p + P3.look_at(pos, PC, up)[0] * 26 * e_in(launch, 3)
    return pos, PC, up, fov, p, THETA0 + spin, az


def callouts(img, row, p, az, t):
    bt = t / B
    out_a = 1 - c01((bt - CALL_OUT[0]) / (CALL_OUT[1] - CALL_OUT[0]))
    if out_a <= 0:
        return
    a0 = math.radians(az)
    pts = [p + np.array([0.95 * math.cos(a0 + 2.3), 0.5, 0.95 * math.sin(a0 + 2.3)]),        # Oberseite hinten
           p + np.array([1.5 * math.cos(a0 - 0.75), 0.05, 1.5 * math.sin(a0 - 0.75)]),        # Kante vorne rechts
           p + np.array([1.5 * math.cos(a0 + 0.55), -0.3, 1.5 * math.sin(a0 + 0.55)])]        # Kante vorne links
    xy, _ = R15.proj(row, pts)
    ends = [np.array([xy[0][0] - 40, 560.0]), np.array([xy[1][0] + 70, 1360.0]), np.array([xy[2][0] - 70, 1480.0])]
    s, c = clear_ctx()
    labels = []
    for (b0, txt, sup), anchor, end in zip(CALLOUT, xy, ends):
        pr = c01((bt - b0) / 0.55)
        if pr <= 0:
            continue
        q = e_out(pr, 3)
        k = e_back(c01(pr * 3), 2.5)
        rgb(c, BLACK, out_a)
        c.arc(anchor[0], anchor[1], 10 * k, 0, 2 * math.pi)
        c.fill()
        rgb(c, OR, out_a)
        c.arc(anchor[0], anchor[1], 5 * k, 0, 2 * math.pi)
        c.fill()
        mid = anchor + (end - anchor) * q
        rgb(c, BLACK, out_a)
        c.set_line_width(3)
        c.move_to(*anchor)
        c.line_to(*mid)
        c.stroke()
        labels.append((end, txt, sup, c01((pr - 0.4) / 0.45), anchor[1] > end[1]))
    img.alpha_composite(to_pil(s))
    for end, txt, sup, pl, above in labels:
        im = with_sup(R15.line_img(txt, 60, 750, BLACK), R15.line_img(sup, 30, 750, OR))
        x = min(max(end[0], 40 + im.width / 2), W - 40 - im.width / 2)
        y = end[1] + (-1 if above else 1) * (im.height / 2 + 14)
        reveal_c(img, im, x, y, pl, a=out_a)


def product_bg(bt):
    img = solid(WHITE)
    g = scaled(headline("PUCK", 620, GREY), lerp(1.0, 1.06, c01((bt - 4) / 4)))
    reveal_c(img, g, W / 2, H / 2 + 20, c01((bt - 4.35) / 0.5))
    return img


def product_frame(t, fidx):
    bt = t / B
    img = product_bg(bt)
    rows, lens, pk = np.zeros((KSUB, 13)), np.zeros((KSUB, 2)), np.zeros((KSUB, 7))
    for j in range(KSUB):
        tk = max(t + ((j + 0.5) / KSUB - 0.5) * (0.6 / FPS), 4 * B)
        pos, tgt, up, fov, p, th, _ = product_state(tk)
        rows[j] = cam_row(pos, tgt, up, fov)
        pk[j] = (p[0], p[1], p[2], th, 1.0, 0.0, tk)
    rgbp, cov = render_puck(W, H, rows, lens, pk, fidx + 20)
    lay = layer_from(rgbp, cov)
    u = c01((bt - 4) / 1.2)
    if bt < LAUNCH[0] + 0.1:
        img.alpha_composite(soft_shadow(lay, lerp(15, 30, u), lerp(0.32, 0.2, u)), (0, int(lerp(45, 80, u))))
    img.alpha_composite(lay)
    pos, tgt, up, fov, p, th, az = product_state(t)
    callouts(img, cam_row(pos, tgt, up, fov), p, az, t)
    return img


# ================================================================= 8–16: Schüsse mit Wisch-Übergang (3D)
SHOT_C = np.array([0.0, 60.0, 0.0])
SHOT_F = np.array([0.0, -0.22, -1.0]) / np.linalg.norm([0.0, -0.22, -1.0])
SHOT_D = 15.0
#         Wort        Fläche  Schrift Label  Flugwinkel (Bildschirm, Grad)
SHOTS = [("SNAP", OR, BLACK, WHITE, 0), ("SLAP", BLACK, WHITE, OR, 180), ("WRIST", WHITE, BLACK, OR, 125),
         ("BACKHAND", OR, BLACK, WHITE, -35), ("DANGLE", BLACK, WHITE, OR, 200), ("DEKE", WHITE, BLACK, OR, 55),
         ("TOE DRAG", OR, BLACK, WHITE, 225), ("SNIPE", BLACK, WHITE, OR, -10), (None, WHITE, BLACK, OR, 0)]
FLY_IN, FLY_OUT = 0.11, 0.15                      # Flug k: t_k - FLY_IN ... t_k + FLY_OUT, t_k = Beat 8 + k
L_FLY = 10.5


def shot_basis():
    return P3.look_at(SHOT_C, SHOT_C + SHOT_F, np.array([0.0, 1.0, 0.0]))


SHOT_ROW = P3.cam_row(SHOT_C, *shot_basis(), 40.0)
CENTRE = SHOT_C + SHOT_F * SHOT_D


def fly_dir(k):
    r, u, _ = shot_basis()
    a = math.radians(SHOTS[k][4])
    return r * math.cos(a) + u * math.sin(a), np.array([math.cos(a), -math.sin(a)])


def s_lin(k, t):
    tk = (8 + k) * B
    return lerp(-L_FLY, L_FLY, (t - (tk - FLY_IN)) / (FLY_IN + FLY_OUT))


def puck_pos(k, t):
    d, _ = fly_dir(k)
    if k < 8:
        return CENTRE + d * s_lin(k, t)
    x = (t - (16 * B - FLY_IN)) / (FLY_IN + 0.3)
    return CENTRE + d * (-L_FLY * (1 - e_out(x, 4)))


def spin_at(k, t):
    tau = t - (8 + k) * B
    if k < 8 or tau < 0:
        return THETA0 + 30.0 * tau
    return THETA0 + 15.0 * (1 - math.exp(-2 * tau)) + 0.9 * tau


def shot_scene(k, lt):
    word, bg, fg, sup_col, _ = SHOTS[k]
    img = solid(bg)
    main = fit_headline(word, fg, 960, 330)
    im = with_sup(main, R15.line_img(f"({k + 1:02d})", 40, 800, sup_col), 10, 0.7)
    paste_c(img, scaled(im, lerp(1.0, 1.05, c01(lt / B))), W / 2, H / 2)
    return img


def question_scene(t):
    bt = t / B
    img = solid(WHITE)
    po = c01((bt - 19.8) / 0.2)
    reveal_c(img, headline("WHICH SHOT", 168, BLACK), W / 2, 520, c01((bt - 17) / 0.35), po)
    reveal_c(img, headline("IS YOURS?", 168, BLACK), W / 2, 1390, c01((bt - 18) / 0.35), po)
    opts = R15.line_img("SNAP · SLAP · WRIST · BACKHAND", 38, 800, OR, track=5)
    reveal_c(img, opts, W / 2, 1515, c01((bt - 19) / 0.35), po)
    return img


def scene_at(k, t):
    """Fläche nach Flug k (k = 8: Frage)."""
    return shot_scene(k, t - (8 + k) * B) if k < 8 else question_scene(t)


_PEND = None


def product_end():
    global _PEND
    if _PEND is None:
        _PEND = product_bg(8.0)
    return _PEND


def puck_layer(k, t, fidx, bob=False, orbit=False):
    rows, lens, pk = np.zeros((KSUB, 13)), np.zeros((KSUB, 2)), np.zeros((KSUB, 7))
    vis = False
    for j in range(KSUB):
        tj = t + ((j + 0.5) / KSUB - 0.5) * (0.55 / FPS)
        rows[j] = SHOT_ROW
        if orbit:
            o = 9 * math.sin((tj - 16.7 * B) * 1.6) * c01((tj / B - 16.7) * 2)
            az = math.degrees(math.atan2(-SHOT_F[2], -SHOT_F[0])) + o
            rows[j] = cam_row(sph(CENTRE, SHOT_D, az, math.degrees(math.asin(-SHOT_F[1]))), CENTRE,
                              np.array([0.0, 1.0, 0.0]), 40.0)
        tk = (8 + k) * B
        if k < 8 and not (tk - FLY_IN - 0.02 <= tj <= tk + FLY_OUT + 0.02):
            pk[j] = (0, -500, 0, 0, 0.0, 0.0, tj)
            continue
        p = puck_pos(k, tj)
        if bob:
            p = p + np.array([0, 0.25 * math.sin((tj - 16.4 * B) * 3.0) * c01((tj / B - 16.4) * 2), 0])
        pk[j] = (p[0], p[1], p[2], spin_at(k, tj), 1.0, 0.0, tj)
        vis = True
    if not vis:
        return None
    rgbp, cov = render_puck(W, H, rows, lens, pk, fidx + 50)
    return layer_from(rgbp, cov)


_YY, _XX = np.mgrid[0:H, 0:W].astype(np.float32)


def shot_frame(t, fidx):
    bt = t / B
    k = None
    for kk in range(9):
        tk = (8 + kk) * B
        if tk - FLY_IN <= t <= tk + FLY_OUT:
            k = kk
    if k is None:
        kk = int(bt - 8)
        return scene_at(kk, t)
    old = scene_at(k - 1, t) if k > 0 else product_end()
    new = scene_at(k, t)
    d3, d2 = fly_dir(k)
    pb, _ = R15.proj(SHOT_ROW, [CENTRE + d3 * s_lin(k, t)])          # Wischkante läuft linear mit
    side = (_XX - pb[0][0]) * d2[0] + (_YY - pb[0][1]) * d2[1]
    m = Image.fromarray((np.clip(0.5 - side / 3.0, 0, 1) * 255).astype(np.uint8), "L")
    img = Image.composite(new, old, m)
    lay = puck_layer(k, t, fidx)
    if lay is not None:
        if k == 8:
            img.alpha_composite(soft_shadow(lay, 26, 0.2 * c01((t - 16 * B) / 0.2)), (0, 40))
        img.alpha_composite(lay)
    return img


def question_frame(t, fidx):
    img = question_scene(t)
    lay = puck_layer(8, t, fidx, bob=True, orbit=True)
    img.alpha_composite(soft_shadow(lay, 26, 0.2), (0, 40))
    img.alpha_composite(lay)
    return img


# ================================================================= 20–26: Logo
def end_frame(t):
    bt = t / B
    img = solid(BLACK)
    sp, _ = sprite()
    m = mark(200)
    word = R15.line_img("bladesandpucks", 92, 800, WHITE, track=-2)
    total = m.width + 36 + word.width
    q = e_out(c01((bt - 21.6) / 0.6), 4)
    mx, my = lerp(W / 2, W / 2 - total / 2 + m.width / 2, q), H / 2
    slot = (mx - m.width / 2 + MARK_SLOT[0] * m.width, my - m.height / 2 + MARK_SLOT[1] * m.height)
    fly = e_io(c01((bt - 20.3) / 0.85))
    d = lerp(500, MARK_SLOT[2] * m.width * 0.62, fly)
    cx, cy = lerp(W / 2, slot[0], fly), lerp(H / 2, slot[1], fly)
    ang = 540 * (1 - (1 - c01((bt - 20) / 1.2)) ** 2)
    ma = c01((bt - 21.0) / 0.3)
    if ma > 0:
        paste_c(img, m, mx, my, ma)
    pa = 1 - c01((bt - 21.1) / 0.25)
    if pa > 0:
        paste_c(img, scaled(sp.rotate(ang, Image.BICUBIC), d / 680), cx, cy, pa)
    if q > 0:
        vis = int(word.width * q)
        if vis > 2:
            R15.put(img, word.crop((0, 0, vis, word.height)), mx + m.width / 2 + 36, my - word.height / 2 + 8)
    reveal_c(img, R15.line_img("THE PUCK  pt. 2", 36, 750, DIM, track=6), W / 2, H / 2 + 200, c01((bt - 22.3) / 0.4))
    return img


# ================================================================= Bild
def averaged(fn, t, n, lo, hi):
    acc = None
    for j in range(n):
        tj = min(max(t + ((j + 0.5) / n - 0.5) * (0.6 / FPS), lo), hi)
        a = np.asarray(fn(tj).convert("RGB"), np.float32)
        acc = a if acc is None else acc + a
    return acc / n / 255


def compose(t, fidx=0):
    bt = t / B
    if bt < 4:
        arr = averaged(grid_frame, t, SUB2D if bt > 1.9 else 1, 0.0, 4 * B - 1e-4)
    elif t < 8 * B - FLY_IN:
        arr = np.asarray(product_frame(t, fidx).convert("RGB"), np.float32) / 255
    elif t <= 16 * B + FLY_OUT:
        arr = np.asarray(shot_frame(t, fidx).convert("RGB"), np.float32) / 255
    elif bt < 20:
        arr = np.asarray(question_frame(t, fidx).convert("RGB"), np.float32) / 255
    else:
        arr = averaged(end_frame, t, SUB2D if bt < 22.3 else 1, 20 * B, DUR)
    lc = t - 20 * B
    if 0 <= lc < 0.3:                                # Zoom-Punch auf dem Schnitt zum Logo
        zp = 1 + 0.04 * math.exp(-lc * 14)
        pil = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))
        w2, h2 = W / zp, H / zp
        pil = pil.transform((W, H), Image.EXTENT, ((W - w2) / 2, (H - h2) / 2, (W + w2) / 2, (H + h2) / 2),
                            Image.BILINEAR)
        arr = np.asarray(pil, np.float32) / 255
    arr = arr + np.random.default_rng(fidx + 3).normal(0, 0.007, arr.shape[:2])[..., None]
    return (np.clip(arr, 0, 1) * 255).astype(np.uint8)


# ================================================================= Musik (Trap, 140 BPM, a-Moll, Stereo)
SR = 44100


def make_audio(path):
    n = int((DUR + 0.6) * SR)
    rng = np.random.default_rng(20)
    L, Rr = np.zeros(n), np.zeros(n)
    send = np.zeros((n, 2))

    def tt(sec):
        return np.arange(int(sec * SR)) / SR

    def put_(sig, at, vol=1.0, pan=0.0, rev=0.0):
        st = int(round(at * SR))
        if st >= n:
            return
        if st < 0:
            sig, st = sig[-st:], 0
        e = min(n, st + len(sig))
        s = sig[: e - st] * vol
        gl, gr = math.cos((pan + 1) * math.pi / 4) * 1.41, math.sin((pan + 1) * math.pi / 4) * 1.41
        L[st:e] += s * gl
        Rr[st:e] += s * gr
        if rev:
            send[st:e, 0] += s * gl * rev
            send[st:e, 1] += s * gr * rev

    def lp(x, k):
        c = np.cumsum(np.concatenate([np.zeros(k), x]))
        return (c[k:] - c[:-k]) / k

    def hp(x, k):
        return x - lp(x, k)

    def noise(sec):
        return rng.standard_normal(int(sec * SR))

    def kick(vol=1.0):
        x = tt(0.38)
        f = 46 + 190 * np.exp(-x * 38)
        body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 8.5)
        return np.tanh(body * 3.0 + hp(noise(0.38), 2) * np.exp(-x * 400) * 0.6) * vol

    def clap(vol=1.0):
        x = tt(0.3)
        env = sum((x >= d) * np.exp(-np.maximum(x - d, 0) * 70) for d in (0.0, 0.009, 0.019, 0.03))
        return hp(lp(noise(0.3), 2), 6) * (env * 0.45 + np.exp(-x * 13) * 0.55) * 0.8 * vol

    def hat(vol=0.16, dec=150):
        return hp(noise(0.05), 1) * np.exp(-tt(0.05) * dec) * vol

    def b808(freq, dur, glide=0.0, f_to=None):
        x = tt(dur)
        f = freq * (1 + glide * np.exp(-x * 10))
        if f_to:
            f = f + (f_to - freq) * np.clip((x - dur * 0.5) / (dur * 0.3), 0, 1)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * 2.6) * np.minimum(x / 0.003, 1) * np.exp(-x * 1.1) * 0.8

    def bell(freq, dur=0.7, vol=0.2):
        x = tt(dur)
        mod = np.sin(2 * np.pi * freq * 3.5 * x) * 2.2 * np.exp(-x * 6)
        return np.sin(2 * np.pi * freq * x + mod) * np.exp(-x * 4.5) * np.minimum(x / 0.002, 1) * vol

    def pad(freqs, dur, vol=0.08):
        x = tt(dur)
        sig = sum(((x * f * dt) % 1) * 2 - 1 for f in freqs for dt in (0.997, 1.003))
        return lp(lp(sig, 40), 40) * np.minimum(x / 0.4, 1) * np.clip((dur - x) / 0.6, 0, 1) * vol

    def whoosh(dur=0.4, vol=1.0):
        x = tt(dur)
        nz = noise(dur)
        env = np.exp(-((x / dur - 0.55) ** 2) * 18)
        kx = 40 - 34 * (x / dur)
        out = sum(lp(nz, kk) * np.exp(-((kx - kk) ** 2) / 60) for kk in (36, 18, 8, 4))
        return out * env * 1.8 * vol

    def riser(dur, vol=1.0):
        x = tt(dur)
        sw = np.sin(2 * np.pi * np.cumsum(220 + 2400 * (x / dur) ** 2.2) / SR) * (x / dur) ** 3 * 0.18
        return (hp(noise(dur), 3) * (x / dur) ** 2.5 * 0.32 + sw) * vol

    def impact(vol=1.0, f0=38):
        x = tt(1.6)
        f = f0 + 140 * np.exp(-x * 14)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 2.4) * 2.6) * vol

    def tick(freq=1900, vol=0.18):
        x = tt(0.06)
        return (np.sin(2 * np.pi * freq * x) + 0.5 * np.sin(2 * np.pi * freq * 2.01 * x)) * np.exp(-x * 80) * vol

    def pop(vol=0.3):
        x = tt(0.12)
        return np.sin(2 * np.pi * np.cumsum(900 + 1400 * np.exp(-x * 60)) / SR) * np.exp(-x * 35) * vol

    A1, F1, G1, E1 = 55.0, 43.65, 49.0, 41.2
    roots = [A1, F1, G1, E1]
    mel = [880.0, 1046.5, 1318.5, 1046.5, 987.8, 880.0, 784.0, 659.25]

    # 0–4 Intro: Tick auf jeder Drehung, Glocken, Riser + Snare-Roll in den Zoom
    put_(impact(0.9, 42), 0.0, rev=0.3)
    for b in range(4):
        put_(tick(2300 if b % 2 else 1800, 0.25), b * B, pan=-0.3 if b % 2 else 0.3, rev=0.2)
        put_(whoosh(0.22, 0.25), b * B - 0.03)
    for k8 in range(8):
        put_(bell(mel[k8] * 0.5, 0.6, 0.12), k8 * B / 2, pan=0.2 * math.sin(k8), rev=0.35)
    for b16 in range(8, 16):
        put_(hat(0.05 + 0.012 * (b16 - 8)), b16 * B / 4, pan=0.4)
    put_(riser(2 * B, 1.0), 2 * B, rev=0.2)
    for b16 in range(8, 16):
        put_(clap(0.08 + 0.06 * (b16 - 8)), (2 * B) + (b16 - 8) * B / 4, rev=0.1)
    put_(pad([220.0, 261.6, 329.6], 4 * B + 0.4, 0.05), 0.0, rev=0.3)

    # 4–8 Product: Halbzeit-Beat, Pops für die Callouts
    put_(impact(1.2, 36), 4 * B, rev=0.4)
    for b in (4, 6.5):
        put_(kick(), b * B)
    put_(clap(0.8), 6 * B, rev=0.35)
    put_(b808(A1, 2 * B, 0.6), 4 * B)
    put_(b808(F1, 1.5 * B, 0.3, G1), 6.5 * B)
    for b in np.arange(4, 8, 0.5):
        put_(hat(0.12 if b % 1 == 0 else 0.07), b * B, pan=0.35)
    for k8 in range(8):
        put_(bell(mel[(k8 + 2) % 8], 0.7, 0.1), (4 + k8 / 2) * B, pan=-0.25, rev=0.4)
    for i, (b0, _, _) in enumerate(CALLOUT):
        put_(pop(0.35), b0 * B + 0.02, pan=(-0.4, 0.4, -0.2)[i], rev=0.25)
    put_(pad([220.0, 261.6, 329.6, 440.0], 4 * B, 0.06), 4 * B, rev=0.3)
    put_(riser(0.75 * B, 0.7), 7.25 * B)
    put_(whoosh(0.35, 0.9), LAUNCH[0] * B, pan=0.6)

    # 8–16 Schüsse: voller Beat, Whoosh pro Flug (Panorama nach Flugrichtung)
    for b in np.arange(8, 16, 0.5):
        pos = b % 4
        if pos in (0.0, 2.5):
            put_(kick(), b * B)
        if pos in (1.0, 3.0):
            put_(clap(), b * B, rev=0.3)
        put_(hat(0.15 if b % 1 == 0 else 0.1), b * B, pan=0.3)
        if pos == 3.5:
            for j in range(1, 4):
                put_(hat(0.09), b * B + j * B / 6, pan=0.3)
        if pos == 1.5:
            for j in range(4):
                put_(hat(0.07, 220), b * B + j * B / 8, pan=-0.3)
        bar = int((b - 8) // 4)
        if pos == 0.0:
            put_(b808(roots[(bar * 2) % 4], 2.4 * B, 0.6), b * B)
        if pos == 2.5:
            put_(b808(roots[(bar * 2 + 1) % 4], 1.4 * B, 0.4), b * B)
        put_(bell(mel[int(b * 2) % 8], 0.5, 0.075), b * B, pan=-0.2, rev=0.3)
    for k in range(8):
        a = math.radians(SHOTS[k][4])
        put_(whoosh(0.3, 0.85), (8 + k) * B - 0.17)
        put_(whoosh(0.18, 0.4), (8 + k) * B - 0.06, pan=0.7 * math.cos(a))
    put_(pad([220.0, 261.6, 329.6], 8 * B, 0.04), 8 * B, rev=0.3)

    # 16–20 Frage: Puck stoppt, Text-Pops
    put_(whoosh(0.35, 0.9), 16 * B - 0.17)
    put_(impact(0.9, 40), 16 * B + 0.12, rev=0.35)
    for b in np.arange(16, 20, 0.5):
        pos = b % 4
        if pos in (0.0, 2.5):
            put_(kick(), b * B)
        if pos in (1.0, 3.0):
            put_(clap(0.8), b * B, rev=0.35)
        put_(hat(0.1 if b % 1 == 0 else 0.06), b * B, pan=0.3)
    put_(b808(A1, 2 * B, 0.6), 16 * B)
    put_(b808(G1, 2 * B, 0.3, E1), 18 * B)
    for b in (17, 18, 19):
        put_(pop(0.3), b * B, rev=0.3)
    put_(riser(B, 0.8), 19 * B)

    # 20–26 Logo: Drums aus, Glockenakkord, langer 808
    put_(impact(1.2, 34), 20 * B, rev=0.5)
    put_(whoosh(0.5, 0.6), 20.3 * B)
    put_(bell(440.0, 3.0, 0.22) + bell(523.25, 3.0, 0.16) + bell(659.25, 3.0, 0.14), 21.1 * B, rev=0.6)
    put_(b808(A1, 3.2, 0.6), 21.1 * B)
    put_(tick(2600, 0.2), 21.6 * B, rev=0.3)
    put_(pad([220.0, 329.6, 440.0], 6 * B, 0.05), 20 * B, rev=0.4)

    # Hall: Faltung mit abklingendem Rauschen
    irn = int(1.8 * SR)
    xr = np.arange(irn) / SR
    ir_l = lp(rng.standard_normal(irn) * np.exp(-xr / 0.42), 6)
    ir_r = lp(rng.standard_normal(irn) * np.exp(-xr / 0.42), 6)
    mix = np.stack([L + fftconvolve(send[:, 0], ir_l)[:n] * 0.035,
                    Rr + fftconvolve(send[:, 1], ir_r)[:n] * 0.035], 1)
    mix /= np.percentile(np.abs(mix), 99.9) + 1e-9
    mix = np.tanh(mix * 1.15)
    mix *= np.clip((DUR + 0.5 - np.arange(n) / SR) / 0.5, 0, 1)[:, None]
    mix = mix / np.max(np.abs(mix)) * 0.95
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


def main():
    os.chdir(HERE)
    make_audio("audio_puck2.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_puck2.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "19",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart",
           "reel20_puck2.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(9 * B - 0.02, 9999)).save("reel20_thumbnail.jpg", quality=92)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "reel20_puck2.mp4", "-c:v", "copy", "-an",
                    "reel20_puck2_ohne_ton.mp4"])
    print("fertig: reel20_puck2.mp4")


if __name__ == "__main__":
    main()
