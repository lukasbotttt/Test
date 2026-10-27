"""Reel 42 – "This NHL game had NINE periods." Längstes Spiel der NHL-Geschichte (Playoff-Overtime ohne Shootout).

Fakten (geprüft):
  - NHL-Regelbuch 2026-27, Regel 84.5: Playoffs – bei Gleichstand nach drei Dritteln 20-Minuten-Overtimes,
    das erste Tor entscheidet. Regel 84.4: Shootout nur in der regulären Saison.
  - NHL.com "This Date in NHL History: March 24" + Hockey-Reference "NHL's Longest Games":
    24.03.1936, Forum Montreal, Detroit Red Wings 1, Montreal Maroons 0, Game 1 Halbfinale.
    Mud Bruneteau trifft bei 16:30 der 6. Overtime (116:30 Verlängerung, 176:30 gesamt), um 2:25 Uhr morgens.
    Bis heute das längste NHL-Spiel. 3 reguläre Drittel + 6 Overtimes = 9 Perioden.
Look: Vintage-Anzeigetafel mit Glühbirnen-Ziffern in dunkler Halle (Ziffern prozedural, keine Logos, keine Fotos).

Aufruf: python3 reel42_ninth.py vo | prev 0.5,3 out.jpg | (ohne Argument: rendern) | audio
"""
import json
import math
import os
import subprocess
import sys
import time
import wave
from multiprocessing import Pool

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
W, H, FPS = 1080, 1920, 30
SR = 48000
TEMPO = 1.08

VO_LINES = [
    ("q", "This NHL game had nine periods."),
    ("rule", "Playoffs have no shootout. You play until somebody scores."),
    ("story", "Detroit versus the Montreal Maroons. Zero to zero, into the sixth overtime."),
    ("goal", "At two twenty-five in the morning, Bruneteau scored."),
    ("stat", "A hundred seventy-six minutes."),
    ("cta", "Should the regular season ditch the shootout? Yes or no?"),
]
VO_KEYS = [k for k, _ in VO_LINES]
FIXES = {"bɹˈʌnɪtˌoʊ": "bɹˌuːnɛtˈoʊ"}
VO_START = {"q": 0.10, "rule": 2.25, "story": 5.45, "goal": 10.17, "stat": 12.98, "cta": 14.72}
DUR = 17.95
WT = {                                           # Wortanfänge (s nach Satzbeginn, nach 1,08x), faster-whisper small.en
    "q": [0.0, 0.18, 0.56, 0.82, 1.08, 1.32],
    "rule": [0.0, 0.3, 0.5, 0.72, 1.54, 1.62, 1.74, 1.98, 2.38],
    "story": [0.0, 0.34, 0.66, 0.86, 1.3, 2.42, 2.58, 2.72, 3.06, 3.38, 3.56, 3.84],
    "goal": [0.0, 0.18, 0.82, 0.96, 1.06, 1.66, 1.96],
    "stat": [0.0, 0.72],
    "cta": [0.0, 0.14, 0.26, 0.52, 0.82, 1.1, 1.28, 2.04, 2.12, 2.3],
}


def wt(key, i):
    return VO_START[key] + WT[key][i]


T_ROLL = 0.75                                    # Periodenziffer rollt 1 -> 9
T_STRIKE = wt("rule", 3)                         # "shootout" -> durchgestrichen
T_UNTIL = wt("rule", 4)                          # "You play until somebody scores"
T_STORY = VO_START["story"]
T_ZERO = wt("story", 5)                          # "zero to zero"
T_SIXTH = wt("story", 10)                        # "sixth (overtime)"
T_GOALSC = VO_START["goal"]
T_225 = wt("goal", 1)
T_GOAL = wt("goal", 6)                           # "scored"
T_STAT = VO_START["stat"]
T_CTA = VO_START["cta"]
T_YN = wt("cta", 7)

AMBER = np.array((1.0, 0.72, 0.30), np.float32)
WARM = np.array((1.0, 0.86, 0.62), np.float32)
WHITE = np.array((0.96, 0.96, 0.97), np.float32)
RED = np.array((0.92, 0.12, 0.12), np.float32)
GREEN = np.array((0.25, 0.82, 0.38), np.float32)


def c01(x):
    return min(1.0, max(0.0, x))


def smooth(p):
    p = c01(p)
    return p * p * (3 - 2 * p)


def e_out(p):
    p = c01(p)
    return 1 - (1 - p) ** 3


def e_back(p, s=1.7):
    p = c01(p) - 1
    return p * p * ((s + 1) * p + s) + 1


# ================================================================= Text / Sprites (prämultipliziert)
def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def text_spr(txt, name, size, col, track=0.0, stroke=0, fill=True):
    f = font(name, size)
    w = int(sum(f.getlength(c) for c in txt) + track * size * max(0, len(txt) - 1)) + size + 2 * stroke
    asc, desc = f.getmetrics()
    im = Image.new("RGBA", (w, asc + desc + size // 2 + 2 * stroke), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = size // 2 + stroke
    c255 = tuple(int(v * 255) for v in col)
    for ch in txt:
        d.text((x, size // 4 + stroke), ch, font=f, fill=(c255 + (255,)) if fill else (0, 0, 0, 0),
               stroke_width=stroke, stroke_fill=c255 + (255,))
        x += f.getlength(ch) + track * size
    im = im.crop(im.getbbox())
    a = np.asarray(im, np.float32) / 255
    a[..., :3] *= a[..., 3:4]
    return a


def fitw(a, maxw):
    if a.shape[1] <= maxw:
        return a
    s = maxw / a.shape[1]
    return cv2.resize(a, (int(a.shape[1] * s), int(a.shape[0] * s)), interpolation=cv2.INTER_AREA)


def scaled(a, s):
    if abs(s - 1) < 1e-3:
        return a
    return cv2.resize(a, (max(1, int(a.shape[1] * s)), max(1, int(a.shape[0] * s))),
                      interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)


def over_c(img, spr, cx, cy, k=1.0):
    if k <= 0:
        return
    h, w = spr.shape[:2]
    x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if xb <= xa or yb <= ya:
        return
    s = spr[ya - y0:yb - y0, xa - x0:xb - x0] * k
    nc = img.shape[2]                             # 3 = Bild, 4 = Sprite-Ebene (prämultipliziert)
    img[ya:yb, xa:xb] = s[..., :nc] + img[ya:yb, xa:xb] * (1 - s[..., 3:4])


def glow_c(img, spr, cx, cy, col, sigma, k):
    """Farbiger Schein hinter einem Sprite (additiv)."""
    if k <= 0:
        return
    pad = int(sigma * 3)
    a = np.pad(spr[..., 3], pad)
    g = cv2.GaussianBlur(a, (0, 0), sigma)[..., None] * col * k
    h, w = g.shape[:2]
    x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if xb > xa and yb > ya:
        img[ya:yb, xa:xb] += g[ya - y0:yb - y0, xa - x0:xb - x0]


def blur_q(img, sigma):
    h, w = img.shape[:2]
    small = cv2.resize(img, (w // 4, h // 4), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), sigma / 4)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)


def pill(txt, bg, fg, size=34):
    t = text_spr(txt, "ArchivoX800.ttf", size, fg, 0.16)
    h, w = t.shape[0] + 30, t.shape[1] + 60
    a = np.zeros((h, w, 4), np.float32)
    cv2.rectangle(a, (0, 0), (w - 1, h - 1), (float(bg[0]), float(bg[1]), float(bg[2]), 1.0), -1, cv2.LINE_AA)
    over_c(a, t, w / 2, h / 2)
    return a


# ================================================================= Anzeigetafel
BX0, BY0, BX1, BY1 = 50, 690, 1030, 1300        # Tafel
SEGS = {0: "abcdef", 1: "bc", 2: "abged", 3: "abgcd", 4: "fgbc", 5: "afgcd", 6: "afgedc", 7: "abc", 8: "abcdefg", 9: "abcdfg"}


def seg_points(cx, cy, w, h):
    x0, y0 = cx - w / 2, cy - h / 2
    hx = np.linspace(x0 + w * 0.2, x0 + w * 0.8, 4)
    vt = np.linspace(y0 + h * 0.12, y0 + h * 0.4, 3)
    vb = np.linspace(y0 + h * 0.6, y0 + h * 0.88, 3)
    return {"a": [(x, y0) for x in hx], "g": [(x, y0 + h / 2) for x in hx], "d": [(x, y0 + h) for x in hx],
            "f": [(x0, y) for y in vt], "b": [(x0 + w, y) for y in vt],
            "e": [(x0, y) for y in vb], "c": [(x0 + w, y) for y in vb]}


DIG = {}                                          # Ziffernplätze: name -> (cx, cy, w, h)
DIG["c0"], DIG["c1"], DIG["c2"], DIG["c3"] = [(cx, 845, 70, 118) for cx in (340, 440, 640, 740)]
DIG["home"] = (240, 1110, 108, 186)
DIG["away"] = (840, 1110, 108, 186)
DIG["per"] = (540, 1120, 140, 236)
DIG_PTS = {k: seg_points(*v) for k, v in DIG.items()}
CHASE = []
for i in range(30):
    CHASE.append((BX0 + 25 + i * (BX1 - BX0 - 50) / 29, BY0 + 18))
for i in range(30):
    CHASE.append((BX1 - 25 - i * (BX1 - BX0 - 50) / 29, BY1 - 18))
for i in range(1, 19):
    CHASE.append((BX0 + 18, BY0 + 18 + i * (BY1 - BY0 - 36) / 19))
    CHASE.append((BX1 - 18, BY0 + 18 + i * (BY1 - BY0 - 36) / 19))


def board_panel():
    ss = 2
    im = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((BX0 * ss, BY0 * ss, BX1 * ss, BY1 * ss), 34 * ss, fill=(26, 19, 14, 255), outline=(92, 66, 40, 255), width=6 * ss)
    d.rounded_rectangle(((BX0 + 40) * ss, (BY0 + 40) * ss, (BX1 - 40) * ss, (BY1 - 40) * ss), 18 * ss, fill=(10, 8, 7, 255),
                        outline=(70, 50, 30, 255), width=3 * ss)
    # Fenster für Uhr / Tore / Periode
    for (x0, y0, x1, y1) in ((280, 770, 800, 920), (150, 990, 330, 1230), (750, 990, 930, 1230), (440, 975, 640, 1260)):
        d.rounded_rectangle((x0 * ss, y0 * ss, x1 * ss, y1 * ss), 10 * ss, fill=(4, 3, 3, 255), outline=(48, 36, 24, 255), width=2 * ss)
    im = im.resize((W, H), Image.LANCZOS)
    a = np.asarray(im, np.float32) / 255
    a[..., :3] *= a[..., 3:4]
    for txt, cx, cy, size in (("TIME", 540, 752, 26), ("DETROIT", 240, 958, 30), ("MAROONS", 840, 958, 30), ("PERIOD", 540, 950, 26)):
        over_c(a, text_spr(txt, "ArchivoX800.ttf", size, (0.80, 0.70, 0.55), 0.25), cx, cy)
    return a


def draw_digit(base, lit, key, d, bright):
    cx, cy, w, h = DIG[key]
    r = max(3, int(w * 0.085))
    on = SEGS.get(d, "") if d is not None else ""
    for seg, pts in DIG_PTS[key].items():
        for x, y in pts:
            p = (int(round(x)), int(round(y)))
            if seg in on and bright > 0:
                cv2.circle(lit, p, r, tuple(float(v * bright) for v in AMBER), -1, cv2.LINE_AA)
                cv2.circle(lit, p, max(1, r // 2), tuple(float(v * bright) for v in WARM), -1, cv2.LINE_AA)
            else:
                cv2.circle(base, p, r, (0.10, 0.07, 0.04), -1, cv2.LINE_AA)
                cv2.circle(base, (p[0] - r // 3, p[1] - r // 3), max(1, r // 4), (0.2, 0.16, 0.12), -1, cv2.LINE_AA)


def colon(base, lit, bright):
    for y in (820, 870):
        cv2.circle(lit if bright > 0 else base, (540, y), 7, tuple(float(v * max(bright, 0.12)) for v in AMBER), -1, cv2.LINE_AA)


# ================================================================= Zustand der Tafel
def clock_spin(t, t0, per_len):
    """Uhr läuft im Zeitraffer 20:00 -> 0:00 je Periode; liefert (mm, ss)."""
    u = ((t - t0) / per_len) % 1.0
    secs = int(1200 * (1 - u))
    return secs // 60, secs % 60


def board_state(t):
    """-> dict(per, home, away, mm, ss, flicker, chase)"""
    st = dict(home=0, away=0, mm=16, ss=30, chase=0.0, ot="")
    if t < T_ROLL:
        st["per"] = 1 + int(8 * smooth(t / T_ROLL))
        st["mm"], st["ss"] = clock_spin(t, 0, T_ROLL / 8)
    elif t < VO_START["rule"]:
        st["per"] = 9
    elif t < T_STORY:
        # Erklärung: Overtimes laufen weiter (Periode 4, 5, 6 …)
        if t < T_UNTIL:
            st["per"], st["mm"], st["ss"] = 3, 0, 0
        else:
            k = int((t - T_UNTIL) / 0.42)
            st["per"] = min(9, 4 + k)
            st["mm"], st["ss"] = clock_spin(t, T_UNTIL, 0.42)
    elif t < T_GOALSC:
        span = T_SIXTH - (T_STORY + 0.15)
        p = c01((t - (T_STORY + 0.15)) / span)
        st["per"] = 1 + int(8 * p) if t < T_SIXTH else 9
        per_len = span / 8
        if t < T_SIXTH:
            st["mm"], st["ss"] = clock_spin(t, T_STORY + 0.15, per_len)
        else:
            st["mm"], st["ss"] = clock_spin(t, T_SIXTH, 2.8)
    else:
        st["per"] = 9
        if t < T_GOAL:                            # Uhr läuft auf 16:30 (abgelaufene Zeit der 6. OT)
            p = c01((t - T_GOALSC) / (T_GOAL - T_GOALSC))
            secs = int(990 * smooth(p) + 0)
            st["mm"], st["ss"] = secs // 60, secs % 60
        if t >= T_GOAL:
            st["home"] = 1
            st["chase"] = 1.0
    if st["per"] >= 4:
        st["ot"] = f"OT{st['per'] - 3}"
    return st


def board_layer(t):
    base = np.zeros((H, W, 3), np.float32)
    lit = np.zeros((H, W, 3), np.float32)
    st = board_state(t)
    on = 1.0                                      # Tafel leuchtet ab Bild 0 (Hook-Bild)
    # Ziffern
    mm, ss = st["mm"], st["ss"]
    for key, d in (("c0", mm // 10 if mm >= 10 else None), ("c1", mm % 10), ("c2", ss // 10), ("c3", ss % 10)):
        draw_digit(base, lit, key, d, 0.85 * on)
    colon(base, lit, 0.85 * on)
    flash0 = 1.0
    if T_ZERO <= t < T_ZERO + 0.9:                # "zero to zero": Spielstand blinkt
        flash0 = 0.35 + 0.65 * (int((t - T_ZERO) * 8) % 2)
    hb = on * (1.0 if t < T_GOAL else (0.6 + 0.4 * (int((t - T_GOAL) * 7) % 2) if t < T_GOAL + 1.6 else 1.0))
    draw_digit(base, lit, "home", st["home"], hb * flash0)
    draw_digit(base, lit, "away", st["away"], on * flash0)
    pb = on * (1.0 + (0.35 * (0.5 + 0.5 * math.sin(t * 12)) if VO_START["q"] + 0.75 < t < 2.2 else 0))
    draw_digit(base, lit, "per", st["per"], pb)
    # Lauflichter am Rahmen
    for i, (x, y) in enumerate(CHASE):
        if st["chase"] > 0:
            k = 1.0 if (i + int((t - T_GOAL) * 14)) % 4 == 0 else 0.25
        else:
            k = 0.18 + 0.1 * math.sin(t * 2 + i * 0.4)
        cv2.circle(lit, (int(x), int(y)), 6, tuple(float(v * k * on) for v in AMBER), -1, cv2.LINE_AA)
    return base, lit, st


# ================================================================= Hintergrund
def make_bg():
    yy = np.arange(H, dtype=np.float32)[:, None, None]
    xx = np.arange(W, dtype=np.float32)[None, :, None]
    img = np.ones((H, W, 3), np.float32) * np.array((0.035, 0.028, 0.024), np.float32)
    img += np.exp(-(((xx - 540) / 620) ** 2 + ((yy - 990) / 520) ** 2)) * np.array((0.20, 0.13, 0.07), np.float32)
    img += np.exp(-(((xx - 540) / 900) ** 2 + ((yy + 200) / 500) ** 2)) * np.array((0.10, 0.07, 0.05), np.float32)
    rng = np.random.default_rng(3)
    bok = np.zeros((H, W, 3), np.float32)
    for _ in range(40):
        x, y = rng.uniform(0, W), rng.uniform(0, 640)
        r, b = rng.uniform(5, 20), rng.uniform(0.15, 0.6)
        cv2.circle(bok, (int(x), int(y)), int(r), (b, b * 0.8, b * 0.55), -1, cv2.LINE_AA)
    img += cv2.GaussianBlur(bok, (0, 0), 7) * 0.7
    vig = 1 - 0.55 * np.clip(((xx / W - 0.5) ** 2 * 1.3 + (yy / H - 0.5) ** 2) * 2.0, 0, 1)
    return img, vig


BG, VIG = make_bg()
PANEL = board_panel()

# ================================================================= Text-Assets
HOOK1 = text_spr("THIS NHL GAME", "Anton.ttf", 132, WHITE, 0.02)
HOOK2 = fitw(text_spr("HAD 9 PERIODS", "Anton.ttf", 190, AMBER, 0.02), 940)
PIL_PLAYOFFS = pill("IN THE PLAYOFFS", (0.92, 0.12, 0.12), (1, 1, 1), 34)
SHOOTOUT = text_spr("SHOOTOUT", "Anton.ttf", 210, WHITE, 0.02)
NEXTGOAL1 = text_spr("NEXT GOAL", "Anton.ttf", 170, WHITE, 0.02)
NEXTGOAL2 = text_spr("WINS", "Anton.ttf", 170, AMBER, 0.02)
DATE = text_spr("MARCH 24, 1936", "Anton.ttf", 150, AMBER, 0.02)
FORUM = text_spr("PLAYOFFS · MONTREAL FORUM", "ArchivoX800.ttf", 34, (0.85, 0.80, 0.72), 0.16)
STILL = text_spr("STILL 0 : 0", "Anton.ttf", 190, WHITE, 0.02)
SIXTH = fitw(text_spr("6TH OVERTIME", "Anton.ttf", 190, AMBER, 0.02), 990)
AM = text_spr("2:25 AM", "Anton.ttf", 190, WHITE, 0.02)
GOAL = text_spr("GOAL!", "Anton.ttf", 260, AMBER, 0.02)
GOALSUB = text_spr("MUD BRUNETEAU · 16:30 OF THE 6TH OT", "ArchivoX800.ttf", 34, WHITE, 0.08)
STAT = text_spr("176:30", "Anton.ttf", 300, AMBER, 0.02)
STATSUB = text_spr("LONGEST GAME IN NHL HISTORY", "ArchivoX800.ttf", 40, WHITE, 0.1)
CTA1 = text_spr("DITCH THE", "Anton.ttf", 150, WHITE, 0.02)
CTA2 = text_spr("SHOOTOUT?", "Anton.ttf", 190, AMBER, 0.02)
OT_LBL = {k: text_spr(f"OT{k}", "ArchivoX800.ttf", 28, AMBER, 0.2) for k in range(1, 7)}
PIP_LBL = [text_spr(s, "ArchivoX800.ttf", 22, (0.75, 0.68, 0.58), 0.1) for s in ("1", "2", "3", "OT1", "OT2", "OT3", "OT4", "OT5", "OT6")]
PIP_HDR = text_spr("3 PERIODS + 6 OVERTIMES", "ArchivoX800.ttf", 30, (0.9, 0.85, 0.78), 0.12)


def yesno():
    out = []
    for txt, col in (("YES", GREEN), ("NO", RED)):
        t = text_spr(txt, "Anton.ttf", 110, (1, 1, 1), 0.04)
        w, h = 360, 170
        a = np.zeros((h, w, 4), np.float32)
        cv2.rectangle(a, (0, 0), (w - 1, h - 1), (float(col[0]), float(col[1]), float(col[2]), 1.0), -1, cv2.LINE_AA)
        over_c(a, t, w / 2, h / 2)
        out.append(a)
    return out


YES, NO = yesno()


def clock_face(hour_deg, min_deg, size=330):
    ss = 2
    n = size * ss
    im = np.zeros((n, n, 4), np.float32)
    c = n // 2
    cv2.circle(im, (c, c), c - 6, (0.94, 0.90, 0.80, 1.0), -1, cv2.LINE_AA)
    cv2.circle(im, (c, c), c - 6, (0.25, 0.18, 0.10, 1.0), 14, cv2.LINE_AA)
    for i in range(60):
        a = math.radians(i * 6)
        r0 = c - 30 if i % 5 == 0 else c - 22
        p0 = (int(c + math.sin(a) * r0), int(c - math.cos(a) * r0))
        p1 = (int(c + math.sin(a) * (c - 16)), int(c - math.cos(a) * (c - 16)))
        cv2.line(im, p0, p1, (0.1, 0.08, 0.06, 1.0), 8 if i % 5 == 0 else 3, cv2.LINE_AA)
    for deg, ln, wd in ((hour_deg, 0.5, 18), (min_deg, 0.78, 11)):
        a = math.radians(deg)
        cv2.line(im, (c, c), (int(c + math.sin(a) * c * ln), int(c - math.cos(a) * c * ln)), (0.08, 0.06, 0.05, 1.0), wd, cv2.LINE_AA)
    cv2.circle(im, (c, c), 14, (0.75, 0.15, 0.1, 1.0), -1, cv2.LINE_AA)
    return cv2.resize(im, (size, size), interpolation=cv2.INTER_AREA)


# ================================================================= Szenen-Text oben
TOP_Y = 400


def top_texts(img, t):
    def slam(spr, cx, cy, t0, t1, glow=None, s0=1.6):
        if not (t0 <= t < t1):
            return
        p = c01((t - t0) / 0.14)
        s = 1 + (s0 - 1) * (1 - p) ** 2
        a = c01((t - t0) / 0.06) * (1 - smooth((t - (t1 - 0.12)) / 0.12))
        sp = scaled(spr, s)
        if glow is not None:
            glow_c(img, sp, cx, cy, glow, 22, 0.55 * a)
        over_c(img, sp, cx, cy, a)

    q_end = VO_START["rule"] - 0.02
    # Hook: ab Bild 0 voll sichtbar, leichter Zoom
    if t < q_end:
        a = 1 - smooth((t - (q_end - 0.1)) / 0.1)
        s = 1.0 + 0.04 * (1 - e_out(t / 0.6))
        over_c(img, scaled(HOOK1, s), 540, 290, a)
        glow_c(img, HOOK2, 540, 470, AMBER, 26, 0.5 * a * (0.8 + 0.2 * math.sin(t * 9)))
        over_c(img, scaled(HOOK2, s), 540, 470, a)
    # Regel
    if VO_START["rule"] <= t < T_STORY:
        tl = t - VO_START["rule"]
        a = c01(tl / 0.08) * (1 - smooth((t - (T_STORY - 0.1)) / 0.1))
        over_c(img, PIL_PLAYOFFS, 540 - 40 * (1 - e_out(tl / 0.25)), 230, a)
        if t < T_UNTIL:
            over_c(img, SHOOTOUT, 540, 420, a)
            if t >= T_STRIKE:                     # roter Strich quer durch
                p = e_out((t - T_STRIKE) / 0.18)
                x0, x1 = 540 - SHOOTOUT.shape[1] / 2 - 20, 540 - SHOOTOUT.shape[1] / 2 - 20 + (SHOOTOUT.shape[1] + 40) * p
                lay = np.zeros((H, W, 3), np.float32)
                cv2.line(lay, (int(x0), 470), (int(x1), int(470 - 95 * p)), tuple(float(v) for v in RED), 26, cv2.LINE_AA)
                m = lay.max(-1, keepdims=True) > 0
                img[:] = np.where(m, lay, img)
        else:
            slam(NEXTGOAL1, 540, 370, T_UNTIL, T_STORY, None, 1.4)
            slam(NEXTGOAL2, 540, 525, T_UNTIL + 0.1, T_STORY, AMBER, 1.4)
    # Geschichte
    slam(DATE, 540, 360, T_STORY, T_ZERO, AMBER, 1.3)
    if T_STORY + 0.25 <= t < T_ZERO:
        over_c(img, FORUM, 540, 495, smooth((t - T_STORY - 0.25) / 0.25) * (1 - smooth((t - (T_ZERO - 0.1)) / 0.1)))
    slam(STILL, 540, 420, T_ZERO, T_SIXTH, None, 1.35)
    slam(SIXTH, 540, 420, T_SIXTH, T_GOALSC, AMBER, 1.35)
    # 2:25 Uhr: Wanduhr + Uhrzeit
    if T_GOALSC <= t < T_GOAL:
        a = c01((t - T_GOALSC) / 0.1) * (1 - smooth((t - (T_GOAL - 0.08)) / 0.08))
        p = e_out((t - T_GOALSC) / 0.55)
        hour = 72.5 - 30 * (1 - p)                 # Minutenzeiger wirbelt drei Runden, landet auf 25 Min (150°)
        cf = clock_face(hour, 150 - 1080 * (1 - p))
        over_c(img, cf, 250, 420, a)
        if t >= T_225:
            over_c(img, scaled(AM, 0.62 + 0.0), 715, 420, a * c01((t - T_225) / 0.1))
    # Tor
    slam(GOAL, 540, 380, T_GOAL, T_STAT, AMBER, 1.8)
    if T_GOAL + 0.25 <= t < T_STAT:
        over_c(img, GOALSUB, 540, 545, smooth((t - T_GOAL - 0.25) / 0.2) * (1 - smooth((t - (T_STAT - 0.1)) / 0.1)))
    # 176:30 zählt hoch
    if T_STAT <= t < T_CTA:
        a = c01((t - T_STAT) / 0.06) * (1 - smooth((t - (T_CTA - 0.1)) / 0.1))
        p = e_out((t - T_STAT) / 0.7)
        secs = int(round((176 * 60 + 30) * p))
        txt = f"{secs // 60}:{secs % 60:02d}"
        spr = STAT if p >= 1 else text_spr(txt, "Anton.ttf", 300, AMBER, 0.02)
        glow_c(img, spr, 540, 390, AMBER, 30, 0.5 * a)
        over_c(img, spr, 540, 390, a)
        if t >= T_STAT + 0.5:
            over_c(img, STATSUB, 540, 580, a * smooth((t - T_STAT - 0.5) / 0.2))
    # CTA
    slam(CTA1, 540, 300, T_CTA, DUR + 1, None, 1.3)
    slam(CTA2, 540, 470, T_CTA + 0.12, DUR + 1, AMBER, 1.3)


def lower(img, t, st):
    """Unter der Tafel: 9 Perioden-Kästchen (3 + 6 OT) bzw. YES/NO."""
    if t >= T_CTA:
        if t >= T_YN - 0.05:
            for i, (b, x) in enumerate(((YES, 345), (NO, 735))):
                p = e_back((t - (T_YN - 0.05 + i * 0.08)) / 0.3)
                pulse = 1 + 0.04 * math.sin((t - T_YN) * 7 + i * 3) if t > T_YN + 0.4 else 1
                over_c(img, scaled(b, max(0.01, p) * pulse), x, 1420, c01(p * 3))
        return
    n = st["per"] if t >= 0 else 0
    if t < T_ROLL:
        n = st["per"]
    filled = n
    pw, gap = 88, 11
    x0 = 540 - (9 * pw + 8 * gap) / 2
    a_hdr = c01((t - 1.1) / 0.2) if t < VO_START["rule"] else 1.0
    over_c(img, PIP_HDR, 540, 1345, a_hdr)
    lay = np.zeros((H, W, 3), np.float32)
    for i in range(9):
        x = x0 + i * (pw + gap)
        col = WHITE if i < 3 else AMBER
        on = i < filled
        cv2.rectangle(lay if on else img, (int(x), 1380), (int(x + pw), 1410),
                      tuple(float(v * (0.95 if on else 0.13)) for v in col), -1, cv2.LINE_AA)
        over_c(img, PIP_LBL[i], x + pw / 2, 1440, 0.9)
    img += lay
    img += blur_q(lay, 14) * 0.6


# ================================================================= Komposition
def compose(t, fidx=0):
    img = BG.copy()
    # Tafel
    over_c(img, PANEL, 540, 960)
    base, lit, st = board_layer(t)
    m = base.max(-1, keepdims=True) > 0
    img = np.where(m, base, img)
    img += lit + blur_q(lit, 10) * 0.9 + blur_q(lit, 34) * 0.55
    lower(img, t, st)
    top_texts(img, t)
    # Tor: Blitz + Kamera-Ruck
    fl = 0.0
    for t0, f in ((T_GOAL, 0.55), (T_STAT, 0.2), (T_STRIKE, 0.12), (T_SIXTH, 0.15), (T_UNTIL, 0.12)):
        if t >= t0:
            fl += f * math.exp(-(t - t0) * 14)
    img += fl * WARM
    amp = 0.0
    for t0, a in ((T_GOAL, 22), (T_STAT, 10), (T_SIXTH, 8), (T_ZERO, 6), (T_STRIKE, 8)):
        if t >= t0:
            amp += a * math.exp(-(t - t0) * 9)
    s = 1.0 + 0.025 * smooth(t / DUR) + 0.03 * math.exp(-max(0.0, t - T_GOAL) * 6) * (t >= T_GOAL)
    mtx = cv2.getRotationMatrix2D((540, 960), 0, s)
    mtx[0, 2] += amp * math.sin(t * 93)
    mtx[1, 2] += amp * math.cos(t * 71)
    img = cv2.warpAffine(img, mtx, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    img = img + blur_q(np.clip(img - 0.8, 0, None), 24) * 0.4
    img *= VIG
    rng = np.random.default_rng(fidx)
    img += cv2.resize(rng.standard_normal((H // 2, W // 2)).astype(np.float32), (W, H), interpolation=cv2.INTER_NEAREST)[..., None] * 0.014
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


def preview(ts, out):
    ims = [Image.fromarray(compose(float(x), 7)) for x in ts]
    th = [im.resize((360, 640)) for im in ims]
    sheet = Image.new("RGB", (len(th) * 368, 640), (40, 40, 40))
    for i, im in enumerate(th):
        sheet.paste(im, (i * 368, 0))
    sheet.save(out, quality=90)


# ================================================================= Ton
def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(42)
    mus = np.zeros((n, 2))
    sfx = np.zeros((n, 2))

    def tt(sec):
        return np.arange(int(sec * SR)) / SR

    def put(buf, sig, at, vol=1.0, pan=0.0):
        st = int(round(at * SR))
        if st >= n:
            return
        s0 = max(0, -st)
        st = max(st, 0)
        e = min(n, st + len(sig) - s0)
        gl, gr = math.cos((pan + 1) * math.pi / 4) * 1.41, math.sin((pan + 1) * math.pi / 4) * 1.41
        buf[st:e, 0] += sig[s0:s0 + e - st] * vol * gl
        buf[st:e, 1] += sig[s0:s0 + e - st] * vol * gr

    def lp(x, k):
        c = np.cumsum(np.concatenate([np.zeros(k), x]))
        return (c[k:] - c[:-k]) / k

    def hp(x, k):
        return x - lp(x, k)

    def noise(sec):
        return rng.standard_normal(int(sec * SR))

    def kick(vol=1.0):
        x = tt(0.45)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(44 + 160 * np.exp(-x * 32)) / SR) * np.exp(-x * 7) * 3.0) * vol

    def tick(vol=0.3, f0=2400):
        x = tt(0.05)
        return np.sin(2 * np.pi * f0 * x) * np.exp(-x * 120) * vol

    def clunk(vol=0.8):
        x = tt(0.6)
        return (lp(noise(0.6), 10) * 3 * np.exp(-x * 30) + np.sin(2 * np.pi * 70 * x) * np.exp(-x * 14)) * vol

    def boom(vol=0.8):
        x = tt(1.2)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(46 + 100 * np.exp(-x * 13)) / SR) * np.exp(-x * 3.5) * 3) * vol

    def whoosh(dur=0.3, vol=0.4):
        x = tt(dur)
        return hp(lp(noise(dur), 6), 40) * np.sin(np.pi * x / dur) ** 2 * vol

    def bell(vol=0.5):
        x = tt(1.4)
        return sum(np.sin(2 * np.pi * f * x) * a for f, a in ((880, 1.0), (1320, 0.5), (2210, 0.25))) * np.exp(-x * 3) * vol

    def crowd(dur=2.5, vol=0.4, swell=0.15):
        x = tt(dur)
        sig = lp(noise(dur), 10) - lp(noise(dur), 60) * 0.6
        return sig * np.minimum(x / swell, 1) * np.clip((dur - x) / 1.0, 0, 1) * vol * 2

    def drone(dur, f, vol):
        x = tt(dur)
        sig = np.sin(2 * np.pi * f * x) + 0.5 * np.sin(2 * np.pi * f * 1.5 * x) + 0.3 * np.sin(2 * np.pi * f * 2 * x)
        return lp(sig, 20) * np.minimum(x / 0.4, 1) * np.clip((dur - x) / 0.4, 0, 1) * vol

    def strike(vol=0.6):
        x = tt(0.35)
        return hp(noise(0.35), 3) * np.exp(-x * 14) * vol

    # Musik: dunkler Puls (Kick auf jedem Beat, 112 BPM) + Uhr-Ticken, das in der Geschichte schneller wird
    beat = 60 / 112
    tb = 0.0
    while tb < DUR - 0.5:
        if not (T_GOALSC - 0.2 < tb < T_GOAL):    # vor dem Tor Pause (Spannung)
            put(mus, kick(0.9), tb)
        tb += beat
    put(mus, drone(DUR, 55.0, 0.35), 0.0)
    tk, k = T_STORY, 0
    while tk < T_GOALSC:                          # tick-tack, wird schneller
        prog = (tk - T_STORY) / (T_GOALSC - T_STORY)
        put(mus, tick(0.25, 2600 if k % 2 else 1900), tk, pan=-0.3 if k % 2 else 0.3)
        tk += 0.5 - 0.32 * prog
        k += 1
    tk = T_GOALSC
    while tk < T_GOAL:                            # Sekundenzeiger vor dem Tor
        put(mus, tick(0.35, 2200), tk)
        tk += 0.22
    # Effekte
    put(sfx, clunk(0.9), 0.0)
    for i in range(8):
        put(sfx, tick(0.32, 1800 + 120 * i), T_ROLL * (i + 1) / 8 - 0.05)
    put(sfx, boom(0.6), T_ROLL)
    put(sfx, bell(0.25), T_ROLL)
    put(sfx, crowd(DUR, 0.10, 1.0), 0.0)
    put(sfx, strike(0.6), T_STRIKE)
    put(sfx, whoosh(0.3, 0.4), T_UNTIL - 0.2)
    put(sfx, boom(0.5), T_UNTIL)
    for i in range(6):
        put(sfx, tick(0.2, 2000), T_UNTIL + 0.42 * (i + 1))
    put(sfx, whoosh(0.35, 0.45), T_STORY - 0.25)
    put(sfx, clunk(0.6), T_STORY)
    put(sfx, boom(0.5), T_ZERO)
    put(sfx, boom(0.6), T_SIXTH)
    put(sfx, whoosh(0.3, 0.35), T_GOALSC - 0.15)
    put(sfx, boom(1.0), T_GOAL)
    put(sfx, crowd(1.7, 0.9, 0.08), T_GOAL)                  # Jubel klingt vor "176 minutes" ab
    put(sfx, bell(0.45), T_GOAL)
    put(sfx, bell(0.35), T_GOAL + 0.35)
    put(sfx, boom(0.35), T_STAT)
    for i in range(6):                             # Zähler-Ticks enden vor "minutes" (Wort frei lassen)
        put(sfx, tick(0.08, 3000), T_STAT + i * 0.06)
    put(sfx, whoosh(0.3, 0.4), T_CTA - 0.2)
    put(sfx, boom(0.45), T_CTA)
    put(sfx, tick(0.4, 1500), T_YN)
    put(sfx, tick(0.4, 1500), T_YN + 0.08)
    # Stimme
    voice = np.zeros(n)
    for k in VO_KEYS:
        tmp = os.path.join(HERE, f"_vo42_{k}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "voice", f"reel42_{k}.wav"),
                        "-af", f"atempo={TEMPO}", "-ar", str(SR), "-ac", "1", tmp], check=True)
        with wave.open(tmp) as w:
            v = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        os.remove(tmp)
        st = int(VO_START[k] * SR)
        e = min(n, st + len(v))
        voice[st:e] += v[: e - st]
    voice /= np.max(np.abs(voice)) + 1e-9
    kk = int(0.08 * SR)
    venv = np.convolve(np.abs(voice), np.ones(kk) / kk, mode="same")
    duck = 1 - 0.72 * np.clip(venv / 0.06, 0, 1)
    sduck = 1 - 0.45 * np.clip(venv / 0.06, 0, 1)
    mus /= np.max(np.abs(mus)) + 1e-9
    sfx /= np.max(np.abs(sfx)) + 1e-9
    mix = mus * 0.34 * duck[:, None] + sfx * 0.55 * sduck[:, None] + voice[:, None] * 1.0
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
    tts_kokoro.synth(VO_LINES, os.path.join(HERE, "voice", "reel42"), speed=1.25, fixes=FIXES)


def _frame(i):
    return compose(i / FPS, i).tobytes()


def main():
    os.chdir(HERE)
    make_audio("audio_ninth.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_ninth.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "19",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=9",
           "-ar", "44100", "-shortest", "-movflags", "+faststart", "reel42_ninth.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    with Pool(4) as pool:
        for i, fr in enumerate(pool.imap(_frame, range(nf), chunksize=4)):
            proc.stdin.write(fr)
            if i % 60 == 0:
                print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(0.9, 9999)).save("reel42_thumbnail.jpg", quality=92)
    print("fertig: reel42_ninth.mp4")


def remux():
    os.chdir(HERE)
    make_audio("audio_ninth.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "reel42_ninth.mp4", "-i", "audio_ninth.wav",
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-af",
                    "loudnorm=I=-14:TP=-1.5:LRA=9", "-ar", "44100", "-shortest", "-movflags", "+faststart",
                    "_tmp_42.mp4"], check=True)
    os.replace("_tmp_42.mp4", "reel42_ninth.mp4")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "vo":
        make_voice()
    elif len(sys.argv) > 1 and sys.argv[1] == "prev":
        preview(sys.argv[2].split(","), sys.argv[3])
    elif len(sys.argv) > 1 and sys.argv[1] == "audio":
        remux()
    else:
        main()
