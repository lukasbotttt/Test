"""Instagram-Bild #2: WHEN WOULD YOU PULL THE GOALIE? - 3D-Standbild im 4:5-Format (1080x1350), weisses Studio.

Held: ein leeres Tor (Goalie gezogen) aus hoher Frontalperspektive mit Torraum (Crease), dazu eine grosse Anzeigetafel
(Stand 1:2, 3. Drittel) und ein Zeitstrahl des 3. Drittels (20:00 bis 0:00) mit "?"-Regler. Es steht keine Antwort im Bild:
Die Studie (Asness & Brown 2018) gehoert in Caption/Kommentare.
Fakten im Bild: 1:2 + "DOWN BY ONE GOAL" (ein Tor Rueckstand), 3RD = 3. Drittel, ein Drittel dauert 20 Minuten
(NHL Official Rules 2023-24: "three (3) regular twenty (20) minute periods").
Technik: Eis (Raytracer puck3d), Tor-Gestaenge (Mesh-Rasterizer mesh3d), Netz + Grafik (cairo), Typo (Inter).
Gerendert in doppelter Aufloesung, danach mit LANCZOS auf 1080x1350 verkleinert.
Aufruf: python3 ig02_net.py                      -> ig02_net.jpg
        IGW=540 IGSPP=8 python3 ig02_net.py      (schnelle Vorschau, IGOUT=<Datei> setzt das Ziel)
"""
import math
import os
import time

import cairocffi as cairo
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import gaussian_filter

import mesh3d as M3
import puck3d as P3
import reel15_puck as R15
import reel18_dangle as R18
import reel25_goalline as G

HERE = R15.HERE
W = int(os.environ.get("IGW", "2160"))
H = W * 5 // 4
S = W / 1080                                     # Layout in 1080er-Einheiten
SPP = int(os.environ.get("IGSPP", "64"))
OUT = os.environ.get("IGOUT", os.path.join(HERE, "ig02_net.jpg"))

INK, ORANGE = R15.INK, R15.ORANGE
RED = (225, 30, 40)
BLUE = (40, 110, 210)
GREY = (110, 114, 126)
LINEGREY = (214, 218, 226)
HALO = (255, 255, 255)

GX = G.GOAL_X                                    # Torlinie bei x = 1068 (Tor oeffnet sich nach -x)
PR = G.PR
ZC, YC = 36.0 + PR, 48.0 + PR                    # Pfostenachsen (wie G.FRAME)

def frame_meshes(k=1.7):
    """Tor-Gestaenge wie G.frame_meshes(), aber fuer die Grafik etwas kraeftiger (Rohre k-mal dicker, gleiche Achsen)."""
    red, white = M3.MAT_IDS["post_red"], M3.MAT_IDS["frame_white"]
    pr = PR * k
    out = []
    for sz in (-1.0, 1.0):
        pts = np.array([[GX, y, sz * ZC] for y in np.linspace(-0.5, YC, 14)])
        out.append(M3.tube_along(pts, np.full(len(pts), pr), lambda u: red, nr=32))
        out.append(G.sphere_mesh(np.array([GX, YC, sz * ZC]), pr, "post_red"))
    pts = np.array([[GX, YC, z] for z in np.linspace(-ZC, ZC, 30)])
    out.append(M3.tube_along(pts, np.full(len(pts), pr), lambda u: red, nr=32))
    phi = np.linspace(0, math.pi, 48)
    base = np.stack([GX + 40 * np.sin(phi), np.full_like(phi, 0.9 * k), -ZC * np.cos(phi)], 1)
    out.append(M3.tube_along(base, np.full(len(base), 0.9 * k), lambda u: white, nr=16))
    top = np.stack([GX + 20 * np.sin(phi), np.full_like(phi, YC), -ZC * np.cos(phi)], 1)
    out.append(M3.tube_along(top, np.full(len(top), 0.55 * k), lambda u: white, nr=12))
    return out


# ---------------------------------------------------------------- Kamera (hoch, frontal, leicht seitlich)
EL = math.radians(float(os.environ.get("IGEL", "32")))       # Elevation
AZ = math.radians(float(os.environ.get("IGAZ", "24")))       # seitlicher Versatz
DIST = float(os.environ.get("IGDIST", "348"))
FOV = float(os.environ.get("IGFOV", "32"))
NET_PX = [float(v) for v in os.environ.get("IGNET", "500,800").split(",")]    # Bildposition der Tormitte (1080x1350)
CENTER = np.array([GX + 14.0, 20.0, 0.0])
UP = np.array([0.0, 1.0, 0.0])

M3.MAT_SPEC[M3.MAT_IDS["post_red"]] = 1.5                       # glaenzendere Pfosten
# Licht: von vorn links oben, Schatten fallen nach hinten rechts
M3.LIGHT = np.array([-0.55, 1.0, -0.45])                    # Schattierung der Pfosten (Hauptlicht vorn links)
M3.LIGHT /= np.linalg.norm(M3.LIGHT)
SH_LIGHT = tuple(float(v) for v in os.environ.get("IGSH", "0.5,1.0,-0.2").split(","))   # Schatten fallen zur Kamera hin


def camera():
    pos = CENTER + DIST * np.array([-math.cos(EL) * math.cos(AZ), math.sin(EL), -math.cos(EL) * math.sin(AZ)])
    tgt = CENTER.copy()
    want = np.array([NET_PX[0] / 1080 * 2 - 1, 1 - NET_PX[1] / 1350 * 2])
    for _ in range(14):
        r, u, f = P3.look_at(pos, tgt, UP)
        row = P3.cam_row(pos, r, u, f, FOV)
        d = CENTER - pos
        z = d @ f
        nx = (d @ r) / z / (row[12] * W / H)
        ny = (d @ u) / z / row[12]
        tgt = tgt + (nx - want[0]) * row[12] * (W / H) * z * r + (ny - want[1]) * row[12] * z * u
    r, u, f = P3.look_at(pos, tgt, UP)
    return P3.cam_row(pos, r, u, f, FOV), pos


def proj(row, pts):
    return P3.project(row, np.asarray(pts, float).reshape(-1, 3), W, H)


def ppi(row, z):
    """Pixel pro Zoll in der Tiefe z."""
    return (H / 2) / (row[12] * np.maximum(z, 1e-3))


def ice_hit(row):
    """Schnittpunkt jedes Pixelstrahls mit der Eisebene (x, z) + Maske."""
    xs = ((np.arange(W) + 0.5) / W * 2 - 1).astype(np.float32)
    ys = (1 - (np.arange(H) + 0.5) / H * 2).astype(np.float32)
    nx, ny = np.meshgrid(xs, ys)
    pos, r, u, f, tanh = row[0:3], row[3:6], row[6:9], row[9:12], row[12]
    d = f[None, None, :] + nx[..., None] * (tanh * W / H) * r[None, None, :] + ny[..., None] * tanh * u[None, None, :]
    dy = d[..., 1]
    hit = dy < -1e-4
    tt = np.where(hit, -pos[1] / np.where(hit, dy, -1.0), 0.0)
    return pos[0] + tt * d[..., 0], pos[2] + tt * d[..., 2], hit


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- cairo-Ebenen
def new_layer():
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    return s, cairo.Context(s)


def layer_arrays(s):
    s.flush()
    a = np.frombuffer(s.get_data(), np.uint8).reshape(H, W, 4).astype(np.float32) / 255
    return a[..., [2, 1, 0]], a[..., 3]


def rgba(ctx, col, a=1.0):
    ctx.set_source_rgba(col[0] / 255, col[1] / 255, col[2] / 255, a)


def rrect(ctx, x, y, w, h, r):
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    ctx.close_path()


def poly(ctx, xy):
    ctx.move_to(*xy[0])
    for p in xy[1:]:
        ctx.line_to(*p)


# ---------------------------------------------------------------- Tornetz (Vektor)
PHI = np.linspace(0, math.pi, 61)


def net_base(phi):
    return np.stack([GX + 40 * np.sin(phi), np.full_like(phi, 0.9), -ZC * np.cos(phi)], -1)


def net_top(phi):
    return np.stack([GX + 20 * np.sin(phi), np.full_like(phi, YC), -ZC * np.cos(phi)], -1)


def net_lines(nu=34, nv=13):
    """Maschen als Polylinien (Welt) + Flaechen (Welt) fuer die milchige Fuellung."""
    lines, fills = [], []
    b, t = net_base(PHI), net_top(PHI)
    for j in range(1, nv):                                         # waagerechte Maschen (Seiten + Rueckwand)
        v = j / nv
        lines.append(b + (t - b) * v)
    ph = np.linspace(0, math.pi, nu + 1)
    for p in ph[1:-1]:                                             # senkrechte Maschen
        bb, tt = net_base(np.array([p]))[0], net_top(np.array([p]))[0]
        lines.append(np.array([bb + (tt - bb) * v for v in np.linspace(0, 1, 8)]))
    fills.append(np.concatenate([b, t[::-1]]))                     # Wandflaeche (Band)
    for z in np.linspace(-ZC, ZC, 21)[1:-1]:                       # Dach (flach, y = YC)
        d = 20 * math.sqrt(max(0.0, 1 - (z / ZC) ** 2))
        lines.append(np.array([[GX, YC, z], [GX + d, YC, z]]))
    for s in (0.25, 0.5, 0.75):
        lines.append(np.stack([GX + s * 20 * np.sin(PHI), np.full_like(PHI, YC), -ZC * np.cos(PHI)], -1))
    fills.append(np.concatenate([np.array([[GX, YC, -ZC], [GX, YC, ZC]]), net_top(PHI)[::-1]]))
    return lines, fills


NET_LINES, NET_FILLS = net_lines()


def net_layer(row, mirror=False, a_mul=1.0, w_mul=1.0):
    s, ctx = new_layer()
    sg = np.array([1.0, -1.0 if mirror else 1.0, 1.0])
    for fl in NET_FILLS:
        xy, z = proj(row, fl * sg)
        poly(ctx, xy)
        ctx.close_path()
        rgba(ctx, (206, 214, 228), 0.34 * a_mul)
        ctx.fill()
    for pl in NET_LINES:
        xy, z = proj(row, pl * sg)
        if (z < 2).any():
            continue
        ctx.set_line_width(float(np.clip(0.13 * ppi(row, z.mean()) * w_mul, 1.1 * S, 4.0 * S)))
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        rgba(ctx, (96, 106, 128), 0.70 * a_mul)
        poly(ctx, xy)
        ctx.stroke()
    return layer_arrays(s)


def net_shadow_layer(row):
    """Schatten des Netzes auf dem Eis (Netzlinien entlang des Lichts aufs Eis projiziert)."""
    s, ctx = new_layer()
    sl = np.asarray(SH_LIGHT, float)
    sl /= np.linalg.norm(sl)
    for pl in NET_LINES:
        sh = pl - sl[None, :] * (pl[:, 1:2] / sl[1])
        sh[:, 1] = 0.05
        xy, z = proj(row, sh)
        if (z < 2).any():
            continue
        ctx.set_line_width(float(np.clip(0.2 * ppi(row, z.mean()), 1.5 * S, 5.0 * S)))
        rgba(ctx, (60, 70, 90), 0.55)
        poly(ctx, xy)
        ctx.stroke()
    _, a = layer_arrays(s)
    return gaussian_filter(a, 2.2 * S)


# ---------------------------------------------------------------- Ice-level graphics
def ring_pts(cx, cz, r, a0=0.0, a1=2 * math.pi, n=160):
    a = np.linspace(a0, a1, n)
    return np.stack([cx + r * np.cos(a), np.full(n, 0.15), cz + r * np.sin(a)], 1)


GHOST_C = np.array([GX - 28.0, 0.0, float(os.environ.get("IGGZ", "-9"))])                   # Stammplatz des Goalies im Torraum
GHOST_R = 21.0


def ghost_ring(row):
    """Gestrichelter Ring + helle Scheibe auf dem Eis: der leere Platz des gezogenen Goalies (Marker, kein Spieler).
    Gibt (rgb, alpha, Bildmitte in 1080er-Einheiten, Pixelradius) zurueck."""
    s, ctx = new_layer()
    a = np.linspace(0, 2 * math.pi, 120)
    pts = np.stack([GHOST_C[0] + GHOST_R * np.cos(a), np.full(120, 0.15), GHOST_C[2] + GHOST_R * np.sin(a)], 1)
    xy, z = proj(row, pts)
    poly(ctx, xy)
    ctx.close_path()
    rgba(ctx, (255, 255, 255), 0.55)
    ctx.fill_preserve()
    ctx.set_line_width(6.5 * S)
    ctx.set_dash([20 * S, 13 * S])
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    rgba(ctx, BLUE, 0.95)
    ctx.stroke()
    c_xy, _ = proj(row, GHOST_C + np.array([0.0, 0.15, 0.0]))
    rpx = float(ppi(row, z.mean()) * GHOST_R)
    rgb, al = layer_arrays(s)
    return rgb, al, (c_xy[0][0] / S, c_xy[0][1] / S), rpx / S


# ---------------------------------------------------------------- Typo
def word(txt, size, col):
    """Grosse Schlagzeile mit Lichthof; gibt (Bild, Kappen-Bounding-Box ohne Glow) zurueck."""
    sz = int(size * S)
    im = R18.word_img(txt, sz, col, HALO, cache=False)
    bb = R15.line_img(txt, sz, 900, col, cache=False).getchannel("A").point(lambda v: 255 if v > 90 else 0).getbbox()
    return im, (bb[0] + 40, bb[1] + 40, bb[2] + 40, bb[3] + 40)


def lead(txt, size, col):
    """Kleinere Zeile mit dezentem Lichthof und leichtem Schatten (bleibt scharf lesbar)."""
    sz = int(size * S)
    raw = R15.line_img(txt, sz, 900, col, cache=False)
    pad = 40
    sh = Image.new("RGBA", (raw.width + 2 * pad, raw.height + 2 * pad), (0, 0, 0, 0))
    a = Image.new("L", sh.size, 0)
    a.paste(raw.getchannel("A"), (pad, pad))
    glow = Image.new("RGBA", sh.size, HALO + (0,))
    glow.putalpha(a.filter(ImageFilter.GaussianBlur(max(3, sz // 16))).point(lambda v: min(255, int(v * 1.2))))
    dark = Image.new("RGBA", sh.size, (0, 0, 0, 0))
    dark.putalpha(a.filter(ImageFilter.GaussianBlur(3 * S)).point(lambda v: int(v * 0.30)))
    sh.alpha_composite(glow)
    sh.alpha_composite(dark, (int(2 * S), int(4 * S)))
    sh.alpha_composite(raw, (pad, pad))
    bb = raw.getchannel("A").point(lambda v: 255 if v > 90 else 0).getbbox()
    return sh, (bb[0] + pad, bb[1] + pad, bb[2] + pad, bb[3] + pad)


def lead_fit(txt, col, max_w, max_size):
    size = max_size
    while size > 20:
        im, bb = lead(txt, size, col)
        if (bb[2] - bb[0]) <= max_w * S:
            return im, bb, size
        size -= 1
    return im, bb, size


def word_fit(txt, col, max_w, max_size):
    size = max_size
    while size > 20:
        im, bb = word(txt, size, col)
        if (bb[2] - bb[0]) <= max_w * S:
            return im, bb, size
        size -= 1
    return im, bb, size


def word_parts(parts, size):
    """Mehrfarbige Zeile aus (Text, Farbe)-Teilen; gemeinsame Grundlinie, exakte Zeichenbreiten."""
    sz = int(size * S)
    f = R15.ifont(sz, 900)
    xs, acc = [], ""
    for t, _ in parts:
        xs.append(f.getlength(acc, features=["tnum"]) if acc else 0.0)
        acc += t
    total = f.getlength(acc, features=["tnum"])
    first, bb0 = word(parts[0][0], size, parts[0][1])
    canvas = Image.new("RGBA", (int(total) + 160, first.height), (0, 0, 0, 0))
    boxes = []
    for (t, col), x in zip(parts, xs):
        im, bb = word(t, size, col)
        canvas.alpha_composite(im, (int(round(x)), 0))
        boxes.append((bb[0] + x, bb[1], bb[2] + x, bb[3]))
    return canvas, (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes),
                    max(b[3] for b in boxes))


def line(txt, size, wght, col, track=0.0):
    return R15.line_img(txt, int(size * S), wght, col, track=track * S, cache=False)


def vis_bbox(im):
    return im.getchannel("A").point(lambda v: 255 if v > 90 else 0).getbbox()


def paste_top(L, im, cx, top, bb=None):
    """Zentriert in x, sichtbare Oberkante bei y = top (1080er-Einheiten). Gibt die sichtbare Unterkante zurueck."""
    bb = bb or vis_bbox(im)
    x = cx * S - (bb[0] + bb[2]) / 2
    y = top * S - bb[1]
    L.alpha_composite(im, (int(round(x)), int(round(y))))
    return (top * S + (bb[3] - bb[1])) / S


def paste_mid(L, im, cx, cy):
    bb = vis_bbox(im)
    x = cx * S - (bb[0] + bb[2]) / 2
    y = cy * S - (bb[1] + bb[3]) / 2
    L.alpha_composite(im, (int(round(x)), int(round(y))))


def soft_shadow(draw_fn, dy, sigma, alpha):
    s, ctx = new_layer()
    draw_fn(ctx)
    _, a = layer_arrays(s)
    a = gaussian_filter(a, sigma * S)
    a = np.roll(a, int(dy * S), axis=0) * alpha
    return a


# ---------------------------------------------------------------- Anzeigetafel
BUG_W, BUG_H, BUG_F = 860.0, 136.0, 50.0                    # Breite, Hoehe Hauptteil, Hoehe Fussband
BX, BY, BGAP = 124.0, 22.0, 76.0                            # Wertkasten: Breite, Randabstand oben, Abstand (Doppelpunkt)
D1 = 30.0 + 2 * BX + BGAP + 34.0                            # erster Trenner (x relativ zur Karte)
D2 = D1 + 206.0                                             # zweiter Trenner


def bug_geometry(cx, top):
    x0, y0 = (cx - BUG_W / 2) * S, top * S
    return x0, y0, BUG_W * S, (BUG_H + BUG_F) * S


def bug_shapes(cx, top):
    """Vektor-Teil: Karte, Wertkaesten, Fussband (cairo)."""
    x0, y0, w, h = bug_geometry(cx, top)
    hm = BUG_H * S
    sh = soft_shadow(lambda c: (rrect(c, x0, y0, w, h, 38 * S), rgba(c, (0, 0, 0), 1.0), c.fill()), 16, 16, 0.28)
    s, ctx = new_layer()
    ctx.save()
    rrect(ctx, x0, y0, w, h, 38 * S)
    ctx.clip()
    gr = cairo.LinearGradient(0, y0, 0, y0 + hm)
    gr.add_color_stop_rgba(0, 1, 1, 1, 1)
    gr.add_color_stop_rgba(1, 0.945, 0.953, 0.968, 1)
    ctx.set_source(gr)
    ctx.paint()
    rgba(ctx, INK, 1.0)                                     # Fussband
    ctx.rectangle(x0, y0 + hm, w, h - hm)
    ctx.fill()
    ctx.restore()
    rrect(ctx, x0, y0, w, h, 38 * S)
    rgba(ctx, LINEGREY, 1.0)
    ctx.set_line_width(3 * S)
    ctx.stroke()
    for i, (c_top, c_bot) in enumerate((((64, 136, 234), (28, 94, 198)), ((242, 54, 64), (203, 20, 34)))):
        xx = x0 + (30.0 + i * (BX + BGAP)) * S
        yb, hb = y0 + BY * S, hm - 2 * BY * S
        gr = cairo.LinearGradient(0, yb, 0, yb + hb)
        gr.add_color_stop_rgba(0, c_top[0] / 255, c_top[1] / 255, c_top[2] / 255, 1)
        gr.add_color_stop_rgba(1, c_bot[0] / 255, c_bot[1] / 255, c_bot[2] / 255, 1)
        rrect(ctx, xx, yb, BX * S, hb, 24 * S)
        ctx.set_source(gr)
        ctx.fill()
    cxm = x0 + (30.0 + BX + BGAP / 2) * S                   # Doppelpunkt (zwei Punkte)
    rgba(ctx, INK, 1.0)
    for dy in (-19, 19):
        ctx.arc(cxm, y0 + hm / 2 + dy * S, 9 * S, 0, 2 * math.pi)
        ctx.fill()
    rgba(ctx, LINEGREY, 1.0)                                # Trenner
    ctx.set_line_width(3 * S)
    for dx in (D1, D2):
        ctx.move_to(x0 + dx * S, y0 + 30 * S)
        ctx.line_to(x0 + dx * S, y0 + hm - 30 * S)
        ctx.stroke()
    rgb, a = layer_arrays(s)
    return sh, rgb, a


def bug_text(L, cx, top):
    x0, y0, w, h = bug_geometry(cx, top)
    hm = BUG_H * S
    ym = (y0 + hm / 2) / S
    for i, num in enumerate(("1", "2")):
        paste_mid(L, line(num, 100, 900, (255, 255, 255)), (x0 / S) + 30.0 + i * (BX + BGAP) + BX / 2, ym)
    paste_mid(L, line("3RD", 62, 900, INK, track=3), (x0 / S) + (D1 + D2) / 2, ym)
    paste_mid(L, line("?:??", 84, 900, ORANGE), (x0 / S) + (D2 + BUG_W) / 2, ym)
    paste_mid(L, line("DOWN BY ONE GOAL", 24, 800, (255, 255, 255), track=7), (x0 + w / 2) / S, (y0 + hm + (h - hm) / 2) / S)


# ---------------------------------------------------------------- Hauptprogramm
def main():
    t0 = time.time()
    row, campos = camera()
    print("Kamera", np.round(campos, 1), flush=True)

    # --- Eis (Raytracer)
    cams = row[None, :].copy()
    lens = np.array([[0.0, 100.0]])
    pk = np.array([[GX, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0]])
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, SPP, 3, cams, lens, pk, R15.logo_tex(), base, puck, cov)
    img = P3.tonemap(base)
    sat = img.max(-1, keepdims=True) - img.min(-1, keepdims=True)
    neutral = np.clip(1.0 - sat * 9.0, 0, 1)
    img = img * (1 - neutral) + (1.0 - (1.0 - img) * float(os.environ.get("IGICE", "0.62"))) * neutral   # weissere Eisflaeche
    print("Eis", round(time.time() - t0, 1), "s", flush=True)

    # --- hinter dem Tor geht das Eis in den weissen Studiohintergrund ueber (kein Bandenrand im Bild)
    x, z, hit = ice_hit(row)
    bd = np.array([0.958, 0.962, 0.974], np.float32)                      # weisser Studiohintergrund
    dist = np.sqrt((x - GX) ** 2 + z ** 2)
    behind = np.maximum(smoothstep(GX + 40.0, GX + 130.0, x), smoothstep(330.0, 560.0, dist)) * hit + (~hit)
    # leichter Lichtkegel: Eis nahe dem Tor etwas heller, nach aussen weich abfallend
    pool = np.exp(-(((x - (GX - 30.0)) / 330.0) ** 2 + (z / 300.0) ** 2))
    img = img * (0.93 + 0.08 * pool[..., None])
    img = img * (1 - behind[..., None]) + bd[None, None, :] * behind[..., None]

    # --- Torgestaenge (mesh3d), echte Pfosten + gespiegelte Kopie als Eisreflexion
    fr = frame_meshes()
    mir = []
    for m in fr:
        mm = M3.Mesh(m.v * [1, -1, 1], m.n * [1, -1, 1], m.t, m.m, m.uvw)
        mir.append(mm)
    r_rgb, r_a, _, _, r_pos = M3.render(mir, row, W, H, campos, want_pos=True)
    fade = np.clip(1 + r_pos[..., 1] / 34.0, 0, 1) ** 1.6
    k_ref = (0.30 * r_a * fade)[..., None]
    img = img * (1 - k_ref) + (r_rgb / np.maximum(r_a, 1e-3)[..., None]) * k_ref
    nr_rgb, nr_a = net_layer(row, mirror=True, a_mul=0.34)
    nfade = 1.0
    img = img * (1 - nr_a[..., None] * 0.55) + nr_rgb * 0.55
    f_rgb, f_a, shadow, _ = M3.render(fr, row, W, H, campos, shadow_light=SH_LIGHT)
    sh = gaussian_filter(np.clip(shadow, 0, 1), 3 * S)
    nsh = net_shadow_layer(row)
    img = img * (1 - 0.42 * sh[..., None]) * (1 - 0.30 * nsh[..., None])
    print("Gestaenge", round(time.time() - t0, 1), "s", flush=True)

    # --- Graphik auf dem Eis, Netz, Gestaenge
    g_rgb, g_a, g_c, g_r = ghost_ring(row)
    img = img * (1 - g_a[..., None]) + g_rgb
    n_rgb, n_a = net_layer(row)
    img = img * (1 - n_a[..., None]) + n_rgb
    img = img * (1 - f_a[..., None]) + f_rgb

    # --- Text-Ebene (Schlagzeile zuerst: Anzeigetafel richtet sich nach ihrer Unterkante)
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    paste_mid(L, line("NHL RULES EXPLAINED", 30, 800, ORANGE, 9), 540, 78)
    HEAD = os.environ.get("IGHEAD", "B")
    y = 116.0
    if HEAD == "A":
        im1, bb1, _ = word_fit("WHEN WOULD YOU", INK, 940, 98)
        y = paste_top(L, im1, 540, y, bb1) + 26
        im2, bb2 = word_parts([("PULL THE ", INK), ("GOALIE?", RED)], 98)
        y = paste_top(L, im2, 540, y, bb2)
    else:
        im1, bb1, _ = lead_fit("WHEN WOULD YOU PULL THE", INK, 940, 62)
        y = paste_top(L, im1, 540, y, bb1) + 26
        im3, bb3, _ = word_fit("GOALIE?", RED, 940, 190)
        y = paste_top(L, im3, 540, y, bb3)
    print("Headline endet bei", round(y), flush=True)
    BUG_TOP = float(os.environ.get("IGBUG", str(y + 34)))

    # weicher heller Verlauf unten (Lesbarkeit von Zeitstrahl + Aufruf)
    yy_ = np.arange(H, dtype=np.float32)[:, None, None] / S
    fade_b = np.clip((yy_ - 1196.0) / 62.0, 0, 1) ** 1.3 * 0.9
    img = img * (1 - fade_b) + bd[None, None, :] * fade_b

    # --- Anzeigetafel (Vektor)
    sh_b, b_rgb, b_a = bug_shapes(540.0, BUG_TOP)
    img = img * (1 - sh_b[..., None])
    img = img * (1 - b_a[..., None]) + b_rgb

    pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
    bug_text(L, 540.0, BUG_TOP)
    gl = line("G", int(g_r * 0.95), 900, BLUE)
    gl.putalpha(gl.getchannel("A").point(lambda v: int(v * 0.8)))
    paste_mid(L, gl, g_c[0], g_c[1])
    paste_mid(L, line("COMMENT YOUR TIME", 36, 850, INK, track=7), 540, 1258)
    paste_mid(L, line("@BLADESANDPUCKS", 22, 700, GREY, track=6), 540, 1310)
    pil.alpha_composite(L)

    arr = np.asarray(pil.convert("RGB")).astype(np.float32) / 255
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    v = np.clip(np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H * 0.55) / H) ** 2) * 2 - 0.55, 0, 1) ** 1.6
    arr = arr * (1 - 0.09 * v[..., None])
    arr += np.random.default_rng(2).normal(0, 0.006, arr.shape[:2])[..., None]
    out = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))
    if W > 1080:
        out = out.resize((1080, 1350), Image.LANCZOS)
    out.save(OUT, quality=95, subsampling=0)
    print("gespeichert:", OUT, out.size, round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
