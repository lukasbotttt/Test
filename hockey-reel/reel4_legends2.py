"""Reel 4: "Forgotten Legends Part 2" – echte Spielerfotos (Wikimedia Commons) + Sprecher.

Aufruf: python3 reel4_legends2.py  ->  reel4_legends2.mp4
Fakten: Datsyuk = "The Magic Man"; Forsberg = Stanley Cup 1996 + 2001, Olympia-Gold 1994 + 2006;
Selänne = 76 Tore als Rookie (1992-93, NHL-Rekord); Bure = "The Russian Rocket".
Fotos (Wikimedia Commons, Namensnennung im Video):
  Datsyuk  – Alexey Chernyadyev, CC BY-SA 3.0
  Forsberg – Håkan Dahlström, CC BY 2.0
  Selänne  – Arnold C, Attribution
  Bure     – Håkan Dahlström, CC BY 2.0
"""
import itertools
import math
import os
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import make_hockey_reel as m
import reel3_cup_day as r3
from make_hockey_reel import ICE, WHITE, GREY, W, H, clamp, ease_out_back, ease_out_cubic, paste_center, text_img

FPS = 30
HERE = m.HERE
PHOTOS = os.path.join(HERE, "photos")
r3.VOICE = os.path.join(HERE, "voice", "reel4.mp3")
SENTENCES = ["Forgotten legends, part two.",
             "Pavel Datsyuk, the Magic Man.",
             "Peter Forsberg, two Cups and two Olympic golds.",
             "Teemu Selanne, seventy-six goals as a rookie.",
             "Pavel Bure, the Russian Rocket.",
             "Now pick one.",
             "Datsyuk or Forsberg?"]
PLAYERS = [  # (Foto, Name, Fakt, Credit, Fokus-Höhe 0..1)
    ("datsyuk.jpg", "PAVEL DATSYUK", "\"THE MAGIC MAN\"", "Photo: Alexey Chernyadyev / CC BY-SA 3.0", 0.3),
    ("forsberg.jpg", "PETER FORSBERG", "2 CUPS · 2 OLYMPIC GOLDS", "Photo: Håkan Dahlström / CC BY 2.0", 0.3),
    ("selanne.jpg", "TEEMU SELÄNNE", "76 GOALS AS A ROOKIE", "Photo: Arnold C / Wikimedia Commons", 0.3),
    ("bure.jpg", "PAVEL BURE", "\"THE RUSSIAN ROCKET\"", "Photo: Håkan Dahlström / CC BY 2.0", 0.3),
]
TAIL = 2.0
SR = 44100


# ---------------------------------------------------------------- Timing
def sentence_spans(segs):
    """Wählt die Satzgrenzen unter den Pausen so, dass die Sprechdauer jedes Satzes möglichst gut
    zur Buchstabenzahl passt (bei Kommas entstehen auch Pausen, daher nicht einfach 'größte Pausen')."""
    n = len(SENTENCES)
    lens = np.array([len(s) for s in SENTENCES], float)
    lens /= lens.sum()
    total = sum(b - a for a, b in segs)
    best, best_cut = None, None
    for cut in itertools.combinations(range(len(segs) - 1), n - 1):
        bounds = [-1, *cut, len(segs) - 1]
        durs = np.array([sum(b - a for a, b in segs[bounds[i] + 1:bounds[i + 1] + 1]) for i in range(n)]) / total
        err = ((durs - lens) ** 2).sum()
        if best is None or err < best:
            best, best_cut = err, bounds
    return [(segs[best_cut[i] + 1][0], segs[best_cut[i + 1]][1]) for i in range(n)]


# ---------------------------------------------------------------- Bilder
_cover = {}


def cover(name, w, h, focus=0.3):
    key = (name, w, h)
    if key not in _cover:
        im = Image.open(os.path.join(PHOTOS, name)).convert("RGB")
        s = max(w / im.width, h / im.height) * 1.12  # Reserve für Zoom
        im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
        _cover[key] = im
    return _cover[key]


def place(frame, name, x0, y0, w, h, z, focus=0.3, darken=0.0):
    im = cover(name, w, h)
    cw, ch = int(w * 1.12 / z), int(h * 1.12 / z)
    cx = (im.width - cw) // 2
    cy = int((im.height - ch) * focus)
    crop = im.crop((cx, cy, cx + cw, cy + ch)).resize((w, h), Image.BILINEAR)
    if darken:
        crop = Image.blend(crop, Image.new("RGB", crop.size, (5, 10, 25)), darken)
    frame.paste(crop, (x0, y0))


def top_shade():
    y = np.linspace(0, 1, H)[:, None]
    a = 0.25 * np.clip(1 - y / 0.15, 0, 1) + 0.8 * np.exp(-((y - 0.68) / 0.13) ** 2) + 0.35 * np.clip((y - 0.85) / 0.15, 0, 1)
    a = np.clip(a, 0, 0.85)
    ov = Image.new("RGBA", (W, H), (5, 10, 25, 0))
    ov.putalpha(Image.fromarray((np.repeat(a, W, 1) * 255).astype(np.uint8)))
    return ov


SHADE = top_shade()


def credit(frame, txt):
    paste_center(frame, text_img(txt, 26, GREY, "SemiBold"), W / 2, H - 70)


# ---------------------------------------------------------------- Szenen
def hook(frame, lt):
    z = 1.0 + 0.25 * (1 - ease_out_cubic(lt / 0.35))
    for i, p in enumerate(PLAYERS):
        place(frame, p[0], (i % 2) * 540, (i // 2) * 960, 540, 960, z + 0.05 * lt, p[4])
    d = ImageDraw.Draw(frame)
    d.line((540, 0, 540, H), fill=(5, 10, 25), width=10)
    d.line((0, 960, W, 960), fill=(5, 10, 25), width=10)
    band = Image.new("RGBA", (W, 420), (5, 10, 25, 200))
    frame.alpha_composite(band, (0, 760))
    paste_center(frame, text_img("FORGOTTEN LEGENDS", 130, WHITE), W / 2, 880, scale=ease_out_back(lt / 0.25))
    paste_center(frame, text_img("PART 2", 150, ICE), W / 2, 1050, scale=ease_out_back((lt - 0.12) / 0.25))


def player(frame, lt, dur, p):
    name, nm, fact, cred, focus = p
    place(frame, name, 0, 0, W, H, 1.0 + 0.08 * lt / dur + (0.1 * (1 - lt / 0.12) if lt < 0.12 else 0), focus)
    frame.alpha_composite(SHADE)
    paste_center(frame, text_img(nm, 150, WHITE), W / 2, 1230, scale=ease_out_back(lt / 0.25))
    paste_center(frame, text_img(fact, 84, ICE), W / 2, 1380, scale=ease_out_back((lt - 0.2) / 0.25))
    credit(frame, cred)


def versus(frame, lt):
    place(frame, PLAYERS[0][0], 0, 0, 540, H, 1.0 + 0.04 * lt, 0.3)
    place(frame, PLAYERS[1][0], 540, 0, 540, H, 1.0 + 0.04 * lt, 0.3)
    frame.alpha_composite(SHADE)
    d = ImageDraw.Draw(frame)
    d.line((540, 0, 540, H), fill=ICE, width=8)
    pulse = 1 + 0.06 * math.sin(lt * 8)
    r = 95 * ease_out_back(lt / 0.3) * pulse
    d.ellipse((W / 2 - r, 820 - r, W / 2 + r, 820 + r), fill=(5, 10, 25), outline=ICE, width=8)
    if r > 20:
        paste_center(frame, text_img("VS", 110, WHITE), W / 2, 823, scale=clamp(r / 95))
    paste_center(frame, text_img("WHO'S BETTER?", 140, WHITE), W / 2, 1270, scale=ease_out_back(lt / 0.3))
    paste_center(frame, text_img("DATSYUK", 92, ICE), 270, 1110, scale=ease_out_back((lt - 0.3) / 0.3))
    paste_center(frame, text_img("FORSBERG", 92, ICE), 810, 1110, scale=ease_out_back((lt - 0.45) / 0.3))
    if lt > 0.9:
        p = ease_out_cubic((lt - 0.9) / 0.3)
        paste_center(frame, text_img("Comment your pick", 60, WHITE, "ExtraBold"), W / 2, 1410 + (1 - p) * 60, alpha=p)
        y = 1480 + abs(math.sin(lt * 6)) * 26
        d.polygon([(W / 2 - 36, y), (W / 2 + 36, y), (W / 2, y + 46)], fill=ICE + (255,))
    credit(frame, "Photos: A. Chernyadyev CC BY-SA 3.0 · H. Dahlström CC BY 2.0")


def build_timeline(spans, total):
    # Schnitte kurz vor jedem Satz; Satz 5+6 ("Now pick one. Datsyuk or Forsberg?") = VS-Szene
    starts = [0.0] + [max(0.0, s[0] - 0.06) for s in spans[1:5]] + [total]
    return list(zip(starts[:-1], starts[1:]))


def render(spans, total):
    shots = build_timeline(spans, total)
    nf = int(round(total * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", "audio_mix.wav", "-c:v", "libx264", "-preset", "medium",
           "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
           "-movflags", "+faststart", "reel4_legends2.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, cwd=HERE)
    for i in range(nf):
        t = i / FPS
        k = max(j for j, (a, _) in enumerate(shots) if a <= t + 1e-6)
        a, b = shots[k]
        lt = t - a
        frame = Image.new("RGBA", (W, H), (5, 10, 25, 255))
        if k == 0:
            hook(frame, lt)
        elif k <= 4:
            player(frame, lt, b - a, PLAYERS[k - 1])
        else:
            versus(frame, lt)
        if lt < 0.1 and k > 0:  # kurzer Blitz beim Schnitt
            frame.alpha_composite(Image.new("RGBA", (W, H), (220, 245, 255, int(170 * (1 - lt / 0.1)))))
        d = ImageDraw.Draw(frame)
        d.rectangle((0, H - 12, W, H), fill=(0, 0, 0, 140))
        d.rectangle((0, H - 12, int(W * t / total), H), fill=ICE + (255,))
        proc.stdin.write(frame.convert("RGB").tobytes())
        if i == 8:
            frame.convert("RGB").save(os.path.join(HERE, "reel4_thumbnail.jpg"), quality=92)
    proc.stdin.close()
    proc.wait()
    return shots


def main():
    voice = r3.load_voice()
    segs = r3.speech_segments(voice)
    spans = sentence_spans(segs)
    total = spans[-1][1] + TAIL
    print("Sätze:", [(round(a, 2), round(b, 2)) for a, b in spans], "Länge:", round(total, 2))
    shots = build_timeline(spans, total)
    bounds = [s[0] for s in shots] + [total]
    r3.mix_audio(voice, bounds, total)
    render(spans, total)
    print("fertig: reel4_legends2.mp4")


if __name__ == "__main__":
    main()
