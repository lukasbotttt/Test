"""MARLODEEE hype video - 3D scene layer (numba SDF raymarcher, no text).

    import marlo_scene as M
    img = M.render(t)                  # float32 (1920, 1080, 3) linear HDR RGB, t in seconds (frame i -> i / M.FPS)
    img = M.render(t, 540, 960)        # fast preview (same framing)
    M.kick_env(t)                      # 0..1 kick pulse, exactly 1.0 on every beat start (0 in the 6.0-6.4 s gap)

Pure function of t (no hidden state, deterministic, independent of call order and thread count).
Constants: FRAMES = 480, FPS = 30, DUR = 16.0, BEAT = 0.4 s (12 frames), BAR = 1.6 s (48 frames), 150 BPM.

Look: near-black base (#05060A), mirror-black floor with Fresnel reflections, black glass / chrome / rubber-puck /
glowing orb SDF objects with neon rim light in the palette (lime #C8FF00, magenta #FF2A8A, violet #7B3CFF), elliptical
neon ring tunnel behind the scene, lasers + a hot-spot beam, floor shockwave rings, mirrored floor grid.

Timeline (seconds): 0-3.2 intro (3 heroes hop, every contact exactly on a beat, frame 0 = contact squash);
3.2-6.0 build (drop-in spawns land on 3.2/4.0/4.8/5.6 s, ring tunnel flies in, orbit accelerates, strobes on claps
3.6/4.4/5.2); 6.0-6.4 gap (everything hangs, camera pulls back, single hot spot); 6.4 drop (all objects slam down
on frame 192, shockwave, flash, camera kick + shake), groove until 12.8 (bars 7-8 add more beams); 12.8-16.0 outro
(extras fly off on beats, heroes return to their intro positions, last frame leads straight into frame 0).

Performance (4 cores, no other load): ~0.8 s/frame at 1080x1920 (max ~1.6 s), ~0.25 s/frame at 540x960.
The module is parallel (numba prange); set NUMBA_NUM_THREADS=1 per process when running several processes.
"""
import math

import numpy as np
from numba import njit, prange

FRAMES = 480
FPS = 30
DUR = 16.0
BEAT = 0.4
BAR = 1.6
EPS_T = 1e-7

# ----------------------------------------------------------------------------- palette (linear)
LIME = (0.578, 1.0, 0.0)
MAG = (1.0, 0.0232, 0.2541)
VIO = (0.198, 0.0452, 1.0)
WHITE = (1.0, 1.0, 1.0)

# ----------------------------------------------------------------------------- ENV parameter slots
E_BG = 0
E_HORIZ = 1
E_BOX0 = 2          # 2..7 : six soft boxes
E_FLASH = 8
E_RING_AMT = 9
E_RING_S = 10
E_RING_SP = 11
E_RING_RX = 12
E_RING_RY = 13
E_RING_YC = 14
E_RING_PULSE = 15
E_RING_ZLIM = 16
E_RING_W = 17
E_RING_INT = 18
E_LASER = 19
E_SPOT = 20
E_GRID = 21
E_COS = 22
E_SIN = 23
E_KICK = 24
E_STROBE = 25
E_FRAME = 26
E_F0 = 27
E_SPOT_R = 28
E_DIM = 29
E_CLAP = 30
E_NR = 31           # number of rings
E_RZ0 = 32          # 32..47 : ring plane z
E_RF0 = 48          # 48..63 : ring fade (near * far * reveal)
E_NSLOTS = 64

NBOX = 6

# ----------------------------------------------------------------------------- soft boxes (world directions)


def _unit(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


def _make_boxes():
    # center dir, half width (tangent units), half height, color
    defs = [
        # back-left magenta tall strip
        ((-0.85, 0.30, -0.55), 0.10, 0.75, MAG),
        # back-right lime tall strip
        ((0.85, 0.30, -0.55), 0.10, 0.75, LIME),
        # overhead big soft box (cool white)
        ((0.0, 1.0, -0.15), 0.70, 0.55, (0.85, 0.9, 1.0)),
        # front-left violet strip
        ((-0.90, 0.22, 0.45), 0.12, 0.60, VIO),
        # front-right white strip
        ((0.85, 0.28, 0.55), 0.10, 0.60, (1.0, 0.97, 0.95)),
        # back low wide glow (behind the scene)
        ((0.0, 0.18, -1.0), 1.10, 0.18, VIO),
    ]
    B = np.zeros((NBOX, 15))
    for k, (c, wu, wv, col) in enumerate(defs):
        c = _unit(c)
        up = np.array([0.0, 1.0, 0.0])
        if abs(c[1]) > 0.95:
            up = np.array([0.0, 0.0, -1.0])
        u = _unit(np.cross(up, c))
        v = _unit(np.cross(c, u))
        B[k, 0:3] = c
        B[k, 3:6] = u
        B[k, 6:9] = v
        B[k, 9] = wu
        B[k, 10] = wv
        B[k, 11:14] = col
    return B


BOXES = _make_boxes()

# ----------------------------------------------------------------------------- numba kernel


@njit(cache=True, fastmath=True)
def sdf_one(px, py, pz, OB, i):
    ux = (px - OB[i, 0]) * OB[i, 3]
    uy = (py - OB[i, 1]) * OB[i, 4]
    uz = (pz - OB[i, 2]) * OB[i, 5]
    qx = OB[i, 6] * ux + OB[i, 7] * uy + OB[i, 8] * uz
    qy = OB[i, 9] * ux + OB[i, 10] * uy + OB[i, 11] * uz
    qz = OB[i, 12] * ux + OB[i, 13] * uy + OB[i, 14] * uz
    ty = int(OB[i, 15])
    if ty == 0:
        d = math.sqrt(qx * qx + qy * qy + qz * qz) - OB[i, 16]
    elif ty == 1:
        a = OB[i, 16] - OB[i, 17]
        ax = abs(qx) - a
        ay = abs(qy) - a
        az = abs(qz) - a
        mx = max(ax, 0.0)
        my = max(ay, 0.0)
        mz = max(az, 0.0)
        d = math.sqrt(mx * mx + my * my + mz * mz) + min(max(ax, max(ay, az)), 0.0) - OB[i, 17]
    elif ty == 2:
        rr = OB[i, 18]
        l = math.sqrt(qx * qx + qz * qz) - (OB[i, 16] - rr)
        v = abs(qy) - (OB[i, 17] - rr)
        ml = max(l, 0.0)
        mv = max(v, 0.0)
        d = min(max(l, v), 0.0) + math.sqrt(ml * ml + mv * mv) - rr
    elif ty == 3:
        l = math.sqrt(qx * qx + qz * qz) - OB[i, 16]
        d = math.sqrt(l * l + qy * qy) - OB[i, 17]
    else:
        hl = OB[i, 16]
        yy = min(max(qy, -hl), hl)
        d = math.sqrt(qx * qx + (qy - yy) * (qy - yy) + qz * qz) - OB[i, 17]
    return d * OB[i, 22]


@njit(cache=True, fastmath=True)
def obj_normal(px, py, pz, OB, i):
    e = 0.0012
    d0 = sdf_one(px + e, py - e, pz - e, OB, i)
    d1 = sdf_one(px - e, py - e, pz + e, OB, i)
    d2 = sdf_one(px - e, py + e, pz - e, OB, i)
    d3 = sdf_one(px + e, py + e, pz + e, OB, i)
    nx = d0 - d1 - d2 + d3
    ny = -d0 - d1 + d2 + d3
    nz = -d0 + d1 - d2 + d3
    l = math.sqrt(nx * nx + ny * ny + nz * nz) + 1e-12
    return nx / l, ny / l, nz / l


@njit(cache=True, fastmath=True)
def trace_objs(ox, oy, oz, dx, dy, dz, tmax, OB, n, lst, t0s, t1s, pixang):
    cnt = 0
    tmin = 1e30
    tend = -1.0
    for i in range(n):
        if OB[i, 23] < 0.5:
            continue
        rx = ox - OB[i, 0]
        ry = oy - OB[i, 1]
        rz = oz - OB[i, 2]
        b = rx * dx + ry * dy + rz * dz
        c = rx * rx + ry * ry + rz * rz - OB[i, 21] * OB[i, 21]
        disc = b * b - c
        if disc > 0.0:
            s = math.sqrt(disc)
            ta = -b - s
            tb = -b + s
            if tb > 0.0 and ta < tmax:
                if ta < 0.0:
                    ta = 0.0
                lst[cnt] = i
                t0s[cnt] = ta
                t1s[cnt] = tb
                cnt += 1
                if ta < tmin:
                    tmin = ta
                if tb > tend:
                    tend = tb
    if cnt == 0:
        return -1.0, -1
    if tend > tmax:
        tend = tmax
    t = tmin
    for step in range(80):
        px = ox + dx * t
        py = oy + dy * t
        pz = oz + dz * t
        dm = 1e30
        im = -1
        for k in range(cnt):
            d = sdf_one(px, py, pz, OB, lst[k])
            if d < dm:
                dm = d
                im = lst[k]
        eps = max(1.5e-4, 0.3 * t * pixang)
        if dm < eps:
            return t, im
        t += dm
        if t > tend:
            break
    return -1.0, -1


@njit(cache=True, fastmath=True)
def env_col(dx, dy, dz, rough, ENV, refl):
    """refl=0: what the camera sees behind the scene (near-black + soft glow at the tunnel vanishing point).
    refl=1: what mirrors/glass reflect: the same backdrop (so the mirror floor continues it seamlessly) plus
    a dim sky gradient and the soft boxes (strips)."""
    bg = ENV[E_BG]
    hz = 1.0 / (1.0 + (dy / 0.05) * (dy / 0.05))
    hb = ENV[E_HORIZ] * hz
    cd = -dz
    q = (1.0 - cd) / 0.035
    gl = ENV[E_HORIZ] * 0.30 / (1.0 + q * q)
    r = 0.0016 + gl * 0.55 + hb * 0.55
    g = 0.0018 + gl * 0.10 + hb * 0.10
    b = 0.0035 + gl * 1.0 + hb * 1.0
    if refl < 0.5:
        return r, g, b
    up = max(dy, 0.0)
    sky = (0.012 + 0.07 * up) * bg * 0.3
    r += sky * 0.5
    g += sky * 0.45
    b += sky * 1.0
    soft = 0.035 + 0.55 * rough
    for k in range(NBOX):
        cdk = dx * BOXES[k, 0] + dy * BOXES[k, 1] + dz * BOXES[k, 2]
        if cdk < 0.2:
            continue
        a = (dx * BOXES[k, 3] + dy * BOXES[k, 4] + dz * BOXES[k, 5]) / cdk
        bb = (dx * BOXES[k, 6] + dy * BOXES[k, 7] + dz * BOXES[k, 8]) / cdk
        mx = (BOXES[k, 9] - abs(a)) / soft + 0.5
        my = (BOXES[k, 10] - abs(bb)) / soft + 0.5
        if mx <= 0.0 or my <= 0.0:
            continue
        mx = min(mx, 1.0)
        my = min(my, 1.0)
        mx = mx * mx * (3.0 - 2.0 * mx)
        my = my * my * (3.0 - 2.0 * my)
        I = ENV[E_BOX0 + k] * mx * my / (1.0 + 3.0 * rough)
        r += I * BOXES[k, 11]
        g += I * BOXES[k, 12]
        b += I * BOXES[k, 13]
    return r, g, b


@njit(cache=True, fastmath=True)
def pal3(k):
    c = k % 3
    if c == 0:
        return 0.578, 1.0, 0.0
    elif c == 1:
        return 1.0, 0.0232, 0.2541
    return 0.198, 0.0452, 1.0


@njit(cache=True, fastmath=True)
def volume(ox, oy, oz, dx, dy, dz, tmax, ENV, LS, nl, pixang):
    """Additive emissive volume: ring tunnel + lasers/spot shafts, up to distance tmax."""
    r = 0.0
    g = 0.0
    b = 0.0
    # --- ring tunnel (planes z = z_k, elliptical rings; z and fades precomputed per frame)
    amt = ENV[E_RING_AMT]
    if amt > 0.002 and dz < -1e-4:
        nr = int(ENV[E_NR])
        rx0 = ENV[E_RING_RX]
        ry0 = ENV[E_RING_RY]
        yc = ENV[E_RING_YC]
        pulse = ENV[E_RING_PULSE]
        w0 = ENV[E_RING_W]
        inten = ENV[E_RING_INT] * amt
        sc = 1.0 + 0.06 * pulse
        rx = rx0 * sc
        ry = ry0 * sc
        irx = 1.0 / rx
        iry = 1.0 / ry
        for k in range(nr):
            fk = ENV[E_RF0 + k]
            if fk <= 0.0:
                continue
            zk = ENV[E_RZ0 + k]
            t = (zk - oz) / dz
            if t <= 0.0 or t >= tmax:
                continue
            px = ox + t * dx
            py = oy + t * dy
            ex = px * irx
            ey = (py - yc) * iry
            e2 = ex * ex + ey * ey
            if e2 < 0.30 or e2 > 2.1:
                continue
            e = math.sqrt(e2)
            gr = math.sqrt(ex * ex * irx * irx + ey * ey * iry * iry) / e
            dist = (e - 1.0) / gr
            w = math.sqrt(w0 * w0 + (0.9 * t * pixang) * (0.9 * t * pixang))
            q = dist / w
            prof = 1.0 / ((1.0 + q * q) * (1.0 + q * q))
            q2 = dist / (7.0 * w + 0.15)
            win = 1.0 - (dist * dist) * (1.0 / 3.61)
            if win < 0.0:
                win = 0.0
            halo = 0.10 / (1.0 + q2 * q2) * win * win
            val = (prof + halo) * (w0 / w) * inten * fk
            cr, cg, cb = pal3(k)
            r += val * cr
            g += val * cg
            b += val * cb
    # --- laser lines
    lam = 1.0
    if nl > 0:
        for k in range(nl):
            ax = LS[k, 0]
            ay = LS[k, 1]
            az = LS[k, 2]
            ex = LS[k, 3]
            ey = LS[k, 4]
            ez = LS[k, 5]
            wx = ox - ax
            wy = oy - ay
            wz = oz - az
            bdot = dx * ex + dy * ey + dz * ez
            den = 1.0 - bdot * bdot
            if den < 1e-5:
                continue
            dd = dx * wx + dy * wy + dz * wz
            ee = ex * wx + ey * wy + ez * wz
            t = (bdot * ee - dd) / den
            s = (ee - bdot * dd) / den
            if t <= 0.0 or t >= tmax or s < 0.0 or s > LS[k, 11]:
                continue
            cx = wx + t * dx - s * ex
            cy = wy + t * dy - s * ey
            cz = wz + t * dz - s * ez
            d2 = cx * cx + cy * cy + cz * cz
            wd = LS[k, 6] * (1.0 + 0.05 * s) + 0.5 * t * pixang
            q = d2 / (wd * wd)
            val = LS[k, 7] * lam / ((1.0 + q) * (1.0 + q)) * (LS[k, 6] / wd) / (1.0 + 0.02 * t)
            fs = 1.0 - s / LS[k, 11]
            val *= fs
            r += val * LS[k, 8]
            g += val * LS[k, 9]
            b += val * LS[k, 10]
    return r, g, b


@njit(cache=True, fastmath=True)
def floor_emit(px, pz, tdist, cosv, OB, n, EV, nev, ENV, pixang):
    r = 0.0
    g = 0.0
    b = 0.0
    # underglow of objects
    for i in range(n):
        if OB[i, 23] < 0.5:
            continue
        ddx = px - OB[i, 0]
        ddz = pz - OB[i, 2]
        s = OB[i, 21] * 1.05
        q = (ddx * ddx + ddz * ddz) / (s * s)
        hb = OB[i, 31]
        a = OB[i, 27] * 0.45 / ((1.0 + q) * (1.0 + q)) / (1.0 + 1.6 * hb * hb)
        r += a * OB[i, 24]
        g += a * OB[i, 25]
        b += a * OB[i, 26]
    # shock rings and contact flashes
    for e in range(nev):
        ddx = px - EV[e, 0]
        ddz = pz - EV[e, 1]
        d = math.sqrt(ddx * ddx + ddz * ddz)
        u = (d - EV[e, 2]) / EV[e, 3]
        q = 1.0 + u * u
        a = EV[e, 4] * (0.8 / (q * q * q) + 0.05 / (1.0 + 0.04 * u * u))
        f = d / EV[e, 6]
        a += EV[e, 5] / ((1.0 + f * f) * (1.0 + f * f))
        r += a * EV[e, 7]
        g += a * EV[e, 8]
        b += a * EV[e, 9]
    # grid (rotates with the formation)
    ga = ENV[E_GRID]
    if ga > 0.002:
        c = ENV[E_COS]
        s = ENV[E_SIN]
        gx = c * px + s * pz
        gz = -s * px + c * pz
        sp = 1.2
        foot = tdist * pixang / max(cosv, 0.04)
        w = max(0.012, 0.8 * foot)
        fx = abs(gx / sp - math.floor(gx / sp + 0.5)) * sp
        fz = abs(gz / sp - math.floor(gz / sp + 0.5)) * sp
        qx = fx / w
        qz = fz / w
        lx = 1.0 / (1.0 + qx * qx)
        lz = 1.0 / (1.0 + qz * qz)
        att = min(1.0, max(0.0, 1.0 - foot / (0.5 * sp) * 1.3)) / (1.0 + 0.05 * tdist)
        v = (lx + lz) * min(1.0, 0.012 / w) * ga * att
        r += v * 0.198 * 0.9
        g += v * 0.0452 * 0.9
        b += v * 0.9
    # spot pool
    sa = ENV[E_SPOT]
    if sa > 0.002:
        q = (px * px + pz * pz) / (ENV[E_SPOT_R] * ENV[E_SPOT_R])
        v = sa * 0.35 / ((1.0 + q) * (1.0 + q))
        r += v
        g += v * 0.9
        b += v * 0.8
    return r, g, b


@njit(cache=True, fastmath=True)
def irradiance(nx, ny, nz, ENV):
    """Cheap diffuse light from the soft boxes (cosine weighted, area weighted) + faint ambient."""
    r = 0.004
    g = 0.004
    b = 0.008
    for k in range(NBOX):
        c = nx * BOXES[k, 0] + ny * BOXES[k, 1] + nz * BOXES[k, 2]
        if c <= 0.0:
            continue
        w = c * min(1.0, BOXES[k, 9] * BOXES[k, 10] * 2.0) * ENV[E_BOX0 + k] * 0.35
        r += w * BOXES[k, 11]
        g += w * BOXES[k, 12]
        b += w * BOXES[k, 13]
    return r, g, b


@njit(cache=True, fastmath=True)
def shade_obj(px, py, pz, nx, ny, nz, dx, dy, dz, i, rr, rg, rb, OB, ENV):
    """Shade a surface point given reflected radiance (rr,rg,rb)."""
    mat = int(OB[i, 20])
    ndv = -(nx * dx + ny * dy + nz * dz)
    if ndv < 0.0:
        ndv = 0.0
    om = 1.0 - ndv
    om2 = om * om
    f5 = om2 * om2 * om
    kick = ENV[E_KICK]
    cr = OB[i, 24]
    cg = OB[i, 25]
    cb = OB[i, 26]
    rim = om2 * om2 * om2 * (0.8 + 1.6 * kick) * ENV[E_DIM]
    if mat == 0:  # chrome
        F = 0.80 + 0.20 * f5
        r = F * rr + rim * cr * 0.5
        g = F * rg + rim * cg * 0.5
        b = F * rb + rim * cb * 0.5
    elif mat == 1:  # black glass
        F = 0.08 + 0.92 * f5
        ir, ig, ib = irradiance(nx, ny, nz, ENV)
        r = F * rr + (1.0 - F) * 0.012 * ir
        g = F * rg + (1.0 - F) * 0.012 * ig
        b = F * rb + (1.0 - F) * 0.012 * ib
        r += rim * cr * 0.8
        g += rim * cg * 0.8
        b += rim * cb * 0.8
        gl = (0.2 + 0.8 * om2) * 0.04 * (0.4 + kick)
        r += gl * cr
        g += gl * cg
        b += gl * cb
    elif mat == 2:  # rubber puck
        F = 0.06 + 0.30 * f5
        ir, ig, ib = irradiance(nx, ny, nz, ENV)
        r = F * rr + 0.07 * ir
        g = F * rg + 0.07 * ig
        b = F * rb + 0.07 * ib
        r += rim * cr * 0.28
        g += rim * cg * 0.28
        b += rim * cb * 0.28
    else:  # glowing orb
        F = 0.10 + 0.90 * f5
        em = 1.3 + 2.2 * kick
        core = 0.30 + 0.70 * ndv
        r = F * rr + em * core * cr
        g = F * rg + em * core * cg
        b = F * rb + em * core * cb
        r += rim * cr
        g += rim * cg
        b += rim * cb
    if ny < 0.0:
        hb = OB[i, 31]
        ug = -ny * OB[i, 27] * 0.30 / (1.0 + 0.8 * hb)
        r += ug * cr
        g += ug * cg
        b += ug * cb
    return r, g, b


@njit(cache=True, fastmath=True)
def radiance_sec(ox, oy, oz, dx, dy, dz, floor_mode, OB, n, EV, nev, LS, nl, ENV, lst, t0s, t1s, pixang):
    """Radiance along a secondary ray: objects (env-lit), floor (emission), environment, volume."""
    t, i = trace_objs(ox, oy, oz, dx, dy, dz, 1e9, OB, n, lst, t0s, t1s, pixang)
    tf = 1e30
    if dy < -1e-5 and oy > 0.0:
        tf = -oy / dy
    r = 0.0
    g = 0.0
    b = 0.0
    thit = 1e9
    oid = 0
    if i >= 0 and t < tf:
        px = ox + dx * t
        py = oy + dy * t
        pz = oz + dz * t
        nx, ny, nz = obj_normal(px, py, pz, OB, i)
        rdn = dx * nx + dy * ny + dz * nz
        rx = dx - 2.0 * rdn * nx
        ry = dy - 2.0 * rdn * ny
        rz = dz - 2.0 * rdn * nz
        mat = int(OB[i, 20])
        rough = 0.0
        if mat == 2:
            rough = 0.40
        er, eg, eb = env_col(rx, ry, rz, rough, ENV, 1.0)
        if ry < 0.0:
            tt = -py / ry
            fr, fg, fb = floor_emit(px + rx * tt, pz + rz * tt, tt, -ry, OB, n, EV, nev, ENV, pixang)
            er = er * 0.15 + fr
            eg = eg * 0.15 + fg
            eb = eb * 0.15 + fb
        r, g, b = shade_obj(px, py, pz, nx, ny, nz, dx, dy, dz, i, er, eg, eb, OB, ENV)
        if floor_mode:
            k = 1.0 / (1.0 + 0.30 * t)
            r *= k
            g *= k
            b *= k
        thit = t
        oid = i + 1
    elif tf < 1e29:
        px = ox + dx * tf
        pz = oz + dz * tf
        fr, fg, fb = floor_emit(px, pz, tf, -dy, OB, n, EV, nev, ENV, pixang)
        er, eg, eb = env_col(dx, -dy, dz, 0.0, ENV, 1.0)
        om = 1.0 + dy
        F = 0.35 + 0.65 * om * om * om * om * om
        r = fr + F * er * 0.7
        g = fg + F * eg * 0.7
        b = fb + F * eb * 0.7
        thit = tf
        oid = 15
    else:
        r, g, b = env_col(dx, dy, dz, 0.0, ENV, 1.0)
    vr, vg, vb = volume(ox, oy, oz, dx, dy, dz, thit, ENV, LS, nl, pixang)
    return r + vr, g + vg, b + vb, oid


@njit(cache=True, fastmath=True)
def shade_pixel(fx, fy, W, H, CAM, OB, n, EV, nev, LS, nl, ENV, lst, t0s, t1s):
    pixang = 1.0 / CAM[12]
    u = fx - 0.5 * W - CAM[13]
    v = 0.5 * H - fy
    dx = CAM[9] * CAM[12] + CAM[3] * u + CAM[6] * v
    dy = CAM[10] * CAM[12] + CAM[4] * u + CAM[7] * v
    dz = CAM[11] * CAM[12] + CAM[5] * u + CAM[8] * v
    l = math.sqrt(dx * dx + dy * dy + dz * dz)
    dx /= l
    dy /= l
    dz /= l
    ox = CAM[0]
    oy = CAM[1]
    oz = CAM[2]
    t, i = trace_objs(ox, oy, oz, dx, dy, dz, 1e9, OB, n, lst, t0s, t1s, pixang)
    tf = 1e30
    if dy < -1e-5:
        tf = -oy / dy
    r = 0.0
    g = 0.0
    b = 0.0
    idv = 0
    thit = 1e9
    if i >= 0 and t < tf:
        px = ox + dx * t
        py = oy + dy * t
        pz = oz + dz * t
        nx, ny, nz = obj_normal(px, py, pz, OB, i)
        rdn = dx * nx + dy * ny + dz * nz
        rx = dx - 2.0 * rdn * nx
        ry = dy - 2.0 * rdn * ny
        rz = dz - 2.0 * rdn * nz
        mat = int(OB[i, 20])
        if mat == 2:
            er, eg, eb = env_col(rx, ry, rz, 0.40, ENV, 1.0)
            if ry < 0.0:
                tt = -py / ry
                fr, fg, fb = floor_emit(px + rx * tt, pz + rz * tt, tt, -ry, OB, n, EV, nev, ENV, pixang)
                er = er * 0.15 + fr
                eg = eg * 0.15 + fg
                eb = eb * 0.15 + fb
            sid = 0
        else:
            er, eg, eb, sid = radiance_sec(px + nx * 0.01, py + ny * 0.01, pz + nz * 0.01, rx, ry, rz, False,
                                           OB, n, EV, nev, LS, nl, ENV, lst, t0s, t1s, pixang)
        r, g, b = shade_obj(px, py, pz, nx, ny, nz, dx, dy, dz, i, er, eg, eb, OB, ENV)
        idv = (i + 1) + 32 * sid
        thit = t
    elif tf < 1e29:
        px = ox + dx * tf
        pz = oz + dz * tf
        cosv = -dy
        om = 1.0 - cosv
        om2 = om * om
        F = ENV[E_F0] + (1.0 - ENV[E_F0]) * om2 * om2 * om
        F *= 1.0 / (1.0 + tf * 0.012)
        er, eg, eb, sid = radiance_sec(px, 1e-4, pz, dx, -dy, dz, True, OB, n, EV, nev, LS, nl, ENV, lst, t0s,
                                       t1s, pixang)
        fr, fg, fb = floor_emit(px, pz, tf, cosv, OB, n, EV, nev, ENV, pixang)
        r = F * er * 0.95 + fr
        g = F * eg * 0.97 + fg
        b = F * eb + fb
        idv = 31 + 32 * sid
        thit = tf
    else:
        r, g, b = env_col(dx, dy, dz, 0.0, ENV, 0.0)
        idv = 0
    vr, vg, vb = volume(ox, oy, oz, dx, dy, dz, thit, ENV, LS, nl, pixang)
    r += vr
    g += vg
    b += vb
    return r, g, b, idv


@njit(cache=True, fastmath=True)
def hash_u(x, y, f):
    h = (x * 374761393 + y * 668265263 + f * 2147483647) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h = h ^ (h >> 16)
    return (h & 0xFFFFFF) / 16777216.0


@njit(cache=True, fastmath=True)
def lum3(r, g, b):
    return 0.3 * r + 0.55 * g + 0.15 * b


@njit(cache=True, fastmath=True, parallel=True)
def render_kernel(W, H, CAM, OB, n, EV, nev, LS, nl, ENV, img, out, ids, dither, aa):
    # pass 1: one sample per pixel (+ object/reflection id buffer for edge detection)
    for j in prange(H):
        lst = np.empty(16, np.int64)
        t0s = np.empty(16, np.float64)
        t1s = np.empty(16, np.float64)
        for i in range(W):
            r, g, b, idv = shade_pixel(i + 0.5, j + 0.5, W, H, CAM, OB, n, EV, nev, LS, nl, ENV, lst, t0s, t1s)
            img[j, i, 0] = r
            img[j, i, 1] = g
            img[j, i, 2] = b
            ids[j, i] = idv
    # pass 2: adaptive supersampling on id edges and high-contrast pixels (reads img, writes out: deterministic)
    for j in prange(H):
        lst = np.empty(16, np.int64)
        t0s = np.empty(16, np.float64)
        t1s = np.empty(16, np.float64)
        for i in range(W):
            r0 = img[j, i, 0]
            g0 = img[j, i, 1]
            b0 = img[j, i, 2]
            out[j, i, 0] = r0
            out[j, i, 1] = g0
            out[j, i, 2] = b0
            if not aa:
                continue
            c = ids[j, i]
            l0 = lum3(r0, g0, b0)
            edge = 0
            jc = np.int64(j)
            for k in range(4):
                ii = np.int64(i)
                jj = jc
                if k == 0:
                    ii = ii - 1
                elif k == 1:
                    ii = ii + 1
                elif k == 2:
                    jj = jj - 1
                else:
                    jj = jj + 1
                if ii < 0 or ii >= W or jj < 0 or jj >= H:
                    continue
                if ids[jj, ii] != c:
                    edge = 2
                    break
                l1 = lum3(img[jj, ii, 0], img[jj, ii, 1], img[jj, ii, 2])
                if abs(l0 - l1) > 0.45 * (0.08 + max(l0, l1)):
                    edge = 1
            if edge > 0:
                ns = 4
                if edge == 2:
                    ns = 6
                sr = r0
                sg = g0
                sb = b0
                for k in range(ns):
                    if k == 0:
                        ox = -0.375
                        oy = -0.125
                    elif k == 1:
                        ox = 0.125
                        oy = -0.375
                    elif k == 2:
                        ox = 0.375
                        oy = 0.125
                    elif k == 3:
                        ox = -0.125
                        oy = 0.375
                    elif k == 4:
                        ox = 0.30
                        oy = -0.30
                    else:
                        ox = -0.30
                        oy = 0.30
                    r, g, b, idv = shade_pixel(i + 0.5 + ox, j + 0.5 + oy, W, H, CAM, OB, n, EV, nev, LS, nl,
                                               ENV, lst, t0s, t1s)
                    sr += r
                    sg += g
                    sb += b
                inv = 1.0 / (ns + 1.0)
                out[j, i, 0] = sr * inv
                out[j, i, 1] = sg * inv
                out[j, i, 2] = sb * inv
    # pass 3: flash / dither / clamp
    fl = ENV[E_FLASH]
    fr_ = int(ENV[E_FRAME])
    for j in prange(H):
        for i in range(W):
            r = out[j, i, 0]
            g = out[j, i, 1]
            b = out[j, i, 2]
            if fl > 0.0:
                yy = (j - 0.5 * H) / H
                xx = (i - 0.5 * W) / H
                rad = 1.0 / (1.0 + 2.0 * (xx * xx + yy * yy))
                k = fl * (0.6 + 0.4 * rad)
                r = r * (1.0 + 0.3 * k) + k * 0.34
                g = g * (1.0 + 0.3 * k) + k * 0.34
                b = b * (1.0 + 0.3 * k) + k * 0.34
            if dither > 0.0:
                # +-0.5 LSB (8-bit sRGB) dither, scaled to the local linear step so dark gradients do not band
                nzu = hash_u(i, j, fr_) - 0.5
                lm = max(r, max(g, b))
                if lm > 1.0:
                    lm = 1.0
                stp = max(0.0003, 0.00892 * lm ** 0.5833)
                nz = nzu * stp * dither
                r += nz
                g += nz
                b += nz
            if r < 0.0:
                r = 0.0
            if g < 0.0:
                g = 0.0
            if b < 0.0:
                b = 0.0
            if r > 5.0:
                r = 5.0 + (r - 5.0) / (1.0 + (r - 5.0) * 0.5)
            if g > 5.0:
                g = 5.0 + (g - 5.0) / (1.0 + (g - 5.0) * 0.5)
            if b > 5.0:
                b = 5.0 + (b - 5.0) / (1.0 + (b - 5.0) * 0.5)
            out[j, i, 0] = r
            out[j, i, 1] = g
            out[j, i, 2] = b


# ============================================================================= scene packing helpers (python)
def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def pack_object(OB, i, center, scale, R, typ, par, mat, col, glow, bottom, visible=1.0):
    """R = local->world rotation (3x3). The kernel needs q = R^T u (rows of R^T)."""
    scale = np.asarray(scale, dtype=np.float64)
    OB[i, 0:3] = center
    OB[i, 3:6] = 1.0 / scale
    OB[i, 6:15] = np.asarray(R).T.reshape(9)
    OB[i, 15] = typ
    p = list(par) + [0.0] * (4 - len(par))
    OB[i, 16:20] = p[:4]
    OB[i, 20] = mat
    # bounding sphere radius
    if typ == 0:
        ext = par[0]
    elif typ == 1:
        ext = (par[0] - par[1]) * 1.7321 + par[1]
    elif typ == 2:
        ext = math.hypot(par[0], par[1])
    elif typ == 3:
        ext = par[0] + par[1]
    else:
        ext = par[0] + par[1]
    OB[i, 21] = ext * float(scale.max()) * 1.03
    OB[i, 22] = float(scale.min()) * 0.9
    OB[i, 23] = visible
    OB[i, 24:27] = col
    OB[i, 27] = glow
    OB[i, 31] = bottom


def cam_arrays(pos, target, roll, fov_deg, H, shift_px=0.0):
    pos = np.asarray(pos, dtype=np.float64)
    f = _unit(np.asarray(target) - pos)
    up0 = np.array([0.0, 1.0, 0.0])
    r = _unit(np.cross(f, up0))
    u = np.cross(r, f)
    c, s = math.cos(roll), math.sin(roll)
    r2 = r * c + u * s
    u2 = -r * s + u * c
    focal = 0.5 * H / math.tan(math.radians(fov_deg) * 0.5)
    CAM = np.zeros(16)
    CAM[0:3] = pos
    CAM[3:6] = r2
    CAM[6:9] = u2
    CAM[9:12] = f
    CAM[12] = focal
    CAM[13] = shift_px
    return CAM


# ============================================================================= timeline / math helpers
def _clamp01(x):
    return min(max(x, 0.0), 1.0)


def sstep(x):
    x = _clamp01(x)
    return x * x * (3.0 - 2.0 * x)


def sstep2(x):
    x = _clamp01(x)
    return x * x * x * (x * (6.0 * x - 15.0) + 10.0)


def lerp(a, b, u):
    return a + (b - a) * u


def hermite(t, t0, t1, v0, v1, m0=0.0, m1=0.0):
    h = t1 - t0
    u = _clamp01((t - t0) / h)
    u2, u3 = u * u, u * u * u
    return ((2 * u3 - 3 * u2 + 1) * v0 + (u3 - 2 * u2 + u) * h * m0 + (-2 * u3 + 3 * u2) * v1 + (u3 - u2) * h * m1)


T_BUILD, T_GAP, T_DROP, T_OUTRO = 3.2, 6.0, 6.4, 12.8


def kick_env(t, decay=0.11):
    """Kick pulse, 0..1: exactly 1.0 at every beat start (t = 0.4*k, k = 0..39) and then exp(-dt/0.11) decaying
    (0.26 after 0.15 s, 0.03 after 0.4 s). 0.0 during the GAP (6.0 <= t < 6.4), where the kick is cut.
    Accepts a float or a numpy array and returns the same kind (float or float array)."""
    scalar = np.isscalar(t)
    a = np.asarray(t, dtype=np.float64)
    k = np.floor(a / BEAT + 1e-6)
    ph = np.maximum(a - k * BEAT, 0.0)
    env = np.exp(-ph / decay)
    gap = (a >= T_GAP - 1e-6) & (a < T_DROP - 1e-6)
    env = np.where(gap, 0.0, env)
    return float(env) if scalar else env


def beat_info(t):
    """(bar 1..10, beat in bar 1..4, phase 0..1 inside the beat) for time t in seconds."""
    b = int(math.floor(t / BEAT + 1e-6))
    return b // 4 + 1, b % 4 + 1, (t - b * BEAT) / BEAT


# Audio accents (times in seconds, from the music layer's event list marlo_music_events.json; hard-coded so this
# module has no file dependency). Weights scale the visual accent.
CLAP_EVENTS = ([(3.6, 0.9), (4.4, 0.9), (5.2, 0.9)] + [(6.8 + 0.8 * m, 1.0) for m in range(8)] +
               [(13.2, 0.8), (14.0, 0.6), (14.8, 0.45)])
STAB_TIMES = [6.4, 6.7, 7.0, 7.5, 7.8, 8.3, 8.6, 9.1, 9.4, 9.8, 10.2, 10.6, 11.0, 11.4, 11.8, 12.2, 12.6, 13.1, 13.9]
ROLL_TIMES = [4.8, 5.0, 5.2, 5.3, 5.4, 5.5, 5.6, 5.65, 5.7, 5.75, 5.8, 5.85, 5.9, 5.95]


def _env_events(t, events, decay, win):
    v = 0.0
    for c, w in events:
        a = t - c + EPS_T
        if 0.0 <= a < win:
            v = max(v, w * math.exp(-a / decay))
    return v


def clap_env(t, decay=0.07):
    """Clap pulse: 1.0 (weighted) on beats 2 and 4 of bars 3, 4 and 5-9: 3.6, 4.4, 5.2, 6.8, 7.6 ... 12.4, then the
    fading outro claps 13.2, 14.0, 14.8. Drives the light strobes."""
    return _env_events(t, CLAP_EVENTS, decay, 0.6)


def stab_env(t, decay=0.12):
    """Hard-trance stab accent (1.0 at each stab time): drives laser bursts and ring pulses in the drop."""
    return _env_events(t, [(c, 1.0) for c in STAB_TIMES], decay, 0.8)


def roll_env(t, decay=0.05):
    """Snare-roll hit accent (4.8-6.0 s): small flickers on the build lights."""
    return _env_events(t, [(c, 1.0) for c in ROLL_TIMES], decay, 0.3)


from scipy.interpolate import PchipInterpolator  # noqa: E402

# squash/stretch response after a contact, in frames: -1 = full squash, +1 = full stretch
_G_KEYS_F = [0, 1, 2, 3, 4, 5, 6, 8, 10, 14]
_G_KEYS_V = [-1.0, -0.40, 1.0, 0.62, 0.34, 0.14, 0.0, -0.07, 0.0, 0.0]
_G_POST = PchipInterpolator(_G_KEYS_F, _G_KEYS_V)

OBJ = [
    dict(name="sphere", typ=0, par=(0.80,), mat=0, col=MAG, h0=0.80, yaw=0.0),
    dict(name="cube", typ=1, par=(0.62, 0.16), mat=1, col=LIME, h0=0.62, yaw=0.45),
    dict(name="puck", typ=2, par=(0.74, 0.31, 0.11), mat=2, col=VIO, h0=0.34, yaw=0.0),
    dict(name="torus", typ=3, par=(0.60, 0.25), mat=0, col=LIME, h0=0.25, yaw=0.0),
    dict(name="capsule", typ=4, par=(0.42, 0.32), mat=1, col=MAG, h0=0.74, yaw=0.0),
    dict(name="cube2", typ=1, par=(0.38, 0.10), mat=0, col=VIO, h0=0.38, yaw=0.8),
    dict(name="orb", typ=0, par=(0.36,), mat=3, col=LIME, h0=0.36, yaw=0.0),
]
NOBJ = len(OBJ)

# formation positions (x, z); heroes A,B,C have their own intro positions
POS_INTRO = {0: (0.0, -0.45), 1: (-1.18, 0.30), 2: (1.28, 0.50)}
POS_FORM = {0: (0.0, 0.0), 1: (-1.80, 0.25), 2: (1.80, 0.45), 3: (-1.00, 1.30), 4: (1.05, -1.75), 5: (0.95, 1.45),
            6: (-0.90, -1.50)}


def _rec(f, pos, **kw):
    d = dict(t=f / FPS, f=f, pos=pos, flight="hop", H=1.0, tumble=0.0, axis=0, sq=0.55, st=1.35, pre=0.25, land=True,
             ring=1.0, vis=True, ringR=2.2)
    d.update(kw)
    return d


def _build_schedules():
    S = [[] for _ in range(NOBJ)]

    def add(i, f, pos, **kw):
        S[i].append(_rec(f, pos, **kw))

    # ---------------------------------------------------------------- A: chrome sphere, 1-beat hops
    for f in range(0, 96, 12):
        add(0, f, POS_INTRO[0], H=1.15, sq=0.55, st=1.38, ring=1.0)
    for f in range(96, 168, 12):
        add(0, f, POS_FORM[0], H=1.25, sq=0.55, st=1.38, ring=1.3 if f == 96 else 1.0)
    add(0, 168, POS_FORM[0], flight="hang", H=2.3, ring=1.6, st=1.45)
    add(0, 192, POS_FORM[0], H=1.6, sq=0.45, st=1.45, pre=0.55, ring=4.0, ringR=3.0)
    for f in range(204, 384, 12):
        add(0, f, POS_FORM[0], H=1.6, sq=0.55, st=1.42, ring=1.4)
    for f in range(384, 480, 12):
        add(0, f, POS_INTRO[0], H=1.15, sq=0.55, st=1.38, ring=1.0)
    add(0, 480, POS_INTRO[0], H=1.15, sq=0.55, st=1.38, ring=1.0)

    # ---------------------------------------------------------------- B: black glass cube, 2-beat tumbling hops
    for f in range(0, 96, 24):
        add(1, f, POS_INTRO[1], H=2.0, tumble=90.0, axis=0, sq=0.58, st=1.32, ring=1.2, pre=0.3)
    for f in range(96, 168, 24):
        add(1, f, POS_FORM[1], H=2.1, tumble=90.0, axis=0, sq=0.58, st=1.32, ring=1.2, pre=0.3)
    add(1, 168, POS_FORM[1], flight="hang", H=2.7, tumble=90.0, axis=0, ring=1.6)
    add(1, 192, POS_FORM[1], H=2.4, tumble=90.0, axis=0, sq=0.48, st=1.4, pre=0.55, ring=4.0, ringR=3.0)
    for f in range(216, 384, 24):
        add(1, f, POS_FORM[1], H=2.4, tumble=90.0, axis=0, sq=0.58, st=1.35, ring=1.5, pre=0.3)
    for f in range(384, 480, 24):
        add(1, f, POS_INTRO[1], H=2.0, tumble=90.0, axis=0, sq=0.58, st=1.32, ring=1.2, pre=0.3)
    add(1, 480, POS_INTRO[1], H=2.0, tumble=90.0, axis=0, sq=0.58, st=1.32, ring=1.2, pre=0.3)

    # ---------------------------------------------------------------- C: black puck, flips; drop = off-beat eighth
    for f in range(0, 96, 12):
        add(2, f, POS_INTRO[2], H=1.0, tumble=180.0, axis=2, sq=0.60, st=1.5, ring=1.0, pre=0.3)
    for f in range(96, 168, 12):
        add(2, f, POS_FORM[2], H=1.0, tumble=180.0, axis=2, sq=0.60, st=1.5, ring=1.0, pre=0.3)
    add(2, 168, POS_FORM[2], flight="hang", H=2.5, tumble=180.0, axis=2, ring=1.6)
    add(2, 192, POS_FORM[2], H=0.55, tumble=0.0, sq=0.5, st=1.5, pre=0.55, ring=4.0, ringR=3.0)
    for f in range(198, 384, 12):
        add(2, f, POS_FORM[2], H=1.0, tumble=180.0, axis=2, sq=0.60, st=1.5, ring=1.3, pre=0.3)
    # 378 -> 384 short hop back on the beat
    for f in range(384, 480, 12):
        add(2, f, POS_INTRO[2], H=1.0, tumble=180.0, axis=2, sq=0.60, st=1.5, ring=1.0, pre=0.3)
    add(2, 480, POS_INTRO[2], H=1.0, tumble=180.0, axis=2, sq=0.60, st=1.5, ring=1.0, pre=0.3)
    # fix the short hop 378->384 height
    for r in S[2]:
        if r["f"] == 378:
            r["H"] = 0.5
            r["tumble"] = 0.0

    # ---------------------------------------------------------------- D: torus (lands 96), 1-beat hops, exits 396
    add(3, 84, POS_FORM[3], flight="fall", H=13.0, land=False, ring=0.0)
    for f in range(96, 168, 12):
        add(3, f, POS_FORM[3], H=1.0, tumble=180.0, axis=0, sq=0.58, st=1.4, ring=2.0 if f == 96 else 1.0,
            pre=0.5 if f == 96 else 0.3)
    add(3, 168, POS_FORM[3], flight="hang", H=2.1, tumble=180.0, axis=0, ring=1.6)
    add(3, 192, POS_FORM[3], H=1.1, tumble=180.0, axis=0, sq=0.45, st=1.45, pre=0.55, ring=4.0, ringR=3.0)
    for f in range(204, 396, 12):
        add(3, f, POS_FORM[3], H=1.1, tumble=180.0, axis=0, sq=0.58, st=1.4, ring=1.3, pre=0.3)
    add(3, 396, POS_FORM[3], flight="rise", H=15.0, sq=0.58, st=1.6, ring=1.3, pre=0.3)
    add(3, 408, POS_FORM[3], flight="hop", land=False, vis=False, ring=0.0)

    # ---------------------------------------------------------------- E: capsule (lands 120), off-beat in drop, exits 408
    add(4, 108, POS_FORM[4], flight="fall", H=13.0, land=False, ring=0.0)
    for f in range(120, 168, 12):
        add(4, f, POS_FORM[4], H=1.0, tumble=0.0, sq=0.55, st=1.32, ring=2.0 if f == 120 else 1.0,
            pre=0.5 if f == 120 else 0.3)
    add(4, 168, POS_FORM[4], flight="hang", H=2.2, ring=1.6)
    add(4, 192, POS_FORM[4], H=0.55, sq=0.45, st=1.45, pre=0.55, ring=4.0, ringR=3.0)
    for f in range(198, 384, 12):
        add(4, f, POS_FORM[4], H=1.05, sq=0.55, st=1.32, ring=1.3, pre=0.3)
    for r in S[4]:
        if r["f"] == 378:
            r["H"] = 0.5
    add(4, 384, POS_FORM[4], H=1.05, sq=0.55, st=1.32, ring=1.3, pre=0.3)
    add(4, 396, POS_FORM[4], H=1.05, sq=0.55, st=1.32, ring=1.3, pre=0.3)
    add(4, 408, POS_FORM[4], flight="rise", H=15.0, sq=0.58, st=1.6, ring=1.3, pre=0.3)
    add(4, 420, POS_FORM[4], flight="hop", land=False, vis=False, ring=0.0)

    # ---------------------------------------------------------------- F: small chrome cube (lands 144), 16th micro hops
    add(5, 132, POS_FORM[5], flight="fall", H=13.0, land=False, ring=0.0)
    for f in range(144, 168, 12):
        add(5, f, POS_FORM[5], H=0.9, tumble=90.0, axis=2, sq=0.62, st=1.3, ring=2.0 if f == 144 else 1.0,
            pre=0.5 if f == 144 else 0.3)
    add(5, 168, POS_FORM[5], flight="hang", H=2.0, tumble=90.0, axis=2, ring=1.6)
    add(5, 192, POS_FORM[5], H=0.3, sq=0.5, st=1.4, pre=0.55, ring=4.0, ringR=3.0)
    micro = []
    for b in range(192, 420, 12):
        for j, hh in ((3, 0.30), (6, 0.22), (9, 0.30)):
            micro.append((b + j, hh))
    for f, hh in micro:
        add(5, f, POS_FORM[5], H=hh, sq=0.78, st=1.15, pre=0.12, ring=0.35, ringR=1.0)
    # hop across the kick: set heights; the last hop of each beat is longer (9 -> 15)
    for r in S[5]:
        if r["f"] >= 192 and (r["f"] - 192) % 12 == 9:
            r["H"] = 0.55
    add(5, 420, POS_FORM[5], flight="rise", H=15.0, sq=0.62, st=1.5, ring=1.0, pre=0.3)
    add(5, 432, POS_FORM[5], flight="hop", land=False, vis=False, ring=0.0)

    # ---------------------------------------------------------------- G: glowing orb (lands 168), micro hops, exits 432
    add(6, 156, POS_FORM[6], flight="fall", H=13.0, land=False, ring=0.0)
    add(6, 168, POS_FORM[6], flight="hang", H=2.0, ring=2.5, sq=0.55, st=1.4, pre=0.5)
    add(6, 192, POS_FORM[6], H=0.3, sq=0.5, st=1.4, pre=0.55, ring=4.0, ringR=3.0)
    micro = []
    for b in range(192, 432, 12):
        for j, hh in ((6, 0.26), (9, 0.2)):
            micro.append((b + j, hh))
    for f, hh in micro:
        add(6, f, POS_FORM[6], H=hh, sq=0.78, st=1.15, pre=0.12, ring=0.35, ringR=1.0)
    for r in S[6]:
        if r["f"] >= 192 and (r["f"] - 192) % 12 == 9:
            r["H"] = 0.75
    add(6, 432, POS_FORM[6], flight="rise", H=15.0, sq=0.62, st=1.5, ring=1.0, pre=0.3)
    add(6, 444, POS_FORM[6], flight="hop", land=False, vis=False, ring=0.0)

    for i in range(NOBJ):
        S[i].sort(key=lambda r: r["f"])
        fs = [r["f"] for r in S[i]]
        assert len(fs) == len(set(fs)), (i, [f for f in fs if fs.count(f) > 1])
    return S


SCHED = _build_schedules()


# ============================================================================= object state
_SCH_T = [np.array([r["t"] for r in S]) for S in SCHED]


def obj_state(i, t):
    """State of object i at time t, or None if not visible. Returns dict(pos, h, sy, tumble, axis, flight, tau)."""
    S = SCHED[i]
    idx = int(np.searchsorted(_SCH_T[i], t + EPS_T, side="right")) - 1
    if idx < 0 or idx + 1 >= len(S):
        return None
    r0, r1 = S[idx], S[idx + 1]
    if not r0["vis"]:
        return None
    D = r1["t"] - r0["t"]
    tau = t - r0["t"]
    u = _clamp01(tau / D)
    fl = r0["flight"]
    H = r0["H"]
    if fl == "hop":
        h = H * 4.0 * u * (1.0 - u)
    elif fl == "fall":
        h = H * (1.0 - u * u)
    elif fl == "rise":
        h = H * u * u
    else:  # hang: rise to apex at +12 frames (6.0 s), hover, then slam in the last 4 frames
        a = tau * FPS
        if a <= 12.0:
            h = H * (1.0 - ((12.0 - a) / 12.0) ** 2)
        elif a <= 20.0:
            h = H + 0.35 * sstep((a - 12.0) / 8.0)
        else:
            w = _clamp01((a - 20.0) / 4.0)
            h = (H + 0.35) * (1.0 - w * w)
    sy = 1.0
    if r0["land"]:
        g = float(_G_POST(min(tau * FPS, 14.0)))
        if g < 0.0:
            sy *= 1.0 + (-g) * (r0["sq"] - 1.0)
        else:
            sy *= 1.0 + g * (r0["st"] - 1.0)
    if r1["land"]:
        sigma = r1["t"] - t
        P = sstep((0.20 - sigma) / (0.20 - 1.0 / FPS))
        sy *= 1.0 + r1["pre"] * P
    if fl == "fall":
        sy *= 1.0 + 0.45 * sstep(u * 3.0)
    elif fl == "rise":
        sy *= 1.0 + 0.5 * sstep(u * 3.0)
    if fl in ("hop", "hang"):
        s = sstep(u)
        px = lerp(r0["pos"][0], r1["pos"][0], s)
        pz = lerp(r0["pos"][1], r1["pos"][1], s)
    else:
        px, pz = r0["pos"]
    tum = r0["tumble"]
    ang = 0.0
    if tum != 0.0:
        if fl == "hang":
            ang = tum * sstep(u / 0.82)
        else:
            ang = tum * sstep2((u - 0.04) / 0.84)
    return dict(pos=(px, pz), h=max(h, 0.0), sy=sy, tumble=math.radians(ang), axis=r0["axis"], flight=fl, tau=tau)


# ============================================================================= turntable angle and tunnel offset
def _omega_raw(t, rate):
    if t < T_BUILD:
        return 0.0
    if t < T_GAP:
        u = (t - T_BUILD) / (T_GAP - T_BUILD)
        return 2.6 * u * u
    if t < T_DROP:
        return lerp(2.6, rate * 0.8, sstep((t - T_GAP) / 0.25))
    a = t - T_DROP
    return rate + 2.2 * math.exp(-a / 0.30) + 0.7 * kick_env(t)


def _phi_end(rate, dt=1.0 / 1200.0):
    tg = np.arange(0.0, 14.0 + dt, dt)
    om = np.array([_omega_raw(x, rate) for x in tg])
    fade = np.clip((tg - T_OUTRO) / 1.2, 0, 1)
    fade = fade * fade * (3 - 2 * fade)
    om = om * (1.0 - fade)
    cum = np.concatenate([[0.0], np.cumsum(0.5 * (om[1:] + om[:-1]) * dt)])
    return tg, cum


def _build_phi():
    # solve the drop turntable rate so that the total rotation at 14.0 s is exactly 2 full turns (loop closure)
    target = 4.0 * math.pi
    r0, r1 = 0.0, 1.4
    e0 = _phi_end(r0)[1][-1]
    e1 = _phi_end(r1)[1][-1]
    rate = r0 + (target - e0) * (r1 - r0) / (e1 - e0)
    tg, cum = _phi_end(rate)
    delta = target - cum[-1]
    return tg, cum, delta


_PHI_T, _PHI_C, _PHI_D = _build_phi()


def phi_angle(t):
    """Turntable rotation of the object formation (rad); equals a multiple of 2*pi from 14.0 s on (loop)."""
    tt = min(max(t, 0.0), 14.0)
    v = float(np.interp(tt, _PHI_T, _PHI_C))
    return v + _PHI_D * sstep2((tt - T_OUTRO) / 1.2)


RING_SP = 3.4
RING_N = 16


def _tunnel_speed(t):
    if t < T_BUILD:
        vb = 2.0
    elif t < T_GAP:
        u = (t - T_BUILD) / (T_GAP - T_BUILD)
        vb = 2.0 + 26.0 * u * u
    elif t < T_DROP:
        vb = lerp(28.0, 3.0, sstep((t - T_GAP) / 0.15))
    elif t < T_OUTRO:
        a = t - T_DROP
        vb = 22.0 + 45.0 * math.exp(-a / 0.3)
    else:
        vb = lerp(22.0, 2.0, sstep((t - T_OUTRO) / 1.6))
    k = kick_env(t)
    return vb * (1.0 + 0.8 * k) if (T_DROP <= t < T_OUTRO + 0.8) else vb * (1.0 + 0.3 * k)


def _build_tunnel():
    dt = 1.0 / 960.0
    tg = np.arange(0.0, DUR + dt, dt)
    v = np.array([_tunnel_speed(x) for x in tg])
    cum = np.concatenate([[0.0], np.cumsum(0.5 * (v[1:] + v[:-1]) * dt)])
    eps = cum[-1] - RING_SP * round(cum[-1] / RING_SP)
    cum = cum - eps * tg / DUR
    return tg, cum


_TUN_T, _TUN_S = _build_tunnel()


def tunnel_offset(t):
    return float(np.interp(t % DUR if t >= DUR else t, _TUN_T, _TUN_S))


# ============================================================================= camera
def _cam_intro(tt):
    D = 9.0 - 0.5 * tt / 3.2
    th = 5.0 + 0.3 * tt
    az = 4.0 * math.sin(2 * math.pi * tt / 3.2)
    roll = 6.5 + 1.5 * math.sin(2 * math.pi * tt / 3.2 + 0.7)
    return dict(D=D, th=th, az=az, roll=roll, ty=1.1, tx=0.0, fov=62.0, ox=0.0, oy=0.0)


def _cam_build(t):
    c = _cam_intro(t)
    u = _clamp01((t - T_BUILD) / (T_GAP - T_BUILD))
    s2 = sstep2(u)
    c["D"] += 1.2 * s2
    c["th"] += 5.0 * s2
    c["az"] += 10.0 * math.sin(2 * math.pi * t / 3.2) * sstep(u)
    c["roll"] += 4.0 * math.sin(2 * math.pi * t / 1.6) * sstep(u)
    v = _clamp01((t - T_GAP) / (T_DROP - T_GAP))
    c["D"] += 1.8 * sstep2(v)
    c["th"] += 2.5 * sstep(v)
    c["ty"] += 0.35 * sstep(v)
    c["fov"] += 2.0 * sstep(v)
    return c


def _shake(a):
    """Camera shake offsets (world units, deg) decaying after the drop impact at a = t - 6.4."""
    if a < 0.0:
        return 0.0, 0.0, 0.0
    amp = math.exp(-a / 0.22)
    sx = math.sin(2 * math.pi * 13.1 * a + 0.3) + 0.5 * math.sin(2 * math.pi * 23.0 * a + 1.1)
    sy = math.sin(2 * math.pi * 11.3 * a + 2.0) + 0.5 * math.sin(2 * math.pi * 19.0 * a)
    sr = math.sin(2 * math.pi * 9.1 * a + 0.9)
    return 0.30 * amp * sx, 0.22 * amp * sy, 2.5 * amp * sr


def _cam_drop(t):
    a = t - T_DROP
    k = kick_env(t)
    D = 8.7 + 0.45 * math.sin(2 * math.pi * a / 6.4) - 0.5 * k - 1.5 * math.exp(-a / 0.18)
    th = 9.0 + 3.0 * math.sin(2 * math.pi * a / 6.4 + 1.2)
    az = 10.0 * math.sin(2 * math.pi * a / 3.2)
    roll = 3.5 * math.sin(2 * math.pi * a / 3.2 + 0.6)
    ox, oy, rr = _shake(a)
    return dict(D=D, th=th, az=az, roll=roll + rr, ty=1.4, tx=0.0, fov=62.0 - 3.0 * k, ox=ox, oy=oy)


def _last_beat_fill(t):
    """Pitch-fall fill of the last beat (15.6-16.0 s): camera dips and pushes in, back to the exact start pose."""
    u = (t - (DUR - BEAT)) / BEAT
    if u <= 0.0 or u >= 1.0:
        return 0.0
    return math.sin(math.pi * u) ** 2


def camera_params(t):
    c = _camera_params(t)
    f = _last_beat_fill(t)
    if f > 0.0:
        c["th"] -= 2.5 * f
        c["fov"] -= 2.5 * f
        c["roll"] += 1.5 * f
    return c


def _camera_params(t):
    if t < T_DROP - 1e-9:
        c = _cam_build(t) if t >= T_BUILD else _cam_intro(t)
        k = kick_env(t)
        if t >= T_BUILD and t < T_GAP:
            c["fov"] -= 2.0 * max(k, 0.0) * sstep((t - T_BUILD) / 1.0)
        return c
    c = _cam_drop(t)
    if t > T_OUTRO:
        w = sstep((t - T_OUTRO) / 1.6)
        ci = _cam_intro(t - DUR)
        for key in c:
            c[key] = lerp(c[key], ci[key], w)
    return c


def camera_arrays(t, H):
    c = camera_params(t)
    th = math.radians(c["th"])
    az = math.radians(c["az"])
    tgt = np.array([c["tx"], c["ty"], 0.0])
    pos = tgt + c["D"] * np.array([math.sin(az) * math.cos(th), math.sin(th), math.cos(az) * math.cos(th)])
    pos[0] += c["ox"]
    pos[1] += c["oy"]
    return cam_arrays(pos, tgt, math.radians(c["roll"]), c["fov"], H, -30.0 * H / 1920.0)


# ============================================================================= energy / lights
def energy(t):
    if t < T_BUILD:
        return 0.72
    if t < T_GAP:
        return 0.72 + 0.28 * sstep((t - T_BUILD) / 2.8)
    if t < T_DROP:
        return lerp(1.0, 0.22, sstep((t - T_GAP) / 0.12))
    if t < T_OUTRO:
        return 1.0
    return lerp(1.0, 0.72, sstep((t - T_OUTRO) / 1.6))


def _ramp(t, t0, t1, v0, v1):
    return lerp(v0, v1, sstep((t - t0) / (t1 - t0)))


def tunnel_amount(t):
    if t < T_BUILD:
        return 0.015
    if t < T_GAP:
        return _ramp(t, T_BUILD, 4.0, 0.015, 1.0)
    if t < T_DROP:
        return _ramp(t, T_GAP, 6.12, 1.0, 0.14)
    if t < T_OUTRO:
        return 1.0
    return _ramp(t, T_OUTRO, 14.4, 1.0, 0.015)


def laser_amount(t):
    if t < 4.4:
        return 0.0
    if t < T_GAP:
        return _ramp(t, 4.4, 5.6, 0.0, 0.6)
    if t < T_DROP:
        return 0.0
    if t < T_OUTRO:
        return 1.0
    return _ramp(t, T_OUTRO, 13.6, 1.0, 0.0)


def spot_amount(t):
    if T_GAP - 0.08 <= t < T_DROP:
        return sstep((t - (T_GAP - 0.08)) / 0.2)
    return 0.0


def gap_dim(t):
    """1.0 normally; falls to ~0.2 inside the GAP (single hot spot)."""
    if T_GAP <= t < T_DROP:
        return lerp(1.0, 0.2, sstep((t - T_GAP) / 0.12))
    return 1.0


def lead_amount(t):
    """0 -> 1 when the melodic lead joins (bars 7-8 of the drop, 9.6-12.8 s): more beams, brighter rings."""
    if T_DROP + 3.2 <= t < T_OUTRO:
        return sstep((t - (T_DROP + 3.2)) / 0.3)
    if T_OUTRO <= t < T_OUTRO + 0.8:
        return 1.0 - sstep((t - T_OUTRO) / 0.8)
    return 0.0


def flash_amount(t):
    a = t - T_DROP + EPS_T
    if a >= 0.0:
        return math.exp(-a / 0.07)
    return 0.0


# ============================================================================= scene assembly
MAX_EV = 28
MAX_LS = 14
DITHER = 1.0             # dither amplitude in 8-bit LSB (peak-to-peak) against banding in dark gradients; 0 = off


def _events(t):
    ev = []
    for i in range(NOBJ):
        o = OBJ[i]
        for r in SCHED[i]:
            if not r["land"] or r["ring"] <= 0.0:
                continue
            for off in (0.0, -DUR):
                tc = r["t"] + off
                a = t - tc + EPS_T
                lim = 0.35 if r["ring"] < 0.5 else 1.3
                if 0.0 <= a < lim:
                    px, pz = r["pos"]
                    ph = phi_angle(tc if tc >= 0.0 else tc + DUR)
                    c, s = math.cos(ph), math.sin(ph)
                    x = c * px + s * pz
                    z = -s * px + c * pz
                    rr = r["ringR"]
                    R = 0.45 + rr * (1.0 - math.exp(-a / 0.20))
                    w = 0.05 + 0.22 * a + 0.02 * rr
                    tap = (1.0 - a / lim) ** 2
                    amp = r["ring"] * 0.8 * math.exp(-a / 0.28) * tap
                    fl = r["ring"] * 1.0 * math.exp(-a / 0.07) * tap
                    fr = 0.45 + 0.2 * rr
                    col = o["col"]
                    ev.append([x, z, R, w, amp, fl, fr, col[0], col[1], col[2]])
    # giant drop shockwave(s)
    a = t - T_DROP + EPS_T
    if 0.0 <= a < 1.8:
        R = 46.0 * (1.0 - math.exp(-a / 0.40))
        ev.append([0.0, 0.0, R, 0.35 + 2.2 * a, 1.1 * math.exp(-a / 0.40), 0.6 * math.exp(-a / 0.07), 3.2, 1.0, 0.92, 1.0])
        a2 = a - 0.10
        if a2 >= 0.0:
            R2 = 30.0 * (1.0 - math.exp(-a2 / 0.35))
            ev.append([0.0, 0.0, R2, 0.25 + 1.6 * a2, 1.6 * math.exp(-a2 / 0.4), 0.0, 1.0, *MAG])
    # spawn-landing shockwaves (build): larger ring on each word beat
    ev.sort(key=lambda e: -(e[4] + 0.3 * e[5]))
    return ev[:MAX_EV]


def _lasers(t, k, la, lead, stab):
    ls = []
    for j in range(8 + (4 if lead > 0.01 else 0)):
        x0 = (j - 3.5) * 1.5
        sweep = 0.55 * math.sin(2 * math.pi * (t / 3.2) + 0.9 * j) + 0.25 * math.sin(2 * math.pi * (t / 1.6) * 0.5 + j)
        ax = (j - 3.5) * 0.17 + sweep
        ez = 0.30 * math.sin(2 * math.pi * t / 6.4 + 0.7 * j)
        e = _unit((math.sin(ax), math.cos(0.35 + 0.1 * math.sin(j)), ez - 0.25))
        col = (LIME, MAG, VIO)[j % 3]
        inten = 2.0 * (0.35 + 0.8 * k + 0.9 * stab) * la * (1.0 + 0.35 * lead)
        if j >= 8:
            inten *= lead
        ls.append([x0, 0.0, -9.0, e[0], e[1], e[2], 0.07, inten, col[0], col[1], col[2], 45.0])
    return ls


def scene_at(t, H, t_main=None):
    t_main = t if t_main is None else t_main
    k = kick_env(t)
    cl = clap_env(t)
    stab = stab_env(t)
    roll = roll_env(t)
    E = energy(t)
    phi = phi_angle(t)
    cph, sph = math.cos(phi), math.sin(phi)
    OB = np.zeros((NOBJ, 32))
    for i in range(NOBJ):
        st = obj_state(i, t)
        o = OBJ[i]
        if st is None:
            OB[i, 23] = 0.0
            pack_object(OB, i, (0, 50, 0), (1, 1, 1), np.eye(3), o["typ"], o["par"], o["mat"], o["col"], 0.0, 0.0, 0.0)
            continue
        sy = st["sy"]
        sxz = 1.0 / math.sqrt(sy)
        px, pz = st["pos"]
        x = cph * px + sph * pz
        z = -sph * px + cph * pz
        cy = st["h"] + o["h0"] * sy
        R = rot_y(o["yaw"] + phi)
        if st["tumble"] != 0.0:
            R = R @ (rot_x(st["tumble"]) if st["axis"] == 0 else rot_z(st["tumble"]))
        glow = (0.35 + 0.65 * k) * (0.5 + 0.7 * E) + 0.9 * cl
        pack_object(OB, i, (x, cy, z), (sxz, sy, sxz), R, o["typ"], o["par"], o["mat"], o["col"], glow, st["h"], 1.0)
    ev = _events(t)
    gd = gap_dim(t)
    EV = np.zeros((MAX_EV, 10))
    for j, e in enumerate(ev):
        EV[j] = e
        EV[j, 4] *= gd
        EV[j, 5] *= gd
    nev = len(ev)

    spot = spot_amount(t)
    lead = lead_amount(t)
    LS = np.zeros((MAX_LS, 12))
    la = laser_amount(t)
    nl = 0
    if la > 0.002:
        for row in _lasers(t, k, la, lead, stab):
            LS[nl] = row
            nl += 1
    if spot > 0.0:
        LS[nl] = [0.0, 14.0, 0.0, 0.0, -1.0, 0.0, 0.30, 2.6 * spot, 1.0, 0.9, 0.7, 14.0]
        nl += 1

    ENV = np.zeros(E_NSLOTS)
    ENV[E_BG] = 0.5 + 0.9 * E
    ENV[E_HORIZ] = (0.010 + 0.018 * E) * (0.6 + 0.8 * k)
    pulse = E * (0.70 + 0.55 * k) + 1.3 * cl + 0.35 * roll
    boxes = [4.6, 4.6, 2.0, 1.8, 2.0, 0.0]
    for j in range(NBOX):
        ENV[E_BOX0 + j] = boxes[j] * pulse
    ENV[E_BOX0 + 2] += 7.0 * spot
    ENV[E_FLASH] = flash_amount(t_main)
    ENV[E_RING_AMT] = tunnel_amount(t)
    ENV[E_RING_S] = tunnel_offset(t)
    ENV[E_RING_SP] = RING_SP
    ENV[E_RING_RX] = 4.4
    ENV[E_RING_RY] = 7.0
    ENV[E_RING_YC] = 1.8
    ENV[E_RING_PULSE] = max(k, 0.6 * stab) if T_BUILD <= t < T_OUTRO + 1.0 else 0.3 * k
    ENV[E_RING_ZLIM] = 999.0 if t >= 4.0 else (22.0 if t < T_BUILD else _ramp(t, T_BUILD, 4.0, 22.0, 90.0))
    ENV[E_RING_W] = 0.05
    ENV[E_RING_INT] = 2.4 * (0.55 + 0.7 * k + 0.35 * stab + 0.5 * roll) * (1.0 + 0.22 * lead)
    ENV[E_LASER] = 1.0
    ENV[E_SPOT] = spot
    ENV[E_SPOT_R] = 1.7
    ENV[E_GRID] = (0.03 + 0.14 * E) * (0.6 + 0.8 * k) * gd
    ENV[E_COS] = cph
    ENV[E_SIN] = -sph
    ENV[E_KICK] = k
    ENV[E_STROBE] = cl
    ENV[E_F0] = 0.42
    ENV[E_DIM] = 0.35 + 0.65 * E
    ENV[E_CLAP] = cl
    ENV[E_NR] = RING_N
    S = ENV[E_RING_S]
    L = RING_SP * RING_N
    zl = ENV[E_RING_ZLIM]
    for kk in range(RING_N):
        u = (kk * RING_SP + S) % L
        zk = -L - 2.0 + u
        depth = -zk
        vis = 1.0 if zl >= 900.0 else _clamp01((zl - depth) * 0.5 + 0.5)
        near = min(1.0, (-3.0 - zk) * 0.4)
        far = min(1.0, (L + 1.5 - depth) * 0.12) / (1.0 + (depth * 0.03) ** 2)
        ENV[E_RZ0 + kk] = zk
        ENV[E_RF0 + kk] = max(0.0, vis * near * far)
    ENV[E_FRAME] = int(round(t_main * FPS))
    CAM = camera_arrays(t, H)
    return CAM, OB, EV, nev, LS, nl, ENV


def _render_one(t, W, H, aa, dither, t_main):
    CAM, OB, EV, nev, LS, nl, ENV = scene_at(t, H, t_main)
    img = np.empty((H, W, 3), np.float32)
    ids = np.empty((H, W), np.int32)
    out = np.empty((H, W, 3), np.float32)
    render_kernel(W, H, CAM, OB, NOBJ, EV, nev, LS, nl, ENV, img, out, ids, float(dither), bool(aa))
    return out


def render(t, W=1080, H=1920, samples=1, shutter=0.5, aa=True, dither=DITHER):
    """Linear HDR RGB frame (float32, H x W x 3, values up to ~6) of the 3D scene at time t seconds.

    No text, deterministic, stateless: the same t always gives the same pixels; t is wrapped into [0, 16).
    Frame i of the video is render(i / FPS). W=540, H=960 gives a fast preview (same framing).
    samples > 1 averages that many sub-frame renders over a forward-looking shutter of `shutter` frames
    (motion blur; cost scales with samples; forward-looking so contact squash poses stay intact)."""
    t = float(t)
    t = t % DUR if (t >= DUR or t < 0.0) else t
    if samples <= 1:
        return _render_one(t, W, H, aa, dither, t)
    acc = None
    for i in range(int(samples)):
        ts = (t + shutter / FPS * i / samples) % DUR
        o = _render_one(ts, W, H, aa, dither, t)
        acc = o if acc is None else acc + o
    return acc * np.float32(1.0 / samples)
