"""3D-Hüte für mesh3d (reel35): Basecaps (Krone + Schirm + Knopf) und Wollmützen (mit Bommel).

hat_local(kind, col) -> Liste von M3.Mesh im lokalen System (Krempe/Unterkante bei y = 0, Schirm zeigt nach +x)
place_hat(local, pos, R) -> Meshes in Weltkoordinaten (R = 3x3-Rotation)
Maße in Zoll (Cap: Krone ~7,6" breit, 4" hoch, Schirm ~3").
"""
import math

import numpy as np

import mesh3d as M3

COLORS = ["cap_red", "cap_navy", "cap_black", "cap_white", "cap_grey", "cap_orange", "cap_blue"]


def _dome(rx, ry, rz, mat, nu=10, nv=22, y0=0.0, squash_top=1.0):
    """Halbkugel (offen unten), Pol oben."""
    verts = []
    for i in range(nu):
        th = (math.pi / 2) * i / (nu - 1)                # 0 = Pol, pi/2 = Rand
        for j in range(nv):
            ph = 2 * math.pi * j / nv
            verts.append((rx * math.sin(th) * math.cos(ph), y0 + ry * math.cos(th) ** squash_top,
                          rz * math.sin(th) * math.sin(ph)))
    v = np.array(verts)
    t = np.array(M3.grid_tris(nu, nv), np.int32)
    return M3.Mesh(v, M3.vertex_normals(v, t), t, M3.MAT_IDS[mat], v.copy())


def _brim(mat, r_in=3.7, length=3.1, half_w=3.3, curve=0.55, thick=0.18):
    """Gebogener Schirm vorn (+x): Ober- und Unterseite."""
    nu, nv = 6, 13
    top, bot = [], []
    for i in range(nu):
        u = i / (nu - 1)
        for j in range(nv):
            w = (j / (nv - 1)) * 2 - 1
            x = r_in * math.sqrt(max(1 - (w * half_w / (r_in + 0.4)) ** 2, 0.0)) * (1 - u) + (r_in + length) * u
            x *= 1 - 0.18 * w * w * u
            z = w * half_w * (1 + 0.15 * u)
            y = 0.3 - curve * w * w - 0.35 * u
            top.append((x, y + thick, z))
            bot.append((x, y, z))
    out = []
    for pts, mat_ in ((top, mat), (bot, "cap_under")):
        v = np.array(pts)
        t = np.array(M3.grid_tris(nu, nv, wrap=False), np.int32)
        out.append(M3.Mesh(v, M3.vertex_normals(v, t), t, M3.MAT_IDS[mat_], v.copy()))
    return out


def _ball(c, r, mat, n=8):
    verts = []
    for i in range(n):
        th = math.pi * i / (n - 1)
        for j in range(n + 2):
            ph = 2 * math.pi * j / (n + 2)
            verts.append((c[0] + r * math.sin(th) * math.cos(ph), c[1] + r * math.cos(th),
                          c[2] + r * math.sin(th) * math.sin(ph)))
    v = np.array(verts)
    t = np.array(M3.grid_tris(n, n + 2), np.int32)
    return M3.Mesh(v, M3.vertex_normals(v, t), t, M3.MAT_IDS[mat], v.copy())


def hat_local(kind, col, col2="cap_white"):
    if kind == "cap":
        return [_dome(3.8, 4.0, 3.6, col, squash_top=0.8)] + _brim(col) + [_ball((0, 3.95, 0), 0.38, col)]
    # Wollmütze: höhere Kuppel, Umschlag in Zweitfarbe, Bommel
    return [_dome(3.7, 5.2, 3.7, col, y0=1.4, squash_top=0.9),
            M3.loft_y(0.0, 1.5, 3, lambda y: (0.0, 0.0, 3.95, 3.95), col2, nr=22),
            _ball((0, 6.9, 0), 1.25, col2)]


def place_hat(local, pos, R):
    out = []
    for m in local:
        v = m.v @ R.T + pos
        n = m.n @ R.T
        out.append(M3.Mesh(v, n, m.t, m.m, m.uvw))
    return out


def rot(axis, ang):
    a = np.asarray(axis, float)
    a = a / (np.linalg.norm(a) + 1e-12)
    x, y, z = a
    c, s = math.cos(ang), math.sin(ang)
    C = 1 - c
    return np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                     [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                     [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])
