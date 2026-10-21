"""3D-Krake (Mantel, Augen, 8 Arme mit Saugnäpfen) für mesh3d – fällt aufs Eis und breitet die Arme aus.

octopus_mesh(center_xz, s, wob, heading, scale) -> Liste von M3.Mesh
  s   0 = in der Luft (Arme hängen nach unten zusammen), 1 = flach auf dem Eis ausgebreitet
  wob Nachwippen nach der Landung (0..1)
tip_positions(...) -> Weltpunkte der 8 Armspitzen (für die Nummern 1–8)
"""
import math

import numpy as np

import mesh3d as M3

ARM_N = 22
ARM_LEN = 22.0


def _sphere(center, radii, mat, nu=26, nv=34, w=1.0):
    verts, uvw = [], []
    for i in range(nu):
        th = math.pi * i / (nu - 1)
        for j in range(nv):
            ph = 2 * math.pi * j / nv
            verts.append((center[0] + radii[0] * math.sin(th) * math.cos(ph), center[1] + radii[1] * math.cos(th),
                          center[2] + radii[2] * math.sin(th) * math.sin(ph)))
            uvw.append((i / (nu - 1), j / nv, w))
    v = np.array(verts)
    t = np.array(M3.grid_tris(nu, nv), np.int32)
    return M3.Mesh(v, M3.vertex_normals(v, t), t, M3.MAT_IDS[mat], np.array(uvw))


def _arm_points(k, s, wob, t_phase):
    """Mittellinie eines Arms im lokalen System (Mantel-Unterseite bei y ~ 2.5)."""
    a = k * math.pi / 4 + 0.18 * math.sin(k * 1.7)
    d = np.array([math.cos(a), 0.0, math.sin(a)])
    side = np.array([-d[2], 0.0, d[0]])
    pts = []
    for i in range(ARM_N):
        u = i / (ARM_N - 1)
        # flach: radial aufs Eis, leicht geschwungen, Spitze eingerollt
        r = 3.2 + ARM_LEN * u
        curl = 2.6 * math.sin(u * 2.6 + k) * u + (3.5 * (u - 0.8) / 0.2 if u > 0.8 else 0.0) * (1 if k % 2 else -1)
        flat = d * r + side * curl + np.array([0.0, 0.9 + 1.4 * (1 - u) ** 2, 0.0])
        flat[1] += wob * 1.6 * math.sin(u * 7.0 - t_phase * 18.0 + k) * u
        # hängend: nach unten/außen gebündelt (wie beim Fliegen)
        hang = d * (3.0 + 7.0 * u) + side * 1.5 * math.sin(u * 5 + k) + np.array([0.0, 2.0 - ARM_LEN * 0.95 * u, 0.0])
        q = s ** 0.8
        pts.append(hang * (1 - q) + flat * q)
    return np.array(pts)


def octopus_mesh(center_xz, y0, s, wob=0.0, heading=0.0, scale=1.0, t_phase=0.0):
    c, sn = math.cos(heading), math.sin(heading)
    R = np.array([[c, 0, -sn], [0, 1, 0], [sn, 0, c]])
    off = np.array([center_xz[0], y0, center_xz[1]])
    meshes = []
    squash = 1.0 - 0.18 * wob * math.sin(t_phase * 22.0) if wob > 0 else 1.0
    mantle = _sphere((0.0, 6.5, -1.2), (5.2, 6.4 * squash, 5.8), "octopus", w=1.0)
    head = _sphere((0.0, 2.6, 0.6), (5.8, 3.2, 5.6), "octopus", w=1.0)
    meshes += [mantle, head]
    for sx in (-1, 1):
        meshes.append(_sphere((sx * 2.6, 4.4, 3.9), (1.25, 1.25, 1.25), "eye_white", 12, 16))
        meshes.append(_sphere((sx * 2.7, 4.4, 4.95), (0.5, 0.5, 0.35), "eye_black", 8, 12))
    for k in range(8):
        pts = _arm_points(k, s, wob, t_phase)
        radii = [1.55 * (1 - 0.85 * (i / (ARM_N - 1))) + 0.18 for i in range(ARM_N)]
        arm = M3.tube_along(pts, radii, lambda u: M3.MAT_IDS["octopus"], nr=14)
        arm.uvw[:, 2] = 0.0
        meshes.append(arm)
    out = []
    for m in meshes:
        v = (m.v * scale) @ R.T + off
        n = m.n @ R.T
        out.append(M3.Mesh(v, n, m.t, m.m, m.uvw))
    return out


def tip_positions(center_xz, y0, s, wob=0.0, heading=0.0, scale=1.0, t_phase=0.0):
    c, sn = math.cos(heading), math.sin(heading)
    R = np.array([[c, 0, -sn], [0, 1, 0], [sn, 0, c]])
    off = np.array([center_xz[0], y0, center_xz[1]])
    tips = []
    for k in range(8):
        p = _arm_points(k, s, wob, t_phase)[-3]
        tips.append((p * scale) @ R.T + off)
    return np.array(tips)
