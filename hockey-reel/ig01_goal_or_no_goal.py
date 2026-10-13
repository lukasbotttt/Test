"""Instagram-Bild #1: GOAL OR NO GOAL? – 3D-Standbild im 4:5-Format (1080x1350), Kinolook mit Tiefenschärfe.

Puck liegt noch 0,3 Zoll auf der Torlinie (NHL-Regel 78.4: kein Tor, solange der Puck die Linie berührt).
Gerendert in doppelter Auflösung (Raytracer mit Linsenunschärfe für Eis + Puck, Torgestänge aus mesh3d mit
tiefenabhängiger Unschärfe), danach auf 1080x1350 verkleinert.
Aufruf: python3 ig01_goal_or_no_goal.py            -> ig01_goal_or_no_goal.jpg
        IGW=540 IGSPP=8 python3 ig01_goal_or_no_goal.py   (schnelle Vorschau)
"""
import math
import os

import cairocffi as cairo
import numpy as np
from PIL import Image, ImageFilter
from scipy.ndimage import gaussian_filter

import mesh3d as M3
import puck3d as P3
import reel15_puck as R15
import reel18_dangle as R18
import reel25_goalline as G

HERE = R15.HERE
W = int(os.environ.get("IGW", "2160"))
H = W * 5 // 4
S = W / 1080                                     # Layout in 1080er-Einheiten
SPP = int(os.environ.get("IGSPP", "96"))
OUT = os.environ.get("IGOUT", os.path.join(HERE, "ig01_goal_or_no_goal.jpg"))

CAM_POS = np.array([float(v) for v in os.environ.get("IGPOS", "1062,8.5,-32").split(",")])
CAM_TGT = np.array([float(v) for v in os.environ.get("IGTGT", "1070.2,1.6,-3").split(",")])
FOV = float(os.environ.get("IGFOV", "32"))
APERTURE = float(os.environ.get("IGAP", "0.45"))        # Linsenradius in Zoll
PUCK = np.array([G.HOOK_X, 0.5, G.PZ])
ROT = float(os.environ.get("IGROT", "2.0"))
INK, ORANGE = R15.INK, R15.ORANGE
RED, GREEN, HALO = G.RED, G.GREEN, G.HALO


def camera():
    r, u, f = P3.look_at(CAM_POS, CAM_TGT, np.array([0.0, 1.0, 0.0]))
    return P3.cam_row(CAM_POS, r, u, f, FOV), f


def depth(row, p):
    return float((np.asarray(p, float) - row[0:3]) @ row[9:12])


def coc_px(row, d, focus):
    """Radius des Unschärfekreises (Pixel) für Tiefe d bei Fokus auf `focus`."""
    px_per_in_focus = (H / 2) / (row[12] * focus)
    return APERTURE * abs(d - focus) / d * px_per_in_focus


def blur_layer(rgb, a, radius):
    if radius < 0.6:
        return rgb, a
    sig = float(radius) * 0.6
    return (gaussian_filter(rgb, (sig, sig, 0)).astype(np.float32),
            gaussian_filter(a, sig).astype(np.float32))


def net_layer(row, focus):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(s)
    ds = []
    for pl in G.NET:
        xy, z = P3.project(row, pl, W, H)
        if (z < 2).any():
            continue
        ds.append(z.mean())
        wdt = float(np.clip(0.42 * (H / 2) / (row[12] * z.mean()), 1.0, 6.0 * S))
        ctx.set_source_rgba(112 / 255, 120 / 255, 136 / 255, 0.55)
        ctx.set_line_width(wdt)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.move_to(*xy[0])
        for p in xy[1:]:
            ctx.line_to(*p)
        ctx.stroke()
    s.flush()
    a = np.frombuffer(s.get_data(), np.uint8).reshape(H, W, 4).astype(np.float32) / 255
    rgb, al = a[..., [2, 1, 0]], a[..., 3]
    return blur_layer(rgb, al, coc_px(row, float(np.median(ds)) if ds else focus, focus))


def word(txt, size, col):
    return R18.word_img(txt, int(size * S), col, HALO)


def line(txt, size, wght, col, track):
    return R15.line_img(txt, int(size * S), wght, col, track=track * S, cache=False)


def paste_c(L, im, cx, cy):
    L.alpha_composite(im, (int(round(cx - im.width / 2)), int(round(cy - im.height / 2))))


def main():
    row, f = camera()
    focus = depth(row, PUCK + np.array([0, 0.5, 0]))
    cams = row[None, :].copy()
    lens = np.array([[APERTURE, focus]])
    pk = np.array([[PUCK[0], PUCK[1], PUCK[2], ROT, 1.0, 0.0, 0.0]])
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, SPP, 7, cams, lens, pk, R15.logo_tex(), base, puck, cov)
    base, puck = P3.tonemap(base), P3.tonemap(puck)

    fr = G.FRAME
    near, far = fr[0:2], fr[2:]
    occ = G.cyl_mesh(PUCK - np.array([0, 0.5, 0]), 1.5, 1.0, "occluder", group=1)
    f_rgb, f_a, shadow, _ = M3.render(far + [occ], row, W, H, CAM_POS, alpha_by_group=np.array([1.0, 0.0], np.float32),
                                      shadow_light=(0.02, 1.0, -0.03))
    n_rgb, n_a, n_sh, _ = M3.render(near, row, W, H, CAM_POS, shadow_light=(0.02, 1.0, -0.03))
    zc = 36.0 + G.PR
    d_far = depth(row, np.array([G.GOAL_X, 10.0, zc]))
    d_near = depth(row, np.array([G.GOAL_X, 10.0, -zc]))
    f_rgb, f_a = blur_layer(f_rgb, f_a, coc_px(row, d_far, focus))
    n_rgb, n_a = blur_layer(n_rgb, n_a, coc_px(row, d_near, focus))
    sh = np.clip(shadow + n_sh, 0, 1)
    sh = np.asarray(Image.fromarray((sh * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6 * S)),
                    np.float32) / 255

    img = base * (1 - 0.15 * sh[..., None])
    nt_rgb, nt_a = net_layer(row, focus)
    img = img * (1 - nt_a[..., None]) + nt_rgb
    img = img * (1 - f_a[..., None]) + f_rgb
    pa = cov[..., None]
    img = img * (1 - pa) + puck * pa
    img = img * (1 - n_a[..., None]) + n_rgb

    # weicher heller Verlauf hinter der unteren Zeile (Lesbarkeit über der Torlinie)
    yy = np.arange(H, dtype=np.float32)[:, None, None]
    fade = np.clip((yy - H * 0.84) / (H * 0.12), 0, 1) ** 1.4 * 0.72
    img = img * (1 - fade) + np.array([0.95, 0.96, 0.98], np.float32) * fade

    # Typo
    pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    paste_c(L, line("NHL RULES EXPLAINED", 30, 800, ORANGE, 9), W / 2, 118 * S)
    paste_c(L, word("GOAL", 240, GREEN), W / 2, 285 * S)
    paste_c(L, word("OR", 64, INK), W / 2, 418 * S)
    paste_c(L, word("NO GOAL?", 150, RED), W / 2, 520 * S)
    paste_c(L, line("COMMENT YOUR CALL", 34, 850, INK, 7), W / 2, 1238 * S)
    paste_c(L, line("@BLADESANDPUCKS", 24, 700, (110, 114, 126), 6), W / 2, 1290 * S)
    pil.alpha_composite(L)

    arr = np.asarray(pil.convert("RGB")).astype(np.float32) / 255
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    v = np.clip(np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H * 0.55) / H) ** 2) * 2 - 0.55, 0, 1) ** 1.6
    arr = arr * (1 - 0.22 * v[..., None])
    arr += np.random.default_rng(1).normal(0, 0.006, arr.shape[:2])[..., None]
    out = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))
    if W > 1080:
        out = out.resize((1080, 1350), Image.LANCZOS)
    out.save(OUT, quality=95, subsampling=0)
    print("gespeichert:", OUT, out.size)


if __name__ == "__main__":
    main()
