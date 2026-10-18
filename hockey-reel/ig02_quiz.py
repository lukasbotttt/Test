"""Instagram-Bild #2 (Quiz): HE STARTED THE FIGHT. - wie viele Strafminuten? 3D-Standbild im 4:5-Format (1080x1350).

Dunkle Arena mit Spotlicht: eine freistehende LED-Wand (2x2 Module, Punktmatrix) auf spiegelndem Eis, Antworten
A 5 / B 10 / C 17 / D 25 (PIM = penalty minutes). Alle vier Module sind gleich gross, gleich hell, gleiche Farbe.
Fakt fuer die Caption (NHL Official Rules 2023-24, Regel 46.11): Anstifter = instigating minor (2) + major fuer
Fighting (5) + 10-Minuten-Misconduct = 17 PIM.
Keine Personen, keine Logos. Eis: Raytracer (puck3d), Wand: Mesh-Rasterizer (mesh3d), LED-Flaechen per Homographie.
Gerendert in doppelter Aufloesung, danach auf 1080x1350 verkleinert.
Aufruf: python3 ig02_quiz.py                      -> ig02_quiz.jpg
        IGW=540 IGSPP=8 IGOUT=/pfad/x.jpg python3 ig02_quiz.py   (schnelle Vorschau)
"""
import math
import os

import cairocffi as cairo
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import gaussian_filter

import mesh3d as M3
import puck3d as P3
import reel15_puck as R15
import reel18_dangle as R18

HERE = R15.HERE


def add_material(name, col, spec, shine):
    """Neues Material zur Laufzeit in mesh3d eintragen (Datei bleibt unveraendert; neue Eintraege hinten)."""
    M3.MAT[name] = (col, spec, shine)
    M3.MAT_IDS = {k: i for i, k in enumerate(M3.MAT)}
    M3.MAT_COL = np.array([M3.MAT[k][0] for k in M3.MAT], np.float32)
    M3.MAT_SPEC = np.array([M3.MAT[k][1] for k in M3.MAT], np.float32)
    M3.MAT_SHINE = np.array([M3.MAT[k][2] for k in M3.MAT], np.float32)


if os.environ.get("IGGLOVEMAT", "1") == "1":                    # satte, leicht glaenzende Handschuhfarben (nur im Speicher)
    M3.MAT["glove_blue"] = ((0.026, 0.078, 0.35), 0.50, 34.0)
    M3.MAT["glove_red"] = ((0.47, 0.026, 0.037), 0.50, 34.0)
add_material("led_housing", (0.085, 0.09, 0.105), 0.9, 38.0)
add_material("led_plinth", (0.06, 0.065, 0.078), 1.0, 50.0)

W = int(os.environ.get("IGW", "2160"))
H = W * 5 // 4
S = W / 1080                                      # Layout in 1080er-Einheiten
SPP = int(os.environ.get("IGSPP", "64"))
OUT = os.environ.get("IGOUT", os.path.join(HERE, "ig02_quiz.jpg"))
INK, ORANGE = R15.INK, (255, 112, 28)
WHITE = (244, 246, 250)
LEDC = (255, 58, 40)                              # LED-Rot (wie reel30)
LEDN = (255, 96, 62)                              # Ziffern etwas heisser als der Buchstaben-Block
HOT = (255, 205, 170)

# ================================================================= Layout (in 1080er-Pixeln)
FOV = 30.0
TANH = math.tan(math.radians(FOV) / 2)
K = 11.5                                          # Pixel pro Zoll in der Wandebene
D = (1350 / 2) / (TANH * K)                       # Kameraabstand zur Wandmitte
THETA = math.radians(9.0)                         # Sichtstrahl-Neigung = Rueckneigung der Wand
YC_PX = 828.0                                     # Bildhoehe der Wandmitte
PW, PH, MOD, MGAP = 420.0, 206.0, 14.0, 8.0       # LED-Flaeche, Modulrand, Fuge
MW, MH = PW + 2 * MOD, PH + 2 * MOD
FW, FH = 2 * MW + MGAP, 2 * MH + MGAP
INCH = 1.0 / K

# ================================================================= Kamera + Wand
ALPHA = math.atan(((YC_PX - 675.0) / 675.0) * TANH)      # Wandmitte liegt ALPHA unter der optischen Achse
X0 = -560.0                                        # Wand steht auf freiem Eis (keine Linien im Bild)
WALL_C = np.array([X0, 23.5, 0.0])
RIGHT = np.array([1.0, 0.0, 0.0])
NRM = np.array([0.0, math.sin(THETA), math.cos(THETA)])     # Wandnormale (zur Kamera)
UPW = np.array([0.0, math.cos(THETA), -math.sin(THETA)])    # Wand-"oben" (lehnt zurueck)
CAM_POS = WALL_C + D * NRM
_pitch = THETA - ALPHA
CAM_TGT = CAM_POS + np.array([0.0, -math.sin(_pitch), -math.cos(_pitch)])
APERTURE = float(os.environ.get("IGAP", "0.9"))


def camera():
    r, u, f = P3.look_at(CAM_POS, CAM_TGT, np.array([0.0, 1.0, 0.0]))
    return P3.cam_row(CAM_POS, r, u, f, FOV), f


def to_world(v):
    v = np.asarray(v, float)
    return WALL_C + v[..., 0:1] * RIGHT + v[..., 1:2] * UPW + v[..., 2:3] * NRM


def rot_world(n):
    n = np.asarray(n, float)
    return n[..., 0:1] * RIGHT + n[..., 1:2] * UPW + n[..., 2:3] * NRM


# ================================================================= Gerundete Quader
def rbox(lo, hi, r, mat, nseg=4):
    """Quader (lo..hi je Achse) mit rundem Rand r, aus unterteilten Flaechen projiziert (glatte Normalen)."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    lines = []
    for ax in range(3):
        a = [lo[ax] + r * i / nseg for i in range(nseg + 1)] + [hi[ax] - r * (nseg - i) / nseg for i in range(nseg + 1)]
        lines.append(np.array(sorted(set(a))))
    inner_lo, inner_hi = lo + r, hi - r
    verts, norms, tris = [], [], []
    for ax in range(3):
        for side in (0, 1):
            o1, o2 = [a for a in range(3) if a != ax]
            g1, g2 = np.meshgrid(lines[o1], lines[o2], indexing="ij")
            n1, n2 = g1.shape
            p = np.zeros((n1, n2, 3))
            p[..., ax] = hi[ax] if side else lo[ax]
            p[..., o1], p[..., o2] = g1, g2
            q = np.clip(p, inner_lo, inner_hi)
            d = p - q
            ln = np.linalg.norm(d, axis=-1, keepdims=True)
            nn = d / np.maximum(ln, 1e-9)
            pp = q + r * nn
            base = len(verts)
            verts += list(pp.reshape(-1, 3))
            norms += list(nn.reshape(-1, 3))
            for i in range(n1 - 1):
                for j in range(n2 - 1):
                    a_, b_, c_, d_ = base + i * n2 + j, base + i * n2 + j + 1, base + (i + 1) * n2 + j, base + (i + 1) * n2 + j + 1
                    tris += [(a_, c_, b_), (b_, c_, d_)]
    return M3.Mesh(np.array(verts), np.array(norms), np.array(tris, np.int32), M3.MAT_IDS[mat])


def wall_meshes():
    """Vier gleiche Module + Sockel; Weltkoordinaten."""
    out = []
    depth = 8.0
    for ix in (-1, 1):
        for iy in (-1, 1):
            cx = ix * (MW + MGAP) / 2 * INCH
            cy = iy * (MH + MGAP) / 2 * INCH
            m = rbox([cx - MW / 2 * INCH, cy - MH / 2 * INCH, -depth], [cx + MW / 2 * INCH, cy + MH / 2 * INCH, 0.0], 0.9,
                     "led_housing")
            m.v, m.n = to_world(m.v), rot_world(m.n)
            out.append(m)
    back = rbox([-FW / 2 * INCH, -FH / 2 * INCH, -10.0], [FW / 2 * INCH, FH / 2 * INCH, -depth + 1.0], 0.4, "box_floor")
    back.v, back.n = to_world(back.v), rot_world(back.n)
    out.append(back)
    pl = rbox([X0 - (FW / 2 * INCH + 2.5), 0.0, -8.0], [X0 + FW / 2 * INCH + 2.5, 1.7, 4.8], 0.6, "led_plinth")
    out.append(pl)
    return out


def mirror(meshes):
    res = []
    for m in meshes:
        mm = M3.Mesh(m.v * np.array([1, -1, 1]), m.n * np.array([1, -1, 1]), m.t, m.m, m.uvw)
        res.append(mm)
    return res


# ================================================================= 3D-Handschuh (Form wie in reel30_fight.py)
def glove_local(scale=1.45):
    lerp = R15.lerp
    nu, nr = 64, 28
    us = np.linspace(0.0, 14.0, nu)
    verts = []
    for u in us:
        if u < 4.8:
            hh, hw = 3.0 + 0.25 * (4.8 - u) / 4.8, 2.95
        elif u < 9.0:
            t = (u - 4.8) / 4.2
            hh, hw = lerp(3.0, 2.45, t), lerp(2.95, 2.7, t)
        else:
            hh, hw = 2.25 + 0.45 * abs(math.sin(math.pi * (u - 9.0) / 1.25)), 2.65
        e = 14.0 - u
        k = math.sqrt(max(0.0, 1 - max(0.0, 1 - e / 1.2) ** 2)) if e < 1.2 else 1.0
        k0 = math.sqrt(max(0.0, 1 - max(0.0, 1 - u / 0.35) ** 2)) if u < 0.35 else 1.0
        k = max(min(k, 0.6 + 0.4 * k0), 0.08)
        for j in range(nr):
            th = 2 * math.pi * j / nr
            c, sn = math.cos(th), math.sin(th)
            w = hw * k * math.copysign(abs(c) ** 0.7, c)
            y = hh + hh * (0.55 + 0.45 * k) * math.copysign(abs(sn) ** 0.7, sn)
            verts.append((u, y, w))
    tris = list(map(tuple, M3.grid_tris(nu, nr)))
    tris += M3.cap(verts, (nu - 1) * nr, nr, (14.0, 2.4, 0.0))
    tris += [(t[1], t[0], t[2]) for t in M3.cap(verts, 0, nr, (0.0, 3.0, 0.0))]
    v = np.array(verts)
    t = np.array(tris, np.int32)
    hand = M3.Mesh(v, M3.vertex_normals(v, t), t, 0, v.copy())
    thumb = M3.tube_along([(5.6, 2.2, 2.6), (7.8, 2.6, 3.4), (9.8, 2.4, 3.3), (10.9, 2.1, 2.8)],
                          [1.25, 1.2, 1.05, 0.8], lambda s_: 0, nr=16)
    thumb.uvw = thumb.v.copy()
    m = M3.merge([hand, thumb])
    m.v = (m.v - np.array([7.0, 2.5, 0.0])) * scale
    return m


def glove_placed(x, z, head, mat, scale=1.0, roll=0.0):
    g = glove_local(1.45 * scale)
    c, sn = math.cos(head), math.sin(head)
    Ry = np.array([[c, 0, sn], [0, 1, 0], [-sn, 0, c]])
    cr, sr = math.cos(roll), math.sin(roll)
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    R = Ry @ Rx
    v, n = g.v @ R.T, g.n @ R.T
    v = v + np.array([x, -v[:, 1].min(), z])
    return M3.Mesh(v, n, g.t, M3.MAT_IDS[mat], g.uvw)


# ================================================================= Projektion / Homographie
def proj_px(row, pts):
    xy, z = P3.project(row, np.asarray(pts, float), W, H)
    return xy


def panel_corners_world(ix, iy, mirrored=False):
    """Weltkoordinaten der vier Ecken (TL, TR, BR, BL) der LED-Flaeche des Moduls (ix, iy), ix,iy in {0,1}."""
    cx = (-1 + 2 * ix) * (MW + MGAP) / 2
    cy = (1 - 2 * iy) * (MH + MGAP) / 2
    pts = np.array([[cx - PW / 2, cy + PH / 2, 0.05], [cx + PW / 2, cy + PH / 2, 0.05],
                    [cx + PW / 2, cy - PH / 2, 0.05], [cx - PW / 2, cy - PH / 2, 0.05]])
    pts[:, :2] *= INCH
    pw = to_world(pts)
    if mirrored:
        pw = pw * np.array([1, -1, 1])
    return pw


def homography(src, dst):
    """PIL: Koeffizienten, die Ausgabepixel (dst) auf Quellpixel (src) abbilden."""
    A, b = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b += [u, v]
    return np.linalg.solve(np.array(A, float), np.array(b, float))


def warp(img, dst_quad):
    """img (PIL, beliebiger Modus) auf das Viereck dst_quad (TL,TR,BR,BL in Ausgabepixeln) -> Bild WxH."""
    w, h = img.size
    src = [(0, 0), (w, 0), (w, h), (0, h)]
    co = homography(src, dst_quad)
    return img.transform((W, H), Image.PERSPECTIVE, tuple(co), Image.BICUBIC)


# ================================================================= LED-Module (Punktmatrix)
PITCH = 7.0


def _glyph(txt, size, wght):
    return R15.line_img(txt, int(size * S), wght, (255, 255, 255), cache=False)


def _mask_canvas(w, h, items):
    """items: [(PIL RGBA-Text, cx, cy)] -> Maske float (h, w) (hi-res px)."""
    m = Image.new("L", (w, h), 0)
    for im, cx, cy in items:
        m.paste(im.getchannel("A"), (int(round(cx - im.width / 2)), int(round(cy - im.height / 2))), im.getchannel("A"))
    return np.asarray(m, np.float32) / 255


def dot_tile(p, rad):
    yy, xx = (np.mgrid[0:p, 0:p].astype(np.float32) + 0.5 - p / 2)
    r = np.sqrt(xx * xx + yy * yy)
    return np.clip((rad - r) / (0.12 * p) + 0.5, 0, 1), np.clip(1 - r / rad, 0, 1)


def led_panel(letter, number):
    """RGB-Textur der LED-Flaeche (hi-res) + Emission; alle Module nutzen exakt denselben Code."""
    pw, ph = int(round(PW * S)), int(round(PH * S))
    p = int(round(PITCH * S))
    gw, gh = pw // p, ph // p
    pw, ph = gw * p, gh * p
    # Maske in Zellaufloesung (hi-res px)
    badge = Image.new("L", (pw, ph), 0)
    d = ImageDraw.Draw(badge)
    bs = 132 * S
    bx0, by0 = 22 * S, (PH * S - bs) / 2
    d.rounded_rectangle((bx0, by0, bx0 + bs, by0 + bs), 16 * S, fill=255)
    lg = _glyph(letter, 124, 900)
    bm = np.asarray(badge, np.float32) / 255
    lm = _mask_canvas(pw, ph, [(lg, bx0 + bs / 2, by0 + bs / 2)])
    badge_lit = np.clip(bm - lm * 1.4, 0, 1)                               # Buchstabe = ausgeschaltete LEDs im Block
    num = R15.line_img(number, int(170 * S), 900, (255, 255, 255), track=-6 * S, cache=False)
    nm = _mask_canvas(pw, ph, [(num, 290 * S, PH * S / 2)])

    def cell_lit(m):
        c = m.reshape(gh, p, gw, p).mean(axis=(1, 3))
        return np.kron(np.clip((c - 0.12) / 0.55, 0, 1), np.ones((p, p), np.float32))

    soft, core = dot_tile(p, 0.40 * p)
    soft_t, core_t = np.tile(soft, (gh, gw)), np.tile(core, (gh, gw))
    base_b = np.array(LEDC, np.float32) / 255
    base_n = np.array(LEDN, np.float32) / 255
    hot = np.array(HOT, np.float32) / 255
    heat = (core_t[..., None] ** 2.2)
    on = (cell_lit(badge_lit) * soft_t)[..., None] * (base_b + (hot - base_b) * heat * 0.8)
    on = on + (cell_lit(nm) * soft_t)[..., None] * (base_n + (hot - base_n) * heat)
    off = 0.050 * soft_t[..., None] * base_b                                  # ausgeschaltete LEDs
    rgb = np.clip(off + on * 1.25, 0, 1.6)
    # Glow innerhalb der Flaeche (Badge schwaecher, damit der Buchstabe sauber dunkel bleibt)
    on_b = (cell_lit(badge_lit) * soft_t)[..., None] * (base_b + (hot - base_b) * heat * 0.8)
    on_n = on - on_b
    g1 = gaussian_filter(on_n, (3.0 * S, 3.0 * S, 0)) + 0.35 * gaussian_filter(on_b, (2.0 * S, 2.0 * S, 0))
    g2 = gaussian_filter(on_n, (10.0 * S, 10.0 * S, 0)) + 0.30 * gaussian_filter(on_b, (7.0 * S, 7.0 * S, 0))
    rgb = np.clip(rgb + 0.55 * g1 + 0.30 * g2, 0, 1)
    return Image.fromarray((rgb * 255).astype(np.uint8)), on


ANSWERS = [("A", "5"), ("B", "10"), ("C", "17"), ("D", "25")]       # Reihenfolge: links oben, rechts oben, ...


# ================================================================= Licht (dunkle Arena)
_NDC = None


def ice_hit(row):
    global _NDC
    if _NDC is None:
        xs = (np.arange(W) + 0.5) / W * 2 - 1
        ys = 1 - (np.arange(H) + 0.5) / H * 2
        _NDC = np.meshgrid(xs.astype(np.float32), ys.astype(np.float32))
    nx, ny = _NDC
    pos, r, u, f, tanh = row[0:3], row[3:6], row[6:9], row[9:12], row[12]
    asp = W / H
    d = f[None, None, :] + nx[..., None] * (tanh * asp) * r[None, None, :] + ny[..., None] * tanh * u[None, None, :]
    dy = d[..., 1]
    hit = dy < -1e-4
    tt = np.where(hit, -pos[1] / np.where(hit, dy, -1.0), 0.0)
    return pos[0] + tt * d[..., 0], pos[2] + tt * d[..., 2], hit


SPOTS = [  # (x, z, rx, rz, Staerke, Farbe)
    (X0, 20.0, 300.0, 170.0, 0.11, (0.92, 0.96, 1.0)),
    (X0, 50.0, 190.0, 80.0, 0.11, (1.0, 0.14, 0.10)),
    (X0, -170.0, 380.0, 200.0, 0.07, (0.45, 0.60, 1.0)),
]
GLOVE_SPOTS = os.environ.get("IGGLOVE", "1") == "1"
AMB = np.array([0.050, 0.060, 0.100], np.float32)


def light_map(row, mesh_a=None, mesh_pos=None):
    x, z, hit = ice_hit(row)
    if mesh_a is not None:
        k = np.clip(mesh_a, 0, 1)
        safe = np.where(k[..., None] > 0.01, mesh_pos / np.maximum(k, 1e-3)[..., None], 0.0)
        x = x * (1 - k) + safe[..., 0] * k
        z = z * (1 - k) + safe[..., 2] * k
        hit = np.maximum(hit.astype(np.float32), k)
    L = np.broadcast_to(AMB, (H, W, 3)).copy()
    spots = list(SPOTS)
    if GLOVE_SPOTS:
        spots += [(X0 + dx, z + 2.0, 52.0, 30.0, 0.24, (0.85, 0.92, 1.0)) for dx, z, *_ in GLOVES]
    for sx, sz, rx, rz, kk, col in spots:
        g = np.exp(-(((x - sx) / rx) ** 2 + ((z - sz) / rz) ** 2)).astype(np.float32) * hit
        L += g[..., None] * (kk * np.array(col, np.float32))
    return L


# ================================================================= Hilfen
def blur_big(a, sigma):
    """Gauss-Unschaerfe fuer grosse Radien ueber ein verkleinertes Bild (Ergebnis in voller Groesse)."""
    f = max(1, int(sigma // 6))
    sm = a[::f, ::f] if f > 1 else a
    sm = gaussian_filter(sm, (sigma / f, sigma / f) + (0,) * (a.ndim - 2))
    if a.ndim == 2:
        return np.asarray(Image.fromarray(sm.astype(np.float32), mode="F").resize((W, H), Image.BILINEAR), np.float32)
    out = np.empty(a.shape, np.float32)
    for c in range(a.shape[2]):
        out[..., c] = np.asarray(Image.fromarray(sm[..., c].astype(np.float32), mode="F").resize((W, H), Image.BILINEAR),
                                 np.float32)
    return out


def paste_c(L, im, cx, cy):
    L.alpha_composite(im, (int(round(cx - im.width / 2)), int(round(cy - im.height / 2))))


def line(txt, size, wght, col, track=0.0):
    return R15.line_img(txt, int(size * S), wght, col, track=track * S, cache=False)


def word(txt, size, col, glow):
    return R18.word_img(txt, int(size * S), col, glow, cache=False)


# ================================================================= Bild
M3.LIGHT = np.array([-0.42, 0.88, 0.46])
M3.LIGHT /= np.linalg.norm(M3.LIGHT)


def stage_glow():
    """Weicher blauer Lichtdunst hinter der Wand (Bildraum)."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    g = np.exp(-(((xx - W * 0.5) / (W * 0.62)) ** 2 + ((yy - H * 0.50) / (H * 0.34)) ** 2))
    return g[..., None] * np.array([0.050, 0.085, 0.185], np.float32)


def beam():
    """Sehr weicher Lichtkegel von oben auf die Wand (Bildraum, additiv); oben und unten sanft ausgeblendet."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    t = np.clip(yy / (H * 0.60), 0, 1)
    half = (200 + 330 * t) * S
    edge = 1 - np.clip((np.abs(xx - W / 2) - half * 0.40) / (half * 0.60), 0, 1)
    edge = edge * edge * (3 - 2 * edge)
    amp = np.exp(-((yy / H - 0.30) / 0.17) ** 2)
    b = edge * amp
    return b[..., None] * np.array([0.050, 0.075, 0.130], np.float32) * float(os.environ.get("IGBEAM", "1.6"))


def panel_sheen():
    """Weicher Glasreflex quer ueber die LED-Flaeche (fuer alle Module gleich)."""
    pw, ph = int(round(PW * S)), int(round(PH * S))
    yy, xx = np.mgrid[0:ph, 0:pw].astype(np.float32)
    d = (xx / pw * 0.62 + (1 - yy / ph) * 0.38)
    band = np.exp(-((d - 0.42) / 0.10) ** 2) * 0.5 + np.exp(-((d - 0.66) / 0.04) ** 2) * 0.25
    top = np.clip(1 - yy / (ph * 0.55), 0, 1) ** 2 * 0.5
    return np.clip((band * top * 0.9 + 0.0), 0, 1)


GLOVES = [(-24.0, 28.0, 0.85, "glove_blue", 0.92, 0.0),       # (dx, z, Richtung, Material, Skala, Rollen)
          (26.0, 25.0, 2.30, "glove_red", 0.92, 0.0)]
if os.environ.get("IGGLOVES"):                                  # Experimente: "dx,z,head,mat,scale,roll;..."
    GLOVES = [(float(a), float(b), float(c), d, float(e), float(f_)) for a, b, c, d, e, f_ in
              (t.split(",") for t in os.environ["IGGLOVES"].split(";"))]


def ice_scratches(row):
    """Feine Kufenspuren auf dem Eis (Weltkoordinaten -> Bild), nur als Helligkeitsmaske."""
    rng = np.random.default_rng(11)
    surf = cairo.ImageSurface(cairo.FORMAT_A8, W, H)
    ctx = cairo.Context(surf)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for i in range(170):
        x0, z0 = X0 + rng.uniform(-170, 170), rng.uniform(-15, 150)
        ang = rng.normal(0.0, 0.5) + (math.pi if rng.random() < 0.5 else 0.0)
        ln, cv = rng.uniform(30, 260), rng.normal(0, 0.0035)
        ts = np.linspace(0, ln, 28)
        a = ang + cv * ts
        xs = x0 + np.cumsum(np.cos(a)) * (ln / 28)
        zs = z0 + np.cumsum(np.sin(a)) * (ln / 28)
        xy = proj_px(row, np.stack([xs, np.zeros_like(xs), zs], 1))
        ctx.set_source_rgba(0, 0, 0, float(rng.uniform(0.05, 0.22)) * (1.4 if i % 9 == 0 else 1.0))
        ctx.set_line_width(float(rng.uniform(0.7, 1.9)) * S)
        ctx.move_to(*xy[0])
        for q in xy[1:]:
            ctx.line_to(*q)
        ctx.stroke()
    surf.flush()
    st = surf.get_stride()
    a8 = np.frombuffer(surf.get_data(), np.uint8).reshape(H, st)[:, :W].astype(np.float32) / 255
    return gaussian_filter(a8, 0.7 * S)


def glove_layer(row):
    """Vordergrund-Handschuh(e): -> rgb(pm), alpha, Schattenmaske, gespiegelt rgb(pm)."""
    meshes = [glove_placed(X0 + dx, z, hd, mat, sc, rl) for dx, z, hd, mat, sc, rl in GLOVES]
    ss = 1 if W >= 1600 else 2
    g_rgb, g_a, g_sh, _, g_pos = M3.render(meshes, row, W, H, CAM_POS, ss=ss, shadow_light=(0.05, 1.0, 0.10), want_pos=True)
    r_rgb, r_a, _, _, r_pos = M3.render(mirror(meshes), row, W, H, CAM_POS, ss=ss, want_pos=True)
    return g_rgb * light_map(row, g_a, g_pos) * 1.45, g_a, g_sh, r_rgb * light_map(row, r_a, r_pos) * 1.45, r_a


def render_scene():
    row, f = camera()
    focus = float(np.linalg.norm(WALL_C - CAM_POS))
    cams = row[None, :].copy()
    lens = np.array([[APERTURE, focus]])
    pk = np.array([[0.0, -50.0, 0.0, 0.0, 0.0, 0.0, 0.0]])
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, SPP, 5, cams, lens, pk, R15.logo_tex(), base, puck, cov)
    ice = P3.tonemap(base)

    meshes = wall_meshes()
    ss = 1 if W >= 1600 else 2
    m_rgb, m_a, shadow, _, m_pos = M3.render(meshes, row, W, H, CAM_POS, ss=ss, shadow_light=(0.03, 1.0, 0.05), want_pos=True)
    r_rgb, r_a, _, _, r_pos = M3.render(mirror(meshes), row, W, H, CAM_POS, ss=ss, want_pos=True)

    # LED-Flaechen: je Modul dieselbe Textur-Funktion, auf die Wandebene (und gespiegelt aufs Eis) projiziert
    led = np.zeros((H, W, 3), np.float32)
    led_a = np.zeros((H, W), np.float32)
    led_r = np.zeros((H, W, 3), np.float32)
    emis = np.zeros((H, W, 3), np.float32)
    sheen = panel_sheen()
    for i, (lt, nm) in enumerate(ANSWERS):
        ix, iy = i % 2, i // 2
        tex, on = led_panel(lt, nm)
        rgba = tex.convert("RGBA")
        quad = proj_px(row, panel_corners_world(ix, iy))
        a = np.asarray(warp(rgba, quad), np.float32) / 255
        sh_w = np.asarray(warp(Image.fromarray((sheen * 255).astype(np.uint8)), quad), np.float32) / 255
        led = led * (1 - a[..., 3:4]) + a[..., :3] * a[..., 3:4]
        led = led + sh_w[..., None] * a[..., 3:4] * np.array([0.050, 0.060, 0.085], np.float32) * float(os.environ.get("IGSHEEN", "1"))
        led_a = np.maximum(led_a, a[..., 3])
        em = warp(Image.fromarray((np.clip(on, 0, 1) * 255).astype(np.uint8)).convert("RGB"), quad)
        emis = np.maximum(emis, np.asarray(em, np.float32) / 255 * a[..., 3:4])
        ar = np.asarray(warp(rgba, proj_px(row, panel_corners_world(ix, iy, mirrored=True))), np.float32) / 255
        led_r = led_r * (1 - ar[..., 3:4]) + ar[..., :3] * ar[..., 3:4]

    Lm_w = light_map(row, m_a, m_pos)
    Lm_r = light_map(row, r_a, r_pos)
    Lm_i = light_map(row)
    img = ice * Lm_i + ice_scratches(row)[..., None] * Lm_i * 0.5 * float(os.environ.get('IGSCR', '1')) + stage_glow() + beam()
    img = img * (1 - 0.6 * np.clip(shadow, 0, 1)[..., None])

    glove = GLOVE_SPOTS
    if glove:
        g_rgb, g_a, g_sh, gr_rgb, gr_a = glove_layer(row)
        img = img * (1 - 0.65 * np.clip(g_sh, 0, 1)[..., None])

    # Spiegelung im Eis: Wand + LED, nach unten ausgeblendet, leicht weichgezeichnet
    ys = np.arange(H, dtype=np.float32)[:, None]
    y_contact = proj_px(row, np.array([[X0, 0.0, 4.8]]))[0, 1]
    fade = (1 - np.clip((ys - y_contact) / (0.17 * H), 0, 1)) ** 1.5
    r_housing = r_rgb * Lm_r * 1.7
    sharp = led_r * 0.80 + r_housing * 0.35
    refl = gaussian_filter(sharp, (2.0 * S, 1.0 * S, 0)) * 0.7 + blur_big(led_r, 16 * S) * 0.65
    img = img + refl * fade[..., None] * (1 - m_a[..., None])

    # Wand (Gehaeuse) und LED-Flaechen (selbstleuchtend)
    img = img * (1 - m_a[..., None]) + m_rgb * Lm_w * 1.7
    img = img * (1 - led_a[..., None]) + led
    bl = blur_big(emis, 7 * S) * 0.55 + blur_big(emis, 26 * S) * 0.75 + blur_big(emis, 90 * S) * 0.95
    img = img + bl * np.array([1.0, 0.85, 0.85], np.float32)

    if glove:
        img = img + gaussian_filter(gr_rgb, (3 * S, 1.5 * S, 0)) * 0.25 * fade[..., None]
        coc = 0.55 * S
        g_rgb_b = gaussian_filter(g_rgb, (coc, coc, 0))
        g_a_b = gaussian_filter(g_a, coc)
        img = img * (1 - g_a_b[..., None]) + g_rgb_b
    return np.clip(img, 0, 1), row


def shadowed(im, blur=10, k=0.8):
    """Textzeile mit weichem dunklem Hof (Lesbarkeit ueber Spiegelung/Eis)."""
    pad = int(blur * 3 * S)
    a = Image.new("L", (im.width + 2 * pad, im.height + 2 * pad), 0)
    a.paste(im.getchannel("A"), (pad, pad))
    a = a.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(blur * S)).point(lambda v: min(255, int(v * 2.0 * k)))
    out = Image.new("RGBA", a.size, (4, 6, 12, 0))
    out.putalpha(a)
    out.alpha_composite(im, (pad, pad))
    return out


def two_tone(parts, size, wght, track, gap):
    """Zeile aus mehreren Teilen (Text, Farbe) nebeneinander."""
    ims = [line(t, size, wght, c, track) for t, c in parts]
    g = int(gap * S)
    out = Image.new("RGBA", (sum(i.width for i in ims) + g * (len(ims) - 1), max(i.height for i in ims)), (0, 0, 0, 0))
    x = 0
    for im in ims:
        out.alpha_composite(im, (x, 0))
        x += im.width + g
    return out


def typography(img):
    yy = np.arange(H, dtype=np.float32)[:, None, None] / H
    img = img * (1 - 0.55 * np.clip((yy - 0.875) / 0.10, 0, 1) ** 1.2)
    pil = Image.fromarray((img * 255).astype(np.uint8)).convert("RGBA")
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    paste_c(L, line("NHL RULES EXPLAINED", 28, 800, ORANGE, 8), W / 2, 88 * S)
    paste_c(L, word("HE STARTED", 150, WHITE, (90, 110, 170)), W / 2, 214 * S)
    paste_c(L, word("THE FIGHT.", 169, (255, 52, 44), (170, 20, 20)), W / 2, 373 * S)
    paste_c(L, line("HOW MANY PENALTY MINUTES?", 53, 850, (226, 230, 240), 3), W / 2, 506 * S)
    paste_c(L, line("PIM = PENALTY MINUTES", 23, 700, (150, 160, 182), 4), W / 2, 566 * S)
    paste_c(L, shadowed(two_tone([("COMMENT", WHITE), ("A, B, C OR D", ORANGE)], 41, 850, 5, 16)), W / 2, 1262 * S)
    paste_c(L, shadowed(line("@BLADESANDPUCKS", 24, 700, (140, 146, 162), 6), 7), W / 2, 1312 * S)
    pil.alpha_composite(L)
    return np.asarray(pil.convert("RGB")).astype(np.float32) / 255


def finish(arr):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    v = np.clip(np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H * 0.55) / H) ** 2) * 2 - 0.55, 0, 1) ** 1.6
    arr = arr * (1 - 0.40 * v[..., None])
    arr += np.random.default_rng(2).normal(0, 0.007, arr.shape[:2])[..., None]
    return np.clip(arr, 0, 1)


def main():
    img, row = render_scene()
    arr = finish(typography(img))
    out = Image.fromarray((arr * 255).astype(np.uint8))
    if W > 1080:
        out = out.resize((1080, 1350), Image.LANCZOS)
    out.save(OUT, quality=95, subsampling=0)
    print("gespeichert:", OUT, out.size)


if __name__ == "__main__":
    main()
