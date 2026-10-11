"""Reel 17: THE PERFECT GOAL – TikTok-Edit-Version (dunkle Arena, Schnitte auf den Beat, 13 s).

Gleicher Spielzug wie Reel 16 (Puckweg aus reel16_goal.py), aber geschnitten wie ein Hockey-Edit:
  0.0–3.0   Dangle in 6 Einstellungen à 0,5 s ("WATCH THIS." / LEFT. / RIGHT. / LEFT.)
  3.0–5.5   SAUCER: Zeitlupe, Kamera umkreist den fliegenden Puck
  5.5–7.0   ONE-TIMER: Peitschenschwenk, Verfolgung
  7.0–7.5   Kamera hinter dem Netz – Puck schlägt direkt vor der Linse ein ("TOP SHELF.")
  7.5–9.0   Torlicht-Stroboskop, Orbit ums Tor
  9.0–11.0  Replay: Neonspur des Spielzugs in der Draufsicht
  11.0–13.0 "RATE IT 1–10"
Renderer: puck3d_dark.py. Aufruf: python3 reel17_edit.py -> reel17_edit.mp4
"""
import math
import os
import subprocess
import time
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import puck3d_dark as P3
import reel15_puck as R15
import reel16_goal as G
from reel15_puck import (W, H, FPS, SPP, KSUB, SHUTTER, ORANGE, c01, smooth, sio, e_out, e_in, e_back, lerp, sph,
                         line_img, reveal, put, proj, projected, px_per_in, stroke_poly, partial, surface, surf_rgba,
                         over, PHI2, GOAL_X)

DUR = 13.0
HERE = R15.HERE
WHITE = (250, 250, 252)
RED = (255, 40, 50)
NEON = (255, 120, 30)
GA = G.GA
TOP_C = np.array([424.0, 0.0, 0.0])


# ================================================================= Puck (Story-Zeit tau)
def pstate(tau):
    p = G.puck_raw(tau)
    th = G.THETA0 + float(np.interp(tau, G.SPIN_T, G.SPIN_A))
    return p, th


def fwd(tau, dt=0.03):
    v = G.puck_raw(tau + dt) - G.puck_raw(tau - dt)
    v[1] = 0
    n = np.linalg.norm(v)
    return v / n if n > 1e-6 else np.array([1.0, 0, 0])


def side(f):
    return np.array([-f[2], 0.0, f[0]])


UP = np.array([0.0, 1.0, 0.0])
SHOT_D = G.HIT_P - G.SHOT_A
SHOT_D /= np.linalg.norm(SHOT_D)


# ================================================================= Einstellungen (Rigs)
def rig_front(tau, u, s=1.0):
    p, _ = pstate(tau)
    f = fwd(tau)
    pos = p + f * (13 - 3 * u) + side(f) * 3 * s + UP * 1.3
    return pos, p, UP, 40, 0.05


def rig_side(tau, u, s=1.0):
    p, _ = pstate(tau)
    f = fwd(tau)
    pos = p + side(f) * 13 * s + f * (-5 + 10 * u) + UP * 2.2
    return pos, p + f * 2, UP, 42, 0.04


def rig_top(tau, u):
    p, _ = pstate(tau)
    th = 1.2 + 2.6 * u
    up = np.array([math.cos(th), 0.0, math.sin(th)])
    return p + UP * (30 - 8 * u) + np.array([0.01, 0, 0]), p, up, 44, 0.0


def rig_chase(tau, u):
    p, _ = pstate(tau)
    f = fwd(tau)
    return p - f * 10 + UP * 2.4 + side(f) * 1.5, p + f * 12, UP, 46, 0.03


def rig_orbit(tau, u):
    p, _ = pstate(tau)
    az = lerp(250, 610, sio(u))
    el = lerp(-22, 38, sio(u))
    return sph(p, 11.0, az, el), p, UP, 40, 0.06


def rig_whip(tau, u):
    p, _ = pstate(tau)
    az0 = math.degrees(math.atan2(-SHOT_D[2], -SHOT_D[0]))
    az = lerp(az0 + 130, az0, e_out(u, 3))
    return sph(p, 13.0, az, 8), p, UP, 46, 0.03


def rig_shot(tau, u):
    p, _ = pstate(tau)
    d = SHOT_D.copy()
    return p - d * 18 + UP * 3.5, p + d * 40, UP, 50, 0.0


def rig_netcam(tau, u):
    p, _ = pstate(tau)
    pos = np.array([GOAL_X + 52.0, 30.0, -26.0])
    return pos, p * 0.7 + np.array([GOAL_X - 40, 24.0, 0.0]) * 0.3, UP, 46, 0.0


def rig_celebrate(tau, u):
    return sph(GA, lerp(220, 180, u), lerp(155, 210, sio(u)), lerp(12, 24, u)), GA, UP, 50, 0.0


def rig_top_replay(tau, u):
    h = R15.TOP_H * lerp(1.04, 0.98, u)
    return TOP_C + np.array([-0.5, h, 0]), TOP_C.copy(), np.array([1.0, 0, 0]), 30, 0.0


def rig_cta(tau, u):
    c = TOP_C + (np.array([GOAL_X - 150, 0, 0]) - TOP_C) * e_in(u, 2)
    h = R15.TOP_H * lerp(0.98, 0.42, e_in(u, 2))
    return c + np.array([-0.5, h, 0]), c, np.array([1.0, 0, 0]), 30, 0.0


#        v0,   v1,   tau0,  tau1,  rig,                         Wort
SHOTS = [(0.0, 0.5, 1.30, 1.75, lambda t, u: rig_front(t, u, 1), "WATCH THIS."),
         (0.5, 1.0, 1.75, 2.15, lambda t, u: rig_side(t, u, 1), "LEFT."),
         (1.0, 1.5, 2.15, 2.90, rig_top, None),
         (1.5, 2.0, 2.90, 3.40, rig_chase, "RIGHT."),
         (2.0, 2.5, 3.40, 4.10, lambda t, u: rig_front(t, u, -1), None),
         (2.5, 3.0, 4.10, 4.75, lambda t, u: rig_side(t, u, -1), "LEFT."),
         (3.0, 5.5, 4.75, 8.40, rig_orbit, "SAUCER."),
         (5.5, 6.0, 8.40, 8.95, rig_whip, "ONE-TIMER."),
         (6.0, 7.0, 8.95, 10.30, rig_shot, None),
         (7.0, 7.5, 10.30, 10.66, rig_netcam, "TOP SHELF."),
         (7.5, 9.0, 10.66, 12.2, rig_celebrate, None),
         (9.0, 11.0, 12.2, 12.2, rig_top_replay, "REPLAY"),
         (11.0, 13.0, 12.2, 12.2, rig_cta, None)]
CUTS = [s[0] for s in SHOTS[1:]]


def shot_at(t):
    for k, s in enumerate(SHOTS):
        if s[0] <= t < s[1]:
            return k
    return len(SHOTS) - 1


def tau_of(k, t):
    v0, v1, a, b = SHOTS[k][:4]
    u = c01((t - v0) / (v1 - v0))
    if k == 6:                                      # Zeitlupe in der Mitte des Saucers
        u = u + 0.12 * math.sin(2 * math.pi * u)
    if k == 8:                                      # Speed-Ramp beim Schuss
        u = u ** 1.25
    return a + (b - a) * u, c01((t - v0) / (v1 - v0))


def state(t, k=None):
    k = shot_at(t) if k is None else k
    tau, u = tau_of(k, t)
    pos, tgt, up, fov, ap = SHOTS[k][4](tau, u)
    p, th = pstate(tau)
    vis = 1.0 if k < 11 else (1.0 if tau < 16 else 0.0)
    return k, tau, pos, tgt, up, fov, ap, p, th, vis


def shake(t):
    off = np.zeros(3)
    for ts, amp in ((7.45, 4.0), (5.95, 1.5), (0.0, 0.6)):
        lt = t - ts
        if 0 <= lt < 0.6:
            e = amp * math.exp(-lt * 8)
            off += np.array([math.sin(lt * 91), math.cos(lt * 77), math.sin(lt * 63)]) * e
    return off


def cam_row_at(t, k=None):
    k, tau, pos, tgt, up, fov, ap, p, th, vis = state(t, k)
    pos = pos + shake(t) * (0.15 if k < 11 else 3.0)
    r, u_, f = P3.look_at(pos, tgt, up)
    return P3.cam_row(pos, r, u_, f, fov), ap, float(np.linalg.norm(tgt - pos)), (p, th, vis, k, tau)


def render3d(t, fidx):
    k = shot_at(t)
    v0, v1 = SHOTS[k][:2]
    cams, lens, pk = np.zeros((KSUB, 13)), np.zeros((KSUB, 2)), np.zeros((KSUB, 7))
    for j in range(KSUB):
        tk = min(max(t + ((j + 0.5) / KSUB - 0.5) * SHUTTER, v0), v1 - 1e-4)
        row, ap, focus, (p, th, vis, _, _) = cam_row_at(tk, k)
        cams[j], lens[j] = row, (ap, focus)
        pk[j] = (p[0], p[1], p[2], th, vis, 0.0, tk)
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, SPP, fidx + 7, cams, lens, pk, R15.logo_tex(), base, puck, cov)
    return P3.tonemap(base), P3.tonemap(puck), cov


# ================================================================= Overlays
def neon_trail(ctx, cam, tau, k):
    if k >= 11 or tau < 1.35:
        return
    ts = np.linspace(max(1.3, tau - 0.3), tau, 24)
    pts = np.array([G.puck_raw(x) for x in ts])
    pts[:, 1] = np.maximum(pts[:, 1] - 0.45, 0.03)
    xy, z = proj(cam, pts)
    if (z < 0.6).any() or len(xy) < 2:
        return
    w = float(np.clip(1.4 * px_per_in(cam, z[-1]), 4, 60))
    stroke_poly(ctx, xy, NEON, 0.18, w * 2.2)
    stroke_poly(ctx, xy, NEON, 0.55, w * 0.9)
    stroke_poly(ctx, xy, (255, 220, 170), 0.9, max(2.0, w * 0.25))


def scratches(ctx, cam):
    pos = cam[0:3]
    if pos[1] > 300:
        return
    for pl, a in G.SCRATCHES:
        dist = np.linalg.norm(pl[0] - pos)
        if dist > 200:
            continue
        xy, z = proj(cam, pl)
        if (z < 0.6).any():
            continue
        wd = float(np.clip(0.05 * px_per_in(cam, z.mean()), 0.6, 3.0))
        stroke_poly(ctx, xy, (150, 175, 220), a * 0.6 * (1 - dist / 200), wd)


def fx(ctx, t, cam, tau, k):
    # Eisspray bei den Haken
    for n_, td in enumerate(G.DEKES):
        tv = None
        for kk in range(6):
            a, b = SHOTS[kk][2:4]
            if a <= td < b:
                tv = SHOTS[kk][0] + (td - a) / (b - a) * 0.5
        if tv is not None and 0 <= t - tv < 0.5 and shot_at(t) == shot_at(tv):
            p = G.puck_raw(td)
            G.spray(ctx, cam, (t - tv) + td, td, p + np.array([0, 0.3, 0]), -fwd(td), 30 + n_, 80, 1.1)
    # Schuss: Ringe
    if k in (7, 8) and 8.9 <= tau < 9.4:
        pp, zp = projected(cam, G.SHOT_A)
        if zp > 0.5:
            q = e_out((tau - 8.9) / 0.5, 3)
            for col, rmax, wdt in ((NEON, 380, 9), (WHITE, 240, 3)):
                ctx.set_source_rgba(col[0] / 255, col[1] / 255, col[2] / 255, (1 - q) * 0.9)
                ctx.set_line_width(wdt * (1 - q) + 1)
                ctx.arc(pp[0], pp[1], 30 + rmax * q, 0, 2 * math.pi)
                ctx.stroke()
    # Tor: Funken
    if k in (9, 10) and tau >= G.T_HIT:
        li = tau - G.T_HIT
        r_ = G.rv(90, 77)
        for i in range(90):
            lt = li - r_[i, 0] * 0.05
            if lt < 0 or lt > 0.8:
                continue
            v = np.array([-(10 + r_[i, 1] * 60), 15 + r_[i, 2] * 60, (r_[i, 3] - 0.5) * 90])
            p = G.HIT_P + v * lt + np.array([0, -0.5 * 300 * lt * lt, 0])
            xy, z = proj(cam, [p, p - v * 0.02])
            if (z > 1).all():
                stroke_poly(ctx, xy, (255, 196, 70), 0.95 * (1 - lt / 0.8), 3.5)


def replay(ctx, t, cam):
    if t < 9.0:
        return
    fr = smooth(9.15, 10.5, t)
    xy, z = proj(cam, G.TRAIL)
    if fr <= 0 or not (z > 5).all():
        return
    pl = partial(xy, fr)
    stroke_poly(ctx, pl, NEON, 0.15, 34)
    stroke_poly(ctx, pl, NEON, 0.5, 14)
    stroke_poly(ctx, pl, (255, 230, 190), 1.0, 5)
    head = pl[-1]
    ctx.set_source_rgba(1, 1, 1, 1)
    ctx.arc(head[0], head[1], 9, 0, 2 * math.pi)
    ctx.fill()
    for f_, _, _ in G.MARKS:
        if fr >= f_ - 0.001:
            idx = min(len(xy) - 1, int(f_ * (len(xy) - 1)))
            kk = e_back(c01((fr - f_) / 0.08), 2.4)
            ctx.set_source_rgba(1, 1, 1, 1)
            ctx.arc(xy[idx][0], xy[idx][1], 11 * kk, 0, 2 * math.pi)
            ctx.fill()


def replay_labels(L, t, cam):
    if not 9.0 <= t < 11.2:
        return
    fr = smooth(9.15, 10.5, t)
    xy, z = proj(cam, G.TRAIL)
    if not (z > 5).all():
        return
    out = smooth(10.9, 11.1, t)
    for f_, txt, sd in G.MARKS:
        if fr >= f_ - 0.001:
            idx = min(len(xy) - 1, int(f_ * (len(xy) - 1)))
            p = xy[idx]
            reveal(L, line_img(txt, 32, 800, WHITE, track=2), p[0] + (26 if sd > 0 else -26), p[1],
                   smooth(0, 0.08, fr - f_ + 0.001), out, "l" if sd > 0 else "r")


# ---------------- Wörter (Slam auf jeden Schnitt)
_WORDS = {}


def word_img(txt, size, col):
    key = (txt, size, col)
    if key not in _WORDS:
        img = line_img(txt, size, 900, col)
        pad = 40
        sh = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
        a = Image.new("L", sh.size, 0)
        a.paste(img.getchannel("A"), (pad, pad))
        glow = Image.new("RGBA", sh.size, NEON + (0,))
        glow.putalpha(a.filter(ImageFilter.GaussianBlur(16)).point(lambda v: min(255, int(v * 1.3))))
        dark = Image.new("RGBA", sh.size, (0, 0, 0, 0))
        dark.putalpha(a.filter(ImageFilter.GaussianBlur(5)).point(lambda v: int(v * 0.6)))
        sh.alpha_composite(glow)
        sh.alpha_composite(dark, (4, 8))
        sh.alpha_composite(img, (pad, pad))
        _WORDS[key] = sh
    return _WORDS[key]


def words(L, t):
    k = shot_at(t)
    v0, v1, _, _, _, w = SHOTS[k]
    if w and k < 12:
        lt = t - v0
        size = 210 if len(w) <= 6 else (170 if len(w) <= 10 else 150)
        col = RED if w == "TOP SHELF." else WHITE
        img = word_img(w, size, col)
        sc = (1.0 if k == 0 else lerp(1.6, 1.0, e_out(lt / 0.12, 3))) * (1 + 0.04 * (t - v0))
        a = (1.0 if k == 0 else c01(lt / 0.05)) * (1 - smooth(v1 - 0.06, v1, t) if k != 6 else 1 - smooth(5.3, 5.5, t))
        im = img.resize((int(img.width * sc), int(img.height * sc)), Image.BILINEAR)
        if a < 1:
            im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
        y = 520 if k < 11 else 300
        put(L, im, W / 2 - im.width / 2, y - im.height / 2)
    if k == 6 and t > 3.4:
        reveal(L, line_img("SLOW-MO", 34, 700, (200, 205, 220), track=8), W / 2, 660, smooth(3.4, 3.6, t), smooth(5.3, 5.5, t))
    if t >= 11.0:
        reveal(L, word_img("RATE IT", 190, WHITE), W / 2, 470, smooth(11.05, 11.25, t))
        reveal(L, word_img("1 – 10?", 230, NEON), W / 2, 680, smooth(11.2, 11.4, t))
        reveal(L, line_img("COMMENT YOUR SCORE", 40, 700, (210, 214, 226), 4), W / 2, 850, smooth(11.4, 11.6, t))


# ================================================================= Bild
_VIG = None


def vignette():
    global _VIG
    if _VIG is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2) * 2
        _VIG = (1 - 0.45 * np.clip(r - 0.45, 0, 1) ** 1.3)[..., None]
    return _VIG


def bloom(img):
    br = np.clip(img - 0.62, 0, None)
    small = Image.fromarray((np.clip(br, 0, 1) * 255).astype(np.uint8)).resize((W // 6, H // 6), Image.BILINEAR)
    b1 = np.asarray(small.filter(ImageFilter.GaussianBlur(3)).resize((W, H), Image.BILINEAR)).astype(np.float32) / 255
    b2 = np.asarray(small.filter(ImageFilter.GaussianBlur(10)).resize((W, H), Image.BILINEAR)).astype(np.float32) / 255
    return img + b1 * 0.7 + b2 * 0.8


def compose(t, fidx):
    base, puck, cov = render3d(t, fidx)
    row, ap, focus, (p, th, vis, k, tau) = cam_row_at(t)
    sc, sctx = surface()
    scratches(sctx, row)
    img = over(base, *surf_rgba(sc))
    tr, tctx = surface()
    neon_trail(tctx, row, tau, k)
    img = over(img, *surf_rgba(tr))
    pa = cov[..., None]
    netcam = k == 9
    if k >= 7 and k <= 12:
        nb, nf = R15.draw_net(row, tau, False), R15.draw_net(row, tau, True)
        b_ = surf_rgba(nb)
        f_ = surf_rgba(nf)
        inside = p[0] > GOAL_X - 0.5
        if not netcam:
            img = over(img, *b_)
            if not inside:
                img = over(img, *f_)
        img = img * (1 - pa) + puck * pa
        if netcam:
            img = over(img, *b_)
        if inside or netcam:
            img = over(img, *f_)
    else:
        img = img * (1 - pa) + puck * pa
    fs, ctx = surface()
    fx(ctx, t, row, tau, k)
    replay(ctx, t, row)
    img = over(img, *surf_rgba(fs))
    # Torlicht-Stroboskop
    if k in (9, 10) and tau >= G.T_HIT:
        li = tau - G.T_HIT
        strobe = 0.5 + 0.5 * math.cos(li * 2 * math.pi * 3.2)
        a = 0.32 * strobe * math.exp(-li * 0.6)
        img = img * (1 - a) + np.array([1.0, 0.08, 0.1], np.float32) * a
    img = bloom(img)
    # Schnitt-Blitz + Zoom-Punch + Farbversatz
    lc = min([t - c for c in CUTS if t >= c] + [t + 0.5])
    if lc < 0.1:
        img = img + (1 - lc / 0.1) * 0.35
    zp = 1 + 0.07 * math.exp(-lc * 14)
    img = np.clip(img, 0, 1)
    pil = Image.fromarray((img * 255).astype(np.uint8))
    if zp > 1.002:
        w2, h2 = W / zp, H / zp
        pil = pil.transform((W, H), Image.EXTENT, ((W - w2) / 2, (H - h2) / 2, (W + w2) / 2, (H + h2) / 2), Image.BILINEAR)
    arr = np.asarray(pil).astype(np.float32) / 255
    ca = int(round(10 * math.exp(-lc * 12) + (12 if k == 9 and tau >= G.T_HIT - 0.02 else 0) * math.exp(-max(0, tau - G.T_HIT) * 20)))
    if ca:
        arr[..., 0] = np.roll(arr[..., 0], ca, 1)
        arr[..., 2] = np.roll(arr[..., 2], -ca, 1)
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    words(L, t)
    replay_labels(L, t, row)
    ta = np.asarray(L).astype(np.float32) / 255
    arr = arr * (1 - ta[..., 3:4]) + ta[..., :3] * ta[..., 3:4]
    arr = arr * vignette()
    arr += np.random.default_rng(fidx).normal(0, 0.012, arr.shape[:2])[..., None]
    return (np.clip(arr, 0, 1) * 255).astype(np.uint8)


# ================================================================= Sound (Phonk/Trap, 120 BPM)
SR = 44100


def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(17)
    mus, sfx = np.zeros(n), np.zeros(n)

    def tt(sec):
        return np.arange(int(sec * SR)) / SR

    def put_(buf, sig, at, vol=1.0):
        st = int(round(at * SR))
        if st < 0:
            sig, st = sig[-st:], 0
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

    def scrape(dur=0.35, vol=0.7):
        x = tt(dur)
        return hp(noise(dur), 2) * np.exp(-x * 8) * vol

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
        if 3.0 <= tb < 5.5 or tb >= 11.0 and tb < 12.0:
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
    # Zeitlupe: Herzschlag + gedehnter Bass
    for hb in (3.1, 3.9, 4.7):
        put_(sfx, boom(0.35, 42, 0.7), hb)
        put_(sfx, boom(0.3, 42, 0.45), hb + 0.18)
    put_(sfx, bass808(41.2, 2.4, 0.0) * 0.6, 3.0)
    put_(sfx, riser(0.5, 0.9), 5.0)
    for c in CUTS:
        put_(sfx, whoosh(0.22, 0.6), c - 0.12)
    for tv in (0.75, 1.75, 2.75):
        put_(sfx, scrape(0.35, 0.8), tv)
    put_(sfx, crack(1.2), 5.95)
    put_(sfx, boom(1.2, 44, 1.0), 5.95)
    put_(sfx, whoosh(0.5, 1.0), 6.9)
    put_(sfx, lp(noise(0.4), 18) * np.exp(-tt(0.4) * 8) * 1.5, 7.45)
    put_(sfx, boom(1.8, 38, 1.3), 7.45)
    put_(sfx, horn(2.2), 7.5)
    put_(sfx, crowd(3.0, 0.7) * np.exp(-tt(3.0) * 0.5), 7.5)
    put_(sfx, riser(1.4, 0.7), 9.0)
    put_(sfx, boom(1.0, 50, 0.8), 11.0)

    mix = mus * 0.75 + sfx
    mix /= np.percentile(np.abs(mix), 99.9) + 1e-9
    mix = np.tanh(mix * 1.1)
    mix = mix / np.max(np.abs(mix)) * 0.95
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


def main():
    os.chdir(HERE)
    make_audio("audio_edit.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_edit.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "19",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
           "reel17_edit.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(7.55, 9999)).save("reel17_thumbnail.jpg", quality=92)
    print("fertig: reel17_edit.mp4")


if __name__ == "__main__":
    main()
