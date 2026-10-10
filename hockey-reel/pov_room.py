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
LID_Q = [(26, 758), (1098, 794), (1090, 1430), (8, 1484)]             # Deckel mit Rahmen (Außenkante)
LID_FW, LID_FH = 1100, 690                                              # Deckel flach (Ebenen-Pixel)
LID_INSET = (32, 34, 32, 40)                                            # Rahmen links, oben, rechts, unten
KB_Q = [(-10, 1548), (1110, 1478), (1400, 2330), (-330, 2410)]        # Tastaturfeld (Ebene)
DECK_Q = [(8, 1484), (1090, 1430), (1120, 1440), (1120, 1490), (-30, 1552), (-30, 1500)]
LOOP = None                                                             # Videolänge (Kamera schließt den Kreis)


def _lid_map(pt):
    c = persp_coeffs([(0, 0), (LID_FW, 0), (LID_FW, LID_FH), (0, LID_FH)], LID_Q)
    x, y = pt
    den = c[6] * x + c[7] * y + 1
    return ((c[0] * x + c[1] * y + c[2]) / den, (c[3] * x + c[4] * y + c[5]) / den)


_l, _t, _r, _b = LID_INSET
SCREEN_Q = [_lid_map(p_) for p_ in ((_l, _t), (LID_FW - _r, _t), (LID_FW - _r, LID_FH - _b), (_l, LID_FH - _b))]


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
    d.rectangle((182, 90, 200, 730), fill=mag)
    d.rectangle((188, 90, 191, 730), fill=(255, 238, 255))
    d.rectangle((300, 110, 318, 730), fill=mag)
    d.rectangle((310, 110, 313, 730), fill=(255, 238, 255))
    # großes Paneel rechts mit Verlauf von Magenta nach Dunkelviolett
    for k in range(200):
        a = (1 - k / 200) ** 4.5
        col = tuple(int(14 + (c - 14) * a) for c in (150, 30, 160))
        d.rectangle((540 + k * 3, 150, 543 + k * 3, 612), fill=col)
    d.rectangle((530, 150, 544, 640), fill=mag)
    d.rectangle((535, 150, 538, 640), fill=(255, 238, 255))
    d.rectangle((532, 612, w + 10, 628), fill=mag)
    d.rectangle((532, 619, w + 10, 622), fill=(255, 238, 255))
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
    d.rectangle((-10, 0, w + 10, 40), fill=(3, 2, 5))               # Monitorrahmen oben
    arr = _glow(img, 36, 0.45) * 0.8
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.5))
    # Monitor leicht schräg (passend zur Neigung von Deckel und Tastatur)
    src = [(0, 0), (w, 0), (w, h), (0, h)]
    dst = [(-16, -40), (w + 16, 5), (w, h + 5), (0, h - 40)]
    img = img.transform((w, h), Image.PERSPECTIVE, persp_coeffs(dst, src), Image.BICUBIC, fillcolor=(4, 3, 7))
    full = Image.new("RGB", (W, H), (4, 3, 7))
    full.paste(img, (0, -40))
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


def _fn_glyph(d, i, cx, cy, s_, col):
    """Kleine, generische Symbole für F1–F12."""
    r = 13 * s_
    if i in (1, 2):                                      # Sonne klein/groß
        rr = r * (0.45 if i == 1 else 0.6)
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=col, width=3)
        for k in range(8):
            a_ = k * math.pi / 4
            d.line((cx + math.cos(a_) * rr * 1.5, cy + math.sin(a_) * rr * 1.5, cx + math.cos(a_) * rr * 2.0,
                    cy + math.sin(a_) * rr * 2.0), fill=col, width=3)
    elif i == 3:                                         # Fenster-Raster
        for dx in (-1, 1):
            for dy in (-1, 1):
                d.rectangle((cx + dx * r * 0.9 - r * 0.7, cy + dy * r * 0.6 - r * 0.45, cx + dx * r * 0.9 + r * 0.1 * dx,
                             cy + dy * r * 0.6 + r * 0.1), outline=col, width=2)
    elif i == 4:                                         # Lupe
        d.ellipse((cx - r * 0.8, cy - r * 0.8, cx + r * 0.5, cy + r * 0.5), outline=col, width=3)
        d.line((cx + r * 0.4, cy + r * 0.4, cx + r, cy + r), fill=col, width=3)
    elif i == 5:                                         # Mikrofon
        d.rounded_rectangle((cx - r * 0.35, cy - r, cx + r * 0.35, cy + r * 0.2), radius=r * 0.35, fill=col)
        d.arc((cx - r * 0.7, cy - r * 0.5, cx + r * 0.7, cy + r * 0.6), 0, 180, fill=col, width=3)
    elif i == 6:                                         # Mond
        d.ellipse((cx - r * 0.8, cy - r * 0.8, cx + r * 0.8, cy + r * 0.8), fill=col)
        d.ellipse((cx - r * 0.3, cy - r * 1.0, cx + r * 1.1, cy + r * 0.5), fill=(4, 4, 5))
    elif i in (7, 8, 9):                                 # zurück / Play-Pause / vor
        if i == 8:
            d.polygon([(cx - r, cy - r * 0.6), (cx - r * 0.1, cy), (cx - r, cy + r * 0.6)], fill=col)
            d.rectangle((cx + r * 0.2, cy - r * 0.6, cx + r * 0.4, cy + r * 0.6), fill=col)
            d.rectangle((cx + r * 0.65, cy - r * 0.6, cx + r * 0.85, cy + r * 0.6), fill=col)
        else:
            sg = -1 if i == 7 else 1
            for k in (0, 1):
                ox = cx + sg * (k * r * 0.8 - r * 0.4)
                d.polygon([(ox - sg * r * 0.5, cy - r * 0.6), (ox + sg * r * 0.4, cy), (ox - sg * r * 0.5, cy + r * 0.6)], fill=col)
    else:                                                # Lautsprecher (aus / leise / laut)
        d.polygon([(cx - r, cy - r * 0.35), (cx - r * 0.55, cy - r * 0.35), (cx - r * 0.1, cy - r * 0.8),
                   (cx - r * 0.1, cy + r * 0.8), (cx - r * 0.55, cy + r * 0.35), (cx - r, cy + r * 0.35)], fill=col)
        for k in range(i - 10):
            rr = r * (0.5 + 0.4 * k)
            d.arc((cx - rr, cy - rr, cx + rr, cy + rr), -45, 45, fill=col, width=3)


def build_keyboard_plane():
    """Tastatur flach von oben: Basis (schwarze Kappen + leuchtende Beschriftung), Lichtkanten-Maske
    (Hintergrundbeleuchtung tritt an den Kappenrändern aus) und Glanz-Maske (Oberkante der Kappen)."""
    base = Image.new("RGB", (KB_PW, KB_PH), (0, 0, 0))
    rim = Image.new("L", (KB_PW, KB_PH), 0)
    caps = Image.new("L", (KB_PW, KB_PH), 0)
    sheen = Image.new("L", (KB_PW, KB_PH), 0)
    d, rd, cd, sd = ImageDraw.Draw(base), ImageDraw.Draw(rim), ImageDraw.Draw(caps), ImageDraw.Draw(sheen)
    gap = U * 0.12
    y = 30
    x0 = 70
    leg = (232, 234, 242)
    for hrow, keys in _keyboard_rows():
        kh = U * hrow
        x = x0
        for label, wu, _ in keys:
            kw = U * wu
            box = (x + gap / 2, y + gap / 2, x + kw - gap / 2, y + kh - gap / 2)
            d.rounded_rectangle(box, radius=U * 0.1, fill=(4, 4, 5))
            cd.rounded_rectangle(box, radius=U * 0.1, fill=255)
            rd.rounded_rectangle((box[0] - 3, box[1] - 3, box[2] + 3, box[3] + 3), radius=U * 0.12, outline=255, width=7)
            sd.rounded_rectangle((box[0] + 6, box[1] + 4, box[2] - 6, box[1] + (box[3] - box[1]) * 0.15), radius=6, fill=255)
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            if "\t" in label:
                top, bot = label.split("\t")
                d.text((cx, cy - kh * 0.2), top, font=ifont(500, int(U * 0.26)), fill=leg, anchor="mm")
                d.text((cx, cy + kh * 0.2), bot, font=ifont(500, int(U * 0.3)), fill=leg, anchor="mm")
            elif len(label) == 1:
                d.text((cx, cy), label, font=ifont(500, int(U * 0.36)), fill=leg, anchor="mm")
            elif label.startswith("F"):
                d.text((cx, cy + kh * 0.24), label, font=ifont(500, int(U * 0.15)), fill=leg, anchor="mm")
                _fn_glyph(d, int(label[1:]), cx, cy - kh * 0.12, 1.0, leg)
            elif label:
                d.text((box[0] + U * 0.14, box[3] - U * 0.16), label, font=ifont(500, int(U * 0.2)), fill=leg, anchor="lm")
            x += kw
        y += kh
    rim = rim.filter(ImageFilter.GaussianBlur(5))
    rim = Image.fromarray((np.asarray(rim).astype(np.float32) * (1 - np.asarray(caps).astype(np.float32) / 255)).astype(np.uint8))
    return base, rim, sheen


def build_keyboard():
    base, rim, sheen = build_keyboard_plane()
    coeffs = persp_coeffs(KB_Q, [(0, 0), (KB_PW, 0), (KB_PW, KB_PH), (0, KB_PH)])
    wb = np.asarray(base.transform((W, H), Image.PERSPECTIVE, coeffs, Image.BICUBIC)).astype(np.float32)
    wr = np.asarray(rim.transform((W, H), Image.PERSPECTIVE, coeffs, Image.BICUBIC)).astype(np.float32) / 255
    ws = np.asarray(sheen.transform((W, H), Image.PERSPECTIVE, coeffs, Image.BICUBIC)).astype(np.float32) / 255
    ys = np.arange(H, dtype=np.float32)[:, None]
    # Lichtkanten: Hintergrundbeleuchtung, unten (näher) kräftiger
    wr = wr * (1 + 0.6 * np.clip((ys - 1550) / 360, 0, 1))
    wb += wr[..., None] * np.array([150, 162, 190], np.float32) * 0.8
    # Beschriftung leuchtet
    lum = wb.max(axis=2)
    legend = np.clip((lum - 120) / 100, 0, 1)
    glow = Image.fromarray((legend * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))
    wb += (np.asarray(glow).astype(np.float32) / 255 * 36)[..., None] * np.array([0.9, 0.92, 1.0])
    # Tiefenunschärfe: nach unten (näher an der Kamera) stärker
    sharp = Image.fromarray(np.clip(wb, 0, 255).astype(np.uint8))
    soft = sharp.filter(ImageFilter.GaussianBlur(7))
    k = np.clip((ys[..., None] - 1640) / 240, 0, 1)
    kb = np.asarray(sharp).astype(np.float32) * (1 - k) + np.asarray(soft).astype(np.float32) * k
    near = np.exp(-(ys - 1480) / 200)
    mask = np.asarray(quad_mask(KB_Q)).astype(np.float32)[..., None] / 255
    sheen_m = np.asarray(Image.fromarray((ws * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.5))).astype(np.float32) / 255
    return kb * mask, (sheen_m * near)[..., None] * mask


# ================================================================= Laptop-Gehäuse
SS = 3


def build_laptop():
    """Deckel als flache Fläche (abgerundet, Lichtkante), perspektivisch und überabgetastet gerendert."""
    S2 = 2
    flat = Image.new("RGBA", (LID_FW * S2, LID_FH * S2), (0, 0, 0, 0))
    d = ImageDraw.Draw(flat)
    d.rounded_rectangle((0, 0, LID_FW * S2 - 1, LID_FH * S2 - 1), radius=36 * S2, fill=(9, 9, 11, 255))
    # Lichtkante oben: links violett, nach rechts auslaufend
    for k in range(60):
        u = k / 60
        col = tuple(int(lerp_(a_, b_, u)) for a_, b_ in zip((95, 65, 115), (35, 28, 45)))
        d.line((36 * S2 + (LID_FW - 72) * S2 * u, 2, 36 * S2 + (LID_FW - 72) * S2 * (u + 1 / 60) + 2, 2), fill=col + (255,), width=3)
    d.line((2, 40 * S2, 2, (LID_FH - 40) * S2), fill=(55, 52, 62, 255), width=5)
    big = (W * SS, H * SS)
    dst = [(x * SS, y * SS) for x, y in LID_Q]
    lid = flat.transform(big, Image.PERSPECTIVE, persp_coeffs(dst, [(0, 0), (flat.width, 0), (flat.width, flat.height), (0, flat.height)]),
                         Image.BICUBIC)
    lay = Image.new("RGBA", big, (0, 0, 0, 0))
    dd = ImageDraw.Draw(lay)
    dd.polygon([(x * SS, y * SS) for x, y in DECK_Q[:4]] + [(1120 * SS, 1470 * SS), (-30 * SS, 1530 * SS), (-30 * SS, 1500 * SS)],
               fill=(18, 18, 22, 255))
    dd.polygon([(-30 * SS, 1530 * SS), (1120 * SS, 1470 * SS), (1120 * SS, 1490 * SS), (-30 * SS, 1552 * SS)], fill=(12, 12, 15, 255))
    lay.alpha_composite(lid)
    return lay.resize((W, H), Image.LANCZOS)


def lerp_(a, b, t):
    return a + (b - a) * t


def screen_mask():
    """Aktive Bildfläche mit leicht gerundeten Ecken (überabgetastet)."""
    S2 = 2
    _l, _t, _r, _b = LID_INSET
    fw, fh = (LID_FW - _l - _r) * S2, (LID_FH - _t - _b) * S2
    flat = Image.new("L", (fw, fh), 0)
    ImageDraw.Draw(flat).rounded_rectangle((0, 0, fw - 1, fh - 1), radius=10 * S2, fill=255)
    dst = [(x * SS, y * SS) for x, y in SCREEN_Q]
    mk = flat.transform((W * SS, H * SS), Image.PERSPECTIVE, persp_coeffs(dst, [(0, 0), (fw, 0), (fw, fh), (0, fh)]), Image.BICUBIC)
    return mk.resize((W, H), Image.LANCZOS)


def deck_mask():
    mk = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mk).polygon(DECK_Q, fill=255)
    return np.asarray(mk.filter(ImageFilter.GaussianBlur(6))).astype(np.float32)[..., None] / 255


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
        if abs((boxes[i][2] - boxes[i][0]) - (boxes[i - 1][2] - boxes[i - 1][0])) < 4 * r:
            x0_, x1_ = min(boxes[i][0], boxes[i - 1][0]), max(boxes[i][2], boxes[i - 1][2])
            boxes[i][0] = boxes[i - 1][0] = x0_
            boxes[i][2] = boxes[i - 1][2] = x1_
    for b in boxes:
        d.rounded_rectangle(b, radius=r, fill=(252, 253, 253, 255))
    # konkave Innenecken dort, wo ein schmaler auf einen breiten Kasten trifft
    for i in range(1, len(boxes)):
        up, lo = boxes[i - 1], boxes[i]
        if abs((lo[2] - lo[0]) - (up[2] - up[0])) < 1:
            d.rectangle((lo[0], lo[1] - r, lo[2], lo[1] + r), fill=(252, 253, 253, 255))
            continue
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
        _STATIC["kb"], _STATIC["sheen"] = build_keyboard()
        _STATIC["kbm"] = (np.asarray(quad_mask(KB_Q)).astype(np.float32) / 255)[..., None]
        _STATIC["laptop"] = np.asarray(build_laptop()).astype(np.float32)
        _STATIC["deck"] = deck_mask()
        _STATIC["scr_mask"] = np.asarray(screen_mask()).astype(np.float32)[..., None] / 255
        _STATIC["coeffs"] = persp_coeffs(SCREEN_Q, [(0, 0), (SCR_W, 0), (SCR_W, SCR_H), (0, SCR_H)])
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H * 0.55) / H) ** 2)
        _STATIC["vig"] = (1 - 0.5 * np.clip(r * 1.6 - 0.35, 0, 1) ** 1.5)[..., None]
        # schwacher Glanz (Spiegelung der LED) auf dem Display
        gl = np.clip(1 - np.abs((xx - 0.55 * yy) - (-260)) / 260, 0, 1) * np.clip((1100 - xx) / 900, 0, 1)
        _STATIC["glare"] = (gl * 5)[..., None] * np.array([1.0, 0.45, 1.0])
        # Blickwinkel: rechts/unten etwas dunkler; niederfrequente Moiré-Bänder
        cf = persp_coeffs(SCREEN_Q, [(0, 0), (1, 0), (1, 1), (0, 1)])
        den = cf[6] * xx + cf[7] * yy + 1
        u = np.clip((cf[0] * xx + cf[1] * yy + cf[2]) / den, 0, 1)
        v = np.clip((cf[3] * xx + cf[4] * yy + cf[5]) / den, 0, 1)
        off = 1 - 0.16 * u ** 1.2 - 0.12 * u * v
        _STATIC["screen_mul"] = off[..., None]
        # Kamera-Weg: geglätteter Zufallspfad + zwei kleine Rucke
        rng = np.random.default_rng(31)
        n = 1200
        walk = np.cumsum(rng.standard_normal((n, 3)), 0)
        k_ = np.ones(90) / 90
        walk = np.stack([np.convolve(walk[:, i], k_, mode="same") for i in range(3)], 1)
        walk -= walk.mean(0)
        walk /= np.abs(walk).max(0) + 1e-6
        _STATIC["walk"] = walk
    return _STATIC


def filmed_screen(scr):
    """LCD wie vom Handy gefilmt: tiefes, leicht violettes Schwarz, warme gedämpfte Lichter, weiche Kanten,
    Halation an hellen Stellen und ein leichter Schärfungs-Saum wie bei Handy-Videos."""
    a = np.asarray(scr.convert("RGB")).astype(np.float32) / 255
    lift = np.array([0.015, 0.014, 0.024])
    gain = np.array([0.82, 0.785, 0.72])
    a = lift + gain * a ** 1.12
    out = Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2.0))
    o = np.asarray(out).astype(np.float32)
    hot = Image.fromarray(np.clip(o.max(axis=2) - 170, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(5))
    o += (np.asarray(hot).astype(np.float32) * 0.35)[..., None]
    small = out.resize((SCR_W // 8, SCR_H // 8), Image.BILINEAR).filter(ImageFilter.GaussianBlur(4))
    b = np.asarray(small.resize((SCR_W, SCR_H), Image.BILINEAR)).astype(np.float32)
    o = o + np.clip(b - 120, 0, 255) * 0.2
    x = o / 255
    o = 255 * np.where(x < 0.72, x, 0.72 + 0.28 * (1 - np.exp(-(x - 0.72) / 0.28)))
    im = Image.fromarray(np.clip(o, 0, 255).astype(np.uint8))
    return im.filter(ImageFilter.UnsharpMask(radius=2, percent=40, threshold=2))


def camera(t):
    """Fast ruhige Handyaufnahme: langsamer Zufallspfad (vertikal mehr), zwei kleine Rucke.
    Mit LOOP gesetzt schließt der Pfad nahtlos (Ende = Anfang)."""
    walk = static()["walk"]
    fps_ = 60.0
    def at(tt):
        i = tt * fps_
        i0 = int(math.floor(i)) % len(walk)
        f = i - math.floor(i)
        return walk[i0] * (1 - f) + walk[(i0 + 1) % len(walk)] * f
    w_ = at(t)
    if LOOP:
        w_ = w_ - (at(LOOP) - at(0.0)) * (t / LOOP)
    dx, dy, rot = w_[0] * 1.0, w_[1] * 5.0, w_[2] * 0.08
    for tb, amp in ((0.6, 4.0), (9.6, 3.0)):
        if LOOP is None or tb < LOOP:
            u = (t - tb) / 0.12
            if 0 <= u:
                dy += amp * (1 - math.exp(-u * 3)) * math.exp(-max(0.0, t - tb - 0.12) * 1.2)
    return dx, dy, rot, 1.03


def compose(scr, t, overlay, exposure=1.0, seed=0):
    st = static()
    film = filmed_screen(scr)
    warped = np.asarray(film.transform((W, H), Image.PERSPECTIVE, st["coeffs"], Image.BICUBIC)).astype(np.float32)
    mean = np.asarray(film.resize((16, 10), Image.BOX)).astype(np.float32).reshape(-1, 3).mean(0)
    # Raumlicht folgt der Bildschirmhelligkeit (dunkel -45 %, hell +25 %)
    luma = float(mean.mean())
    room = float(np.interp(luma, [5, 30, 190], [0.55, 1.0, 1.25]))
    img = st["bg"] * (0.75 + 0.25 * room)
    la = st["laptop"]
    img = img * (1 - la[..., 3:] / 255) + la[..., :3] * (la[..., 3:] / 255)
    img += st["deck"] * mean * 0.5                                     # Bildschirmlicht auf dem Gehäuse
    m_ = st["scr_mask"]
    img = img * (1 - m_) + (warped * st["screen_mul"] + st["glare"]) * m_
    kbm = st["kbm"]
    kb = st["kb"] * (0.6 + 0.4 * room) + st["sheen"] * mean * 0.55
    img = img * (1 - kbm) + kb * kbm
    # Kamera
    dx, dy, rot, zoom = camera(t)
    im = Image.fromarray(np.clip(img * exposure, 0, 255).astype(np.uint8))
    im = im.rotate(rot, resample=Image.BICUBIC, center=(W / 2, H * 0.55), translate=(dx, dy))
    w2, h2 = W / zoom, H / zoom
    im = im.transform((W, H), Image.EXTENT, ((W - w2) / 2, (H - h2) / 2, (W + w2) / 2, (H + h2) / 2), Image.BICUBIC)
    arr = np.asarray(im).astype(np.float32) * st["vig"]
    arr = np.clip((arr - 7) * 255 / 248, 0, 255)                        # Schwarz absaufen lassen (Handy-Nachtvideo)
    def nz(sd):
        return np.random.default_rng(sd).normal(0, 1.3, (H // 4, W // 4)).astype(np.float32)
    noise = 0.6 * nz(seed) + 0.4 * nz(seed + 100000 - 1)
    noise = np.asarray(Image.fromarray(noise).resize((W, H), Image.BILINEAR))
    arr += noise[..., None] * np.clip(arr / 12, 0, 1)
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
