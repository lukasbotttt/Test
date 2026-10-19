"""Reel 31: NHL RULES EXPLAINED – PART 8: POWER PLAY (neuer Motion-Design-Look, ~17 s).

Fakten (NHL Official Rules 2023–24):
- Regel 81.1: Icing wird nur gegen ein Team gepfiffen, das "equal or superior in numerical strength (power-play)"
  ist. Ein Team in Unterzahl darf den Puck also über alle Linien schießen – kein Pfiff.
- Regel 16.2: Trifft das Team in Überzahl, endet die (erste) kleine Strafe sofort ("shall automatically terminate").
  Gilt nicht für große Strafen (Major) und nicht für Penalty-Shot-Tore.
- Geschichte: HIST_* unten (Quellen im Kommentar dort).
Look: Motion Design – schwarzer 9:16-Rahmen, fester Titel oben, 16:9-Panel in der Mitte mit Kinetic Typography
(Archivo Expanded, OFL), UI-Karten mit 3D-Kippung, Monospace-Zählern (JetBrains Mono, OFL), orangem Akzent,
Bokeh und Bewegungsunschärfe. Bewusst ohne Spieler, ohne Logos.
Stimme: Kokoro "Michael" (tts_kokoro.py, Apache-2.0), Sätze einzeln, 1,08x.
Aufruf: python3 reel31_powerplay.py vo                 -> voice/reel31_*.wav
        python3 reel31_powerplay.py audio              -> nur Ton neu mischen
        python3 reel31_powerplay.py prev 1.0,4.2 x.jpg -> Einzelbilder als Kontaktbogen
        python3 reel31_powerplay.py                    -> reel31_powerplay.mp4
"""
import json
import math
import os
import subprocess
import sys
import time
import wave
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30
SHUT = 0.8 / FPS                               # Verschlusszeit für Bewegungsunschärfe
PY, PW, PH = 656, 1080, 608                    # 16:9-Panel (volle Breite) in der Bildmitte
ACC = (240, 90, 60)                            # Akzent Orangerot
WHITE = (244, 244, 246)
GREY = (128, 131, 140)
DARK = (22, 22, 25)
TEMPO = 1.08

# ================================================================= Timeline aus dem Voiceover
VO_FIXES = {"bˈeɪlɪvˌoʊ": "bˌeɪlɪvˈoʊ"}       # Béliveau: bay-lee-VOH
VO_LINES = [
    ("q", "Why can THIS team ice the puck?"),
    ("sh", "They're short-handed. Four on five."),
    ("rule", "Icing only counts if you're even or stronger. No whistle."),
    ("goal", "Power-play goal? The minor ends. Instantly."),
    ("blame", "Blame it on Montreal."),
    ("hist", "Béliveau once scored three goals in forty-four seconds on one power play."),
    ("cta", "Should short-handed teams get to ice it? Yes or no?"),
]
VO_KEYS = [k for k, _ in VO_LINES]
VO_START = {"q": 0.15, "sh": 1.95, "rule": 4.0, "goal": 7.15, "blame": 9.7, "hist": 10.9, "cta": 14.8}
DUR = 17.95
# Wortanfänge (s nach Satzbeginn, nach 1,08x) – aus faster-whisper
WT = {
    "q": [0.0, 0.18, 0.32, 0.46, 0.68, 0.92, 1.14],
    "sh": [0.0, 0.1, 0.32, 1.02, 1.12, 1.3],
    "rule": [0.0, 0.3, 0.5, 0.8, 1.06, 1.16, 1.32, 1.4, 2.26, 2.34],
    "goal": [0.0, 0.16, 0.36, 0.94, 1.0, 1.18, 1.56],
    "blame": [0.0, 0.24, 0.36, 0.52],
    "hist": [0.0, 0.38, 0.6, 0.88, 1.22, 1.5, 1.72, 2.02, 2.6, 2.82, 3.0, 3.28],
    "cta": [0.0, 0.14, 0.36, 0.64, 0.94, 1.18, 1.26, 1.46, 1.98, 2.12, 2.32],
}


def at(key, s):
    return VO_START[key] + s


def wt(key, i):
    return VO_START[key] + WT[key][i]


T_SH = VO_START["sh"]
T_RULE = VO_START["rule"]
T_NOWH = wt("rule", 8)                         # "no whistle"
T_GOAL = VO_START["goal"]
T_BACK = wt("goal", 3)                         # "the minor" -> zurück ins Dunkle
T_ENDS = wt("goal", 5)                         # "ends" -> Uhr springt auf 0:00
T_BLAME = VO_START["blame"]
T_HIST = VO_START["hist"]
T_CTA = VO_START["cta"]
T_SHOT, T_ARRIVE = 0.32, 0.92                  # Puck fliegt übers ganze Eis
T_BOX = wt("sh", 1) + 0.12                     # Spieler landet in der Box, Strafuhr läuft
SCENES = [0.0, T_SH, T_RULE, T_GOAL, T_BLAME, T_CTA]

# Geschichte (Faktencheck: hockey-reference.com Boxscore 195511050MTL; NHL.com "This Date in History: Nov. 5";
# Dave Stubbs, NHL.com 6.6.2020 "Montreal felt 1956 rule change hurt power play"):
# 5.11.1955, Montreal Forum, Canadiens 4:2 Bruins. Béliveau trifft im 2. Drittel um 0:42, 1:08 und 1:26 – drei
# Überzahltore in 44 Sekunden, während Cal Gardner (Charging) und Hal Laycoe (Hooking) beide auf der Strafbank
# sitzen (5 gegen 3, eine durchgehende Überzahl). Damals saß man die kleine Strafe immer voll ab. Am 6.6.1956
# beschließt die Liga 5:1 (nur Montreal dagegen), dass ein Überzahltor die kleine Strafe beendet – ab 1956/57,
# Spitzname "The Canadiens Rule". Darum "Blame it on Montreal" (Montreals Überzahl insgesamt war der Anlass,
# Béliveaus 44 Sekunden das bekannteste Beispiel) – nicht "dieses eine Spiel hat die Regel geändert".
HIST_KICKER = "NOV 5, 1955 · MONTREAL vs BOSTON"
HIST_GOALS = [0.0, 26.0, 44.0]                # 0:42, 1:08, 1:26 -> Abstand in Sekunden


# ================================================================= Helfer
def c01(x):
    return 0.0 if x < 0 else (1.0 if x > 1 else x)


def e_out(x, p=3):
    return 1 - (1 - c01(x)) ** p


def e_in(x, p=3):
    return c01(x) ** p


def sio(x):
    return 0.5 - 0.5 * math.cos(math.pi * c01(x))


def back(x, s=1.6):
    x = c01(x) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def lerp(a, b, t):
    return a + (b - a) * t


_FONTS = {}
FONT_FILES = {"x9": "ArchivoX900.ttf", "x8": "ArchivoX800.ttf", "x5": "ArchivoX500.ttf", "a7": "Archivo700.ttf",
              "m5": "JBMono500.ttf", "m7": "JBMono700.ttf", "in": "Inter.ttf"}


def font(fk, size):
    key = (fk, size)
    if key not in _FONTS:
        f = ImageFont.truetype(os.path.join(HERE, "fonts", FONT_FILES[fk[:2]]), size)
        if fk.startswith("in"):
            f.set_variation_by_name({"in": "Regular", "in5": "Medium", "in6": "SemiBold"}[fk])
        _FONTS[key] = f
    return _FONTS[key]


def to_spr(img):
    a = np.asarray(img, np.float32) / 255
    a[..., :3] *= a[..., 3:4]
    return a


class Spr:
    """Vormultipliziertes RGBA-Sprite mit Ankerpunkt (ax, ay) und PIL-Original für Skalierung."""

    def __init__(self, img, ax, ay, tw=0):
        self.img, self.arr, self.ax, self.ay, self.tw = img, to_spr(img), ax, ay, tw
        self._sc = {}
        self._glow = None

    def scaled(self, s):
        s = round(s, 2)
        if abs(s - 1) < 0.005:
            return self.arr, self.ax, self.ay
        if s not in self._sc:
            w, h = self.img.size
            im = self.img.resize((max(1, int(w * s)), max(1, int(h * s))), Image.BICUBIC)
            self._sc[s] = (to_spr(im), self.ax * s, self.ay * s)
        return self._sc[s]

    def glow(self, sigma=9):
        if self._glow is None:
            pad = int(sigma * 3)
            a = np.pad(self.arr[..., :3], ((pad, pad), (pad, pad), (0, 0)))
            self._glow = (np.stack([gaussian_filter(a[..., c], sigma) for c in range(3)], -1), self.ax + pad,
                          self.ay + pad)
        return self._glow


_TXT = {}


def text_spr(txt, fk, size, col, track=0.0):
    key = (txt, fk, size, col, track)
    if key in _TXT:
        return _TXT[key]
    f = font(fk, size)
    pad = int(size * 0.35) + 4
    if track:
        adv = [f.getlength(ch) + track * size for ch in txt]
        tw = sum(adv) - track * size
    else:
        tw = f.getlength(txt)
    asc, desc = f.getmetrics()
    im = Image.new("RGBA", (int(tw + 2 * pad + 2), asc + desc + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if track:
        x = pad
        for ch, a in zip(txt, adv):
            d.text((x, pad), ch, font=f, fill=col + (255,))
            x += a
    else:
        d.text((pad, pad), txt, font=f, fill=col + (255,))
    cap = f.getbbox("H")
    s = Spr(im, pad + tw / 2, pad + (cap[1] + cap[3]) / 2, tw)
    _TXT[key] = s
    return s


def blit(dst, src, x, y, a=1.0):
    """src (vormultipliziert, h x w x 4) 'over' dst (H x W x 3) mit linker oberer Ecke (x, y)."""
    if a <= 0.003:
        return
    x, y = int(round(x)), int(round(y))
    h, w = src.shape[:2]
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, dst.shape[1]), min(y + h, dst.shape[0])
    if x1 <= x0 or y1 <= y0:
        return
    s = src[y0 - y:y1 - y, x0 - x:x1 - x]
    if a < 0.999:
        s = s * a
    d = dst[y0:y1, x0:x1]
    d *= 1 - s[..., 3:4]
    d += s[..., :3]


def blit_add(dst, rgb, x, y, a=1.0):
    if a <= 0.003:
        return
    x, y = int(round(x)), int(round(y))
    h, w = rgb.shape[:2]
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, dst.shape[1]), min(y + h, dst.shape[0])
    if x1 <= x0 or y1 <= y0:
        return
    dst[y0:y1, x0:x1] += rgb[y0 - y:y1 - y, x0 - x:x1 - x] * a


def blit_mb(dst, arr, pts, a=1.0):
    """Bewegungsunschärfe: Mittelwert des Sprites über mehrere Unterbild-Positionen."""
    if a <= 0.003:
        return
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if max(xs) - min(xs) < 1.5 and max(ys) - min(ys) < 1.5:
        blit(dst, arr, pts[0][0], pts[0][1], a)
        return
    n = max(2, min(12, int(max(max(xs) - min(xs), max(ys) - min(ys)) / 3) + 2))
    pts = [(lerp(pts[0][0], pts[-1][0], i / (n - 1)), lerp(pts[0][1], pts[-1][1], i / (n - 1))) for i in range(n)]
    bx, by = int(math.floor(min(xs))), int(math.floor(min(ys)))
    h, w = arr.shape[:2]
    acc = np.zeros((int(max(ys) - by) + h + 2, int(max(xs) - bx) + w + 2, 4), np.float32)
    for x, y in pts:
        ix, iy = int(round(x - bx)), int(round(y - by))
        acc[iy:iy + h, ix:ix + w] += arr
    acc /= n
    blit(dst, acc, bx, by, a)


def draw(dst, spr, x, y, a=1.0, s=1.0, x0=None, y0=None, glow=0.0):
    """Sprite am Anker (x, y) zeichnen; (x0, y0) = Position eine Verschlusszeit früher (Bewegungsunschärfe)."""
    arr, ax, ay = spr.scaled(s)
    if glow > 0:
        g, gx, gy = spr.glow()
        blit_add(dst, g, x - gx, y - gy, glow * a)
    if x0 is None:
        blit(dst, arr, x - ax, y - ay, a)
    else:
        blit_mb(dst, arr, [(x0 - ax, y0 - ay), (x - ax, y - ay)], a)


def rrect_img(w, h, r, fill, border=None, bw=2, ss=3):
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), r * ss, fill=fill,
                        outline=border, width=bw * ss if border else 0)
    return im.resize((w, h), Image.LANCZOS)


def persp_coeffs(src_pts, dst_pts):
    """PIL-PERSPECTIVE: bildet Ausgabe-Punkte (dst) auf Eingabe-Punkte (src) ab."""
    m = []
    for (x, y), (u, v) in zip(dst_pts, src_pts):
        m.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        m.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    b = np.array(src_pts, np.float64).reshape(8)
    return np.linalg.solve(np.array(m, np.float64), b).tolist()


def tilt(img, yaw, pitch, f=1400.0):
    """Karte im Raum kippen (Grad). Gibt (Bild, Ankerverschiebung) zurück; Anker = Kartenmitte."""
    w, h = img.size
    if abs(yaw) < 0.2 and abs(pitch) < 0.2:
        return img, (w / 2, h / 2)
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    out = []
    for x, y in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        X, Z = x * cy, x * sy
        Y, Z = y * cp - Z * sp, y * sp + Z * cp
        k = f / (f + Z)
        out.append((X * k, Y * k))
    xs, ys = [p[0] for p in out], [p[1] for p in out]
    ox, oy = min(xs), min(ys)
    ow, oh = int(math.ceil(max(xs) - ox)) + 2, int(math.ceil(max(ys) - oy)) + 2
    dst = [(p[0] - ox, p[1] - oy) for p in out]
    co = persp_coeffs([(0, 0), (w, 0), (w, h), (0, h)], dst)
    return img.transform((ow, oh), Image.PERSPECTIVE, co, Image.BICUBIC), (-ox, -oy)


def card_draw(dst, img, cx, cy, a=1.0, yaw=0.0, pitch=0.0, s=1.0, shadow=True):
    if a <= 0.003:
        return
    if abs(s - 1) > 0.005:
        img = img.resize((max(1, int(img.size[0] * s)), max(1, int(img.size[1] * s))), Image.BICUBIC)
    im, (ax, ay) = tilt(img, yaw, pitch)
    arr = to_spr(im)
    if shadow:
        sh = np.zeros(arr.shape[:2] + (4,), np.float32)
        sh[..., 3] = gaussian_filter(arr[..., 3], 14) * 0.55
        blit(dst, sh, cx - ax, cy - ay + 16, a)
    blit(dst, arr, cx - ax, cy - ay, a)


# ================================================================= Kinetic Typography
class KLine:
    """Zeile, die Wort für Wort aufgebaut wird und sich dabei neu zentriert (wie in der Vorlage)."""

    def __init__(self, words, fk, size, cx, cy, times, t_out, track=0.02, space=0.32, glow=0.55):
        self.sprs = [text_spr(w, fk, size, col, track) for w, col in words]
        self.cols = [col for _, col in words]
        self.cx, self.cy, self.times, self.t_out, self.glow = cx, cy, times, t_out, glow
        self.size = size
        gap = space * size
        self.offs, x = [], 0.0
        self.inc = []
        for i, s in enumerate(self.sprs):
            self.offs.append(x + s.tw / 2)
            self.inc.append(s.tw + (gap if i else 0))
            x += s.tw + gap

    def state(self, t, i):
        start = self.cx - 0.5 * sum(inc * e_out((t - ti) / 0.34) for inc, ti in zip(self.inc, self.times))
        p = (t - self.times[i]) / 0.26
        x = start + self.offs[i] + (1 - e_out(p)) * self.size * 0.35
        y = self.cy + (1 - e_out(p)) * self.size * 0.45
        a = c01(p * 1.8)
        s = 1 + (1 - e_out(p)) * 0.10
        if self.t_out is not None:
            q = (t - self.t_out) / 0.22
            y -= e_in(q, 2) * self.size * 1.2
            a *= 1 - c01(q)
        return x, y, a, s

    def render(self, dst, t):
        if self.t_out is not None and t > self.t_out + 0.25:
            return
        for i, spr in enumerate(self.sprs):
            if t < self.times[i]:
                continue
            x, y, a, s = self.state(t, i)
            x0, y0, _, _ = self.state(t - SHUT, i)
            draw(dst, spr, x, y, a, s, x0, y0, glow=self.glow if self.cols[i] == ACC else 0.0)


def typed(dst, txt, fk, size, col, x, y, t, t0, cps=38, cursor=True, anchor="l"):
    """Schreibmaschinen-Text (Monospace-Labels); x = linker Rand oder Mitte (anchor 'c')."""
    n = int(max(0, (t - t0) * cps))
    if n <= 0:
        return
    s = text_spr(txt[:n], fk, size, col)
    ax = x if anchor == "l" else x - text_spr(txt, fk, size, col).tw / 2
    draw(dst, s, ax + s.tw / 2, y)
    if cursor and n < len(txt) or (cursor and int(t * 3) % 2 == 0 and t - t0 < len(txt) / cps + 0.8):
        blit(dst, solid(ACC, int(size * 0.55), int(size * 1.05)), ax + s.tw + 4, y - size * 0.52)


_SOLID = {}


def solid(col, w, h, a=1.0):
    key = (col, w, h, a)
    if key not in _SOLID:
        arr = np.zeros((h, w, 4), np.float32)
        arr[..., :3] = np.array(col, np.float32) / 255 * a
        arr[..., 3] = a
        _SOLID[key] = arr
    return _SOLID[key]


# ================================================================= Hintergrund, Bokeh, Licht
def panel_bg():
    yy, xx = np.mgrid[0:PH, 0:PW].astype(np.float32)
    base = 0.045 + 0.050 * np.exp(-((xx - 330) ** 2 / (2 * 520 ** 2) + (yy + 60) ** 2 / (2 * 260 ** 2)))
    base += 0.025 * np.exp(-((yy - 40) ** 2) / (2 * 120 ** 2))
    vig = 1 - 0.55 * (((xx - PW / 2) / (PW * 0.62)) ** 2 + ((yy - PH * 0.42) / (PH * 0.85)) ** 2)
    g = np.clip(base * np.clip(vig, 0.25, 1), 0, 1)
    return np.stack([g * 1.0, g * 0.985, g * 1.02], -1).astype(np.float32)


BG = None


def disc_rgb(r, col, soft):
    R = int(r * 2.2) + 4
    yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
    d = np.sqrt(xx ** 2 + yy ** 2)
    m = np.clip((r - d) / max(soft, 0.8), 0, 1) ** 1.2
    m = gaussian_filter(m, soft * 0.6)
    return (m[..., None] * (np.array(col, np.float32) / 255)).astype(np.float32), R


_rng = np.random.default_rng(31)
BOKEH = []
for _i in range(15):
    r = float(_rng.uniform(6, 26))
    BOKEH.append(dict(x=float(_rng.uniform(30, PW - 30)), y=float(_rng.uniform(40, PH - 30)), r=r,
                      vx=float(_rng.uniform(-9, 9)), vy=float(_rng.uniform(-7, 3)), ph=float(_rng.uniform(0, 6.28)),
                      a=float(_rng.uniform(0.10, 0.32)) * (0.55 if r > 18 else 1.0),
                      spr=disc_rgb(r, ACC if _i % 5 else (255, 210, 190), r * 0.35 + 1)))


def bokeh(dst, t, k=1.0):
    for b in BOKEH:
        x = (b["x"] + b["vx"] * t) % (PW + 80) - 40
        y = (b["y"] + b["vy"] * t + 8 * math.sin(t * 0.7 + b["ph"])) % (PH + 60) - 30
        a = b["a"] * (0.75 + 0.25 * math.sin(t * 1.3 + b["ph"])) * k
        rgb, R = b["spr"]
        blit_add(dst, rgb, x - R, y - R, a)


BEAM = None


def beam(dst, t, t0, t1, x0, x1, k=0.10):
    """Weicher Lichtkegel von oben, der über die Szene wandert."""
    global BEAM
    if not (t0 <= t <= t1):
        return
    if BEAM is None:
        im = Image.new("L", (700, PH + 200), 0)
        ImageDraw.Draw(im).polygon([(300, 0), (400, 0), (700, PH + 200), (0, PH + 200)], fill=255)
        m = gaussian_filter(np.asarray(im, np.float32) / 255, 40)
        BEAM = m[..., None] * np.array([1.0, 0.93, 0.88], np.float32)
    p = (t - t0) / (t1 - t0)
    a = k * math.sin(math.pi * p) ** 0.7
    blit_add(dst, BEAM, lerp(x0, x1, sio(p)) - 350, -120, a)


# ================================================================= UI-Bausteine
def cursor_img():
    ss = 4
    im = Image.new("RGBA", (34 * ss, 44 * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pts = [(3, 2), (3, 34), (11, 26), (17, 40), (23, 37), (17, 24), (28, 24)]
    d.polygon([(x * ss, y * ss) for x, y in pts], fill=(250, 250, 250, 255), outline=(20, 20, 22, 255))
    d.line([(x * ss, y * ss) for x, y in pts + [pts[0]]], fill=(20, 20, 22, 255), width=2 * ss)
    return Spr(im.resize((34, 44), Image.LANCZOS), 3, 2)


CURSOR = None


def tag_spr(txt, col=ACC, fg=(20, 20, 22), size=22):
    key = ("tag", txt, col, fg, size)
    if key not in _TXT:
        t = text_spr(txt, "m7", size, fg)
        w, h = int(t.tw + size * 1.0), int(size * 1.55)
        im = rrect_img(w, h, 6, col + (255,))
        im.alpha_composite(t.img, (int(w / 2 - t.ax), int(h / 2 - t.ay)))
        _TXT[key] = Spr(im, 0, 0)
    return _TXT[key]


def draw_cursor(dst, x, y, a, label=None, la=1.0, x0=None, y0=None):
    global CURSOR
    if CURSOR is None:
        CURSOR = cursor_img()
    draw(dst, CURSOR, x, y, a, 1.0, x0, y0)
    if label and la > 0.01:
        tg = tag_spr(label)
        draw(dst, tg, x + 26, y + 40, a * la, 0.85 + 0.15 * e_out(la * 3))


def ring(dst, x, y, r, w, col, a):
    if a <= 0.01 or r <= 1:
        return
    R = int(r + w + 3)
    yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
    d = np.abs(np.sqrt(xx ** 2 + yy ** 2) - r)
    m = np.clip(w / 2 + 0.8 - d, 0, 1)
    blit_add(dst, m[..., None] * (np.array(col, np.float32) / 255), x - R, y - R, a)


def dot(dst, x, y, r, col, a=1.0, glow=0.0):
    key = ("dot", r, col)
    if key not in _SOLID:
        R = int(r + 2)
        yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
        m = np.clip(r + 0.5 - np.sqrt(xx ** 2 + yy ** 2), 0, 1)
        arr = np.zeros(m.shape + (4,), np.float32)
        arr[..., :3] = m[..., None] * (np.array(col, np.float32) / 255)
        arr[..., 3] = m
        g = disc_rgb(r * 2.2, col, r * 1.4)
        _SOLID[key] = (arr, R, g)
    arr, R, (g, gR) = _SOLID[key]
    if glow:
        blit_add(dst, g, x - gR, y - gR, glow * a)
    blit(dst, arr, x - R, y - R, a)


# ================================================================= Szene A: Hook mit Eisfläche
RINK_W, RINK_H = 720, 306                      # 200 x 85 ft
GL_Y = 14.5 + math.sqrt(28 ** 2 - 17 ** 2)       # Torlinie (11 ft vor der Bande) bis zur Eckrundung (r = 28 ft)
CARD_A = (540, 398)
RINK_DY = 15                                    # Eisfläche sitzt unter der Kopfzeile der Karte


def rink_xy(X, Y):
    return CARD_A[0] + X * RINK_W / 200, CARD_A[1] + RINK_DY + Y * RINK_H / 85


def rink_card():
    ss = 2
    cw, ch = 800, 386
    card = rrect_img(cw, ch, 22, (30, 30, 34, 238), (255, 255, 255, 26), 2)
    im = Image.new("RGBA", (cw * ss, ch * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    ox, oy = cw * ss / 2, (ch / 2 + RINK_DY) * ss
    k = RINK_W * ss / 200

    def P(X, Y):
        return ox + X * k, oy + Y * k

    line = (255, 255, 255, 60)
    d.rounded_rectangle((*P(-100, -42.5), *P(100, 42.5)), int(28 * k), outline=(255, 255, 255, 90), width=3 * ss)
    for X in (-25, 25):
        d.line((*P(X, -42.5), *P(X, 42.5)), fill=(150, 165, 190, 120), width=3 * ss)
    d.line((*P(0, -42.5), *P(0, 42.5)), fill=ACC + (200,), width=4 * ss)
    for X in (-89, 89):                                             # Torlinie endet an der runden Bande
        d.line((*P(X, -GL_Y), *P(X, GL_Y)), fill=ACC + (130,), width=2 * ss)
    for cx, cy in ((0, 0), (-69, -22), (-69, 22), (69, -22), (69, 22)):
        d.ellipse((*P(cx - 15, cy - 15), *P(cx + 15, cy + 15)), outline=line, width=2 * ss)
    for X, sgn in ((-89, 1), (89, -1)):
        d.pieslice((*P(X - 6, -6), *P(X + 6, 6)), -90 if sgn > 0 else 90, 90 if sgn > 0 else 270,
                   fill=(255, 255, 255, 22), outline=line, width=2 * ss)
        xn = X - 3.3 * sgn                                          # Tor hinter der Linie (6 ft breit)
        d.rectangle((*P(min(X, xn), -3), *P(max(X, xn), 3)), outline=(255, 255, 255, 120), width=2 * ss)
    rink = im.resize((cw, ch), Image.LANCZOS)
    card.alpha_composite(rink)
    hdr = text_spr("ICING CAM · 4 v 5", "m5", 15, GREY)
    card.alpha_composite(hdr.img, (int(24 - (hdr.ax - hdr.tw / 2)), int(17 - hdr.ay)))
    return card


RINK = None
PK = [(78, -14), (66, 20), (52, -2), (58, -30)]                      # Unterzahl (orange), verteidigt rechts
PP = [(82, 30), (62, 4), (44, 24), (40, -22), (30, 6)]               # Überzahl (weiß)
SHOOTER = 2
PUCK_A, PUCK_B = (48, -2), (-96.5, 9)                               # nach links: weg von TikToks Button-Leiste


def puck_pos(t):
    if t < T_SHOT:
        return PUCK_A
    p = e_out((t - T_SHOT) / (T_ARRIVE - T_SHOT), 2)
    x, y = lerp(PUCK_A[0], PUCK_B[0], p), lerp(PUCK_A[1], PUCK_B[1], p)
    if t > T_ARRIVE:                                               # kleiner Abpraller an der Bande
        q = e_out((t - T_ARRIVE) / 0.5)
        x, y = lerp(PUCK_B[0], -93.0, q), lerp(PUCK_B[1], 13.0, q)
    return x, y


def scene_hook(dst, t):
    global RINK
    if t > T_SH + 0.35:
        return
    if RINK is None:
        RINK = rink_card()
    q = c01((t - T_SH) / 0.3)
    a = 1 - e_in(q, 2)
    dy = e_in(q, 2) * 120
    s = 1.035 - 0.035 * e_out(t / 1.4)
    card_draw(dst, RINK, CARD_A[0], CARD_A[1] + dy, a, pitch=-10 * e_in(q, 2), s=s)
    w = [wt("q", i) - 0.05 for i in range(7)]
    KLine([("WHY", WHITE), ("CAN", WHITE), ("THIS", ACC), ("TEAM", WHITE)], "x9", 54, 540, 74,
          [-0.2, w[1], w[2], w[3]], T_SH - 0.04).render(dst, t)
    KLine([("ICE", WHITE), ("THE", WHITE), ("PUCK?", WHITE)], "x9", 54, 540, 146, w[4:7], T_SH).render(dst, t)
    if a < 0.02:
        return

    def RP(X, Y):
        x, y = rink_xy(X, Y)
        return CARD_A[0] + (x - CARD_A[0]) * s, CARD_A[1] + dy + (y - CARD_A[1]) * s

    for X, Y in PP:
        x, y = RP(X, Y)
        dot(dst, x, y, 9, WHITE, a * 0.92)
    tp = wt("q", 2)
    for i, (X, Y) in enumerate(PK):
        x, y = RP(X, Y)
        pul = c01((t - tp - 0.04 * i) / 0.55)
        if 0 < pul < 1:
            ring(dst, x, y, 10 + 26 * e_out(pul), 3, ACC, a * (1 - pul))
        dot(dst, x, y, 10, ACC, a, glow=0.35 + 0.5 * (1 - pul) * (pul > 0))
    gl = c01((t - (T_ARRIVE - 0.12)) / 0.15) * (1 - c01((t - 1.7) / 0.4))
    if gl > 0:                                                      # Torlinie leuchtet auf
        x, y0 = RP(-89, -GL_Y)
        _, y1 = RP(-89, GL_Y)
        blit_add(dst, solid(ACC, 4, int(y1 - y0))[..., :3], x - 2, y0, 0.9 * gl * a)
    for k in range(10):                                             # Leuchtspur des Pucks
        tt = t - k * 0.022
        if tt < T_SHOT:
            break
        x, y = RP(*puck_pos(tt))
        dot(dst, x, y, 7 - k * 0.45, ACC, a * (0.55 - k * 0.05), glow=0.0)
    x, y = RP(*puck_pos(t))
    x0, y0 = RP(*puck_pos(t - SHUT))
    dot(dst, x, y, 7, WHITE, a, glow=0.5)
    if math.hypot(x - x0, y - y0) > 2:
        for k in range(1, 5):
            dot(dst, lerp(x, x0, k / 4), lerp(y, y0, k / 4), 6, WHITE, a * 0.25)
    # Cursor mit Label "ICING?"
    c = e_out((t - 0.95) / 0.45)
    if c > 0:
        tx, ty = x - 4, y - 2
        cx, cy = lerp(60, tx, c), lerp(640, ty, c)
        cx0, cy0 = lerp(60, tx, e_out((t - SHUT - 0.95) / 0.45)), lerp(640, ty, e_out((t - SHUT - 0.95) / 0.45))
        draw_cursor(dst, cx, cy, a, "ICING?", c01((t - 1.3) / 0.15), cx0, cy0)


# ================================================================= Szene B: Unterzahl
def card_img(kind, t):
    w, h = 236, 252
    im = rrect_img(w, h, 20, (34, 34, 38, 245), (255, 255, 255, 30), 2)
    if kind == "box":
        lab = text_spr("PENALTY BOX", "m5", 16, GREY)
        im.alpha_composite(lab.img, (int(w / 2 - lab.ax), int(34 - lab.ay)))
        clk = text_spr(fmt(penalty_left(t)), "m7", 66, WHITE)
        im.alpha_composite(clk.img, (int(w / 2 - clk.ax), int(150 - clk.ay)))
        bar = rrect_img(140, 6, 3, (255, 255, 255, 30))
        im.alpha_composite(bar, (w // 2 - 70, 210))
        fill = int(140 * penalty_left(t) / 120)
        if fill > 6:
            im.alpha_composite(rrect_img(fill, 6, 3, ACC + (255,)), (w // 2 - 70, 210))
    else:
        num, col, lab_t, dcol, nd = (("4", ACC, "SHORT-HANDED", ACC, 4) if kind == "pk" else
                                     ("5", WHITE, "POWER PLAY", WHITE, 5))
        n = text_spr(num, "x9", 132, col)
        im.alpha_composite(n.img, (int(w / 2 - n.ax), int(112 - n.ay)))
        lab = text_spr(lab_t, "m5", 16, GREY)
        im.alpha_composite(lab.img, (int(w / 2 - lab.ax), int(212 - lab.ay)))
        dd = ImageDraw.Draw(im)
        for i in range(nd):
            x = w / 2 + (i - (nd - 1) / 2) * 24
            dd.ellipse((x - 6, 178 - 6, x + 6, 178 + 6), fill=dcol + (255,))
    return im


def penalty_left(t):
    return max(0.0, 120.0 - max(0.0, t - T_BOX - 0.25))


def fmt(sec):
    sec = int(math.ceil(sec - 1e-6))
    return f"{sec // 60}:{sec % 60:02d}"


CARDS_B = [("pk", 270, wt("sh", 3)), ("box", 540, wt("sh", 0) + 0.05), ("pp", 810, wt("sh", 5))]


def scene_short(dst, t):
    if not (T_SH - 0.05 <= t <= T_RULE + 0.45):
        return
    beam(dst, t, T_SH, T_RULE + 0.2, 380, 760, 0.07)
    hl = KLine([("SHORT-HANDED", WHITE)], "x9", 66, 540, 96, [wt("sh", 1) - 0.06], T_RULE)
    hl.render(dst, t)
    for i, (kind, cx, t0) in enumerate(CARDS_B):
        p = (t - t0) / 0.42
        if p <= 0:
            continue
        yaw = -78 * (1 - back(p, 1.2)) if kind != "pp" else 78 * (1 - back(p, 1.2))
        a = c01(p * 2.5)
        q = c01((t - T_RULE - 0.04 * i) / 0.3)
        yaw += 70 * e_in(q, 2) * (1 if i != 1 else 0)
        a *= 1 - c01(q * 1.2) if i != 1 else 1
        cy = 362 + (1 - e_out(p)) * 50
        if kind == "box":                                           # Box-Karte schrumpft zur Strafuhr oben rechts
            m = e_in(q, 2) if q < 1 else 1
            cx_, cy_ = lerp(cx, 948, sio(q)), lerp(cy, 44, sio(q))
            card_draw(dst, card_img(kind, t), cx_, cy_, a * (1 - c01((q - 0.6) / 0.4)), yaw, 0, 1 - 0.75 * m)
            # Spieler (oranger Punkt) fällt in die Box
            d = c01((t - T_BOX + 0.25) / 0.25)
            if 0 < d < 1:
                dot(dst, cx_, lerp(cy_ - 260, cy_ - 60, e_in(d, 2)), 10, ACC, a * (1 - d * 0.3), glow=0.6)
            elif d >= 1 and t < T_BOX + 0.4:
                ring(dst, cx_, cy_ - 60, 10 + 50 * e_out((t - T_BOX) / 0.4), 3, ACC, 1 - c01((t - T_BOX) / 0.4))
        else:
            card_draw(dst, card_img(kind, t), cx, cy, a, yaw, 0)
    vs = text_spr("v", "x5", 34, GREY)
    a = c01((t - wt("sh", 4)) / 0.2) * (1 - c01((t - T_RULE) / 0.2))
    for x in (405, 675):
        pass
    if a > 0:
        draw(dst, vs, 405, 362, a * 0)


def hud(dst, t):
    """Strafuhr oben rechts im Panel, bis zum Überzahltor."""
    a = c01((t - T_RULE - 0.2) / 0.2) * (1 - c01((t - T_GOAL) / 0.06))
    if a <= 0:
        return
    key = ("hud", fmt(penalty_left(t)))
    if key not in _TXT:
        w, h = 214, 50
        im = rrect_img(w, h, 25, (34, 34, 38, 240), (255, 255, 255, 34), 2)
        lab = text_spr("BOX", "m5", 17, GREY)
        im.alpha_composite(lab.img, (int(40 + lab.tw / 2 - lab.ax), int(h / 2 - lab.ay)))
        clk = text_spr(fmt(penalty_left(t)), "m7", 26, WHITE)
        im.alpha_composite(clk.img, (int(w - 22 - clk.tw - (clk.ax - clk.tw / 2)), int(h / 2 - clk.ay)))
        _TXT[key] = Spr(im, w / 2, h / 2)
    draw(dst, _TXT[key], 948, 44, a, 0.9 + 0.1 * e_out(a))
    blink = 0.55 + 0.45 * math.cos(t * 2 * math.pi * 1.0)
    dot(dst, 948 - 107 + 22, 44, 6, ACC, a * blink, glow=0.5)


# ================================================================= Szene C: Regel 81.1
RULE_LINES = ["Should any player of a team, equal or superior",
              "in numerical strength (power-play) to the opposing",
              "team, shoot, bat or deflect the puck … beyond the",
              "goal line of the opposing team, play shall be stopped."]
HL = ("equal or superior", 0)


def rule_card(t):
    w, h = 880, 262
    im = rrect_img(w, h, 18, (30, 30, 34, 245), (255, 255, 255, 28), 2)
    d = ImageDraw.Draw(im)
    for i in range(3):
        d.ellipse((22 + i * 18, 20, 32 + i * 18, 30), fill=(255, 255, 255, 50 if i else 70))
    hd = text_spr("NHL RULE 81.1  ·  ICING", "m5", 16, GREY)
    im.alpha_composite(hd.img, (int(w / 2 - hd.ax), int(25 - hd.ay)))
    d.line((0, 50, w, 50), fill=(255, 255, 255, 22), width=2)
    f = font("in", 27)
    t0 = T_RULE + 0.12
    chars = int(max(0, (t - t0) * 95))
    y = 66
    hl_p = e_out((t - wt("rule", 5) + 0.05) / 0.35)
    for li, ln in enumerate(RULE_LINES):
        shown = ln[:max(0, chars)]
        chars -= len(ln)
        if li == HL[1] and hl_p > 0:
            i0 = ln.index(HL[0])
            x0 = 30 + f.getlength(ln[:i0])
            x1 = x0 + f.getlength(HL[0])
            xe = lerp(x0, x1, hl_p)
            d.rounded_rectangle((x0 - 6, y + 2, xe + 6, y + 38), 6, fill=ACC + (255,))
        if shown:
            if li == HL[1] and hl_p > 0:
                i0 = ln.index(HL[0])
                parts = [(shown[:i0], (205, 207, 214)), (shown[i0:i0 + len(HL[0])], (20, 20, 22)),
                         (shown[i0 + len(HL[0]):], (205, 207, 214))]
                x = 30
                for s, col in parts:
                    if s:
                        d.text((x, y), s, font=f, fill=col + (255,))
                    x += f.getlength(s)
            else:
                d.text((30, y), shown, font=f, fill=(205, 207, 214, 255))
        y += 46
    return im


def radial(dst, cx, cy, t, t0, n=26, col=ACC):
    p = (t - t0) / 0.5
    if not 0 < p < 1:
        return
    rng = np.random.default_rng(7)
    im = Image.new("L", (PW, PH), 0)
    d = ImageDraw.Draw(im)
    for i in range(n):
        ang = i / n * 2 * math.pi + rng.uniform(-0.08, 0.08)
        r0 = 180 + 520 * e_out(p) * rng.uniform(0.6, 1.0)
        ln = 60 + 140 * (1 - p) * rng.uniform(0.5, 1.0)
        x0, y0 = cx + math.cos(ang) * r0, cy + math.sin(ang) * r0 * 0.62
        x1, y1 = cx + math.cos(ang) * (r0 + ln), cy + math.sin(ang) * (r0 + ln) * 0.62
        d.line((x0, y0, x1, y1), fill=255, width=3)
    m = np.asarray(im, np.float32)[..., None] / 255
    dst += m * (np.array(col, np.float32) / 255) * (1 - p) * 0.9


def scene_rule(dst, t):
    if not (T_RULE - 0.05 <= t <= T_GOAL + 0.05):
        return
    wr = [wt("rule", i) - 0.05 for i in range(10)]
    out = T_NOWH - 0.22
    typed(dst, "ICING ONLY COUNTS IF YOU'RE…", "m7", 24, ACC, 540, 46, t, T_RULE + 0.02, cps=30, anchor="c",
          cursor=False) if t < out + 0.2 else None
    KLine([("EVEN", WHITE), ("OR", WHITE), ("STRONGER", ACC)], "x9", 64, 540, 112, wr[5:8], out).render(dst, t)
    q = c01((t - out) / 0.18)
    a = c01((t - T_RULE) / 0.2) * (1 - q)
    if a > 0:
        p = e_out((t - T_RULE) / 0.45)
        card_draw(dst, rule_card(t), 540, 392 + (1 - p) * 60 + q * 0, a, 0, 14 * (1 - p), 1 + 0.12 * q)
    # Impact "NO WHISTLE."
    if t >= T_NOWH - 0.04:
        p = (t - T_NOWH + 0.04) / 0.32
        s = lerp(1.55, 1.0, back(p, 1.3))
        x_out = c01((t - T_GOAL + 0.12) / 0.12)
        aa = c01(p * 3) * (1 - x_out)
        radial(dst, 540, 300, t, T_NOWH)
        nw = text_spr("NO WHISTLE", "x9", 100, WHITE)
        dt = text_spr(".", "x9", 100, ACC)
        draw(dst, nw, 540 - 22, 300, aa, s, glow=0.0)
        draw(dst, dt, 540 - 22 + nw.tw / 2 * s + 18 * s, 300, aa, s, glow=0.9)
        sub = text_spr("RULE 81.6 · \"PLAY SHALL CONTINUE\"", "m5", 20, GREY)
        draw(dst, sub, 540, 392, c01((t - T_NOWH - 0.35) / 0.2) * (1 - x_out))


# ================================================================= Szene D: Überzahltor
def ruler(dst, cy, t, t0, col_tick, col_head, x0=140, x1=940, n=41, head=None):
    for i in range(n):
        x = lerp(x0, x1, i / (n - 1))
        big = i % 5 == 0
        h = 26 if big else 12
        a = c01((t - t0 - i * 0.006) / 0.15)
        blit(dst, solid(col_tick, 2, h, 1.0), x - 1, cy - h / 2, a * (0.9 if big else 0.55))
    if head is not None:
        blit(dst, solid(col_head, 4, 70), head - 2, cy - 35)


def scene_goal(dst, t):
    if not (T_GOAL - 0.02 <= t <= T_BLAME + 0.3):
        return
    if t < T_BACK:                                                  # oranger Blitz: POWER-PLAY GOAL
        fl = 1 - c01((t - T_GOAL) / 0.08)
        dst[:] = np.array(ACC, np.float32) / 255 * (1 + 0.25 * fl)
        g = np.linspace(1.08, 0.92, PH, dtype=np.float32)[:, None, None]
        dst *= g
        k = KLine([("POWER-PLAY", DARK), ("GOAL", DARK)], "x9", 64, 540, 230,
                  [T_GOAL - 0.02, wt("goal", 1) - 0.05], None, glow=0)
        k.render(dst, t)
        hp = e_out((t - T_GOAL) / 0.55, 2)
        ruler(dst, 380, t, T_GOAL, DARK, (250, 250, 250), head=lerp(150, 540, hp))
        return
    out = c01((t - T_BLAME + 0.32) / 0.22)
    a = c01((t - T_BACK) / 0.12) * (1 - out)
    lab = text_spr("PENALTY BOX", "m5", 22, GREY)
    draw(dst, lab, 540, 120 - out * 40, a)
    snap = c01((t - T_ENDS) / 0.18)
    left = penalty_left(T_GOAL)
    if snap <= 0:
        clk = text_spr(fmt(left), "m7", 170, WHITE)
        draw(dst, clk, 540, 262 - out * 60, a)
    else:
        old = text_spr(fmt(left), "m7", 170, WHITE)
        new = text_spr("0:00", "m7", 170, ACC)
        draw(dst, old, 540, 262 - 90 * e_in(snap, 2), a * (1 - snap))
        draw(dst, new, 540, 262 + 90 * (1 - e_out(snap)) - out * 60, a * snap, 1.0, glow=0.8)
        rp = c01((t - T_ENDS) / 0.6)
        ring(dst, 540, 262, 120 + 300 * e_out(rp), 3, ACC, (1 - rp) * a)
    KLine([("MINOR", ACC), ("OVER.", WHITE)], "x9", 62, 540, 432, [T_ENDS - 0.02, T_ENDS + 0.14],
          T_BLAME - 0.32).render(dst, t)
    note = text_spr("RULE 16.2 · A MAJOR KEEPS RUNNING", "m5", 19, GREY)
    draw(dst, note, 540, 512, c01((t - wt("goal", 6)) / 0.25) * (1 - out))


# ================================================================= Szene E: Geschichte
def goal_time(g, c0, c1):
    """Zeitpunkt, zu dem der (sinusförmig beschleunigte) Zähler bei g Sekunden steht."""
    return c0 + (c1 - c0) * math.acos(1 - 2 * g / HIST_GOALS[-1]) / math.pi


def scene_hist(dst, t):
    if not (T_BLAME - 0.05 <= t <= T_CTA + 0.3):
        return
    out = T_CTA - 0.06
    oq = c01((t - out) / 0.2)
    if oq < 1:
        typed(dst, HIST_KICKER, "m7", 22, ACC, 540, 44, t, T_BLAME + 0.25, cps=48, anchor="c", cursor=False)
    wb = [wt("blame", i) - 0.05 for i in range(4)]
    KLine([("BLAME", WHITE), ("IT", WHITE), ("ON", WHITE)], "x9", 46, 540, 236, wb[:3], T_HIST - 0.12).render(dst, t)
    KLine([("MONTREAL.", ACC)], "x9", 104, 540, 330, [wb[3]], T_HIST - 0.08).render(dst, t)
    tag = text_spr("\"THE CANADIENS RULE\" · SINCE 1956-57", "m5", 18, GREY)
    draw(dst, tag, 540, 420, c01((t - wb[3] - 0.45) / 0.2) * (1 - c01((t - T_HIST + 0.12) / 0.15)))
    KLine([("BÉLIVEAU", WHITE)], "x9", 66, 540, 112, [wt("hist", 0) - 0.06], out).render(dst, t)
    c0, c1 = wt("hist", 2), wt("hist", 7) + 0.15                    # "scored" .. "seconds": Zähler 0 -> 44
    p = c01((t - c0) / (c1 - c0))
    sec = HIST_GOALS[-1] * sio(p) if p < 1 else HIST_GOALS[-1]
    a = c01((t - T_HIST - 0.1) / 0.25) * (1 - oq)
    if a > 0:
        cnt = text_spr(f"00:{int(sec):02d}", "m7", 116, WHITE if p < 1 else ACC)
        draw(dst, cnt, 540, 250, a, glow=0.6 if p >= 1 else 0)
        x0, x1 = 140, 940
        ruler(dst, 392, t, T_HIST + 0.1, (200, 200, 205), ACC, x0, x1, 51,
              head=lerp(x0, x1, sec / 50.0) if p > 0 else None)
        for i, g in enumerate(HIST_GOALS):
            tg = goal_time(g, c0, c1)
            if t < tg:
                continue
            pp = c01((t - tg) / 0.3)
            x = lerp(x0, x1, g / 50.0)
            dot(dst, x, 392, 11 * back(pp, 2.0), ACC, a, glow=0.8)
            ring(dst, x, 392, 11 + 40 * e_out(pp), 3, ACC, a * (1 - pp))
            lb = text_spr(f"GOAL {i + 1}", "m7", 17, WHITE)
            draw(dst, lb, x, 440, a * c01(pp * 3))
            tm = text_spr(f"+{int(g)}s", "m5", 16, GREY)
            draw(dst, tm, x, 344, a * c01(pp * 3))
    KLine([("3 GOALS", WHITE), ("·", GREY), ("44 SECONDS", ACC)], "x9", 46, 540, 512,
          [wt("hist", 3) - 0.05, wt("hist", 6) - 0.15, wt("hist", 6) - 0.05], out).render(dst, t)
    note = text_spr("5-ON-3 · BACK THEN, MINORS WERE SERVED IN FULL", "m5", 17, GREY)
    draw(dst, note, 540, 572, c01((t - wt("hist", 9)) / 0.25) * (1 - oq))


# ================================================================= Szene F: Frage
def pill(txt, w=300, h=112, hot=0.0):
    key = ("pill", txt, round(hot, 2))
    if key not in _TXT:
        fill = tuple(int(lerp(a_, b_, hot)) for a_, b_ in zip((34, 34, 38), ACC)) + (248,)
        im = rrect_img(w, h, h // 2, fill, (255, 255, 255, 40), 2)
        tx = text_spr(txt, "x9", 56, WHITE)
        im.alpha_composite(tx.img, (int(w / 2 - tx.ax), int(h / 2 - tx.ay)))
        _TXT[key] = im
    return _TXT[key]


def scene_cta(dst, t):
    if t < T_CTA - 0.05:
        return
    w = [wt("cta", i) - 0.05 for i in range(11)]
    KLine([("SHOULD", WHITE), ("SHORT-HANDED", WHITE), ("TEAMS", WHITE)], "x9", 40, 540, 64, [w[0], w[1], w[3]],
          None).render(dst, t)
    KLine([("ICE", ACC), ("IT?", ACC)], "x9", 92, 540, 158, [w[6], w[7]], None).render(dst, t)
    for i, (txt, cx, t0, tl) in enumerate((("YES", 360, T_CTA + 0.35, w[8]), ("NO", 720, T_CTA + 0.47, w[10]))):
        p = (t - t0) / 0.4
        if p <= 0:
            continue
        hl = c01((t - tl) / 0.08) * (1 - 0.6 * e_out((t - tl - 0.12) / 0.5)) if t > tl else 0.0
        pop_ = 1 + 0.08 * math.sin(math.pi * c01((t - tl) / 0.25)) if t > tl else 1.0
        card_draw(dst, pill(txt, hot=round(hl * 20) / 20), cx, 372 + (1 - e_out(p)) * 40,
                  c01(p * 2.5) * (0.55 + 0.45 * c01((t - tl + 0.1) / 0.1)), 0, -40 * (1 - back(p, 1.4)),
                  (0.9 + 0.1 * back(p, 1.6)) * pop_)
    c = (t - w[4]) / 0.6
    if c > 0:
        def cp(tt):
            k = sio((tt - w[4]) / 0.6)
            sway = 0.0 if tt < w[4] + 0.6 else math.sin((tt - w[4] - 0.6) * 2.2) * 150
            return lerp(60, 540 + sway, k), lerp(600, 420, k)
        x, y = cp(t)
        x0, y0 = cp(t - SHUT)
        draw_cursor(dst, x, y, c01(c * 3), "COMMENT", c01((t - w[10] - 0.2) / 0.2), x0, y0)
    hd = text_spr("@bladesandpucks", "a7", 24, GREY)
    draw(dst, hd, 540, 560, c01((t - w[10] - 0.3) / 0.3) * 0.9)


# ================================================================= Rahmen (Header, Fortschritt)
HEADER = None


def header():
    global HEADER
    if HEADER is None:
        arr = np.zeros((H, W, 3), np.float32)
        k = text_spr("NHL RULES EXPLAINED · PART 8", "in6", 27, ACC)
        draw(arr, k, 540, 416)
        tt = text_spr("Power Play", "in6", 50, WHITE)
        draw(arr, tt, 540, 466)
        HEADER = arr
    return HEADER


def progress(frame, t):
    y = PY + PH + 58
    n = len(SCENES)
    cur = max(i for i, s in enumerate(SCENES) if t >= s - 0.05)
    xs = [540 + (i - (n - 1) / 2) * 30 for i in range(n)]
    for i, x in enumerate(xs):
        if i == cur:
            p = e_out((t - SCENES[i] + 0.05) / 0.3)
            w = int(10 + 22 * p)
            blit(frame, rr_spr(w, 10, ACC), x - w / 2, y - 5)
        else:
            blit(frame, rr_spr(10, 10, (90, 90, 96) if i > cur else (170, 170, 176)), x - 5, y - 5)


def rr_spr(w, h, col):
    key = ("rr", w, h, col)
    if key not in _SOLID:
        _SOLID[key] = to_spr(rrect_img(w, h, h // 2, col + (255,)))
    return _SOLID[key]


def compose(t, fidx=0):
    global BG
    if BG is None:
        BG = panel_bg()
    p = BG.copy()
    flash = T_GOAL <= t < T_BACK
    if not flash:
        bokeh(p, t)
    scene_hook(p, t)
    scene_short(p, t)
    hud(p, t)
    scene_rule(p, t)
    scene_goal(p, t)
    scene_hist(p, t)
    scene_cta(p, t)
    if T_NOWH - 0.02 <= t < T_NOWH + 0.06:                          # kurzer Lichtblitz beim Impact
        p += 0.08 * (1 - (t - T_NOWH + 0.02) / 0.08)
    frame = header().copy()
    frame[PY:PY + PH] = p
    progress(frame, t)
    frame += np.random.default_rng(fidx).normal(0, 0.008, (H, W))[..., None].astype(np.float32)
    return (np.clip(frame, 0, 1) * 255).astype(np.uint8)


# ================================================================= Ton
SR = 44100


def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(31)
    mus = np.zeros((n, 2))
    sfx = np.zeros((n, 2))
    B = 60 / 112

    def tt(sec):
        return np.arange(int(sec * SR)) / SR

    def put_(buf, sig, at_, vol=1.0, pan=0.0):
        st = int(round(at_ * SR))
        if st >= n or st + len(sig) <= 0:
            return
        s0 = max(0, -st)
        st = max(st, 0)
        e = min(n, st + len(sig) - s0)
        gl, gr = math.cos((pan + 1) * math.pi / 4) * 1.41, math.sin((pan + 1) * math.pi / 4) * 1.41
        buf[st:e, 0] += sig[s0: s0 + e - st] * vol * gl
        buf[st:e, 1] += sig[s0: s0 + e - st] * vol * gr

    def lp(x, k):
        c = np.cumsum(np.concatenate([np.zeros(k), x]))
        return (c[k:] - c[:-k]) / k

    def hp(x, k):
        return x - lp(x, k)

    def noise(sec):
        return rng.standard_normal(int(sec * SR))

    def kick(vol=1.0):
        x = tt(0.4)
        f = 45 + 120 * np.exp(-x * 30)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 9) * 2.0) * vol

    def pluck(freq, vol=0.1, dec=7.0):
        x = tt(0.6)
        sig = np.sin(2 * np.pi * freq * x) + 0.35 * np.sin(2 * np.pi * freq * 2 * x) * np.exp(-x * 12)
        return sig * np.exp(-x * dec) * np.minimum(x / 0.004, 1) * vol

    def pad(freqs, dur, vol=0.05):
        x = tt(dur)
        sig = sum(np.sin(2 * np.pi * f * x + 0.4 * np.sin(2 * np.pi * 0.3 * x + i)) for i, f in enumerate(freqs))
        env = np.minimum(x / 0.8, 1) * np.clip((dur - x) / 0.8, 0, 1)
        return lp(sig, 4) * env * vol

    def tick(vol=0.25, f=3200):
        x = tt(0.025)
        return np.sin(2 * np.pi * f * x) * np.exp(-x * 260) * vol

    def click(vol=0.3):
        x = tt(0.03)
        return hp(noise(0.03), 2) * np.exp(-x * 300) * vol

    def whoosh(dur=0.5, vol=0.4, up=True):
        x = tt(dur)
        env = (x / dur) ** 2 * np.exp(-((x / dur - 0.8) ** 2) * 6) if up else np.sin(np.pi * x / dur) ** 2
        return hp(lp(noise(dur), 5), 30) * env * vol

    def boom(vol=1.0):
        x = tt(1.4)
        f = 32 + 90 * np.exp(-x * 9)
        body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 2.6)
        return np.tanh((body * 2.2 + lp(noise(1.4), 6) * np.exp(-x * 14) * 0.5)) * vol

    def hit(vol=0.8):
        x = tt(0.5)
        return np.tanh((hp(noise(0.5), 2) * np.exp(-x * 30) + np.sin(2 * np.pi * 70 * x) * np.exp(-x * 10)) * 2) * vol

    def riser(dur=0.6, vol=0.3):
        x = tt(dur)
        f = 300 + 2200 * (x / dur) ** 2
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.3 + hp(noise(dur), 3) * 0.7) * (x / dur) ** 2 * vol

    def slap(vol=0.7):
        x = tt(0.18)
        return np.tanh((hp(noise(0.18), 1) * np.exp(-x * 60) * 1.4 + np.sin(2 * np.pi * 180 * x) * np.exp(-x * 40))
                       * 2) * vol

    def chime(vol=0.3):
        out = np.zeros(int(1.4 * SR))
        for i, f in enumerate((880.0, 1318.5, 1760.0)):
            x = tt(1.4 - 0.06 * i)
            out[int(0.06 * i * SR):][:len(x)] += np.sin(2 * np.pi * f * x) * np.exp(-x * 3.5) * vol
        return out

    def pop(vol=0.4, f=900):
        x = tt(0.09)
        return np.sin(2 * np.pi * np.cumsum(f * (1 + 1.5 * np.exp(-x * 60))) / SR) * np.exp(-x * 45) * vol

    # Musik: ruhiger Puls in a-Moll, Plucks in Achteln, Fläche drunter
    chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (196.0, 246.94, 293.66), (164.81, 207.65, 246.94)]
    arp = [0, 1, 2, 1, 2, 0, 1, 2]
    for k8 in range(int(DUR / (B / 2))):
        tb = k8 * B / 2
        b = k8 / 2
        if tb > DUR - 0.5:
            continue
        ch = chords[int(b // 4) % 4]
        if b % 1 == 0:
            put_(mus, kick(0.55 if b % 2 == 0 else 0.35), tb)
        if T_GOAL - 0.4 < tb < T_BACK:
            continue
        put_(mus, pluck(ch[arp[k8 % 8]] * 2, 0.10), tb, pan=0.4 * math.sin(k8))
        if b % 4 == 0:
            put_(mus, pad([f / 2 for f in ch], 4 * B + 0.4, 0.05), tb)
    for i, ts in enumerate([wt("q", i) for i in range(7)] + [wt("sh", 1)] + [wt("rule", i) for i in (5, 6, 7)]
                           + [wt("cta", i) for i in (0, 1, 3, 6, 7)]):
        put_(sfx, click(0.22), ts - 0.02, pan=0.2 * (-1) ** i)
    put_(sfx, slap(0.8), T_SHOT)
    put_(sfx, whoosh(0.55, 0.35, False), T_SHOT)
    put_(sfx, hit(0.35), T_ARRIVE)
    put_(sfx, pop(0.35, 1300), 1.3)
    put_(sfx, whoosh(0.4, 0.3), T_SH - 0.3)
    for _, _, t0 in CARDS_B:
        put_(sfx, whoosh(0.35, 0.28, False), t0 - 0.05, pan=0.0)
        put_(sfx, pop(0.25, 700), t0 + 0.28)
    put_(sfx, hit(0.4), T_BOX)
    for k in range(int(T_GOAL - T_BOX)):
        put_(sfx, tick(0.12, 2600), T_BOX + 0.25 + k)
    put_(sfx, whoosh(0.35, 0.25), T_RULE - 0.25)
    put_(sfx, riser(0.45, 0.2), T_NOWH - 0.45)
    put_(sfx, boom(1.0), T_NOWH)
    put_(sfx, riser(0.6, 0.3), T_GOAL - 0.6)
    put_(sfx, hit(0.9), T_GOAL)
    put_(sfx, boom(0.6), T_GOAL)
    put_(sfx, whoosh(0.3, 0.25), T_BACK - 0.2)
    put_(sfx, chime(0.3), T_ENDS)
    put_(sfx, whoosh(0.35, 0.25), T_BLAME - 0.25)
    put_(sfx, hit(0.5), wt("blame", 3))
    put_(sfx, whoosh(0.3, 0.2), T_HIST - 0.2)
    c0, c1 = wt("hist", 2), wt("hist", 7) + 0.15
    for k in range(int(HIST_GOALS[-1])):                             # Zähler 0 -> 44
        put_(sfx, tick(0.08, 3400), goal_time(k, c0, c1))
    for g in HIST_GOALS:
        put_(sfx, pop(0.5, 1100), goal_time(g, c0, c1))
    put_(sfx, whoosh(0.35, 0.25), T_CTA - 0.25)
    put_(sfx, pop(0.4, 900), wt("cta", 8) + 0.1)
    put_(sfx, pop(0.4, 700), wt("cta", 10) + 0.1)
    voice = np.zeros(n)
    for k in VO_KEYS:
        tmp = os.path.join(HERE, f"_vo_{k}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "voice", f"reel31_{k}.wav"),
                        "-af", f"atempo={TEMPO}", "-ar", str(SR), "-ac", "1", tmp], check=True)
        with wave.open(tmp) as w:
            v = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        os.remove(tmp)
        st = int(VO_START[k] * SR)
        e = min(n, st + len(v))
        voice[st:e] += v[: e - st]
    voice /= np.max(np.abs(voice)) + 1e-9
    k = int(0.08 * SR)
    venv = np.convolve(np.abs(voice), np.ones(k) / k, mode="same")
    duck = 1 - 0.7 * np.clip(venv / 0.06, 0, 1)
    sduck = 1 - 0.5 * np.clip(venv / 0.06, 0, 1)
    mus /= np.max(np.abs(mus)) + 1e-9
    sfx /= np.max(np.abs(sfx)) + 1e-9
    mix = mus * 0.36 * duck[:, None] + sfx * 0.5 * sduck[:, None] + voice[:, None] * 1.0
    mix = np.tanh(mix * 1.05)
    mix *= np.clip((DUR - np.arange(n) / SR) / 0.3, 0, 1)[:, None]
    mix = mix / np.max(np.abs(mix)) * 0.95
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


def make_voice():
    import tts_kokoro
    tts_kokoro.synth(VO_LINES, os.path.join(HERE, "voice", "reel31"), speed=1.2, fixes=VO_FIXES)


def check_vo():
    with open(os.path.join(HERE, "voice", "reel31_timing.json")) as f:
        vo_dur = {k: v / TEMPO for k, v in json.load(f).items()}
    for i, k in enumerate(VO_KEYS[:-1]):
        nxt = VO_KEYS[i + 1]
        if VO_START[k] + vo_dur[k] > VO_START[nxt] + 0.35:
            print(f"Warnung: Satz {k} überlappt {nxt} ({VO_START[k] + vo_dur[k]:.2f} > {VO_START[nxt]:.2f})")
    if VO_START[VO_KEYS[-1]] + vo_dur[VO_KEYS[-1]] > DUR - 0.2:
        print("Warnung: letzter Satz zu lang für DUR")


def remux():
    os.chdir(HERE)
    make_audio("audio_powerplay.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "reel31_powerplay.mp4", "-i", "audio_powerplay.wav", "-map",
                    "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-af",
                    "loudnorm=I=-14:TP=-1.0:LRA=9", "-ar", "44100", "-shortest", "-movflags", "+faststart",
                    "_tmp_pp.mp4"], check=True)
    os.replace("_tmp_pp.mp4", "reel31_powerplay.mp4")


def _frame(i):
    return compose(i / FPS, i).tobytes()


def preview(ts, out):
    ims = [Image.fromarray(compose(float(t), 1)) for t in ts]
    th = [im.resize((W // 3, H // 3)) for im in ims]
    cols = min(6, len(th))
    rows = (len(th) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (W // 3), rows * (H // 3)), (40, 40, 40))
    for i, im in enumerate(th):
        sheet.paste(im, ((i % cols) * (W // 3), (i // cols) * (H // 3)))
    sheet.save(out, quality=88)


def main():
    os.chdir(HERE)
    check_vo()
    make_audio("audio_powerplay.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_powerplay.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
           "-ar", "44100", "-shortest", "-movflags", "+faststart", "reel31_powerplay.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    with Pool(4) as pool:
        for i, fr in enumerate(pool.imap(_frame, range(nf), chunksize=4)):
            proc.stdin.write(fr)
            if i % 60 == 0:
                print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(1.2, 9999)).save("reel31_thumbnail.jpg", quality=92)
    print("fertig: reel31_powerplay.mp4")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "vo":
        make_voice()
    elif len(sys.argv) > 1 and sys.argv[1] == "audio":
        remux()
    elif len(sys.argv) > 1 and sys.argv[1] == "prev":
        preview(sys.argv[2].split(","), sys.argv[3])
    else:
        main()
