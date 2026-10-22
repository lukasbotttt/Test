"""Gameday-Post + Story: Eisteufel Frankfurt vs. EC Wallernhausen Pirates (Testspiel, Sa 24.10., 18:30, Lauterbach).

Idee: Puck liegt im Mittelkreis, das Eis ist geteilt – links Teufels-Rot, rechts Piraten-Gelb, dazwischen ein
Blitz. Unten ein abreißbares Eintrittsticket mit den Spieldaten. Daten wie im Ankündigungs-Reel 19 (Plakat).
Renderer: puck3d_dark.py (Standbild, viele Samples). Aufruf: python3 gameday_post.py -> gameday_post.jpg, gameday_story.jpg
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import puck3d_dark as P3
import reel19_gameday as G
from reel15_puck import line_img, put
from reel18_dangle import word_img

HERE = os.path.dirname(os.path.abspath(__file__))
W = 1080
RED = (235, 30, 42)
GOLD = (250, 205, 30)
WHITE = (250, 250, 252)
INK = (24, 22, 30)
CREAM = (246, 243, 236)


def render_bg(H, dist, el, ty, spp=48):
    P = G.P
    pos = G.sph(P, dist, 250, el)
    r, u, f = P3.look_at(pos, P + np.array([0, ty, 0]), np.array([0.0, 1, 0]))
    row = P3.cam_row(pos, r, u, f, 40)
    blank = np.zeros((256, 256, 4), np.float32)                  # Puck ohne Aufdruck (sauberes Gummi)
    pk = np.array([[P[0], 0.5, P[2], 3.15, 1.0, 0.0, 5.0]])
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, spp, 24, row[None], np.array([[0.05, dist]]), pk, blank, base, puck, cov)
    img = P3.tonemap(base) * (1 - cov[..., None]) + P3.tonemap(puck) * cov[..., None]
    # geteiltes Licht: links rot, rechts gelb, weicher diagonaler Übergang
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    s = np.clip((xx - W / 2 + (yy - H * 0.55) * 0.18) / 220 + 0.5, 0, 1)[..., None]
    tint = (1 - s) * np.array([1.35, 0.55, 0.55], np.float32) + s * np.array([1.3, 1.08, 0.45], np.float32)
    img = img * (0.55 + 0.45 * tint) + (1 - s) * np.array([0.10, 0.0, 0.01]) * 0.6 + s * np.array([0.09, 0.07, 0.0]) * 0.6
    return np.clip(img, 0, 1).astype(np.float32), row


def bolt_layer(H, a, b, seed):
    import cairocffi as cairo
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    G.bolt(ctx, np.array(a, float), np.array(b, float), seed, 9, (255, 236, 200), 0.95)
    G.bolt(ctx, np.array(a, float), np.array(b, float), seed + 3, 4, (255, 255, 255), 0.7)
    buf = np.ndarray((H, W, 4), np.uint8, surf.get_data()).copy()
    im = Image.fromarray(buf[..., [2, 1, 0, 3]], "RGBA")
    glow = im.filter(ImageFilter.GaussianBlur(14))
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.alpha_composite(glow)
    out.alpha_composite(glow)
    out.alpha_composite(im)
    return out


def bloom(img):
    """Weiches Leuchten der hellen Stellen (beliebige Bildhöhe)."""
    hi = np.clip(img - 0.55, 0, 1)
    pil = Image.fromarray((hi * 255).astype(np.uint8))
    b1 = np.asarray(pil.filter(ImageFilter.GaussianBlur(12))).astype(np.float32) / 255
    b2 = np.asarray(pil.filter(ImageFilter.GaussianBlur(40))).astype(np.float32) / 255
    return img + b1 * 0.6 + b2 * 0.7


def logo(L, name, cx, cy, h, col):
    G.draw_logo(L, name, cx, cy, h, 1.0, col, 1.0)


def ticket(L, cx, cy, w=900, h=250, ang=-3.0):
    """Eintrittsticket mit Abriss-Perforation."""
    s = 2
    stub = 200
    im = Image.new("RGBA", ((w + 80) * s, (h + 80) * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x0, y0 = 40 * s, 40 * s
    d.rounded_rectangle((x0, y0, x0 + w * s, y0 + h * s), 22 * s, fill=CREAM + (255,))
    px = x0 + (w - stub) * s                                   # Perforation mit Kerben oben/unten
    for yy in (y0, y0 + h * s):
        d.ellipse((px - 18 * s, yy - 18 * s, px + 18 * s, yy + 18 * s), fill=(0, 0, 0, 0))
    for k in range(12):
        y = y0 + 26 * s + k * (h - 52) * s / 11
        d.ellipse((px - 4 * s, y - 4 * s, px + 4 * s, y + 4 * s), fill=(150, 146, 140, 255))
    d.rectangle((x0, y0 + 22 * s, x0 + 12 * s, y0 + h * s - 22 * s), fill=RED + (255,))
    im = im.resize((w + 80, h + 80), Image.LANCZOS)
    cols = [("BULLY", "18:30 UHR", 130), ("ORT", "EISSPORTHALLE", 395), ("", "LAUTERBACH", 395)]
    put(im, line_img("BULLY", 26, 800, (140, 136, 130), track=8), 40 + 50, 40 + 40)
    put(im, line_img("18:30", 92, 900, INK), 40 + 46, 40 + 78)
    put(im, line_img("UHR", 30, 900, RED, track=6), 40 + 52, 40 + 186)
    put(im, line_img("ORT", 26, 800, (140, 136, 130), track=8), 40 + 330, 40 + 40)
    put(im, line_img("EISSPORTHALLE", 40, 900, INK, track=2), 40 + 328, 40 + 86)
    put(im, line_img("LAUTERBACH", 40, 900, INK, track=2), 40 + 328, 40 + 134)
    put(im, line_img("TESTSPIEL", 26, 900, RED, track=8), 40 + 330, 40 + 190)
    del cols
    # Abriss-Abschnitt: hochkant
    st = Image.new("RGBA", (h - 40, stub - 30), (0, 0, 0, 0))
    t1 = line_img("SA 24.10.", 46, 900, INK)
    t2 = line_img("BLADES & PUCKS", 17, 800, (140, 136, 130), track=3)
    put(st, t1, st.width / 2 - t1.width / 2, 30)
    put(st, t2, st.width / 2 - t2.width / 2, 108)
    st = st.rotate(90, expand=True, resample=Image.BICUBIC)
    put(im, st, 40 + w - stub + 15 + (stub - 15) / 2 - st.width / 2, 40 + h / 2 - st.height / 2)
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sh.putalpha(im.getchannel("A").filter(ImageFilter.GaussianBlur(16)).point(lambda v: int(v * 0.6)))
    im2 = Image.new("RGBA", (im.width + 40, im.height + 40), (0, 0, 0, 0))
    im2.alpha_composite(sh, (20, 34))
    im2.alpha_composite(im, (20, 10))
    im2 = im2.rotate(ang, expand=True, resample=Image.BICUBIC)
    put(L, im2, cx - im2.width / 2, cy - im2.height / 2)


def brand(L, y):
    import reel33_lines_neon as N
    im = N.brand_img("bladesandpucks_lockup_transparent.png", 250).img
    put(L, im, W / 2 - im.width / 2, y - im.height / 2)


def make(H, out, lay):
    img, row = render_bg(H, *lay["cam"])
    from reel15_puck import projected
    pxy, _ = projected(row, G.P + np.array([0.0, 1.2, 0.0]))
    img = bloom(img)
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    L.alpha_composite(bolt_layer(H, (W / 2 + 30, lay["bolt"]), (float(pxy[0]), float(pxy[1]) - 10), 11))
    brand(L, lay["brand"])
    k = line_img("SAMSTAG  ·  24.10.", 40, 800, WHITE, track=14)
    put(L, k, W / 2 - k.width / 2, lay["kick"] - k.height / 2)
    gd = word_img("GAMEDAY", 220, WHITE, RED)
    gd = gd.resize((min(gd.width, 1100), int(gd.height * min(gd.width, 1100) / gd.width)), Image.LANCZOS)
    put(L, gd, W / 2 - gd.width / 2, lay["title"] - gd.height / 2)
    ly = lay["logos"]
    logo(L, "devil", 245, ly, lay["lh"], RED)
    logo(L, "pirates", 835, ly, lay["lh"], GOLD)
    vs = word_img("VS.", 110, WHITE, (255, 190, 70))
    put(L, vs, W / 2 - vs.width / 2, ly - 30 - vs.height / 2)
    for txt, cx, col in (("EISTEUFEL", 245, RED), ("PIRATES", 835, GOLD)):
        im = line_img(txt, 40, 900, WHITE, track=6)
        put(L, im, cx - im.width / 2, ly + lay["lh"] / 2 + 24)
    ticket(L, W / 2, lay["ticket"])
    cta = word_img(lay["cta"], 76, WHITE, RED)
    put(L, cta, W / 2 - cta.width / 2, lay["cta_y"] - cta.height / 2)
    arr = np.asarray(L).astype(np.float32) / 255
    img = img * (1 - arr[..., 3:4]) + arr[..., :3] * arr[..., 3:4]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2) * 2
    img = img * (1 - 0.5 * np.clip(r - 0.5, 0, 1) ** 1.3)[..., None]
    img += np.random.default_rng(3).normal(0, 0.012, img.shape[:2])[..., None]
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(out, quality=93)
    print("fertig:", out)


STORY = dict(cam=(34, 14, 1.0), brand=150, kick=330, title=470, logos=880, lh=360, bolt=640,
             ticket=1540, cta="AUF GEHT'S, TEUFEL!", cta_y=1790)
POST = dict(cam=(26, 17, 1.9), brand=95, kick=210, title=340, logos=650, lh=300, bolt=470,
            ticket=1105, cta="AUF GEHT'S, TEUFEL!", cta_y=1290)

if __name__ == "__main__":
    os.chdir(HERE)
    import sys
    spp = int(os.environ.get("SPP", "48"))
    if len(sys.argv) < 2 or sys.argv[1] == "story":
        make(1920, "gameday_story.jpg", STORY)
    if len(sys.argv) < 2 or sys.argv[1] == "post":
        make(1350, "gameday_post.jpg", POST)
