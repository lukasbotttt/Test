"""NEXT MATCH (@nextmatch.studio) – Logo-Entwürfe: Gameday-Grafiken & Motion-Videos für Vereine.

Farben: Schwarz #0A0B10, Weiß #F4F4F6, Akzent Neon-Lime #C6FF2E. Schrift: Archivo Expanded Black (OFL).
Aufruf: python3 logo.py  -> out/*.png (Profilbild 1080x1080, Wortmarke transparent, Vergleichsbogen)
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "..", "hockey-reel", "fonts")
OUT = os.path.join(HERE, "out")
BG = (10, 11, 16)
WHITE = (244, 244, 246)
LIME = (198, 255, 46)
LIME_INK = (112, 170, 0)                          # Lime-Variante für weiße Untergründe
GREY = (120, 124, 136)
SHEAR = 0.22                                      # Kursivneigung (≈ 12°)


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def text_img(txt, name, size, col, track=0.0):
    f = font(name, size)
    asc, desc = f.getmetrics()
    w = int(sum(f.getlength(c) for c in txt) + track * size * (len(txt) - 1)) + size
    im = Image.new("RGBA", (w, asc + desc + size // 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = size // 2
    for c in txt:
        d.text((x, size // 4), c, font=f, fill=col + (255,))
        x += f.getlength(c) + track * size
    return im.crop(im.getbbox())


def shear(im, k=SHEAR):
    """Kursiv: oben nach rechts neigen."""
    w, h = im.size
    out_w = int(w + k * h) + 2
    # PIL bildet Ausgabe -> Eingabe ab: x_in = x_out + k*y - k*h  (oben um k*h nach rechts verschoben)
    return im.transform((out_w, h), Image.AFFINE, (1, k, -k * h, 0, 1, 0), Image.BICUBIC)


def glow(im, col, radius, strength):
    a = im.getchannel("A").filter(ImageFilter.GaussianBlur(radius))
    g = Image.new("RGBA", im.size, col + (0,))
    g.putalpha(a.point(lambda v: int(min(255, v * strength))))
    return g


def pad(im, p):
    out = Image.new("RGBA", (im.width + 2 * p, im.height + 2 * p), (0, 0, 0, 0))
    out.alpha_composite(im, (p, p))
    return out


# ================================================================= Symbol A: NM-Ligatur mit Vorwärts-Pfeil
def stem_runs(im):
    """Spalten, die über die volle Höhe gefüllt sind (senkrechte Stämme) -> [(x0, x1), ...]."""
    a = np.asarray(im.getchannel("A")) > 128
    idx = np.where(a.mean(0) > 0.98)[0]
    groups = np.split(idx, np.where(np.diff(idx) > 1)[0] + 1)
    return [(int(g[0]), int(g[-1]) + 1) for g in groups]


def chevrons_upright(h, stem, n=2, col=LIME):
    """»-Pfeil (ungeneigt), Strichstärke passend zu den Buchstabenstämmen."""
    ss = 4
    w, dep, gap = stem * 0.82, h * 0.40, stem * 0.42
    W_ = int(n * (w + dep) + (n - 1) * gap) + 4
    im = Image.new("RGBA", (W_ * ss, int(h) * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i in range(n):
        x0 = i * (w + gap)
        d.polygon([(p * ss, q * ss) for p, q in ((x0, 0), (x0 + w, 0), (x0 + w + dep, h / 2),
                                                 (x0 + w, h), (x0, h), (x0 + dep, h / 2))], fill=col + (255,))
    im = im.resize((W_, int(h)), Image.LANCZOS)
    return im.crop(im.getbbox())


def symbol_nm(cap=400, arrow=True):
    """N und M aus Archivo Expanded Black teilen sich einen Stamm (Ligatur), dahinter der Lime-Pfeil », alles kursiv."""
    size = int(cap / 0.69)
    n = text_img("N", "ArchivoX900.ttf", size, WHITE)
    m = text_img("M", "ArchivoX900.ttf", size, WHITE)
    n_stem = stem_runs(n)[-1]
    m_stem = stem_runs(m)[0]
    stem = n_stem[1] - n_stem[0]
    xm = n_stem[0] - m_stem[0]
    h = max(n.height, m.height)
    parts = [(n, 0), (m, xm)]
    w = xm + m.width
    if arrow:
        ch = chevrons_upright(h, stem)
        parts.append((ch, w + int(stem * 0.55)))
        w += int(stem * 0.55) + ch.width
    im = Image.new("RGBA", (w + 4, h), (0, 0, 0, 0))
    for p, x in parts:
        im.alpha_composite(p, (x, (h - p.height) // 2))
    im = shear(im)
    return im.crop(im.getbbox())


# ================================================================= Wortmarke
def wordmark(size=150, stacked=False, chevrons=False):
    a = shear(text_img("NEXT", "ArchivoX900.ttf", size, WHITE, 0.02))
    b = shear(text_img("MATCH", "ArchivoX900.ttf", size, WHITE, 0.02))
    st = shear(text_img("STUDIO", "ArchivoX800.ttf", int(size * 0.26), LIME, 0.55), SHEAR * 0.6)
    gap = int(size * 0.32)
    if stacked:
        w = max(a.width, b.width)
        h = a.height + b.height + int(size * 0.18) + st.height + int(size * 0.28)
        im = Image.new("RGBA", (w + 40, h + 20), (0, 0, 0, 0))
        im.alpha_composite(a, (int(size * 0.12), 0))
        im.alpha_composite(b, (0, a.height + int(size * 0.18)))
        im.alpha_composite(st, (int(size * 0.04), a.height + b.height + int(size * 0.18) + int(size * 0.28)))
        return im.crop(im.getbbox())
    chev = None
    if chevrons:
        chev = symbol_chevrons(int(size * 0.96))
    w = a.width + gap + (chev.width + gap if chev else 0) + b.width
    h = max(a.height, b.height) + int(size * 0.2) + st.height
    im = Image.new("RGBA", (w + 20, h + 20), (0, 0, 0, 0))
    x = 0
    im.alpha_composite(a, (x, 0))
    x += a.width + gap
    if chev:
        im.alpha_composite(chev, (x, int((a.height - chev.height) / 2)))
        x += chev.width + gap
    im.alpha_composite(b, (x, 0))
    im.alpha_composite(st, (w - st.width, max(a.height, b.height) + int(size * 0.2)))
    return im.crop(im.getbbox())


def symbol_chevrons(height):
    im = shear(chevrons_upright(height, height * 0.2))
    return im.crop(im.getbbox())


# ================================================================= Hintergrund / Profilbild
def bg_square(n=1080, accent=0.18):
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) / n
    base = np.array(BG, np.float32) / 255
    img = np.ones((n, n, 3), np.float32) * base
    spot = np.exp(-(((xx - 0.72) / 0.45) ** 2 + ((yy - 0.25) / 0.45) ** 2))
    img += spot[..., None] * np.array(LIME, np.float32) / 255 * accent * 0.35
    img += np.exp(-(((xx - 0.2) / 0.5) ** 2 + ((yy - 0.9) / 0.4) ** 2))[..., None] * np.array([0.2, 0.25, 0.45]) * 0.12
    # feine Diagonal-Speedlines
    lines = ((xx * 1.0 + yy * 0.45) * 38) % 1.0
    img += ((lines < 0.04) * 0.025)[..., None]
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).convert("RGBA")


def center(dst, im, cx, cy):
    dst.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def fit(im, maxw, maxh):
    s = min(maxw / im.width, maxh / im.height)
    return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)


def profile_a():
    n = 1080
    img = bg_square(n)
    sym = fit(symbol_nm(500), 820, 440)
    g = glow(pad(sym, 80), LIME, 40, 0.35)
    center(img, g, n / 2, n / 2)
    center(img, sym, n / 2, n / 2)
    return img


def profile_b():
    n = 1080
    img = bg_square(n)
    wm = fit(wordmark(200, stacked=True), 760, 600)
    center(img, wm, n / 2, n / 2 + 10)
    return img


def profile_c():
    """Wappen/Badge: Ring mit Schriftzug, NM-Symbol in der Mitte (Vereins-Ästhetik)."""
    n = 1080
    img = bg_square(n, 0.1)
    ss = 3
    ring = Image.new("RGBA", (n * ss, n * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(ring)
    c = n * ss / 2
    for r, wd, col in ((470, 14, LIME), (400, 5, WHITE)):
        d.ellipse((c - r * ss, c - r * ss, c + r * ss, c + r * ss), outline=col + (255,), width=wd * ss)
    ring = ring.resize((n, n), Image.LANCZOS)
    img.alpha_composite(ring)
    # Text im Ring: oben im Uhrzeigersinn, unten gegen den Uhrzeigersinn (aufrecht lesbar), Lime-Punkte bei 3 und 9 Uhr
    f = font("ArchivoX800.ttf", 46)
    R = 430                                        # Mitte zwischen Lime-Ring (470) und weißem Ring (400)
    arc_text(img, "NEXT MATCH STUDIO", f, R, -math.pi / 2, True, 9)
    arc_text(img, "GAMEDAY · MOTION", f, R, math.pi / 2, False, 9)
    for ang in (0, math.pi):
        x, y = n / 2 + R * math.cos(ang), n / 2 + R * math.sin(ang)
        ImageDraw.Draw(img).ellipse((x - 9, y - 9, x + 9, y + 9), fill=LIME + (255,))
    sym = fit(symbol_nm(400), 560, 300)
    center(img, glow(pad(sym, 60), LIME, 30, 0.3), n / 2, n / 2)
    center(img, sym, n / 2, n / 2)
    return img


def arc_text(img, txt, f, R, mid_angle, clockwise, track):
    """Buchstaben entlang eines Kreisbogens, zentriert um mid_angle (Bildkoordinaten, y nach unten)."""
    n = img.width
    widths = [f.getlength(ch) + track for ch in txt]
    total = sum(widths) - track
    sgn = 1 if clockwise else -1
    a = mid_angle - sgn * (total / R) / 2
    y0, y1 = f.getbbox("H")[1::2]                  # Versalhöhe -> Buchstaben mittig auf den Radius setzen
    for ch, wch in zip(txt, widths):
        mid = a + sgn * ((wch - track) / 2) / R
        ci = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        ImageDraw.Draw(ci).text((50 - f.getlength(ch) / 2, 50 - (y0 + y1) / 2), ch, font=f, fill=WHITE + (255,))
        rot = -math.degrees(mid + math.pi / 2) if clockwise else -math.degrees(mid - math.pi / 2)
        ci = ci.rotate(rot, resample=Image.BICUBIC)
        center(img, ci, n / 2 + R * math.cos(mid), n / 2 + R * math.sin(mid))
        a += sgn * wch / R


def lockup(cap=300, dark=False):
    """Symbol | NEXT MATCH / S T U D I O nebeneinander (Website, Rechnungen, Video-Wasserzeichen)."""
    sym = symbol_nm(cap)
    h = sym.height
    blk = fit(wordmark(int(cap * 0.9)), 10 ** 5, h)
    bar_w, gap = max(3, cap // 50), int(cap * 0.28)
    im = Image.new("RGBA", (sym.width + 2 * gap + bar_w + blk.width + 8, h + 8), (0, 0, 0, 0))
    im.alpha_composite(sym, (0, 4))
    bx = sym.width + gap
    ImageDraw.Draw(im).polygon([(bx + SHEAR * h, 4), (bx + SHEAR * h + bar_w, 4), (bx + bar_w, 4 + h), (bx, 4 + h)],
                               fill=GREY + (255,))
    im.alpha_composite(blk, (bx + bar_w + gap, 4))
    im = im.crop(im.getbbox())
    return light_version(im) if dark else im


def light_version(im):
    """Für helle Untergründe: Weiß -> Schwarz, Lime -> kräftigeres Grün (Neon-Lime ist auf Weiß kaum lesbar)."""
    return recolor(im, BG, LIME_INK)


def circle_preview(im, d=420):
    m = Image.new("L", (im.width, im.height), 0)
    ImageDraw.Draw(m).ellipse((0, 0, im.width - 1, im.height - 1), fill=255)
    out = im.copy()
    out.putalpha(m)
    return out.resize((d, d), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    pa, pb, pc = profile_a(), profile_b(), profile_c()
    for name, im in (("A", pa), ("B", pb), ("C", pc)):
        im.convert("RGB").save(os.path.join(OUT, f"profil_{name}.png"))
    wa = wordmark(170)
    wc = wordmark(170, chevrons=True)
    sa = symbol_nm(600)
    la, ld = lockup(300), lockup(300, dark=True)
    for name, im in (("wortmarke", wa), ("wortmarke_pfeil", wc), ("symbol", sa), ("symbol_hell", light_version(sa)),
                     ("lockup", la), ("lockup_hell", ld)):
        im.save(os.path.join(OUT, f"{name}.png"))
    # Vergleichsbogen: je Variante Kreis-Vorschau + Wortmarke, darunter Einsatz auf hellem Grund
    sheet = Image.new("RGBA", (1800, 1260), BG + (255,))
    d = ImageDraw.Draw(sheet)
    fl = font("JBMono700.ttf", 34)
    light = (ld, light_version(wc), light_version(wa))
    for i, (lab, prof, wm) in enumerate((("A  ·  NM-SYMBOL", pa, la), ("B  ·  WORTMARKE", pb, wc), ("C  ·  BADGE", pc, wa))):
        x = 60 + i * 590
        d.text((x, 50), lab, font=fl, fill=LIME + (255,))
        sheet.alpha_composite(circle_preview(prof, 460), (x + 30, 120))
        wmf = fit(wm, 480, 130)
        sheet.alpha_composite(wmf, (x + 260 - wmf.width // 2, 690 - wmf.height // 2))
        lightbg = Image.new("RGBA", (520, 300), (240, 240, 242, 255))
        dark = fit(light[i], 440, 130)
        lightbg.alpha_composite(dark, ((520 - dark.width) // 2, (300 - dark.height) // 2))
        sheet.alpha_composite(lightbg, (x, 900))
    sheet.convert("RGB").save(os.path.join(OUT, "vergleich.png"))
    print("fertig")


def recolor(im, col, lime=None):
    """Weiß -> col, optional Lime -> lime. Weiß erkennt man am hohen Blauanteil (Lime hat kaum Blau)."""
    arr = np.asarray(im).astype(np.float32)
    white = arr[..., 2] > 0.5 * arr[..., 1]
    arr[white, 0:3] = col
    if lime is not None:
        arr[~white, 0:3] = lime
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


if __name__ == "__main__":
    main()
