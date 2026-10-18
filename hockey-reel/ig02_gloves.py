"""Instagram-Bild #2: GLOVES OFF. – 3D-Standbild im 4:5-Format (1080x1350), dunkle Arena, Kinolook.

Zwei übergroße 3D-Eishockey-Handschuhe (blau / rot) liegen frisch fallen gelassen auf dem Eis und zeigen mit den
Fingern aufeinander; dazwischen liegt ein schwarzer Puck ohne Logo (das Eishockey-Signal). Handschuhe: lange,
ausgestellte Stulpe mit Randwulst, Handrücken-Schalen, vier getrennte Finger mit Rollen, Daumen, Piping und Nähte.
Ein harter Spot-Fleck auf dem Eis (helle, klar begrenzte Ellipse), farbiges Gegenlicht per Light-Linking (blau nur
links, rot nur rechts), Lichtkegel im Dunst, Kratzer und Spiegelung im Eis, flache Schärfentiefe.
Bewusst ohne Menschen, ohne Logos. Das Bild stellt nur eine Frage.

Technik: eigener G-Buffer-Rasterizer auf Basis von mesh3d (Z-Buffer, perspektivisch korrekt), eigenes Shading
(Spot + zwei Rim-Lichter + Eis-Bounce), Eis als Ebene per Pixel schattiert (Spot-Pool, Kratzer, Fresnel-Spiegelung),
Spiegelbild der Handschuhe, Kegel-Volumen per Raymarching, Tiefenschärfe über CoC-Schichten, Bloom, Vignette, Korn.
Text im Bild (alles Englisch, keine Fakten, nur eine Frage): NHL RULES EXPLAINED / GLOVES OFF. /
SHOULD THE NHL BAN FIGHTING? / YES or NO? / COMMENT BELOW / @BLADESANDPUCKS.
Aufruf: python3 ig02_gloves.py                       -> ig02_gloves.jpg (2160x2700 gerendert, auf 1080x1350 verkleinert, ca. 1-2 Min.)
        IGW=540 IGSS=1 IGTEX=2048 python3 ig02_gloves.py   (schnelle Vorschau)
        IGBASE=pfad.png  speichert/lädt das 3D-Bild ohne Text, damit Typografie schnell iteriert werden kann
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from numba import njit, prange
from scipy.interpolate import CubicSpline
from scipy.ndimage import gaussian_filter, map_coordinates

import mesh3d as M3
import puck3d as P3
import reel15_puck as R15

HERE = R15.HERE
W = int(os.environ.get("IGW", "2160"))
H = W * 5 // 4
S = W / 1080                                          # Layout in 1080er-Einheiten
SS = int(os.environ.get("IGSS", "2"))                 # Supersampling des Mesh-Rasterizers
OUT = os.environ.get("IGOUT", os.path.join(HERE, "ig02_gloves.jpg"))
STAGE = os.environ.get("IGSTAGE", "full")
INK, ORANGE = R15.INK, R15.ORANGE
BLUE_T = (70, 140, 255)
RED_T = (255, 58, 66)


# ================================================================= kleine Helfer
def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def sgnpow(c, p):
    return np.sign(c) * np.abs(c) ** p


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


# ================================================================= 3D-Handschuh
# lokal: u = Länge (0 = Stulpenrand, GL = Fingerspitzen), y = oben (Handrücken), w = seitlich (Daumen bei +w); Einheiten: Zoll
U0 = 2.9                                                      # zusätzliche, ausgestellte Stulpe vor der Hand
GL = 14.0 + U0
PART_BODY, PART_THUMB, PART_INSIDE, PART_PUCK = 0, 1, 2, 3
NR = 132                                                      # Ringauflösung (viertelbar: Mitte oben liegt exakt auf einem Punkt)
FING_W = (-1.72, 0.0, 1.72)                                   # Trennrillen zwischen den vier Fingern (w in Zoll)


def prof(u):
    """(halbe Breite, Dicke) des Handschuhs an der Stelle u (ohne Rundung der Enden)."""
    v = u - U0
    kx = [0.0, 1.6, 3.6, 6.0, 9.0, 12.0, 14.0]
    hw = np.interp(v, kx, [3.95, 3.55, 3.05, 3.15, 3.45, 3.5, 3.35])
    th = np.interp(v, kx, [4.35, 3.95, 3.30, 3.05, 3.25, 3.05, 2.85])
    # Handrücken-Schalen (3 Platten) und Fingerrollen (4 Segmente): scharfe Rillen, gewölbte Platten
    sh = np.abs(np.sin(np.pi * np.clip((v - 4.6) / 1.55, 0, 3.0))) ** 0.55 * ((v > 4.6) & (v < 9.25))
    fr = np.abs(np.sin(np.pi * np.clip((v - 9.5) / 1.12, 0, 3.5))) ** 0.5 * ((v > 9.5) & (v < 13.42))
    th = th + 0.30 * sh + 0.42 * fr
    # ausgestellte Stulpe (Trichter) mit Randwulst
    fl = np.clip((U0 - u) / U0, 0.0, 1.0) ** 1.6
    hw = hw + 1.30 * fl
    th = th + 1.05 * fl
    bead = 0.20 * np.exp(-((u - 0.34) / 0.27) ** 2)
    return hw + bead, th + bead * 1.35


def end_k(u):
    """Rundung an den Fingerspitzen (stark)."""
    e = GL - u
    k = np.where(e < 1.15, np.sqrt(np.clip(1 - np.clip(1 - e / 1.15, 0, 1) ** 2.6, 0, 1)), 1.0)
    return np.maximum(k, 0.05)


def _ring_unit(nr, pw=0.62):
    """Einheits-Superellipse, nach Bogenlänge gleichmäßig abgetastet (gleichmäßige Auflösung für die Fingerrillen)."""
    a = np.linspace(0, 2 * math.pi, 6000, endpoint=False)
    x, y = sgnpow(np.cos(a), pw), sgnpow(np.sin(a), pw)
    seg = np.hypot(np.diff(np.r_[x, x[0]]), np.diff(np.r_[y, y[0]]))
    cum = np.r_[0.0, np.cumsum(seg)][:-1]
    tgt = np.arange(nr) / nr * seg.sum()
    return np.interp(tgt, cum, x), np.interp(tgt, cum, y)


RX, RY = _ring_unit(NR)


def groove_depth(u):
    """Tiefe der Längsrillen zwischen den Fingern entlang u."""
    v = u - U0
    return 0.30 * float(smoothstep(8.9, 9.7, v)) * (1.0 - float(smoothstep(13.55, 13.95, v)))


def ring_pts(u, nr, scale=1.0):
    assert nr == NR
    hw, th = prof(u)
    k = end_k(u) if u > GL - 1.3 else 1.0
    th_ = th * k
    w = hw * k * RX * scale
    y = th_ / 2 + th_ / 2 * RY * scale
    gd = groove_depth(u)
    if gd > 0:
        G = sum(np.exp(-((w - wg * hw * k / 3.4) / (0.19 * (0.35 + 0.65 * k))) ** 2) for wg in FING_W)
        y = y - gd * k * G * np.clip((RY - 0.1) / 0.4, 0, 1)
    return [(u, float(a), float(b)) for a, b in zip(y, w)]


def glove_local():
    nu, nr = 235, NR
    us = np.concatenate([np.linspace(0.0, GL - 1.4, nu - 62, endpoint=False), np.linspace(GL - 1.4, GL, 62)])
    verts = []
    for u in us:
        verts += ring_pts(float(u), nr)
    tris = list(map(tuple, M3.grid_tris(len(us), nr)))
    tris += M3.cap(verts, (len(us) - 1) * nr, nr, (GL, 1.0, 0.0))
    v = np.array(verts)
    t = np.array(tris, np.int32)
    body = M3.Mesh(v, M3.vertex_normals(v, t), t, PART_BODY, v.copy())
    # Daumen: Röhre entlang einer Kurve, hinten geschlossen und vorn abgerundet
    path = [(4.6, 1.5, 2.5), (6.0, 1.7, 3.5), (7.8, 2.0, 4.3), (9.6, 2.1, 4.55), (11.2, 2.0, 4.35), (12.3, 1.9, 4.0),
            (12.8, 1.85, 3.85), (12.95, 1.85, 3.8)]
    rad = [0.30, 0.90, 1.16, 1.12, 0.96, 0.70, 0.40, 0.05]
    path = np.array(path) + np.array([U0, 0.0, 0.0])
    ts = np.linspace(0, 1, 40)
    cs = CubicSpline(np.linspace(0, 1, len(path)), path)
    cr = CubicSpline(np.linspace(0, 1, len(path)), rad)
    thumb = M3.tube_along(cs(ts), np.maximum(cr(ts), 0.04), lambda s: PART_THUMB, nr=22)
    thumb.uvw = thumb.v.copy()
    thumb.m[:] = PART_THUMB
    # Stulpen-Öffnung: kurzer Rand nach innen + trichterförmiger dunkler Innenraum
    r0 = ring_pts(0.0, nr)
    r1 = [(0.45, y, w) for (_, y, w) in ring_pts(0.0, nr, 0.93)]
    ctr = (U0 + 1.6, prof(0.0)[1] / 2 * 0.98, 0.0)
    iv = np.array(r0 + r1 + [ctr])
    it = []
    for j in range(nr):
        a, b = j, (j + 1) % nr
        it += [(a, nr + a, b), (b, nr + a, nr + b), (nr + a, 2 * nr, nr + b)]
    it = np.array(it, np.int32)
    inside = M3.Mesh(iv, np.tile([-1.0, 0.0, 0.0], (len(iv), 1)), it, PART_INSIDE, iv.copy())
    m = M3.merge([body, thumb, inside])
    m.v = m.v - np.array([GL * 0.5, 0.0, 0.0])                # Mitte in den Ursprung (Auflage y = 0)
    return m


GLOVE = glove_local()


# ================================================================= Puck (schwarz, ohne Logo)
PUCK_R, PUCK_H, PUCK_B = 1.5, 1.0, 0.26                       # Zoll: Radius, Dicke, Kantenrundung


def puck_local(nr=96):
    r, h, b = PUCK_R, PUCK_H, PUCK_B
    prof_pts, prof_n = [(0.0, 0.0)], [(0.0, -1.0)]
    prof_pts.append((r - b, 0.0))
    prof_n.append((0.0, -1.0))
    for k in range(1, 10):                                     # untere Kante
        t = -math.pi / 2 + (math.pi / 2) * k / 9
        prof_pts.append((r - b + b * math.cos(t), b + b * math.sin(t)))
        prof_n.append((math.cos(t), math.sin(t)))
    for k in range(0, 10):                                     # obere Kante
        t = (math.pi / 2) * k / 9
        prof_pts.append((r - b + b * math.cos(t), h - b + b * math.sin(t)))
        prof_n.append((math.cos(t), math.sin(t)))
    prof_pts.append((0.0, h))
    prof_n.append((0.0, 1.0))
    verts, norms = [], []
    for (pr, py), (qr, qy) in zip(prof_pts, prof_n):
        for j in range(nr):
            a = 2 * math.pi * j / nr
            verts.append((pr * math.cos(a), py, pr * math.sin(a)))
            norms.append((qr * math.cos(a), qy, qr * math.sin(a)))
    v = np.array(verts)
    t = M3.grid_tris(len(prof_pts), nr)
    return M3.Mesh(v, np.array(norms), t, PART_PUCK, v.copy())


PUCK = puck_local()


# ================================================================= Pose der Handschuhe
def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def place_glove(team, x, z, yaw, roll, pitch, mirror, scale=1.0):
    """Handschuh auf das Eis legen: lokal (u, y, w) -> Welt. yaw = Richtung der Fingerspitzen in der x/z-Ebene
    (0 = +x, +90 Grad = zur Kamera, die bei +z steht)."""
    v = GLOVE.v * scale
    n = GLOVE.n.copy()
    uvw = GLOVE.uvw.copy()
    if mirror:
        v = v * np.array([1, 1, -1.0])
        n = n * np.array([1, 1, -1.0])
    # lokal: u -> +x, y -> +y, w -> +z; erst Roll (um u), dann Pitch (um w), dann Gier (um y)
    R = rot_y(-yaw) @ rot_z(pitch) @ rot_x(roll)
    v = v @ R.T
    n = n @ R.T
    v[:, 1] -= v[:, 1].min()
    v[:, 0] += x
    v[:, 2] += z
    m = M3.Mesh(v, n, GLOVE.t, GLOVE.m, uvw, group=team)
    m.v0 = GLOVE.v * scale                                  # unverändert, für Muster
    return m


def place_puck(x, z, yaw, scale):
    """Puck flach auf dem Eis: lokal (Achse y) -> Welt, gedreht um y, skaliert."""
    R = rot_y(-yaw)
    v = (PUCK.v * scale) @ R.T
    n = PUCK.n @ R.T
    v[:, 0] += x
    v[:, 2] += z
    return M3.Mesh(v, n, PUCK.t, PUCK.m, PUCK.uvw.copy(), group=2)


# Handschuh-Paar: (Team, x, z, yaw Grad, Roll Grad, Pitch Grad, gespiegelt) + Puck in der Lücke
def gloves():
    a = float(os.environ.get("IGYAW", "58"))
    gx = float(os.environ.get("IGGX", "6.3"))
    r0 = float(os.environ.get("IGROLL0", "42"))
    r1 = float(os.environ.get("IGROLL1", "-36"))
    sc = float(os.environ.get("IGSC", "0.95"))
    away = os.environ.get("IGTHUMB", "away") == "away"          # Daumen zeigt von der Kamera weg (oben/hinten)
    px, pz = [float(v) for v in os.environ.get("IGPUCK", "0.3,9.0").split(",")]
    ps = float(os.environ.get("IGPS", "1.7"))
    out = [place_glove(0, -gx, 1.6, math.radians(a), math.radians(r0), math.radians(-1.5), away, sc),
           place_glove(1, gx + 0.4, -1.4, math.radians(180 - a - 4), math.radians(r1), math.radians(-1.0), not away, sc)]
    if ps > 0:
        out.append(place_puck(px, pz, 0.35, ps))
    return out


# ================================================================= Licht (Welt, Zoll)
POOL_C = np.array([0.0, 0.0, float(os.environ.get("IGPCZ", "2.0"))])
POOL_R = np.array([float(os.environ.get("IGPX", "18.5")), float(os.environ.get("IGPZ", "13.5"))])


def pool(x, z):
    """Spot-Fleck auf dem Eis (0..1): helle, klar begrenzte Ellipse mit hellem Kern und dunklem Abfall nach außen."""
    d = np.sqrt(((x - POOL_C[0]) / POOL_R[0]) ** 2 + ((z - POOL_C[2]) / POOL_R[1]) ** 2)
    edge = 1.0 - smoothstep(0.90, 1.0, d)
    core = np.exp(-d * d * 2.6)
    return (edge * (0.13 + 0.87 * core) + 0.025 * np.exp(-d * d * 0.35)).astype(np.float32)


KEY_POS = np.array([3.0, 70.0, -6.0])
RIM_B = unit([-1.0, 0.40, -1.20])                         # Gegenlicht links (blau)
RIM_R = unit([1.0, 0.40, -1.20])                          # Gegenlicht rechts (rot)
C_RIM_B = np.array([0.06, 0.44, 1.00], np.float32)
C_RIM_R = np.array([1.00, 0.10, 0.12], np.float32)
FILL = unit([-0.45, 0.55, 1.0])
FILL_I = float(os.environ.get("IGFILL", "0.95"))

TEAM_COL = {0: dict(main=(0.010, 0.070, 0.480), dark=(0.005, 0.020, 0.150), glow=(0.10, 0.30, 1.0)),
            1: dict(main=(0.560, 0.020, 0.032), dark=(0.190, 0.007, 0.011), glow=(1.0, 0.10, 0.12))}
WHITE_L = np.array([0.74, 0.76, 0.80], np.float32)
BLACK_L = np.array([0.012, 0.013, 0.017], np.float32)
PALM_L = np.array([0.055, 0.045, 0.040], np.float32)


def glove_albedo(part, team, uvw):
    """Farbe, Glanz, Schärfe, Kavitätsabdunklung, Bump-Stärke, Rim-Faktor je Fragment (u, y, w lokal; |w| wird genutzt)."""
    n = len(part)
    col = np.zeros((n, 3), np.float32)
    spec = np.full(n, 0.10, np.float32)
    shine = np.full(n, 14.0, np.float32)
    cav = np.ones(n, np.float32)
    bump = np.full(n, 0.30, np.float32)
    rimk = np.ones(n, np.float32)
    for tm in (0, 1):
        tcol = TEAM_COL[tm]
        sel = team == tm
        if not sel.any():
            continue
        u, y, w = uvw[sel, 0], uvw[sel, 1], np.abs(uvw[sel, 2])
        v = u - U0                                                  # Maß ab Handbeginn
        pt = part[sel]
        hw0, _ = prof(u)
        hw, th = prof(u)
        kk = end_k(u)
        hw, th = hw * kk, th * kk                                   # tatsächliche Ringgröße an den Enden
        c = np.tile(np.array(tcol["main"], np.float32), (len(u), 1))
        dark = np.array(tcol["dark"], np.float32)
        sp = np.full(len(u), 0.13, np.float32)
        sh = np.full(len(u), 16.0, np.float32)
        bp = np.full(len(u), 0.55, np.float32)
        rk = np.ones(len(u), np.float32)
        body = pt == PART_BODY
        # Handrücken-Rillen / Fingerrollen: Kavitäten + Ziernähte
        s1 = np.abs(np.sin(np.pi * np.clip((v - 4.6) / 1.55, 0, 3.0))) ** 0.55
        s2 = np.abs(np.sin(np.pi * np.clip((v - 9.5) / 1.12, 0, 3.5))) ** 0.5
        groove = ((v > 4.6) & (v < 9.25) & (s1 < 0.42)) | ((v > 9.5) & (v < 13.42) & (s2 < 0.5))
        cv = np.where(groove & body, 0.14 + 0.9 * np.where(v < 9.4, s1, s2), 1.0).astype(np.float32)
        rel = y / np.maximum(th, 0.1)
        # Fingertrennrillen (Längsrillen): dunkel, nur auf der Oberseite
        fing = body & (rel > 0.55) & (v > 8.9) & (v < 13.95)
        gw = 0.20 * (0.35 + 0.65 * kk)
        gg = np.exp(-(w / gw) ** 2) + np.exp(-((w - 1.72 * hw0 * kk / 3.4) / gw) ** 2)
        gfade = smoothstep(8.9, 9.7, v) * (1.0 - smoothstep(13.3, 13.95, v))
        cv = cv * np.where(fing, 1.0 - 0.62 * np.clip(gg, 0, 1) * gfade, 1.0).astype(np.float32)
        # Ziernähte (Stichreihen) an den Rillenrändern
        sv = np.where(v < 9.4, s1, s2)
        stitch = body & (np.abs(sv - 0.62) < 0.035) & (((v > 4.7) & (v < 9.2)) | ((v > 9.6) & (v < 13.3))) \
            & ((w * 2.7) % 1.0 < 0.58)
        c[stitch] = c[stitch] * 0.45 + WHITE_L * 0.55
        bp[stitch] = 0.25
        # untere Seitenpartie (Gewebe) und Handfläche
        side_dark = body & (rel < 0.34) & (w > 0.25 * hw)
        c[side_dark] = dark
        sp[side_dark], sh[side_dark], bp[side_dark] = 0.05, 8.0, 0.9
        palm = body & (rel < 0.10) & (v > 3.0)
        c[palm] = PALM_L
        sp[palm], sh[palm], bp[palm] = 0.05, 10.0, 0.35
        # Piping entlang der Seitenkante
        pipe = body & (np.abs(rel - 0.34) < 0.028) & (v > 3.5) & (v < 13.3)
        c[pipe] = WHITE_L
        sp[pipe], sh[pipe], bp[pipe] = 0.10, 12.0, 0.25
        # Stulpe: sauberes, fast schwarzes Nylon mit feiner Steppung, weißer Randwulst und weißer Abschlussstreifen
        band = body & (u < U0 + 1.2)
        c[band] = BLACK_L
        sp[band], sh[band], bp[band], rk[band] = 0.05, 9.0, 0.10, 0.05
        quilt = 0.5 + 0.5 * np.sin(u * 5.2 + w * 5.2) * np.sin(u * 5.2 - w * 5.2)
        cv = np.where(band, cv * (0.80 + 0.20 * quilt), cv).astype(np.float32)
        edge = body & (u < 0.42)
        c[edge] = WHITE_L * 0.30
        sp[edge], sh[edge], bp[edge], rk[edge] = 0.06, 14.0, 0.15, 0.10
        stripe = body & (u >= U0 + 1.2) & (u < U0 + 1.5)
        c[stripe] = WHITE_L
        sp[stripe], sh[stripe], bp[stripe] = 0.10, 12.0, 0.3
        mid = body & (v > 3.75) & (v < 4.05)
        c[mid] = WHITE_L
        # Daumenspitze: dunkles Leder
        tip = (pt == PART_THUMB) & (v > 11.7)
        c[tip] = dark
        sp[tip], sh[tip], bp[tip] = 0.08, 10.0, 0.35
        # Daumen: dunkle Rillen
        th_ = pt == PART_THUMB
        cv[th_ & (np.abs(v - 8.2) < 0.12)] = 0.3
        cv[th_ & (np.abs(v - 10.1) < 0.12)] = 0.3
        ins = pt == PART_INSIDE
        c[ins] = np.array([0.006, 0.007, 0.012], np.float32)
        sp[ins], sh[ins], rk[ins] = 0.02, 6.0, 0.0
        col[sel], spec[sel], shine[sel], cav[sel], bump[sel], rimk[sel] = c, sp, sh, cv, bp, rk
    # Puck: schwarzes Gummi mit Rändelung an der Flanke
    sel = team == 2
    if sel.any():
        x, y, z = uvw[sel, 0], uvw[sel, 1], uvw[sel, 2]
        ang = np.arctan2(z, x)
        rr = np.hypot(x, z)
        side = (y > PUCK_B * 0.5) & (y < PUCK_H - PUCK_B * 0.5) & (rr > PUCK_R - 0.06)
        kn = (0.5 + 0.5 * np.sin(ang * 44 + y * 15.0)) * (0.5 + 0.5 * np.sin(ang * 44 - y * 15.0))
        c = np.tile(np.array([0.026, 0.027, 0.032], np.float32), (len(x), 1))
        c = np.where(side[:, None], c * (0.75 + 0.9 * kn[:, None]), c).astype(np.float32)
        cvp = np.where(side, 0.55 + 0.45 * kn, 1.0).astype(np.float32)
        col[sel] = c
        spec[sel] = np.where(side, 0.22, 0.40)
        shine[sel] = 16.0
        cav[sel] = cvp
        bump[sel] = 0.12
        flat = ((y > PUCK_H - 0.01) | (y < 0.01)) & (rr < PUCK_R - PUCK_B + 0.02)
        rimk[sel] = np.where(flat, 0.10, 1.0)
    return col, spec, shine, cav, bump, rimk


@njit(parallel=True, fastmath=True, cache=True)
def _grain(P, sc, eps, out):
    """Rauschen und Gradient (4 Auswertungen) für Mikro-Bump: out[:,0] = Wert, out[:,1:4] = Gradient."""
    for i in prange(P.shape[0]):
        x, y, z = P[i, 0] * sc, P[i, 1] * sc, P[i, 2] * sc
        n0 = P3.fbm3(x, y, z)
        out[i, 0] = n0
        out[i, 1] = (P3.fbm3(x + eps, y, z) - n0) / eps
        out[i, 2] = (P3.fbm3(x, y + eps, z) - n0) / eps
        out[i, 3] = (P3.fbm3(x, y, z + eps) - n0) / eps


# Light-Linking: Rim-Gewicht (blau, rot) je Gruppe: blau trifft nur den linken, rot nur den rechten Handschuh
RIMW = np.array([[1.0, 0.04], [0.04, 1.0], [0.80, 0.80]], np.float32)
KEY_I = float(os.environ.get("IGKEY", "2.9"))
RIM_I = float(os.environ.get("IGRIM", "1.5"))


def shade_glove(P, N, part, team, uvw, campos, mirror_cam=False):
    """Beleuchtung der Handschuh-Fragmente (linear HDR)."""
    alb, spec, shine, cav, bump, rimk = glove_albedo(part, team, uvw)
    V = unit_rows(campos - P)
    # Mikro-Bump (Leder/Gewebe) aus Rauschen in lokalen Koordinaten + weicher Albedo-Schwankung
    g = np.zeros((len(P), 4), np.float32)
    _grain(np.ascontiguousarray(uvw, np.float64), 11.0, 0.05, g)
    gv = g[:, 1:4]
    gv = gv - (gv * N).sum(1, keepdims=True) * N
    N = N - gv * (bump[:, None] * 0.07)
    N = N / (np.linalg.norm(N, axis=1, keepdims=True) + 1e-9)
    g2 = np.zeros((len(P), 4), np.float32)
    _grain(np.ascontiguousarray(uvw, np.float64), 2.4, 0.2, g2)
    alb = alb * (0.86 + 0.28 * g[:, 0:1]) * (0.90 + 0.20 * g2[:, 0:1])
    flip = (N * V).sum(1) < 0
    N = np.where(flip[:, None], -N, N)
    pl = pool(P[:, 0], P[:, 2])
    sp_k = (0.06 + 0.94 * pl)[:, None]
    # Key-Spot
    Lk = unit_rows(KEY_POS - P)
    ndl = np.clip((N * Lk).sum(1), 0, 1)[:, None]
    out = alb * ndl * sp_k * KEY_I
    Hk = unit_rows(Lk + V)
    out = out + spec[:, None] * np.clip((N * Hk).sum(1), 0, 1)[:, None] ** shine[:, None] * sp_k * 2.0
    # Rim-Lichter (farbig, per Light-Linking nur auf "ihren" Handschuh)
    rw = RIMW[team]
    for k, (Ld, Cc) in enumerate(((RIM_B, C_RIM_B), (RIM_R, C_RIM_R))):
        wk = rw[:, k:k + 1] * rimk[:, None] * RIM_I
        nl = np.clip(N @ Ld, 0, 1)[:, None]
        Hh = unit_rows(Ld[None, :] + V)
        sr = np.clip((N * Hh).sum(1), 0, 1)[:, None] ** np.maximum(shine[:, None] * 1.6, 18.0)
        fr = (1 - np.clip((N * V).sum(1), 0, 1))[:, None] ** 2.0
        out = out + wk * (alb * nl ** 2 * Cc * 1.1 + (0.30 + 0.70 * spec[:, None] * 2.0) * sr * Cc * 3.0 + fr * nl * Cc * 1.1)
    # weiches Auffüll-Licht von vorn-links-oben
    nlf = np.clip(N @ FILL, 0, 1)[:, None]
    out = out + alb * nlf * FILL_I
    Hf = unit_rows(FILL[None, :] + V)
    out = out + spec[:, None] * np.clip((N * Hf).sum(1), 0, 1)[:, None] ** (shine[:, None] * 1.3) * FILL_I * 1.6
    # Eis-Bounce (teamfarben getönt: links leicht cyan, rechts neutral kühl) + Himmel
    down = np.clip(0.5 - 0.5 * N[:, 1:2], 0, 1)
    up = np.clip(0.5 + 0.5 * N[:, 1:2], 0, 1)
    gp = pl[:, None]
    bounce = np.where((team == 0)[:, None], np.array([0.34, 0.66, 1.0], np.float32),
                      np.where((team == 1)[:, None], np.array([0.80, 0.56, 0.66], np.float32),
                               np.array([0.50, 0.66, 0.95], np.float32)))
    out = out + alb * down * (bounce * (0.25 + 1.3 * gp))
    out = out + alb * up * np.array([0.020, 0.030, 0.060], np.float32)
    out = out * cav[:, None]
    ao = (0.34 + 0.66 * smoothstep(0.0, 1.5, P[:, 1])) * (0.62 + 0.38 * smoothstep(0.0, 4.6, P[:, 1]))
    return (out * ao[:, None]).astype(np.float32)


def unit_rows(a):
    return a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)


# ================================================================= G-Buffer (Z-Buffer-Rasterizer aus mesh3d)
def gbuffer(m, cam, campos, ss, mirror=False):
    """Rastert das Gitter (optional an y=0 gespiegelt) und schattiert es.
    Gibt vormultipliziertes RGB (H,W,3), Alpha (H,W), mittlere Tiefe (H,W) und Höhe über dem Eis (H,W) zurück."""
    vr = m.v.copy()
    if mirror:
        vr[:, 1] *= -1
    sx, sy, sz = M3.project(cam, vr, W, H, ss)
    Hs, Ws = H * ss, W * ss
    depth = np.full((Hs, Ws), 1e9, np.float32)
    tid = np.full((Hs, Ws), -1, np.int32)
    b0 = np.zeros((Hs, Ws), np.float32)
    b1 = np.zeros((Hs, Ws), np.float32)
    M3._raster(sx.astype(np.float64), sy.astype(np.float64), sz.astype(np.float64), m.t, depth, tid, b0, b1)
    cov = tid >= 0
    rgb = np.zeros((Hs, Ws, 3), np.float32)
    zbuf = np.zeros((Hs, Ws), np.float32)
    hgt = np.zeros((Hs, Ws), np.float32)
    if cov.any():
        t = tid[cov]
        w0, w1 = b0[cov][:, None], b1[cov][:, None]
        w2 = 1 - w0 - w1
        tri = m.t[t]
        P = (w0 * m.v[tri[:, 0]] + w1 * m.v[tri[:, 1]] + w2 * m.v[tri[:, 2]]).astype(np.float32)
        N = (w0 * m.n[tri[:, 0]] + w1 * m.n[tri[:, 1]] + w2 * m.n[tri[:, 2]]).astype(np.float32)
        N = N / (np.linalg.norm(N, axis=1, keepdims=True) + 1e-9)
        UVW = (w0 * m.uvw[tri[:, 0]] + w1 * m.uvw[tri[:, 1]] + w2 * m.uvw[tri[:, 2]]).astype(np.float32)
        cp = campos.copy()
        if mirror:
            cp[1] *= -1
        col = shade_glove(P, N, m.m[t], m.g[t], UVW, cp.astype(np.float32), mirror)
        rgb[cov] = col
        zbuf[cov] = depth[cov]
        hgt[cov] = P[:, 1]

    def down(a):
        return a.reshape(H, ss, W, ss, *a.shape[2:]).mean(axis=(1, 3))

    a = down(cov.astype(np.float32))
    zsum, hsum = down(zbuf), down(hgt)
    rgb_d = down(rgb)
    return rgb_d, a, zsum / np.maximum(a, 1e-4), hsum / np.maximum(a, 1e-4)


def merge_gloves(gl):
    return M3.merge(gl)


# ================================================================= Kamera
CAM_POS = np.array([float(v) for v in os.environ.get("IGPOS", "0,14.5,82").split(",")])
CAM_TGT = np.array([float(v) for v in os.environ.get("IGTGT", "-0.3,1.8,0").split(",")])
FOV = float(os.environ.get("IGFOV", "30"))
APERTURE = float(os.environ.get("IGAP", "0.6"))


def camera():
    r, u, f = P3.look_at(CAM_POS, CAM_TGT, np.array([0.0, 1.0, 0.0]))
    return P3.cam_row(CAM_POS, r, u, f, FOV), f


# ================================================================= Ebene Eis: Treffer, Kratzer
def ray_dirs(row):
    """Pixelstrahlen (H,W,3) und NDC-Gitter."""
    xs = ((np.arange(W) + 0.5) / W * 2 - 1).astype(np.float32)
    ys = (1 - (np.arange(H) + 0.5) / H * 2).astype(np.float32)
    nx, ny = np.meshgrid(xs, ys)
    pos, r, u, f, tanh = row[0:3], row[3:6], row[6:9], row[9:12], row[12]
    d = (f[None, None, :] + nx[..., None] * (tanh * W / H) * r[None, None, :] + ny[..., None] * tanh * u[None, None, :])
    d = (d / np.linalg.norm(d, axis=2, keepdims=True)).astype(np.float32)
    return d, nx, ny


def ice_hit(row, d):
    pos = row[0:3]
    dy = d[..., 1]
    hit = dy < -1e-4
    t = np.where(hit, -pos[1] / np.where(hit, dy, -1.0), 0.0).astype(np.float32)
    return (pos[0] + t * d[..., 0]).astype(np.float32), (pos[2] + t * d[..., 2]).astype(np.float32), t, hit


_SCR = {}


def scratch_tex(n=4096, extent=(-46.0, 46.0, -32.0, 42.0), seed=7):
    """Kratzer-Textur (Eis, Draufsicht): lange, leicht gekrümmte Kufenspuren + Büschel + feine Maserung."""
    key = (n, extent, seed)
    if key in _SCR:
        return _SCR[key]
    rng = np.random.default_rng(seed)
    x0, x1, z0, z1 = extent
    sx, sz = n / (x1 - x0), n / (z1 - z0)
    im = Image.new("L", (n, n), 0)
    dr = ImageDraw.Draw(im)

    def arc(px, pz, th, kappa, length, val, wd):
        pts = []
        steps = max(int(length / 0.5), 2)
        for _ in range(steps):
            pts.append(((px - x0) * sx, (pz - z0) * sz))
            px += math.cos(th) * 0.5
            pz += math.sin(th) * 0.5
            th += kappa * 0.5
        dr.line(pts, fill=int(val), width=wd)

    for _ in range(int(os.environ.get("IGSCR", "2600"))):             # lange Kufenspuren
        px, pz = rng.uniform(x0, x1), rng.uniform(z0, z1)
        arc(px, pz, rng.uniform(0, 2 * math.pi), rng.normal(0, 1 / 70.0), rng.lognormal(math.log(22), 0.7),
            rng.uniform(40, 255) * rng.uniform(0.4, 1.0), 1 if rng.random() < 0.85 else 2)
    for _ in range(60):                                              # Bremsspuren: Büschel
        cx, cz = rng.normal(0, 16), rng.normal(0, 12)
        th = rng.uniform(0, 2 * math.pi)
        for _ in range(rng.integers(10, 26)):
            arc(cx + rng.normal(0, 0.8), cz + rng.normal(0, 0.8), th + rng.normal(0, 0.12), rng.normal(0, 1 / 18.0),
                rng.uniform(4, 15), rng.uniform(40, 200), 1)
    a = np.asarray(im, np.float32) / 255
    a = gaussian_filter(a, 0.9)
    a = a / max(float(a.max()), 1e-3)
    _SCR[key] = (a, extent)
    return _SCR[key]


def sample_tex(tex, x, z):
    a, (x0, x1, z0, z1) = tex
    n = a.shape[0]
    ix = (x - x0) / (x1 - x0) * n
    iz = (z - z0) / (z1 - z0) * n
    out = map_coordinates(a, [iz, ix], order=1, mode="constant", cval=0.0)
    return out.astype(np.float32)


def value_noise(x, z, scale, seed):
    """Weiche, großflächige Maserung (Eis-Wellen) per Gitter-Rauschen."""
    rng = np.random.default_rng(seed)
    g = rng.random((64, 64)).astype(np.float32)
    g = gaussian_filter(g, 1.0, mode="wrap")
    g = (g - g.min()) / (g.max() - g.min())
    return map_coordinates(g, [(z / scale) % 64, (x / scale) % 64], order=1, mode="wrap").astype(np.float32)


# ================================================================= Hintergrund + Dunst
def blur_img(img, sigma):
    """Gauß-Weichzeichner mit schneller Verkleinerung bei großen Radien (img: HxW oder HxWxC)."""
    if sigma < 0.4:
        return img
    f = 1
    while sigma / f > 5.0:
        f *= 2
    if f == 1:
        s = (sigma, sigma, 0) if img.ndim == 3 else sigma
        return gaussian_filter(img, s, mode="nearest").astype(np.float32)
    h, w = img.shape[:2]
    hp, wp = -(-h // f) * f, -(-w // f) * f
    pad = [(0, hp - h), (0, wp - w)] + ([(0, 0)] if img.ndim == 3 else [])
    im = np.pad(img, pad, mode="edge")
    sm = im.reshape(hp // f, f, wp // f, f, *im.shape[2:]).mean(axis=(1, 3))
    s = (sigma / f, sigma / f, 0) if img.ndim == 3 else sigma / f
    sm = gaussian_filter(sm, s, mode="nearest").astype(np.float32)
    if img.ndim == 2:
        up = np.asarray(Image.fromarray(sm, "F").resize((wp, hp), Image.BICUBIC), np.float32)
    else:
        up = np.stack([np.asarray(Image.fromarray(np.ascontiguousarray(sm[..., c]), "F").resize((wp, hp), Image.BICUBIC),
                                  np.float32) for c in range(img.shape[2])], -1)
    return up[:h, :w]


def disc(r, soft):
    n = int(r * 2 + 6)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    d = np.sqrt((xx - n / 2 + 0.5) ** 2 + (yy - n / 2 + 0.5) ** 2)
    body = 1 - smoothstep(r - soft, r + 0.5, d)
    rim = np.exp(-((d - r * 0.93) / max(soft * 1.2, 1.0)) ** 2) * 0.35
    return (body * 0.75 + rim).astype(np.float32)


def add_disc(img, cx, cy, r, col, amp):
    d = disc(r, max(1.0, r * 0.18))
    n = d.shape[0]
    x0, y0 = int(round(cx - n / 2)), int(round(cy - n / 2))
    xs, ys = max(0, -x0), max(0, -y0)
    xe, ye = min(n, W - x0), min(n, H - y0)
    if xs >= xe or ys >= ye:
        return
    img[y0 + ys:y0 + ye, x0 + xs:x0 + xe] += d[ys:ye, xs:xe, None] * np.asarray(col, np.float32) * amp


def horizon_row(row):
    """Bildzeile des Horizonts (unendlich ferne Punkte auf Augenhöhe)."""
    f, u, tanh = row[9:12], row[6:9], row[12]
    hv = np.array([f[0], 0.0, f[2]])
    hv /= np.linalg.norm(hv)
    ys = (hv @ u) / (hv @ f) / tanh
    return (1 - ys) * H / 2


def backdrop(row, d, nx, ny):
    """Dunkle Arena in der Ferne: Dunstband am Horizont, farbige Fernlichter, Bokeh. HDR linear (H,W,3)."""
    el = d[..., 1]
    az = np.arctan2(d[..., 0], -d[..., 2])
    base = np.zeros((H, W, 3), np.float32)
    base += np.array([0.0015, 0.002, 0.005], np.float32)
    band = np.exp(-(np.maximum(el, 0) / 0.035) ** 2)[..., None] * np.array([0.006, 0.009, 0.020], np.float32)
    base += band
    # farbige Fernlichter links/rechts (Gegenlicht aus der Tiefe): schmal, damit die Mitte dunkel bleibt
    for a0, col, amp in ((-0.43, (0.04, 0.24, 1.0), 0.62), (0.43, (1.0, 0.08, 0.14), 0.58)):
        gl = np.exp(-((az - a0) / 0.17) ** 2) * np.exp(-(np.maximum(el, 0) / 0.20) ** 2)
        base += gl[..., None] * np.array(col, np.float32) * amp
    return base


def bokeh_layer(row):
    """Ferne Hallenlichter als unscharfe Scheiben (über dem Horizont) und ihre matte Spiegelung im Eis."""
    rng = np.random.default_rng(11)
    hr = float(horizon_row(row))
    layer = np.zeros((H, W, 3), np.float32)
    for i in range(int(os.environ.get("IGBOKEH", "15"))):
        cx = rng.uniform(-0.05, 1.05) * W
        up = rng.beta(1.3, 2.2)
        r = rng.uniform(14, 40) * S * (1.0 + 0.5 * up)
        cy = (float(os.environ.get("IGBY0", "300")) + up * float(os.environ.get("IGBY1", "250"))) * S
        kind = rng.random()
        if cx < W * 0.45:
            col = (0.35, 0.62, 1.0) if kind < 0.65 else (0.8, 0.9, 1.0)
        elif cx > W * 0.55:
            col = (1.0, 0.30, 0.30) if kind < 0.65 else (1.0, 0.86, 0.75)
        else:
            col = (0.75, 0.85, 1.0) if kind < 0.7 else (1.0, 0.9, 0.78)
        amp = rng.uniform(0.05, 0.20) * (1.0 - 0.5 * up)
        add_disc(layer, cx, cy, r, col, amp)
    # Spiegelung: an der Horizontlinie spiegeln, vertikal gestreckt verwischen, nach unten ausblenden
    rows = np.arange(H)
    src = np.clip((2 * hr - rows).astype(np.int64), 0, H - 1)
    mir = layer[src]
    mir = blur_img(mir, 4 * S) if False else gaussian_filter(mir, (11 * S, 3 * S, 0), mode="nearest")
    fade = np.exp(-np.maximum(rows - hr, 0) / (90 * S)).astype(np.float32)
    mir = mir * (fade * (rows > hr))[:, None, None] * 0.55
    return layer, mir.astype(np.float32)


# ================================================================= Eis schattieren
ICE_ALB = np.array([0.60, 0.72, 0.90], np.float32)
SIDE_B = (-19.0, -9.0)
SIDE_R = (19.0, -9.0)


def shade_ice(row, d, bg):
    """Eis als Ebene: Spot-Fleck, farbige Seiten-Pools, Kratzer, Fresnel-Spiegelung der Ferne. -> HDR, Tiefe, Fresnel, hit"""
    pos, rr_, uu, ff, tanh = row[0:3], row[3:6], row[6:9], row[9:12], row[12]
    x, z, t, hit = ice_hit(row, d)
    cosv = np.clip(-d[..., 1], 0.0, 1.0)
    I = pool(x, z)
    ripple = value_noise(x, z, 6.0, 3) * 0.6 + value_noise(x, z, 1.7, 5) * 0.4
    tex = scratch_tex(int(os.environ.get("IGTEX", "6144")))
    scr = sample_tex(tex, x, z)
    ex = np.exp(-(((x - SIDE_B[0]) / 11.0) ** 2 + ((z - SIDE_B[1]) / 15.0) ** 2))
    er = np.exp(-(((x - SIDE_R[0]) / 11.0) ** 2 + ((z - SIDE_R[1]) / 15.0) ** 2))
    diff = ICE_ALB[None, None, :] * (0.004 + float(os.environ.get("IGICE", "1.5")) * (I * (0.90 + 0.20 * ripple))[..., None])
    diff += ICE_ALB[None, None, :] * (scr * (0.15 + I) * 0.55)[..., None] * (0.35 + 0.65 * I[..., None])
    diff += ICE_ALB[None, None, :] * (ex[..., None] * np.array([0.05, 0.22, 1.0], np.float32) * 0.55
                                      + er[..., None] * np.array([1.0, 0.08, 0.10], np.float32) * 0.55)
    # Fresnel-Spiegelung der fernen Arena (unendlich weit: Projektion der Spiegelrichtung ins Bild)
    Rd = d.copy()
    Rd[..., 1] = -Rd[..., 1]
    rf = (Rd * ff).sum(2)
    xs_ = ((Rd * rr_).sum(2) / np.maximum(rf, 1e-4) / (tanh * W / H) + 1) * W / 2
    ys_ = (1 - (Rd * uu).sum(2) / np.maximum(rf, 1e-4) / tanh) * H / 2
    bgb = blur_img(bg, 5.0 * S)
    refl = np.stack([map_coordinates(bgb[..., c], [np.clip(ys_, 0, H - 1), np.clip(xs_, 0, W - 1)], order=1)
                     for c in range(3)], -1)
    off = ((ys_ < 0) | (ys_ > H - 1)) | ((xs_ < 0) | (xs_ > W - 1))
    refl = np.where(off[..., None], np.array([0.004, 0.006, 0.014], np.float32), refl)
    F = (0.025 + 0.975 * (1 - cosv) ** 5).astype(np.float32)
    F = np.clip(F * float(os.environ.get("IGFRES", "0.9")), 0, 1)
    haze_col = np.array([0.008, 0.012, 0.026], np.float32)
    fog = 1 - np.exp(-t / 150.0)
    diff = diff * (1 - fog[..., None]) + haze_col * fog[..., None]
    ice = diff * (1 - F[..., None]) + refl * F[..., None]
    ice += ICE_ALB[None, None, :] * (scr * I * (1 - fog) * float(os.environ.get("IGSCRI", "0.85")))[..., None]
    # Spiegelung des Spots (matt): Schimmer im Vordergrund
    kd = unit_rows((KEY_POS[None, :] - np.stack([x, np.zeros_like(x), z], -1)).reshape(-1, 3)).reshape(H, W, 3)
    cs = np.clip((Rd * kd).sum(2), 0, 1)
    ice += (np.exp(-((1 - cs) / 0.010)) * 1.8 * F)[..., None] * np.array([0.8, 0.9, 1.0], np.float32)
    zmap = ((np.stack([x - pos[0], -pos[1] * np.ones_like(x), z - pos[2]], -1)) * ff).sum(2)
    ice = np.where(hit[..., None], ice, bg)
    zmap = np.where(hit, zmap, 1e5).astype(np.float32)
    return ice.astype(np.float32), zmap, F, hit


# ================================================================= Tiefenschärfe
def var_blur(img, coc, levels):
    """Ortsabhängige Unschärfe: coc (Pixel-Radius je Pixel) -> Gauß-Sigma = 0.55*coc, lineare Mischung benachbarter Stufen."""
    sig = (coc * 0.55).astype(np.float32)
    out = np.zeros_like(img)
    lv = list(levels)
    for i, s in enumerate(lv):
        lo = lv[i - 1] if i > 0 else None
        hi = lv[i + 1] if i + 1 < len(lv) else None
        w = np.zeros_like(sig)
        if lo is None:
            w = np.where(sig <= s, 1.0, 0.0)
        else:
            w = np.where((sig > lo) & (sig <= s), (sig - lo) / (s - lo), 0.0)
        if hi is None:
            w = np.where(sig > s, 1.0, w)
        else:
            w = np.where((sig > s) & (sig < hi), (hi - sig) / (hi - s), w)
        if not w.any():
            continue
        out += (w[..., None] if img.ndim == 3 else w) * (blur_img(img, s) if s > 0.3 else img)
    return out


def coc_map(z, fz, row):
    ppi = (H / 2) / (row[12] * fz)
    c = APERTURE * np.abs(z - fz) / np.maximum(z, 1e-3) * ppi
    return np.clip(c, 0, 26 * S).astype(np.float32)


# ================================================================= Dunst im Spot
def beam_layer(row):
    """Weiche Lichtwolke (Dunst im Spot) um die Handschuhe, oben ausklingend."""
    hr = horizon_row(row)
    xy, _ = P3.project(row, np.array([[0.0, 4.0, 0.0]]), W, H)
    cx, cy = float(xy[0, 0]), float(xy[0, 1])
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    g = np.exp(-(((xx - cx) / (0.55 * W)) ** 2 + ((yy - (cy - 110 * S)) / (330 * S)) ** 2))
    return g.astype(np.float32)


# ================================================================= Lichtkegel (Volumen)
CONE_R = POOL_R * float(os.environ.get("IGCR", "0.8"))
CONE_APEX = 150.0


def cone_layer(row, sc=4):
    """Streulicht im Scheinwerferkegel: Raymarching durch einen elliptischen Kegel (niedrige Auflösung), hoch skaliert."""
    h, w = H // sc, W // sc
    xs = ((np.arange(w) + 0.5) / w * 2 - 1).astype(np.float32)
    ys = (1 - (np.arange(h) + 0.5) / h * 2).astype(np.float32)
    nx, ny = np.meshgrid(xs, ys)
    pos, r, u, f, tanh = row[0:3], row[3:6], row[6:9], row[9:12], row[12]
    d = f[None, None, :] + nx[..., None] * (tanh * W / H) * r[None, None, :] + ny[..., None] * tanh * u[None, None, :]
    d = (d / np.linalg.norm(d, axis=2, keepdims=True)).astype(np.float32)
    acc = np.zeros((h, w), np.float32)
    ts = np.linspace(38.0, 128.0, 56, dtype=np.float32)
    dt = float(ts[1] - ts[0])
    for t in ts:
        px, py, pz = pos[0] + t * d[..., 0], pos[1] + t * d[..., 1], pos[2] + t * d[..., 2]
        s_ = np.clip((CONE_APEX - py) / CONE_APEX, 0.02, 1.0)
        dx, dz = (px - POOL_C[0]) / (CONE_R[0] * s_), (pz - POOL_C[2]) / (CONE_R[1] * s_)
        dd = np.sqrt(dx * dx + dz * dz)
        phi = np.arctan2(dz, dx)
        streak = 0.70 + 0.30 * np.cos(5 * phi + 0.8) * np.cos(3 * phi - 0.4) + 0.12 * np.cos(11 * phi)
        dens = (1.0 - smoothstep(0.50, 1.0, dd)) * np.exp(-np.maximum(py, 0) / float(os.environ.get("IGCH", "16"))) * (py > 0)
        acc += dens * streak
    acc = acc * dt / 60.0
    im = np.asarray(Image.fromarray(acc, "F").resize((W, H), Image.BICUBIC), np.float32)
    return blur_img(im, 3 * S)


# ================================================================= Lichtschäfte
def shafts_layer(row):
    """Wenige schmale, sehr weiche Lichtkeile von oben auf den Spot-Fleck (Dunst im Scheinwerferkegel)."""
    apex = np.array([0.0, 140.0, -3.0])
    rng = np.random.default_rng(21)
    im = Image.new("F", (W, H), 0.0)
    dr = ImageDraw.Draw(im)
    n = 9
    for i in range(n):
        a0 = rng.uniform(0, 2 * math.pi)
        da = rng.uniform(0.07, 0.17)
        pts = [apex]
        for a in (a0, a0 + da):
            pts.append(np.array([POOL_C[0] + 0.9 * POOL_R[0] * math.cos(a), 0.0, POOL_C[2] + 0.9 * POOL_R[1] * math.sin(a)]))
        xy, z = P3.project(row, np.array(pts), W, H)
        dr.polygon([tuple(p_) for p_ in xy], fill=float(rng.uniform(0.35, 1.0)))
    a = np.asarray(im, np.float32)
    yy = np.arange(H, dtype=np.float32)[:, None]
    base_y = float(P3.project(row, np.array([[0.0, 6.0, 0.0]]), W, H)[0][0, 1])
    g = np.clip(1.0 - (base_y - yy) / (640 * S), 0, 1) ** 1.2
    return blur_img(a * g, 15 * S)


# ================================================================= Staubkörner / Eisstaub im Licht
def dust_layer(row, fz):
    rng = np.random.default_rng(5)
    n = int(os.environ.get("IGDUST", "70"))
    pts = np.stack([rng.normal(0, 10, n), rng.uniform(0.5, 17, n), rng.normal(-1, 7, n)], 1)
    xy, z = P3.project(row, pts, W, H)
    layer = np.zeros((H, W, 3), np.float32)
    for i in range(n):
        foc = abs(z[i] - fz) / max(z[i], 1.0)
        r = (0.8 + 7.0 * foc * float(APERTURE) * 2.2) * S
        amp = rng.uniform(0.25, 1.1) / (1.0 + 4.0 * foc * float(APERTURE) * 2.2) ** 2
        warm = rng.random()
        col = (1.0, 0.92, 0.82) if warm < 0.35 else (0.78, 0.88, 1.0)
        if 0 <= xy[i, 0] < W and 0 <= xy[i, 1] < H:
            add_disc(layer, xy[i, 0], xy[i, 1], max(r, 0.8 * S), col, amp * 0.5)
    return layer


# ================================================================= Schatten
SHADOW_L = unit([0.22, 1.0, -0.40])


def shadow_masks(m, row):
    """Weicher Schlagschatten (Richtungslicht) + Kontaktschatten (senkrechte Projektion) auf dem Eis, in Bildauflösung."""
    ss = max(SS, 1)
    v = m.v
    sh = v - SHADOW_L[None, :] * (v[:, 1:2] / SHADOW_L[1])
    sh[:, 1] = 0.02
    hx, hy, _ = M3.project(row, sh, W, H, ss)
    cast = np.zeros((H * ss, W * ss), np.float32)
    M3._raster_mask(hx.astype(np.float64), hy.astype(np.float64), m.t, cast)
    low = v[:, 1] < 99
    ct = v.copy()
    ct[:, 1] = 0.02
    cx_, cy_, _ = M3.project(row, ct, W, H, ss)
    contact = np.zeros_like(cast)
    M3._raster_mask(cx_.astype(np.float64), cy_.astype(np.float64), m.t, contact)

    def down(a):
        return a.reshape(H, ss, W, ss).mean(axis=(1, 3))

    cast, contact = down(cast), down(contact)
    return blur_img(cast, 7 * S), blur_img(contact, 14 * S), blur_img(contact, 2.5 * S)


# ================================================================= Szene
def render_hdr():
    row, f = camera()
    d, nx, ny = ray_dirs(row)
    bg = backdrop(row, d, nx, ny)
    ice, zmap, F, hit = shade_ice(row, d, bg)
    gl = gloves()
    m = merge_gloves(gl)
    fz = float((np.array([0.0, 2.5, 0.0]) - CAM_POS) @ f)
    # Schatten + Kontaktschatten
    cast, cont_soft, cont_tight = shadow_masks(m, row)
    shade = 1.0 - 0.80 * np.clip(cast, 0, 1) * (1 - 0.0)
    shade *= 1.0 - 0.62 * np.clip(cont_soft * 1.5, 0, 1)
    shade *= 1.0 - 0.80 * np.clip(cont_tight * 1.3, 0, 1)
    shade = np.clip(shade, 0.0, 1.0)
    ground = hit[..., None]
    ice = np.where(ground, ice * shade[..., None], ice)
    # Spiegelung der Handschuhe im Eis
    mr, ma, mz, mh = gbuffer(m, row, CAM_POS, SS, mirror=True)
    k_lo = blur_img(np.concatenate([mr, ma[..., None]], -1), 1.2 * S)
    k_hi = blur_img(np.concatenate([mr, ma[..., None]], -1), 9 * S)
    mixh = smoothstep(0.0, 5.0, mh)[..., None]
    refl = k_lo * (1 - mixh) + k_hi * mixh
    fade = np.exp(-np.maximum(mh, 0) / 6.0)[..., None]
    Fg = np.clip(F * 1.9, 0, 0.85)[..., None]
    ra = refl[..., 3:4] * fade
    ice = ice * (1 - Fg * np.clip(ra * 1.0, 0, 1)) + refl[..., :3] * fade * Fg
    # Lichtkegel
    bm = beam_layer(row)
    ice = ice + bm[..., None] * np.array([0.050, 0.070, 0.115], np.float32) * float(os.environ.get("IGBEAM", "0.25"))
    sf = shafts_layer(row)
    ice = ice + sf[..., None] * np.array([0.050, 0.065, 0.100], np.float32) * float(os.environ.get("IGSHAFT", "0.38"))
    cn = cone_layer(row)
    ice = ice + cn[..., None] * np.array([0.30, 0.42, 0.70], np.float32) * float(os.environ.get("IGCONE", "1.0"))
    # Tiefenschärfe auf Eis/Hintergrund
    coc = coc_map(zmap, fz, row)
    coc = np.where(hit, coc, 0.0).astype(np.float32)
    ice = var_blur(ice, coc, [0.0, 1.5 * S, 3.5 * S, 7 * S, 13 * S])
    bk, bk_m = bokeh_layer(row)
    ice = ice + bk + bk_m
    ice = ice + dust_layer(row, fz)
    # Handschuhe
    gr, ga, gz, gh = gbuffer(m, row, CAM_POS, SS)
    cg = coc_map(np.where(ga > 0.01, gz, fz), fz, row)
    pk = var_blur(np.concatenate([gr, ga[..., None]], -1), cg, [0.0, 1.0 * S, 2.2 * S, 4 * S])
    gr, ga = pk[..., :3], pk[..., 3:4]
    img = ice * (1 - ga) + gr
    # Bloom
    bright = np.maximum(img - 0.85, 0)
    img = img + blur_img(bright, 9 * S) * 0.55 + blur_img(bright, 30 * S) * 0.60
    return img.astype(np.float32), row


def grade(img):
    """Tonemap + Look: kühle Schatten, leichter Kontrast, Vignette."""
    t = P3.tonemap(img)
    t = t ** np.array([1.0, 1.0, 0.97], np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    v = np.clip(np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H * 0.52) / H) ** 2) * 2.2 - 0.40, 0, 1) ** 1.4
    t = t * (1 - 0.70 * v[..., None])
    return np.clip(t, 0, 1)


# ================================================================= Typo
def tx(txt_, size, wght, col, track=0.0):
    return R15.line_img(txt_, max(int(round(size * S)), 4), wght, col, track=track * S, cache=False)


def paste_c(L, im, cx, cy):
    L.alpha_composite(im, (int(round(cx * S - im.width / 2)), int(round(cy * S - im.height / 2))))


def glow_of(im, rad, col_fn, strength=1.0):
    """Weicher Schein hinter einem Textbild; col_fn(x_norm) -> RGB (Verlauf links->rechts)."""
    pad = int(rad * 3)
    a = Image.new("L", (im.width + 2 * pad, im.height + 2 * pad), 0)
    a.paste(im.getchannel("A"), (pad, pad))
    a = a.filter(ImageFilter.GaussianBlur(rad))
    arr = np.asarray(a, np.float32) / 255
    xn = np.linspace(0, 1, arr.shape[1], dtype=np.float32)
    cols = np.array([col_fn(v) for v in xn], np.float32)
    rgb = np.broadcast_to(cols[None, :, :], arr.shape + (3,))
    out = np.concatenate([rgb, np.clip(arr * strength, 0, 1)[..., None] * 255], -1).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def lerp_col(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def team_grad(x):
    if x < 0.5:
        return lerp_col((40, 110, 255), (170, 70, 200), x * 2)
    return lerp_col((170, 70, 200), (255, 40, 50), (x - 0.5) * 2)


def headline(L):
    g = tx("GLOVES OFF.", float(os.environ.get("IGHS", "144")), 900, (255, 255, 255), track=-1.5)
    cy = float(os.environ.get("IGHY", "225"))
    gl = glow_of(g, 20 * S, team_grad, 0.85)
    L.alpha_composite(gl, (int(round(W / 2 - gl.width / 2)), int(round(cy * S - gl.height / 2))))
    # leichter Verlauf in den Buchstaben (oben weiß, unten kühl)
    arr = np.asarray(g).copy().astype(np.float32)
    yy = np.linspace(0, 1, arr.shape[0], dtype=np.float32)[:, None, None]
    tint = np.array([255, 255, 255], np.float32) * (1 - yy) + np.array([196, 214, 255], np.float32) * yy
    arr[..., :3] = tint
    g2 = Image.fromarray(arr.astype(np.uint8), "RGBA")
    paste_c(L, g2, W / 2 / S, cy)


def texts(base):
    pil = Image.fromarray((np.clip(base, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    paste_c(L, tx("NHL RULES EXPLAINED", 28, 800, (255, 122, 32), track=9), 540, 100)
    headline(L)
    # Frage
    q = tx("SHOULD THE NHL BAN FIGHTING?", float(os.environ.get("IGQS", "50")), 800, (236, 240, 250), track=2.5)
    paste_c(L, q, 540, float(os.environ.get("IGQY", "1040")))
    # Aufruf
    yes = tx("YES", 112, 900, BLUE_T)
    orr = tx("or", 62, 700, (200, 206, 222))
    no = tx("NO?", 112, 900, RED_T)
    gap = 26 * S
    tw = yes.width + orr.width + no.width + 2 * gap
    x0 = W / 2 - tw / 2
    cy = float(os.environ.get("IGCY", "1150")) * S
    for im, xx, dy, gc in ((yes, x0, 0, (40, 110, 255)), (orr, x0 + yes.width + gap, 8 * S, None),
                           (no, x0 + yes.width + orr.width + 2 * gap, 0, (255, 40, 50))):
        if gc:
            gl = glow_of(im, 14 * S, lambda v, gc=gc: gc, 0.55)
            L.alpha_composite(gl, (int(round(xx - (gl.width - im.width) / 2)), int(round(cy - gl.height / 2 + dy))))
        L.alpha_composite(im, (int(round(xx)), int(round(cy - im.height / 2 + dy))))
    paste_c(L, tx("COMMENT BELOW", 28, 800, (214, 220, 236), track=9), 540, float(os.environ.get("IGCB", "1228")))
    paste_c(L, tx("@BLADESANDPUCKS", 22, 700, (150, 160, 184), track=6), 540, 1300)
    pil.alpha_composite(L)
    return np.asarray(pil.convert("RGB")).astype(np.float32) / 255


def finish(arr):
    rng = np.random.default_rng(2)
    arr = arr + rng.normal(0, 0.0065, arr.shape[:2])[..., None].astype(np.float32)
    out = Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8))
    if W != 1080:
        out = out.resize((1080, 1350), Image.LANCZOS)
    return out


def main():
    base_path = os.environ.get("IGBASE", "")
    if base_path and os.path.exists(base_path):
        base = np.asarray(Image.open(base_path).convert("RGB"), np.float32) / 255
    else:
        hdr, row = render_hdr()
        base = grade(hdr)
        if base_path:
            Image.fromarray((base * 255).astype(np.uint8)).save(base_path)
    if STAGE == "base":
        out = finish(base)
    else:
        out = finish(texts(base))
    out.save(OUT, quality=95, subsampling=0)
    print("gespeichert:", OUT, out.size)


if __name__ == "__main__":
    main()
