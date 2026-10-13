"""Kleine 3D-Engine für Spieler-Details in den Nahaufnahmen (Schlittschuhe, Beine, Schläger).

Gitter werden prozedural gebaut (Loft entlang einer Achse / extrudierte Profile), mit einem numba-
Rasterizer (Z-Buffer, perspektivisch korrekte Interpolation, 2x Supersampling) gezeichnet und im
Studio-Licht des Puck-Renderers schattiert (Hauptlicht, Himmel, heller Eis-Bounce, Glanz).
Projektion identisch zu puck3d.project, damit alles exakt auf dem gerenderten Eis sitzt.
Einheiten: Zoll, y nach oben.
"""
import math

import numpy as np
from numba import njit
from PIL import Image, ImageFilter

LIGHT = np.array([0.35, 1.0, -0.45])
LIGHT /= np.linalg.norm(LIGHT)

# Materialien: Grundfarbe (linear 0..1), Glanzstärke, Glanzschärfe
MAT = {
    "boot": ((0.035, 0.036, 0.042), 0.35, 60.0),
    "boot_accent": ((0.30, 0.31, 0.34), 0.45, 70.0),
    "tongue": ((0.80, 0.80, 0.82), 0.05, 10.0),
    "lace": ((0.92, 0.92, 0.94), 0.05, 10.0),
    "holder": ((0.86, 0.87, 0.90), 0.35, 50.0),
    "steel": ((0.55, 0.57, 0.62), 1.2, 140.0),
    "sock": ((0.85, 0.23, 0.03), 0.02, 8.0),
    "sock_stripe": ((0.92, 0.92, 0.94), 0.02, 8.0),
    "pants": ((0.025, 0.026, 0.035), 0.12, 20.0),
    "pants_stripe": ((0.14, 0.14, 0.16), 0.12, 20.0),
    "jersey": ((0.85, 0.23, 0.03), 0.04, 10.0),
    "jersey_stripe": ((0.92, 0.92, 0.94), 0.04, 10.0),
    "carbon": ((0.03, 0.03, 0.035), 0.5, 80.0),
    "tape": ((0.90, 0.90, 0.92), 0.05, 10.0),
}
MAT_IDS = {k: i for i, k in enumerate(MAT)}
MAT_COL = np.array([MAT[k][0] for k in MAT], np.float32)
MAT_SPEC = np.array([MAT[k][1] for k in MAT], np.float32)
MAT_SHINE = np.array([MAT[k][2] for k in MAT], np.float32)


class Mesh:
    """Dreiecksnetz mit Vertex-Normalen, Material je Dreieck und Musterkoordinaten je Vertex."""

    def __init__(self, v, n, tris, mat, uvw=None, group=0):
        self.v = np.asarray(v, np.float64)
        self.n = np.asarray(n, np.float64)
        self.t = np.asarray(tris, np.int32)
        self.m = np.full(len(self.t), mat, np.int32) if np.isscalar(mat) else np.asarray(mat, np.int32)
        self.uvw = np.zeros((len(self.v), 3)) if uvw is None else np.asarray(uvw, np.float64)
        self.g = np.full(len(self.t), group, np.int32)


def merge(meshes):
    vs, ns, ts, ms, us, gs = [], [], [], [], [], []
    off = 0
    for m in meshes:
        vs.append(m.v)
        ns.append(m.n)
        ts.append(m.t + off)
        ms.append(m.m)
        us.append(m.uvw)
        gs.append(m.g)
        off += len(m.v)
    out = Mesh(np.concatenate(vs), np.concatenate(ns), np.concatenate(ts), np.concatenate(ms), np.concatenate(us))
    out.g = np.concatenate(gs)
    return out


def vertex_normals(v, tris):
    fn = np.cross(v[tris[:, 1]] - v[tris[:, 0]], v[tris[:, 2]] - v[tris[:, 0]])
    n = np.zeros_like(v)
    for k in range(3):
        np.add.at(n, tris[:, k], fn)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.maximum(ln, 1e-9)


def grid_tris(rows, cols, wrap=True):
    """Dreiecke für ein rows x cols Gitter (Ringe), optional geschlossen in cols-Richtung."""
    tris = []
    cmax = cols if wrap else cols - 1
    for i in range(rows - 1):
        for j in range(cmax):
            a = i * cols + j
            b = i * cols + (j + 1) % cols
            c = (i + 1) * cols + j
            d = (i + 1) * cols + (j + 1) % cols
            tris += [(a, c, b), (b, c, d)]
    return np.array(tris, np.int32)


def cap(v_list, ring_start, cols, center):
    """Fächer-Deckel für einen Ring."""
    ci = len(v_list)
    v_list.append(center)
    return [(ring_start + j, ring_start + (j + 1) % cols, ci) for j in range(cols)]


# ================================================================= Schlittschuh (lokal: u vor, y hoch, w seitlich)
def _boot_h(u):
    """Oberkante des Schuhs über der Sohle (Schaft hinten hoch, Spann, flache Zehenkappe)."""
    pts = [(-5.3, 9.9), (-4.4, 10.7), (-1.6, 10.8), (-0.5, 9.9), (1.0, 7.1), (2.4, 5.9), (4.2, 5.1), (5.4, 4.5), (6.1, 4.0)]
    xs, ys = zip(*pts)
    return float(np.interp(u, xs, ys))


def _boot_w(u):
    pts = [(-5.3, 1.55), (-3.5, 1.85), (-1.0, 1.95), (2.0, 2.0), (4.4, 1.85), (6.1, 1.5)]
    xs, ys = zip(*pts)
    return float(np.interp(u, xs, ys))


def boot_mesh():
    y0 = 2.95
    nu, nr = 44, 30
    us = np.linspace(-5.35, 6.15, nu)
    verts, uvw = [], []
    for u in us:
        e = min(u + 5.35, 6.15 - u)                       # Abstand zum Ende -> Rundung
        k = math.sqrt(max(0.0, 1 - max(0.0, 1 - e / 0.9) ** 2)) if e < 0.9 else 1.0
        k = max(k, 0.06)
        h = _boot_h(u)
        a = (h - y0) / 2 * (0.55 + 0.45 * k)
        b = _boot_w(u) * k
        yc = y0 + (h - y0) / 2 - (h - y0) / 2 * (1 - (0.55 + 0.45 * k)) * 0.3
        for j in range(nr):
            th = 2 * math.pi * j / nr
            c, s = math.cos(th), math.sin(th)
            ex = 2 / 2.7
            w = b * math.copysign(abs(c) ** ex, c)
            y = yc + a * math.copysign(abs(s) ** ex, s)
            y = max(y, y0)
            verts.append((u, y, w))
            uvw.append((u, y, w))
    tris = list(map(tuple, grid_tris(nu, nr)))
    tris += cap(verts, 0, nr, (us[0], y0 + 2.0, 0.0))
    uvw.append((us[0], y0 + 2.0, 0.0))
    tris += [(t[1], t[0], t[2]) for t in cap(verts, (nu - 1) * nr, nr, (us[-1], y0 + 0.4, 0.0))]
    uvw.append((us[-1], y0 + 0.4, 0.0))
    v = np.array(verts)
    t = np.array(tris, np.int32)
    return Mesh(v, vertex_normals(v, t), t, MAT_IDS["boot"], uvw)


def loft_y(y0, y1, n, fn, mat, nr=18):
    """Röhre entlang y: fn(y) -> (u_center, w_center, half_u, half_w)."""
    verts = []
    for y in np.linspace(y0, y1, n):
        cu, cw, hu, hw = fn(y)
        for j in range(nr):
            th = 2 * math.pi * j / nr
            verts.append((cu + hu * math.cos(th), y, cw + hw * math.sin(th)))
    tris = list(map(tuple, grid_tris(n, nr)))
    tris += cap(verts, (n - 1) * nr, nr, (fn(y1)[0], y1, fn(y1)[1]))
    v = np.array(verts)
    t = np.array(tris, np.int32)
    return Mesh(v, vertex_normals(v, t), t, MAT_IDS[mat], v.copy())


def extrude(profile, w0, w1, mat, smooth_sides=False):
    """Profil (u, y) zwischen w0 und w1 extrudiert (flache Seiten)."""
    P = np.asarray(profile, float)
    n = len(P)
    verts, tris, norms = [], [], []
    # Seitenflächen (eigene Vertices für harte Kanten)
    for i in range(n):
        a, b = P[i], P[(i + 1) % n]
        e = b - a
        nn = np.array([e[1], -e[0], 0.0])
        nn /= np.linalg.norm(nn) + 1e-9
        k = len(verts)
        verts += [(a[0], a[1], w0), (b[0], b[1], w0), (b[0], b[1], w1), (a[0], a[1], w1)]
        norms += [nn] * 4
        tris += [(k, k + 1, k + 2), (k, k + 2, k + 3)]
    # Kappen (Fächer um den Schwerpunkt)
    c = P.mean(0)
    for wv, sgn in ((w1, 1.0), (w0, -1.0)):
        k = len(verts)
        verts += [(p[0], p[1], wv) for p in P] + [(c[0], c[1], wv)]
        norms += [np.array([0, 0, sgn])] * (n + 1)
        for i in range(n):
            tri = (k + i, k + (i + 1) % n, k + n)
            tris.append(tri if sgn > 0 else (tri[1], tri[0], tri[2]))
    v = np.array(verts)
    return Mesh(v, np.array(norms), np.array(tris, np.int32), MAT_IDS[mat], v.copy())


def skate_local():
    parts = [boot_mesh()]
    # Fersenkappe / Achillessehnenschutz (liegt hinten am Bein an)
    parts.append(loft_y(9.4, 11.9, 6, lambda y: (-4.95 - 0.12 * (y - 9.4), 0.0, 0.26, 1.0 - 0.1 * (y - 9.4)),
                        "boot_accent"))
    # Halter: hinterer und vorderer Turm + Schiene
    parts.append(extrude([(-4.75, 2.98), (-2.15, 2.98), (-2.55, 1.25), (-4.25, 1.25)], -0.62, 0.62, "holder"))
    parts.append(extrude([(2.35, 2.98), (5.35, 2.98), (4.95, 1.25), (2.85, 1.25)], -0.62, 0.62, "holder"))
    parts.append(extrude([(-4.45, 1.42), (5.0, 1.42), (4.95, 0.95), (-4.35, 0.95)], -0.36, 0.36, "holder"))
    # Kufe mit Schliff-Radius (~9 ft)
    us = np.linspace(-5.2, 5.5, 24)
    bottom = [(u, (u - 0.3) ** 2 / 216.0) for u in us]
    prof = [(-5.55, 0.55)] + bottom + [(5.85, 0.6), (5.55, 1.08), (-5.2, 1.08)]
    parts.append(extrude(prof, -0.08, 0.08, "steel"))
    return merge(parts)


SKATE = skate_local()


def place(mesh, cx, cy, cz, heading=0.0):
    """Lokal (u, y, w) -> Welt: x = cx + u·cos, z = cz + u·sin + w."""
    th = math.radians(heading)
    c, s = math.cos(th), math.sin(th)
    v = mesh.v
    out = Mesh(np.stack([cx + v[:, 0] * c - v[:, 2] * s, cy + v[:, 1], cz + v[:, 0] * s + v[:, 2] * c], 1),
               np.stack([mesh.n[:, 0] * c - mesh.n[:, 2] * s, mesh.n[:, 1], mesh.n[:, 0] * s + mesh.n[:, 2] * c], 1),
               mesh.t, mesh.m, mesh.uvw)
    return out


# ================================================================= Bein (Stutzen, Knie, Hose)
def tube_along(points, radii, mat_fn, nr=26):
    """Röhre entlang einer Polylinie (Rotation-Minimizing-Frames)."""
    P = np.asarray(points, float)
    n = len(P)
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    ref = np.array([0.0, 0.0, 1.0])
    N0 = np.cross(T[0], ref)
    if np.linalg.norm(N0) < 1e-6:
        N0 = np.cross(T[0], np.array([1.0, 0, 0]))
    N0 /= np.linalg.norm(N0)
    frames = [N0]
    for i in range(1, n):
        nprev = frames[-1]
        nn = nprev - np.dot(nprev, T[i]) * T[i]
        frames.append(nn / np.linalg.norm(nn))
    verts, uvw = [], []
    for i in range(n):
        N = frames[i]
        B = np.cross(T[i], N)
        for j in range(nr):
            th = 2 * math.pi * j / nr
            verts.append(P[i] + radii[i] * (math.cos(th) * N + math.sin(th) * B))
            uvw.append((i / (n - 1), j / nr, 0.0))
    tris = grid_tris(n, nr)
    v = np.array(verts)
    mats = np.array([mat_fn(uvw[t[0]][0]) for t in tris], np.int32)
    return Mesh(v, vertex_normals(v, tris), tris, mats, np.array(uvw))


def ik_knee(hip, ankle, l_thigh, l_shin, fwd):
    d = hip - ankle
    dist = min(np.linalg.norm(d), l_thigh + l_shin - 1e-3)
    dirv = d / (np.linalg.norm(d) + 1e-9)
    a = (l_shin ** 2 - l_thigh ** 2 + dist ** 2) / (2 * dist)
    h = math.sqrt(max(l_shin ** 2 - a ** 2, 0.0))
    perp = fwd - np.dot(fwd, dirv) * dirv
    perp /= np.linalg.norm(perp) + 1e-9
    return ankle + dirv * a + perp * h


def bezier(p0, p1, p2, n):
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t ** 2 * p2


def leg_meshes(ankle, hip, fwd=np.array([1.0, 0, 0])):
    knee = ik_knee(hip, ankle, 18.0, 16.5, fwd)
    sh = bezier(ankle, (ankle + knee) / 2 + fwd * 0.6, knee, 14)          # Schienbein (leicht nach vorn gewölbt)
    th = bezier(knee, (knee + hip) / 2 + fwd * 0.4, hip, 10)
    pts = np.concatenate([sh, th[1:]])
    m = len(sh)
    r = []
    for i in range(len(pts)):
        if i < m:
            q = i / (m - 1)
            r.append(np.interp(q, [0, 0.12, 0.3, 0.75, 0.92, 1.0], [1.75, 2.2, 2.8, 2.95, 3.4, 3.6]))
        else:
            q = (i - m + 1) / (len(pts) - m)
            r.append(np.interp(q, [0, 0.3, 1.0], [3.6, 3.5, 3.7]))
    stripe = lambda s: MAT_IDS["sock_stripe"] if (0.30 < s < 0.335 or 0.355 < s < 0.39) else MAT_IDS["sock"]
    sock = tube_along(pts, r, stripe)
    # Hockeyhose ab etwa 7 Zoll über dem Knie
    pa = knee + (hip - knee) * 0.5
    pts2 = np.concatenate([bezier(pa, (pa + hip) / 2, hip, 8), hip + np.array([[0.0, 8.0, 0.0], [0.0, 30.0, 0.0]])])
    r2 = np.interp(np.linspace(0, 1, 10), [0, 0.04, 0.12, 0.8, 1], [3.55, 5.0, 5.3, 6.0, 6.0])   # Saum schließt ans Bein an
    pants = tube_along(pts2, r2, lambda s: MAT_IDS["pants_stripe"] if 0.25 < s < 0.33 else MAT_IDS["pants"])
    # Saum der Hose schließen
    return [sock, pants]


def torso_mesh(hip_center):
    """Trikot-Unterkante über der Hose (nur der untere Teil ist im Bild)."""
    pts = np.stack([hip_center + np.array([0.0, y, 0.0]) for y in np.linspace(3.0, 40.0, 38)])
    r = np.interp(np.linspace(0, 1, 38), [0, 0.1, 1], [10.5, 10.0, 10.5])
    st = lambda s: MAT_IDS["jersey_stripe"] if (0.035 < s < 0.075 or 0.1 < s < 0.13) else MAT_IDS["jersey"]
    return tube_along(pts, r, st, nr=32)


# ================================================================= Schläger
def stick_mesh(heel, toe, top, blade_h=2.8):
    """Blatt (Heel->Toe, mit Tape) + Schaft (Heel -> Griff)."""
    heel, toe, top = map(lambda a: np.asarray(a, float), (heel, toe, top))
    along = toe - heel
    L = np.linalg.norm(along)
    a = along / L
    up = np.array([0.0, 1.0, 0.0])
    side = np.cross(a, up)
    verts, norms, tris, mats = [], [], [], []
    nseg = 10
    for i in range(nseg + 1):
        s = i / nseg
        bend = 0.9 * s * s                                              # Blattkrümmung
        p = heel + along * s - side * bend
        hgt = blade_h * (1 - 0.25 * s * s)
        for (dy, dw) in ((0.05, -0.13), (hgt, -0.13), (hgt, 0.13), (0.05, 0.13)):
            verts.append(p + up * dy + side * dw)
    ring = 4
    for i in range(nseg):
        for j in range(ring):
            k0, k1 = i * ring + j, i * ring + (j + 1) % ring
            k2, k3 = (i + 1) * ring + j, (i + 1) * ring + (j + 1) % ring
            tris += [(k0, k2, k1), (k1, k2, k3)]
            mats += [MAT_IDS["tape"]] * 2
    v1 = np.array(verts)
    t1 = np.array(tris, np.int32)
    blade = Mesh(v1, vertex_normals(v1, t1), t1, np.array(mats), v1.copy())
    sh0 = heel + up * 1.6 - a * 0.4
    shaft_pts = np.stack([sh0 + (top - sh0) * q for q in np.linspace(0, 1, 6)])
    shaft = tube_along(shaft_pts, [0.62] * 6, lambda s: MAT_IDS["carbon"], nr=8)
    return [blade, shaft]


# ================================================================= Rasterizer
@njit(cache=True)
def _raster(sx, sy, sz, tris, depth, tri_id, b0, b1):
    Hh, Ww = depth.shape
    for t in range(tris.shape[0]):
        i0, i1, i2 = tris[t, 0], tris[t, 1], tris[t, 2]
        z0, z1, z2 = sz[i0], sz[i1], sz[i2]
        if z0 < 1.0 or z1 < 1.0 or z2 < 1.0:
            continue
        x0, y0, x1, y1, x2, y2 = sx[i0], sy[i0], sx[i1], sy[i1], sx[i2], sy[i2]
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if abs(area) < 1e-12:
            continue
        mnx = max(int(math.floor(min(x0, min(x1, x2)))), 0)
        mxx = min(int(math.ceil(max(x0, max(x1, x2)))), Ww - 1)
        mny = max(int(math.floor(min(y0, min(y1, y2)))), 0)
        mxy = min(int(math.ceil(max(y0, max(y1, y2)))), Hh - 1)
        if mnx > mxx or mny > mxy:
            continue
        inv = 1.0 / area
        for py in range(mny, mxy + 1):
            cy = py + 0.5
            for px in range(mnx, mxx + 1):
                cx = px + 0.5
                w0 = ((x1 - cx) * (y2 - cy) - (x2 - cx) * (y1 - cy)) * inv
                w1 = ((x2 - cx) * (y0 - cy) - (x0 - cx) * (y2 - cy)) * inv
                w2 = 1.0 - w0 - w1
                if w0 < 0 or w1 < 0 or w2 < 0:
                    continue
                iz = w0 / z0 + w1 / z1 + w2 / z2
                z = 1.0 / iz
                if z < depth[py, px]:
                    depth[py, px] = z
                    tri_id[py, px] = t
                    b0[py, px] = w0 / z0 * z
                    b1[py, px] = w1 / z1 * z


@njit(cache=True)
def _raster_mask(sx, sy, tris, mask):
    Hh, Ww = mask.shape
    for t in range(tris.shape[0]):
        i0, i1, i2 = tris[t, 0], tris[t, 1], tris[t, 2]
        x0, y0, x1, y1, x2, y2 = sx[i0], sy[i0], sx[i1], sy[i1], sx[i2], sy[i2]
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if abs(area) < 1e-12:
            continue
        mnx = max(int(math.floor(min(x0, min(x1, x2)))), 0)
        mxx = min(int(math.ceil(max(x0, max(x1, x2)))), Ww - 1)
        mny = max(int(math.floor(min(y0, min(y1, y2)))), 0)
        mxy = min(int(math.ceil(max(y0, max(y1, y2)))), Hh - 1)
        inv = 1.0 / area
        for py in range(mny, mxy + 1):
            cy = py + 0.5
            for px in range(mnx, mxx + 1):
                cx = px + 0.5
                w0 = ((x1 - cx) * (y2 - cy) - (x2 - cx) * (y1 - cy)) * inv
                w1 = ((x2 - cx) * (y0 - cy) - (x0 - cx) * (y2 - cy)) * inv
                if w0 < 0 or w1 < 0 or 1.0 - w0 - w1 < 0:
                    continue
                mask[py, px] = 1.0


def project(cam, pts, W, H, ss):
    pos, r, u, f, tanh = cam[0:3], cam[3:6], cam[6:9], cam[9:12], cam[12]
    d = pts - pos
    z = d @ f
    zz = np.maximum(z, 1e-6)
    x = (d @ r) / zz / (tanh * W / H)
    y = (d @ u) / zz / tanh
    return (x + 1) * W * ss / 2, (1 - y) * H * ss / 2, z


def _shade_pattern(mat, uvw):
    """Musterdetails: Schnürung, Ösen, Zierstreifen am Schuh."""
    col = MAT_COL[mat].copy()
    boot = mat == MAT_IDS["boot"]
    if boot.any():
        u, y, w = uvw[boot, 0], uvw[boot, 1], uvw[boot, 2]
        h = np.interp(u, [-5.3, -4.4, -1.6, -0.5, 1.0, 2.4, 4.2, 5.4, 6.1], [9.9, 10.7, 10.8, 9.9, 7.1, 5.9, 5.1, 4.5, 4.0])
        top = (y > h - 0.9) & (u > -0.4) & (u < 2.9) & (np.abs(w) < 1.05)
        lace = top & (((u * 1.5 + w * 1.25) % 1.0 < 0.2) | ((u * 1.5 - w * 1.25) % 1.0 < 0.2)) & (np.abs(w) < 0.8)
        gap = top & ~lace & (np.abs(w) < 0.75)
        eyelet = top & (np.abs(np.abs(w) - 0.92) < 0.1) & ((u * 1.5) % 1.0 < 0.25)
        stripe = (np.abs(y - 4.4) < 0.28) & (u < 4.6) & (np.abs(w) > 1.0)
        side_panel = (u < -0.8) & (y > 6.2) & (y < 9.2) & (np.abs(w) > 1.1)
        c = col[boot]
        c[stripe] = MAT_COL[MAT_IDS["boot_accent"]]
        c[side_panel] = c[side_panel] * 0.6 + np.array([0.09, 0.09, 0.10], np.float32) * 0.4
        c[gap] = np.array([0.55, 0.55, 0.57], np.float32)
        c[lace] = MAT_COL[MAT_IDS["lace"]]
        c[eyelet] = np.array([0.6, 0.62, 0.66], np.float32)
        col[boot] = c
    tape = mat == MAT_IDS["tape"]
    if tape.any():
        q = (uvw[tape, 0] * 1.1 + uvw[tape, 1] * 0.7) % 1.0 < 0.06       # Tape-Wicklung
        c = col[tape]
        c[q] = c[q] * 0.82
        col[tape] = c
    return col


def render(meshes, cam, W, H, campos, ss=2, alpha_by_group=None, extra_planes=None):
    """-> (rgb vormultipliziert, alpha, tiefe) in Ausgabeauflösung, plus Schattenmaske aufs Eis."""
    m = merge(meshes)
    sx, sy, sz = project(cam, m.v, W, H, ss)
    Hs, Ws = H * ss, W * ss
    depth = np.full((Hs, Ws), 1e9, np.float32)
    tid = np.full((Hs, Ws), -1, np.int32)
    b0 = np.zeros((Hs, Ws), np.float32)
    b1 = np.zeros((Hs, Ws), np.float32)
    _raster(sx.astype(np.float64), sy.astype(np.float64), sz.astype(np.float64), m.t, depth, tid, b0, b1)
    cov = tid >= 0
    rgb = np.zeros((Hs, Ws, 3), np.float32)
    alpha = np.zeros((Hs, Ws), np.float32)
    if cov.any():
        t = tid[cov]
        w0, w1 = b0[cov][:, None], b1[cov][:, None]
        w2 = 1 - w0 - w1
        tri = m.t[t]
        P = w0 * m.v[tri[:, 0]] + w1 * m.v[tri[:, 1]] + w2 * m.v[tri[:, 2]]
        N = w0 * m.n[tri[:, 0]] + w1 * m.n[tri[:, 1]] + w2 * m.n[tri[:, 2]]
        N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-9
        Vd = campos - P
        Vd /= np.linalg.norm(Vd, axis=1, keepdims=True)
        flip = (N * Vd).sum(1) < 0
        N[flip] *= -1
        UVW = w0 * m.uvw[tri[:, 0]] + w1 * m.uvw[tri[:, 1]] + w2 * m.uvw[tri[:, 2]]
        mat = m.m[t]
        base = _shade_pattern(mat, UVW)
        ndl = np.clip(N @ LIGHT, 0, 1)[:, None]
        sky = (0.5 + 0.5 * N[:, 1:2])
        bounce = (0.5 - 0.5 * N[:, 1:2])
        # Fuß-Abdunklung (Ambient Occlusion) nahe am Eis
        ao = np.clip(0.55 + P[:, 1:2] / 6.0, 0.55, 1.0)
        diff = base * (1.25 * ndl + 0.55 * sky + 0.45 * bounce) * ao
        Hh = LIGHT + Vd
        Hh /= np.linalg.norm(Hh, axis=1, keepdims=True)
        spec = MAT_SPEC[mat][:, None] * np.clip((N * Hh).sum(1), 0, 1)[:, None] ** MAT_SHINE[mat][:, None]
        rim = 0.18 * (1 - np.clip((N * Vd).sum(1), 0, 1))[:, None] ** 3     # helle Ränder vom Studio-Licht
        col = diff + spec + rim * (0.6 + 0.4 * base)
        a = np.ones(len(t), np.float32)
        if alpha_by_group is not None:
            a = alpha_by_group[m.g[t]]
        rgb[cov] = col * a[:, None]
        alpha[cov] = a
    # transparente Ebene(n), mit Tiefentest gegen die Gitter
    plane_a = np.zeros((Hs, Ws), np.float32)
    if extra_planes:
        for quad, a_pl in extra_planes:
            if a_pl <= 0:
                continue
            qx, qy, qz = project(cam, np.asarray(quad, float), W, H, ss)
            pd = np.full((Hs, Ws), 1e9, np.float32)
            pt = np.full((Hs, Ws), -1, np.int32)
            pb0 = np.zeros((Hs, Ws), np.float32)
            pb1 = np.zeros((Hs, Ws), np.float32)
            _raster(qx, qy, qz, np.array([[0, 1, 2], [0, 2, 3]], np.int32), pd, pt, pb0, pb1)
            vis = (pt >= 0) & (pd < depth)
            plane_a[vis] = np.maximum(plane_a[vis], a_pl)
    # Schatten: Gitter entlang des Lichts aufs Eis projizieren
    sh = m.v - LIGHT[None, :] * (m.v[:, 1:2] / LIGHT[1])
    sh[:, 1] = 0.05
    hx, hy, _ = project(cam, sh, W, H, ss)
    mask = np.zeros((Hs, Ws), np.float32)
    ok = np.ones(len(m.t), bool) if alpha_by_group is None else alpha_by_group[m.g] > 0.5
    _raster_mask(hx.astype(np.float64), hy.astype(np.float64), m.t[ok], mask)

    def down(a):
        return a.reshape(H, ss, W, ss, *a.shape[2:]).mean(axis=(1, 3))

    mask_img = Image.fromarray((down(mask) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(7))
    return down(rgb), down(alpha), np.asarray(mask_img, np.float32) / 255, down(plane_a)
