"""Kleiner Raytracer (numba) für Reel 15: Puck auf Eis, Studio-Licht.

Einheiten: Zoll. Eisfläche y = 0, Spielfeld 200 x 85 ft (x = Länge, z = Breite), Mitte im Ursprung.
Puck: Zylinder r = 1.5, Höhe 1 (NHL: 3" Durchmesser, 1" dick).
Pro Pixel spp Samples mit Zufalls-Jitter für Kantenglättung, Bewegungsunschärfe (Unterzeitpunkte),
Tiefenunschärfe (dünne Linse), weiche Schatten (Flächenlicht) und leicht matte Eisreflexion.
render() liefert Hintergrund (Eis/Studio) und Puck getrennt, damit Vektor-Ebenen (Tornetz)
dazwischen liegen können.
"""
import math

import numpy as np
from numba import njit, prange

R = 1.5
HH = 0.5
BEV = 0.07
RINK_X, RINK_Z, CORNER = 1200.0, 510.0, 336.0

KEY = np.array([0.42, 0.78, -0.50])
KEY = KEY / np.linalg.norm(KEY)
RIM = np.array([0.55, 0.40, 0.75])
RIM = RIM / np.linalg.norm(RIM)
KX, KY, KZ = KEY
RX, RY, RZ = RIM
KEY_INT, SKY_INT, KEY_CONE = 1.0, 0.52, 0.10


# ----------------------------------------------------------------- Zufall / Rauschen
@njit(inline="always", cache=True)
def pcg(v):
    state = (v * 747796405 + 2891336453) & 0xFFFFFFFF
    word = ((state >> (((state >> 28) & 15) + 4)) ^ state) * 277803737 & 0xFFFFFFFF
    return ((word >> 22) ^ word) & 0xFFFFFFFF


@njit(inline="always", cache=True)
def rnd(seed):
    return pcg(seed & 0xFFFFFFFF) / 4294967296.0


@njit(inline="always", cache=True)
def h2(ix, iz):
    return pcg(((ix * 73856093) ^ (iz * 19349663)) & 0xFFFFFFFF) / 4294967296.0


@njit(inline="always", cache=True)
def h3(ix, iy, iz):
    return pcg(((ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791)) & 0xFFFFFFFF) / 4294967296.0


@njit(inline="always", cache=True)
def vnoise2(x, z):
    ix, iz = math.floor(x), math.floor(z)
    fx, fz = x - ix, z - iz
    fx, fz = fx * fx * (3 - 2 * fx), fz * fz * (3 - 2 * fz)
    ix, iz = int(ix), int(iz)
    a = h2(ix, iz) + (h2(ix + 1, iz) - h2(ix, iz)) * fx
    b = h2(ix, iz + 1) + (h2(ix + 1, iz + 1) - h2(ix, iz + 1)) * fx
    return a + (b - a) * fz


@njit(inline="always", cache=True)
def vnoise3(x, y, z):
    ix, iy, iz = math.floor(x), math.floor(y), math.floor(z)
    fx, fy, fz = x - ix, y - iy, z - iz
    fx, fy, fz = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy), fz * fz * (3 - 2 * fz)
    ix, iy, iz = int(ix), int(iy), int(iz)
    c000, c100 = h3(ix, iy, iz), h3(ix + 1, iy, iz)
    c010, c110 = h3(ix, iy + 1, iz), h3(ix + 1, iy + 1, iz)
    c001, c101 = h3(ix, iy, iz + 1), h3(ix + 1, iy, iz + 1)
    c011, c111 = h3(ix, iy + 1, iz + 1), h3(ix + 1, iy + 1, iz + 1)
    x00, x10 = c000 + (c100 - c000) * fx, c010 + (c110 - c010) * fx
    x01, x11 = c001 + (c101 - c001) * fx, c011 + (c111 - c011) * fx
    y0, y1 = x00 + (x10 - x00) * fy, x01 + (x11 - x01) * fy
    return y0 + (y1 - y0) * fz


@njit(inline="always", cache=True)
def fbm3(x, y, z):
    return (vnoise3(x, y, z) * 0.5 + vnoise3(x * 2.03, y * 2.03, z * 2.03) * 0.3
            + vnoise3(x * 4.1, y * 4.1, z * 4.1) * 0.2)


@njit(inline="always", cache=True)
def smooth(a, b, x):
    t = (x - a) / (b - a)
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    return t * t * (3 - 2 * t)


@njit(inline="always", cache=True)
def aa(d, fw):
    v = d / fw + 0.5
    return 0.0 if v < 0 else (1.0 if v > 1 else v)


# ----------------------------------------------------------------- Puck
@njit(inline="always", cache=True)
def puck_local(ox, oy, oz, dx, dy, dz, cx, cy, cz, cs, sn):
    px, py, pz = ox - cx, oy - cy, oz - cz
    lx, lz = cs * px - sn * pz, sn * px + cs * pz
    ldx, ldz = cs * dx - sn * dz, sn * dx + cs * dz
    return lx, py, lz, ldx, dy, ldz


@njit(inline="always", cache=True)
def hit_cyl(ox, oy, oz, dx, dy, dz):
    tb, part = 1e30, 0
    a = dx * dx + dz * dz
    if a > 1e-12:
        b = ox * dx + oz * dz
        c = ox * ox + oz * oz - R * R
        disc = b * b - a * c
        if disc >= 0:
            t0 = (-b - math.sqrt(disc)) / a
            if t0 > 1e-4:
                y = oy + t0 * dy
                if -HH <= y <= HH:
                    tb, part = t0, 1
    if abs(dy) > 1e-12:
        t = (HH - oy) / dy
        if 1e-4 < t < tb:
            x, z = ox + t * dx, oz + t * dz
            if x * x + z * z <= R * R:
                tb, part = t, 2
        t = (-HH - oy) / dy
        if 1e-4 < t < tb:
            x, z = ox + t * dx, oz + t * dz
            if x * x + z * z <= R * R:
                tb, part = t, 3
    return tb, part


@njit(inline="always", cache=True)
def env(dx, dy, dz):
    """Studio-Umgebung für Spiegelungen: helle Kuppel, Softbox (Key) und Streiflicht (Rim)."""
    if dy < 0:
        g = 0.62 + 0.1 * dy
        return g, g * 1.01, g * 1.03
    base = 0.42 + 0.30 * dy
    r, g, b = base, base * 1.01, base * 1.04
    ck = dx * KX + dy * KY + dz * KZ
    if ck > 0.90:
        s = smooth(0.90, 0.955, ck) * 7.0
        r += s
        g += s
        b += s
    cr = dx * RX + dy * RY + dz * RZ
    if cr > 0.93:
        s = smooth(0.93, 0.975, cr) * 5.0
        r += s
        g += s * 0.98
        b += s * 0.95
    if dy < 0.12:                                 # Lichtband am Horizont
        s = smooth(0.12, 0.0, dy) * 0.22
        r += s
        g += s
        b += s
    return r, g, b


@njit(inline="always", cache=True)
def shade_puck(lx, ly, lz, part, dx, dy, dz, cs, sn, frost, spark_t, logo, seed, simple):
    # lokale Normale (mit abgerundeter Kante)
    rr = math.sqrt(lx * lx + lz * lz) + 1e-9
    if part == 1:
        nx, ny, nz = lx / rr, 0.0, lz / rr
        ay = abs(ly)
        if ay > HH - BEV:
            w = (ay - (HH - BEV)) / BEV * 0.75
            ny = w * (1.0 if ly > 0 else -1.0)
            nx, nz = nx * (1 - w), nz * (1 - w)
        if ay < 0.32:                              # Riffelung (Rautenmuster) im Mittelband
            th = math.atan2(lz, lx) * R
            k = 2 * math.pi / 0.14
            p = math.cos((th + ly) * k) + math.cos((th - ly) * k)
            bump = 0.07 * p * smooth(0.32, 0.26, ay)
            tx, tz = -lz / rr, lx / rr
            nx += tx * bump
            nz += tz * bump
            ny += bump * 0.6 * math.sin((th + ly) * k)
    else:
        sgn = 1.0 if part == 2 else -1.0
        nx, ny, nz = 0.0, sgn, 0.0
        if rr > R - BEV:
            w = (rr - (R - BEV)) / BEV * 0.75
            nx, nz = lx / rr * w, lz / rr * w
            ny = sgn * (1 - w)
    nl = math.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / nl, ny / nl, nz / nl
    # in Weltkoordinaten
    wx, wz = cs * nx + sn * nz, -sn * nx + cs * nz
    nx, nz = wx, wz
    # Material
    ar, ag, ab = 0.018, 0.018, 0.02
    rough = 0.34
    if part == 2:                                  # Aufdruck oben
        u = (lx / (R * 0.82)) * 0.5 + 0.5
        v = (lz / (R * 0.82)) * 0.5 + 0.5
        if 0 <= u < 1 and 0 <= v < 1:
            th_, tw_ = logo.shape[0], logo.shape[1]
            px = logo[int(v * th_), int(u * tw_)]
            a = px[3]
            if a > 0.01:
                ar = ar * (1 - a) + px[0] * 0.75 * a
                ag = ag * (1 - a) + px[1] * 0.75 * a
                ab = ab * (1 - a) + px[2] * 0.75 * a
                rough = rough * (1 - a) + 0.6 * a
    fa = 0.0
    sparkle = 0.0
    if frost > 0.0:
        if part == 1:
            front = (ly + HH) / (2 * HH) * 0.55
        else:
            front = 0.55 + (1 - rr / R) * 0.45 if part == 2 else 0.0
        n = fbm3(lx * 2.6 + 11.0, ly * 2.6, lz * 2.6)
        fa = smooth(0.0, 0.08, frost * 1.35 - front - (n - 0.5) * 0.55)
        if fa > 0:
            cr_ = vnoise3(lx * 14.0, ly * 14.0, lz * 14.0)
            fl = 0.70 + 0.22 * cr_
            ar = ar * (1 - fa) + fl * 0.93 * fa
            ag = ag * (1 - fa) + fl * 0.98 * fa
            ab = ab * (1 - fa) + fl * 1.06 * fa
            rough = rough * (1 - fa) + 0.8 * fa
            q = 55.0
            gx, gy, gz = lx * q, ly * q, lz * q
            cx_, cy_, cz_ = int(math.floor(gx)), int(math.floor(gy)), int(math.floor(gz))
            hv = h3(cx_, cy_, cz_)
            if hv > 0.965:
                ddx_ = gx - cx_ - 0.5
                ddy_ = gy - cy_ - 0.5
                ddz_ = gz - cz_ - 0.5
                core = math.exp(-(ddx_ * ddx_ + ddy_ * ddy_ + ddz_ * ddz_) * 18.0)
                sparkle = fa * core * (0.5 + 0.5 * math.sin(spark_t * 7.0 + hv * 600.0)) ** 4 * 14.0
    vx, vy, vz = -dx, -dy, -dz
    # diffus: Key + Himmel (oben) + Eis-Aufhellung (unten)
    ndl = nx * KX + ny * KY + nz * KZ
    dif = KEY_INT * (ndl if ndl > 0 else 0.0)
    hemi = SKY_INT * (0.5 + 0.5 * ny) + 0.55 * (0.5 - 0.5 * ny)
    cr = ar * (dif + hemi)
    cg = ag * (dif + hemi)
    cb = ab * (dif + hemi * 1.02)
    # Spiegelung (Fresnel)
    ndv = nx * vx + ny * vy + nz * vz
    ndv = ndv if ndv > 0 else 0.0
    fres = 0.04 + 0.96 * (1 - ndv) ** 5 * (1 - rough * 0.65)
    fres *= (1 - fa * 0.85)
    rx_ = dx - 2 * (dx * nx + dy * ny + dz * nz) * nx
    ry_ = dy - 2 * (dx * nx + dy * ny + dz * nz) * ny
    rz_ = dz - 2 * (dx * nx + dy * ny + dz * nz) * nz
    if not simple:
        j1, j2, j3 = rnd(seed * 3 + 1) - 0.5, rnd(seed * 3 + 2) - 0.5, rnd(seed * 3 + 3) - 0.5
        rx_ += j1 * rough * 0.5
        ry_ += j2 * rough * 0.5
        rz_ += j3 * rough * 0.5
        rl = math.sqrt(rx_ * rx_ + ry_ * ry_ + rz_ * rz_)
        rx_, ry_, rz_ = rx_ / rl, ry_ / rl, rz_ / rl
    er, eg, eb = env(rx_, ry_, rz_)
    spec_scale = 1.0 - rough * 0.55
    cr += er * fres * spec_scale + sparkle
    cg += eg * fres * spec_scale + sparkle
    cb += eb * fres * spec_scale + sparkle
    return cr, cg, cb


# ----------------------------------------------------------------- Eis
@njit(inline="always", cache=True)
def disc_cov(x, z, cx, cz, r, fw):
    d = math.sqrt((x - cx) ** 2 + (z - cz) ** 2)
    return aa(r - d, fw)


@njit(inline="always", cache=True)
def ring_cov(x, z, cx, cz, r, w, fw):
    d = math.sqrt((x - cx) ** 2 + (z - cz) ** 2)
    return aa(w - abs(d - r), fw)


@njit(inline="always", cache=True)
def mix(r, g, b, cr, cg, cb, a):
    return r + (cr - r) * a, g + (cg - g) * a, b + (cb - b) * a


@njit(inline="always", cache=True)
def ice_albedo(x, z, fw):
    qx, qz = abs(x) - (RINK_X - CORNER), abs(z) - (RINK_Z - CORNER)
    ox, oz = (qx if qx > 0 else 0.0), (qz if qz > 0 else 0.0)
    m = qx if qx > qz else qz
    sd = math.sqrt(ox * ox + oz * oz) + (m if m < 0 else 0.0) - CORNER
    if sd > 0:
        g = 0.60 + 0.02 * vnoise2(x / 30, z / 30)
        r, gg, b = g, g * 1.01, g * 1.03
        bl = aa(5.0 - sd, fw)
        return mix(r, gg, b, 0.10, 0.11, 0.13, bl)
    n = vnoise2(x / 48, z / 48) * 0.6 + vnoise2(x / 7, z / 7) * 0.3 + vnoise2(x / 0.9, z / 0.9) * 0.1
    w = 0.885 + n * 0.045
    r, g, b = w * 0.985, w * 0.995, w * 1.01
    # Bande (von oben sichtbar)
    r, g, b = mix(r, g, b, 0.10, 0.11, 0.13, aa(3.0 - abs(sd + 3.0), fw))
    RED = (0.74, 0.10, 0.12)
    BLU = (0.12, 0.27, 0.66)
    ax = abs(x)
    # Mittellinie, blaue Linien, Torlinien
    r, g, b = mix(r, g, b, RED[0], RED[1], RED[2], aa(6.0 - ax, fw) * 0.92)
    r, g, b = mix(r, g, b, BLU[0], BLU[1], BLU[2], aa(6.0 - abs(ax - 300.0), fw) * 0.92)
    r, g, b = mix(r, g, b, RED[0], RED[1], RED[2], aa(1.0 - abs(ax - 1068.0), fw) * 0.92)
    # Mittelkreis + Bully-Punkt
    r, g, b = mix(r, g, b, BLU[0], BLU[1], BLU[2], ring_cov(x, z, 0.0, 0.0, 180.0, 1.0, fw) * 0.92)
    r, g, b = mix(r, g, b, BLU[0], BLU[1], BLU[2], disc_cov(x, z, 0.0, 0.0, 6.0, fw) * 0.95)
    sx = 1.0 if x > 0 else -1.0
    sz = 1.0 if z > 0 else -1.0
    # Bullykreise im Drittel
    r, g, b = mix(r, g, b, RED[0], RED[1], RED[2], ring_cov(x, z, sx * 828.0, sz * 264.0, 180.0, 1.0, fw) * 0.92)
    r, g, b = mix(r, g, b, RED[0], RED[1], RED[2], disc_cov(x, z, sx * 828.0, sz * 264.0, 12.0, fw) * 0.95)
    # neutrale Bullypunkte
    r, g, b = mix(r, g, b, RED[0], RED[1], RED[2], disc_cov(x, z, sx * 240.0, sz * 264.0, 12.0, fw) * 0.95)
    # Torraum
    gx = sx * 1068.0
    dd = math.sqrt((x - gx) ** 2 + z * z)
    if sx * (gx - x) >= -1 and dd < 80:
        inside = aa(72.0 - dd, fw) * aa(48.0 - abs(z), fw) * aa(sx * (gx - x) + 0.5, fw)
        r, g, b = mix(r, g, b, 0.48, 0.72, 0.93, inside * 0.85)
        r, g, b = mix(r, g, b, RED[0], RED[1], RED[2], aa(1.0 - abs(dd - 72.0), fw) * aa(48.0 - abs(z), fw) * 0.9)
    return r, g, b


@njit(inline="always", cache=True)
def backdrop(dy):
    t = dy if dy > 0 else 0.0
    return 1.02 + 0.10 * t, 1.04 + 0.10 * t, 1.09 + 0.08 * t


@njit(inline="always", cache=True)
def trace(ox, oy, oz, dx, dy, dz, pc, pvis, frost, spark_t, logo, seed, pixw):
    """Gibt (r, g, b, ist_puck) zurück."""
    cx, cy, cz, cs, sn = pc[0], pc[1], pc[2], pc[3], pc[4]
    tp, part = 1e30, 0
    lx = ly = lz = ldx = ldy = ldz = 0.0
    if pvis > 0.5:
        lx, ly, lz, ldx, ldy, ldz = puck_local(ox, oy, oz, dx, dy, dz, cx, cy, cz, cs, sn)
        tp, part = hit_cyl(lx, ly, lz, ldx, ldy, ldz)
    ti = -oy / dy if dy < -1e-9 else 1e30
    if part > 0 and tp < ti:
        hx, hy, hz = lx + tp * ldx, ly + tp * ldy, lz + tp * ldz
        r, g, b = shade_puck(hx, hy, hz, part, dx, dy, dz, cs, sn, frost, spark_t, logo, seed, False)
        return r, g, b, 1
    if ti > 1e29:
        r, g, b = backdrop(dy)
        return r, g, b, 0
    px, pz = ox + ti * dx, oz + ti * dz
    fw = ti * pixw / max(-dy, 0.02) * 0.6 + 1e-3
    ar, ag, ab = ice_albedo(px, pz, fw)
    # weicher Schatten des Pucks (Flächenlicht) + Kontakt-Okklusion
    sh, ao = 1.0, 1.0
    if pvis > 0.5:
        ddx, ddz = px - cx, pz - cz
        dist = math.sqrt(ddx * ddx + ddz * ddz)
        if dist < 40.0:
            u1, u2 = rnd(seed * 7 + 11), rnd(seed * 7 + 12)
            a_ = 2 * math.pi * u1
            rr_ = KEY_CONE * math.sqrt(u2)
            lx_, ly_, lz_ = KX + math.cos(a_) * rr_, KY, KZ + math.sin(a_) * rr_
            ll = math.sqrt(lx_ * lx_ + ly_ * ly_ + lz_ * lz_)
            lx_, ly_, lz_ = lx_ / ll, ly_ / ll, lz_ / ll
            sx_, sy_, sz_, sdx, sdy, sdz = puck_local(px, 0.0, pz, lx_, ly_, lz_, cx, cy, cz, cs, sn)
            ts, ps = hit_cyl(sx_, sy_, sz_, sdx, sdy, sdz)
            if ps > 0:
                sh = 0.0
            lift = cy - HH
            e = dist - R
            e = e if e > 0 else 0.0
            ao = 1.0 - (0.55 * math.exp(-e / 0.45) + 0.22 * math.exp(-e / 2.2)) * math.exp(-lift / 0.8)
    cr = ar * (KEY_INT * KY * sh + SKY_INT * ao)
    cg = ag * (KEY_INT * KY * sh + SKY_INT * ao)
    cb = ab * (KEY_INT * KY * sh + SKY_INT * ao * 1.03)
    # Eis-Spiegelung (leicht matt)
    cosv = -dy
    fres = 0.025 + 0.42 * (1 - cosv) ** 6
    rdx = dx + (rnd(seed * 5 + 3) - 0.5) * 0.035
    rdy = -dy
    rdz = dz + (rnd(seed * 5 + 4) - 0.5) * 0.035
    rl = math.sqrt(rdx * rdx + rdy * rdy + rdz * rdz)
    rdx, rdy, rdz = rdx / rl, rdy / rl, rdz / rl
    er, eg, eb = backdrop(rdy)
    er, eg, eb = er * 0.92, eg * 0.92, eb * 0.92
    if pvis > 0.5:
        lx, ly, lz, ldx, ldy, ldz = puck_local(px, 0.0, pz, rdx, rdy, rdz, cx, cy, cz, cs, sn)
        tr, pr = hit_cyl(lx, ly, lz, ldx, ldy, ldz)
        if pr > 0:
            hx, hy, hz = lx + tr * ldx, ly + tr * ldy, lz + tr * ldz
            er, eg, eb = shade_puck(hx, hy, hz, pr, rdx, rdy, rdz, cs, sn, frost, spark_t, logo, seed, True)
    cr = cr * (1 - fres) + er * fres
    cg = cg * (1 - fres) + eg * fres
    cb = cb * (1 - fres) + eb * fres
    # weicher Horizont: flache Strahlen und große Distanzen laufen in den Studio-Hintergrund
    br, bg, bb = backdrop(0.0)
    fog = smooth(-0.012, -0.001, dy)
    far = smooth(350.0, 2600.0, ti) if oy < 400 else 0.0
    fog = fog if fog > far else far
    cr += (br - cr) * fog
    cg += (bg - cg) * fog
    cb += (bb - cb) * fog
    return cr, cg, cb, 0


@njit(parallel=True, fastmath=True, cache=True)
def render(W, H, spp, fseed, cam, lens, puck, logo, out_base, out_puck, out_np):
    """cam[k] = (px,py,pz, rx,ry,rz, ux,uy,uz, fx,fy,fz, tanhalf), lens[k] = (aperture, focus),
    puck[k] = (cx,cy,cz, rot, visible, frost, spark_t). k = Unterzeitpunkt (Bewegungsunschärfe)."""
    K = cam.shape[0]
    aspect = W / H
    for j in prange(H):
        pc = np.empty(5)
        for i in range(W):
            br = bg_ = bb = 0.0
            pr = pg = pb = 0.0
            nb = 0
            npk = 0
            for s in range(spp):
                seed = pcg((fseed * 9781 + (j * W + i)) * 64 + s)
                k = (s + int(rnd(seed + 17) * K)) % K
                jx, jy = rnd(seed + 1), rnd(seed + 2)
                tanh = cam[k, 12]
                sx = ((i + jx) / W * 2 - 1) * tanh * aspect
                sy = (1 - (j + jy) / H * 2) * tanh
                dx = cam[k, 9] + sx * cam[k, 3] + sy * cam[k, 6]
                dy = cam[k, 10] + sx * cam[k, 4] + sy * cam[k, 7]
                dz = cam[k, 11] + sx * cam[k, 5] + sy * cam[k, 8]
                dl = math.sqrt(dx * dx + dy * dy + dz * dz)
                dx, dy, dz = dx / dl, dy / dl, dz / dl
                ox, oy, oz = cam[k, 0], cam[k, 1], cam[k, 2]
                ap = lens[k, 0]
                if ap > 0:
                    fd = lens[k, 1] / (dx * cam[k, 9] + dy * cam[k, 10] + dz * cam[k, 11])
                    fx, fy, fz = ox + dx * fd, oy + dy * fd, oz + dz * fd
                    a_ = 2 * math.pi * rnd(seed + 3)
                    r_ = ap * math.sqrt(rnd(seed + 4))
                    lx, ly = math.cos(a_) * r_, math.sin(a_) * r_
                    ox += lx * cam[k, 3] + ly * cam[k, 6]
                    oy += lx * cam[k, 4] + ly * cam[k, 7]
                    oz += lx * cam[k, 5] + ly * cam[k, 8]
                    dx, dy, dz = fx - ox, fy - oy, fz - oz
                    dl = math.sqrt(dx * dx + dy * dy + dz * dz)
                    dx, dy, dz = dx / dl, dy / dl, dz / dl
                pc[0], pc[1], pc[2] = puck[k, 0], puck[k, 1], puck[k, 2]
                pc[3], pc[4] = math.cos(puck[k, 3]), math.sin(puck[k, 3])
                pixw = 2 * tanh / H
                r, g, b, isp = trace(ox, oy, oz, dx, dy, dz, pc, puck[k, 4], puck[k, 5], puck[k, 6], logo, seed, pixw)
                if isp:
                    pr += r
                    pg += g
                    pb += b
                    npk += 1
                else:
                    br += r
                    bg_ += g
                    bb += b
                    nb += 1
            if nb > 0:
                out_base[j, i, 0], out_base[j, i, 1], out_base[j, i, 2] = br / nb, bg_ / nb, bb / nb
            if npk > 0:
                out_puck[j, i, 0], out_puck[j, i, 1], out_puck[j, i, 2] = pr / npk, pg / npk, pb / npk
            out_np[j, i] = npk / spp
            if nb == 0:
                out_base[j, i, 0], out_base[j, i, 1], out_base[j, i, 2] = pr / npk, pg / npk, pb / npk


def tonemap(x):
    """ACES-Näherung + sRGB."""
    x = np.maximum(x, 0)
    y = (x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14)
    return np.clip(y, 0, 1) ** (1 / 2.2)


def look_at(pos, target, up):
    f = np.asarray(target, float) - np.asarray(pos, float)
    f /= np.linalg.norm(f)
    r = np.cross(f, up)
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return r, u, f


def cam_row(pos, r, u, f, fov_deg):
    return np.array([*pos, *r, *u, *f, math.tan(math.radians(fov_deg) / 2)])


def project(cam, pts, W, H):
    """Weltpunkte (N,3) -> Bildpunkte (N,2) und Tiefe (N,)."""
    pos, r, u, f, tanh = cam[0:3], cam[3:6], cam[6:9], cam[9:12], cam[12]
    d = np.asarray(pts, float) - pos
    z = d @ f
    x = (d @ r) / np.maximum(z, 1e-6) / (tanh * W / H)
    y = (d @ u) / np.maximum(z, 1e-6) / tanh
    return np.stack([(x + 1) * W / 2, (1 - y) * H / 2], -1), z
