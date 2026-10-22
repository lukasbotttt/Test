"""Gameday-Post + Story: Eisteufel Frankfurt vs. EC Wallernhausen Pirates (Testspiel, Sa 24.10., 18:30, Lauterbach).

Look "Matchday-Plakat": dunkles 3D-Eis, Spotlicht von oben auf den Puck, Teamfarben als Streulicht von den Seiten
(links Rot, rechts Gold), metallische Headline (Archivo Expanded), Logos mit Schatten und Farbschein,
Eintrittsticket aus Papier mit Perforation. Daten wie im Ankündigungs-Reel 19 (Plakat).
Renderer: puck3d_dark.py (Standbild). Aufruf: python3 gameday_post.py [story|post] -> gameday_story.jpg, gameday_post.jpg
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import puck3d_dark as P3
import reel19_gameday as G
from reel15_puck import projected

HERE = os.path.dirname(os.path.abspath(__file__))
W = 1080
RED = (226, 28, 40)
GOLD = (246, 196, 32)
WHITE = (246, 246, 249)
SILVER = (196, 200, 210)
INK = (22, 21, 28)
PAPER = (244, 240, 232)
OFF_Y = {1350: -285.0}                                                        # Korrektur je Format (gemessen)
FONT = {"x9": "ArchivoX900.ttf", "x8": "ArchivoX800.ttf", "a7": "Archivo700.ttf", "m7": "JBMono700.ttf",
        "m5": "JBMono500.ttf"}
_F = {}


# ================================================================= Typo
def font(fk, size):
    key = (fk, size)
    if key not in _F:
        _F[key] = ImageFont.truetype(os.path.join(HERE, "fonts", FONT[fk]), size)
    return _F[key]


def text_mask(txt, fk, size, track=0.0):
    f = font(fk, size)
    ws = [f.getlength(c) for c in txt]
    tw = int(sum(ws) + track * size * (len(txt) - 1)) + 4
    asc, desc = f.getmetrics()
    m = Image.new("L", (tw + 8, asc + desc + 8), 0)
    d = ImageDraw.Draw(m)
    x = 4
    for c, w in zip(txt, ws):
        d.text((x, 4), c, font=f, fill=255)
        x += w + track * size
    return m.crop(m.getbbox())


def text(txt, fk, size, col, track=0.0, a=255):
    m = text_mask(txt, fk, size, track)
    im = Image.new("RGBA", m.size, col + (0,))
    im.putalpha(m.point(lambda v: v * a // 255))
    return im


def metal(txt, fk, size, track=0.0):
    """Headline mit gebürstetem Metallverlauf, feiner Kante und weichem Schatten."""
    m = text_mask(txt, fk, size, track)
    h = m.height
    top, mid, bot = np.array([255, 255, 255.0]), np.array([214, 218, 228.0]), np.array([150, 156, 170.0])
    col = np.zeros((h, m.width, 3))
    for y in range(h):
        u = y / max(h - 1, 1)
        c = top + (mid - top) * (u / 0.55) if u < 0.55 else mid + (bot - mid) * ((u - 0.55) / 0.45)
        col[y] = c
    col += np.random.default_rng(5).normal(0, 3.0, (1, m.width, 1))          # Bürstung
    fill = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    fill.putalpha(m)
    pad = 40
    out = Image.new("RGBA", (m.width + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
    a = Image.new("L", out.size, 0)
    a.paste(m, (pad, pad))
    sh.putalpha(a.filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * 0.75)))
    out.alpha_composite(sh, (0, 12))
    edge = Image.new("RGBA", out.size, (255, 255, 255, 0))                    # helle Oberkante
    edge.putalpha(a.filter(ImageFilter.GaussianBlur(1)).point(lambda v: int(v * 0.5)))
    out.alpha_composite(edge, (0, -2))
    out.alpha_composite(fill, (pad, pad))
    return out


def put(dst, im, cx, cy):
    dst.alpha_composite(im, (int(round(cx - im.width / 2)), int(round(cy - im.height / 2))))


# ================================================================= Hintergrund
def puck_cam(H, dist, el, target_y):
    """Kamera so wählen, dass der Puck bei target_y (Pixel) liegt."""
    P = G.P
    pos = G.sph(P, dist, 250, el)
    best = None
    for ty in np.linspace(-8, 8, 161):
        r, u, f = P3.look_at(pos, P + np.array([0, ty, 0]), np.array([0.0, 1, 0]))
        row = P3.cam_row(pos, r, u, f, 38)
        xy, _ = projected_h(row, P + np.array([0, 0.5, 0]), H)
        err = abs(xy[1] - target_y)
        if best is None or err < best[0]:
            best = (err, row, xy)
    return best[1], best[2]


def projected_h(row, p, H):
    """projected() rechnet mit 1920 px Höhe – für andere Formate umrechnen."""
    xy, z = projected(row, p)
    return np.array([xy[0], xy[1] + OFF_Y.get(H, 0.0)]), z


def render_bg(H, dist, el, puck_y, spp=64):
    row, pxy = puck_cam(H, dist, el, puck_y)
    P = G.P
    blank = np.zeros((256, 256, 4), np.float32)
    pk = np.array([[P[0], 0.5, P[2], 3.15, 1.0, 0.0, 5.0]])
    base = np.zeros((H, W, 3), np.float32)
    puck = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    P3.render(W, H, spp, 24, row[None], np.array([[0.04, dist]]), pk, blank, base, puck, cov)
    img = P3.tonemap(base) * (1 - cov[..., None]) + P3.tonemap(puck) * cov[..., None]
    img = img * 0.62
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    px, py = float(pxy[0]), float(pxy[1])
    # Spotlicht: Kegel von oben + heller Lichtfleck um den Puck
    half = 60 + (yy / py) * 230
    cone = np.clip(1 - np.abs(xx - px) / np.maximum(half, 1), 0, 1) ** 1.6 * np.clip(yy / py, 0, 1.1) ** 0.8
    cone *= (yy < py + 60)
    cone = np.asarray(Image.fromarray((cone * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(30)),
                      np.float32) / 255
    pool = np.exp(-(((xx - px) / 300) ** 2 + ((yy - py - 10) / 95) ** 2))
    ice = (1 - cov)[..., None]                                   # Puck selbst nicht überstrahlen
    img = img + (cone[..., None] * np.array([0.13, 0.13, 0.15]) + pool[..., None] * np.array([0.26, 0.26, 0.29])) * ice
    img = img + cov[..., None] * cone[..., None] * 0.05
    # Teamfarben als Streulicht von den Seiten
    for cx, col in ((-160, RED), (W + 160, GOLD)):
        g = np.exp(-(((xx - cx) / 520) ** 2 + ((yy - H * 0.5) / (H * 0.42)) ** 2))
        img = img + g[..., None] * (np.array(col, np.float32) / 255) * 0.30
    # Eiskristalle im Licht
    rng = np.random.default_rng(24)
    sp = np.zeros((H, W), np.float32)
    for _ in range(170):
        y = rng.uniform(0, py)
        x = px + rng.uniform(-1, 1) * (60 + y / py * 230)
        r = rng.uniform(1.0, 3.2)
        y0, y1, x0, x1 = int(max(0, y - 6)), int(min(H, y + 7)), int(max(0, x - 6)), int(min(W, x + 7))
        sy, sx = np.mgrid[y0:y1, x0:x1]
        sp[y0:y1, x0:x1] += np.exp(-((sx - x) ** 2 + (sy - y) ** 2) / (r * r)) * rng.uniform(0.2, 0.8)
    img = img + sp[..., None] * 0.35
    return np.clip(img, 0, 1).astype(np.float32), (px, py)


# ================================================================= Elemente
def logo(L, name, cx, cy, h, col):
    im = G.LOGO[name]
    im = im.resize((int(im.width * h / im.height), int(h)), Image.LANCZOS)
    pad = 120
    a = Image.new("L", (im.width + 2 * pad, im.height + 2 * pad), 0)
    a.paste(im.getchannel("A"), (pad, pad))
    aura = Image.new("RGBA", a.size, col + (0,))
    aura.putalpha(a.filter(ImageFilter.GaussianBlur(60)).point(lambda v: int(min(255, v * 0.9))))
    sh = Image.new("RGBA", a.size, (0, 0, 0, 0))
    sh.putalpha(a.filter(ImageFilter.GaussianBlur(18)).point(lambda v: int(v * 0.8)))
    out = Image.new("RGBA", a.size, (0, 0, 0, 0))
    out.alpha_composite(aura)
    out.alpha_composite(sh, (0, 20))
    out.alpha_composite(im, (pad, pad))
    put(L, out, cx, cy)


def vs_badge(L, cx, cy, d=124):
    s = 3
    im = Image.new("RGBA", ((d + 40) * s, (d + 40) * s), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    c = (d + 40) * s / 2
    r = d * s / 2
    dr.ellipse((c - r, c - r, c + r, c + r), fill=(14, 13, 18, 215), outline=(235, 235, 240, 255), width=3 * s)
    r2 = r - 9 * s
    dr.ellipse((c - r2, c - r2, c + r2, c + r2), outline=(255, 255, 255, 70), width=1 * s)
    im = im.resize((d + 40, d + 40), Image.LANCZOS)
    t = text("VS", "x9", 44, WHITE, 0.04)
    put(im, t, im.width / 2, im.height / 2 + 1)
    put(L, im, cx, cy)


def rule(L, cx, cy, w, col=(255, 255, 255), a=110):
    dr = ImageDraw.Draw(L)
    dr.line((cx - w / 2, cy, cx + w / 2, cy), fill=col + (a,), width=2)


def kicker(L, txt, cy, line_w=90):
    t = text(txt, "m7", 26, (230, 230, 236), 0.42)
    put(L, t, W / 2, cy)
    rule(L, W / 2 - t.width / 2 - 30 - line_w / 2, cy, line_w)
    rule(L, W / 2 + t.width / 2 + 30 + line_w / 2, cy, line_w)


def ticket(L, cx, cy, w=920, h=260, ang=-2.5):
    s = 2
    stub = 210
    pad = 40
    im = Image.new("RGBA", ((w + 2 * pad) * s, (h + 2 * pad) * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = pad * s, pad * s, (pad + w) * s, (pad + h) * s
    d.rounded_rectangle((x0, y0, x1, y1), 18 * s, fill=PAPER + (255,))
    px = x0 + (w - stub) * s
    for yy in (y0, y1):
        d.ellipse((px - 17 * s, yy - 17 * s, px + 17 * s, yy + 17 * s), fill=(0, 0, 0, 0))
    for k in range(13):
        y = y0 + 28 * s + k * (h - 56) * s / 12
        d.ellipse((px - 3.5 * s, y - 3.5 * s, px + 3.5 * s, y + 3.5 * s), fill=(176, 170, 160, 255))
    ins = 13 * s                                                     # feine Innenlinie
    d.rounded_rectangle((x0 + ins, y0 + ins, px - 24 * s, y1 - ins), 8 * s, outline=(196, 190, 180, 255), width=s)
    d.rounded_rectangle((px + 24 * s, y0 + ins, x1 - ins, y1 - ins), 8 * s, outline=(196, 190, 180, 255), width=s)
    d.rectangle((x0 + ins + 10 * s, y0 + ins + 26 * s, x0 + ins + 16 * s, y1 - ins - 26 * s), fill=RED + (255,))
    im = im.resize((w + 2 * pad, h + 2 * pad), Image.LANCZOS)
    arr = np.asarray(im).astype(np.float32)                          # Papierstruktur
    n = np.random.default_rng(9).normal(0, 4.0, arr.shape[:2])
    n = np.asarray(Image.fromarray(np.clip(n + 128, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7)),
                   np.float32) - 128
    arr[..., :3] += n[..., None] * (arr[..., 3:4] > 0)
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    lab = (150, 144, 134)
    lx = pad + 58
    im.alpha_composite(text("BULLY", "m7", 17, lab, 0.3), (lx, pad + 40))
    im.alpha_composite(text("18:30", "x9", 76, INK, 0.0), (lx - 2, pad + 84))
    im.alpha_composite(text("UHR", "x8", 24, RED, 0.25), (lx, pad + 190))
    dx = pad + 372
    ImageDraw.Draw(im).line((dx - 26, pad + 44, dx - 26, pad + h - 44), fill=(200, 194, 184, 255), width=2)
    im.alpha_composite(text("SPIELORT", "m7", 17, lab, 0.3), (dx, pad + 40))
    im.alpha_composite(text("EISSPORTHALLE", "x8", 27, INK, 0.02), (dx, pad + 86))
    im.alpha_composite(text("LAUTERBACH", "x8", 27, INK, 0.02), (dx, pad + 124))
    im.alpha_composite(text("TESTSPIEL", "x8", 20, RED, 0.3), (dx, pad + 190))
    sx = pad + w - stub / 2 + 10
    for t, y in ((text("SAMSTAG", "m7", 16, lab, 0.3), pad + 58), (text("24", "x9", 96, INK), pad + 128),
                 (text("OKTOBER", "x8", 20, RED, 0.25), pad + 200)):
        put(im, t, sx, y)
    sh = Image.new("RGBA", (im.width + 60, im.height + 60), (0, 0, 0, 0))
    a = Image.new("L", sh.size, 0)
    a.paste(im.getchannel("A"), (30, 30))
    sh.putalpha(a.filter(ImageFilter.GaussianBlur(22)).point(lambda v: int(v * 0.75)))
    out = Image.new("RGBA", sh.size, (0, 0, 0, 0))
    out.alpha_composite(sh, (0, 22))
    out.alpha_composite(im, (30, 30))
    out = out.rotate(ang, expand=True, resample=Image.BICUBIC)
    put(L, out, cx, cy)


# ================================================================= Layout
def make(H, out, lay):
    img, (px, py) = render_bg(H, lay["dist"], lay["el"], lay["puck"])
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    kicker(L, "TESTSPIEL", lay["kick"])
    g = metal("GAMEDAY", "x9", lay["gsize"], 0.0)
    if g.width > 1040:                                            # inkl. 40 px Schattenrand je Seite -> ~960 px Schrift
        g = g.resize((1040, int(g.height * 1040 / g.width)), Image.LANCZOS)
    put(L, g, W / 2, lay["title"])
    d = text("SAMSTAG, 24. OKTOBER", "a7", 32, SILVER, 0.22)
    put(L, d, W / 2, lay["date"])
    ImageDraw.Draw(L).rectangle((W / 2 - 34, lay["date"] + 34, W / 2 + 34, lay["date"] + 39), fill=RED + (255,))
    ly, lh = lay["logos"], lay["lh"]
    logo(L, "devil", 262, ly, lh, RED)
    logo(L, "pirates", 818, ly, lh, GOLD)
    vs_badge(L, W / 2, ly)
    for name, sub, cx in (("EISTEUFEL", "FRANKFURT", 262), ("PIRATES", "WALLERNHAUSEN", 818)):
        put(L, text(name, "x8", 38, WHITE, 0.06), cx, ly + lh / 2 + 52)
        put(L, text(sub, "m7", 19, SILVER, 0.36), cx, ly + lh / 2 + 92)
    ticket(L, W / 2, lay["ticket"])
    c = text("AUF GEHT'S, EISTEUFEL!", "x9", lay["csize"], WHITE, 0.02)
    put(L, c, W / 2, lay["cta"])
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2) * 2
    img = img * (1 - 0.55 * np.clip(r - 0.55, 0, 1) ** 1.2)[..., None]
    arr = np.asarray(L).astype(np.float32) / 255
    img = img * (1 - arr[..., 3:4]) + arr[..., :3] * arr[..., 3:4]
    img += np.random.default_rng(3).normal(0, 0.010, img.shape[:2])[..., None]
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(out, quality=94, subsampling=0)
    print("fertig:", out)


STORY = dict(dist=30, el=13, puck=1268, kick=215, title=340, gsize=176, date=468, logos=800, lh=360,
             ticket=1555, cta=1800, csize=58)
POST = dict(dist=34, el=14, puck=880, kick=105, title=215, gsize=168, date=335, logos=590, lh=290,
            ticket=1085, cta=1285, csize=52)

if __name__ == "__main__":
    os.chdir(HERE)
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    if which in ("story", "both"):
        make(1920, "gameday_story.jpg", STORY)
    if which in ("post", "both"):
        make(1350, "gameday_post.jpg", POST)
