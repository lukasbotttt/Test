"""Reel 19: GAMEDAY – Testspiel-Ankündigung für die Eisteufel Frankfurt (Instagram, 12 s, dunkle Arena).

Daten vom Plakat: EC Wallernhausen Pirates vs. Eisteufel Frankfurt, 24.10., 18:30 Uhr, Eissporthalle Lauterbach.
  0.0–1.0   Puck (mit Teufel-Aufdruck) knallt auf den Bullypunkt ("TESTSPIEL.")
  1.0–3.0   Eisteufel-Logo slammt rein, Kamera umkreist den Puck
  3.0–3.5   "VS." mit Blitz
  3.5–5.5   Pirates-Wappen
  5.5–12.0  Duell-Karte: beide Logos, Blitz, 24.10. / 18:30 UHR / EISSPORTHALLE LAUTERBACH, ab 9 s "KOMMT VORBEI!"
Logos: brand/gameday/*_cut.png (offizielle Vereinslogos: eisteufel.de, Instagram @ecwallernhausen). Renderer: puck3d_dark.py.
Aufruf: python3 reel19_gameday.py -> reel19_gameday.mp4 + reel19_post.jpg (4:5) + reel19_story.jpg
"""
import math
import os
import subprocess
import time
import wave

import cairocffi as cairo
import numpy as np
from PIL import Image, ImageFilter

import puck3d_dark as P3
import reel15_puck as R15
from reel15_puck import (W, H, FPS, SPP, KSUB, SHUTTER, c01, smooth, sio, e_out, e_in, lerp, sph, line_img, reveal,
                         put, surface, surf_rgba, over, proj, PHI2)
from reel18_dangle import word_img, vignette, bloom

DUR = 12.0
HERE = R15.HERE
WHITE = (250, 250, 252)
RED = (235, 30, 42)
GOLD = (250, 205, 30)
P = np.array([130.0, 0.5, -60.0])                 # freies Eis im Mittelkreis (nicht auf der roten Linie)
T_LAND = 0.42
UP = np.array([0.0, 1.0, 0.0])
CUTS = [1.0, 3.0, 3.5, 5.5]


# ================================================================= Logos
def _load(name):
    return Image.open(os.path.join(HERE, "brand", "gameday", f"{name}_cut.png")).convert("RGBA")


LOGO = {"devil": _load("devil"), "pirates": _load("pirates")}
_GLOW = {}


def glow_of(name, col):
    key = (name, col)
    if key not in _GLOW:
        im = LOGO[name]
        pad = 90
        a = Image.new("L", (im.width + 2 * pad, im.height + 2 * pad), 0)
        a.paste(im.getchannel("A"), (pad, pad))
        g = Image.new("RGBA", a.size, col + (0,))
        g.putalpha(a.filter(ImageFilter.GaussianBlur(34)).point(lambda v: min(255, int(v * 1.6))))
        sh = Image.new("RGBA", a.size, (0, 0, 0, 0))
        sh.putalpha(a.filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(v * 0.7)))
        g.alpha_composite(sh, (6, 14))
        _GLOW[key] = (g, pad)
    return _GLOW[key]


def draw_logo(L, name, cx, cy, h, alpha, col, glow=1.0):
    if alpha <= 0 or h < 4:
        return
    im = LOGO[name]
    s = h / im.height
    g, pad = glow_of(name, col)
    gw, gh = max(1, int(g.width * s)), max(1, int(g.height * s))
    gi = g.resize((gw, gh), Image.BILINEAR)
    ga = min(1.0, alpha * glow)
    if ga < 1:
        gi.putalpha(gi.getchannel("A").point(lambda v: int(v * ga)))
    put(L, gi, cx - gw / 2, cy - gh / 2)
    li = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    if alpha < 1:
        li.putalpha(li.getchannel("A").point(lambda v: int(v * alpha)))
    put(L, li, cx - li.width / 2, cy - li.height / 2)


def _puck_tex():
    im = LOGO["devil"]
    s = max(im.size)
    sq = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    sq.paste(im, ((s - im.width) // 2, (s - im.height) // 2))
    sq = sq.transpose(Image.FLIP_LEFT_RIGHT).resize((256, 256), Image.LANCZOS)
    return np.ascontiguousarray(np.asarray(sq).astype(np.float32) / 255)


PUCK_TEX = _puck_tex()


# ================================================================= Puck + Kamera
def puck_state(t):
    if t < T_LAND:
        y = 0.5 + 0.5 * 386 * (T_LAND - t) ** 2
    else:
        y = 0.5 + 0.25 * math.sin(math.pi * c01((t - T_LAND) / 0.12))
    th = 1.15 + 0.9 * max(0.0, t - T_LAND) * math.exp(-max(0.0, t - T_LAND) * 0.15)
    return np.array([P[0], y, P[2]]), th


def shot(t):
    if t < 1.0:
        u = t / 1.0
        return sph(P, lerp(17, 13, u), 250, lerp(7, 10, u)), P + UP * 1.2, UP, 40, 0.06
    if t < 3.0:
        u = (t - 1.0) / 2.0
        return sph(P, lerp(40, 26, sio(u)), lerp(200, 320, sio(u)), lerp(10, 24, u)), P + UP, UP, 44, 0.05
    if t < 3.5:
        u = (t - 3.0) / 0.5
        return sph(P, 18, lerp(330, 420, e_out(u, 3)), 5), P + UP, UP, 46, 0.03
    if t < 5.5:
        u = (t - 3.5) / 2.0
        return sph(P, lerp(24, 17, u), lerp(130, 80, sio(u)), lerp(4, 11, u)), P + UP, UP, 42, 0.05
    u = (t - 5.5) / (DUR - 5.5)
    return sph(P, lerp(330, 260, sio(u)), lerp(80, 125, u), lerp(62, 74, sio(u))), P, UP, 40, 0.0


def shake(t):
    off = np.zeros(3)
    for ts, amp in ((T_LAND, 1.0), (1.0, 1.4), (3.0, 2.2), (3.5, 1.4), (5.5, 6.0), (6.0, 9.0), (9.0, 6.0)):
        lt = t - ts
        if 0 <= lt < 0.6:
            e = amp * math.exp(-lt * 8)
            off += np.array([math.sin(lt * 91), math.cos(lt * 77), math.sin(lt * 63)]) * e
    return off


def seg_of(t):
    return sum(1 for c in CUTS if t >= c)


def cam_row_at(t):
    pos, tgt, up, fov, ap = shot(t)
    pos = pos + shake(t) * (0.15 if t < 5.5 else 1.0)
    r, u_, f = P3.look_at(pos, tgt, up)
    return P3.cam_row(pos, r, u_, f, fov), ap, float(np.linalg.norm(tgt - pos))


def render3d(t, fidx):
    sg = seg_of(t)
    lo = ([0.0] + CUTS)[sg]
    hi = (CUTS + [DUR])[sg]
    cams, lens, pk = np.zeros((KSUB, 13)), np.zeros((KSUB, 2)), np.zeros((KSUB, 7))
    for j in range(KSUB):
        tk = min(max(t + ((j + 0.5) / KSUB - 0.5) * SHUTTER, lo), hi - 1e-4)
        row, ap, focus = cam_row_at(tk)
        cams[j], lens[j] = row, (ap, focus)
        p, th = puck_state(tk)
        pk[j] = (p[0], p[1], p[2], th, 1.0, 0.0, tk)
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, SPP, fidx + 19, cams, lens, pk, PUCK_TEX, base, puck, cov)
    return P3.tonemap(base), P3.tonemap(puck), cov


# ================================================================= Effekte
def bolt_pts(a, b, seed, levels=6, rough=0.22):
    rng = np.random.default_rng(seed)
    pts = [np.array(a, float), np.array(b, float)]
    disp = np.linalg.norm(np.array(b) - np.array(a)) * rough
    for _ in range(levels):
        new = [pts[0]]
        for p, q in zip(pts[:-1], pts[1:]):
            m = (p + q) / 2
            d = q - p
            n = np.array([-d[1], d[0]]) / (np.linalg.norm(d) + 1e-9)
            new += [m + n * rng.normal(0, disp), q]
        pts = new
        disp *= 0.55
    return np.array(pts)


def bolt(ctx, a, b, seed, width, col, alpha=1.0):
    pts = bolt_pts(a, b, seed)
    for c, al, wd in ((col, 0.12, width * 7), (col, 0.45, width * 2.6), ((255, 255, 255), 1.0, width * 0.8)):
        R15.stroke_poly(ctx, pts, c, al * alpha, wd)
    rng = np.random.default_rng(seed + 999)
    for _ in range(3):                                          # Verästelungen
        i = int(rng.integers(len(pts) // 5, len(pts) * 4 // 5))
        d = pts[min(i + 8, len(pts) - 1)] - pts[i]
        end = pts[i] + np.array([d[0] * 3 + rng.normal(0, 60), d[1] * 3]) * rng.uniform(0.6, 1.2)
        br = bolt_pts(pts[i], end, seed + i, 4, 0.3)
        R15.stroke_poly(ctx, br, col, 0.35 * alpha, width * 1.4)
        R15.stroke_poly(ctx, br, (255, 255, 255), 0.8 * alpha, width * 0.4)


EMB = np.random.default_rng(66).random((80, 6))


def embers(ctx, t, amt):
    if amt <= 0:
        return
    for e in EMB:
        sp = 90 + 200 * e[1]
        y = H + 60 - ((t * sp + e[2] * H * 1.5) % (H * 1.45))
        x = e[0] * W + 40 * math.sin(t * (0.8 + e[3]) + e[4] * 6)
        r = 2 + 4 * e[5]
        fl = 0.55 + 0.45 * math.sin(t * 13 + e[4] * 20)
        col = (1.0, 0.25 + 0.35 * e[3], 0.08)
        ctx.set_source_rgba(*col, 0.12 * amt * fl)
        ctx.arc(x, y, r * 4, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgba(1.0, 0.75, 0.4, 0.9 * amt * fl)
        ctx.arc(x, y, r * 0.7, 0, 2 * math.pi)
        ctx.fill()


def impact_ring(ctx, cam, t):
    li = t - T_LAND
    if 0 <= li < 0.5:
        q = e_out(li / 0.5, 3)
        ring = np.stack([P[0] + 48 * q * np.cos(PHI2), np.full_like(PHI2, 0.05), P[2] + 48 * q * np.sin(PHI2)], 1)
        xy, z = proj(cam, ring)
        if (z > 1).all():
            R15.stroke_poly(ctx, xy, RED, 0.9 * (1 - q), 6)


def fx(t, cam):
    s, ctx = surface()
    embers(ctx, t, smooth(0.9, 1.3, t))
    impact_ring(ctx, cam, t)
    if 3.0 <= t < 3.5:                                          # VS-Blitz quer durchs Bild
        sd = int(t * 30) // 2
        bolt(ctx, (W * 0.85, -40), (W * 0.2, H + 40), 400 + sd, 9, (255, 200, 80), 1 - smooth(3.38, 3.5, t))
    if t >= 5.5:                                                # Blitz zwischen den Logos
        a = smooth(5.55, 5.7, t)
        sd = int(t * 30) // 3
        fl = 0.75 + 0.25 * math.sin(t * 40)
        bolt(ctx, (W / 2 + 10, 520), (W / 2 - 10, 1000), 700 + sd, 5, (255, 190, 70), a * fl)
    return surf_rgba(s)


# ================================================================= Text + Logos
def slam(t, t0, dur=0.14, s0=1.7):
    lt = t - t0
    if lt < 0:
        return 0.0, 1.0
    return c01(lt / 0.05), lerp(s0, 1.0, e_out(c01(lt / dur), 3))


def word_at(L, txt, size, col, glow, cx, cy, t, t0, t1=None, s0=1.6):
    a, sc = slam(t, t0, s0=s0)
    if t1 is not None:
        a *= 1 - smooth(t1 - 0.08, t1, t)
    if a <= 0:
        return
    img = word_img(txt, size, col, glow)
    im = img.resize((max(1, int(img.width * sc)), max(1, int(img.height * sc))), Image.BILINEAR)
    if a < 1:
        im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    put(L, im, cx - im.width / 2, cy - im.height / 2)


def layer(t):
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    beat = math.exp(-((t * 2) % 1) * 6) if 1.0 <= t else 0.0
    # 0–1: TESTSPIEL
    if t < 1.0:
        a = 1.0 - smooth(0.92, 1.0, t)
        img = word_img("TESTSPIEL.", 170, WHITE, RED)
        sc = 1 + 0.05 * t
        im = img.resize((int(img.width * sc), int(img.height * sc)), Image.BILINEAR)
        if a < 1:
            im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
        put(L, im, W / 2 - im.width / 2, 560 - im.height / 2)
        reveal(L, line_img("EISTEUFEL FRANKFURT", 34, 700, (215, 215, 225), track=10), W / 2, 700, smooth(0.15, 0.35, t),
               smooth(0.85, 0.98, t))
    # 1–3: Eisteufel
    if 1.0 <= t < 3.0:
        a, sc = slam(t, 1.0, 0.16, 1.8)
        draw_logo(L, "devil", W / 2, 760, 640 * sc * (1 + 0.02 * beat), a * (1 - smooth(2.92, 3.0, t)), RED, 0.9 + 0.3 * beat)
        word_at(L, "EISTEUFEL", 190, WHITE, RED, W / 2, 1230, t, 1.12, 3.0)
        reveal(L, line_img("FRANKFURT", 56, 800, RED, track=24), W / 2, 1345, smooth(1.3, 1.45, t), smooth(2.9, 3.0, t))
    # 3–3.5: VS.
    if 3.0 <= t < 3.5:
        word_at(L, "VS.", 380, WHITE, (255, 190, 70), W / 2, 800, t, 3.0, 3.5, 2.2)
    # 3.5–5.5: Pirates
    if 3.5 <= t < 5.5:
        a, sc = slam(t, 3.5, 0.16, 1.8)
        draw_logo(L, "pirates", W / 2, 760, 640 * sc * (1 + 0.02 * beat), a * (1 - smooth(5.42, 5.5, t)), GOLD, 0.8 + 0.3 * beat)
        word_at(L, "PIRATES", 200, WHITE, GOLD, W / 2, 1230, t, 3.62, 5.5)
        reveal(L, line_img("EC WALLERNHAUSEN", 50, 800, GOLD, track=14), W / 2, 1345, smooth(3.8, 3.95, t),
               smooth(5.4, 5.5, t))
    # ab 5.5: Duell-Karte
    if t >= 5.5:
        q = e_out(c01((t - 5.5) / 0.28), 4)
        bump = 1 + 0.025 * beat
        draw_logo(L, "devil", lerp(-300, 245, q), 760, 400 * bump, 1.0, RED, 0.85 + 0.3 * beat)
        draw_logo(L, "pirates", lerp(W + 300, 835, q), 760, 400 * bump, 1.0, GOLD, 0.7 + 0.3 * beat)
        word_at(L, "VS.", 120, WHITE, (255, 190, 70), W / 2, 770, t, 5.65, None, 2.0)
        reveal(L, line_img("TESTSPIEL", 40, 800, RED, track=22), W / 2, 300, smooth(5.6, 5.8, t))
        word_at(L, "24.10.", 270, WHITE, RED, W / 2, 1125, t, 6.0, None, 1.9)
        word_at(L, "18:30 UHR", 120, WHITE, RED, W / 2, 1290, t, 6.5, None, 1.6)
        reveal(L, line_img("EISSPORTHALLE LAUTERBACH", 44, 800, (225, 225, 232), track=8), W / 2, 1385,
               smooth(7.0, 7.2, t))
        word_at(L, "KOMMT VORBEI!", 130, WHITE, RED, W / 2, 430, t, 9.0, None, 1.7)
    return L


# ================================================================= Bild
def compose(t, fidx):
    base, puck, cov = render3d(t, fidx)
    row, _, _ = cam_row_at(t)
    pa = cov[..., None]
    img = base * (1 - pa) + puck * pa
    img = img * np.array([1.06, 0.9, 0.9], np.float32)          # Teufels-Rot
    img = over(img, *fx(t, row))
    if t >= 5.5:                                                     # Hintergrund für die Karte abdunkeln
        img = img * (1 - 0.45 * smooth(5.5, 5.8, t))
    img = bloom(img)
    lc = min([t - c for c in CUTS + [6.0, 9.0] if t >= c] + [t + 0.5])
    li = t - T_LAND
    if lc < 0.1:
        img = img + (1 - lc / 0.1) * 0.35
    if 0 <= li < 0.08:
        img = img + (1 - li / 0.08) * 0.25
    zp = 1 + 0.06 * math.exp(-lc * 14)
    img = np.clip(img, 0, 1)
    pil = Image.fromarray((img * 255).astype(np.uint8))
    if zp > 1.002:
        w2, h2 = W / zp, H / zp
        pil = pil.transform((W, H), Image.EXTENT, ((W - w2) / 2, (H - h2) / 2, (W + w2) / 2, (H + h2) / 2), Image.BILINEAR)
    arr = np.asarray(pil).astype(np.float32) / 255
    ca = int(round(10 * math.exp(-lc * 12)))
    if ca:
        arr[..., 0] = np.roll(arr[..., 0], ca, 1)
        arr[..., 2] = np.roll(arr[..., 2], -ca, 1)
    L = layer(t)
    ta = np.asarray(L).astype(np.float32) / 255
    arr = arr * (1 - ta[..., 3:4]) + ta[..., :3] * ta[..., 3:4]
    arr = arr * vignette()
    arr += np.random.default_rng(fidx).normal(0, 0.012, arr.shape[:2])[..., None]
    return (np.clip(arr, 0, 1) * 255).astype(np.uint8)


# ================================================================= Sound (Phonk, 120 BPM)
SR = 44100


def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(19)
    mus, sfx = np.zeros(n), np.zeros(n)

    def tt(sec):
        return np.arange(int(sec * SR)) / SR

    def put_(buf, sig, at, vol=1.0):
        st = int(round(at * SR))
        e = min(n, st + len(sig))
        if st < n:
            buf[st:e] += sig[: e - st] * vol

    def lp(x, k):
        c = np.cumsum(np.concatenate([np.zeros(k), x]))
        return (c[k:] - c[:-k]) / k

    def hp(x, k):
        return x - lp(x, k)

    def noise(sec):
        return rng.standard_normal(int(sec * SR))

    def kick(vol=1.0):
        x = tt(0.35)
        f = 45 + 160 * np.exp(-x * 35)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 9) * 3.0) * vol

    def snare(vol=1.0):
        x = tt(0.3)
        return (np.sin(2 * np.pi * 185 * x) * np.exp(-x * 30) * 0.6 + hp(noise(0.3), 3) * np.exp(-x * 18)) * 0.6 * vol

    def hat(vol=0.18):
        return hp(noise(0.04), 2) * np.exp(-tt(0.04) * 120) * vol

    def bass808(freq, dur, glide=0.0):
        x = tt(dur)
        f = freq * (1 + glide * np.exp(-x * 8))
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * 2.5) * np.minimum(x / 0.005, 1) * np.exp(-x * 1.6) * 0.8

    def cowbell(freq, dur=0.25, vol=0.25):
        x = tt(dur)
        sig = np.sign(np.sin(2 * np.pi * freq * x)) + np.sign(np.sin(2 * np.pi * freq * 1.48 * x))
        return lp(sig, 3) * np.exp(-x * 14) * vol

    def whoosh(dur=0.4, vol=1.0):
        x = tt(dur)
        nz = noise(dur)
        env = np.sin(np.pi * x / dur) ** 2
        return (lp(nz, 30) * (1 - x / dur) + (lp(nz, 5) - lp(nz, 30)) * (x / dur) * 1.4) * env * 1.3 * vol

    def boom(dur=1.2, f0=45, vol=1.0):
        x = tt(dur)
        f = f0 + 110 * np.exp(-x * 14)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 3) * 2.2) * vol

    def crack(vol=1.0):
        x = tt(0.4)
        body = np.sin(2 * np.pi * np.cumsum(240 * (1 + 2 * np.exp(-x * 80))) / SR) * np.exp(-x * 18)
        return np.tanh((body + hp(noise(0.4), 2) * np.exp(-x * 60) * 1.4) * 1.8) * vol

    def thunder(dur=1.4, vol=1.0):
        x = tt(dur)
        nz = noise(dur)
        snap = hp(nz, 2) * np.exp(-x * 25) * 1.2
        rumble = lp(nz, 60) * 6 * np.exp(-x * 2.2) * (1 + 0.5 * np.sin(2 * np.pi * 7 * x))
        return np.tanh((snap + rumble) * 1.5) * vol

    def riser(dur, vol=1.0):
        x = tt(dur)
        sw = np.sin(2 * np.pi * np.cumsum(200 + 2200 * (x / dur) ** 2) / SR) * (x / dur) ** 3 * 0.15
        return (hp(noise(dur), 4) * (x / dur) ** 2 * 0.4 + sw) * vol

    def horn(dur=2.0):
        x = tt(dur)
        sig = sum(2 * ((x * f * (1 + 0.003 * np.sin(2 * np.pi * 4.5 * x))) % 1) - 1 for f in (110.0, 138.6, 164.8))
        return lp(lp(sig, 10), 6) / 3 * np.minimum(x / 0.05, 1) * np.clip((dur - x) / 0.3, 0, 1) * 0.7

    def crowd(dur, vol):
        x = tt(dur)
        return lp(noise(dur), 14) * 3 * (0.8 + 0.2 * np.sin(2 * np.pi * 0.7 * x)) * vol

    B = 0.5
    notes = [55.0, 55.0, 65.4, 49.0]
    bell = [880.0, 880.0, 1046.5, 987.8, 880.0, 784.0, 880.0, 659.3]
    for k in range(int(DUR / B)):
        tb = k * B
        if tb < 1.0 or 3.0 <= tb < 3.5 or tb >= 11.5:
            continue
        put_(mus, kick(), tb)
        if k % 2 == 1:
            put_(mus, snare(), tb)
        for j in range(4):
            put_(mus, hat(0.2 if j % 2 == 0 else 0.12), tb + j * B / 4)
        if k % 4 == 3:
            for j in range(4):
                put_(mus, hat(0.12), tb + B / 2 + j * B / 8)
        put_(mus, bass808(notes[(k // 2) % 4], 0.48, 0.6 if k % 4 == 0 else 0.0), tb)
        put_(mus, cowbell(bell[k % 8] / 2, 0.22, 0.2), tb + 0.25)
    put_(sfx, whoosh(0.45, 0.8), 0.0)
    put_(sfx, crack(1.1), T_LAND)
    put_(sfx, boom(0.8, 50, 0.7), T_LAND)
    put_(sfx, riser(0.55, 0.8), 0.45)
    for c in (1.0, 3.5, 5.5, 6.0, 9.0):
        put_(sfx, boom(1.3, 40, 1.1), c)
        put_(sfx, whoosh(0.25, 0.6), c - 0.15)
    put_(sfx, thunder(1.6, 1.3), 3.0)
    put_(sfx, crack(0.7), 6.5)
    put_(sfx, crack(0.5), 7.0)
    put_(sfx, horn(2.2), 9.0)
    put_(sfx, crowd(3.0, 0.7) * np.exp(-tt(3.0) * 0.6), 9.0)
    put_(sfx, boom(1.5, 38, 0.9), 11.5)

    mix = mus * 0.75 + sfx
    mix /= np.percentile(np.abs(mix), 99.9) + 1e-9
    mix = np.tanh(mix * 1.1)
    mix *= np.clip((DUR - np.arange(n) / SR) / 0.4, 0, 1)
    mix = mix / np.max(np.abs(mix)) * 0.95
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


def stills():
    """Feed-Post (4:5) und Story aus dem Schlussbild."""
    fr = Image.fromarray(compose(11.0, 9999))
    fr.save("reel19_story.jpg", quality=92)
    fr.crop((0, 175, W, 175 + 1350)).save("reel19_post.jpg", quality=92)


def main():
    os.chdir(HERE)
    make_audio("audio_gameday.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_gameday.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "21",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
           "reel19_gameday.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    stills()
    print("fertig: reel19_gameday.mp4")


if __name__ == "__main__":
    main()
