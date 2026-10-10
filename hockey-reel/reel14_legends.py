"""Reel 14: TOP 5 FORGOTTEN LEGENDS – ranked by your likes.

Grundlage: die meistgelikten Antworten unter dem 80K-Video vom 11.12.2024 ("The forgotten legends of hockey –
Who comes to mind?", 1.788 Kommentare, 4.986 Likes, 80.499 Views; Windsor-Export vom 10.10.2026).
Ablauf (14,2 s, 150 BPM, Schläge bei 0,2 + 0,4·k):
  0.0–1.8   Hook: Kommentar-Sturm, Post-Karte "WE ASKED.", "1,788 COMMENTS LATER", "YOUR TOP 5" (0.6)
  1.8–3.4   #5 Sedin-Brüder (134 Likes)   3.4–5.8 #4 Bédard (181)   5.8–7.8 #3 Selänne (182)
  7.8–9.4   #2 Kane (211)                  9.4–10.2 Spannung: Silhouette + Trommelwirbel
  10.2–12.6 #1 Toews (285): Blitz, Goldstrahlen, Konfetti
  12.6–14.2 "WHO DID EVERYONE FORGET? / COMMENT A NAME", Überblendung in den Hook (Loop)
Übergänge = Swipe nach oben wie im TikTok-Feed. Spieler erscheinen schwarz-weiß ("vergessen") und werden
farbig, sobald der Like-Zähler steht ("erinnert").
Fotos (Wikimedia Commons): Henrik Sedin – Hockey Broad, CC BY-SA 2.0; Daniel Sedin – mark6mauno, CC BY 2.0;
Connor Bédard – Jenn G, CC BY-SA 2.0; Teemu Selänne – s.yume, CC BY 2.0; Patrick Kane, Jonathan Toews –
Lisa Gansky, CC BY-SA 2.0. Freisteller: prep_reel14_cuts.py. Stimme: vidIQ-Voiceover (Adam).
Aufruf: python3 reel14_legends.py  ->  reel14_legends.mp4
"""
import math
import os
import subprocess
import wave
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
from scipy.signal import fftconvolve

import make_hockey_reel as m
import reel3_cup_day as r3
import reel11b_fanwall as fx
from make_hockey_reel import font
from reel10_studio import (W, H, ORANGE, WHITE, c01, e_io, e_out, e_in, e_back, lerp, layer, glow_onto,
                           tracked, odometer, gradient_text, light_sweep)

FPS = 30
DUR = 14.2
HERE = m.HERE
r3.VOICE = os.path.join(HERE, "voice", "reel14.mp3")
VOICE_AT = [0.08, 1.86, 3.46, 5.86, 7.86, 9.32, 12.66]
GOLD = (255, 196, 70)
HEART = (254, 44, 85)
INK = (22, 22, 28)
GREY = (112, 112, 124)
VIOLET = (126, 100, 220)
SWIPE = 0.28
T_TOP5 = 0.6
T_TENSION, T_DROP, T_CTA = 9.4, 10.2, 12.6
T_FLOOD = 0.86                     # lokale Zeit, ab der die Farbe zurückkommt
EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
BRAND = os.path.join(HERE, "brand")

# echte Antworten unter dem Original-Video (für den Kommentar-Sturm im Hook)
STORM = ["Carry price", "Dustin Byfuglien ngl", "Rick Nash", "brandon holtby", "Tim horton", "leo komarov",
         "ryhan lash", "Peter Forsberg", "Kronwall", "Tory Krug", "Mats Sundin ngl", "bröderna sedin",
         "Börje Salming", "Joe Thornton", "Martin St. Louis", "Bobby Orr", "Dustin buflyn", "Japp Patrik hersley",
         "Sidney Crosby", "Guy Lafleur", "Ryan getzlaf ducks legend", "Chara,a bruins legend", "Jakub voreacheck",
         "Patrick laine", "Marcus Krüger", "patrice bergeron", "Trevor zegras", "Shea Weber",
         "Tbh zegras disappeared", "Wayne Gretzky", "Thearon fleury", "Darnell nurse", "Nicklas Bäckström",
         "Charlie simmer", "Al macinnis", "Taylor hall", "Pk Suban", "Dmitry orlov?", "mason mctavish",
         "Evgini malkin"]

# Rang -> Daten. cuts: (Freisteller, Skalierung, x, y, Helligkeit)
PL = {
    5: dict(t0=1.8, t1=3.4, first="HENRIK & DANIEL", last="SEDINS", fact="1,000+ NHL POINTS EACH",
            user="tylerhockey_forlife", text="Sedin brothers", likes=134,
            cuts=[("sedin_henrik", 1.25, 226, 395, 0.82), ("sedin_daniel", 1.0, 225, 470, 1.0)], badge=(178, 420),
            credit="Photos: Hockey Broad / CC BY-SA 2.0  ·  mark6mauno / CC BY 2.0"),
    4: dict(t0=3.4, t1=5.8, first="CONNOR", last="BÉDARD", fact="#1 OVERALL PICK 2023",
            user="ceaseglazeralt84", likes=181,
            text="Hear me out, Bédard. Cuz everyone was so hyped abt him and now he’s an average nhl player",
            cuts=[("bedard", 1.0, 80, 340, 1.0)], credit="Photo: Jenn G / CC BY-SA 2.0"),
    3: dict(t0=5.8, t1=7.8, first="TEEMU", last="SELÄNNE", fact="76 GOALS AS A ROOKIE – STILL THE RECORD",
            user="kaljakeisari", text="I think selänne no one talk about him now", likes=182,
            cuts=[("selanne_oly", 0.86, 230, 330, 1.0)], credit="Photo: s.yume / CC BY 2.0"),
    2: dict(t0=7.8, t1=9.4, first="PATRICK", last="KANE", fact="3× STANLEY CUP CHAMPION",
            user="rehnen2009", text="Patrick kane", likes=211,
            cuts=[("kane", 1.12, 40, 340, 1.0)], credit="Photo: Lisa Gansky / CC BY-SA 2.0"),
    1: dict(t0=T_DROP, t1=T_CTA, first="JONATHAN", last="TOEWS", fact="CAPTAIN OF 3 STANLEY CUP WINNERS",
            user="ott.masonn31", text="Jonathan Toews 💔", likes=285,
            cuts=[("toews", 1.14, 30, 340, 1.0)], credit="Photo: Lisa Gansky / CC BY-SA 2.0"),
}
for _r, _p in PL.items():
    _p["rank"] = _r

FADE_Y0, FADE_Y1 = 760, 1060       # Spieler blendet nach unten aus (Platz für Name, Fakt, Karte)
NAME_Y, FIRST_Y, FACT_Y = 1036, 893, 1174
CARD_X, CARD_W, CARD_TOP, CM = 70, 860, 1238, 36
AV_COLS = [(255, 146, 60), (64, 170, 255), (126, 100, 220), (60, 190, 130), (240, 84, 120)]


# ================================================================= Text mit Emoji
_EMO = {}


def emoji_img(ch, size):
    key = (ch, int(size))
    if key not in _EMO:
        f = ImageFont.truetype(EMOJI_FONT, 109)
        im = Image.new("RGBA", (190, 190), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((95, 95), ch, font=f, embedded_color=True, anchor="mm")
        im = im.crop(im.getbbox())
        s = size / max(im.width, im.height)
        _EMO[key] = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    return _EMO[key]


def runs(txt):
    out, cur = [], ""
    for ch in txt:
        if ch == "️":
            continue
        if ord(ch) >= 0x2600:
            if cur:
                out.append(("t", cur))
                cur = ""
            out.append(("e", ch))
        else:
            cur += ch
    if cur:
        out.append(("t", cur))
    return out


def rich_width(txt, f, esz):
    return sum(f.getlength(s) if k == "t" else esz * 1.12 for k, s in runs(txt))


def draw_rich(img, x, cy, txt, f, fill, esz):
    d = ImageDraw.Draw(img)
    for k, s in runs(txt):
        if k == "t":
            d.text((x, cy), s, font=f, fill=fill, anchor="lm")
            x += f.getlength(s)
        else:
            e = emoji_img(s, esz)
            img.alpha_composite(e, (int(x + esz * 0.06), int(cy - e.height / 2)))
            x += esz * 1.12


def wrap_rich(txt, f, esz, maxw):
    lines, cur = [], ""
    for w_ in txt.split(" "):
        test = w_ if not cur else cur + " " + w_
        if rich_width(test, f, esz) <= maxw or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w_
    lines.append(cur)
    return lines


def heart_poly(cx, cy, s):
    pts = []
    for k in range(48):
        a = 2 * math.pi * k / 48
        pts.append((cx + 16 * math.sin(a) ** 3 * s,
                    cy - (13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)) * s))
    return pts


def bubble_icon(d, cx, cy, s, col):
    d.rounded_rectangle((cx - 15 * s, cy - 12 * s, cx + 15 * s, cy + 9 * s), radius=8 * s, fill=col)
    d.polygon([(cx - 7 * s, cy + 7 * s), (cx - 9 * s, cy + 16 * s), (cx + 2 * s, cy + 8 * s)], fill=col)


def anton_fit(txt, size, maxw):
    return fx.fit(txt, "anton", size, maxw)


# ================================================================= Hintergrund
_BG = None


def bg_base():
    global _BG
    if _BG is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H * 0.38) / H) ** 2 * 0.55)
        k = np.clip(1 - r * 1.55, 0, 1) ** 1.4
        inner, outer = np.array([62, 52, 92], np.float32), np.array([11, 9, 18], np.float32)
        rgb = outer + (inner - outer) * k[..., None]
        # feine Eis-Struktur
        rng = np.random.default_rng(4)
        n = rng.normal(0, 1, (H // 6, W // 6)).astype(np.float32)
        n = np.asarray(Image.fromarray(((n + 3) * 40).clip(0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC))
        rgb += (n.astype(np.float32)[..., None] - 120) * 0.035
        _BG = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert("RGBA")
    return _BG


_STORM = None


def storm_layers():
    """Zwei Ebenen aus Kommentar-Pillen, je Spalte gleichmäßig verteilt; Periode P für nahtloses Scrollen."""
    global _STORM
    if _STORM is None:
        _STORM = []
        # Periode P und Pillen pro Spalte je Ebene; Geschwindigkeit = P / DUR -> nahtloser Loop
        for size, ph, alpha, blur, P, per, xs, seed in ((25, 52, 0.42, 1.4, 1300, 4, (110, 370, 640, 900), 3),
                                                         (31, 64, 0.80, 0.0, 2600, 7, (190, 520, 860), 9)):
            strip = Image.new("RGBA", (W, P), (0, 0, 0, 0))
            f = font("SemiBold", size)
            rng = np.random.default_rng(seed)
            order = list(rng.permutation(len(STORM)))
            k = 0
            for ci, cx in enumerate(xs):
                for j in range(per):
                    txt = STORM[order[k % len(order)]]
                    k += 1
                    y = (j + 0.5) * P / per + rng.uniform(-60, 60) + ci * 37
                    tw = f.getlength(txt)
                    pw = tw + ph + 34
                    x0 = cx + rng.uniform(-50, 50) - pw / 2
                    pill = Image.new("RGBA", (int(pw) + 4, ph + 4), (0, 0, 0, 0))
                    pd = ImageDraw.Draw(pill)
                    pd.rounded_rectangle((2, 2, pw, ph), radius=ph / 2, fill=(255, 255, 255, 30),
                                         outline=(255, 255, 255, 70), width=2)
                    col = AV_COLS[(k * 3 + ci) % len(AV_COLS)]
                    pd.ellipse((10, 10, ph - 6, ph - 6), fill=col + (230,))
                    pd.text((ph + 8, ph / 2 + 2), txt, font=f, fill=(238, 238, 246, 255), anchor="lm")
                    for yy in (y % P, y % P - P):          # über den Rand -> oben wieder hinein
                        fx.put_img(strip, pill, x0, yy - ph / 2)
            if blur:
                strip = strip.filter(ImageFilter.GaussianBlur(blur))
            strip = fx.fade_layer(strip, alpha)
            tall = Image.new("RGBA", (W, P + H), (0, 0, 0, 0))
            for k2 in range(0, P + H, P):
                tall.alpha_composite(strip.crop((0, 0, W, min(P, P + H - k2))), (0, k2))
            _STORM.append((tall, P, P / DUR))
    return _STORM


_DIM = None


def center_dim():
    global _DIM
    if _DIM is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / 610) ** 2 + ((yy - 880) / 600) ** 2)
        a = np.clip((1.12 - r) / 0.42, 0, 1) ** 1.3 * 205
        _DIM = Image.fromarray(np.dstack([np.full((H, W, 3), (14, 11, 22), np.uint8), a.astype(np.uint8)]), "RGBA")
    return _DIM


def storm_bg(t):
    img = bg_base().copy()
    for tall, P, speed in storm_layers():               # Kommentare steigen nach oben
        off = int((speed * t) % P)
        img.alpha_composite(tall.crop((0, off, W, off + H)))
    img.alpha_composite(center_dim())
    return img


# ================================================================= Spieler (Freisteller, s/w -> Farbe)
_BUST = {}


def bust_assets(rank):
    if rank in _BUST:
        return _BUST[rank]
    P = PL[rank]
    col = layer()
    for name, sc, x, y, lum in P["cuts"]:
        cut = Image.open(os.path.join(HERE, "photos", f"{name}_cut.png")).convert("RGBA")
        cut = cut.resize((int(cut.width * sc), int(cut.height * sc)), Image.LANCZOS)
        if lum < 1:
            a_ = cut.getchannel("A")
            cut = Image.eval(cut.convert("RGB"), lambda v: int(v * lum)).convert("RGBA")
            cut.putalpha(a_)
        fx.put_img(col, cut, x, y)
    arr = np.asarray(col).astype(np.float32)
    ys = np.arange(H, dtype=np.float32)[:, None]
    fade = np.clip((FADE_Y1 - ys) / (FADE_Y1 - FADE_Y0), 0, 1)
    a = arr[..., 3] * fade
    rgb = arr[..., :3] * (0.42 + 0.58 * fade[..., None])
    lum_ = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    color = (rgb - lum_[..., None]) * 1.12 + lum_[..., None]
    color = (color - 128) * 1.07 + 128
    bw = lum_[..., None] * np.array([0.9, 0.95, 1.07], np.float32)
    bw = (bw - 128) * 0.9 + 112
    al = Image.fromarray(a.astype(np.uint8))
    rim_a = ImageChops.subtract(al, al.filter(ImageFilter.MinFilter(7))).filter(ImageFilter.GaussianBlur(1.4))
    rim_a = np.asarray(rim_a).astype(np.float32) * np.clip(1.2 - (ys - 300) / 900, 0, 1)
    rim = Image.new("RGBA", (W, H), (215, 232, 255, 0))
    rim.putalpha(Image.fromarray(np.clip(rim_a * 1.1, 0, 255).astype(np.uint8)))
    glow_col = GOLD if rank == 1 else VIOLET
    halo = Image.new("RGBA", (W, H), glow_col + (0,))
    halo.putalpha(al.resize((W // 4, H // 4)).filter(ImageFilter.GaussianBlur(16)).resize((W, H), Image.BILINEAR)
                  .point(lambda v: int(v * 0.8)))
    bbox = al.getbbox()
    mk = lambda c: Image.fromarray(np.dstack([np.clip(c, 0, 255), a]).astype(np.uint8), "RGBA")
    _BUST[rank] = dict(color=mk(color), bw=mk(bw), rim=rim, halo=halo, bbox=bbox, alpha=al)
    return _BUST[rank]


def flood(B, q):
    """s/w -> Farbe, Front läuft von unten nach oben (q 0..1) mit leuchtender Kante."""
    if q <= 0:
        return B["bw"].copy()
    if q >= 1:
        return B["color"].copy()
    x0, y0, x1, y1 = B["bbox"]
    img = B["bw"].copy()
    rc = np.asarray(B["color"].crop(B["bbox"])).astype(np.float32)
    rb = np.asarray(B["bw"].crop(B["bbox"])).astype(np.float32)
    band = 160
    yf = y1 - q * (y1 - y0 + band)
    ys = np.arange(y0, y1, dtype=np.float32)[:, None]
    mk = np.clip((ys - yf) / band, 0, 1)[..., None]
    rgb = rb[..., :3] * (1 - mk) + rc[..., :3] * mk
    line = np.exp(-((ys - yf - band * 0.15) / 14) ** 2)[..., None] * np.array([255, 205, 150], np.float32)
    rgb += line * (rc[..., 3:4] / 255) * 0.95
    out = np.concatenate([np.clip(rgb, 0, 255), rc[..., 3:4]], -1)
    img.paste(Image.fromarray(out.astype(np.uint8), "RGBA"), (x0, y0))
    return img


def bust_layer(rank, q, lt, dur, sil=0.0):
    B = bust_assets(rank)
    out = B["halo"].copy()
    if sil > 0:                                     # Silhouette (Spannung vor #1)
        body = Image.new("RGBA", (W, H), (10, 8, 16, 0))
        body.putalpha(B["alpha"])
        out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        out.alpha_composite(fx.fade_layer(B["halo"].copy(), 0.6))
        out.alpha_composite(body)
        rim = Image.new("RGBA", (W, H), GOLD + (0,))
        rim.putalpha(B["rim"].getchannel("A").point(lambda v: min(255, int(v * 1.6 * sil))))
        out.alpha_composite(rim)
    else:
        out.alpha_composite(flood(B, q))
        out.alpha_composite(B["rim"])
    sc = 1 + 0.035 * e_io(c01(lt / dur))
    dy = 70 * (1 - e_out(lt / 0.55, 3))
    big = out.resize((int(W * sc), int(H * sc)), Image.BILINEAR) if sc > 1.002 else out
    res = layer()
    fx.put_img(res, big, 540 - 540 * sc, 800 - 800 * sc + dy)
    return res


# ================================================================= Karten
_CARD = {}


def card_static(rank):
    if rank in _CARD:
        return _CARD[rank]
    P = PL[rank]
    fs = 40 if len(P["text"]) <= 30 else 32
    f = font("ExtraBold", fs)
    tx = 128
    lines = wrap_rich(P["text"], f, fs * 1.05, CARD_W - tx - 104)
    lh = int(fs * 1.3)
    h = 30 + 30 + 14 + lh * len(lines) + 10 + 26 + 26
    c = Image.new("RGBA", (CARD_W + 2 * CM, h + 2 * CM), (0, 0, 0, 0))
    sh = Image.new("L", c.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle((CM, CM + 16, CM + CARD_W, CM + 16 + h), radius=30, fill=170)
    c.putalpha(sh.filter(ImageFilter.GaussianBlur(16)))
    d = ImageDraw.Draw(c)
    d.rounded_rectangle((CM, CM, CM + CARD_W, CM + h), radius=30, fill=(247, 247, 250, 255))
    col = AV_COLS[sum(map(ord, P["user"])) % len(AV_COLS)]
    d.ellipse((CM + 26, CM + 26, CM + 108, CM + 108), fill=col + (255,))
    d.text((CM + 67, CM + 68), P["user"][0].upper(), font=font("Black", 40), fill=WHITE + (255,), anchor="mm")
    d.text((CM + tx, CM + 46), P["user"], font=font("SemiBold", 27), fill=(92, 92, 104, 255), anchor="lm")
    y = CM + 30 + 30 + 14 + lh / 2
    for ln in lines:
        draw_rich(c, CM + tx, y, ln, f, INK + (255,), fs * 1.05)
        y += lh
    d.text((CM + tx, y - lh / 2 + 10 + 13), "Reply", font=font("SemiBold", 23), fill=(150, 150, 162, 255), anchor="lm")
    _CARD[rank] = (c, h)
    return _CARD[rank]


HEART_DX, HEART_DY = CARD_W - 60, 64


def card_frame(rank, prog, pop):
    base, h = card_static(rank)
    c = base.copy()
    d = ImageDraw.Draw(c)
    hx, hy = CM + HEART_DX, CM + HEART_DY
    if pop <= 0:
        pts = heart_poly(hx, hy, 1.5)
        d.line(pts + pts[:1], fill=(150, 150, 162, 255), width=4, joint="curve")
    else:
        s = 1.5 * lerp(0.4, 1.0, e_back(c01(pop / 0.22), 2.6))
        d.polygon(heart_poly(hx, hy, s), fill=HEART + (255,))
    odometer(c, str(PL[rank]["likes"]), hx, hy + 54, 29, prog, "Black", (64, 64, 74), stagger=0.18, spins=1)
    return c, h


_POST = None


def post_card():
    """Die Original-Caption des 80K-Videos als Post-Karte."""
    global _POST
    if _POST is None:
        cw, h = 920, 330
        c = Image.new("RGBA", (cw + 2 * CM, h + 2 * CM), (0, 0, 0, 0))
        sh = Image.new("L", c.size, 0)
        ImageDraw.Draw(sh).rounded_rectangle((CM, CM + 18, CM + cw, CM + 18 + h), radius=34, fill=190)
        c.putalpha(sh.filter(ImageFilter.GaussianBlur(18)))
        d = ImageDraw.Draw(c)
        d.rounded_rectangle((CM, CM, CM + cw, CM + h), radius=34, fill=(248, 248, 251, 255))
        av = Image.open(os.path.join(BRAND, "bladesandpucks_profilbild_1080.png")).convert("RGBA").resize((92, 92), Image.LANCZOS)
        mk = Image.new("L", (92, 92), 0)
        ImageDraw.Draw(mk).ellipse((0, 0, 91, 91), fill=255)
        av.putalpha(mk)
        c.alpha_composite(av, (CM + 30, CM + 28))
        d.text((CM + 140, CM + 56), "bladesandpucks", font=font("Black", 32), fill=INK + (255,), anchor="lm")
        d.text((CM + 140, CM + 96), "Dec 11, 2024", font=font("SemiBold", 24), fill=GREY + (255,), anchor="lm")
        f = font("ExtraBold", 44)
        draw_rich(c, CM + 34, CM + 168, "The forgotten legends of hockey 🏒❄️", f, INK + (255,), 46)
        draw_rich(c, CM + 34, CM + 226, "Who comes to mind? 🤔", f, INK + (255,), 46)
        y = CM + 286
        fs = font("Bold", 28)
        x = CM + 40
        d.polygon(heart_poly(x + 14, y, 0.95), fill=HEART + (255,))
        d.text((x + 42, y), "4,986", font=fs, fill=(70, 70, 80, 255), anchor="lm")
        x += 42 + fs.getlength("4,986") + 50
        bubble_icon(d, x + 14, y - 2, 1.0, ORANGE + (255,))
        fb = font("Black", 30)
        d.text((x + 42, y), "1,788", font=fb, fill=(226, 112, 20, 255), anchor="lm")
        x += 42 + fb.getlength("1,788") + 50
        d.polygon([(x + 4, y - 14), (x + 4, y + 14), (x + 28, y)], fill=(70, 70, 80, 255))
        d.text((x + 42, y), "80.5K", font=fs, fill=(70, 70, 80, 255), anchor="lm")
        _POST = c
    return _POST


# ================================================================= Gemeinsame Bausteine
_NUM = {}


def numeral(rank):
    if rank not in _NUM:
        f = font("anton", 1000)
        lay = Image.new("RGBA", (1100, 1500), (0, 0, 0, 0))
        col = GOLD if rank == 1 else ORANGE
        ImageDraw.Draw(lay).text((550, 750), str(rank), font=f, fill=(0, 0, 0, 0), stroke_width=5,
                                 stroke_fill=col + (80,), anchor="mm")
        _NUM[rank] = lay.crop(lay.getbbox())
    return _NUM[rank]


_BADGE = {}


def badge(rank):
    if rank not in _BADGE:
        col = GOLD if rank == 1 else ORANGE
        f = font("anton", 230)
        lay = Image.new("RGBA", (520, 360), (0, 0, 0, 0))
        ImageDraw.Draw(lay).text((260, 180), f"#{rank}", font=f, fill=col + (255,), anchor="mm")
        lay = lay.crop(lay.getbbox())
        g = Image.new("RGBA", (lay.width + 80, lay.height + 80), (0, 0, 0, 0))
        g.alpha_composite(lay, (40, 40))
        glow = g.filter(ImageFilter.GaussianBlur(18))
        glow = fx.fade_layer(glow, 0.7)
        glow.alpha_composite(g)
        _BADGE[rank] = glow
    return _BADGE[rank]


BADGE_C = (205, 455)


def draw_badge(L, rank, lt, t0=0.10):
    p = c01((lt - t0) / 0.14)
    if p <= 0:
        return
    bx, by = PL[rank].get("badge", BADGE_C)
    b = badge(rank)
    sc = lerp(2.1, 1.0, e_in(p, 2))
    if lt > t0 + 0.14:
        sc *= 1 + 0.05 * math.exp(-(lt - t0 - 0.14) * 10) * math.sin((lt - t0 - 0.14) * 40)
    bi = b.resize((int(b.width * sc), int(b.height * sc)), Image.BILINEAR)
    fx.put_img(L, fx.fade_layer(bi, c01(p * 3)), bx - bi.width / 2, by - bi.height / 2)
    d = ImageDraw.Draw(L)
    fx.ring(d, bx, by, lt - t0 - 0.14, 0.4, 420, GOLD if rank == 1 else ORANGE, 10)


def pill(L, txt, cx, cy, p, col):
    if p <= 0:
        return
    f = font("Black", 31)
    w_ = (f.getlength(txt) + 60) * p
    h_ = 62 * min(1.0, p)
    d = ImageDraw.Draw(L)
    d.rounded_rectangle((cx - w_ / 2, cy - h_ / 2, cx + w_ / 2, cy + h_ / 2), radius=h_ / 2, fill=col + (255,))
    if p > 0.55:
        d.text((cx, cy + 1), txt, font=f, fill=INK + (int(255 * c01((p - 0.55) / 0.3)),), anchor="mm")


def shadow_onto(base, lay, radius=12, strength=0.8):
    """Weicher dunkler Schatten unter einer Textebene (Lesbarkeit auf hellen Trikots)."""
    a = lay.getchannel("A").resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(radius / 4))
    a = a.resize((W, H), Image.BILINEAR).point(lambda v: min(255, int(v * 1.6 * strength)))
    sh = Image.new("RGBA", (W, H), (6, 4, 12, 0))
    sh.putalpha(a)
    base.alpha_composite(sh)


_FLOOR = None


def floor():
    """Dunkler Verlauf unter dem Spieler, damit Name, Fakt und Karte frei stehen."""
    global _FLOOR
    if _FLOOR is None:
        ys = np.arange(H, dtype=np.float32)
        a = np.clip((ys - 800) / 260, 0, 1) ** 1.3 * 175
        a = np.broadcast_to(a[:, None], (H, W))
        _FLOOR = Image.fromarray(np.dstack([np.full((H, W, 3), (10, 8, 16), np.uint8), a.astype(np.uint8)]), "RGBA")
    return _FLOOR


def letters_up(lt, t0, stagger=0.025, dist=60, dur=0.26):
    return lambda i, n: (0, dist * (1 - e_out((lt - t0 - i * stagger) / dur)), e_out((lt - t0 - i * stagger) / (dur * 0.6)))


# ================================================================= Szenen (lt = lokale Zeit)
def rank_scene(rank, lt):
    P = PL[rank]
    dur = P["t1"] - P["t0"]
    reveal = rank == 1
    img = bg_base().copy()
    addq = fx.qcanvas()
    fx.rays(addq, lt + rank, 540, 640, (0.75 if reveal else 0.26) * e_out(lt / 0.4), GOLD if reveal else VIOLET)
    if reveal and lt < 0.8:
        fx.flare(addq, 540, 700, 1.1 * (1 - lt / 0.8) ** 2, (255, 210, 130))
    img = fx.add_light(img, addq)
    # Riesenziffer hinter dem Spieler
    num = numeral(rank)
    s = lerp(1.14, 1.0, e_out(lt / 0.7, 3))
    ni = num.resize((int(num.width * s), int(num.height * s)), Image.BILINEAR)
    fx.put_img(img, fx.fade_layer(ni, e_out(lt / 0.3)), 590 - ni.width / 2, 800 - ni.height / 2)
    em = layer()
    fx.embers(ImageDraw.Draw(em), lt + rank * 2.3, seed=rank, n=40)
    img.alpha_composite(fx.fade_layer(em, 0.55))
    # Spieler
    q = 1.0 if reveal else c01((lt - T_FLOOD) / 0.36)
    img.alpha_composite(bust_layer(rank, q, lt, dur))
    fxl = layer()
    fd = ImageDraw.Draw(fxl)
    if reveal:
        fx.sparks(fd, lt, [(60, H + 10), (W - 60, H + 10)], 41, n=60, spread=0.25, speed=(1400, 2000),
                  life=(0.6, 1.0), window=0.6, col=(255, 222, 150))
        fx.confetti(fd, lt + 0.6, n=120, seed=7, speed=1.0)
    img.alpha_composite(fxl)
    img.alpha_composite(floor())
    # Name, Fakt, Rang
    L = layer()
    fn = layer()
    tracked(fn, P["first"], 540, FIRST_Y, 40, "ExtraBold", (236, 236, 244), 10, per_letter=letters_up(lt, 0.16, 0.015, 26))
    shadow_onto(L, fn, 10, 0.85)
    L.alpha_composite(fn)
    size = anton_fit(P["last"], 200, 940)
    nm = layer()
    if reveal:
        gradient_text(nm, P["last"], 540, NAME_Y, size, "anton", (255, 246, 210), GOLD, (214, 128, 36), tracking=6)
        nm = fx.scale_layer(nm, lerp(1.5, 1.0, e_out(lt / 0.22, 3)), 540, NAME_Y)
        light_sweep(nm, c01((lt - 0.5) / 0.6))
    else:
        tracked(nm, P["last"], 540, NAME_Y, size, "anton", WHITE, 6, per_letter=letters_up(lt, 0.2, 0.03, 70))
    shadow_onto(L, nm, 16, 0.75)
    glow_onto(L, nm, 28, 0.4 if reveal else 0.25)
    pill(L, P["fact"], 540, FACT_Y, e_back(c01((lt - 0.42) / 0.3)), GOLD if reveal else ORANGE)
    draw_badge(L, rank, lt, 0.04 if reveal else 0.10)
    tracked(L, P["credit"], 540, 1880, 21, "SemiBold", (150, 150, 165), 1, alpha=0.85)
    img.alpha_composite(L)
    # Kommentar-Karte mit Like-Zähler
    c_in, c_cnt, c_pop = (0.32, 0.44, 0.96) if reveal else (0.30, 0.40, 0.84)
    cp = e_out(c01((lt - c_in) / 0.30), 3)
    if cp > 0:
        card, h = card_frame(rank, c01((lt - c_cnt) / 0.44), lt - c_pop)
        rot = lerp(-7, 0, cp)
        ci = card.rotate(rot, resample=Image.BICUBIC, expand=True) if abs(rot) > 0.05 else card
        y = CARD_TOP - CM + (1 - cp) * 320
        fx.put_img(img, fx.fade_layer(ci, c01(cp * 3)), CARD_X - CM - (ci.width - card.width) / 2,
                   y - (ci.height - card.height) / 2)
        pl = lt - c_pop
        if 0 <= pl < 0.6:
            sp = layer()
            hx, hy = CARD_X + HEART_DX, CARD_TOP + HEART_DY
            fx.sparks(ImageDraw.Draw(sp), pl, [(hx, hy)], 50 + rank, n=22, spread=3.1, speed=(260, 620), grav=500,
                      life=(0.25, 0.5), window=0.02, col=(255, 120, 150), width=4)
            if reveal:
                fx.confetti(ImageDraw.Draw(sp), pl + 0.9, n=60, seed=17, speed=1.2)
            img.alpha_composite(sp)
    return fx.to_arr(img)


def tension(lt):
    img = Image.blend(bg_base().convert("RGB"), Image.new("RGB", (W, H), (4, 3, 8)), 0.5).convert("RGBA")
    addq = fx.qcanvas()
    cone = np.clip(1 - np.abs(fx.QXX - fx.QW / 2) / (40 + fx.QYY * 0.35), 0, 1) * np.exp(-fx.QYY / 300)
    flick = 0.8 + 0.2 * math.sin(lt * 37) * math.sin(lt * 11)
    addq += cone[..., None] * np.array([255, 220, 160], np.float32) * 0.55 * flick * e_out(lt / 0.3)
    img = fx.add_light(img, addq)
    num = numeral(1)
    s = lerp(1.25, 1.06, e_out(lt / 0.8, 2))
    ni = num.resize((int(num.width * s), int(num.height * s)), Image.BILINEAR)
    fx.put_img(img, fx.fade_layer(ni, 0.9 * e_out(lt / 0.3)), 590 - ni.width / 2, 800 - ni.height / 2)
    sil = layer()
    sil.alpha_composite(bust_layer(1, 0, lt, 2.4, sil=0.6 + 0.4 * flick))
    img.alpha_composite(sil)
    L = layer()
    draw_badge(L, 1, lt, 0.12)
    q = layer()
    size = anton_fit("???", 215, 940)
    ImageDraw.Draw(q).text((540, NAME_Y), "???", font=font("anton", size), fill=(0, 0, 0, 0), stroke_width=4,
                           stroke_fill=GOLD + (int(255 * (0.55 + 0.45 * math.sin(lt * 14) ** 2) * e_out(lt / 0.3)),),
                           anchor="mm")
    glow_onto(L, q, 26, 0.5)
    img.alpha_composite(L)
    return fx.to_arr(img)


def hook_fg(lt, t, top5=True):
    L = layer()
    tracked(L, "WE ASKED.", 540, 468, 66, "Black", WHITE, 8)
    card = post_card()
    fx.put_img(L, card, 540 - card.width / 2, 548 - CM + 6 * math.sin(2 * math.pi * 3 * t / DUR))
    size = anton_fit("1,788 COMMENTS LATER", 130, 930)
    f = font("anton", size)
    w1, w2 = f.getlength("1,788 "), f.getlength("COMMENTS LATER")
    x = 540 - (w1 + w2) / 2
    d = ImageDraw.Draw(L)
    d.text((x, 1018), "1,788 ", font=f, fill=ORANGE + (255,), anchor="lm")
    d.text((x + w1, 1018), "COMMENTS LATER", font=f, fill=WHITE + (255,), anchor="lm")
    if top5 and lt >= T_TOP5:
        p = c01((lt - T_TOP5) / 0.12)
        sc = lerp(2.2, 1.0, e_in(p, 2))
        if lt > T_TOP5 + 0.12:
            sc *= 1 + 0.045 * math.exp(-(lt - T_TOP5 - 0.12) * 9) * math.sin((lt - T_TOP5 - 0.12) * 42)
        t5 = layer()
        size = anton_fit("YOUR TOP 5", 270, 960)
        f5 = font("anton", size)
        a1, a2 = f5.getlength("YOUR TOP "), f5.getlength("5")
        x = 540 - (a1 + a2) / 2
        td = ImageDraw.Draw(t5)
        td.text((x, 1250), "YOUR TOP ", font=f5, fill=WHITE + (255,), anchor="lm")
        td.text((x + a1, 1250), "5", font=f5, fill=ORANGE + (255,), anchor="lm")
        t5 = fx.scale_layer(t5, sc, 540, 1250)
        glow_onto(L, fx.fade_layer(t5, c01(p * 3)), 30, 0.45)
        fx.ring(d, 540, 1250, lt - T_TOP5 - 0.12, 0.45, 760, ORANGE, 14)
        fx.sparks(d, lt - T_TOP5 - 0.12, [(540, 1250)], 5, n=34, spread=2.9, speed=(500, 1300), grav=900,
                  life=(0.25, 0.5), window=0.02, col=(255, 214, 170), width=4)
    return L


def hook(lt, t):
    img = storm_bg(t)
    L = hook_fg(lt, t)
    img.alpha_composite(L)
    return fx.to_arr(img)


def cta_fg(lt):
    L = layer()
    tx = layer()
    for k, (txt, size, col, y) in enumerate((("WHO DID", 150, WHITE, 612), ("EVERYONE", 195, WHITE, 800),
                                              ("FORGET?", 195, ORANGE, 994))):
        tracked(tx, txt, 540, y, anton_fit(txt, size, 960), "anton", col, 6,
                per_letter=lambda i, n, k=k: (0, 0, 1.0) if lt > 1 else
                (0, 50 * (1 - e_out((lt - 0.06 - k * 0.1 - i * 0.02) / 0.22)), e_out((lt - 0.06 - k * 0.1 - i * 0.02) / 0.12)))
    glow_onto(L, tx, 30, 0.45)
    cm = layer()
    tracked(cm, "COMMENT A NAME", 540, 1172, 64, "Black", WHITE, 4,
            per_letter=lambda i, n: (0, 30 * (1 - e_out((lt - 0.45 - i * 0.015) / 0.25)), e_out((lt - 0.45 - i * 0.015) / 0.2)))
    if lt > 0.6:
        y = 1236 + abs(math.sin((lt - 0.6) * 6)) * 22
        ImageDraw.Draw(cm).polygon([(540 - 36, y), (540 + 36, y), (540, y + 46)], fill=ORANGE + (255,))
    glow_onto(L, cm, 26, 0.5)
    return L


def cta(lt, t):
    img = storm_bg(t)
    xf = e_io(c01((t - (DUR - 0.46)) / 0.4))            # Überblendung in den Hook (Loop), fertig vor dem letzten Bild
    if xf < 1:
        img.alpha_composite(fx.fade_layer(cta_fg(lt), 1 - xf))
    if xf > 0:
        img.alpha_composite(fx.fade_layer(hook_fg(0.0, t, top5=False), xf))
    return fx.to_arr(img)


SCENES = [(0.0, 1.8, lambda lt, t: hook(lt, t)),
          (1.8, 3.4, lambda lt, t: rank_scene(5, lt)),
          (3.4, 5.8, lambda lt, t: rank_scene(4, lt)),
          (5.8, 7.8, lambda lt, t: rank_scene(3, lt)),
          (7.8, 9.4, lambda lt, t: rank_scene(2, lt)),
          (9.4, 10.2, lambda lt, t: tension(lt)),
          (10.2, 12.6, lambda lt, t: rank_scene(1, lt)),
          (12.6, DUR, lambda lt, t: cta(lt, t))]
SWIPES = {1.8, 3.4, 5.8, 7.8, 9.4, 12.6}


def swipe_p(x):
    x = c01(x / SWIPE)
    return x * x * (3 - 2 * x)


def vmblur(arr, k):
    """Vertikale Bewegungsunschärfe (Box, Länge 2k) über kumulierte Summen."""
    k = int(k)
    if k < 2:
        return arr
    pad = np.pad(arr, ((k, k), (0, 0), (0, 0)), mode="edge")
    cs = np.cumsum(pad, axis=0, dtype=np.float64)
    return ((cs[2 * k:] - cs[:-2 * k]) / (2 * k))[:H].astype(np.float32)


def scene_at(t):
    for k, (a, b, fn) in enumerate(SCENES):
        if a <= t < b or k == len(SCENES) - 1:
            break
    if a in SWIPES and t < a + SWIPE:                   # Swipe nach oben wie im Feed
        pa, _, fa = SCENES[k - 1]
        A, B = fa(t - pa, t), fn(t - a, t)
        sh = int(round(swipe_p(t - a) * H))
        out = np.empty_like(A)
        out[:H - sh] = A[sh:]
        out[H - sh:] = B[:sh]
        speed = (swipe_p(t - a + 0.004) - swipe_p(t - a - 0.004)) / 0.008 * H      # px/s
        return vmblur(out, speed / 120)                  # Verschlusszeit 1/60 s
    arr = fn(t - a, t)
    if T_DROP <= t < T_DROP + 0.4:                      # Blitz beim #1-Reveal
        w = (1 - e_out((t - T_DROP) / 0.4, 2)) * 0.95
        arr = arr * (1 - w) + np.array([255, 246, 225], np.float32) * w
    return arr


# ================================================================= Overlays (laufen nicht mit dem Swipe)
_WM = None


def watermark():
    global _WM
    if _WM is None:
        wm = Image.open(os.path.join(BRAND, "bladesandpucks_watermark_white.png")).convert("RGBA")
        s = 62 / wm.height
        _WM = fx.fade_layer(wm.resize((int(wm.width * s), 62), Image.LANCZOS), 0.55)
    return _WM


def current_rank(t):
    for r in (5, 4, 3, 2):
        if PL[r]["t0"] <= t + SWIPE / 2 < PL[r]["t1"]:
            return r
    return 1


def overlay(t):
    L = layer()
    wm = watermark()
    L.alpha_composite(wm, (W - 52 - wm.width, 204))
    a = e_io((t - 1.8) / SWIPE) * (1 - e_io((t - T_CTA) / SWIPE))
    if a > 0.01:
        tracked(L, "FORGOTTEN LEGENDS  ·  RANKED BY YOUR LIKES", 520, 236, 24, "Bold", (214, 208, 232), 4, alpha=a)
        cur = current_rank(t)
        d = ImageDraw.Draw(L)
        f = font("Black", 26)
        for k, r in enumerate((5, 4, 3, 2, 1)):
            x, y = 520 + (k - 2) * 66, 296
            if r == cur:
                col = GOLD if r == 1 else ORANGE
                d.ellipse((x - 25, y - 25, x + 25, y + 25), fill=col + (int(255 * a),))
                d.text((x, y + 1), str(r), font=f, fill=INK + (int(255 * a),), anchor="mm")
            elif r > cur:
                d.ellipse((x - 21, y - 21, x + 21, y + 21), fill=(255, 255, 255, int(70 * a)))
                d.text((x, y + 1), str(r), font=f, fill=(255, 255, 255, int(190 * a)), anchor="mm")
            else:
                d.ellipse((x - 21, y - 21, x + 21, y + 21), outline=(255, 255, 255, int(120 * a)), width=3)
                d.text((x, y + 1), str(r), font=f, fill=(255, 255, 255, int(150 * a)), anchor="mm")
    return L


# ================================================================= Nachbearbeitung
IMPACTS = [(T_TOP5 + 0.12, 0.7), (1.94, 0.4), (3.54, 0.4), (5.94, 0.4), (7.94, 0.4), (9.56, 0.5), (T_DROP, 1.3)]


def impact_env(t):
    return max([amp * math.exp(-(t - ti) * 10) for ti, amp in IMPACTS if t >= ti] + [0.0])


def shake(t):
    dx = dy = 0.0
    for k, (ti, amp) in enumerate(IMPACTS):
        lt = t - ti
        if 0 <= lt < 0.45:
            e = amp * 26 * math.exp(-lt * 9)
            dx += math.sin(lt * 97 + k) * e
            dy += math.cos(lt * 83 + 2 * k) * e
    return dx, dy


def bloom(arr):
    lum = arr.max(axis=2)
    br = arr * np.clip((lum - 225) / 30, 0, 1)[..., None]
    small = br.reshape(H // 8, 8, W // 8, 8, 3).mean(axis=(1, 3))
    im = Image.fromarray(np.clip(small, 0, 255).astype(np.uint8))
    b1 = np.asarray(im.filter(ImageFilter.GaussianBlur(3)).resize((W, H), Image.BILINEAR)).astype(np.float32)
    b2 = np.asarray(im.filter(ImageFilter.GaussianBlur(10)).resize((W, H), Image.BILINEAR)).astype(np.float32)
    return arr + b1 * 0.14 + b2 * 0.2


def post(arr, t, i):
    arr = bloom(arr)
    dx, dy = shake(t)
    if abs(dx) + abs(dy) > 0.5:
        im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        z = 1.04
        w2, h2 = W / z, H / z
        box = ((W - w2) / 2 + dx, (H - h2) / 2 + dy, (W + w2) / 2 + dx, (H + h2) / 2 + dy)
        arr = np.asarray(im.transform((W, H), Image.EXTENT, box, Image.BILINEAR)).astype(np.float32)
    k = int(round(8 * impact_env(t)))
    if k:
        arr[..., 0] = np.roll(arr[..., 0], k, 1)
        arr[..., 2] = np.roll(arr[..., 2], -k, 1)
    arr = arr * fx.vignette()
    arr += np.random.default_rng(i).normal(0, 2.2, arr.shape[:2])[..., None]
    return np.clip(arr, 0, 255).astype(np.uint8)


FAST = [(T_TOP5, T_TOP5 + 0.14, 3), (T_DROP, T_DROP + 0.1, 3)]


def frame_t(t):
    arr = scene_at(t)
    ov = np.asarray(overlay(t)).astype(np.float32)
    a = ov[..., 3:4] / 255
    return arr * (1 - a) + ov[..., :3] * a


def render_frame(i):
    t = i / FPS
    sub = next((k for a, b, k in FAST if a <= t < b), 1)
    if sub > 1:
        arr = sum(frame_t(max(0.0, min(DUR - 1e-3, t + dt))) for dt in (-1 / 90, 0, 1 / 90)) / 3
    else:
        arr = frame_t(t)
    return post(arr, t, i).tobytes()


# ================================================================= Sound
SR = 44100


def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(14)
    music, sfx, vox = np.zeros(n), np.zeros(n), np.zeros(n)

    def tt(sec):
        return np.arange(int(sec * SR)) / SR

    def put(buf, sig, at, vol=1.0):
        st = int(round(at * SR))
        if st < 0:
            sig, st = sig[-st:], 0
        e = min(n, st + len(sig))
        if st < n:
            buf[st:e] += sig[: e - st] * vol

    def lp(x, k):
        if k <= 1:
            return x
        c = np.cumsum(np.concatenate([np.zeros(k), x]))
        return (c[k:] - c[:-k]) / k

    def hp(x, k):
        return x - lp(x, k)

    def noise(sec):
        return rng.standard_normal(int(sec * SR))

    def kick():
        x = tt(0.45)
        f = 46 + 110 * np.exp(-x * 28)
        body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 7.5)
        return np.tanh((body + noise(0.45) * np.exp(-x * 400) * 0.3) * 2.2) * 0.9

    def clap():
        x = tt(0.3)
        out = np.zeros(len(x))
        nz = hp(noise(0.3), 6)
        for off, dec in ((0, 60), (0.011, 60), (0.022, 16)):
            st = int(off * SR)
            out[st:] += nz[: len(x) - st] * np.exp(-x[: len(x) - st] * dec)
        return lp(out, 2) * 0.55

    def snare(vol=1.0):
        x = tt(0.16)
        body = np.sin(2 * np.pi * 190 * x) * np.exp(-x * 30) * 0.5
        return (body + hp(noise(0.16), 3) * np.exp(-x * 26) * 0.6) * vol

    def hat(open_=False):
        d_ = 0.25 if open_ else 0.06
        x = tt(d_)
        return hp(noise(d_), 3) * np.exp(-x * (18 if open_ else 90)) * 0.22

    def sub(freq, dur):
        x = tt(dur)
        f = freq * (1 + 0.6 * np.exp(-x * 40))
        env = np.minimum(x / 0.005, 1) * np.clip((dur - x) / 0.06, 0, 1) * np.exp(-x * 1.2)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * 2.5) * env * 0.7

    def saws(freqs, dur, det=(-0.006, 0.0, 0.006)):
        x = tt(dur)
        sig = sum(2 * ((x * f * (1 + dd)) % 1) - 1 for f in freqs for dd in det)
        return lp(lp(sig, 7), 5) / (len(freqs) * len(det)), x

    def stab(freqs, dur=0.9, vol=0.9):
        sig, x = saws(freqs, dur)
        return sig * np.minimum(x / 0.008, 1) * np.exp(-x * 3.0) * vol

    def pad(freqs, dur, vol=0.18):
        sig, x = saws(freqs, dur)
        sig = lp(sig, 14)
        return sig * np.minimum(x / 0.25, 1) * np.clip((dur - x) / 0.25, 0, 1) * vol

    def boom(dur=2.0, f0=55, vol=1.0):
        x = tt(dur)
        f = f0 + 140 * np.exp(-x * 14)
        body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 2.2)
        tail = lp(noise(dur), 30) * np.exp(-x * 2.8) * 0.8
        hit = hp(noise(dur), 4) * np.exp(-x * 30) * 0.5
        return np.tanh((body + tail + hit) * 1.6) * 0.9 * vol

    def whoosh(dur=0.45, vol=1.0):
        x = tt(dur)
        nz = noise(dur)
        env = np.sin(np.pi * x / dur) ** 2
        lo, hi = lp(nz, 40), lp(nz, 8) - lp(nz, 40)
        mv = x / dur
        return (lo * (1 - mv) + hi * mv * 1.4) * env * 1.4 * vol

    def riser(dur, vol=1.0):
        x = tt(dur)
        sweep = np.sin(2 * np.pi * np.cumsum(200 + 1400 * (x / dur) ** 2) / SR) * (x / dur) ** 3 * 0.18
        return (hp(noise(dur), 5) * (x / dur) ** 2 * 0.5 + sweep) * vol

    def crash(vol=0.25):
        x = tt(1.6)
        return hp(noise(1.6), 2) * np.exp(-x * 2.6) * vol

    def horn(dur=1.6):
        x = tt(dur)
        sig = sum(2 * ((x * f * (1 + 0.003 * np.sin(2 * np.pi * 4.5 * x))) % 1) - 1 for f in (110.0, 138.6, 164.8))
        sig = lp(lp(sig, 10), 6)
        return sig / 3 * np.minimum(x / 0.06, 1) * np.clip((dur - x) / 0.35, 0, 1) * 0.75

    def crowd(dur, vol):
        x = tt(dur)
        a = lp(noise(dur), 14) * 3
        mod = 0.75 + 0.25 * np.sin(2 * np.pi * 0.7 * x + 1) * np.sin(2 * np.pi * 0.23 * x)
        return a * mod * vol

    def crackle(dur, density=140, vol=0.35):
        x = np.zeros(int(dur * SR))
        for _ in range(int(dur * density)):
            p = int(rng.integers(0, len(x) - 300))
            amp = rng.uniform(0.2, 1) * np.exp(-p / SR * 1.5)
            x[p:p + 200] += hp(rng.standard_normal(200), 2) * np.exp(-np.arange(200) / 25) * amp
        return x * vol

    def bloop(f0=520, f1=980, dur=0.09, vol=0.5):
        x = tt(dur)
        f = f0 + (f1 - f0) * (x / dur) ** 0.6
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 30) * vol

    def pluck(freqs, dur=0.5, vol=0.4):
        x = tt(dur)
        return sum(np.sin(2 * np.pi * f * x) * np.exp(-x * (9 + 2 * k)) for k, f in enumerate(freqs)) / len(freqs) * vol

    def shimmer(dur=0.4, vol=0.25):
        x = tt(dur)
        sig = sum(np.sin(2 * np.pi * f * x * (1 + 0.4 * x / dur)) for f in (1760, 2217, 2637, 3520))
        return sig / 4 * (x / dur) ** 1.5 * np.clip((dur - x) / 0.05, 0, 1) * vol

    FM = [174.6, 207.7, 261.6, 349.2]
    DB = [138.6, 174.6, 207.7, 277.2]
    EB = [155.6, 196.0, 233.1, 311.1]
    AB = [207.7, 261.6, 311.1, 415.3]
    ROOT = [87.3, 87.3, 69.3, 77.8]
    CHORD = [FM, FM, DB, EB]

    # ---------- Beat (Achtel = 0.2 s, Takt beginnt bei 0.2 + 1.6·k)
    drums, bass = np.zeros(n), np.zeros(n)
    k8 = 0
    while k8 * 0.2 < DUR - 0.05:
        tp = round(k8 * 0.2, 4)
        pos, bar = (k8 - 1) % 8, (k8 - 1) // 8
        tension = T_TENSION <= tp < T_DROP
        outro = tp >= T_CTA
        if not tension:
            if pos in (0, 5) and not (outro and pos == 5):
                put(drums, kick(), tp, 0.95 if not outro else 0.75)
            if pos == 4:
                put(drums, clap(), tp, 0.85)
            put(drums, hat(), tp, 0.8 if pos % 2 == 0 else 0.5)
            if T_DROP <= tp < T_CTA and pos in (6, 7):
                for j in (1, 2):
                    put(drums, hat(), tp + j * 0.2 / 3, 0.45)
            if pos == 7 and bar % 2 == 1:
                put(drums, hat(True), tp, 0.55)
            if pos in (0, 5) and tp >= 0.2:
                put(bass, sub(ROOT[bar % 4], 0.95 if pos == 0 else 0.55), tp)
        k8 += 1
    music += drums + bass * 0.9
    for b in range(9):
        st = 0.2 + b * 1.6
        if st < DUR - 0.2 and not (T_TENSION - 1.6 < st < T_DROP):
            put(music, pad(CHORD[b % 4], min(1.6, DUR - st) + 0.05), st)
    for at, ch in ((T_TOP5 + 0.12, FM), (1.8, FM), (3.4, DB), (5.8, EB), (7.8, FM), (T_DROP, AB), (T_CTA, FM)):
        put(music, stab(ch, 1.0), at)

    # ---------- Effekte
    put(sfx, riser(0.5, 0.6), T_TOP5 - 0.38)
    put(sfx, boom(1.3, 62, 0.95), T_TOP5 + 0.12)
    put(sfx, crash(0.22), T_TOP5 + 0.12)
    for a in sorted(SWIPES):
        put(sfx, whoosh(0.34, 1.0), a - 0.08)
    tick_x = tt(0.02)
    tick = np.sin(2 * np.pi * 3000 * tick_x) * np.exp(-tick_x * 300) * 0.12
    for r in (5, 4, 3, 2, 1):
        P = PL[r]
        reveal = r == 1
        c_in, c_cnt, c_pop = (0.32, 0.44, 0.96) if reveal else (0.30, 0.40, 0.84)
        t0 = P["t0"]
        if not reveal:
            put(sfx, boom(0.7, 70, 0.55), t0 + 0.24)              # Rang-Badge
        put(sfx, bloop(), t0 + c_in + 0.12)                       # Karte landet
        for j in range(1, 28):                                    # Zähler
            put(sfx, tick, t0 + c_cnt + 0.44 * (1 - (1 - j / 28) ** 0.5))
        put(sfx, pluck((1320, 1980, 2640), 0.5, 0.45), t0 + c_pop)
        put(sfx, bloop(700, 1400, 0.07, 0.35), t0 + c_pop)
        if not reveal:
            put(sfx, shimmer(0.42, 0.22), t0 + T_FLOOD - 0.05)
    # Spannung: Trommelwirbel + Riser, dann Drop
    tp, gap = T_TENSION + 0.05, 0.1
    while tp < T_DROP - 0.02:
        put(sfx, snare(0.35 + 0.65 * (tp - T_TENSION) / 0.8), tp)
        tp += gap
        gap = max(0.022, gap * 0.86)
    put(sfx, riser(0.8, 1.0), T_TENSION)
    put(sfx, boom(0.6, 60, 0.6), T_TENSION + 0.16)
    put(sfx, boom(2.2, 45, 1.2), T_DROP)
    put(sfx, crash(0.35), T_DROP)
    put(sfx, horn(1.5), T_DROP + 0.03)
    put(sfx, crowd(2.4, 0.9) * np.exp(-tt(2.4) * 0.7), T_DROP)
    put(sfx, crackle(1.6, 90, 0.25), T_DROP + 0.3)
    put(sfx, crowd(1.6, 0.35) * np.clip((DUR - T_CTA - tt(1.6)) / 0.5, 0, 1), T_CTA)

    # ---------- Stadionsprecher mit Hallen-Hall
    v = r3.load_voice()
    segs = r3.speech_segments(v)
    assert len(segs) == len(VOICE_AT), segs
    for (a, b), at in zip(segs, VOICE_AT):
        clip = v[max(0, int((a - 0.04) * SR)): int((b + 0.15) * SR)].astype(np.float64)
        ramp = np.minimum(np.arange(len(clip)) / (0.01 * SR), 1) * np.minimum((len(clip) - np.arange(len(clip))) / (0.03 * SR), 1)
        put(vox, clip * ramp, at)
    vox = hp(vox, 130)
    vox = np.tanh(vox * 2.2) / 1.6
    irl = int(1.4 * SR)
    ix = np.arange(irl) / SR
    ir = lp(rng.standard_normal(irl), 3) * np.exp(-ix * 3.8)
    ir[: int(0.02 * SR)] *= np.linspace(0, 1, int(0.02 * SR))
    ir /= np.sqrt(np.sum(ir ** 2))
    wet = fftconvolve(vox, ir)[:n]
    slap = np.zeros(n)
    dl = int(0.1 * SR)
    slap[dl:] = vox[:-dl]
    vox_out = vox + wet * 0.26 + slap * 0.14
    env = lp(np.abs(vox), 2200)
    duck = 1 - 0.5 * np.clip(env / (env.max() * 0.25 + 1e-9), 0, 1)

    mix = music * 0.58 * duck + sfx * 0.72 + vox_out * 1.3
    mix /= np.percentile(np.abs(mix), 99.95) + 1e-9
    mix = np.tanh(mix * 0.95)
    mix = mix / np.max(np.abs(mix)) * 0.95
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


def main():
    os.chdir(HERE)
    make_audio("audio_legends.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_legends.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "21",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
           "reel14_legends.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(4) as pool:
        for k, buf in enumerate(pool.imap(render_frame, range(nf), chunksize=2)):
            proc.stdin.write(buf)
            if k % 60 == 0:
                print(f"{k}/{nf}", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.frombytes("RGB", (W, H), render_frame(int(1.5 * FPS))).save("reel14_thumbnail.jpg", quality=92)
    print("fertig: reel14_legends.mp4")


if __name__ == "__main__":
    main()
