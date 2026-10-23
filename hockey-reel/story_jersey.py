"""Story zu Reel 37: "Strafzettel fürs Trikot" – eingestecktes Löwen-Trikot mit angeklemmtem Penalty-Ticket.

Aufbau (1080x1920): Kicker "NEW REEL", Headline, Trikot (eingesteckt, rote Markierung) vor unscharfem Studio-Eis,
schräger Strafzettel mit Klammer, Freiraum für den Umfrage-Sticker "TUCK IT / LEAVE IT", "TAP TO WATCH".
Fakten wie im Reel: Rule 9.5 (Ausrüstung unter der Uniform), erst Verwarnung, dann 2 Minuten, seit 2026-27 wieder.
Aufruf: python3 story_jersey.py -> story_jersey.png / .jpg
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import cloth2d as C
import gameday_post as GP
import reel37_jersey as R

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1080, 1920
INK = (22, 21, 28)
RED = (225, 30, 40)
ORANGE = (240, 104, 20)
GREEN = (30, 160, 80)
PAPER = (250, 244, 214)                          # gelblicher Strafzettel


def put(dst, im, cx, cy):
    dst.alpha_composite(im, (int(round(cx - im.width / 2)), int(round(cy - im.height / 2))))


def background():
    os.environ.setdefault("BGSPP", "24")
    bg = R.bg_plate()
    im = Image.fromarray((np.clip(bg, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(10))
    arr = np.asarray(im).astype(np.float32) / 255
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2) * 2
    arr = arr * (1 - 0.35 * np.clip(r - 0.5, 0, 1))[..., None]
    return Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)).convert("RGBA")


def jersey_layer():
    kit, _ = C.frame(0.6, 1.0, 0.07)
    im = Image.fromarray((np.clip(kit, 0, 1) * 255).astype(np.uint8), "RGBA")
    sc = 0.86
    im = im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS)
    pad = 60
    out = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    a = Image.new("L", out.size, 0)
    a.paste(im.getchannel("A"), (pad, pad))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
    sh.putalpha(a.filter(ImageFilter.GaussianBlur(22)).point(lambda v: int(v * 0.45)))
    out.alpha_composite(sh, (0, 26))
    out.alpha_composite(im, (pad, pad))
    tuck = ((C.CX - 230) * sc + pad, (C.WAIST - 10) * sc + pad)
    return out, tuck


def dashed_ellipse(L, cx, cy, rx, ry, col, width=9, dash=26, gap=16):
    d = ImageDraw.Draw(L)
    n = int(2 * math.pi * max(rx, ry) / (dash + gap))
    for k in range(n):
        a0 = 2 * math.pi * k / n
        a1 = a0 + 2 * math.pi * dash / (dash + gap) / n
        pts = [(cx + rx * math.cos(a), cy + ry * math.sin(a)) for a in np.linspace(a0, a1, 8)]
        d.line(pts, fill=col + (255,), width=width)


def ticket():
    """Strafzettel (Knöllchen-Look) mit Klammer."""
    w, h = 560, 640
    s = 2
    im = Image.new("RGBA", ((w + 40) * s, (h + 90) * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x0, y0 = 20 * s, 60 * s
    d.rectangle((x0, y0, x0 + w * s, y0 + h * s), fill=PAPER + (255,))
    for k in range(int(w / 18)):                                          # gezackter Abriss unten
        xa = x0 + k * 18 * s
        d.polygon([(xa, y0 + h * s), (xa + 9 * s, y0 + (h + 10) * s), (xa + 18 * s, y0 + h * s)], fill=PAPER + (255,))
    d.rectangle((x0, y0, x0 + w * s, y0 + 92 * s), fill=RED + (255,))
    im = im.resize((w + 40, h + 90), Image.LANCZOS)
    arr = np.asarray(im).astype(np.float32)                               # Papierstruktur
    n = np.random.default_rng(7).normal(0, 5.0, arr.shape[:2])
    arr[..., :3] += n[..., None] * (arr[..., 3:4] > 0)
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    d = ImageDraw.Draw(im)
    x0, y0 = 20, 60
    put(im, GP.text("PENALTY TICKET", "x9", 40, (255, 255, 255), 0.04), x0 + w / 2, y0 + 47)
    lab = (120, 110, 80)
    rows = [("OFFENSE", "JERSEY TUCKED IN"), ("RULE", "9.5 · GEAR UNDER UNIFORM"), ("1ST TIME", "WARNING"),
            ("AFTER THAT", "2 MINUTES")]
    y = y0 + 130
    for i, (k, v) in enumerate(rows):
        im.alpha_composite(GP.text(k, "m7", 20, lab, 0.3), (x0 + 36, int(y)))
        col = RED if i == 3 else INK
        size = 40 if i < 3 else 52
        vv = GP.text(v, "x8", size, col, 0.01)
        if vv.width > w - 72:
            vv = vv.resize((w - 72, int(vv.height * (w - 72) / vv.width)), Image.LANCZOS)
        im.alpha_composite(vv, (x0 + 36, int(y + 32)))
        y += 32 + vv.height + 30
        if i < 3:
            for xx in range(x0 + 36, x0 + w - 36, 14):
                d.line((xx, y - 16, xx + 7, y - 16), fill=(190, 180, 150, 255), width=2)
    # Stempel
    st = Image.new("RGBA", (290, 116), (0, 0, 0, 0))
    sd = ImageDraw.Draw(st)
    sd.rounded_rectangle((6, 6, 284, 110), 14, outline=RED + (210,), width=7)
    put(st, GP.text("ENFORCED", "x9", 34, RED, 0.04, a=210), 145, 46)
    put(st, GP.text("SINCE 2026-27", "m7", 17, RED, 0.25, a=210), 145, 86)
    st = st.rotate(14, expand=True, resample=Image.BICUBIC)
    im.alpha_composite(st, (x0 + w - st.width - 24, y0 + h - st.height - 14))
    # Klammer oben
    cl = Image.new("RGBA", (im.width, 120), (0, 0, 0, 0))
    cd = ImageDraw.Draw(cl)
    cx = im.width // 2
    cd.rounded_rectangle((cx - 70, 6, cx + 70, 96), 18, fill=(150, 154, 164, 255), outline=(90, 94, 104, 255), width=4)
    cd.rounded_rectangle((cx - 46, 22, cx + 46, 60), 12, fill=(110, 114, 124, 255))
    im.alpha_composite(cl, (0, 0))
    sh = Image.new("RGBA", (im.width + 60, im.height + 60), (0, 0, 0, 0))
    a = Image.new("L", sh.size, 0)
    a.paste(im.getchannel("A"), (30, 30))
    sh.putalpha(a.filter(ImageFilter.GaussianBlur(18)).point(lambda v: int(v * 0.6)))
    out = Image.new("RGBA", sh.size, (0, 0, 0, 0))
    out.alpha_composite(sh, (12, 24))
    out.alpha_composite(im, (30, 30))
    return out.rotate(-8, expand=True, resample=Image.BICUBIC)


def chip(txt, col, fg=(255, 255, 255), size=30):
    t = GP.text(txt, "m7", size, fg, 0.3)
    im = Image.new("RGBA", (t.width + 56, t.height + 34), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, im.width - 1, im.height - 1), im.height // 2, fill=col + (255,))
    put(im, t, im.width / 2, im.height / 2)
    return im


def main():
    os.chdir(HERE)
    img = background()
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    put(L, chip("NEW REEL", RED), W / 2, 150)
    for txt, cy, size, col in (("THIS GETS YOU", 255, 84, INK), ("A PENALTY NOW.", 360, 104, RED)):
        im = GP.text(txt, "x9", size, col, 0.0)
        if im.width > 1000:
            im = im.resize((1000, int(im.height * 1000 / im.width)), Image.LANCZOS)
        halo = Image.new("RGBA", (im.width + 60, im.height + 60), (255, 255, 255, 0))
        a = Image.new("L", halo.size, 0)
        a.paste(im.getchannel("A"), (30, 30))
        halo.putalpha(a.filter(ImageFilter.GaussianBlur(14)).point(lambda v: min(255, int(v * 1.6))))
        put(L, halo, W / 2, cy)
        put(L, im, W / 2, cy)
    jl, (tx, ty) = jersey_layer()
    jx, jy = W / 2 - 150, 990
    put(L, jl, jx, jy)
    ex, ey = jx - jl.width / 2 + tx, jy - jl.height / 2 + ty
    dashed_ellipse(L, ex, ey + 6, 160, 88, RED)
    tk = ticket()
    tk = tk.resize((int(tk.width * 0.84), int(tk.height * 0.84)), Image.LANCZOS)
    put(L, tk, 770, 1010)
    # Freiraum für den Umfrage-Sticker
    q = GP.text("TUCK IT OR LEAVE IT?", "x9", 64, INK, 0.0)
    halo = Image.new("RGBA", (q.width + 60, q.height + 60), (255, 255, 255, 0))
    a = Image.new("L", halo.size, 0)
    a.paste(q.getchannel("A"), (30, 30))
    halo.putalpha(a.filter(ImageFilter.GaussianBlur(14)).point(lambda v: min(255, int(v * 1.6))))
    put(L, halo, W / 2, 1530)
    put(L, q, W / 2, 1530)
    put(L, chip("TAP TO WATCH  ›", INK, size=28), W / 2, 1808)
    img.alpha_composite(L)
    img.save("story_jersey.png")
    img.convert("RGB").save("story_jersey.jpg", quality=93)
    print("fertig: story_jersey.png")


if __name__ == "__main__":
    main()
