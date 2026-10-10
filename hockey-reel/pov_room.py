"""Gefilmter Laptop im dunklen Raum (POV-Handyaufnahme) – Umgebung, Kamera und Nachbearbeitung.

Der Bildschirminhalt wird flach (SCR_W x SCR_H, 16:10) gerendert und mit compose() in die Szene
gesetzt: Neon-Monitor im Hintergrund, Laptop mit Rahmen, beleuchtete Tastatur mit Lichtspill vom
Bildschirm, Handkamera-Wackeln, Belichtungsnachführung, Rauschen und Text-Overlay im TikTok-Stil.
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import make_hockey_reel as m

W, H = 1080, 1920
SCR_W, SCR_H = 1600, 1000
INTER = m.os.path.join(m.HERE, "fonts", "Inter.ttf")
_ifonts = {}


def ifont(weight, size):
    key = (weight, size)
    if key not in _ifonts:
        f = ImageFont.truetype(INTER, size)
        f.set_variation_by_axes([min(32, max(14, size)), weight])
        _ifonts[key] = f
    return _ifonts[key]


def persp_coeffs(dst, src):
    A, B = [], []
    for (x, y), (X, Y) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -X * x, -X * y])
        B.append(X)
        A.append([0, 0, 0, x, y, 1, -Y * x, -Y * y])
        B.append(Y)
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()


def quad_mask(quad, blur=0.0, size=(W, H)):
    mk = Image.new("L", size, 0)
    ImageDraw.Draw(mk).polygon(quad, fill=255)
    return mk.filter(ImageFilter.GaussianBlur(blur)) if blur else mk


# ================================================================= Geometrie (Bildkoordinaten)
SCREEN_Q = [(58, 792), (1066, 826), (1056, 1398), (40, 1446)]         # aktive Bildfläche
LID_Q = [(26, 758), (1098, 794), (1090, 1430), (8, 1484)]             # Deckel mit Rahmen
DECK_TOP = [(-30, 1500), (1120, 1440)]                                  # Scharnierkante
KB_Q = [(-10, 1548), (1110, 1478), (1650, 2330), (-760, 2420)]        # Tastaturfeld (Ebene)


# ================================================================= Hintergrund: Neon-Monitor
def _glow(img, radius, gain):
    small = img.resize((img.width // 4, img.height // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(radius / 4))
    g = np.asarray(small.resize(img.size, Image.BILINEAR)).astype(np.float32)
    return np.clip(np.asarray(img).astype(np.float32) + g * gain, 0, 255)


def build_background():
    w, h = W, 1000
    img = Image.new("RGB", (w, h), (7, 5, 12))
    d = ImageDraw.Draw(img)
    # Monitorfläche mit abstraktem Neon-Wallpaper
    d.rectangle((-10, 40, w + 10, 960), fill=(9, 5, 14))
    mag, pink, blue, vio = (215, 40, 205), (255, 170, 250), (70, 60, 255), (120, 40, 230)
    # linker Block: blaues Band unten
    for k in range(40):
        a = k / 40
        col = tuple(int(c * (0.25 + 0.75 * a)) for c in blue)
        d.rectangle((0, 560 + k * 4, 205, 564 + k * 4), fill=tuple(int(c * 0.8) for c in col))
    d.rectangle((0, 718, 205, 726), fill=(170, 170, 255))
    # senkrechte Lichtkanten
    d.rectangle((182, 90, 190, 730), fill=pink)
    d.rectangle((190, 90, 200, 730), fill=mag)
    d.rectangle((300, 110, 312, 730), fill=mag)
    d.rectangle((312, 110, 318, 730), fill=pink)
    # großes Paneel rechts mit Verlauf von Magenta nach Dunkelviolett
    for k in range(200):
        a = (1 - k / 200) ** 4.5
        col = tuple(int(14 + (c - 14) * a) for c in (150, 30, 160))
        d.rectangle((540 + k * 3, 150, 543 + k * 3, 612), fill=col)
    d.rectangle((532, 150, 542, 640), fill=pink)
    d.rectangle((532, 612, w + 10, 622), fill=mag)
    d.rectangle((532, 622, w + 10, 628), fill=pink)
    # blaue Querbalken unten rechts
    for k in range(18):
        a = 1 - k / 18
        d.rectangle((560, 660 + k * 3, w + 10, 663 + k * 3), fill=tuple(int(c * (0.3 + 0.7 * a)) for c in vio))
    d.rectangle((560, 716, w + 10, 724), fill=(150, 150, 255))
    d.rectangle((548, 650, 556, 735), fill=mag)
    # Menüleiste des Monitors (winzig, unscharf)
    d.rectangle((0, 40, w, 62), fill=(24, 18, 30))
    f = ifont(500, 14)
    x = 30
    for word in ("Finder", "File", "Edit", "View", "Go", "Window", "Help"):
        d.text((x, 51), word, font=f, fill=(90, 84, 100), anchor="lm")
        x += f.getlength(word) + 26
    arr = _glow(img, 36, 0.3) * 0.8
    img = Image.fromarray(arr.astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.5))
    # Schreibtisch-LED links hinter dem Laptop
    d = ImageDraw.Draw(img)
    d.rectangle((-10, 838, 70, 872), fill=(235, 60, 225))
    d.rectangle((1040, 812, w + 10, 832), fill=(205, 55, 215))
    arr = _glow(img, 60, 0.45)
    full = Image.new("RGB", (W, H), (4, 3, 7))
    full.paste(Image.fromarray(arr.astype(np.uint8)), (0, -40))
    return full


# ================================================================= Tastatur
KB_PW, KB_PH = 2600, 1100
U = 168          # eine Tasteneinheit in Ebenen-Pixeln


def _keyboard_rows():
    fn = [("esc", 1.4, "")] + [(f"F{i}", 1.0, "") for i in range(1, 13)] + [("", 1.0, "")]
    pairs = lambda txt: [(c[0] + "\t" + c[1], 1, "") for c in txt.split()]
    r1 = pairs("~` !1 @2 #3 $4 %5 ^6 &7 *8 (9 )0 _- +=") + [("delete", 1.5, "")]
    r2 = [("tab", 1.5, "")] + [(c, 1, "") for c in "QWERTYUIOP"] + pairs("{[ }] |\\")
    r3 = [("caps lock", 1.8, "")] + [(c, 1, "") for c in "ASDFGHJKL"] + pairs(":; \"'") + [("return", 1.8, "")]
    r4 = [("shift", 2.3, "")] + [(c, 1, "") for c in "ZXCVBNM"] + pairs("<, >. ?/") + [("shift", 2.3, "")]
    return [(0.55, fn), (1, r1), (1, r2), (1, r3), (1, r4)]


def build_keyboard_plane():
    """Tastatur flach von oben: Basis (Kappen + leuchtende Beschriftung) und Spill-Maske (Kappenflächen)."""
    base = Image.new("RGB", (KB_PW, KB_PH), (5, 5, 7))
    spill = Image.new("L", (KB_PW, KB_PH), 0)
    d, sd = ImageDraw.Draw(base), ImageDraw.Draw(spill)
    gap = U * 0.12
    y = 30
    x0 = 70
    for hrow, keys in _keyboard_rows():
        kh = U * hrow
        x = x0
        for label, wu, _ in keys:
            kw = U * wu
            box = (x + gap / 2, y + gap / 2, x + kw - gap / 2, y + kh - gap / 2)
            d.rounded_rectangle(box, radius=U * 0.1, fill=(13, 13, 16))
            d.rounded_rectangle((box[0] + 4, box[1] + 3, box[2] - 4, box[1] + 8), radius=4, fill=(22, 22, 26))
            sd.rounded_rectangle(box, radius=U * 0.1, fill=255)
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            leg = (232, 234, 242)
            if "\t" in label:
                top, bot = label.split("\t")
                d.text((cx, cy - kh * 0.2), top, font=ifont(500, int(U * 0.26)), fill=leg, anchor="mm")
                d.text((cx, cy + kh * 0.2), bot, font=ifont(500, int(U * 0.3)), fill=leg, anchor="mm")
            elif len(label) == 1:
                d.text((cx, cy), label, font=ifont(500, int(U * 0.36)), fill=leg, anchor="mm")
            elif label.startswith("F"):
                d.text((cx, cy + kh * 0.22), label, font=ifont(500, int(U * 0.16)), fill=leg, anchor="mm")
                d.ellipse((cx - 9, cy - kh * 0.16 - 9, cx + 9, cy - kh * 0.16 + 9), outline=leg, width=3)
            elif label:
                d.text((box[0] + U * 0.14, box[3] - U * 0.16), label, font=ifont(500, int(U * 0.2)), fill=leg, anchor="lm")
            x += kw
        y += kh
    return base, spill


def build_keyboard():
    base, spill = build_keyboard_plane()
    coeffs = persp_coeffs(KB_Q, [(0, 0), (KB_PW, 0), (KB_PW, KB_PH), (0, KB_PH)])
    wb = np.asarray(base.transform((W, H), Image.PERSPECTIVE, coeffs, Image.BICUBIC)).astype(np.float32)
    ws = np.asarray(spill.transform((W, H), Image.PERSPECTIVE, coeffs, Image.BICUBIC)).astype(np.float32) / 255
    # Beschriftung leuchtet (Hintergrundbeleuchtung)
    lum = wb.max(axis=2)
    legend = np.clip((lum - 90) / 120, 0, 1)
    glow = Image.fromarray((legend * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))
    wb += (np.asarray(glow).astype(np.float32) / 255 * 40)[..., None] * np.array([0.9, 0.92, 1.0])
    # Tiefenunschärfe: nach unten (näher an der Kamera) stärker
    sharp = Image.fromarray(np.clip(wb, 0, 255).astype(np.uint8))
    soft = sharp.filter(ImageFilter.GaussianBlur(5))
    ys = np.arange(H, dtype=np.float32)[:, None, None]
    k = np.clip((ys - 1760) / 260, 0, 1)
    kb = np.asarray(sharp).astype(np.float32) * (1 - k) + np.asarray(soft).astype(np.float32) * k
    spill_s = np.asarray(Image.fromarray((ws * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))).astype(np.float32) / 255
    near = np.clip(1 - (ys[..., 0] - 1450) / 520, 0.15, 1)       # nahe am Bildschirm heller
    mask = np.asarray(quad_mask(KB_Q)).astype(np.float32)[..., None] / 255
    return kb * mask, (spill_s * near)[..., None] * mask


# ================================================================= Laptop-Gehäuse
def build_laptop():
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.polygon(LID_Q, fill=(10, 10, 12, 255))
    # Lichtkante am Deckel (fängt das Neonlicht)
    d.line([LID_Q[0], LID_Q[1]], fill=(120, 70, 140, 255), width=3)
    d.line([LID_Q[0], LID_Q[3]], fill=(70, 50, 90, 255), width=3)
    # Scharnier und Gehäuseoberseite
    d.polygon([LID_Q[3], LID_Q[2], (1120, 1440), (1120, 1470), (-30, 1530), (-30, 1500)], fill=(18, 18, 22, 255))
    d.polygon([(-30, 1530), (1120, 1470), (1120, 1490), (-30, 1552)], fill=(12, 12, 15, 255))
    return lay


# ================================================================= Overlay (TikTok-Textstil)
def overlay_text(lines, y_center=457, size=62):
    """TikTok-'Classic'-Text: schwarze Schrift auf weißen Kästen je Zeile, Ecken gerundet, Innenecken konkav."""
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    f = ifont(650, size)
    pitch = int(size * 1.33)
    pad_x, r = 34, 16
    y0 = y_center - pitch * len(lines) / 2
    boxes = []
    for i, txt in enumerate(lines):
        tw = f.getlength(txt)
        cy = y0 + pitch * (i + 0.5)
        boxes.append([W / 2 - tw / 2 - pad_x, cy - pitch / 2 - 4, W / 2 + tw / 2 + pad_x, cy + pitch / 2 + 4])
    for i in range(1, len(boxes)):             # Kästen lückenlos aneinander
        boxes[i][1] = boxes[i - 1][3]
    for b in boxes:
        d.rounded_rectangle(b, radius=r, fill=(252, 253, 253, 255))
    # konkave Innenecken dort, wo ein schmaler auf einen breiten Kasten trifft
    for i in range(1, len(boxes)):
        up, lo = boxes[i - 1], boxes[i]
        narrow, wide, below = (lo, up, True) if lo[2] - lo[0] < up[2] - up[0] else (up, lo, False)
        yj = lo[1]
        d.rectangle((narrow[0], yj - r if not below else yj, narrow[2], yj + r if below else yj), fill=(252, 253, 253, 255))
        for side in (-1, 1):
            x = narrow[0] if side < 0 else narrow[2]
            if below:
                d.rectangle((x + (-r if side < 0 else 0), yj - 1, x + (0 if side < 0 else r), yj + r), fill=(252, 253, 253, 255))
                d.ellipse((x - 2 * r if side < 0 else x, yj, x if side < 0 else x + 2 * r, yj + 2 * r), fill=(0, 0, 0, 0))
            else:
                d.rectangle((x + (-r if side < 0 else 0), yj - r, x + (0 if side < 0 else r), yj + 1), fill=(252, 253, 253, 255))
                d.ellipse((x - 2 * r if side < 0 else x, yj - 2 * r, x if side < 0 else x + 2 * r, yj), fill=(0, 0, 0, 0))
    for i, txt in enumerate(lines):
        cy = y0 + pitch * (i + 0.5)
        d.text((W / 2, cy + 3), txt, font=f, fill=(0, 0, 0, 255), anchor="mm")
    return lay


# ================================================================= Zusammensetzen
_STATIC = {}


def static():
    if not _STATIC:
        _STATIC["bg"] = np.asarray(build_background()).astype(np.float32)
        _STATIC["kb"], _STATIC["spill"] = build_keyboard()
        _STATIC["laptop"] = build_laptop()
        _STATIC["scr_mask"] = np.asarray(quad_mask(SCREEN_Q, 0.8)).astype(np.float32)[..., None] / 255
        _STATIC["coeffs"] = persp_coeffs(SCREEN_Q, [(0, 0), (SCR_W, 0), (SCR_W, SCR_H), (0, SCR_H)])
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H * 0.55) / H) ** 2)
        _STATIC["vig"] = (1 - 0.5 * np.clip(r * 1.6 - 0.35, 0, 1) ** 1.5)[..., None]
        # Glanz auf dem Display (Spiegelung der LED, sehr schwach)
        gl = np.clip(1 - np.abs((xx - 0.55 * yy) - (-260)) / 260, 0, 1) * np.clip((1100 - xx) / 900, 0, 1)
        _STATIC["glare"] = (gl * 14)[..., None] * np.array([1.0, 0.45, 1.0])
        mo = np.sin(xx * 0.61 + yy * 0.23) * np.sin(xx * 0.17 - yy * 0.58)
        _STATIC["moire"] = (1 + 0.022 * mo)[..., None] * np.array([1.0, 0.99, 1.01])
    return _STATIC


def filmed_screen(scr):
    """LCD wie vom Handy gefilmt: angehobenes, violettes Schwarz, warme gedämpfte Lichter, leichte Unschärfe, Bloom."""
    a = np.asarray(scr.convert("RGB")).astype(np.float32) / 255
    lift = np.array([0.07, 0.065, 0.11])
    gain = np.array([0.80, 0.765, 0.70])
    a = lift + gain * a ** 1.12
    out = Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8))
    out = out.filter(ImageFilter.GaussianBlur(1.1))
    small = out.resize((SCR_W // 8, SCR_H // 8), Image.BILINEAR).filter(ImageFilter.GaussianBlur(4))
    b = np.asarray(small.resize((SCR_W, SCR_H), Image.BILINEAR)).astype(np.float32)
    o = np.asarray(out).astype(np.float32)
    o = o + np.clip(b - 120, 0, 255) * 0.22
    x = o / 255
    o = 255 * np.where(x < 0.72, x, 0.72 + 0.28 * (1 - np.exp(-(x - 0.72) / 0.28)))
    return Image.fromarray(np.clip(o, 0, 255).astype(np.uint8))


def camera(t):
    """Handkamera: langsames Driften + feines Zittern (Pixel, Grad, Zoom)."""
    dx = 1.4 * math.sin(t * 0.7 + 0.4) + 0.5 * math.sin(t * 2.3 + 1.1) + 0.25 * math.sin(t * 11.0)
    dy = 1.8 * math.sin(t * 0.55 + 2.0) + 0.5 * math.sin(t * 2.9) + 0.2 * math.sin(t * 13.0 + 0.5)
    rot = 0.05 * math.sin(t * 0.5 + 0.8) + 0.02 * math.sin(t * 2.1)
    zoom = 1.03 + 0.003 * math.sin(t * 0.4)
    return dx, dy, rot, zoom


def compose(scr, t, overlay, exposure=1.0, seed=0):
    st = static()
    film = filmed_screen(scr)
    warped = np.asarray(film.transform((W, H), Image.PERSPECTIVE, st["coeffs"], Image.BICUBIC)).astype(np.float32)
    mean = np.asarray(film.resize((16, 10), Image.BOX)).astype(np.float32).reshape(-1, 3).mean(0)
    # Raumlicht folgt der Bildschirmhelligkeit (dunkel -45 %, hell +25 %)
    luma = float(mean.mean())
    room = float(np.interp(luma, [8, 40, 200], [0.55, 1.0, 1.25]))
    img = st["bg"] * (0.75 + 0.25 * room)
    lap = st["laptop"]
    la = np.asarray(lap).astype(np.float32)
    img = img * (1 - la[..., 3:] / 255) + la[..., :3] * (la[..., 3:] / 255)
    m_ = st["scr_mask"]
    img = img * (1 - m_) + (warped * st["moire"] + st["glare"]) * m_
    kbm = (st["kb"].max(axis=2, keepdims=True) > 0).astype(np.float32)
    kb = st["kb"] * room + st["spill"] * mean * 0.3
    img = img * (1 - kbm) + kb * kbm
    # Kamera
    dx, dy, rot, zoom = camera(t)
    im = Image.fromarray(np.clip(img * exposure, 0, 255).astype(np.uint8))
    im = im.rotate(rot, resample=Image.BICUBIC, center=(W / 2, H * 0.55), translate=(dx, dy))
    w2, h2 = W / zoom, H / zoom
    im = im.transform((W, H), Image.EXTENT, ((W - w2) / 2, (H - h2) / 2, (W + w2) / 2, (H + h2) / 2), Image.BICUBIC)
    arr = np.asarray(im).astype(np.float32) * st["vig"]
    rng = np.random.default_rng(seed)
    lum_noise = rng.normal(0, 3.2, (H // 2, W // 2)).astype(np.float32)
    lum_noise = np.asarray(Image.fromarray(lum_noise).resize((W, H), Image.BILINEAR))
    arr += lum_noise[..., None] * (1.2 - arr / 255)
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
    out.alpha_composite(overlay)
    return out.convert("RGB")


# ================================================================= Bildschirm-Chrome (Videoplayer, Mauszeiger)
def draw_hud(img, t_play, total, alpha=1.0, playing=True, cy=None):
    """Generischer Videoplayer-Balken (schwebend, dunkel, abgerundet) unten im Bild."""
    if alpha <= 0.01:
        return
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    w_, h_ = 560, 92
    cx = img.width / 2
    cy = cy or img.height - 150
    a = int(255 * alpha)
    d.rounded_rectangle((cx - w_ / 2, cy - h_ / 2, cx + w_ / 2, cy + h_ / 2), radius=22, fill=(30, 30, 34, int(220 * alpha)),
                        outline=(70, 70, 76, int(160 * alpha)), width=1)
    wt = (235, 235, 240, a)
    # Lautstärke
    vx = cx - w_ / 2 + 34
    d.polygon([(vx, cy - 22), (vx + 6, cy - 22), (vx + 13, cy - 29), (vx + 13, cy - 9), (vx + 6, cy - 16), (vx, cy - 16)], fill=wt)
    d.line((vx + 24, cy - 19, vx + 120, cy - 19), fill=(90, 90, 96, a), width=4)
    d.line((vx + 24, cy - 19, vx + 92, cy - 19), fill=(60, 140, 255, a), width=4)
    d.ellipse((vx + 86, cy - 25, vx + 98, cy - 13), fill=wt)
    # Transport
    px = cx
    for sgn in (-1, 1):
        bx = px + sgn * 62
        for k in (0, 1):
            ox = bx + sgn * (k * 12 - 6)
            d.polygon([(ox - sgn * 8, cy - 28), (ox + sgn * 6, cy - 19), (ox - sgn * 8, cy - 10)], fill=wt)
    if playing:
        d.rectangle((px - 9, cy - 30, px - 3, cy - 8), fill=wt)
        d.rectangle((px + 3, cy - 30, px + 9, cy - 8), fill=wt)
    else:
        d.polygon([(px - 8, cy - 31), (px + 12, cy - 19), (px - 8, cy - 7)], fill=wt)
    # rechts: Teilen / Vollbild
    rx = cx + w_ / 2 - 80
    d.rounded_rectangle((rx, cy - 28, rx + 18, cy - 12), radius=3, outline=wt, width=2)
    d.line((rx + 40, cy - 28, rx + 40, cy - 14), fill=wt, width=2)
    d.rectangle((rx + 32, cy - 20, rx + 48, cy - 9), outline=wt, width=2)
    # Zeitleiste
    f = ifont(500, 15)
    pos = max(0.0, min(1.0, t_play / total))
    x0, x1 = cx - w_ / 2 + 80, cx + w_ / 2 - 80
    d.text((cx - w_ / 2 + 22, cy + 22), f"00:{int(t_play):02d}", font=f, fill=(200, 200, 205, a), anchor="lm")
    d.text((cx + w_ / 2 - 22, cy + 22), f"00:{int(total):02d}", font=f, fill=(200, 200, 205, a), anchor="rm")
    d.line((x0, cy + 22, x1, cy + 22), fill=(85, 85, 92, a), width=3)
    d.line((x0, cy + 22, x0 + (x1 - x0) * pos, cy + 22), fill=(225, 225, 230, a), width=3)
    d.rounded_rectangle((x0 + (x1 - x0) * pos - 3, cy + 13, x0 + (x1 - x0) * pos + 3, cy + 31), radius=2, fill=wt)
    img.alpha_composite(lay) if img.mode == "RGBA" else img.paste(lay, (0, 0), lay)


def draw_cursor(img, x, y, scale=1.6):
    """Generischer Mauspfeil (schwarz mit weißem Rand)."""
    pts = [(0, 0), (0, 17), (4, 13), (7, 20), (10, 19), (7, 12), (12, 12)]
    P = [(x + px * scale, y + py * scale) for px, py in pts]
    d = ImageDraw.Draw(img)
    d.polygon(P, fill=(10, 10, 12), outline=(255, 255, 255))
    d.line(P + [P[0]], fill=(255, 255, 255), width=max(1, int(scale * 1.3)))
