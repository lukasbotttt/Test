"""MARLODEEE hype video - TYPE + FX layer (kinetic typography, bloom, CA, glitch, filmic grade).

    import marlo_type as T
    rgb8 = T.compose_frame(scene_rgb, t)     # scene_rgb: float32 linear-HDR (H, W, 3) from marlo_scene.render
                                             # t: seconds (frame i -> i / 30), returns uint8 (H, W, 3)

Everything is a pure function of (scene_rgb, t): no hidden state, deterministic, any 9:16 size (540x960, 1080x1920 ...).
All design coordinates are 1080x1920 px and are scaled by W / 1080.

Pipeline: kinetic type layer (per-letter SDF glyph rendering with squash/stretch springs, extrusion, outline, bevel,
neon glow, ghost smear) + FX shapes (rings, sparks, inhale line) are composited into the HDR scene, then multi-scale
bloom, chromatic aberration (pulses on every kick), glitch row slices, shockwave lens, ACES-like tone mapping,
vignette, scanlines and grain in one fused numba pass.

Timeline (150 BPM, 12 frames per beat, 48 per bar), see the contract: hero slam at 0.0, build words 3.2/4.0/4.8/5.6,
gap inhale 6.0-6.4, drop explosion 6.4 + word-per-beat kinetic layouts, end card from 12.8 with the credit in the last
1.6 s, the last beat hops the hero back into its frame-0 pose (loop).
"""
import math
import os

import numpy as np
from numba import njit, prange
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage
from scipy.interpolate import PchipInterpolator

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 30
DUR = 16.0
FRAMES = 480
BEAT_F = 12.0
DW, DH = 1080.0, 1920.0

# ----------------------------------------------------------------------------- palette (linear)
LIME = (0.578, 1.0, 0.0)
MAG = (1.0, 0.0232, 0.2541)
VIO = (0.198, 0.0452, 1.0)
WHITE = (1.0, 1.0, 1.0)
ACCENT = {"lime": LIME, "mag": MAG, "vio": VIO, "white": WHITE}

# ----------------------------------------------------------------------------- small helpers


def clamp01(x):
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def sstep(x):
    x = clamp01(x)
    return x * x * (3.0 - 2.0 * x)


def lerp(a, b, u):
    return a + (b - a) * u


def ease_out_back(x, c1=1.70158):
    x = clamp01(x)
    c3 = c1 + 1.0
    return 1.0 + c3 * (x - 1.0) ** 3 + c1 * (x - 1.0) ** 2


# squash/stretch response after a contact, in frames: -1 full squash, +1 full stretch (same curve as the scene's heroes)
_GK = [0, 1, 2, 3, 4, 5, 6, 8, 10, 14]
_GV = [-1.0, -0.40, 1.0, 0.62, 0.34, 0.14, 0.0, -0.07, 0.0, 0.0]
_GX = np.linspace(0.0, 14.0, 281)
_GLUT = PchipInterpolator(_GK, _GV)(_GX)


def G(p):
    if p < 0.0:
        return -1.0
    if p >= 14.0:
        return 0.0
    return float(np.interp(p, _GX, _GLUT))


def kick_env(t, decay=0.11):
    """1.0 on every beat start (t = 0.4 k), exp(-dt/0.11) after it, 0 inside the GAP (6.0-6.4 s)."""
    if 6.0 - 1e-6 <= t < 6.4 - 1e-6:
        return 0.0
    k = math.floor(t / 0.4 + 1e-6)
    return math.exp(-max(t - k * 0.4, 0.0) / decay)


def _env_at(t, events, decay, win=0.6):
    v = 0.0
    for c, w in events:
        a = t - c + 1e-7
        if 0.0 <= a < win:
            v = max(v, w * math.exp(-a / decay))
    return v


CLAP_T = [3.6, 4.4, 5.2] + [6.8 + 0.8 * m for m in range(8)] + [13.2, 14.0, 14.8]
ROLL_T = [4.8, 5.0, 5.2, 5.3, 5.4, 5.5, 5.6, 5.65, 5.7, 5.75, 5.8, 5.85, 5.9, 5.95]
ROLL_F = [r * FPS for r in ROLL_T]

# ============================================================================= glyph SDF cache
# name -> (path, variation axes, base em px, cap height ratio)
FONTS = {
    "anton": (os.path.join(HERE, "fonts", "Anton.ttf"), None, 360, 0.86),
    "inter": (os.path.join(HERE, "fonts", "Inter.ttf"), [32, 900], 240, 0.727),
    "inters": (os.path.join(HERE, "fonts", "Inter.ttf"), [20, 800], 144, 0.727),
}
SS = 2
PADB = 72            # SDF padding in base px
_FCACHE = {}
_GLY = {}


def _pil_font(fk, size):
    key = (fk, size)
    f = _FCACHE.get(key)
    if f is None:
        path, axes, _, _ = FONTS[fk]
        f = ImageFont.truetype(path, size)
        if axes:
            f.set_variation_by_axes(axes)
        _FCACHE[key] = f
    return f


class Glyph:
    __slots__ = ("sdf", "adv", "ox", "oy", "cap", "em", "empty")


def get_glyph(fk, ch):
    key = (fk, ch)
    g = _GLY.get(key)
    if g is not None:
        return g
    path, axes, em, capr = FONTS[fk]
    big = em * SS
    f = _pil_font(fk, big)
    g = Glyph()
    g.em = em
    g.cap = capr * em
    g.adv = f.getlength(ch) / SS
    bb = f.getbbox(ch, anchor="ls")
    if ch.strip() == "" or bb[2] <= bb[0]:
        g.empty = True
        g.sdf = np.full((4, 4), 1e3, np.float32)
        g.ox = g.oy = 2.0
        _GLY[key] = g
        return g
    g.empty = False
    pad = PADB * SS
    x0 = int(math.floor(min(0.0, bb[0]))) - pad
    x1 = int(math.ceil(max(g.adv * SS, bb[2]))) + pad
    y0 = int(math.floor(min(bb[1], -capr * big))) - pad
    y1 = int(math.ceil(max(bb[3], 0))) + pad
    # make sizes multiples of SS
    x0 -= x0 % SS
    y0 -= y0 % SS
    x1 += (-x1) % SS
    y1 += (-y1) % SS
    w, h = x1 - x0, y1 - y0
    im = Image.new("L", (w, h), 0)
    ImageDraw.Draw(im).text((-x0, -y0), ch, font=f, fill=255, anchor="ls")
    m = np.asarray(im, dtype=np.float32) / 255.0
    inside = m >= 0.5
    d_out = ndimage.distance_transform_edt(~inside)
    d_in = ndimage.distance_transform_edt(inside)
    sdf = np.where(inside, 0.5 - d_in, d_out - 0.5).astype(np.float32)
    # refine edge pixels with the antialiased coverage (sub-pixel accuracy)
    edge = (m > 0.02) & (m < 0.98)
    sdf = np.where(edge, (0.5 - m) * 1.0, sdf).astype(np.float32)
    sdf = sdf.reshape(h // SS, SS, w // SS, SS).mean(axis=(1, 3)) / SS
    g.sdf = np.ascontiguousarray(sdf, dtype=np.float32)
    g.ox = -x0 / SS
    g.oy = -y0 / SS
    _GLY[key] = g
    return g


def pair_kern(fk, a, b):
    f = _pil_font(fk, FONTS[fk][2] * SS)
    return (f.getlength(a + b) - f.getlength(a) - f.getlength(b)) / SS


# ============================================================================= numba kernels
@njit(cache=True, fastmath=True, inline="always")
def _bil(a, u, v):
    h = a.shape[0]
    w = a.shape[1]
    fu = u - 0.5
    fv = v - 0.5
    i0 = int(math.floor(fu))
    j0 = int(math.floor(fv))
    tu = fu - i0
    tv = fv - j0
    i1 = i0 + 1
    j1 = j0 + 1
    if i0 < 0:
        i0 = 0
    elif i0 > w - 1:
        i0 = w - 1
    if i1 < 0:
        i1 = 0
    elif i1 > w - 1:
        i1 = w - 1
    if j0 < 0:
        j0 = 0
    elif j0 > h - 1:
        j0 = h - 1
    if j1 < 0:
        j1 = 0
    elif j1 > h - 1:
        j1 = h - 1
    return (a[j0, i0] * (1.0 - tu) + a[j0, i1] * tu) * (1.0 - tv) + (a[j1, i0] * (1.0 - tu) + a[j1, i1] * tu) * tv


@njit(cache=True, fastmath=True, inline="always")
def _c01(x):
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


@njit(cache=True, fastmath=True, inline="always")
def _sst(x):
    x = _c01(x)
    return x * x * (3.0 - 2.0 * x)


# parameter layout of P for k_glyph
P_SPS, P_AL = 0, 1
P_FT, P_FB = 2, 5           # face top / bottom colour (3 each)
P_VTOP, P_VBOT, P_HOR, P_HSOFT, P_BMUL = 8, 9, 10, 11, 12
P_OL, P_OW = 13, 16         # outline colour (3), width px
P_E0, P_E1, P_EXT, P_EX, P_EY, P_RIMI = 17, 20, 23, 24, 25, 26
P_GL, P_GR, P_GI = 27, 30, 31
P_BEV, P_BEVW = 32, 33
P_MODE, P_HOLLOW = 34, 35
P_SHU, P_SHW, P_SHI = 36, 37, 38
P_STW = 39
P_RIM = 40                  # rim / stroke colour (3)
P_N = 48


@njit(cache=True, fastmath=True, parallel=True)
def k_glyph(layer, sdf, M, bx0, bx1, by0, by1, P):
    sps = P[0]
    al = P[1]
    ftr, ftg, ftb = P[2], P[3], P[4]
    fbr, fbg, fbb = P[5], P[6], P[7]
    vtop = P[8]
    vbot = P[9]
    hor = P[10]
    hsoft = P[11]
    bmul = P[12]
    olr, olg, olb = P[13], P[14], P[15]
    ow = P[16]
    e0r, e0g, e0b = P[17], P[18], P[19]
    e1r, e1g, e1b = P[20], P[21], P[22]
    ext = P[23]
    ex = P[24]
    ey = P[25]
    rimi = P[26]
    glr, glg, glb = P[27], P[28], P[29]
    grad = P[30]
    gint = P[31]
    bev = P[32]
    bevw = P[33]
    mode = P[34]
    hollow = P[35]
    shu = P[36]
    shw = P[37]
    shi = P[38]
    stw = P[39]
    rmr, rmg, rmb = P[40], P[41], P[42]
    nst = int(min(16.0, max(3.0, math.ceil(ext / 1.6))))
    du_e = (M[0] * ex + M[1] * ey) * ext / nst
    dv_e = (M[3] * ex + M[4] * ey) * ext / nst
    dmax = ext + ow + 3.5 * grad + 2.0
    Hh = layer.shape[0]
    Ww = layer.shape[1]
    if by0 < 0:
        by0 = 0
    if bx0 < 0:
        bx0 = 0
    if by1 > Hh:
        by1 = Hh
    if bx1 > Ww:
        bx1 = Ww
    for y in prange(by0, by1):
        for x in range(bx0, bx1):
            px = x + 0.5
            py = y + 0.5
            u = M[0] * px + M[1] * py + M[2]
            v = M[3] * px + M[4] * py + M[5]
            d = _bil(sdf, u, v) * sps
            if d > dmax:
                continue
            r = layer[y, x, 0]
            g = layer[y, x, 1]
            b = layer[y, x, 2]
            a = layer[y, x, 3]
            if mode > 0.5:
                # ring-only echo (additive light)
                cv = _c01(0.5 - (abs(d - ow) - stw))
                if cv > 0.0:
                    k = cv * al
                    r += ftr * k
                    g += ftg * k
                    b += ftb * k
                layer[y, x, 0] = r
                layer[y, x, 1] = g
                layer[y, x, 2] = b
                continue
            # --- outer glow (additive)
            if gint > 0.0 and d > 0.0:
                gl = gint * math.exp(-d / grad) * al
                r += glr * gl
                g += glg * gl
                b += glb * gl
            # --- extrusion
            if ext > 0.0 and d > -1.0:
                dmin = d
                kb = 0
                for k in range(1, nst + 1):
                    dk = _bil(sdf, u - du_e * k, v - dv_e * k) * sps
                    if dk < dmin:
                        dmin = dk
                        kb = k
                ec = _c01(0.5 - dmin)
                if ec > 0.0:
                    fr = kb / nst
                    cr = e0r * (1.0 - fr) + e1r * fr
                    cg = e0g * (1.0 - fr) + e1g * fr
                    cb = e0b * (1.0 - fr) + e1b * fr
                    rim = _c01(1.0 + dmin / 1.6) * rimi
                    cr += rmr * rim
                    cg += rmg * rim
                    cb += rmb * rim
                    ec *= al
                    r = r * (1.0 - ec) + cr * ec
                    g = g * (1.0 - ec) + cg * ec
                    b = b * (1.0 - ec) + cb * ec
                    a = ec + a * (1.0 - ec)
            # --- outline
            if ow > 0.0:
                oc = _c01(0.5 - (d - ow)) * (1.0 - 0.55 * hollow) * al
                if oc > 0.0:
                    r = r * (1.0 - oc) + olr * oc
                    g = g * (1.0 - oc) + olg * oc
                    b = b * (1.0 - oc) + olb * oc
                    a = oc + a * (1.0 - oc)
            # --- face
            fc = _c01(0.5 - d)
            if fc > 0.0:
                tn = _c01((v - vtop) / (vbot - vtop))
                sm = _sst((tn - (hor - hsoft)) / (2.0 * hsoft))
                mb = bmul + (1.0 - bmul) * _c01((tn - hor) / (1.0 - hor + 1e-6))
                cr = ftr * (1.0 - sm) + fbr * sm * mb
                cg = ftg * (1.0 - sm) + fbg * sm * mb
                cb = ftb * (1.0 - sm) + fbb * sm * mb
                if bev > 0.0 and d > -bevw:
                    gu = (_bil(sdf, u + 1.0, v) - _bil(sdf, u - 1.0, v)) * 0.5
                    gv = (_bil(sdf, u, v + 1.0) - _bil(sdf, u, v - 1.0)) * 0.5
                    gx = M[0] * gu + M[3] * gv
                    gy = M[1] * gu + M[4] * gv
                    gn = math.sqrt(gx * gx + gy * gy) + 1e-6
                    nl = (gx * -0.45 + gy * -0.89) / gn
                    bw = _c01(1.0 + d / bevw)
                    lit = max(nl, 0.0) * bw
                    sha = max(-nl, 0.0) * bw
                    k1 = 1.0 - bev * 0.55 * sha
                    cr = cr * k1 + bev * 1.7 * lit * lit
                    cg = cg * k1 + bev * 1.7 * lit * lit
                    cb = cb * k1 + bev * 1.7 * lit * lit
                if shi > 0.0:
                    sh = math.exp(-((u - shu) / shw) ** 2) * shi
                    cr += sh
                    cg += sh
                    cb += sh
                fa = fc * (1.0 - 0.88 * hollow) * al
                r = r * (1.0 - fa) + cr * fa
                g = g * (1.0 - fa) + cg * fa
                b = b * (1.0 - fa) + cb * fa
                a = fa + a * (1.0 - fa)
                if hollow > 0.0 and stw > 0.0:
                    sc = fc * _c01((d + stw) + 0.5) * hollow * al
                    r = r * (1.0 - sc) + rmr * sc
                    g = g * (1.0 - sc) + rmg * sc
                    b = b * (1.0 - sc) + rmb * sc
                    a = sc + a * (1.0 - sc)
            layer[y, x, 0] = r
            layer[y, x, 1] = g
            layer[y, x, 2] = b
            layer[y, x, 3] = a


@njit(cache=True, fastmath=True, parallel=True)
def k_ring(layer, cx, cy, R, hw, sy, cr, cg, cb, inten, soft, x_cut0, x_cut1):
    """Additive luminous ring (ellipse: y radius scaled by sy), half width hw, falloff `soft` px."""
    Hh = layer.shape[0]
    Ww = layer.shape[1]
    ext_ = R + hw + soft + 2.0
    y0 = max(0, int(cy - ext_ * sy))
    y1 = min(Hh, int(cy + ext_ * sy) + 1)
    x0 = max(0, int(cx - ext_))
    x1 = min(Ww, int(cx + ext_) + 1)
    for y in prange(y0, y1):
        for x in range(x0, x1):
            dx = x + 0.5 - cx
            dy = (y + 0.5 - cy) / sy
            rr = math.sqrt(dx * dx + dy * dy)
            dd = abs(rr - R) - hw
            if dd > soft:
                continue
            if dd <= 0.0:
                k = 1.0
            else:
                k = math.exp(-dd / (soft * 0.35 + 1e-6))
            k *= inten
            layer[y, x, 0] += cr * k
            layer[y, x, 1] += cg * k
            layer[y, x, 2] += cb * k


@njit(cache=True, fastmath=True)
def k_sparks(layer, S):
    """S rows: x0, y0, x1, y1, half width, r, g, b (premultiplied HDR intensity). Additive tapered streaks."""
    Hh = layer.shape[0]
    Ww = layer.shape[1]
    for n in range(S.shape[0]):
        ax, ay, bx, by, wd = S[n, 0], S[n, 1], S[n, 2], S[n, 3], S[n, 4]
        dx = bx - ax
        dy = by - ay
        L2 = dx * dx + dy * dy + 1e-6
        xa = int(max(0.0, min(ax, bx) - wd - 3.0))
        xb = int(min(Ww - 1.0, max(ax, bx) + wd + 3.0))
        ya = int(max(0.0, min(ay, by) - wd - 3.0))
        yb = int(min(Hh - 1.0, max(ay, by) + wd + 3.0))
        for y in range(ya, yb + 1):
            for x in range(xa, xb + 1):
                px = x + 0.5 - ax
                py = y + 0.5 - ay
                tt = (px * dx + py * dy) / L2
                if tt < 0.0:
                    tt = 0.0
                elif tt > 1.0:
                    tt = 1.0
                qx = px - tt * dx
                qy = py - tt * dy
                dd = math.sqrt(qx * qx + qy * qy)
                w = wd * (0.25 + 0.75 * tt)          # thin tail (a), thick head (b)
                if dd > w + 2.5:
                    continue
                if dd <= w:
                    k = 1.0
                else:
                    k = math.exp(-(dd - w) / 1.2)
                k *= (0.35 + 0.65 * tt)
                layer[y, x, 0] += S[n, 5] * k
                layer[y, x, 1] += S[n, 6] * k
                layer[y, x, 2] += S[n, 7] * k


@njit(cache=True, fastmath=True, parallel=True)
def k_rect(layer, x0f, y0f, x1f, y1f, cr, cg, cb, inten, alpha_mode):
    """Anti-aliased rectangle. alpha_mode 0: additive light, 1: premultiplied over."""
    Hh = layer.shape[0]
    Ww = layer.shape[1]
    ya = max(0, int(y0f) - 1)
    yb = min(Hh, int(y1f) + 2)
    xa = max(0, int(x0f) - 1)
    xb = min(Ww, int(x1f) + 2)
    for y in prange(ya, yb):
        cy = _c01(min(y + 1.0 - y0f, y1f - y))
        for x in range(xa, xb):
            cx = _c01(min(x + 1.0 - x0f, x1f - x))
            k = cy * cx * inten
            if k <= 0.0:
                continue
            if alpha_mode == 0:
                layer[y, x, 0] += cr * k
                layer[y, x, 1] += cg * k
                layer[y, x, 2] += cb * k
            else:
                layer[y, x, 0] = layer[y, x, 0] * (1.0 - k) + cr * k
                layer[y, x, 1] = layer[y, x, 1] * (1.0 - k) + cg * k
                layer[y, x, 2] = layer[y, x, 2] * (1.0 - k) + cb * k
                layer[y, x, 3] = k + layer[y, x, 3] * (1.0 - k)


@njit(cache=True, fastmath=True, parallel=True)
def k_comp(scene, layer, out):
    Hh = scene.shape[0]
    Ww = scene.shape[1]
    for y in prange(Hh):
        for x in range(Ww):
            ia = 1.0 - layer[y, x, 3]
            out[y, x, 0] = scene[y, x, 0] * ia + layer[y, x, 0]
            out[y, x, 1] = scene[y, x, 1] * ia + layer[y, x, 1]
            out[y, x, 2] = scene[y, x, 2] * ia + layer[y, x, 2]


@njit(cache=True, fastmath=True, parallel=True)
def k_bright_down(comp, dst, thr):
    """2x2 box downsample of the soft-thresholded HDR image."""
    Hh = comp.shape[0]
    Ww = comp.shape[1]
    h2 = dst.shape[0]
    w2 = dst.shape[1]
    for y in prange(h2):
        for x in range(w2):
            sr = 0.0
            sg = 0.0
            sb = 0.0
            for j in range(2):
                yy = min(2 * y + j, Hh - 1)
                for i in range(2):
                    xx = min(2 * x + i, Ww - 1)
                    r = comp[yy, xx, 0]
                    g = comp[yy, xx, 1]
                    b = comp[yy, xx, 2]
                    m = max(r, max(g, b))
                    if m > thr:
                        k = (m - thr) / (m + 1e-4)
                        mm = m if m < 12.0 else 12.0
                        k *= mm / (m + 1e-4)
                        sr += r * k
                        sg += g * k
                        sb += b * k
            dst[y, x, 0] = sr * 0.25
            dst[y, x, 1] = sg * 0.25
            dst[y, x, 2] = sb * 0.25


@njit(cache=True, fastmath=True, parallel=True)
def k_down(src, dst):
    Hh = src.shape[0]
    Ww = src.shape[1]
    h2 = dst.shape[0]
    w2 = dst.shape[1]
    for y in prange(h2):
        for x in range(w2):
            for c in range(3):
                s = 0.0
                for j in range(2):
                    yy = min(2 * y + j, Hh - 1)
                    for i in range(2):
                        xx = min(2 * x + i, Ww - 1)
                        s += src[yy, xx, c]
                dst[y, x, c] = s * 0.25


@njit(cache=True, fastmath=True, inline="always")
def _bil_ch(a, u, v, c):
    h = a.shape[0]
    w = a.shape[1]
    fu = u - 0.5
    fv = v - 0.5
    i0 = int(math.floor(fu))
    j0 = int(math.floor(fv))
    tu = fu - i0
    tv = fv - j0
    i1 = i0 + 1
    j1 = j0 + 1
    if i0 < 0:
        i0 = 0
    elif i0 > w - 1:
        i0 = w - 1
    if i1 < 0:
        i1 = 0
    elif i1 > w - 1:
        i1 = w - 1
    if j0 < 0:
        j0 = 0
    elif j0 > h - 1:
        j0 = h - 1
    if j1 < 0:
        j1 = 0
    elif j1 > h - 1:
        j1 = h - 1
    return (a[j0, i0, c] * (1.0 - tu) + a[j0, i1, c] * tu) * (1.0 - tv) + \
           (a[j1, i0, c] * (1.0 - tu) + a[j1, i1, c] * tu) * tv


@njit(cache=True, fastmath=True, inline="always")
def _hash2(x, y, s):
    h = np.uint32(x) * np.uint32(374761393) + np.uint32(y) * np.uint32(668265263) + np.uint32(s) * np.uint32(2246822519)
    h = (h ^ (h >> np.uint32(13))) * np.uint32(1274126177)
    h = h ^ (h >> np.uint32(16))
    return (h & np.uint32(65535)) / 32768.0 - 1.0


# F layout for k_final
F_CX, F_CY, F_ZOOM, F_CA, F_CAH = 0, 1, 2, 3, 4
F_SWX, F_SWY, F_SWR, F_SWW, F_SWA = 5, 6, 7, 8, 9
F_BLOOM, F_W1 = 10, 11     # w1..w5 = 11..15
F_EXPO, F_FLASH, F_SAT, F_VIG = 16, 17, 18, 19
F_SCAN, F_SCANP, F_SCANPH, F_GRAIN, F_SEED = 20, 21, 22, 23, 24
F_DESAT, F_FR, F_FG, F_FB = 25, 26, 27, 28
F_N = 32


@njit(cache=True, fastmath=True, parallel=True)
def k_final(comp, L1, L2, L3, L4, L5, out, rowdx, rowca, F):
    Hh = comp.shape[0]
    Ww = comp.shape[1]
    cx = F[0] * Ww
    cy = F[1] * Hh
    zoom = F[2]
    ca = F[3]
    cah = F[4] * Ww
    swx = F[5] * Ww
    swy = F[6] * Hh
    swr = F[7] * Ww
    sww = F[8] * Ww
    swa = F[9] * Ww
    bamt = F[10]
    w1, w2, w3, w4, w5 = F[11], F[12], F[13], F[14], F[15]
    expo = F[16]
    flash = F[17]
    sat = F[18]
    vig = F[19]
    scan = F[20]
    scanp = F[21]
    scanph = F[22]
    grain = F[23]
    seed = int(F[24])
    desat = F[25]
    flr, flg, flb = F[26], F[27], F[28]
    s1x = L1.shape[1] / Ww
    s1y = L1.shape[0] / Hh
    s2x = L2.shape[1] / Ww
    s2y = L2.shape[0] / Hh
    s3x = L3.shape[1] / Ww
    s3y = L3.shape[0] / Hh
    s4x = L4.shape[1] / Ww
    s4y = L4.shape[0] / Hh
    s5x = L5.shape[1] / Ww
    s5y = L5.shape[0] / Hh
    hx = 2.0 / Ww
    hy = 2.0 / Hh
    for y in prange(Hh):
        rdx = rowdx[y]
        rca = rowca[y]
        for x in range(Ww):
            px = x + 0.5 + rdx
            py = y + 0.5
            qx = (px - cx) / zoom
            qy = (py - cy) / zoom
            if swa != 0.0:
                ddx = qx + cx - swx
                ddy = qy + cy - swy
                rr = math.sqrt(ddx * ddx + ddy * ddy) + 1e-3
                qq = (rr - swr) / sww
                disp = swa * qq * math.exp(-qq * qq)
                qx += ddx / rr * disp
                qy += ddy / rr * disp
            gx = cx + qx
            gy = cy + qy
            rx = cx + qx * (1.0 + ca) + cah + rca
            ry = cy + qy * (1.0 + ca)
            bx = cx + qx * (1.0 - ca) - cah - rca
            by = cy + qy * (1.0 - ca)
            r = _bil_ch(comp, rx, ry, 0)
            g = _bil_ch(comp, gx, gy, 1)
            b = _bil_ch(comp, bx, by, 2)
            r *= expo
            g *= expo
            b *= expo
            # bloom pyramid (sampled at the green coordinate)
            for c in range(3):
                bl = w1 * _bil_ch(L1, gx * s1x, gy * s1y, c) + w2 * _bil_ch(L2, gx * s2x, gy * s2y, c) + \
                    w3 * _bil_ch(L3, gx * s3x, gy * s3y, c) + w4 * _bil_ch(L4, gx * s4x, gy * s4y, c) + \
                    w5 * _bil_ch(L5, gx * s5x, gy * s5y, c)
                bl *= bamt * expo
                if c == 0:
                    r += bl
                elif c == 1:
                    g += bl
                else:
                    b += bl
            if flash > 0.0:
                r += flash * flr
                g += flash * flg
                b += flash * flb
            # ACES (Narkowicz fit)
            r = (r * (2.51 * r + 0.03)) / (r * (2.43 * r + 0.59) + 0.14)
            g = (g * (2.51 * g + 0.03)) / (g * (2.43 * g + 0.59) + 0.14)
            b = (b * (2.51 * b + 0.03)) / (b * (2.43 * b + 0.59) + 0.14)
            r = _c01(r)
            g = _c01(g)
            b = _c01(b)
            lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
            sa = sat * (1.0 - desat)
            r = lum + (r - lum) * sa
            g = lum + (g - lum) * sa
            b = lum + (b - lum) * sa
            r = _c01(r)
            g = _c01(g)
            b = _c01(b)
            # display gamma
            r = r ** 0.4545
            g = g ** 0.4545
            b = b ** 0.4545
            # vignette
            vx = (x + 0.5 - Ww * 0.5) * hx
            vy = (y + 0.5 - Hh * 0.5) * hy
            rv = math.sqrt(vx * vx + vy * vy)
            vk = _c01((rv - 0.38) / 1.0)
            vf = 1.0 - vig * vk * vk
            # scanlines
            sl = 0.5 + 0.5 * math.cos(6.2831853 * (y / scanp) + scanph)
            sf = 1.0 - scan * sl * sl
            m = vf * sf
            r *= m
            g *= m
            b *= m
            # grain / dither
            n = _hash2(x, y, seed) * grain * (1.0 - 0.45 * lum) + _hash2(x + 7919, y + 104729, seed + 17) * 0.004
            r += n
            g += n
            b += n
            out[y, x, 0] = np.uint8(_c01(r) * 255.0 + 0.5)
            out[y, x, 1] = np.uint8(_c01(g) * 255.0 + 0.5)
            out[y, x, 2] = np.uint8(_c01(b) * 255.0 + 0.5)


# ============================================================================= words / letters
STY = {
    "lime": dict(face=LIME, rim=LIME),
    "mag": dict(face=MAG, rim=MAG),
    "vio": dict(face=VIO, rim=VIO),
    "white": dict(face=WHITE, rim=LIME),
    "whitemag": dict(face=WHITE, rim=MAG),
    "whitevio": dict(face=WHITE, rim=VIO),
}


def measure(text, fk, tracking=0.0):
    """Advance sum of `text` in em units (incl. kerning and tracking)."""
    em = FONTS[fk][2]
    tot = 0.0
    for i, ch in enumerate(text):
        tot += get_glyph(fk, ch).adv / em
        if i + 1 < len(text):
            tot += pair_kern(fk, ch, text[i + 1]) / em + tracking
    return tot


def stack_layout(lines, fk, cx, cy, width, gap=26.0, tracking=0.0, widths=None):
    """Justified lockup: returns [(text, cx, cy_line, width_line)] with every line `width` wide."""
    capr = FONTS[fk][3]
    ems, caps = [], []
    for j, ln in enumerate(lines):
        w = widths[j] if widths else width
        em = w / measure(ln, fk, tracking)
        ems.append(em)
        caps.append(capr * em)
    total = sum(caps) + gap * (len(lines) - 1)
    y = cy - total / 2.0
    out = []
    for j, ln in enumerate(lines):
        out.append((ln, cx, y + caps[j] / 2.0, widths[j] if widths else width))
        y += caps[j] + gap
    return out


class Word:
    def __init__(self, text, fk, cx, cy, width=None, em=None, t_in=0.0, t_out=None, entry="drop", exit_="scatter",
                 style="lime", amp=0.8, boost=0.9, rot=0.0, tracking=0.0, stagger=0.3, order="lr", wave=0.0,
                 hollow_keys=None, seed=1, place=None, accents=None, boost_frames=None, ext=0.075, glow=1.0,
                 echo=False, jitter=None, drop_h=None, F_in=None, L_out=None, exit_v=1.0, small=False,
                 bevel=0.9, hits=None, face_gain=1.0, shine=None, flip_dir=1.0, popamp=1.0, ex_stagger=None):
        self.text = text
        self.fk = fk
        self.cx0, self.cy0, self.rot0 = float(cx), float(cy), float(rot)
        self.t_in = float(t_in)
        self.t_out = None if t_out is None else float(t_out)
        self.entry = entry
        self.exit = exit_
        self.style = style
        self.accents = accents or []          # [(frame, style)]
        self.boost_frames = boost_frames or []
        self.amp = amp
        self.boost = boost
        self.wave = wave
        self.hollow_keys = hollow_keys or []   # [(frame, value)] smooth steps over 4 frames
        self.place = place
        self.ext = ext
        self.glow = glow
        self.echo = echo
        self.jitter = jitter                   # (f0, f1, strength)
        self.small = small
        self.bevel = bevel
        self.hits = hits or []
        self.face_gain = face_gain
        self.shine = shine
        self.popamp = popamp
        em_b = FONTS[fk][2]
        glyphs = [get_glyph(fk, c) for c in text]
        advs = [g.adv for g in glyphs]
        pos = []
        x = 0.0
        for i, ch in enumerate(text):
            pos.append(x)
            x += advs[i]
            if i + 1 < len(text):
                x += pair_kern(fk, ch, text[i + 1]) + tracking * em_b
        w0 = x
        self.k = (width / w0) if width else (em / em_b)
        self.width = w0 * self.k
        self.capk = FONTS[fk][3] * em_b * self.k          # cap height in design px
        self.glyphs = glyphs
        self.lx = [(pos[i] + advs[i] / 2.0 - w0 / 2.0) * self.k for i in range(len(text))]
        n = len(text)
        self.idx = [i for i in range(n) if not glyphs[i].empty]
        rs = np.random.RandomState(seed * 7919 + n)
        self.r1 = rs.rand(n)
        self.r2 = rs.rand(n)
        self.r3 = rs.rand(n) * 2 - 1
        self.sign = [1.0 if i % 2 == 0 else -1.0 for i in range(n)]
        self.ai = [0.78 + 0.22 * math.sin(1.9 * i + seed) for i in range(n)]
        rank = list(range(n))
        if order == "rl":
            rank = rank[::-1]
        elif order == "center":
            rank = [abs(i - (n - 1) / 2.0) for i in range(n)]
        elif order == "rand":
            rank = [float(v) * n for v in rs.rand(n)]
        self.lag_in = [stagger * r for r in rank]
        exs = stagger * 0.8 if ex_stagger is None else ex_stagger
        self.lag_out = [exs * r for r in rank]
        kind = entry
        self.F_in = F_in if F_in is not None else {"drop": 6, "rise": 6, "zoom": 4, "slide_l": 6, "slide_r": 6,
                                                    "spin": 7, "flip": 6, "pop": 3, "burst": 0, "none": 0}.get(kind, 0)
        self.L_out = L_out if L_out is not None else {"scatter": 9, "fall": 11, "suck": 6, "shrink": 5, "blast": 6,
                                                        "cut": 0, None: 0}.get(exit_, 0)
        self.drop_h = drop_h if drop_h is not None else (cy + 160.0)
        self.exit_v = exit_v
        self.flip_dir = flip_dir

    # -- helpers
    def accent_at(self, f):
        a = self.style
        for ff, nm in self.accents:
            if f >= ff:
                a = nm
        return a

    def hollow_at(self, f):
        cur = 0.0
        for ff, v in self.hollow_keys:
            if f >= ff:
                cur = lerp(cur, v, sstep((f - ff) / 4.0))
        return cur

    def placement(self, f):
        if self.place is not None:
            return self.place(f)
        return self.cx0, self.cy0, 1.0, self.rot0


def _pulse(p, A, ai):
    g = G(p)
    u = p / BEAT_F
    sy = 1.0 + A * 0.20 * g
    sx = 1.0 - A * 0.11 * g
    fall = sstep((u - 0.55) / 0.4)
    sy += A * 0.10 * fall
    sx -= A * 0.04 * fall
    hop = A * ai * 0.15 * 4.0 * u * (1.0 - u)
    return sx, sy, hop, g


def letter_state(wd, i, f):
    """Per-letter animation state at frame f (float). None if the letter is not visible."""
    tin = f - wd.t_in - wd.lag_in[i]
    if tin < -wd.F_in:
        return None
    tout = (f - wd.t_out - wd.lag_out[i]) if wd.t_out is not None else -1e9
    if tout > wd.L_out:
        return None
    dx = dy = rot = 0.0
    sx = sy = zs = al = 1.0
    flash = 0.0
    capk = wd.capk
    kind = wd.entry
    r1, r2, r3 = wd.r1[i], wd.r2[i], wd.r3[i]
    sg = wd.sign[i]
    exiting = tout >= 0.0
    if tin < 0.0:
        F = max(wd.F_in, 1)
        u = (tin + F) / F
        al = clamp01((tin + F) / 1.5)
        if kind == "drop":
            D = wd.drop_h * (0.85 + 0.3 * r1)
            dy = -D * (1.0 - u * u)
            sy *= 1.0 + 0.55 * u
            sx *= 1.0 - 0.16 * u
            rot = 7.0 * sg * (1.0 - u)
        elif kind == "rise":
            D = 520.0 * (0.85 + 0.3 * r1)
            dy = D * (1.0 - u * u)
            sy *= 1.0 + 0.55 * u
            sx *= 1.0 - 0.16 * u
            rot = 7.0 * sg * (1.0 - u)
        elif kind == "zoom":
            zs = 1.0 + 0.55 * (1.0 - u * u)
            sy *= 1.0 + 0.18 * u
            al = clamp01((tin + F) / 1.2)
        elif kind in ("slide_l", "slide_r"):
            d = -1.0 if kind == "slide_l" else 1.0
            dx = d * 620.0 * (1.0 - u) ** 2 * (0.9 + 0.2 * r1)
            sx *= 1.0 + 0.9 * (1.0 - u)
            sy *= 1.0 - 0.22 * (1.0 - u)
        elif kind == "spin":
            rot = wd.flip_dir * 320.0 * (1.0 - u) ** 2
            zs = 0.45 + 0.55 * u
        elif kind == "flip":
            sy = -1.0 + 2.0 * (1.0 - (1.0 - u) ** 2)
            al = clamp01((tin + F) / 1.0)
        elif kind == "pop":
            zs = 0.15 + 0.85 * u
            sy *= 1.0 + 0.2 * u
    A = 0.0
    if not exiting and tin >= 0.0:
        A = wd.amp
        boost_on = tin < 12.0
        for bf in wd.boost_frames:
            if 0.0 <= f - bf < 12.0:
                boost_on = True
        if boost_on:
            A += wd.boost
        p = tin if tin < 12.0 - wd.lag_in[i] else (f % BEAT_F)
        if boost_on and tin >= 12.0 - wd.lag_in[i]:
            p = f % BEAT_F
        psx, psy, hop, g = _pulse(p, A, wd.ai[i])
        sx *= psx
        sy *= psy
        dy -= hop * capk
        rot += A * 2.0 * sg * g
        if kind == "burst" and tin < 16.0:
            ang = math.atan2(0.2 * (r2 - 0.5), wd.lx[i] + 1e-3 * (r1 - 0.5))
            amp_push = 24.0 * math.exp(-0.2 * tin) * math.cos(0.55 * tin)
            dx += math.cos(ang) * amp_push * (1.0 if wd.lx[i] >= 0 else 1.0)
            dy += math.sin(ang) * amp_push * 0.6 - 10.0 * math.exp(-0.25 * tin)
            rot += 10.0 * sg * math.exp(-0.22 * tin) * math.cos(0.5 * tin)
        flash = math.exp(-tin / 3.5) if tin < 14.0 else 0.0
        if kind == "pop" and tin < 10.0:
            # overshoot spring on the pop entry
            s_ = 1.0 + 0.25 * wd.popamp * math.exp(-0.28 * tin) * math.cos(0.9 * tin) * (1.0 if tin > 0.0 else 0.0)
            zs *= s_
    # additional pulses (snare roll etc.)
    if wd.hits and not exiting and tin >= 0.0:
        for hf in wd.hits:
            q = f - hf
            if 0.0 <= q < 8.0:
                gq = G(q)
                sy *= 1.0 + 0.07 * gq
                sx *= 1.0 - 0.04 * gq
                zs *= 1.0 + 0.02 * math.exp(-q / 3.0)
                flash = max(flash, 0.6 * math.exp(-q / 2.5))
    # wave baseline
    if wd.wave != 0.0:
        dy += -wd.wave * capk * math.sin(2.0 * math.pi * (i / max(len(wd.text) - 1, 1)) * 0.9 + f * 0.13)
    # exit
    if exiting:
        L = max(wd.L_out, 1)
        u = clamp01(tout / L)
        ex = wd.exit
        ang = (i * 2.399 + wd.r2[i] * 6.28)
        if ex == "scatter":
            v = 34.0 * wd.exit_v * (0.55 + 0.9 * r1)
            ux = math.cos(ang)
            uy = math.sin(ang) - 0.35
            dx += ux * v * tout * (1.0 + 0.06 * tout)
            dy += uy * v * tout * (1.0 + 0.06 * tout) + 1.2 * tout * tout
            rot += r3 * 38.0 * tout / 3.0
            zs *= 1.0 + 0.05 * tout
            al *= clamp01(1.0 - tout / (L + 1.0)) ** 0.7
            sy *= 1.0 + 0.25 * u
        elif ex == "fall":
            dy += 2.4 * tout * tout + 4.0 * tout
            rot += r3 * 7.0 * tout
            al *= 1.0 - sstep((tout - 6.0) / 6.0)
            sy *= 1.0 + 0.5 * u
            sx *= 1.0 - 0.15 * u
        elif ex == "suck":
            k_ = sstep(u)
            dx += -wd.lx[i] * k_ * 0.95
            dy += -capk * 0.5 * k_ * 0.9
            sy *= max(0.04, 1.0 - 0.96 * sstep(u * 1.7))
            sx *= 1.0 + 0.5 * sstep(u * 1.6)
            zs *= 1.0 - 0.5 * u * u
            al *= 1.0 - sstep((u - 0.6) / 0.4)
        elif ex == "shrink":
            sy *= max(0.03, 1.0 - 1.1 * sstep(u * 1.5))
            sx *= 1.0 + 0.35 * u
            al *= 1.0 - sstep((u - 0.55) / 0.45)
        elif ex == "blast":
            zs *= 1.0 + 0.8 * u * u
            sy *= 1.0 + 0.4 * u
            al *= 1.0 - u ** 1.6
    return dict(dx=dx, dy=dy, rot=rot, sx=sx, sy=sy, zs=zs, al=al, flash=flash, tin=tin)


# ----------------------------------------------------------------------------- drawing
def _build_P(wd, accent, st, s, ktot_sps, capk_s, fk_gain, ghost, hollow, f, shine_u, small):
    sty = STY[accent]
    face = sty["face"]
    rim = sty["rim"]
    P = np.zeros(P_N, np.float64)
    P[P_SPS] = ktot_sps
    P[P_AL] = st["al"] * ghost
    fg = fk_gain * wd.face_gain * (1.0 + 0.9 * st["flash"])
    top = (2.6, 2.6, 2.6)
    for c in range(3):
        P[P_FT + c] = top[c] * fg
        P[P_FB + c] = face[c] * 2.35 * fg
    P[P_VTOP] = 0.0
    P[P_VBOT] = 1.0
    P[P_HOR] = 0.62
    P[P_HSOFT] = 0.30
    P[P_BMUL] = 1.0
    ow = max(1.3 * s, 0.032 * capk_s) if not small else max(1.2 * s, 0.05 * capk_s)
    P[P_OL] = 0.012
    P[P_OL + 1] = 0.010
    P[P_OL + 2] = 0.028
    P[P_OW] = ow
    ext = 0.0 if small else max(2.0 * s, wd.ext * capk_s)
    for c in range(3):
        P[P_E0 + c] = rim[c] * 0.36
        P[P_E1 + c] = (0.012, 0.008, 0.035)[c]
    P[P_EXT] = ext
    P[P_EX] = 0.32
    P[P_EY] = 0.95
    P[P_RIMI] = 0.0 if small else 0.85
    for c in range(3):
        P[P_GL + c] = rim[c] * 1.5
        P[P_RIM + c] = rim[c] * 2.8
    P[P_GR] = max(4.0 * s, 0.085 * capk_s)
    P[P_GI] = (0.55 if not small else 0.30) * wd.glow
    P[P_BEV] = (wd.bevel if not small else 0.25)
    P[P_BEVW] = max(2.0 * s, 0.05 * capk_s)
    P[P_HOLLOW] = hollow
    P[P_STW] = max(1.8 * s, 0.022 * capk_s)
    if wd.shine is not None and shine_u is not None:
        P[P_SHU] = shine_u
        P[P_SHW] = 0.10 * 1.0
        P[P_SHI] = 0.9
    else:
        P[P_SHI] = 0.0
        P[P_SHW] = 1.0
    return P


def _letter_matrix(pxs, pys, ang, sx, sy, ktot, ox_p, oy_p):
    th = math.radians(ang)
    c, s_ = math.cos(th), math.sin(th)
    if abs(sx) < 0.02:
        sx = 0.02 if sx >= 0 else -0.02
    if abs(sy) < 0.02:
        sy = 0.02 if sy >= 0 else -0.02
    a = c / (sx * ktot)
    b = s_ / (sx * ktot)
    d = -s_ / (sy * ktot)
    e = c / (sy * ktot)
    M = np.array([a, b, ox_p - a * pxs - b * pys, d, e, oy_p - d * pxs - e * pys], np.float64)
    return M


def _letter_pose(wd, i, st, f, s, jit=None):
    """Return (pivot_x, pivot_y, angle, sx, sy, ktot_screen) in render pixels."""
    cx, cy, ws, rotw = wd.placement(f)
    zs = st["zs"] * ws
    capk = wd.capk
    th = math.radians(rotw)
    c, s_ = math.cos(th), math.sin(th)
    ox = zs * wd.lx[i]
    oy = zs * capk * 0.5
    px = cx + c * ox - s_ * oy + st["dx"]
    py = cy + s_ * ox + c * oy + st["dy"]
    ang = rotw + st["rot"]
    sx, sy = st["sx"], st["sy"]
    if jit is not None:
        px += jit[0]
        py += jit[1]
        sx *= jit[2]
    return px * s, py * s, ang, sx, sy, wd.k * zs * s


def _draw_letter(layer, wd, i, st, f, s, fkick, ghost=1.0, mode=0, echo_k=1.0, jit=None, accent=None, hollow=0.0,
                 shine_u=None):
    g = wd.glyphs[i]
    pxs, pys, ang, sx, sy, ktot = _letter_pose(wd, i, st, f, s, jit)
    if echo_k != 1.0:
        cx, cy, ws, rotw = wd.placement(f)
        pxs = cx * s + (pxs - cx * s) * echo_k
        pys = cy * s + (pys - cy * s) * echo_k
        ktot *= echo_k
    ox_p = g.ox + g.adv / 2.0
    oy_p = g.oy
    M = _letter_matrix(pxs, pys, ang, sx, sy, ktot, ox_p, oy_p)
    H, W = layer.shape[0], layer.shape[1]
    # bbox from SDF rect corners
    h, w = g.sdf.shape
    th = math.radians(ang)
    c, s_ = math.cos(th), math.sin(th)
    xs, ys = [], []
    for (uu, vv) in ((0, 0), (w, 0), (0, h), (w, h)):
        qx = (uu - ox_p) * ktot * sx
        qy = (vv - oy_p) * ktot * sy
        xs.append(pxs + c * qx - s_ * qy)
        ys.append(pys + s_ * qx + c * qy)
    capk_s = wd.capk * st["zs"] * wd.placement(f)[2] * s
    ext_pad = (wd.ext * capk_s + 8.0) if not wd.small else 4.0
    bx0 = int(max(0, math.floor(min(xs) - 2)))
    bx1 = int(min(W, math.ceil(max(xs) + ext_pad + 2)))
    by0 = int(max(0, math.floor(min(ys) - 2)))
    by1 = int(min(H, math.ceil(max(ys) + ext_pad + 2)))
    if bx1 <= bx0 or by1 <= by0:
        return
    if accent is None:
        accent = wd.accent_at(f)
    sps = ktot * math.sqrt(abs(sx * sy))
    P = _build_P(wd, accent, st, s, sps, capk_s, 1.0 + 0.30 * fkick, ghost, hollow, f, shine_u, wd.small)
    if mode == 1:
        P[P_MODE] = 1.0
        P[P_OW] = 3.0 * s
        P[P_STW] = max(1.2 * s, 0.012 * capk_s)
        P[P_AL] = st["al"] * ghost
        sty = STY[accent]
        for c_ in range(3):
            P[P_FT + c_] = sty["rim"][c_] * 2.2
    k_glyph(layer, g.sdf, M, bx0, bx1, by0, by1, P)


def draw_word(layer, wd, f, s, fkick, glitch=0.0):
    """Draw all letters of a word incl. smear ghosts, echo rings, glitch jitter."""
    if f < wd.t_in - wd.F_in - 1.0:
        return
    if wd.t_out is not None and f > wd.t_out + wd.L_out + wd.lag_out[-1] + 2.0:
        return
    accent = wd.accent_at(f)
    hollow = wd.hollow_at(f)
    cxw = wd.placement(f)
    # shine sweep position (in SDF units) per letter: sweeps over the word right after each beat
    for i in wd.idx:
        st = letter_state(wd, i, f)
        if st is None:
            continue
        jit = None
        if wd.jitter is not None:
            j0, j1, js = wd.jitter
            if j0 <= f < j1:
                fi = int(f)
                rs = np.random.RandomState(fi * 131 + i * 17 + 5)
                amt = js * (0.35 + 0.65 * (f - j0) / (j1 - j0))
                if rs.rand() < 0.35 + 0.5 * amt:
                    jit = (rs.randn() * 14.0 * amt, rs.randn() * 5.0 * amt, 1.0 + rs.randn() * 0.12 * amt)
        # velocity -> ghosts
        st_prev = letter_state(wd, i, f - 0.5)
        n_g = 0
        if st_prev is not None:
            p0 = _letter_pose(wd, i, st, f, 1.0)
            p1 = _letter_pose(wd, i, st_prev, f - 0.5, 1.0)
            sp = math.hypot(p0[0] - p1[0], p0[1] - p1[1]) * 2.0
            dsc = abs(p0[3] * p0[4] - p1[3] * p1[4]) * wd.capk * 2.0
            sp = sp + dsc * 0.6
            n_g = int(min(4, sp / 26.0))
        for gi in range(n_g, 0, -1):
            fg = f - gi * 0.5
            stg = letter_state(wd, i, fg)
            if stg is None:
                continue
            _draw_letter(layer, wd, i, stg, fg, s, fkick, ghost=0.34 * (1.0 - gi / (n_g + 1.0)) + 0.06, jit=jit,
                         accent=accent, hollow=hollow)
        shine_u = None
        if wd.shine is not None:
            g = wd.glyphs[i]
            ph = (f - wd.shine) % 48.0
            cxx = lerp(-0.3, 1.3, clamp01(ph / 16.0)) * wd.width  # word-space x position of the sweep
            shine_u = (g.ox + g.adv / 2.0) + (cxx - wd.width / 2.0 - wd.lx[i]) / wd.k
            if ph > 18.0:
                shine_u = None
        _draw_letter(layer, wd, i, st, f, s, fkick, jit=jit, accent=accent, hollow=hollow, shine_u=shine_u)
        if wd.echo and st["tin"] >= 0.0 and st["al"] > 0.5:
            p = f % BEAT_F
            if p < 9.0:
                ek = 1.0 + 0.22 * (p / 9.0) ** 0.6
                st2 = dict(st)
                st2["sx"] = st2["sy"] = 1.0
                st2["dx"] = st2["dy"] = 0.0
                st2["rot"] = 0.0
                st2["al"] = 0.55 * (1.0 - p / 9.0) ** 1.4
                _draw_letter(layer, wd, i, st2, f, s, 0.0, mode=1, echo_k=ek, accent=accent)


# ============================================================================= timeline
def _build_words():
    Ws = []
    B = 12

    def add(*a, **k):
        w = Word(*a, **k)
        Ws.append(w)
        return w

    # ---------------------------------------------------------------- INTRO hero (frame 0 = contact squash)
    lay_intro = stack_layout(["MARLO", "DEEE"], "anton", 540, 650, 760, gap=26)
    for j, (tx, cx, cy, w) in enumerate(lay_intro):
        add(tx, "anton", cx, cy, width=w, t_in=0, t_out=93, entry="none", exit_="fall", style="lime",
            accents=[(48, "mag")], amp=0.8, boost=0.9, boost_frames=[48], stagger=0.0, ex_stagger=0.9, seed=3 + j,
            echo=True, shine=24)

    # ---------------------------------------------------------------- BUILD
    lay_b = stack_layout(["HARD", "TECHNO"], "anton", 540, 690, 700, gap=28)
    (t0, cx0, cy0, w0), (t1, cx1, cy1, w1) = lay_b
    add("HARD", "anton", cx0, cy0, width=w0, t_in=96, t_out=141, entry="drop", exit_="blast", style="lime",
        accents=[(120, "mag")], boost_frames=[120], amp=0.8, boost=0.9, seed=11, stagger=0.3)
    add("TECHNO", "anton", cx1, cy1, width=w1, t_in=96, t_out=117, entry="drop", exit_="fall", style="lime",
        amp=0.8, boost=0.9, seed=12, stagger=0.3, ex_stagger=0.5)
    wt = w1 * measure("TRANCE", "anton") / measure("TECHNO", "anton")
    add("TRANCE", "anton", cx1, cy1, width=wt, t_in=120, t_out=141, entry="drop", exit_="blast", style="mag",
        amp=0.8, boost=0.9, seed=13, stagger=0.3, ex_stagger=0.2)
    add("MELODIC", "anton", 540, 700, width=760, t_in=144, t_out=165, entry="rise", exit_="blast", style="vio",
        wave=0.10, amp=0.8, boost=0.9, seed=14, stagger=0.3, hits=[r for r in ROLL_F if 144 < r < 165], ex_stagger=0.2)
    lay_g = stack_layout(["MARLO", "DEEE"], "anton", 540, 700, 740, gap=26)
    glits = [r for r in ROLL_F if 168 <= r < 180]
    for j, (tx, cx, cy, w) in enumerate(lay_g):
        add(tx, "anton", cx, cy, width=w, t_in=168, t_out=180, entry="flip", exit_="suck", style="white",
            amp=0.6, boost=0.9, seed=3 + j, stagger=0.0, jitter=(168, 180, 1.0), hits=glits, echo=False,
            ex_stagger=0.0)

    # ---------------------------------------------------------------- DROP
    lay_d = stack_layout(["MARLO", "DEEE"], "anton", 540, 790, 720, gap=26)
    for j, (tx, cx, cy, w) in enumerate(lay_d):
        add(tx, "anton", cx, cy, width=w, t_in=192, t_out=213, entry="burst", exit_="scatter", style="white",
            amp=0.9, boost=0.9, seed=3 + j, stagger=0.0, echo=True, ex_stagger=0.25, glow=1.3)
    add("HARD", "anton", 540, 760, width=740, t_in=216, t_out=225, entry="zoom", exit_="scatter", style="mag",
        rot=-3.0, amp=0.9, boost=0.9, seed=21, stagger=0.25, echo=True, ex_stagger=0.25)
    add("TECHNO", "anton", 540, 860, width=760, t_in=228, t_out=237, entry="slide_r", exit_="scatter", style="lime",
        rot=2.5, amp=0.9, boost=0.9, seed=22, stagger=0.25, echo=True, ex_stagger=0.25)
    add("TRANCE", "anton", 540, 700, width=760, t_in=240, t_out=249, entry="drop", exit_="scatter", style="vio",
        rot=-2.0, amp=0.9, boost=0.9, seed=23, stagger=0.3, echo=True, ex_stagger=0.25)
    add("MELODIC", "anton", 540, 900, width=760, t_in=252, t_out=261, entry="pop", exit_="scatter", style="lime",
        rot=0.0, wave=0.07, amp=0.9, boost=0.9, seed=24, stagger=0.3, echo=True, ex_stagger=0.25)
    lay_d5 = stack_layout(["MARLO", "DEEE"], "anton", 540, 770, 700, gap=26)
    for j, (tx, cx, cy, w) in enumerate(lay_d5):
        add(tx, "anton", cx, cy, width=w, t_in=264, t_out=285, entry="spin", exit_="scatter", style="whitemag",
            rot=4.0, amp=0.9, boost=0.9, seed=3 + j, stagger=0.2, echo=True, ex_stagger=0.2, flip_dir=1.0 - 2.0 * j)

    # ---- bar 7: the wall (outline ghosts of previous lines)
    wall = stack_layout(["HARD", "TECHNO", "TRANCE", "MELODIC"], "anton", 540, 800, 0, gap=22,
                        widths=[560, 600, 600, 640])
    entries = ["drop", "slide_l", "slide_r", "zoom"]
    styles = ["lime", "mag", "vio", "lime"]
    for j, (tx, cx, cy, w) in enumerate(wall):
        tin = 288 + 12 * j
        hk = [(tin + 12, 1.0)] if j < 3 else [(336, 1.0)]
        add(tx, "anton", cx, cy, width=w, t_in=tin, t_out=333, entry=entries[j], exit_="scatter", style=styles[j],
            hollow_keys=hk, amp=0.9 if j == 3 else 0.7, boost=0.9, seed=31 + j, stagger=0.25, echo=(j == 3),
            ex_stagger=0.15, wave=0.05 if j == 3 else 0.0, drop_h=cy + 120)

    # ---- bar 8: hero stack then one wide line
    lay_h = stack_layout(["MARLO", "DEEE"], "anton", 540, 790, 740, gap=26)
    for j, (tx, cx, cy, w) in enumerate(lay_h):
        add(tx, "anton", cx, cy, width=w, t_in=336, t_out=357, entry="burst", exit_="scatter", style="white",
            accents=[(348, "whitemag")], boost_frames=[348], amp=0.9, boost=0.9, seed=3 + j, stagger=0.0, echo=True,
            ex_stagger=0.2, glow=1.3)
    add("MARLODEEE", "anton", 540, 790, width=800, t_in=360, t_out=381, entry="zoom", exit_="blast", style="white",
        accents=[(372, "whitevio")], boost_frames=[372], amp=0.9, boost=0.9, seed=41, stagger=0.2, echo=True,
        wave=0.05, ex_stagger=0.2, glow=1.3)

    # ---------------------------------------------------------------- END CARD
    lay_e = stack_layout(["MARLO", "DEEE"], "anton", 540, 520, 600, gap=22)
    for j, (tx, cx, cy, w) in enumerate(lay_e):
        ci, cyi, wi = lay_intro[j][1], lay_intro[j][2], lay_intro[j][3]

        def mk(cx=cx, cy=cy, w=w, cyi=cyi, wi=wi):
            def place(f):
                lam = sstep((f - 468.0) / 12.0)
                return lerp(cx, 540.0, lam), lerp(cy, cyi, lam), lerp(1.0, wi / w, lam), 0.0
            return place
        add(tx, "anton", cx, cy, width=w, t_in=384, t_out=None, entry="burst", style="white",
            accents=[(408, "lime"), (432, "whitemag"), (468, "lime")], boost_frames=[468], amp=0.8, boost=0.9,
            seed=3 + j, stagger=0.0, echo=False, place=mk(), glow=1.2)
    add("HARD TECHNO · HARD TRANCE · MELODIC", "anton", 540, 875, width=800, tracking=0.0, t_in=396,
        t_out=465, entry="pop", exit_="shrink", style="white", amp=0.45, boost=0.5, seed=51, stagger=0.12,
        ex_stagger=0.1, small=True, ext=0.0, glow=0.8, popamp=0.5)
    add("@MARLODEEEJAY", "inter", 540, 1010, width=720, tracking=0.0, t_in=408, t_out=465, entry="rise",
        exit_="shrink", style="lime", amp=0.5, boost=0.6, seed=52, stagger=0.2, ex_stagger=0.1, ext=0.06,
        glow=0.9)
    add("3D MOTION BY @BLADESANDPUCKS", "inters", 540, 1425, width=520, tracking=0.02, t_in=432, t_out=None,
        entry="pop", style="white", amp=0.18, boost=0.3, seed=53, stagger=0.06, small=True, ext=0.0, glow=0.5,
        popamp=0.3)
    return Ws


_WORDS = None


def words():
    global _WORDS
    if _WORDS is None:
        _WORDS = _build_words()
    return _WORDS


# ============================================================================= FX schedule
FX_C = (0.5, 800.0 / 1920.0)       # impact centre (fraction of W, H)


def _glitch_strength(f):
    """0..1 glitch/slice intensity at the contract moments."""
    g = 0.0
    for f0, amp, ln in ((0, 0.9, 4), (96, 0.55, 4), (192, 1.0, 5), (288, 0.4, 3), (384, 0.7, 4)):
        q = f - f0
        if 0.0 <= q < ln:
            g = max(g, amp * (1.0 - q / ln) ** 1.3)
    if 168.0 <= f < 180.0:                       # MARLODEEE glitch word (5.6 - 6.0 s), intensifying
        q = (f - 168.0) / 12.0
        fi = int(f)
        flick = 1.0 if (fi * 7 + 3) % 3 != 0 else 0.35
        g = max(g, (0.22 + 0.7 * q) * flick)
    if f >= 478.0:                               # loop transition into the frame-0 hit
        g = max(g, 0.25)
    return g


def _glitch_rows(H, W, f, gs):
    rowdx = np.zeros(H, np.float32)
    rowca = np.zeros(H, np.float32)
    if gs <= 0.01:
        return rowdx, rowca
    rs = np.random.RandomState(int(f) * 977 + 13)
    nb = int(3 + 13 * gs)
    for _ in range(nb):
        yc = rs.randint(0, H)
        hh = max(2, int(H * rs.uniform(0.004, 0.055) * (0.5 + gs)))
        dxv = rs.choice([-1.0, 1.0]) * rs.uniform(0.012, 0.11) * W * gs
        cav = rs.uniform(-1.0, 1.0) * 0.012 * W * gs
        rowdx[yc:yc + hh] += dxv
        rowca[yc:yc + hh] += cav
    # a couple of 1-2 px tear lines
    for _ in range(int(2 + 6 * gs)):
        yc = rs.randint(0, H)
        rowdx[yc:yc + 2] += rs.choice([-1.0, 1.0]) * 0.18 * W * gs
    return rowdx, rowca


def _fx_params(t, f, H, W, s):
    F = np.zeros(F_N, np.float64)
    k = kick_env(t)
    if t < 3.2:
        kl = 0.75
    elif t < 6.0:
        kl = 0.9
    elif t < 6.4:
        kl = 0.0
    elif t < 12.8:
        kl = 1.0
    else:
        kl = 0.8
    gap = sstep((t - 6.0) / 0.1) if 6.0 <= t < 6.4 else 0.0
    a = t - 6.4
    gs = _glitch_strength(f)
    drop_e = math.exp(-a / 0.09) if a >= 0.0 else 0.0
    F[F_CX] = 0.5
    F[F_CY] = 0.46
    zoom = 1.0 + 0.010 * kl * k + 0.028 * gap
    if 0.0 <= a < 1.0:
        zoom += 0.075 * math.exp(-a / 0.07)
    for tc in (9.6, 12.8):
        q = t - tc
        if 0.0 <= q < 0.6:
            zoom += 0.03 * math.exp(-q / 0.07)
    F[F_ZOOM] = zoom
    ca = 0.0012 + 0.0052 * kl * k + 0.020 * drop_e + 0.010 * gs
    if t < 0.4:
        ca += 0.004 * math.exp(-t / 0.08)
    F[F_CA] = ca
    F[F_CAH] = 0.0010 * kl * k + 0.003 * drop_e + 0.004 * gs
    # shockwave lens
    sw_a = 0.0
    for tc, amp in ((6.4, 0.045), (9.6, 0.016), (12.8, 0.020)):
        q = t - tc
        if 0.0 <= q < 0.7:
            R = (q / 0.55) * 1.35
            F[F_SWX] = FX_C[0]
            F[F_SWY] = FX_C[1]
            F[F_SWR] = R
            F[F_SWW] = 0.07 + 0.06 * q
            sw_a = amp * math.exp(-q / 0.22)
    F[F_SWA] = sw_a
    bl = 0.80 + 0.10 * kl * k + 1.2 * drop_e + 0.7 * gap
    F[F_BLOOM] = bl
    for i, w in enumerate((0.26, 0.30, 0.30, 0.26, 0.20)):
        F[F_W1 + i] = w
    expo = 1.0 + 0.05 * kl * k - 0.12 * gap
    F[F_EXPO] = expo
    fl = 0.0
    for tc, amp, dec in ((0.0, 0.10, 0.06), (3.2, 0.10, 0.06), (6.4, 0.95, 0.045), (9.6, 0.30, 0.05),
                         (12.8, 0.34, 0.05)):
        q = t - tc
        if 0.0 <= q < 0.5:
            fl = max(fl, amp * math.exp(-q / dec))
    F[F_FLASH] = fl
    F[F_FR], F[F_FG], F[F_FB] = 1.6, 1.6, 1.6
    F[F_SAT] = 1.14
    F[F_DESAT] = 0.30 * gap
    F[F_VIG] = 0.40 + 0.22 * gap + 0.06 * (1.0 - k) * kl
    F[F_SCAN] = 0.030 + 0.07 * gs
    F[F_SCANP] = max(2.0, 4.0 * s)
    F[F_SCANPH] = f * 0.45
    F[F_GRAIN] = 0.020 + 0.012 * gs
    F[F_SEED] = int(f) % 100000 + 1
    return F, gs


def _draw_fx(layer, t, f, W, H, s):
    cx, cy = FX_C[0] * W, FX_C[1] * H
    # ---- gap inhale (6.0 - 6.4 s): contracting rings + line + converging streaks
    if 180.0 <= f < 192.0:
        u = (f - 180.0) / 12.0
        R = lerp(560.0, 26.0, u * u) * s
        k_ring(layer, cx, cy, R, 2.6 * s, 1.0, 1.0, 1.0, 1.0, 3.2 * (0.35 + 0.65 * u), 5.0 * s, 0.0, 0.0)
        R2 = lerp(900.0, 90.0, u ** 1.7) * s
        k_ring(layer, cx, cy, R2, 1.6 * s, 1.0, MAG[0] * 2.0, MAG[1] * 2.0, MAG[2] * 2.0, 1.6 * u, 4.0 * s, 0.0, 0.0)
        L = lerp(720.0, 30.0, u ** 1.4) * s
        k_rect(layer, cx - L / 2, cy - 1.6 * s, cx + L / 2, cy + 1.6 * s, 2.2, 2.2, 2.2, 1.0, 0)
        k_rect(layer, cx - L * 0.9 / 2, cy - 6 * s, cx + L * 0.9 / 2, cy + 6 * s, LIME[0] * 1.2, LIME[1] * 1.2,
               LIME[2] * 1.2, 0.35 * u, 0)
        rs = np.random.RandomState(77)
        n = 40
        S = np.zeros((n, 8), np.float64)
        for j in range(n):
            ang = rs.rand() * 6.2832
            rad = (260.0 + 640.0 * rs.rand()) * s
            col = (LIME, MAG, WHITE, VIO)[j % 4]
            u1, u0 = max(u - 0.10, 0.0), u
            p1 = rad * (1.0 - u0) ** 2
            p0 = rad * (1.0 - u1) ** 2
            S[j, :] = (cx + math.cos(ang) * p0, cy + math.sin(ang) * p0 * 1.0, cx + math.cos(ang) * p1,
                       cy + math.sin(ang) * p1 * 1.0, 1.6 * s, col[0] * 2.2 * u, col[1] * 2.2 * u, col[2] * 2.2 * u)
        k_sparks(layer, S)
        k_rect(layer, cx - 7 * s * u, cy - 7 * s * u, cx + 7 * s * u, cy + 7 * s * u, 3.0, 3.0, 3.0, 1.0, 0)
    # ---- impact bursts: shock rings + sparks
    for f0, strength, nspark in ((192.0, 1.0, 110), (288.0, 0.55, 70), (384.0, 0.55, 70), (0.0, 0.3, 30),
                                 (96.0, 0.3, 30)):
        a = f - f0
        if a < 0.0 or a > 30.0:
            continue
        rs = np.random.RandomState(int(f0) + 5)
        # rings
        for (spd, col, wd_, it) in ((1500.0, WHITE, 5.0, 3.0), (1000.0, LIME, 4.0, 2.2), (640.0, MAG, 3.0, 1.8)):
            R = spd * (1.0 - math.exp(-a / 9.0))
            hw = (wd_ + 0.25 * a) * s
            amp = strength * it * math.exp(-a / 11.0)
            if amp > 0.02:
                k_ring(layer, cx, cy, R * s, hw, 1.0, col[0], col[1], col[2], amp, 6.0 * s, 0.0, 0.0)
        # sparks
        S = np.zeros((nspark, 8), np.float64)
        cnt = 0
        for j in range(nspark):
            ang = rs.rand() * 6.2832
            v = (16.0 + 60.0 * rs.rand() ** 1.5) * (0.6 + 0.4 * strength)
            life = 12.0 + 16.0 * rs.rand()
            if a >= life:
                continue
            col = (WHITE, LIME, MAG, VIO, WHITE)[j % 5]
            drag = 0.11

            def pos(aa):
                dist = v * (1.0 - math.exp(-drag * aa)) / drag
                return cx / s + math.cos(ang) * dist * 1.0, cy / s + math.sin(ang) * dist * 1.0 + 0.55 * aa * aa * 0.5

            p0 = pos(max(a - 1.6, 0.0))
            p1 = pos(a)
            fade = (1.0 - a / life) ** 1.5 * strength
            S[cnt, :] = (p0[0] * s, p0[1] * s, p1[0] * s, p1[1] * s, (1.5 + 2.5 * rs.rand()) * s,
                         col[0] * 3.2 * fade, col[1] * 3.2 * fade, col[2] * 3.2 * fade)
            cnt += 1
        if cnt:
            k_sparks(layer, S[:cnt])


def _bloom_levels(comp, thr=0.95):
    H, W = comp.shape[0], comp.shape[1]
    L = []
    cur = np.empty(((H + 1) // 2, (W + 1) // 2, 3), np.float32)
    k_bright_down(comp, cur, np.float32(thr))
    sig = (1.2, 1.4, 1.5, 1.5, 1.5)
    for lv in range(5):
        cur = ndimage.gaussian_filter(cur, sigma=(sig[lv], sig[lv], 0), mode="nearest")
        L.append(cur)
        if lv < 4:
            nxt = np.empty(((cur.shape[0] + 1) // 2, (cur.shape[1] + 1) // 2, 3), np.float32)
            k_down(cur, nxt)
            cur = nxt
    return L


def text_layer(W, H, t):
    """Premultiplied RGBA float32 layer with all kinetic typography and FX shapes at time t."""
    s = W / DW
    f = t * FPS
    layer = np.zeros((H, W, 4), np.float32)
    fk = kick_env(t)
    for wd in words():
        draw_word(layer, wd, f, s, fk)
    _draw_fx(layer, t, f, W, H, s)
    return layer


def compose_frame(scene_rgb, t):
    """scene_rgb: float32 linear-HDR (H, W, 3) from marlo_scene.render; t seconds. Returns uint8 (H, W, 3)."""
    scene = np.ascontiguousarray(scene_rgb, dtype=np.float32)
    H, W = scene.shape[0], scene.shape[1]
    t = float(t)
    if t < 0.0 or t >= DUR:
        t = t % DUR
    f = t * FPS
    s = W / DW
    layer = text_layer(W, H, t)
    comp = np.empty_like(scene)
    k_comp(scene, layer, comp)
    L = _bloom_levels(comp)
    F, gs = _fx_params(t, f, H, W, s)
    rowdx, rowca = _glitch_rows(H, W, f, gs)
    out = np.empty((H, W, 3), np.uint8)
    k_final(comp, L[0], L[1], L[2], L[3], L[4], out, rowdx, rowca, F)
    return out
